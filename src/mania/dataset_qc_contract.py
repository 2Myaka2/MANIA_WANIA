"""Pure Stage 32.A QC evidence and authoritative release-decision contract.

Findings are supplied observations, not calculated QC. Stage 32.B/32.C own
evaluation; Stage 32.D will bridge decisions to Stage 31 availability.
"""

from dataclasses import dataclass, field, fields
from typing import Literal, get_args

from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)

DATASET_QC_DECISION_SET_SCHEMA_VERSION = "mania.dataset_qc_decision_set.v0.1"
DATASET_QC_DECISION_SET_KIND = "mania_dataset_qc_decision_set"

QCStatus = Literal["pass", "review", "fail"]
QCReleaseDecision = Literal["available", "pending_review", "excluded"]
QCDecisionMode = Literal["automatic", "manual"]

_HardFailReasonCode = Literal[
    "TOPOLOGY_UNREADABLE",
    "TRAJECTORY_UNREADABLE",
    "TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH",
    "TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH",
    "CANONICAL_MAPPING_INCOMPLETE",
    "PROTEIN_PBC_BROKEN",
    "FRAME_TIME_NOT_STRICTLY_INCREASING",
    "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
    "REQUIRED_METADATA_MISSING",
    "REQUIRED_ARTIFACT_MISSING",
    "SCHEMA_INVALID",
    "CANONICAL_REFERENCE_MISMATCH",
    "FORBIDDEN_SELF_LOOP",
    "DUPLICATE_RECORD",
    "OCCUPANCY_OUT_OF_RANGE",
]
_ReviewReasonCode = Literal[
    "RMSD_DRIFT_REVIEW",
    "PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT",
    "EDGE_COUNT_MAD_OUTLIER_REVIEW",
    "CONTACT_FRACTION_MAD_OUTLIER_REVIEW",
    "BASIC_METRIC_MAD_OUTLIER_REVIEW",
    "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW",
]
QCReasonCode = Literal[_HardFailReasonCode, _ReviewReasonCode]
QCEvidenceType = Literal[
    "artifact", "metric", "window", "mapping", "pbc", "manual_review"
]


class DatasetQCContractError(ValueError):
    """Invalid QC structure, severity, identity or decision traceability."""


def _text(value: object, name: str) -> str:
    # Strip outer whitespace only; never infer identifiers or rewrite prose.
    if type(value) is not str or not value.strip():
        raise DatasetQCContractError(f"{name} must be a non-empty string")
    return value.strip()


def _literal(value: object, allowed: tuple[str, ...], name: str) -> None:
    if type(value) is not str or value not in allowed:
        raise DatasetQCContractError(f"{name} must be exactly one of {allowed}")


def expected_qc_status(reason_code: QCReasonCode) -> Literal["fail", "review"]:
    """Return the frozen severity class; no reason code represents PASS."""
    _literal(reason_code, get_args(QCReasonCode), "reason_code")
    return "fail" if reason_code in get_args(_HardFailReasonCode) else "review"


def _portable_path(value: str) -> None:
    # Lexical validation only: no resolution, expansion, existence check or I/O.
    if (
        any(part in ("", ".", "..") for part in value.split("/"))
        or any(marker in value for marker in ("\\", ":", "~", "$", "%"))
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise DatasetQCContractError(
            "artifact_path must be a portable relative forward-slash path "
            "without traversal, home or environment expansion"
        )


@dataclass(frozen=True)
class QCEvidenceRecord:
    """Structured portable evidence; supplied text is not scientifically evaluated."""

    evidence_id: str
    evidence_type: QCEvidenceType
    artifact_role: str | None
    artifact_path: str | None
    window_id: str | None
    metric_name: str | None
    observed_value: str | None
    expected_or_threshold: str | None
    details: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _text(self.evidence_id, "evidence_id"))
        _literal(self.evidence_type, get_args(QCEvidenceType), "evidence_type")
        for name in (
            "artifact_role",
            "artifact_path",
            "window_id",
            "metric_name",
            "observed_value",
            "expected_or_threshold",
            "details",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))
        if self.artifact_path is not None:
            _portable_path(self.artifact_path)
        artifact = self.artifact_role is not None and self.artifact_path is not None
        structured = {
            "artifact": artifact,
            "metric": self.metric_name is not None and self.observed_value is not None,
            "window": self.window_id is not None
            and any(
                value is not None
                for value in (self.metric_name, self.observed_value, self.details)
            ),
            "mapping": artifact or self.details is not None,
            "pbc": artifact
            or self.observed_value is not None
            or self.details is not None,
            "manual_review": self.details is not None,
        }
        if not structured[self.evidence_type]:
            raise DatasetQCContractError(
                f"{self.evidence_type} evidence lacks its required structured payload"
            )

    def to_dict(self) -> dict[str, object]:
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True)
class ReplicaQCCheckResult:
    """One auditable check, including evidence for a PASS."""

    check_id: str
    status: QCStatus
    reason_code: QCReasonCode | None
    human_readable_reason: str | None
    evidence: tuple[QCEvidenceRecord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _text(self.check_id, "check_id"))
        _literal(self.status, get_args(QCStatus), "status")
        if (
            type(self.evidence) is not tuple
            or not self.evidence
            or any(type(item) is not QCEvidenceRecord for item in self.evidence)
        ):
            raise DatasetQCContractError(
                "evidence must be a non-empty tuple of exact QCEvidenceRecord values"
            )
        ids = tuple(item.evidence_id for item in self.evidence)
        if len(set(ids)) != len(ids):
            raise DatasetQCContractError("evidence IDs must be unique within a check")
        if self.status == "pass":
            if self.reason_code is not None or self.human_readable_reason is not None:
                raise DatasetQCContractError("PASS must have no reason code or prose")
        else:
            if (
                self.reason_code is None
                or expected_qc_status(self.reason_code) != self.status
            ):
                raise DatasetQCContractError("reason_code must match the check status")
            object.__setattr__(
                self,
                "human_readable_reason",
                _text(self.human_readable_reason, "human_readable_reason"),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "human_readable_reason": self.human_readable_reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class ReplicaQCDecisionRecord:
    """Authoritative decision for one full Dataset replica key, never condition."""

    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    qc_status: QCStatus
    findings: tuple[ReplicaQCCheckResult, ...]
    release_decision: QCReleaseDecision
    decision_mode: QCDecisionMode
    decision_reason_code: QCReasonCode | None
    human_readable_reason: str | None
    decision_evidence_ids: tuple[str, ...]
    reviewer: str | None
    decision_note: str | None

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        _literal(self.qc_status, get_args(QCStatus), "qc_status")
        _literal(self.release_decision, get_args(QCReleaseDecision), "release_decision")
        _literal(self.decision_mode, get_args(QCDecisionMode), "decision_mode")
        if (
            type(self.findings) is not tuple
            or not self.findings
            or any(type(item) is not ReplicaQCCheckResult for item in self.findings)
        ):
            raise DatasetQCContractError(
                "findings must be a non-empty tuple of exact ReplicaQCCheckResult "
                "values"
            )
        checks = tuple(item.check_id for item in self.findings)
        if len(set(checks)) != len(checks):
            raise DatasetQCContractError("check IDs must be unique within a replica")
        evidence_ids = tuple(
            evidence.evidence_id for item in self.findings for evidence in item.evidence
        )
        if len(set(evidence_ids)) != len(evidence_ids):
            raise DatasetQCContractError("evidence IDs must be unique across findings")
        statuses = {item.status for item in self.findings}
        expected = (
            "fail"
            if "fail" in statuses
            else "review"
            if "review" in statuses
            else "pass"
        )
        if self.qc_status != expected:
            raise DatasetQCContractError(
                "qc_status must equal the status derived from findings"
            )
        if type(self.decision_evidence_ids) is not tuple:
            raise DatasetQCContractError("decision_evidence_ids must be a tuple")
        ids = tuple(
            _text(value, "decision evidence ID") for value in self.decision_evidence_ids
        )
        if len(set(ids)) != len(ids):
            raise DatasetQCContractError("decision evidence IDs must be unique")
        if not set(ids).issubset(evidence_ids):
            raise DatasetQCContractError(
                "decision evidence references unknown evidence"
            )
        object.__setattr__(self, "decision_evidence_ids", ids)

        if self.qc_status == "pass":
            if (
                self.release_decision != "available"
                or self.decision_mode != "automatic"
                or self.decision_reason_code is not None
                or self.human_readable_reason is not None
                or ids
                or self.reviewer is not None
                or self.decision_note is not None
            ):
                raise DatasetQCContractError(
                    "PASS requires automatic available with no decision reason, "
                    "evidence references or manual provenance"
                )
            return

        if (
            self.decision_reason_code is None
            or expected_qc_status(self.decision_reason_code) != self.qc_status
        ):
            raise DatasetQCContractError(
                "decision reason must match the QC status class"
            )
        matching = tuple(
            item
            for item in self.findings
            if item.reason_code == self.decision_reason_code
            and item.status == self.qc_status
        )
        if not matching:
            raise DatasetQCContractError(
                "decision reason must occur in a matching finding"
            )
        supporting_ids = {
            evidence.evidence_id for item in matching for evidence in item.evidence
        }
        if not ids or not set(ids).issubset(supporting_ids):
            raise DatasetQCContractError(
                "decision evidence must support findings carrying the decision reason"
            )
        object.__setattr__(
            self,
            "human_readable_reason",
            _text(self.human_readable_reason, "human_readable_reason"),
        )
        if self.qc_status == "fail" and (
            self.release_decision != "excluded" or self.decision_mode != "automatic"
        ):
            raise DatasetQCContractError(
                "FAIL requires automatic excluded; no manual override"
            )
        if self.decision_mode == "automatic":
            if self.qc_status == "review" and self.release_decision != "pending_review":
                raise DatasetQCContractError("automatic REVIEW requires pending_review")
            if self.reviewer is not None or self.decision_note is not None:
                raise DatasetQCContractError(
                    "automatic decisions forbid reviewer and decision_note"
                )
        else:
            if self.release_decision not in ("available", "excluded"):
                raise DatasetQCContractError(
                    "manual REVIEW must resolve to available or excluded"
                )
            for name in ("reviewer", "decision_note"):
                object.__setattr__(self, name, _text(getattr(self, name), name))

    @property
    def replica_key(self) -> tuple[str, str, str, str]:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        result = {item.name: getattr(self, item.name) for item in fields(self)}
        result["findings"] = [item.to_dict() for item in self.findings]
        result["decision_evidence_ids"] = list(self.decision_evidence_ids)
        return result


@dataclass(frozen=True)
class DatasetQCDecisionSet:
    """Sorted replica decisions pinned to the accepted Stage 30 reference."""

    records: tuple[ReplicaQCDecisionRecord, ...]
    schema_version: str = field(
        init=False, default=DATASET_QC_DECISION_SET_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=DATASET_QC_DECISION_SET_KIND)
    canonical_reference_id: str = field(
        init=False, default=CANONICAL_RESIDUE_MAPPING_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256
    )

    def __post_init__(self) -> None:
        if type(self.records) is not tuple or any(
            type(item) is not ReplicaQCDecisionRecord for item in self.records
        ):
            raise DatasetQCContractError(
                "records must be a tuple of exact ReplicaQCDecisionRecord values"
            )
        keys = tuple(item.replica_key for item in self.records)
        if len(set(keys)) != len(keys):
            raise DatasetQCContractError("replica keys must be unique")
        object.__setattr__(
            self,
            "records",
            tuple(sorted(self.records, key=lambda item: item.replica_key)),
        )

    def to_dict(self) -> dict[str, object]:
        result = {item.name: getattr(self, item.name) for item in fields(self)}
        result["records"] = [item.to_dict() for item in self.records]
        return result


def build_dataset_qc_decision_set(
    records: tuple[ReplicaQCDecisionRecord, ...],
) -> DatasetQCDecisionSet:
    """Validate and sort full replica keys without changing the supplied tuple."""
    return DatasetQCDecisionSet(records)


__all__ = [
    "DATASET_QC_DECISION_SET_SCHEMA_VERSION",
    "DATASET_QC_DECISION_SET_KIND",
    "QCStatus",
    "QCReleaseDecision",
    "QCDecisionMode",
    "QCReasonCode",
    "QCEvidenceType",
    "DatasetQCContractError",
    "QCEvidenceRecord",
    "ReplicaQCCheckResult",
    "ReplicaQCDecisionRecord",
    "DatasetQCDecisionSet",
    "expected_qc_status",
    "build_dataset_qc_decision_set",
]
