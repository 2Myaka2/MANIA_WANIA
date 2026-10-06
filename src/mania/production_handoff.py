"""Portable compact production handoff, independent of producer/coordinate storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator

from mania.artifact_inventory import ArtifactInventory, ArtifactInventoryEntry
from mania.artifact_inventory_io import read_artifact_inventory
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.canonical_window_tables import (
    DatasetCanonicalResidueMappingBinding,
    DatasetCanonicalResidueMappingBindings,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.preprocessing.molecular_partner_metadata_io import (
    read_molecular_partner_metadata,
    read_strict_json,
    write_atomic_text,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.protein_integrity_observations import (
    read_protein_integrity,
    validate_protein_integrity,
)
from mania.preprocessing.trajectory_rmsd import StrictModel
from mania.preprocessing.trajectory_rmsd_io import (
    MEASUREMENT_FILENAME,
    TIMESERIES_FILENAME,
    FileBinding,
    atomic_json,
    bind_file,
    portable_member,
    read_rmsd_evidence,
)
from mania.run_provenance import PortableArtifactReference, RunProvenance
from mania.run_provenance_io import read_run_provenance
from mania.software_identity import get_software_identity

HANDOFF_CONTRACT = "mania.production_handoff.v1"
# Actual compact files. Scientific authority that is genuinely unavailable is
# represented separately, never by omitting these technical prerequisites.
REQUIRED_INPUT_ROLES = (
    "preparation_report",
    "protein_integrity_observations",
    "frame_evidence",
    "source_binding",
    "source_time_authority",
    "source_attestation",
    "canonical_residue_mapping",
    "molecular_partner_metadata",
    "dataset_request",
)
REQUIRED_OUTPUT_ROLES = (
    "temporal_execution",
    "pbc_audit",
    "runtime_metadata",
    "perframe_completion",
    "contacts_perframe",
    "molecular_partner_catalog",
    "protein_lipid_perframe",
    "protein_glycan_perframe",
    "protein_edges_by_window_source",
    "protein_lipid_contacts_by_window_source",
    "protein_glycan_contacts_by_window_source",
    "protein_edges_by_window_canonical",
    "protein_lipid_contacts_by_window_canonical",
    "protein_glycan_contacts_by_window_canonical",
    "protein_rmsd_timeseries",
    "protein_rmsd_measurement",
)
CONDITIONAL_AUTHORITIES = (
    "biological_annotations",
    "partner_correspondence",
    "review_assessment",
    "group_qc_aggregation",
)


class EvidenceRequirement(StrictModel):
    role: str
    artifact_id: str
    requirement: Literal["required", "conditional"]
    state: Literal["present", "genuinely_unavailable", "not_applicable"]
    binding: FileBinding | None
    reason: str | None

    @model_validator(mode="after")
    def requirement_state(self) -> EvidenceRequirement:
        if self.requirement == "required" and self.state != "present":
            raise ValueError("Mandatory compact evidence cannot be absent")
        if self.state == "present":
            if (
                self.binding is None
                or self.binding.path is None
                or self.reason is not None
            ):
                raise ValueError(
                    "Present evidence needs a portable actual-file binding"
                )
            if self.binding.artifact_id != self.artifact_id:
                raise ValueError("Requirement/artifact identity mismatch")
        elif self.binding is not None or not self.reason or not self.reason.strip():
            raise ValueError("Unavailable authority requires an explicit reason")
        return self


class HandoffManifest(StrictModel):
    schema_version: Literal["mania.production_handoff.v0.1"]
    kind: Literal["mania_production_handoff"]
    contract_id: Literal["mania.production_handoff.v1"]
    producer_identity: dict[str, Any]
    replica_identity: DatasetTrajectoryIdentity
    preparation_identity: FileBinding
    required_evidence: list[EvidenceRequirement]
    large_artifact_identities: dict[str, FileBinding]
    input_resolver: dict[str, FileBinding]
    authority_states: dict[str, str]
    scientific_outputs: list[str]
    rmsd_bindings: dict[str, FileBinding]
    replay_requirements: list[str]
    technical_validation_binding: FileBinding

    @model_validator(mode="after")
    def complete_registry(self) -> HandoffManifest:
        ids = [e.artifact_id for e in self.required_evidence]
        paths = [e.binding.path for e in self.required_evidence if e.binding]
        if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
            raise ValueError("Duplicate handoff evidence IDs/paths")
        required = {
            e.role for e in self.required_evidence if e.requirement == "required"
        }
        if not set(
            (
                *REQUIRED_INPUT_ROLES,
                *REQUIRED_OUTPUT_ROLES,
                "preparation_evidence",
                "preprocessing_inventory",
                "preprocessing_provenance",
                "technical_validation",
                "science_completion",
            )
        ).issubset(required):
            raise ValueError("Missing mandatory compact handoff category")
        if set(self.large_artifact_identities) != {
            "topology",
            "raw_trajectory",
            "prepared_trajectory",
        } or any(b.path is not None for b in self.large_artifact_identities.values()):
            raise ValueError("Coordinates require documentary identities, not members")
        if set(self.authority_states) != set(CONDITIONAL_AUTHORITIES):
            raise ValueError("Handoff requires exact explicit authority states")
        if set(self.rmsd_bindings) != {"measurements", "metadata"}:
            raise ValueError("Handoff requires both RMSD authorities")
        by_role = {e.role: e for e in self.required_evidence}
        if self.preparation_identity != by_role["preparation_report"].binding or (
            self.technical_validation_binding != by_role["technical_validation"].binding
        ):
            raise ValueError("Handoff preparation/validation binding mismatch")
        for role in CONDITIONAL_AUTHORITIES:
            evidence = by_role.get(role)
            if evidence is None or self.authority_states[role] != evidence.state:
                raise ValueError(
                    "Authority availability differs from evidence registry"
                )
        return self


class HandoffCompletion(StrictModel):
    schema_version: Literal["mania.production_handoff_complete.v0.1"]
    kind: Literal["mania_production_handoff_complete"]
    contract_id: Literal["mania.production_handoff.v1"]
    replica_identity: DatasetTrajectoryIdentity
    production_eligible: bool
    handoff_state: Literal["complete"]
    required_evidence_count: int
    bindings: dict[str, FileBinding]

    @model_validator(mode="after")
    def seal_members(self) -> HandoffCompletion:
        if (
            set(self.bindings)
            != {
                "science_completion",
                "manifest",
                "inventory",
                "provenance",
                "validation",
            }
            or self.required_evidence_count < 1
        ):
            raise ValueError("Incomplete handoff completion seal")
        expected_paths = {
            "science_completion": self.bindings["science_completion"].path,
            "manifest": "handoff/manifest.json",
            "inventory": "handoff/artifact_inventory.json",
            "provenance": "handoff/run_provenance.json",
            "validation": "handoff/validation.json",
        }
        if any(
            binding.path != expected_paths[role]
            for role, binding in self.bindings.items()
        ):
            raise ValueError("Seal requires exact portable completion paths")
        marker = self.bindings["science_completion"].path
        if marker not in ("science_complete.json", "technical_complete.json") or (
            marker == "technical_complete.json" and self.production_eligible
        ):
            raise ValueError("Invalid production/technical completion identity")
        return self


class PreparationEvidence(StrictModel):
    schema_version: Literal["mania.preparation_evidence.v0.1"]
    kind: Literal["mania_preparation_evidence"]
    replica_identity: DatasetTrajectoryIdentity
    input_bindings: dict[str, FileBinding]
    large_artifact_identities: dict[str, FileBinding]
    production_eligible: bool
    authority_absences: dict[str, str]

    @model_validator(mode="after")
    def required_bindings(self) -> PreparationEvidence:
        if not set(REQUIRED_INPUT_ROLES).issubset(self.input_bindings) or (
            set(self.large_artifact_identities)
            != {"topology", "raw_trajectory", "prepared_trajectory"}
        ):
            raise ValueError("Incomplete normalized preparation evidence")
        return self


@dataclass(frozen=True)
class HandoffInputs:
    identity: DatasetTrajectoryIdentity
    compact_files: dict[str, Path]
    large_artifact_identities: dict[str, FileBinding]
    production_eligible: bool
    authority_absences: dict[str, str]


@dataclass(frozen=True)
class RetainedInputs:
    source: HandoffInputs
    bindings: dict[str, FileBinding]

    def rmsd_source_bindings(self) -> dict[str, FileBinding]:
        result = dict(self.source.large_artifact_identities)
        # RMSD paths are documentary IDs. The handoff resolver supplies actual members.
        for role, input_role in (
            ("mapping", "canonical_residue_mapping"),
            ("preparation_report", "preparation_report"),
        ):
            result[role] = self.bindings[input_role].model_copy(update={"path": None})
        return result


def _copy_immutable(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("Evidence source must be a physical regular file")
    if source.suffix.lower() in {".dcd", ".xtc", ".trr", ".tpr", ".psf"}:
        raise ValueError("Coordinate/topology files are documentary identities only")
    # Reports/logs/controls are retained exactly, including original absolute paths.
    # Those paths remain inert text; consumers use only the portable resolver.
    payload = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise ValueError("Existing retained evidence is immutable")
        return
    result = write_atomic_text(payload.decode("utf-8"), destination, overwrite=False)
    if not result.passed or destination.read_bytes() != payload:
        raise ValueError("Exact immutable compact evidence copy failed")


def retain_handoff_inputs(root: Path, inputs: HandoffInputs) -> RetainedInputs:
    if not set(REQUIRED_INPUT_ROLES).issubset(inputs.compact_files):
        raise ValueError("Missing mandatory compact preparation/control input")
    if not set(inputs.authority_absences).issubset(CONDITIONAL_AUTHORITIES):
        raise ValueError("Unknown authority absence role")
    retained = {}
    for role, source in sorted(inputs.compact_files.items()):
        if role not in (*REQUIRED_INPUT_ROLES, *CONDITIONAL_AUTHORITIES) and (
            not role.startswith("source_control_")
        ):
            raise ValueError("Unknown handoff input role")
        path = f"evidence/producer/{role}/{source.name}"
        target = portable_member(root, path)
        _copy_immutable(source, target)
        retained[role] = bind_file(target, f"evidence:{role}", path)
    evidence = PreparationEvidence.model_validate(
        {
            "schema_version": "mania.preparation_evidence.v0.1",
            "kind": "mania_preparation_evidence",
            "replica_identity": inputs.identity.to_dict(),
            "input_bindings": {
                k: b.model_dump(mode="json") for k, b in retained.items()
            },
            "large_artifact_identities": {
                k: b.model_dump(mode="json")
                for k, b in inputs.large_artifact_identities.items()
            },
            "production_eligible": inputs.production_eligible,
            "authority_absences": inputs.authority_absences,
        }
    )
    atomic_json(
        root / "evidence/preparation_evidence.json", evidence.model_dump(mode="json")
    )
    return RetainedInputs(inputs, retained)


def _require_binding(root: Path, binding: FileBinding) -> Path:
    target = portable_member(root, binding.path or "")
    if (
        not target.is_file()
        or bind_file(target, binding.artifact_id, binding.path) != binding
    ):
        raise ValueError(f"Missing/changed handoff evidence: {binding.artifact_id}")
    return target


def _coordinate_free_replay(root: Path, manifest: HandoffManifest) -> None:
    from tempfile import TemporaryDirectory

    from mania import canonical_window_tables_io as canonical_io
    from mania.preprocessing.protein_edge_window_table_io import (
        write_dataset_protein_edge_window_csv,
    )
    from mania.preprocessing.specialized_contact_window_tables_io import (
        write_protein_glycan_window_csv,
        write_protein_lipid_window_csv,
    )
    from mania.preprocessing.window_replay import replay_window_tables

    science = root / "preprocessing"
    entries = {e.role: e.binding for e in manifest.required_evidence if e.binding}
    mapping_binding = entries["canonical_residue_mapping"]
    assert mapping_binding is not None
    mapping = read_canonical_residue_mapping(_require_binding(root, mapping_binding))
    key = manifest.replica_identity.replica_key
    bindings = DatasetCanonicalResidueMappingBindings(
        (DatasetCanonicalResidueMappingBinding(*key, mapping),)
    )
    temporal = read_preprocessing_temporal_execution(
        science / "temporal_execution.json"
    )
    if len(temporal.bindings) != 1 or (
        temporal.bindings[0].dataset_spec.identity != manifest.replica_identity
    ):
        raise ValueError("Handoff temporal replica identity mismatch")
    replay = replay_window_tables(science, temporal, mapping_bindings=bindings)
    writers: Any = (
        (write_dataset_protein_edge_window_csv, replay.protein),
        (write_protein_lipid_window_csv, replay.lipid),
        (write_protein_glycan_window_csv, replay.glycan),
        (
            canonical_io.write_canonical_protein_edge_window_csv,
            replay.canonical_protein,
        ),
        (canonical_io.write_canonical_protein_lipid_window_csv, replay.canonical_lipid),
        (
            canonical_io.write_canonical_protein_glycan_window_csv,
            replay.canonical_glycan,
        ),
    )
    with TemporaryDirectory(prefix="mania-handoff-replay-") as temporary:
        for writer, table in writers:
            result = writer(table, Path(temporary))
            if (
                not result.passed
                or result.output_path.read_bytes()
                != (science / result.output_path.name).read_bytes()
            ):
                raise ValueError("Coordinate-free handoff window replay mismatch")


def validate_handoff(root: Path) -> HandoffManifest:
    """Validate all retained compact bytes and replay without opening coordinates."""
    manifest = HandoffManifest.model_validate(
        read_strict_json(root / "handoff/manifest.json")
    )
    return _validate_handoff_contents(root, manifest)


def _validate_handoff_contents(
    root: Path,
    manifest: HandoffManifest,
    completion_document: dict[str, Any] | None = None,
) -> HandoffManifest:
    for evidence in manifest.required_evidence:
        if evidence.binding is not None and not (
            evidence.role == "science_completion" and completion_document is not None
        ):
            _require_binding(root, evidence.binding)
    by_role = {e.role: e.binding for e in manifest.required_evidence if e.binding}
    science = root / "preprocessing"
    metadata, rows = read_rmsd_evidence(science)
    if metadata.dataset_identity != manifest.replica_identity:
        raise ValueError("Handoff/RMSD replica mismatch")
    for role, expected in manifest.large_artifact_identities.items():
        if metadata.source_bindings[role] != expected:
            raise ValueError("Handoff/RMSD coordinate lineage mismatch")
    for role, input_role in (
        ("mapping", "canonical_residue_mapping"),
        ("preparation_report", "preparation_report"),
    ):
        binding = by_role[input_role]
        assert binding is not None
        if metadata.source_bindings[role] != binding.model_copy(update={"path": None}):
            raise ValueError("Handoff/RMSD compact input lineage mismatch")
    expected_rmsd = {
        "measurements": bind_file(
            science / TIMESERIES_FILENAME,
            "output:protein_rmsd_timeseries",
            f"preprocessing/{TIMESERIES_FILENAME}",
        ),
        "metadata": bind_file(
            science / MEASUREMENT_FILENAME,
            "output:protein_rmsd_measurement",
            f"preprocessing/{MEASUREMENT_FILENAME}",
        ),
    }
    if manifest.rmsd_bindings != expected_rmsd:
        raise ValueError("Handoff/RMSD cross-file binding mismatch")

    def member(role: str) -> Path:
        binding = by_role[role]
        assert binding is not None
        return _require_binding(root, binding)

    integrity = read_protein_integrity(member("protein_integrity_observations"))
    from mania.preprocessing.trajectory_rmsd import validate_selection_mapping

    validate_selection_mapping(
        metadata.atom_selection,
        read_canonical_residue_mapping(member("canonical_residue_mapping")),
    )
    if integrity.dataset_identity != manifest.replica_identity or (
        integrity.source_bindings != manifest.large_artifact_identities
    ):
        raise ValueError("Protein integrity replica/coordinate lineage mismatch")
    validate_protein_integrity(
        integrity, member("preparation_report"), member("frame_evidence")
    )
    if any(
        f.bond_representation_max_error_A is None for f in integrity.observations
    ) and (integrity.protein_remains_broken is None):
        raise ValueError(
            "Handoff needs all-frame bonded observations or explicit assessment"
        )
    for row in rows:
        if row.state == "resolved":
            frame = integrity.observations[row.prepared_frame_index or 0]
            if (row.source_frame_index, row.actual_time_ps) != (
                frame.source_frame_index,
                frame.time_ps,
            ):
                raise ValueError("RMSD/preparation source frame/time mapping mismatch")
    read_molecular_partner_metadata(member("molecular_partner_metadata"))
    preparation_model = PreparationEvidence.model_validate(
        read_strict_json(member("preparation_evidence"))
    )
    preparation = preparation_model.model_dump(mode="json")
    if preparation["large_artifact_identities"] != {
        k: b.model_dump(mode="json")
        for k, b in manifest.large_artifact_identities.items()
    }:
        raise ValueError("Preparation/handoff coordinate lineage mismatch")
    if preparation["replica_identity"] != manifest.replica_identity.to_dict():
        raise ValueError("Preparation manifest identity mismatch")
    for role in REQUIRED_INPUT_ROLES:
        if (
            FileBinding.model_validate(preparation["input_bindings"][role])
            != by_role[role]
        ):
            raise ValueError("Preparation/handoff compact resolver mismatch")
    inventory = read_artifact_inventory(science / "artifact_inventory.json")
    provenance = read_run_provenance(science / "run_provenance.json")
    if provenance.status != "completed" or inventory.checksum_mode != "sha256":
        raise ValueError("Handoff requires completed hash-bound preprocessing")
    outputs = [e for e in inventory.artifacts if e.direction == "output"]
    if {e.path for e in outputs} != set(manifest.scientific_outputs):
        raise ValueError("Handoff must retain all inventoried scientific outputs")
    for entry in outputs:
        output_binding = by_role.get(entry.role)
        if output_binding is None or (entry.sha256, entry.byte_size, entry.path) != (
            output_binding.sha256,
            output_binding.byte_size,
            (output_binding.path or "").removeprefix("preprocessing/"),
        ):
            raise ValueError("Preprocessing inventory/handoff output mismatch")
    for entry in inventory.artifacts:
        if entry.direction == "input":
            bound = manifest.input_resolver.get(entry.artifact_id)
            if bound is None or (entry.sha256, entry.byte_size) != (
                bound.sha256,
                bound.byte_size,
            ):
                raise ValueError("Preprocessing input has no exact portable resolver")
    validation = read_strict_json(member("technical_validation"))
    if validation.get("replay") != "PASS" or (
        validation.get("validation", {}).get("status") != "passed"
        or validation.get("validation", {}).get("complete") is not True
    ):
        raise ValueError("Producer full-input validation/replay evidence is incomplete")
    marker = (
        completion_document
        if completion_document is not None
        else read_strict_json(member("science_completion"))
    )
    expected_science = {
        e.path: e.sha256 for e in inventory.artifacts if e.direction == "output"
    }
    if any(marker["artifacts"].get(k) != v for k, v in expected_science.items()):
        raise ValueError("Science completion differs from retained scientific bytes")
    from mania.validation import validate_run_artifacts

    compact_mappings = {
        k: _require_binding(root, b)
        for k, b in manifest.input_resolver.items()
        if b.path is not None
    }
    compact_validation = validate_run_artifacts(
        science,
        scope="preprocessing",
        input_artifact_paths=compact_mappings,
    )
    if not compact_validation.passed or compact_validation.unsupported_count:
        raise ValueError("Strict compact preprocessing validation failed")
    _coordinate_free_replay(root, manifest)
    return manifest


def _completion_marker(root: Path) -> Path:
    markers = [
        root / name
        for name in ("science_complete.json", "technical_complete.json")
        if (root / name).is_file()
    ]
    if len(markers) != 1:
        raise ValueError("Handoff requires one prior science or technical completion")
    return markers[0]


def validate_handoff_prerequisites(
    root: Path,
    retained: RetainedInputs,
    *,
    technical_validation: Path,
    completion_document: dict[str, Any],
    completion_path: str = "science_complete.json",
) -> None:
    """Verify compact evidence closure before publishing the existing marker."""
    if completion_path not in ("science_complete.json", "technical_complete.json"):
        raise ValueError("Invalid prior completion marker path")
    if completion_path == "technical_complete.json" and (
        retained.source.production_eligible
        or completion_document.get("production_eligible") is not False
    ):
        raise ValueError("Technical completion cannot become production eligible")
    # This binding exists only in the unpublished model; final publication hashes
    # the actual immutable marker. No placeholder bytes are written to disk.
    draft = _build_handoff_manifest(
        root,
        retained,
        technical_validation,
        FileBinding(
            artifact_id="evidence:science_completion",
            path=completion_path,
            byte_size=0,
            sha256="0" * 64,
            format="json",
        ),
    )
    _validate_handoff_contents(root, draft, completion_document)


def _build_handoff_manifest(
    root: Path,
    retained: RetainedInputs,
    technical_validation: Path,
    completion_binding: FileBinding,
) -> HandoffManifest:
    science = root / "preprocessing"
    inventory = read_artifact_inventory(science / "artifact_inventory.json")
    leaves = dict(retained.bindings)
    extras = {
        "preparation_evidence": root / "evidence/preparation_evidence.json",
        "preprocessing_inventory": science / "artifact_inventory.json",
        "preprocessing_provenance": science / "run_provenance.json",
        "technical_validation": technical_validation,
    }
    leaves["science_completion"] = completion_binding
    for role, path in extras.items():
        leaves[role] = bind_file(
            path, f"evidence:{role}", path.relative_to(root).as_posix()
        )
    for entry in inventory.artifacts:
        if entry.direction == "output":
            if entry.role in leaves:
                raise ValueError("Ambiguous handoff output role")
            leaves[entry.role] = bind_file(
                science / entry.path, entry.artifact_id, f"preprocessing/{entry.path}"
            )
    resolver = {}
    input_roles = {
        "input_manifest": root / "inputs/preprocessing.json",
        "canonical_residue_mapping": retained.source.compact_files[
            "canonical_residue_mapping"
        ],
        "molecular_partner_metadata": retained.source.compact_files[
            "molecular_partner_metadata"
        ],
    }
    for entry in inventory.artifacts:
        if entry.direction != "input":
            continue
        if entry.role == "condition_topology":
            resolver[entry.artifact_id] = retained.source.large_artifact_identities[
                "topology"
            ]
        elif entry.role == "condition_trajectory":
            resolver[entry.artifact_id] = retained.source.large_artifact_identities[
                "prepared_trajectory"
            ]
        elif entry.role in retained.bindings:
            resolver[entry.artifact_id] = retained.bindings[entry.role]
        elif entry.role == "input_manifest":
            leaves[entry.role] = bind_file(
                input_roles[entry.role], entry.artifact_id, "inputs/preprocessing.json"
            )
            resolver[entry.artifact_id] = leaves[entry.role]
        else:
            # Controls may share a retained file under a common evidence role.
            matches = [
                b
                for b in leaves.values()
                if (b.sha256, b.byte_size) == (entry.sha256, entry.byte_size)
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Missing/ambiguous compact input retention: {entry.role}"
                )
            resolver[entry.artifact_id] = matches[0]
    requirements = [
        EvidenceRequirement(
            role=role,
            artifact_id=b.artifact_id,
            requirement="required",
            state="present",
            binding=b,
            reason=None,
        )
        for role, b in sorted(leaves.items())
    ]
    states = {}
    for role in CONDITIONAL_AUTHORITIES:
        if role in retained.bindings:
            states[role] = "present"
        else:
            reason = retained.source.authority_absences.get(role)
            if not reason:
                raise ValueError(f"Missing explicit authority availability: {role}")
            states[role] = "genuinely_unavailable"
            requirements.append(
                EvidenceRequirement(
                    role=role,
                    artifact_id=f"authority:{role}",
                    requirement="conditional",
                    state="genuinely_unavailable",
                    binding=None,
                    reason=reason,
                )
            )
    manifest = HandoffManifest(
        schema_version="mania.production_handoff.v0.1",
        kind="mania_production_handoff",
        contract_id="mania.production_handoff.v1",
        producer_identity=get_software_identity().to_dict(),
        replica_identity=retained.source.identity,
        preparation_identity=leaves["preparation_report"],
        required_evidence=requirements,
        large_artifact_identities=retained.source.large_artifact_identities,
        input_resolver=resolver,
        authority_states=states,
        scientific_outputs=[
            e.path for e in inventory.artifacts if e.direction == "output"
        ],
        rmsd_bindings={
            "measurements": leaves["protein_rmsd_timeseries"],
            "metadata": leaves["protein_rmsd_measurement"],
        },
        replay_requirements=[
            "compact_perframe",
            "temporal_execution",
            "explicit_mapping",
        ],
        technical_validation_binding=leaves["technical_validation"],
    )
    return manifest


def publish_handoff(
    root: Path,
    retained: RetainedInputs,
    *,
    technical_validation: Path,
) -> HandoffCompletion:
    """Publish a new immutable handoff; never upgrades a completed legacy attempt."""
    if (root / "handoff").exists() or (root / "handoff_complete.json").exists():
        raise ValueError("Existing handoff namespace is immutable")
    marker = _completion_marker(root)
    manifest = _build_handoff_manifest(
        root,
        retained,
        technical_validation,
        bind_file(marker, "evidence:science_completion", marker.name),
    )
    leaves = {e.role: e.binding for e in manifest.required_evidence if e.binding}
    atomic_json(root / "handoff/manifest.json", manifest.model_dump(mode="json"))
    validate_handoff(root)
    atomic_json(
        root / "handoff/validation.json",
        {
            "schema_version": "mania.production_handoff_validation.v0.1",
            "status": "passed",
            "complete": True,
            "coordinate_access": False,
            "replay": "byte_identical",
            "validated_members": len(leaves),
        },
    )
    for role, portable_path in (
        ("handoff_manifest", "handoff/manifest.json"),
        ("handoff_validation", "handoff/validation.json"),
    ):
        leaves[role] = bind_file(root / portable_path, f"handoff:{role}", portable_path)
    handoff_inventory = ArtifactInventory(
        run_id=retained.source.identity.trajectory_id,
        workflow="production_handoff",
        inventory_path="handoff/artifact_inventory.json",
        checksum_mode="sha256",
        artifacts=tuple(
            ArtifactInventoryEntry(
                b.artifact_id,
                "output",
                role,
                b.path or "",
                b.format,
                b.byte_size,
                b.sha256,
            )
            for role, b in sorted(leaves.items())
        ),
    )
    atomic_json(root / "handoff/artifact_inventory.json", handoff_inventory.to_dict())
    now = datetime.now(UTC)  # Provenance-only clock, never scientific artifact bytes.
    provenance = RunProvenance(
        run_id=retained.source.identity.trajectory_id,
        workflow="production_handoff",
        status="completed",
        started_at_utc=now,
        ended_at_utc=now,
        software_identity=get_software_identity(),
        command=("mania", "production", "handoff"),
        resolved_configuration={
            "contract_id": HANDOFF_CONTRACT,
            "coordinate_access": False,
        },
        conditions=(manifest.replica_identity.condition,)
        if manifest.replica_identity.condition
        else (),
        artifact_references=tuple(
            PortableArtifactReference(role, b.path or "")
            for role, b in sorted(leaves.items())
        ),
    )
    atomic_json(root / "handoff/run_provenance.json", provenance.to_dict())
    return seal_handoff(root, production_eligible=retained.source.production_eligible)


def seal_handoff(root: Path, *, production_eligible: bool) -> HandoffCompletion:
    manifest = validate_handoff(root)
    seal = HandoffCompletion(
        schema_version="mania.production_handoff_complete.v0.1",
        kind="mania_production_handoff_complete",
        contract_id="mania.production_handoff.v1",
        replica_identity=manifest.replica_identity,
        production_eligible=production_eligible,
        handoff_state="complete",
        required_evidence_count=sum(
            e.requirement == "required" for e in manifest.required_evidence
        ),
        bindings={
            role: bind_file(root / path, f"seal:{role}", path)
            for role, path in (
                ("science_completion", _completion_marker(root).name),
                ("manifest", "handoff/manifest.json"),
                ("inventory", "handoff/artifact_inventory.json"),
                ("provenance", "handoff/run_provenance.json"),
                ("validation", "handoff/validation.json"),
            )
        },
    )
    _validate_seal_dependencies(root, seal)
    atomic_json(root / "handoff_complete.json", seal.model_dump(mode="json"))
    return seal


def _validate_seal_dependencies(root: Path, seal: HandoffCompletion) -> None:
    for binding in seal.bindings.values():
        _require_binding(root, binding)
    inventory = read_artifact_inventory(root / "handoff/artifact_inventory.json")
    if (
        inventory.workflow != "production_handoff"
        or inventory.checksum_mode != "sha256"
    ):
        raise ValueError("Invalid handoff inventory")
    for entry in inventory.artifacts:
        _require_binding(
            root,
            FileBinding(
                artifact_id=entry.artifact_id,
                path=entry.path,
                byte_size=entry.byte_size,
                sha256=entry.sha256 or "",
                format=entry.format,
            ),
        )
    provenance = read_run_provenance(root / "handoff/run_provenance.json")
    if provenance.status != "completed" or provenance.workflow != "production_handoff":
        raise ValueError("Handoff provenance incomplete")
    validation = read_strict_json(root / "handoff/validation.json")
    if validation != {
        "schema_version": "mania.production_handoff_validation.v0.1",
        "status": "passed",
        "complete": True,
        "coordinate_access": False,
        "replay": "byte_identical",
        "validated_members": len(inventory.artifacts) - 2,
    }:
        raise ValueError("Handoff validation report mismatch")
    manifest = HandoffManifest.model_validate(
        read_strict_json(root / "handoff/manifest.json")
    )
    preparation = read_strict_json(root / "evidence/preparation_evidence.json")
    science_marker = read_strict_json(
        _require_binding(root, seal.bindings["science_completion"])
    )
    if seal.production_eligible != preparation["production_eligible"] or (
        "production_eligible" in science_marker
        and seal.production_eligible != science_marker["production_eligible"]
    ):
        raise ValueError("Handoff seal cannot change production eligibility")
    required = {
        e.artifact_id: e.binding for e in manifest.required_evidence if e.binding
    }
    actual = {
        e.artifact_id: FileBinding(
            artifact_id=e.artifact_id,
            path=e.path,
            byte_size=e.byte_size,
            sha256=e.sha256 or "",
            format=e.format,
        )
        for e in inventory.artifacts
    }
    if any(actual.get(k) != v for k, v in required.items()) or set(actual) != {
        *required,
        "handoff:handoff_manifest",
        "handoff:handoff_validation",
    }:
        raise ValueError("Handoff inventory omits mandatory evidence")
    if (
        set((r.role, r.path) for r in provenance.artifact_references)
        != {(e.role, e.path) for e in inventory.artifacts}
        or seal.replica_identity != manifest.replica_identity
        or (
            seal.required_evidence_count
            != sum(e.requirement == "required" for e in manifest.required_evidence)
        )
    ):
        raise ValueError("Handoff seal/provenance identity mismatch")


def load_completed_handoff(root: Path) -> HandoffManifest:
    if not (root / "handoff_complete.json").is_file():
        raise ValueError("Legacy science completion is not handoff completion")
    seal = HandoffCompletion.model_validate(
        read_strict_json(root / "handoff_complete.json")
    )
    _validate_seal_dependencies(root, seal)
    return validate_handoff(root)


def read_handoff_inputs(path: Path) -> HandoffInputs:
    """Read an explicit future common producer control."""
    from mania.preprocessing.molecular_partner_metadata_io import exact_fields

    data = exact_fields(
        read_strict_json(path),
        {
            "schema_version",
            "identity",
            "compact_files",
            "large_artifact_identities",
            "production_eligible",
            "authority_absences",
        },
    )
    if data["schema_version"] != "mania.production_handoff_inputs.v0.1" or (
        type(data["production_eligible"]) is not bool
    ):
        raise ValueError("Invalid explicit new-contract producer inputs")
    return HandoffInputs(
        identity=DatasetTrajectoryIdentity.model_validate(data["identity"]),
        compact_files={k: path.parent / v for k, v in data["compact_files"].items()},
        large_artifact_identities={
            k: FileBinding.model_validate(v)
            for k, v in data["large_artifact_identities"].items()
        },
        production_eligible=data["production_eligible"],
        authority_absences=data["authority_absences"],
    )
