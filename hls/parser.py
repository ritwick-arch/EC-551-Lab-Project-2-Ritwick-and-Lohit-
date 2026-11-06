"""Read an equation file: one 'dst = a op b' per line."""
import re
from dataclasses import dataclass

from .ir import MASK, WIDTH

MAX_EQUATIONS = 20
_NAME = r"[A-Za-z][A-Za-z0-9_]*"
_OPERAND = rf"{_NAME}|[0-9]+"
_LINE = re.compile(rf"\s*({_NAME})\s*=\s*({_OPERAND})\s*([-+*])\s*({_OPERAND})\s*;?\s*", re.ASCII)


@dataclass(frozen=True)
class Equation:
    dst: str
    a: str | int
    op: str         # '+', '-' or '*'
    b: str | int
    line: int


def _operand(token, line):
    if not token[0].isdigit():
        return token
    value = int(token)
    if value > MASK:
        raise ValueError(f"line {line}: constant {value} does not fit in {WIDTH} bits (max {MASK})")
    return value


def _bad_line(line, code):
    shown = code.strip().encode("ascii", "backslashreplace").decode()
    msg = f"line {line}: expected 'dst = a op b' with op one of + - *, got: {shown}"
    odd = sorted({f"U+{ord(c):04X}" for c in code if ord(c) > 127})
    if odd:
        msg += f" (non-ASCII character {', '.join(odd)})"
    return msg


def parse_text(text):
    """Parse equation text; raise ValueError naming the first bad line."""
    equations = []
    for n, raw in enumerate(text.split("\n"), 1):
        code = raw.split("#", 1)[0]
        if not code.strip():
            continue
        m = _LINE.fullmatch(code)
        if not m:
            raise ValueError(_bad_line(n, code))
        dst, a, op, b = m.groups()
        equations.append(Equation(dst, _operand(a, n), op, _operand(b, n), n))
    if not equations:
        raise ValueError("no equations found")
    if len(equations) > MAX_EQUATIONS:
        raise ValueError(f"{len(equations)} equations; the limit is {MAX_EQUATIONS}")
    return equations


def parse_file(path):
    """Parse an equation file (UTF-8, with or without a BOM)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not UTF-8 text") from None
    return parse_text(text)
