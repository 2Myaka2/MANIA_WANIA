"""Reference artifact comparison helpers."""

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
