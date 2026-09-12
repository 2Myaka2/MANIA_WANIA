"""Coordinate accepted artifact validators after Stage 25.D.1 integrity checks."""

import csv
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Context, Decimal, localcontext
from functools import partial
from pathlib import Path
from typing import Any, Literal

from mania.artifact_inventory import ArtifactInventoryEntry
from mania.artifact_inventory_io import (
    ArtifactInventoryReadError,
    read_artifact_inventory,
)
from mania.dataset_parameter_table import (
    DatasetParameterTableReadError,
    read_dataset_parameter_table_csv,
)
from mania.run_provenance import PortableArtifactReference
from mania.run_provenance_io import RunProvenanceReadError, read_run_provenance
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
    "dataset_parameter_table": "dataset_parameter_table",
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
    "temporal_execution": "temporal_execution",
    "protein_edges_by_window_source": "protein_edges_by_window_source",
    "molecular_partner_metadata": "molecular_partner_metadata",
    "molecular_partner_catalog": "molecular_partner_catalog",
    "protein_lipid_contacts_by_window_source": (
        "protein_lipid_contacts_by_window_source"
    ),
    "protein_glycan_contacts_by_window_source": (
        "protein_glycan_contacts_by_window_source"
    ),
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
    "dataset_parameter_table": "read_dataset_parameter_table_csv",
    "graph_pair": "validate_preprocessing_graph_csvs",
    "graph": "validate_graph_json",
    "rg": "validate_rg_timeseries_csv",
    "contacts": "validate_contact_edges_csv",
    "perframe": "validate_contacts_perframe_csv",
    "preprocessing_runtime_metadata": "read_runtime_metadata",
    "analysis_runtime_metadata": "read_runtime_metadata",
    "pbc_audit": "read_pbc_audit",
    "temporal_execution": "read_preprocessing_temporal_execution",
    "protein_edges_by_window_source": "read_dataset_protein_edge_window_csv",
    "molecular_partner_metadata": "read_molecular_partner_metadata",
    "molecular_partner_catalog": "read_molecular_partner_catalog",
    "protein_lipid_contacts_by_window_source": "read_protein_lipid_window_csv",
    "protein_glycan_contacts_by_window_source": "read_protein_glycan_window_csv",
}


_STAGE30_INPUT_ROLES = ("canonical_residue_mapping", "biological_annotation_metadata")
_STAGE30_FAMILIES = {
    "protein_edges": "edge",
    "protein_lipid_contacts": "lipid",
    "protein_glycan_contacts": "glycan",
}
_STAGE30_OUTPUT_ROLES = tuple(
    f"{family}_by_window_canonical{suffix}"
    for suffix in ("", "_annotated")
    for family in _STAGE30_FAMILIES
)
_STAGE30_ROLES = (*_STAGE30_INPUT_ROLES, *_STAGE30_OUTPUT_ROLES)
_PREPROCESSING_POLICY.update({role: role for role in _STAGE30_ROLES})
_VALIDATORS.update({role: f"read_{role}" for role in _STAGE30_ROLES})


def _read_stage30(contract: str, path: Path) -> object:
    from mania import annotated_window_tables_io, canonical_window_tables_io
    from mania.biological_annotations_io import (
        read_dataset_system_biological_annotations,
    )
    from mania.canonical_residue_mapping_io import read_canonical_residue_mapping

    if contract == "canonical_residue_mapping":
        return read_canonical_residue_mapping(path)
    if contract == "biological_annotation_metadata":
        return read_dataset_system_biological_annotations(path)
    annotated = contract.endswith("_annotated")
    family = contract.split("_by_window_canonical")[0]
    kind = _STAGE30_FAMILIES[family]
    module = annotated_window_tables_io if annotated else canonical_window_tables_io
    prefix = "annotated_canonical" if annotated else "canonical"
    return getattr(module, f"read_{prefix}_protein_{kind}_window_csv")(path)


def _cross_check_stage30(
    run_root: Path,
    entries: tuple[ArtifactInventoryEntry, ...],
    provenance: Any,
    dataset_context: Any,
    models: dict[str, Any],
    sources: dict[str, Any],
) -> None:
    """Reconstruct using the production pure APIs and explicit portable bindings."""
    from mania import annotated_window_tables as annotations_api
    from mania import canonical_window_tables as canonical_api
    from mania.canonical_residue_mapping import (
        CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
        CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    )

    configuration = provenance.to_dict()["resolved_configuration"] if provenance else {}
    completed_run = provenance is not None and provenance.status == "completed"
    by_role = {
        role: tuple(e for e in entries if e.role == role) for role in _STAGE30_ROLES
    }
    refs = provenance.artifact_references if provenance else ()
    mapping_specs = configuration.get("canonical_residue_mapping_bindings", [])
    annotation_specs = configuration.get("biological_annotation_bindings", [])
    mapping_entries = by_role[_STAGE30_INPUT_ROLES[0]]
    annotation_entries = by_role[_STAGE30_INPUT_ROLES[1]]
    active = bool(
        mapping_specs or annotation_specs or mapping_entries or annotation_entries
    )
    if not active and "canonical_reference" in configuration:
        raise ValueError("Canonical reference requires explicit mapping inputs")
    if active:
        if dataset_context is None or not mapping_entries:
            raise ValueError(
                "Stage 30 controls require Dataset context and mapping inputs"
            )
        if configuration.get("canonical_reference") != {
            "reference_id": CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
            "sequence_sha256": CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
        }:
            raise ValueError(
                "Canonical reference provenance must match pinned reference"
            )
    replica_keys = (
        {b.dataset_spec.identity.replica_key for b in dataset_context.bindings}
        if dataset_context
        else set()
    )
    system_keys = {key[:2] for key in replica_keys}
    if (
        not active
        and not any(by_role[role] for role in _STAGE30_OUTPUT_ROLES)
        and not any(ref.role in _STAGE30_ROLES for ref in refs)
        and not any(
            (run_root / f"{role}.csv").exists() for role in _STAGE30_OUTPUT_ROLES
        )
    ):
        return
    bound_mappings = []
    bound_annotations: dict[tuple[str, ...], Any] = {}
    for role, spec_list, control_entries, key_fields, path_field in (
        (
            _STAGE30_INPUT_ROLES[0],
            mapping_specs,
            mapping_entries,
            ("dataset_id", "system_id", "trajectory_id", "replica_id"),
            "mapping_path",
        ),
        (
            _STAGE30_INPUT_ROLES[1],
            annotation_specs,
            annotation_entries,
            ("dataset_id", "system_id"),
            "annotation_metadata_path",
        ),
    ):
        if type(spec_list) is not list or len(spec_list) != len(control_entries):
            raise ValueError(
                "Stage 30 provenance and inventory input counts must match"
            )
        controls = {entry.path: entry for entry in control_entries}
        used_paths = []
        keys = []
        for ordinal, spec in enumerate(spec_list, 1):
            if type(spec) is not dict or set(spec) != {*key_fields, path_field}:
                raise ValueError("Exact Stage 30 binding fields required")
            key = tuple(spec[name] for name in key_fields)
            if any(
                type(value) is not str or not value or value != value.strip()
                for value in key
            ):
                raise ValueError("Stage 30 binding identifiers must be strict strings")
            if key not in (
                replica_keys if role == _STAGE30_INPUT_ROLES[0] else system_keys
            ):
                raise ValueError("Stage 30 binding must match Dataset identity")
            path = spec[path_field]
            if type(path) is not str or path not in controls:
                raise ValueError("Stage 30 binding path must match an input entry")
            entry = controls[path]
            if (
                entry.direction != "input"
                or entry.condition is not None
                or entry.format != "json"
                or entry.artifact_id != f"input:{role}:{ordinal:04d}"
                or path != f"inputs/{role}/{ordinal:04d}/{Path(path).name}"
            ):
                raise ValueError("Stage 30 control inventory identity must match")
            used_paths.append(path)
            keys.append(key)
            model = models.get(entry.artifact_id)
            if model is None:
                continue  # unresolved/failed strict input reads already have records
            if role == _STAGE30_INPUT_ROLES[0]:
                bound_mappings.append(
                    canonical_api.DatasetCanonicalResidueMappingBinding(
                        key[0], key[1], key[2], key[3], model
                    )
                )
            else:
                binding = annotations_api.DatasetBiologicalAnnotationBinding(
                    key[0], key[1], model
                )
                if key in bound_annotations and bound_annotations[key] != binding:
                    raise ValueError(
                        "Conflicting annotation content for Dataset system"
                    )
                bound_annotations[key] = binding
        if len(set(used_paths)) != len(used_paths) or set(used_paths) != set(controls):
            raise ValueError("Stage 30 control paths must bind exactly once")
        if keys != sorted(keys) or (
            role == _STAGE30_INPUT_ROLES[0] and len(set(keys)) != len(keys)
        ):
            raise ValueError("Stage 30 binding keys must be deterministic and unique")
    mappings = canonical_api.DatasetCanonicalResidueMappingBindings(
        tuple(bound_mappings)
    )
    annotations = annotations_api.DatasetBiologicalAnnotationBindings(
        tuple(bound_annotations[key] for key in sorted(bound_annotations))
    )
    for family, kind in _STAGE30_FAMILIES.items():
        source_role = f"{family}_by_window_source"
        canonical_role = f"{family}_by_window_canonical"
        annotated_role = f"{canonical_role}_annotated"
        source_entries = tuple(e for e in entries if e.role == source_role)
        for role, required in (
            (canonical_role, bool(mapping_entries and source_entries)),
            (annotated_role, bool(annotation_entries and source_entries)),
        ):
            outputs = by_role[role]
            references = tuple(ref for ref in refs if ref.role == role)
            if (
                (
                    completed_run
                    and required
                    and (len(outputs) != 1 or len(references) != 1)
                )
                or len(outputs) > 1
                or len(references) > 1
                or bool(outputs) != bool(references)
                or any(
                    e.direction != "output"
                    or e.condition is not None
                    or e.path != f"{role}.csv"
                    or e.format != "csv"
                    or e.artifact_id != f"output:{role}"
                    for e in outputs
                )
                or any(ref.path != f"{role}.csv" for ref in references)
                or (
                    completed_run
                    and (run_root / f"{role}.csv").exists()
                    and not outputs
                )
            ):
                raise ValueError("Stage 30 required artifact and lineage must match")
            if outputs and (
                not mapping_entries
                or not source_entries
                or (
                    role == annotated_role
                    and (not annotation_entries or not by_role[canonical_role])
                )
            ):
                raise ValueError(
                    "Stage 30 output requires explicit input and source lineage"
                )
        source = sources.get(source_role)
        canonical_entries = by_role[canonical_role]
        canonical = (
            models.get(canonical_entries[0].artifact_id) if canonical_entries else None
        )
        if (
            canonical is not None
            and source is not None
            and all(e.artifact_id in models for e in mapping_entries)
        ):
            expected = getattr(
                canonical_api, f"build_canonical_protein_{kind}_window_table"
            )(
                source,
                mapping_bindings=mappings,
            )
            if expected != canonical:
                raise ValueError(
                    "Canonical table must equal reconstruction from explicit mapping"
                )
        annotated_entries = by_role[annotated_role]
        annotated = (
            models.get(annotated_entries[0].artifact_id) if annotated_entries else None
        )
        if (
            canonical is not None
            and annotated is not None
            and all(e.artifact_id in models for e in annotation_entries)
        ):
            expected_annotated = getattr(
                annotations_api,
                f"build_annotated_canonical_protein_{kind}_window_table",
            )(
                canonical,
                annotation_bindings=annotations,
            )
            if expected_annotated != annotated:
                raise ValueError(
                    "Annotated table must equal complete system reconstruction"
                )


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
    if contract in _STAGE30_ROLES:
        return _read_stage30(contract, path)
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
    if contract == "molecular_partner_metadata":
        from mania.preprocessing.molecular_partner_metadata_io import (
            read_molecular_partner_metadata,
        )

        return read_molecular_partner_metadata(path)
    if contract == "molecular_partner_catalog":
        from mania.preprocessing.molecular_partner_catalog_io import (
            read_molecular_partner_catalog,
        )

        return read_molecular_partner_catalog(path)
    if contract == "protein_lipid_contacts_by_window_source":
        from mania.preprocessing.specialized_contact_window_tables_io import (
            read_protein_lipid_window_csv,
        )

        return read_protein_lipid_window_csv(path)
    if contract == "protein_glycan_contacts_by_window_source":
        from mania.preprocessing.specialized_contact_window_tables_io import (
            read_protein_glycan_window_csv,
        )

        return read_protein_glycan_window_csv(path)
    if contract == "protein_edges_by_window_source":
        from mania.preprocessing.protein_edge_window_table_io import (
            read_dataset_protein_edge_window_csv,
        )

        return read_dataset_protein_edge_window_csv(path)
    if contract == "temporal_execution":
        from mania.preprocessing.physical_time_execution_io import (
            read_preprocessing_temporal_execution,
        )

        return read_preprocessing_temporal_execution(path)
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
    from mania.annotated_window_tables_io import AnnotatedWindowCsvReadError
    from mania.biological_annotations_io import BiologicalAnnotationReadError
    from mania.canonical_residue_mapping_io import CanonicalResidueMappingReadError
    from mania.canonical_window_tables_io import CanonicalWindowCsvReadError
    from mania.preprocessing.dataset_binding import PreprocessingDatasetBindingError
    from mania.preprocessing.molecular_partner_catalog_io import (
        MolecularPartnerCatalogReadError,
    )
    from mania.preprocessing.molecular_partner_metadata_io import (
        MolecularPartnerMetadataReadError,
    )
    from mania.preprocessing.pbc_audit_io import PbcAuditReadError
    from mania.preprocessing.physical_time_execution_io import (
        PreprocessingTemporalExecutionReadError,
    )
    from mania.preprocessing.protein_edge_window_table_io import (
        DatasetProteinEdgeWindowCsvReadError,
    )
    from mania.preprocessing.specialized_contact_window_tables_io import (
        SpecializedContactWindowCsvReadError,
    )

    try:
        result = call()
    except (
        artifacts.ArtifactValidationError,
        OSError,
        UnicodeError,
        csv.Error,
        RuntimeMetadataReadError,
        PbcAuditReadError,
        DatasetParameterTableReadError,
        PreprocessingDatasetBindingError,
        PreprocessingTemporalExecutionReadError,
        DatasetProteinEdgeWindowCsvReadError,
        MolecularPartnerCatalogReadError,
        MolecularPartnerMetadataReadError,
        SpecializedContactWindowCsvReadError,
        AnnotatedWindowCsvReadError,
        BiologicalAnnotationReadError,
        CanonicalResidueMappingReadError,
        CanonicalWindowCsvReadError,
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


def _validate_replica_aggregation(
    run_root: Path,
    integrity: ArtifactSetValidationReport,
    input_artifact_paths: Mapping[str, Path] | None,
) -> UnifiedArtifactValidationReport:
    """Strict controls plus accepted A/B/C reconstruction, with no trajectory access."""
    from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
    from mania.replica_aggregation_run import (
        MANIFEST_ARTIFACT_ID,
        MANIFEST_ROLE,
        REPLICA_AGGREGATION_WORKFLOW,
        collect_replica_aggregation_input_specs,
        replica_aggregation_configuration,
    )
    from mania.replica_aggregation_tables_io import replica_aggregation_csv_bytes
    from mania.replica_aggregation_workflow import (
        FAMILIES,
        execute_replica_aggregation_manifest,
    )

    records: list[SpecializedArtifactValidationRecord] = []
    issues: list[UnifiedArtifactValidationIssue] = []
    mappings = {} if input_artifact_paths is None else input_artifact_paths

    def report() -> UnifiedArtifactValidationReport:
        return UnifiedArtifactValidationReport(
            integrity.scope, integrity.run_id, integrity.workflow, integrity,
            tuple(records), tuple(issues),
        )

    def fail(code: str, message: str) -> None:
        issues.append(UnifiedArtifactValidationIssue("error", code, message))

    try:
        inventory = read_artifact_inventory(run_root / integrity.inventory_path)
        provenance = read_run_provenance(run_root / integrity.provenance_path)
    except (ArtifactInventoryReadError, RunProvenanceReadError):
        return report()
    if inventory.workflow != REPLICA_AGGREGATION_WORKFLOW or (
        provenance.workflow != REPLICA_AGGREGATION_WORKFLOW
    ):
        fail("aggregation_workflow_mismatch",
             "Selected scope requires aggregation run.")
    observations = {r.artifact_id: r for r in integrity.artifact_records}
    entries = inventory.artifacts
    if tuple((e.artifact_id, e.direction, e.role, e.path, e.condition,
              e.byte_size, e.sha256) for e in entries) != tuple(
        (r.artifact_id, r.direction, r.role, r.path, r.condition,
         r.byte_size_expected, r.sha256_expected) for r in integrity.artifact_records
    ):
        fail("inventory_changed", "Inventory differs from integrity observations.")
        return report()
    readers: dict[str, Callable[[str | Path], Any]] = {
        MANIFEST_ROLE: read_replica_aggregation_manifest,
    }
    readers.update({f.input_role: f.canonical_reader for f in FAMILIES})
    readers.update({f.output_role: f.reader for f in FAMILIES})
    models: dict[str, Any] = {}
    for entry in entries:
        observation = observations[entry.artifact_id]
        reader = readers.get(entry.role)
        validator = f"read_{entry.role}" if reader is not None else None
        status: SpecializedValidationStatus
        if observation.resolution_status == "not_resolved":
            status = "not_resolved" if reader is not None else "unsupported"
        elif observation.byte_size_matches is not True or (
            observation.sha256_expected is not None
            and observation.sha256_matches is not True
        ):
            status = "skipped_integrity_failure"
        elif reader is None:
            status = "unsupported"
        else:
            try:
                path = run_root / entry.path if entry.direction == "output" else (
                    mappings[entry.artifact_id]
                )
                models[entry.artifact_id] = reader(path)
                status = "passed"
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                status = "failed"
                fail("aggregation_artifact_invalid",
                     "Strict aggregation reader failed.")
        if status == "unsupported":
            issues.append(UnifiedArtifactValidationIssue(
                "warning", "unsupported_artifact_role",
                "Artifact role has no supported aggregation validation policy.",
                artifact_id=entry.artifact_id, path=entry.path,
            ))
        records.append(SpecializedArtifactValidationRecord(
            entry.artifact_id, entry.role, entry.path, entry.condition, validator,
            status, int(status == "failed"),
        ))

    manifest_entries = tuple(e for e in entries if e.role == MANIFEST_ROLE)
    if len(manifest_entries) != 1 or any(
        e.direction != "input" or e.artifact_id != MANIFEST_ARTIFACT_ID
        for e in manifest_entries
    ):
        fail("aggregation_manifest_missing",
             "Exactly one control manifest is required.")
        return report()
    manifest = models.get(MANIFEST_ARTIFACT_ID)
    if manifest is None:
        return report()
    try:
        specs = collect_replica_aggregation_input_specs(
            manifest, mappings[MANIFEST_ARTIFACT_ID],
        )
        expected_inputs = tuple(
            (s.artifact_id, s.direction, s.role, s.path, s.format, s.condition)
            for s in specs
        )
        actual_inputs = tuple(
            (e.artifact_id, e.direction, e.role, e.path, e.format, e.condition)
            for e in entries if e.direction == "input"
        )
        if actual_inputs != expected_inputs:
            raise ValueError("Manifest canonical input inventory mismatch")
        if provenance.to_dict()["resolved_configuration"] != (
            replica_aggregation_configuration(manifest, inventory.checksum_mode)
        ):
            raise ValueError("Manifest provenance configuration mismatch")
        if provenance.conditions != tuple(dict.fromkeys(
            g.spec.condition for g in manifest.groups if g.spec.condition is not None
        )) or provenance.sampling_by_condition:
            raise ValueError("Aggregation condition or sampling evidence mismatch")
        output_refs = {
            (e.role, e.path) for e in entries if e.direction == "output"
        }
        if output_refs != {
            (r.role, r.path) for r in provenance.artifact_references
            if r.role != "artifact_inventory"
        }:
            raise ValueError("Output inventory and provenance references must agree")
        for family in FAMILIES:
            declared = tuple(e for e in entries if e.role == family.output_role)
            present = bool(getattr(manifest, f"{family.name}_canonical_table_paths"))
            if len(declared) > 1 or (declared and not present):
                raise ValueError("Unexpected aggregate family output")
            if provenance.status == "completed" and len(declared) != int(present):
                raise ValueError("Missing required aggregate output")
            if not present and (run_root / family.filename).exists():
                raise ValueError("Unexpected aggregate file for absent family")
            if any(e.direction != "output" or e.path != family.filename
                   or e.artifact_id != f"output:{family.name}" or e.format != "csv"
                   or e.condition is not None for e in declared):
                raise ValueError("Invalid aggregate output lineage")
    except (ValueError, TypeError, KeyError):
        fail("aggregation_lineage_mismatch",
             "Aggregation controls and lineage disagree.")
        return report()

    # Failed runs may have incomplete outputs or invalid scientific group binding.
    # Strict readers and generic integrity still apply to every declared artifact.
    if provenance.status == "failed" or any(r.status != "passed" for r in records):
        return report()
    try:
        mapped = {s.local_path: mappings[s.artifact_id]
                  for s in specs if s.role != MANIFEST_ROLE}
        expected = execute_replica_aggregation_manifest(manifest, mapped_paths=mapped)
        for family in FAMILIES:
            if family.name not in expected:
                continue
            model = expected[family.name]
            if models[f"output:{family.name}"] != model or (
                (run_root / family.filename).read_bytes()
                != replica_aggregation_csv_bytes(model)
            ):
                raise ValueError("Aggregate differs from accepted API reconstruction")
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        fail("aggregation_reconstruction_mismatch",
             "Aggregate models and bytes must equal accepted A/B/C reconstruction.")
    return report()


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
    if scope == "replica_aggregation":
        return _validate_replica_aggregation(run_root, integrity, input_artifact_paths)
    if scope == "dataset_qc":
        from mania.validation.dataset_qc import validate_dataset_qc_run

        return validate_dataset_qc_run(run_root, integrity, input_artifact_paths)
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
    # Keep imports local to preserve the validation/preprocessing import boundary.
    from mania.preprocessing.dataset_binding import (
        PreprocessingDatasetBindingError,
        PreprocessingDatasetContext,
    )

    dataset_context: PreprocessingDatasetContext | None = None
    from mania.preprocessing.pbc_audit import PbcAudit
    from mania.preprocessing.physical_time_execution import (
        PreprocessingTemporalExecution,
    )
    from mania.preprocessing.physical_time_execution_io import (
        PreprocessingTemporalExecutionReadError,
    )
    from mania.preprocessing.protein_edge_window_table import (
        DatasetProteinEdgeWindowTable,
    )
    from mania.preprocessing.protein_edge_window_table_io import (
        DatasetProteinEdgeWindowCsvReadError,
    )

    specialized_roles = (
        "molecular_partner_catalog",
        "protein_lipid_contacts_by_window_source",
        "protein_glycan_contacts_by_window_source",
    )
    specialized_artifacts: dict[str, Any] = {}
    stage30_models: dict[str, Any] = {}

    def validate_stage30(entry: ArtifactInventoryEntry) -> object:
        artifact = _read_stage30(entry.role, local(entry))
        stage30_models[entry.artifact_id] = artifact
        return artifact

    metadata_entries = tuple(
        e for e in entries if e.role == "molecular_partner_metadata"
    )
    source_table: DatasetProteinEdgeWindowTable | None = None
    source_role = "protein_edges_by_window_source"
    source_path = f"{source_role}.csv"
    configuration: dict[str, object] = {}
    temporal_execution: PreprocessingTemporalExecution | None = None
    pbc_audit: PbcAudit | None = None
    provenance = None
    if scope == "preprocessing":
        try:
            provenance = read_run_provenance(run_root / integrity.provenance_path)
        except RunProvenanceReadError:
            # The integrity report already diagnoses unreadable provenance.
            pass
        else:
            recorded_configuration = provenance.to_dict()["resolved_configuration"]
            assert isinstance(recorded_configuration, dict)
            configuration = recorded_configuration
            if "dataset_context" in configuration:
                try:
                    dataset_context = PreprocessingDatasetContext.from_dict(
                        configuration["dataset_context"]
                    )
                    names = tuple(
                        b.execution_condition for b in dataset_context.bindings
                    )
                    if names != tuple(c for c in provenance.conditions if c in names):
                        raise PreprocessingDatasetBindingError(
                            "Invalid execution conditions."
                        )
                except PreprocessingDatasetBindingError:
                    issues.append(UnifiedArtifactValidationIssue(
                        "error", "dataset_context_invalid",
                        "Preprocessing Dataset context is invalid.",
                        path=integrity.provenance_path,
                    ))
        temporal_entries = tuple(e for e in entries if e.role == "temporal_execution")
        temporal_references = (
            tuple(
                r for r in provenance.artifact_references
                if r.role == "temporal_execution"
            )
            if provenance is not None else ()
        )
        needs_temporal = (
            dataset_context is not None and provenance is not None
            and provenance.status == "completed"
        )
        temporal_lineage_invalid = (
            (dataset_context is None and bool(temporal_entries or temporal_references))
            or (needs_temporal and (
                len(temporal_entries) != 1 or len(temporal_references) != 1
            ))
            or (bool(temporal_entries) != bool(temporal_references))
            or any(
                e.direction != "output" or e.path != "temporal_execution.json"
                or e.artifact_id != "output:temporal_execution"
                or e.format != "json" or e.condition is not None
                for e in temporal_entries
            )
            or any(r.path != "temporal_execution.json" for r in temporal_references)
        )
        if temporal_lineage_invalid:
            issues.append(UnifiedArtifactValidationIssue(
                "error", "temporal_execution_lineage_mismatch",
                "Completed Dataset execution requires one temporal output/reference; "
                "legacy execution requires neither.",
                path=integrity.inventory_path,
            ))
        source_entries = tuple(e for e in entries if e.role == source_role)
        source_references = (
            tuple(r for r in provenance.artifact_references if r.role == source_role)
            if provenance is not None else ()
        )
        contact_options = configuration.get("contact_detection_options")
        needs_source = (
            needs_temporal and configuration.get("include_contacts") is True
            and isinstance(contact_options, dict)
            and contact_options.get("contact_selection") == "protein"
        )
        if (
            (needs_source and (len(source_entries) != 1 or len(source_references) != 1))
            or (bool(source_entries) != bool(source_references))
            or len(source_entries) > 1 or len(source_references) > 1
            or (bool(source_entries or source_references) and (
                dataset_context is None or len(temporal_entries) != 1
                or len(temporal_references) != 1
            ))
            or (dataset_context is None and (run_root / source_path).exists())
            or any(
                e.direction != "output" or e.path != source_path
                or e.artifact_id != f"output:{source_role}"
                or e.format != "csv" or e.condition is not None
                for e in source_entries
            )
            or any(r.path != source_path for r in source_references)
        ):
            issues.append(UnifiedArtifactValidationIssue(
                "error", "protein_edge_window_lineage_mismatch",
                "Dataset protein contacts require one source output/reference; "
                "declared source tables require Dataset and temporal evidence.",
                path=integrity.inventory_path,
            ))
        metadata_names = tuple(e.condition for e in metadata_entries)
        dataset_names = (
            tuple(b.execution_condition for b in dataset_context.bindings)
            if dataset_context is not None
            else ()
        )
        if len(set(metadata_names)) != len(metadata_names) or any(
            e.direction != "input"
            or e.format != "json"
            or e.condition not in dataset_names
            or e.artifact_id
            != (f"input:condition:{provenance.conditions.index(e.condition) + 1:04d}"
                ":molecular_partner_metadata")
            for e in metadata_entries
            if provenance is not None
        ):
            issues.append(
                UnifiedArtifactValidationIssue(
                    "error",
                    "molecular_partner_metadata_lineage_mismatch",
                    "Molecular partner metadata requires unique "
                    "condition-scoped Dataset inputs.",
                    path=integrity.inventory_path,
                )
            )
        for role in specialized_roles:
            suffix = "json" if role == "molecular_partner_catalog" else "csv"
            expected_path = f"{role}.{suffix}"
            specialized_entries = tuple(e for e in entries if e.role == role)
            refs = (
                tuple(r for r in provenance.artifact_references if r.role == role)
                if provenance is not None
                else ()
            )
            required = (
                bool(metadata_entries)
                and provenance is not None
                and provenance.status == "completed"
            )
            if (
                (required and (len(specialized_entries) != 1 or len(refs) != 1))
                or len(specialized_entries) > 1
                or len(refs) > 1
                or bool(specialized_entries) != bool(refs)
                or (
                    bool(specialized_entries or refs)
                    and (not metadata_entries or not temporal_entries)
                )
                or any(
                    e.direction != "output"
                    or e.path != expected_path
                    or e.format != suffix
                    or e.condition is not None
                    or e.artifact_id != f"output:{role}"
                    for e in specialized_entries
                )
                or any(r.path != expected_path for r in refs)
            ):
                issues.append(
                    UnifiedArtifactValidationIssue(
                        "error",
                        "specialized_contact_lineage_mismatch",
                        "Successful metadata-bearing Dataset execution requires "
                        "exactly one catalog and both source tables.",
                        path=expected_path,
                    )
                )
        table_entries = tuple(e for e in entries if e.role == "dataset_parameter_table")
        uses_table = dataset_context is not None and any(
            b.source != "inline_manifest" for b in dataset_context.bindings
        )
        if (uses_table and (
            len(table_entries) != 1
            or table_entries[0].direction != "input"
            or table_entries[0].format != "csv"
            or table_entries[0].condition is not None
        )) or (not uses_table and table_entries):
            issues.append(UnifiedArtifactValidationIssue(
                "error", "dataset_parameter_table_lineage_mismatch",
                "Dataset table context requires exactly one parameter-table input, "
                "and vice versa.",
                path=integrity.inventory_path,
            ))

    def validate_dataset_table(path: Path) -> object:
        table = read_dataset_parameter_table_csv(path)
        if dataset_context is not None:
            specs = {spec.identity.replica_key: spec for spec in table.specs}
            for binding in dataset_context.bindings:
                if binding.source == "inline_manifest":
                    continue
                recorded = binding.dataset_spec
                actual = specs.get(recorded.identity.replica_key)
                if actual is None or actual.to_dict() != recorded.to_dict():
                    raise PreprocessingDatasetBindingError(
                        "Dataset context does not match the parameter table."
                    )
        return table

    def validate_temporal(path: Path) -> object:
        nonlocal temporal_execution
        execution = _invoke("temporal_execution", path, None)
        assert isinstance(execution, PreprocessingTemporalExecution)
        if dataset_context is None or tuple(
            (b.execution_condition, b.dataset_spec) for b in execution.bindings
        ) != tuple(
            (b.execution_condition, b.dataset_spec) for b in dataset_context.bindings
        ):
            raise PreprocessingTemporalExecutionReadError(
                "Temporal execution must match requested Dataset bindings."
            )
        temporal_execution = execution
        return execution

    def validate_specialized(role: str, path: Path) -> object:
        artifact = _invoke(role, path, None)
        specialized_artifacts[role] = artifact
        return artifact

    def validate_source(path: Path) -> object:
        nonlocal source_table
        table = _invoke(source_role, path, None)
        assert isinstance(table, DatasetProteinEdgeWindowTable)
        source_table = table
        return table

    def cross_check_source() -> object:
        # All specialized reads have completed, independent of inventory order.
        if dataset_context is None or temporal_execution is None:
            raise DatasetProteinEdgeWindowCsvReadError(
                "Missing Dataset temporal evidence."
            )
        assert source_table is not None
        bindings = {
            b.dataset_spec.identity.replica_key: b for b in temporal_execution.bindings
        }
        windows = {
            key: {(w.window_id, w.window_index): w for w in b.window_plan.windows}
            for key, b in bindings.items()
        }
        for row in source_table.rows:
            key = (row.dataset_id, row.system_id, row.trajectory_id, row.replica_id)
            binding = bindings.get(key)
            if binding is None or any(
                getattr(row, name) != getattr(binding.dataset_spec.identity, name)
                for name in ("variant_id", "engine", "condition", "disulfide_state")
            ):
                raise DatasetProteinEdgeWindowCsvReadError(
                    "Dataset row identity mismatch."
                )
            window = windows[key].get((row.window_id, row.window_index))
            if window is None or any(
                getattr(row, name) != getattr(window, temporal_name)
                for name, temporal_name in (
                    ("requested_window_start_ns", "requested_start_ns"),
                    ("requested_window_end_ns", "requested_end_ns"),
                    ("right_endpoint_inclusive", "right_endpoint_inclusive"),
                    ("requested_sample_count", "requested_sample_count"),
                    ("resolved_frame_count", "sampled_frame_count"),
                    ("missing_sample_count", "missing_sample_count"),
                    ("coverage_fraction", "coverage_fraction"),
                )
            ):
                raise DatasetProteinEdgeWindowCsvReadError("Temporal window mismatch.")
            with localcontext(Context(prec=28)):
                for name, actual in (
                    ("effective_window_start_ns", window.effective_start_time_ps),
                    ("effective_window_end_ns", window.effective_end_time_ps),
                ):
                    if actual is None or getattr(row, name) != float(
                        Decimal(str(actual)) / Decimal("1000")
                    ):
                        raise DatasetProteinEdgeWindowCsvReadError(
                            "Effective temporal window mismatch."
                        )
        return source_table

    def validate_pbc(path: Path) -> object:
        nonlocal pbc_audit
        audit = _invoke("pbc_audit", path, None)
        assert isinstance(audit, PbcAudit)
        pbc_audit = audit
        return audit

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
                partial(validate_stage30, entry)
                if contract in _STAGE30_ROLES
                else partial(validate_dataset_table, local(entry))
                if contract == "dataset_parameter_table"
                else partial(validate_temporal, local(entry))
                if contract == "temporal_execution"
                else partial(validate_source, local(entry))
                if contract == source_role
                else partial(validate_specialized, contract, local(entry))
                if contract in specialized_roles
                else partial(validate_pbc, local(entry))
                if contract == "pbc_audit"
                else partial(_invoke, contract, local(entry), entry.condition),
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
    if source_table is not None and _failure_count(cross_check_source):
        records[:] = [
            replace(r, status="failed", issue_count=r.issue_count + 1)
            if r.role == source_role and r.status == "passed" else r
            for r in records
        ]
        issues.append(UnifiedArtifactValidationIssue(
            "error", "protein_edge_window_context_mismatch",
            "Source rows must match Dataset replica identity and temporal windows.",
            path=source_path,
        ))
    if scope == "preprocessing" and specialized_artifacts:

        def cross_check_specialized() -> object:
            from mania.preprocessing.molecular_partner_catalog_io import (
                MolecularPartnerCatalogReadError,
                cross_check_specialized_source_tables,
            )

            try:
                if temporal_execution is None or any(
                    role not in specialized_artifacts for role in specialized_roles
                ):
                    raise ValueError("Missing specialized or temporal evidence")
                cross_check_specialized_source_tables(
                    specialized_artifacts[specialized_roles[0]],
                    temporal_execution,
                    specialized_artifacts[specialized_roles[1]],
                    specialized_artifacts[specialized_roles[2]],
                    tuple(
                        e.condition for e in metadata_entries if e.condition is not None
                    ),
                )
            except ValueError:
                raise MolecularPartnerCatalogReadError(
                    "Specialized context evidence mismatch."
                ) from None
            return specialized_artifacts

        if _failure_count(cross_check_specialized):
            records[:] = [
                replace(r, status="failed", issue_count=r.issue_count + 1)
                if r.role in specialized_roles and r.status == "passed"
                else r
                for r in records
            ]
            issues.append(
                UnifiedArtifactValidationIssue(
                    "error",
                    "specialized_contact_context_mismatch",
                    "Specialized catalog and source rows must match "
                    "Dataset, temporal, and partner evidence.",
                    path="molecular_partner_catalog.json",
                )
            )
    if scope == "preprocessing":
        try:
            _cross_check_stage30(
                run_root,
                entries,
                provenance,
                dataset_context,
                stage30_models,
                {source_role: source_table, **specialized_artifacts},
            )
        except (ValueError, TypeError):
            records[:] = [
                replace(r, status="failed", issue_count=r.issue_count + 1)
                if r.role in _STAGE30_ROLES and r.status == "passed"
                else r
                for r in records
            ]
            issues.append(
                UnifiedArtifactValidationIssue(
                    "error",
                    "stage30_lineage_or_reconstruction_mismatch",
                    "Canonical and annotated tables must match Dataset controls, "
                    "pinned reference provenance, source models, and artifact lineage.",
                    path=integrity.inventory_path,
                )
            )
    if temporal_execution is not None and pbc_audit is not None:
        counts = {c.condition: c.sampled_frame_count for c in pbc_audit.conditions}
        if any(
            b.execution_condition in counts
            and counts[b.execution_condition] != b.sampling_plan.sampled_frame_count
            for b in temporal_execution.bindings
        ):
            issues.append(UnifiedArtifactValidationIssue(
                "error", "temporal_execution_pbc_count_mismatch",
                "PBC sampled counts must equal physical selected sample counts.",
                path="pbc_audit.json",
            ))
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
