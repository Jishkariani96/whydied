from whydied.models import ProcStatus

_KB_IN_BYTES = 1024


def _parse_kb_value(value: str) -> int:
    return int(value.split()[0]) * _KB_IN_BYTES


def _parse_proc_status(text: str) -> ProcStatus:
    state: str | None = None
    rss_bytes: int | None = None
    peak_rss_bytes: int | None = None

    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator == "":
            continue

        value = value.strip()
        if key == "State":
            state = value
        elif key == "VmRSS":
            rss_bytes = _parse_kb_value(value)
        elif key == "VmHWM":
            peak_rss_bytes = _parse_kb_value(value)

    return ProcStatus(
        state=state,
        rss_bytes=rss_bytes,
        peak_rss_bytes=peak_rss_bytes,
    )


def read_proc_status(pid: int) -> ProcStatus | None:
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as status_file:
            return _parse_proc_status(status_file.read())
    except FileNotFoundError:
        return None
