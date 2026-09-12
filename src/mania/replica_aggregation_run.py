"""Narrow Stage 31 adapters for the unchanged inventory and provenance schemas."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mania.artifact_inventory import ArtifactChecksumMode
from mania.artifact_inventory_io import (
    ArtifactInventoryFileSpec,
    build_artifact_inventory,
    write_artifact_inventory,
)
from mania.replica_aggregation_manifest import ReplicaAggregationManifest
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_aggregation_workflow import (
    FAMILIES,
    build_replica_aggregation_tables,
    load_replica_aggregation_inputs,
)
from mania.run_provenance import (
    PortableArtifactReference,
    RunProvenance,
    RunProvenanceIssue,
)
from mania.run_provenance_io import read_run_provenance, write_run_provenance
from mania.software_identity import get_software_identity

REPLICA_AGGREGATION_WORKFLOW = "replica_aggregation"
MANIFEST_ROLE = "replica_aggregation_manifest"
MANIFEST_ARTIFACT_ID = "input:replica_aggregation_manifest"
MANIFEST_PORTABLE_PATH = "inputs/replica_aggregation_manifest.json"


def collect_replica_aggregation_input_specs(
    manifest: ReplicaAggregationManifest,
    manifest_path: Path,
) -> tuple[ArtifactInventoryFileSpec, ...]:
    specs = [
        ArtifactInventoryFileSpec(
            MANIFEST_ARTIFACT_ID,
            "input",
            MANIFEST_ROLE,
            manifest_path,
            MANIFEST_PORTABLE_PATH,
            "json",
        )
    ]
    for family in FAMILIES:
        for index, path in enumerate(
            getattr(manifest, f"{family.name}_canonical_table_paths"),
            start=1,
        ):
            specs.append(
                ArtifactInventoryFileSpec(
                    f"input:{family.name}:{index:04d}",
                    "input",
                    family.input_role,
                    path,
                    f"inputs/{family.name}/{index:04d}/canonical.csv",
                    "csv",
                )
            )
    return tuple(specs)


def replica_aggregation_configuration(
    manifest: ReplicaAggregationManifest,
    checksum_mode: ArtifactChecksumMode,
) -> dict[str, object]:
    return {
        "workflow": REPLICA_AGGREGATION_WORKFLOW,
        "manifest_path": MANIFEST_PORTABLE_PATH,
        "canonical_reference": {
            "reference_id": manifest.canonical_reference_id,
            "sequence_sha256": manifest.canonical_reference_sequence_sha256,
        },
        "group_count": len(manifest.groups),
        "input_families": {
            f.name: bool(getattr(manifest, f"{f.name}_canonical_table_paths"))
            for f in FAMILIES
        },
        "scientific_conditions": list(
            dict.fromkeys(group.spec.condition for group in manifest.groups)
        ),
        "artifact_checksum_mode": checksum_mode,
    }


class ReplicaAggregationRunError(ValueError):
    """A portable CLI failure, with the execution phase preserved."""


@dataclass(frozen=True)
class ReplicaAggregationRunResult:
    output_dir: Path
    tables: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow": REPLICA_AGGREGATION_WORKFLOW,
            "status": "completed",
            "group_outputs": {
                family.filename: self.tables[family.name].row_count
                for family in FAMILIES
                if family.name in self.tables
            },
            "artifact_inventory": "artifact_inventory.json",
            "run_provenance": "run_provenance.json",
            "trajectory_passes": 0,
        }


def run_replica_aggregation(
    manifest_path: Path,
    output_dir: Path,
    *,
    checksum_mode: ArtifactChecksumMode = "none",
    overwrite: bool = False,
) -> ReplicaAggregationRunResult:
    if checksum_mode not in ("none", "sha256") or type(overwrite) is not bool:
        raise ValueError("Invalid checksum mode or overwrite")
    try:
        manifest = read_replica_aggregation_manifest(manifest_path)
    except ValueError as exc:
        raise ReplicaAggregationRunError(
            f"Replica aggregation manifest failed: {exc}"
        ) from None
    input_specs = collect_replica_aggregation_input_specs(manifest, manifest_path)
    paths = [output_dir / f.filename for f in FAMILIES]
    paths.extend(
        output_dir / name
        for name in (
            "artifact_inventory.json",
            "run_provenance.json",
        )
    )
    try:
        if any(
            p.resolve() == s.local_path.resolve()
            or (p.exists() and s.local_path.exists() and p.samefile(s.local_path))
            for p in paths
            for s in input_specs
        ):
            raise ValueError("Output must not replace aggregation inputs")
        if not overwrite and any(os.path.lexists(p) for p in paths):
            raise ValueError("Target already exists; use --overwrite")
        if (output_dir / "run_provenance.json").exists() and (
            read_run_provenance(output_dir / "run_provenance.json").workflow
            != REPLICA_AGGREGATION_WORKFLOW
        ):
            raise ValueError("A dedicated replica aggregation output root is required")
        if any(
            (output_dir / f.filename).exists()
            and not getattr(manifest, f"{f.name}_canonical_table_paths")
            for f in FAMILIES
        ):
            raise ValueError("Unexpected existing aggregate for absent input family")
    except (OSError, ValueError):
        raise ReplicaAggregationRunError(
            "Replica aggregation export write failed: output preflight failed."
        ) from None

    started = datetime.now(UTC)
    run_id = "replica-aggregation-" + started.strftime("%Y%m%dT%H%M%S%fZ")
    software = get_software_identity()
    outputs: list[ArtifactInventoryFileSpec] = []
    phase = "input"
    failure: str | None = None
    tables: dict[str, Any] = {}
    try:
        inputs = load_replica_aggregation_inputs(manifest)
        phase = "aggregation"
        tables = build_replica_aggregation_tables(manifest, inputs)
        phase = "export write"
        for family in FAMILIES:
            if family.name not in tables:
                continue
            result = family.writer(tables[family.name], output_dir, overwrite=overwrite)
            if not result.written:
                raise ValueError("Aggregate CSV write failed")
            outputs.append(
                ArtifactInventoryFileSpec(
                    f"output:{family.name}",
                    "output",
                    family.output_role,
                    result.output_path,
                    family.filename,
                    "csv",
                )
            )
    except Exception:
        failure = (
            "Replica aggregation failed: group or correspondence validation failed."
            if phase == "aggregation"
            else f"Replica aggregation {phase} failed: workflow could not finish."
        )

    references = [PortableArtifactReference(s.role, s.path) for s in outputs]
    try:
        inventory = build_artifact_inventory(
            run_id=run_id,
            workflow=REPLICA_AGGREGATION_WORKFLOW,
            inventory_path="artifact_inventory.json",
            file_specs=input_specs + tuple(outputs),
            checksum_mode=checksum_mode,
        )
        written = write_artifact_inventory(inventory, output_dir, overwrite=overwrite)
        if not written.written:
            raise ValueError("Inventory write failed")
        references.append(
            PortableArtifactReference(
                "artifact_inventory",
                "artifact_inventory.json",
            )
        )
    except Exception:
        failure = (
            failure or "Replica aggregation export write failed: inventory failed."
        )

    try:
        provenance = RunProvenance(
            run_id=run_id,
            workflow=REPLICA_AGGREGATION_WORKFLOW,
            status="failed" if failure else "completed",
            started_at_utc=started,
            ended_at_utc=datetime.now(UTC),
            software_identity=software,
            command=(
                "mania",
                "dataset",
                "aggregate-replicas",
                "--manifest",
                MANIFEST_PORTABLE_PATH,
                "--output",
                ".",
                "--artifact-checksum-mode",
                checksum_mode,
            )
            + (("--overwrite",) if overwrite else ()),
            resolved_configuration=replica_aggregation_configuration(
                manifest,
                checksum_mode,
            ),
            conditions=tuple(
                dict.fromkeys(
                    g.spec.condition
                    for g in manifest.groups
                    if g.spec.condition is not None
                )
            ),
            artifact_references=tuple(references),
            issues=(
                RunProvenanceIssue(
                    "error",
                    "replica_aggregation_failed",
                    "Replica aggregation run failed.",
                    phase,
                    None,
                ),
            )
            if failure
            else (),
        )
        if not write_run_provenance(
            provenance, output_dir, overwrite=overwrite
        ).written:
            raise ValueError("Provenance write failed")
    except Exception:
        failure = (
            failure or "Replica aggregation export write failed: provenance failed."
        )
    if failure:
        raise ReplicaAggregationRunError(failure)
    return ReplicaAggregationRunResult(output_dir, tables)
