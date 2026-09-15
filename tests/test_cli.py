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


def test_child_command_is_passed_unchanged_after_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = ["python", "-c", "raise SystemExit(0)"]
    calls: list[list[str]] = []

    def inspect_process(command_arg: list[str]) -> InspectionResult:
        calls.append(command_arg)
        return _inspection_result(ExitTermination(code=0))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    main(["--", *command])

    assert calls == [command]


def test_clean_child_exit_output_uses_inspection_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def inspect_process(_command: list[str]) -> InspectionResult:
        return _inspection_result(
            ExitTermination(code=0), pid=4321, runtime_seconds=1.25
        )

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    main(["--", "child"])

    output = capsys.readouterr().out
    assert "PID: 4321" in output
    assert "Runtime: 1.25s" in output
    assert "Return code: 0" in output
    assert "Termination: exit 0" in output


def test_non_zero_child_exit_output_uses_inspection_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def inspect_process(_command: list[str]) -> InspectionResult:
        return _inspection_result(ExitTermination(code=3))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    main(["--", "child"])

    output = capsys.readouterr().out
    assert "Return code: 3" in output
    assert "Termination: exit 3" in output


def test_signal_termination_output_uses_inspection_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def inspect_process(_command: list[str]) -> InspectionResult:
        return _inspection_result(SignalTermination(number=9, name="SIGKILL"))

    monkeypatch.setattr("whydied.cli.inspect_process", inspect_process)

    main(["--", "child"])

    output = capsys.readouterr().out
    assert "Return code: -9" in output
    assert "Termination: SIGKILL (9)" in output
