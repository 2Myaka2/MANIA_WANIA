"""Strict Stage 30.C application of explicit mappings to intermediate tables.

Only protein identities are enriched. Source evidence and accepted scientific
metrics remain intact; Dataset workflow and biological annotations are 30.D.
"""

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Generic, TypeVar

from mania.canonical_reference import CanonicalProteinReference
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
    canonical_residue_for_mapping,
    require_mapped_source_residue,
    validate_canonical_residue_mapping_table,
)
from mania.preprocessing.protein_edge_window_table import (
    DatasetProteinEdgeWindowRow,
    DatasetProteinEdgeWindowTable,
)
from mania.preprocessing.specialized_contact_window_tables import (
    ProteinGlycanWindowRow,
    ProteinGlycanWindowTable,
    ProteinLipidWindowRow,
    ProteinLipidWindowTable,
)

CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION = (
    "mania.canonical_protein_edges_by_window.v0.1"
)
CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_KIND = "mania_canonical_protein_edges_by_window"
CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME = "protein_edges_by_window_canonical.csv"
CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_SCHEMA_VERSION = (
    "mania.canonical_protein_lipid_contacts_by_window.v0.1"
)
CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_KIND = (
    "mania_canonical_protein_lipid_contacts_by_window"
)
CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME = (
    "protein_lipid_contacts_by_window_canonical.csv"
)
CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_SCHEMA_VERSION = (
    "mania.canonical_protein_glycan_contacts_by_window.v0.1"
)
CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_KIND = (
    "mania_canonical_protein_glycan_contacts_by_window"
)
CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME = (
    "protein_glycan_contacts_by_window_canonical.csv"
)

_ReplicaKey = tuple[str, str, str, str]


class CanonicalWindowTableError(ValueError):
    """Invalid binding, missing mapping, or ambiguous canonical table identity."""


def _text(value: object, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise CanonicalWindowTableError(f"{name} must be a non-empty stripped string")


def _values(record: Any) -> dict[str, Any]:
    return {
        item.name: getattr(record, item.name) for item in fields(record) if item.init
    }


def _validate_mapping(
    table: CanonicalResidueMappingTable, reference: CanonicalProteinReference
) -> None:
    if type(table) is not CanonicalResidueMappingTable:
        raise CanonicalWindowTableError(
            "mapping_table must be exact mapping-table type"
        )
    try:
        # Reconstruct to detect bypassed frozen-model invariants, including keys,
        # record status and fixed provenance, before the accepted 30.B validation.
        if type(table.mappings) is not tuple:
            raise ValueError("mappings must be a tuple")
        for record in table.mappings:
            if type(record) is not CanonicalResidueMappingRecord:
                raise ValueError("mapping records must have exact type")
            CanonicalResidueMappingRecord(**_values(record))
        reconstructed = CanonicalResidueMappingTable(table.mappings)
        if table.to_dict() != reconstructed.to_dict():
            raise ValueError(
                "Mapping reference metadata must match the pinned reference"
            )
        validate_canonical_residue_mapping_table(table, reference=reference)
    except (ValueError, TypeError) as exc:
        raise CanonicalWindowTableError(str(exc)) from None


@dataclass(frozen=True)
class DatasetCanonicalResidueMappingBinding:
    """One explicit mapping table for one exact Dataset replica, never condition."""

    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    mapping_table: CanonicalResidueMappingTable

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
            _text(getattr(self, name), name)
        if type(self.mapping_table) is not CanonicalResidueMappingTable:
            raise CanonicalWindowTableError(
                "mapping_table must be exact mapping-table type"
            )

    @property
    def replica_key(self) -> _ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id


@dataclass(frozen=True)
class DatasetCanonicalResidueMappingBindings:
    """Unique bindings in deterministic replica-key order; extra bindings are valid."""

    bindings: tuple[DatasetCanonicalResidueMappingBinding, ...]

    def __post_init__(self) -> None:
        if type(self.bindings) is not tuple or any(
            type(binding) is not DatasetCanonicalResidueMappingBinding
            for binding in self.bindings
        ):
            raise CanonicalWindowTableError(
                "bindings must be a tuple of exact bindings"
            )
        keys = [binding.replica_key for binding in self.bindings]
        if len(set(keys)) != len(keys):
            raise CanonicalWindowTableError("Dataset replica keys must be unique")
        if keys != sorted(keys):
            raise CanonicalWindowTableError(
                "bindings must follow deterministic replica order"
            )
        reference = load_default_napi2b_canonical_reference()
        for binding in self.bindings:
            binding.__post_init__()
            _validate_mapping(binding.mapping_table, reference)

    def lookup(self, replica_key: _ReplicaKey) -> CanonicalResidueMappingTable:
        """Require the exact four-field replica key; no condition/engine fallback."""
        if type(replica_key) is not tuple or len(replica_key) != 4:
            raise CanonicalWindowTableError(
                "replica_key must be an exact four-field tuple"
            )
        for value in replica_key:
            _text(value, "replica key identifier")
        for binding in self.bindings:
            if binding.replica_key == replica_key:
                return binding.mapping_table
        raise CanonicalWindowTableError(
            "No explicit mapping binding for Dataset replica"
        )


@dataclass(frozen=True)
class _CanonicalWindowRow:
    dataset_id: str
    system_id: str
    trajectory_id: str
    variant_id: str
    engine: str
    condition: str | None
    replica_id: str
    disulfide_state: str | None
    window_id: str
    window_index: int
    requested_window_start_ns: float
    requested_window_end_ns: float
    right_endpoint_inclusive: bool
    effective_window_start_ns: float
    effective_window_end_ns: float
    requested_sample_count: int
    resolved_frame_count: int
    missing_sample_count: int
    coverage_fraction: float

    @property
    def replica_key(self) -> _ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, Any]:
        return {
            name: list(value) if type(value) is tuple else value
            for name, value in _values(self).items()
        }


def _validate_row(
    row: _CanonicalWindowRow, source_type: type[Any], prefixes: tuple[str, ...]
) -> None:
    try:
        source = {item.name: getattr(row, item.name) for item in fields(source_type)}
        if source_type is DatasetProteinEdgeWindowRow and (
            source["source_residue_index"] > source["target_residue_index"]
        ):
            # 28.B validates source-topology orientation. Restore it on a private
            # copy only; the canonical row remains in publication orientation.
            _swap_edge_sides(source, canonical=False)
        source_type(**source)
        reference = load_default_napi2b_canonical_reference()
        for prefix in prefixes:
            resid = getattr(row, f"{prefix}resid")
            _text(resid, f"{prefix}resid")
            chain = getattr(row, f"{prefix}chain_id")
            canonical_prefix = "" if prefix == "protein_" else prefix
            record = CanonicalResidueMappingRecord(
                row.engine,
                chain,
                resid,
                getattr(row, f"{prefix}resname"),
                getattr(row, f"{canonical_prefix}canonical_residue_number"),
                getattr(row, f"{canonical_prefix}canonical_resname"),
                "mapped",
            )
            canonical_residue_for_mapping(record, reference)
    except (ValueError, TypeError) as exc:
        raise CanonicalWindowTableError(str(exc)) from None


def _swap_edge_sides(values: dict[str, Any], *, canonical: bool) -> None:
    suffixes: tuple[str, ...] = ("residue_index", "chain_id", "resid", "resname")
    if canonical:
        suffixes += ("canonical_residue_number", "canonical_resname")
    for suffix in suffixes:
        source, target = f"source_{suffix}", f"target_{suffix}"
        values[source], values[target] = values[target], values[source]


@dataclass(frozen=True)
class CanonicalProteinEdgeWindowRow(_CanonicalWindowRow):
    source_residue_index: int
    source_chain_id: str | None
    source_resid: str
    source_resname: str
    source_canonical_residue_number: int
    source_canonical_resname: str
    target_residue_index: int
    target_chain_id: str | None
    target_resid: str
    target_resname: str
    target_canonical_residue_number: int
    target_canonical_resname: str
    edge_type: str
    n_contact_frames: int
    occupancy: float
    n_contact_episodes: int
    mean_episode_length_ns: float
    max_episode_length_ns: float
    edge_weight: float

    def __post_init__(self) -> None:
        _validate_row(self, DatasetProteinEdgeWindowRow, ("source_", "target_"))
        if self.source_canonical_residue_number >= self.target_canonical_residue_number:
            raise CanonicalWindowTableError(
                "Canonical edge orientation requires source < target; self-loops fail"
            )

    @property
    def row_identity(self) -> tuple[str, str, str, str, str, int, int, str]:
        return (
            *self.replica_key,
            self.window_id,
            self.source_canonical_residue_number,
            self.target_canonical_residue_number,
            self.edge_type,
        )

    @property
    def row_order(self) -> tuple[str, str, str, str, int, str, int, int]:
        return (
            *self.replica_key,
            self.window_index,
            self.edge_type,
            self.source_canonical_residue_number,
            self.target_canonical_residue_number,
        )


@dataclass(frozen=True)
class _CanonicalSpecializedRow(_CanonicalWindowRow):
    protein_residue_index: int
    protein_chain_id: str | None
    protein_resid: str
    protein_resname: str
    canonical_residue_number: int
    canonical_resname: str
    _partner_kind: ClassVar[str]

    @property
    def row_identity(self) -> tuple[str, str, str, str, str, int, str]:
        return (
            *self.replica_key,
            self.window_id,
            self.canonical_residue_number,
            getattr(self, f"{self._partner_kind}_partner_id"),
        )

    @property
    def row_order(self) -> tuple[str, str, str, str, int, int, str]:
        return (
            *self.replica_key,
            self.window_index,
            self.canonical_residue_number,
            getattr(self, f"{self._partner_kind}_partner_id"),
        )


@dataclass(frozen=True)
class CanonicalProteinLipidWindowRow(_CanonicalSpecializedRow):
    lipid_partner_id: str
    lipid_partner_name: str
    lipid_component_residue_indexes: tuple[int, ...]
    n_contact_frames: int
    occupancy: float
    n_contact_episodes: int
    mean_episode_length_ns: float
    max_episode_length_ns: float
    distance_mean_A: float
    distance_min_A: float
    _partner_kind = "lipid"

    def __post_init__(self) -> None:
        _validate_row(self, ProteinLipidWindowRow, ("protein_",))


@dataclass(frozen=True)
class CanonicalProteinGlycanWindowRow(_CanonicalSpecializedRow):
    glycan_partner_id: str
    glycan_partner_name: str
    glycan_component_residue_indexes: tuple[int, ...]
    carrier_residue_index: int
    first_sugar_residue_index: int
    linkage_evidence: str
    carrier_link_atom_index: int | None
    first_sugar_link_atom_index: int | None
    n_contact_frames: int
    occupancy: float
    n_contact_episodes: int
    mean_episode_length_ns: float
    max_episode_length_ns: float
    distance_mean_A: float
    distance_min_A: float
    _partner_kind = "glycan"

    def __post_init__(self) -> None:
        _validate_row(self, ProteinGlycanWindowRow, ("protein_",))


_Row = TypeVar(
    "_Row",
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinGlycanWindowRow,
)


@dataclass(frozen=True)
class _CanonicalWindowTable(Generic[_Row]):
    rows: tuple[_Row, ...]
    schema_version: str = field(init=False)
    kind: str = field(init=False)
    canonical_reference_id: str = field(
        init=False, default=CANONICAL_RESIDUE_MAPPING_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256
    )
    _row_type: ClassVar[type[_CanonicalWindowRow]]

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or any(
            type(row) is not self._row_type for row in self.rows
        ):
            raise CanonicalWindowTableError(
                "rows must be a tuple of exact layer row type"
            )
        for row in self.rows:
            row.__post_init__()
        identities = [row.row_identity for row in self.rows]
        if len(set(identities)) != len(identities):
            raise CanonicalWindowTableError("Canonical row identity collision")
        order = [row.row_order for row in self.rows]
        if order != sorted(order):
            raise CanonicalWindowTableError(
                "rows must follow deterministic canonical order"
            )
        for item in fields(self):
            if not item.init and getattr(self, item.name) != item.default:
                raise CanonicalWindowTableError(
                    "Fixed canonical table metadata must match"
                )

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "canonical_reference_id": self.canonical_reference_id,
            "canonical_reference_sequence_sha256": (
                self.canonical_reference_sequence_sha256
            ),
            "row_count": self.row_count,
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass(frozen=True)
class CanonicalProteinEdgeWindowTable(
    _CanonicalWindowTable[CanonicalProteinEdgeWindowRow]
):
    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_KIND)
    _row_type = CanonicalProteinEdgeWindowRow


@dataclass(frozen=True)
class CanonicalProteinLipidWindowTable(
    _CanonicalWindowTable[CanonicalProteinLipidWindowRow]
):
    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_KIND)
    _row_type = CanonicalProteinLipidWindowRow


@dataclass(frozen=True)
class CanonicalProteinGlycanWindowTable(
    _CanonicalWindowTable[CanonicalProteinGlycanWindowRow]
):
    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_KIND)
    _row_type = CanonicalProteinGlycanWindowRow


def _build_rows(
    source_table: Any,
    source_type: type[Any],
    row_type: type[_Row],
    mapping_bindings: DatasetCanonicalResidueMappingBindings,
) -> tuple[_Row, ...]:
    if type(source_table) is not source_type:
        raise CanonicalWindowTableError(
            f"source_table must be exact {source_type.__name__}"
        )
    if type(mapping_bindings) is not DatasetCanonicalResidueMappingBindings:
        raise CanonicalWindowTableError(
            "mapping_bindings must be exact binding collection"
        )
    mapping_bindings.__post_init__()
    try:
        source_table.__post_init__()
        reference = load_default_napi2b_canonical_reference()
        rows = []
        for source in source_table.rows:
            replica_key = (
                source.dataset_id,
                source.system_id,
                source.trajectory_id,
                source.replica_id,
            )
            mapping = mapping_bindings.lookup(replica_key)
            values = _values(source)
            prefixes = (
                ("source_", "target_")
                if source_type is DatasetProteinEdgeWindowTable
                else ("protein_",)
            )
            for prefix in prefixes:
                resid = getattr(source, f"{prefix}resid")
                _text(resid, f"{prefix}resid")
                key = (
                    source.engine,
                    getattr(source, f"{prefix}chain_id"),
                    resid,
                    getattr(source, f"{prefix}resname"),
                )
                record = require_mapped_source_residue(
                    mapping,
                    source_engine=key[0],
                    source_chain_id=key[1],
                    source_resid=key[2],
                    source_resname=key[3],
                )
                if record.source_key != key:
                    raise CanonicalWindowTableError(
                        "Retrieved mapping source key must be exact"
                    )
                canonical = canonical_residue_for_mapping(record, reference)
                output_prefix = "" if prefix == "protein_" else prefix
                values[f"{output_prefix}canonical_residue_number"] = (
                    canonical.canonical_residue_number
                )
                values[f"{output_prefix}canonical_resname"] = (
                    canonical.canonical_resname
                )
            if source_type is DatasetProteinEdgeWindowTable and (
                values["source_canonical_residue_number"]
                > values["target_canonical_residue_number"]
            ):
                _swap_edge_sides(values, canonical=True)
            rows.append(row_type(**values))
        return tuple(sorted(rows, key=lambda row: row.row_order))
    except (ValueError, TypeError) as exc:
        raise CanonicalWindowTableError(str(exc)) from None


def build_canonical_protein_edge_window_table(
    source_table: DatasetProteinEdgeWindowTable,
    *,
    mapping_bindings: DatasetCanonicalResidueMappingBindings,
) -> CanonicalProteinEdgeWindowTable:
    return CanonicalProteinEdgeWindowTable(
        _build_rows(
            source_table,
            DatasetProteinEdgeWindowTable,
            CanonicalProteinEdgeWindowRow,
            mapping_bindings,
        )
    )


def build_canonical_protein_lipid_window_table(
    source_table: ProteinLipidWindowTable,
    *,
    mapping_bindings: DatasetCanonicalResidueMappingBindings,
) -> CanonicalProteinLipidWindowTable:
    return CanonicalProteinLipidWindowTable(
        _build_rows(
            source_table,
            ProteinLipidWindowTable,
            CanonicalProteinLipidWindowRow,
            mapping_bindings,
        )
    )


def build_canonical_protein_glycan_window_table(
    source_table: ProteinGlycanWindowTable,
    *,
    mapping_bindings: DatasetCanonicalResidueMappingBindings,
) -> CanonicalProteinGlycanWindowTable:
    return CanonicalProteinGlycanWindowTable(
        _build_rows(
            source_table,
            ProteinGlycanWindowTable,
            CanonicalProteinGlycanWindowRow,
            mapping_bindings,
        )
    )


__all__ = [
    "CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION",
    "CANONICAL_PROTEIN_EDGE_WINDOW_TABLE_KIND",
    "CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME",
    "CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_SCHEMA_VERSION",
    "CANONICAL_PROTEIN_LIPID_WINDOW_TABLE_KIND",
    "CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME",
    "CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_SCHEMA_VERSION",
    "CANONICAL_PROTEIN_GLYCAN_WINDOW_TABLE_KIND",
    "CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME",
    "DatasetCanonicalResidueMappingBinding",
    "DatasetCanonicalResidueMappingBindings",
    "CanonicalProteinEdgeWindowRow",
    "CanonicalProteinEdgeWindowTable",
    "CanonicalProteinLipidWindowRow",
    "CanonicalProteinLipidWindowTable",
    "CanonicalProteinGlycanWindowRow",
    "CanonicalProteinGlycanWindowTable",
    "CanonicalWindowTableError",
    "build_canonical_protein_edge_window_table",
    "build_canonical_protein_lipid_window_table",
    "build_canonical_protein_glycan_window_table",
]
