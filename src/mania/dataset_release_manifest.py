"""Stage 33 release controls and publication manifest; no scientific execution."""

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any

from mania.dataset_release_contract import (
    DATASET_RELEASE_CANONICAL_REFERENCE_ID,
    DATASET_RELEASE_CANONICAL_REFERENCE_SHA256,
    DATASET_RELEASE_VERSION,
    PRODUCTION_EXECUTION_DAG,
    PUBLICATION_ARTIFACT_REGISTRY,
)
from mania.dataset_release_csv import require_portable_publication_path
from mania.dataset_release_metadata import ReplicaKey, SystemKey
from mania.preprocessing.temporal_policy import (
    LEGACY_BOUNDARY_PROFILE,
    BoundaryProfile,
    require_boundary_profile,
)

DATASET_RELEASE_EXPORT_MANIFEST_SCHEMA_VERSION = (
    "mania.dataset_release_export_manifest.v0.1"
)
DATASET_RELEASE_EXPORT_MANIFEST_KIND = "mania_dataset_release_export_manifest"
DATASET_RELEASE_MANIFEST_SCHEMA_VERSION = "mania.dataset_release_manifest.v0.1"
DATASET_RELEASE_MANIFEST_KIND = "mania_dataset_release_manifest"
EXPORT_MANIFEST_FILENAME = "dataset_release_export_manifest.json"
RELEASE_MANIFEST_PATH = "release/dataset_manifest.json"
RELEASE_INVENTORY_PATH = "release/artifact_inventory.json"
RELEASE_PROVENANCE_PATH = "release/provenance.json"


def require_text(value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("Expected nonempty stripped text")


def require_path(value: str) -> None:
    require_portable_publication_path(value)
    if "$" in value or "%" in value:
        raise ValueError("Environment substitutions are forbidden in release paths")


def require_keys(values: tuple[Any, ...], size: int) -> None:
    if type(values) is not tuple:
        raise ValueError("Expected immutable publication selections")
    for key in values:
        if type(key) is not tuple or len(key) != size:
            raise ValueError("Expected exact full publication key")
        for value in key:
            require_text(value)
    if len(set(values)) != len(values):
        raise ValueError("Duplicate publication selection")


def require_models(values: tuple[Any, ...], model: type) -> None:
    if type(values) is not tuple or any(type(v) is not model for v in values):
        raise ValueError("Expected immutable exact release bindings")
    for value in values:
        replace(value)
    if len(set(values)) != len(values):
        raise ValueError("Duplicate release binding")


@dataclass(frozen=True)
class ReleaseInputBinding:
    artifact_id: str
    path: str

    def __post_init__(self) -> None:
        require_text(self.artifact_id)
        require_path(self.path)


@dataclass(frozen=True)
class ReleaseUpstreamRun:
    provenance_path: str
    inventory_path: str
    input_bindings: tuple[ReleaseInputBinding, ...]

    def __post_init__(self) -> None:
        require_path(self.provenance_path)
        require_path(self.inventory_path)
        require_models(self.input_bindings, ReleaseInputBinding)
        if len({b.artifact_id for b in self.input_bindings}) != len(
            self.input_bindings
        ):
            raise ValueError("Duplicate upstream input artifact ID")
        object.__setattr__(
            self,
            "input_bindings",
            tuple(sorted(self.input_bindings, key=lambda b: b.artifact_id)),
        )


@dataclass(frozen=True)
class ReleaseCanonicalBinding:
    family: str
    path: str
    replica_keys: tuple[ReplicaKey, ...]

    def __post_init__(self) -> None:
        if type(self.family) is not str or self.family not in (
            "protein",
            "lipid",
            "glycan",
        ):
            raise ValueError("Unknown canonical input family")
        require_path(self.path)
        require_keys(self.replica_keys, 4)
        if not self.replica_keys:
            raise ValueError("Canonical artifacts require explicit replica coverage")
        object.__setattr__(self, "replica_keys", tuple(sorted(self.replica_keys)))


@dataclass(frozen=True)
class ReleaseAnnotationBinding:
    dataset_id: str
    system_id: str
    path: str

    def __post_init__(self) -> None:
        require_text(self.dataset_id)
        require_text(self.system_id)
        require_path(self.path)


@dataclass(frozen=True)
class DatasetReleaseExportManifest:
    dataset_id: str
    stage32_run: ReleaseUpstreamRun
    stage31_run: ReleaseUpstreamRun
    decision_set_path: str
    qc_summary_path: str
    qc_derived_manifest_path: str
    aggregation_manifest_used_path: str
    protein_aggregate_path: str | None
    lipid_aggregate_path: str | None
    glycan_aggregate_path: str | None
    canonical_bindings: tuple[ReleaseCanonicalBinding, ...]
    temporal_evidence_paths: tuple[str, ...]
    annotation_bindings: tuple[ReleaseAnnotationBinding, ...]
    publication_inputs_path: str
    scientific_release_replica_keys: tuple[ReplicaKey, ...]
    annotation_publication_system_keys: tuple[SystemKey, ...]
    schema_version: str = field(
        init=False,
        default=DATASET_RELEASE_EXPORT_MANIFEST_SCHEMA_VERSION,
    )
    kind: str = field(init=False, default=DATASET_RELEASE_EXPORT_MANIFEST_KIND)

    def __post_init__(self) -> None:
        require_text(self.dataset_id)
        for item in fields(self):
            if not item.init and (
                type(getattr(self, item.name)) is not type(item.default)
                or getattr(self, item.name) != item.default
            ):
                raise ValueError("Incorrect fixed release control contract")
        for name in ("stage32_run", "stage31_run"):
            value = getattr(self, name)
            if type(value) is not ReleaseUpstreamRun:
                raise ValueError("Expected explicit upstream run evidence")
            replace(value)
        for item in fields(self):
            if item.name.endswith("_path"):
                value = getattr(self, item.name)
                if value is not None:
                    require_path(value)
                elif "aggregate" not in item.name:
                    raise ValueError("Required release authority path is missing")
        require_models(self.canonical_bindings, ReleaseCanonicalBinding)
        require_models(self.annotation_bindings, ReleaseAnnotationBinding)
        if type(self.temporal_evidence_paths) is not tuple:
            raise ValueError("Expected explicit temporal path tuple")
        for path in self.temporal_evidence_paths:
            require_path(path)
        if len(set(self.temporal_evidence_paths)) != len(self.temporal_evidence_paths):
            raise ValueError("Duplicate temporal path")
        require_keys(self.scientific_release_replica_keys, 4)
        require_keys(self.annotation_publication_system_keys, 2)
        if any(
            key[0] != self.dataset_id
            for key in (
                *self.scientific_release_replica_keys,
                *self.annotation_publication_system_keys,
                *(k for b in self.canonical_bindings for k in b.replica_keys),
            )
        ) or any(b.dataset_id != self.dataset_id for b in self.annotation_bindings):
            raise ValueError("Release bindings must belong to the declared Dataset")
        if len({b.path for b in self.canonical_bindings}) != len(
            self.canonical_bindings
        ):
            raise ValueError("Canonical paths must be unique")
        if len({(b.dataset_id, b.system_id) for b in self.annotation_bindings}) != len(
            self.annotation_bindings
        ):
            raise ValueError("Annotation system bindings must be unique")
        for name in (
            "scientific_release_replica_keys",
            "annotation_publication_system_keys",
            "temporal_evidence_paths",
        ):
            object.__setattr__(self, name, tuple(sorted(getattr(self, name))))
        object.__setattr__(
            self,
            "canonical_bindings",
            tuple(
                sorted(
                    self.canonical_bindings,
                    key=lambda b: (b.family, b.path),
                )
            ),
        )
        object.__setattr__(
            self,
            "annotation_bindings",
            tuple(
                sorted(
                    self.annotation_bindings,
                    key=lambda b: (b.dataset_id, b.system_id),
                )
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetReleaseManifest:
    dataset_id: str
    authoritative_stage32_decision_source: str
    authoritative_qc_derived_stage31_manifest_source: str
    authoritative_stage31_aggregation_source: str
    boundary_profile: BoundaryProfile = LEGACY_BOUNDARY_PROFILE
    schema_version: str = field(
        init=False, default=DATASET_RELEASE_MANIFEST_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=DATASET_RELEASE_MANIFEST_KIND)
    release_version: str = field(init=False, default=DATASET_RELEASE_VERSION)
    canonical_reference_id: str = field(
        init=False,
        default=DATASET_RELEASE_CANONICAL_REFERENCE_ID,
    )
    canonical_reference_sequence_sha256: str = field(
        init=False,
        default=DATASET_RELEASE_CANONICAL_REFERENCE_SHA256,
    )
    production_execution_dag: tuple[str, ...] = field(
        init=False,
        default=PRODUCTION_EXECUTION_DAG,
    )
    release_table_count: int = field(init=False, default=17)
    release_json_count: int = field(init=False, default=3)
    upstream_reference_base: str = field(
        init=False,
        default="export_control_manifest_parent",
    )
    export_control_manifest_source: str = field(
        init=False,
        default=f"inputs/{EXPORT_MANIFEST_FILENAME}",
    )

    def __post_init__(self) -> None:
        require_boundary_profile(self.boundary_profile)
        version = (
            DATASET_RELEASE_MANIFEST_SCHEMA_VERSION
            if self.boundary_profile == LEGACY_BOUNDARY_PROFILE
            else "mania.dataset_release_manifest.v0.2"
        )
        object.__setattr__(self, "schema_version", version)
        require_text(self.dataset_id)
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name.endswith("_source"):
                require_path(value)
            if not item.init and (
                type(value) is not type(item.default)
                or value != (version if item.name == "schema_version" else item.default)
            ):
                raise ValueError("Release manifest frozen contract mismatch")

    def to_dict(self) -> dict[str, object]:
        values = asdict(self)
        if self.boundary_profile == LEGACY_BOUNDARY_PROFILE:
            values.pop("boundary_profile")
        return {
            **values,
            "publication_artifacts": [
                a.to_dict() for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts
            ],
        }
