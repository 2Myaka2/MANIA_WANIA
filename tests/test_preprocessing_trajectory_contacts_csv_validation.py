import csv
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactEdgesCsvValidationIssue,
    PreprocessingContactEdgesCsvValidationResult,
    PreprocessingContactEdgesCsvWriteIssue,
    PreprocessingContactEdgesCsvWriteResult,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingContactsPerFrameCsvValidationIssue,
    PreprocessingContactsPerFrameCsvValidationResult,
    PreprocessingContactsPerFrameCsvWriteIssue,
    PreprocessingContactsPerFrameCsvWriteResult,
    PreprocessingManifestContactsResult,
    compute_condition_contacts,
    compute_manifest_contacts,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts_export_validation.py"
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


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


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


def issue_kinds(result: object) -> set[str]:
    return {issue.kind for issue in result.issues}


def make_pair(
    minimum_distance: float = 3.0,
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=0,
        target_residue_index=1,
        source_residue_id=10,
        target_residue_id="11A",
        source_resname="ALA",
        target_resname="GLY",
        source_segid="PROA",
        target_segid="PROA",
        minimum_distance=minimum_distance,
        distance_unit="angstrom",
        atom_filter="heavy",
    )


def make_condition() -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name="normal",
        options=PreprocessingContactDetectionOptions(),
        frame_results=(
            PreprocessingContactFrameResult(
                condition_name="normal",
                frame_index=0,
                time_ps=0.0,
                contacts=(make_pair(3.0),),
            ),
            PreprocessingContactFrameResult(
                condition_name="normal",
                frame_index=1,
                time_ps=2.0,
                contacts=(make_pair(4.0),),
            ),
        ),
        status="computed",
    )


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactsPerFrameCsvValidationIssue is not None
    assert PreprocessingContactsPerFrameCsvValidationResult is not None
    assert validate_contacts_perframe_csv is not None
    assert PreprocessingContactEdgesCsvValidationIssue is not None
    assert PreprocessingContactEdgesCsvValidationResult is not None
    assert validate_contact_edges_csv is not None


def test_existing_contacts_exports_and_computation_remain_available() -> None:
    assert PreprocessingContactsPerFrameCsvWriteIssue is not None
    assert PreprocessingContactsPerFrameCsvWriteResult is not None
    assert PreprocessingContactEdgesCsvWriteIssue is not None
    assert PreprocessingContactEdgesCsvWriteResult is not None
    assert write_contacts_perframe_csv is not None
    assert write_contact_edges_csv is not None
    assert PreprocessingContactDetectionOptions is not None
    assert PreprocessingContactPairResult is not None
    assert PreprocessingContactFrameResult is not None
    assert PreprocessingConditionContactsResult is not None
    assert PreprocessingManifestContactsResult is not None
    assert compute_condition_contacts is not None
    assert compute_manifest_contacts is not None


def test_valid_contacts_perframe_csv_passes(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(), perframe_row(frame_index="1")])

    result = validate_contacts_perframe_csv(path)

    assert result.passed is True
    assert result.row_count == 2
    assert result.valid_row_count == 2
    assert result.invalid_row_count == 0
    assert result.condition_count == 1
    assert result.frame_count == 2
    assert result.contact_count == 2
    assert result.issues == ()


def test_header_only_contacts_perframe_csv_passes(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [])

    result = validate_contacts_perframe_csv(path)

    assert result.passed is True
    assert result.row_count == 0
    assert result.contact_count == 0
    assert result.issues == ()


def test_invalid_contacts_perframe_header_fails(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, list(reversed(PERFRAME_HEADER)), [perframe_row()])

    result = validate_contacts_perframe_csv(path)

    assert result.passed is False
    assert issue_kinds(result) == {"invalid_header"}


def test_invalid_contacts_perframe_column_count_fails(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row()[:-1]])

    result = validate_contacts_perframe_csv(path)

    assert "invalid_column_count" in issue_kinds(result)


def test_contacts_perframe_required_field_empty_fails(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(condition_name="")])

    result = validate_contacts_perframe_csv(path)

    assert "empty_required_field" in issue_kinds(result)


@pytest.mark.parametrize(
    ("field_name", "value", "expected_kind"),
    [
        ("frame_index", "x", "invalid_integer"),
        ("frame_index", "-1", "negative_integer"),
        ("source_residue_index", "-1", "negative_integer"),
        ("target_residue_index", "-1", "negative_integer"),
    ],
)
def test_contacts_perframe_invalid_integer_fields_fail(
    tmp_path: Path,
    field_name: str,
    value: str,
    expected_kind: str,
) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(**{field_name: value})])

    result = validate_contacts_perframe_csv(path)

    assert expected_kind in issue_kinds(result)


def test_contacts_perframe_same_residue_pair_fails(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(
        path,
        PERFRAME_HEADER,
        [perframe_row(source_residue_index="1", target_residue_index="1")],
    )

    result = validate_contacts_perframe_csv(path)

    assert "same_residue_pair" in issue_kinds(result)


@pytest.mark.parametrize("time_ps", ["-1", "nan", "inf", "not-a-number"])
def test_contacts_perframe_invalid_time_fails(
    tmp_path: Path,
    time_ps: str,
) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(time_ps=time_ps)])

    result = validate_contacts_perframe_csv(path)

    assert "invalid_time_ps" in issue_kinds(result)


def test_contacts_perframe_empty_time_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(time_ps="")])

    result = validate_contacts_perframe_csv(path)

    assert result.passed is True


@pytest.mark.parametrize(
    ("minimum_distance", "expected_kind"),
    [
        ("-1", "negative_float"),
        ("nan", "invalid_float"),
        ("inf", "invalid_float"),
        ("not-a-number", "invalid_float"),
    ],
)
def test_contacts_perframe_invalid_minimum_distance_fails(
    tmp_path: Path,
    minimum_distance: str,
    expected_kind: str,
) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(
        path,
        PERFRAME_HEADER,
        [perframe_row(minimum_distance=minimum_distance)],
    )

    result = validate_contacts_perframe_csv(path)

    assert expected_kind in issue_kinds(result)


def test_contacts_perframe_invalid_atom_filter_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(atom_filter="carbon")])

    result = validate_contacts_perframe_csv(path)

    assert "invalid_atom_filter" in issue_kinds(result)


@pytest.mark.parametrize("frame_passed", ["True", "FALSE", "yes", ""])
def test_contacts_perframe_invalid_frame_passed_fails(
    tmp_path: Path,
    frame_passed: str,
) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(frame_passed=frame_passed)])

    result = validate_contacts_perframe_csv(path)

    assert "invalid_frame_passed" in issue_kinds(result)


def test_contacts_perframe_duplicate_row_key_fails(tmp_path: Path) -> None:
    path = tmp_path / "contacts_perframe.csv"
    write_csv(path, PERFRAME_HEADER, [perframe_row(), perframe_row()])

    result = validate_contacts_perframe_csv(path)

    assert "duplicate_row_key" in issue_kinds(result)


def test_valid_contact_edges_csv_passes(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [edges_row(), edges_row(source_residue_index="2", target_residue_index="3")],
    )

    result = validate_contact_edges_csv(path)

    assert result.passed is True
    assert result.row_count == 2
    assert result.valid_row_count == 2
    assert result.invalid_row_count == 0
    assert result.condition_count == 1
    assert result.aggregate_edge_count == 2
    assert result.issues == ()


def test_header_only_contact_edges_csv_passes(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [])

    result = validate_contact_edges_csv(path)

    assert result.passed is True
    assert result.row_count == 0
    assert result.aggregate_edge_count == 0
    assert result.issues == ()


def test_invalid_contact_edges_header_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, list(reversed(EDGES_HEADER)), [edges_row()])

    result = validate_contact_edges_csv(path)

    assert result.passed is False
    assert issue_kinds(result) == {"invalid_header"}


def test_invalid_contact_edges_column_count_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row()[:-1]])

    result = validate_contact_edges_csv(path)

    assert "invalid_column_count" in issue_kinds(result)


def test_contact_edges_required_field_empty_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(condition_name="")])

    result = validate_contact_edges_csv(path)

    assert "empty_required_field" in issue_kinds(result)


@pytest.mark.parametrize(
    ("field_name", "value", "expected_kind"),
    [
        ("source_residue_index", "-1", "negative_integer"),
        ("target_residue_index", "-1", "negative_integer"),
        ("source_residue_index", "x", "invalid_integer"),
    ],
)
def test_contact_edges_invalid_residue_indexes_fail(
    tmp_path: Path,
    field_name: str,
    value: str,
    expected_kind: str,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(**{field_name: value})])

    result = validate_contact_edges_csv(path)

    assert expected_kind in issue_kinds(result)


def test_contact_edges_same_residue_pair_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [edges_row(source_residue_index="1", target_residue_index="1")],
    )

    result = validate_contact_edges_csv(path)

    assert "same_residue_pair" in issue_kinds(result)


@pytest.mark.parametrize("contact_frame_count", ["0", "-1", "x"])
def test_contact_edges_invalid_contact_frame_count_fails(
    tmp_path: Path,
    contact_frame_count: str,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [edges_row(contact_frame_count=contact_frame_count)],
    )

    result = validate_contact_edges_csv(path)

    assert "invalid_contact_frame_count" in issue_kinds(result)


@pytest.mark.parametrize("total_frame_count", ["0", "-1", "x"])
def test_contact_edges_invalid_total_frame_count_fails(
    tmp_path: Path,
    total_frame_count: str,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(total_frame_count=total_frame_count)])

    result = validate_contact_edges_csv(path)

    assert "invalid_total_frame_count" in issue_kinds(result)


def test_contact_edges_contact_count_exceeds_total_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [edges_row(contact_frame_count="3", total_frame_count="2")],
    )

    result = validate_contact_edges_csv(path)

    assert "contact_frame_count_exceeds_total_frame_count" in issue_kinds(result)


@pytest.mark.parametrize(
    "contact_frequency",
    ["-0.1", "1.1", "nan", "inf", "not-a-number"],
)
def test_contact_edges_invalid_contact_frequency_fails(
    tmp_path: Path,
    contact_frequency: str,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(contact_frequency=contact_frequency)])

    result = validate_contact_edges_csv(path)

    assert "invalid_contact_frequency" in issue_kinds(result)


def test_contact_edges_frequency_mismatch_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [
            edges_row(
                contact_frame_count="1",
                total_frame_count="4",
                contact_frequency="0.9",
            )
        ],
    )

    result = validate_contact_edges_csv(path)

    assert "contact_frequency_mismatch" in issue_kinds(result)


@pytest.mark.parametrize("field_name", ["minimum_distance", "mean_minimum_distance"])
@pytest.mark.parametrize(
    ("value", "expected_kind"),
    [
        ("-1", "negative_float"),
        ("nan", "invalid_float"),
        ("inf", "invalid_float"),
        ("not-a-number", "invalid_float"),
    ],
)
def test_contact_edges_invalid_distances_fail(
    tmp_path: Path,
    field_name: str,
    value: str,
    expected_kind: str,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(**{field_name: value})])

    result = validate_contact_edges_csv(path)

    assert expected_kind in issue_kinds(result)


def test_contact_edges_mean_distance_below_minimum_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(
        path,
        EDGES_HEADER,
        [edges_row(minimum_distance="4.0", mean_minimum_distance="3.0")],
    )

    result = validate_contact_edges_csv(path)

    assert "mean_distance_below_minimum_distance" in issue_kinds(result)


def test_contact_edges_invalid_atom_filter_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(atom_filter="carbon")])

    result = validate_contact_edges_csv(path)

    assert "invalid_atom_filter" in issue_kinds(result)


def test_contact_edges_duplicate_aggregate_key_fails(tmp_path: Path) -> None:
    path = tmp_path / "contact_edges.csv"
    write_csv(path, EDGES_HEADER, [edges_row(), edges_row()])

    result = validate_contact_edges_csv(path)

    assert "duplicate_row_key" in issue_kinds(result)


def test_missing_files_fail(tmp_path: Path) -> None:
    perframe = validate_contacts_perframe_csv(tmp_path / "missing_perframe.csv")
    edges = validate_contact_edges_csv(tmp_path / "missing_edges.csv")

    assert issue_kinds(perframe) == {"missing_file"}
    assert issue_kinds(edges) == {"missing_file"}


def test_directory_paths_fail(tmp_path: Path) -> None:
    perframe = validate_contacts_perframe_csv(tmp_path)
    edges = validate_contact_edges_csv(tmp_path)

    assert issue_kinds(perframe) == {"path_is_directory"}
    assert issue_kinds(edges) == {"path_is_directory"}


def test_validation_issue_to_dict_is_json_safe() -> None:
    perframe_issue = PreprocessingContactsPerFrameCsvValidationIssue(
        kind="invalid_header",
        row_number=None,
        field="header",
        message="Bad header.",
    )
    edges_issue = PreprocessingContactEdgesCsvValidationIssue(
        kind="invalid_header",
        row_number=2,
        field="header",
        message="Bad header.",
    )

    perframe_payload = perframe_issue.to_dict()
    edges_payload = edges_issue.to_dict()

    assert json.loads(json.dumps(perframe_payload)) == perframe_payload
    assert json.loads(json.dumps(edges_payload)) == edges_payload


def test_validation_issue_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsPerFrameCsvValidationIssue(
            kind="",
            row_number=None,
            field="header",
            message="Bad header.",
        )
    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvValidationIssue(
            kind="invalid_header",
            row_number=0,
            field="header",
            message="Bad header.",
        )


def test_validation_result_to_dict_is_json_safe() -> None:
    perframe_issue = PreprocessingContactsPerFrameCsvValidationIssue(
        kind="invalid_header",
        row_number=None,
        field="header",
        message="Bad header.",
    )
    edges_issue = PreprocessingContactEdgesCsvValidationIssue(
        kind="invalid_header",
        row_number=None,
        field="header",
        message="Bad header.",
    )
    perframe_result = PreprocessingContactsPerFrameCsvValidationResult(
        csv_path="contacts_perframe.csv",
        passed=False,
        row_count=0,
        valid_row_count=0,
        invalid_row_count=0,
        condition_count=0,
        frame_count=0,
        contact_count=0,
        issues=(perframe_issue,),
    )
    edges_result = PreprocessingContactEdgesCsvValidationResult(
        csv_path="contact_edges.csv",
        passed=False,
        row_count=0,
        valid_row_count=0,
        invalid_row_count=0,
        condition_count=0,
        aggregate_edge_count=0,
        issues=(edges_issue,),
    )

    perframe_payload = perframe_result.to_dict()
    edges_payload = edges_result.to_dict()

    assert json.loads(json.dumps(perframe_payload)) == perframe_payload
    assert json.loads(json.dumps(edges_payload)) == edges_payload


def test_validation_result_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactsPerFrameCsvValidationResult(
            csv_path="contacts_perframe.csv",
            passed="true",
            row_count=0,
            valid_row_count=0,
            invalid_row_count=0,
            condition_count=0,
            frame_count=0,
            contact_count=0,
        )
    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvValidationResult(
            csv_path="contact_edges.csv",
            passed=True,
            row_count=-1,
            valid_row_count=0,
            invalid_row_count=0,
            condition_count=0,
            aggregate_edge_count=0,
        )


def test_valid_files_written_by_writers_pass_validators(tmp_path: Path) -> None:
    condition = make_condition()
    perframe_path = tmp_path / "contacts_perframe.csv"
    edges_path = tmp_path / "contact_edges.csv"

    perframe_write = write_contacts_perframe_csv(condition, perframe_path)
    edges_write = write_contact_edges_csv(condition, edges_path)
    perframe_validation = validate_contacts_perframe_csv(perframe_path)
    edges_validation = validate_contact_edges_csv(edges_path)

    assert perframe_write.passed is True
    assert edges_write.passed is True
    assert perframe_validation.passed is True
    assert edges_validation.passed is True


def test_validation_module_does_not_compute_contacts() -> None:
    source = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    assert "compute_condition_contacts" not in source
    assert "compute_manifest_contacts" not in source
    assert ".trajectory" not in source
    assert ".atoms" not in source
    assert ".positions" not in source


def test_validation_module_does_not_write_csv() -> None:
    source = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    assert "write_contacts_perframe_csv" not in source
    assert "write_contact_edges_csv" not in source


def test_validation_module_does_not_compare_references() -> None:
    source = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    assert "compare_contacts" not in source
    assert "reference_comparison" not in source


def test_validation_module_has_no_graph_validation_or_export() -> None:
    source = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

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
def test_validation_module_has_no_forbidden_heavy_dependencies(
    forbidden_import: str,
) -> None:
    source = VALIDATION_MODULE_PATH.read_text(encoding="utf-8")

    assert f"import {forbidden_import}" not in source
    assert f"from {forbidden_import}" not in source
