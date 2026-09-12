"""Frozen Stage 32 Dataset QC controls; full replica identity is authoritative."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from mania._dataset_qc_json import portable_path
from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)
from mania.dataset_qc_contract import QCReasonCode, expected_qc_status

DATASET_QC_MANIFEST_SCHEMA_VERSION = "mania.dataset_qc_manifest.v0.1"
DATASET_QC_MANIFEST_KIND = "mania_dataset_qc_manifest"
DATASET_QC_MANIFEST_FILENAME = "dataset_qc_manifest.json"


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("Expected non-empty string")
    return value.strip()


@dataclass(frozen=True)
class QCManualReviewResolution:
    release_decision: Literal["available", "excluded"]
    decision_reason_code: QCReasonCode
    human_readable_reason: str
    decision_evidence_ids: tuple[str, ...]
    reviewer: str
    decision_note: str

    def __post_init__(self) -> None:
        if type(self.release_decision) is not str or self.release_decision not in (
            "available",
            "excluded",
        ):
            raise ValueError("Manual resolution requires available or excluded")
        if expected_qc_status(self.decision_reason_code) != "review":
            raise ValueError("Manual resolution requires a review reason")
        for name in ("human_readable_reason", "reviewer", "decision_note"):
            object.__setattr__(self, name, _text(getattr(self, name)))
        if type(self.decision_evidence_ids) is not tuple or not (
            self.decision_evidence_ids
        ):
            raise ValueError("Manual resolution requires evidence IDs")
        ids = tuple(_text(v) for v in self.decision_evidence_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("Manual evidence IDs must be unique")
        object.__setattr__(self, "decision_evidence_ids", ids)


@dataclass(frozen=True)
class DatasetQCWorkflowReplica:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    hard_qc_evidence_path: Path
    review_qc_evidence_path: Path | None
    manual_resolution: QCManualReviewResolution | None

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
            object.__setattr__(self, name, _text(getattr(self, name)))
        for name in ("hard_qc_evidence_path", "review_qc_evidence_path"):
            value = getattr(self, name)
            if value is None and name == "review_qc_evidence_path":
                continue
            if not isinstance(value, Path):
                raise ValueError("Evidence path must be a Path")
            portable_path(value.as_posix())
        if self.manual_resolution is not None:
            if type(self.manual_resolution) is not QCManualReviewResolution:
                raise ValueError("Expected exact manual resolution")
            replace(self.manual_resolution)

    @property
    def replica_key(self) -> tuple[str, str, str, str]:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id


@dataclass(frozen=True)
class DatasetQCManifest:
    aggregation_manifest_template_path: Path
    replicas: tuple[DatasetQCWorkflowReplica, ...]
    schema_version: str = field(init=False, default=DATASET_QC_MANIFEST_SCHEMA_VERSION)
    kind: str = field(init=False, default=DATASET_QC_MANIFEST_KIND)
    canonical_reference_id: str = field(
        init=False,
        default=CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    )
    canonical_reference_sequence_sha256: str = field(
        init=False,
        default=CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.aggregation_manifest_template_path, Path):
            raise ValueError("Template path must be a Path")
        portable_path(self.aggregation_manifest_template_path.as_posix())
        if (
            type(self.replicas) is not tuple
            or not self.replicas
            or any(type(r) is not DatasetQCWorkflowReplica for r in self.replicas)
        ):
            raise ValueError("Expected non-empty tuple of exact QC replica controls")
        for replica in self.replicas:
            replace(replica)
        if len({r.replica_key for r in self.replicas}) != len(self.replicas):
            raise ValueError("QC replica keys must be unique")
        object.__setattr__(
            self,
            "replicas",
            tuple(
                sorted(
                    self.replicas,
                    key=lambda r: r.replica_key,
                )
            ),
        )
