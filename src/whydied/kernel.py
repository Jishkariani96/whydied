import subprocess
from datetime import datetime

from whydied.models import KernelLogAvailable, KernelLogUnavailable


def read_kernel_log(
    since: datetime | None = None,
) -> KernelLogAvailable | KernelLogUnavailable:
    command = ["journalctl", "-k", "-o", "cat", "--no-pager"]
    if since is not None:
        if since.tzinfo is None or since.utcoffset() is None:
            raise ValueError("since must be a timezone-aware datetime")
        command.extend(["--since", since.isoformat()])

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
