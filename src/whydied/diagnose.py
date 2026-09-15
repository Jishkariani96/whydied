import signal

from whydied.kernel import parse_oom_kill_events
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    KernelEvidenceStatus,
    KernelLog,
    KernelLogAvailable,
    KernelLogUnavailable,
    ProcessResult,
    SignalTermination,
)


def diagnose_process(
    process_result: ProcessResult,
    kernel_log: KernelLog,
) -> Diagnosis:
    if isinstance(kernel_log, KernelLogUnavailable):
        return Diagnosis(
            cause=DiagnosisCause.UNKNOWN,
            kernel_evidence=KernelEvidenceStatus.UNAVAILABLE,
        )

    matching_victim = _has_matching_oom_victim(process_result, kernel_log)
    if not matching_victim:
        return Diagnosis(
            cause=DiagnosisCause.UNKNOWN,
            kernel_evidence=KernelEvidenceStatus.NO_OOM_VICTIM_MATCH,
        )

    if _terminated_by_sigkill(process_result):
        return Diagnosis(
            cause=DiagnosisCause.OOM_KILL,
            kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
        )

    return Diagnosis(
        cause=DiagnosisCause.UNKNOWN,
        kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
    )


def _has_matching_oom_victim(
    process_result: ProcessResult,
    kernel_log: KernelLogAvailable,
) -> bool:
    return any(
        event.victim_pid == process_result.pid
        for event in parse_oom_kill_events(kernel_log.messages)
    )


def _terminated_by_sigkill(process_result: ProcessResult) -> bool:
    return (
        isinstance(process_result.termination, SignalTermination)
        and process_result.termination.number == signal.SIGKILL
    )
