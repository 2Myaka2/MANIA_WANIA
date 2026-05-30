"""Report skeleton helpers for MANIA."""

from __future__ import annotations

from dataclasses import dataclass

from mania.export.manifest import Manifest
from mania.pipeline import PipelinePlan
from mania.qc.runner import QCReport


@dataclass(frozen=True)
class ReportSummary:
    """Immutable summary of a future MANIA analysis report."""

    title: str
    project_name: str
    run_id: str
    run_mode: str
    conditions: tuple[str, ...]
    qc_passed: bool
    artifact_count: int


def build_report_summary(
    plan: PipelinePlan,
    manifest: Manifest,
    qc_report: QCReport,
) -> ReportSummary:
    """Build a report summary skeleton without filesystem I/O."""
    artifact_count = (
        len(manifest.per_condition_artifacts) * len(plan.conditions)
        + len(manifest.cross_condition_artifacts)
    )
    return ReportSummary(
        title="MANIA analysis report skeleton",
        project_name=plan.project_name,
        run_id=plan.run_id,
        run_mode=plan.run_mode,
        conditions=plan.conditions,
        qc_passed=qc_report.passed,
        artifact_count=artifact_count,
    )


def report_summary_to_dict(summary: ReportSummary) -> dict[str, object]:
    """Return a JSON-serializable dictionary for a report summary."""
    return {
        "title": summary.title,
        "project_name": summary.project_name,
        "run_id": summary.run_id,
        "run_mode": summary.run_mode,
        "conditions": list(summary.conditions),
        "qc_passed": summary.qc_passed,
        "artifact_count": summary.artifact_count,
    }


def format_report_summary(summary: ReportSummary) -> str:
    """Format a report summary as a stable human-readable message."""
    return "\n".join(
        [
            summary.title,
            f"Project: {summary.project_name}",
            f"Run ID: {summary.run_id}",
            f"Run mode: {summary.run_mode}",
            f"Conditions: {', '.join(summary.conditions)}",
            f"QC passed: {str(summary.qc_passed).lower()}",
            f"Expected artifacts: {summary.artifact_count}",
        ]
    )


__all__ = [
    "ReportSummary",
    "build_report_summary",
    "format_report_summary",
    "report_summary_to_dict",
]
