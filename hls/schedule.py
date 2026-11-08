
"""The five schedulers: asap, alap, casap, calap and custom."""


def schedule(dag, mode, limits=None, latency=None, cycles=None) -> list[int]:
    """Return the 1-based starting step of every operation."""

    # Default duration is one clock cycle per operation.
    durations = {"add": 1, "sub": 1, "mul": 1}

    if cycles is not None:
        durations.update(cycles)

    # Every operation must take at least one cycle.
    for kind, duration in durations.items():
        if not isinstance(duration, int) or duration < 1:
            raise ValueError(f"Invalid duration for {kind}: {duration}")

    mode = mode.lower()

    if mode == "asap":
        starts = [0] * len(dag.ops)

        # Process operations in their original order.
        for i, op in enumerate(dag.ops):

            # Operations without dependencies start at step 1.
            if not dag.preds[i]:
                starts[i] = 1

            else:
                # Find when the latest predecessor finishes.
                earliest = 1

                for p in dag.preds[i]:
                    predecessor = dag.ops[p]

                    finish = (
                        starts[p]
                        + durations[predecessor.kind]
                    )

                    earliest = max(earliest, finish)

                starts[i] = earliest

        return starts

    
    if mode == "casap":
        limits = {} if limits is None else limits

        # Validate the available hardware resources.
        for kind, count in limits.items():
            if kind not in durations:
                raise ValueError(f"Unknown resource type: {kind}")
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"Invalid resource limit for {kind}: {count}")

        n = len(dag.ops)
        starts = [0] * n
        remaining = n
        step = 1

        # Tracks occupied hardware for each clock step.
        usage = {}

        while remaining > 0:

            # Check operations in original equation order.
            for i, op in enumerate(dag.ops):

                # Skip operations already scheduled.
                if starts[i] != 0:
                    continue

                # All predecessors must have finished.
                ready = all(
                    starts[p] != 0
                    and starts[p] + durations[dag.ops[p].kind] <= step
                    for p in dag.preds[i]
                )

                if not ready:
                    continue

                kind = op.kind
                duration = durations[kind]
                limit = limits.get(kind)

                # Check resource availability for every
                # step occupied by this operation.
                available = True

                if limit is not None:
                    for t in range(step, step + duration):
                        used = usage.get(t, {}).get(kind, 0)

                        if used >= limit:
                            available = False
                            break

                if not available:
                    continue

                # Schedule the operation.
                starts[i] = step
                remaining -= 1

                # Reserve its hardware for its full duration.
                for t in range(step, step + duration):
                    if t not in usage:
                        usage[t] = {}

                    usage[t][kind] = usage[t].get(kind, 0) + 1

            step += 1

        return starts

    if mode == "alap":
        # First calculate the minimum possible latency.
        earliest = schedule(dag, "asap", cycles=durations)

        minimum_latency = max(
            (
                earliest[i] + durations[op.kind] - 1
                for i, op in enumerate(dag.ops)
            ),
            default=0
        )

        # If no latency is specified, use the ASAP latency.
        if latency is None:
            latency = minimum_latency

        if latency < minimum_latency:
            raise ValueError(
                f"Latency {latency} is shorter than "
                f"the minimum possible latency {minimum_latency}"
            )

        starts = [0] * len(dag.ops)

        # Process operations backward through the DAG.
        for i in range(len(dag.ops) - 1, -1, -1):
            op = dag.ops[i]
            duration = durations[op.kind]

            if not dag.succs[i]:
                # Independent terminal operations finish at latency.
                starts[i] = latency - duration + 1
            else:
                # Must finish before the earliest successor begins.
                latest_successor = min(
                    starts[s] for s in dag.succs[i]
                )

                starts[i] = latest_successor - duration

        return starts

    if mode == "calap":
        limits = {} if limits is None else limits

        # Validate resource limits.
        for kind, count in limits.items():
            if kind not in durations:
                raise ValueError(f"Unknown resource type: {kind}")
            if not isinstance(count, int) or count < 1:
                raise ValueError(f"Invalid resource limit for {kind}: {count}")

        n = len(dag.ops)

        # ASAP times determine backward scheduling priority.
        asap_starts = schedule(dag, "asap", cycles=durations)

        # Reverse-time starting steps.
        reverse_starts = [0] * n
        remaining = n
        step = 1
        usage = {}

        # Larger ASAP times have higher priority.
        # Original equation order breaks ties.
        priority = sorted(
            range(n),
            key=lambda i: (-asap_starts[i], i)
        )

        while remaining > 0:

            for i in priority:
                if reverse_starts[i] != 0:
                    continue

                # In reverse time, successors must finish first.
                ready = all(
                    reverse_starts[s] != 0
                    and reverse_starts[s]
                        + durations[dag.ops[s].kind] <= step
                    for s in dag.succs[i]
                )

                if not ready:
                    continue

                kind = dag.ops[i].kind
                duration = durations[kind]
                limit = limits.get(kind)

                available = True

                if limit is not None:
                    for t in range(step, step + duration):
                        used = usage.get(t, {}).get(kind, 0)

                        if used >= limit:
                            available = False
                            break

                if not available:
                    continue

                # Place this operation in reverse time.
                reverse_starts[i] = step
                remaining -= 1

                # Reserve its unit for the entire duration.
                for t in range(step, step + duration):
                    if t not in usage:
                        usage[t] = {}

                    usage[t][kind] = usage[t].get(kind, 0) + 1

            step += 1

        # Total length of the backward schedule.
        total_length = max(
            (
                reverse_starts[i] + durations[op.kind] - 1
                for i, op in enumerate(dag.ops)
            ),
            default=0
        )

        if latency is None:
            latency = total_length

        if latency < total_length:
            raise ValueError(
                f"Resource limits require {total_length} steps, "
                f"but latency is {latency}"
            )

        # Mirror reverse-time starts into forward-time starts.
        starts = [
            latency - reverse_starts[i]
            - durations[op.kind] + 2
            for i, op in enumerate(dag.ops)
        ]

        return starts

    if mode == "custom":
        from itertools import product

        # Determine the minimum possible latency.
        asap_starts = schedule(dag, "asap", cycles=durations)

        minimum_latency = max(
            (
                asap_starts[i] + durations[op.kind] - 1
                for i, op in enumerate(dag.ops)
            ),
            default=0
        )

        if latency is None:
            latency = minimum_latency

        if latency < minimum_latency:
            raise ValueError(
                f"Latency {latency} is shorter than "
                f"the minimum possible latency {minimum_latency}"
            )

        # Count how many operations use each hardware type.
        counts = {
            kind: sum(op.kind == kind for op in dag.ops)
            for kind in ("add", "sub", "mul")
        }

        # Each used type needs at least one unit.
        # Unused types need zero units.
        ranges = [
            range(1, counts[kind] + 1)
            if counts[kind] > 0 else (0,)
            for kind in ("add", "sub", "mul")
        ]

        budgets = []

        for add, sub, mul in product(*ranges):
            budgets.append({
                "add": add,
                "sub": sub,
                "mul": mul
            })

        # Fewest total units first.
        # Then fewest multipliers, then fewest adders.
        budgets.sort(
            key=lambda b: (
                sum(b.values()),
                b["mul"],
                b["add"]
            )
        )

        for budget in budgets:
            active_limits = {
                kind: count
                for kind, count in budget.items()
                if count > 0
            }

            for candidate_mode in ("casap", "calap"):

                try:
                    candidate = schedule(
                        dag,
                        candidate_mode,
                        limits=active_limits,
                        latency=latency if candidate_mode == "calap" else None,
                        cycles=durations
                    )
                except ValueError:
                    continue

                finish = max(
                    (
                        candidate[i] + durations[op.kind] - 1
                        for i, op in enumerate(dag.ops)
                    ),
                    default=0
                )

                if finish <= latency:
                    return candidate

        raise ValueError(
            f"No schedule found within latency {latency}"
        )


    raise NotImplementedError(
        f"Scheduling mode '{mode}' is not implemented yet"
    )
