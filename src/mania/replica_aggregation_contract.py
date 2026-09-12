"""Pure Stage 31.A grouping after explicit Stage 30 canonicalization.

Only canonical per-replica tables may feed future Stage 31.B/31.C statistics;
source-indexed tables are audit evidence, never cross-replica join identities.
An absent sparse entity row in an available replica will contribute occupancy
zero. Unavailable/excluded replicas never contribute zero or enter statistics.
This module carries availability evidence only: no tables, statistics or QC.
"""

from dataclasses import asdict, dataclass, field
from decimal import Context, Decimal, localcontext
from math import isclose, isfinite
from typing import Literal

from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)
from mania.dataset_identity import DatasetEngine
from mania.preprocessing.physical_time_windows import (
    WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE,
    WINDOW_OVERLAP_PERCENT_REL_TOLERANCE,
)

REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID = CANONICAL_RESIDUE_MAPPING_REFERENCE_ID
REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256 = (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256
)

ReplicaWindowAvailabilityStatus = Literal["available", "unavailable", "excluded"]

_PhysicalWindowKey = tuple[
    Decimal, Decimal, Decimal, Decimal, bool, Decimal, Decimal, Decimal
]
_GroupKey = tuple[str, str, DatasetEngine, _PhysicalWindowKey]
_PHYSICAL_NUMBER_FIELDS = (
    "requested_production_start_ns",
    "requested_production_end_ns",
    "requested_window_start_ns",
    "requested_window_end_ns",
    "window_length_ns",
    "window_step_ns",
    "overlap_percent",
)


class ReplicaAggregationContractError(ValueError):
    """Invalid group, membership, canonical reference or requested window."""


def _text(value: object, name: str) -> str:
    # Match Dataset identifiers: actual strings, strip only, retain case and
    # internal text, and impose no naming convention or inferred identity.
    if not isinstance(value, str) or not value.strip():
        raise ReplicaAggregationContractError(f"{name} must be a non-empty string")
    return value.strip()


def _engine(value: object) -> None:
    if type(value) is not str or value not in ("gromacs", "namd"):
        raise ReplicaAggregationContractError("engine must be exactly gromacs or namd")


def _reference(reference_id: object, sequence_sha256: object) -> None:
    if (
        type(reference_id) is not str
        or reference_id != REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
        or type(sequence_sha256) is not str
        or sequence_sha256 != REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
    ):
        raise ReplicaAggregationContractError(
            "canonical reference must match the pinned Stage 30 reference"
        )


def _window(value: object) -> None:
    if type(value) is not ReplicaAggregationWindowDefinition:
        raise ReplicaAggregationContractError(
            "window must be an exact ReplicaAggregationWindowDefinition"
        )


def _decimal(value: object, name: str) -> Decimal:
    valid = False
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        try:
            valid = isfinite(value) and value >= 0
        except OverflowError:
            pass
    if not valid:
        raise ReplicaAggregationContractError(
            f"{name} must be a finite non-negative number"
        )
    return Decimal(str(value))


def _decimal_context(values: tuple[Decimal, ...]) -> Context:
    # Accepted Stage 27 approach: span all supplied digits/exponents and isolate
    # arithmetic from caller precision, rounding and traps.
    precision = (
        max(value.adjusted() for value in values)
        - min(int(value.as_tuple().exponent) for value in values)
        + 8
    )
    return Context(prec=max(1, precision))


@dataclass(frozen=True)
class ReplicaAggregationWindowDefinition:
    """Requested physical identity only; effective coverage is separate evidence."""

    window_id: str
    window_index: int
    requested_production_start_ns: float
    requested_production_end_ns: float
    requested_window_start_ns: float
    requested_window_end_ns: float
    right_endpoint_inclusive: bool
    window_length_ns: float
    window_step_ns: float
    overlap_percent: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _text(self.window_id, "window_id"))
        if type(self.window_index) is not int or self.window_index < 0:
            raise ReplicaAggregationContractError(
                "window_index must be a non-negative integer"
            )
        if type(self.right_endpoint_inclusive) is not bool:
            raise ReplicaAggregationContractError(
                "right_endpoint_inclusive must be an exact bool"
            )
        values = tuple(
            _decimal(getattr(self, name), name) for name in _PHYSICAL_NUMBER_FIELDS
        )
        production_start, production_end, start, end, length, step, overlap = values
        if production_end <= production_start:
            raise ReplicaAggregationContractError(
                "production interval must be positive"
            )
        if end <= start:
            raise ReplicaAggregationContractError("requested window must be positive")
        if start < production_start or end > production_end:
            raise ReplicaAggregationContractError(
                "requested window must lie within requested production"
            )
        if not 0 < step <= length:
            raise ReplicaAggregationContractError(
                "window must satisfy 0 < step <= length"
            )
        if not 0 <= overlap < 100:
            raise ReplicaAggregationContractError("overlap_percent must be in [0, 100)")
        with localcontext(_decimal_context(values)):
            if end - start != length:
                raise ReplicaAggregationContractError(
                    "requested window duration must equal window_length_ns exactly"
                )
        # Stage 27's representation tolerance validates the supplied schedule;
        # it never rounds or merges distinct physical compatibility keys.
        implied = (1 - self.window_step_ns / self.window_length_ns) * 100
        if not isclose(
            self.overlap_percent,
            implied,
            rel_tol=WINDOW_OVERLAP_PERCENT_REL_TOLERANCE,
            abs_tol=WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE,
        ):
            raise ReplicaAggregationContractError(
                "overlap_percent must agree with (1 - step / length) * 100"
            )

    @property
    def physical_window_key(self) -> _PhysicalWindowKey:
        values = tuple(
            Decimal(str(getattr(self, name))) for name in _PHYSICAL_NUMBER_FIELDS
        )
        with localcontext(_decimal_context(values)):
            p_start, p_end, start, end, length, step, overlap = (
                value.normalize() if value else Decimal(0) for value in values
            )
        return (
            p_start,
            p_end,
            start,
            end,
            self.right_endpoint_inclusive,
            length,
            step,
            overlap,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReplicaAggregationGroupSpec:
    """Explicit expected membership; condition is consistency metadata only."""

    dataset_id: str
    system_id: str
    engine: DatasetEngine
    variant_id: str
    condition: str | None
    disulfide_state: str | None
    expected_replica_ids: tuple[str, ...]
    window: ReplicaAggregationWindowDefinition
    canonical_reference_id: str = field(
        default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID, init=False
    )
    canonical_reference_sequence_sha256: str = field(
        default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256, init=False
    )

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "variant_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("condition", "disulfide_state"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))
        _engine(self.engine)
        _window(self.window)
        if (
            type(self.expected_replica_ids) is not tuple
            or not self.expected_replica_ids
        ):
            raise ReplicaAggregationContractError(
                "expected_replica_ids must be a non-empty tuple"
            )
        ids = tuple(
            _text(value, "expected replica ID") for value in self.expected_replica_ids
        )
        if len(set(ids)) != len(ids):
            raise ReplicaAggregationContractError("expected replica IDs must be unique")
        object.__setattr__(self, "expected_replica_ids", ids)

    @property
    def group_key(self) -> _GroupKey:
        return (
            self.dataset_id,
            self.system_id,
            self.engine,
            self.window.physical_window_key,
        )

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["expected_replica_ids"] = list(self.expected_replica_ids)
        return result


@dataclass(frozen=True)
class ReplicaAggregationMember:
    """One known replica/window state, independently of sparse entity rows."""

    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    variant_id: str
    engine: DatasetEngine
    condition: str | None
    disulfide_state: str | None
    canonical_reference_id: str
    canonical_reference_sequence_sha256: str
    window: ReplicaAggregationWindowDefinition
    availability_status: ReplicaWindowAvailabilityStatus
    availability_reason: str | None

    def __post_init__(self) -> None:
        for name in (
            "dataset_id",
            "system_id",
            "trajectory_id",
            "replica_id",
            "variant_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("condition", "disulfide_state"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))
        _engine(self.engine)
        _reference(
            self.canonical_reference_id, self.canonical_reference_sequence_sha256
        )
        _window(self.window)
        if type(
            self.availability_status
        ) is not str or self.availability_status not in (
            "available",
            "unavailable",
            "excluded",
        ):
            raise ReplicaAggregationContractError("invalid availability_status")
        if self.availability_status == "available":
            if self.availability_reason is not None:
                raise ReplicaAggregationContractError(
                    "available members require availability_reason=None"
                )
        else:
            reason = _text(self.availability_reason, "availability_reason")
            # Portable prose only. Reject path separators and control characters
            # rather than retaining/redacting machine-specific path fragments.
            if any(char in reason for char in ("/", "\\", "~")) or any(
                not char.isprintable() for char in reason
            ):
                raise ReplicaAggregationContractError(
                    "availability_reason must be portable text "
                    "without paths or controls"
                )
            object.__setattr__(self, "availability_reason", reason)

    @property
    def replica_key(self) -> tuple[str, str, str, str]:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CompatibleReplicaAggregationGroup:
    """Validated group in expected order, with explicit availability partitions."""

    spec: ReplicaAggregationGroupSpec
    members: tuple[ReplicaAggregationMember, ...]

    def __post_init__(self) -> None:
        if type(self.spec) is not ReplicaAggregationGroupSpec:
            raise ReplicaAggregationContractError(
                "spec must be an exact ReplicaAggregationGroupSpec"
            )
        if (
            type(self.members) is not tuple
            or not self.members
            or any(
                type(member) is not ReplicaAggregationMember for member in self.members
            )
        ):
            raise ReplicaAggregationContractError(
                "members must be a non-empty tuple of exact ReplicaAggregationMember"
            )
        keys = tuple(member.replica_key for member in self.members)
        if len(set(keys)) != len(keys):
            raise ReplicaAggregationContractError("replica keys must be unique")
        ids = tuple(member.replica_id for member in self.members)
        if len(set(ids)) != len(ids):
            raise ReplicaAggregationContractError("replica IDs must be unique")
        if set(ids) != set(self.spec.expected_replica_ids):
            raise ReplicaAggregationContractError(
                "member replica IDs must match expected_replica_ids exactly"
            )
        for member in self.members:
            for name in (
                "dataset_id",
                "system_id",
                "engine",
                "variant_id",
                "condition",
                "disulfide_state",
                "canonical_reference_id",
                "canonical_reference_sequence_sha256",
            ):
                if getattr(member, name) != getattr(self.spec, name):
                    raise ReplicaAggregationContractError(
                        f"member {name} must match spec"
                    )
            if (
                member.window.physical_window_key
                != self.spec.window.physical_window_key
            ):
                raise ReplicaAggregationContractError(
                    "member physical_window_key must match spec"
                )
            if (
                member.window.window_id != self.spec.window.window_id
                or member.window.window_index != self.spec.window.window_index
            ):
                raise ReplicaAggregationContractError(
                    "member window_id and window_index must match spec"
                )
        by_id = {member.replica_id: member for member in self.members}
        object.__setattr__(
            self,
            "members",
            tuple(by_id[replica_id] for replica_id in self.spec.expected_replica_ids),
        )

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def available_members(self) -> tuple[ReplicaAggregationMember, ...]:
        return tuple(m for m in self.members if m.availability_status == "available")

    @property
    def unavailable_members(self) -> tuple[ReplicaAggregationMember, ...]:
        return tuple(m for m in self.members if m.availability_status == "unavailable")

    @property
    def excluded_members(self) -> tuple[ReplicaAggregationMember, ...]:
        return tuple(m for m in self.members if m.availability_status == "excluded")

    @property
    def available_replica_count(self) -> int:
        return len(self.available_members)

    @property
    def unavailable_replica_count(self) -> int:
        return len(self.unavailable_members)

    @property
    def excluded_replica_count(self) -> int:
        return len(self.excluded_members)

    def to_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec.to_dict(),
            "members": [member.to_dict() for member in self.members],
        }


def build_compatible_replica_aggregation_group(
    spec: ReplicaAggregationGroupSpec,
    members: tuple[ReplicaAggregationMember, ...],
) -> CompatibleReplicaAggregationGroup:
    """Validate all evidence before ordering by the caller's expected tuple."""
    return CompatibleReplicaAggregationGroup(spec, members)


__all__ = [
    "REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID",
    "REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256",
    "ReplicaWindowAvailabilityStatus",
    "ReplicaAggregationWindowDefinition",
    "ReplicaAggregationGroupSpec",
    "ReplicaAggregationMember",
    "CompatibleReplicaAggregationGroup",
    "ReplicaAggregationContractError",
    "build_compatible_replica_aggregation_group",
]
