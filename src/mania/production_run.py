"""Thin production operations over existing preprocessing, replay, QC and aggregation.

No coordinate preparation, scientific policy, or contact calculation lives here.
The input binding is an external attestation, not an automatically issued PBC PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mania import canonical_window_tables_io as canonical_io
from mania.artifact_inventory_io import read_artifact_inventory
from mania.biological_annotations_io import read_dataset_system_biological_annotations
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.canonical_window_tables import DatasetCanonicalResidueMappingBinding
from mania.dataset_qc_evidence_io import read_replica_hard_qc_evidence
from mania.dataset_qc_manifest_io import read_dataset_qc_manifest
from mania.dataset_qc_run import collect_dataset_qc_input_specs, run_dataset_qc
from mania.dataset_qc_workflow import build_qc_derived_replica_aggregation_manifest
from mania.preprocessing.input_manifest import (
    PreprocessingInputManifest,
    TrajectoryInputConfig,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    read_molecular_partner_metadata,
    read_strict_json,
    write_atomic_text,
)
from mania.preprocessing.namd_authority import (
    ElementControl,
    TimeControl,
    read_control,
    validate_elements,
    validate_time,
)
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.temporal_policy import PreprocessingTemporalPolicy
from mania.preprocessing.window_replay import replay_window_tables
from mania.production_catalog import (
    CATALOG_COLUMNS,
    CONTROL_COLUMNS,
    RAW_COLUMNS,
    CatalogTrajectory,
    ProductionCatalog,
    ProductionError,
    contained_path,
    data_root_from_environment,
    load_production_catalog,
    portable_path,
)
from mania.replica_aggregation_contract import ReplicaAggregationWindowDefinition
from mania.replica_aggregation_manifest import ReplicaAggregationManifest
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_aggregation_run import (
    collect_replica_aggregation_input_specs,
    run_replica_aggregation,
)
from mania.run_provenance_io import read_run_provenance
from mania.validation import validate_run_artifacts

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1)]
_BINDING_FILES = {
    *RAW_COLUMNS,
    *CONTROL_COLUMNS,
    "prepared_trajectory",
    "prepared_time_control",
    "pbc_evidence",
}
_FAMILY_FILES = {
    "protein": "protein_edges_by_window_canonical.csv",
    "lipid": "protein_lipid_contacts_by_window_canonical.csv",
    "glycan": "protein_glycan_contacts_by_window_canonical.csv",
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class BoundFile(_StrictModel):
    path: str
    size_bytes: Annotated[int, Field(gt=0)]
    sha256: Digest

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        portable_path(value)
        return value


class PreparedLineage(_StrictModel):
    protocol: Literal["unwrap_bonded_fragments_center_protein_wrap_complete_fragments"]
    internal_mic: Literal[False]
    atom_order_preserved: Literal[True]
    frame_order_preserved: Literal[True]
    topology_sha256: Digest
    raw_trajectory_sha256: Digest
    prepared_trajectory_sha256: Digest
    frame_count: Annotated[int, Field(gt=0)]
    atom_count: Annotated[int, Field(gt=0)]
    reviewer: Text
    note: Text

    @field_validator("reviewer", "note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("External authority must be nonblank and stripped")
        return value

    @field_validator(
        "internal_mic", "atom_order_preserved", "frame_order_preserved", mode="before"
    )
    @classmethod
    def exact_boolean(cls, value: Any) -> bool:
        if type(value) is not bool:
            raise ValueError("Lineage flags must be JSON booleans")
        return value


class ProductionInputBinding(_StrictModel):
    schema_version: Literal["mania.production_input_binding.v0.1"]
    dataset_id: str
    catalog_row: dict[str, str]
    temporal_policy: PreprocessingTemporalPolicy
    files: dict[str, BoundFile]
    prepared_lineage: PreparedLineage

    @field_validator("catalog_row")
    @classmethod
    def exact_row(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) != set(CATALOG_COLUMNS):
            raise ValueError("Input binding must retain every exact catalog column")
        return value

    @field_validator("files")
    @classmethod
    def exact_files(cls, value: dict[str, BoundFile]) -> dict[str, BoundFile]:
        if set(value) != _BINDING_FILES:
            raise ValueError(
                "Input binding requires the exact raw/control/prepared roles"
            )
        return value

    @model_validator(mode="after")
    def lineage_hashes(self) -> ProductionInputBinding:
        for field, role in (
            ("topology_sha256", "topology_path"),
            ("raw_trajectory_sha256", "trajectory_path"),
            ("prepared_trajectory_sha256", "prepared_trajectory"),
        ):
            if getattr(self.prepared_lineage, field) != self.files[role].sha256:
                raise ValueError("Prepared-input lineage digest mismatch")
        return self


def read_production_input_binding(path: Path) -> ProductionInputBinding:
    return ProductionInputBinding.model_validate(read_strict_json(path))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _readable(path: Path) -> None:
    if not path.is_file() or not os.access(path, os.R_OK):
        raise ProductionError(f"Required readable regular file is missing: {path}")
    with path.open("rb") as stream:
        stream.read(1)


def _within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ProductionError(f"Scientific path escapes MANIA_DATA_ROOT: {path}")
    return resolved


def _output_root(
    output: Path, data_root: Path, min_free_bytes: int
) -> tuple[Path, int]:
    if type(min_free_bytes) is not int or min_free_bytes < 0:
        raise ProductionError("min-free-bytes must be a nonnegative integer")
    absolute = output.absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise ProductionError("Output directory ancestors must not be symlinks")
    resolved = absolute.resolve()
    if resolved.is_relative_to(data_root) or data_root.is_relative_to(resolved):
        raise ProductionError("Source/output collision: roots must be disjoint")
    ancestor = resolved
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
        raise ProductionError("Output destination is not a writable directory")
    free = shutil.disk_usage(ancestor).free
    if free < min_free_bytes:
        raise ProductionError(
            f"Insufficient free space: {free} < {min_free_bytes} bytes"
        )
    return resolved, free


def _no_symlinks(root: Path) -> None:
    if any(p.is_symlink() for p in (root, *root.parents)) or (
        root.exists() and any(p.is_symlink() for p in root.rglob("*"))
    ):
        raise ProductionError("Output tree must not contain symlinks")


def _write_json(path: Path, value: Any) -> None:
    result = write_atomic_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        path,
        overwrite=False,
    )
    if not result.passed:
        raise ProductionError(f"Protected output write failed: {path}")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ProductionPreflight:
    catalog: ProductionCatalog
    selected: CatalogTrajectory
    data_root: Path
    output_root: Path
    binding_path: Path
    binding: ProductionInputBinding
    paths: dict[str, Path]
    free_bytes: int

    @property
    def trajectory_root(self) -> Path:
        return self.output_root / "trajectories" / self.selected.trajectory_id

    def request(self) -> dict[str, Any]:
        return {
            "schema_version": "mania.production_request.v0.1",
            "catalog_version": self.catalog.descriptor["catalog_version"],
            "dataset_version": self.catalog.descriptor["dataset_version"],
            "binding_path": self.binding_path.relative_to(self.data_root).as_posix(),
            "binding_sha256": file_digest(self.binding_path),
            "binding": self.binding.model_dump(mode="json"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "preflight_passed",
            "trajectory_id": self.selected.trajectory_id,
            "replica_group_id": self.selected.group_id,
            "output": str(self.trajectory_root),
            "free_bytes": self.free_bytes,
            "catalog_readiness": self.selected.row["readiness_status"],
            "temporal_policy": self.catalog.temporal_policy.model_dump(mode="json"),
            "trajectory_pbc_qc_certified": False,
        }


def _validate_controls(preflight: ProductionPreflight) -> None:
    p, binding = preflight.paths, preflight.binding
    elements = read_control(p["element_control"], ElementControl)
    raw = read_control(p["time_control"], TimeControl)
    prepared = read_control(p["prepared_time_control"], TimeControl)
    # Embedded control paths are used literally. No basename or mass-based guessing.
    embedded = [
        elements.psf.path,
        elements.source_directory,
        *(s.path for s in elements.sources),
    ]
    for time in (raw, prepared):
        embedded.extend((time.config.path, time.log.path, time.dcd.path))
        if (
            Path(time.config.path).resolve() != p["config_path"]
            or Path(time.log.path).resolve() != p["log_path"]
        ):
            raise ProductionError("Time control/source identity mismatch")
    for path in embedded:
        if not Path(path).is_absolute():
            raise ProductionError("Embedded authority paths must be explicitly rebound")
        _within(preflight.data_root, Path(path))
    validate_elements(elements, p["topology_path"])
    raw_times = validate_time(raw, p["trajectory_path"])
    prepared_times = validate_time(prepared, p["prepared_trajectory"])
    lineage = binding.prepared_lineage
    if (
        raw_times != prepared_times
        or raw.dcd.frame_count != prepared.dcd.frame_count
        or raw.dcd.frame_count != lineage.frame_count
        or raw.dcd.atom_count != prepared.dcd.atom_count
        or raw.dcd.atom_count != lineage.atom_count
        or sum(elements.used_type_counts.values()) != lineage.atom_count
        or lineage.topology_sha256 != binding.files["topology_path"].sha256
        or lineage.raw_trajectory_sha256 != binding.files["trajectory_path"].sha256
        or lineage.prepared_trajectory_sha256
        != binding.files["prepared_trajectory"].sha256
        or p["trajectory_path"].samefile(p["prepared_trajectory"])
    ):
        raise ProductionError("Prepared-input lineage/frame/atom/time mismatch")
    # Require the full source production axis; analysis selection remains Stage 27.
    if raw.production_end_step * float(raw.timestep_fs) / 1_000_000 != float(
        preflight.selected.row["nominal_duration_ns"]
    ):
        raise ProductionError("Source time authority does not cover catalog production")
    read_canonical_residue_mapping(p["canonical_mapping"])
    annotations = read_dataset_system_biological_annotations(
        p["biological_annotations"]
    )
    identity = preflight.selected.spec.identity
    if (annotations.dataset_id, annotations.system_id) != identity.replica_key[:2]:
        raise ProductionError("Biological annotation system identity mismatch")
    read_molecular_partner_metadata(p["partner_metadata"])


def preflight_trajectory(
    catalog_path: Path,
    trajectory_id: str,
    output_root: Path,
    *,
    input_binding: Path | None = None,
    min_free_bytes: int = 0,
    resume: bool = False,
) -> ProductionPreflight:
    catalog = load_production_catalog(catalog_path)
    selected = catalog.trajectory(trajectory_id)
    if selected.row["source_group"] != "egor_namd":
        raise ProductionError("This interface currently supports Egor NAMD selections")
    data_root = data_root_from_environment()
    output, free = _output_root(output_root, data_root, min_free_bytes)
    target = output / "trajectories" / selected.trajectory_id
    _no_symlinks(target)
    if target.exists() and not resume:
        raise ProductionError("Existing trajectory output is protected; use --resume")
    if input_binding is None:
        if not resume or not (target / "request.json").is_file():
            raise ProductionError(
                "Explicit --input-binding with prepared lineage is required"
            )
        request = read_strict_json(target / "request.json")
        input_binding = contained_path(data_root, request["binding_path"])
    binding_path = _within(data_root, input_binding)
    _readable(binding_path)
    binding = read_production_input_binding(binding_path)
    if (
        binding.catalog_row != selected.row
        or binding.dataset_id != selected.spec.identity.dataset_id
        or binding.temporal_policy != catalog.temporal_policy
    ):
        raise ProductionError(
            "Catalog/control/timing identity mismatch in input binding"
        )
    # Check catalog paths even when an explicit binding relocates their files.
    for key in (*RAW_COLUMNS, *CONTROL_COLUMNS):
        if selected.row[key]:
            contained_path(data_root, selected.row[key])
    paths = {}
    for role, record in binding.files.items():
        path = contained_path(data_root, record.path)
        _readable(path)
        if (
            path.stat().st_size != record.size_bytes
            or file_digest(path) != record.sha256
        ):
            raise ProductionError(f"Stale/wrong bound input: {role}")
        paths[role] = path
    result = ProductionPreflight(
        catalog, selected, data_root, output, binding_path, binding, paths, free
    )
    _validate_controls(result)
    if (
        target.exists()
        and read_strict_json(target / "request.json") != result.request()
    ):
        raise ProductionError("Changed inputs/catalog/control lineage forbid resume")
    return result


def _manifest(preflight: ProductionPreflight) -> PreprocessingInputManifest:
    p = preflight.paths
    return PreprocessingInputManifest(
        output_root=preflight.trajectory_root / "preprocessing",
        temporal_policy=preflight.catalog.temporal_policy,
        conditions=(
            TrajectoryInputConfig(
                condition=preflight.selected.spec.identity.condition or "",
                topology_path=p["topology_path"],
                trajectory_paths=(p["prepared_trajectory"],),
                dataset_spec=preflight.selected.spec,
                canonical_residue_mapping_path=p["canonical_mapping"],
                biological_annotation_metadata_path=p["biological_annotations"],
                molecular_partner_metadata_path=p["partner_metadata"],
                namd_element_control_path=p["element_control"],
                namd_time_control_path=p["prepared_time_control"],
                production_input_binding_path=preflight.binding_path,
            ),
        ),
    )


def _preprocessing_mappings(preflight: ProductionPreflight) -> dict[str, Path]:
    p = preflight.paths
    condition = "input:condition:0001:"
    return {
        "input:manifest": preflight.trajectory_root / "inputs" / "preprocessing.json",
        condition + "topology": p["topology_path"],
        condition + "trajectory:0001": p["prepared_trajectory"],
        condition + "molecular_partner_metadata": p["partner_metadata"],
        condition + "namd_element_control": p["element_control"],
        condition + "namd_time_control": p["prepared_time_control"],
        condition + "production_input_binding": preflight.binding_path,
        "input:canonical_residue_mapping:0001": p["canonical_mapping"],
        "input:biological_annotation_metadata:0001": p["biological_annotations"],
    }


def _validate_stage(
    root: Path, scope: Any, mappings: dict[str, Path]
) -> dict[str, Any]:
    _no_symlinks(root)
    inventory = read_artifact_inventory(root / "artifact_inventory.json")
    if {e.artifact_id for e in inventory.artifacts if e.direction == "input"} != set(
        mappings
    ):
        raise ProductionError("Stage input inventory differs from explicit bindings")
    provenance = read_run_provenance(root / "run_provenance.json")
    report = validate_run_artifacts(root, scope=scope, input_artifact_paths=mappings)
    if (
        provenance.status != "completed"
        or report.status != "passed"
        or not report.complete
        or report.unsupported_count
    ):
        raise ProductionError(
            "Completed stage requires passed, complete artifact validation"
        )
    return report.to_dict()


def _science(preflight: ProductionPreflight) -> PreprocessingTemporalExecution:
    root = preflight.trajectory_root / "preprocessing"
    manifest_path = preflight.trajectory_root / "inputs" / "preprocessing.json"
    if read_strict_json(manifest_path) != _manifest(preflight).model_dump(mode="json"):
        raise ProductionError("Saved execution manifest differs from catalog controls")
    _validate_stage(root, "preprocessing", _preprocessing_mappings(preflight))
    temporal = read_preprocessing_temporal_execution(root / "temporal_execution.json")
    if len(temporal.bindings) != 1 or (
        temporal.bindings[0].dataset_spec != preflight.selected.spec
        or temporal.bindings[0].window_plan.boundary_profile
        != preflight.catalog.temporal_policy.boundary_profile
    ):
        raise ProductionError(
            "Completed science has incompatible Dataset/temporal binding"
        )
    # Strict completion reading and accepted window aggregation; zero geometry calls.
    replay_window_tables(root, temporal)
    return temporal


def _tree_digests(root: Path) -> dict[str, str]:
    _no_symlinks(root)
    return {
        p.relative_to(root).as_posix(): file_digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def run_production_trajectory(
    catalog_path: Path,
    trajectory_id: str,
    output_root: Path,
    *,
    input_binding: Path | None = None,
    min_free_bytes: int,
    resume: bool = False,
) -> dict[str, Any]:
    if type(min_free_bytes) is not int or min_free_bytes <= 0:
        raise ProductionError("production run requires positive min-free-bytes")
    preflight = preflight_trajectory(
        catalog_path,
        trajectory_id,
        output_root,
        input_binding=input_binding,
        min_free_bytes=min_free_bytes,
        resume=resume,
    )
    root = preflight.trajectory_root
    reused = root.exists()
    if not reused:
        root.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir()  # Exclusive claim; a concurrent launcher cannot share this run.
        _write_json(root / "request.json", preflight.request())
        manifest_path = root / "inputs" / "preprocessing.json"
        _write_json(manifest_path, _manifest(preflight).model_dump(mode="json"))
        from mania.cli import run_production_preprocessing

        run_production_preprocessing(
            manifest_path,
            root / "preprocessing",
            preflight.selected.spec.identity.condition or "",
        )
        # A source/control change during computation cannot receive a completion claim.
        preflight = preflight_trajectory(
            catalog_path,
            trajectory_id,
            output_root,
            input_binding=input_binding,
            min_free_bytes=0,
            resume=True,
        )
    _science(preflight)  # Incomplete computation is never resumed or overwritten.
    completion = {
        "request_sha256": _hash_json(preflight.request()),
        "artifacts": _tree_digests(root / "preprocessing"),
    }
    marker = root / "science_complete.json"
    if marker.exists():
        if read_strict_json(marker) != completion:
            raise ProductionError("Changed completed artifacts forbid resume")
    else:
        _write_json(marker, completion)
    return {
        "status": "science_complete",
        "trajectory_id": trajectory_id,
        "reused": reused,
        "output": str(root),
        "qc_status": "not_evaluated",
    }


def _accepted_trajectory(
    catalog: Path,
    selected: CatalogTrajectory,
    output: Path,
) -> tuple[ProductionPreflight, PreprocessingTemporalExecution]:
    preflight = preflight_trajectory(
        catalog, selected.trajectory_id, output, resume=True
    )
    marker = preflight.trajectory_root / "science_complete.json"
    if not marker.is_file():
        raise ProductionError(
            f"Completed science is required: {selected.trajectory_id}"
        )
    completion = read_strict_json(marker)
    if completion != {
        "request_sha256": _hash_json(preflight.request()),
        "artifacts": _tree_digests(preflight.trajectory_root / "preprocessing"),
    }:
        raise ProductionError("Changed completed trajectory evidence")
    return preflight, _science(preflight)


def _windows(
    temporal: PreprocessingTemporalExecution,
) -> tuple[ReplicaAggregationWindowDefinition, ...]:
    binding = temporal.bindings[0]
    p = binding.dataset_spec.temporal
    return tuple(
        ReplicaAggregationWindowDefinition(
            w.window_id,
            w.window_index,
            p.production_start_ns,
            p.production_end_ns,
            w.requested_start_ns,
            w.requested_end_ns,
            w.right_endpoint_inclusive,
            p.window_length_ns,
            p.window_step_ns,
            p.overlap_percent,
            binding.window_plan.boundary_profile,
        )
        for w in binding.window_plan.windows
    )


def _group_template(
    template: ReplicaAggregationManifest,
    completed: tuple[tuple[ProductionPreflight, PreprocessingTemporalExecution], ...],
) -> None:
    windows = _windows(completed[0][1])
    if any(_windows(t) != windows for _, t in completed):
        raise ProductionError("Mixed or incompatible temporal profiles/windows")
    members = {p.selected.spec.identity.replica_key: p for p, _ in completed}
    if len(template.groups) != len(windows) or {
        g.spec.window for g in template.groups
    } != set(windows):
        raise ProductionError("Aggregation template must cover exact catalog windows")
    identity_fields = (
        "dataset_id",
        "system_id",
        "engine",
        "variant_id",
        "condition",
        "disulfide_state",
    )
    first = completed[0][0].selected.spec.identity
    for group in template.groups:
        if (
            set(group.spec.expected_replica_ids) != {k[3] for k in members}
            or {m.replica_key for m in group.members} != set(members)
            or any(getattr(group.spec, k) != getattr(first, k) for k in identity_fields)
        ):
            raise ProductionError("Cross-group or incomplete catalog membership")
        for member in group.members:
            identity = members[member.replica_key].selected.spec.identity
            if any(getattr(member, k) != getattr(identity, k) for k in identity_fields):
                raise ProductionError("Conflicting aggregation member identity")
    for family, filename in _FAMILY_FILES.items():
        paths = getattr(template, f"{family}_canonical_table_paths")
        if family == "protein" or paths:
            expected = {
                p.trajectory_root / "preprocessing" / filename for p, _ in completed
            }
            if set(paths) != expected:
                raise ProductionError("Aggregation must use completed catalog science")
        if family != "protein" and paths:
            for group in template.groups:
                if any(
                    m.availability_status == "available" for m in group.members
                ) and (not getattr(group, f"{family}_correspondences").correspondences):
                    raise ProductionError(
                        "Specialized aggregation requires correspondence"
                    )


def assemble_production_group(
    catalog_path: Path,
    replica_group_id: str,
    output_root: Path,
    *,
    qc_manifest: Path | None = None,
    min_free_bytes: int = 0,
) -> dict[str, Any]:
    catalog = load_production_catalog(catalog_path)
    selected = catalog.group(replica_group_id)
    data_root = data_root_from_environment()
    output, _ = _output_root(output_root, data_root, min_free_bytes)
    group_root = output / "groups" / replica_group_id
    _no_symlinks(group_root)
    completed = tuple(_accepted_trajectory(catalog_path, s, output) for s in selected)
    if qc_manifest is None:
        return {
            "status": "blocked_qc",
            "replica_group_id": replica_group_id,
            "science_preserved": True,
            "reason": "Explicit --qc-manifest is required",
        }
    qc_path = _within(data_root, qc_manifest)
    _readable(qc_path)
    control = read_dataset_qc_manifest(qc_path)
    if {r.replica_key for r in control.replicas} != {
        s.spec.identity.replica_key for s in selected
    }:
        raise ProductionError("QC must cover exact expected catalog membership")
    specs = collect_dataset_qc_input_specs(control, qc_path)
    for spec in specs:
        _readable(_within(data_root, spec.local_path))
    template = read_replica_aggregation_manifest(
        qc_path.parent / control.aggregation_manifest_template_path
    )
    _group_template(template, completed)
    temporal_by_key = {p.selected.spec.identity.replica_key: t for p, t in completed}
    inputs_by_key = {p.selected.spec.identity.replica_key: p for p, _ in completed}
    for replica in control.replicas:
        hard = read_replica_hard_qc_evidence(
            qc_path.parent / replica.hard_qc_evidence_path
        )
        actual = temporal_by_key[replica.replica_key].bindings[0]
        if hard.identity != actual.dataset_spec.identity or (
            hard.sampling_plan != actual.sampling_plan
        ):
            raise ProductionError("QC evidence must bind the actual completed sampling")
        completed_input = inputs_by_key[replica.replica_key]
        expected_mapping = DatasetCanonicalResidueMappingBinding(
            *replica.replica_key,
            read_canonical_residue_mapping(completed_input.paths["canonical_mapping"]),
        )
        if (
            hard.mapping_binding is not None
            and hard.mapping_binding != expected_mapping
        ):
            raise ProductionError(
                "QC mapping differs from completed canonical authority"
            )
        for evidence in hard.required_artifacts:
            family = {
                "protein_edge": "protein",
                "protein_lipid": "lipid",
                "protein_glycan": "glycan",
            }.get(evidence.canonical_family or "")
            if evidence.canonical_table is not None and family is not None:
                kind = "edge" if family == "protein" else family
                table = getattr(
                    canonical_io, f"read_canonical_protein_{kind}_window_csv"
                )(
                    completed_input.trajectory_root
                    / "preprocessing"
                    / _FAMILY_FILES[family]
                )
                if evidence.canonical_table != table:
                    raise ProductionError(
                        "QC scientific evidence differs from saved science"
                    )
    request = {
        "inputs": {s.artifact_id: file_digest(s.local_path) for s in specs},
        "science": {
            p.selected.trajectory_id: _hash_json(
                read_strict_json(p.trajectory_root / "science_complete.json")
            )
            for p, _ in completed
        },
    }
    # A changed manual resolution gets a separate attempt, preserving prior evidence.
    attempt = group_root / "attempts" / _hash_json(request)
    qc_root, aggregate_root = attempt / "qc", attempt / "aggregation"
    qc_mappings = {s.artifact_id: s.local_path for s in specs}
    if not attempt.exists():
        attempt.parent.mkdir(parents=True, exist_ok=True)
        attempt.mkdir()
        _write_json(attempt / "request.json", request)
    elif read_strict_json(attempt / "request.json") != request:
        raise ProductionError("Group attempt identity mismatch")
    qc_marker = attempt / "qc_complete.json"
    if qc_root.exists():
        _validate_stage(qc_root, "dataset_qc", qc_mappings)
    else:
        run_dataset_qc(qc_path, qc_root, checksum_mode="sha256")
        _validate_stage(qc_root, "dataset_qc", qc_mappings)
    qc_hashes = _tree_digests(qc_root)
    if qc_marker.exists():
        if read_strict_json(qc_marker) != qc_hashes:
            raise ProductionError("Changed accepted QC outputs")
    else:
        _write_json(qc_marker, qc_hashes)
    from mania.dataset_qc_decision_io import read_dataset_qc_decision_set

    decisions = read_dataset_qc_decision_set(qc_root / "dataset_qc_decision_set.json")
    if any(r.release_decision == "pending_review" for r in decisions.records):
        return {
            "status": "pending_review",
            "replica_group_id": replica_group_id,
            "science_preserved": True,
            "output": str(attempt),
        }
    derived = build_qc_derived_replica_aggregation_manifest(template, decisions)
    derived_path = qc_root / "replica_aggregation_manifest_qc_derived.json"
    if read_replica_aggregation_manifest(derived_path) != derived:
        raise ProductionError("Aggregation requires exact QC-derived availability")
    aggregation_specs = collect_replica_aggregation_input_specs(derived, derived_path)
    if not aggregate_root.exists():
        run_replica_aggregation(derived_path, aggregate_root, checksum_mode="sha256")
    _validate_stage(
        aggregate_root,
        "replica_aggregation",
        {s.artifact_id: s.local_path for s in aggregation_specs},
    )
    final = {"request": request, "artifacts": _tree_digests(aggregate_root)}
    marker = attempt / "aggregation_complete.json"
    if marker.exists():
        if read_strict_json(marker) != final:
            raise ProductionError("Changed accepted aggregation outputs")
    else:
        _write_json(marker, final)
    return {
        "status": "aggregation_complete",
        "replica_group_id": replica_group_id,
        "output": str(attempt),
        "science_preserved": True,
    }
