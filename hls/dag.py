"""Build the data-dependency DAG over the SSA ops."""
from .ir import DAG


def build_dag(ops):
    """Edges run from the op that writes a value to every op that reads it."""
    producer = {op.dst: op.index for op in ops}
    preds = [sorted({producer[x] for x in (op.a, op.b) if isinstance(x, str) and x in producer}) for op in ops]
    succs = [[] for _ in ops]
    for i, ps in enumerate(preds):
        for p in ps:
            succs[p].append(i)
    return DAG(list(ops), preds, succs)
