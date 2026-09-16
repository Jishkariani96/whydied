import subprocess
from datetime import UTC, datetime, timedelta, timezone

import pytest

from whydied.kernel import (
    parse_oom_kill_events,
    read_kernel_cursor,
    read_kernel_log,
    read_kernel_log_after,
)
from whydied.models import (
    KernelCursorAvailable,
    KernelCursorUnavailable,
    KernelLogAvailable,
    KernelLogUnavailable,
    OOMKillEvent,
)


def test_read_kernel_cursor_extracts_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=0,
            stdout="kernel message\n  -- cursor: s=abc123;i=456  \n",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_cursor() == KernelCursorAvailable(cursor="s=abc123;i=456")


def test_read_kernel_cursor_constructs_deterministic_command(
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
            stdout="-- cursor: cursor-value\n",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    read_kernel_cursor()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (["journalctl", "-k", "--no-pager", "--show-cursor", "-n", "1"],)
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True


def test_read_kernel_cursor_success_without_cursor_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=0,
            stdout="kernel message only\n",
            stderr="",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_cursor() == KernelCursorUnavailable(
        reason="kernel journal cursor unavailable"
    )


def test_read_kernel_cursor_non_zero_exit_uses_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=1,
            stdout="",
            stderr="permission denied\n",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_cursor() == KernelCursorUnavailable(reason="permission denied")


def test_read_kernel_cursor_non_zero_exit_empty_stderr_has_fallback(
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

    assert read_kernel_cursor() == KernelCursorUnavailable(
        reason="journalctl exited with status 7"
    )


def test_read_kernel_cursor_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_cursor() == KernelCursorUnavailable(
        reason="journalctl executable not found"
    )


def test_read_kernel_cursor_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise OSError("execution failed deterministically")

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_cursor() == KernelCursorUnavailable(
        reason="failed to run journalctl: execution failed deterministically"
    )


def test_read_kernel_log_after_constructs_deterministic_command(
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

    read_kernel_log_after("s=abc123;i=456")

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        [
            "journalctl",
            "-k",
            "--after-cursor=s=abc123;i=456",
            "-o",
            "cat",
            "--no-pager",
        ],
    )
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True


def test_read_kernel_log_after_collects_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    assert read_kernel_log_after("cursor") == KernelLogAvailable(
        messages=("first kernel message", "second kernel message")
    )


def test_read_kernel_log_after_empty_successful_output(
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

    assert read_kernel_log_after("cursor") == KernelLogAvailable(messages=())


def test_read_kernel_log_after_non_zero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["journalctl"],
            returncode=1,
            stdout="",
            stderr="permission denied\n",
        )

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_log_after("cursor") == KernelLogUnavailable(
        reason="permission denied"
    )


def test_read_kernel_log_after_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_log_after("cursor") == KernelLogUnavailable(
        reason="journalctl executable not found"
    )


def test_read_kernel_log_after_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_journalctl(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise OSError("execution failed deterministically")

    monkeypatch.setattr("whydied.kernel.subprocess.run", run_journalctl)

    assert read_kernel_log_after("cursor") == KernelLogUnavailable(
        reason="failed to run journalctl: execution failed deterministically"
    )


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


def test_read_kernel_log_until_only_includes_timestamp_and_offset(
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
        until=datetime(
            2025,
            1,
            2,
            6,
            7,
            8,
            tzinfo=timezone(timedelta(hours=-3)),
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
            "--until",
            "2025-01-02T06:07:08-03:00",
        ],
    )
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True


def test_read_kernel_log_since_and_until_are_in_deterministic_order(
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
        since=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        until=datetime(2025, 1, 2, 3, 5, 5, tzinfo=UTC),
    )

    assert len(calls) == 1
    args, _kwargs = calls[0]
    assert args == (
        [
            "journalctl",
            "-k",
            "-o",
            "cat",
            "--no-pager",
            "--since",
            "2025-01-02T03:04:05+00:00",
            "--until",
            "2025-01-02T03:05:05+00:00",
        ],
    )


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


def test_read_kernel_log_naive_until_raises_value_error_without_subprocess(
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

    with pytest.raises(ValueError, match="until must be a timezone-aware datetime"):
        read_kernel_log(until=datetime(2025, 1, 2, 3, 4, 5))  # noqa: DTZ001

    assert subprocess_called is False


def test_read_kernel_log_invalid_interval_raises_value_error_without_subprocess(
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

    with pytest.raises(ValueError, match="since must be less than or equal to until"):
        read_kernel_log(
            since=datetime(2025, 1, 2, 3, 5, 5, tzinfo=UTC),
            until=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        )

    assert subprocess_called is False


def test_read_kernel_log_equal_boundaries_are_accepted(
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

    boundary = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    read_kernel_log(since=boundary, until=boundary)

    assert len(calls) == 1
    args, _kwargs = calls[0]
    assert args == (
        [
            "journalctl",
            "-k",
            "-o",
            "cat",
            "--no-pager",
            "--since",
            "2025-01-02T03:04:05+00:00",
            "--until",
            "2025-01-02T03:04:05+00:00",
        ],
    )


def test_read_kernel_log_compares_chronology_across_offsets(
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
            12,
            0,
            0,
            tzinfo=timezone(timedelta(hours=4)),
        ),
        until=datetime(2025, 1, 2, 9, 0, 0, tzinfo=UTC),
    )

    assert len(calls) == 1
    args, _kwargs = calls[0]
    assert args == (
        [
            "journalctl",
            "-k",
            "-o",
            "cat",
            "--no-pager",
            "--since",
            "2025-01-02T12:00:00+04:00",
            "--until",
            "2025-01-02T09:00:00+00:00",
        ],
    )


def test_read_kernel_log_rejects_cross_offset_interval_by_actual_chronology(
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

    with pytest.raises(ValueError, match="since must be less than or equal to until"):
        read_kernel_log(
            since=datetime(2025, 1, 2, 8, 0, 0, tzinfo=UTC),
            until=datetime(
                2025,
                1,
                2,
                12,
                30,
                0,
                tzinfo=timezone(timedelta(hours=5)),
            ),
        )

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
