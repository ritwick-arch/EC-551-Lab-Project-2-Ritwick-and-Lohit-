"""Command line: python -m hls FILE [options]."""
import argparse
import re
import sys
from pathlib import Path

from .check import KINDS, check_schedule, length, unit_counts
from .dag import build_dag
from .datapath import MAX_DIGIT, SLOTS, build_design, check_slots, evaluate
from .ir import MASK
from .parser import parse_file
from .report import board_section, codes_section, dag_section, eval_section, schedule_section, ssa_section, summary
from .schedule import schedule
from .ssa import ssa_text, to_ssa
from .verilog import core_v, testbench_v

MODES = ("asap", "alap", "casap", "calap", "custom")
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
        if not 1 <= getattr(args, f"{kind}_cycles") <= MAX_LATENCY:
            raise ValueError(f"--{kind}-cycles must be 1-{MAX_LATENCY}")
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


def _eval_values(design, given):
    """Switch values for --eval: one hex digit for every input that isn't hardcoded."""
    values = {}
    for name, value in given.items():
        x = f"{name}_0"
        if x in design.fixed:
            raise ValueError(f"--eval {name}: {name} is hardcoded with --set {name}={design.fixed[x]}")
        if value > MAX_DIGIT:
            raise ValueError(f"--eval {name}={value}: switch inputs are one hex digit (0-{MAX_DIGIT})")
        values[x] = value
    for n, x in enumerate(design.slots):
        if x not in values:
            where = SLOTS[n] if n < len(SLOTS) else "no slot"
            raise ValueError(f"--eval: no value for {x[:-2]} ({where})")
    return evaluate(design, values)


def _heading(args, dag, steps, cycles, limits):
    """The mode and what shaped it, for the schedule section."""
    asap_length = length(dag, schedule(dag, "asap", cycles=cycles), cycles)
    target = args.latency if args.latency is not None else asap_length
    default = "" if args.latency is not None else " (the ASAP length)"
    given = ", ".join(f"{k} {limits[k]}" for k in KINDS if k in limits) or "none"
    parts = [args.schedule]
    if args.schedule == "alap":
        parts.append(f"latency {target}{default}")
    elif args.schedule in ("casap", "calap"):
        parts.append(f"unit limits: {given}")
        if args.schedule == "calap" and args.latency is not None:
            parts.append(f"latency {args.latency}")
    elif args.schedule == "custom":
        found = "casap" if schedule(dag, "casap", limits=unit_counts(dag, steps, cycles), cycles=cycles) == steps else "calap"
        parts.append(f"fewest units that end by step {target}{default}, found with {found}")
    slow = [f"{k} takes {cycles[k]} steps" for k in KINDS if cycles[k] > 1]
    return ", ".join(parts + slow)


def _command(argv):
    return "python -m hls " + " ".join(f'"{a}"' if " " in a or not a else a for a in argv)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    ap = _Parser(prog="hls", description="EC551 Program 2: equations to scheduled Verilog.")
    ap.add_argument("file", help="equation file, one 'dst = a op b' per line")
    ap.add_argument("--schedule", type=str.lower, choices=MODES, default="asap", help="scheduling mode (default asap)")
    for kind in KINDS:
        ap.add_argument(f"--{kind}", type=int, metavar="N", help=f"most {kind} units in use at once (casap, calap)")
    ap.add_argument("--latency", type=int, metavar="L", help="latency bound in steps (alap, calap, custom)")
    for kind in KINDS:
        ap.add_argument(f"--{kind}-cycles", type=int, default=1, metavar="N", help=f"steps per {kind} op (default 1)")
    ap.add_argument("--set", nargs="+", action="extend", metavar="NAME=VALUE", help="hardcode inputs that get no switch")
    ap.add_argument("--eval", nargs="*", action="extend", metavar="NAME=VALUE",
                    help="print the values the board should show for these switch settings")
    ap.add_argument("--export-ssa", metavar="FILE", help="write the SSA form to FILE")
    ap.add_argument("--out", metavar="DIR", help="write hls_core.v, testbench.v and schedule.txt into DIR")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    try:
        _check_flags(args)
        program = to_ssa(parse_file(args.file))
        fixed = _assignments(args.set, "--set", program)
        given = _assignments(args.eval, "--eval", program)
        dag = build_dag(program.ops)
        limits = {k: getattr(args, k) for k in KINDS if getattr(args, k) is not None}
        cycles = {k: getattr(args, f"{k}_cycles") for k in KINDS}
        steps = schedule(dag, args.schedule, limits, args.latency, cycles)
        check_schedule(dag, steps, cycles, limits, args.latency)
        design = build_design(program, dag, steps, cycles, fixed)
        if args.out is not None:
            check_slots(design)
            if Path(args.out).exists() and not Path(args.out).is_dir():
                raise ValueError(f"--out {args.out} is a file, not a folder")
            Path(args.out).mkdir(parents=True, exist_ok=True)
        values = _eval_values(design, given) if args.eval is not None else None
        report = "\n\n".join([summary(args.file, program), board_section(design), ssa_section(program),
                               dag_section(dag), schedule_section(design, _heading(args, dag, steps, cycles, limits)),
                               codes_section(design)])
        print(report)
        if values is not None:
            print("\n" + eval_section(design, values))
        if args.export_ssa is not None:
            _write(args.export_ssa, ssa_text(program))
            print(f"wrote {args.export_ssa}")
        if args.out is not None:
            out = Path(args.out)
            _write(out / "hls_core.v", core_v(design, f"{args.file}, {args.schedule} schedule"))
            _write(out / "testbench.v", testbench_v(design))
            _write(out / "schedule.txt", f"# {_command(argv)}\n\n{report}\n")
            print(f"wrote {out / 'hls_core.v'}, {out / 'testbench.v'} and {out / 'schedule.txt'}")
    except (OSError, ValueError) as e:
        sys.exit(f"error: {e}")
    return 0
