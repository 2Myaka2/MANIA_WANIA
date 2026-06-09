"""Minimal notebook export adapters."""

import csv
import math
from collections.abc import Sequence
from pathlib import Path

from mania.constants import (
    CENTRALITY_COLUMNS,
    COMMUNITIES_COLUMNS,
    RG_TIMESERIES_COLUMNS,
)
from mania.validation.artifacts import (
    ArtifactValidationError,
    validate_condition_column,
    validate_csv_artifact_schema,
)

NOTEBOOK_RG_COLUMNS = ("frame", "rg_A", "condition")


class NotebookExportAdapterError(Exception):
    """Raised when notebook export adaptation fails."""


def export_rg_timeseries(
    source_dir: str | Path,
    output_dir: str | Path,
    condition: str,
    *,
    frame_time_ps: float,
) -> Path:
    """Export notebook-like Rg timeseries to the backend contract layout."""
    frame_time = _validate_frame_time_ps(frame_time_ps)
    input_path = Path(source_dir) / f"rg_timeseries_{condition}.csv"
    if not input_path.is_file():
        raise NotebookExportAdapterError(f"Missing Rg timeseries input: {input_path}")

    rows = _read_notebook_rg_rows(input_path, condition, frame_time)

    output_path = Path(output_dir) / condition / "rg_timeseries.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=RG_TIMESERIES_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    try:
        validate_csv_artifact_schema(output_path, "rg_timeseries.csv")
        validate_condition_column(output_path, condition)
    except ArtifactValidationError as exc:
        raise NotebookExportAdapterError(
            f"Output Rg timeseries failed validation: {output_path}"
        ) from exc

    return output_path


def export_centrality(
    source_dir: str | Path,
    output_dir: str | Path,
    condition: str,
) -> Path:
    """Export notebook-like centrality rows to the backend contract layout."""
    return _export_contract_csv_table(
        source_dir=source_dir,
        output_dir=output_dir,
        condition=condition,
        input_name=f"centrality_{condition}.csv",
        output_name="centrality.csv",
        output_columns=CENTRALITY_COLUMNS,
    )


def export_communities(
    source_dir: str | Path,
    output_dir: str | Path,
    condition: str,
) -> Path:
    """Export notebook-like community rows to the backend contract layout."""
    return _export_contract_csv_table(
        source_dir=source_dir,
        output_dir=output_dir,
        condition=condition,
        input_name=f"communities_{condition}.csv",
        output_name="communities.csv",
        output_columns=COMMUNITIES_COLUMNS,
    )


def _export_contract_csv_table(
    source_dir: str | Path,
    output_dir: str | Path,
    condition: str,
    *,
    input_name: str,
    output_name: str,
    output_columns: Sequence[str],
) -> Path:
    input_path = Path(source_dir) / input_name
    if not input_path.is_file():
        raise NotebookExportAdapterError(f"Missing notebook export input: {input_path}")

    rows = _read_contract_like_rows(input_path, condition, output_columns)

    output_path = Path(output_dir) / condition / output_name
    _write_contract_rows(output_path, output_columns, rows)
    _validate_output_csv(output_path, output_name, condition)
    return output_path


def _read_contract_like_rows(
    input_path: Path,
    condition: str,
    output_columns: Sequence[str],
) -> list[dict[str, str]]:
    with input_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        _validate_required_header(reader.fieldnames, output_columns, input_path)

        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            if _is_empty_data_row(row):
                continue

            row_condition = _validate_row_condition(
                row,
                condition,
                input_path,
                row_number,
            )
            rows.append(
                {
                    column: row[column] if row[column] is not None else ""
                    for column in output_columns
                }
            )
            rows[-1]["condition"] = row_condition

    if not rows:
        raise NotebookExportAdapterError(f"No data rows found: {input_path}")
    return rows


def _read_notebook_rg_rows(
    input_path: Path,
    condition: str,
    frame_time_ps: float,
) -> list[dict[str, str]]:
    with input_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        _validate_notebook_rg_header(reader.fieldnames, input_path)

        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            if _is_empty_data_row(row):
                continue

            row_condition = _validate_row_condition(
                row,
                condition,
                input_path,
                row_number,
            )

            frame = row.get("frame")
            frame_value = _parse_frame(frame, input_path, row_number)

            rg_value = row.get("rg_A")
            _validate_rg_value(rg_value, input_path, row_number)

            rows.append(
                {
                    "frame": frame if frame is not None else "",
                    "time_ps": _format_time_ps(frame_value * frame_time_ps),
                    "rg_A": rg_value if rg_value is not None else "",
                    "condition": row_condition,
                }
            )

    return rows


def _validate_frame_time_ps(frame_time_ps: object) -> float:
    if isinstance(frame_time_ps, bool) or not isinstance(frame_time_ps, int | float):
        raise NotebookExportAdapterError(
            f"frame_time_ps must be a positive finite number: {frame_time_ps!r}"
        )
    frame_time = float(frame_time_ps)
    if not math.isfinite(frame_time) or frame_time <= 0:
        raise NotebookExportAdapterError(
            f"frame_time_ps must be a positive finite number: {frame_time_ps!r}"
        )
    return frame_time


def _validate_notebook_rg_header(
    fieldnames: Sequence[str] | None,
    input_path: Path,
) -> None:
    _validate_required_header(fieldnames, NOTEBOOK_RG_COLUMNS, input_path)


def _validate_required_header(
    fieldnames: Sequence[str] | None,
    required_columns: Sequence[str],
    input_path: Path,
) -> None:
    if fieldnames is None:
        raise NotebookExportAdapterError(f"CSV file is empty: {input_path}")

    missing_columns = [
        column for column in required_columns if column not in fieldnames
    ]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise NotebookExportAdapterError(
            f"Missing notebook export columns in {input_path}: {missing_text}"
        )


def _validate_row_condition(
    row: dict[str, str | None],
    condition: str,
    input_path: Path,
    row_number: int,
) -> str:
    row_condition = row.get("condition")
    if row_condition is None or row_condition.strip() == "":
        raise NotebookExportAdapterError(
            f"Missing condition value at row {row_number}: {input_path}"
        )
    if row_condition != condition:
        raise NotebookExportAdapterError(
            "Mismatched condition value at "
            f"row {row_number}: expected {condition!r}, got {row_condition!r}"
        )
    return row_condition


def _write_contract_rows(
    output_path: Path,
    output_columns: Sequence[str],
    rows: Sequence[dict[str, str]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(rows)


def _validate_output_csv(
    output_path: Path,
    artifact_name: str,
    condition: str,
) -> None:
    try:
        validate_csv_artifact_schema(output_path, artifact_name)
        validate_condition_column(output_path, condition)
    except ArtifactValidationError as exc:
        raise NotebookExportAdapterError(
            f"Output artifact failed validation: {output_path}"
        ) from exc


def _parse_frame(frame: str | None, input_path: Path, row_number: int) -> int:
    if frame is None or frame.strip() == "":
        raise NotebookExportAdapterError(
            f"Missing frame value at row {row_number}: {input_path}"
        )
    try:
        return int(frame)
    except ValueError as exc:
        raise NotebookExportAdapterError(
            f"Invalid frame value at row {row_number}: {frame!r}"
        ) from exc


def _validate_rg_value(
    rg_value: str | None,
    input_path: Path,
    row_number: int,
) -> None:
    if rg_value is None or rg_value.strip() == "":
        raise NotebookExportAdapterError(
            f"Missing rg_A value at row {row_number}: {input_path}"
        )
    try:
        parsed = float(rg_value)
    except ValueError as exc:
        raise NotebookExportAdapterError(
            f"Invalid rg_A value at row {row_number}: {rg_value!r}"
        ) from exc
    if not math.isfinite(parsed):
        raise NotebookExportAdapterError(
            f"Non-finite rg_A value at row {row_number}: {rg_value!r}"
        )


def _format_time_ps(time_ps: float) -> str:
    if time_ps.is_integer():
        return str(int(time_ps))
    return format(time_ps, "g")


def _is_empty_data_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value.strip() == "" for value in row.values())


__all__ = [
    "NotebookExportAdapterError",
    "export_centrality",
    "export_communities",
    "export_rg_timeseries",
]
