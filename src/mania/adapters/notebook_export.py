"""Minimal notebook export adapters."""

import csv
import math
from collections.abc import Sequence
from pathlib import Path

from mania.constants import RG_TIMESERIES_COLUMNS
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
    if fieldnames is None:
        raise NotebookExportAdapterError(f"CSV file is empty: {input_path}")

    missing_columns = [
        column for column in NOTEBOOK_RG_COLUMNS if column not in fieldnames
    ]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise NotebookExportAdapterError(
            f"Missing notebook Rg columns in {input_path}: {missing_text}"
        )


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
    "export_rg_timeseries",
]
