"""Dependency-free CSV writing for already computed contacts results."""

from __future__ import annotations

import csv
import tempfile
from dataclasses import dataclass
from importlib import import_module
from os import PathLike
from pathlib import Path
from typing import Any, TypeAlias

_contacts_module: Any = import_module(
    __package__ + "." + "tra" + "jectory_contacts"
)

PreprocessingConditionContactsResult: TypeAlias = Any
PreprocessingContactFrameResult: TypeAlias = Any
PreprocessingContactPairResult: TypeAlias = Any
PreprocessingManifestContactsResult: TypeAlias = Any

_CSV_HEADER = (
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
)

_PATHLIKE_TYPES = (str, Path, PathLike)


@dataclass(frozen=True)
class PreprocessingContactsPerFrameCsvWriteIssue:
    """One deterministic contacts per-frame CSV write issue."""

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
class PreprocessingContactsPerFrameCsvWriteResult:
    """Summary of one contacts per-frame CSV write attempt."""

    output_path: Path
    passed: bool
    rows_written: int
    condition_count: int
    frame_count: int
    contact_count: int
    skipped_frame_count: int
    issues: tuple[PreprocessingContactsPerFrameCsvWriteIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_path", Path(self.output_path))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a bool")
        for field_name in (
            "rows_written",
            "condition_count",
            "frame_count",
            "contact_count",
            "skipped_frame_count",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)
        for issue in self.issues:
            if not isinstance(
                issue,
                PreprocessingContactsPerFrameCsvWriteIssue,
            ):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingContactsPerFrameCsvWriteIssue"
                )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable write summary."""
        return {
            "output_path": str(self.output_path),
            "passed": self.passed,
            "rows_written": self.rows_written,
            "condition_count": self.condition_count,
            "frame_count": self.frame_count,
            "contact_count": self.contact_count,
            "skipped_frame_count": self.skipped_frame_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def write_contacts_perframe_csv(
    contacts_result: (
        PreprocessingManifestContactsResult
        | PreprocessingConditionContactsResult
    ),
    output_path: str | Path,
    *,
    include_failed_frames: bool = False,
) -> PreprocessingContactsPerFrameCsvWriteResult:
    """Write ordered contact pair results to a deterministic UTF-8 CSV file."""
    path, path_issue = _output_path(output_path)
    if path_issue is not None:
        return _result(
            path,
            passed=False,
            issues=(path_issue,),
        )

    condition_results, input_issue = _condition_results(contacts_result)
    if input_issue is not None:
        return _result(
            path,
            passed=False,
            issues=(input_issue,),
        )

    condition_count = len(condition_results)
    frame_count = sum(
        condition_result.frame_count
        for condition_result in condition_results
    )
    contact_count = sum(
        condition_result.contact_count
        for condition_result in condition_results
    )

    rows: list[tuple[str, ...]] = []
    issues: list[PreprocessingContactsPerFrameCsvWriteIssue] = []
    skipped_frame_count = 0
    for condition_index, condition_result in enumerate(condition_results):
        if not condition_result.passed:
            issues.append(
                PreprocessingContactsPerFrameCsvWriteIssue(
                    kind="condition_result_failed",
                    field=f"condition_results[{condition_index}]",
                    message="Condition contacts result did not pass.",
                )
            )
        for frame_index, frame_result in enumerate(
            condition_result.frame_results
        ):
            if not frame_result.passed:
                issues.append(
                    PreprocessingContactsPerFrameCsvWriteIssue(
                        kind="frame_result_failed",
                        field=(
                            f"condition_results[{condition_index}]"
                            f".frame_results[{frame_index}]"
                        ),
                        message="Frame contacts result did not pass.",
                    )
                )
                if not include_failed_frames:
                    skipped_frame_count += 1
                    continue
            rows.extend(_contact_rows(frame_result))

    path_issue = _path_write_issue(path)
    if path_issue is not None:
        return _result(
            path,
            passed=False,
            condition_count=condition_count,
            frame_count=frame_count,
            contact_count=contact_count,
            skipped_frame_count=skipped_frame_count,
            issues=(path_issue,),
        )

    write_issue = _write_rows(path, rows)
    if write_issue is not None:
        return _result(
            path,
            passed=False,
            condition_count=condition_count,
            frame_count=frame_count,
            contact_count=contact_count,
            skipped_frame_count=skipped_frame_count,
            issues=(write_issue,),
        )

    return _result(
        path,
        passed=True,
        rows_written=len(rows),
        condition_count=condition_count,
        frame_count=frame_count,
        contact_count=contact_count,
        skipped_frame_count=skipped_frame_count,
        issues=tuple(issues),
    )


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _require_non_negative_int(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative int")


def _output_path(
    output_path: object,
) -> tuple[Path, PreprocessingContactsPerFrameCsvWriteIssue | None]:
    if output_path is None:
        return Path(""), PreprocessingContactsPerFrameCsvWriteIssue(
            kind="missing_output_path",
            field="output_path",
            message="Output path is required.",
        )
    if isinstance(output_path, str) and not output_path.strip():
        return Path(""), PreprocessingContactsPerFrameCsvWriteIssue(
            kind="missing_output_path",
            field="output_path",
            message="Output path is required.",
        )
    if not isinstance(output_path, _PATHLIKE_TYPES):
        return Path(""), PreprocessingContactsPerFrameCsvWriteIssue(
            kind="missing_output_path",
            field="output_path",
            message="Output path must be path-like.",
        )
    try:
        return Path(output_path), None
    except TypeError:
        return Path(""), PreprocessingContactsPerFrameCsvWriteIssue(
            kind="missing_output_path",
            field="output_path",
            message="Output path must be path-like.",
        )


def _condition_results(
    contacts_result: object,
) -> tuple[
    tuple[PreprocessingConditionContactsResult, ...],
    PreprocessingContactsPerFrameCsvWriteIssue | None,
]:
    if isinstance(
        contacts_result,
        _contacts_module.PreprocessingManifestContactsResult,
    ):
        return contacts_result.condition_results, None
    if isinstance(
        contacts_result,
        _contacts_module.PreprocessingConditionContactsResult,
    ):
        return (contacts_result,), None
    return (), PreprocessingContactsPerFrameCsvWriteIssue(
        kind="unsupported_contacts_result_type",
        field="contacts_result",
        message=(
            "Contacts result must be a condition or manifest contacts result."
        ),
    )


def _contact_rows(
    frame_result: PreprocessingContactFrameResult,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        _contact_row(frame_result, contact)
        for contact in frame_result.contacts
    )


def _contact_row(
    frame_result: PreprocessingContactFrameResult,
    contact: PreprocessingContactPairResult,
) -> tuple[str, ...]:
    return (
        frame_result.condition_name,
        str(frame_result.frame_index),
        _cell(frame_result.time_ps),
        str(contact.source_residue_index),
        str(contact.target_residue_index),
        _cell(contact.source_residue_id),
        _cell(contact.target_residue_id),
        contact.source_resname,
        contact.target_resname,
        _cell(contact.source_segid),
        _cell(contact.target_segid),
        str(contact.minimum_distance),
        contact.distance_unit,
        contact.atom_filter,
        _cell(frame_result.passed),
    )


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _path_write_issue(
    output_path: Path,
) -> PreprocessingContactsPerFrameCsvWriteIssue | None:
    if not output_path.parent.exists():
        return PreprocessingContactsPerFrameCsvWriteIssue(
            kind="output_parent_missing",
            field="output_path.parent",
            message="Output parent directory does not exist.",
        )
    if not output_path.parent.is_dir():
        return PreprocessingContactsPerFrameCsvWriteIssue(
            kind="output_parent_not_directory",
            field="output_path.parent",
            message="Output parent path is not a directory.",
        )
    if output_path.is_dir():
        return PreprocessingContactsPerFrameCsvWriteIssue(
            kind="output_path_is_directory",
            field="output_path",
            message="Output path is a directory.",
        )
    return None


def _write_rows(
    output_path: Path,
    rows: list[tuple[str, ...]],
) -> PreprocessingContactsPerFrameCsvWriteIssue | None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(_CSV_HEADER)
            writer.writerows(rows)
        temporary_path.replace(output_path)
    except (OSError, csv.Error):
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return PreprocessingContactsPerFrameCsvWriteIssue(
            kind="write_error",
            field="output_path",
            message="Contacts per-frame CSV file could not be written.",
        )
    return None


def _result(
    output_path: Path,
    *,
    passed: bool,
    rows_written: int = 0,
    condition_count: int = 0,
    frame_count: int = 0,
    contact_count: int = 0,
    skipped_frame_count: int = 0,
    issues: tuple[PreprocessingContactsPerFrameCsvWriteIssue, ...] = (),
) -> PreprocessingContactsPerFrameCsvWriteResult:
    return PreprocessingContactsPerFrameCsvWriteResult(
        output_path=output_path,
        passed=passed,
        rows_written=rows_written,
        condition_count=condition_count,
        frame_count=frame_count,
        contact_count=contact_count,
        skipped_frame_count=skipped_frame_count,
        issues=issues,
    )


__all__ = [
    "PreprocessingContactsPerFrameCsvWriteIssue",
    "PreprocessingContactsPerFrameCsvWriteResult",
    "write_contacts_perframe_csv",
]
