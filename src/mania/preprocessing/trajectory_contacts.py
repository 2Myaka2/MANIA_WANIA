"""Dependency-free definition and options contracts for contact detection."""

from __future__ import annotations

import math
from dataclasses import dataclass

_ATOM_FILTERS = ("heavy", "all")
_CONTACT_LEVEL = "residue"
_DISTANCE_DEFINITION = "minimum_selected_atom_distance"
_FRAME_SCOPE = "per_frame"
_PAIR_SCOPE = "distinct_residue_pair"
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


__all__ = [
    "PreprocessingContactDefinition",
    "PreprocessingContactDetectionOptions",
]
