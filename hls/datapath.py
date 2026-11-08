"""Bind ops to units (F), place inputs on switch slots and list the observe codes (H)."""
from dataclasses import dataclass

from .check import KINDS, last_step, length
from .ir import MASK

SLOTS = ("SW11-8", "SW7-4", "SW3-0")
SLOT_BITS = ("sw[11:8]", "sw[7:4]", "sw[3:0]")
MAX_DIGIT = 15


@dataclass
class Unit:
    name: str       # e.g. 'add0'
    kind: str
    ops: list       # indices of its ops, in start order
    ports: tuple    # (left, right): each port's sources in first-use order, a register name or a constant


@dataclass
class Design:
    program: object
    dag: object
    steps: list         # start step of each op
    cycles: dict
    latency: int
    units: list         # adders, then subtractors, then multipliers, by index
    unit_of: list       # unit index of each op
    slots: list         # switch inputs (SSA names) in slot order; more than 3 only without --out
    fixed: dict         # --set inputs: SSA name -> value
    codes: list         # observe table: ('unit' | 'result' | 'input', name)

    def last(self, i):
        return last_step(self.dag.ops[i], self.steps[i], self.cycles)

    def source(self, x):
        """What an operand reads: a register name, or a constant (also for --set inputs)."""
        return self.fixed.get(x, x) if isinstance(x, str) else x

    def running(self, t):
        """(unit index, op index) for every op that holds its unit in step t."""
        return [(self.unit_of[i], i) for i in range(len(self.steps)) if self.steps[i] <= t <= self.last(i)]


def bind(dag, steps, cycles):
    """Left-edge: in start order, each op takes the lowest-numbered free unit of its type."""
    units, unit_of = [], [None] * len(steps)
    ends = []
    for i in sorted(range(len(steps)), key=lambda i: (steps[i], i)):
        op = dag.ops[i]
        free = [u for u, unit in enumerate(units) if unit.kind == op.kind and ends[u] < steps[i]]
        if free:
            u = free[0]
        else:
            u = len(units)
            units.append(Unit("", op.kind, [], ([], [])))
            ends.append(0)
        units[u].ops.append(i)
        ends[u] = last_step(op, steps[i], cycles)
        unit_of[i] = u
    order = sorted(range(len(units)), key=lambda u: (KINDS.index(units[u].kind), u))
    renumber = {u: n for n, u in enumerate(order)}
    units = [units[u] for u in order]
    seen = {kind: 0 for kind in KINDS}
    for unit in units:
        unit.name = f"{unit.kind}{seen[unit.kind]}"
        seen[unit.kind] += 1
    return units, [renumber[u] for u in unit_of]


def build_design(program, dag, steps, cycles, fixed_names):
    """The datapath for a checked schedule; fixed_names maps --set names (without _0) to values."""
    fixed = {f"{name}_0": value for name, value in fixed_names.items()}
    units, unit_of = bind(dag, steps, cycles)
    design = Design(program, dag, steps, cycles, length(dag, steps, cycles), units, unit_of,
                    [x for x in program.inputs if x not in fixed], fixed, [])
    for unit in units:
        for i in unit.ops:
            op = dag.ops[i]
            for port, x in zip(unit.ports, (op.a, op.b)):
                src = design.source(x)
                if src not in port:
                    port.append(src)
    design.codes = ([("unit", u.name) for u in units] + [("result", op.dst) for op in dag.ops]
                    + [("input", x) for x in design.slots[:len(SLOTS)]])
    return design


def check_slots(design):
    """Generating Verilog needs a switch slot for every input that isn't hardcoded."""
    extra = design.slots[len(SLOTS):]
    if extra:
        names = ", ".join(x[:-2] for x in extra)
        raise ValueError(f"{len(design.slots)} inputs need switches but there are {len(SLOTS)} slots: "
                         f"hardcode {names} with --set NAME=VALUE")


def evaluate(design, switch_values):
    """Every value for the given switch inputs (by SSA name), wrapped to 16 bits like the hardware."""
    values = dict(design.fixed)
    values.update(switch_values)
    for op in design.dag.ops:
        a, b = (values[x] if isinstance(x, str) else x for x in (op.a, op.b))
        values[op.dst] = {"add": a + b, "sub": a - b, "mul": a * b}[op.kind] & MASK
    return values
