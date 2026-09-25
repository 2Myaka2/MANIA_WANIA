"""Pure Stage 33.B metadata projection from accepted, explicit authorities.

Only the packaged Stage 30 reference is loaded by the canonical public APIs.
No caller artifact is opened, no trajectory/QC evaluator is run, and no release
directories are created. CSV writing is a separate operation.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import TypeAlias

from mania.biological_annotations import DatasetSystemBiologicalAnnotations
from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_qc_summary import DatasetQCSummary, build_dataset_qc_summary
from mania.dataset_release_canonical import (
    build_dataset_release_nodes,
    build_dataset_release_residue_annotations,
)
from mania.dataset_release_contract import (
    CANONICAL_NODE_COUNT,
    CONTACT_DEFINITION_REQUIRED_PARAMETERS,
    REPLICA_KEY,
)
from mania.dataset_release_csv import (
    METADATA_TABLE_IDS,
    DatasetReleaseTable,
    build_publication_table,
    publication_number,
    require_portable_publication_path,
)
from mania.dataset_release_qc import (
    build_dataset_release_qc_tables,
    validate_publication_qc_inputs,
)
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)
from mania.preprocessing.temporal_policy import (
    LEGACY_BOUNDARY_PROFILE,
    BoundaryProfile,
    require_boundary_profile,
)
from mania.replica_aggregation_contract import ReplicaAggregationMember
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    require_fixed_metadata,
)

ReplicaKey: TypeAlias = tuple[str, str, str, str]
SystemKey: TypeAlias = tuple[str, str]
_LABELS = ("engine", "variant_id", "condition", "disulfide_state")
_DECISION_FIELDS = (
    "qc_status",
    "release_decision",
    "decision_mode",
    "decision_reason_code",
    "human_readable_reason",
)


class DatasetReleaseMetadataError(ValueError):
    """Missing authority, inconsistent metadata or invalid publication selection."""


def _unique_replica_keys(keys: Iterable[ReplicaKey]) -> tuple[ReplicaKey, ...]:
    values = tuple(keys)
    if any(
        type(k) is not tuple
        or len(k) != 4
        or any(type(v) is not str or not v or v != v.strip() for v in k)
        for k in values
    ) or len(values) != len(set(values)):
        raise DatasetReleaseMetadataError("Full replica keys must be exact and unique")
    return values


@dataclass(frozen=True)
class QCDerivedAggregationEvidence:
    """Caller attestation binding a Stage 32-derived manifest to its decisions.

    Stage 31's model has no derivation tag. A pre-QC template alone is therefore
    not accepted. The caller supplies this explicit evidence from the completed
    Stage 32 operation; 33.D will verify full artifact lineage. No QC is rerun.
    """

    manifest: ReplicaAggregationManifest
    decisions: DatasetQCDecisionSet
    source_artifact_role: str
    source_artifact_path: str

    def __post_init__(self) -> None:
        if type(self.manifest) is not ReplicaAggregationManifest or (
            type(self.decisions) is not DatasetQCDecisionSet
        ):
            raise DatasetReleaseMetadataError("Expected accepted Stage 31/32 models")
        if self.source_artifact_role != "qc_derived_replica_aggregation_manifest":
            raise DatasetReleaseMetadataError(
                "QC-derived Stage 31 authority is required"
            )
        require_portable_publication_path(self.source_artifact_path)
        require_fixed_metadata(self.manifest)
        # Do not replace(manifest): that accepted constructor resolves/stats its
        # source paths. Validate only the already-constructed metadata groups.
        for group in self.manifest.groups:
            if replace(group) != group:
                raise DatasetReleaseMetadataError("Manifest groups must be validated")


def _candidate_members(
    decisions: DatasetQCDecisionSet,
    authority: QCDerivedAggregationEvidence,
) -> tuple[ReplicaAggregationMember, ...]:
    if type(authority) is not QCDerivedAggregationEvidence:
        raise DatasetReleaseMetadataError(
            "Explicit QC-derived manifest evidence is required"
        )
    replace(authority)
    validate_publication_qc_inputs(decisions, build_dataset_qc_summary(decisions))
    if authority.decisions != decisions:
        raise DatasetReleaseMetadataError(
            "QC-derived evidence binds different decisions"
        )
    members: dict[ReplicaKey, ReplicaAggregationMember] = {}
    for group in authority.manifest.groups:
        for member in group.members:
            previous = members.get(member.replica_key)
            if previous is not None and any(
                getattr(previous, name) != getattr(member, name)
                for name in (*_LABELS, "availability_status", "availability_reason")
            ):
                raise DatasetReleaseMetadataError(
                    "Replica metadata/availability differs across windows"
                )
            members[member.replica_key] = member
    by_key = {r.replica_key: r for r in decisions.records}
    if members.keys() != by_key.keys():
        raise DatasetReleaseMetadataError(
            "QC and manifest candidate replica coverage must match"
        )
    for key, member in members.items():
        # Stage 32 preserves a technical unavailable state even for QC exclusion.
        if member.availability_status != "unavailable" and (
            member.availability_status != by_key[key].release_decision
        ):
            raise DatasetReleaseMetadataError(
                "QC decision and aggregation availability disagree"
            )
    return tuple(members[k] for k in sorted(members))


def build_dataset_release_systems(
    members: tuple[ReplicaAggregationMember, ...],
) -> DatasetReleaseTable:
    if not members:
        raise DatasetReleaseMetadataError("Publication systems must be nonempty")
    systems: dict[SystemKey, dict[str, object]] = {}
    for member in members:
        if type(member) is not ReplicaAggregationMember:
            raise DatasetReleaseMetadataError(
                "Expected accepted Stage 31 member identity"
            )
        replace(member)
        key = (member.dataset_id, member.system_id)
        row = {n: getattr(member, n) for n in ("dataset_id", "system_id", *_LABELS)}
        if key in systems and systems[key] != row:
            raise DatasetReleaseMetadataError(
                "System-level metadata disagrees across replicas"
            )
        systems[key] = row
    return build_publication_table("systems", systems.values())


def build_dataset_release_simulations(
    decisions: DatasetQCDecisionSet,
    authority: QCDerivedAggregationEvidence,
    *,
    scientific_release_replica_keys: Iterable[ReplicaKey],
) -> DatasetReleaseTable:
    members = _candidate_members(decisions, authority)
    build_dataset_release_systems(members)  # Also enforce system-level agreement.
    selected = set(_unique_replica_keys(scientific_release_replica_keys))
    by_key = {r.replica_key: r for r in decisions.records}
    if not selected <= by_key.keys() or any(
        by_key[k].release_decision != "available" for k in selected
    ):
        raise DatasetReleaseMetadataError(
            "Scientific release keys must be QC-available candidates"
        )
    return build_publication_table(
        "simulations",
        (
            {
                **{n: getattr(m, n) for n in (*REPLICA_KEY, *_LABELS)},
                **{n: getattr(by_key[m.replica_key], n) for n in _DECISION_FIELDS},
                "aggregation_availability_status": m.availability_status,
                "aggregation_availability_reason": m.availability_reason,
                "included_in_scientific_release": m.replica_key in selected,
                "included_in_replica_aggregation": m.availability_status == "available",
            }
            for m in members
        ),
    )


def _effective_ns(value: float | None) -> Decimal | None:
    if value is None:
        return None
    sign, digits, exponent = publication_number(value).as_tuple()
    assert isinstance(exponent, int)
    return Decimal((sign, digits, exponent - 3))


def _validate_window_labels(table: DatasetReleaseTable) -> None:
    identities: dict[tuple[object, ...], tuple[object, ...]] = {}
    names = (
        "requested_production_start_ns",
        "requested_production_end_ns",
        "requested_window_start_ns",
        "requested_window_end_ns",
        "right_endpoint_inclusive",
        "window_length_ns",
        "window_step_ns",
        "overlap_percent",
        "frame_stride_ps",
    )
    for row in table.records():
        replica = tuple(row[n] for n in REPLICA_KEY)
        definition = tuple(row[n] for n in names)
        for label in ("window_id", "window_index"):
            key = (*replica, label, row[label])
            if key in identities and identities[key] != definition:
                raise DatasetReleaseMetadataError(
                    "Duplicate window label/index has incompatible physical definitions"
                )
            identities[key] = definition


def build_dataset_release_time_windows(
    evidence: tuple[PreprocessingConditionTemporalExecution, ...],
) -> DatasetReleaseTable:
    rows: list[dict[str, object]] = []
    for execution in evidence:
        if type(execution) is not PreprocessingConditionTemporalExecution:
            raise DatasetReleaseMetadataError(
                "Expected accepted Stage 27 temporal evidence"
            )
        replace(execution.sampling_plan)
        replace(execution.window_plan)
        replace(execution)  # Accepted plan links, without either planner/evaluator.
        identity = execution.dataset_spec.identity
        plan = execution.window_plan
        for window in plan.windows:
            replace(window)  # Counts, coverage, bounds and partition consistency.
            rows.append(
                {
                    **{n: getattr(identity, n) for n in REPLICA_KEY},
                    "window_id": window.window_id,
                    "window_index": window.window_index,
                    "requested_production_start_ns": plan.requested_production_start_ns,
                    "requested_production_end_ns": plan.requested_production_end_ns,
                    "requested_window_start_ns": window.requested_start_ns,
                    "requested_window_end_ns": window.requested_end_ns,
                    "right_endpoint_inclusive": window.right_endpoint_inclusive,
                    "window_length_ns": plan.requested_window_length_ns,
                    "window_step_ns": plan.requested_window_step_ns,
                    "overlap_percent": plan.requested_overlap_percent,
                    "frame_stride_ps": (
                        execution.sampling_plan.requested_frame_stride_ps
                    ),
                    "expected_sample_count": window.requested_sample_count,
                    "resolved_sample_count": window.sampled_frame_count,
                    "missing_sample_count": window.missing_sample_count,
                    "coverage_fraction": window.coverage_fraction,
                    "effective_start_ns": _effective_ns(window.effective_start_time_ps),
                    "effective_end_ns": _effective_ns(window.effective_end_time_ps),
                }
            )
    table = build_publication_table("time_windows", rows)
    _validate_window_labels(table)
    return table


def build_dataset_release_contact_definition(
    *,
    replica_key: ReplicaKey,
    contact_definition_id: str,
    contact_layer: str,
    interaction_type: str,
    parameters: Mapping[str, object],
    source_artifact_role: str,
    source_artifact_path: str,
    units: Mapping[str, str] | None = None,
) -> DatasetReleaseTable:
    """Project a caller's complete accepted definition tree, including all options.

    Parameters come from recorded configuration/accepted semantic evidence, e.g.
    PreprocessingContactDetectionOptions.to_dict(include_contact_selection=True),
    typed edge semantics/atom maps and Stage 29 constants. No defaults, thresholds,
    PBC preparation or inapplicable parameters are inferred here.
    """
    _unique_replica_keys((replica_key,))
    if (
        not isinstance(parameters, Mapping)
        or not set(CONTACT_DEFINITION_REQUIRED_PARAMETERS) <= parameters.keys()
    ):
        raise DatasetReleaseMetadataError(
            "Contact definition lacks required accepted parameter roots"
        )
    rows: list[dict[str, object]] = []
    units = {} if units is None else units

    def visit(value: object, path: str) -> None:
        row: dict[str, object] = {
            **dict(zip(REPLICA_KEY, replica_key, strict=True)),
            "contact_definition_id": contact_definition_id,
            "contact_layer": contact_layer,
            "interaction_type": interaction_type,
            "parameter_path": path,
            "string_value": None,
            "integer_value": None,
            "number_value": None,
            "boolean_value": None,
            "unit": units.get(path),
            "source_artifact_role": source_artifact_role,
            "source_artifact_path": source_artifact_path,
        }
        if isinstance(value, Mapping):
            kind = "object"
        elif type(value) in (tuple, list):
            kind = "array"
        elif value is None:
            kind = "null"
        elif type(value) is bool:
            kind = "boolean"
        elif type(value) is int:
            kind = "integer"
        elif type(value) in (float, Decimal):
            kind = "number"
        elif type(value) is str:
            kind = "string"
        else:
            raise DatasetReleaseMetadataError("Unsupported contact parameter value")
        row["parameter_kind"] = kind
        if kind in ("string", "integer", "number", "boolean"):
            row[f"{kind}_value"] = value
        rows.append(row)
        if isinstance(value, Mapping):
            if any(type(k) is not str for k in value):
                raise DatasetReleaseMetadataError("Contact object keys must be text")
            for name in sorted(value):
                escaped = name.replace("~", "~0").replace("/", "~1")
                visit(value[name], f"{path}/{escaped}")
        elif isinstance(value, (tuple, list)):
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")

    try:
        visit(parameters, "$")
    except RecursionError:
        raise DatasetReleaseMetadataError(
            "Contact parameter tree is cyclic or too deep"
        ) from None
    if not set(units) <= {r["parameter_path"] for r in rows}:
        raise DatasetReleaseMetadataError(
            "Unit evidence references an unknown parameter path"
        )
    return build_publication_table("contact_definitions", rows)


def build_dataset_release_software_versions(
    records: Iterable[Mapping[str, object]],
) -> DatasetReleaseTable:
    """Copy exact schema-shaped run/caller evidence; never inspect this environment.

    Different runs may legitimately record different versions. Conflicting (or
    duplicate) records under the frozen source-scoped primary key always fail.
    """
    return build_publication_table("software_versions", records)


@dataclass(frozen=True)
class DatasetReleaseMetadataTables:
    systems: DatasetReleaseTable
    simulations: DatasetReleaseTable
    time_windows: DatasetReleaseTable
    contact_definitions: DatasetReleaseTable
    software_versions: DatasetReleaseTable
    quality_control: DatasetReleaseTable
    quality_control_findings: DatasetReleaseTable
    quality_control_evidence: DatasetReleaseTable
    nodes: DatasetReleaseTable
    residue_annotations: DatasetReleaseTable
    boundary_profile: BoundaryProfile = field(
        default=LEGACY_BOUNDARY_PROFILE, kw_only=True
    )

    def __post_init__(self) -> None:
        require_boundary_profile(self.boundary_profile)
        for name in METADATA_TABLE_IDS:
            table = getattr(self, name)
            if type(table) is not DatasetReleaseTable or table.table_id != name:
                raise DatasetReleaseMetadataError(
                    "Bundle table identity must match its slot"
                )
        if not self.systems.row_count or not self.simulations.row_count:
            raise DatasetReleaseMetadataError(
                "Release candidate population must be nonempty"
            )
        if self.nodes.row_count != CANONICAL_NODE_COUNT:
            raise DatasetReleaseMetadataError(
                "Release nodes must contain all 690 positions"
            )
        validate_dataset_release_metadata_relationships(self)

    @property
    def tables(self) -> tuple[DatasetReleaseTable, ...]:
        return tuple(getattr(self, name) for name in METADATA_TABLE_IDS)

    def to_dict(self) -> dict[str, object]:
        return {t.table_id: t.to_dict() for t in self.tables}


def validate_dataset_release_metadata_relationships(
    bundle: DatasetReleaseMetadataTables,
) -> None:
    """All in-scope frozen FKs, including complete simulations/QC linkage."""
    tables = {t.table_id: t for t in bundle.tables}
    for table in bundle.tables:
        for fk in table.spec.foreign_keys:
            target = tables.get(fk.target_table)
            if target is None:
                continue
            keys = {tuple(r[n] for n in fk.target_columns) for r in target.records()}
            if any(
                tuple(r[n] for n in fk.local_columns) not in keys
                for r in table.records()
            ):
                raise DatasetReleaseMetadataError(
                    f"Invalid {table.table_id} -> {target.table_id} foreign key"
                )
    _validate_window_labels(bundle.time_windows)


def build_dataset_release_metadata_tables(
    *,
    decisions: DatasetQCDecisionSet,
    summary: DatasetQCSummary,
    aggregation_authority: QCDerivedAggregationEvidence,
    scientific_release_replica_keys: Iterable[ReplicaKey],
    annotation_publication_system_keys: Iterable[SystemKey],
    temporal_evidence: tuple[PreprocessingConditionTemporalExecution, ...],
    annotation_metadata: tuple[DatasetSystemBiologicalAnnotations, ...],
    contact_definitions: tuple[DatasetReleaseTable, ...],
    software_version_records: Iterable[Mapping[str, object]],
) -> DatasetReleaseMetadataTables:
    """Build exactly ten publication tables without executing the production DAG."""
    profiles = {b.window_plan.boundary_profile for b in temporal_evidence}
    profiles.update(
        g.spec.window.boundary_profile for g in aggregation_authority.manifest.groups
    )
    if len(profiles) != 1:
        raise DatasetReleaseMetadataError(
            "Release cannot mix temporal boundary profiles"
        )
    boundary_profile = next(iter(profiles))
    qc = build_dataset_release_qc_tables(decisions, summary)
    members = _candidate_members(decisions, aggregation_authority)
    systems = build_dataset_release_systems(members)
    selected_systems = tuple(annotation_publication_system_keys)
    annotations = build_dataset_release_residue_annotations(
        annotation_metadata,
        annotation_publication_system_keys=selected_systems,
    )
    system_keys = {(m.dataset_id, m.system_id) for m in members}
    if not set(selected_systems) <= system_keys:
        raise DatasetReleaseMetadataError(
            "Annotation selection must be a subset of systems"
        )
    by_key = {m.replica_key: m for m in members}
    for evidence in temporal_evidence:
        identity = evidence.dataset_spec.identity
        member = by_key.get(identity.replica_key)
        if member is None or any(
            getattr(identity, n) != getattr(member, n) for n in _LABELS
        ):
            raise DatasetReleaseMetadataError(
                "Temporal evidence disagrees with candidate identity"
            )
    if any(t.table_id != "contact_definitions" for t in contact_definitions):
        raise DatasetReleaseMetadataError("Expected explicit contact definition tables")
    software = build_dataset_release_software_versions(software_version_records)
    if any(
        r["dataset_id"] not in {k[0] for k in system_keys} for r in software.records()
    ):
        raise DatasetReleaseMetadataError(
            "Software evidence must belong to a candidate Dataset"
        )
    return DatasetReleaseMetadataTables(
        systems,
        build_dataset_release_simulations(
            decisions,
            aggregation_authority,
            scientific_release_replica_keys=scientific_release_replica_keys,
        ),
        build_dataset_release_time_windows(temporal_evidence),
        build_publication_table(
            "contact_definitions",
            (row for t in contact_definitions for row in t.records()),
        ),
        software,
        qc.quality_control,
        qc.quality_control_findings,
        qc.quality_control_evidence,
        build_dataset_release_nodes(),
        annotations,
        boundary_profile=boundary_profile,
    )
