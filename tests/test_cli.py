import sys

import pytest

from whydied.cli import build_parser, main


def test_parser_program_name() -> None:
    parser = build_parser()

    assert parser.prog == "whydied"


def test_help_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "Linux killed your process" in capsys.readouterr().out


def test_version_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert "whydied 0.1.0" in capsys.readouterr().out


def test_missing_child_command_fails_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    assert "child command is required" in capsys.readouterr().err


def test_clean_child_exit(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--", sys.executable, "-c", "raise SystemExit(0)"])

    output = capsys.readouterr().out
    assert "Return code: 0" in output
    assert "Termination: exit 0" in output


def test_non_zero_child_exit(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--", sys.executable, "-c", "raise SystemExit(3)"])

    output = capsys.readouterr().out
    assert "Return code: 3" in output
    assert "Termination: exit 3" in output
