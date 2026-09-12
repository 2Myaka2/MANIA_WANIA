"""Strict serialization of exact accepted 32.B inputs and 32.C evidence.

The hard wrapper contains precisely the public evaluator's keyword inputs.
No observations, sampling targets, contacts, or metrics are calculated here.
"""

from dataclasses import dataclass
from pathlib import Path

from mania._dataset_qc_json import read_model, write_model
from mania.canonical_window_tables import DatasetCanonicalResidueMappingBinding
from mania.dataset_hard_qc import (
    ReplicaProteinPBCEvidence,
    ReplicaRawIntegrityEvidence,
    RequiredArtifactEvidence,
    RequiredMetadataEvidence,
    SourceResidueKey,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_review_qc import ReplicaReviewQCEvidence
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
)
from mania.preprocessing.physical_time_sampling import ResolvedPhysicalTimeSamplingPlan


@dataclass(frozen=True)
class ReplicaHardQCEvidence:
    identity: DatasetTrajectoryIdentity
    raw_integrity: ReplicaRawIntegrityEvidence
    mapping_binding: DatasetCanonicalResidueMappingBinding | None
    required_source_keys: tuple[SourceResidueKey, ...] | None
    protein_pbc: ReplicaProteinPBCEvidence | None
    sampling_plan: ResolvedPhysicalTimeSamplingPlan | None
    required_metadata: tuple[RequiredMetadataEvidence, ...]
    required_artifacts: tuple[RequiredArtifactEvidence, ...]


def read_replica_hard_qc_evidence(path: str | Path) -> ReplicaHardQCEvidence:
    return read_model(path, ReplicaHardQCEvidence)


def write_replica_hard_qc_evidence(
    evidence: ReplicaHardQCEvidence,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_model(evidence, ReplicaHardQCEvidence, path, overwrite=overwrite)


def read_replica_review_qc_evidence(path: str | Path) -> ReplicaReviewQCEvidence:
    return read_model(path, ReplicaReviewQCEvidence)


def write_replica_review_qc_evidence(
    evidence: ReplicaReviewQCEvidence,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_model(evidence, ReplicaReviewQCEvidence, path, overwrite=overwrite)
