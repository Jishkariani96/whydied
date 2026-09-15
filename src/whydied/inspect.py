from datetime import UTC, datetime

from whydied.diagnose import diagnose_process
from whydied.kernel import read_kernel_log
from whydied.models import InspectionResult
from whydied.runner import run_process


def inspect_process(command: list[str]) -> InspectionResult:
    started_at = _utc_now()
    process_result = run_process(command)
    ended_at = _utc_now()
    kernel_log = read_kernel_log(since=started_at, until=ended_at)
    diagnosis = diagnose_process(process_result, kernel_log)

    return InspectionResult(
        process=process_result,
        kernel_log=kernel_log,
        diagnosis=diagnosis,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
