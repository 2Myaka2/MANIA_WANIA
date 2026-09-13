"""Lossless normalization of authoritative Stage 32 decisions and summary."""

from dataclasses import asdict, dataclass, replace

from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_qc_summary import DatasetQCSummary, build_dataset_qc_summary
from mania.dataset_release_csv import DatasetReleaseTable, build_publication_table
from mania.replica_aggregation_manifest import require_fixed_metadata


class DatasetReleaseQCError(ValueError):
    """Inconsistent or non-production-resolved publication QC evidence."""


def validate_publication_qc_inputs(
    decisions: DatasetQCDecisionSet,
    summary: DatasetQCSummary,
) -> None:
    if (
        type(decisions) is not DatasetQCDecisionSet
        or type(summary) is not DatasetQCSummary
    ):
        raise DatasetReleaseQCError("Expected accepted Stage 32 decisions and summary")
    require_fixed_metadata(decisions)
    records = tuple(
        replace(
            r,
            findings=tuple(
                replace(f, evidence=tuple(replace(e) for e in f.evidence))
                for f in r.findings
            ),
        )
        for r in decisions.records
    )
    if DatasetQCDecisionSet(records) != decisions:
        raise DatasetReleaseQCError("Decision input must already be validated")
    if not records:
        raise DatasetReleaseQCError(
            "Publication requires at least one candidate replica"
        )
    if any(r.release_decision == "pending_review" for r in records):
        raise DatasetReleaseQCError("pending_review is not a publishable release state")
    # This accepted Stage 32 projection checks counts and decision identity; it
    # does not invoke either QC evaluator or calculate a scientific observation.
    if replace(summary) != build_dataset_qc_summary(decisions):
        raise DatasetReleaseQCError("Stage 32 summary and decisions disagree")


@dataclass(frozen=True)
class DatasetReleaseQCTables:
    quality_control: DatasetReleaseTable
    quality_control_findings: DatasetReleaseTable
    quality_control_evidence: DatasetReleaseTable


def build_dataset_release_qc_tables(
    decisions: DatasetQCDecisionSet,
    summary: DatasetQCSummary,
) -> DatasetReleaseQCTables:
    """Keep PASS findings, all evidence, selected IDs and manual provenance."""
    validate_publication_qc_inputs(decisions, summary)
    findings: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    for decision in decisions.records:
        identity = dict(
            zip(
                ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                decision.replica_key,
                strict=True,
            )
        )
        selected = set(decision.decision_evidence_ids)
        traced: list[str] = []
        for finding in decision.findings:
            findings.append(
                {
                    **identity,
                    "check_id": finding.check_id,
                    "status": finding.status,
                    "reason_code": finding.reason_code,
                    "human_readable_reason": finding.human_readable_reason,
                }
            )
            for item in finding.evidence:
                used = item.evidence_id in selected
                if used:
                    traced.append(item.evidence_id)
                evidence.append(
                    {
                        **identity,
                        "check_id": finding.check_id,
                        **item.to_dict(),
                        "used_for_decision": used,
                    }
                )
        if len(traced) != len(selected) or set(traced) != selected:
            raise DatasetReleaseQCError("Decision evidence must map exactly once")
    return DatasetReleaseQCTables(
        build_publication_table("quality_control", (asdict(r) for r in summary.rows)),
        build_publication_table("quality_control_findings", findings),
        build_publication_table("quality_control_evidence", evidence),
    )
