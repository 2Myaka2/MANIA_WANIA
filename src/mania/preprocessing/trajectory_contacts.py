"""Dependency-free definition and options contracts for contact detection."""

from __future__ import annotations

import math
from dataclasses import dataclass

_ATOM_FILTERS = ("heavy", "all")
_CONTACT_LEVEL = "residue"
_DISTANCE_DEFINITION = "minimum_selected_atom_distance"
_FRAME_SCOPE = "per_frame"
_PAIR_SCOPE = "distinct_residue_pair"
_CONTACT_RESULT_STATUSES = (
    "not_computed",
    "computed",
    "partial",
    "failed",
)
_BOOLEAN_OPTION_FIELDS = (
    "exclude_same_residue",
    "exclude_duplicate_pairs",
    "include_frame_index",
    "include_time_ps",
)


def _require_positive_finite_number(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a finite positive number")


def _normalize_unit(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("distance_unit must be a non-empty string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("distance_unit must be a non-empty string")
    return normalized


def _normalize_skip_resnames(value: object) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError("skip_resnames must be a list or tuple")

    normalized_resnames: list[str] = []
    seen_resnames: set[str] = set()
    for resname in value:
        if not isinstance(resname, str):
            raise ValueError("skip_resnames entries must be strings")
        normalized = resname.strip()
        if not normalized:
            raise ValueError("skip_resnames entries must not be empty")
        if normalized not in seen_resnames:
            normalized_resnames.append(normalized)
            seen_resnames.add(normalized)
    return tuple(normalized_resnames)


def _normalize_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _normalize_optional_residue_id(
    value: object,
    field_name: str,
) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an int, string, or None")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _normalize_non_empty_string(value, field_name)
    raise ValueError(f"{field_name} must be an int, string, or None")


def _normalize_optional_string(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _normalize_non_empty_string(value, field_name)


def _require_non_negative_int(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative int")


def _require_non_negative_finite_number(
    value: object,
    field_name: str,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"{field_name} must be a finite non-negative number"
        )


def _require_optional_non_negative_finite_number(
    value: object,
    field_name: str,
) -> None:
    if value is not None:
        _require_non_negative_finite_number(value, field_name)


@dataclass(frozen=True)
class PreprocessingContactDefinition:
    """Serializable definition of the Stage 13 residue contact MVP."""

    contact_level: str = _CONTACT_LEVEL
    distance_definition: str = _DISTANCE_DEFINITION
    frame_scope: str = _FRAME_SCOPE
    pair_scope: str = _PAIR_SCOPE
    default_atom_filter: str = "heavy"
    default_cutoff_distance: float = 4.5
    distance_unit: str = "angstrom"

    def __post_init__(self) -> None:
        if self.contact_level != _CONTACT_LEVEL:
            raise ValueError("contact_level must be 'residue'")
        if self.distance_definition != _DISTANCE_DEFINITION:
            raise ValueError(
                "distance_definition must be "
                "'minimum_selected_atom_distance'"
            )
        if self.frame_scope != _FRAME_SCOPE:
            raise ValueError("frame_scope must be 'per_frame'")
        if self.pair_scope != _PAIR_SCOPE:
            raise ValueError("pair_scope must be 'distinct_residue_pair'")
        if self.default_atom_filter not in _ATOM_FILTERS:
            raise ValueError("default_atom_filter must be 'heavy' or 'all'")
        _require_positive_finite_number(
            self.default_cutoff_distance,
            "default_cutoff_distance",
        )
        object.__setattr__(
            self,
            "distance_unit",
            _normalize_unit(self.distance_unit),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable definition dictionary."""
        return {
            "contact_level": self.contact_level,
            "distance_definition": self.distance_definition,
            "frame_scope": self.frame_scope,
            "pair_scope": self.pair_scope,
            "default_atom_filter": self.default_atom_filter,
            "default_cutoff_distance": self.default_cutoff_distance,
            "distance_unit": self.distance_unit,
        }


@dataclass(frozen=True)
class PreprocessingContactDetectionOptions:
    """Configuration reserved for future residue contact extraction."""

    cutoff_distance: float = 4.5
    distance_unit: str = "angstrom"
    atom_filter: str = "heavy"
    contact_level: str = _CONTACT_LEVEL
    exclude_same_residue: bool = True
    exclude_duplicate_pairs: bool = True
    skip_resnames: tuple[str, ...] = ()
    include_frame_index: bool = True
    include_time_ps: bool = True

    def __post_init__(self) -> None:
        _require_positive_finite_number(
            self.cutoff_distance,
            "cutoff_distance",
        )
        object.__setattr__(
            self,
            "distance_unit",
            _normalize_unit(self.distance_unit),
        )
        if self.atom_filter not in _ATOM_FILTERS:
            raise ValueError("atom_filter must be 'heavy' or 'all'")
        if self.contact_level != _CONTACT_LEVEL:
            raise ValueError("contact_level must be 'residue'")
        for field_name in _BOOLEAN_OPTION_FIELDS:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")
        object.__setattr__(
            self,
            "skip_resnames",
            _normalize_skip_resnames(self.skip_resnames),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable options dictionary."""
        return {
            "cutoff_distance": self.cutoff_distance,
            "distance_unit": self.distance_unit,
            "atom_filter": self.atom_filter,
            "contact_level": self.contact_level,
            "exclude_same_residue": self.exclude_same_residue,
            "exclude_duplicate_pairs": self.exclude_duplicate_pairs,
            "skip_resnames": list(self.skip_resnames),
            "include_frame_index": self.include_frame_index,
            "include_time_ps": self.include_time_ps,
        }


@dataclass(frozen=True)
class PreprocessingContactComputationIssue:
    """One deterministic contacts result or computation issue."""

    kind: str
    field: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "kind",
            _normalize_non_empty_string(self.kind, "kind"),
        )
        object.__setattr__(
            self,
            "field",
            _normalize_non_empty_string(self.field, "field"),
        )
        object.__setattr__(
            self,
            "message",
            _normalize_non_empty_string(self.message, "message"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable issue dictionary."""
        return {
            "kind": self.kind,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True)
class PreprocessingContactPairResult:
    """One residue-residue contact observed in one frame."""

    source_residue_index: int
    target_residue_index: int
    source_resname: str
    target_resname: str
    minimum_distance: float
    distance_unit: str = "angstrom"
    atom_filter: str = "heavy"
    source_residue_id: int | str | None = None
    target_residue_id: int | str | None = None
    source_segid: str | None = None
    target_segid: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int(
            self.source_residue_index,
            "source_residue_index",
        )
        _require_non_negative_int(
            self.target_residue_index,
            "target_residue_index",
        )
        if self.source_residue_index == self.target_residue_index:
            raise ValueError("source and target residue indexes must differ")
        object.__setattr__(
            self,
            "source_resname",
            _normalize_non_empty_string(
                self.source_resname,
                "source_resname",
            ),
        )
        object.__setattr__(
            self,
            "target_resname",
            _normalize_non_empty_string(
                self.target_resname,
                "target_resname",
            ),
        )
        _require_non_negative_finite_number(
            self.minimum_distance,
            "minimum_distance",
        )
        object.__setattr__(
            self,
            "distance_unit",
            _normalize_unit(self.distance_unit),
        )
        if self.atom_filter not in _ATOM_FILTERS:
            raise ValueError("atom_filter must be 'heavy' or 'all'")
        object.__setattr__(
            self,
            "source_residue_id",
            _normalize_optional_residue_id(
                self.source_residue_id,
                "source_residue_id",
            ),
        )
        object.__setattr__(
            self,
            "target_residue_id",
            _normalize_optional_residue_id(
                self.target_residue_id,
                "target_residue_id",
            ),
        )
        object.__setattr__(
            self,
            "source_segid",
            _normalize_optional_string(self.source_segid, "source_segid"),
        )
        object.__setattr__(
            self,
            "target_segid",
            _normalize_optional_string(self.target_segid, "target_segid"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable contact pair."""
        return {
            "source_residue_index": self.source_residue_index,
            "target_residue_index": self.target_residue_index,
            "source_resname": self.source_resname,
            "target_resname": self.target_resname,
            "minimum_distance": self.minimum_distance,
            "distance_unit": self.distance_unit,
            "atom_filter": self.atom_filter,
            "source_residue_id": self.source_residue_id,
            "target_residue_id": self.target_residue_id,
            "source_segid": self.source_segid,
            "target_segid": self.target_segid,
        }


@dataclass(frozen=True)
class PreprocessingContactFrameResult:
    """Contacts detected for one condition frame."""

    condition_name: str
    frame_index: int
    time_ps: float | None = None
    contacts: tuple[PreprocessingContactPairResult, ...] = ()
    issues: tuple[PreprocessingContactComputationIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "condition_name",
            _normalize_non_empty_string(
                self.condition_name,
                "condition_name",
            ),
        )
        _require_non_negative_int(self.frame_index, "frame_index")
        _require_optional_non_negative_finite_number(
            self.time_ps,
            "time_ps",
        )
        for contact in self.contacts:
            if not isinstance(contact, PreprocessingContactPairResult):
                raise ValueError(
                    "contacts must contain PreprocessingContactPairResult"
                )
        for issue in self.issues:
            if not isinstance(issue, PreprocessingContactComputationIssue):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingContactComputationIssue"
                )

    @property
    def contact_count(self) -> int:
        """Return the number of contact pairs in this frame."""
        return len(self.contacts)

    @property
    def passed(self) -> bool:
        """Return whether this frame has no contacts issues."""
        return self.issues == ()

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable frame result."""
        return {
            "condition_name": self.condition_name,
            "frame_index": self.frame_index,
            "time_ps": self.time_ps,
            "contact_count": self.contact_count,
            "contacts": [contact.to_dict() for contact in self.contacts],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
        }


@dataclass(frozen=True)
class PreprocessingConditionContactsResult:
    """Aggregate contacts results for one condition."""

    condition_name: str
    options: PreprocessingContactDetectionOptions
    frame_results: tuple[PreprocessingContactFrameResult, ...] = ()
    issues: tuple[PreprocessingContactComputationIssue, ...] = ()
    status: str = "not_computed"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "condition_name",
            _normalize_non_empty_string(
                self.condition_name,
                "condition_name",
            ),
        )
        if not isinstance(self.options, PreprocessingContactDetectionOptions):
            raise ValueError(
                "options must be PreprocessingContactDetectionOptions"
            )
        frame_indexes: set[int] = set()
        for frame_result in self.frame_results:
            if not isinstance(frame_result, PreprocessingContactFrameResult):
                raise ValueError(
                    "frame_results must contain "
                    "PreprocessingContactFrameResult"
                )
            if frame_result.condition_name != self.condition_name:
                raise ValueError(
                    "frame result condition_name must match condition result"
                )
            if frame_result.frame_index in frame_indexes:
                raise ValueError(
                    "frame result indexes must be unique within a condition"
                )
            frame_indexes.add(frame_result.frame_index)
        for issue in self.issues:
            if not isinstance(issue, PreprocessingContactComputationIssue):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingContactComputationIssue"
                )
        if self.status not in _CONTACT_RESULT_STATUSES:
            raise ValueError(
                "status must be not_computed, computed, partial, or failed"
            )

    @property
    def frame_count(self) -> int:
        """Return the number of frame results."""
        return len(self.frame_results)

    @property
    def contact_count(self) -> int:
        """Return the total number of contact pairs across frames."""
        return sum(frame.contact_count for frame in self.frame_results)

    @property
    def passed_frame_count(self) -> int:
        """Return the number of frame results without issues."""
        return sum(frame.passed for frame in self.frame_results)

    @property
    def failed_frame_count(self) -> int:
        """Return the number of frame results with issues."""
        return self.frame_count - self.passed_frame_count

    @property
    def passed(self) -> bool:
        """Return whether the condition was fully computed without issues."""
        return (
            self.status == "computed"
            and self.issues == ()
            and all(frame.passed for frame in self.frame_results)
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable condition result."""
        return {
            "condition_name": self.condition_name,
            "status": self.status,
            "options": self.options.to_dict(),
            "frame_count": self.frame_count,
            "contact_count": self.contact_count,
            "passed_frame_count": self.passed_frame_count,
            "failed_frame_count": self.failed_frame_count,
            "frame_results": [
                frame_result.to_dict()
                for frame_result in self.frame_results
            ],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
        }


@dataclass(frozen=True)
class PreprocessingManifestContactsResult:
    """Aggregate contacts results for manifest conditions."""

    condition_results: tuple[PreprocessingConditionContactsResult, ...] = ()
    issues: tuple[PreprocessingContactComputationIssue, ...] = ()

    def __post_init__(self) -> None:
        condition_names: set[str] = set()
        for condition_result in self.condition_results:
            if not isinstance(
                condition_result,
                PreprocessingConditionContactsResult,
            ):
                raise ValueError(
                    "condition_results must contain "
                    "PreprocessingConditionContactsResult"
                )
            if condition_result.condition_name in condition_names:
                raise ValueError("condition result names must be unique")
            condition_names.add(condition_result.condition_name)
        for issue in self.issues:
            if not isinstance(issue, PreprocessingContactComputationIssue):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingContactComputationIssue"
                )

    @property
    def condition_count(self) -> int:
        """Return the number of condition results."""
        return len(self.condition_results)

    @property
    def computed_condition_count(self) -> int:
        """Return the number of conditions with computed status."""
        return sum(
            result.status == "computed"
            for result in self.condition_results
        )

    @property
    def failed_condition_count(self) -> int:
        """Return the number of condition results that do not pass."""
        return sum(not result.passed for result in self.condition_results)

    @property
    def frame_count(self) -> int:
        """Return the total number of frame results."""
        return sum(result.frame_count for result in self.condition_results)

    @property
    def contact_count(self) -> int:
        """Return the total number of contact pairs."""
        return sum(result.contact_count for result in self.condition_results)

    @property
    def passed_frame_count(self) -> int:
        """Return the total number of passing frame results."""
        return sum(
            result.passed_frame_count for result in self.condition_results
        )

    @property
    def failed_frame_count(self) -> int:
        """Return the total number of failing frame results."""
        return sum(
            result.failed_frame_count for result in self.condition_results
        )

    @property
    def passed(self) -> bool:
        """Return whether every available condition passes."""
        return (
            self.issues == ()
            and bool(self.condition_results)
            and all(result.passed for result in self.condition_results)
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable manifest result."""
        return {
            "condition_count": self.condition_count,
            "computed_condition_count": self.computed_condition_count,
            "failed_condition_count": self.failed_condition_count,
            "frame_count": self.frame_count,
            "contact_count": self.contact_count,
            "passed_frame_count": self.passed_frame_count,
            "failed_frame_count": self.failed_frame_count,
            "condition_results": [
                condition_result.to_dict()
                for condition_result in self.condition_results
            ],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
        }


__all__ = [
    "PreprocessingConditionContactsResult",
    "PreprocessingContactComputationIssue",
    "PreprocessingContactDefinition",
    "PreprocessingContactDetectionOptions",
    "PreprocessingContactFrameResult",
    "PreprocessingContactPairResult",
    "PreprocessingManifestContactsResult",
]
