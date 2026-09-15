from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class KernelLogAvailable:
    messages: tuple[str, ...]


@dataclass(frozen=True)
class KernelLogUnavailable:
    reason: str


KernelLog = KernelLogAvailable | KernelLogUnavailable


@dataclass(frozen=True)
class OOMKillEvent:
    victim_pid: int
    victim_name: str


class DiagnosisCause(StrEnum):
    OOM_KILL = "oom_kill"
    UNKNOWN = "unknown"


class KernelEvidenceStatus(StrEnum):
    OOM_VICTIM_MATCH = "oom_victim_match"
    NO_OOM_VICTIM_MATCH = "no_oom_victim_match"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Diagnosis:
    cause: DiagnosisCause
    kernel_evidence: KernelEvidenceStatus


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


@dataclass(frozen=True)
class InspectionResult:
    process: ProcessResult
    kernel_log: KernelLog
    diagnosis: Diagnosis
