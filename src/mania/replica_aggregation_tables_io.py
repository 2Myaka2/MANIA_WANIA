"""Strict deterministic CSV exports for Dataset-level replica aggregates."""

import csv
import io
from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from mania import replica_aggregation_tables as tables
from mania.preprocessing.molecular_partner_metadata_io import write_atomic_text
from mania.preprocessing.protein_edge_window_table_io import (
    _FLOAT,
    _INTEGER,
    _serialize,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationIssue as ReplicaAggregationCsvValidationIssue,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationReport as CsvValidationReport,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvWriteResult as ReplicaAggregationCsvWriteResult,
)

CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_CSV_COLUMNS = tuple(
    f.name for f in fields(tables.CanonicalProteinEdgeReplicaAggregationRow)
)
CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_CSV_COLUMNS = tuple(
    f.name for f in fields(tables.CanonicalProteinLipidReplicaAggregationRow)
)
CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_CSV_COLUMNS = tuple(
    f.name for f in fields(tables.CanonicalProteinGlycanReplicaAggregationRow)
)

_Table = TypeVar(
    "_Table",
    tables.CanonicalProteinEdgeReplicaAggregationTable,
    tables.CanonicalProteinLipidReplicaAggregationTable,
    tables.CanonicalProteinGlycanReplicaAggregationTable,
)
_INTEGERS = {
    "window_index",
    "source_canonical_residue_number",
    "target_canonical_residue_number",
    "canonical_residue_number",
    "n_replicates_available",
    "n_replicates_supporting",
}
_FLOATS = {
    "requested_production_start_ns",
    "requested_production_end_ns",
    "requested_window_start_ns",
    "requested_window_end_ns",
    "window_length_ns",
    "window_step_ns",
    "overlap_percent",
    "mean_occupancy",
    "std_occupancy",
    "median_occupancy",
    "support_fraction",
}


class ReplicaAggregationCsvReadError(ValueError):
    """Invalid aggregate schema, scalar, identity, reference, order or statistics."""


def _parse(name: str, value: str) -> Any:
    if name in ("condition", "disulfide_state", "std_occupancy") and value == "":
        return None
    if name == "right_endpoint_inclusive":
        if value not in ("true", "false"):
            raise ValueError("Expected lowercase boolean")
        return value == "true"
    if name in _INTEGERS:
        if not _INTEGER.fullmatch(value):
            raise ValueError("Invalid integer")
        return int(value)
    if name in _FLOATS:
        if not _FLOAT.fullmatch(value):
            raise ValueError("Invalid finite float")
        return float(value)
    return value


def _read(path: str | Path, table_type: type[_Table]) -> _Table:
    try:
        row_type = table_type._row_type
        columns = tuple(f.name for f in fields(row_type))
        with Path(path).open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != columns:
                raise ValueError("Invalid exact CSV header")
            rows = tuple(
                row_type(
                    **{
                        name: _parse(name, value)
                        for name, value in zip(columns, cells, strict=True)
                    }
                )
                for cells in reader
            )
        return table_type(rows)
    except (OSError, ValueError, TypeError, OverflowError, csv.Error):
        raise ReplicaAggregationCsvReadError(
            "Invalid or unreadable canonical replica aggregation CSV."
        ) from None


def replica_aggregation_csv_bytes(table: _Table) -> bytes:
    if type(table) not in (
        tables.CanonicalProteinEdgeReplicaAggregationTable,
        tables.CanonicalProteinLipidReplicaAggregationTable,
        tables.CanonicalProteinGlycanReplicaAggregationTable,
    ):
        raise ValueError("Expected exact aggregate table")
    table.__post_init__()
    columns = tuple(f.name for f in fields(table._row_type))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    for row in table.rows:
        writer.writerow(_serialize(getattr(row, name)) for name in columns)
    return stream.getvalue().encode("utf-8")


def _write(
    table: _Table,
    output_dir: str | Path,
    overwrite: bool,
    table_type: type[_Table],
    filename: str,
) -> ReplicaAggregationCsvWriteResult:
    if type(table) is not table_type:
        raise ValueError("Expected exact aggregate table type")
    payload = replica_aggregation_csv_bytes(table).decode("utf-8")
    target = Path(output_dir) / filename
    result = write_atomic_text(payload, target, overwrite=overwrite)
    return ReplicaAggregationCsvWriteResult(target, result.written, result.error)


def _validate(path: str | Path, reader: Any) -> CsvValidationReport:
    try:
        table = reader(path)
    except ReplicaAggregationCsvReadError as exc:
        return CsvValidationReport(
            Path(path), None, (ReplicaAggregationCsvValidationIssue("csv", str(exc)),)
        )
    return CsvValidationReport(Path(path), table.row_count, ())


def read_canonical_protein_edge_replica_aggregation_csv(
    path: str | Path,
) -> tables.CanonicalProteinEdgeReplicaAggregationTable:
    return _read(path, tables.CanonicalProteinEdgeReplicaAggregationTable)


def write_canonical_protein_edge_replica_aggregation_csv(
    table: tables.CanonicalProteinEdgeReplicaAggregationTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ReplicaAggregationCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        tables.CanonicalProteinEdgeReplicaAggregationTable,
        tables.CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_CSV_FILENAME,
    )


def validate_canonical_protein_edge_replica_aggregation_csv(
    path: str | Path,
) -> CsvValidationReport:
    return _validate(path, read_canonical_protein_edge_replica_aggregation_csv)


def read_canonical_protein_lipid_replica_aggregation_csv(
    path: str | Path,
) -> tables.CanonicalProteinLipidReplicaAggregationTable:
    return _read(path, tables.CanonicalProteinLipidReplicaAggregationTable)


def write_canonical_protein_lipid_replica_aggregation_csv(
    table: tables.CanonicalProteinLipidReplicaAggregationTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ReplicaAggregationCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        tables.CanonicalProteinLipidReplicaAggregationTable,
        tables.CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_CSV_FILENAME,
    )


def validate_canonical_protein_lipid_replica_aggregation_csv(
    path: str | Path,
) -> CsvValidationReport:
    return _validate(path, read_canonical_protein_lipid_replica_aggregation_csv)


def read_canonical_protein_glycan_replica_aggregation_csv(
    path: str | Path,
) -> tables.CanonicalProteinGlycanReplicaAggregationTable:
    return _read(path, tables.CanonicalProteinGlycanReplicaAggregationTable)


def write_canonical_protein_glycan_replica_aggregation_csv(
    table: tables.CanonicalProteinGlycanReplicaAggregationTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ReplicaAggregationCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        tables.CanonicalProteinGlycanReplicaAggregationTable,
        tables.CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_CSV_FILENAME,
    )


def validate_canonical_protein_glycan_replica_aggregation_csv(
    path: str | Path,
) -> CsvValidationReport:
    return _validate(path, read_canonical_protein_glycan_replica_aggregation_csv)
