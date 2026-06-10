"""Lightweight reference artifact comparison helpers."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPARISON_STATUS_PASS = "pass"
COMPARISON_STATUS_FAIL = "fail"

COMPARISON_MODE_FILE_EXISTS = "file_exists"
COMPARISON_MODE_CSV_EXACT = "csv_exact"
COMPARISON_MODE_JSON_EXACT = "json_exact"

_MAX_CSV_ROW_DIFFERENCES = 10


class ReferenceComparisonError(Exception):
    """Raised when the comparison harness is used with invalid inputs."""


@dataclass(frozen=True)
class ReferenceDifference:
    """A machine-readable difference found during reference comparison."""

    artifact: str
    check: str
    expected: str
    actual: str
    message: str


@dataclass(frozen=True)
class ReferenceComparisonResult:
    """Result for one compared artifact."""

    artifact: str
    status: str
    differences: tuple[ReferenceDifference, ...]

    @property
    def passed(self) -> bool:
        """Return whether this artifact comparison passed."""
        return self.status == COMPARISON_STATUS_PASS and not self.differences


@dataclass(frozen=True)
class ReferenceComparisonReport:
    """Collection of reference comparison results."""

    results: tuple[ReferenceComparisonResult, ...]

    @property
    def passed(self) -> bool:
        """Return whether every artifact comparison passed."""
        return all(result.passed for result in self.results)

    def failed_results(self) -> tuple[ReferenceComparisonResult, ...]:
        """Return only failing artifact comparison results."""
        return tuple(result for result in self.results if not result.passed)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of this report."""
        return {
            "passed": self.passed,
            "results": [
                {
                    "artifact": result.artifact,
                    "status": result.status,
                    "passed": result.passed,
                    "differences": [
                        {
                            "artifact": difference.artifact,
                            "check": difference.check,
                            "expected": difference.expected,
                            "actual": difference.actual,
                            "message": difference.message,
                        }
                        for difference in result.differences
                    ],
                }
                for result in self.results
            ],
        }


@dataclass(frozen=True)
class ArtifactComparisonSpec:
    """Specification for comparing one artifact relative to two roots."""

    relative_path: str
    mode: str
    artifact: str | None = None


def compare_file_exists(
    path: str | Path,
    artifact: str | None = None,
) -> ReferenceComparisonResult:
    """Compare whether a file exists."""
    file_path = Path(path)
    artifact_name = _artifact_name(artifact, file_path)
    if file_path.is_file():
        return _pass_result(artifact_name)
    return _fail_result(
        artifact_name,
        ReferenceDifference(
            artifact=artifact_name,
            check="file_exists",
            expected="exists",
            actual="missing",
            message=f"Expected file to exist: {file_path}",
        ),
    )


def compare_csv_exact(
    expected_path: str | Path,
    actual_path: str | Path,
    artifact: str | None = None,
) -> ReferenceComparisonResult:
    """Compare two CSV files exactly as rows of strings."""
    expected_csv_path = Path(expected_path)
    actual_csv_path = Path(actual_path)
    artifact_name = _artifact_name(artifact, actual_csv_path, expected_csv_path)
    missing_file_differences = _missing_file_differences(
        artifact_name,
        (("expected", expected_csv_path), ("actual", actual_csv_path)),
    )
    if missing_file_differences:
        return _result_from_differences(artifact_name, missing_file_differences)

    expected_rows = _read_csv_rows(expected_csv_path)
    actual_rows = _read_csv_rows(actual_csv_path)

    differences: list[ReferenceDifference] = []
    expected_header = expected_rows[0] if expected_rows else []
    actual_header = actual_rows[0] if actual_rows else []
    if expected_header != actual_header:
        differences.append(
            ReferenceDifference(
                artifact=artifact_name,
                check="csv_header",
                expected=_json_string(expected_header),
                actual=_json_string(actual_header),
                message="CSV header differs",
            )
        )

    expected_data_rows = expected_rows[1:] if expected_rows else []
    actual_data_rows = actual_rows[1:] if actual_rows else []
    if len(expected_data_rows) != len(actual_data_rows):
        differences.append(
            ReferenceDifference(
                artifact=artifact_name,
                check="csv_row_count",
                expected=str(len(expected_data_rows)),
                actual=str(len(actual_data_rows)),
                message="CSV data row count differs",
            )
        )

    differing_rows = 0
    for row_index, (expected_row, actual_row) in enumerate(
        zip(expected_data_rows, actual_data_rows, strict=False),
        start=2,
    ):
        if expected_row == actual_row:
            continue
        differences.append(
            ReferenceDifference(
                artifact=artifact_name,
                check="csv_row",
                expected=_json_string(expected_row),
                actual=_json_string(actual_row),
                message=f"CSV row {row_index} differs",
            )
        )
        differing_rows += 1
        if differing_rows >= _MAX_CSV_ROW_DIFFERENCES:
            break

    return _result_from_differences(artifact_name, tuple(differences))


def compare_json_exact(
    expected_path: str | Path,
    actual_path: str | Path,
    artifact: str | None = None,
) -> ReferenceComparisonResult:
    """Compare two JSON files exactly after loading them as Python objects."""
    expected_json_path = Path(expected_path)
    actual_json_path = Path(actual_path)
    artifact_name = _artifact_name(artifact, actual_json_path, expected_json_path)
    missing_file_differences = _missing_file_differences(
        artifact_name,
        (("expected", expected_json_path), ("actual", actual_json_path)),
    )
    if missing_file_differences:
        return _result_from_differences(artifact_name, missing_file_differences)

    expected_object = _read_json(expected_json_path)
    actual_object = _read_json(actual_json_path)
    if expected_object == actual_object:
        return _pass_result(artifact_name)
    return _fail_result(
        artifact_name,
        ReferenceDifference(
            artifact=artifact_name,
            check="json_exact",
            expected=_json_string(expected_object),
            actual=_json_string(actual_object),
            message="JSON objects differ",
        ),
    )


def compare_artifact_sets(
    expected_root: str | Path,
    actual_root: str | Path,
    specs: Iterable[ArtifactComparisonSpec],
) -> ReferenceComparisonReport:
    """Compare artifacts under two roots according to ordered specs."""
    expected_root_path = Path(expected_root)
    actual_root_path = Path(actual_root)
    results: list[ReferenceComparisonResult] = []

    for spec in specs:
        relative_path = _validate_artifact_relative_path(spec.relative_path)
        artifact_name = (
            spec.artifact if spec.artifact is not None else spec.relative_path
        )
        expected_path = expected_root_path / relative_path
        actual_path = actual_root_path / relative_path

        if spec.mode == COMPARISON_MODE_FILE_EXISTS:
            results.append(compare_file_exists(actual_path, artifact=artifact_name))
            continue

        if spec.mode == COMPARISON_MODE_CSV_EXACT:
            missing_differences = _expected_actual_file_differences(
                artifact_name,
                expected_path,
                actual_path,
            )
            if missing_differences:
                results.append(
                    _result_from_differences(artifact_name, missing_differences)
                )
                continue
            results.append(
                compare_csv_exact(expected_path, actual_path, artifact=artifact_name)
            )
            continue

        if spec.mode == COMPARISON_MODE_JSON_EXACT:
            missing_differences = _expected_actual_file_differences(
                artifact_name,
                expected_path,
                actual_path,
            )
            if missing_differences:
                results.append(
                    _result_from_differences(artifact_name, missing_differences)
                )
                continue
            results.append(
                compare_json_exact(expected_path, actual_path, artifact=artifact_name)
            )
            continue

        raise ReferenceComparisonError(f"Unknown comparison mode: {spec.mode!r}")

    return build_comparison_report(results)


def build_comparison_report(
    results: Iterable[ReferenceComparisonResult],
) -> ReferenceComparisonReport:
    """Build a reference comparison report from comparison results."""
    return ReferenceComparisonReport(results=tuple(results))


def write_comparison_report(
    report: ReferenceComparisonReport,
    path: str | Path,
) -> Path:
    """Write a reference comparison report as stable pretty JSON."""
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def _artifact_name(
    artifact: str | None,
    primary_path: Path,
    fallback_path: Path | None = None,
) -> str:
    if artifact is not None:
        return artifact
    if primary_path.name:
        return primary_path.name
    if fallback_path is not None and fallback_path.name:
        return fallback_path.name
    raise ReferenceComparisonError("Artifact name could not be inferred")


def _pass_result(artifact: str) -> ReferenceComparisonResult:
    return ReferenceComparisonResult(
        artifact=artifact,
        status=COMPARISON_STATUS_PASS,
        differences=(),
    )


def _fail_result(
    artifact: str,
    difference: ReferenceDifference,
) -> ReferenceComparisonResult:
    return ReferenceComparisonResult(
        artifact=artifact,
        status=COMPARISON_STATUS_FAIL,
        differences=(difference,),
    )


def _result_from_differences(
    artifact: str,
    differences: tuple[ReferenceDifference, ...],
) -> ReferenceComparisonResult:
    status = COMPARISON_STATUS_FAIL if differences else COMPARISON_STATUS_PASS
    return ReferenceComparisonResult(
        artifact=artifact,
        status=status,
        differences=differences,
    )


def _missing_file_differences(
    artifact: str,
    paths: tuple[tuple[str, Path], ...],
) -> tuple[ReferenceDifference, ...]:
    differences: list[ReferenceDifference] = []
    for label, path in paths:
        if path.is_file():
            continue
        differences.append(
            ReferenceDifference(
                artifact=artifact,
                check="file_exists",
                expected=f"{label} exists",
                actual="missing",
                message=f"Expected {label} file to exist: {path}",
            )
        )
    return tuple(differences)


def _expected_actual_file_differences(
    artifact: str,
    expected_path: Path,
    actual_path: Path,
) -> tuple[ReferenceDifference, ...]:
    differences: list[ReferenceDifference] = []
    if not expected_path.is_file():
        differences.append(
            ReferenceDifference(
                artifact=artifact,
                check="expected_file_exists",
                expected="exists",
                actual="missing",
                message=f"Expected reference file to exist: {expected_path}",
            )
        )
    if not actual_path.is_file():
        differences.append(
            ReferenceDifference(
                artifact=artifact,
                check="actual_file_exists",
                expected="exists",
                actual="missing",
                message=f"Expected actual file to exist: {actual_path}",
            )
        )
    return tuple(differences)


def _validate_artifact_relative_path(relative_path: str) -> Path:
    if relative_path == "":
        raise ReferenceComparisonError("Artifact relative path must not be empty")
    path = Path(relative_path)
    if path.is_absolute():
        raise ReferenceComparisonError(
            f"Artifact relative path must not be absolute: {relative_path!r}"
        )
    if ".." in path.parts:
        raise ReferenceComparisonError(
            f"Artifact relative path must not contain '..': {relative_path!r}"
        )
    return path


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.reader(csv_file))


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as json_file:
            return json.load(json_file)
    except json.JSONDecodeError as exc:
        raise ReferenceComparisonError(f"Invalid JSON file: {path}") from exc


def _json_string(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


__all__ = [
    "ArtifactComparisonSpec",
    "COMPARISON_MODE_CSV_EXACT",
    "COMPARISON_MODE_FILE_EXISTS",
    "COMPARISON_MODE_JSON_EXACT",
    "COMPARISON_STATUS_FAIL",
    "COMPARISON_STATUS_PASS",
    "ReferenceComparisonError",
    "ReferenceComparisonReport",
    "ReferenceComparisonResult",
    "ReferenceDifference",
    "build_comparison_report",
    "compare_artifact_sets",
    "compare_csv_exact",
    "compare_file_exists",
    "compare_json_exact",
    "write_comparison_report",
]
