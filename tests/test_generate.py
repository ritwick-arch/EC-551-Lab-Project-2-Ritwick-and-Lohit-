import importlib.util
import random
from pathlib import Path

import pytest

from hls.check import check_schedule, unit_counts
from hls.cli import main
from hls.dag import build_dag
from hls.datapath import bind, build_design, evaluate
from hls.parser import parse_text
from hls.schedule import schedule
from hls.ssa import to_ssa

ROOT = Path(__file__).resolve().parents[1]
ONE = {"add": 1, "sub": 1, "mul": 1}
SPEC = "X = A + B\nY = X + A\nZ = X - B\nQ = B * Z\n"


def design_of(text, mode="asap", limits=None, latency=None, cycles=ONE, fixed=None):
    program = to_ssa(parse_text(text))
    dag = build_dag(program.ops)
    steps = schedule(dag, mode, limits, latency, cycles)
    check_schedule(dag, steps, cycles, limits, latency)
    return build_design(program, dag, steps, cycles, fixed or {})


def run(tmp_path, text, *flags):
    src = tmp_path / "eq.txt"
    src.write_text(text)
    return main([str(src), *flags])


def test_spec_datapath():
    d = design_of(SPEC)
    assert [(u.name, u.ops) for u in d.units] == [("add0", [0, 1]), ("sub0", [2]), ("mul0", [3])]
    assert d.units[0].ports == (["A_0", "X_1"], ["B_0", "A_0"])
    assert d.units[1].ports == (["X_1"], ["B_0"]) and d.units[2].ports == (["B_0"], ["Z_1"])
    assert d.codes == [("unit", "add0"), ("unit", "sub0"), ("unit", "mul0"), ("result", "X_1"), ("result", "Y_1"),
                       ("result", "Z_1"), ("result", "Q_1"), ("input", "A_0"), ("input", "B_0")]


def test_set_inputs_become_constants():
    d = design_of("X = A + C\nY = C * B\n", fixed={"C": 7})
    assert d.slots == ["A_0", "B_0"] and d.fixed == {"C_0": 7}
    assert [u.ports for u in d.units] == [(["A_0"], [7]), ([7], ["B_0"])]


def test_binding_uses_the_fewest_units(random_program):
    rng = random.Random(1)
    for _ in range(1000):
        program = to_ssa(parse_text(random_program(rng)))
        dag = build_dag(program.ops)
        cycles = {k: rng.randint(1, 3) for k in ONE}
        mode = rng.choice(["asap", "alap", "casap", "calap", "custom"])
        limits = {k: rng.randint(1, 3) for k in ONE} if mode in ("casap", "calap") else None
        steps = schedule(dag, mode, limits, None, cycles)
        units, unit_of = bind(dag, steps, cycles)
        counts = {k: sum(u.kind == k for u in units) for k in ONE}
        assert {k: n for k, n in counts.items() if n} == unit_counts(dag, steps, cycles)
        for u, unit in enumerate(units):
            spans = [(steps[i], steps[i] + cycles[dag.ops[i].kind] - 1) for i in unit.ops]
            assert all(unit_of[i] == u and dag.ops[i].kind == unit.kind for i in unit.ops)
            assert all(a[1] < b[0] for a, b in zip(spans, spans[1:]))


def test_evaluate_wraps_like_the_hardware():
    d = design_of("X = A - B\nY = 65535 + A\nZ = 300 * 300\n")
    v = evaluate(d, {"A_0": 1, "B_0": 2})
    assert (v["X_1"], v["Y_1"], v["Z_1"]) == (65535, 0, 90000 % 65536)


@pytest.mark.parametrize("steps, message", [
    ([1, 1, 2, 3], "line 2 starts in step 1, before X_1 is ready in step 2"),
    ([1, 2, 2, 2], "line 4 starts in step 2, before Z_1 is ready in step 3"),
])
def test_check_catches_broken_dependencies(steps, message):
    dag = build_dag(to_ssa(parse_text(SPEC)).ops)
    with pytest.raises(ValueError, match="^schedule check failed: " + message):
        check_schedule(dag, steps, ONE)


def test_check_catches_limits_and_bounds():
    dag = build_dag(to_ssa(parse_text("X = A + B\nY = A + C\n")).ops)
    with pytest.raises(ValueError, match="2 add units busy at once, over the limit 1"):
        check_schedule(dag, [1, 1], ONE, {"add": 1})
    with pytest.raises(ValueError, match="it takes 2 steps, over --latency 1"):
        check_schedule(dag, [1, 2], ONE, latency=1)


def test_too_many_steps(tmp_path):
    with pytest.raises(SystemExit, match="^error: the schedule takes 400 steps; the state display fits at most 254"):
        run(tmp_path, "X = A * B\nY = X * A\n", "--mul-cycles", "200")


def test_too_many_inputs(tmp_path, capsys):
    text = "X = A + B\nY = C + D\nZ = X * E\n"
    assert run(tmp_path, text) == 0
    assert "  no slot  D_0: hardcode it with --set D=VALUE" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="^error: 5 inputs need switches but there are 3 slots: hardcode D, E with"):
        run(tmp_path, text, "--out", str(tmp_path / "out"))
    assert not (tmp_path / "out").exists()
    assert run(tmp_path, text, "--set", "D=9", "E=1", "--out", str(tmp_path / "out")) == 0
    assert "16'd9" in (tmp_path / "out" / "hls_core.v").read_text()


def test_eval_output(tmp_path, capsys):
    assert run(tmp_path, SPEC, "--eval", "A=3", "B=4") == 0
    out = capsys.readouterr().out
    assert "eval: A_0 = 3 (SW11-8), B_0 = 4 (SW7-4)" in out
    assert "  06    Q_1    000C  12" in out
    assert "  02    000A (10)  0003 (3)  ----" in out


@pytest.mark.parametrize("flags, message", [
    (["--eval", "A=3"], "--eval: no value for B (SW7-4)"),
    (["--eval", "A=3", "B=16"], "--eval B=16: switch inputs are one hex digit (0-15)"),
    (["--set", "B=5", "--eval", "A=1", "B=2"], "--eval B: B is hardcoded with --set B=5"),
])
def test_eval_errors(tmp_path, flags, message):
    with pytest.raises(SystemExit, match="^error: " + message.replace("(", r"\(").replace(")", r"\)")):
        run(tmp_path, SPEC, *flags)


def test_custom_says_which_mode_found_it(tmp_path, capsys):
    run(tmp_path, "X = C + A\nY = B + A\nZ = Y * A\nW = C - B\nV = X * Y\n", "--schedule", "custom", "--latency", "3")
    assert "schedule (custom, fewest units that end by step 3, found with casap)" in capsys.readouterr().out


def test_multi_step_ops_in_the_grid(tmp_path, capsys):
    run(tmp_path, "P = A * B\nQ = C * D\nR = P + Q\n", "--schedule", "casap", "--mul", "1", "--mul-cycles", "2")
    out = capsys.readouterr().out
    assert "  02    .                P_1 = A_0 * B_0 (2/2)" in out
    assert "latency 5 steps, 6 presses to DONE; units: 1 adder, 1 multiplier" in out


def test_outputs_are_byte_identical_on_rerun(tmp_path):
    out = tmp_path / "out"
    run(tmp_path, SPEC, "--schedule", "calap", "--add", "1", "--out", str(out))
    first = {f: (out / f).read_bytes() for f in ("hls_core.v", "testbench.v", "schedule.txt")}
    run(tmp_path, SPEC, "--schedule", "calap", "--add", "1", "--out", str(out))
    assert first == {f: (out / f).read_bytes() for f in first}
    assert first["schedule.txt"].startswith(f"# python -m hls {tmp_path / 'eq.txt'} --schedule calap --add 1".encode())
    assert all(b"\r" not in data and data.isascii() for data in first.values())


def _runs():
    spec = importlib.util.spec_from_file_location("make_examples", ROOT / "scripts" / "make_examples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RUNS


@pytest.mark.parametrize("name, mode, flags", _runs())
def test_committed_examples_are_current(tmp_path, monkeypatch, capsys, name, mode, flags):
    monkeypatch.chdir(ROOT)
    out = tmp_path / mode
    assert main([f"examples/{name}/{name}.txt", "--schedule", mode, *flags, "--out", str(out)]) == 0
    folder = ROOT / "examples" / name / mode
    for f in ("hls_core.v", "testbench.v"):
        assert (out / f).read_text() == (folder / f).read_text(), f"rerun scripts/make_examples.py: {name}/{mode}/{f}"
    fresh, committed = ((p / "schedule.txt").read_text().split("\n", 1)[1] for p in (out, folder))
    assert fresh == committed
    assert "PASS 4096/4096" in (folder / "sim.log").read_text()
