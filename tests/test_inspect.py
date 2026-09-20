import signal

import pytest

from whydied.inspect import inspect_process
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    InspectionResult,
    KernelCursorAvailable,
    KernelCursorUnavailable,
    KernelEvidenceStatus,
    KernelLogAvailable,
    KernelLogUnavailable,
    ProcessResult,
    SignalTermination,
)


@pytest.fixture
def initial_pid_namespace(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    reads: list[bool] = []

    def read_pid_namespace_is_initial() -> bool:
        reads.append(True)
        return True

    monkeypatch.setattr(
        "whydied.inspect.read_pid_namespace_is_initial",
        read_pid_namespace_is_initial,
    )
    return reads


def _process_result(
    termination: ExitTermination | SignalTermination,
    *,
    pid: int = 1234,
) -> ProcessResult:
    return ProcessResult(
        pid=pid,
        runtime_seconds=0.1,
        returncode=(
            termination.code
            if isinstance(termination, ExitTermination)
            else -termination.number
        ),
        termination=termination,
        proc_status=None,
    )


def test_inspect_process_coordinates_cursor_process_log_and_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    command = ["python", "child.py"]
    cursor_result = KernelCursorAvailable(cursor="cursor-value")
    process_result = _process_result(ExitTermination(code=0))
    kernel_log = KernelLogAvailable(messages=("kernel message",))
    diagnosis = Diagnosis(
        cause=DiagnosisCause.CLEAN_EXIT,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )
    events: list[str] = []

    def read_kernel_cursor() -> KernelCursorAvailable:
        assert events == []
        events.append("read_kernel_cursor")
        return cursor_result

    def run_process(command_arg: list[str]) -> ProcessResult:
        assert events == ["read_kernel_cursor"]
        assert command_arg is command
        events.append("run_process")
        return process_result

    def read_kernel_log_after(cursor: str) -> KernelLogAvailable:
        assert events == ["read_kernel_cursor", "run_process"]
        assert cursor == cursor_result.cursor
        events.append("read_kernel_log_after")
        return kernel_log

    def diagnose_process(
        process_arg: ProcessResult,
        kernel_log_arg: KernelLogAvailable,
        *,
        pid_namespace_is_initial: bool | None,
    ) -> Diagnosis:
        assert events == [
            "read_kernel_cursor",
            "run_process",
            "read_kernel_log_after",
        ]
        assert process_arg is process_result
        assert kernel_log_arg is kernel_log
        assert pid_namespace_is_initial is True
        events.append("diagnose_process")
        return diagnosis

    monkeypatch.setattr("whydied.inspect.read_kernel_cursor", read_kernel_cursor)
    monkeypatch.setattr("whydied.inspect.run_process", run_process)
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr("whydied.inspect.diagnose_process", diagnose_process)

    result = inspect_process(command)

    assert result == InspectionResult(
        process=process_result,
        kernel_log=kernel_log,
        diagnosis=diagnosis,
    )
    assert events == [
        "read_kernel_cursor",
        "run_process",
        "read_kernel_log_after",
        "diagnose_process",
    ]
    assert initial_pid_namespace == [True]


def test_inspect_process_cursor_unavailable_does_not_query_unbounded_log(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    cursor_result = KernelCursorUnavailable(reason="cursor unavailable")
    process_result = _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL")
    )
    kernel_read_called = False

    def read_kernel_log_after(_cursor: str) -> KernelLogAvailable:
        nonlocal kernel_read_called
        kernel_read_called = True
        return KernelLogAvailable(messages=())

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: cursor_result,
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr(
        "whydied.inspect._sleep",
        lambda _seconds: pytest.fail("kernel log retry was not expected"),
    )

    result = inspect_process(["python"])

    assert result.kernel_log == KernelLogUnavailable(reason="cursor unavailable")
    assert result.diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.UNAVAILABLE,
    )
    assert kernel_read_called is False


def test_inspect_process_unavailable_post_cursor_log_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    process_result = _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL")
    )
    cursors: list[str] = []

    def read_kernel_log_after(cursor: str) -> KernelLogUnavailable:
        cursors.append(cursor)
        return KernelLogUnavailable(reason="journalctl unavailable")

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: KernelCursorAvailable(cursor="cursor-value"),
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr(
        "whydied.inspect._sleep",
        lambda _seconds: pytest.fail("kernel log retry was not expected"),
    )

    result = inspect_process(["python"])

    assert result.diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.UNAVAILABLE,
    )
    assert cursors == ["cursor-value"]


@pytest.mark.parametrize(
    ("termination", "expected_cause"),
    (
        (ExitTermination(code=0), DiagnosisCause.CLEAN_EXIT),
        (ExitTermination(code=3), DiagnosisCause.NON_ZERO_EXIT),
        (
            SignalTermination(number=signal.SIGTERM, name="SIGTERM"),
            DiagnosisCause.SIGNAL,
        ),
        (
            SignalTermination(number=signal.SIGSEGV, name="SIGSEGV"),
            DiagnosisCause.SIGNAL,
        ),
    ),
)
def test_inspect_process_non_sigkill_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
    termination: ExitTermination | SignalTermination,
    expected_cause: DiagnosisCause,
) -> None:
    process_result = _process_result(termination)
    cursors: list[str] = []

    def read_kernel_log_after(cursor: str) -> KernelLogAvailable:
        cursors.append(cursor)
        return KernelLogAvailable(messages=())

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: KernelCursorAvailable(cursor="cursor-value"),
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr(
        "whydied.inspect._sleep",
        lambda _seconds: pytest.fail("kernel log retry was not expected"),
    )

    result = inspect_process(["python"])

    assert result.diagnosis == Diagnosis(
        cause=expected_cause,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )
    assert cursors == ["cursor-value"]


def test_inspect_process_immediate_oom_match_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    process_result = _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL"),
        pid=4321,
    )
    cursors: list[str] = []

    def read_kernel_log_after(cursor: str) -> KernelLogAvailable:
        cursors.append(cursor)
        return KernelLogAvailable(
            messages=("Memory cgroup out of memory: Killed process 4321 (python)",)
        )

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: KernelCursorAvailable(cursor="cursor-value"),
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr(
        "whydied.inspect._sleep",
        lambda _seconds: pytest.fail("kernel log retry was not expected"),
    )

    result = inspect_process(["python"])

    assert result.diagnosis == Diagnosis(
        cause=DiagnosisCause.OOM_KILL,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )
    assert cursors == ["cursor-value"]


def test_inspect_process_sigkill_no_match_retries_and_finds_oom(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    process_result = _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL"),
        pid=4321,
    )
    kernel_logs = [
        KernelLogAvailable(messages=()),
        KernelLogAvailable(
            messages=("Memory cgroup out of memory: Killed process 4321 (python)",)
        ),
    ]
    cursors: list[str] = []
    sleeps: list[float] = []

    def read_kernel_log_after(cursor: str) -> KernelLogAvailable:
        cursors.append(cursor)
        return kernel_logs.pop(0)

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: KernelCursorAvailable(cursor="original-cursor"),
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr("whydied.inspect._sleep", sleeps.append)

    result = inspect_process(["python"])

    assert result.diagnosis == Diagnosis(
        cause=DiagnosisCause.OOM_KILL,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )
    assert sleeps == [0.1]
    assert cursors == ["original-cursor", "original-cursor"]
    assert initial_pid_namespace == [True]


def test_inspect_process_sigkill_retries_stop_at_configured_bound(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    process_result = _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL")
    )
    cursors: list[str] = []
    sleeps: list[float] = []

    def read_kernel_log_after(cursor: str) -> KernelLogAvailable:
        cursors.append(cursor)
        return KernelLogAvailable(messages=())

    monkeypatch.setattr(
        "whydied.inspect.read_kernel_cursor",
        lambda: KernelCursorAvailable(cursor="original-cursor"),
    )
    monkeypatch.setattr(
        "whydied.inspect.run_process",
        lambda _command: process_result,
    )
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr("whydied.inspect._sleep", sleeps.append)

    result = inspect_process(["python"])

    assert result.diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )
    assert sleeps == [0.1] * 5
    assert cursors == ["original-cursor"] * 6


def test_inspect_process_run_process_error_skips_kernel_and_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
    initial_pid_namespace: list[bool],
) -> None:
    events: list[str] = []

    def read_kernel_cursor() -> KernelCursorAvailable:
        events.append("read_kernel_cursor")
        return KernelCursorAvailable(cursor="cursor-value")

    def run_process(_command: list[str]) -> ProcessResult:
        events.append("run_process")
        raise RuntimeError("child failed to start")

    def read_kernel_log_after(_cursor: str) -> KernelLogAvailable:
        events.append("read_kernel_log_after")
        return KernelLogAvailable(messages=())

    def diagnose_process(
        _process_result: ProcessResult,
        _kernel_log: KernelLogAvailable,
    ) -> Diagnosis:
        events.append("diagnose_process")
        return Diagnosis(
            cause=DiagnosisCause.UNKNOWN,
            kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
        )

    monkeypatch.setattr("whydied.inspect.read_kernel_cursor", read_kernel_cursor)
    monkeypatch.setattr("whydied.inspect.run_process", run_process)
    monkeypatch.setattr("whydied.inspect.read_kernel_log_after", read_kernel_log_after)
    monkeypatch.setattr("whydied.inspect.diagnose_process", diagnose_process)

    with pytest.raises(RuntimeError, match="child failed to start"):
        inspect_process(["python"])

    assert events == ["read_kernel_cursor", "run_process"]
    assert initial_pid_namespace == []
