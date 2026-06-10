import csv
import json
from collections.abc import Sequence
from pathlib import Path

from mania.comparison.reference import (
    COMPARISON_STATUS_FAIL,
    COMPARISON_STATUS_PASS,
    ReferenceComparisonReport,
    ReferenceComparisonResult,
    ReferenceDifference,
    build_comparison_report,
    compare_csv_exact,
    compare_file_exists,
    compare_json_exact,
    write_comparison_report,
)


def write_text(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


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


def write_json(path: Path, payload: object) -> Path:
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
