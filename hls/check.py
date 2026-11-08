"""Check a schedule against D's timing rules before any Verilog is written."""

KINDS = ("add", "sub", "mul")
MAX_STEPS = 254     # the state shows as 2 hex digits and DONE is L+1


def last_step(op, start, cycles):
    return start + cycles[op.kind] - 1


def length(dag, steps, cycles):
    """The schedule's latency: the last step any op holds."""
    return max(last_step(op, s, cycles) for op, s in zip(dag.ops, steps))


def unit_counts(dag, steps, cycles):
    """Most ops of each type running in one step, for the types the program uses."""
    counts = {}
    for kind in KINDS:
        spans = [(s, last_step(op, s, cycles)) for op, s in zip(dag.ops, steps) if op.kind == kind]
        if spans:
            counts[kind] = max(sum(a <= t <= b for a, b in spans) for t in range(1, max(b for _, b in spans) + 1))
    return counts


def check_schedule(dag, steps, cycles, limits=None, latency=None):
    """Return the latency; raise ValueError if the schedule breaks a dependency, a limit or a bound."""
    if len(steps) != len(dag.ops) or not all(type(s) is int and s >= 1 for s in steps):
        raise ValueError(f"schedule check failed: bad start steps {steps}")
    total = length(dag, steps, cycles)
    if total > MAX_STEPS:
        raise ValueError(f"the schedule takes {total} steps; the state display fits at most {MAX_STEPS}")
    for i, op in enumerate(dag.ops):
        for p in dag.preds[i]:
            ready = last_step(dag.ops[p], steps[p], cycles) + 1
            if steps[i] < ready:
                raise ValueError(f"schedule check failed: line {op.line} starts in step {steps[i]}, "
                                 f"before {dag.ops[p].dst} is ready in step {ready}")
    for kind, n in unit_counts(dag, steps, cycles).items():
        if limits and kind in limits and n > limits[kind]:
            raise ValueError(f"schedule check failed: {n} {kind} units busy at once, over the limit {limits[kind]}")
    if latency is not None and total > latency:
        raise ValueError(f"schedule check failed: it takes {total} steps, over --latency {latency}")
    return total
