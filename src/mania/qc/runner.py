"""QC report skeleton helpers for MANIA."""

from __future__ import annotations

from dataclasses import dataclass

QC_LEVELS = ("info", "warning", "error")


@dataclass(frozen=True)
class QCMessage:
    """Immutable message in a MANIA QC report."""

    code: str
    level: str
    message: str


@dataclass(frozen=True)
class QCReport:
    """Immutable summary of future MANIA QC checks."""

    passed: bool
    messages: tuple[QCMessage, ...]


def make_qc_message(code: str, level: str, message: str) -> QCMessage:
    """Build a QC message after validating its level."""
    if level not in QC_LEVELS:
        raise ValueError(f"Unknown QC level: {level}")
    return QCMessage(code=code, level=level, message=message)


def build_empty_qc_report() -> QCReport:
    """Build an empty passing QC report."""
    return QCReport(passed=True, messages=())


def build_skeleton_qc_report() -> QCReport:
    """Build a placeholder QC report without running real checks."""
    return QCReport(
        passed=True,
        messages=(
            make_qc_message(
                code="QC_SKEL_001",
                level="info",
                message="QC checks are not implemented yet.",
            ),
        ),
    )


def qc_report_to_dict(report: QCReport) -> dict[str, object]:
    """Return a JSON-serializable dictionary for a QC report skeleton."""
    return {
        "passed": report.passed,
        "messages": [
            {
                "code": message.code,
                "level": message.level,
                "message": message.message,
            }
            for message in report.messages
        ],
    }


def format_qc_report_summary(report: QCReport) -> str:
    """Format a QC report skeleton as a stable human-readable message."""
    lines = [
        "MANIA QC report skeleton",
        f"Passed: {str(report.passed).lower()}",
        f"Messages: {len(report.messages)}",
    ]
    lines.extend(
        f"[{message.level}] {message.code}: {message.message}"
        for message in report.messages
    )
    return "\n".join(lines)


__all__ = [
    "QC_LEVELS",
    "QCMessage",
    "QCReport",
    "build_empty_qc_report",
    "build_skeleton_qc_report",
    "format_qc_report_summary",
    "make_qc_message",
    "qc_report_to_dict",
]
