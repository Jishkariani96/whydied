import pytest

from whydied.models import (
    Diagnosis,
    DiagnosisCause,
    ExitTermination,
    InspectionResult,
    KernelEvidenceStatus,
    KernelLogAvailable,
    ProcessResult,
    ProcStatus,
    SignalTermination,
)
from whydied.report import format_report

_DEFAULT_TERMINATION = ExitTermination(code=0)
_DEFAULT_PROC_STATUS = ProcStatus(
    state="R (running)",
    rss_bytes=1024 * 1024,
    peak_rss_bytes=2 * 1024 * 1024,
)


def _inspection(
    *,
    termination: ExitTermination | SignalTermination = _DEFAULT_TERMINATION,
    cause: DiagnosisCause = DiagnosisCause.CLEAN_EXIT,
    kernel_evidence: KernelEvidenceStatus = (KernelEvidenceStatus.NO_OOM_VICTIM_MATCH),
    proc_status: ProcStatus | None = _DEFAULT_PROC_STATUS,
) -> InspectionResult:
    return InspectionResult(
        process=ProcessResult(
            pid=1234,
            runtime_seconds=1.236,
            returncode=(
                termination.code
                if isinstance(termination, ExitTermination)
                else -termination.number
            ),
            termination=termination,
            proc_status=proc_status,
        ),
        kernel_log=KernelLogAvailable(messages=()),
        diagnosis=Diagnosis(cause=cause, kernel_evidence=kernel_evidence),
    )


def test_format_report_for_normal_exit_and_clean_exit_diagnosis() -> None:
    report = format_report(_inspection())

    assert (
        report
        == """Process:
  PID: 1234
  Runtime: 1.24s
  Return code: 0
  Termination: exit 0

Diagnosis:
  Cause: clean exit
  Kernel evidence: no matching OOM victim

Memory:
  RSS: 1.00 MiB
  Peak RSS: 2.00 MiB"""
    )


@pytest.mark.parametrize(
    ("cause", "label"),
    (
        (DiagnosisCause.CLEAN_EXIT, "clean exit"),
        (DiagnosisCause.NON_ZERO_EXIT, "non-zero exit"),
        (DiagnosisCause.SIGNAL, "signal termination"),
        (DiagnosisCause.OOM_KILL, "OOM kill"),
        (DiagnosisCause.UNKNOWN, "unknown"),
    ),
)
def test_format_report_formats_diagnosis_causes(
    cause: DiagnosisCause,
    label: str,
) -> None:
    report = format_report(_inspection(cause=cause))

    assert f"  Cause: {label}" in report


def test_format_report_for_signal_termination_and_confirmed_oom() -> None:
    report = format_report(
        _inspection(
            termination=SignalTermination(number=9, name="SIGKILL"),
            cause=DiagnosisCause.OOM_KILL,
            kernel_evidence=KernelEvidenceStatus.OOM_VICTIM_MATCH,
        )
    )

    assert "  Return code: -9" in report
    assert "  Termination: SIGKILL (9)" in report
    assert "  Cause: OOM kill" in report
    assert "  Kernel evidence: matching OOM victim found" in report


def test_format_report_with_unavailable_kernel_evidence() -> None:
    report = format_report(
        _inspection(kernel_evidence=KernelEvidenceStatus.UNAVAILABLE)
    )

    assert "  Kernel evidence: unavailable" in report


def test_format_report_with_unavailable_proc_status() -> None:
    report = format_report(_inspection(proc_status=None))

    assert report.endswith("Memory:\n  unavailable")


@pytest.mark.parametrize(
    ("rss_bytes", "peak_rss_bytes", "expected_memory"),
    (
        (None, 2 * 1024 * 1024, "RSS: unavailable\n  Peak RSS: 2.00 MiB"),
        (1024 * 1024, None, "RSS: 1.00 MiB\n  Peak RSS: unavailable"),
    ),
)
def test_format_report_with_individual_missing_memory_fields(
    rss_bytes: int | None,
    peak_rss_bytes: int | None,
    expected_memory: str,
) -> None:
    report = format_report(
        _inspection(
            proc_status=ProcStatus(
                state=None,
                rss_bytes=rss_bytes,
                peak_rss_bytes=peak_rss_bytes,
            )
        )
    )

    assert report.endswith(f"Memory:\n  {expected_memory}")


def test_format_report_converts_bytes_to_mebibytes_deterministically() -> None:
    report = format_report(
        _inspection(
            proc_status=ProcStatus(
                state=None,
                rss_bytes=1_572_864,
                peak_rss_bytes=2_621_440,
            )
        )
    )

    assert report.endswith("Memory:\n  RSS: 1.50 MiB\n  Peak RSS: 2.50 MiB")
