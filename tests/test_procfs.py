import os

from whydied.models import ProcStatus
from whydied.procfs import _parse_proc_status, read_proc_status


def test_parse_state_preserves_full_value() -> None:
    status = _parse_proc_status("State:\tS (sleeping)\n")

    assert status.state == "S (sleeping)"


def test_parse_rss_converts_kb_to_bytes() -> None:
    status = _parse_proc_status("VmRSS:\t123 kB\n")

    assert status.rss_bytes == 123 * 1024


def test_parse_peak_rss_converts_kb_to_bytes() -> None:
    status = _parse_proc_status("VmHWM:\t456 kB\n")

    assert status.peak_rss_bytes == 456 * 1024


def test_parse_missing_fields_are_none() -> None:
    status = _parse_proc_status("Name:\tpython\n")

    assert status == ProcStatus(
        state=None,
        rss_bytes=None,
        peak_rss_bytes=None,
    )


def test_parse_proc_status_combines_supported_fields() -> None:
    status = _parse_proc_status(
        "Name:\tpython\nState:\tR (running)\nVmRSS:\t10 kB\nVmHWM:\t20 kB\n"
    )

    assert status == ProcStatus(
        state="R (running)",
        rss_bytes=10 * 1024,
        peak_rss_bytes=20 * 1024,
    )


def test_nonexistent_pid_returns_none() -> None:
    assert read_proc_status(-1) is None


def test_read_current_python_pid_status_returns_proc_status() -> None:
    status = read_proc_status(os.getpid())

    assert isinstance(status, ProcStatus)
