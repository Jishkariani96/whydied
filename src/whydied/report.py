from whydied.models import (
    DiagnosisCause,
    ExitTermination,
    InspectionResult,
    KernelEvidenceStatus,
    SignalTermination,
)

_MIB = 1024 * 1024

_SIGNAL_EXPLANATIONS = {
    "SIGABRT": "abort signal",
    "SIGSEGV": "segmentation fault",
    "SIGTERM": "termination request",
}


def format_report(inspection: InspectionResult) -> str:
    """Format an inspection result as a deterministic human-readable report."""
    process = inspection.process
    diagnosis = inspection.diagnosis

    lines = [
        "Process:",
        f"  PID: {process.pid}",
        f"  Runtime: {process.runtime_seconds:.2f}s",
        f"  Return code: {process.returncode}",
        f"  Termination: {_format_termination(process.termination)}",
        "",
        "Diagnosis:",
        f"  Cause: {_format_cause(diagnosis.cause)}",
    ]

    if isinstance(process.termination, SignalTermination):
        lines.append(f"  Detail: {_format_signal_detail(process.termination)}")

    if diagnosis.cause in (DiagnosisCause.OOM_KILL, DiagnosisCause.UNKNOWN):
        lines.append(
            f"  Kernel evidence: {_format_kernel_evidence(diagnosis.kernel_evidence)}"
        )

    lines.extend(("", "Memory:"))

    if process.proc_status is None:
        lines.append("  unavailable")
    else:
        lines.extend(
            (
                f"  RSS: {_format_memory(process.proc_status.rss_bytes)}",
                f"  Peak RSS: {_format_memory(process.proc_status.peak_rss_bytes)}",
            )
        )

    return "\n".join(lines)


def _format_termination(termination: ExitTermination | SignalTermination) -> str:
    if isinstance(termination, ExitTermination):
        return f"exit {termination.code}"
    return f"{termination.name} ({termination.number})"


def _format_signal_detail(termination: SignalTermination) -> str:
    detail = f"process received {termination.name}"
    explanation = _SIGNAL_EXPLANATIONS.get(termination.name)
    if explanation is not None:
        detail += f" ({explanation})"
    return detail


def _format_cause(cause: DiagnosisCause) -> str:
    return {
        DiagnosisCause.CLEAN_EXIT: "clean exit",
        DiagnosisCause.NON_ZERO_EXIT: "non-zero exit",
        DiagnosisCause.SIGNAL: "signal termination",
        DiagnosisCause.OOM_KILL: "OOM kill",
        DiagnosisCause.UNKNOWN: "unknown",
    }[cause]


def _format_kernel_evidence(status: KernelEvidenceStatus) -> str:
    return {
        KernelEvidenceStatus.OOM_VICTIM_MATCH: "matching OOM victim found",
        KernelEvidenceStatus.NO_OOM_VICTIM_MATCH: "no matching OOM victim",
        KernelEvidenceStatus.UNAVAILABLE: "unavailable",
    }[status]


def _format_memory(byte_count: int | None) -> str:
    if byte_count is None:
        return "unavailable"
    return f"{byte_count / _MIB:.2f} MiB"
