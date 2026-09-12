"""Pure Stage 32.B hard findings over existing evidence; no release decisions.

Strict readers and workflow adapters belong to 32.D. Accepted canonical models
are inspected without calling constructors that load the packaged reference.
See docs/dataset_hard_qc.md for evidence authority and omitted-check policy.
"""

import re
from dataclasses import dataclass, field, replace
from decimal import Context, Decimal, localcontext
from itertools import pairwise
from typing import Literal, TypeAlias

from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowTable,
    DatasetCanonicalResidueMappingBinding,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_contract import (
    DatasetQCContractError,
    QCEvidenceRecord,
    QCReasonCode,
    ReplicaQCCheckResult,
)
from mania.preprocessing.physical_time_sampling import (
    MissingPhysicalTimeSample,
    PhysicalTimeSamplingIssue,
    ResolvedPhysicalTimeSample,
    ResolvedPhysicalTimeSamplingPlan,
)

HardQCStatus = Literal["pass", "fail"]
CanonicalTableFamily = Literal["protein_edge", "protein_lipid", "protein_glycan"]
CanonicalTable: TypeAlias = (
    CanonicalProteinEdgeWindowTable
    | CanonicalProteinLipidWindowTable
    | CanonicalProteinGlycanWindowTable
)
SourceResidueKey: TypeAlias = tuple[str, str | None, str, str]
_TABLE_TYPES = {
    "protein_edge": CanonicalProteinEdgeWindowTable,
    "protein_lipid": CanonicalProteinLipidWindowTable,
    "protein_glycan": CanonicalProteinGlycanWindowTable,
}
HARD_QC_FIXED_CHECK_IDS = (
    "topology_readable",
    "trajectory_readable",
    "topology_trajectory_atom_count",
    "topology_trajectory_atom_order",
    "canonical_mapping_complete",
    "protein_pbc_integrity",
    "frame_time_strictly_increasing",
    "production_frame_coverage",
    "canonical_reference",
    "forbidden_self_loops",
    "duplicate_records",
    "occupancy_range",
)


class DatasetHardQCError(ValueError):
    """Malformed evaluator inputs, distinct from valid hard-QC FAIL findings."""


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise DatasetHardQCError(f"{name} must be a non-empty string")
    return value.strip()


def _bool(value: object, name: str) -> None:
    if type(value) is not bool:
        raise DatasetHardQCError(f"{name} must be exact bool")


def _item_id(value: str) -> str:
    value = _text(value, "item ID")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is None:
        raise DatasetHardQCError(
            "item IDs require letters, digits, dots, dashes or underscores"
        )
    return value


def _evidence(value: object) -> None:
    if type(value) is not QCEvidenceRecord:
        raise DatasetHardQCError("evidence must be exact QCEvidenceRecord")
    try:
        replace(value)
    except DatasetQCContractError as exc:
        raise DatasetHardQCError(str(exc)) from None
    if value.evidence_type == "manual_review":
        raise DatasetHardQCError("hard evidence cannot be manual_review")


@dataclass(frozen=True)
class ReplicaRawIntegrityEvidence:
    """Authoritative observations of the same declared all-atom universe."""

    topology_readable: bool
    trajectory_readable: bool
    topology_atom_count: int | None
    trajectory_atom_count: int | None
    atom_order_consistent: bool | None
    atom_universe_id: str
    topology_evidence: QCEvidenceRecord
    trajectory_evidence: QCEvidenceRecord
    atom_order_evidence: QCEvidenceRecord | None

    def __post_init__(self) -> None:
        for source in ("topology", "trajectory"):
            readable = getattr(self, f"{source}_readable")
            count = getattr(self, f"{source}_atom_count")
            _bool(readable, f"{source}_readable")
            if count is not None and (type(count) is not int or count < 0):
                raise DatasetHardQCError("atom counts must be non-negative exact ints")
            if readable and count is None:
                raise DatasetHardQCError("readable sources require atom-count evidence")
            _evidence(getattr(self, f"{source}_evidence"))
        object.__setattr__(self, "atom_universe_id", _item_id(self.atom_universe_id))
        if self.atom_order_consistent is not None:
            _bool(self.atom_order_consistent, "atom_order_consistent")
            _evidence(self.atom_order_evidence)
        elif self.atom_order_evidence is not None:
            _evidence(self.atom_order_evidence)


@dataclass(frozen=True)
class ReplicaProteinPBCEvidence:
    """Explicit protein-integrity observation, not a box-metadata inference."""

    protein_remains_broken: bool
    evidence: QCEvidenceRecord

    def __post_init__(self) -> None:
        _bool(self.protein_remains_broken, "protein_remains_broken")
        _evidence(self.evidence)
        if self.evidence.evidence_type != "pbc":
            raise DatasetHardQCError("protein integrity requires pbc evidence")


@dataclass(frozen=True)
class RequiredMetadataEvidence:
    item_id: str
    present: bool
    evidence: QCEvidenceRecord

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _item_id(self.item_id))
        _bool(self.present, "present")
        _evidence(self.evidence)


@dataclass(frozen=True)
class RequiredArtifactEvidence:
    """An explicit required role, strict-reader outcome and optional accepted table.

    None schema state means missing validation evidence. Canonical families need
    their existing model for structural inspection after successful validation.
    """

    item_id: str
    present: bool
    schema_valid: bool | None
    evidence: QCEvidenceRecord
    canonical_family: CanonicalTableFamily | None = None
    canonical_table: CanonicalTable | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _item_id(self.item_id))
        _bool(self.present, "present")
        _evidence(self.evidence)
        if self.schema_valid is not None:
            _bool(self.schema_valid, "schema_valid")
        if not self.present and (
            self.schema_valid is not None or self.canonical_table is not None
        ):
            raise DatasetHardQCError(
                "absent artifacts cannot have validation or tables"
            )
        if self.canonical_family is not None and (
            type(self.canonical_family) is not str
            or self.canonical_family not in _TABLE_TYPES
        ):
            raise DatasetHardQCError("unknown canonical family")
        if self.canonical_table is not None and (
            self.canonical_family is None
            or type(self.canonical_table) is not _TABLE_TYPES[self.canonical_family]
        ):
            raise DatasetHardQCError("canonical table must match its exact family type")


@dataclass(frozen=True)
class ReplicaHardQCEvaluation:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    checks: tuple[ReplicaQCCheckResult, ...]
    hard_qc_status: HardQCStatus = field(init=False)

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if (
            type(self.checks) is not tuple
            or not self.checks
            or any(type(check) is not ReplicaQCCheckResult for check in self.checks)
        ):
            raise DatasetHardQCError(
                "checks must be a non-empty tuple of 32.A findings"
            )
        for check in self.checks:
            try:
                replace(check)
            except DatasetQCContractError as exc:
                raise DatasetHardQCError(str(exc)) from None
            if check.status not in ("pass", "fail"):
                raise DatasetHardQCError("hard checks allow only pass/fail")
        ids = [check.check_id for check in self.checks]
        evidence_ids = [e.evidence_id for c in self.checks for e in c.evidence]
        if len(set(ids)) != len(ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise DatasetHardQCError("check and evidence IDs must be unique")
        object.__setattr__(
            self,
            "hard_qc_status",
            ("fail" if any(c.status == "fail" for c in self.checks) else "pass"),
        )

    @property
    def replica_key(self) -> tuple[str, str, str, str]:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "system_id": self.system_id,
            "trajectory_id": self.trajectory_id,
            "replica_id": self.replica_id,
            "checks": [check.to_dict() for check in self.checks],
            "hard_qc_status": self.hard_qc_status,
        }


def _metric(name: str, observed: object, threshold: str) -> QCEvidenceRecord:
    return QCEvidenceRecord(
        name, "metric", None, None, None, name, str(observed), threshold, None
    )


def _check(
    check_id: str,
    passed: bool,
    code: QCReasonCode,
    reason: str,
    *evidence: QCEvidenceRecord,
) -> ReplicaQCCheckResult:
    # Stable per-check references allow the same source evidence to support
    # multiple checks without violating 32.A's eventual global ID uniqueness.
    return ReplicaQCCheckResult(
        check_id,
        "pass" if passed else "fail",
        None if passed else code,
        None if passed else reason,
        tuple(
            replace(e, evidence_id=f"{check_id}:evidence:{i}")
            for i, e in enumerate(evidence)
        ),
    )


def _missing(check_id: str, *, artifact: bool = False) -> ReplicaQCCheckResult:
    return _check(
        check_id,
        False,
        "REQUIRED_ARTIFACT_MISSING" if artifact else "REQUIRED_METADATA_MISSING",
        "Required artifact is absent."
        if artifact
        else "Required authoritative evidence is absent.",
        _metric(check_id, "absent", "present"),
    )


def _requirements(
    values: tuple[RequiredMetadataEvidence, ...] | tuple[RequiredArtifactEvidence, ...],
    expected_type: type[RequiredMetadataEvidence] | type[RequiredArtifactEvidence],
) -> None:
    if type(values) is not tuple or any(type(v) is not expected_type for v in values):
        raise DatasetHardQCError("requirements must be a tuple of exact evidence types")
    ids = [v.item_id for v in values]
    if len(set(ids)) != len(ids):
        raise DatasetHardQCError("requirement IDs must be unique within their category")
    for value in values:
        replace(value)


def _mapping_check(
    binding: DatasetCanonicalResidueMappingBinding | None,
    required: tuple[SourceResidueKey, ...] | None,
) -> ReplicaQCCheckResult:
    check_id = "canonical_mapping_complete"
    if binding is None:
        return _missing(check_id, artifact=True)
    if required is None:
        return _missing(check_id)
    records = {r.source_key: r for r in binding.mapping_table.mappings}
    incomplete = tuple(
        key
        for key in required
        if (key not in records or records[key].mapping_status != "mapped")
    )
    evidence = QCEvidenceRecord(
        check_id,
        "mapping",
        None,
        None,
        None,
        None,
        None,
        None,
        f"Required source residues: {len(required)}; "
        f"missing or unmapped records: {len(incomplete)}.",
    )
    return _check(
        check_id,
        not incomplete,
        "CANONICAL_MAPPING_INCOMPLETE",
        "Required source protein residues lack explicit mapped records.",
        evidence,
    )


def _time_checks(plan: ResolvedPhysicalTimeSamplingPlan) -> list[ReplicaQCCheckResult]:
    times = tuple(Decimal(str(s.actual_time_ps)) for s in plan.selected_samples)
    violations = sum(b <= a for a, b in pairwise(times))
    # Accepted Stage 27 rejects these axes before selecting any samples. Its
    # retained diagnostic is a negative observation, unlike missing samples.
    source_violation = any(i.code == "non_monotonic_source_time" for i in plan.issues)
    monotonic = _check(
        "frame_time_strictly_increasing",
        not violations and not source_violation,
        "FRAME_TIME_NOT_STRICTLY_INCREASING",
        "Actual frame times contain an equal or decreasing adjacent observation.",
        _metric("resolved_time_pair_violations", violations, "0"),
        _metric("source_non_monotonic_time_reported", source_violation, "False"),
        _metric("resolved_actual_time_count", len(times), ">=0; sparse is valid"),
    )
    expected = plan.requested_sample_count
    resolved = len(plan.selected_samples)
    # A fixed fresh context makes repeating quotients independent of ambient
    # precision/traps. The decision uses exact cross multiplication in Decimal.
    with localcontext(Context(prec=max(50, len(str(expected)) + 4))):
        coverage = Decimal(resolved) / Decimal(expected)
        passed = Decimal(resolved) >= Decimal("0.95") * Decimal(expected)
    return [
        monotonic,
        _check(
            "production_frame_coverage",
            passed,
            "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
            "Fewer than 95% of expected requested production samples resolved.",
            _metric("production_frame_coverage", coverage, ">=0.95"),
            _metric(
                "expected_production_samples", expected, "Stage 27 requested count"
            ),
            _metric(
                "resolved_expected_production_samples", resolved, ">=0.95 * expected"
            ),
        ),
    ]


def _validate_sampling_evidence(plan: ResolvedPhysicalTimeSamplingPlan) -> None:
    # Validate the supplied partition, never regenerate targets or rematch frames.
    for name in (
        "requested_sample_count",
        "sampled_frame_count",
        "missing_sample_count",
        "source_frame_count",
    ):
        value = getattr(plan, name)
        if type(value) is not int or value < 0:
            raise DatasetHardQCError("sampling counts must be non-negative exact ints")
    if plan.requested_sample_count == 0:
        raise DatasetHardQCError("expected production sampling must be nonempty")
    for records, cls in (
        (plan.selected_samples, ResolvedPhysicalTimeSample),
        (plan.missing_samples, MissingPhysicalTimeSample),
        (plan.issues, PhysicalTimeSamplingIssue),
    ):
        if type(records) is not tuple or any(type(r) is not cls for r in records):
            raise DatasetHardQCError(
                "sampling evidence requires exact accepted records"
            )
    if (
        len(plan.selected_samples) != plan.sampled_frame_count
        or len(plan.missing_samples) != plan.missing_sample_count
        or plan.sampled_frame_count + plan.missing_sample_count
        != plan.requested_sample_count
        or plan.sampled_frame_count > plan.source_frame_count
    ):
        raise DatasetHardQCError("sampling counts must describe the expected partition")
    seen: set[int] = set()
    for samples in (plan.selected_samples, plan.missing_samples):
        previous = -1
        for sample in samples:
            index = sample.requested_sample_index
            if (
                type(index) is not int
                or not previous < index < plan.requested_sample_count
                or index in seen
            ):
                raise DatasetHardQCError(
                    "sampling records must partition targets in order"
                )
            seen.add(index)
            previous = index
    source_indexes = []
    for sample in plan.selected_samples:
        if type(sample.source_frame_index) is not int or sample.source_frame_index < 0:
            raise DatasetHardQCError(
                "source frame indexes must be non-negative exact ints"
            )
        source_indexes.append(sample.source_frame_index)
        value = sample.actual_time_ps
        if (
            type(value) not in (int, float)
            or not Decimal(str(value)).is_finite()
            or value < 0
        ):
            raise DatasetHardQCError("actual times must be finite non-negative numbers")
    if len(set(source_indexes)) != len(source_indexes):
        raise DatasetHardQCError("resolved samples must use distinct source frames")


def _structural_checks(
    artifacts: tuple[RequiredArtifactEvidence, ...],
    binding: DatasetCanonicalResidueMappingBinding | None,
    replica_key: tuple[str, str, str, str],
) -> list[ReplicaQCCheckResult]:
    references = []
    if binding is not None:
        references.append(
            (
                binding.mapping_table.canonical_reference_id,
                binding.mapping_table.canonical_reference_sequence_sha256,
            )
        )
    tables = [a.canonical_table for a in artifacts if a.canonical_table is not None]
    for reference_table in tables:
        references.append(
            (
                reference_table.canonical_reference_id,
                reference_table.canonical_reference_sequence_sha256,
            )
        )
    pinned = (
        CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
        CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    )
    checks = (
        [
            _check(
                "canonical_reference",
                all(r == pinned for r in references),
                "CANONICAL_REFERENCE_MISMATCH",
                "Canonical reference ID or sequence hash differs.",
                *(
                    _metric(
                        f"canonical_reference_{i}",
                        f"{r[0]} {r[1]}",
                        f"{pinned[0]} {pinned[1]}",
                    )
                    for i, r in enumerate(references)
                ),
            )
        ]
        if references
        else [_missing("canonical_reference")]
    )
    loops: list[QCEvidenceRecord] = []
    duplicates: list[QCEvidenceRecord] = []
    occupancies: list[QCEvidenceRecord] = []
    loop_count = duplicate_count = occupancy_count = 0
    for artifact in artifacts:
        table = artifact.canonical_table
        if table is None:
            continue
        if type(table.rows) is not tuple or any(
            type(row) is not table._row_type for row in table.rows
        ):
            raise DatasetHardQCError("canonical rows must have the exact accepted type")
        rows = [r for r in table.rows if r.replica_key == replica_key]
        identities = [r.row_identity for r in rows]
        duplicate = len(identities) - len(set(identities))
        duplicate_count += duplicate
        duplicates.append(_metric(artifact.item_id, duplicate, "duplicate records = 0"))
        if type(table) is CanonicalProteinEdgeWindowTable:
            count = sum(
                r.source_canonical_residue_number == r.target_canonical_residue_number
                for r in table.rows
                if r.replica_key == replica_key
            )
            loop_count += count
            loops.append(_metric(artifact.item_id, count, "forbidden self-loops = 0"))
        invalid = 0
        for row in rows:
            if type(row.occupancy) not in (int, float):
                raise DatasetHardQCError("stored occupancy must be an int or float")
            value = Decimal(str(row.occupancy))
            if not value.is_finite() or not Decimal(0) <= value <= Decimal(1):
                invalid += 1
                occupancies.append(
                    _metric(
                        f"{artifact.item_id}:row:{len(occupancies)}:occupancy",
                        value,
                        "finite; 0 <= occupancy <= 1",
                    )
                )
        occupancy_count += invalid
        occupancies.append(
            _metric(artifact.item_id, invalid, "invalid occupancy rows = 0")
        )
    criteria: tuple[tuple[str, int, QCReasonCode, str, list[QCEvidenceRecord]], ...] = (
        (
            "forbidden_self_loops",
            loop_count,
            "FORBIDDEN_SELF_LOOP",
            "Canonical protein edges contain forbidden self-loops.",
            loops,
        ),
        (
            "duplicate_records",
            duplicate_count,
            "DUPLICATE_RECORD",
            "Canonical table contains repeated accepted row identities.",
            duplicates,
        ),
        (
            "occupancy_range",
            occupancy_count,
            "OCCUPANCY_OUT_OF_RANGE",
            "Stored occupancy must be finite and in the inclusive range [0, 1].",
            occupancies,
        ),
    )
    for check_id, count, code, reason, evidence in criteria:
        if evidence:
            checks.append(_check(check_id, count == 0, code, reason, *evidence))
    return checks


def evaluate_replica_hard_qc(
    *,
    identity: DatasetTrajectoryIdentity,
    raw_integrity: ReplicaRawIntegrityEvidence,
    mapping_binding: DatasetCanonicalResidueMappingBinding | None,
    required_source_keys: tuple[SourceResidueKey, ...] | None,
    protein_pbc: ReplicaProteinPBCEvidence | None,
    sampling_plan: ResolvedPhysicalTimeSamplingPlan | None,
    required_metadata: tuple[RequiredMetadataEvidence, ...],
    required_artifacts: tuple[RequiredArtifactEvidence, ...],
) -> ReplicaHardQCEvaluation:
    """Inspect existing evidence in fixed order without I/O or scientific builders.

    Requirement collections are explicit, never discovered from sparse science.
    A missing model is evidence absence; malformed model types raise the public
    error. Numeric hard defects in canonical model fields remain QC findings.
    """
    if type(identity) is not DatasetTrajectoryIdentity:
        raise DatasetHardQCError("identity must be exact DatasetTrajectoryIdentity")
    if type(raw_integrity) is not ReplicaRawIntegrityEvidence:
        raise DatasetHardQCError(
            "raw_integrity must be exact ReplicaRawIntegrityEvidence"
        )
    replace(raw_integrity)
    if protein_pbc is not None and type(protein_pbc) is not ReplicaProteinPBCEvidence:
        raise DatasetHardQCError("protein_pbc must be exact ReplicaProteinPBCEvidence")
    if protein_pbc is not None:
        replace(protein_pbc)
    if mapping_binding is not None:
        if type(mapping_binding) is not DatasetCanonicalResidueMappingBinding:
            raise DatasetHardQCError("mapping_binding must be exact accepted binding")
        if mapping_binding.replica_key != identity.replica_key:
            raise DatasetHardQCError("mapping binding must match the full replica key")
        table = mapping_binding.mapping_table
        if type(table) is not CanonicalResidueMappingTable:
            raise DatasetHardQCError("mapping table must have its exact accepted type")
        try:
            replace(table)
            for record in table.mappings:
                replace(record)
        except (TypeError, ValueError):
            raise DatasetHardQCError("malformed accepted mapping evidence") from None
    if required_source_keys is not None:
        if type(required_source_keys) is not tuple:
            raise DatasetHardQCError("required_source_keys must be a tuple")
        for key in required_source_keys:
            if type(key) is not tuple or len(key) != 4:
                raise DatasetHardQCError("required source keys must have four fields")
            try:
                CanonicalResidueMappingRecord(*key, None, None, "unmapped")
            except (TypeError, ValueError):
                raise DatasetHardQCError(
                    "invalid required Stage 30 source key"
                ) from None
        if len(set(required_source_keys)) != len(required_source_keys):
            raise DatasetHardQCError("required source keys must be unique")
    if (
        sampling_plan is not None
        and type(sampling_plan) is not ResolvedPhysicalTimeSamplingPlan
    ):
        raise DatasetHardQCError("sampling_plan must be exact accepted Stage 27 plan")
    if sampling_plan is not None:
        _validate_sampling_evidence(sampling_plan)
    _requirements(required_metadata, RequiredMetadataEvidence)
    _requirements(required_artifacts, RequiredArtifactEvidence)
    artifacts = tuple(sorted(required_artifacts, key=lambda a: a.item_id))
    families = [a.canonical_family for a in artifacts if a.canonical_family is not None]
    if len(set(families)) != len(families):
        raise DatasetHardQCError("supply one complete table per canonical family")
    raw = raw_integrity
    checks = [
        _check(
            "topology_readable",
            raw.topology_readable,
            "TOPOLOGY_UNREADABLE",
            "Authoritative topology readability check failed.",
            raw.topology_evidence,
            _metric("topology_readable", raw.topology_readable, "True"),
        ),
        _check(
            "trajectory_readable",
            raw.trajectory_readable,
            "TRAJECTORY_UNREADABLE",
            "Authoritative trajectory readability check failed.",
            raw.trajectory_evidence,
            _metric("trajectory_readable", raw.trajectory_readable, "True"),
        ),
    ]
    both_readable = raw.topology_readable and raw.trajectory_readable
    if both_readable:
        checks.append(
            _check(
                "topology_trajectory_atom_count",
                raw.topology_atom_count == raw.trajectory_atom_count,
                "TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH",
                "Topology and trajectory all-atom counts differ "
                "in the declared universe.",
                raw.topology_evidence,
                raw.trajectory_evidence,
                _metric(
                    "topology_atom_count",
                    raw.topology_atom_count,
                    "trajectory_atom_count",
                ),
                _metric(
                    "trajectory_atom_count",
                    raw.trajectory_atom_count,
                    "topology_atom_count",
                ),
                _metric(
                    "atom_universe_id", raw.atom_universe_id, "same all-atom universe"
                ),
            )
        )
        checks.append(
            _missing("topology_trajectory_atom_order")
            if raw.atom_order_consistent is None
            else _check(
                "topology_trajectory_atom_order",
                raw.atom_order_consistent,
                "TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH",
                "Authoritative evidence reports inconsistent semantic atom order.",
                raw.atom_order_evidence or raw.topology_evidence,
                _metric("atom_order_consistent", raw.atom_order_consistent, "True"),
            )
        )
    # Retained artifact-level evidence stays useful after raw readability fails.
    if raw.topology_readable or mapping_binding is not None:
        checks.append(_mapping_check(mapping_binding, required_source_keys))
    if protein_pbc is not None:
        checks.append(
            _check(
                "protein_pbc_integrity",
                not protein_pbc.protein_remains_broken,
                "PROTEIN_PBC_BROKEN",
                "Authoritative evidence reports protein remains PBC-broken.",
                protein_pbc.evidence,
                _metric(
                    "protein_remains_pbc_broken",
                    protein_pbc.protein_remains_broken,
                    "False",
                ),
            )
        )
    elif both_readable:
        checks.append(_missing("protein_pbc_integrity"))
    if sampling_plan is not None:
        checks.extend(_time_checks(sampling_plan))
    elif raw.trajectory_readable:
        checks.extend(
            _missing(i)
            for i in ("frame_time_strictly_increasing", "production_frame_coverage")
        )
    for item in sorted(required_metadata, key=lambda m: m.item_id):
        checks.append(
            _check(
                f"required_metadata:{item.item_id}",
                item.present,
                "REQUIRED_METADATA_MISSING",
                "Explicitly required metadata is absent.",
                item.evidence,
                _metric("present", item.present, "True"),
            )
        )
    for artifact in artifacts:
        checks.append(
            _check(
                f"required_artifact:{artifact.item_id}",
                artifact.present,
                "REQUIRED_ARTIFACT_MISSING",
                "Explicitly required artifact is absent.",
                artifact.evidence,
                _metric("present", artifact.present, "True"),
            )
        )
    for artifact in artifacts:
        if not artifact.present:
            continue
        check_id = f"schema:{artifact.item_id}"
        if artifact.schema_valid is None:
            checks.append(_missing(check_id))
        else:
            checks.append(
                _check(
                    check_id,
                    artifact.schema_valid,
                    "SCHEMA_INVALID",
                    "Accepted strict artifact validation failed.",
                    artifact.evidence,
                    _metric("schema_valid", artifact.schema_valid, "True"),
                )
            )
        if (
            artifact.canonical_family is not None
            and artifact.schema_valid is True
            and (artifact.canonical_table is None)
        ):
            checks.append(_missing(f"schema:{artifact.item_id}:canonical_model"))
    checks.extend(_structural_checks(artifacts, mapping_binding, identity.replica_key))
    return ReplicaHardQCEvaluation(*identity.replica_key, tuple(checks))


__all__ = [
    "HardQCStatus",
    "CanonicalTableFamily",
    "CanonicalTable",
    "SourceResidueKey",
    "HARD_QC_FIXED_CHECK_IDS",
    "DatasetHardQCError",
    "ReplicaRawIntegrityEvidence",
    "ReplicaProteinPBCEvidence",
    "RequiredMetadataEvidence",
    "RequiredArtifactEvidence",
    "ReplicaHardQCEvaluation",
    "evaluate_replica_hard_qc",
]
