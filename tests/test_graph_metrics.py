import csv
import json
from pathlib import Path

import pytest

from mania.analysis.contract_graph import (
    ContractGraph,
    load_contract_graph,
    load_contract_graph_from_condition_dir,
)
from mania.analysis.graph_metrics import (
    GraphMetricsError,
    GraphTopologyMetrics,
    compute_graph_topology_metrics,
    write_graph_topology_metrics,
)
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS

FIXTURE_ROOT = Path("tests/fixtures/expected_contract_subset_tiny")


def write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def node_row(resid: str, *, condition: str = "normal") -> dict[str, str]:
    row = {column: "" for column in NODE_COLUMNS}
    row.update(
        {
            "resid": resid,
            "resname": "ALA",
            "region": "TM1",
            "condition": condition,
        }
    )
    return row


def edge_row(
    source: str,
    target: str,
    *,
    edge_type: str = "contact",
    condition: str = "normal",
    contact_freq: str = "0.5",
    mean_dist_a: str = "7.25",
) -> dict[str, str]:
    row = {column: "" for column in EDGE_COLUMNS}
    row.update(
        {
            "resid_i": source,
            "resid_j": target,
            "edge_type": edge_type,
            "condition": condition,
            "contact_freq": contact_freq,
            "mean_dist_A": mean_dist_a,
        }
    )
    return row


def load_graph_from_rows(
    tmp_path: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    condition: str = "normal",
) -> ContractGraph:
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, nodes)
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, edges)
    return load_contract_graph(nodes_path, edges_path, condition=condition)


def test_normal_fixture_topology_metrics() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )
    expected_strength = float(graph.edges[0].row["contact_freq"])

    metrics = compute_graph_topology_metrics(graph)

    assert isinstance(metrics, GraphTopologyMetrics)
    assert metrics.condition == "normal"
    assert metrics.node_ids == ("1", "2")
    assert metrics.get("1").degree == 1
    assert metrics.get("2").degree == 1
    assert metrics.get("1").strength == expected_strength
    assert metrics.get("2").strength == expected_strength
    assert metrics.get("1").node_id == "1"


def test_tumor_fixture_topology_metrics_preserve_node_order() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )

    metrics = compute_graph_topology_metrics(graph)

    assert metrics.condition == "tumor"
    assert metrics.node_ids == ("1", "2")
    assert tuple(metric.node_id for metric in metrics.node_metrics) == ("1", "2")


def test_isolated_node_has_zero_degree_and_strength(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2"), node_row("3")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    metrics = compute_graph_topology_metrics(graph)

    assert metrics.get("3").degree == 0
    assert metrics.get("3").strength == 0.0


def test_duplicate_edge_rows_add_strength_but_not_degree(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[
            edge_row("1", "2", contact_freq="0.5"),
            edge_row("2", "1", contact_freq="0.7"),
        ],
    )

    metrics = compute_graph_topology_metrics(graph)

    assert metrics.get("1").degree == 1
    assert metrics.get("2").degree == 1
    assert metrics.get("1").strength == pytest.approx(1.2)
    assert metrics.get("2").strength == pytest.approx(1.2)


def test_same_pair_with_different_edge_type_contributes_to_strength(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[
            edge_row("1", "2", edge_type="contact", contact_freq="0.5"),
            edge_row("2", "1", edge_type="hydrogen_bond", contact_freq="0.7"),
        ],
    )

    metrics = compute_graph_topology_metrics(graph)

    assert metrics.get("1").degree == 1
    assert metrics.get("2").degree == 1
    assert metrics.get("1").strength == pytest.approx(1.2)
    assert metrics.get("2").strength == pytest.approx(1.2)


def test_self_loop_contributes_strength_once(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1")],
        edges=[edge_row("1", "1", contact_freq="0.5")],
    )

    metrics = compute_graph_topology_metrics(graph)

    assert metrics.get("1").strength == 0.5
    assert metrics.get("1").degree == graph.degree("1")


def test_custom_weight_column_is_used(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5", mean_dist_a="7.25")],
    )

    metrics = compute_graph_topology_metrics(graph, weight_column="mean_dist_A")

    assert metrics.get("1").strength == 7.25
    assert metrics.get("2").strength == 7.25


def test_missing_weight_column_fails(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphMetricsError, match="Missing weight column"):
        compute_graph_topology_metrics(graph, weight_column="missing_weight")


def test_empty_weight_value_fails(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="")],
    )

    with pytest.raises(GraphMetricsError, match="Empty weight value"):
        compute_graph_topology_metrics(graph)


def test_non_numeric_weight_fails(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="abc")],
    )

    with pytest.raises(GraphMetricsError, match="Invalid weight value"):
        compute_graph_topology_metrics(graph)


@pytest.mark.parametrize("contact_freq", ("nan", "inf", "-inf"))
def test_non_finite_weight_fails(tmp_path: Path, contact_freq: str) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq=contact_freq)],
    )

    with pytest.raises(GraphMetricsError, match="Non-finite weight value"):
        compute_graph_topology_metrics(graph)


def test_unknown_node_get_fails() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )
    metrics = compute_graph_topology_metrics(graph)

    with pytest.raises(GraphMetricsError, match="Unknown node ID"):
        metrics.get("999")


def test_to_dict_is_json_serializable() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )
    metrics = compute_graph_topology_metrics(graph)

    payload = metrics.to_dict()

    assert {"condition", "node_metrics"}.issubset(payload)
    assert json.loads(json.dumps(payload)) == {
        "condition": "normal",
        "node_metrics": [
            {"node_id": "1", "degree": 1, "strength": 0.75},
            {"node_id": "2", "degree": 1, "strength": 0.75},
        ],
    }


def test_write_graph_topology_metrics_creates_json_file(tmp_path: Path) -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )
    metrics = compute_graph_topology_metrics(graph)

    path = write_graph_topology_metrics(
        metrics,
        tmp_path / "metrics" / "graph_topology_metrics.json",
    )

    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["condition"] == metrics.condition
    assert loaded["node_metrics"]
    assert path.read_text(encoding="utf-8").endswith("\n")
