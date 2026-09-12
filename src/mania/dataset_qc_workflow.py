"""Stage 32 orchestration and pure production bridge; no trajectory runtime."""

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from pathlib import Path

from mania.dataset_hard_qc import ReplicaHardQCEvaluation, evaluate_replica_hard_qc
from mania.dataset_qc_contract import (
    DatasetQCDecisionSet,
    ReplicaQCDecisionRecord,
    build_dataset_qc_decision_set,
)
from mania.dataset_qc_evidence_io import (
    read_replica_hard_qc_evidence,
    read_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import DatasetQCManifest, QCManualReviewResolution
from mania.dataset_qc_manifest_io import read_dataset_qc_manifest
from mania.dataset_qc_summary import DatasetQCSummary, build_dataset_qc_summary
from mania.dataset_review_qc import (
    ReplicaReviewQCEvaluation,
    evaluate_dataset_review_qc,
)
from mania.replica_aggregation_manifest import ReplicaAggregationManifest
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_specialized_aggregation import SpecializedPartnerCorrespondences

QC_DERIVED_REPLICA_AGGREGATION_MANIFEST_FILENAME = (
    "replica_aggregation_manifest_qc_derived.json"
)
ReplicaKey = tuple[str, str, str, str]


class DatasetQCWorkflowError(ValueError):
    """Portable failure with deterministic workflow-phase prefix."""


def require_qc_coverage(
    template: ReplicaAggregationManifest,
    keys: tuple[ReplicaKey, ...],
) -> None:
    if type(template) is not ReplicaAggregationManifest:
        raise ValueError("Expected exact Stage 31 aggregation manifest")
    # Revalidate nested correspondences even for direct callers with damaged models.
    replace(template)
    members = tuple(m for g in template.groups for m in g.members)
    if any(m.availability_status == "excluded" for m in members):
        raise ValueError("Pre-QC excluded template members are forbidden")
    if len(keys) != len(set(keys)) or set(keys) != {m.replica_key for m in members}:
        raise ValueError("QC must cover exactly the template full replica-key set")


def _project_correspondences(
    source: SpecializedPartnerCorrespondences,
    available: set[ReplicaKey],
) -> SpecializedPartnerCorrespondences:
    if not available:
        return SpecializedPartnerCorrespondences(())
    projected = []
    for correspondence in source.correspondences:
        members = tuple(m for m in correspondence.members if m.replica_key in available)
        if {m.replica_key for m in members} != available:
            raise ValueError("Retained correspondence binding is missing")
        projected.append(replace(correspondence, members=members))
    return SpecializedPartnerCorrespondences(tuple(projected))


def build_qc_derived_replica_aggregation_manifest(
    template: ReplicaAggregationManifest,
    decisions: DatasetQCDecisionSet,
) -> ReplicaAggregationManifest:
    """Restrict authorized correspondence membership; never infer local bindings."""
    if type(decisions) is not DatasetQCDecisionSet:
        raise ValueError("Expected exact accepted QC decision set")
    validated = build_dataset_qc_decision_set(
        tuple(replace(r) for r in decisions.records)
    )
    require_qc_coverage(template, tuple(r.replica_key for r in validated.records))
    authority = {r.replica_key: r for r in validated.records}
    if any(r.release_decision == "pending_review" for r in validated.records):
        raise ValueError("Pending review forbids a production aggregation manifest")
    groups = []
    for group in template.groups:
        members = []
        for member in group.members:
            decision = authority[member.replica_key]
            if member.availability_status == "unavailable":
                members.append(member)
            elif decision.release_decision == "excluded":
                members.append(
                    replace(
                        member,
                        availability_status="excluded",
                        availability_reason=(
                            f"QC exclusion [{decision.decision_reason_code}]: "
                            f"{decision.human_readable_reason}"
                        ),
                    )
                )
            else:
                members.append(
                    replace(
                        member,
                        availability_status="available",
                        availability_reason=None,
                    )
                )
        available = {
            m.replica_key for m in members if m.availability_status == "available"
        }
        groups.append(
            replace(
                group,
                members=tuple(members),
                lipid_correspondences=_project_correspondences(
                    group.lipid_correspondences,
                    available,
                ),
                glycan_correspondences=_project_correspondences(
                    group.glycan_correspondences,
                    available,
                ),
            )
        )
    return replace(template, groups=tuple(groups))


def build_replica_qc_decision(
    hard: ReplicaHardQCEvaluation,
    review: ReplicaReviewQCEvaluation | None,
    manual: QCManualReviewResolution | None,
) -> ReplicaQCDecisionRecord:
    """Combine accepted findings, with first FAIL/REVIEW automatic authority."""
    if hard.hard_qc_status == "fail":
        if manual is not None or review is not None:
            raise ValueError("Hard FAIL forbids manual resolution and review authority")
        findings = hard.checks
    else:
        if review is None or review.replica_key != hard.replica_key:
            raise ValueError("Hard PASS requires matching review evaluation")
        findings = hard.checks + review.checks
    primary = next((f for f in findings if f.status != "pass"), None)
    if manual is not None:
        if primary is None or primary.status != "review":
            raise ValueError("Manual resolution is only permitted for REVIEW")
        return ReplicaQCDecisionRecord(
            *hard.replica_key,
            "review",
            findings,
            manual.release_decision,
            "manual",
            manual.decision_reason_code,
            manual.human_readable_reason,
            manual.decision_evidence_ids,
            manual.reviewer,
            manual.decision_note,
        )
    return ReplicaQCDecisionRecord(
        *hard.replica_key,
        "pass" if primary is None else primary.status,
        findings,
        "available"
        if primary is None
        else ("excluded" if primary.status == "fail" else "pending_review"),
        "automatic",
        None if primary is None else primary.reason_code,
        None if primary is None else primary.human_readable_reason,
        () if primary is None else tuple(e.evidence_id for e in primary.evidence),
        None,
        None,
    )


@dataclass(frozen=True)
class DatasetQCOutputs:
    manifest: DatasetQCManifest
    decisions: DatasetQCDecisionSet
    summary: DatasetQCSummary
    derived_manifest: ReplicaAggregationManifest | None

    @property
    def production_ready(self) -> bool:
        return all(
            r.release_decision != "pending_review" for r in self.decisions.records
        )


def execute_dataset_qc_manifest(
    manifest: DatasetQCManifest,
    manifest_path: Path,
    *,
    mapped_paths: Mapping[Path, Path] | None = None,
) -> DatasetQCOutputs:
    """Build all output models before any writer is invoked.

    Explicit validation mappings are keyed by manifest-relative control paths;
    ordinary execution resolves those paths against the QC manifest location.
    """

    def resolve(path: Path) -> Path:
        return (
            manifest_path.parent / path if mapped_paths is None else mapped_paths[path]
        )

    phase = "aggregation bridge"
    try:
        template = read_replica_aggregation_manifest(
            resolve(manifest.aggregation_manifest_template_path),
        )
        require_qc_coverage(template, tuple(r.replica_key for r in manifest.replicas))
        phase = "evidence"
        hard_inputs = tuple(
            read_replica_hard_qc_evidence(
                resolve(r.hard_qc_evidence_path),
            )
            for r in manifest.replicas
        )
        for replica, evidence in zip(manifest.replicas, hard_inputs, strict=True):
            if evidence.identity.replica_key != replica.replica_key:
                raise ValueError("Hard evidence identity must match full replica key")
        phase = "hard QC"
        hard_results = tuple(
            evaluate_replica_hard_qc(**{f.name: getattr(e, f.name) for f in fields(e)})
            for e in hard_inputs
        )
        phase = "evidence"
        reviews = []
        for replica, hard, evidence in zip(
            manifest.replicas, hard_results, hard_inputs, strict=True
        ):
            if replica.review_qc_evidence_path is None:
                if hard.hard_qc_status == "pass":
                    raise ValueError("Hard PASS requires a review evidence path")
                continue
            review = read_replica_review_qc_evidence(
                resolve(replica.review_qc_evidence_path),
            )
            if review.replica_key != replica.replica_key or (
                review.engine != evidence.identity.engine
            ):
                raise ValueError("Review identity/engine must match hard evidence")
            if hard.hard_qc_status == "pass":
                reviews.append(review)
        phase = "review QC"
        review_results = evaluate_dataset_review_qc(hard_results, tuple(reviews))
        review_by_key = {r.replica_key: r for r in review_results.evaluations}
        phase = "decision"
        decisions = build_dataset_qc_decision_set(
            tuple(
                build_replica_qc_decision(
                    h, review_by_key.get(h.replica_key), r.manual_resolution
                )
                for r, h in zip(manifest.replicas, hard_results, strict=True)
            )
        )
        summary = build_dataset_qc_summary(decisions)
        ready = all(r.release_decision != "pending_review" for r in decisions.records)
        phase = "aggregation bridge"
        derived = (
            build_qc_derived_replica_aggregation_manifest(template, decisions)
            if ready
            else None
        )
        return DatasetQCOutputs(manifest, decisions, summary, derived)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        prefix = (
            f"Dataset {phase}"
            if phase in ("hard QC", "review QC")
            else (f"Dataset QC {phase}")
        )
        raise DatasetQCWorkflowError(f"{prefix} failed: {exc}") from None


def load_dataset_qc_manifest(path: Path) -> DatasetQCManifest:
    try:
        return read_dataset_qc_manifest(path)
    except ValueError as exc:
        raise DatasetQCWorkflowError(f"Dataset QC manifest failed: {exc}") from None
