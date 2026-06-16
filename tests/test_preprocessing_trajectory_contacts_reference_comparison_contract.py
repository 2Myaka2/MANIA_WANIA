import csv
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingContactsReferenceComparisonInput,
    PreprocessingContactsReferenceComparisonInputValidationResult,
    PreprocessingContactsReferenceComparisonIssue,
    PreprocessingContactsReferenceComparisonOptions,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    validate_contacts_reference_comparison_input,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts_reference_comparison.py"
)
PERFRAME_HEADER = [
    "condition_name",
    "frame_index",
    "time_ps",
    "source_residue_index",
    "target_residue_index",
    "source_residue_id",
    "target_residue_id",
    "source_resname",
    "target_resname",
    "source_segid",
    "target_segid",
    "minimum_distance",
    "distance_unit",
    "atom_filter",
    "frame_passed",
]
EDGES_HEADER = [
    "condition_name",
    "source_residue_index",
    "target_residue_index",
    "source_residue_id",
    "target_residue_id",
    "source_resname",
    "target_resname",
    "source_segid",
    "target_segid",
    "contact_frame_count",
    "total_frame_count",
    "contact_frequency",
    "minimum_distance",
    "mean_minimum_distance",
    "distance_unit",
    "atom_filter",
]
TOLERANCE_FIELDS = (
    "distance_abs_tolerance",
    "distance_rel_tolerance",
    "frequency_abs_tolerance",
    "frequency_rel_tolerance",
)
BOOLEAN_FIELDS = (
    "require_exact_row_order",
    "compare_perframe",
    "compare_contact_edges",
)


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def perframe_row(**updates: str) -> list[str]:
    values = {
        "condition_name": "normal",
        "frame_index": "0",
        "time_ps": "0.0",
        "source_residue_index": "0",
        "target_residue_index": "1",
        "source_residue_id": "10",
        "target_residue_id": "11A",
        "source_resname": "ALA",
        "target_resname": "GLY",
        "source_segid": "PROA",
        "target_segid": "PROA",
        "minimum_distance": "3.25",
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
        "frame_passed": "true",
    }
    values.update(updates)
    return [values[field_name] for field_name in PERFRAME_HEADER]


def edges_row(**updates: str) -> list[str]:
    values = {
        "condition_name": "normal",
        "source_residue_index": "0",
        "target_residue_index": "1",
        "source_residue_id": "10",
        "target_residue_id": "11A",
        "source_resname": "ALA",
        "target_resname": "GLY",
        "source_segid": "PROA",
        "target_segid": "PROA",
        "contact_frame_count": "1",
        "total_frame_count": "2",
        "contact_frequency": "0.5",
        "minimum_distance": "3.0",
        "mean_minimum_distance": "3.5",
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
    }
    values.update(updates)
    return [values[field_name] for field_name in EDGES_HEADER]


def write_valid_perframe(path: Path) -> Path:
    return write_csv(path, PERFRAME_HEADER, [perframe_row()])


def write_valid_edges(path: Path) -> Path:
    return write_csv(path, EDGES_HEADER, [edges_row()])


def make_valid_input(
    tmp_path: Path,
    *,
    options: PreprocessingContactsReferenceComparisonOptions | None = None,
) -> PreprocessingContactsReferenceComparisonInput:
    return PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv=write_valid_perframe(
            tmp_path / "generated_contacts_perframe.csv"
        ),
        reference_contacts_perframe_csv=write_valid_perframe(
            tmp_path / "reference_contacts_perframe.csv"
        ),
        generated_contact_edges_csv=write_valid_edges(
            tmp_path / "generated_contact_edges.csv"
        ),
        reference_contact_edges_csv=write_valid_edges(
            tmp_path / "reference_contact_edges.csv"
        ),
        options=options or PreprocessingContactsReferenceComparisonOptions(),
    )


def issue_kinds(
    result: PreprocessingContactsReferenceComparisonInputValidationResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactsReferenceComparisonOptions is not None
    assert PreprocessingContactsReferenceComparisonInput is not None
    assert PreprocessingContactsReferenceComparisonIssue is not None
    assert (
        PreprocessingContactsReferenceComparisonInputValidationResult
        is not None
    )
    assert validate_contacts_reference_comparison_input is not None


def test_existing_contacts_writer_and_validator_apis_still_work() -> None:
    assert write_contacts_perframe_csv is not None
    assert write_contact_edges_csv is not None
    assert validate_contacts_perframe_csv is not None
    assert validate_contact_edges_csv is not None


def test_default_options_are_valid_and_json_safe() -> None:
    options = PreprocessingContactsReferenceComparisonOptions()

    payload = options.to_dict()

    assert payload == {
        "distance_abs_tolerance": 1e-9,
        "distance_rel_tolerance": 1e-9,
        "frequency_abs_tolerance": 1e-12,
        "frequency_rel_tolerance": 1e-12,
        "require_exact_row_order": False,
        "compare_perframe": True,
        "compare_contact_edges": True,
    }
    assert options.distance_abs_tolerance >= 0
    assert options.distance_rel_tolerance >= 0
    assert options.frequency_abs_tolerance >= 0
    assert options.frequency_rel_tolerance >= 0
    assert options.compare_perframe is True
    assert options.compare_contact_edges is True
    assert options.require_exact_row_order is False
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize("field_name", TOLERANCE_FIELDS)
@pytest.mark.parametrize(
    "invalid_value",
    [-1.0, float("nan"), float("inf"), float("-inf"), True, "1e-9"],
)
def test_options_reject_invalid_tolerances(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsReferenceComparisonOptions(
            **{field_name: invalid_value}
        )


@pytest.mark.parametrize("field_name", BOOLEAN_FIELDS)
@pytest.mark.parametrize("invalid_value", [0, 1, "true", "false", None])
def test_options_reject_invalid_booleans(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsReferenceComparisonOptions(
            **{field_name: invalid_value}
        )


def test_options_reject_both_comparison_targets_disabled() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsReferenceComparisonOptions(
            compare_perframe=False,
            compare_contact_edges=False,
        )


def test_input_converts_paths_to_path_and_serializes() -> None:
    comparison_input = PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv="generated_perframe.csv",
        reference_contacts_perframe_csv="reference_perframe.csv",
        generated_contact_edges_csv="generated_edges.csv",
        reference_contact_edges_csv="reference_edges.csv",
    )

    payload = comparison_input.to_dict()

    assert comparison_input.generated_contacts_perframe_csv == Path(
        "generated_perframe.csv"
    )
    assert comparison_input.reference_contacts_perframe_csv == Path(
        "reference_perframe.csv"
    )
    assert comparison_input.generated_contact_edges_csv == Path(
        "generated_edges.csv"
    )
    assert comparison_input.reference_contact_edges_csv == Path(
        "reference_edges.csv"
    )
    assert comparison_input.has_perframe_pair is True
    assert comparison_input.has_contact_edges_pair is True
    assert payload["generated_contacts_perframe_csv"] == "generated_perframe.csv"
    assert payload["reference_contacts_perframe_csv"] == "reference_perframe.csv"
    assert payload["generated_contact_edges_csv"] == "generated_edges.csv"
    assert payload["reference_contact_edges_csv"] == "reference_edges.csv"
    assert json.loads(json.dumps(payload)) == payload


def test_input_rejects_invalid_options_object() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsReferenceComparisonInput(options={})


def test_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingContactsReferenceComparisonIssue(
        kind="path_missing",
        field="generated_contacts_perframe_csv",
        message="CSV path is missing.",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "path_missing",
        "field": "generated_contacts_perframe_csv",
        "message": "CSV path is missing.",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_issue_rejects_empty_strings() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsReferenceComparisonIssue(
            kind="",
            field="csv_path",
            message="Missing.",
        )


def test_validation_result_to_dict_is_json_serializable() -> None:
    comparison_input = PreprocessingContactsReferenceComparisonInput()
    issue = PreprocessingContactsReferenceComparisonIssue(
        kind="missing_generated_perframe_csv",
        field="generated_contacts_perframe_csv",
        message="Generated per-frame CSV is missing.",
    )
    result = PreprocessingContactsReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        passed=False,
        perframe_enabled=True,
        contact_edges_enabled=False,
        issues=(issue,),
    )

    payload = result.to_dict()

    assert payload["comparison_input"] == comparison_input.to_dict()
    assert payload["issues"] == [issue.to_dict()]
    assert json.loads(json.dumps(payload)) == payload


def test_valid_input_with_both_pairs_passes(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        make_valid_input(tmp_path)
    )

    assert result.passed is True
    assert result.perframe_enabled is True
    assert result.contact_edges_enabled is True
    assert result.issues == ()


def test_valid_input_with_only_perframe_enabled_passes(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "generated.csv"
            ),
            reference_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert result.passed is True
    assert result.perframe_enabled is True
    assert result.contact_edges_enabled is False
    assert result.issues == ()


def test_valid_input_with_only_contact_edges_enabled_passes(
    tmp_path: Path,
) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contact_edges_csv=write_valid_edges(
                tmp_path / "generated.csv"
            ),
            reference_contact_edges_csv=write_valid_edges(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False
            ),
        )
    )

    assert result.passed is True
    assert result.perframe_enabled is False
    assert result.contact_edges_enabled is True
    assert result.issues == ()


def test_missing_generated_perframe_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            reference_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["missing_generated_perframe_csv"]


def test_missing_reference_perframe_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "generated.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["missing_reference_perframe_csv"]


def test_missing_generated_contact_edges_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            reference_contact_edges_csv=write_valid_edges(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False
            ),
        )
    )

    assert issue_kinds(result) == ["missing_generated_contact_edges_csv"]


def test_missing_reference_contact_edges_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contact_edges_csv=write_valid_edges(
                tmp_path / "generated.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False
            ),
        )
    )

    assert issue_kinds(result) == ["missing_reference_contact_edges_csv"]


def test_nonexistent_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=tmp_path / "missing.csv",
            reference_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["path_missing"]


def test_directory_path_fails(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=tmp_path,
            reference_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["path_is_directory"]


def test_same_generated_and_reference_path_fails(tmp_path: Path) -> None:
    path = write_valid_perframe(tmp_path / "contacts_perframe.csv")

    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=path,
            reference_contacts_perframe_csv=path,
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["same_generated_and_reference_path"]


def test_invalid_perframe_csv_fails_input_validation(tmp_path: Path) -> None:
    generated_path = write_csv(
        tmp_path / "generated.csv",
        list(reversed(PERFRAME_HEADER)),
        [perframe_row()],
    )
    reference_path = write_valid_perframe(tmp_path / "reference.csv")

    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=generated_path,
            reference_contacts_perframe_csv=reference_path,
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert issue_kinds(result) == ["perframe_validation_failed"]


def test_invalid_contact_edges_csv_fails_input_validation(
    tmp_path: Path,
) -> None:
    generated_path = write_csv(
        tmp_path / "generated.csv",
        list(reversed(EDGES_HEADER)),
        [edges_row()],
    )
    reference_path = write_valid_edges(tmp_path / "reference.csv")

    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contact_edges_csv=generated_path,
            reference_contact_edges_csv=reference_path,
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False
            ),
        )
    )

    assert issue_kinds(result) == ["contact_edges_validation_failed"]


def test_disabled_perframe_paths_are_not_required(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contact_edges_csv=write_valid_edges(
                tmp_path / "generated.csv"
            ),
            reference_contact_edges_csv=write_valid_edges(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False
            ),
        )
    )

    assert result.passed is True
    assert "missing_generated_perframe_csv" not in issue_kinds(result)
    assert "missing_reference_perframe_csv" not in issue_kinds(result)


def test_disabled_contact_edges_paths_are_not_required(tmp_path: Path) -> None:
    result = validate_contacts_reference_comparison_input(
        PreprocessingContactsReferenceComparisonInput(
            generated_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "generated.csv"
            ),
            reference_contacts_perframe_csv=write_valid_perframe(
                tmp_path / "reference.csv"
            ),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert result.passed is True
    assert "missing_generated_contact_edges_csv" not in issue_kinds(result)
    assert "missing_reference_contact_edges_csv" not in issue_kinds(result)


def test_validation_rejects_invalid_input_type() -> None:
    with pytest.raises(ValueError):
        validate_contacts_reference_comparison_input({})


def test_source_boundary_module_does_not_implement_comparison() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "def compare_contacts" not in source
    assert "def compare_contacts_outputs" not in source
    assert "class PreprocessingContactsReferenceComparisonResult" not in source
    assert "ComparisonRowResult" not in source
    assert "Mismatch" not in source
    assert "Difference" not in source


def test_source_boundary_module_does_not_compute_contacts_or_write_csv() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "compute_condition_contacts" not in source
    assert "compute_manifest_contacts" not in source
    assert "write_contacts_perframe_csv" not in source
    assert "write_contact_edges_csv" not in source


def test_source_boundary_module_has_no_graph_export() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "graph.json" not in source
    assert "nodes.csv" not in source
    assert "backend graph" not in source
    assert "graph_edges" not in source
    assert "write_graph_edges" not in source
    assert "graph diagnostics" not in source


@pytest.mark.parametrize(
    "forbidden_import",
    ["MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"],
)
def test_source_boundary_module_has_no_forbidden_heavy_dependencies(
    forbidden_import: str,
) -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert f"import {forbidden_import}" not in source
    assert f"from {forbidden_import}" not in source
