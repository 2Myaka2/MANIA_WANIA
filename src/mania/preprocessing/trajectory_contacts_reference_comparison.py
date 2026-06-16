"""Dependency-free contracts for future contacts CSV reference comparison."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mania.preprocessing.trajectory_contacts_export_validation import (
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
)

_TOLERANCE_FIELDS = (
    "distance_abs_tolerance",
    "distance_rel_tolerance",
    "frequency_abs_tolerance",
    "frequency_rel_tolerance",
)
_BOOLEAN_FIELDS = (
    "require_exact_row_order",
    "compare_perframe",
    "compare_contact_edges",
)


_ContactsCsvValidator = Callable[[str | Path], Any]


@dataclass(frozen=True)
class PreprocessingContactsReferenceComparisonOptions:
    """Options reserved for future contacts CSV reference comparison."""

    distance_abs_tolerance: float = 1e-9
    distance_rel_tolerance: float = 1e-9
    frequency_abs_tolerance: float = 1e-12
    frequency_rel_tolerance: float = 1e-12
    require_exact_row_order: bool = False
    compare_perframe: bool = True
    compare_contact_edges: bool = True

    def __post_init__(self) -> None:
        for field_name in _TOLERANCE_FIELDS:
            _require_non_negative_finite_number(
                getattr(self, field_name),
                field_name,
            )
        for field_name in _BOOLEAN_FIELDS:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")
        if not self.compare_perframe and not self.compare_contact_edges:
            raise ValueError(
                "at least one contacts comparison target must be enabled"
            )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable options dictionary."""
        return {
            "distance_abs_tolerance": self.distance_abs_tolerance,
            "distance_rel_tolerance": self.distance_rel_tolerance,
            "frequency_abs_tolerance": self.frequency_abs_tolerance,
            "frequency_rel_tolerance": self.frequency_rel_tolerance,
            "require_exact_row_order": self.require_exact_row_order,
            "compare_perframe": self.compare_perframe,
            "compare_contact_edges": self.compare_contact_edges,
        }


@dataclass(frozen=True)
class PreprocessingContactsReferenceComparisonInput:
    """Paths and options for future contacts CSV reference comparison."""

    generated_contacts_perframe_csv: Path | None = None
    reference_contacts_perframe_csv: Path | None = None
    generated_contact_edges_csv: Path | None = None
    reference_contact_edges_csv: Path | None = None
    options: PreprocessingContactsReferenceComparisonOptions = field(
        default_factory=PreprocessingContactsReferenceComparisonOptions
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.options,
            PreprocessingContactsReferenceComparisonOptions,
        ):
            raise ValueError(
                "options must be "
                "PreprocessingContactsReferenceComparisonOptions"
            )
        for field_name in (
            "generated_contacts_perframe_csv",
            "reference_contacts_perframe_csv",
            "generated_contact_edges_csv",
            "reference_contact_edges_csv",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, Path(value))

    @property
    def has_perframe_pair(self) -> bool:
        """Return whether both per-frame CSV paths are present."""
        return (
            self.generated_contacts_perframe_csv is not None
            and self.reference_contacts_perframe_csv is not None
        )

    @property
    def has_contact_edges_pair(self) -> bool:
        """Return whether both aggregate contacts CSV paths are present."""
        return (
            self.generated_contact_edges_csv is not None
            and self.reference_contact_edges_csv is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable input dictionary."""
        return {
            "generated_contacts_perframe_csv": _path_to_string(
                self.generated_contacts_perframe_csv
            ),
            "reference_contacts_perframe_csv": _path_to_string(
                self.reference_contacts_perframe_csv
            ),
            "generated_contact_edges_csv": _path_to_string(
                self.generated_contact_edges_csv
            ),
            "reference_contact_edges_csv": _path_to_string(
                self.reference_contact_edges_csv
            ),
            "options": self.options.to_dict(),
        }


@dataclass(frozen=True)
class PreprocessingContactsReferenceComparisonIssue:
    """One deterministic contacts reference comparison input issue."""

    kind: str
    field: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _non_empty_string(self.kind, "kind"))
        object.__setattr__(
            self,
            "field",
            _non_empty_string(self.field, "field"),
        )
        object.__setattr__(
            self,
            "message",
            _non_empty_string(self.message, "message"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable issue dictionary."""
        return {
            "kind": self.kind,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True)
class PreprocessingContactsReferenceComparisonInputValidationResult:
    """Readiness report for future contacts CSV reference comparison."""

    comparison_input: PreprocessingContactsReferenceComparisonInput
    passed: bool
    perframe_enabled: bool
    contact_edges_enabled: bool
    issues: tuple[PreprocessingContactsReferenceComparisonIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(
            self.comparison_input,
            PreprocessingContactsReferenceComparisonInput,
        ):
            raise ValueError(
                "comparison_input must be "
                "PreprocessingContactsReferenceComparisonInput"
            )
        for field_name in (
            "passed",
            "perframe_enabled",
            "contact_edges_enabled",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")
        for issue in self.issues:
            if not isinstance(
                issue,
                PreprocessingContactsReferenceComparisonIssue,
            ):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingContactsReferenceComparisonIssue"
                )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable input validation report."""
        return {
            "comparison_input": self.comparison_input.to_dict(),
            "passed": self.passed,
            "perframe_enabled": self.perframe_enabled,
            "contact_edges_enabled": self.contact_edges_enabled,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_contacts_reference_comparison_input(
    comparison_input: PreprocessingContactsReferenceComparisonInput,
) -> PreprocessingContactsReferenceComparisonInputValidationResult:
    """Validate paths, options, and CSV contracts for requested targets."""
    if not isinstance(
        comparison_input,
        PreprocessingContactsReferenceComparisonInput,
    ):
        raise ValueError(
            "comparison_input must be "
            "PreprocessingContactsReferenceComparisonInput"
        )

    issues: list[PreprocessingContactsReferenceComparisonIssue] = []
    options = comparison_input.options
    try:
        _validate_options(options)
    except ValueError:
        issues.append(
            _issue(
                "invalid_options",
                "options",
                "Contacts reference comparison options are invalid.",
            )
        )

    if options.compare_perframe:
        _validate_target_pair(
            generated_path=comparison_input.generated_contacts_perframe_csv,
            reference_path=comparison_input.reference_contacts_perframe_csv,
            generated_field="generated_contacts_perframe_csv",
            reference_field="reference_contacts_perframe_csv",
            missing_generated_kind="missing_generated_perframe_csv",
            missing_reference_kind="missing_reference_perframe_csv",
            validation_failed_kind="perframe_validation_failed",
            validator=validate_contacts_perframe_csv,
            issues=issues,
        )
    if options.compare_contact_edges:
        _validate_target_pair(
            generated_path=comparison_input.generated_contact_edges_csv,
            reference_path=comparison_input.reference_contact_edges_csv,
            generated_field="generated_contact_edges_csv",
            reference_field="reference_contact_edges_csv",
            missing_generated_kind="missing_generated_contact_edges_csv",
            missing_reference_kind="missing_reference_contact_edges_csv",
            validation_failed_kind="contact_edges_validation_failed",
            validator=validate_contact_edges_csv,
            issues=issues,
        )
    if not options.compare_perframe and not options.compare_contact_edges:
        issues.append(
            _issue(
                "missing_comparison_target",
                "options",
                "At least one contacts comparison target must be enabled.",
            )
        )

    issue_items = tuple(issues)
    return PreprocessingContactsReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        passed=not issue_items,
        perframe_enabled=options.compare_perframe,
        contact_edges_enabled=options.compare_contact_edges,
        issues=issue_items,
    )


def _validate_target_pair(
    *,
    generated_path: Path | None,
    reference_path: Path | None,
    generated_field: str,
    reference_field: str,
    missing_generated_kind: str,
    missing_reference_kind: str,
    validation_failed_kind: str,
    validator: _ContactsCsvValidator,
    issues: list[PreprocessingContactsReferenceComparisonIssue],
) -> None:
    generated_is_file = _validate_required_path(
        generated_path,
        field=generated_field,
        missing_kind=missing_generated_kind,
        issues=issues,
    )
    reference_is_file = _validate_required_path(
        reference_path,
        field=reference_field,
        missing_kind=missing_reference_kind,
        issues=issues,
    )
    if generated_is_file and reference_is_file:
        assert generated_path is not None
        assert reference_path is not None
        if _same_resolved_path(generated_path, reference_path):
            issues.append(
                _issue(
                    "same_generated_and_reference_path",
                    f"{generated_field},{reference_field}",
                    (
                        "Generated and reference CSV paths must resolve to "
                        "different files."
                    ),
                )
            )
        _validate_csv_contract(
            generated_path,
            field=generated_field,
            validation_failed_kind=validation_failed_kind,
            validator=validator,
            issues=issues,
        )
        _validate_csv_contract(
            reference_path,
            field=reference_field,
            validation_failed_kind=validation_failed_kind,
            validator=validator,
            issues=issues,
        )


def _validate_required_path(
    path: Path | None,
    *,
    field: str,
    missing_kind: str,
    issues: list[PreprocessingContactsReferenceComparisonIssue],
) -> bool:
    if path is None:
        issues.append(
            _issue(
                missing_kind,
                field,
                "Requested contacts comparison CSV path is missing.",
            )
        )
        return False
    if not path.exists():
        issues.append(
            _issue(
                "path_missing",
                field,
                "Requested contacts comparison CSV path does not exist.",
            )
        )
        return False
    if path.is_dir():
        issues.append(
            _issue(
                "path_is_directory",
                field,
                "Requested contacts comparison CSV path is a directory.",
            )
        )
        return False
    return True


def _validate_csv_contract(
    path: Path,
    *,
    field: str,
    validation_failed_kind: str,
    validator: _ContactsCsvValidator,
    issues: list[PreprocessingContactsReferenceComparisonIssue],
) -> None:
    if not callable(validator):
        raise ValueError("validator must be callable")
    result = validator(path)
    if not result.passed:
        issues.append(
            _issue(
                validation_failed_kind,
                field,
                "Contacts comparison CSV does not satisfy its CSV contract.",
            )
        )


def _same_resolved_path(generated_path: Path, reference_path: Path) -> bool:
    try:
        return generated_path.resolve() == reference_path.resolve()
    except OSError:
        return generated_path == reference_path


def _validate_options(
    options: PreprocessingContactsReferenceComparisonOptions,
) -> None:
    if not isinstance(options, PreprocessingContactsReferenceComparisonOptions):
        raise ValueError(
            "options must be PreprocessingContactsReferenceComparisonOptions"
        )
    options.__post_init__()


def _require_non_negative_finite_number(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a finite non-negative number")


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _path_to_string(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _issue(
    kind: str,
    field: str,
    message: str,
) -> PreprocessingContactsReferenceComparisonIssue:
    return PreprocessingContactsReferenceComparisonIssue(
        kind=kind,
        field=field,
        message=message,
    )
