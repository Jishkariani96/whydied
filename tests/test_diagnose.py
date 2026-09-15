import signal

from whydied.diagnose import diagnose_process
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    KernelEvidenceStatus,
    KernelLogAvailable,
    KernelLogUnavailable,
    ProcessResult,
    SignalTermination,
)


def _process_result(
    termination: ExitTermination | SignalTermination,
    *,
    pid: int = 1234,
) -> ProcessResult:
    if isinstance(termination, ExitTermination):
        returncode = termination.code
    else:
        returncode = -termination.number

    return ProcessResult(
        pid=pid,
        runtime_seconds=0.1,
        returncode=returncode,
        termination=termination,
        proc_status=None,
    )


def _sigkill_result(*, pid: int = 1234) -> ProcessResult:
    return _process_result(
        SignalTermination(number=signal.SIGKILL, name="SIGKILL"),
        pid=pid,
    )


def _available_with_victim(pid: int, name: str = "python") -> KernelLogAvailable:
    return KernelLogAvailable(messages=(f"Killed process {pid} ({name})",))


def test_sigkill_with_matching_oom_victim_pid_diagnoses_oom_kill() -> None:
    diagnosis = diagnose_process(_sigkill_result(), _available_with_victim(1234))

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.OOM_KILL,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_sigkill_with_oom_victim_for_other_pid_is_unknown_without_match() -> None:
    diagnosis = diagnose_process(_sigkill_result(), _available_with_victim(9999))

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )


def test_sigkill_with_empty_available_kernel_messages_is_unknown_without_match() -> (
    None
):
    diagnosis = diagnose_process(_sigkill_result(), KernelLogAvailable(messages=()))

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )


def test_sigkill_with_unrelated_kernel_messages_is_unknown_without_match() -> None:
    diagnosis = diagnose_process(
        _sigkill_result(),
        KernelLogAvailable(messages=("usb 1-1: new device", "eth0: link ready")),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
    )


def test_sigkill_with_unavailable_kernel_evidence_is_unknown_unavailable() -> None:
    diagnosis = diagnose_process(
        _sigkill_result(),
        KernelLogUnavailable(reason="journalctl unavailable"),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.UNAVAILABLE,
    )


def test_clean_exit_with_matching_oom_victim_pid_is_unknown_with_match() -> None:
    diagnosis = diagnose_process(
        _process_result(ExitTermination(code=0)),
        _available_with_victim(1234),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_non_zero_exit_with_matching_oom_victim_pid_is_unknown_with_match() -> None:
    diagnosis = diagnose_process(
        _process_result(ExitTermination(code=3)),
        _available_with_victim(1234),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_sigterm_with_matching_oom_victim_pid_is_unknown_with_match() -> None:
    diagnosis = diagnose_process(
        _process_result(SignalTermination(number=signal.SIGTERM, name="SIGTERM")),
        _available_with_victim(1234),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_sigsegv_with_matching_oom_victim_pid_is_unknown_with_match() -> None:
    diagnosis = diagnose_process(
        _process_result(SignalTermination(number=signal.SIGSEGV, name="SIGSEGV")),
        _available_with_victim(1234),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_multiple_oom_events_with_one_matching_pid_diagnoses_oom_for_sigkill() -> None:
    diagnosis = diagnose_process(
        _sigkill_result(pid=2222),
        KernelLogAvailable(
            messages=(
                "Killed process 1111 (first)",
                "Killed process 2222 (second)",
            )
        ),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.OOM_KILL,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def test_process_name_mismatch_does_not_prevent_pid_correlation() -> None:
    diagnosis = diagnose_process(
        _sigkill_result(pid=1234),
        _available_with_victim(1234, name="different-name"),
    )

    assert diagnosis == Diagnosis(
        cause=DiagnosisCause.OOM_KILL,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )
