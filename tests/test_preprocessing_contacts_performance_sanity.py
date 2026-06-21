import csv
import json
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingContactsReferenceComparisonInput,
    PreprocessingContactsReferenceComparisonOptions,
    PreprocessingManifestContactsResult,
    compare_contacts_outputs,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = REPO_ROOT / "tests" / "test_preprocessing_contacts_performance_sanity.py"
BOUNDARY_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_contacts_performance_boundary.md"
)
EXPECTED_CONDITION_COUNT = 2
EXPECTED_FRAME_COUNT = 6
EXPECTED_CONTACT_COUNT = 12
EXPECTED_AGGREGATE_ROW_COUNT = 6
PERFRAME_ROW_BOUND = 18
AGGREGATE_ROW_BOUND = 8


def make_pair(
    source_residue_index: int,
    target_residue_index: int,
    *,
    minimum_distance: float,
    source_resname: str,
    target_resname: str,
    source_segid: str,
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=source_residue_index,
        target_residue_index=target_residue_index,
        source_residue_id=source_residue_index + 100,
        target_residue_id=target_residue_index + 100,
        source_resname=source_resname,
        target_resname=target_resname,
        source_segid=source_segid,
        target_segid=source_segid,
        minimum_distance=minimum_distance,
        distance_unit="angstrom",
        atom_filter="heavy",
    )


def make_frame(
    condition_name: str,
    frame_index: int,
    contacts: tuple[PreprocessingContactPairResult, ...],
    *,
    failed: bool = False,
) -> PreprocessingContactFrameResult:
    return PreprocessingContactFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=float(frame_index),
        contacts=contacts,
        issues=(
            mania.preprocessing.PreprocessingContactComputationIssue(
                kind="contact_computation_error",
                field=f"frames[{frame_index}]",
                message="Expected synthetic frame failure.",
            ),
        )
        if failed
        else (),
    )


def make_condition(
    condition_name: str,
    frames: tuple[PreprocessingContactFrameResult, ...],
) -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=PreprocessingContactDetectionOptions(),
        frame_results=frames,
        status="computed",
    )


def build_small_manifest_contacts_result() -> PreprocessingManifestContactsResult:
    normal_pairs = {
        "a": make_pair(
            0,
            1,
            minimum_distance=3.0,
            source_resname="ALA",
            target_resname="GLY",
            source_segid="NORM",
        ),
        "b": make_pair(
            2,
            3,
            minimum_distance=3.8,
            source_resname="SER",
            target_resname="THR",
            source_segid="NORM",
        ),
        "c": make_pair(
            4,
            5,
            minimum_distance=4.1,
            source_resname="LYS",
            target_resname="ASP",
            source_segid="NORM",
        ),
    }
    tumor_pairs = {
        "d": make_pair(
            1,
            2,
            minimum_distance=2.9,
            source_resname="VAL",
            target_resname="ILE",
            source_segid="TUMR",
        ),
        "e": make_pair(
            3,
            4,
            minimum_distance=3.6,
            source_resname="ASN",
            target_resname="GLN",
            source_segid="TUMR",
        ),
        "f": make_pair(
            5,
            6,
            minimum_distance=4.0,
            source_resname="PHE",
            target_resname="TYR",
            source_segid="TUMR",
        ),
    }
    normal = make_condition(
        "normal",
        (
            make_frame("normal", 0, (normal_pairs["a"], normal_pairs["b"])),
            make_frame("normal", 1, (normal_pairs["a"], normal_pairs["c"])),
            make_frame("normal", 2, (normal_pairs["b"], normal_pairs["c"])),
        ),
    )
    tumor = make_condition(
        "tumor",
        (
            make_frame("tumor", 0, (tumor_pairs["d"], tumor_pairs["e"])),
            make_frame("tumor", 1, (tumor_pairs["d"], tumor_pairs["f"])),
            make_frame("tumor", 2, (tumor_pairs["e"], tumor_pairs["f"])),
        ),
    )
    return PreprocessingManifestContactsResult(condition_results=(normal, tumor))


def build_header_only_manifest_contacts_result() -> PreprocessingManifestContactsResult:
    return PreprocessingManifestContactsResult()


def build_failed_frame_contacts_result() -> PreprocessingConditionContactsResult:
    good_pair = make_pair(
        0,
        1,
        minimum_distance=3.0,
        source_resname="ALA",
        target_resname="GLY",
        source_segid="FAIL",
    )
    failed_pair = make_pair(
        2,
        3,
        minimum_distance=3.5,
        source_resname="SER",
        target_resname="THR",
        source_segid="FAIL",
    )
    return PreprocessingConditionContactsResult(
        condition_name="failed_frame",
        options=PreprocessingContactDetectionOptions(),
        frame_results=(
            make_frame("failed_frame", 0, (good_pair,)),
            make_frame("failed_frame", 1, (failed_pair,), failed=True),
        ),
        status="partial",
    )


def write_synthetic_outputs(
    tmp_path: Path,
    prefix: str,
    result: PreprocessingManifestContactsResult | PreprocessingConditionContactsResult,
) -> tuple[Path, Path]:
    perframe_path = tmp_path / f"{prefix}_contacts_perframe.csv"
    edges_path = tmp_path / f"{prefix}_contact_edges.csv"
    write_contacts_perframe_csv(result, perframe_path)
    write_contact_edges_csv(result, edges_path)
    return perframe_path, edges_path


def comparison_input(
    generated_perframe: Path,
    reference_perframe: Path,
    generated_edges: Path,
    reference_edges: Path,
) -> PreprocessingContactsReferenceComparisonInput:
    return PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv=generated_perframe,
        reference_contacts_perframe_csv=reference_perframe,
        generated_contact_edges_csv=generated_edges,
        reference_contact_edges_csv=reference_edges,
        options=PreprocessingContactsReferenceComparisonOptions(),
    )


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.reader(csv_file))


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerows(rows)


def row_result_count(result: object) -> int:
    return sum(
        len(target_result.row_results)
        for target_result in result.target_results
    )


def row_issue_kinds(result: object) -> list[str]:
    return [
        issue.kind
        for target_result in result.target_results
        for row_result in target_result.row_results
        for issue in row_result.issues
    ]


def test_public_imports_remain_dependency_free() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactPairResult is not None
    assert PreprocessingContactFrameResult is not None
    assert PreprocessingConditionContactsResult is not None
    assert PreprocessingManifestContactsResult is not None
    assert write_contacts_perframe_csv is not None
    assert write_contact_edges_csv is not None
    assert validate_contacts_perframe_csv is not None
    assert validate_contact_edges_csv is not None
    assert PreprocessingContactsReferenceComparisonInput is not None
    assert PreprocessingContactsReferenceComparisonOptions is not None
    assert compare_contacts_outputs is not None


def test_synthetic_manifest_contacts_result_has_bounded_shape() -> None:
    result = build_small_manifest_contacts_result()

    assert result.condition_count == EXPECTED_CONDITION_COUNT
    assert result.frame_count == EXPECTED_FRAME_COUNT
    assert result.contact_count == EXPECTED_CONTACT_COUNT
    assert result.contact_count <= PERFRAME_ROW_BOUND
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_perframe_writer_produces_bounded_output_rows(tmp_path: Path) -> None:
    result = build_small_manifest_contacts_result()
    output_path = tmp_path / "contacts_perframe.csv"

    write_result = write_contacts_perframe_csv(result, output_path)
    validation = validate_contacts_perframe_csv(output_path)

    assert write_result.passed is True
    assert write_result.rows_written == EXPECTED_CONTACT_COUNT
    assert write_result.rows_written <= PERFRAME_ROW_BOUND
    assert validation.passed is True
    assert validation.row_count == write_result.rows_written
    assert validation.contact_count == EXPECTED_CONTACT_COUNT


def test_contact_edges_writer_produces_bounded_aggregate_rows(
    tmp_path: Path,
) -> None:
    result = build_small_manifest_contacts_result()
    output_path = tmp_path / "contact_edges.csv"

    write_result = write_contact_edges_csv(result, output_path)
    validation = validate_contact_edges_csv(output_path)

    assert write_result.passed is True
    assert write_result.rows_written <= EXPECTED_CONTACT_COUNT
    assert write_result.rows_written == EXPECTED_AGGREGATE_ROW_COUNT
    assert write_result.rows_written <= AGGREGATE_ROW_BOUND
    assert validation.passed is True
    assert validation.row_count == write_result.rows_written
    assert validation.aggregate_edge_count == EXPECTED_AGGREGATE_ROW_COUNT


def test_identical_comparison_reports_stay_bounded(tmp_path: Path) -> None:
    result = build_small_manifest_contacts_result()
    generated_perframe, generated_edges = write_synthetic_outputs(
        tmp_path,
        "generated",
        result,
    )
    reference_perframe, reference_edges = write_synthetic_outputs(
        tmp_path,
        "reference",
        result,
    )

    comparison = compare_contacts_outputs(
        comparison_input(
            generated_perframe,
            reference_perframe,
            generated_edges,
            reference_edges,
        )
    )

    assert comparison.passed is True
    assert comparison.matched_row_count == (
        EXPECTED_CONTACT_COUNT + EXPECTED_AGGREGATE_ROW_COUNT
    )
    assert comparison.failed_row_count == 0
    assert row_issue_kinds(comparison) == []
    assert row_result_count(comparison) == comparison.matched_row_count
    assert row_result_count(comparison) <= (
        PERFRAME_ROW_BOUND + AGGREGATE_ROW_BOUND
    )


def test_mismatch_comparison_report_stays_bounded(tmp_path: Path) -> None:
    result = build_small_manifest_contacts_result()
    generated_perframe, generated_edges = write_synthetic_outputs(
        tmp_path,
        "generated",
        result,
    )
    reference_perframe, reference_edges = write_synthetic_outputs(
        tmp_path,
        "reference",
        result,
    )
    rows = read_csv(generated_perframe)
    rows[1][11] = "4.0"
    write_csv(generated_perframe, rows)

    comparison = compare_contacts_outputs(
        comparison_input(
            generated_perframe,
            reference_perframe,
            generated_edges,
            reference_edges,
        )
    )

    assert comparison.passed is False
    assert comparison.matched_row_count == (
        EXPECTED_CONTACT_COUNT + EXPECTED_AGGREGATE_ROW_COUNT
    )
    assert comparison.failed_row_count == 1
    assert row_issue_kinds(comparison).count("minimum_distance_mismatch") == 1
    assert comparison.max_distance_abs_difference == 1.0
    assert row_result_count(comparison) == comparison.matched_row_count
    assert row_result_count(comparison) <= (
        PERFRAME_ROW_BOUND + AGGREGATE_ROW_BOUND
    )


def test_header_only_outputs_remain_lightweight(tmp_path: Path) -> None:
    result = build_header_only_manifest_contacts_result()
    generated_perframe, generated_edges = write_synthetic_outputs(
        tmp_path,
        "generated",
        result,
    )
    reference_perframe, reference_edges = write_synthetic_outputs(
        tmp_path,
        "reference",
        result,
    )

    perframe_write = write_contacts_perframe_csv(
        result,
        tmp_path / "extra_contacts_perframe.csv",
    )
    edges_write = write_contact_edges_csv(
        result,
        tmp_path / "extra_contact_edges.csv",
    )
    perframe_validation = validate_contacts_perframe_csv(generated_perframe)
    edges_validation = validate_contact_edges_csv(generated_edges)
    comparison = compare_contacts_outputs(
        comparison_input(
            generated_perframe,
            reference_perframe,
            generated_edges,
            reference_edges,
        )
    )

    assert perframe_write.passed is True
    assert perframe_write.rows_written == 0
    assert edges_write.passed is True
    assert edges_write.rows_written == 0
    assert perframe_validation.passed is True
    assert perframe_validation.row_count == 0
    assert edges_validation.passed is True
    assert edges_validation.row_count == 0
    assert comparison.passed is True
    assert comparison.matched_row_count == 0
    assert row_result_count(comparison) == 0
    assert json.loads(json.dumps(comparison.to_dict())) == comparison.to_dict()


def test_failed_frame_skip_behavior_stays_bounded(tmp_path: Path) -> None:
    result = build_failed_frame_contacts_result()
    perframe_path = tmp_path / "contacts_perframe.csv"
    edges_path = tmp_path / "contact_edges.csv"

    perframe_write = write_contacts_perframe_csv(result, perframe_path)
    edges_write = write_contact_edges_csv(result, edges_path)
    perframe_validation = validate_contacts_perframe_csv(perframe_path)
    edges_validation = validate_contact_edges_csv(edges_path)

    assert perframe_write.passed is True
    assert perframe_write.rows_written == 1
    assert perframe_write.skipped_frame_count == 1
    assert perframe_write.rows_written <= PERFRAME_ROW_BOUND
    assert edges_write.passed is True
    assert edges_write.rows_written == 1
    assert edges_write.skipped_frame_count == 1
    assert edges_write.rows_written <= AGGREGATE_ROW_BOUND
    assert perframe_validation.passed is True
    assert perframe_validation.row_count == 1
    assert edges_validation.passed is True
    assert edges_validation.row_count == 1
    assert read_csv(edges_path)[1][10] == "1"


def test_source_contains_no_machine_specific_measurement_code() -> None:
    source_text = THIS_FILE.read_text(encoding="utf-8")
    forbidden = (
        "time" + ".time",
        "time" + ".perf_counter",
        "pytest" + "-" + "bench" + "mark",
        "bench" + "mark",
        "dur" + "ation",
        "sec" + "onds",
        "hard " + "timing " + "threshold",
    )

    for text in forbidden:
        assert text not in source_text


def test_source_contains_no_scientific_or_local_data_dependency() -> None:
    source_text = THIS_FILE.read_text(encoding="utf-8")
    forbidden = (
        "MD" + "Analysis",
        "MANIA_RUN_LOCAL" + "_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE" + "_PACKAGE",
        "data" + "/" + "reference",
        "tests" + "/" + "local_scientific",
    )

    for text in forbidden:
        assert text not in source_text


def test_no_graph_output_api_checks_are_added() -> None:
    source_text = THIS_FILE.read_text(encoding="utf-8")
    boundary_text = BOUNDARY_DOC_PATH.read_text(encoding="utf-8")
    stage_text = boundary_text.split(
        "## Stage 13.5b lightweight sanity checks",
        maxsplit=1,
    )[-1].split("## Explicit non-goals", maxsplit=1)[0]
    forbidden = (
        "graph" + ".json",
        "backend " + "graph " + "nodes.csv",
        "backend " + "graph " + "edges.csv",
        "graph " + "export API usage",
    )

    for text in forbidden:
        assert text not in source_text
        assert text not in stage_text
