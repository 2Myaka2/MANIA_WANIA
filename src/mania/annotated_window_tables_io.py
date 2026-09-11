"""Strict, deterministic, atomic CSV I/O for Stage 30.D annotated tables."""

import csv
import io
import stat
from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from mania.annotated_window_tables import (
    ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME,
    ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME,
    ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME,
    AnnotatedCanonicalProteinEdgeWindowRow,
    AnnotatedCanonicalProteinEdgeWindowTable,
    AnnotatedCanonicalProteinGlycanWindowRow,
    AnnotatedCanonicalProteinGlycanWindowTable,
    AnnotatedCanonicalProteinLipidWindowRow,
    AnnotatedCanonicalProteinLipidWindowTable,
)
from mania.canonical_window_tables_io import _parse as _parse_canonical_cell
from mania.preprocessing.molecular_partner_metadata_io import write_atomic_text
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationIssue as AnnotatedWindowCsvValidationIssue,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvValidationReport as AnnotatedWindowCsvValidationReport,
)
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvWriteResult as AnnotatedWindowCsvWriteResult,
)
from mania.preprocessing.protein_edge_window_table_io import (
    _serialize,
)

ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(AnnotatedCanonicalProteinEdgeWindowRow)
)
ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(AnnotatedCanonicalProteinLipidWindowRow)
)
ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS = tuple(
    item.name for item in fields(AnnotatedCanonicalProteinGlycanWindowRow)
)

_Table = TypeVar(
    "_Table",
    AnnotatedCanonicalProteinEdgeWindowTable,
    AnnotatedCanonicalProteinLipidWindowTable,
    AnnotatedCanonicalProteinGlycanWindowTable,
)


class AnnotatedWindowCsvReadError(ValueError):
    """Invalid canonical CSV structure, scalars, reference, identity, or order."""


def _parse(name: str, value: str) -> Any:
    annotation_name = name.removeprefix("source_").removeprefix("target_")
    if (
        annotation_name.startswith("is_")
        or annotation_name == "glycosylation_present_in_topology"
    ):
        if value == "" and annotation_name == "glycosylation_present_in_topology":
            return None
        if value not in ("true", "false"):
            raise ValueError("Invalid boolean cell")
        return value == "true"
    if annotation_name in (
        "glycan_name",
        "glycosylation_source",
        "glycosylation_verifier",
    ):
        return value or None
    return _parse_canonical_cell(name, value)


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
        raise AnnotatedWindowCsvReadError(
            "Invalid or unreadable annotated canonical window CSV."
        ) from None


def read_annotated_canonical_protein_edge_window_csv(
    path: str | Path,
) -> AnnotatedCanonicalProteinEdgeWindowTable:
    return _read(
        path,
        ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
        AnnotatedCanonicalProteinEdgeWindowRow,
        AnnotatedCanonicalProteinEdgeWindowTable,
    )


def read_annotated_canonical_protein_lipid_window_csv(
    path: str | Path,
) -> AnnotatedCanonicalProteinLipidWindowTable:
    return _read(
        path,
        ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
        AnnotatedCanonicalProteinLipidWindowRow,
        AnnotatedCanonicalProteinLipidWindowTable,
    )


def read_annotated_canonical_protein_glycan_window_csv(
    path: str | Path,
) -> AnnotatedCanonicalProteinGlycanWindowTable:
    return _read(
        path,
        ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
        AnnotatedCanonicalProteinGlycanWindowRow,
        AnnotatedCanonicalProteinGlycanWindowTable,
    )


def _write(
    table: _Table,
    output_dir: str | Path,
    overwrite: bool,
    table_type: type[_Table],
    columns: tuple[str, ...],
    filename: str,
) -> AnnotatedWindowCsvWriteResult:
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
        return AnnotatedWindowCsvWriteResult(target, result.written, result.error)
    except (csv.Error, TypeError, ValueError, OverflowError):
        return AnnotatedWindowCsvWriteResult(target, False, "CSV serialization failed.")


def write_annotated_canonical_protein_edge_window_csv(
    table: AnnotatedCanonicalProteinEdgeWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> AnnotatedWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        AnnotatedCanonicalProteinEdgeWindowTable,
        ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
        ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME,
    )


def write_annotated_canonical_protein_lipid_window_csv(
    table: AnnotatedCanonicalProteinLipidWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> AnnotatedWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        AnnotatedCanonicalProteinLipidWindowTable,
        ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
        ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME,
    )


def write_annotated_canonical_protein_glycan_window_csv(
    table: AnnotatedCanonicalProteinGlycanWindowTable,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> AnnotatedWindowCsvWriteResult:
    return _write(
        table,
        output_dir,
        overwrite,
        AnnotatedCanonicalProteinGlycanWindowTable,
        ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
        ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME,
    )


def _validate(path: str | Path, reader: Any) -> AnnotatedWindowCsvValidationReport:
    target = Path(path)
    try:
        table = reader(target)
    except AnnotatedWindowCsvReadError as exc:
        return AnnotatedWindowCsvValidationReport(
            target, None, (AnnotatedWindowCsvValidationIssue("csv", str(exc)),)
        )
    return AnnotatedWindowCsvValidationReport(target, table.row_count, ())


def validate_annotated_canonical_protein_edge_window_csv(
    path: str | Path,
) -> AnnotatedWindowCsvValidationReport:
    return _validate(path, read_annotated_canonical_protein_edge_window_csv)


def validate_annotated_canonical_protein_lipid_window_csv(
    path: str | Path,
) -> AnnotatedWindowCsvValidationReport:
    return _validate(path, read_annotated_canonical_protein_lipid_window_csv)


def validate_annotated_canonical_protein_glycan_window_csv(
    path: str | Path,
) -> AnnotatedWindowCsvValidationReport:
    return _validate(path, read_annotated_canonical_protein_glycan_window_csv)


__all__ = [
    "ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_COLUMNS",
    "ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_COLUMNS",
    "ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS",
    "AnnotatedWindowCsvReadError",
    "AnnotatedWindowCsvWriteResult",
    "AnnotatedWindowCsvValidationIssue",
    "AnnotatedWindowCsvValidationReport",
    "read_annotated_canonical_protein_edge_window_csv",
    "write_annotated_canonical_protein_edge_window_csv",
    "validate_annotated_canonical_protein_edge_window_csv",
    "read_annotated_canonical_protein_lipid_window_csv",
    "write_annotated_canonical_protein_lipid_window_csv",
    "validate_annotated_canonical_protein_lipid_window_csv",
    "read_annotated_canonical_protein_glycan_window_csv",
    "write_annotated_canonical_protein_glycan_window_csv",
    "validate_annotated_canonical_protein_glycan_window_csv",
]
