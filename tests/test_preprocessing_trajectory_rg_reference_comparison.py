import csv
import json
import math
from collections.abc import Sequence
from pathlib import Path

import pytest

import mania.preprocessing
import mania.preprocessing.trajectory_rg_reference_comparison as comparison_module
from mania.preprocessing import (
    PreprocessingRgReferenceComparisonInput,
    PreprocessingRgReferenceComparisonInputValidationResult,
    PreprocessingRgReferenceComparisonIssue,
    PreprocessingRgReferenceComparisonOptions,
    PreprocessingRgReferenceComparisonResult,
    PreprocessingRgReferenceComparisonRowResult,
    compare_rg_timeseries_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_rg_reference_comparison.py"
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


def compare_rows(
    tmp_path: Path,
    actual_rows: Sequence[Sequence[str]],
    reference_rows: Sequence[Sequence[str]],
    *,
    options: PreprocessingRgReferenceComparisonOptions | None = None,
    validate_csv_contract: bool = True,
) -> PreprocessingRgReferenceComparisonResult:
    actual_path = write_csv(tmp_path / "actual.csv", actual_rows)
    reference_path = write_csv(tmp_path / "reference.csv", reference_rows)
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=actual_path,
        reference_csv_path=reference_path,
        options=options or PreprocessingRgReferenceComparisonOptions(),
    )
    return compare_rg_timeseries_csv(
        comparison_input,
        validate_csv_contract=validate_csv_contract,
    )


def row_issue_kinds(
    result: PreprocessingRgReferenceComparisonResult,
) -> list[str]:
    return [
        issue.kind
        for row_result in result.row_results
        for issue in row_result.issues
    ]


def global_issue_kinds(
    result: PreprocessingRgReferenceComparisonResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingRgReferenceComparisonRowResult is not None
    assert PreprocessingRgReferenceComparisonResult is not None
    assert compare_rg_timeseries_csv is not None


def test_row_result_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgReferenceComparisonIssue(
        kind="rg_value_mismatch",
        field="rg_value",
        message="Values differ.",
    )
    row_result = PreprocessingRgReferenceComparisonRowResult(
        condition_name="normal",
        frame_index=0,
        actual_row_number=2,
        reference_row_number=2,
        actual_time_ps=0.0,
        reference_time_ps=0.0,
        time_abs_difference=0.0,
        actual_rg_value=10.0,
        reference_rg_value=11.0,
        rg_abs_difference=1.0,
        rg_rel_difference=1.0 / 11.0,
        actual_rg_unit="angstrom",
        reference_rg_unit="angstrom",
        passed=False,
        issues=(issue,),
    )

    payload = row_result.to_dict()

    assert payload["issues"] == [issue.to_dict()]
    json.dumps(payload)


def test_comparison_result_to_dict_is_json_serializable() -> None:
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=Path("actual.csv"),
        reference_csv_path=Path("reference.csv"),
    )
    result = PreprocessingRgReferenceComparisonResult(
        comparison_input=comparison_input,
        passed=False,
        input_validation_passed=False,
        actual_row_count=0,
        reference_row_count=0,
        matched_row_count=0,
        passed_row_count=0,
        failed_row_count=0,
        missing_actual_row_count=0,
        missing_reference_row_count=0,
        extra_actual_row_count=0,
        extra_reference_row_count=0,
        max_rg_abs_difference=None,
        max_rg_rel_difference=None,
        max_time_abs_difference=None,
        row_results=(),
        issues=(),
    )

    payload = result.to_dict()

    assert payload["comparison_input"] == comparison_input.to_dict()
    json.dumps(payload)


def test_identical_valid_csvs_pass(tmp_path: Path) -> None:
    rows = (
        VALID_ROW,
        ("normal", "1", "1.0", "11.0", "angstrom", "true"),
    )

    result = compare_rows(tmp_path, rows, rows)

    assert result.passed is True
    assert result.matched_row_count == 2
    assert result.failed_row_count == 0
    assert result.max_rg_abs_difference == 0.0
    assert result.max_rg_rel_difference == 0.0
    assert result.max_time_abs_difference == 0.0


def test_absolute_rg_tolerance_can_pass(tmp_path: Path) -> None:
    options = PreprocessingRgReferenceComparisonOptions(
        rg_abs_tolerance=0.2,
        rg_rel_tolerance=0.0,
    )

    result = compare_rows(
        tmp_path,
        (("normal", "0", "0.0", "10.1", "angstrom", "true"),),
        (VALID_ROW,),
        options=options,
    )

    assert result.passed is True
    assert result.max_rg_abs_difference == pytest.approx(0.1)


def test_relative_rg_tolerance_can_pass(tmp_path: Path) -> None:
    options = PreprocessingRgReferenceComparisonOptions(
        rg_abs_tolerance=0.0,
        rg_rel_tolerance=0.02,
    )

    result = compare_rows(
        tmp_path,
        (("normal", "0", "0.0", "101.0", "angstrom", "true"),),
        (("normal", "0", "0.0", "100.0", "angstrom", "true"),),
        options=options,
    )

    assert result.passed is True
    assert result.max_rg_abs_difference == 1.0
    assert result.max_rg_rel_difference == 0.01


def test_rg_difference_outside_tolerances_fails(tmp_path: Path) -> None:
    result = compare_rows(
        tmp_path,
        (("normal", "0", "0.0", "12.0", "angstrom", "true"),),
        (VALID_ROW,),
    )

    assert result.passed is False
    assert "rg_value_mismatch" in row_issue_kinds(result)


@pytest.mark.parametrize(
    ("actual_value", "expected_relative", "expected_passed"),
    [
        ("0.0", 0.0, True),
        ("1.0", float("inf"), False),
    ],
)
def test_zero_reference_relative_difference_is_deterministic(
    tmp_path: Path,
    actual_value: str,
    expected_relative: float,
    expected_passed: bool,
) -> None:
    result = compare_rows(
        tmp_path,
        (("normal", "0", "0.0", actual_value, "angstrom", "true"),),
        (("normal", "0", "0.0", "0.0", "angstrom", "true"),),
    )

    relative = result.row_results[0].rg_rel_difference
    if math.isinf(expected_relative):
        assert relative is not None and math.isinf(relative)
    else:
        assert relative == expected_relative
    assert result.passed is expected_passed
    json.dumps(result.to_dict())


def test_time_tolerance_and_presence_policies(tmp_path: Path) -> None:
    within = compare_rows(
        tmp_path,
        (("normal", "0", "1.05", "10.0", "angstrom", "true"),),
        (("normal", "0", "1.0", "10.0", "angstrom", "true"),),
        options=PreprocessingRgReferenceComparisonOptions(
            time_abs_tolerance=0.1
        ),
    )
    outside = compare_rows(
        tmp_path,
        (("normal", "0", "1.2", "10.0", "angstrom", "true"),),
        (("normal", "0", "1.0", "10.0", "angstrom", "true"),),
        options=PreprocessingRgReferenceComparisonOptions(
            time_abs_tolerance=0.1
        ),
    )
    presence = compare_rows(
        tmp_path,
        (("normal", "0", "", "10.0", "angstrom", "true"),),
        (VALID_ROW,),
    )
    both_missing = compare_rows(
        tmp_path,
        (("normal", "0", "", "10.0", "angstrom", "true"),),
        (("normal", "0", "", "10.0", "angstrom", "true"),),
    )

    assert within.passed is True
    assert outside.passed is False
    assert "time_value_mismatch" in row_issue_kinds(outside)
    assert presence.passed is False
    assert "time_presence_mismatch" in row_issue_kinds(presence)
    assert both_missing.passed is True
    assert both_missing.max_time_abs_difference is None


def test_unit_matching_follows_options(tmp_path: Path) -> None:
    actual = (("normal", "0", "0.0", "10.0", "nm", "true"),)
    required = compare_rows(tmp_path, actual, (VALID_ROW,))
    optional = compare_rows(
        tmp_path,
        actual,
        (VALID_ROW,),
        options=PreprocessingRgReferenceComparisonOptions(
            require_matching_units=False
        ),
    )

    assert required.passed is False
    assert "rg_unit_mismatch" in row_issue_kinds(required)
    assert optional.passed is True
    assert optional.row_results[0].actual_rg_unit == "nm"


@pytest.mark.parametrize(
    ("actual_unit", "reference_unit", "expected_kind"),
    [
        ("", "angstrom", "actual_missing_rg_unit"),
        ("angstrom", "", "reference_missing_rg_unit"),
    ],
)
def test_missing_required_unit_fails(
    tmp_path: Path,
    actual_unit: str,
    reference_unit: str,
    expected_kind: str,
) -> None:
    result = compare_rows(
        tmp_path,
        (("normal", "0", "0.0", "10.0", actual_unit, "true"),),
        (("normal", "0", "0.0", "10.0", reference_unit, "true"),),
        validate_csv_contract=False,
    )

    assert result.passed is False
    assert expected_kind in row_issue_kinds(result)
    assert "rg_unit_mismatch" not in row_issue_kinds(result)


def test_missing_and_extra_rows_follow_options(tmp_path: Path) -> None:
    extra_reference = ("normal", "1", "1.0", "11.0", "angstrom", "true")
    extra_actual = ("normal", "2", "2.0", "12.0", "angstrom", "true")
    default = compare_rows(
        tmp_path,
        (VALID_ROW, extra_actual),
        (VALID_ROW, extra_reference),
    )
    allowed = compare_rows(
        tmp_path,
        (VALID_ROW, extra_actual),
        (VALID_ROW, extra_reference),
        options=PreprocessingRgReferenceComparisonOptions(
            allow_extra_actual_rows=True,
            allow_extra_reference_rows=True,
        ),
    )

    assert default.passed is False
    assert {"missing_actual_row", "extra_actual_row"} <= set(
        row_issue_kinds(default)
    )
    assert default.missing_actual_row_count == 1
    assert default.extra_reference_row_count == 1
    assert default.missing_reference_row_count == 1
    assert default.extra_actual_row_count == 1
    assert allowed.passed is True
    assert allowed.passed_row_count == 3


@pytest.mark.parametrize(
    ("side", "expected_kind"),
    [
        ("actual", "duplicate_actual_row_key"),
        ("reference", "duplicate_reference_row_key"),
    ],
)
def test_duplicate_keys_fail_deterministically(
    tmp_path: Path,
    side: str,
    expected_kind: str,
) -> None:
    duplicate_rows = (
        VALID_ROW,
        ("normal", "0", "1.0", "11.0", "angstrom", "true"),
    )
    actual_rows = duplicate_rows if side == "actual" else (VALID_ROW,)
    reference_rows = duplicate_rows if side == "reference" else (VALID_ROW,)

    result = compare_rows(tmp_path, actual_rows, reference_rows)

    assert result.passed is False
    assert expected_kind in global_issue_kinds(result)
    assert result.row_results == ()


@pytest.mark.parametrize(
    ("side", "expected_kind"),
    [
        ("actual", "actual_frame_not_passed"),
        ("reference", "reference_frame_not_passed"),
    ],
)
def test_failed_frames_fail_without_numeric_comparison(
    tmp_path: Path,
    side: str,
    expected_kind: str,
) -> None:
    failed = ("normal", "0", "0.0", "", "", "false")
    actual_rows = (failed,) if side == "actual" else (VALID_ROW,)
    reference_rows = (failed,) if side == "reference" else (VALID_ROW,)

    result = compare_rows(tmp_path, actual_rows, reference_rows)

    assert result.passed is False
    assert expected_kind in row_issue_kinds(result)
    assert result.row_results[0].rg_abs_difference is None


@pytest.mark.parametrize(
    ("side", "expected_kind"),
    [
        ("actual", "actual_missing_rg_value"),
        ("reference", "reference_missing_rg_value"),
    ],
)
def test_missing_passed_rg_values_fail(
    tmp_path: Path,
    side: str,
    expected_kind: str,
) -> None:
    missing = ("normal", "0", "0.0", "", "angstrom", "true")
    actual_rows = (missing,) if side == "actual" else (VALID_ROW,)
    reference_rows = (missing,) if side == "reference" else (VALID_ROW,)

    result = compare_rows(
        tmp_path,
        actual_rows,
        reference_rows,
        validate_csv_contract=False,
    )

    assert result.passed is False
    assert expected_kind in row_issue_kinds(result)
    assert result.row_results[0].rg_abs_difference is None


def test_contract_validation_blocks_invalid_csv(tmp_path: Path) -> None:
    actual_path = tmp_path / "actual.csv"
    actual_path.write_text("invalid", encoding="utf-8")
    reference_path = write_csv(tmp_path / "reference.csv", (VALID_ROW,))
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=actual_path,
        reference_csv_path=reference_path,
    )

    result = compare_rg_timeseries_csv(comparison_input)

    assert result.passed is False
    assert result.input_validation_passed is False
    assert result.row_results == ()
    assert global_issue_kinds(result) == [
        "input_validation_failed",
        "actual_csv_validation_failed",
    ]


def test_disabled_contract_validation_is_passed_through(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_path = write_csv(tmp_path / "actual.csv", (VALID_ROW,))
    reference_path = write_csv(tmp_path / "reference.csv", (VALID_ROW,))
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=actual_path,
        reference_csv_path=reference_path,
    )
    original = comparison_module.validate_rg_reference_comparison_input
    called_values: list[bool] = []

    def recording_validation(
        value: PreprocessingRgReferenceComparisonInput,
        *,
        validate_csv_contract: bool = True,
    ) -> PreprocessingRgReferenceComparisonInputValidationResult:
        called_values.append(validate_csv_contract)
        return original(
            value,
            validate_csv_contract=validate_csv_contract,
        )

    monkeypatch.setattr(
        comparison_module,
        "validate_rg_reference_comparison_input",
        recording_validation,
    )

    result = compare_rg_timeseries_csv(
        comparison_input,
        validate_csv_contract=False,
    )

    assert result.passed is True
    assert called_values == [False]


def test_disabled_contract_validation_reports_parse_error(
    tmp_path: Path,
) -> None:
    actual_path = tmp_path / "actual.csv"
    actual_path.write_text("invalid", encoding="utf-8")
    reference_path = write_csv(tmp_path / "reference.csv", (VALID_ROW,))
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=actual_path,
        reference_csv_path=reference_path,
    )

    result = compare_rg_timeseries_csv(
        comparison_input,
        validate_csv_contract=False,
    )

    assert result.input_validation_passed is True
    assert global_issue_kinds(result) == ["csv_parse_error"]


def test_missing_input_file_returns_empty_failed_result(tmp_path: Path) -> None:
    reference_path = write_csv(tmp_path / "reference.csv", (VALID_ROW,))
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=tmp_path / "missing.csv",
        reference_csv_path=reference_path,
    )

    result = compare_rg_timeseries_csv(comparison_input)

    assert result.passed is False
    assert result.input_validation_passed is False
    assert result.actual_row_count == 0
    assert result.reference_row_count == 0
    assert result.row_results == ()
    assert global_issue_kinds(result) == [
        "input_validation_failed",
        "missing_actual_csv",
    ]


def test_summary_maxima_counts_and_order_are_deterministic(
    tmp_path: Path,
) -> None:
    actual_rows = (
        ("normal", "0", "0.0", "10.0", "angstrom", "true"),
        ("normal", "1", "1.2", "12.0", "angstrom", "true"),
        ("normal", "3", "3.0", "13.0", "angstrom", "true"),
    )
    reference_rows = (
        ("normal", "1", "1.0", "10.0", "angstrom", "true"),
        ("normal", "0", "0.0", "10.0", "angstrom", "true"),
        ("normal", "2", "2.0", "12.0", "angstrom", "true"),
    )

    result = compare_rows(
        tmp_path,
        actual_rows,
        reference_rows,
        options=PreprocessingRgReferenceComparisonOptions(
            allow_extra_actual_rows=True,
            allow_extra_reference_rows=True,
        ),
        validate_csv_contract=False,
    )

    assert result.actual_row_count == 3
    assert result.reference_row_count == 3
    assert result.matched_row_count == 2
    assert result.passed_row_count == 3
    assert result.failed_row_count == 1
    assert result.missing_actual_row_count == 1
    assert result.missing_reference_row_count == 1
    assert result.max_rg_abs_difference == 2.0
    assert result.max_rg_rel_difference == 0.2
    assert result.max_time_abs_difference == pytest.approx(0.2)
    assert [
        (row.condition_name, row.frame_index) for row in result.row_results
    ] == [
        ("normal", 1),
        ("normal", 0),
        ("normal", 2),
        ("normal", 3),
    ]


def test_unsupported_frame_matching_mode_fails(tmp_path: Path) -> None:
    result = compare_rows(
        tmp_path,
        (VALID_ROW,),
        (VALID_ROW,),
        options=PreprocessingRgReferenceComparisonOptions(
            require_matching_frame_indexes=False
        ),
    )

    assert result.passed is False
    assert global_issue_kinds(result) == ["unsupported_matching_mode"]


def test_condition_matching_can_be_disabled_for_unique_frames(
    tmp_path: Path,
) -> None:
    result = compare_rows(
        tmp_path,
        (("actual", "0", "0.0", "10.0", "angstrom", "true"),),
        (("reference", "0", "0.0", "10.0", "angstrom", "true"),),
        options=PreprocessingRgReferenceComparisonOptions(
            require_matching_condition_names=False
        ),
    )

    assert result.passed is True
    assert result.matched_row_count == 1


def test_disabled_condition_matching_rejects_ambiguous_frames(
    tmp_path: Path,
) -> None:
    actual_rows = (
        ("normal", "0", "0.0", "10.0", "angstrom", "true"),
        ("tumor", "0", "0.0", "10.0", "angstrom", "true"),
    )

    result = compare_rows(
        tmp_path,
        actual_rows,
        (VALID_ROW,),
        options=PreprocessingRgReferenceComparisonOptions(
            require_matching_condition_names=False
        ),
    )

    assert result.passed is False
    assert "ambiguous_frame_key" in global_issue_kinds(result)


def test_source_stays_inside_exported_csv_comparison_boundary() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8")
    lowered = source_text.lower()

    for forbidden_text in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
        "write_rg_timeseries_csv",
        "report_bundle",
        "contacts",
        "graph",
        "edges",
        "nodes",
        "workflow",
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden_text.lower() not in lowered
