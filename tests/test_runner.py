import sys

from whydied.models import ExitTermination, SignalTermination
from whydied.runner import decode_termination, run_process


def test_decode_zero_exit_code() -> None:
    assert decode_termination(0) == ExitTermination(code=0)


def test_decode_positive_non_zero_exit_code() -> None:
    assert decode_termination(2) == ExitTermination(code=2)


def test_decode_sigterm() -> None:
    assert decode_termination(-15) == SignalTermination(number=15, name="SIGTERM")


def test_decode_sigkill() -> None:
    assert decode_termination(-9) == SignalTermination(number=9, name="SIGKILL")


def test_decode_sigsegv() -> None:
    assert decode_termination(-11) == SignalTermination(number=11, name="SIGSEGV")


def test_decode_unknown_signal() -> None:
    assert decode_termination(-999) == SignalTermination(
        number=999,
        name="UNKNOWN_SIGNAL",
    )


def test_run_process_clean_exit() -> None:
    result = run_process([sys.executable, "-c", "raise SystemExit(0)"])

    assert result.pid > 0
    assert result.runtime_seconds >= 0
    assert result.returncode == 0
    assert result.termination == ExitTermination(code=0)


def test_run_process_non_zero_exit() -> None:
    result = run_process([sys.executable, "-c", "raise SystemExit(3)"])

    assert result.returncode == 3
    assert result.termination == ExitTermination(code=3)


def test_run_process_signal_termination() -> None:
    result = run_process(
        [
            sys.executable,
            "-c",
            "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
        ]
    )

    assert result.returncode == -15
    assert result.termination == SignalTermination(number=15, name="SIGTERM")


def test_run_process_sigkill() -> None:
    result = run_process(
        [
            sys.executable,
            "-c",
            "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
        ]
    )

    assert result.returncode == -9
    assert result.termination == SignalTermination(
        number=9,
        name="SIGKILL",
    )
