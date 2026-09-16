import re
import subprocess
from datetime import datetime

from whydied.models import (
    KernelCursor,
    KernelCursorAvailable,
    KernelCursorUnavailable,
    KernelLogAvailable,
    KernelLogUnavailable,
    OOMKillEvent,
)

_OOM_KILL_EVENT_PATTERN = re.compile(r"\bKilled process ([1-9][0-9]*) \(([^)]+)\)")
_CURSOR_PREFIX = "-- cursor:"


def read_kernel_cursor() -> KernelCursor:
    command = ["journalctl", "-k", "--no-pager", "--show-cursor", "-n", "1"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return KernelCursorUnavailable(reason="journalctl executable not found")
    except OSError as exc:
        return KernelCursorUnavailable(reason=f"failed to run journalctl: {exc}")

    if result.returncode != 0:
        reason = result.stderr.strip()
        if not reason:
            reason = f"journalctl exited with status {result.returncode}"
        return KernelCursorUnavailable(reason=reason)

    for line in result.stdout.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith(_CURSOR_PREFIX):
            cursor = stripped_line.removeprefix(_CURSOR_PREFIX).strip()
            if cursor:
                return KernelCursorAvailable(cursor=cursor)

    return KernelCursorUnavailable(reason="kernel journal cursor unavailable")


def read_kernel_log(
    since: datetime | None = None,
    until: datetime | None = None,
) -> KernelLogAvailable | KernelLogUnavailable:
    command = ["journalctl", "-k", "-o", "cat", "--no-pager"]
    if since is not None:
        _validate_aware_datetime(since, "since")
        command.extend(["--since", since.isoformat()])
    if until is not None:
        _validate_aware_datetime(until, "until")
        command.extend(["--until", until.isoformat()])
    if since is not None and until is not None and since > until:
        raise ValueError("since must be less than or equal to until")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return KernelLogUnavailable(reason="journalctl executable not found")
    except OSError as exc:
        return KernelLogUnavailable(reason=f"failed to run journalctl: {exc}")

    if result.returncode != 0:
        reason = result.stderr.strip()
        if not reason:
            reason = f"journalctl exited with status {result.returncode}"
        return KernelLogUnavailable(reason=reason)

    return KernelLogAvailable(
        messages=tuple(line for line in result.stdout.splitlines() if line != "")
    )


def _validate_aware_datetime(value: datetime, parameter_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{parameter_name} must be a timezone-aware datetime")


def parse_oom_kill_events(
    messages: tuple[str, ...],
) -> tuple[OOMKillEvent, ...]:
    events: list[OOMKillEvent] = []
    for message in messages:
        match = _OOM_KILL_EVENT_PATTERN.search(message)
        if match is None:
            continue
        events.append(
            OOMKillEvent(
                victim_pid=int(match.group(1)),
                victim_name=match.group(2),
            )
        )
    return tuple(events)
