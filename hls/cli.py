"""Command line: python -m hls FILE [options]."""
import argparse
import re
import sys
from pathlib import Path

from .dag import build_dag
from .ir import MASK
from .parser import parse_file
from .report import dag_section, ssa_section, summary
from .schedule import schedule
from .ssa import ssa_text, to_ssa

MODES = ("asap", "alap", "casap", "calap", "custom")
KINDS = ("add", "sub", "mul")
LIMIT_MODES = ("casap", "calap")
LATENCY_MODES = ("alap", "calap", "custom")
MAX_LATENCY = 254
_ASSIGN = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=([0-9]+)", re.ASCII)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.exit(f"error: {message}")


def _check_flags(args):
    """Reject flags the chosen mode doesn't use, and out-of-range numbers."""
    for kind in KINDS:
        n = getattr(args, kind)
        if n is not None:
            if args.schedule not in LIMIT_MODES:
                raise ValueError(f"--{kind} is only used by {' and '.join(LIMIT_MODES)}")
            if n < 1:
                raise ValueError(f"--{kind} must be at least 1")
        if getattr(args, f"{kind}_cycles") < 1:
            raise ValueError(f"--{kind}-cycles must be at least 1")
    if args.latency is not None:
        if args.schedule not in LATENCY_MODES:
            raise ValueError("--latency is only used by alap, calap and custom")
        if not 1 <= args.latency <= MAX_LATENCY:
            raise ValueError(f"--latency must be 1-{MAX_LATENCY}")


def _assignments(items, flag, program):
    """Parse NAME=VALUE items and check each NAME is an input."""
    values = {}
    for item in items or []:
        m = _ASSIGN.fullmatch(item)
        if not m:
            raise ValueError(f"{flag} expects NAME=VALUE, got: {item}")
        name, text = m.groups()
        value = int(text)
        if value > MASK:
            raise ValueError(f"{flag} {name}={text}: values are 0-{MASK}")
        if name in values:
            raise ValueError(f"{flag} {name} is given twice")
        if f"{name}_0" not in program.inputs:
            raise ValueError(f"{flag} {name}: {name} is not an input of this file")
        values[name] = value
    return values


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = _Parser(prog="hls", description="EC551 Program 2: equations to scheduled Verilog.")
    ap.add_argument("file", help="equation file, one 'dst = a op b' per line")
    ap.add_argument("--schedule", type=str.lower, choices=MODES, default="asap", help="scheduling mode (default asap)")
    for kind in KINDS:
        ap.add_argument(f"--{kind}", type=int, metavar="N", help=f"most {kind} units in use at once (casap, calap)")
    ap.add_argument("--latency", type=int, metavar="L", help="latency bound in steps (alap, calap, custom)")
    for kind in KINDS:
        ap.add_argument(f"--{kind}-cycles", type=int, default=1, metavar="N", help=f"steps per {kind} op (default 1)")
    ap.add_argument("--set", nargs="+", action="extend", metavar="NAME=VALUE", help="hardcode inputs that get no switch")
    ap.add_argument("--eval", nargs="+", action="extend", metavar="NAME=VALUE", help="print expected values for these inputs")
    ap.add_argument("--export-ssa", metavar="FILE", help="write the SSA form to FILE")
    ap.add_argument("--out", metavar="DIR", help="write hls_core.v, testbench.v and schedule.txt into DIR")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    try:
        _check_flags(args)
        program = to_ssa(parse_file(args.file))
        _assignments(args.set, "--set", program)
        _assignments(args.eval, "--eval", program)
        dag = build_dag(program.ops)
        limits = {k: getattr(args, k) for k in KINDS if getattr(args, k) is not None}
        cycles = {k: getattr(args, f"{k}_cycles") for k in KINDS}
        try:
            steps = schedule(dag, args.schedule, limits, args.latency, cycles)
        except NotImplementedError:
            steps = None
        sections = [summary(args.file, program), ssa_section(program), dag_section(dag)]
        if steps is None:
            sections.append(f"schedule ({args.schedule}): not implemented yet")
        print("\n\n".join(sections))
        if args.export_ssa is not None:
            _write(args.export_ssa, ssa_text(program))
            print(f"wrote {args.export_ssa}")
    except (OSError, ValueError) as e:
        sys.exit(f"error: {e}")
    return 0
