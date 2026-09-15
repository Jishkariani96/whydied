from datetime import UTC, datetime

import pytest

from whydied.inspect import inspect_process
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    InspectionResult,
    KernelEvidenceStatus,
    KernelLogAvailable,
    KernelLogUnavailable,
    ProcessResult,
)


def _process_result() -> ProcessResult:
    return ProcessResult(
        pid=1234,
        runtime_seconds=0.1,
        returncode=0,
        termination=ExitTermination(code=0),
        proc_status=None,
    )


def _diagnosis(kernel_evidence: KernelEvidenceStatus) -> Diagnosis:
    return Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=kernel_evidence,
    )


def test_inspect_process_coordinates_process_kernel_and_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = ["python", "child.py"]
    process_result = _process_result()
    kernel_log = KernelLogAvailable(messages=("kernel message",))
    diagnosis = _diagnosis(KernelEvidenceStatus.NO_OOM_VICTIM_MATCH)
    started_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    ended_at = datetime(2025, 1, 2, 3, 4, 6, tzinfo=UTC)
    clock_values = [started_at, ended_at]
    events: list[str] = []

    def utc_now() -> datetime:
        events.append("clock")
        return clock_values.pop(0)

    def run_process(command_arg: list[str]) -> ProcessResult:
        assert events == ["clock"]
        assert command_arg is command
        events.append("run_process")
        return process_result

    def read_kernel_log(
        *, since: datetime | None, until: datetime | None
    ) -> KernelLogAvailable:
        assert events == ["clock", "run_process", "clock"]
        assert since is started_at
        assert until is ended_at
        assert since.tzinfo is UTC
        assert until.tzinfo is UTC
        assert since.utcoffset() is not None
        assert until.utcoffset() is not None
        events.append("read_kernel_log")
        return kernel_log

    def diagnose_process(
        process_arg: ProcessResult,
        kernel_log_arg: KernelLogAvailable,
    ) -> Diagnosis:
        assert events == ["clock", "run_process", "clock", "read_kernel_log"]
        assert process_arg is process_result
        assert kernel_log_arg is kernel_log
        events.append("diagnose_process")
        return diagnosis

    monkeypatch.setattr("whydied.inspect._utc_now", utc_now)
    monkeypatch.setattr("whydied.inspect.run_process", run_process)
    monkeypatch.setattr("whydied.inspect.read_kernel_log", read_kernel_log)
    monkeypatch.setattr("whydied.inspect.diagnose_process", diagnose_process)

    result = inspect_process(command)

    assert result == InspectionResult(
        process=process_result,
        kernel_log=kernel_log,
        diagnosis=diagnosis,
    )
    assert result.process is process_result
    assert result.kernel_log is kernel_log
    assert result.diagnosis is diagnosis
    assert events == [
        "clock",
        "run_process",
        "clock",
        "read_kernel_log",
        "diagnose_process",
    ]


def test_inspect_process_passes_unavailable_kernel_log_to_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_result = _process_result()
    kernel_log = KernelLogUnavailable(reason="journalctl unavailable")
    diagnosis = _diagnosis(KernelEvidenceStatus.UNAVAILABLE)
    clock_values = [
        datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        datetime(2025, 1, 2, 3, 4, 6, tzinfo=UTC),
    ]

    def utc_now() -> datetime:
        return clock_values.pop(0)

    def run_process(_command: list[str]) -> ProcessResult:
        return process_result

    def read_kernel_log(
        *, since: datetime | None, until: datetime | None
    ) -> KernelLogUnavailable:
        assert since is not None
        assert until is not None
        return kernel_log

    def diagnose_process(
        process_arg: ProcessResult,
        kernel_log_arg: KernelLogUnavailable,
    ) -> Diagnosis:
        assert process_arg is process_result
        assert kernel_log_arg is kernel_log
        return diagnosis

    monkeypatch.setattr("whydied.inspect._utc_now", utc_now)
    monkeypatch.setattr("whydied.inspect.run_process", run_process)
    monkeypatch.setattr("whydied.inspect.read_kernel_log", read_kernel_log)
    monkeypatch.setattr("whydied.inspect.diagnose_process", diagnose_process)

    result = inspect_process(["python"])

    assert result == InspectionResult(
        process=process_result,
        kernel_log=kernel_log,
        diagnosis=diagnosis,
    )
    assert result.kernel_log is kernel_log


def test_inspect_process_run_process_error_skips_kernel_and_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel_called = False
    diagnosis_called = False

    def utc_now() -> datetime:
        return datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)

    def run_process(_command: list[str]) -> ProcessResult:
        raise RuntimeError("child failed to start")

    def read_kernel_log(
        *, since: datetime | None, until: datetime | None
    ) -> KernelLogAvailable:
        nonlocal kernel_called
        kernel_called = True
        return KernelLogAvailable(messages=())

    def diagnose_process(
        _process_result: ProcessResult,
        _kernel_log: KernelLogAvailable,
    ) -> Diagnosis:
        nonlocal diagnosis_called
        diagnosis_called = True
        return _diagnosis(KernelEvidenceStatus.NO_OOM_VICTIM_MATCH)

    monkeypatch.setattr("whydied.inspect._utc_now", utc_now)
    monkeypatch.setattr("whydied.inspect.run_process", run_process)
    monkeypatch.setattr("whydied.inspect.read_kernel_log", read_kernel_log)
    monkeypatch.setattr("whydied.inspect.diagnose_process", diagnose_process)

    with pytest.raises(RuntimeError, match="child failed to start"):
        inspect_process(["python"])

    assert kernel_called is False
    assert diagnosis_called is False
