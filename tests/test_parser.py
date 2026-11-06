import re

import pytest

from hls.parser import Equation, parse_file, parse_text


@pytest.mark.parametrize("line, expected", [
    ("X=A+B", Equation("X", "A", "+", "B", 1)),
    ("\tx1 = a_2 *   b  ", Equation("x1", "a_2", "*", "b", 1)),
    ("X = A * A", Equation("X", "A", "*", "A", 1)),
    ("Y = X * 2", Equation("Y", "X", "*", 2, 1)),
    ("Z = 3 + 4", Equation("Z", 3, "+", 4, 1)),
    ("X = 007 + A", Equation("X", 7, "+", "A", 1)),
    ("X = A + B;", Equation("X", "A", "+", "B", 1)),
    ("X = A - B  # sum", Equation("X", "A", "-", "B", 1)),
    ("X = A + 65535", Equation("X", "A", "+", 65535, 1)),
])
def test_accepted(line, expected):
    assert parse_text(line) == [expected]


@pytest.mark.parametrize("line", [
    "X = A + B + C", "X = (A + B) * C", "X = -A", "X = A + -3", "X = A / B", "X = A ^ B",
    "X = A", "X = 5", "3 = A + B", "X == A + B", "X = A +", "X = 1_000 + A", "X = 2A + B",
    "X = A + B // sum", "_X = A + B", "X = A + B;;",
])
def test_rejected(line):
    with pytest.raises(ValueError, match=r"^line 1: expected 'dst = a op b'"):
        parse_text(line)


@pytest.mark.parametrize("line, code", [
    ("X = A − B", "U+2212"),        # Unicode minus that looks like '-'
    ("X = Ä + B", "U+00C4"),
    ("X = A + ٣", "U+0663"),        # Arabic-Indic digit three
    ("X = A + B", "U+00A0"),        # no-break space
])
def test_non_ascii_named(line, code):
    with pytest.raises(ValueError, match=re.escape(code)) as e:
        parse_text(line)
    assert str(e.value).isascii()


def test_constant_too_big():
    with pytest.raises(ValueError, match="line 2: constant 70000 does not fit in 16 bits"):
        parse_text("X = A + B\nY = 70000 + A")


def test_line_numbers_count_blank_and_comment_lines():
    eqs = parse_text("# header\n\nX = A + B\n  # note\nY = X * 2\n")
    assert [e.line for e in eqs] == [3, 5]
    with pytest.raises(ValueError, match="^line 4:"):
        parse_text("# header\n\nX = A + B\nY = X % 2\n")


def test_empty_and_comment_only():
    for text in ["", "\n\n", "# nothing here\n   # still nothing"]:
        with pytest.raises(ValueError, match="no equations found"):
            parse_text(text)


def test_equation_limit():
    twenty = "\n".join(f"X{i} = A + {i}" for i in range(20))
    assert len(parse_text(twenty + "\n# comment\n" * 30)) == 20
    with pytest.raises(ValueError, match="21 equations; the limit is 20"):
        parse_text(twenty + "\nY = A + B")


def test_crlf_and_bom_file(tmp_path):
    path = tmp_path / "notepad.txt"
    path.write_bytes(b"\xef\xbb\xbfX = A + B\r\nY = X * 2\r\n")
    assert parse_file(path) == [Equation("X", "A", "+", "B", 1), Equation("Y", "X", "*", 2, 2)]


def test_not_utf8(tmp_path):
    path = tmp_path / "latin1.txt"
    path.write_bytes(b"X = A + B # caf\xe9\n")
    with pytest.raises(ValueError, match="is not UTF-8 text"):
        parse_file(path)
