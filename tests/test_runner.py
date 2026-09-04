import sys

import pytest

from whydied.models import ExitTermination, ProcStatus, SignalTermination
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


def test_long_enough_child_produces_proc_status() -> None:
    result = run_process([sys.executable, "-c", "import time; time.sleep(0.2)"])

    assert result.proc_status is not None


def test_observed_rss_values_are_integer_or_none() -> None:
    result = run_process([sys.executable, "-c", "import time; time.sleep(0.2)"])

    assert result.proc_status is not None
    assert result.proc_status.rss_bytes is None or isinstance(
        result.proc_status.rss_bytes,
        int,
    )
    assert result.proc_status.peak_rss_bytes is None or isinstance(
        result.proc_status.peak_rss_bytes,
        int,
    )


def test_very_short_lived_child_may_have_no_proc_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("whydied.runner.read_proc_status", lambda _pid: None)

    result = run_process([sys.executable, "-c", "raise SystemExit(0)"])

    assert result.returncode == 0
    assert result.proc_status is None


def test_runner_handles_proc_status_becoming_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = [
        ProcStatus(state="S (sleeping)", rss_bytes=10, peak_rss_bytes=30),
        ProcStatus(state="R (running)", rss_bytes=20, peak_rss_bytes=25),
    ]

    def read_status(_pid: int) -> ProcStatus | None:
        if observations:
            return observations.pop(0)
        return None

    monkeypatch.setattr("whydied.runner.read_proc_status", read_status)

    result = run_process([sys.executable, "-c", "import time; time.sleep(0.12)"])

    assert result.returncode == 0
    assert result.proc_status == ProcStatus(
        state="R (running)",
        rss_bytes=20,
        peak_rss_bytes=30,
    )
