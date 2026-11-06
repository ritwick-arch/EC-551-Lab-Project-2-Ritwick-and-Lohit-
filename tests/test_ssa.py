from hls.dag import build_dag
from hls.ir import Op
from hls.parser import parse_text
from hls.ssa import ssa_text, to_ssa

SPEC = "X = A + B\nY = X + A\nZ = X - B\nQ = B * Z\n"


def ssa(text):
    return to_ssa(parse_text(text))


def texts(program):
    return [op.text() for op in program.ops]


def test_spec_example():
    p = ssa(SPEC)
    assert texts(p) == ["X_1 = A_0 + B_0", "Y_1 = X_1 + A_0", "Z_1 = X_1 - B_0", "Q_1 = B_0 * Z_1"]
    assert p.inputs == ["A_0", "B_0"]
    assert p.outputs == [("X", "X_1"), ("Y", "Y_1"), ("Z", "Z_1"), ("Q", "Q_1")]
    assert p.ops[3] == Op(3, "Q_1", "mul", "B_0", "Z_1", 4)


def test_reassignment_and_constants():
    p = ssa("X = A + B\nX = X * 2\nY = X - A\n")
    assert texts(p) == ["X_1 = A_0 + B_0", "X_2 = X_1 * 2", "Y_1 = X_2 - A_0"]
    assert p.outputs == [("X", "X_2"), ("Y", "Y_1")]


def test_reassigned_input_and_read_before_assignment():
    p = ssa("A = A + B\nY = X + A\nX = A + B\n")
    assert texts(p) == ["A_1 = A_0 + B_0", "Y_1 = X_0 + A_1", "X_1 = A_1 + B_0"]
    assert p.inputs == ["A_0", "B_0", "X_0"]
    assert p.outputs == [("A", "A_1"), ("Y", "Y_1"), ("X", "X_1")]


def test_user_name_that_looks_like_a_version():
    p = ssa("X = A + B\nX_1 = X + 1\nX = X_1 * 2\n")
    assert texts(p) == ["X_1 = A_0 + B_0", "X_1_1 = X_1 + 1", "X_2 = X_1_1 * 2"]


def test_constant_only_and_dead_values_kept():
    p = ssa("Z = 3 + 4\nX = A + B\nX = A * B\n")
    assert texts(p) == ["Z_1 = 3 + 4", "X_1 = A_0 + B_0", "X_2 = A_0 * B_0"]
    assert p.outputs == [("Z", "Z_1"), ("X", "X_2")]


def test_export_text_and_reparse():
    p = ssa("X = A + B\nX = X * 2\nY = X - A\n")
    text = ssa_text(p)
    assert text == ("# inputs: A_0 B_0\n# outputs: X_2 Y_1\n"
                    "X_1 = A_0 + B_0\nX_2 = X_1 * 2\nY_1 = X_2 - A_0\n")
    again = to_ssa(parse_text(text))
    assert [op.kind for op in again.ops] == [op.kind for op in p.ops]
    assert build_dag(again.ops).preds == build_dag(p.ops).preds


def test_export_no_inputs():
    assert ssa_text(ssa("Z = 3 + 4")).startswith("# inputs: (none)\n# outputs: Z_1\n")
