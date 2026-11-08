import pytest

from hls.cli import main

SPEC = "X = A + B\nY = X + A\nZ = X - B\nQ = B * Z\n"


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / "spec.txt"
    path.write_text(SPEC)
    return path


def test_report_sections(spec, capsys):
    assert main([str(spec)]) == 0
    out = capsys.readouterr().out
    assert "(4 equations)" in out and "inputs:  A_0, B_0" in out
    assert "outputs: X = X_1, Y = Y_1, Z = Z_1, Q = Q_1" in out
    assert "  Q_1 = B_0 * Z_1" in out
    assert "  4     Q_1 = B_0 * Z_1  Z_1" in out
    assert out.isascii()


def test_export_ssa(spec, tmp_path, capsys):
    target = tmp_path / "sub" / "spec.ssa.txt"
    assert main([str(spec), "--export-ssa", str(target)]) == 0
    assert target.read_bytes() == (b"# inputs: A_0 B_0\n# outputs: X_1 Y_1 Z_1 Q_1\n"
                                   b"X_1 = A_0 + B_0\nY_1 = X_1 + A_0\nZ_1 = X_1 - B_0\nQ_1 = B_0 * Z_1\n")
    assert f"wrote {target}" in capsys.readouterr().out


@pytest.mark.parametrize("flags, message", [
    (["--mul", "1"], "--mul is only used by casap and calap"),
    (["--schedule", "alap", "--add", "2"], "--add is only used by casap and calap"),
    (["--schedule", "casap", "--latency", "5"], "--latency is only used by alap, calap and custom"),
    (["--schedule", "casap", "--mul", "0"], "--mul must be at least 1"),
    (["--mul-cycles", "0"], "--mul-cycles must be 1-254"),
    (["--add-cycles", "255"], "--add-cycles must be 1-254"),
    (["--schedule", "alap", "--latency", "255"], "--latency must be 1-254"),
    (["--set", "E=3"], "--set E: E is not an input of this file"),
    (["--set", "A"], "--set expects NAME=VALUE, got: A"),
    (["--set", "A=1", "A=2"], "--set A is given twice"),
    (["--eval", "A=70000"], "--eval A=70000: values are 0-65535"),
    (["--set", "A=0x1F"], "--set expects NAME=VALUE, got: A=0x1F"),
    (["--schedule", "list"], "argument --schedule: invalid choice: 'list'"),
    (["--schedule", "casap", "--mul", "two"], "argument --mul: invalid int value: 'two'"),
    (["--frob"], "unrecognized arguments: --frob"),
])
def test_flag_errors(spec, flags, message):
    with pytest.raises(SystemExit, match="^error: " + message.replace("+", r"\+")):
        main([str(spec)] + flags)


def test_flags_accepted(spec):
    assert main([str(spec), "--schedule", "CALAP", "--add", "1", "--latency", "6", "--mul-cycles", "2",
                 "--set", "A=31", "--eval", "B=4"]) == 0


def test_missing_file_argument(capsys):
    with pytest.raises(SystemExit, match="^error: the following arguments are required: file$"):
        main([])


def test_missing_file_and_parse_error(tmp_path):
    with pytest.raises(SystemExit, match="^error: "):
        main([str(tmp_path / "missing.txt")])
    bad = tmp_path / "bad.txt"
    bad.write_text("X = A + B\nY = A / B\n")
    with pytest.raises(SystemExit, match="^error: line 2: "):
        main([str(bad)])


def test_error_after_parsing_writes_nothing(spec, tmp_path):
    target = tmp_path / "sub" / "out.ssa.txt"
    with pytest.raises(SystemExit, match="^error: --set E: "):
        main([str(spec), "--set", "E=3", "--export-ssa", str(target)])
    assert not target.parent.exists()
