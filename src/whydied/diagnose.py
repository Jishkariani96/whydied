import signal

from whydied.kernel import parse_oom_kill_events
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    KernelEvidenceStatus,
    KernelLog,
    KernelLogAvailable,
    KernelLogUnavailable,
    ProcessResult,
)


def diagnose_process(
    process_result: ProcessResult,
    kernel_log: KernelLog,
) -> Diagnosis:
    kernel_evidence = _classify_kernel_evidence(process_result, kernel_log)
    return Diagnosis(
        cause=_classify_cause(process_result, kernel_evidence),
        kernel_evidence=kernel_evidence,
    )


def _classify_kernel_evidence(
    process_result: ProcessResult,
    kernel_log: KernelLog,
) -> KernelEvidenceStatus:
    if isinstance(kernel_log, KernelLogUnavailable):
        return KernelEvidenceStatus.UNAVAILABLE
    if _has_matching_oom_victim(process_result, kernel_log):
        return KernelEvidenceStatus.OOM_VICTIM_MATCH
    return KernelEvidenceStatus.NO_OOM_VICTIM_MATCH


def _classify_cause(
    process_result: ProcessResult,
    kernel_evidence: KernelEvidenceStatus,
) -> DiagnosisCause:
    termination = process_result.termination
    if isinstance(termination, ExitTermination):
        if termination.code == 0:
            return DiagnosisCause.CLEAN_EXIT
        return DiagnosisCause.NON_ZERO_EXIT
    if termination.number != signal.SIGKILL:
        return DiagnosisCause.SIGNAL
    if kernel_evidence == KernelEvidenceStatus.OOM_VICTIM_MATCH:
        return DiagnosisCause.OOM_KILL
    return DiagnosisCause.UNKNOWN


def _has_matching_oom_victim(
    process_result: ProcessResult,
    kernel_log: KernelLogAvailable,
) -> bool:
    return any(
        event.victim_pid == process_result.pid
        for event in parse_oom_kill_events(kernel_log.messages)
    )
