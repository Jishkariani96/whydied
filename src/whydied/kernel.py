import subprocess

from whydied.models import KernelLogAvailable, KernelLogUnavailable


def read_kernel_log() -> KernelLogAvailable | KernelLogUnavailable:
    try:
        result = subprocess.run(
            ["journalctl", "-k", "-o", "cat", "--no-pager"],
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
