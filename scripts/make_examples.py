"""Regenerate every example's committed output: python scripts/make_examples.py

On SCC, run `module load yosys/0.48` first so each run also gets an Icarus sim.log.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONE = ["--add", "1", "--sub", "1", "--mul", "1"]
# (example, mode, flags): each run is written to examples/<example>/<mode>/.
RUNS = [
    ("spec", "asap", []),
    ("five", "asap", []),
    ("five", "alap", []),
    ("five", "casap", ONE),
    ("five", "calap", ONE),
    ("five", "custom", ["--latency", "3"]),
    ("reassign", "casap", ["--mul", "1", "--mul-cycles", "2"]),
    ("constant", "alap", ["--latency", "4"]),
    ("twenty", "casap", ["--add", "2", "--sub", "1", "--mul", "2", "--set", "D=1000"]),
    ("overflow", "asap", []),
]
RTL = ["adder.v", "subtractor.v", "multiplier.v"]


def hls(*args):
    return subprocess.run([sys.executable, "-m", "hls", *args], cwd=ROOT, capture_output=True, text=True)


def simulate(folder):
    """Compile with paths relative to the run folder, so the log reads the same on any machine."""
    rtl = [f"../../../rtl/{f}" for f in RTL]
    subprocess.run(["iverilog", "-g2005", "-o", "sim.vvp", *rtl, "hls_core.v", "testbench.v"], cwd=folder, check=True)
    log = subprocess.run(["vvp", "-n", "sim.vvp"], cwd=folder, capture_output=True, text=True, check=True).stdout
    (folder / "sim.vvp").unlink()
    (folder / "sim.log").write_text(log, encoding="utf-8", newline="\n")
    return log.splitlines()[0]


def main():
    sim = shutil.which("iverilog") is not None
    for name, mode, flags in RUNS:
        out = f"examples/{name}/{mode}"
        r = hls(f"examples/{name}/{name}.txt", "--schedule", mode, *flags,
                "--export-ssa", f"examples/{name}/{name}.ssa.txt", "--out", out)
        if r.returncode:
            sys.exit(f"{out}: {r.stderr.strip()}")
        print(f"{out}: {simulate(ROOT / out) if sim else 'generated (no iverilog, so no sim.log)'}")
    r = hls("examples/errors/bad.txt")
    (ROOT / "examples/errors/error.txt").write_text(r.stderr, encoding="utf-8", newline="\n")
    print(f"examples/errors: {r.stderr.strip()}")


if __name__ == "__main__":
    main()
