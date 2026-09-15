import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from whydied.kernel import parse_oom_kill_events, read_kernel_log
from whydied.models import KernelLogAvailable, KernelLogUnavailable, OOMKillEvent


def test_read_kernel_log_successful_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=0,
            stdout="first kernel message\nsecond kernel message\n",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_log() == KernelLogAvailable(
        messages=(
            "first kernel message",
            "second kernel message",
        )
    )


def test_read_kernel_log_empty_successful_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_log() == KernelLogAvailable(messages=())


def test_read_kernel_log_non_zero_exit_uses_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=1,
            stdout="",
            stderr="No journal files were opened due to insufficient permissions.\n",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    result = read_kernel_log()

    assert isinstance(result, KernelLogUnavailable)
    assert (
        result.reason == "No journal files were opened due to insufficient permissions."
    )
    assert "oom" not in result.reason.lower()


def test_read_kernel_log_non_zero_exit_empty_stderr_has_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=7,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    result = read_kernel_log()

    assert isinstance(result, KernelLogUnavailable)
    assert result.reason == "journalctl exited with status 7"


def test_read_kernel_log_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    result = read_kernel_log()

    assert isinstance(result, KernelLogUnavailable)
    assert result.reason == "journalctl executable not found"


def test_read_kernel_log_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise OSError("execution failed deterministically")

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    result = read_kernel_log()

    assert isinstance(result, KernelLogUnavailable)
    assert (
        result.reason == "failed to run journalctl: execution failed deterministically"
    )


def test_read_kernel_log_with_since_includes_timestamp_and_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def run_journalctl(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    read_kernel_log(
        since=datetime(
            2025,
            1,
            2,
            3,
            4,
            5,
            tzinfo=timezone(timedelta(hours=4)),
        )
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        [
            "journalctl",
            "-k",
            "-o",
            "cat",
            "--no-pager",
            "--since",
            "2025-01-02T03:04:05+04:00",
        ],
    )
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True


def test_read_kernel_log_naive_since_raises_value_error_without_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess_called = False

    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal subprocess_called
        subprocess_called = True
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    with pytest.raises(ValueError, match="timezone-aware"):
        read_kernel_log(since=datetime(2025, 1, 2, 3, 4, 5))  # noqa: DTZ001

    assert subprocess_called is False


def test_read_kernel_log_command_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def run_journalctl(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    read_kernel_log()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (["journalctl", "-k", "-o", "cat", "--no-pager"],)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True


def test_parse_oom_kill_events_modern_victim_line() -> None:
    events = parse_oom_kill_events(
        (
            (
                "kernel: Out of memory: Killed process 1234 (python) "
                "total-vm:1000kB, anon-rss:200kB, file-rss:0kB, "
                "shmem-rss:0kB, UID:1000 pgtables:64kB oom_score_adj:0"
            ),
        )
    )

    assert events == (OOMKillEvent(victim_pid=1234, victim_name="python"),)


def test_parse_oom_kill_events_short_victim_line() -> None:
    events = parse_oom_kill_events(("Killed process 42 (worker)",))

    assert events == (OOMKillEvent(victim_pid=42, victim_name="worker"),)


def test_parse_oom_kill_events_allows_text_before_victim_structure() -> None:
    events = parse_oom_kill_events(
        ("localhost kernel: memory: Killed process 99 (service) now",)
    )

    assert events == (OOMKillEvent(victim_pid=99, victim_name="service"),)


def test_parse_oom_kill_events_extracts_pid_as_integer() -> None:
    event = parse_oom_kill_events(("Killed process 5678 (batch)",))[0]

    assert event.victim_pid == 5678
    assert isinstance(event.victim_pid, int)


def test_parse_oom_kill_events_preserves_process_name() -> None:
    event = parse_oom_kill_events(("Killed process 123 (PyThOn-worker.1)",))[0]

    assert event.victim_name == "PyThOn-worker.1"


def test_parse_oom_kill_events_multiple_events_preserve_order() -> None:
    events = parse_oom_kill_events(
        (
            "Killed process 10 (first)",
            "unrelated kernel message",
            "Killed process 20 (second)",
        )
    )

    assert events == (
        OOMKillEvent(victim_pid=10, victim_name="first"),
        OOMKillEvent(victim_pid=20, victim_name="second"),
    )


def test_parse_oom_kill_events_unrelated_messages_produce_no_events() -> None:
    events = parse_oom_kill_events(
        (
            "usb 1-1: new high-speed USB device number 2",
            "eth0: link becomes ready",
            "process exited after SIGKILL",
        )
    )

    assert events == ()


def test_parse_oom_kill_events_oom_kill_context_without_victim_produces_no_event() -> (
    None
):
    events = parse_oom_kill_events(
        ("oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=/",)
    )

    assert events == ()


def test_parse_oom_kill_events_out_of_memory_without_victim_produces_no_event() -> None:
    events = parse_oom_kill_events(("Out of memory: Kill process 123 (python)",))

    assert events == ()


def test_parse_oom_kill_events_malformed_victim_lines_produce_no_events() -> None:
    events = parse_oom_kill_events(
        (
            "Killed process (python)",
            "Killed process abc (python)",
            "Killed process 0 (python)",
            "Killed process 123 ()",
            "Killed process 123 python",
            "Killed process 123 (python",
        )
    )

    assert events == ()


def test_parse_oom_kill_events_empty_input_produces_empty_tuple() -> None:
    assert parse_oom_kill_events(()) == ()
