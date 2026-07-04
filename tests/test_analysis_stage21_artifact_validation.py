import csv
import json
from itertools import combinations
from pathlib import Path

import pytest

from mania.analysis import (
    COMPARISON_STATUS_COMPUTED,
    COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE,
    COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE,
    STATIC_RIN_COMMUNITIES_COLUMNS,
    STATIC_RIN_COMMUNITY_ALGORITHM,
    STATIC_RIN_COMPARISON_COLUMNS,
    STATIC_RIN_COMPARISON_METHODS,
    STATIC_RIN_COMPARISON_METRICS,
    STATIC_RIN_DEFERRED_COMPARISON_SCOPES,
    STATIC_RIN_GRAPH_SCHEMA_VERSION,
    STATIC_RIN_METRICS_COLUMNS,
    STATIC_RIN_REGION_ENRICHMENT_COLUMNS,
    STATIC_RIN_REGION_ENRICHMENT_METHOD,
    STATIC_RIN_STATS_COLUMNS,
    STATUS_COMPUTED,
    StaticRinEdge,
    StaticRinGraph,
    StaticRinInteraction,
    StaticRinNode,
    compare_static_rin_metrics_from_artifacts,
    compute_static_rin_communities,
    compute_static_rin_metrics,
    compute_static_rin_region_enrichment,
    write_static_rin_communities_csv,
    write_static_rin_comparison_artifacts,
    write_static_rin_graph_json,
    write_static_rin_metrics_csv,
    write_static_rin_region_enrichment_csv,
)
from mania.constants import EDGE_TYPE_PRIORITY

CONDITIONS = ("normal", "tumor")
REGIONS = ("ECD", "ECD", "ECD", "TM", "ECD", "TM", "TM", "TM")


def _node(condition: str, residue_index: int) -> StaticRinNode:
    return StaticRinNode(
        id=f"{condition}:{residue_index}",
        condition=condition,
        residue_index=residue_index,
        resid=str(residue_index * 10),
        resname="GLY" if residue_index == 2 else "ALA",
        segment_id="A",
        region=REGIONS[residue_index - 1],
        x_ca=None,
        y_ca=None,
        z_ca=None,
        tm_relative_z=None,
        rmsf_A=None,
        sasa_A2=None,
        ss=None,
    )


def _edge(
    condition: str,
    source_index: int,
    target_index: int,
    weight: float | None,
) -> StaticRinEdge:
    source = _node(condition, source_index)
    target = _node(condition, target_index)
    interaction = StaticRinInteraction(
        edge_type="vdw",
        contact_frame_count=None,
        sampled_frame_count=None,
        contact_freq=weight,
        mean_dist_A=None,
        std_dist_A=None,
    )
    return StaticRinEdge(
        id=f"{condition}:{source_index}--{target_index}:vdw",
        condition=condition,
        source=source.id,
        target=target.id,
        residue_index_i=source_index,
        resid_i=source.resid,
        resname_i=source.resname,
        segment_id_i=source.segment_id,
        residue_index_j=target_index,
        resid_j=target.resid,
        resname_j=target.resname,
        segment_id_j=target.segment_id,
        primary_edge_type="vdw",
        all_edge_types=("vdw",),
        interactions=(interaction,),
    )


def _graph(condition: str) -> StaticRinGraph:
    edge_pairs = (
        *combinations(range(1, 5), 2),
        *combinations(range(5, 9), 2),
    )
    edges = tuple(
        _edge(
            condition,
            source,
            target,
            (
                None
                if (source, target) == (1, 2)
                else 0.2
                if condition == "normal"
                else 0.1 + (source + target) / 100
            ),
        )
        for source, target in edge_pairs
    )
    return StaticRinGraph(
        condition=condition,
        nodes=tuple(_node(condition, index) for index in range(1, 9)),
        edges=edges,
        source_artifacts={
            "residue_table": f"residue_table_{condition}.csv",
            "protein_contact_edges": (
                f"protein_contact_edges_undirected_{condition}.csv"
            ),
        },
    )


def _write_stage21_bundle(root: Path) -> tuple[Path, dict[str, bytes]]:
    analysis_root = root / "analysis"
    centrality_paths: list[Path] = []
    for condition in reversed(CONDITIONS):
        condition_root = analysis_root / condition
        graph = _graph(condition)
        graph_path = write_static_rin_graph_json(
            graph, condition_root / "graph.json"
        )
        metrics = compute_static_rin_metrics(graph)
        centrality_path = write_static_rin_metrics_csv(metrics, condition_root)
        communities = compute_static_rin_communities(graph)
        communities_path = write_static_rin_communities_csv(
            communities, condition_root
        )
        enrichment = compute_static_rin_region_enrichment(graph, communities)
        enrichment_path = write_static_rin_region_enrichment_csv(
            enrichment, condition_root
        )
        assert all(
            path.is_file()
            for path in (
                graph_path,
                centrality_path,
                communities_path,
                enrichment_path,
            )
        )
        centrality_paths.append(centrality_path)

    comparison = compare_static_rin_metrics_from_artifacts(centrality_paths)
    write_static_rin_comparison_artifacts(comparison, analysis_root)
    files = {
        path.relative_to(analysis_root).as_posix(): path.read_bytes()
        for path in sorted(analysis_root.rglob("*"))
        if path.is_file()
    }
    return analysis_root, files


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def _identity(row: dict[str, object] | dict[str, str]) -> tuple[object, ...]:
    return (
        int(row["residue_index"]),
        row["resid"],
        row["resname"],
        row["segment_id"] or None,
    )


def test_stage21_artifacts_are_schema_valid_consistent_and_deterministic(
    tmp_path: Path,
) -> None:
    first_root, first_bytes = _write_stage21_bundle(tmp_path / "first")
    _, second_bytes = _write_stage21_bundle(tmp_path / "second")

    assert first_bytes == second_bytes
    assert tuple(first_bytes) == (
        "comparison.csv",
        "normal/centrality_normal.csv",
        "normal/communities_normal.csv",
        "normal/graph.json",
        "normal/region_enrichment_normal.csv",
        "stats.csv",
        "tumor/centrality_tumor.csv",
        "tumor/communities_tumor.csv",
        "tumor/graph.json",
        "tumor/region_enrichment_tumor.csv",
    )

    centrality_by_condition: dict[str, list[dict[str, str]]] = {}
    for condition in CONDITIONS:
        condition_root = first_root / condition
        graph = json.loads(
            (condition_root / "graph.json").read_text(encoding="utf-8")
        )
        centrality_header, centrality_rows = _read_csv(
            condition_root / f"centrality_{condition}.csv"
        )
        communities_header, community_rows = _read_csv(
            condition_root / f"communities_{condition}.csv"
        )
        enrichment_header, enrichment_rows = _read_csv(
            condition_root / f"region_enrichment_{condition}.csv"
        )
        centrality_by_condition[condition] = centrality_rows

        assert graph["schema_version"] == STATIC_RIN_GRAPH_SCHEMA_VERSION
        assert graph["condition"] == condition
        assert graph["directed"] is False
        assert graph["n_nodes"] == len(graph["nodes"]) == 8
        assert graph["n_edges"] == len(graph["edges"]) == 12
        assert graph["edge_priority"] == list(EDGE_TYPE_PRIORITY)
        assert [node["residue_index"] for node in graph["nodes"]] == list(
            range(1, 9)
        )
        assert [node["id"] for node in graph["nodes"]] == [
            f"{condition}:{index}" for index in range(1, 9)
        ]
        graph_node_ids = {node["id"] for node in graph["nodes"]}
        graph_identities = {_identity(node) for node in graph["nodes"]}
        assert all(
            edge["source"] in graph_node_ids and edge["target"] in graph_node_ids
            for edge in graph["edges"]
        )
        assert all(edge["primary_edge_type"] == "vdw" for edge in graph["edges"])
        assert all(edge["all_edge_types"] == ["vdw"] for edge in graph["edges"])
        assert all(edge["weight"] == edge["contact_freq"] for edge in graph["edges"])
        missing_weight = next(
            edge for edge in graph["edges"] if edge["residue_index_i"] == 1
            and edge["residue_index_j"] == 2
        )
        assert missing_weight["contact_freq"] is None
        assert missing_weight["weight"] is None
        source_artifacts = graph["metadata"]["source_artifacts"]
        assert all(Path(value).name == value for value in source_artifacts.values())

        assert centrality_header == STATIC_RIN_METRICS_COLUMNS
        assert communities_header == STATIC_RIN_COMMUNITIES_COLUMNS
        assert enrichment_header == STATIC_RIN_REGION_ENRICHMENT_COLUMNS
        assert {_identity(row) for row in centrality_rows} == graph_identities
        assert {_identity(row) for row in community_rows} == graph_identities
        assert [int(row["residue_index"]) for row in centrality_rows] == list(
            range(1, 9)
        )
        assert [int(row["residue_index"]) for row in community_rows] == list(
            range(1, 9)
        )
        assert {row["node_id"] for row in centrality_rows} == graph_node_ids
        assert {row["node_id"] for row in community_rows} == graph_node_ids
        assert {row["condition"] for row in centrality_rows} == {condition}
        assert {row["condition"] for row in community_rows} == {condition}
        expected_strengths = {index: 0.0 for index in range(1, 9)}
        for edge in graph["edges"]:
            if edge["weight"] is not None:
                expected_strengths[edge["residue_index_i"]] += edge["weight"]
                expected_strengths[edge["residue_index_j"]] += edge["weight"]
        assert {
            int(row["residue_index"]): float(row["strength"])
            for row in centrality_rows
        } == pytest.approx(expected_strengths)

        assert {row["algorithm"] for row in community_rows} == {
            STATIC_RIN_COMMUNITY_ALGORITHM
        }
        assert all("louvain" not in row["algorithm"] for row in community_rows)
        community_ids = {int(row["community_id"]) for row in community_rows}
        assert community_ids == {1, 2}
        for community_id in community_ids:
            members = [
                row
                for row in community_rows
                if int(row["community_id"]) == community_id
            ]
            assert {int(row["community_size"]) for row in members} == {
                len(members)
            }
            assert {int(row["n_communities"]) for row in members} == {2}

        graph_regions = {
            node["region"] for node in graph["nodes"] if node["region"]
        }
        assert graph_regions == {"ECD", "TM"}
        assert {row["region"] for row in enrichment_rows} <= graph_regions
        assert "other" not in {row["region"] for row in enrichment_rows}
        assert {row["status"] for row in enrichment_rows} == {STATUS_COMPUTED}
        assert {row["method"] for row in enrichment_rows} == {
            STATIC_RIN_REGION_ENRICHMENT_METHOD
        }
        assert {
            int(row["community_id"]) for row in enrichment_rows
        } <= community_ids
        assert all(0.0 <= float(row["p_value"]) <= 1.0 for row in enrichment_rows)
        assert "p_adjusted" not in enrichment_header
        for row in enrichment_rows:
            counts = tuple(
                int(row[column])
                for column in (
                    "region_count_in_community",
                    "non_region_count_in_community",
                    "region_count_outside_community",
                    "non_region_count_outside_community",
                )
            )
            assert sum(counts) == int(row["labeled_node_count"])
            assert counts[0] + counts[1] == int(row["community_size"])
            assert counts[0] + counts[2] == int(row["total_region_count"])
        assert [
            (int(row["community_id"]), row["region"])
            for row in enrichment_rows
        ] == [(1, "ECD"), (1, "TM"), (2, "ECD"), (2, "TM")]

    comparison_header, comparison_rows = _read_csv(first_root / "comparison.csv")
    stats_header, stats_rows = _read_csv(first_root / "stats.csv")
    assert comparison_header == STATIC_RIN_COMPARISON_COLUMNS
    assert stats_header == STATIC_RIN_STATS_COLUMNS
    assert {
        (row["condition_a"], row["condition_b"]) for row in comparison_rows
    } == {CONDITIONS}
    assert {row["scope"] for row in comparison_rows} == {"node_metrics"}
    assert {row["metric"] for row in comparison_rows} == set(
        STATIC_RIN_COMPARISON_METRICS
    )
    assert {row["status"] for row in comparison_rows} == {
        COMPARISON_STATUS_COMPUTED
    }
    centrality_indexes = {
        condition: {int(row["residue_index"]): row for row in rows}
        for condition, rows in centrality_by_condition.items()
    }
    for row in comparison_rows:
        residue_index = int(row["residue_index"])
        row_a = centrality_indexes[row["condition_a"]][residue_index]
        row_b = centrality_indexes[row["condition_b"]][residue_index]
        assert _identity(row) == _identity(row_a) == _identity(row_b)
        assert json.loads(row["entity_key"]) == list(_identity(row))
        assert row["node_id_a"] == row_a["node_id"]
        assert row["node_id_b"] == row_b["node_id"]
        assert row["source_artifact_a"] == "centrality_normal.csv"
        assert row["source_artifact_b"] == "centrality_tumor.csv"
        assert float(row["value_a"]) == pytest.approx(float(row_a[row["metric"]]))
        assert float(row["value_b"]) == pytest.approx(float(row_b[row["metric"]]))
        assert float(row["delta"]) == pytest.approx(
            float(row["value_b"]) - float(row["value_a"])
        )
    assert [
        (int(row["residue_index"]), row["metric"]) for row in comparison_rows
    ] == [
        (residue_index, metric)
        for residue_index in range(1, 9)
        for metric in STATIC_RIN_COMPARISON_METRICS
    ]

    node_stats = [row for row in stats_rows if row["scope"] == "node_metrics"]
    unsupported = [
        row
        for row in stats_rows
        if row["status"] == COMPARISON_STATUS_SKIPPED_UNSUPPORTED_SCOPE
    ]
    assert [
        (row["metric"], row["method"]) for row in node_stats
    ] == [
        (metric, method)
        for metric in STATIC_RIN_COMPARISON_METRICS
        for method in STATIC_RIN_COMPARISON_METHODS
    ]
    assert all(row["matched_count"] == "8" for row in node_stats)
    assert all(row["unmatched_condition_a_count"] == "0" for row in node_stats)
    assert all(row["unmatched_condition_b_count"] == "0" for row in node_stats)
    assert all(row["missing_metric_count"] == "0" for row in node_stats)
    assert all(row["p_value"] == "" for row in stats_rows)
    assert all(row["p_adjusted"] == "" for row in stats_rows)
    assert all(row["correction"] == "none" for row in stats_rows)
    assert {row["scope"] for row in unsupported} == set(
        STATIC_RIN_DEFERRED_COMPARISON_SCOPES
    )
    assert all(row["method"] == "not_implemented" for row in unsupported)
    assert all(row["statistic"] == row["effect_size"] == "" for row in unsupported)
    constant_effect_rows = [
        row
        for row in node_stats
        if row["method"] == "cohens_dz" and row["metric"] != "strength"
    ]
    assert all(
        row["status"] == COMPARISON_STATUS_SKIPPED_UNDEFINED_VARIANCE
        for row in constant_effect_rows
    )
    assert all(
        row["statistic"] == row["effect_size"] == ""
        and row["ci_low"] == row["ci_high"] == ""
        for row in constant_effect_rows
    )
    strength_effect = next(
        row
        for row in node_stats
        if row["metric"] == "strength" and row["method"] == "cohens_dz"
    )
    assert strength_effect["status"] == COMPARISON_STATUS_COMPUTED
    assert strength_effect["effect_size"] != ""
    strength_summary = next(
        row
        for row in node_stats
        if row["metric"] == "strength"
        and row["method"] == "paired_delta_summary"
    )
    strength_deltas = [
        float(row["delta"])
        for row in comparison_rows
        if row["metric"] == "strength"
    ]
    assert float(strength_summary["statistic"]) == pytest.approx(
        sum(strength_deltas) / len(strength_deltas)
    )
    for metric in ("betweenness", "closeness"):
        normal_values = [
            row[metric] for row in centrality_by_condition["normal"]
        ]
        tumor_values = [row[metric] for row in centrality_by_condition["tumor"]]
        assert normal_values == tumor_values
    comparison_ids = {row["comparison_id"] for row in comparison_rows}
    assert comparison_ids == {"node_metrics:normal__tumor"}
    assert {row["comparison_id"] for row in stats_rows} == comparison_ids
