"""Dataset-level export models copying accepted Stage 31 results exactly."""

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, ClassVar, Generic, TypeVar

from mania.dataset_identity import DatasetEngine
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    ReplicaAggregationWindowDefinition,
    build_compatible_replica_aggregation_group,
)
from mania.replica_aggregation_manifest import (
    aggregation_group_identity,
    require_fixed_metadata,
)
from mania.replica_protein_edge_aggregation import (
    CanonicalProteinEdgeReplicaAggregate,
    CanonicalProteinEdgeReplicaAggregation,
)
from mania.replica_specialized_aggregation import (
    CanonicalProteinGlycanReplicaAggregate,
    CanonicalProteinGlycanReplicaAggregation,
    CanonicalProteinLipidReplicaAggregate,
    CanonicalProteinLipidReplicaAggregation,
)

CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_CSV_FILENAME = (
    "protein_edges_by_window_canonical_replica_aggregation.csv"
)
CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_CSV_FILENAME = (
    "protein_lipid_contacts_by_window_canonical_replica_aggregation.csv"
)
CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_CSV_FILENAME = (
    "protein_glycan_contacts_by_window_canonical_replica_aggregation.csv"
)


@dataclass(frozen=True)
class _AggregateGroupColumns:
    dataset_id: str
    system_id: str
    engine: DatasetEngine
    variant_id: str
    condition: str | None
    disulfide_state: str | None
    window_id: str
    window_index: int
    requested_production_start_ns: float
    requested_production_end_ns: float
    requested_window_start_ns: float
    requested_window_end_ns: float
    right_endpoint_inclusive: bool
    window_length_ns: float
    window_step_ns: float
    overlap_percent: float

    _aggregate_type: ClassVar[type[Any]]

    @property
    def window(self) -> ReplicaAggregationWindowDefinition:
        return ReplicaAggregationWindowDefinition(
            **{
                f.name: getattr(self, f.name)
                for f in fields(ReplicaAggregationWindowDefinition)
            }
        )

    @property
    def group_identity(self) -> tuple[object, ...]:
        return (
            self.dataset_id,
            self.system_id,
            self.engine,
            self.window.physical_window_key,
            self.window_id,
            self.window_index,
        )

    @property
    def entity_identity(self) -> tuple[object, ...]:
        raise NotImplementedError

    @property
    def row_identity(self) -> tuple[object, ...]:
        return (*self.group_identity, *self.entity_identity)

    @property
    def row_order(self) -> tuple[Any, ...]:
        entity = self.entity_identity
        return (
            self.dataset_id,
            self.system_id,
            self.engine,
            self.window_index,
            *(
                tuple(reversed(entity))
                if len(entity) == 2
                else (entity[2], entity[0], entity[1])
            ),
            self.window.physical_window_key,
            self.window_id,
        )

    def __post_init__(self) -> None:
        for name in (
            "dataset_id",
            "system_id",
            "variant_id",
            "condition",
            "disulfide_state",
        ):
            value = getattr(self, name)
            if value is None and name in ("condition", "disulfide_state"):
                continue
            if type(value) is not str or not value or value != value.strip():
                raise ValueError("Group metadata must be non-empty stripped strings")
        if type(self.engine) is not str or self.engine not in ("gromacs", "namd"):
            raise ValueError("Invalid exact engine")
        _ = self.window
        self._aggregate_type(
            **{f.name: getattr(self, f.name) for f in fields(self._aggregate_type)}
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalProteinEdgeReplicaAggregationRow(_AggregateGroupColumns):
    source_canonical_residue_number: int
    source_canonical_resname: str
    target_canonical_residue_number: int
    target_canonical_resname: str
    edge_type: str
    mean_occupancy: float
    std_occupancy: float | None
    median_occupancy: float
    n_replicates_available: int
    n_replicates_supporting: int
    support_fraction: float

    _aggregate_type = CanonicalProteinEdgeReplicaAggregate

    @property
    def entity_identity(self) -> tuple[object, ...]:
        return (self.source_canonical_residue_number,
                self.target_canonical_residue_number, self.edge_type)


@dataclass(frozen=True)
class CanonicalProteinLipidReplicaAggregationRow(_AggregateGroupColumns):
    canonical_residue_number: int
    canonical_resname: str
    partner_correspondence_id: str
    partner_name: str
    mean_occupancy: float
    std_occupancy: float | None
    median_occupancy: float
    n_replicates_available: int
    n_replicates_supporting: int
    support_fraction: float

    _aggregate_type = CanonicalProteinLipidReplicaAggregate

    @property
    def entity_identity(self) -> tuple[object, ...]:
        return (self.canonical_residue_number, self.partner_correspondence_id)


@dataclass(frozen=True)
class CanonicalProteinGlycanReplicaAggregationRow(_AggregateGroupColumns):
    canonical_residue_number: int
    canonical_resname: str
    partner_correspondence_id: str
    partner_name: str
    mean_occupancy: float
    std_occupancy: float | None
    median_occupancy: float
    n_replicates_available: int
    n_replicates_supporting: int
    support_fraction: float

    _aggregate_type = CanonicalProteinGlycanReplicaAggregate

    @property
    def entity_identity(self) -> tuple[object, ...]:
        return (self.canonical_residue_number, self.partner_correspondence_id)


_Row = TypeVar("_Row", bound=_AggregateGroupColumns)


@dataclass(frozen=True)
class _AggregationTable(Generic[_Row]):
    rows: tuple[_Row, ...]
    canonical_reference_id: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
    )
    _row_type: ClassVar[type[_AggregateGroupColumns]]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def __post_init__(self) -> None:
        require_fixed_metadata(self)
        if type(self.rows) is not tuple or any(
            type(row) is not self._row_type for row in self.rows
        ):
            raise ValueError("Expected tuple of exact aggregate table rows")
        metadata: dict[tuple[object, ...], tuple[object, ...]] = {}
        for row in self.rows:
            replace(row)
            values = (
                row.variant_id,
                row.condition,
                row.disulfide_state,
                row.to_dict()["n_replicates_available"],
            )
            if metadata.setdefault(row.group_identity, values) != values:
                raise ValueError("Inconsistent group metadata")
        identities = [row.row_identity for row in self.rows]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate aggregate row identity")
        order = [row.row_order for row in self.rows]
        if order != sorted(order):
            raise ValueError("Aggregate rows must follow deterministic order")


@dataclass(frozen=True)
class CanonicalProteinEdgeReplicaAggregationTable(
    _AggregationTable[CanonicalProteinEdgeReplicaAggregationRow]
):
    _row_type = CanonicalProteinEdgeReplicaAggregationRow


@dataclass(frozen=True)
class CanonicalProteinLipidReplicaAggregationTable(
    _AggregationTable[CanonicalProteinLipidReplicaAggregationRow]
):
    _row_type = CanonicalProteinLipidReplicaAggregationRow


@dataclass(frozen=True)
class CanonicalProteinGlycanReplicaAggregationTable(
    _AggregationTable[CanonicalProteinGlycanReplicaAggregationRow]
):
    _row_type = CanonicalProteinGlycanReplicaAggregationRow


def _build(
    results: tuple[Any, ...], result_type: type[Any], row_type: type[_Row]
) -> tuple[_Row, ...]:
    if type(results) is not tuple or any(type(r) is not result_type for r in results):
        raise ValueError("Expected tuple of exact accepted aggregation results")
    seen = set()
    rows: list[_Row] = []
    for result in results:
        require_fixed_metadata(result)
        result.__post_init__()
        build_compatible_replica_aggregation_group(
            result.group.spec, result.group.members,
        )
        identity = aggregation_group_identity(result.group.spec)
        if identity in seen:
            raise ValueError("Duplicate aggregation result group")
        seen.add(identity)
        spec = result.group.spec
        common = {
            name: getattr(spec, name)
            for name in (
                "dataset_id",
                "system_id",
                "engine",
                "variant_id",
                "condition",
                "disulfide_state",
            )
        }
        common.update(spec.window.to_dict())
        aggregates = (
            result.edges
            if result_type is CanonicalProteinEdgeReplicaAggregation
            else result.rows
        )
        rows.extend(row_type(**common, **row.to_dict()) for row in aggregates)
    return tuple(sorted(rows, key=lambda row: row.row_order))


def build_canonical_protein_edge_replica_aggregation_table(
    results: tuple[CanonicalProteinEdgeReplicaAggregation, ...],
) -> CanonicalProteinEdgeReplicaAggregationTable:
    return CanonicalProteinEdgeReplicaAggregationTable(
        _build(
            results,
            CanonicalProteinEdgeReplicaAggregation,
            CanonicalProteinEdgeReplicaAggregationRow,
        )
    )


def build_canonical_protein_lipid_replica_aggregation_table(
    results: tuple[CanonicalProteinLipidReplicaAggregation, ...],
) -> CanonicalProteinLipidReplicaAggregationTable:
    return CanonicalProteinLipidReplicaAggregationTable(
        _build(
            results,
            CanonicalProteinLipidReplicaAggregation,
            CanonicalProteinLipidReplicaAggregationRow,
        )
    )


def build_canonical_protein_glycan_replica_aggregation_table(
    results: tuple[CanonicalProteinGlycanReplicaAggregation, ...],
) -> CanonicalProteinGlycanReplicaAggregationTable:
    return CanonicalProteinGlycanReplicaAggregationTable(
        _build(
            results,
            CanonicalProteinGlycanReplicaAggregation,
            CanonicalProteinGlycanReplicaAggregationRow,
        )
    )
