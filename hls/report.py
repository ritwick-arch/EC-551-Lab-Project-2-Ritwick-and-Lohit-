"""Plain-ASCII sections of the run report."""
from .datapath import SLOTS


def _table(rows):
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  " + "  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows)


def summary(path, program):
    outputs = ", ".join(f"{v} = {name}" for v, name in program.outputs)
    return (f"hls: {path} ({len(program.ops)} equations)\n"
            f"inputs:  {', '.join(program.inputs) or '(none)'}\n"
            f"outputs: {outputs}")


def ssa_section(program):
    return "SSA\n" + "\n".join(f"  {op.text()}" for op in program.ops)


def dag_section(dag):
    rows = [("line", "statement", "depends on")]
    for op, preds in zip(dag.ops, dag.preds):
        rows.append((str(op.line), op.text(), ", ".join(dag.ops[p].dst for p in preds) or "-"))
    return "DAG\n" + _table(rows)


NOUN = {"add": "adder", "sub": "subtractor", "mul": "multiplier"}


def _hex(v, digits=2):
    return f"{v:0{digits}X}"


def _slot(n):
    return SLOTS[n] if n < len(SLOTS) else "no slot"


def _count(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def board_section(design):
    rows = []
    for n, x in enumerate(design.slots):
        if n < len(SLOTS):
            rows.append((SLOTS[n], x))
        else:
            rows.append(("no slot", f"{x}: hardcode it with --set {x[:-2]}=VALUE"))
    rows += [(SLOTS[n], "unused") for n in range(len(design.slots), len(SLOTS))]
    rows += [("--set", f"{x} = {v}") for x, v in design.fixed.items()]
    rows += [("SW15-12", "observe code within the page; BTNU next page, BTNC step, CPU_RESETN reset")]
    return "board\n" + _table(rows)


def schedule_section(design, heading):
    ops, units = design.dag.ops, design.units
    rows = [("step",) + tuple(u.name for u in units)]
    for t in range(1, design.latency + 1):
        cells = ["."] * len(units)
        for u, i in design.running(t):
            n = design.cycles[ops[i].kind]
            cells[u] = ops[i].text() + (f" ({t - design.steps[i] + 1}/{n})" if n > 1 else "")
        rows.append((_hex(t),) + tuple(cells))
    counts = ", ".join(_count(sum(u.kind == k for u in units), NOUN[k]) for k in NOUN if any(u.kind == k for u in units))
    return (f"schedule ({heading})\n" + _table(rows) + "\n"
            f"latency {_count(design.latency, 'step')}, {design.latency + 1} presses to DONE; units: {counts}")


def codes_section(design):
    outputs = {name: var for var, name in design.program.outputs}
    rows = [("code", "page", "SW15-12", "shows")]
    for n, (kind, name) in enumerate(design.codes):
        if kind == "unit":
            what = f"{name} output (---- when idle)"
        elif kind == "result":
            what = name + (f" (output {outputs[name]})" if name in outputs else "")
        else:
            what = f"{name} ({SLOTS[design.slots.index(name)]})"
        rows.append((_hex(n), str(n // 16), _hex(n % 16, 1), what))
    return "observe codes (code = 16 x page + SW15-12, in hex as the display shows it)\n" + _table(rows)


def eval_section(design, values):
    given = ", ".join(f"{x} = {values[x]} ({_slot(n)})" for n, x in enumerate(design.slots)) or "no switch inputs"
    rows = [("code", "value", "hex", "dec")]
    for n, (kind, name) in enumerate(design.codes):
        if kind != "unit":
            rows.append((_hex(n), name, _hex(values[name], 4), str(values[name])))
    ops, units = design.dag.ops, design.units
    grid = [("step",) + tuple(u.name for u in units)]
    for t in range(1, design.latency + 1):
        cells = ["----"] * len(units)
        for u, i in design.running(t):
            v = values[ops[i].dst]
            cells[u] = f"{_hex(v, 4)} ({v})"
        grid.append((_hex(t),) + tuple(cells))
    return (f"eval: {given}\n"
            f"at DONE (state {_hex(design.latency + 1)}):\n" + _table(rows) + "\n"
            "each unit while the display shows that step (---- = idle):\n" + _table(grid))
