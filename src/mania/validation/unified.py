"""Coordinate accepted artifact validators after Stage 25.D.1 integrity checks."""

import csv
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Literal

from mania.artifact_inventory import ArtifactInventoryEntry
from mania.artifact_inventory_io import (
    ArtifactInventoryReadError,
    read_artifact_inventory,
)
from mania.run_provenance import PortableArtifactReference
from mania.runtime_metadata_io import RuntimeMetadataReadError, read_runtime_metadata
from mania.validation import artifacts, graph, run_artifacts
from mania.validation.run_artifacts import (
    ArtifactSetValidationIssue,
    ArtifactSetValidationReport,
    ArtifactValidationScope,
)

UNIFIED_ARTIFACT_VALIDATION_SCHEMA_VERSION = "mania.unified_artifact_validation.v0.1"
UNIFIED_ARTIFACT_VALIDATION_KIND = "mania_unified_artifact_validation"

SpecializedValidationStatus = Literal[
    "passed",
    "failed",
    "not_applicable",
    "not_resolved",
    "skipped_integrity_failure",
    "unsupported",
]
UnifiedArtifactValidationStatus = Literal["passed", "partial", "failed"]


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty stripped string")


@dataclass(frozen=True)
class SpecializedArtifactValidationRecord:
    """One artifact/check outcome; a grouped check covers both pair members."""

    artifact_id: str
    role: str
    path: str
    condition: str | None
    validator: str | None
    status: SpecializedValidationStatus
    issue_count: int

    def __post_init__(self) -> None:
        for name in ("artifact_id", "role"):
            _text(getattr(self, name), name)
        PortableArtifactReference(self.role, self.path)
        if self.condition is not None:
            _text(self.condition, "condition")
        if self.validator is not None:
            _text(self.validator, "validator")
        if self.status not in (
            "passed",
            "failed",
            "not_applicable",
            "not_resolved",
            "skipped_integrity_failure",
            "unsupported",
        ):
            raise ValueError("invalid specialized status")
        if type(self.issue_count) is not int or self.issue_count < 0:
            raise ValueError("issue_count must be a non-negative integer")
        if self.status in ("not_applicable", "unsupported"):
            if self.validator is not None:
                raise ValueError("inapplicable/unsupported records have no validator")
        elif self.status != "skipped_integrity_failure" and self.validator is None:
            raise ValueError("applicable checks require a validator")
        if (self.status == "failed") != (self.issue_count > 0):
            raise ValueError("only failed checks require a positive issue_count")

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "role": self.role,
            "path": self.path,
            "condition": self.condition,
            "validator": self.validator,
            "status": self.status,
            "issue_count": self.issue_count,
        }


@dataclass(frozen=True)
class UnifiedArtifactValidationIssue:
    """Portable normalized diagnostic, never an underlying validator message."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    artifact_id: str | None = None
    path: str | None = None
    condition: str | None = None
    validator: str | None = None

    def __post_init__(self) -> None:
        ArtifactSetValidationIssue(
            self.severity,
            self.code,
            self.message,
            self.artifact_id,
            self.path,
            self.condition,
        )
        if self.validator is not None:
            _text(self.validator, "validator")

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "artifact_id": self.artifact_id,
            "path": self.path,
            "condition": self.condition,
            "validator": self.validator,
        }


@dataclass(frozen=True)
class UnifiedArtifactValidationReport:
    """Technical validation only; partial reports have no errors but lack coverage."""

    scope: ArtifactValidationScope
    run_id: str | None
    workflow: str | None
    integrity_report: ArtifactSetValidationReport
    specialized_records: tuple[SpecializedArtifactValidationRecord, ...]
    issues: tuple[UnifiedArtifactValidationIssue, ...]
    schema_version: str = field(
        init=False, default=UNIFIED_ARTIFACT_VALIDATION_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=UNIFIED_ARTIFACT_VALIDATION_KIND)
    status: UnifiedArtifactValidationStatus = field(init=False)

    def __post_init__(self) -> None:
        if type(self.integrity_report) is not ArtifactSetValidationReport:
            raise ValueError("integrity_report must be ArtifactSetValidationReport")
        if (self.scope, self.run_id, self.workflow) != (
            self.integrity_report.scope,
            self.integrity_report.run_id,
            self.integrity_report.workflow,
        ):
            raise ValueError("report identity must agree with integrity_report")
        for name, model in (
            ("specialized_records", SpecializedArtifactValidationRecord),
            ("issues", UnifiedArtifactValidationIssue),
        ):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(
                type(v) is not model for v in values
            ):
                raise ValueError(f"{name} must be a tuple of {model.__name__}")
        status: UnifiedArtifactValidationStatus = (
            "failed"
            if self.error_count or self.specialized_failed_count
            else "partial"
            if self.integrity_report.status == "partial"
            or any(
                r.status in ("unsupported", "not_resolved", "skipped_integrity_failure")
                for r in self.specialized_records
            )
            else "passed"
        )
        object.__setattr__(self, "status", status)

    @property
    def passed(self) -> bool:
        return self.status != "failed"

    @property
    def complete(self) -> bool:
        return self.status == "passed"

    @property
    def specialized_validation_count(self) -> int:
        return self.specialized_passed_count + self.specialized_failed_count

    @property
    def specialized_passed_count(self) -> int:
        return sum(r.status == "passed" for r in self.specialized_records)

    @property
    def specialized_failed_count(self) -> int:
        return sum(r.status == "failed" for r in self.specialized_records)

    @property
    def unsupported_count(self) -> int:
        return sum(r.status == "unsupported" for r in self.specialized_records)

    @property
    def error_count(self) -> int:
        return self.integrity_report.error_count + sum(
            i.severity == "error" for i in self.issues
        )

    @property
    def warning_count(self) -> int:
        return self.integrity_report.warning_count + sum(
            i.severity == "warning" for i in self.issues
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "scope": self.scope,
            "run_id": self.run_id,
            "workflow": self.workflow,
            "status": self.status,
            "passed": self.passed,
            "complete": self.complete,
            "integrity_report": self.integrity_report.to_dict(),
            "specialized_validation_count": self.specialized_validation_count,
            "specialized_passed_count": self.specialized_passed_count,
            "specialized_failed_count": self.specialized_failed_count,
            "unsupported_count": self.unsupported_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "specialized_records": [r.to_dict() for r in self.specialized_records],
            "issues": [i.to_dict() for i in self.issues],
        }


# These are contract identifiers selected only by this fixed policy, never imports
# or callable names supplied by metadata. Analysis reuses a Stage 20 role alias.
_PREPROCESSING_POLICY: dict[str, str | None] = {
    "input_manifest": None,
    "condition_topology": None,
    "condition_trajectory": None,
    "condition_reference_structure": None,
    "reference_nodes": "graph_pair",
    "reference_edges": "graph_pair",
    "reference_graph": "graph",
    "graph_nodes": "graph_pair",
    "graph_edges": "graph_pair",
    "graph_json": "graph",
    "residue_table": "residue_table",
    "protein_contact_edges": "protein_contact_edges",
    "protein_contacts_perframe": "protein_contacts_perframe",
    "edge_semantics": None,
    "residue_library": None,
    "preprocessing_manifest": None,
    "rg_timeseries": "rg",
    "contact_edges": "contacts",
    "contacts_perframe": "perframe",
    "graph_diagnostics_report": None,
    "reference_comparison_report": None,
    "runtime_metadata": "preprocessing_runtime_metadata",
    "pbc_audit": "pbc_audit",
}
_ANALYSIS_POLICY: dict[str, str | None] = {
    "preprocessing_manifest": None,
    "edge_semantics": None,
    "residue_library": None,
    "residue_table": "residue_table",
    "protein_contact_edges": "protein_contact_edges",
    "contacts_perframe": "protein_contacts_perframe",
    "analysis_graph": "graph",
    "analysis_centrality": "centrality",
    "analysis_communities": "communities",
    "analysis_region_enrichment": "region_enrichment",
    "analysis_temporal_rin": "temporal_rin",
    "analysis_conformation_pca": "conformation_pca",
    "analysis_conformation_labels": "conformation_labels",
    "analysis_comparison": "comparison",
    "analysis_stats": "stats",
    "analysis_manifest": None,
    "runtime_metadata": "analysis_runtime_metadata",
}
_PAIR_ROLES = {
    "graph_nodes": ("graph_nodes", "graph_edges"),
    "graph_edges": ("graph_nodes", "graph_edges"),
    "reference_nodes": ("reference_nodes", "reference_edges"),
    "reference_edges": ("reference_nodes", "reference_edges"),
}
_VALIDATORS = {
    "graph_pair": "validate_preprocessing_graph_csvs",
    "graph": "validate_graph_json",
    "rg": "validate_rg_timeseries_csv",
    "contacts": "validate_contact_edges_csv",
    "perframe": "validate_contacts_perframe_csv",
    "preprocessing_runtime_metadata": "read_runtime_metadata",
    "analysis_runtime_metadata": "read_runtime_metadata",
    "pbc_audit": "read_pbc_audit",
}


def _csv_contracts() -> dict[str, tuple[str, ...]]:
    # Explicit local imports keep the existing validation package import boundary
    # free of preprocessing/analysis initialization cycles. No discovery occurs.
    from mania.analysis.conformation_clustering import CONFORMATION_LABELS_COLUMNS
    from mania.analysis.conformation_pca import CONFORMATION_PCA_COLUMNS
    from mania.analysis.static_rin_communities import STATIC_RIN_COMMUNITIES_COLUMNS
    from mania.analysis.static_rin_comparison import (
        STATIC_RIN_COMPARISON_COLUMNS,
        STATIC_RIN_STATS_COLUMNS,
    )
    from mania.analysis.static_rin_metrics import STATIC_RIN_METRICS_COLUMNS
    from mania.analysis.static_rin_region_enrichment import (
        STATIC_RIN_REGION_ENRICHMENT_COLUMNS,
    )
    from mania.analysis.temporal_rin_metrics import TEMPORAL_RIN_METRICS_COLUMNS
    from mania.preprocessing.trajectory_protein_contact_export import (
        PROTEIN_CONTACT_EDGE_COLUMNS,
        PROTEIN_CONTACT_PERFRAME_COLUMNS,
    )
    from mania.preprocessing.trajectory_residue_table_export import (
        RESIDUE_TABLE_COLUMNS,
    )

    return {
        "residue_table": RESIDUE_TABLE_COLUMNS,
        "protein_contact_edges": PROTEIN_CONTACT_EDGE_COLUMNS,
        "protein_contacts_perframe": PROTEIN_CONTACT_PERFRAME_COLUMNS,
        "centrality": STATIC_RIN_METRICS_COLUMNS,
        "communities": STATIC_RIN_COMMUNITIES_COLUMNS,
        "region_enrichment": STATIC_RIN_REGION_ENRICHMENT_COLUMNS,
        "temporal_rin": TEMPORAL_RIN_METRICS_COLUMNS,
        "conformation_pca": CONFORMATION_PCA_COLUMNS,
        "conformation_labels": CONFORMATION_LABELS_COLUMNS,
        "comparison": STATIC_RIN_COMPARISON_COLUMNS,
        "stats": STATIC_RIN_STATS_COLUMNS,
    }


def _invoke(
    contract: str,
    path: Path,
    condition: str | None,
    peer: Path | None = None,
) -> object:
    if contract in ("preprocessing_runtime_metadata", "analysis_runtime_metadata"):
        metadata = read_runtime_metadata(path)
        scope = contract.removesuffix("_runtime_metadata")
        expected_path = (
            "runtime_metadata.json"
            if scope == "preprocessing" else "analysis/runtime_metadata.json"
        )
        if metadata.scope != scope or metadata.metadata_path != expected_path:
            raise RuntimeMetadataReadError("Runtime metadata scope/path mismatch.")
        return metadata
    if contract == "pbc_audit":
        from mania.preprocessing.pbc_audit_io import PbcAuditReadError, read_pbc_audit

        audit = read_pbc_audit(path)
        if audit.audit_path != "pbc_audit.json":
            raise PbcAuditReadError("PBC audit path mismatch.")
        return audit
    if contract == "graph":
        return graph.validate_graph_json(path, expected_condition=condition)
    if contract == "graph_pair":
        from mania.preprocessing.trajectory_graph_export import (
            validate_preprocessing_graph_csvs,
        )

        assert peer is not None
        return validate_preprocessing_graph_csvs(path, peer)
    if contract == "rg":
        from mania.preprocessing.trajectory_rg_export_validation import (
            validate_rg_timeseries_csv,
        )

        return validate_rg_timeseries_csv(path)
    if contract in ("contacts", "perframe"):
        from mania.preprocessing.trajectory_contacts_export_validation import (
            validate_contact_edges_csv,
            validate_contacts_perframe_csv,
        )

        return (
            validate_contact_edges_csv(path)
            if contract == "contacts"
            else validate_contacts_perframe_csv(path)
        )
    return artifacts.validate_csv_artifact_schema(
        path, contract, expected_columns=_csv_contracts()[contract]
    )


def _failure_count(call: Callable[[], object]) -> int:
    from mania.preprocessing.pbc_audit_io import PbcAuditReadError

    try:
        result = call()
    except (
        artifacts.ArtifactValidationError, OSError, UnicodeError, csv.Error,
        RuntimeMetadataReadError, PbcAuditReadError,
    ):
        # Public validator exceptions and ordinary file/read failures only.
        return 1
    if (
        getattr(result, "passed", True) is False
        or getattr(result, "is_valid", True) is False
    ):
        issues = getattr(result, "issues", ())
        return max(1, len(issues)) if isinstance(issues, (tuple, list)) else 1
    return 0


def validate_run_artifacts(
    run_root: Path,
    *,
    scope: ArtifactValidationScope,
    input_artifact_paths: Mapping[str, Path] | None = None,
) -> UnifiedArtifactValidationReport:
    """Validate declared artifacts read-only; never certify scientific acceptance."""
    integrity = run_artifacts.validate_run_artifact_integrity(
        run_root, scope=scope, input_artifact_paths=input_artifact_paths
    )
    records: list[SpecializedArtifactValidationRecord] = []
    issues: list[UnifiedArtifactValidationIssue] = []

    def report() -> UnifiedArtifactValidationReport:
        return UnifiedArtifactValidationReport(
            scope,
            integrity.run_id,
            integrity.workflow,
            integrity,
            tuple(records),
            tuple(issues),
        )

    try:
        inventory = read_artifact_inventory(run_root / integrity.inventory_path)
    except ArtifactInventoryReadError:
        if not any(i.code == "inventory_read_error" for i in integrity.issues):
            issues.append(
                UnifiedArtifactValidationIssue(
                    "error",
                    "inventory_read_error",
                    "Inventory could not be reread after integrity validation.",
                    path=integrity.inventory_path,
                )
            )
        return report()

    entries = tuple(
        e
        for e in inventory.artifacts
        if e.path
        not in (
            integrity.provenance_path,
            integrity.inventory_path,
        )
    )
    # A different inventory cannot authorize checks using earlier file observations.
    identities = tuple(
        (e.artifact_id, e.direction, e.role, e.path, e.condition, e.byte_size, e.sha256)
        for e in entries
    )
    observed = tuple(
        (
            r.artifact_id,
            r.direction,
            r.role,
            r.path,
            r.condition,
            r.byte_size_expected,
            r.sha256_expected,
        )
        for r in integrity.artifact_records
    )
    if identities != observed:
        issues.append(
            UnifiedArtifactValidationIssue(
                "error",
                "inventory_changed",
                "Inventory entries differ from the integrity observations.",
                path=integrity.inventory_path,
            )
        )
        return report()
    observations = {r.artifact_id: r for r in integrity.artifact_records}
    policy = _PREPROCESSING_POLICY if scope == "preprocessing" else _ANALYSIS_POLICY
    mappings = {} if input_artifact_paths is None else input_artifact_paths
    completed: set[str] = set()

    def record(
        entry: ArtifactInventoryEntry,
        validator: str | None,
        status: SpecializedValidationStatus,
        count: int = 0,
    ) -> None:
        records.append(
            SpecializedArtifactValidationRecord(
                entry.artifact_id,
                entry.role,
                entry.path,
                entry.condition,
                validator,
                status,
                count,
            )
        )

    def issue(
        entry: ArtifactInventoryEntry,
        validator: str | None,
        code: str,
        message: str,
        severity: Literal["error", "warning"] = "error",
    ) -> None:
        issues.append(
            UnifiedArtifactValidationIssue(
                severity,
                code,
                message,
                entry.artifact_id,
                entry.path,
                entry.condition,
                validator,
            )
        )

    def gate(entry: ArtifactInventoryEntry) -> SpecializedValidationStatus | None:
        observation = observations[entry.artifact_id]
        if observation.resolution_status == "not_resolved":
            return "not_resolved"
        if observation.byte_size_matches is not True or (
            observation.sha256_expected is not None
            and observation.sha256_matches is not True
        ):
            return "skipped_integrity_failure"
        return None

    def local(entry: ArtifactInventoryEntry) -> Path:
        return (
            run_root / entry.path
            if entry.direction == "output"
            else mappings[entry.artifact_id]
        )

    def check(
        members: tuple[ArtifactInventoryEntry, ...],
        validator: str,
        call: Callable[[], object],
    ) -> bool:
        count = _failure_count(call)
        for member in members:
            record(member, validator, "failed" if count else "passed", count)
        if count:
            issue(
                members[0],
                validator,
                "specialized_validation_failed",
                "Existing specialized artifact validation failed.",
            )
        return count == 0

    for entry in entries:
        if entry.artifact_id in completed:
            continue
        contract = policy.get(entry.role)
        validator = (
            None
            if contract is None
            else _VALIDATORS.get(contract, "validate_csv_artifact_schema")
        )
        if contract == "graph_pair":
            roles = _PAIR_ROLES[entry.role]
            members = tuple(
                e
                for role in roles
                for e in entries
                if (
                    e.role == role
                    and e.direction == entry.direction
                    and e.condition == entry.condition
                )
            )
            completed.update(e.artifact_id for e in members)
            assert validator is not None
            if len(members) != 2 or tuple(e.role for e in members) != roles:
                for member in members:
                    member_gate = gate(member)
                    record(
                        member,
                        validator,
                        member_gate or "failed",
                        0 if member_gate else 1,
                    )
                issue(
                    entry,
                    validator,
                    "invalid_graph_pair",
                    "Graph CSV validation requires one declared nodes/edges pair.",
                )
                continue
            gates = [gate(e) for e in members]
            blocked: SpecializedValidationStatus | None = (
                "skipped_integrity_failure"
                if "skipped_integrity_failure" in gates
                else "not_resolved"
                if "not_resolved" in gates
                else None
            )
            if blocked is not None:
                for member in members:
                    record(member, validator, gate(member) or blocked)
                continue
            check(
                members,
                validator,
                partial(
                    _invoke,
                    "graph_pair",
                    local(members[0]),
                    entry.condition,
                    local(members[1]),
                ),
            )
            continue
        blocked = gate(entry)
        if blocked == "skipped_integrity_failure":
            record(entry, validator, blocked)
        elif entry.role not in policy:
            record(entry, None, "unsupported")
            issue(
                entry,
                None,
                "unsupported_artifact_role",
                "Artifact role has no supported specialized validation policy.",
                "warning",
            )
        elif contract is None:
            record(entry, None, "not_applicable")
        elif blocked is not None:
            record(entry, validator, blocked)
        else:
            assert validator is not None
            valid = check(
                (entry,),
                validator,
                partial(_invoke, contract, local(entry), entry.condition),
            )
            # Only these accepted generic CSV contracts use condition. Cross-run
            # comparison/stats and legacy condition_name tables keep their semantics.
            if valid and contract not in _VALIDATORS and entry.condition is not None:
                if "condition" in _csv_contracts()[contract]:
                    check(
                        (entry,),
                        "validate_condition_column",
                        partial(
                            artifacts.validate_condition_column,
                            local(entry),
                            entry.condition,
                        ),
                    )
    # Group invocation order follows its first inventory member; report records
    # remain in inventory order, with schema preceding condition checks.
    order = {e.artifact_id: index for index, e in enumerate(entries)}
    records.sort(key=lambda r: order[r.artifact_id])
    return report()


__all__ = [
    "UNIFIED_ARTIFACT_VALIDATION_SCHEMA_VERSION",
    "UNIFIED_ARTIFACT_VALIDATION_KIND",
    "SpecializedValidationStatus",
    "UnifiedArtifactValidationStatus",
    "SpecializedArtifactValidationRecord",
    "UnifiedArtifactValidationIssue",
    "UnifiedArtifactValidationReport",
    "validate_run_artifacts",
]
