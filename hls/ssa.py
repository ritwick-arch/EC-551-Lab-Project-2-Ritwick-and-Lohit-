"""Single static assignment: every value gets its own versioned name."""
from dataclasses import dataclass

from .ir import KIND, Op


@dataclass(frozen=True)
class Program:
    ops: list[Op]
    inputs: list[str]               # SSA names of primary inputs, in order of first appearance
    outputs: list[tuple[str, str]]  # (variable, final SSA name), in order of first assignment


def to_ssa(equations):
    """Rename every value to NAME_k; names read before any assignment become inputs NAME_0."""
    version, inputs, assigned, ops = {}, [], [], []

    def read(x):
        if isinstance(x, int):
            return x
        if x not in version:
            version[x] = 0
            inputs.append(f"{x}_0")
        return f"{x}_{version[x]}"

    for eq in equations:
        a, b = read(eq.a), read(eq.b)
        if eq.dst not in assigned:
            assigned.append(eq.dst)
        version[eq.dst] = version.get(eq.dst, 0) + 1
        ops.append(Op(len(ops), f"{eq.dst}_{version[eq.dst]}", KIND[eq.op], a, b, eq.line))
    return Program(ops, inputs, [(v, f"{v}_{version[v]}") for v in assigned])


def ssa_text(program):
    """The --export-ssa file: a comment header, then one SSA equation per line."""
    lines = [f"# inputs: {' '.join(program.inputs) or '(none)'}",
             f"# outputs: {' '.join(name for _, name in program.outputs)}"]
    return "\n".join(lines + [op.text() for op in program.ops]) + "\n"
