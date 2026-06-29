import json
from copy import deepcopy
from pathlib import Path

import pytest

from mania.analysis import (
    AnalysisGraphMetricsOptions,
    compute_analysis_graph_metrics_from_graph_json,
)


def graph_payload(
    *,
    condition: str = "normal",
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "condition": condition,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "directed": False,
        "schema_version": "0.1",
        "nodes": nodes,
        "edges": edges,
    }


def test_path_graph_centrality_metrics_are_deterministic() -> None:
    payload = graph_payload(
        nodes=[
            {"id": "A", "condition": "normal"},
            {"id": "B", "condition": "normal"},
            {"id": "C", "condition": "normal"},
        ],
        edges=[
            {
                "source": "A",
                "target": "B",
                "condition": "normal",
                "contact_freq": 0.25,
            },
            {
                "source": "B",
                "target": "C",
                "condition": "normal",
                "contact_freq": "0.75",
            },
        ],
    )

    result = compute_analysis_graph_metrics_from_graph_json(payload)
    rows = {str(row["node_id"]): row for row in result.metrics_by_condition["normal"]}

    assert result.passed is True
    assert [rows[node]["degree"] for node in ("A", "B", "C")] == [1, 2, 1]
    assert rows["A"]["strength"] == pytest.approx(0.25)
    assert rows["B"]["strength"] == pytest.approx(1.0)
    assert rows["C"]["strength"] == pytest.approx(0.75)
    assert rows["B"]["betweenness"] == pytest.approx(1.0)
    assert rows["A"]["betweenness"] == pytest.approx(0.0)
    assert rows["B"]["closeness"] == pytest.approx(1.0)
    assert rows["A"]["closeness"] == pytest.approx(2.0 / 3.0)
    assert all(isinstance(row["eigenvector"], float) for row in rows.values())
    assert sum(float(row["pagerank"]) for row in rows.values()) == pytest.approx(1.0)
    assert {row["kcore"] for row in rows.values()} == {1}
    assert result.report["metrics"] == [
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
    ]
    json.dumps(result.to_dict(), allow_nan=False)


def test_missing_and_non_numeric_weights_use_zero_without_mutating_graph() -> None:
    payload = graph_payload(
        nodes=[
            {"id": "A", "condition": "normal"},
            {"id": "B", "condition": "normal"},
            {"id": "C", "condition": "normal"},
        ],
        edges=[
            {
                "source": "A",
                "target": "B",
                "condition": "normal",
                "edge_type": "backbone",
            },
            {
                "source": "B",
                "target": "C",
                "condition": "normal",
                "contact_freq": "not-a-number",
            },
        ],
    )
    original = deepcopy(payload)

    result = compute_analysis_graph_metrics_from_graph_json(payload)
    rows = {str(row["node_id"]): row for row in result.metrics_by_condition["normal"]}

    assert result.passed is True
    assert {row["strength"] for row in rows.values()} == {0.0}
    assert "analysis_weight_field_missing" in {
        issue.kind for issue in result.issues
    }
    assert payload == original
    assert "contact_freq" not in payload["edges"][0]  # type: ignore[index]


def test_custom_weight_field_controls_weighted_strength() -> None:
    payload = graph_payload(
        nodes=[
            {"id": "A", "condition": "normal"},
            {"id": "B", "condition": "normal"},
            {"id": "C", "condition": "normal"},
        ],
        edges=[
            {"source": "A", "target": "B", "score": 1.5},
            {"source": "A", "target": "C", "score": 2},
        ],
    )

    result = compute_analysis_graph_metrics_from_graph_json(
        payload,
        options=AnalysisGraphMetricsOptions(weight_field="score"),
    )
    rows = {str(row["node_id"]): row for row in result.metrics_by_condition["normal"]}

    assert rows["A"]["strength"] == pytest.approx(3.5)
    assert rows["B"]["strength"] == pytest.approx(1.5)
    assert rows["C"]["strength"] == pytest.approx(2.0)


def test_community_detection_finds_two_obvious_clusters() -> None:
    node_ids = ("A", "B", "C", "D", "E", "F")
    edge_pairs = (
        ("A", "B"),
        ("A", "C"),
        ("B", "C"),
        ("D", "E"),
        ("D", "F"),
        ("E", "F"),
        ("C", "D"),
    )
    payload = graph_payload(
        nodes=[{"id": node_id, "condition": "normal"} for node_id in node_ids],
        edges=[
            {
                "source": source,
                "target": target,
                "condition": "normal",
                "contact_freq": 1.0,
            }
            for source, target in edge_pairs
        ],
    )

    result = compute_analysis_graph_metrics_from_graph_json(payload)
    rows = {str(row["node_id"]): row for row in result.metrics_by_condition["normal"]}
    summary = result.report["conditions_summary"]
    assert isinstance(summary, dict)

    assert rows["A"]["community"] == rows["B"]["community"] == rows["C"]["community"]
    assert rows["D"]["community"] == rows["E"]["community"] == rows["F"]["community"]
    assert rows["A"]["community"] != rows["D"]["community"]
    assert len(result.communities_by_condition["normal"]) == 6
    assert summary["normal"]["community_count"] == 2
    assert isinstance(summary["normal"]["modularity"], float)


def test_multi_condition_rows_preserve_node_features_and_coordinates(
    tmp_path: Path,
) -> None:
    feature_fields: dict[str, object] = {
        "resid": "10",
        "resname": "LYS",
        "chain_id": "A",
        "region": "ECD",
        "ss": "H",
        "rmsf_A": 1.25,
        "sasa_A2": 42.5,
        "x": 1.0,
        "y": 2.0,
        "z": 3.0,
        "x_ca": 1.0,
        "y_ca": 2.0,
        "z_ca": 3.0,
    }
    payload = graph_payload(
        nodes=[
            {"id": "normal-10", "condition": "normal", **feature_fields},
            {"id": "normal-11", "condition": "normal", "resid": "11"},
            {
                "id": "tumor-10",
                "condition": "tumor",
                **{**feature_fields, "x": 9.0, "x_ca": 9.0},
            },
            {"id": "tumor-11", "condition": "tumor", "resid": "11"},
        ],
        edges=[
            {
                "source": "normal-10",
                "target": "normal-11",
                "condition": "normal",
                "contact_freq": 0.5,
            },
            {
                "source": "tumor-10",
                "target": "tumor-11",
                "condition": "tumor",
                "contact_freq": 0.8,
            },
        ],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = compute_analysis_graph_metrics_from_graph_json(path)
    normal = result.metrics_by_condition["normal"][0]
    tumor = result.metrics_by_condition["tumor"][0]

    assert result.report["conditions"] == ["normal", "tumor"]
    for field_name, value in feature_fields.items():
        assert normal[field_name] == value
    assert normal["x_ca"] == 1.0
    assert tumor["x_ca"] == 9.0
    assert normal["node_id"] == "normal-10"
    assert tumor["node_id"] == "tumor-10"


def test_empty_graph_returns_deterministic_issue_and_json_safe_report() -> None:
    payload = graph_payload(nodes=[], edges=[])

    first = compute_analysis_graph_metrics_from_graph_json(payload)
    second = compute_analysis_graph_metrics_from_graph_json(payload)

    assert first.passed is False
    assert first.metrics_by_condition == {"normal": []}
    assert first.communities_by_condition == {"normal": []}
    assert [issue.kind for issue in first.issues] == ["analysis_graph_empty"]
    assert first.to_dict() == second.to_dict()
    json.dumps(first.report, allow_nan=False)


def test_community_computation_can_be_disabled() -> None:
    payload = graph_payload(
        nodes=[
            {"id": "A", "condition": "normal"},
            {"id": "B", "condition": "normal"},
        ],
        edges=[{"source": "A", "target": "B", "contact_freq": 1.0}],
    )

    result = compute_analysis_graph_metrics_from_graph_json(
        payload,
        options=AnalysisGraphMetricsOptions(compute_communities=False),
    )

    assert result.passed is True
    assert result.communities_by_condition["normal"] == []
    assert all(
        row["community"] is None
        for row in result.metrics_by_condition["normal"]
    )
    assert result.report["community_detection"] == {
        "algorithm": "disabled",
        "seed": 42,
    }
