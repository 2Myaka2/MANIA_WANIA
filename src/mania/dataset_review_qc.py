"""Pure Stage 32.C review findings from supplied evidence, never release decisions.

RMSD drift is an authoritative bool assessment, not a coordinate calculation.
Only hard-passing replicas enter the unscaled, inclusive-cohort MAD comparison.
Readers, production decisions and workflow integration belong to Stage 32.D.
"""

import re
from dataclasses import dataclass, field, fields, replace
from decimal import Context, Decimal, localcontext
from typing import Literal, TypeAlias, get_args

from mania.dataset_hard_qc import DatasetHardQCError, ReplicaHardQCEvaluation
from mania.dataset_identity import DatasetEngine
from mania.dataset_qc_contract import (
    DatasetQCContractError,
    QCEvidenceRecord,
    QCReasonCode,
    ReplicaQCCheckResult,
)

ReviewQCStatus = Literal["pass", "review"]
ReviewMADMetricFamily = Literal["edge_count", "contact_fraction", "basic_metric"]
ReplicaKey: TypeAlias = tuple[str, str, str, str]
MetricKey: TypeAlias = tuple[ReviewMADMetricFamily, str]
CohortKey: TypeAlias = tuple[str, str, DatasetEngine]
_MAD_REASONS: dict[ReviewMADMetricFamily, QCReasonCode] = {
    "edge_count": "EDGE_COUNT_MAD_OUTLIER_REVIEW",
    "contact_fraction": "CONTACT_FRACTION_MAD_OUTLIER_REVIEW",
    "basic_metric": "BASIC_METRIC_MAD_OUTLIER_REVIEW",
}


class DatasetReviewQCError(ValueError):
    """Malformed or incomplete review input, distinct from scientific REVIEW."""


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise DatasetReviewQCError(f"{name} must be a non-empty string")
    # Lexical portability only; never resolve paths or inspect the environment.
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or re.search(
        r"(?<![\w.])(?:/|[A-Za-z]:[\\/]|~[/\\]|\$\w+|\$\{|%\w+%)",
        value,
    ):
        raise DatasetReviewQCError(f"{name} must be portable text without local paths")
    return value.strip()


def _identity(value: object) -> None:
    for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
        object.__setattr__(value, name, _text(getattr(value, name), name))


def _engine(value: object) -> None:
    if type(value) is not str or value not in get_args(DatasetEngine):
        raise DatasetReviewQCError("engine must be exactly gromacs or namd")


def _records(value: object, cls: type, name: str, *, nonempty: bool = False) -> None:
    if (
        type(value) is not tuple
        or (nonempty and not value)
        or any(type(item) is not cls for item in value)
    ):
        raise DatasetReviewQCError(f"{name} must be a tuple of exact {cls.__name__}")


def _evidence(value: tuple[QCEvidenceRecord, ...]) -> None:
    _records(value, QCEvidenceRecord, "evidence", nonempty=True)
    for record in value:
        try:
            replace(record)
        except DatasetQCContractError as exc:
            raise DatasetReviewQCError(str(exc)) from None
        if record.evidence_type == "manual_review":
            raise DatasetReviewQCError("manual reviewer evidence belongs to Stage 32.D")
        for name, text in record.to_dict().items():
            if text is not None:
                _text(text, name)
    if len({e.evidence_id for e in value}) != len(value):
        raise DatasetReviewQCError("evidence IDs must be unique within their container")


@dataclass(frozen=True)
class RMSDDriftAssessment:
    drift_detected: bool
    assessment_method: str
    evidence: tuple[QCEvidenceRecord, ...]

    def __post_init__(self) -> None:
        if type(self.drift_detected) is not bool:
            raise DatasetReviewQCError("drift_detected must be exact bool")
        object.__setattr__(
            self,
            "assessment_method",
            _text(self.assessment_method, "assessment_method"),
        )
        _evidence(self.evidence)

    def to_dict(self) -> dict[str, object]:
        return {
            "drift_detected": self.drift_detected,
            "assessment_method": self.assessment_method,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class ProteinEdgeEmptyWindowEvidence:
    """Counts of valid requested windows with existing table/schema evidence.

    The caller attests to this scope; missing windows are hard-QC evidence,
    never empty scientific windows. This model does not discover artifacts.
    """

    expected_window_count: int
    empty_window_count: int
    evidence: tuple[QCEvidenceRecord, ...]

    def __post_init__(self) -> None:
        if (
            type(self.expected_window_count) is not int
            or type(self.empty_window_count) is not int
            or self.expected_window_count <= 0
            or not 0 <= self.empty_window_count <= self.expected_window_count
        ):
            raise DatasetReviewQCError(
                "window counts must be exact ints with 0 <= empty <= expected and "
                "expected > 0"
            )
        _evidence(self.evidence)

    def to_dict(self) -> dict[str, object]:
        return {
            "expected_window_count": self.expected_window_count,
            "empty_window_count": self.empty_window_count,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class ReplicaMADMetricObservation:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    engine: DatasetEngine
    metric_family: ReviewMADMetricFamily
    metric_name: str
    value: int | float
    unit: str | None
    evidence: tuple[QCEvidenceRecord, ...]

    def __post_init__(self) -> None:
        _identity(self)
        _engine(self.engine)
        if type(self.metric_family) is not str or self.metric_family not in get_args(
            ReviewMADMetricFamily
        ):
            raise DatasetReviewQCError("unknown MAD metric family")
        object.__setattr__(self, "metric_name", _text(self.metric_name, "metric_name"))
        if type(self.value) not in (int, float):
            raise DatasetReviewQCError("metric value must be a finite int or float")
        value = Decimal(str(self.value))
        if not value.is_finite():
            raise DatasetReviewQCError("metric value must be finite")
        if self.metric_family == "edge_count" and (
            value < 0 or value != value.to_integral_value()
        ):
            raise DatasetReviewQCError("edge_count must be a non-negative integer")
        if self.metric_family == "contact_fraction" and not 0 <= value <= 1:
            raise DatasetReviewQCError("contact_fraction must be in [0, 1]")
        if self.unit is not None:
            object.__setattr__(self, "unit", _text(self.unit, "unit"))
        _evidence(self.evidence)

    @property
    def replica_key(self) -> ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    @property
    def metric_key(self) -> MetricKey:
        return self.metric_family, self.metric_name

    def to_dict(self) -> dict[str, object]:
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result["evidence"] = [e.to_dict() for e in self.evidence]
        return result


@dataclass(frozen=True)
class ReplicaReviewQCEvidence:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    engine: DatasetEngine
    rmsd_drift: RMSDDriftAssessment
    protein_edge_empty_windows: ProteinEdgeEmptyWindowEvidence
    mad_metrics: tuple[ReplicaMADMetricObservation, ...]

    def __post_init__(self) -> None:
        _identity(self)
        _engine(self.engine)
        if type(self.rmsd_drift) is not RMSDDriftAssessment:
            raise DatasetReviewQCError("explicit RMSD drift assessment is required")
        if type(self.protein_edge_empty_windows) is not ProteinEdgeEmptyWindowEvidence:
            raise DatasetReviewQCError("explicit empty-window evidence is required")
        replace(self.rmsd_drift)
        replace(self.protein_edge_empty_windows)
        _records(self.mad_metrics, ReplicaMADMetricObservation, "mad_metrics")
        for metric in self.mad_metrics:
            replace(metric)
            if metric.replica_key != self.replica_key or metric.engine != self.engine:
                raise DatasetReviewQCError("metric identity/engine must match replica")
        if len({m.metric_key for m in self.mad_metrics}) != len(self.mad_metrics):
            raise DatasetReviewQCError("MAD metric identities must be unique")
        object.__setattr__(
            self,
            "mad_metrics",
            tuple(sorted(self.mad_metrics, key=lambda m: m.metric_key)),
        )

    @property
    def replica_key(self) -> ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "system_id": self.system_id,
            "trajectory_id": self.trajectory_id,
            "replica_id": self.replica_id,
            "engine": self.engine,
            "rmsd_drift": self.rmsd_drift.to_dict(),
            "protein_edge_empty_windows": self.protein_edge_empty_windows.to_dict(),
            "mad_metrics": [m.to_dict() for m in self.mad_metrics],
        }


@dataclass(frozen=True)
class ReplicaReviewQCEvaluation:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    checks: tuple[ReplicaQCCheckResult, ...]
    review_qc_status: ReviewQCStatus = field(init=False)

    def __post_init__(self) -> None:
        _identity(self)
        _records(self.checks, ReplicaQCCheckResult, "checks", nonempty=True)
        for check in self.checks:
            try:
                replace(check)
            except DatasetQCContractError as exc:
                raise DatasetReviewQCError(str(exc)) from None
            if check.status not in get_args(ReviewQCStatus):
                raise DatasetReviewQCError("review checks allow only pass/review")
            _text(check.check_id, "check_id")
            if check.human_readable_reason is not None:
                _text(check.human_readable_reason, "human_readable_reason")
            _evidence(check.evidence)
        ids = [c.check_id for c in self.checks]
        evidence_ids = [e.evidence_id for c in self.checks for e in c.evidence]
        if len(set(ids)) != len(ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise DatasetReviewQCError("check and evidence IDs must be unique")
        object.__setattr__(
            self,
            "review_qc_status",
            "review" if any(c.status == "review" for c in self.checks) else "pass",
        )

    @property
    def replica_key(self) -> ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "system_id": self.system_id,
            "trajectory_id": self.trajectory_id,
            "replica_id": self.replica_id,
            "checks": [c.to_dict() for c in self.checks],
            "review_qc_status": self.review_qc_status,
        }


@dataclass(frozen=True)
class DatasetReviewQCEvaluation:
    evaluations: tuple[ReplicaReviewQCEvaluation, ...]
    skipped_hard_failed_replica_keys: tuple[ReplicaKey, ...]

    def __post_init__(self) -> None:
        _records(self.evaluations, ReplicaReviewQCEvaluation, "evaluations")
        for evaluation in self.evaluations:
            replace(evaluation)
        _records(self.skipped_hard_failed_replica_keys, tuple, "skipped replica keys")
        for key in self.skipped_hard_failed_replica_keys:
            if len(key) != 4 or any(_text(v, "replica key") != v for v in key):
                raise DatasetReviewQCError("skipped keys require four normalized IDs")
        keys = [e.replica_key for e in self.evaluations]
        keys.extend(self.skipped_hard_failed_replica_keys)
        if len(set(keys)) != len(keys):
            raise DatasetReviewQCError(
                "evaluated and skipped replica keys must be unique"
            )
        object.__setattr__(
            self,
            "evaluations",
            tuple(sorted(self.evaluations, key=lambda e: e.replica_key)),
        )
        object.__setattr__(
            self,
            "skipped_hard_failed_replica_keys",
            tuple(sorted(self.skipped_hard_failed_replica_keys)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluations": [e.to_dict() for e in self.evaluations],
            "skipped_hard_failed_replica_keys": [
                list(key) for key in self.skipped_hard_failed_replica_keys
            ],
        }


def _metric(name: str, value: object, threshold: str | None = None) -> QCEvidenceRecord:
    return QCEvidenceRecord(
        name, "metric", None, None, None, name, str(value), threshold, None
    )


def _check(
    check_id: str,
    review: bool,
    code: QCReasonCode,
    reason: str,
    *evidence: QCEvidenceRecord,
) -> ReplicaQCCheckResult:
    # Match 32.B's per-check references, preserving structured source payloads.
    return ReplicaQCCheckResult(
        check_id,
        "review" if review else "pass",
        code if review else None,
        reason if review else None,
        tuple(
            replace(e, evidence_id=f"{check_id}:evidence:{i}")
            for i, e in enumerate(evidence)
        ),
    )


def _local_checks(evidence: ReplicaReviewQCEvidence) -> list[ReplicaQCCheckResult]:
    drift = evidence.rmsd_drift
    windows = evidence.protein_edge_empty_windows
    # A fresh context isolates precision, rounding, traps and flags. Counts retain
    # the exact rational value even when the decimal expansion repeats.
    with localcontext(
        Context(prec=max(50, len(str(windows.expected_window_count)) + 4))
    ):
        fraction = Decimal(windows.empty_window_count) / Decimal(
            windows.expected_window_count
        )
        empty_review = fraction > Decimal("0.01")
    return [
        _check(
            "rmsd_drift",
            drift.drift_detected,
            "RMSD_DRIFT_REVIEW",
            "The supplied authoritative assessment detects RMSD drift.",
            _metric("drift_detected", drift.drift_detected, "False"),
            _metric("assessment_method", drift.assessment_method),
            *drift.evidence,
        ),
        _check(
            "protein_edge_empty_window_fraction",
            empty_review,
            "PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT",
            "More than 1% of valid requested protein-edge windows have zero edges.",
            _metric("empty_window_fraction", fraction, "<=0.01"),
            _metric("expected_window_count", windows.expected_window_count),
            _metric("empty_window_count", windows.empty_window_count),
            *windows.evidence,
        ),
    ]


def _median(values: tuple[Decimal, ...]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _mad_checks(
    observations: tuple[ReplicaMADMetricObservation, ...],
) -> dict[ReplicaKey, ReplicaQCCheckResult]:
    values = tuple(Decimal(str(m.value)) for m in observations)
    # Enough significant digits for exact finite-decimal sums, differences,
    # even medians and bands, including widely separated numeric exponents.
    precision = max(
        50,
        max(v.adjusted() for v in values)
        - min(int(v.as_tuple().exponent) for v in values)
        + 8,
    )
    results = {}
    with localcontext(Context(prec=precision)):
        median = _median(values)
        mad = _median(tuple(abs(v - median) for v in values))
        band = mad > 0 and len(values) >= 2
        lower = median - Decimal(3) * mad if band else None
        upper = median + Decimal(3) * mad if band else None
        for observation, value in zip(observations, values, strict=True):
            code = _MAD_REASONS[observation.metric_family]
            reason = (
                "The metric is strictly outside the median plus/minus 3 raw MAD band."
            )
            if len(values) == 1:
                review = False
                comparison = "not_applicable_single_replica"
            elif mad == 0:
                review = value != median
                code = "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW"
                reason = "The metric differs from the median of a zero-MAD cohort."
                comparison = "zero_mad_reference_distribution"
            else:
                assert lower is not None and upper is not None
                review = value < lower or value > upper
                comparison = "raw_mad_band"
            results[observation.replica_key] = _check(
                f"mad:{observation.metric_family}:{observation.metric_name}",
                review,
                code,
                reason,
                _metric("target_value", value),
                _metric("reference_count", len(values)),
                _metric("median", median),
                _metric("mad", mad),
                _metric("lower_band", lower if band else "not_applicable"),
                _metric("upper_band", upper if band else "not_applicable"),
                _metric("comparison", comparison),
                _metric("engine", observation.engine),
                _metric("metric_family", observation.metric_family),
                _metric("metric_name", observation.metric_name),
                _metric(
                    "unit", observation.unit if observation.unit is not None else "None"
                ),
                *observation.evidence,
            )
    return results


def evaluate_dataset_review_qc(
    hard_evaluations: tuple[ReplicaHardQCEvaluation, ...],
    review_evidence: tuple[ReplicaReviewQCEvidence, ...],
) -> DatasetReviewQCEvaluation:
    """Evaluate complete hard-PASS evidence; skip hard-FAIL replicas entirely.

    Cohorts use dataset/system/engine, then exact metric family/name. Every
    hard-PASS member must supply the same metric set and matching explicit units.
    The target remains in its reference cohort. No condition lookup or I/O.
    """
    _records(hard_evaluations, ReplicaHardQCEvaluation, "hard_evaluations")
    _records(review_evidence, ReplicaReviewQCEvidence, "review_evidence")
    hard_by_key = {}
    for hard in hard_evaluations:
        try:
            validated = replace(hard)
        except DatasetHardQCError as exc:
            raise DatasetReviewQCError(str(exc)) from None
        if validated.to_dict() != hard.to_dict():
            raise DatasetReviewQCError(
                "hard result must match its accepted derived status"
            )
        if hard.replica_key in hard_by_key:
            raise DatasetReviewQCError("duplicate hard result replica key")
        hard_by_key[hard.replica_key] = hard
    evidence_by_key = {}
    for evidence in review_evidence:
        replace(evidence)
        if evidence.replica_key in evidence_by_key:
            raise DatasetReviewQCError("duplicate review evidence replica key")
        if evidence.replica_key not in hard_by_key:
            raise DatasetReviewQCError(
                "review evidence has no matching full hard replica key"
            )
        evidence_by_key[evidence.replica_key] = evidence
    cohorts: dict[CohortKey, list[ReplicaReviewQCEvidence]] = {}
    checks: dict[ReplicaKey, list[ReplicaQCCheckResult]] = {}
    skipped = []
    for key, hard in sorted(hard_by_key.items()):
        if hard.hard_qc_status == "fail":
            skipped.append(key)
            continue
        if key not in evidence_by_key:
            raise DatasetReviewQCError(
                "hard-PASS replica lacks mandatory review evidence"
            )
        evidence = evidence_by_key[key]
        cohort = evidence.dataset_id, evidence.system_id, evidence.engine
        cohorts.setdefault(cohort, []).append(evidence)
        checks[key] = _local_checks(evidence)
    for members in cohorts.values():
        metric_keys = tuple(m.metric_key for m in members[0].mad_metrics)
        if any(
            tuple(m.metric_key for m in r.mad_metrics) != metric_keys for r in members
        ):
            raise DatasetReviewQCError(
                "incomplete metric cohort: metric sets must match"
            )
        for index in range(len(metric_keys)):
            observations = tuple(r.mad_metrics[index] for r in members)
            if len({m.unit for m in observations}) != 1:
                raise DatasetReviewQCError(
                    "metric cohort units must match without conversion"
                )
            for key, finding in _mad_checks(observations).items():
                checks[key].append(finding)
    return DatasetReviewQCEvaluation(
        tuple(
            ReplicaReviewQCEvaluation(*key, tuple(value))
            for key, value in checks.items()
        ),
        tuple(skipped),
    )


__all__ = [
    "DatasetReviewQCError",
    "DatasetReviewQCEvaluation",
    "ProteinEdgeEmptyWindowEvidence",
    "RMSDDriftAssessment",
    "ReplicaMADMetricObservation",
    "ReplicaReviewQCEvaluation",
    "ReplicaReviewQCEvidence",
    "ReviewMADMetricFamily",
    "ReviewQCStatus",
    "evaluate_dataset_review_qc",
]
