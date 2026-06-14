"""Dependency-free input contracts for future Rg reference comparison."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mania.preprocessing.trajectory_rg_export_validation import (
    validate_rg_timeseries_csv,
)

_TOLERANCE_FIELDS = (
    "rg_abs_tolerance",
    "rg_rel_tolerance",
    "time_abs_tolerance",
)
_BOOLEAN_FIELDS = (
    "require_matching_units",
    "require_matching_frame_indexes",
    "require_matching_condition_names",
    "allow_extra_actual_rows",
    "allow_extra_reference_rows",
)


def _validate_option_values(options: object) -> None:
    for field_name in _TOLERANCE_FIELDS:
        value = getattr(options, field_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(
                f"{field_name} must be a finite non-negative number"
            )
    for field_name in _BOOLEAN_FIELDS:
        if not isinstance(getattr(options, field_name), bool):
            raise ValueError(f"{field_name} must be a bool")


@dataclass(frozen=True)
class PreprocessingRgReferenceComparisonOptions:
    """Options reserved for future Rg reference comparison."""

    rg_abs_tolerance: float = 1e-6
    rg_rel_tolerance: float = 1e-6
    time_abs_tolerance: float = 1e-6
    require_matching_units: bool = True
    require_matching_frame_indexes: bool = True
    require_matching_condition_names: bool = True
    allow_extra_actual_rows: bool = False
    allow_extra_reference_rows: bool = False

    def __post_init__(self) -> None:
        _validate_option_values(self)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable options dictionary."""
        return {
            "rg_abs_tolerance": self.rg_abs_tolerance,
            "rg_rel_tolerance": self.rg_rel_tolerance,
            "time_abs_tolerance": self.time_abs_tolerance,
            "require_matching_units": self.require_matching_units,
            "require_matching_frame_indexes": (
                self.require_matching_frame_indexes
            ),
            "require_matching_condition_names": (
                self.require_matching_condition_names
            ),
            "allow_extra_actual_rows": self.allow_extra_actual_rows,
            "allow_extra_reference_rows": self.allow_extra_reference_rows,
        }


@dataclass(frozen=True)
class PreprocessingRgReferenceComparisonInput:
    """Paths and options for a future Rg reference comparison."""

    actual_csv_path: Path
    reference_csv_path: Path
    options: PreprocessingRgReferenceComparisonOptions = (
        PreprocessingRgReferenceComparisonOptions()
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.options,
            PreprocessingRgReferenceComparisonOptions,
        ):
            raise ValueError(
                "options must be PreprocessingRgReferenceComparisonOptions"
            )
        object.__setattr__(self, "actual_csv_path", Path(self.actual_csv_path))
        object.__setattr__(
            self,
            "reference_csv_path",
            Path(self.reference_csv_path),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable input dictionary."""
        options: object = self.options
        return {
            "actual_csv_path": str(self.actual_csv_path),
            "reference_csv_path": str(self.reference_csv_path),
            "options": (
                options.to_dict()
                if isinstance(
                    options,
                    PreprocessingRgReferenceComparisonOptions,
                )
                else None
            ),
        }


@dataclass(frozen=True)
class PreprocessingRgReferenceComparisonIssue:
    """One deterministic reference comparison input issue."""

    kind: Literal[
        "missing_actual_csv",
        "actual_csv_not_file",
        "missing_reference_csv",
        "reference_csv_not_file",
        "same_actual_and_reference_path",
        "invalid_options",
        "actual_csv_validation_failed",
        "reference_csv_validation_failed",
    ]
    field: str
    message: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable issue dictionary."""
        return {
            "kind": self.kind,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True)
class PreprocessingRgReferenceComparisonInputValidationResult:
    """Readiness report for future Rg reference comparison."""

    comparison_input: PreprocessingRgReferenceComparisonInput
    passed: bool
    actual_csv_validation_passed: bool | None
    reference_csv_validation_passed: bool | None
    issues: tuple[PreprocessingRgReferenceComparisonIssue, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable input validation report."""
        return {
            "comparison_input": self.comparison_input.to_dict(),
            "passed": self.passed,
            "actual_csv_validation_passed": (
                self.actual_csv_validation_passed
            ),
            "reference_csv_validation_passed": (
                self.reference_csv_validation_passed
            ),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_rg_reference_comparison_input(
    comparison_input: PreprocessingRgReferenceComparisonInput,
    *,
    validate_csv_contract: bool = True,
) -> PreprocessingRgReferenceComparisonInputValidationResult:
    """Validate paths, options, and optionally each CSV contract."""
    if not isinstance(
        comparison_input,
        PreprocessingRgReferenceComparisonInput,
    ):
        raise ValueError(
            "comparison_input must be "
            "PreprocessingRgReferenceComparisonInput"
        )

    issues: list[PreprocessingRgReferenceComparisonIssue] = []
    actual_path = comparison_input.actual_csv_path
    reference_path = comparison_input.reference_csv_path
    actual_is_file = _validate_path(
        actual_path,
        missing_kind="missing_actual_csv",
        not_file_kind="actual_csv_not_file",
        field="actual_csv_path",
        issues=issues,
    )
    reference_is_file = _validate_path(
        reference_path,
        missing_kind="missing_reference_csv",
        not_file_kind="reference_csv_not_file",
        field="reference_csv_path",
        issues=issues,
    )

    if (
        actual_is_file
        and reference_is_file
        and actual_path.resolve() == reference_path.resolve()
    ):
        issues.append(
            PreprocessingRgReferenceComparisonIssue(
                kind="same_actual_and_reference_path",
                field="actual_csv_path,reference_csv_path",
                message=(
                    "Actual and reference CSV paths must resolve to "
                    "different files."
                ),
            )
        )

    try:
        _validate_options(comparison_input.options)
    except ValueError:
        issues.append(
            PreprocessingRgReferenceComparisonIssue(
                kind="invalid_options",
                field="options",
                message="Reference comparison options are invalid.",
            )
        )

    actual_csv_validation_passed: bool | None = None
    reference_csv_validation_passed: bool | None = None
    if validate_csv_contract:
        if actual_is_file:
            actual_validation = validate_rg_timeseries_csv(actual_path)
            actual_csv_validation_passed = actual_validation.passed
            if not actual_validation.passed:
                issues.append(
                    PreprocessingRgReferenceComparisonIssue(
                        kind="actual_csv_validation_failed",
                        field="actual_csv_path",
                        message=(
                            "Actual CSV does not satisfy the Rg CSV "
                            "contract."
                        ),
                    )
                )
        if reference_is_file:
            reference_validation = validate_rg_timeseries_csv(reference_path)
            reference_csv_validation_passed = reference_validation.passed
            if not reference_validation.passed:
                issues.append(
                    PreprocessingRgReferenceComparisonIssue(
                        kind="reference_csv_validation_failed",
                        field="reference_csv_path",
                        message=(
                            "Reference CSV does not satisfy the Rg CSV "
                            "contract."
                        ),
                    )
                )

    issue_items = tuple(issues)
    return PreprocessingRgReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        passed=not issue_items,
        actual_csv_validation_passed=actual_csv_validation_passed,
        reference_csv_validation_passed=reference_csv_validation_passed,
        issues=issue_items,
    )


def _validate_options(
    options: PreprocessingRgReferenceComparisonOptions,
) -> None:
    if not isinstance(options, PreprocessingRgReferenceComparisonOptions):
        raise ValueError(
            "options must be PreprocessingRgReferenceComparisonOptions"
        )
    _validate_option_values(options)


def _validate_path(
    path: Path,
    *,
    missing_kind: Literal[
        "missing_actual_csv",
        "missing_reference_csv",
    ],
    not_file_kind: Literal[
        "actual_csv_not_file",
        "reference_csv_not_file",
    ],
    field: str,
    issues: list[PreprocessingRgReferenceComparisonIssue],
) -> bool:
    if not path.exists():
        issues.append(
            PreprocessingRgReferenceComparisonIssue(
                kind=missing_kind,
                field=field,
                message=f"{field} does not exist.",
            )
        )
        return False
    if not path.is_file():
        issues.append(
            PreprocessingRgReferenceComparisonIssue(
                kind=not_file_kind,
                field=field,
                message=f"{field} is not a file.",
            )
        )
        return False
    return True
