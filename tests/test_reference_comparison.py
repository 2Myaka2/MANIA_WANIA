import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from mania.comparison.reference import (
    COMPARISON_MODE_CSV_EXACT,
    COMPARISON_MODE_FILE_EXISTS,
    COMPARISON_MODE_JSON_EXACT,
    COMPARISON_STATUS_FAIL,
    COMPARISON_STATUS_PASS,
    ArtifactComparisonSpec,
    ReferenceComparisonError,
    ReferenceComparisonReport,
    ReferenceComparisonResult,
    ReferenceDifference,
    build_comparison_report,
    compare_artifact_sets,
    compare_csv_exact,
    compare_file_exists,
    compare_json_exact,
    write_comparison_report,
)


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_csv(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[str]] = (),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def passing_result(artifact: str = "artifact.csv") -> ReferenceComparisonResult:
    return ReferenceComparisonResult(
        artifact=artifact,
        status=COMPARISON_STATUS_PASS,
        differences=(),
    )


def failing_result(artifact: str = "artifact.csv") -> ReferenceComparisonResult:
    return ReferenceComparisonResult(
        artifact=artifact,
        status=COMPARISON_STATUS_FAIL,
        differences=(
            ReferenceDifference(
                artifact=artifact,
                check="file_exists",
                expected="exists",
                actual="missing",
                message="missing file",
            ),
        ),
    )


def test_compare_file_exists_passes(tmp_path: Path) -> None:
    path = write_text(tmp_path / "artifact.csv", "a,b\n")

    result = compare_file_exists(path)

    assert result.passed is True
    assert result.status == "pass"
    assert result.differences == ()


def test_compare_file_exists_fails(tmp_path: Path) -> None:
    result = compare_file_exists(tmp_path / "missing.csv")

    assert result.passed is False
    assert result.status == "fail"
    assert len(result.differences) == 1
    assert result.differences[0].check == "file_exists"


def test_compare_csv_exact_passes_for_identical_files(tmp_path: Path) -> None:
    expected = write_csv(
        tmp_path / "expected.csv",
        ("id", "condition"),
        (("1", "normal"),),
    )
    actual = write_csv(
        tmp_path / "actual.csv",
        ("id", "condition"),
        (("1", "normal"),),
    )

    result = compare_csv_exact(expected, actual)

    assert result.passed is True
    assert result.differences == ()


def test_compare_csv_exact_detects_header_difference(tmp_path: Path) -> None:
    expected = write_csv(tmp_path / "expected.csv", ("a", "b"))
    actual = write_csv(tmp_path / "actual.csv", ("a", "c"))

    result = compare_csv_exact(expected, actual)

    assert result.passed is False
    assert any(difference.check == "csv_header" for difference in result.differences)


def test_compare_csv_exact_detects_row_count_difference(tmp_path: Path) -> None:
    expected = write_csv(
        tmp_path / "expected.csv",
        ("id", "condition"),
        (("1", "normal"), ("2", "normal")),
    )
    actual = write_csv(
        tmp_path / "actual.csv",
        ("id", "condition"),
        (("1", "normal"),),
    )

    result = compare_csv_exact(expected, actual)

    assert any(
        difference.check == "csv_row_count" for difference in result.differences
    )


def test_compare_csv_exact_detects_row_content_difference(tmp_path: Path) -> None:
    expected = write_csv(
        tmp_path / "expected.csv",
        ("id", "condition"),
        (("1", "normal"),),
    )
    actual = write_csv(
        tmp_path / "actual.csv",
        ("id", "condition"),
        (("1", "tumor"),),
    )

    result = compare_csv_exact(expected, actual)

    assert any(difference.check == "csv_row" for difference in result.differences)


def test_compare_json_exact_passes_for_equal_objects_with_different_key_order(
    tmp_path: Path,
) -> None:
    expected = write_json(tmp_path / "expected.json", {"a": 1, "b": 2})
    actual = write_json(tmp_path / "actual.json", {"b": 2, "a": 1})

    result = compare_json_exact(expected, actual)

    assert result.passed is True


def test_compare_json_exact_fails_for_different_objects(tmp_path: Path) -> None:
    expected = write_json(tmp_path / "expected.json", {"a": 1})
    actual = write_json(tmp_path / "actual.json", {"a": 2})

    result = compare_json_exact(expected, actual)

    assert result.passed is False
    assert any(difference.check == "json_exact" for difference in result.differences)


def test_reference_comparison_report_passed_property() -> None:
    passing_report = ReferenceComparisonReport(results=(passing_result(),))
    failing = failing_result("missing.csv")
    mixed_report = ReferenceComparisonReport(
        results=(passing_result("present.csv"), failing),
    )

    assert passing_report.passed is True
    assert mixed_report.passed is False
    assert mixed_report.failed_results() == (failing,)


def test_reference_comparison_report_to_dict_is_json_serializable() -> None:
    report = ReferenceComparisonReport(
        results=(passing_result("present.csv"), failing_result("missing.csv")),
    )

    payload = report.to_dict()
    json.dumps(payload)

    assert "passed" in payload
    assert "results" in payload


def test_write_comparison_report_writes_json(tmp_path: Path) -> None:
    report = ReferenceComparisonReport(results=(failing_result("missing.csv"),))
    path = write_comparison_report(report, tmp_path / "comparison" / "report.json")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.is_file()
    assert "passed" in payload
    assert "results" in payload


def test_csv_diff_is_concise(tmp_path: Path) -> None:
    expected = write_csv(
        tmp_path / "expected.csv",
        ("id", "condition"),
        tuple((str(index), "normal") for index in range(12)),
    )
    actual = write_csv(
        tmp_path / "actual.csv",
        ("id", "condition"),
        tuple((str(index), "tumor") for index in range(12)),
    )

    result = compare_csv_exact(expected, actual)

    csv_row_differences = tuple(
        difference
        for difference in result.differences
        if difference.check == "csv_row"
    )
    assert len(csv_row_differences) <= 10


def test_build_comparison_report_returns_report() -> None:
    results = (passing_result("present.csv"), failing_result("missing.csv"))

    report = build_comparison_report(results)

    assert isinstance(report, ReferenceComparisonReport)
    assert report.results == results


def test_compare_artifact_sets_passes_for_csv_and_json_specs(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(expected_root / "a.csv", ("id", "condition"), (("1", "normal"),))
    write_csv(actual_root / "a.csv", ("id", "condition"), (("1", "normal"),))
    write_json(expected_root / "meta.json", {"a": 1, "b": 2})
    write_json(actual_root / "meta.json", {"b": 2, "a": 1})
    specs = (
        ArtifactComparisonSpec("a.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("meta.json", COMPARISON_MODE_JSON_EXACT),
    )

    report = compare_artifact_sets(expected_root, actual_root, specs)

    assert report.passed is True
    assert len(report.results) == 2
    assert report.results[0].artifact == "a.csv"
    assert report.results[1].artifact == "meta.json"


def test_compare_artifact_sets_detects_csv_difference(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(expected_root / "a.csv", ("id", "condition"), (("1", "normal"),))
    write_csv(actual_root / "a.csv", ("id", "condition"), (("1", "tumor"),))

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("a.csv", COMPARISON_MODE_CSV_EXACT),),
    )

    assert report.passed is False
    assert report.failed_results()[0].artifact == "a.csv"
    assert any(
        difference.check == "csv_row"
        for difference in report.failed_results()[0].differences
    )


def test_compare_artifact_sets_detects_json_difference(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_json(expected_root / "meta.json", {"a": 1})
    write_json(actual_root / "meta.json", {"a": 2})

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("meta.json", COMPARISON_MODE_JSON_EXACT),),
    )

    assert report.passed is False
    assert report.failed_results()[0].artifact == "meta.json"
    assert any(
        difference.check == "json_exact"
        for difference in report.failed_results()[0].differences
    )


def test_compare_artifact_sets_detects_missing_actual_file(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(expected_root / "a.csv", ("id",), (("1",),))

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("a.csv", COMPARISON_MODE_CSV_EXACT),),
    )

    assert report.passed is False
    assert any(
        difference.check == "actual_file_exists"
        for difference in report.failed_results()[0].differences
    )


def test_compare_artifact_sets_detects_missing_expected_file(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(actual_root / "a.csv", ("id",), (("1",),))

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("a.csv", COMPARISON_MODE_CSV_EXACT),),
    )

    assert report.passed is False
    assert any(
        difference.check == "expected_file_exists"
        for difference in report.failed_results()[0].differences
    )


def test_compare_artifact_sets_file_exists_mode_checks_actual_root_only(
    tmp_path: Path,
) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_text(actual_root / "artifact.txt", "exists\n")

    pass_report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("artifact.txt", COMPARISON_MODE_FILE_EXISTS),),
    )
    fail_report = compare_artifact_sets(
        expected_root,
        actual_root,
        (ArtifactComparisonSpec("missing.txt", COMPARISON_MODE_FILE_EXISTS),),
    )

    assert pass_report.passed is True
    assert fail_report.passed is False
    assert fail_report.failed_results()[0].differences[0].check == "file_exists"


def test_compare_artifact_sets_unknown_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(ReferenceComparisonError):
        compare_artifact_sets(
            tmp_path / "expected",
            tmp_path / "actual",
            (ArtifactComparisonSpec("a.csv", "unknown"),),
        )


def test_compare_artifact_sets_empty_relative_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ReferenceComparisonError):
        compare_artifact_sets(
            tmp_path / "expected",
            tmp_path / "actual",
            (ArtifactComparisonSpec("", COMPARISON_MODE_CSV_EXACT),),
        )


def test_compare_artifact_sets_absolute_relative_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ReferenceComparisonError):
        compare_artifact_sets(
            tmp_path / "expected",
            tmp_path / "actual",
            (
                ArtifactComparisonSpec(
                    str(tmp_path / "outside.csv"),
                    COMPARISON_MODE_CSV_EXACT,
                ),
            ),
        )


@pytest.mark.parametrize(
    "relative_path",
    ("../outside.csv", "nested/../outside.csv"),
)
def test_compare_artifact_sets_path_traversal_raises(
    tmp_path: Path,
    relative_path: str,
) -> None:
    with pytest.raises(ReferenceComparisonError):
        compare_artifact_sets(
            tmp_path / "expected",
            tmp_path / "actual",
            (ArtifactComparisonSpec(relative_path, COMPARISON_MODE_CSV_EXACT),),
        )


def test_compare_artifact_sets_uses_custom_artifact_name(tmp_path: Path) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(expected_root / "nested" / "a.csv", ("id",), (("1",),))
    write_csv(actual_root / "nested" / "a.csv", ("id",), (("2",),))

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (
            ArtifactComparisonSpec(
                "nested/a.csv",
                COMPARISON_MODE_CSV_EXACT,
                artifact="custom artifact",
            ),
        ),
    )

    assert report.failed_results()[0].artifact == "custom artifact"


def test_compare_artifact_sets_continues_after_normal_failure(
    tmp_path: Path,
) -> None:
    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_csv(expected_root / "a.csv", ("id",), (("1",),))
    write_csv(actual_root / "a.csv", ("id",), (("2",),))
    write_json(expected_root / "meta.json", {"a": 1})
    write_json(actual_root / "meta.json", {"a": 1})

    report = compare_artifact_sets(
        expected_root,
        actual_root,
        (
            ArtifactComparisonSpec("a.csv", COMPARISON_MODE_CSV_EXACT),
            ArtifactComparisonSpec("meta.json", COMPARISON_MODE_JSON_EXACT),
        ),
    )

    assert len(report.results) == 2
    assert report.results[0].passed is False
    assert report.results[1].passed is True
