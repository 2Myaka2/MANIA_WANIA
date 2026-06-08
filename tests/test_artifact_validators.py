import csv
from collections.abc import Sequence
from pathlib import Path

from mania.constants import CENTRALITY_COLUMNS, RG_TIMESERIES_COLUMNS
from mania.validation.artifacts import (
    ArtifactValidationError,
    read_csv_header,
    validate_condition_column,
    validate_csv_artifact_schema,
)


def write_csv(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[str]] = (),
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_valid_artifact_schema_passes(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition"),
        (("0", "0.0", "12.3", "normal"),),
    )

    result = validate_csv_artifact_schema(path, "rg_timeseries.csv")

    assert result.is_valid
    assert result.artifact_name == "rg_timeseries.csv"
    assert result.missing_columns == ()
    assert result.duplicate_columns == ()
    assert result.extra_columns == ()
    assert result.expected_columns == RG_TIMESERIES_COLUMNS


def test_required_column_order_is_not_enforced(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("condition", "rg_A", "frame", "time_ps"),
    )

    result = validate_csv_artifact_schema(path, "rg_timeseries.csv")

    assert result.is_valid


def test_missing_column_fails(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "rg_timeseries.csv", ("frame", "rg_A", "condition"))

    try:
        validate_csv_artifact_schema(path, "rg_timeseries.csv")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_extra_column_fails_by_default(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition", "extra"),
    )

    try:
        validate_csv_artifact_schema(path, "rg_timeseries.csv")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_extra_column_can_be_allowed(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition", "extra"),
    )

    result = validate_csv_artifact_schema(
        path,
        "rg_timeseries.csv",
        allow_extra_columns=True,
    )

    assert result.is_valid
    assert result.extra_columns == ("extra",)
    assert result.allow_extra_columns is True


def test_duplicate_column_fails(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition", "frame"),
    )

    try:
        validate_csv_artifact_schema(path, "rg_timeseries.csv")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_unknown_artifact_fails_without_expected_columns(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "unknown.csv", ("a", "b"))

    try:
        validate_csv_artifact_schema(path, "unknown.csv")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_unknown_artifact_can_use_explicit_expected_columns(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "custom.csv", ("b", "a"))

    result = validate_csv_artifact_schema(
        path,
        "custom.csv",
        expected_columns=("a", "b"),
    )

    assert result.is_valid


def test_empty_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    try:
        read_csv_header(path)
    except ArtifactValidationError:
        pass
    else:
        raise AssertionError("Expected ArtifactValidationError")

    try:
        validate_csv_artifact_schema(path, "rg_timeseries.csv")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_condition_column_validation_passes(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition"),
        (
            ("0", "0.0", "12.3", "normal"),
            ("1", "1.0", "12.4", "normal"),
        ),
    )

    validate_condition_column(path, "normal")


def test_missing_condition_column_fails(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "rg_timeseries.csv", ("frame", "time_ps", "rg_A"))

    try:
        validate_condition_column(path, "normal")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_mixed_condition_values_fail(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition"),
        (
            ("0", "0.0", "12.3", "normal"),
            ("1", "1.0", "12.4", "tumor"),
        ),
    )

    try:
        validate_condition_column(path, "normal")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_empty_condition_value_fails(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        ("frame", "time_ps", "rg_A", "condition"),
        (("0", "0.0", "12.3", ""),),
    )

    try:
        validate_condition_column(path, "normal")
    except ArtifactValidationError:
        return
    raise AssertionError("Expected ArtifactValidationError")


def test_another_contract_artifact_schema_passes(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "centrality.csv", CENTRALITY_COLUMNS)

    result = validate_csv_artifact_schema(path, "centrality.csv")

    assert result.is_valid
