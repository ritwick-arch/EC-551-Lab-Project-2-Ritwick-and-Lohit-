
from hls.ir import DAG, Op
from hls.schedule import schedule


def test_asap():
    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "mul", "X_1", "C", 2),
        Op(2, "Z_1", "add", "D", "E", 3),
    ]

    dag = DAG(
        ops,
        [[], [0], []],
        [[1], [], []]
    )

    result = schedule(dag, "asap")

    assert result == [1, 2, 1]


def test_alap():
    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "mul", "X_1", "C", 2),
        Op(2, "Z_1", "add", "D", "E", 3),
    ]

    dag = DAG(
        ops,
        [[], [0], []],
        [[1], [], []]
    )

    result = schedule(dag, "alap", latency=4)

    assert result == [3, 4, 4]

def test_casap():
    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "add", "C", "D", 2),
        Op(2, "Z_1", "mul", "E", "F", 3),
        Op(3, "Q_1", "add", "X_1", "Y_1", 4),
    ]

    dag = DAG(
        ops,
        [[], [], [], [0, 1]],
        [[3], [3], [], []]
    )

    result = schedule(
        dag, "casap",
        limits={"add": 1, "mul": 1}
    )

    assert result == [1, 2, 1, 3]


def test_calap():
    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "add", "C", "D", 2),
        Op(2, "Z_1", "mul", "X_1", "Y_1", 3),
    ]

    dag = DAG(
        ops,
        [[], [], [0, 1]],
        [[2], [2], []]
    )

    result = schedule(
        dag, "calap",
        limits={"add": 1, "mul": 1}
    )

    assert sorted(result[:2]) == [1, 2]
    assert result[2] == 3


def test_custom():
    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "add", "C", "D", 2),
        Op(2, "Z_1", "add", "E", "F", 3),
    ]

    dag = DAG(ops, [[], [], []], [[], [], []])

    for latency, expected_adders in [(1, 3), (2, 2), (3, 1)]:
        result = schedule(dag, "custom", latency=latency)

        actual_adders = max(result.count(t) for t in result)

        assert max(result) <= latency
        assert actual_adders == expected_adders

def test_random_schedules():
    import random

    rng = random.Random(551)

    for case in range(200):
        n = rng.randint(1, 12)

        ops = []
        preds = []
        succs = [[] for _ in range(n)]

        # Generate a random DAG in equation order.
        for i in range(n):
            kind = rng.choice(["add", "sub", "mul"])

            available = list(range(i))
            dependencies = sorted(
                rng.sample(
                    available,
                    rng.randint(0, min(2, i))
                )
            )

            ops.append(
                Op(i, f"X_{i}", kind, "A", "B", i + 1)
            )
            preds.append(dependencies)

            for p in dependencies:
                succs[p].append(i)

        dag = DAG(ops, preds, succs)

        cycles = {
            kind: rng.randint(1, 3)
            for kind in ("add", "sub", "mul")
        }

        limits = {
            kind: rng.randint(1, 3)
            for kind in ("add", "sub", "mul")
        }

        def finish(starts):
            return max(
                starts[i] + cycles[op.kind] - 1
                for i, op in enumerate(ops)
            )

        def validate(starts, resource_limits=None):
            assert len(starts) == n
            assert all(
                isinstance(s, int) and s >= 1
                for s in starts
            )

            # Every dependency must be respected.
            for i in range(n):
                for p in preds[i]:
                    assert (
                        starts[i]
                        >= starts[p] + cycles[ops[p].kind]
                    ), f"Dependency failed in case {case}"

            # Check occupied units at every step.
            if resource_limits is not None:
                for step in range(1, finish(starts) + 1):
                    for kind, limit in resource_limits.items():
                        busy = sum(
                            op.kind == kind
                            and starts[i] <= step
                            < starts[i] + cycles[kind]
                            for i, op in enumerate(ops)
                        )

                        assert busy <= limit, (
                            f"Resource conflict in case {case}"
                        )

        asap = schedule(dag, "asap", cycles=cycles)
        validate(asap)
        minimum = finish(asap)

        alap = schedule(
            dag, "alap",
            latency=minimum + 2,
            cycles=cycles
        )
        validate(alap)
        assert finish(alap) <= minimum + 2

        casap = schedule(
            dag, "casap",
            limits=limits,
            cycles=cycles
        )
        validate(casap, limits)

        calap = schedule(
            dag, "calap",
            limits=limits,
            cycles=cycles
        )
        validate(calap, limits)

        # With no limits, forward scheduling matches ASAP.
        assert schedule(
            dag, "casap", cycles=cycles
        ) == asap

        # With no limits, backward scheduling matches ALAP.
        assert schedule(
            dag, "calap",
            latency=minimum + 2,
            cycles=cycles
        ) == alap

        # Custom scheduling must find a feasible result.
        custom = schedule(
            dag, "custom",
            latency=minimum + 2,
            cycles=cycles
        )
        validate(custom)
        assert finish(custom) <= minimum + 2

def test_scheduler_errors():
    import pytest

    ops = [
        Op(0, "X_1", "add", "A", "B", 1),
        Op(1, "Y_1", "mul", "X_1", "C", 2),
    ]

    dag = DAG(
        ops,
        [[], [0]],
        [[1], []]
    )

    # ALAP cannot finish before the critical path.
    with pytest.raises(ValueError):
        schedule(dag, "alap", latency=1)

    # Custom cannot meet impossible latency.
    with pytest.raises(ValueError):
        schedule(dag, "custom", latency=1)

    # CASAP rejects zero hardware units.
    with pytest.raises(ValueError):
        schedule(dag, "casap", limits={"add": 0})

    # CALAP rejects negative hardware limits.
    with pytest.raises(ValueError):
        schedule(dag, "calap", limits={"mul": -1})

    # Operations cannot take zero clock cycles.
    with pytest.raises(ValueError):
        schedule(dag, "asap", cycles={"mul": 0})
