"""Conservative cross-condition comparison of accepted static RIN metrics."""

from __future__ import annotations

import csv
import itertools
import json
import math
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from mania.analysis.static_rin_metrics import STATIC_RIN_METRICS_COLUMNS

STATIC_RIN_COMPARISON_COLUMNS = (
    "comparison_id",
    "scope",
    "condition_a",
    "condition_b",
    "entity_key",
    "node_id_a",
    "node_id_b",
    "residue_index",
    "resid",
    "resname",
    "segment_id",
    "metric",
    "value_a",
    "value_b",
    "delta",
    "status",
    "source_artifact_a",
    "source_artifact_b",
    "notes",
)

STATIC_RIN_STATS_COLUMNS = (
    "comparison_id",
    "scope",
    "condition_a",
    "condition_b",
    "metric",
    "method",
    "n_a",
    "n_b",
    "matched_count",
    "unmatched_condition_a_count",
    "unmatched_condition_b_count",
    "missing_metric_count",
    "statistic",
    "effect_size",
    "ci_low",
    "ci_high",
    "p_value",
    "p_adjusted",
    "correction",
    "status",
    "notes",
)

STATIC_RIN_COMPARISON_METRICS = STATIC_RIN_METRICS_COLUMNS[6:]
STATIC_RIN_COMPARISON_METHODS = (
    "paired_delta_summary",
    "cohens_dz",
)
STATIC_RIN_DEFERRED_COMPARISON_SCOPES = (
    "edge_metrics",
    "communities",
    "region_enrichment",
)

COMPARISON_STATUS_COMPUTED = "computed"
COMPARISON_STATUS_SKIPPED_MISSING_METRIC = "skipped_missing_metric"
COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_A = (
    "skipped_unmatched_condition_a"
)
COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_B = (
    "skipped_unmatched_condition_b"
)
COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT = "skipped_identity_conflict"
COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA = "skipped_insufficient_data"
COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE = "skipped_undefined_variance"
COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE = "skipped_unsupported_scope"


class StaticRinComparisonError(ValueError):
    """Raised when accepted Stage 21.B artifacts cannot be compared."""


@dataclass(frozen=True)
class StaticRinComparisonRow:
    """One entity-and-metric comparison row."""

    comparison_id: str
    scope: str
    condition_a: str
    condition_b: str
    entity_key: str
    node_id_a: str | None
    node_id_b: str | None
    residue_index: int
    resid: str | None
    resname: str | None
    segment_id: str | None
    metric: str
    value_a: float | None
    value_b: float | None
    delta: float | None
    status: str
    source_artifact_a: str
    source_artifact_b: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        """Return one CSV-ready comparison row."""
        return {
            column: getattr(self, column)
            for column in STATIC_RIN_COMPARISON_COLUMNS
        }


@dataclass(frozen=True)
class StaticRinStatsRow:
    """One method-level statistical result or explicit skipped status."""

    comparison_id: str
    scope: str
    condition_a: str
    condition_b: str
    metric: str
    method: str
    n_a: int
    n_b: int
    matched_count: int
    unmatched_condition_a_count: int
    unmatched_condition_b_count: int
    missing_metric_count: int
    statistic: float | None
    effect_size: float | None
    ci_low: float | None
    ci_high: float | None
    p_value: float | None
    p_adjusted: float | None
    correction: str
    status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        """Return one CSV-ready statistics row."""
        return {column: getattr(self, column) for column in STATIC_RIN_STATS_COLUMNS}


@dataclass(frozen=True)
class StaticRinComparison:
    """Deterministic Stage 21.E comparison and method rows."""

    conditions: tuple[str, ...]
    comparison_rows: tuple[StaticRinComparisonRow, ...]
    stats_rows: tuple[StaticRinStatsRow, ...]


@dataclass(frozen=True)
class StaticRinComparisonArtifacts:
    """Paths to the two root-level Stage 21.E artifacts."""

    comparison_csv: Path
    stats_csv: Path


@dataclass(frozen=True)
class _NodeIdentity:
    residue_index: int
    resid: str
    resname: str
    segment_id: str | None

    @property
    def entity_key(self) -> str:
        return json.dumps(
            [self.residue_index, self.resid, self.resname, self.segment_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class _CentralityRow:
    condition: str
    node_id: str
    identity: _NodeIdentity
    metrics: Mapping[str, float | None]


@dataclass(frozen=True)
class _CentralityArtifact:
    condition: str
    source_name: str
    by_residue_index: Mapping[int, _CentralityRow]


@dataclass(frozen=True)
class _StatsContext:
    comparison_id: str
    condition_a: str
    condition_b: str
    metric: str
    n_a: int
    n_b: int
    matched_count: int
    unmatched_condition_a_count: int
    unmatched_condition_b_count: int
    missing_metric_count: int


def compare_static_rin_metrics_from_artifacts(
    centrality_csvs: Sequence[str | Path],
) -> StaticRinComparison:
    """Compare every lexical condition pair from accepted Stage 21.B CSVs."""
    if isinstance(centrality_csvs, (str, bytes)):
        raise TypeError("centrality_csvs must be a sequence of paths")
    artifacts = tuple(_load_centrality_artifact(Path(path)) for path in centrality_csvs)
    if len(artifacts) < 2:
        raise StaticRinComparisonError(
            "at least two Stage 21.B centrality artifacts are required"
        )
    by_condition: dict[str, _CentralityArtifact] = {}
    for artifact in artifacts:
        if artifact.condition in by_condition:
            raise StaticRinComparisonError(
                f"duplicate centrality condition: {artifact.condition}"
            )
        by_condition[artifact.condition] = artifact

    conditions = tuple(sorted(by_condition))
    comparisons: list[StaticRinComparisonRow] = []
    stats: list[StaticRinStatsRow] = []
    for condition_a, condition_b in itertools.combinations(conditions, 2):
        pair_comparisons, pair_stats = _compare_pair(
            by_condition[condition_a], by_condition[condition_b]
        )
        comparisons.extend(pair_comparisons)
        stats.extend(pair_stats)
    return StaticRinComparison(
        conditions=conditions,
        comparison_rows=tuple(comparisons),
        stats_rows=tuple(stats),
    )


def write_static_rin_comparison_artifacts(
    comparison: StaticRinComparison,
    output_dir: str | Path,
) -> StaticRinComparisonArtifacts:
    """Write deterministic root-level ``comparison.csv`` and ``stats.csv``."""
    if not isinstance(comparison, StaticRinComparison):
        raise TypeError("comparison must be a StaticRinComparison")
    directory = Path(output_dir)
    if directory.exists() and not directory.is_dir():
        raise StaticRinComparisonError(
            "static RIN comparison output is not a directory"
        )
    comparison_path = directory / "comparison.csv"
    stats_path = directory / "stats.csv"
    _write_csv(
        comparison_path,
        STATIC_RIN_COMPARISON_COLUMNS,
        tuple(row.to_dict() for row in comparison.comparison_rows),
    )
    _write_csv(
        stats_path,
        STATIC_RIN_STATS_COLUMNS,
        tuple(row.to_dict() for row in comparison.stats_rows),
    )
    return StaticRinComparisonArtifacts(comparison_path, stats_path)


def _compare_pair(
    artifact_a: _CentralityArtifact,
    artifact_b: _CentralityArtifact,
) -> tuple[list[StaticRinComparisonRow], list[StaticRinStatsRow]]:
    condition_a = artifact_a.condition
    condition_b = artifact_b.condition
    comparison_id = f"node_metrics:{condition_a}__{condition_b}"
    indexes_a = set(artifact_a.by_residue_index)
    indexes_b = set(artifact_b.by_residue_index)
    shared_indexes = indexes_a & indexes_b
    matched_indexes = tuple(
        sorted(
            index
            for index in shared_indexes
            if (
                artifact_a.by_residue_index[index].identity
                == artifact_b.by_residue_index[index].identity
            )
        )
    )
    conflict_indexes = tuple(sorted(shared_indexes - set(matched_indexes)))
    only_a_indexes = tuple(sorted(indexes_a - indexes_b))
    only_b_indexes = tuple(sorted(indexes_b - indexes_a))
    unmatched_a_count = len(only_b_indexes) + len(conflict_indexes)
    unmatched_b_count = len(only_a_indexes) + len(conflict_indexes)

    comparison_rows: list[StaticRinComparisonRow] = []
    for index in sorted(indexes_a | indexes_b):
        row_a = artifact_a.by_residue_index.get(index)
        row_b = artifact_b.by_residue_index.get(index)
        if index in conflict_indexes:
            assert row_a is not None and row_b is not None
            comparison_rows.extend(
                _identity_conflict_rows(
                    comparison_id, artifact_a, artifact_b, row_a, row_b
                )
            )
        elif row_a is None:
            assert row_b is not None
            comparison_rows.extend(
                _unmatched_rows(
                    comparison_id,
                    artifact_a,
                    artifact_b,
                    row_b,
                    missing_condition="a",
                )
            )
        elif row_b is None:
            comparison_rows.extend(
                _unmatched_rows(
                    comparison_id,
                    artifact_a,
                    artifact_b,
                    row_a,
                    missing_condition="b",
                )
            )
        else:
            comparison_rows.extend(
                _matched_rows(
                    comparison_id, artifact_a, artifact_b, row_a, row_b
                )
            )

    stats_rows = _pair_stats_rows(
        comparison_id=comparison_id,
        artifact_a=artifact_a,
        artifact_b=artifact_b,
        matched_indexes=matched_indexes,
        conflict_count=len(conflict_indexes),
        unmatched_a_count=unmatched_a_count,
        unmatched_b_count=unmatched_b_count,
    )
    return comparison_rows, stats_rows


def _matched_rows(
    comparison_id: str,
    artifact_a: _CentralityArtifact,
    artifact_b: _CentralityArtifact,
    row_a: _CentralityRow,
    row_b: _CentralityRow,
) -> list[StaticRinComparisonRow]:
    identity = row_a.identity
    rows: list[StaticRinComparisonRow] = []
    for metric in STATIC_RIN_COMPARISON_METRICS:
        value_a = row_a.metrics[metric]
        value_b = row_b.metrics[metric]
        if value_a is None or value_b is None:
            status = COMPARISON_STATUS_SKIPPED_MISSING_METRIC
            delta = None
            notes = "At least one accepted Stage 21.B metric value is missing."
        else:
            status = COMPARISON_STATUS_COMPUTED
            delta = value_b - value_a
            notes = "delta = value_b - value_a for one exact residue identity match."
        rows.append(
            StaticRinComparisonRow(
                comparison_id=comparison_id,
                scope="node_metrics",
                condition_a=artifact_a.condition,
                condition_b=artifact_b.condition,
                entity_key=identity.entity_key,
                node_id_a=row_a.node_id,
                node_id_b=row_b.node_id,
                residue_index=identity.residue_index,
                resid=identity.resid,
                resname=identity.resname,
                segment_id=identity.segment_id,
                metric=metric,
                value_a=value_a,
                value_b=value_b,
                delta=delta,
                status=status,
                source_artifact_a=artifact_a.source_name,
                source_artifact_b=artifact_b.source_name,
                notes=notes,
            )
        )
    return rows


def _unmatched_rows(
    comparison_id: str,
    artifact_a: _CentralityArtifact,
    artifact_b: _CentralityArtifact,
    row: _CentralityRow,
    *,
    missing_condition: str,
) -> list[StaticRinComparisonRow]:
    identity = row.identity
    missing_a = missing_condition == "a"
    status = (
        COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_A
        if missing_a
        else COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_B
    )
    return [
        StaticRinComparisonRow(
            comparison_id=comparison_id,
            scope="node_metrics",
            condition_a=artifact_a.condition,
            condition_b=artifact_b.condition,
            entity_key=identity.entity_key,
            node_id_a=None if missing_a else row.node_id,
            node_id_b=row.node_id if missing_a else None,
            residue_index=identity.residue_index,
            resid=identity.resid,
            resname=identity.resname,
            segment_id=identity.segment_id,
            metric=metric,
            value_a=None if missing_a else row.metrics[metric],
            value_b=row.metrics[metric] if missing_a else None,
            delta=None,
            status=status,
            source_artifact_a=artifact_a.source_name,
            source_artifact_b=artifact_b.source_name,
            notes=(
                "Stable residue identity is absent from condition_a."
                if missing_a
                else "Stable residue identity is absent from condition_b."
            ),
        )
        for metric in STATIC_RIN_COMPARISON_METRICS
    ]


def _identity_conflict_rows(
    comparison_id: str,
    artifact_a: _CentralityArtifact,
    artifact_b: _CentralityArtifact,
    row_a: _CentralityRow,
    row_b: _CentralityRow,
) -> list[StaticRinComparisonRow]:
    index = row_a.identity.residue_index
    return [
        StaticRinComparisonRow(
            comparison_id=comparison_id,
            scope="node_metrics",
            condition_a=artifact_a.condition,
            condition_b=artifact_b.condition,
            entity_key=f"residue_index:{index}:identity_conflict",
            node_id_a=row_a.node_id,
            node_id_b=row_b.node_id,
            residue_index=index,
            resid=None,
            resname=None,
            segment_id=None,
            metric=metric,
            value_a=row_a.metrics[metric],
            value_b=row_b.metrics[metric],
            delta=None,
            status=COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT,
            source_artifact_a=artifact_a.source_name,
            source_artifact_b=artifact_b.source_name,
            notes=(
                "The shared residue_index has conflicting resid, resname, or "
                "segment_id identity; values are not compared."
            ),
        )
        for metric in STATIC_RIN_COMPARISON_METRICS
    ]


def _pair_stats_rows(
    *,
    comparison_id: str,
    artifact_a: _CentralityArtifact,
    artifact_b: _CentralityArtifact,
    matched_indexes: Sequence[int],
    conflict_count: int,
    unmatched_a_count: int,
    unmatched_b_count: int,
) -> list[StaticRinStatsRow]:
    rows: list[StaticRinStatsRow] = []
    for metric in STATIC_RIN_COMPARISON_METRICS:
        values_a = [
            artifact_a.by_residue_index[index].metrics[metric]
            for index in matched_indexes
        ]
        values_b = [
            artifact_b.by_residue_index[index].metrics[metric]
            for index in matched_indexes
        ]
        complete_pairs = tuple(
            (value_a, value_b)
            for value_a, value_b in zip(values_a, values_b, strict=True)
            if value_a is not None and value_b is not None
        )
        deltas = tuple(value_b - value_a for value_a, value_b in complete_pairs)
        common = _StatsContext(
            comparison_id=comparison_id,
            condition_a=artifact_a.condition,
            condition_b=artifact_b.condition,
            metric=metric,
            n_a=sum(value is not None for value in values_a),
            n_b=sum(value is not None for value in values_b),
            matched_count=len(matched_indexes),
            unmatched_condition_a_count=unmatched_a_count,
            unmatched_condition_b_count=unmatched_b_count,
            missing_metric_count=len(matched_indexes) - len(complete_pairs),
        )
        rows.append(_paired_delta_stats_row(common, deltas, conflict_count))
        rows.append(_cohens_dz_stats_row(common, deltas, conflict_count))

    for scope in STATIC_RIN_DEFERRED_COMPARISON_SCOPES:
        rows.append(
            StaticRinStatsRow(
                comparison_id=comparison_id,
                scope=scope,
                condition_a=artifact_a.condition,
                condition_b=artifact_b.condition,
                metric="not_applicable",
                method="not_implemented",
                n_a=0,
                n_b=0,
                matched_count=0,
                unmatched_condition_a_count=0,
                unmatched_condition_b_count=0,
                missing_metric_count=0,
                statistic=None,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                p_adjusted=None,
                correction="none",
                status=COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE,
                notes=_deferred_scope_note(scope),
            )
        )
    return rows


def _paired_delta_stats_row(
    common: _StatsContext,
    deltas: Sequence[float],
    conflict_count: int,
) -> StaticRinStatsRow:
    statistic: float | None = None
    if conflict_count:
        status = COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT
        notes = _conflict_stats_note(conflict_count)
    elif not deltas:
        status = COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA
        notes = "At least one complete exact-identity metric pair is required."
    else:
        status = COMPARISON_STATUS_COMPUTED
        statistic = math.fsum(deltas) / len(deltas)
        notes = (
            "Arithmetic mean of paired deltas (value_b - value_a); missing "
            "metric pairs are excluded and counted."
        )
    return StaticRinStatsRow(
        comparison_id=common.comparison_id,
        scope="node_metrics",
        condition_a=common.condition_a,
        condition_b=common.condition_b,
        metric=common.metric,
        method="paired_delta_summary",
        n_a=common.n_a,
        n_b=common.n_b,
        matched_count=common.matched_count,
        unmatched_condition_a_count=common.unmatched_condition_a_count,
        unmatched_condition_b_count=common.unmatched_condition_b_count,
        missing_metric_count=common.missing_metric_count,
        statistic=statistic,
        effect_size=None,
        ci_low=None,
        ci_high=None,
        p_value=None,
        p_adjusted=None,
        correction="none",
        status=status,
        notes=notes,
    )


def _cohens_dz_stats_row(
    common: _StatsContext,
    deltas: Sequence[float],
    conflict_count: int,
) -> StaticRinStatsRow:
    effect_size: float | None = None
    if conflict_count:
        status = COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT
        notes = _conflict_stats_note(conflict_count)
    elif len(deltas) < 2:
        status = COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA
        notes = "Cohen's dz requires at least two complete paired differences."
    else:
        mean_delta = math.fsum(deltas) / len(deltas)
        variance = math.fsum((value - mean_delta) ** 2 for value in deltas) / (
            len(deltas) - 1
        )
        if variance == 0.0:
            status = COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE
            notes = (
                "Cohen's dz is undefined because paired differences have zero "
                "sample variance."
            )
        else:
            status = COMPARISON_STATUS_COMPUTED
            effect_size = mean_delta / math.sqrt(variance)
            notes = (
                "Cohen's dz = mean paired difference / sample standard "
                "deviation of paired differences."
            )
    return StaticRinStatsRow(
        comparison_id=common.comparison_id,
        scope="node_metrics",
        condition_a=common.condition_a,
        condition_b=common.condition_b,
        metric=common.metric,
        method="cohens_dz",
        n_a=common.n_a,
        n_b=common.n_b,
        matched_count=common.matched_count,
        unmatched_condition_a_count=common.unmatched_condition_a_count,
        unmatched_condition_b_count=common.unmatched_condition_b_count,
        missing_metric_count=common.missing_metric_count,
        statistic=None,
        effect_size=effect_size,
        ci_low=None,
        ci_high=None,
        p_value=None,
        p_adjusted=None,
        correction="none",
        status=status,
        notes=notes,
    )


def _conflict_stats_note(conflict_count: int) -> str:
    return (
        f"{conflict_count} shared residue_index value(s) have conflicting stable "
        "identity; no statistic is computed for this condition pair. Conflicts "
        "are included in both unmatched counts."
    )


def _deferred_scope_note(scope: str) -> str:
    if scope == "edge_metrics":
        return "Edge comparison is deferred; absent edges are not treated as zero."
    if scope == "communities":
        return "Community IDs are condition-local and are not matched."
    return (
        "Region enrichment comparison is deferred because condition-local "
        "community IDs are not stable cross-condition groups."
    )


def _load_centrality_artifact(path: Path) -> _CentralityArtifact:
    try:
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames != list(STATIC_RIN_METRICS_COLUMNS):
                raise StaticRinComparisonError(
                    f"Stage 21.B centrality columns do not match: {path}"
                )
            records = list(reader)
    except FileNotFoundError as error:
        raise StaticRinComparisonError(
            f"missing Stage 21.B centrality artifact: {path}"
        ) from error
    except (OSError, UnicodeError, csv.Error) as error:
        raise StaticRinComparisonError(
            f"Stage 21.B centrality artifact could not be read: {path}"
        ) from error
    if not records:
        raise StaticRinComparisonError(
            f"Stage 21.B centrality artifact contains no rows: {path}"
        )

    condition: str | None = None
    by_residue_index: dict[int, _CentralityRow] = {}
    identities: set[_NodeIdentity] = set()
    for row_number, record in enumerate(records, start=2):
        row_condition = _required_text(
            record["condition"], f"row {row_number} condition"
        )
        if condition is None:
            condition = row_condition
        elif row_condition != condition:
            raise StaticRinComparisonError(
                f"centrality condition is inconsistent at row {row_number}: {path}"
            )
        residue_index = _required_int(
            record["residue_index"], f"row {row_number} residue_index"
        )
        node_id = _required_text(record["node_id"], f"row {row_number} node_id")
        if node_id != f"{row_condition}:{residue_index}":
            raise StaticRinComparisonError(
                f"centrality node_id is not the accepted format at row {row_number}"
            )
        identity = _NodeIdentity(
            residue_index=residue_index,
            resid=_required_text(record["resid"], f"row {row_number} resid"),
            resname=_required_text(
                record["resname"], f"row {row_number} resname"
            ),
            segment_id=record["segment_id"] or None,
        )
        if residue_index in by_residue_index or identity in identities:
            raise StaticRinComparisonError(
                f"duplicate centrality node identity at row {row_number}: {path}"
            )
        metrics = {
            metric: _optional_metric(
                record[metric],
                f"row {row_number} {metric}",
                integer=metric in {"degree", "kcore"},
            )
            for metric in STATIC_RIN_COMPARISON_METRICS
        }
        by_residue_index[residue_index] = _CentralityRow(
            condition=row_condition,
            node_id=node_id,
            identity=identity,
            metrics=metrics,
        )
        identities.add(identity)
    assert condition is not None
    return _CentralityArtifact(
        condition=condition,
        source_name=path.name,
        by_residue_index=by_residue_index,
    )


def _required_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise StaticRinComparisonError(f"{label} must be a non-empty string")
    return value.strip()


def _required_int(value: str | None, label: str) -> int:
    try:
        if value is None or value.strip() != str(int(value)):
            raise ValueError
        return int(value)
    except ValueError as error:
        raise StaticRinComparisonError(f"{label} must be an integer") from error


def _optional_metric(
    value: str | None,
    label: str,
    *,
    integer: bool,
) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except ValueError as error:
        raise StaticRinComparisonError(f"{label} must be numeric or empty") from error
    if not math.isfinite(numeric):
        raise StaticRinComparisonError(f"{label} must be finite or empty")
    if integer and not numeric.is_integer():
        raise StaticRinComparisonError(f"{label} must be an integer or empty")
    return numeric


def _write_csv(
    path: Path,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(
                csv_file,
                fieldnames=columns,
                lineterminator="\n",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(value) for key, value in row.items()})
        temporary_path.replace(path)
    except (OSError, csv.Error) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise StaticRinComparisonError(
            f"static RIN comparison artifact could not be written: {path}"
        ) from error


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".15g")
    return value


__all__ = [
    "COMPARISON_STATUS_COMPUTED",
    "COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT",
    "COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA",
    "COMPARISON_STATUS_SKIPPED_MISSING_METRIC",
    "COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE",
    "COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_A",
    "COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_B",
    "COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE",
    "STATIC_RIN_COMPARISON_COLUMNS",
    "STATIC_RIN_COMPARISON_METHODS",
    "STATIC_RIN_COMPARISON_METRICS",
    "STATIC_RIN_DEFERRED_COMPARISON_SCOPES",
    "STATIC_RIN_STATS_COLUMNS",
    "StaticRinComparison",
    "StaticRinComparisonArtifacts",
    "StaticRinComparisonError",
    "StaticRinComparisonRow",
    "StaticRinStatsRow",
    "compare_static_rin_metrics_from_artifacts",
    "write_static_rin_comparison_artifacts",
]
