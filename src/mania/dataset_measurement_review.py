"""Coordinate-free presentation and explicit adaptation to accepted Stage 32 types."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from mania.dataset_qc_contract import QCEvidenceRecord
from mania.dataset_review_qc import (
    ProteinEdgeEmptyWindowEvidence,
    ReplicaMADMetricObservation,
    ReplicaReviewQCEvidence,
    RMSDDriftAssessment,
)
from mania.preprocessing.trajectory_rmsd import StrictModel
from mania.preprocessing.trajectory_rmsd_io import (
    MEASUREMENT_FILENAME,
    TIMESERIES_FILENAME,
    atomic_json,
    file_sha256,
    read_rmsd_evidence,
)
from mania.production_handoff import load_completed_handoff


class ExplicitRMSDAssessment(StrictModel):
    schema_version: Literal["mania.production_review_assessment.v0.1"]
    drift_detected: bool
    assessment_method: str
    reviewer: str
    decision_note: str

    def require_authority(self) -> None:
        for value in (self.assessment_method, self.reviewer, self.decision_note):
            if not value or value != value.strip():
                raise ValueError(
                    "Explicit assessment requires method, reviewer and note"
                )


def present_rmsd_review(root: Path) -> dict[str, object]:
    handoff = load_completed_handoff(root)
    metadata, rows = read_rmsd_evidence(root / "preprocessing")
    return {
        "dataset_identity": handoff.replica_identity.to_dict(),
        "measurement_contract_id": metadata.measurement_contract_id,
        "reference": metadata.reference.model_dump(mode="json"),
        "atom_count": metadata.atom_selection.atom_count,
        "unit": "angstrom",
        "completeness": metadata.completeness.model_dump(mode="json"),
        "samples": [s.model_dump(mode="json") for s in rows],
        "automatic_drift_classification": False,
        "assessment_state": "explicit_assessment_required",
    }


def build_rmsd_drift_assessment(
    root: Path,
    assessment: ExplicitRMSDAssessment | None,
) -> RMSDDriftAssessment:
    load_completed_handoff(root)
    if assessment is None:
        raise ValueError("RMSD measurements alone cannot supply a drift assessment")
    assessment.require_authority()
    records = []
    for role, name in (
        ("protein_rmsd_timeseries", TIMESERIES_FILENAME),
        ("protein_rmsd_measurement", MEASUREMENT_FILENAME),
    ):
        path = f"preprocessing/{name}"
        records.append(
            QCEvidenceRecord(
                evidence_id=f"rmsd:{role}",
                evidence_type="artifact",
                artifact_role=role,
                artifact_path=path,
                window_id=None,
                metric_name=None,
                observed_value=None,
                expected_or_threshold=None,
                details=(
                    f"sha256={file_sha256(root / path)}; "
                    f"reviewer={assessment.reviewer}; "
                    f"note={assessment.decision_note}"
                ),
            )
        )
    return RMSDDriftAssessment(
        assessment.drift_detected, assessment.assessment_method, tuple(records)
    )


def build_replica_review_evidence(
    root: Path,
    assessment: ExplicitRMSDAssessment | None,
    *,
    empty_windows: ProteinEdgeEmptyWindowEvidence,
    mad_metrics: tuple[ReplicaMADMetricObservation, ...] = (),
) -> ReplicaReviewQCEvidence:
    handoff = load_completed_handoff(root)
    identity = handoff.replica_identity
    return ReplicaReviewQCEvidence(
        *identity.replica_key,
        identity.engine,
        build_rmsd_drift_assessment(root, assessment),
        empty_windows,
        mad_metrics,
    )


def save_review_assessment(
    root: Path,
    assessment: ExplicitRMSDAssessment,
    destination: Path,
) -> RMSDDriftAssessment:
    if not destination.resolve().is_relative_to((root / "postproduction").resolve()):
        raise ValueError(
            "Review belongs in a fresh postproduction namespace under OUTPUT_ROOT"
        )
    evidence = build_rmsd_drift_assessment(root, assessment)
    atomic_json(
        destination,
        {
            **assessment.model_dump(mode="json"),
            "replica_identity": load_completed_handoff(root).replica_identity.to_dict(),
            "measurement_bindings": {
                name: file_sha256(root / "preprocessing" / name)
                for name in (TIMESERIES_FILENAME, MEASUREMENT_FILENAME)
            },
            "stage32_rmsd_drift": evidence.to_dict(),
        },
    )
    return evidence


def load_review_assessment(root: Path, path: Path) -> ExplicitRMSDAssessment:
    from mania.preprocessing.molecular_partner_metadata_io import (
        exact_fields,
        read_strict_json,
    )

    data = exact_fields(
        read_strict_json(path),
        {
            *ExplicitRMSDAssessment.model_fields,
            "replica_identity",
            "measurement_bindings",
            "stage32_rmsd_drift",
        },
    )
    assessment = ExplicitRMSDAssessment.model_validate(
        {k: data[k] for k in ExplicitRMSDAssessment.model_fields}
    )
    expected = build_rmsd_drift_assessment(root, assessment)
    if data["replica_identity"] != load_completed_handoff(
        root
    ).replica_identity.to_dict() or (
        data["measurement_bindings"]
        != {
            name: file_sha256(root / "preprocessing" / name)
            for name in (TIMESERIES_FILENAME, MEASUREMENT_FILENAME)
        }
        or data["stage32_rmsd_drift"] != expected.to_dict()
    ):
        raise ValueError("Review assessment differs from sealed measurement evidence")
    return assessment
