import signal
import subprocess
import time

from whydied.models import ExitTermination, ProcessResult, SignalTermination


def decode_termination(returncode: int) -> ExitTermination | SignalTermination:
    if returncode >= 0:
        return ExitTermination(code=returncode)

    signal_number = -returncode

    try:
        signal_name = signal.Signals(signal_number).name
    except ValueError:
        signal_name = "UNKNOWN_SIGNAL"

    return SignalTermination(number=signal_number, name=signal_name)


def run_process(command: list[str]) -> ProcessResult:
    started_at = time.monotonic()
    process = subprocess.Popen(command)
    returncode = process.wait()
    ended_at = time.monotonic()

    return ProcessResult(
        pid=process.pid,
        runtime_seconds=ended_at - started_at,
        returncode=returncode,
        termination=decode_termination(returncode),
    )
