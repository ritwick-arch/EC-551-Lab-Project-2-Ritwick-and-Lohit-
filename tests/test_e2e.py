"""End to end (J): generate Verilog, simulate it in Icarus, and lint it. Skipped where the tools are missing.

On SCC: module load yosys/0.48 (Icarus and Yosys). For the lint test also set VERILATOR to the verilator_bin path.
"""
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from hls.check import length
from hls.cli import main
from hls.dag import build_dag
from hls.datapath import build_design, evaluate
from hls.parser import parse_file
from hls.schedule import schedule
from hls.ssa import to_ssa

ROOT = Path(__file__).resolve().parents[1]
RTL = [str(ROOT / "rtl" / f) for f in ("adder.v", "subtractor.v", "multiplier.v")]
EXAMPLES = sorted(p for p in ROOT.glob("examples/*/*.txt") if p.parent.name != "errors" and not p.name.endswith(".ssa.txt"))
ONE = ["--add", "1", "--sub", "1", "--mul", "1"]
IVERILOG = shutil.which("iverilog")
VERILATOR = os.environ.get("VERILATOR") or shutil.which("verilator")
YOSYS = shutil.which("yosys")
needs_iverilog = pytest.mark.skipif(IVERILOG is None, reason="needs Icarus Verilog (on SCC: module load yosys/0.48)")

TRACE = """`timescale 1ns/1ps
module trace;
    reg clk = 1'b0, rst = 1'b1, step = 1'b0;
    reg [11:0] sw = 12'h{sw:03x};
    reg [5:0] code = 6'd0;
    wire [15:0] value;
    wire valid, done;
    wire [7:0] state;
    hls_core dut (.clk(clk), .rst(rst), .step(step), .sw(sw), .code(code),
                  .value(value), .valid(valid), .state(state), .done(done));
    always #5 clk = ~clk;
    integer n, c;
    initial begin
        @(negedge clk) rst = 1'b0;
        @(negedge clk);
        for (n = 0; n <= {presses}; n = n + 1) begin
            for (c = 0; c < 64; c = c + 1) begin
                code = c;
                #1 $display("%0d %0d %0d %b %0d", n, state, c, valid, value);
            end
            @(negedge clk) step = 1'b1;
            @(negedge clk) step = 1'b0;
        end
        $finish;
    end
endmodule
"""


def _sim(folder, bench):
    vvp = folder / f"{Path(bench).stem}.vvp"
    subprocess.run([IVERILOG, "-g2005", "-o", str(vvp), *RTL, str(folder / "hls_core.v"), str(folder / bench)],
                   check=True, capture_output=True)
    return subprocess.run(["vvp", "-n", str(vvp)], check=True, capture_output=True, text=True).stdout


def _flags(path, mode, mul):
    """Tight limits for the constrained modes, a looser latency for alap and custom, --set for inputs past 3."""
    program = to_ssa(parse_file(path))
    cycles = {"add": 1, "sub": 1, "mul": mul}
    dag = build_dag(program.ops)
    flags = ["--schedule", mode, "--mul-cycles", str(mul)]
    if mode in ("casap", "calap"):
        flags += ONE
    if mode in ("alap", "custom"):
        flags += ["--latency", str(length(dag, schedule(dag, "asap", cycles=cycles), cycles) + 1)]
    extra = program.inputs[3:]
    if extra:
        flags += ["--set"] + [f"{x[:-2]}={n + 1}" for n, x in enumerate(extra)]
    return flags


def _check(tmp_path, path, flags, sw):
    """Generate, expect PASS from testbench.v, and compare every code in every state with the --eval model."""
    out = tmp_path / "out"
    assert main([str(path), *flags, "--out", str(out)]) == 0
    log = _sim(out, "testbench.v")
    assert "PASS 4096/4096" in log, log
    program = to_ssa(parse_file(path))
    dag = build_dag(program.ops)
    args = dict(zip(flags[::2], flags[1::2]))
    cycles = {"add": 1, "sub": 1, "mul": int(args.get("--mul-cycles", 1))}
    limits = {k: int(args[f"--{k}"]) for k in cycles if f"--{k}" in args}
    latency = int(args["--latency"]) if "--latency" in args else None
    fixed = {}
    if "--set" in flags:
        fixed = {a.split("=")[0]: int(a.split("=")[1]) for a in flags[flags.index("--set") + 1:]}
    design = build_design(program, dag, schedule(dag, flags[1], limits, latency, cycles), cycles, fixed)
    digits = [(sw >> 8) & 15, (sw >> 4) & 15, sw & 15]
    values = evaluate(design, {x: digits[n] for n, x in enumerate(design.slots)})
    (out / "trace.v").write_text(TRACE.replace("{sw:03x}", f"{sw:03x}").replace("{presses}", str(design.latency + 2)))
    names = [u.name for u in design.units]
    for line in _sim(out, "trace.v").splitlines():
        fields = line.split()
        if len(fields) != 5:
            continue
        n, state, c, valid, value = map(int, fields)
        s = min(n, design.latency + 1)
        want = (0, None)
        if c < len(design.codes):
            kind, name = design.codes[c]
            if kind == "unit":
                ops = [i for u, i in design.running(s) if names[u] == name] if 1 <= s <= design.latency else []
                want = (1, values[dag.ops[ops[0]].dst]) if ops else (0, None)
            elif kind == "result":
                i = next(i for i, op in enumerate(dag.ops) if op.dst == name)
                want = (1, values[name]) if s > design.last(i) else (0, None)
            else:
                want = (1, values[name])
        assert state == s and valid == want[0] and (not valid or value == want[1]), (line, want)


@needs_iverilog
@pytest.mark.parametrize("mul", [1, 2])
@pytest.mark.parametrize("mode", ["asap", "alap", "casap", "calap", "custom"])
@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example(tmp_path, capsys, path, mode, mul):
    _check(tmp_path, path, _flags(path, mode, mul), sw=0x5A3)


@needs_iverilog
@pytest.mark.parametrize("seed", range(24))
def test_random_program(tmp_path, capsys, random_program, seed):
    rng = random.Random(seed)
    path = tmp_path / "eq.txt"
    path.write_text(random_program(rng))
    mode = ["asap", "alap", "casap", "calap", "custom"][seed % 5]
    _check(tmp_path, path, _flags(path, mode, 1 + seed % 2), sw=rng.randrange(4096))


COMMITTED = sorted(ROOT.glob("examples/*/*/hls_core.v"))


@pytest.mark.skipif(VERILATOR is None, reason="needs Verilator (set VERILATOR to verilator_bin)")
@pytest.mark.parametrize("core", COMMITTED, ids=[f"{p.parent.parent.name}-{p.parent.name}" for p in COMMITTED])
def test_lint(core):
    r = subprocess.run([VERILATOR, "--lint-only", "-Wall", *RTL, str(core), "--top-module", "hls_core"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and not r.stderr.strip(), r.stderr


@pytest.mark.skipif(YOSYS is None, reason="needs Yosys (on SCC: module load yosys/0.48)")
@pytest.mark.parametrize("core", COMMITTED, ids=[f"{p.parent.parent.name}-{p.parent.name}" for p in COMMITTED])
def test_no_latches(core):
    script = f"read_verilog {' '.join(RTL)} {core}; synth -top hls_core; select -assert-none t:$dlatch t:$_DLATCH_*"
    r = subprocess.run([YOSYS, "-q", "-p", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
