"""Shared data types: SSA ops, the DAG, and the datapath width."""
from dataclasses import dataclass

WIDTH = 16
MASK = (1 << WIDTH) - 1
KIND = {"+": "add", "-": "sub", "*": "mul"}
SYMBOL = {kind: sym for sym, kind in KIND.items()}


@dataclass(frozen=True)
class Op:
    index: int      # 0-based, in line order
    dst: str        # SSA name, e.g. 'Y_2'
    kind: str       # 'add' | 'sub' | 'mul'
    a: str | int    # SSA name or constant
    b: str | int
    line: int       # line number in the input file

    def text(self):
        return f"{self.dst} = {self.a} {SYMBOL[self.kind]} {self.b}"


@dataclass
class DAG:
    ops: list[Op]             # line order
    preds: list[list[int]]    # ops each op reads (deduplicated)
    succs: list[list[int]]    # ops that read each op
