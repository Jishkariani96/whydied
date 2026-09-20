import os
from pathlib import Path

import pytest

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


def test_parse_swap_converts_kb_to_bytes() -> None:
    status = _parse_proc_status("VmSwap:\t789 kB\n")

    assert status.peak_swap_bytes == 789 * 1024


def test_parse_missing_swap_is_none() -> None:
    status = _parse_proc_status("VmRSS:\t123 kB\n")

    assert status.peak_swap_bytes is None


def test_parse_missing_fields_are_none() -> None:
    status = _parse_proc_status("Name:\tpython\n")

    assert status == ProcStatus(
        state=None,
        rss_bytes=None,
        peak_rss_bytes=None,
        peak_swap_bytes=None,
    )


def test_parse_proc_status_combines_supported_fields() -> None:
    status = _parse_proc_status(
        "Name:\tpython\nState:\tR (running)\n"
        "VmRSS:\t10 kB\nVmHWM:\t20 kB\nVmSwap:\t30 kB\n"
    )

    assert status == ProcStatus(
        state="R (running)",
        rss_bytes=10 * 1024,
        peak_rss_bytes=20 * 1024,
        peak_swap_bytes=30 * 1024,
    )


def test_nonexistent_pid_returns_none() -> None:
    assert read_proc_status(-1) is None


def test_read_proc_status_tolerates_non_utf8_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "status"
    status_path.write_bytes(
        b"Name:\tinvalid-\xff-name\nState:\tS (sleeping)\nVmRSS:\t123 kB\n"
    )
    monkeypatch.setattr(
        "builtins.open",
        lambda *_args, **kwargs: status_path.open(**kwargs),
    )

    assert read_proc_status(1234) == ProcStatus(
        state="S (sleeping)",
        rss_bytes=123 * 1024,
        peak_rss_bytes=None,
        peak_swap_bytes=None,
    )


def test_read_proc_status_permission_denied_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_access(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("procfs access denied")

    monkeypatch.setattr("builtins.open", deny_access)

    assert read_proc_status(1234) is None


def test_read_current_python_pid_status_returns_proc_status() -> None:
    status = read_proc_status(os.getpid())

    assert isinstance(status, ProcStatus)
