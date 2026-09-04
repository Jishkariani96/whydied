import signal
import subprocess
import time

from whydied.models import ExitTermination, ProcessResult, ProcStatus, SignalTermination
from whydied.procfs import read_proc_status

_POLL_INTERVAL_SECONDS = 0.05


def decode_termination(returncode: int) -> ExitTermination | SignalTermination:
    if returncode >= 0:
        return ExitTermination(code=returncode)

    signal_number = -returncode

    try:
        signal_name = signal.Signals(signal_number).name
    except ValueError:
        signal_name = "UNKNOWN_SIGNAL"

    return SignalTermination(number=signal_number, name=signal_name)


def _merge_proc_status(
    current: ProcStatus | None,
    observed: ProcStatus,
) -> ProcStatus:
    if current is None:
        return observed

    peak_rss_bytes = current.peak_rss_bytes
    if observed.peak_rss_bytes is not None:
        if peak_rss_bytes is None:
            peak_rss_bytes = observed.peak_rss_bytes
        else:
            peak_rss_bytes = max(peak_rss_bytes, observed.peak_rss_bytes)

    return ProcStatus(
        state=observed.state if observed.state is not None else current.state,
        rss_bytes=observed.rss_bytes
        if observed.rss_bytes is not None
        else current.rss_bytes,
        peak_rss_bytes=peak_rss_bytes,
    )


def run_process(command: list[str]) -> ProcessResult:
    started_at = time.monotonic()
    process = subprocess.Popen(command)
    proc_status: ProcStatus | None = None

    while True:
        observed_status = read_proc_status(process.pid)
        if observed_status is not None:
            proc_status = _merge_proc_status(proc_status, observed_status)

        try:
            returncode = process.wait(timeout=_POLL_INTERVAL_SECONDS)
        except subprocess.TimeoutExpired:
            continue
        break

    ended_at = time.monotonic()

    return ProcessResult(
        pid=process.pid,
        runtime_seconds=ended_at - started_at,
        returncode=returncode,
        termination=decode_termination(returncode),
        proc_status=proc_status,
    )
