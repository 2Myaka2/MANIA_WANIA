"""Strict, deterministic, atomic CSV I/O for Stage 30.C intermediate tables."""

import csv
import io
import stat
from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from mania.canonical_window_tables import (
    CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME,
    CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME,
    CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME,
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
)
from mania.preprocessing.molecular_partner_metadata_io import write_atomic_text
from mania.preprocessing.protein_edge_window_table_io import (
    _FLOAT,
    _INTEGER,
    _serialize,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationIssue as CanonicalWindowCsvValidationIssue,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationReport as CanonicalWindowCsvValidationReport,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvWriteResult as CanonicalWindowCsvWriteResult,
)
from mania.preprocessing.specialized_contact_window_tables_io import (
    _parse as _parse_source_cell,
)

CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(CanonicalProteinEdgeWindowRow)
)
CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(CanonicalProteinLipidWindowRow)
)
CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(CanonicalProteinGlycanWindowRow)
)

_Table = TypeVar(
    "_Table",
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinLipidWindowTable,
    CanonicalProteinGlycanWindowTable,
)


class CanonicalWindowCsvReadError(ValueError):
    """Invalid canonical CSV structure, scalars, reference, identity, or order."""


def _parse(name: str, value: str) -> Any:
    if name in ("source_chain_id", "target_chain_id"):
        return _parse_source_cell("protein_chain_id", value)
    if name in (
        "source_residue_index",
        "target_residue_index",
        "canonical_residue_number",
        "source_canonical_residue_number",
        "target_canonical_residue_number",
    ):
        if not _INTEGER.fullmatch(value):
            raise ValueError("Invalid integer cell")
        return int(value)
    if name == "edge_weight":
        if not _FLOAT.fullmatch(value):
            raise ValueError("Invalid numeric cell")
        return float(value)
    return _parse_source_cell(name, value)


def _read(
    path: str | Path,
    columns: tuple[str, ...],
    row_type: type[Any],
    table_type: type[_Table],
) -> _Table:
    try:
        if not isinstance(path, (str, Path)) or path == "":
            raise ValueError("Expected a path")
        target = Path(path)
        if not stat.S_ISREG(target.stat().st_mode):
            raise ValueError("Expected a regular CSV file")
        with target.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != columns:
                raise ValueError("Invalid exact CSV header")
            rows = []
            for cells in reader:
                values = {
                    name: _parse(name, value)
                    for name, value in zip(columns, cells, strict=True)
                }
                rows.append(row_type(**values))
        # Construction checks existing canonical order; reading never sorts.
        return table_type(tuple(rows))
    except (OSError, csv.Error, ValueError, TypeError, OverflowError):
        raise CanonicalWindowCsvReadError(
            "Invalid or unreadable canonical window CSV."
        ) from None


def read_canonical_protein_edge_window_csv(
    path: str | Path,
) -> CanonicalProteinEdgeWindowTable:
    return _read(
        path,
        CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
        CanonicalProteinEdgeWindowRow,
        CanonicalProteinEdgeWindowTable,
    )


def read_canonical_protein_lipid_window_csv(
    path: str | Path,
) -> CanonicalProteinLipidWindowTable:
    return _read(
        path,
        CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
        CanonicalProteinLipidWindowRow,
        CanonicalProteinLipidWindowTable,
    )


def read_canonical_protein_glycan_window_csv(
    path: str | Path,
) -> CanonicalProteinGlycanWindowTable:
    return _read(
        path,
        CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
        CanonicalProteinGlycanWindowRow,
        CanonicalProteinGlycanWindowTable,
    )


def _write(
    table: _Table,
    output_dir: str | Path,
    overwrite: bool,
    table_type: type[_Table],
    columns: tuple[str, ...],
    filename: str,
) -> CanonicalWindowCsvWriteResult:
    if type(table) is not table_type:
        raise ValueError(f"table must be exact {table_type.__name__}")
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be a bool")
    if not isinstance(output_dir, (str, Path)) or output_dir == "":
        raise ValueError("output_dir must be a Path or non-empty string")
    # Revalidate before any filesystem mutation, including frozen-object bypasses.
    table.__post_init__()
    target = Path(output_dir) / filename
    try:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        for row in table.rows:
            writer.writerow(
                ";".join(str(i) for i in getattr(row, name))
                if name.endswith("component_residue_indexes")
                else _serialize(getattr(row, name))
                for name in columns
            )
        result = write_atomic_text(stream.getvalue(), target, overwrite=overwrite)
        return CanonicalWindowCsvWriteResult(target, result.written, result.error)
    except (csv.Error, TypeError, ValueError, OverflowError):
        return CanonicalWindowCsvWriteResult(target, False, "CSV serialization failed.")


def write_canonical_protein_edge_window_csv(
    table: CanonicalProteinEdgeWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> CanonicalWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        CanonicalProteinEdgeWindowTable,
        CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
        CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME,
    )


def write_canonical_protein_lipid_window_csv(
    table: CanonicalProteinLipidWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> CanonicalWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        CanonicalProteinLipidWindowTable,
        CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
        CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME,
    )


def write_canonical_protein_glycan_window_csv(
    table: CanonicalProteinGlycanWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> CanonicalWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        CanonicalProteinGlycanWindowTable,
        CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
        CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME,
    )


def _validate(path: str | Path, reader: Any) -> CanonicalWindowCsvValidationReport:
    target = Path(path)
    try:
        table = reader(target)
    except CanonicalWindowCsvReadError as exc:
        return CanonicalWindowCsvValidationReport(
            target, None, (CanonicalWindowCsvValidationIssue("csv", str(exc)),)
        )
    return CanonicalWindowCsvValidationReport(target, table.row_count, ())


def validate_canonical_protein_edge_window_csv(
    path: str | Path,
) -> CanonicalWindowCsvValidationReport:
    return _validate(path, read_canonical_protein_edge_window_csv)


def validate_canonical_protein_lipid_window_csv(
    path: str | Path,
) -> CanonicalWindowCsvValidationReport:
    return _validate(path, read_canonical_protein_lipid_window_csv)


def validate_canonical_protein_glycan_window_csv(
    path: str | Path,
) -> CanonicalWindowCsvValidationReport:
    return _validate(path, read_canonical_protein_glycan_window_csv)


__all__ = [
    "CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS",
    "CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS",
    "CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS",
    "CanonicalWindowCsvReadError",
    "CanonicalWindowCsvWriteResult",
    "CanonicalWindowCsvValidationIssue",
    "CanonicalWindowCsvValidationReport",
    "read_canonical_protein_edge_window_csv",
    "write_canonical_protein_edge_window_csv",
    "validate_canonical_protein_edge_window_csv",
    "read_canonical_protein_lipid_window_csv",
    "write_canonical_protein_lipid_window_csv",
    "validate_canonical_protein_lipid_window_csv",
    "read_canonical_protein_glycan_window_csv",
    "write_canonical_protein_glycan_window_csv",
    "validate_canonical_protein_glycan_window_csv",
]
