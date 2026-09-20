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
    assert exc_info.value.code != 0
    assert inspected_commands == [["child-command"]]
    assert format_called is False
    assert captured.out == ""
    assert "failed to start child process 'child-command'" in captured.err
    assert expected_error in captured.err
    assert "Traceback" not in captured.err


def test_child_command_is_inspected_and_result_is_delegated_to_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = ["python", "-c", "raise SystemExit(0)"]
    inspection = _inspection_result(ExitTermination(code=0))
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

    main(["--", *command])

    assert inspected_commands == [command]
    assert formatted_inspections == [inspection]
    assert capsys.readouterr().out == "formatted report\n"
