"""File-authoritative release assembly; accepted builders, zero trajectory passes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mania.artifact_inventory import ArtifactInventory
from mania.artifact_inventory_io import read_artifact_inventory
from mania.biological_annotations_io import read_dataset_system_biological_annotations
from mania.dataset_qc_decision_io import read_dataset_qc_decision_set
from mania.dataset_qc_manifest_io import read_dataset_qc_manifest
from mania.dataset_qc_run import (
    collect_dataset_qc_input_specs,
    dataset_qc_configuration,
)
from mania.dataset_qc_summary import read_dataset_qc_summary_csv
from mania.dataset_qc_workflow import DatasetQCOutputs
from mania.dataset_release_aggregates import DatasetReleaseAggregationAuthority
from mania.dataset_release_csv import DatasetReleaseTable, publication_csv_bytes
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest import (
    DatasetReleaseExportManifest,
    DatasetReleaseManifest,
    ReleaseUpstreamRun,
)
from mania.dataset_release_manifest_io import (
    read_dataset_release_export_manifest,
    release_json_text,
)
from mania.dataset_release_metadata import (
    DatasetReleaseMetadataTables,
    QCDerivedAggregationEvidence,
    build_dataset_release_metadata_tables,
)
from mania.dataset_release_science import (
    DatasetReleaseScientificTables,
    build_dataset_release_scientific_tables,
)
from mania.dataset_release_source_authority import (
    validate_publication_metric_sources,
    validate_release_canonical_source_authority,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_aggregation_run import (
    collect_replica_aggregation_input_specs,
    replica_aggregation_configuration,
)
from mania.replica_aggregation_tables import (
    CanonicalProteinEdgeReplicaAggregationTable,
    CanonicalProteinGlycanReplicaAggregationTable,
    CanonicalProteinLipidReplicaAggregationTable,
)
from mania.replica_aggregation_workflow import FAMILIES
from mania.run_provenance import RunProvenance
from mania.run_provenance_io import read_run_provenance
from mania.validation.run_artifacts import (
    ArtifactValidationScope,
    validate_run_artifact_integrity,
)


class DatasetReleaseError(ValueError):
    """Portable phase-specific release failure."""


@dataclass(frozen=True)
class DatasetReleaseBundle:
    control: DatasetReleaseExportManifest
    metadata: DatasetReleaseMetadataTables
    science: DatasetReleaseScientificTables
    manifest: DatasetReleaseManifest
    aggregation_authority: DatasetReleaseAggregationAuthority

    @property
    def tables(self) -> tuple[DatasetReleaseTable, ...]:
        return tuple(
            sorted(
                (*self.metadata.tables, *self.science.tables),
                key=lambda table: table.relative_path,
            )
        )

    @property
    def counts(self) -> dict[str, int]:
        rows = self.metadata.simulations.records()
        return {
            "system_count": self.metadata.systems.row_count,
            "simulation_count": len(rows),
            "scientific_release_replica_count": sum(
                r["included_in_scientific_release"] is True for r in rows
            ),
            "excluded_simulation_count": sum(
                r["release_decision"] == "excluded" for r in rows
            ),
            "technically_unavailable_simulation_count": sum(
                r["aggregation_availability_status"] == "unavailable" for r in rows
            ),
            "publication_csv_count": 17,
        }


def _upstream_run(
    binding: ReleaseUpstreamRun,
    base: Path,
    scope: ArtifactValidationScope,
) -> tuple[RunProvenance, ArtifactInventory, dict[str, Path], Path]:
    provenance_path = base / binding.provenance_path
    inventory_path = base / binding.inventory_path
    root = inventory_path.parent
    if inventory_path.name != "artifact_inventory.json" or (
        provenance_path.resolve() != (root / "run_provenance.json").resolve()
    ):
        raise ValueError("Upstream evidence must use the accepted run layout")
    inventory = read_artifact_inventory(inventory_path)
    provenance = read_run_provenance(provenance_path)
    mappings = {b.artifact_id: base / b.path for b in binding.input_bindings}
    if mappings.keys() != {
        e.artifact_id for e in inventory.artifacts if e.direction == "input"
    }:
        raise ValueError("Every upstream inventoried input must be explicitly bound")
    report = validate_run_artifact_integrity(
        root, scope=scope, input_artifact_paths=mappings
    )
    if (
        not report.passed
        or not report.complete
        or (
            inventory.workflow != scope
            or provenance.workflow != scope
            or provenance.status != "completed"
            or provenance.issues
        )
    ):
        raise ValueError("Upstream run integrity or completion failed")
    outputs = {(e.role, e.path) for e in inventory.artifacts if e.direction == "output"}
    refs = {(r.role, r.path) for r in provenance.artifact_references}
    if refs != outputs | {("artifact_inventory", "artifact_inventory.json")}:
        raise ValueError("Upstream successful output references must match inventory")
    command = (
        "mania",
        "dataset",
        "qc" if scope == "dataset_qc" else "aggregate-replicas",
        "--manifest",
        "inputs/dataset_qc_manifest.json"
        if scope == "dataset_qc"
        else "inputs/replica_aggregation_manifest.json",
        "--output",
        ".",
        "--artifact-checksum-mode",
        inventory.checksum_mode,
    )
    if provenance.command not in (command, (*command, "--overwrite")):
        raise ValueError("Upstream command does not bind its accepted manifest input")
    return provenance, inventory, mappings, root


def _output(
    inventory: ArtifactInventory,
    root: Path,
    role: str,
    target: Path,
) -> None:
    matches = [
        e for e in inventory.artifacts if e.direction == "output" and e.role == role
    ]
    if len(matches) != 1 or (root / matches[0].path).resolve() != target.resolve():
        raise ValueError(
            "Publication source is not the declared successful upstream output"
        )


def _input_specs(
    specs: tuple[Any, ...], inventory: ArtifactInventory, mappings: dict[str, Path]
) -> None:
    actual = tuple(e for e in inventory.artifacts if e.direction == "input")
    expected = {s.artifact_id: s for s in specs}
    if expected.keys() != mappings.keys() or len(actual) != len(specs):
        raise ValueError("Upstream input population differs from its run control")
    for entry in actual:
        spec = expected[entry.artifact_id]
        if (
            any(
                getattr(entry, n) != getattr(spec, n)
                for n in (
                    "artifact_id",
                    "direction",
                    "role",
                    "path",
                    "format",
                    "condition",
                )
            )
            or mappings[entry.artifact_id].resolve() != spec.local_path.resolve()
        ):
            raise ValueError(
                "Upstream input binding differs from the exact manifest used"
            )


def load_release_authority(
    control: DatasetReleaseExportManifest, base: Path
) -> tuple[Any, Any, Any]:
    """Verify file lineage with integrity APIs, without upstream science."""
    qc_prov, qc_inventory, qc_inputs, qc_root = _upstream_run(
        control.stage32_run, base, "dataset_qc"
    )
    agg_prov, agg_inventory, agg_inputs, agg_root = _upstream_run(
        control.stage31_run,
        base,
        "replica_aggregation",
    )
    for role, path in (
        ("dataset_qc_decision_set", control.decision_set_path),
        ("dataset_qc_summary", control.qc_summary_path),
        ("qc_derived_replica_aggregation_manifest", control.qc_derived_manifest_path),
    ):
        _output(qc_inventory, qc_root, role, base / path)
    if {e.role for e in qc_inventory.artifacts if e.direction == "output"} != {
        "dataset_qc_decision_set",
        "dataset_qc_summary",
        "qc_derived_replica_aggregation_manifest",
    }:
        raise ValueError("Stage 32 production outputs are incomplete")
    decisions = read_dataset_qc_decision_set(base / control.decision_set_path)
    summary = read_dataset_qc_summary_csv(base / control.qc_summary_path)
    derived = read_replica_aggregation_manifest(base / control.qc_derived_manifest_path)
    used = read_replica_aggregation_manifest(
        base / control.aggregation_manifest_used_path
    )
    authority = DatasetReleaseAggregationAuthority(decisions, derived, used)
    qc_path = qc_inputs["input:dataset_qc_manifest"]
    qc_manifest = read_dataset_qc_manifest(qc_path)
    if {r.replica_key for r in qc_manifest.replicas} != {
        r.replica_key for r in decisions.records
    }:
        raise ValueError("Stage 32 control/decision candidate population differs")
    _input_specs(
        collect_dataset_qc_input_specs(qc_manifest, qc_path), qc_inventory, qc_inputs
    )
    expected_qc_configuration = dataset_qc_configuration(
        qc_manifest,
        qc_inventory.checksum_mode,
        DatasetQCOutputs(qc_manifest, decisions, summary, derived),
    )
    if release_json_text(
        qc_prov.to_dict()["resolved_configuration"]
    ) != release_json_text(expected_qc_configuration):
        raise ValueError(
            "Stage 32 production_ready/counts/control configuration differs"
        )
    used_path = base / control.aggregation_manifest_used_path
    if (
        agg_inputs["input:replica_aggregation_manifest"].resolve()
        != used_path.resolve()
    ):
        raise ValueError("Stage 31 provenance input must bind the exact manifest used")
    _input_specs(
        collect_replica_aggregation_input_specs(used, used_path),
        agg_inventory,
        agg_inputs,
    )
    expected_aggregation_configuration = replica_aggregation_configuration(
        used,
        agg_inventory.checksum_mode,
    )
    if release_json_text(
        agg_prov.to_dict()["resolved_configuration"]
    ) != release_json_text(expected_aggregation_configuration):
        raise ValueError("Stage 31 provenance configuration differs from manifest used")
    aggregates = {}
    empty_types = (
        CanonicalProteinEdgeReplicaAggregationTable,
        CanonicalProteinLipidReplicaAggregationTable,
        CanonicalProteinGlycanReplicaAggregationTable,
    )
    expected_roles = set()
    for family, empty_type in zip(FAMILIES, empty_types, strict=True):
        path = getattr(control, f"{family.name}_aggregate_path")
        produced = bool(getattr(used, f"{family.name}_canonical_table_paths"))
        if produced != (path is not None):
            raise ValueError(
                "Aggregate bindings must match every produced input family"
            )
        if path is None:
            aggregates[family.name] = empty_type(())
        else:
            expected_roles.add(family.output_role)
            _output(agg_inventory, agg_root, family.output_role, base / path)
            aggregates[family.name] = family.reader(base / path)
    if {
        e.role for e in agg_inventory.artifacts if e.direction == "output"
    } != expected_roles:
        raise ValueError("Stage 31 aggregate output population differs")
    return authority, summary, aggregates


def build_dataset_release(manifest_path: Path) -> DatasetReleaseBundle:
    """Read and build all 17 tables and manifest before any publication write."""
    phase = "manifest"
    try:
        control = read_dataset_release_export_manifest(manifest_path)
        base = manifest_path.parent
        phase = "lineage"
        authority, summary, aggregates = load_release_authority(control, base)
        phase = "input"
        candidates = {d.replica_key for d in authority.decisions.records}
        if {k[0] for k in candidates} != {control.dataset_id}:
            raise ValueError("Release Dataset differs from Stage 32 authority")
        canonical = {}
        for family in FAMILIES:
            coverage: set[tuple[str, str, str, str]] = set()
            rows = []
            for binding in control.canonical_bindings:
                if binding.family != family.name:
                    continue
                table = family.canonical_reader(base / binding.path)
                if not set(binding.replica_keys) <= candidates or any(
                    row.replica_key not in binding.replica_keys for row in table.rows
                ):
                    raise ValueError(
                        "Canonical rows disagree with explicit replica coverage"
                    )
                coverage.update(binding.replica_keys)
                rows.extend(table.rows)
            if not set(control.scientific_release_replica_keys) <= coverage:
                raise ValueError(
                    "Selected replica lacks required canonical family artifact coverage"
                )
            canonical[family.name] = family.canonical_table(
                tuple(sorted(rows, key=lambda r: r.row_order))
            )
        phase = "canonical source authority"
        validate_release_canonical_source_authority(
            control, authority.aggregation_manifest_used, canonical
        )
        phase = "input"
        temporal = tuple(
            b
            for path in control.temporal_evidence_paths
            for b in read_preprocessing_temporal_execution(base / path).bindings
        )
        annotations = []
        for annotation_binding in control.annotation_bindings:
            annotation = read_dataset_system_biological_annotations(
                base / annotation_binding.path
            )
            if (annotation.dataset_id, annotation.system_id) != (
                annotation_binding.dataset_id,
                annotation_binding.system_id,
            ):
                raise ValueError(
                    "Annotation file differs from the explicit system binding"
                )
            annotations.append(annotation)
        inputs = read_dataset_release_publication_inputs(
            base / control.publication_inputs_path
        )
        phase = "metadata export"
        metadata = build_dataset_release_metadata_tables(
            decisions=authority.decisions,
            summary=summary,
            aggregation_authority=QCDerivedAggregationEvidence(
                authority.qc_derived_aggregation_manifest,
                authority.decisions,
                "qc_derived_replica_aggregation_manifest",
                control.qc_derived_manifest_path,
            ),
            scientific_release_replica_keys=control.scientific_release_replica_keys,
            annotation_publication_system_keys=control.annotation_publication_system_keys,
            temporal_evidence=temporal,
            annotation_metadata=tuple(annotations),
            contact_definitions=inputs.contact_definitions,
            software_version_records=inputs.software_versions.records(),
        )
        phase = "metric source authority"
        validate_publication_metric_sources(inputs, control, base, metadata)
        phase = "science export"
        science = build_dataset_release_scientific_tables(
            metadata_tables=metadata,
            canonical_protein_edges=canonical["protein"],
            canonical_protein_lipid_contacts=canonical["lipid"],
            canonical_protein_glycan_contacts=canonical["glycan"],
            aggregation_authority=authority,
            protein_aggregate_table=aggregates["protein"],
            lipid_aggregate_table=aggregates["lipid"],
            glycan_aggregate_table=aggregates["glycan"],
            metrics=inputs.metrics,
        )
        phase = "validation"
        from mania.dataset_release_validation import validate_dataset_release_tables

        validate_dataset_release_tables(metadata, science, authority, control)
        manifest = DatasetReleaseManifest(
            control.dataset_id,
            control.decision_set_path,
            control.qc_derived_manifest_path,
            control.stage31_run.provenance_path,
            boundary_profile=metadata.boundary_profile,
        )
        bundle = DatasetReleaseBundle(control, metadata, science, manifest, authority)
        for table in bundle.tables:
            publication_csv_bytes(table)
        release_json_text(manifest.to_dict())
        return bundle
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise DatasetReleaseError(
            f"Dataset release {phase} failed: invalid or inconsistent authority."
        ) from None
