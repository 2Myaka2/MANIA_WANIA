"""Validate and aggregate caller-supplied box observations, without correction."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from itertools import islice
from math import isfinite
from numbers import Real
from pathlib import PurePosixPath
from typing import Literal, cast

PBC_AUDIT_SCHEMA_VERSION = "mania.pbc_audit.v0.1"
PBC_AUDIT_KIND = "mania_pbc_audit"
PBC_AUDIT_FILENAME = "pbc_audit.json"
PBC_DISTANCE_SEMANTICS = (
    "euclidean_selected_atom_coordinates_without_mania_minimum_image_correction"
)
PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED = False
PBC_SCIENTIFIC_STATUS = "unresolved"

PbcMetadataStatus = Literal["complete", "partial", "unavailable", "invalid"]
ExternalPbcPreprocessingStatus = Literal[
    "undeclared",
    "declared_applied",
    "declared_not_applied",
]
_Triple = tuple[float, float, float]


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty stripped string")


def _require_count(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_number(value: object, name: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        valid = isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        bound = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be finite and {bound}")


def _require_triple(value: object, name: str) -> None:
    if not isinstance(value, tuple) or len(value) != 3:
        raise ValueError(f"{name} must be a tuple of three positive numbers")
    for item in value:
        _require_number(item, name, positive=True)


def _triple_payload(value: _Triple | None) -> list[float] | None:
    return None if value is None else list(value)


def _metadata_status(sampled: int, present: int, valid: int) -> PbcMetadataStatus:
    if sampled == 0 or present == 0:
        return "unavailable"
    if valid == 0:
        return "invalid"
    return "complete" if valid == sampled else "partial"


@dataclass(frozen=True)
class PbcFrameObservation:
    """Unit-cell metadata for an already selected frame, without scientific judgment."""

    condition: str
    frame_index: int
    time_ps: float | None
    dimensions_present: bool
    dimensions_valid: bool
    box_lengths_A: _Triple | None
    box_angles_deg: _Triple | None

    def __post_init__(self) -> None:
        _require_text(self.condition, "condition")
        _require_count(self.frame_index, "frame_index")
        if self.time_ps is not None:
            _require_number(self.time_ps, "time_ps")
        for name in ("dimensions_present", "dimensions_valid"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be bool")
        if self.dimensions_valid:
            if not self.dimensions_present:
                raise ValueError("valid dimensions must be present")
            _require_triple(self.box_lengths_A, "box_lengths_A")
            _require_triple(self.box_angles_deg, "box_angles_deg")
        elif self.box_lengths_A is not None or self.box_angles_deg is not None:
            raise ValueError(
                "missing/invalid dimensions require lengths and angles None"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition,
            "frame_index": self.frame_index,
            "time_ps": self.time_ps,
            "dimensions_present": self.dimensions_present,
            "dimensions_valid": self.dimensions_valid,
            "box_lengths_A": _triple_payload(self.box_lengths_A),
            "box_angles_deg": _triple_payload(self.box_angles_deg),
        }


def _observed_dimensions(dimensions: object) -> tuple[_Triple, _Triple] | None:
    # Strings, byte buffers, and mapping keys are not scalar dimension sequences.
    if isinstance(dimensions, (str, bytes, bytearray, Mapping)):
        return None
    try:
        # Bound consumption even for a malformed, unbounded caller iterable.
        values = tuple(islice(cast(Iterable[object], dimensions), 7))
        if len(values) != 6 or any(
            isinstance(value, bool) or not isinstance(value, Real) for value in values
        ):
            return None
        numbers = tuple(float(cast(Real, value)) for value in values)
        if not all(isfinite(value) and value > 0 for value in numbers):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return (numbers[0], numbers[1], numbers[2]), (numbers[3], numbers[4], numbers[5])


def observe_pbc_frame_dimensions(
    *,
    condition: str,
    frame_index: int,
    time_ps: float | None,
    dimensions: object,
) -> PbcFrameObservation:
    """Observe supplied scalar dimensions; never fetch or advance a frame."""
    box = None if dimensions is None else _observed_dimensions(dimensions)
    return PbcFrameObservation(
        condition=condition,
        frame_index=frame_index,
        time_ps=time_ps,
        dimensions_present=dimensions is not None,
        dimensions_valid=box is not None,
        box_lengths_A=None if box is None else box[0],
        box_angles_deg=None if box is None else box[1],
    )


PbcObservationCallback = Callable[[PbcFrameObservation], None]


def observe_pbc_timestep_dimensions(
    *,
    condition: str,
    frame_index: int,
    time_ps: float | None,
    timestep: object,
) -> PbcFrameObservation:
    """Read only dimensions from an already yielded timestep, without correction."""
    try:
        dimensions = getattr(timestep, "dimensions", None)
    except Exception:
        dimensions = None
    return observe_pbc_frame_dimensions(
        condition=condition,
        frame_index=frame_index,
        time_ps=time_ps,
        dimensions=dimensions,
    )


@dataclass(frozen=True)
class PbcConditionAudit:
    """Counts and component ranges over supplied observations, with no frame list."""

    condition: str
    metadata_status: PbcMetadataStatus
    sampled_frame_count: int
    dimensions_present_frame_count: int
    dimensions_valid_frame_count: int
    dimensions_missing_frame_count: int
    dimensions_invalid_frame_count: int
    box_lengths_min_A: _Triple | None
    box_lengths_max_A: _Triple | None
    box_angles_min_deg: _Triple | None
    box_angles_max_deg: _Triple | None
    box_varies: bool | None

    def __post_init__(self) -> None:
        _require_text(self.condition, "condition")
        for name in (
            "sampled_frame_count",
            "dimensions_present_frame_count",
            "dimensions_valid_frame_count",
            "dimensions_missing_frame_count",
            "dimensions_invalid_frame_count",
        ):
            _require_count(getattr(self, name), name)
        if self.dimensions_present_frame_count != (
            self.dimensions_valid_frame_count + self.dimensions_invalid_frame_count
        ):
            raise ValueError("dimensions present count must equal valid + invalid")
        if self.sampled_frame_count != (
            self.dimensions_present_frame_count + self.dimensions_missing_frame_count
        ):
            raise ValueError("sampled count must equal dimensions present + missing")
        expected = _metadata_status(
            self.sampled_frame_count,
            self.dimensions_present_frame_count,
            self.dimensions_valid_frame_count,
        )
        if self.metadata_status != expected:
            raise ValueError("metadata_status must agree with dimension counts")
        if self.box_varies is not None and type(self.box_varies) is not bool:
            raise ValueError("box_varies must be bool or None")
        pairs = (
            (self.box_lengths_min_A, self.box_lengths_max_A),
            (self.box_angles_min_deg, self.box_angles_max_deg),
        )
        varies = False
        for lower, upper in pairs:
            if self.dimensions_valid_frame_count == 0:
                if lower is not None or upper is not None:
                    raise ValueError("zero valid dimensions require ranges None")
                continue
            _require_triple(lower, "box minimum")
            _require_triple(upper, "box maximum")
            assert lower is not None and upper is not None
            if any(low > high for low, high in zip(lower, upper, strict=True)):
                raise ValueError("box minimum must not exceed maximum")
            varies = varies or lower != upper
        if self.dimensions_valid_frame_count < 2:
            if self.box_varies is not None or varies:
                raise ValueError("fewer than two valid dimensions require no variation")
        elif self.box_varies is not varies:
            raise ValueError("box_varies must agree with observed ranges")

    def to_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition,
            "metadata_status": self.metadata_status,
            "sampled_frame_count": self.sampled_frame_count,
            "dimensions_present_frame_count": self.dimensions_present_frame_count,
            "dimensions_valid_frame_count": self.dimensions_valid_frame_count,
            "dimensions_missing_frame_count": self.dimensions_missing_frame_count,
            "dimensions_invalid_frame_count": self.dimensions_invalid_frame_count,
            "box_lengths_min_A": _triple_payload(self.box_lengths_min_A),
            "box_lengths_max_A": _triple_payload(self.box_lengths_max_A),
            "box_angles_min_deg": _triple_payload(self.box_angles_min_deg),
            "box_angles_max_deg": _triple_payload(self.box_angles_max_deg),
            "box_varies": self.box_varies,
        }


def _require_observations(observations: object) -> None:
    if not isinstance(observations, tuple) or any(
        type(item) is not PbcFrameObservation for item in observations
    ):
        raise ValueError("observations must be a tuple of PbcFrameObservation values")


def _component_bounds(values: list[_Triple]) -> tuple[_Triple | None, _Triple | None]:
    if not values:
        return None, None
    x, y, z = zip(*values, strict=True)
    return (min(x), min(y), min(z)), (max(x), max(y), max(z))


def summarize_pbc_condition_observations(
    condition: str,
    observations: tuple[PbcFrameObservation, ...],
) -> PbcConditionAudit:
    """Aggregate supplied frames only; duplicate indexes are not sampled twice."""
    _require_text(condition, "condition")
    _require_observations(observations)
    indexes: set[int] = set()
    lengths: list[_Triple] = []
    angles: list[_Triple] = []
    present = 0
    for observation in observations:
        if observation.condition != condition:
            raise ValueError("observation condition must match condition exactly")
        if observation.frame_index in indexes:
            raise ValueError("frame indexes must be unique within a condition")
        indexes.add(observation.frame_index)
        present += observation.dimensions_present
        if observation.dimensions_valid:
            assert observation.box_lengths_A is not None
            assert observation.box_angles_deg is not None
            lengths.append(observation.box_lengths_A)
            angles.append(observation.box_angles_deg)
    sampled, valid = len(observations), len(lengths)
    lengths_min, lengths_max = _component_bounds(lengths)
    angles_min, angles_max = _component_bounds(angles)
    return PbcConditionAudit(
        condition=condition,
        metadata_status=_metadata_status(sampled, present, valid),
        sampled_frame_count=sampled,
        dimensions_present_frame_count=present,
        dimensions_valid_frame_count=valid,
        dimensions_missing_frame_count=sampled - present,
        dimensions_invalid_frame_count=present - valid,
        box_lengths_min_A=lengths_min,
        box_lengths_max_A=lengths_max,
        box_angles_min_deg=angles_min,
        box_angles_max_deg=angles_max,
        box_varies=(
            None
            if valid < 2
            else lengths_min != lengths_max or angles_min != angles_max
        ),
    )


@dataclass(frozen=True)
class PbcAudit:
    """Observation audit with fixed current distance facts and unresolved science."""

    run_id: str
    workflow: str
    audit_path: str
    external_pbc_preprocessing_status: ExternalPbcPreprocessingStatus
    conditions: tuple[PbcConditionAudit, ...]
    schema_version: str = field(default=PBC_AUDIT_SCHEMA_VERSION, init=False)
    kind: str = field(default=PBC_AUDIT_KIND, init=False)
    distance_semantics: str = field(default=PBC_DISTANCE_SEMANTICS, init=False)
    mania_internal_minimum_image_correction_applied: bool = field(
        default=PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED,
        init=False,
    )
    scientific_pbc_status: str = field(default=PBC_SCIENTIFIC_STATUS, init=False)

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        _require_text(self.workflow, "workflow")
        _require_text(self.audit_path, "audit_path")
        path = PurePosixPath(self.audit_path)
        if (
            path.is_absolute()
            or "\\" in self.audit_path
            or ":" in self.audit_path
            or any(ord(char) < 32 or ord(char) == 127 for char in self.audit_path)
            or any(part in (".", "..") for part in self.audit_path.split("/"))
            or path.as_posix() != self.audit_path
            or path.name != PBC_AUDIT_FILENAME
        ):
            raise ValueError(
                "audit_path must be a normalized portable relative POSIX path "
                f"ending in {PBC_AUDIT_FILENAME}"
            )
        if self.external_pbc_preprocessing_status not in (
            "undeclared",
            "declared_applied",
            "declared_not_applied",
        ):
            raise ValueError("invalid external_pbc_preprocessing_status")
        if not isinstance(self.conditions, tuple) or any(
            type(item) is not PbcConditionAudit for item in self.conditions
        ):
            raise ValueError("conditions must be a tuple of PbcConditionAudit values")
        if len({item.condition for item in self.conditions}) != len(self.conditions):
            raise ValueError("condition names must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "run_id": self.run_id,
            "workflow": self.workflow,
            "audit_path": self.audit_path,
            "distance_semantics": self.distance_semantics,
            "mania_internal_minimum_image_correction_applied": (
                self.mania_internal_minimum_image_correction_applied
            ),
            "external_pbc_preprocessing_status": self.external_pbc_preprocessing_status,
            "scientific_pbc_status": self.scientific_pbc_status,
            "conditions": [condition.to_dict() for condition in self.conditions],
        }


def build_pbc_audit(
    *,
    run_id: str,
    workflow: str,
    condition_names: tuple[str, ...],
    observations: tuple[PbcFrameObservation, ...],
    audit_path: str = PBC_AUDIT_FILENAME,
    external_pbc_preprocessing_status: ExternalPbcPreprocessingStatus = "undeclared",
) -> PbcAudit:
    """Group in declared order, including conditions without observations."""
    if not isinstance(condition_names, tuple) or not condition_names:
        raise ValueError("condition_names must be a non-empty tuple")
    grouped: dict[str, list[PbcFrameObservation]] = {}
    for name in condition_names:
        _require_text(name, "condition name")
        if name in grouped:
            raise ValueError("condition names must be unique")
        grouped[name] = []
    _require_observations(observations)
    for observation in observations:
        if observation.condition not in grouped:
            raise ValueError("observation condition must belong to condition_names")
        grouped[observation.condition].append(observation)
    return PbcAudit(
        run_id=run_id,
        workflow=workflow,
        audit_path=audit_path,
        external_pbc_preprocessing_status=external_pbc_preprocessing_status,
        conditions=tuple(
            summarize_pbc_condition_observations(name, tuple(items))
            for name, items in grouped.items()
        ),
    )


__all__ = [
    "PBC_AUDIT_FILENAME",
    "PBC_AUDIT_KIND",
    "PBC_AUDIT_SCHEMA_VERSION",
    "PBC_DISTANCE_SEMANTICS",
    "PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED",
    "PBC_SCIENTIFIC_STATUS",
    "ExternalPbcPreprocessingStatus",
    "PbcAudit",
    "PbcConditionAudit",
    "PbcFrameObservation",
    "PbcMetadataStatus",
    "PbcObservationCallback",
    "build_pbc_audit",
    "observe_pbc_frame_dimensions",
    "observe_pbc_timestep_dimensions",
    "summarize_pbc_condition_observations",
]
