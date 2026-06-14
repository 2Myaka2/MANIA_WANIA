import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionRgResult,
    PreprocessingManifestRgResult,
    PreprocessingRgComputationIssue,
    PreprocessingRgCsvValidationIssue,
    PreprocessingRgCsvValidationResult,
    PreprocessingRgCsvWriteIssue,
    PreprocessingRgCsvWriteResult,
    PreprocessingRgFrameResult,
    PreprocessingRgReferenceComparisonInput,
    PreprocessingRgReferenceComparisonResult,
    PreprocessingRgReportBundle,
    PreprocessingRgReportBundleIssue,
    PreprocessingRgReportBundleSummary,
    build_rg_report_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_rg_report.py"
)


def make_frame(
    condition_name: str,
    frame_index: int,
    *,
    passed: bool = True,
) -> PreprocessingRgFrameResult:
    issues: tuple[PreprocessingRgComputationIssue, ...] = ()
    rg_value: float | None = 10.0 + frame_index
    if not passed:
        rg_value = None
        issues = (
            PreprocessingRgComputationIssue(
                kind="rg_computation_error",
                condition_name=condition_name,
                frame_index=frame_index,
                field="rg_value",
                message="Expected Rg failure.",
            ),
        )
    return PreprocessingRgFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=float(frame_index),
        rg_value=rg_value,
        rg_unit="angstrom" if passed else None,
        issues=issues,
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frame_passes: tuple[bool, ...] = (True, True),
) -> PreprocessingConditionRgResult:
    return PreprocessingConditionRgResult(
        condition_name=condition_name,
        status="computed",
        runtime_type=None,
        topology_path=None,
        trajectory_paths=(),
        frame_time_ps=1.0,
        rg_unit="angstrom",
        frame_results=tuple(
            make_frame(condition_name, index, passed=passed)
            for index, passed in enumerate(frame_passes)
        ),
    )


def make_write_result(
    *,
    passed: bool = True,
    rows_written: int = 2,
) -> PreprocessingRgCsvWriteResult:
    issues = (
        ()
        if passed
        else (
            PreprocessingRgCsvWriteIssue(
                kind="write_error",
                field="output_path",
                message="Expected write failure.",
            ),
        )
    )
    return PreprocessingRgCsvWriteResult(
        output_path=Path("rg_timeseries.csv"),
        passed=passed,
        rows_written=rows_written,
        condition_count=1,
        frame_count=2,
        skipped_frame_count=max(0, 2 - rows_written),
        issues=issues,
    )


def make_validation_result(
    *,
    passed: bool = True,
    row_count: int = 2,
) -> PreprocessingRgCsvValidationResult:
    issues = (
        ()
        if passed
        else (
            PreprocessingRgCsvValidationIssue(
                kind="invalid_header",
                row_number=None,
                field="header",
                message="Expected validation failure.",
            ),
        )
    )
    return PreprocessingRgCsvValidationResult(
        csv_path=Path("rg_timeseries.csv"),
        passed=passed,
        row_count=row_count,
        valid_row_count=row_count if passed else 0,
        invalid_row_count=0 if passed else row_count,
        issues=issues,
    )


def make_comparison_result(
    *,
    passed: bool = True,
    actual_row_count: int = 2,
    matched_row_count: int = 2,
    failed_row_count: int = 0,
) -> PreprocessingRgReferenceComparisonResult:
    comparison_input = PreprocessingRgReferenceComparisonInput(
        actual_csv_path=Path("actual.csv"),
        reference_csv_path=Path("reference.csv"),
    )
    return PreprocessingRgReferenceComparisonResult(
        comparison_input=comparison_input,
        passed=passed,
        input_validation_passed=True,
        actual_row_count=actual_row_count,
        reference_row_count=2,
        matched_row_count=matched_row_count,
        passed_row_count=matched_row_count - failed_row_count,
        failed_row_count=failed_row_count,
        missing_actual_row_count=0,
        missing_reference_row_count=0,
        extra_actual_row_count=0,
        extra_reference_row_count=0,
        max_rg_abs_difference=0.25,
        max_rg_rel_difference=0.025,
        max_time_abs_difference=0.5,
        row_results=(),
        issues=(),
    )


def empty_summary() -> PreprocessingRgReportBundleSummary:
    return PreprocessingRgReportBundleSummary(
        computation_present=False,
        computation_passed=None,
        condition_count=0,
        computed_condition_count=0,
        failed_condition_count=0,
        frame_count=0,
        passed_frame_count=0,
        failed_frame_count=0,
        csv_write_present=False,
        csv_write_passed=None,
        csv_rows_written=None,
        csv_validation_present=False,
        csv_validation_passed=None,
        csv_validation_row_count=None,
        comparison_present=False,
        comparison_passed=None,
        comparison_matched_row_count=None,
        comparison_failed_row_count=None,
        max_rg_abs_difference=None,
        max_rg_rel_difference=None,
        max_time_abs_difference=None,
    )


def issue_kinds(bundle: PreprocessingRgReportBundle) -> list[str]:
    return [issue.kind for issue in bundle.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingRgReportBundleIssue is not None
    assert PreprocessingRgReportBundleSummary is not None
    assert PreprocessingRgReportBundle is not None
    assert build_rg_report_bundle is not None


def test_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgReportBundleIssue(
        kind="inconsistent_export_counts",
        field="csv_write_result.rows_written",
        message="Counts differ.",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "inconsistent_export_counts",
        "field": "csv_write_result.rows_written",
        "message": "Counts differ.",
    }
    json.dumps(payload)


def test_summary_to_dict_is_json_serializable() -> None:
    payload = empty_summary().to_dict()

    assert payload["computation_present"] is False
    assert payload["comparison_failed_row_count"] is None
    json.dumps(payload)


def test_empty_bundle_is_deterministic() -> None:
    bundle = build_rg_report_bundle()

    assert isinstance(bundle, PreprocessingRgReportBundle)
    assert bundle.passed is False
    assert bundle.summary == empty_summary()
    assert issue_kinds(bundle) == ["missing_computation_result"]
    json.dumps(bundle.to_dict())


def test_manifest_computation_summary_counts_conditions_and_frames() -> None:
    result = PreprocessingManifestRgResult(
        condition_results=(
            make_condition("normal"),
            make_condition("tumor", frame_passes=(True, False)),
        )
    )

    bundle = build_rg_report_bundle(computation_result=result)
    summary = bundle.summary

    assert summary.computation_present is True
    assert summary.computation_passed is result.passed
    assert summary.condition_count == 2
    assert summary.computed_condition_count == 1
    assert summary.failed_condition_count == 1
    assert summary.frame_count == 4
    assert summary.passed_frame_count == 3
    assert summary.failed_frame_count == 1


def test_condition_computation_summary_counts_one_condition() -> None:
    result = make_condition(frame_passes=(True, False))

    summary = build_rg_report_bundle(computation_result=result).summary

    assert summary.condition_count == 1
    assert summary.computed_condition_count == 0
    assert summary.failed_condition_count == 1
    assert summary.frame_count == 2
    assert summary.passed_frame_count == 1
    assert summary.failed_frame_count == 1


def test_csv_write_result_is_summarized() -> None:
    write_result = make_write_result(rows_written=1)

    summary = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_write_result=write_result,
    ).summary

    assert summary.csv_write_present is True
    assert summary.csv_write_passed is True
    assert summary.csv_rows_written == 1


def test_csv_validation_result_is_summarized() -> None:
    validation_result = make_validation_result(row_count=3)

    summary = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_validation_result=validation_result,
    ).summary

    assert summary.csv_validation_present is True
    assert summary.csv_validation_passed is True
    assert summary.csv_validation_row_count == 3


def test_comparison_result_is_summarized() -> None:
    comparison_result = make_comparison_result(
        matched_row_count=2,
        failed_row_count=1,
    )

    summary = build_rg_report_bundle(
        computation_result=make_condition(),
        comparison_result=comparison_result,
    ).summary

    assert summary.comparison_present is True
    assert summary.comparison_passed is comparison_result.passed
    assert summary.comparison_matched_row_count == 2
    assert summary.comparison_failed_row_count == 1
    assert summary.max_rg_abs_difference == 0.25
    assert summary.max_rg_rel_difference == 0.025
    assert summary.max_time_abs_difference == 0.5


def test_full_passing_bundle_has_no_issues() -> None:
    bundle = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_write_result=make_write_result(),
        csv_validation_result=make_validation_result(),
        comparison_result=make_comparison_result(),
    )

    assert bundle.passed is True
    assert bundle.issues == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"computation_result": make_condition(frame_passes=(False,))},
        {
            "computation_result": make_condition(),
            "csv_write_result": make_write_result(passed=False),
        },
        {
            "computation_result": make_condition(),
            "csv_validation_result": make_validation_result(passed=False),
        },
        {
            "computation_result": make_condition(),
            "comparison_result": make_comparison_result(
                passed=False,
                failed_row_count=1,
            ),
        },
    ],
)
def test_bundle_fails_when_a_provided_result_fails(
    kwargs: dict[str, object],
) -> None:
    bundle = build_rg_report_bundle(**kwargs)  # type: ignore[arg-type]

    assert bundle.passed is False


def test_write_validation_count_inconsistency_is_reported() -> None:
    bundle = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_write_result=make_write_result(rows_written=2),
        csv_validation_result=make_validation_result(row_count=1),
    )

    assert issue_kinds(bundle) == ["inconsistent_validation_counts"]


def test_impossible_export_count_is_reported() -> None:
    bundle = build_rg_report_bundle(
        computation_result=make_condition(frame_passes=(True,)),
        csv_write_result=make_write_result(rows_written=2),
    )

    assert issue_kinds(bundle) == ["inconsistent_export_counts"]


def test_validation_comparison_count_inconsistency_is_reported() -> None:
    bundle = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_validation_result=make_validation_result(row_count=2),
        comparison_result=make_comparison_result(actual_row_count=1),
    )

    assert issue_kinds(bundle) == ["inconsistent_validation_counts"]


def test_bundle_serializes_nested_reports_through_to_dict() -> None:
    bundle = build_rg_report_bundle(
        computation_result=make_condition(),
        csv_write_result=make_write_result(),
        csv_validation_result=make_validation_result(),
        comparison_result=make_comparison_result(),
    )

    payload = bundle.to_dict()

    assert isinstance(payload["summary"], dict)
    assert isinstance(payload["computation_result"], dict)
    assert isinstance(payload["csv_write_result"], dict)
    assert isinstance(payload["csv_validation_result"], dict)
    assert isinstance(payload["comparison_result"], dict)
    assert payload["passed"] is True
    json.dumps(payload)


@pytest.mark.parametrize(
    ("field_name", "expected_kind"),
    [
        ("computation_result", "invalid_computation_result"),
        ("csv_write_result", "invalid_write_result"),
        ("csv_validation_result", "invalid_validation_result"),
        ("comparison_result", "invalid_comparison_result"),
    ],
)
def test_invalid_input_types_produce_deterministic_issues(
    field_name: str,
    expected_kind: str,
) -> None:
    kwargs: dict[str, object] = {
        "computation_result": make_condition(),
        field_name: object(),
    }
    if field_name == "computation_result":
        kwargs = {field_name: object()}

    bundle = build_rg_report_bundle(**kwargs)  # type: ignore[arg-type]

    assert issue_kinds(bundle) == [expected_kind]
    present_field = {
        "computation_result": "computation_present",
        "csv_write_result": "csv_write_present",
        "csv_validation_result": "csv_validation_present",
        "comparison_result": "comparison_present",
    }[field_name]
    assert getattr(bundle.summary, present_field) is False


def test_source_stays_inside_in_memory_report_boundary() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8")
    lowered = source_text.lower()

    for forbidden_text in (
        "runtime_object",
        "Universe",
        "MDAnalysis",
        "compute_condition_rg",
        "compute_manifest_rg",
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
        "validate_rg_reference_comparison_input",
        "compare_rg_timeseries_csv",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
        "contacts",
        "graph",
        "edges",
        "nodes",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden_text.lower() not in lowered
