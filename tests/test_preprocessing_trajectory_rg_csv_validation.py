import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionRgResult,
    PreprocessingRgCsvValidationIssue,
    PreprocessingRgCsvValidationResult,
    PreprocessingRgFrameResult,
    validate_rg_timeseries_csv,
    write_rg_timeseries_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_rg_export_validation.py"
)
CSV_HEADER = (
    "condition_name",
    "frame_index",
    "time_ps",
    "rg_value",
    "rg_unit",
    "frame_passed",
)
VALID_ROW = ("normal", "0", "0.0", "10.0", "angstrom", "true")


def write_csv(
    path: Path,
    rows: Sequence[Sequence[str]],
    *,
    header: Sequence[str] = CSV_HEADER,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def issue_kinds(
    result: PreprocessingRgCsvValidationResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert validate_rg_timeseries_csv is not None
    assert PreprocessingRgCsvValidationIssue is not None
    assert PreprocessingRgCsvValidationResult is not None


def test_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgCsvValidationIssue(
        kind="invalid_frame_index",
        row_number=2,
        field="frame_index",
        message="Invalid frame index.",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "invalid_frame_index",
        "row_number": 2,
        "field": "frame_index",
        "message": "Invalid frame index.",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_result_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgCsvValidationIssue(
        kind="missing_file",
        row_number=None,
        field="csv_path",
        message="Missing file.",
    )
    result = PreprocessingRgCsvValidationResult(
        csv_path=Path("rg_timeseries.csv"),
        passed=False,
        row_count=0,
        valid_row_count=0,
        invalid_row_count=0,
        issues=(issue,),
    )

    payload = result.to_dict()

    assert payload["csv_path"] == "rg_timeseries.csv"
    assert set(payload) == {
        "csv_path",
        "passed",
        "row_count",
        "valid_row_count",
        "invalid_row_count",
        "issues",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_writer_produced_csv_passes_validation(tmp_path: Path) -> None:
    condition = PreprocessingConditionRgResult(
        condition_name="normal",
        status="computed",
        runtime_type=None,
        topology_path=None,
        trajectory_paths=(),
        frame_time_ps=None,
        rg_unit="angstrom",
        frame_results=(
            PreprocessingRgFrameResult(
                condition_name="normal",
                frame_index=0,
                time_ps=None,
                rg_value=10.0,
                rg_unit="angstrom",
            ),
            PreprocessingRgFrameResult(
                condition_name="normal",
                frame_index=1,
                time_ps=2.5,
                rg_value=11.0,
                rg_unit="angstrom",
            ),
        ),
    )
    path = tmp_path / "rg_timeseries.csv"
    write_result = write_rg_timeseries_csv(condition, path)

    result = validate_rg_timeseries_csv(path)

    assert write_result.passed is True
    assert result.passed is True
    assert result.row_count == 2
    assert result.valid_row_count == 2
    assert result.invalid_row_count == 0
    assert result.issues == ()


def test_missing_file_fails_with_file_level_issue(tmp_path: Path) -> None:
    result = validate_rg_timeseries_csv(tmp_path / "missing.csv")

    assert result.passed is False
    assert issue_kinds(result) == ["missing_file"]
    assert result.issues[0].row_number is None
    assert result.row_count == 0


def test_directory_path_fails(tmp_path: Path) -> None:
    result = validate_rg_timeseries_csv(tmp_path)

    assert issue_kinds(result) == ["not_file"]
    assert result.issues[0].row_number is None


def test_empty_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "rg_timeseries.csv"
    path.write_text("", encoding="utf-8")

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["empty_file"]


def test_non_utf8_file_fails_with_read_error(tmp_path: Path) -> None:
    path = tmp_path / "rg_timeseries.csv"
    path.write_bytes(b"\xff\xfe")

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["read_error"]
    assert result.issues[0].row_number is None


def test_invalid_header_fails(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        (VALID_ROW,),
        header=("condition", "frame"),
    )

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["invalid_header"]
    assert result.row_count == 0


def test_no_data_rows_fails(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "rg_timeseries.csv", ())

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["no_data_rows"]
    assert result.row_count == 0


@pytest.mark.parametrize(
    "row",
    [
        ("normal", "0", "0.0"),
        ("normal", "0", "0.0", "10.0", "angstrom", "true", "extra"),
    ],
)
def test_invalid_column_count_fails(
    tmp_path: Path,
    row: tuple[str, ...],
) -> None:
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert "invalid_column_count" in issue_kinds(result)
    assert result.row_count == 1
    assert result.invalid_row_count == 1


def test_missing_condition_name_fails(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "rg_timeseries.csv",
        (("", "0", "0.0", "10.0", "angstrom", "true"),),
    )

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["missing_condition_name"]


@pytest.mark.parametrize(
    "value",
    ["", "-1", "1.5", "true", "false", "9" * 5000],
)
def test_invalid_frame_index_fails(tmp_path: Path, value: str) -> None:
    row = ("normal", value, "0.0", "10.0", "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert "invalid_frame_index" in issue_kinds(result)


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "-inf", "invalid"])
def test_invalid_time_fails(tmp_path: Path, value: str) -> None:
    row = ("normal", "0", value, "10.0", "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["invalid_time_ps"]


def test_empty_time_is_valid(tmp_path: Path) -> None:
    row = ("normal", "0", "", "10.0", "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert result.passed is True


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "-inf", "invalid"])
def test_invalid_rg_value_fails(tmp_path: Path, value: str) -> None:
    row = ("normal", "0", "0.0", value, "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["invalid_rg_value"]


def test_empty_rg_value_is_valid_for_failed_frame(tmp_path: Path) -> None:
    row = ("normal", "0", "0.0", "", "", "false")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert result.passed is True


def test_empty_rg_value_fails_for_passed_frame(tmp_path: Path) -> None:
    row = ("normal", "0", "0.0", "", "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["passed_frame_missing_rg_value"]


def test_empty_rg_unit_fails_for_passed_frame(tmp_path: Path) -> None:
    row = ("normal", "0", "0.0", "10.0", "", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["passed_frame_missing_rg_unit"]


def test_empty_rg_unit_is_valid_for_failed_frame(tmp_path: Path) -> None:
    row = ("normal", "0", "0.0", "10.0", "", "false")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert result.passed is True


def test_whitespace_only_rg_unit_fails_without_missing_issue(
    tmp_path: Path,
) -> None:
    row = ("normal", "0", "0.0", "10.0", "   ", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["invalid_rg_unit"]


@pytest.mark.parametrize(
    "value",
    ["TRUE", "True", "FALSE", "False", "1", "0", "yes", "no", ""],
)
def test_invalid_frame_passed_fails(tmp_path: Path, value: str) -> None:
    row = ("normal", "0", "0.0", "10.0", "angstrom", value)
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["invalid_frame_passed"]


def test_non_monotonic_frame_index_is_reported(tmp_path: Path) -> None:
    rows = (
        ("normal", "0", "0.0", "10.0", "angstrom", "true"),
        ("normal", "2", "2.0", "12.0", "angstrom", "true"),
        ("tumor", "0", "0.0", "9.0", "angstrom", "true"),
        ("normal", "1", "1.0", "11.0", "angstrom", "true"),
    )
    path = write_csv(tmp_path / "rg_timeseries.csv", rows)

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == ["non_monotonic_frame_index"]
    assert result.issues[0].row_number == 5
    assert result.valid_row_count == 3
    assert result.invalid_row_count == 1


def test_repeated_frame_index_is_allowed(tmp_path: Path) -> None:
    rows = (
        VALID_ROW,
        ("normal", "0", "1.0", "11.0", "angstrom", "true"),
    )
    path = write_csv(tmp_path / "rg_timeseries.csv", rows)

    result = validate_rg_timeseries_csv(path)

    assert result.passed is True
    assert result.valid_row_count == 2


def test_multiple_row_issues_are_collected(tmp_path: Path) -> None:
    row = ("", "-1", "nan", "invalid", "   ", "TRUE")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert issue_kinds(result) == [
        "missing_condition_name",
        "invalid_frame_index",
        "invalid_time_ps",
        "invalid_rg_value",
        "invalid_rg_unit",
        "invalid_frame_passed",
    ]
    assert {issue.row_number for issue in result.issues} == {2}


def test_valid_and_invalid_row_counts_are_deterministic(
    tmp_path: Path,
) -> None:
    rows = (
        VALID_ROW,
        ("normal", "-1", "1.0", "11.0", "angstrom", "true"),
        ("tumor", "0", "", "", "", "false"),
    )
    path = write_csv(tmp_path / "rg_timeseries.csv", rows)

    result = validate_rg_timeseries_csv(path)

    assert result.row_count == 3
    assert result.valid_row_count == 2
    assert result.invalid_row_count == 1


def test_first_data_row_uses_human_readable_row_number(
    tmp_path: Path,
) -> None:
    row = ("normal", "-1", "0.0", "10.0", "angstrom", "true")
    path = write_csv(tmp_path / "rg_timeseries.csv", (row,))

    result = validate_rg_timeseries_csv(path)

    assert result.issues[0].row_number == 2


def test_validation_does_not_modify_csv(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "rg_timeseries.csv", (VALID_ROW,))
    content_before = path.read_bytes()

    validate_rg_timeseries_csv(path)

    assert path.read_bytes() == content_before


def test_validation_module_avoids_scientific_operations_and_writer() -> None:
    source_text = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "radius_of_gyration",
        "compute_condition_rg",
        "compute_manifest_rg",
        "write_rg_timeseries_csv",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
    ):
        assert forbidden_text not in source_text


def test_validation_module_avoids_later_stage_features() -> None:
    source_text = VALIDATION_MODULE_PATH.read_text(encoding="utf-8").lower()

    for forbidden_text in (
        "comparison",
        "tolerance",
        "contacts",
        "graph",
        "edges",
        "nodes",
    ):
        assert forbidden_text not in source_text


def test_validation_module_has_no_forbidden_scientific_imports() -> None:
    source_text = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    for package_name in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert f"import {package_name}" not in source_text
        assert f"from {package_name}" not in source_text
