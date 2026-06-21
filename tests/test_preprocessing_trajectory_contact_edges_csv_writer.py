import csv
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactComputationIssue,
    PreprocessingContactDetectionOptions,
    PreprocessingContactEdgesCsvWriteIssue,
    PreprocessingContactEdgesCsvWriteResult,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingContactsPerFrameCsvWriteIssue,
    PreprocessingContactsPerFrameCsvWriteResult,
    PreprocessingManifestContactsResult,
    compute_condition_contacts,
    compute_manifest_contacts,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts_export.py"
)
CSV_HEADER = [
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


def make_issue() -> PreprocessingContactComputationIssue:
    return PreprocessingContactComputationIssue(
        kind="contact_computation_error",
        field="contacts",
        message="Expected contact failure.",
    )


def make_pair(
    source_residue_index: int = 0,
    target_residue_index: int = 1,
    *,
    source_residue_id: int | str | None = 10,
    target_residue_id: int | str | None = "11A",
    source_resname: str = "ALA",
    target_resname: str = "GLY",
    source_segid: str | None = "PROA",
    target_segid: str | None = "PROA",
    minimum_distance: float = 3.0,
    distance_unit: str = "angstrom",
    atom_filter: str = "heavy",
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=source_residue_index,
        target_residue_index=target_residue_index,
        source_residue_id=source_residue_id,
        target_residue_id=target_residue_id,
        source_resname=source_resname,
        target_resname=target_resname,
        source_segid=source_segid,
        target_segid=target_segid,
        minimum_distance=minimum_distance,
        distance_unit=distance_unit,
        atom_filter=atom_filter,
    )


def make_frame(
    condition_name: str,
    frame_index: int,
    *,
    contacts: tuple[PreprocessingContactPairResult, ...] = (),
    failed: bool = False,
) -> PreprocessingContactFrameResult:
    return PreprocessingContactFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=float(frame_index),
        contacts=contacts,
        issues=(make_issue(),) if failed else (),
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frames: tuple[PreprocessingContactFrameResult, ...] | None = None,
    status: str = "computed",
    issues: tuple[PreprocessingContactComputationIssue, ...] = (),
) -> PreprocessingConditionContactsResult:
    if frames is None:
        frames = (
            make_frame(
                condition_name,
                0,
                contacts=(make_pair(minimum_distance=3.0),),
            ),
            make_frame(
                condition_name,
                1,
                contacts=(make_pair(minimum_distance=4.0),),
            ),
        )
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=PreprocessingContactDetectionOptions(),
        frame_results=frames,
        issues=issues,
        status=status,
    )


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.reader(csv_file))


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactEdgesCsvWriteIssue is not None
    assert PreprocessingContactEdgesCsvWriteResult is not None
    assert write_contact_edges_csv is not None


def test_existing_contacts_export_apis_remain_available() -> None:
    assert PreprocessingContactsPerFrameCsvWriteIssue is not None
    assert PreprocessingContactsPerFrameCsvWriteResult is not None
    assert write_contacts_perframe_csv is not None


def test_existing_contacts_computation_apis_remain_available() -> None:
    assert PreprocessingContactDetectionOptions is not None
    assert PreprocessingContactPairResult is not None
    assert PreprocessingContactFrameResult is not None
    assert PreprocessingConditionContactsResult is not None
    assert PreprocessingManifestContactsResult is not None
    assert compute_condition_contacts is not None
    assert compute_manifest_contacts is not None


def test_write_issue_validates_and_serializes() -> None:
    issue = PreprocessingContactEdgesCsvWriteIssue(
        kind=" write_error ",
        field=" output_path ",
        message=" Write failed. ",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "write_error",
        "field": "output_path",
        "message": "Write failed.",
    }
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize("field_name", ["kind", "field", "message"])
@pytest.mark.parametrize("invalid_value", ["", "   ", None])
def test_write_issue_rejects_empty_fields(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "kind": "write_error",
        "field": "output_path",
        "message": "Write failed.",
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvWriteIssue(**values)


def test_write_result_validates_and_serializes() -> None:
    issue = PreprocessingContactEdgesCsvWriteIssue(
        kind="duplicate_pair_in_frame",
        field="frame_results[0]",
        message="Duplicate pair.",
    )
    result = PreprocessingContactEdgesCsvWriteResult(
        output_path="contact_edges.csv",
        passed=False,
        rows_written=1,
        condition_count=1,
        frame_count=2,
        contact_count=3,
        aggregate_edge_count=1,
        skipped_frame_count=0,
        issues=(issue,),
    )

    payload = result.to_dict()

    assert result.output_path == Path("contact_edges.csv")
    assert payload == {
        "output_path": "contact_edges.csv",
        "passed": False,
        "rows_written": 1,
        "condition_count": 1,
        "frame_count": 2,
        "contact_count": 3,
        "aggregate_edge_count": 1,
        "skipped_frame_count": 0,
        "issues": [issue.to_dict()],
    }
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    "field_name",
    ["rows_written", "condition_count", "aggregate_edge_count"],
)
@pytest.mark.parametrize("invalid_value", [-1, True, 1.5])
def test_write_result_rejects_invalid_counts(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "output_path": Path("contact_edges.csv"),
        "passed": True,
        "rows_written": 0,
        "condition_count": 0,
        "frame_count": 0,
        "contact_count": 0,
        "aggregate_edge_count": 0,
        "skipped_frame_count": 0,
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvWriteResult(**values)


def test_write_result_rejects_invalid_passed() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvWriteResult(
            output_path=Path("contact_edges.csv"),
            passed="true",
            rows_written=0,
            condition_count=0,
            frame_count=0,
            contact_count=0,
            aggregate_edge_count=0,
            skipped_frame_count=0,
        )


def test_write_result_rejects_invalid_issue_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactEdgesCsvWriteResult(
            output_path=Path("contact_edges.csv"),
            passed=False,
            rows_written=0,
            condition_count=0,
            frame_count=0,
            contact_count=0,
            aggregate_edge_count=0,
            skipped_frame_count=0,
            issues=(object(),),
        )


def test_writes_manifest_aggregate_contacts_result(tmp_path: Path) -> None:
    normal = make_condition(
        "normal",
        frames=(
            make_frame(
                "normal",
                0,
                contacts=(
                    make_pair(0, 1, minimum_distance=3.0),
                    make_pair(2, 3, minimum_distance=5.0),
                ),
            ),
            make_frame(
                "normal",
                1,
                contacts=(make_pair(0, 1, minimum_distance=4.0),),
            ),
        ),
    )
    tumor = make_condition(
        "tumor",
        frames=(
            make_frame(
                "tumor",
                0,
                contacts=(make_pair(0, 1, minimum_distance=2.0),),
            ),
        ),
    )
    manifest = PreprocessingManifestContactsResult(
        condition_results=(normal, tumor)
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(manifest, output_path)

    rows = read_rows(output_path)
    assert result.passed is True
    assert output_path.exists()
    assert rows == [
        CSV_HEADER,
        [
            "normal",
            "0",
            "1",
            "10",
            "11A",
            "ALA",
            "GLY",
            "PROA",
            "PROA",
            "2",
            "2",
            "1.0",
            "3.0",
            "3.5",
            "angstrom",
            "heavy",
        ],
        [
            "normal",
            "2",
            "3",
            "10",
            "11A",
            "ALA",
            "GLY",
            "PROA",
            "PROA",
            "1",
            "2",
            "0.5",
            "5.0",
            "5.0",
            "angstrom",
            "heavy",
        ],
        [
            "tumor",
            "0",
            "1",
            "10",
            "11A",
            "ALA",
            "GLY",
            "PROA",
            "PROA",
            "1",
            "1",
            "1.0",
            "2.0",
            "2.0",
            "angstrom",
            "heavy",
        ],
    ]
    assert result.rows_written == len(rows) - 1
    assert result.aggregate_edge_count == len(rows) - 1


def test_writes_condition_aggregate_contacts_result(tmp_path: Path) -> None:
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(make_condition(), output_path)

    assert result.passed is True
    assert result.condition_count == 1
    assert result.frame_count == 2
    assert result.aggregate_edge_count == 1
    assert read_rows(output_path)[1][0] == "normal"


def test_aggregates_repeated_pair_across_frames(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0, contacts=(make_pair(minimum_distance=4.0),)),
            make_frame("normal", 1, contacts=()),
            make_frame("normal", 2, contacts=(make_pair(minimum_distance=2.0),)),
        )
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    row = read_rows(output_path)[1]
    assert result.passed is True
    assert row[9] == "2"
    assert row[10] == "3"
    assert row[11] == str(2 / 3)
    assert row[12] == "2.0"
    assert row[13] == "3.0"


def test_does_not_merge_pairs_across_conditions(tmp_path: Path) -> None:
    manifest = PreprocessingManifestContactsResult(
        condition_results=(make_condition("normal"), make_condition("tumor"))
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(manifest, output_path)

    rows = read_rows(output_path)[1:]
    assert result.aggregate_edge_count == 2
    assert [row[0] for row in rows] == ["normal", "tumor"]


def test_does_not_merge_different_units_or_atom_filters(
    tmp_path: Path,
) -> None:
    condition = make_condition(
        frames=(
            make_frame(
                "normal",
                0,
                contacts=(
                    make_pair(distance_unit="angstrom", atom_filter="heavy"),
                    make_pair(distance_unit="nm", atom_filter="heavy"),
                    make_pair(distance_unit="angstrom", atom_filter="all"),
                ),
            ),
        )
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    rows = read_rows(output_path)[1:]
    assert result.aggregate_edge_count == 3
    assert [(row[14], row[15]) for row in rows] == [
        ("angstrom", "all"),
        ("angstrom", "heavy"),
        ("nm", "heavy"),
    ]


def test_zero_contacts_writes_header_only(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0),
            make_frame("normal", 1),
        )
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    assert result.passed is True
    assert result.rows_written == 0
    assert result.aggregate_edge_count == 0
    assert read_rows(output_path) == [CSV_HEADER]


def test_empty_manifest_writes_header_only(tmp_path: Path) -> None:
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(
        PreprocessingManifestContactsResult(),
        output_path,
    )

    assert result.passed is True
    assert result.rows_written == 0
    assert result.aggregate_edge_count == 0
    assert result.condition_count == 0
    assert read_rows(output_path) == [CSV_HEADER]


def test_none_values_serialize_as_empty_strings(tmp_path: Path) -> None:
    pair = make_pair(
        source_residue_id=None,
        target_residue_id=None,
        source_segid=None,
        target_segid=None,
    )
    condition = make_condition(
        frames=(make_frame("normal", 0, contacts=(pair,)),)
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    assert result.passed is True
    row = read_rows(output_path)[1]
    assert row[3] == ""
    assert row[4] == ""
    assert row[7] == ""
    assert row[8] == ""


def test_failed_frames_are_skipped_by_default(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0, contacts=(make_pair(0, 1),)),
            make_frame("normal", 1, contacts=(make_pair(2, 3),), failed=True),
        ),
        status="partial",
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    rows = read_rows(output_path)
    assert result.passed is True
    assert result.skipped_frame_count == 1
    assert "frame_result_failed" in {issue.kind for issue in result.issues}
    assert rows[1][10] == "1"
    assert len(rows) == 2


def test_failed_frames_can_be_included(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0, contacts=(make_pair(0, 1),)),
            make_frame("normal", 1, contacts=(make_pair(2, 3),), failed=True),
        ),
        status="partial",
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(
        condition,
        output_path,
        include_failed_frames=True,
    )

    rows = read_rows(output_path)
    assert result.passed is True
    assert result.skipped_frame_count == 0
    assert "frame_result_failed" in {issue.kind for issue in result.issues}
    assert [row[10] for row in rows[1:]] == ["2", "2"]
    assert len(rows) == 3


def test_failed_condition_reports_issue_but_can_write(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(make_frame("normal", 0, contacts=(make_pair(),)),),
        status="failed",
        issues=(make_issue(),),
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    assert result.passed is True
    assert result.rows_written == 1
    assert "condition_result_failed" in {
        issue.kind for issue in result.issues
    }


def test_duplicate_pair_in_same_frame_is_deterministic(
    tmp_path: Path,
) -> None:
    condition = make_condition(
        frames=(
            make_frame(
                "normal",
                0,
                contacts=(
                    make_pair(minimum_distance=4.0),
                    make_pair(minimum_distance=2.0),
                ),
            ),
        )
    )
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(condition, output_path)

    row = read_rows(output_path)[1]
    assert result.passed is False
    assert "duplicate_pair_in_frame" in {
        issue.kind for issue in result.issues
    }
    assert row[9] == "1"
    assert row[12] == "2.0"
    assert row[13] == "2.0"


def test_invalid_contacts_result_type_fails_without_writing(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "contact_edges.csv"

    result = write_contact_edges_csv(object(), output_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "unsupported_contacts_result_type"
    ]
    assert not output_path.exists()


def test_missing_output_path_fails() -> None:
    result = write_contact_edges_csv(make_condition(), "")

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["missing_output_path"]


def test_missing_parent_directory_fails(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "contact_edges.csv"

    result = write_contact_edges_csv(make_condition(), output_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "output_parent_missing"
    ]
    assert not output_path.exists()


def test_parent_path_not_directory_fails(tmp_path: Path) -> None:
    parent_file = tmp_path / "not_a_directory"
    parent_file.write_text("content\n", encoding="utf-8")
    output_path = parent_file / "contact_edges.csv"

    result = write_contact_edges_csv(make_condition(), output_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "output_parent_not_directory"
    ]


def test_output_path_directory_fails(tmp_path: Path) -> None:
    result = write_contact_edges_csv(make_condition(), tmp_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "output_path_is_directory"
    ]


def test_write_result_to_dict_from_writer_is_json_serializable(
    tmp_path: Path,
) -> None:
    result = write_contact_edges_csv(
        make_condition(),
        tmp_path / "contact_edges.csv",
    )

    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_export_module_does_not_compute_contacts() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "compute_condition_contacts",
        "compute_manifest_contacts",
        ".trajectory",
        ".atoms",
        ".positions",
        "euclidean",
    ):
        assert forbidden_text not in source_text


def test_export_module_does_not_validate_or_compare() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in ("validate_contacts", "compare_contacts"):
        assert forbidden_text not in source_text


def test_export_module_has_no_graph_output() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "graph.json",
        "nodes.csv",
        "backend graph",
        "graph_edges",
        "write_graph_edges",
    ):
        assert forbidden_text not in source_text


def test_export_module_has_no_forbidden_scientific_imports() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for package_name in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert f"import {package_name}" not in source_text
        assert f"from {package_name}" not in source_text
