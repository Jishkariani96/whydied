from dataclasses import dataclass


@dataclass(frozen=True)
class KernelLogAvailable:
    messages: tuple[str, ...]


@dataclass(frozen=True)
class KernelLogUnavailable:
    reason: str


KernelLog = KernelLogAvailable | KernelLogUnavailable


@dataclass(frozen=True)
class ProcStatus:
    state: str | None
    rss_bytes: int | None
    peak_rss_bytes: int | None


@dataclass(frozen=True)
class ExitTermination:
    code: int


@dataclass(frozen=True)
class SignalTermination:
    number: int
    name: str


@dataclass(frozen=True)
class ProcessResult:
    pid: int
    runtime_seconds: float
    returncode: int
    termination: ExitTermination | SignalTermination
    proc_status: ProcStatus | None
