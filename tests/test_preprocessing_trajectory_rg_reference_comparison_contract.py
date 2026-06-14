import json
from pathlib import Path

import pytest

import mania.preprocessing
import mania.preprocessing.trajectory_rg_reference_comparison as comparison_module
from mania.preprocessing import (
    PreprocessingConditionRgResult,
    PreprocessingRgCsvValidationResult,
    PreprocessingRgFrameResult,
    PreprocessingRgReferenceComparisonInput,
    PreprocessingRgReferenceComparisonInputValidationResult,
    PreprocessingRgReferenceComparisonIssue,
    PreprocessingRgReferenceComparisonOptions,
    validate_rg_reference_comparison_input,
    write_rg_timeseries_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_rg_reference_comparison.py"
)
TOLERANCE_FIELDS = (
    "rg_abs_tolerance",
    "rg_rel_tolerance",
    "time_abs_tolerance",
)
BOOLEAN_FIELDS = (
    "require_matching_units",
    "require_matching_frame_indexes",
    "require_matching_condition_names",
    "allow_extra_actual_rows",
    "allow_extra_reference_rows",
)


def write_valid_rg_csv(
    path: Path,
    *,
    rg_values: tuple[float, ...] = (10.0,),
    time_values: tuple[float, ...] | None = None,
) -> Path:
    if time_values is None:
        time_values = tuple(float(index) for index in range(len(rg_values)))
    condition_result = PreprocessingConditionRgResult(
        condition_name="normal",
        status="computed",
        runtime_type=None,
        topology_path=None,
        trajectory_paths=(),
        frame_time_ps=None,
        rg_unit="angstrom",
        frame_results=tuple(
            PreprocessingRgFrameResult(
                condition_name="normal",
                frame_index=index,
                time_ps=time_value,
                rg_value=rg_value,
                rg_unit="angstrom",
            )
            for index, (time_value, rg_value) in enumerate(
                zip(time_values, rg_values, strict=True)
            )
        ),
    )
    result = write_rg_timeseries_csv(condition_result, path)
    assert result.passed is True
    return path


def make_input(
    actual_csv_path: str | Path,
    reference_csv_path: str | Path,
) -> PreprocessingRgReferenceComparisonInput:
    return PreprocessingRgReferenceComparisonInput(
        actual_csv_path=actual_csv_path,
        reference_csv_path=reference_csv_path,
    )


def issue_kinds(
    result: PreprocessingRgReferenceComparisonInputValidationResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingRgReferenceComparisonOptions is not None
    assert PreprocessingRgReferenceComparisonInput is not None
    assert PreprocessingRgReferenceComparisonIssue is not None
    assert PreprocessingRgReferenceComparisonInputValidationResult is not None
    assert validate_rg_reference_comparison_input is not None


def test_options_default_serialization_is_json_serializable() -> None:
    options = PreprocessingRgReferenceComparisonOptions()

    payload = options.to_dict()

    assert payload == {
        "rg_abs_tolerance": 1e-6,
        "rg_rel_tolerance": 1e-6,
        "time_abs_tolerance": 1e-6,
        "require_matching_units": True,
        "require_matching_frame_indexes": True,
        "require_matching_condition_names": True,
        "allow_extra_actual_rows": False,
        "allow_extra_reference_rows": False,
    }
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize("field_name", TOLERANCE_FIELDS)
@pytest.mark.parametrize(
    "invalid_value",
    [-1.0, float("nan"), float("inf"), float("-inf"), True, "1e-6"],
)
def test_options_reject_invalid_tolerances(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingRgReferenceComparisonOptions(
            **{field_name: invalid_value}
        )


@pytest.mark.parametrize("field_name", BOOLEAN_FIELDS)
@pytest.mark.parametrize(
    "invalid_value",
    [0, 1, "true", "false", None],
)
def test_options_reject_invalid_booleans(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingRgReferenceComparisonOptions(
            **{field_name: invalid_value}
        )


def test_input_normalizes_paths_and_serializes() -> None:
    comparison_input = make_input("actual.csv", "reference.csv")

    payload = comparison_input.to_dict()

    assert comparison_input.actual_csv_path == Path("actual.csv")
    assert comparison_input.reference_csv_path == Path("reference.csv")
    assert payload["actual_csv_path"] == "actual.csv"
    assert payload["reference_csv_path"] == "reference.csv"
    assert json.loads(json.dumps(payload)) == payload


def test_input_rejects_invalid_options_object() -> None:
    with pytest.raises(ValueError):
        PreprocessingRgReferenceComparisonInput(
            actual_csv_path=Path("actual.csv"),
            reference_csv_path=Path("reference.csv"),
            options={},
        )


def test_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgReferenceComparisonIssue(
        kind="missing_actual_csv",
        field="actual_csv_path",
        message="Actual CSV is missing.",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "missing_actual_csv",
        "field": "actual_csv_path",
        "message": "Actual CSV is missing.",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_validation_result_to_dict_is_json_serializable() -> None:
    comparison_input = make_input("actual.csv", "reference.csv")
    issue = PreprocessingRgReferenceComparisonIssue(
        kind="missing_reference_csv",
        field="reference_csv_path",
        message="Reference CSV is missing.",
    )
    result = PreprocessingRgReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        passed=False,
        actual_csv_validation_passed=None,
        reference_csv_validation_passed=None,
        issues=(issue,),
    )

    payload = result.to_dict()

    assert payload["comparison_input"] == comparison_input.to_dict()
    assert payload["issues"] == [issue.to_dict()]
    assert json.loads(json.dumps(payload)) == payload


def test_validation_rejects_invalid_input_type() -> None:
    with pytest.raises(ValueError):
        validate_rg_reference_comparison_input({})


def test_missing_actual_csv_fails(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("arbitrary", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(tmp_path / "missing.csv", reference_path),
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["missing_actual_csv"]
    assert result.actual_csv_validation_passed is None


def test_missing_reference_csv_fails(tmp_path: Path) -> None:
    actual_path = tmp_path / "actual.csv"
    actual_path.write_text("arbitrary", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, tmp_path / "missing.csv"),
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["missing_reference_csv"]
    assert result.reference_csv_validation_passed is None


def test_directory_actual_path_fails(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("arbitrary", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(tmp_path, reference_path),
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["actual_csv_not_file"]


def test_directory_reference_path_fails(tmp_path: Path) -> None:
    actual_path = tmp_path / "actual.csv"
    actual_path.write_text("arbitrary", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, tmp_path),
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["reference_csv_not_file"]


def test_same_actual_and_reference_path_fails(tmp_path: Path) -> None:
    path = tmp_path / "rg.csv"
    path.write_text("arbitrary", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(path, path),
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["same_actual_and_reference_path"]


def test_distinct_files_pass_without_csv_contract_validation(
    tmp_path: Path,
) -> None:
    actual_path = tmp_path / "actual.csv"
    reference_path = tmp_path / "reference.csv"
    actual_path.write_text("actual", encoding="utf-8")
    reference_path.write_text("reference", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path),
        validate_csv_contract=False,
    )

    assert result.passed is True
    assert result.actual_csv_validation_passed is None
    assert result.reference_csv_validation_passed is None
    assert result.issues == ()


def test_writer_produced_csvs_pass_contract_validation(
    tmp_path: Path,
) -> None:
    actual_path = write_valid_rg_csv(tmp_path / "actual.csv")
    reference_path = write_valid_rg_csv(tmp_path / "reference.csv")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert result.passed is True
    assert result.actual_csv_validation_passed is True
    assert result.reference_csv_validation_passed is True
    assert result.issues == ()


def test_invalid_actual_csv_contract_fails(tmp_path: Path) -> None:
    actual_path = tmp_path / "actual.csv"
    actual_path.write_text("invalid", encoding="utf-8")
    reference_path = write_valid_rg_csv(tmp_path / "reference.csv")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert issue_kinds(result) == ["actual_csv_validation_failed"]
    assert result.actual_csv_validation_passed is False
    assert result.reference_csv_validation_passed is True


def test_invalid_reference_csv_contract_fails(tmp_path: Path) -> None:
    actual_path = write_valid_rg_csv(tmp_path / "actual.csv")
    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("invalid", encoding="utf-8")

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert issue_kinds(result) == ["reference_csv_validation_failed"]
    assert result.actual_csv_validation_passed is True
    assert result.reference_csv_validation_passed is False


def test_validation_does_not_compare_numeric_rg_values(
    tmp_path: Path,
) -> None:
    actual_path = write_valid_rg_csv(
        tmp_path / "actual.csv",
        rg_values=(10.0,),
    )
    reference_path = write_valid_rg_csv(
        tmp_path / "reference.csv",
        rg_values=(999.0,),
    )

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert result.passed is True


def test_validation_does_not_compare_time_values(tmp_path: Path) -> None:
    actual_path = write_valid_rg_csv(
        tmp_path / "actual.csv",
        time_values=(0.0,),
    )
    reference_path = write_valid_rg_csv(
        tmp_path / "reference.csv",
        time_values=(500.0,),
    )

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert result.passed is True


def test_validation_does_not_compare_row_counts(tmp_path: Path) -> None:
    actual_path = write_valid_rg_csv(
        tmp_path / "actual.csv",
        rg_values=(10.0,),
    )
    reference_path = write_valid_rg_csv(
        tmp_path / "reference.csv",
        rg_values=(10.0, 11.0),
    )

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert result.passed is True


def test_skipped_csv_contract_does_not_call_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_path = tmp_path / "actual.csv"
    reference_path = tmp_path / "reference.csv"
    actual_path.write_text("actual", encoding="utf-8")
    reference_path.write_text("reference", encoding="utf-8")

    def fail_if_called(path: str | Path) -> PreprocessingRgCsvValidationResult:
        raise AssertionError(f"validator called for {path}")

    monkeypatch.setattr(
        comparison_module,
        "validate_rg_timeseries_csv",
        fail_if_called,
    )

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path),
        validate_csv_contract=False,
    )

    assert result.passed is True


def test_csv_contract_validation_calls_validator_for_each_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_path = tmp_path / "actual.csv"
    reference_path = tmp_path / "reference.csv"
    actual_path.write_text("actual", encoding="utf-8")
    reference_path.write_text("reference", encoding="utf-8")
    called_paths: list[Path] = []

    def passing_validator(
        path: str | Path,
    ) -> PreprocessingRgCsvValidationResult:
        csv_path = Path(path)
        called_paths.append(csv_path)
        return PreprocessingRgCsvValidationResult(
            csv_path=csv_path,
            passed=True,
            row_count=1,
            valid_row_count=1,
            invalid_row_count=0,
            issues=(),
        )

    monkeypatch.setattr(
        comparison_module,
        "validate_rg_timeseries_csv",
        passing_validator,
    )

    result = validate_rg_reference_comparison_input(
        make_input(actual_path, reference_path)
    )

    assert result.passed is True
    assert called_paths == [actual_path, reference_path]


def test_defensive_invalid_options_issue_is_reported(tmp_path: Path) -> None:
    actual_path = tmp_path / "actual.csv"
    reference_path = tmp_path / "reference.csv"
    actual_path.write_text("actual", encoding="utf-8")
    reference_path.write_text("reference", encoding="utf-8")
    comparison_input = make_input(actual_path, reference_path)
    object.__setattr__(comparison_input, "options", object())

    result = validate_rg_reference_comparison_input(
        comparison_input,
        validate_csv_contract=False,
    )

    assert issue_kinds(result) == ["invalid_options"]
    json.dumps(result.to_dict())


def test_source_has_no_numeric_or_row_comparison_implementation() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8").lower()

    for forbidden_text in (
        "relative_error",
        "delta_rg",
        "rg_difference",
        "matched_rows",
        "mismatch",
    ):
        assert forbidden_text not in source_text


def test_source_has_no_rg_computation_or_runtime_loading() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "write_rg_timeseries_csv",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
    ):
        assert forbidden_text not in source_text


def test_source_has_no_contacts_or_graph_work() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8").lower()

    for forbidden_text in ("contacts", "graph", "edges", "nodes"):
        assert forbidden_text not in source_text


def test_source_has_no_forbidden_scientific_imports() -> None:
    source_text = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden_text not in source_text
