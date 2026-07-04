import csv
import math
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    COMPARISON_STATUS_COMPUTED,
    COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT,
    COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA,
    COMPARISON_STATUS_SKIPPED_MISSING_METRIC,
    COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE,
    COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_A,
    COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_B,
    COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE,
    STATIC_RIN_COMPARISON_COLUMNS,
    STATIC_RIN_DEFERRED_COMPARISON_SCOPES,
    STATIC_RIN_METRICS_COLUMNS,
    STATIC_RIN_STATS_COLUMNS,
    StaticRinComparisonError,
    compare_static_rin_metrics_from_artifacts,
    write_static_rin_comparison_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "analysis" / "static_rin_comparison.py"
)


def _centrality_row(
    condition: str,
    residue_index: int,
    *,
    resid: str | None = None,
    resname: str = "ALA",
    segment_id: str = "A",
    **metrics: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "condition": condition,
        "node_id": f"{condition}:{residue_index}",
        "residue_index": residue_index,
        "resid": resid or str(residue_index * 10),
        "resname": resname,
        "segment_id": segment_id,
        "degree": residue_index,
        "strength": residue_index / 10,
        "betweenness": residue_index / 100,
        "closeness": residue_index / 20,
        "eigenvector": residue_index / 30,
        "pagerank": residue_index / 40,
        "kcore": 1,
    }
    row.update(metrics)
    return row


def _write_centrality(
    path: Path,
    rows: list[dict[str, object]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=STATIC_RIN_METRICS_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _stats_row(result: object, metric: str, method: str):
    return next(
        row
        for row in result.stats_rows
        if row.scope == "node_metrics"
        and row.metric == metric
        and row.method == method
    )


def test_matches_stable_identity_not_row_order_or_condition_node_id(
    tmp_path: Path,
) -> None:
    alpha = _write_centrality(
        tmp_path / "alpha" / "centrality_alpha.csv",
        [
            _centrality_row("alpha", 3, degree=3),
            _centrality_row("alpha", 1, degree=1),
            _centrality_row("alpha", 2, degree=2),
        ],
    )
    zeta = _write_centrality(
        tmp_path / "zeta" / "centrality_zeta.csv",
        [
            _centrality_row("zeta", 2, degree=4),
            _centrality_row("zeta", 3, degree=7),
            _centrality_row("zeta", 1, degree=2),
        ],
    )

    result = compare_static_rin_metrics_from_artifacts((zeta, alpha))
    reverse_input = compare_static_rin_metrics_from_artifacts((alpha, zeta))
    degree_rows = [
        row for row in result.comparison_rows if row.metric == "degree"
    ]

    assert result == reverse_input
    assert result.conditions == ("alpha", "zeta")
    assert [row.residue_index for row in degree_rows] == [1, 2, 3]
    assert [row.node_id_a for row in degree_rows] == [
        "alpha:1",
        "alpha:2",
        "alpha:3",
    ]
    assert [row.node_id_b for row in degree_rows] == [
        "zeta:1",
        "zeta:2",
        "zeta:3",
    ]
    assert [row.delta for row in degree_rows] == [1.0, 2.0, 4.0]
    assert {row.status for row in degree_rows} == {COMPARISON_STATUS_COMPUTED}

    summary = _stats_row(result, "degree", "paired_delta_summary")
    effect = _stats_row(result, "degree", "cohens_dz")
    assert summary.statistic == pytest.approx(7.0 / 3.0)
    assert summary.matched_count == 3
    assert effect.effect_size == pytest.approx(math.sqrt(7.0 / 3.0))
    assert effect.p_value is None
    assert effect.p_adjusted is None
    assert effect.correction == "none"


def test_writes_deterministic_root_artifacts_with_fixed_columns(
    tmp_path: Path,
) -> None:
    condition_b = _write_centrality(
        tmp_path / "inputs" / "centrality_b.csv",
        [_centrality_row("b", 1), _centrality_row("b", 2)],
    )
    condition_a = _write_centrality(
        tmp_path / "inputs" / "centrality_a.csv",
        [_centrality_row("a", 2), _centrality_row("a", 1)],
    )
    result = compare_static_rin_metrics_from_artifacts(
        (condition_b, condition_a)
    )

    artifacts = write_static_rin_comparison_artifacts(result, tmp_path / "output")
    first_comparison = artifacts.comparison_csv.read_bytes()
    first_stats = artifacts.stats_csv.read_bytes()
    write_static_rin_comparison_artifacts(result, tmp_path / "output")

    assert artifacts.comparison_csv == tmp_path / "output" / "comparison.csv"
    assert artifacts.stats_csv == tmp_path / "output" / "stats.csv"
    assert artifacts.comparison_csv.read_bytes() == first_comparison
    assert artifacts.stats_csv.read_bytes() == first_stats
    with artifacts.comparison_csv.open(encoding="utf-8", newline="") as csv_file:
        comparison_reader = csv.DictReader(csv_file)
        comparison_rows = list(comparison_reader)
    with artifacts.stats_csv.open(encoding="utf-8", newline="") as csv_file:
        stats_reader = csv.DictReader(csv_file)
        stats_rows = list(stats_reader)
    assert comparison_reader.fieldnames == list(STATIC_RIN_COMPARISON_COLUMNS)
    assert stats_reader.fieldnames == list(STATIC_RIN_STATS_COLUMNS)
    assert comparison_rows[0]["condition_a"] == "a"
    assert comparison_rows[0]["condition_b"] == "b"
    assert stats_rows[0]["correction"] == "none"
    assert stats_rows[0]["p_value"] == ""
    assert stats_rows[0]["p_adjusted"] == ""


def test_missing_metrics_and_unmatched_nodes_are_counted_without_zero_fill(
    tmp_path: Path,
) -> None:
    condition_a = _write_centrality(
        tmp_path / "centrality_a.csv",
        [
            _centrality_row("a", 1, strength=""),
            _centrality_row("a", 2, strength=0.2),
            _centrality_row("a", 3, strength=0.3),
        ],
    )
    condition_b = _write_centrality(
        tmp_path / "centrality_b.csv",
        [
            _centrality_row("b", 4, strength=0.4),
            _centrality_row("b", 2, strength=0.5),
            _centrality_row("b", 1, strength=0.1),
        ],
    )

    result = compare_static_rin_metrics_from_artifacts(
        (condition_a, condition_b)
    )
    strength_rows = [
        row for row in result.comparison_rows if row.metric == "strength"
    ]

    assert [row.residue_index for row in strength_rows] == [1, 2, 3, 4]
    assert strength_rows[0].status == COMPARISON_STATUS_SKIPPED_MISSING_METRIC
    assert strength_rows[0].value_a is None
    assert strength_rows[0].value_b == pytest.approx(0.1)
    assert strength_rows[0].delta is None
    assert strength_rows[2].status == (
        COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_B
    )
    assert strength_rows[3].status == (
        COMPARISON_STATUS_SKIPPED_UNMATCHED_CONDITION_A
    )
    assert strength_rows[2].delta is None
    assert strength_rows[3].delta is None

    summary = _stats_row(result, "strength", "paired_delta_summary")
    assert summary.matched_count == 2
    assert summary.unmatched_condition_a_count == 1
    assert summary.unmatched_condition_b_count == 1
    assert summary.missing_metric_count == 1
    assert summary.n_a == 1
    assert summary.n_b == 2
    assert summary.statistic == pytest.approx(0.3)


def test_identity_conflict_skips_all_statistics_for_pair(tmp_path: Path) -> None:
    condition_a = _write_centrality(
        tmp_path / "centrality_a.csv",
        [_centrality_row("a", 1, resname="ALA"), _centrality_row("a", 2)],
    )
    condition_b = _write_centrality(
        tmp_path / "centrality_b.csv",
        [_centrality_row("b", 1, resname="GLY"), _centrality_row("b", 2)],
    )

    result = compare_static_rin_metrics_from_artifacts(
        (condition_a, condition_b)
    )
    conflict_rows = [
        row for row in result.comparison_rows if row.residue_index == 1
    ]

    assert {row.status for row in conflict_rows} == {
        COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT
    }
    assert all(row.delta is None for row in conflict_rows)
    assert all(
        row.status == COMPARISON_STATUS_SKIPPED_IDENTITY_CONFLICT
        for row in result.stats_rows
        if row.scope == "node_metrics"
    )
    summary = _stats_row(result, "degree", "paired_delta_summary")
    assert summary.statistic is None
    assert summary.matched_count == 1
    assert summary.unmatched_condition_a_count == 1
    assert summary.unmatched_condition_b_count == 1


def test_insufficient_and_constant_differences_have_explicit_statuses(
    tmp_path: Path,
) -> None:
    one_a = _write_centrality(
        tmp_path / "one_a.csv", [_centrality_row("one_a", 1, degree=1)]
    )
    one_b = _write_centrality(
        tmp_path / "one_b.csv", [_centrality_row("one_b", 1, degree=2)]
    )
    insufficient = compare_static_rin_metrics_from_artifacts((one_a, one_b))

    assert _stats_row(
        insufficient, "degree", "paired_delta_summary"
    ).status == COMPARISON_STATUS_COMPUTED
    assert _stats_row(
        insufficient, "degree", "cohens_dz"
    ).status == COMPARISON_STATUS_SKIPPED_INSUFFICIENT_DATA

    constant_a = _write_centrality(
        tmp_path / "constant_a.csv",
        [
            _centrality_row("constant_a", 1, degree=1),
            _centrality_row("constant_a", 2, degree=2),
        ],
    )
    constant_b = _write_centrality(
        tmp_path / "constant_b.csv",
        [
            _centrality_row("constant_b", 1, degree=2),
            _centrality_row("constant_b", 2, degree=3),
        ],
    )
    constant = compare_static_rin_metrics_from_artifacts(
        (constant_a, constant_b)
    )

    assert _stats_row(
        constant, "degree", "paired_delta_summary"
    ).statistic == pytest.approx(1.0)
    effect = _stats_row(constant, "degree", "cohens_dz")
    assert effect.status == COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE
    assert effect.effect_size is None


def test_all_condition_pairs_and_unsupported_scopes_are_deterministic(
    tmp_path: Path,
) -> None:
    paths = tuple(
        _write_centrality(
            tmp_path / f"centrality_{condition}.csv",
            [_centrality_row(condition, 1)],
        )
        for condition in ("c", "a", "b")
    )

    result = compare_static_rin_metrics_from_artifacts(paths)
    pairs = tuple(
        dict.fromkeys(
            (row.condition_a, row.condition_b) for row in result.comparison_rows
        )
    )
    unsupported = [
        row
        for row in result.stats_rows
        if row.status == COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE
    ]

    assert result.conditions == ("a", "b", "c")
    assert pairs == (("a", "b"), ("a", "c"), ("b", "c"))
    assert len(unsupported) == 3 * len(STATIC_RIN_DEFERRED_COMPARISON_SCOPES)
    assert {row.scope for row in unsupported} == set(
        STATIC_RIN_DEFERRED_COMPARISON_SCOPES
    )
    assert all(row.p_value is None for row in unsupported)
    assert all(row.correction == "none" for row in unsupported)


def test_rejects_nonaccepted_or_ambiguous_centrality_artifacts(
    tmp_path: Path,
) -> None:
    valid = _write_centrality(
        tmp_path / "valid.csv", [_centrality_row("valid", 1)]
    )
    duplicate = _write_centrality(
        tmp_path / "duplicate.csv",
        [_centrality_row("duplicate", 1), _centrality_row("duplicate", 1)],
    )
    wrong_columns = tmp_path / "wrong.csv"
    wrong_columns.write_text("condition,node_id\na,a:1\n", encoding="utf-8")

    with pytest.raises(StaticRinComparisonError, match="duplicate"):
        compare_static_rin_metrics_from_artifacts((valid, duplicate))
    with pytest.raises(StaticRinComparisonError, match="columns do not match"):
        compare_static_rin_metrics_from_artifacts((valid, wrong_columns))
    with pytest.raises(StaticRinComparisonError, match="at least two"):
        compare_static_rin_metrics_from_artifacts((valid,))


def test_public_layer_is_dependency_free_and_wania_agnostic() -> None:
    assert (
        mania.analysis.compare_static_rin_metrics_from_artifacts
        is compare_static_rin_metrics_from_artifacts
    )
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "scipy",
        "mania.wania",
        "wania_graph_payload",
        "temporal_rin",
        "conformation",
    ):
        assert forbidden not in source
