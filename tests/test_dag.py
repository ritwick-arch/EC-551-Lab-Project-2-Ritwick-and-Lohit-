from hls.dag import build_dag
from hls.parser import parse_text
from hls.ssa import to_ssa


def dag(text):
    return build_dag(to_ssa(parse_text(text)).ops)


def test_spec_example_edges():
    d = dag("X = A + B\nY = X + A\nZ = X - B\nQ = B * Z\n")
    assert d.preds == [[], [0], [0], [2]]
    assert d.succs == [[1, 2], [], [3], []]


def test_same_operand_twice_is_one_edge():
    d = dag("X = A + B\nY = X * X\n")
    assert d.preds == [[], [0]]
    assert d.ops[1].a == d.ops[1].b == "X_1"


def test_inputs_and_constants_are_not_edges():
    d = dag("X = A + 3\nY = 2 * 5\nZ = X - Y\n")
    assert d.preds == [[], [], [0, 1]]


def test_reassignment_follows_versions():
    d = dag("X = A + B\nT = X * 2\nX = X + A\nU = T + X\n")
    assert d.preds == [[], [0], [0], [1, 2]]
