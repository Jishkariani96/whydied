import signal
import time

from whydied.diagnose import diagnose_process
from whydied.kernel import read_kernel_cursor, read_kernel_log_after
from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    InspectionResult,
    KernelCursorAvailable,
    KernelEvidenceStatus,
    KernelLogUnavailable,
    ProcessResult,
    SignalTermination,
)
from whydied.runner import run_process

_KERNEL_LOG_RETRY_INTERVAL_SECONDS = 0.1
_KERNEL_LOG_RETRY_ATTEMPTS = 5


def inspect_process(command: list[str]) -> InspectionResult:
    cursor_result = read_kernel_cursor()
    process_result = run_process(command)

    if isinstance(cursor_result, KernelCursorAvailable):
        kernel_log = read_kernel_log_after(cursor_result.cursor)
    else:
        kernel_log = KernelLogUnavailable(reason=cursor_result.reason)

    diagnosis = diagnose_process(process_result, kernel_log)

    if isinstance(cursor_result, KernelCursorAvailable):
        for _ in range(_KERNEL_LOG_RETRY_ATTEMPTS):
            if not _should_retry_kernel_log(process_result, diagnosis):
                break
            _sleep(_KERNEL_LOG_RETRY_INTERVAL_SECONDS)
            kernel_log = read_kernel_log_after(cursor_result.cursor)
            diagnosis = diagnose_process(process_result, kernel_log)

    return InspectionResult(
        process=process_result,
        kernel_log=kernel_log,
        diagnosis=diagnosis,
    )


def _should_retry_kernel_log(
    process_result: ProcessResult,
    diagnosis: Diagnosis,
) -> bool:
    termination = process_result.termination
    return (
        isinstance(termination, SignalTermination)
        and termination.number == signal.SIGKILL
        and diagnosis.cause == DiagnosisCause.UNKNOWN
        and diagnosis.kernel_evidence == KernelEvidenceStatus.NO_OOM_VICTIM_MATCH
    )


def _sleep(seconds: float) -> None:
    time.sleep(seconds)
