"""Stage 33.A logical publication contract, without data processing or I/O.

Descriptors validate schemas only. Stage 33.B/C own adapters; 33.D owns release
assembly, population/lineage enforcement and cross-table row validation.
"""

from dataclasses import dataclass
from typing import Literal

from mania.canonical_reference import (
    NAPI2B_CANONICAL_ISOFORM_ID,
    NAPI2B_CANONICAL_SEQUENCE_LENGTH,
    NAPI2B_CANONICAL_SEQUENCE_SHA256,
    NAPI2B_UNIPROT_SEQUENCE_VERSION,
)

DATASET_RELEASE_CONTRACT_SCHEMA_VERSION = "mania.dataset_release_contract.v0.1"
DATASET_RELEASE_VERSION = "1.0"
DATASET_RELEASE_CANONICAL_REFERENCE_ID = (
    f"uniprotkb:{NAPI2B_CANONICAL_ISOFORM_ID}:"
    f"sequence-v{NAPI2B_UNIPROT_SEQUENCE_VERSION}"
)
DATASET_RELEASE_CANONICAL_REFERENCE_SHA256 = NAPI2B_CANONICAL_SEQUENCE_SHA256
CANONICAL_NODE_COUNT = NAPI2B_CANONICAL_SEQUENCE_LENGTH
CANONICAL_RESIDUE_RANGE = (1, CANONICAL_NODE_COUNT)

PublicationArtifactClass = Literal["control", "audit", "publication"]
PublicationLogicalType = Literal["string", "integer", "number", "boolean"]
PublicationEncoding = Literal["csv", "json", "parquet"]
PUBLICATION_ARTIFACT_CLASSES = ("control", "audit", "publication")
PUBLICATION_LOGICAL_TYPES = ("string", "integer", "number", "boolean")

DEVELOPMENT_ORDER = ("27", "28", "29", "30", "31", "32", "33")
PRODUCTION_DAG_ID = "mania.dataset_production.v1.0"
PRODUCTION_EXECUTION_DAG = (
    "stage27_30_per_replica_science",
    "stage32_authoritative_qc_decisions",
    "stage32_qc_derived_stage31_manifest",
    "stage31_replica_aggregation",
    "stage33_publication",
)
AGGREGATE_PUBLICATION_REQUIRED_LINEAGE = (
    "authoritative_stage32_dataset_qc_decision_set",
    "accepted_qc_derived_stage31_aggregation_manifest",
    "stage31_aggregation_run_from_that_manifest",
)

# Immutable semantic requirements, also exposed by contract.to_dict(). These
# are declarations, not evaluators or mechanisms for overriding QC authority.
PUBLICATION_POPULATION_RULES = (
    "Historical/provenance population differs from scientific release population.",
    "All production candidate replicas remain in simulations, QC and provenance, "
    "including excluded replicas with their decision reasons and evidence linkage.",
    "included_in_replica_aggregation is true only for final QC-derived Stage 31 "
    "member state available; excluded and technically unavailable members are false.",
    "included_in_scientific_release is true only when release_decision is available "
    "and required per-replica scientific evidence exists for the publication layer.",
    "Science and metrics contain only eligible data; missing technical science "
    "does not become QC exclusion. Excluded replicas never enter the denominator.",
    "Simulations booleans summarize eligible contributions: true requires at least "
    "one eligible layer/window; per-layer eligibility remains authoritative for "
    "each scientific row. They never grant eligibility to another layer/window.",
    "A technically valid pre-QC Stage 31 aggregate is not publication-authoritative. "
    "Stage 33.D must verify all three aggregate lineage requirements.",
)
SERIALIZATION_RULES = (
    "The logical publication model is authoritative; serialization is not science.",
    "CSV is mandatory for every table; JSON is mandatory for hierarchical releases.",
    "Parquet is an optional adapter over the same validated logical table model. "
    "CSV works without a Parquet backend; an explicit unsupported Parquet request "
    "must fail with a clear deterministic optional-adapter error.",
    "CSV and optional Parquet must reconstruct equal logical models. A future "
    "narrow optional Arrow-capable dependency is preferred over a dataframe library "
    "for serialization; no such dependency is required or added in 33.A.",
    "Logical null is None; CSV uses a blank cell, JSON null, Parquet native null. "
    "Strings None, null, NA and N/A are never missing-value sentinels. Nullable "
    "text uses nonempty supplied strings so blank CSV cells remain unambiguous; "
    "typed contact parameters distinguish an empty string using parameter_kind.",
    "CSV booleans are lowercase true/false, never 0/1 or yes/no.",
    "No rounding or recalculation of occupancy, support_fraction, lifetime, distance, "
    "mean, median, standard deviation or coverage; numbers round-trip losslessly.",
    "Adapters cannot recanonicalize source IDs, reevaluate QC, override decisions "
    "or change scientific inclusion/exclusion. Nonfinite numbers are forbidden.",
)
SCIENTIFIC_PUBLICATION_RULES = (
    "Canonical names match the pinned Stage 30 reference at positions 1..690. "
    "T330M publishes canonical 330 THR; source MET need not equal canonical THR.",
    "Annotation absence means false only under complete_for_system authority; "
    "supplied glycosylation and variant source/verifier evidence is preserved.",
    "Protein edges remain sparse. Stage 33 creates no all-pairs zero edges; "
    "available sparse absence and zero materialization remain Stage 31 science.",
    "Specialized partner IDs are topology-local per replica. Positive-frame-only "
    "distance means/minima and accepted episodes/lifetimes are copied unchanged.",
    "Glycan carrier-first-sugar covalent observations excluded by Stage 29/30 "
    "remain audit evidence and never reenter ordinary contact summaries.",
    "partner_correspondence_id is an aggregation correspondence identifier, not "
    "canonical lipid/glycan, chemical registry or cross-system molecule identity.",
    "Specialized aggregates contain only six occupancy/support statistics: no "
    "distance, lifetime, contact-frame totals or edge_weight.",
    "Metrics use explicit accepted names without a closed vocabulary or "
    "recomputation; excluded-replica review metrics remain QC/audit evidence.",
    "Requested production/window definitions differ from effective observations; "
    "window_id alone is never physical identity. Missing samples are not negatives.",
)


CONTACT_DEFINITION_REQUIRED_PARAMETERS = (
    "atom_selections",
    "distance_definition",
    "cutoff",
    "type_specific_parameters",
    "pbc_correction_status",
    "occupancy_denominator_semantics",
    "episode_continuity_semantics",
    "gap_tolerance",
    "lifetime_semantics",
    "specialized_distance_semantics",
)


def _text(value: object, field: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{field} must be a nonempty stripped string")


def _names(value: tuple[str, ...], field: str, *, allow_empty: bool = False) -> None:
    if type(value) is not tuple or (not value and not allow_empty):
        raise ValueError(f"{field} must be an immutable tuple")
    for name in value:
        _text(name, field)
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must not contain duplicates")


def _path(value: str) -> None:
    _text(value, "relative_path")
    if any(
        part in ("", ".", "..") or part.startswith("~") for part in value.split("/")
    ) or any(char in value for char in "\\:\x00\r\n\t"):
        raise ValueError("Paths must be portable forward-slash relative paths")


@dataclass(frozen=True)
class PublicationColumnSpec:
    name: str
    logical_type: PublicationLogicalType
    nullable: bool
    description: str

    def __post_init__(self) -> None:
        _text(self.name, "name")
        _text(self.description, "description")
        if self.logical_type not in PUBLICATION_LOGICAL_TYPES:
            raise ValueError("Invalid logical type")
        if type(self.nullable) is not bool:
            raise ValueError("nullable must be boolean")

    def to_dict(self) -> dict[str, object]:
        return dict(
            name=self.name,
            logical_type=self.logical_type,
            nullable=self.nullable,
            description=self.description,
        )


@dataclass(frozen=True)
class PublicationForeignKeySpec:
    local_columns: tuple[str, ...]
    target_table: str
    target_columns: tuple[str, ...]

    def __post_init__(self) -> None:
        _names(self.local_columns, "local_columns")
        _text(self.target_table, "target_table")
        _names(self.target_columns, "target_columns")
        if len(self.local_columns) != len(self.target_columns):
            raise ValueError("Foreign-key arity must match")

    def to_dict(self) -> dict[str, object]:
        return dict(
            local_columns=list(self.local_columns),
            target_table=self.target_table,
            target_columns=list(self.target_columns),
        )


@dataclass(frozen=True)
class PublicationTableSpec:
    table_id: str
    relative_path: str
    artifact_class: PublicationArtifactClass
    columns: tuple[PublicationColumnSpec, ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[PublicationForeignKeySpec, ...]
    required: bool

    def __post_init__(self) -> None:
        _text(self.table_id, "table_id")
        _path(self.relative_path)
        if self.artifact_class not in PUBLICATION_ARTIFACT_CLASSES:
            raise ValueError("Invalid artifact class")
        if type(self.required) is not bool:
            raise ValueError("required must be boolean")
        if (
            type(self.columns) is not tuple
            or not self.columns
            or any(type(column) is not PublicationColumnSpec for column in self.columns)
        ):
            raise ValueError("columns must be a nonempty tuple of column specs")
        names = tuple(column.name for column in self.columns)
        _names(names, "columns")
        _names(self.primary_key, "primary_key")
        if not set(self.primary_key) <= set(names):
            raise ValueError("Primary-key column absent from schema")
        if any(c.nullable for c in self.columns if c.name in self.primary_key):
            raise ValueError("Primary-key columns cannot be nullable")
        if type(self.foreign_keys) is not tuple or any(
            type(fk) is not PublicationForeignKeySpec for fk in self.foreign_keys
        ):
            raise ValueError("foreign_keys must be a tuple of foreign-key specs")
        if len(set(self.foreign_keys)) != len(self.foreign_keys):
            raise ValueError("Duplicate foreign keys")
        if any(not set(fk.local_columns) <= set(names) for fk in self.foreign_keys):
            raise ValueError("Foreign-key local column absent from schema")

    def to_dict(self) -> dict[str, object]:
        return dict(
            table_id=self.table_id,
            relative_path=self.relative_path,
            artifact_class=self.artifact_class,
            columns=[c.to_dict() for c in self.columns],
            primary_key=list(self.primary_key),
            foreign_keys=[fk.to_dict() for fk in self.foreign_keys],
            required=self.required,
        )


@dataclass(frozen=True)
class PublicationJSONSpec:
    """Required logical roles/fields, not the final hierarchical wire schema."""

    required_fields: tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        _names(self.required_fields, "required_fields")
        _text(self.description, "description")

    def to_dict(self) -> dict[str, object]:
        return dict(
            required_fields=list(self.required_fields), description=self.description
        )


@dataclass(frozen=True)
class PublicationArtifactSpec:
    artifact_id: str
    relative_path: str
    artifact_class: PublicationArtifactClass
    logical_schema: PublicationTableSpec | PublicationJSONSpec
    mandatory_encoding: PublicationEncoding
    optional_encodings: tuple[PublicationEncoding, ...] = ()
    required_lineage: tuple[str, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id")
        _path(self.relative_path)
        if self.artifact_class not in PUBLICATION_ARTIFACT_CLASSES:
            raise ValueError("Invalid artifact class")
        if type(self.required) is not bool:
            raise ValueError("required must be boolean")
        _names(self.required_lineage, "required_lineage", allow_empty=True)
        _names(self.optional_encodings, "optional_encodings", allow_empty=True)
        schema = self.logical_schema
        if type(schema) is PublicationTableSpec:
            if (
                self.artifact_id,
                self.relative_path,
                self.artifact_class,
                self.required,
            ) != (
                schema.table_id,
                schema.relative_path,
                schema.artifact_class,
                schema.required,
            ):
                raise ValueError("Artifact and table identity must agree")
            if self.mandatory_encoding != "csv" or self.optional_encodings not in (
                (),
                ("parquet",),
            ):
                raise ValueError("Tables require CSV with optional Parquet only")
        elif type(schema) is PublicationJSONSpec:
            if self.mandatory_encoding != "json" or self.optional_encodings:
                raise ValueError("Hierarchical release artifacts require JSON")
        else:
            raise ValueError("Invalid logical schema")
        if not self.relative_path.endswith(f".{self.mandatory_encoding}"):
            raise ValueError("Path suffix must match mandatory encoding")

    def to_dict(self) -> dict[str, object]:
        return dict(
            artifact_id=self.artifact_id,
            relative_path=self.relative_path,
            artifact_class=self.artifact_class,
            logical_schema=self.logical_schema.to_dict(),
            mandatory_encoding=self.mandatory_encoding,
            optional_encodings=list(self.optional_encodings),
            required_lineage=list(self.required_lineage),
            required=self.required,
        )


@dataclass(frozen=True)
class PublicationArtifactRegistry:
    artifacts: tuple[PublicationArtifactSpec, ...]

    def __post_init__(self) -> None:
        if (
            type(self.artifacts) is not tuple
            or not self.artifacts
            or any(type(a) is not PublicationArtifactSpec for a in self.artifacts)
        ):
            raise ValueError("artifacts must be a nonempty tuple of artifact specs")
        _names(tuple(a.artifact_id for a in self.artifacts), "artifact IDs/table IDs")
        _names(tuple(a.relative_path for a in self.artifacts), "relative paths")
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(self.artifacts, key=lambda artifact: artifact.relative_path)),
        )
        tables = {
            a.artifact_id: a.logical_schema
            for a in self.artifacts
            if isinstance(a.logical_schema, PublicationTableSpec)
        }
        for table in tables.values():
            local = {c.name: c for c in table.columns}
            for fk in table.foreign_keys:
                target = tables.get(fk.target_table)
                if target is None or fk.target_columns != target.primary_key:
                    raise ValueError(
                        "Foreign key must reference an existing primary key"
                    )
                remote = {c.name: c for c in target.columns}
                if any(
                    local[a].logical_type != remote[b].logical_type
                    for a, b in zip(fk.local_columns, fk.target_columns, strict=True)
                ):
                    raise ValueError("Foreign-key logical types must match")

    @property
    def tables(self) -> tuple[PublicationTableSpec, ...]:
        return tuple(
            a.logical_schema
            for a in self.artifacts
            if isinstance(a.logical_schema, PublicationTableSpec)
        )

    def to_dict(self) -> dict[str, object]:
        return {"artifacts": [a.to_dict() for a in self.artifacts]}


def _column(
    name: str,
    kind: PublicationLogicalType = "string",
    *,
    nullable: bool = False,
    description: str,
) -> PublicationColumnSpec:
    return PublicationColumnSpec(name, kind, nullable, description)


def _strings(
    names: tuple[str, ...], description: str, *, nullable: bool = False
) -> tuple[PublicationColumnSpec, ...]:
    return tuple(_column(n, nullable=nullable, description=description) for n in names)


def _numbers(
    names: tuple[str, ...],
    *,
    kind: PublicationLogicalType = "number",
    nullable: bool = False,
    description: str,
) -> tuple[PublicationColumnSpec, ...]:
    return tuple(
        _column(n, kind, nullable=nullable, description=description) for n in names
    )


SYSTEM_KEY = ("dataset_id", "system_id")
REPLICA_KEY = (*SYSTEM_KEY, "trajectory_id", "replica_id")
WINDOW_KEY = (*REPLICA_KEY, "window_id", "window_index")
NODE_KEY = ("canonical_reference_id", "canonical_residue_number")
_SYSTEM = _strings(SYSTEM_KEY, "Authoritative Dataset system identity.")
_REPLICA = _strings(REPLICA_KEY, "Full production candidate replica identity.")
_IDENTITY_LABELS = (
    *_strings(("engine", "variant_id"), "Accepted system metadata; never inferred."),
    *_strings(
        ("condition", "disulfide_state"),
        "Accepted nullable system metadata.",
        nullable=True,
    ),
)
_REFERENCE = _column(
    "canonical_reference_id", description="Pinned Stage 30 reference ID."
)
_REFERENCE_HASH = _column(
    "canonical_reference_sequence_sha256",
    description="Pinned Stage 30 sequence SHA256.",
)
_WINDOW_LABELS = (
    _column("window_id", description="Window label; not physical identity alone."),
    _column("window_index", "integer", description="Accepted window schedule index."),
)
_REQUESTED_BOUNDS = _numbers(
    ("requested_window_start_ns", "requested_window_end_ns"),
    description="Requested physical window boundary in ns, not observed coverage.",
)
_ENDPOINT = _column(
    "right_endpoint_inclusive",
    "boolean",
    description="Accepted requested right-boundary inclusion rule.",
)
_PRODUCTION = _numbers(
    ("requested_production_start_ns", "requested_production_end_ns"),
    description="Requested production interval boundary in ns.",
)
_SCHEDULE = _numbers(
    ("window_length_ns", "window_step_ns", "overlap_percent"),
    description="Unmodified requested physical window schedule.",
)
_WINDOW_DEFINITION = (
    *_WINDOW_LABELS,
    *_PRODUCTION,
    *_REQUESTED_BOUNDS,
    _ENDPOINT,
    *_SCHEDULE,
)
_SCIENCE_WINDOW = (
    *_WINDOW_LABELS,
    *_REQUESTED_BOUNDS,
    _ENDPOINT,
    *_numbers(
        ("effective_window_start_ns", "effective_window_end_ns"),
        description="Accepted actual observed window endpoints in ns.",
    ),
    *_numbers(
        ("requested_sample_count", "resolved_frame_count", "missing_sample_count"),
        kind="integer",
        description="Accepted sampling counts; denominator is resolved.",
    ),
    _column(
        "coverage_fraction",
        "number",
        description="Accepted observed sampling coverage.",
    ),
)
_PER_REPLICA = (*_REPLICA, *_IDENTITY_LABELS, *_SCIENCE_WINDOW, _REFERENCE)
_QC_DECISION = (
    *_strings(
        ("qc_status", "release_decision", "decision_mode"),
        "Authoritative Stage 32 decision; copied without reevaluation.",
    ),
    *_strings(
        ("decision_reason_code", "human_readable_reason"),
        "Authoritative decision reason; absent for PASS.",
        nullable=True,
    ),
)
_CANONICAL_RESIDUE = (
    _column(
        "canonical_residue_number", "integer", description="Stage 30 position 1..690."
    ),
    _column(
        "canonical_resname", description="Pinned canonical name, including THR at 330."
    ),
)
_EDGE = (
    _column(
        "source_canonical_residue_number",
        "integer",
        description="Canonical graph source endpoint; never source topology identity.",
    ),
    _column(
        "source_canonical_resname", description="Pinned source endpoint residue name."
    ),
    _column(
        "target_canonical_residue_number",
        "integer",
        description="Canonical graph target endpoint; never source topology identity.",
    ),
    _column(
        "target_canonical_resname", description="Pinned target endpoint residue name."
    ),
    _column("edge_type", description="Accepted protein interaction type."),
)
_EPISODES = (
    _column(
        "n_contact_frames",
        "integer",
        description="Accepted positive resolved-frame count.",
    ),
    _column(
        "occupancy",
        "number",
        description="Accepted n_contact_frames / resolved_frame_count.",
    ),
    _column(
        "n_contact_episodes",
        "integer",
        description="Accepted continuous episode count.",
    ),
    *_numbers(
        ("mean_episode_length_ns", "max_episode_length_ns"),
        description="Accepted episode durations from actual positive endpoint times.",
    ),
)
_DISTANCES = _numbers(
    ("distance_mean_A", "distance_min_A"),
    description="Accepted distance over contact-positive frames only, in Å.",
)
_STATISTICS = (
    _column(
        "mean_occupancy", "number", description="Accepted Stage 31 occupancy mean."
    ),
    _column(
        "std_occupancy",
        "number",
        nullable=True,
        description="Accepted sample SD; null for fewer than two available replicas.",
    ),
    _column(
        "median_occupancy", "number", description="Accepted Stage 31 occupancy median."
    ),
    *_numbers(
        ("n_replicates_available", "n_replicates_supporting"),
        kind="integer",
        description="Accepted available denominator / positive support counts.",
    ),
    _column(
        "support_fraction",
        "number",
        description="Accepted supporting / available fraction.",
    ),
)


def _fk(
    target: str, columns: tuple[str, ...], target_columns: tuple[str, ...] | None = None
) -> PublicationForeignKeySpec:
    return PublicationForeignKeySpec(columns, target, target_columns or columns)


_SYSTEM_FK = _fk("systems", SYSTEM_KEY)
_REPLICA_FK = _fk("simulations", REPLICA_KEY)
_WINDOW_FK = _fk("time_windows", WINDOW_KEY)
_NODE_FK = _fk("nodes", NODE_KEY)
_EDGE_FKS = tuple(
    _fk(
        "nodes",
        ("canonical_reference_id", f"{side}_canonical_residue_number"),
        NODE_KEY,
    )
    for side in ("source", "target")
)


def _table(
    table_id: str,
    folder: str,
    columns: tuple[PublicationColumnSpec, ...],
    key: tuple[str, ...],
    fks: tuple[PublicationForeignKeySpec, ...] = (),
    *,
    aggregate: bool = False,
) -> PublicationArtifactSpec:
    path = f"{folder}/{table_id}.csv"
    table = PublicationTableSpec(table_id, path, "publication", columns, key, fks, True)
    return PublicationArtifactSpec(
        table_id,
        path,
        "publication",
        table,
        "csv",
        ("parquet",),
        AGGREGATE_PUBLICATION_REQUIRED_LINEAGE if aggregate else (),
    )


def _specialized(kind: Literal["lipid", "glycan"]) -> PublicationArtifactSpec:
    partner = f"{kind}_partner_id"
    return _table(
        f"protein_{kind}_contacts_by_window",
        "science",
        (
            *_PER_REPLICA,
            *_CANONICAL_RESIDUE,
            _column(
                partner,
                description="Topology-local partner ID scoped to full replica key.",
            ),
            _column(f"{kind}_partner_name", description="Supplied local partner name."),
            *_EPISODES,
            *_DISTANCES,
        ),
        (*WINDOW_KEY, "canonical_reference_id", "canonical_residue_number", partner),
        (_REPLICA_FK, _WINDOW_FK, _NODE_FK),
    )


def _aggregate(kind: Literal["protein", "lipid", "glycan"]) -> PublicationArtifactSpec:
    entity: tuple[PublicationColumnSpec, ...]
    entity_key: tuple[str, ...]
    if kind == "protein":
        name = "protein_edges_by_window_replica_aggregation"
        entity = _EDGE
        entity_key = (
            "source_canonical_residue_number",
            "target_canonical_residue_number",
            "edge_type",
        )
        fks = _EDGE_FKS
    else:
        name = f"protein_{kind}_contacts_by_window_replica_aggregation"
        entity = (
            *_CANONICAL_RESIDUE,
            _column(
                "partner_correspondence_id",
                description=(
                    "Aggregation correspondence only; "
                    "not canonical/chemical/cross-system ID."
                ),
            ),
            _column(
                "partner_name", description="Accepted correspondence partner name."
            ),
        )
        entity_key = ("canonical_residue_number", "partner_correspondence_id")
        fks = (_NODE_FK,)
    return _table(
        name,
        "aggregates",
        (
            *_SYSTEM,
            *_IDENTITY_LABELS,
            *_WINDOW_DEFINITION,
            _REFERENCE,
            *entity,
            *_STATISTICS,
        ),
        (
            *SYSTEM_KEY,
            "engine",
            *(c.name for c in _WINDOW_DEFINITION),
            "canonical_reference_id",
            *entity_key,
        ),
        (_SYSTEM_FK, *fks),
        aggregate=True,
    )


_TABLE_ARTIFACTS = (
    _table("systems", "metadata", (*_SYSTEM, *_IDENTITY_LABELS), SYSTEM_KEY),
    _table(
        "simulations",
        "metadata",
        (
            *_REPLICA,
            *_IDENTITY_LABELS,
            *_QC_DECISION,
            _column(
                "aggregation_availability_status",
                nullable=True,
                description=(
                    "Final QC-derived Stage 31 availability; "
                    "null when no final member state exists."
                ),
            ),
            _column(
                "aggregation_availability_reason",
                nullable=True,
                description="Accepted technical/QC availability reason.",
            ),
            _column(
                "included_in_scientific_release",
                "boolean",
                description=(
                    "Available release decision and required science "
                    "exists for the included layer."
                ),
            ),
            _column(
                "included_in_replica_aggregation",
                "boolean",
                description=(
                    "True only for contributions with final "
                    "QC-derived member state available."
                ),
            ),
        ),
        REPLICA_KEY,
        (_SYSTEM_FK, _fk("quality_control", REPLICA_KEY)),
    ),
    _table(
        "time_windows",
        "metadata",
        (
            *_REPLICA,
            *_WINDOW_DEFINITION,
            _column(
                "frame_stride_ps",
                "number",
                description="Accepted requested sampling stride.",
            ),
            *_numbers(
                (
                    "expected_sample_count",
                    "resolved_sample_count",
                    "missing_sample_count",
                ),
                kind="integer",
                description="Requested/resolved/missing sample evidence.",
            ),
            _column(
                "coverage_fraction",
                "number",
                description="Accepted sampling coverage fraction.",
            ),
            *_numbers(
                ("effective_start_ns", "effective_end_ns"),
                nullable=True,
                description="Observed endpoints only where accepted evidence exists.",
            ),
        ),
        WINDOW_KEY,
        (_REPLICA_FK,),
    ),
    _table(
        "contact_definitions",
        "metadata",
        (
            *_REPLICA,
            _column(
                "contact_definition_id", description="Definition ID scoped to replica."
            ),
            _column(
                "contact_layer",
                description="protein-protein, protein-lipid or protein-glycan.",
            ),
            _column(
                "interaction_type", description="Accepted interaction/contact type."
            ),
            _column(
                "parameter_path",
                description=(
                    "Escaped slash-separated parameter path; $ is root, "
                    "array positions are zero-based."
                ),
            ),
            _column(
                "parameter_kind",
                description=(
                    "string/integer/number/boolean/null/object/array; "
                    "preserves empty containers."
                ),
            ),
            _column(
                "string_value",
                nullable=True,
                description="Exact string scalar, when applicable.",
            ),
            _column(
                "integer_value",
                "integer",
                nullable=True,
                description="Exact integer scalar.",
            ),
            _column(
                "number_value",
                "number",
                nullable=True,
                description="Unrounded numeric scalar.",
            ),
            _column(
                "boolean_value", "boolean", nullable=True, description="Boolean scalar."
            ),
            _column(
                "unit",
                nullable=True,
                description="Authoritative parameter unit where applicable.",
            ),
            _column(
                "source_artifact_role",
                description="Authoritative definition/configuration role.",
            ),
            _column(
                "source_artifact_path",
                description="Portable source evidence reference.",
            ),
        ),
        (*REPLICA_KEY, "contact_definition_id", "parameter_path"),
        (_REPLICA_FK,),
    ),
    _table(
        "software_versions",
        "metadata",
        (
            _column("dataset_id", description="Dataset identity."),
            *_strings(
                ("component_role", "component_name"),
                "MANIA/WANIA package, Python/runtime package or MD engine component.",
            ),
            _column(
                "version",
                nullable=True,
                description="Authoritative version; unknown stays null.",
            ),
            _column(
                "run_id",
                nullable=True,
                description="Authoritative source run identity if present.",
            ),
            _column(
                "source_artifact_role",
                description="Software/runtime/engine evidence role.",
            ),
            _column(
                "source_artifact_path",
                description="Portable source evidence reference.",
            ),
        ),
        ("dataset_id", "source_artifact_path", "component_role", "component_name"),
    ),
    _table(
        "quality_control",
        "metadata",
        (
            *_REPLICA,
            _column("hard_qc_status", description="Accepted Stage 32 hard-QC status."),
            _column(
                "review_qc_status",
                nullable=True,
                description="Null for hard-failed replicas.",
            ),
            *_QC_DECISION,
            *_strings(
                ("reviewer", "decision_note"),
                "Manual decision provenance; automatic is null.",
                nullable=True,
            ),
            *_numbers(
                ("hard_fail_count", "review_finding_count", "total_check_count"),
                kind="integer",
                description="Accepted decision summary counts.",
            ),
        ),
        REPLICA_KEY,
        (_REPLICA_FK,),
    ),
    _table(
        "quality_control_findings",
        "metadata",
        (
            *_REPLICA,
            _column("check_id", description="Accepted check identity, including PASS."),
            _column("status", description="Accepted finding status."),
            *_strings(
                ("reason_code", "human_readable_reason"),
                "Accepted finding explanation, null where accepted for PASS.",
                nullable=True,
            ),
        ),
        (*REPLICA_KEY, "check_id"),
        (_fk("quality_control", REPLICA_KEY),),
    ),
    _table(
        "quality_control_evidence",
        "metadata",
        (
            *_REPLICA,
            *_strings(
                ("check_id", "evidence_id", "evidence_type"),
                "Structured evidence identity and accepted type.",
            ),
            *_strings(
                (
                    "artifact_role",
                    "artifact_path",
                    "window_id",
                    "metric_name",
                    "observed_value",
                    "expected_or_threshold",
                    "details",
                ),
                "Accepted nullable evidence text; "
                "artifact_path is portable, never absolute.",
                nullable=True,
            ),
            _column(
                "used_for_decision",
                "boolean",
                description=(
                    "Membership in accepted decision_evidence_ids; no reevaluation."
                ),
            ),
        ),
        (*REPLICA_KEY, "check_id", "evidence_id"),
        (_fk("quality_control_findings", (*REPLICA_KEY, "check_id")),),
    ),
    _table(
        "nodes",
        "canonical",
        (_REFERENCE, _REFERENCE_HASH, *_CANONICAL_RESIDUE),
        NODE_KEY,
    ),
    _table(
        "residue_annotations",
        "canonical",
        (
            *_SYSTEM,
            _REFERENCE,
            *_CANONICAL_RESIDUE,
            _column("annotation_scope", description="Must be complete_for_system."),
            *(
                _column(
                    n,
                    "boolean",
                    description="Accepted reference-derived region membership.",
                )
                for n in ("is_ecd", "is_mx35_region")
            ),
            _column(
                "is_glycosylation_site",
                "boolean",
                description="Supplied complete-system flag.",
            ),
            _column(
                "glycosylation_present_in_topology",
                "boolean",
                nullable=True,
                description="Supplied topology presence; null outside a site.",
            ),
            *_strings(
                ("glycan_name", "glycosylation_source", "glycosylation_verifier"),
                "Supplied glycosylation annotation evidence.",
                nullable=True,
            ),
            *(
                _column(
                    n, "boolean", description="Supplied complete-system variant flag."
                )
                for n in ("is_disulfide_variant_site", "is_cysteine_variant_site")
            ),
            *_strings(
                (
                    "disulfide_variant_source",
                    "disulfide_variant_verifier",
                    "cysteine_variant_source",
                    "cysteine_variant_verifier",
                ),
                "Authoritative Stage 30 variant site source/verifier; "
                "null outside site.",
                nullable=True,
            ),
        ),
        (*SYSTEM_KEY, "canonical_residue_number"),
        (_SYSTEM_FK, _NODE_FK),
    ),
    _table(
        "protein_edges_by_window",
        "science",
        (
            *_PER_REPLICA,
            *_EDGE,
            *_EPISODES,
            _column(
                "edge_weight",
                "number",
                description="Accepted protein edge weight equals occupancy.",
            ),
        ),
        (
            *WINDOW_KEY,
            "canonical_reference_id",
            "source_canonical_residue_number",
            "target_canonical_residue_number",
            "edge_type",
        ),
        (_REPLICA_FK, _WINDOW_FK, *_EDGE_FKS),
    ),
    _specialized("lipid"),
    _specialized("glycan"),
    _aggregate("protein"),
    _aggregate("lipid"),
    _aggregate("glycan"),
    _table(
        "metrics",
        "metrics",
        (
            *_REPLICA,
            _column(
                "metric_id",
                description=(
                    "Deterministic source-record/metric identity "
                    "scoped to replica; no UUID or clock."
                ),
            ),
            _column(
                "window_id", nullable=True, description="Null for a non-window metric."
            ),
            _column(
                "window_index",
                "integer",
                nullable=True,
                description="Null together with window_id for a non-window metric.",
            ),
            _column(
                "metric_name",
                description="Explicit authoritative name; no closed vocabulary.",
            ),
            _column(
                "metric_value",
                "number",
                nullable=True,
                description=(
                    "Accepted value without recomputation; "
                    "null only if accepted upstream."
                ),
            ),
            _column(
                "unit", nullable=True, description="Supplied authoritative metric unit."
            ),
            _column(
                "source_artifact_role",
                description="Authoritative scientific metric source role.",
            ),
            _column(
                "source_artifact_path",
                description="Portable scientific source reference.",
            ),
            _column(
                "source_record_key",
                description="Deterministic row/record locator in the accepted source.",
            ),
        ),
        (*REPLICA_KEY, "metric_id"),
        (_REPLICA_FK, _WINDOW_FK),
    ),
)

_JSON_ARTIFACTS = tuple(
    PublicationArtifactSpec(
        name,
        f"release/{name}.json",
        "publication",
        PublicationJSONSpec(required_fields, description),
        "json",
    )
    for name, required_fields, description in (
        (
            "dataset_manifest",
            (
                "release_schema_version",
                "dataset_release_version",
                "dataset_id",
                "canonical_reference_id",
                "canonical_reference_sequence_sha256",
                "production_dag_id",
                "publication_artifacts",
                "authoritative_stage32_qc_decision_source",
                "authoritative_qc_derived_stage31_manifest_source",
                "authoritative_stage31_aggregation_run_source",
            ),
            "Release identity, registry/references and mandatory "
            "QC-derived aggregation authority.",
        ),
        (
            "artifact_inventory",
            ("release_schema_version", "dataset_id", "artifacts"),
            "Portable inventory of release artifacts with classes, "
            "encodings and lineage references; "
            "existing generic inventory schemas remain unchanged.",
        ),
        (
            "provenance",
            (
                "release_schema_version",
                "dataset_id",
                "production_dag_id",
                "production_execution_dag",
                "candidate_replica_lineage",
                "qc_decision_source",
                "qc_derived_aggregation_manifest_source",
                "aggregation_run_source",
                "publication_artifact_lineage",
            ),
            "Actual order 27–30 -> 32 -> QC-derived 31 -> "
            "31 aggregation -> 33 publication; "
            "all candidates, including excluded replicas, "
            "retain portable evidence linkage. "
            "Stage 33.D decides audit packaging/reference policy; "
            "generic provenance is unchanged.",
        ),
    )
)

PUBLICATION_ARTIFACT_REGISTRY = PublicationArtifactRegistry(
    (*_TABLE_ARTIFACTS, *_JSON_ARTIFACTS)
)
PUBLICATION_TABLE_SPECS = PUBLICATION_ARTIFACT_REGISTRY.tables
PUBLICATION_TABLE_PATHS = tuple(t.relative_path for t in PUBLICATION_TABLE_SPECS)
REQUIRED_RELEASE_JSON_PATHS = tuple(
    a.relative_path
    for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts
    if a.mandatory_encoding == "json"
)


def dataset_release_contract_to_dict() -> dict[str, object]:
    """Return detached, deterministic JSON-safe schema data; never publication data."""
    return {
        "schema_version": DATASET_RELEASE_CONTRACT_SCHEMA_VERSION,
        "dataset_release_version": DATASET_RELEASE_VERSION,
        "canonical_reference_id": DATASET_RELEASE_CANONICAL_REFERENCE_ID,
        "canonical_reference_sequence_sha256": (
            DATASET_RELEASE_CANONICAL_REFERENCE_SHA256
        ),
        "canonical_node_count": CANONICAL_NODE_COUNT,
        "canonical_residue_range": list(CANONICAL_RESIDUE_RANGE),
        "artifact_classes": list(PUBLICATION_ARTIFACT_CLASSES),
        "logical_types": list(PUBLICATION_LOGICAL_TYPES),
        "development_order": list(DEVELOPMENT_ORDER),
        "production_dag_id": PRODUCTION_DAG_ID,
        "production_execution_dag": list(PRODUCTION_EXECUTION_DAG),
        "aggregate_required_lineage": list(AGGREGATE_PUBLICATION_REQUIRED_LINEAGE),
        "population_rules": list(PUBLICATION_POPULATION_RULES),
        "serialization_rules": list(SERIALIZATION_RULES),
        "scientific_rules": list(SCIENTIFIC_PUBLICATION_RULES),
        "contact_definition_required_parameters": list(
            CONTACT_DEFINITION_REQUIRED_PARAMETERS
        ),
        "registry": PUBLICATION_ARTIFACT_REGISTRY.to_dict(),
    }
