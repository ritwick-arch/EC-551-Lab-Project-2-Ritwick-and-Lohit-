"""Plain-ASCII sections of the run report."""


def _table(rows):
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  " + "  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows)


def summary(path, program):
    outputs = ", ".join(f"{v} = {name}" for v, name in program.outputs)
    return (f"hls: {path} ({len(program.ops)} equations)\n"
            f"inputs:  {', '.join(program.inputs) or '(none)'}\n"
            f"outputs: {outputs}")


def ssa_section(program):
    return "SSA\n" + "\n".join(f"  {op.text()}" for op in program.ops)


def dag_section(dag):
    rows = [("line", "statement", "depends on")]
    for op, preds in zip(dag.ops, dag.preds):
        rows.append((str(op.line), op.text(), ", ".join(dag.ops[p].dst for p in preds) or "-"))
    return "DAG\n" + _table(rows)
