import pytest

from whydied.cli import build_parser, main
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    InspectionResult,
    KernelEvidenceStatus,
    KernelLogAvailable,
    ProcessResult,
    SignalTermination,
)


def _inspection_result(
    termination: ExitTermination | SignalTermination,
    *,
    pid: int = 1234,
    runtime_seconds: float = 0.25,
) -> InspectionResult:
    if isinstance(termination, ExitTermination):
        returncode = termination.code
    else:
        returncode = -termination.number

    return InspectionResult(
        process=ProcessResult(
            pid=pid,
            runtime_seconds=runtime_seconds,
            returncode=returncode,
            termination=termination,
            proc_status=None,
        ),
        kernel_log=KernelLogAvailable(messages=()),
        diagnosis=Diagnosis(
            cause=DiagnosisCause.UNKNOWN,
            kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
        ),
    )


def test_parser_program_name() -> None:
    parser = build_parser()

    assert parser.prog == "whydied"


def test_help_still_works_without_inspection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inspection_called = False

    def inspect_process(_command: list[str]) -> InspectionResult:
        nonlocal inspection_called
        inspection_called = True
        return _inspection_result(ExitTermination(code=0))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "Linux killed your process" in capsys.readouterr().out
    assert inspection_called is False


def test_version_still_works_without_inspection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inspection_called = False

    def inspect_process(_command: list[str]) -> InspectionResult:
        nonlocal inspection_called
        inspection_called = True
        return _inspection_result(ExitTermination(code=0))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert "whydied 0.1.0" in capsys.readouterr().out
    assert inspection_called is False


def test_missing_child_command_fails_cleanly_without_inspection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inspection_called = False

    def inspect_process(_command: list[str]) -> InspectionResult:
        nonlocal inspection_called
        inspection_called = True
        return _inspection_result(ExitTermination(code=0))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    assert "child command is required" in capsys.readouterr().err
    assert inspection_called is False


@pytest.mark.parametrize(
    ("launch_error", "expected_error"),
    [
        (
            FileNotFoundError(2, "No such file or directory", "missing-command"),
            "No such file or directory",
        ),
        (
            PermissionError(13, "Permission denied", "not-executable"),
            "Permission denied",
        ),
    ],
)
def test_child_launch_failure_fails_cleanly_without_formatting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    launch_error: OSError,
    expected_error: str,
) -> None:
    inspected_commands: list[list[str]] = []
    format_called = False

    def inspect_process(command: list[str]) -> InspectionResult:
        inspected_commands.append(command)
        raise launch_error

    def format_report(_inspection: InspectionResult) -> str:
        nonlocal format_called
        format_called = True
        return "unexpected report"

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)
    monkeypatch.setattr("whydied.cli.format_report", format_report)

    with pytest.raises(SystemExit) as exc_info:
        main(["--", "child-command"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert inspected_commands == [["child-command"]]
    assert format_called is False
    assert captured.out == ""
    assert "failed to start child process 'child-command'" in captured.err
    assert expected_error in captured.err
    assert "Traceback" not in captured.err


def test_keyboard_interrupt_exits_cleanly_with_shell_sigint_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inspected_commands: list[list[str]] = []
    format_called = False

    def inspect_process(command: list[str]) -> InspectionResult:
        inspected_commands.append(command)
        raise KeyboardInterrupt

    def format_report(_inspection: InspectionResult) -> str:
        nonlocal format_called
        format_called = True
        return "unexpected report"

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)
    monkeypatch.setattr("whydied.cli.format_report", format_report)

    with pytest.raises(SystemExit) as exc_info:
        main(["--", "child-command"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 130
    assert inspected_commands == [["child-command"]]
    assert format_called is False
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("child_exit_code", [0, 7])
def test_child_exit_code_is_propagated_after_printing_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    child_exit_code: int,
) -> None:
    command = ["python", "-c", f"raise SystemExit({child_exit_code})"]
    inspection = _inspection_result(ExitTermination(code=child_exit_code))
    inspected_commands: list[list[str]] = []
    formatted_inspections: list[InspectionResult] = []

    def inspect_process(command_arg: list[str]) -> InspectionResult:
        inspected_commands.append(command_arg)
        return inspection

    def format_report(inspection_arg: InspectionResult) -> str:
        formatted_inspections.append(inspection_arg)
        return "formatted report"

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)
    monkeypatch.setattr("whydied.cli.format_report", format_report)

    with pytest.raises(SystemExit) as exc_info:
        main(["--", *command])

    assert exc_info.value.code == child_exit_code
    assert inspected_commands == [command]
    assert formatted_inspections == [inspection]
    assert capsys.readouterr().out == "formatted report\n"


def test_signal_termination_uses_shell_compatible_exit_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    signal_number = 9
    inspection = _inspection_result(
        SignalTermination(number=signal_number, name="SIGKILL")
    )
    monkeypatch.setattr("whydied.cli.inspect_process", lambda _command: inspection)
    monkeypatch.setattr(
        "whydied.cli.format_report", lambda _inspection: "signal report"
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["--", "child-command"])

    # Shells conventionally encode signal termination as 128 + signal number.
    assert exc_info.value.code == 128 + signal_number
    assert capsys.readouterr().out == "signal report\n"
