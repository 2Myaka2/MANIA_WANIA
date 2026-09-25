"""Pure Stage 33.C projections of accepted canonical science into frozen schemas."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
)
from mania.dataset_release_contract import REPLICA_KEY, SYSTEM_KEY, WINDOW_KEY
from mania.dataset_release_csv import (
    DatasetReleaseTable,
    PublicationScalar,
    build_publication_table,
    publication_table_spec,
)
from mania.dataset_release_metadata import DatasetReleaseMetadataTables
from mania.replica_aggregation_tables import (
    CanonicalProteinEdgeReplicaAggregationTable,
    CanonicalProteinGlycanReplicaAggregationTable,
    CanonicalProteinLipidReplicaAggregationTable,
)

if TYPE_CHECKING:
    from mania.dataset_release_aggregates import DatasetReleaseAggregationAuthority
    from mania.dataset_release_metrics import AuthoritativePublicationMetric

_LABELS = ("engine", "variant_id", "condition", "disulfide_state")


class DatasetReleaseScienceError(ValueError):
    """Missing publication authority or inconsistent scientific relationships."""


def require_publication_reference(model: object) -> None:
    """Check accepted reference evidence without loading or mapping residues."""
    for name, expected in (
        ("canonical_reference_id", CANONICAL_RESIDUE_MAPPING_REFERENCE_ID),
        (
            "canonical_reference_sequence_sha256",
            CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
        ),
    ):
        if getattr(model, name, None) != expected:
            raise DatasetReleaseScienceError("Canonical reference must match exactly")


def _key(
    row: Mapping[str, PublicationScalar], names: tuple[str, ...]
) -> tuple[PublicationScalar, ...]:
    return tuple(row[n] for n in names)


def publication_metadata_index(
    metadata_tables: DatasetReleaseMetadataTables, table_id: str
) -> dict[tuple[PublicationScalar, ...], dict[str, PublicationScalar]]:
    """Validate and index an in-scope accepted metadata table, without mutation."""
    if type(metadata_tables) is not DatasetReleaseMetadataTables:
        raise DatasetReleaseScienceError("Expected Stage 33.B metadata tables")
    table = getattr(metadata_tables, table_id)
    if type(table) is not DatasetReleaseTable or table.table_id != table_id:
        raise DatasetReleaseScienceError("Metadata table identity must match its slot")
    validated = DatasetReleaseTable(table.spec, table.rows)
    return {_key(r, table.spec.primary_key): r for r in validated.records()}


def validate_dataset_release_scientific_relationships(
    tables: Iterable[DatasetReleaseTable],
    metadata_tables: DatasetReleaseMetadataTables,
) -> None:
    """Validate only science/aggregate/metric links to the supplied 33.B tables."""
    indexes = {
        name: publication_metadata_index(metadata_tables, name)
        for name in ("systems", "simulations", "time_windows", "nodes")
    }
    for table in tables:
        validated = DatasetReleaseTable(table.spec, table.rows)
        for row in validated.records():
            global_metric = table.table_id == "metrics" and row["window_id"] is None
            if table.table_id == "metrics" and (
                (row["window_id"] is None) != (row["window_index"] is None)
            ):
                raise DatasetReleaseScienceError("Metric window fields must pair")
            for fk in table.spec.foreign_keys:
                if global_metric and fk.target_table == "time_windows":
                    continue
                target = indexes[fk.target_table].get(_key(row, fk.local_columns))
                if target is None:
                    raise DatasetReleaseScienceError(
                        f"Invalid {table.table_id} -> {fk.target_table} foreign key"
                    )
                if fk.target_table == "nodes":
                    number = fk.local_columns[-1]
                    name = number.replace("residue_number", "resname")
                    if row[name] != target["canonical_resname"]:
                        raise DatasetReleaseScienceError(
                            "Canonical node name disagrees"
                        )
            if all(n in row for n in REPLICA_KEY):
                simulation = indexes["simulations"][_key(row, REPLICA_KEY)]
                if simulation["included_in_scientific_release"] is not True:
                    raise DatasetReleaseScienceError(
                        "Publication row requires a science-included simulation"
                    )
                identity = simulation
            else:
                identity = indexes["systems"][_key(row, SYSTEM_KEY)]
            if any(n in row and row[n] != identity[n] for n in _LABELS):
                raise DatasetReleaseScienceError("Publication identity labels disagree")
            if table.relative_path.startswith("science/"):
                window = indexes["time_windows"][_key(row, WINDOW_KEY)]
                pairs = (
                    ("requested_window_start_ns", "requested_window_start_ns"),
                    ("requested_window_end_ns", "requested_window_end_ns"),
                    ("right_endpoint_inclusive", "right_endpoint_inclusive"),
                    ("requested_sample_count", "expected_sample_count"),
                    ("resolved_frame_count", "resolved_sample_count"),
                    ("missing_sample_count", "missing_sample_count"),
                    ("coverage_fraction", "coverage_fraction"),
                )
                if any(row[a] != window[b] for a, b in pairs):
                    raise DatasetReleaseScienceError(
                        "Science requested window/denominator evidence disagrees"
                    )


def project_publication_rows(
    table_id: str, rows: Iterable[object], canonical_reference_id: str
) -> DatasetReleaseTable:
    """Select frozen columns only; all scientific values come from accepted rows."""
    spec = publication_table_spec(table_id)
    return build_publication_table(
        table_id,
        (
            {
                c.name: canonical_reference_id
                if c.name == "canonical_reference_id"
                else getattr(row, c.name)
                for c in spec.columns
            }
            for row in rows
        ),
    )


def _build_science(
    source: CanonicalProteinEdgeWindowTable
    | CanonicalProteinLipidWindowTable
    | CanonicalProteinGlycanWindowTable,
    table_type: type,
    row_type: type,
    table_id: str,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    if type(source) is not table_type:
        raise DatasetReleaseScienceError("Expected exact Stage 30 canonical table")
    require_publication_reference(source)
    if type(source.rows) is not tuple or any(
        type(row) is not row_type for row in source.rows
    ):
        raise DatasetReleaseScienceError("Expected immutable accepted canonical rows")
    simulations = publication_metadata_index(metadata_tables, "simulations")
    included = []
    for row in source.rows:
        if row.boundary_profile != metadata_tables.boundary_profile:
            raise DatasetReleaseScienceError(
                "Science temporal boundary profile differs"
            )
        simulation = simulations.get(row.replica_key)
        if simulation is None:
            raise DatasetReleaseScienceError("Unknown full replica key in science")
        if isinstance(row, CanonicalProteinEdgeWindowRow) and (
            row.edge_weight != row.occupancy
        ):
            raise DatasetReleaseScienceError("Protein edge_weight must equal occupancy")
        if simulation["included_in_scientific_release"] is True:
            included.append(row)
    table = project_publication_rows(table_id, included, source.canonical_reference_id)
    validate_dataset_release_scientific_relationships((table,), metadata_tables)
    return table


def build_dataset_release_protein_edges(
    source: CanonicalProteinEdgeWindowTable,
    *,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_science(
        source,
        CanonicalProteinEdgeWindowTable,
        CanonicalProteinEdgeWindowRow,
        "protein_edges_by_window",
        metadata_tables,
    )


def build_dataset_release_protein_lipid_contacts(
    source: CanonicalProteinLipidWindowTable,
    *,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_science(
        source,
        CanonicalProteinLipidWindowTable,
        CanonicalProteinLipidWindowRow,
        "protein_lipid_contacts_by_window",
        metadata_tables,
    )


def build_dataset_release_protein_glycan_contacts(
    source: CanonicalProteinGlycanWindowTable,
    *,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_science(
        source,
        CanonicalProteinGlycanWindowTable,
        CanonicalProteinGlycanWindowRow,
        "protein_glycan_contacts_by_window",
        metadata_tables,
    )


@dataclass(frozen=True)
class DatasetReleaseScientificTables:
    protein_edges_by_window: DatasetReleaseTable
    protein_lipid_contacts_by_window: DatasetReleaseTable
    protein_glycan_contacts_by_window: DatasetReleaseTable
    protein_edges_by_window_replica_aggregation: DatasetReleaseTable
    protein_lipid_contacts_by_window_replica_aggregation: DatasetReleaseTable
    protein_glycan_contacts_by_window_replica_aggregation: DatasetReleaseTable
    metrics: DatasetReleaseTable

    def __post_init__(self) -> None:
        for item in fields(self):
            table = getattr(self, item.name)
            if type(table) is not DatasetReleaseTable or table.table_id != item.name:
                raise DatasetReleaseScienceError("Science table must match bundle slot")
            DatasetReleaseTable(table.spec, table.rows)

    @property
    def tables(self) -> tuple[DatasetReleaseTable, ...]:
        return tuple(getattr(self, item.name) for item in fields(self))

    def to_dict(self) -> dict[str, object]:
        return {table.table_id: table.to_dict() for table in self.tables}


def build_dataset_release_scientific_tables(
    *,
    metadata_tables: DatasetReleaseMetadataTables,
    canonical_protein_edges: CanonicalProteinEdgeWindowTable,
    canonical_protein_lipid_contacts: CanonicalProteinLipidWindowTable,
    canonical_protein_glycan_contacts: CanonicalProteinGlycanWindowTable,
    aggregation_authority: "DatasetReleaseAggregationAuthority",
    protein_aggregate_table: CanonicalProteinEdgeReplicaAggregationTable,
    lipid_aggregate_table: CanonicalProteinLipidReplicaAggregationTable,
    glycan_aggregate_table: CanonicalProteinGlycanReplicaAggregationTable,
    metrics: Iterable["AuthoritativePublicationMetric"],
) -> DatasetReleaseScientificTables:
    """Expose all seven schemas, including sparse empty families; never write files."""
    from mania.dataset_release_aggregates import (
        build_dataset_release_glycan_aggregates,
        build_dataset_release_lipid_aggregates,
        build_dataset_release_protein_aggregates,
    )
    from mania.dataset_release_metrics import build_dataset_release_metrics

    return DatasetReleaseScientificTables(
        build_dataset_release_protein_edges(
            canonical_protein_edges, metadata_tables=metadata_tables
        ),
        build_dataset_release_protein_lipid_contacts(
            canonical_protein_lipid_contacts, metadata_tables=metadata_tables
        ),
        build_dataset_release_protein_glycan_contacts(
            canonical_protein_glycan_contacts, metadata_tables=metadata_tables
        ),
        build_dataset_release_protein_aggregates(
            protein_aggregate_table,
            authority=aggregation_authority,
            metadata_tables=metadata_tables,
        ),
        build_dataset_release_lipid_aggregates(
            lipid_aggregate_table,
            authority=aggregation_authority,
            metadata_tables=metadata_tables,
        ),
        build_dataset_release_glycan_aggregates(
            glycan_aggregate_table,
            authority=aggregation_authority,
            metadata_tables=metadata_tables,
        ),
        build_dataset_release_metrics(metrics, metadata_tables=metadata_tables),
    )
