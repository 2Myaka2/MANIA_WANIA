"""Dependency-free result contracts for preprocessing Rg computation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PreprocessingRgComputationIssue:
    """One deterministic Rg computation issue."""

    kind: Literal[
        "condition_not_loaded",
        "runtime_missing",
        "atom_group_missing",
        "frame_iteration_error",
        "rg_computation_error",
        "invalid_frame_index",
        "invalid_time_ps",
        "invalid_rg_value",
        "manifest_load_issue",
        "condition_rg_error",
    ]
    condition_name: str | None
    frame_index: int | None
    field: str
    message: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable issue dictionary."""
        return {
            "kind": self.kind,
            "condition_name": self.condition_name,
            "frame_index": self.frame_index,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True)
class PreprocessingRgFrameResult:
    """Rg result for one condition frame."""

    condition_name: str
    frame_index: int
    time_ps: float | None
    rg_value: float | None
    rg_unit: str | None
    issues: tuple[PreprocessingRgComputationIssue, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.frame_index, bool)
            or not isinstance(self.frame_index, int)
            or self.frame_index < 0
        ):
            raise ValueError("frame_index must be a non-negative int")
        _validate_optional_non_negative_finite(self.time_ps, "time_ps")
        _validate_optional_non_negative_finite(self.rg_value, "rg_value")

    @property
    def passed(self) -> bool:
        """Return whether this frame has a valid result without issues."""
        return self.rg_value is not None and self.issues == ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable frame result."""
        return {
            "condition_name": self.condition_name,
            "frame_index": self.frame_index,
            "time_ps": self.time_ps,
            "rg_value": self.rg_value,
            "rg_unit": self.rg_unit,
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class PreprocessingConditionRgResult:
    """Aggregate Rg results for one condition."""

    condition_name: str
    status: str
    runtime_type: str | None
    topology_path: Path | None
    trajectory_paths: tuple[Path, ...]
    frame_time_ps: float | None
    rg_unit: str | None
    frame_results: tuple[PreprocessingRgFrameResult, ...] = ()
    issues: tuple[PreprocessingRgComputationIssue, ...] = ()

    def __post_init__(self) -> None:
        _validate_optional_non_negative_finite(
            self.frame_time_ps,
            "frame_time_ps",
        )
        for frame_result in self.frame_results:
            if frame_result.condition_name != self.condition_name:
                raise ValueError(
                    "frame result condition_name must match condition result"
                )
            if (
                self.rg_unit is not None
                and frame_result.rg_unit is not None
                and frame_result.rg_unit != self.rg_unit
            ):
                raise ValueError(
                    "frame result rg_unit must match condition result"
                )

    @property
    def passed(self) -> bool:
        """Return whether every available frame passed without issues."""
        return (
            self.issues == ()
            and bool(self.frame_results)
            and all(frame_result.passed for frame_result in self.frame_results)
        )

    @property
    def frame_count(self) -> int:
        """Return the total number of frame results."""
        return len(self.frame_results)

    @property
    def valid_frame_count(self) -> int:
        """Return the number of passing frame results."""
        return sum(frame_result.passed for frame_result in self.frame_results)

    @property
    def failed_frame_count(self) -> int:
        """Return the number of failing frame results."""
        return self.frame_count - self.valid_frame_count

    @property
    def rg_values(self) -> tuple[float, ...]:
        """Return Rg values from passing frames in frame order."""
        return tuple(
            frame_result.rg_value
            for frame_result in self.frame_results
            if frame_result.passed and frame_result.rg_value is not None
        )

    @property
    def time_values_ps(self) -> tuple[float, ...]:
        """Return available frame times in frame order."""
        return tuple(
            frame_result.time_ps
            for frame_result in self.frame_results
            if frame_result.time_ps is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable condition result."""
        path_items = vars(self)["trajectory_paths"]
        return {
            "condition_name": self.condition_name,
            "status": self.status,
            "runtime_type": self.runtime_type,
            "topology_path": (
                str(self.topology_path)
                if self.topology_path is not None
                else None
            ),
            "trajectory_paths": [str(path) for path in path_items],
            "frame_time_ps": self.frame_time_ps,
            "rg_unit": self.rg_unit,
            "frame_results": [
                frame_result.to_dict()
                for frame_result in self.frame_results
            ],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
            "frame_count": self.frame_count,
            "valid_frame_count": self.valid_frame_count,
            "failed_frame_count": self.failed_frame_count,
            "rg_values": list(self.rg_values),
            "time_values_ps": list(self.time_values_ps),
        }


@dataclass(frozen=True)
class PreprocessingManifestRgResult:
    """Aggregate Rg results for manifest conditions."""

    condition_results: tuple[PreprocessingConditionRgResult, ...] = ()
    issues: tuple[PreprocessingRgComputationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether every available condition passed without issues."""
        return (
            self.issues == ()
            and bool(self.condition_results)
            and all(result.passed for result in self.condition_results)
        )

    @property
    def condition_names(self) -> tuple[str, ...]:
        """Return condition names in result order."""
        return tuple(
            result.condition_name for result in self.condition_results
        )

    @property
    def passed_condition_names(self) -> tuple[str, ...]:
        """Return passing condition names in result order."""
        return tuple(
            result.condition_name
            for result in self.condition_results
            if result.passed
        )

    @property
    def failed_condition_names(self) -> tuple[str, ...]:
        """Return failing condition names in result order."""
        return tuple(
            result.condition_name
            for result in self.condition_results
            if not result.passed
        )

    @property
    def total_conditions(self) -> int:
        """Return the total number of condition results."""
        return len(self.condition_results)

    @property
    def passed_conditions(self) -> int:
        """Return the number of passing condition results."""
        return len(self.passed_condition_names)

    @property
    def failed_conditions(self) -> int:
        """Return the number of failing condition results."""
        return len(self.failed_condition_names)

    @property
    def total_frames(self) -> int:
        """Return the total number of frame results."""
        return sum(result.frame_count for result in self.condition_results)

    @property
    def valid_frames(self) -> int:
        """Return the total number of passing frame results."""
        return sum(
            result.valid_frame_count for result in self.condition_results
        )

    @property
    def failed_frames(self) -> int:
        """Return the total number of failing frame results."""
        return sum(
            result.failed_frame_count for result in self.condition_results
        )

    def result_for_condition(
        self,
        condition_name: str,
    ) -> PreprocessingConditionRgResult | None:
        """Return one exact-name condition result when available."""
        for result in self.condition_results:
            if result.condition_name == condition_name:
                return result
        return None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable manifest result."""
        return {
            "passed": self.passed,
            "condition_results": [
                result.to_dict() for result in self.condition_results
            ],
            "issues": [issue.to_dict() for issue in self.issues],
            "condition_names": list(self.condition_names),
            "passed_condition_names": list(self.passed_condition_names),
            "failed_condition_names": list(self.failed_condition_names),
            "total_conditions": self.total_conditions,
            "passed_conditions": self.passed_conditions,
            "failed_conditions": self.failed_conditions,
            "total_frames": self.total_frames,
            "valid_frames": self.valid_frames,
            "failed_frames": self.failed_frames,
        }


def _validate_optional_non_negative_finite(
    value: float | None,
    field: str,
) -> None:
    if value is None:
        return
    try:
        valid = not isinstance(value, bool) and math.isfinite(value)
    except TypeError as exc:
        raise ValueError(f"{field} must be a finite non-negative number") from exc
    if not valid or value < 0:
        raise ValueError(f"{field} must be a finite non-negative number")


__all__ = [
    "PreprocessingConditionRgResult",
    "PreprocessingManifestRgResult",
    "PreprocessingRgComputationIssue",
    "PreprocessingRgFrameResult",
]
