import csv
from collections.abc import Sequence
from pathlib import Path

import pytest

from mania.adapters import NotebookExportAdapterError, export_rg_timeseries
from mania.constants import RG_TIMESERIES_COLUMNS
from mania.validation.artifacts import (
    validate_condition_column,
    validate_csv_artifact_schema,
)

FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return next(csv.reader(csv_file))


def write_csv(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_exports_normal_rg_timeseries(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "normal" / "rg_timeseries.csv"
    assert path.is_file()
    assert read_header(path) == list(RG_TIMESERIES_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 2
    assert [row["condition"] for row in rows] == ["normal", "normal"]
    assert [row["frame"] for row in rows] == ["0", "1"]
    assert [row["time_ps"] for row in rows] == ["0", "100"]
    assert [row["rg_A"] for row in rows] == ["35.0", "37.0"]


def test_exports_tumor_rg_timeseries(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "tumor" / "rg_timeseries.csv"
    assert path.is_file()

    rows = read_rows(path)
    assert len(rows) == 2
    assert [row["condition"] for row in rows] == ["tumor", "tumor"]


def test_exported_rg_timeseries_passes_existing_validators(tmp_path: Path) -> None:
    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=100.0,
    )

    validate_csv_artifact_schema(path, "rg_timeseries.csv")
    validate_condition_column(path, "normal")


def test_missing_source_file_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            condition="missing",
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize(
    "frame_time_ps",
    [0, -1, float("nan"), float("inf")],
)
def test_invalid_frame_time_ps_fails(
    tmp_path: Path,
    frame_time_ps: float,
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=frame_time_ps,
        )


def test_missing_notebook_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "condition"),
        (("0", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "35.0", "tumor"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_empty_condition_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "35.0", ""),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_invalid_frame_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("not-an-int", "35.0", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_invalid_rg_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "not-a-number", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize("rg_value", ["nan", "inf"])
def test_non_finite_rg_value_fails(tmp_path: Path, rg_value: str) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", rg_value, "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_decimal_frame_time_ps_works(tmp_path: Path) -> None:
    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=0.5,
    )

    rows = read_rows(path)
    assert [row["time_ps"] for row in rows] == ["0", "0.5"]


def test_output_directory_is_created(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "normal" / "rg_timeseries.csv"
    assert path.is_file()
