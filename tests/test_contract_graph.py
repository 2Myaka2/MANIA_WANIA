import csv
from pathlib import Path

import pytest

from mania.analysis.contract_graph import (
    ContractGraphError,
    load_contract_graph,
    load_contract_graph_from_condition_dir,
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
    edge_type: str = "protein_lipid",
    condition: str = "normal",
) -> dict[str, str]:
    row = {column: "" for column in EDGE_COLUMNS}
    row.update(
        {
            "resid_i": source,
            "resid_j": target,
            "edge_type": edge_type,
            "condition": condition,
        }
    )
    return row


def write_graph_csvs(
    tmp_path: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> tuple[Path, Path]:
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, nodes)
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, edges)
    return nodes_path, edges_path


def test_load_fixture_graph_preserves_order_and_builds_adjacency() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )

    assert graph.condition == "normal"
    assert graph.n_nodes == 2
    assert graph.n_edges == 1
    assert graph.node_ids == ("1", "2")
    assert graph.has_node("1")
    assert not graph.has_node("3")
    assert graph.neighbors("1") == frozenset({"2"})
    assert graph.neighbors("2") == frozenset({"1"})
    assert graph.degree("1") == 1
    assert graph.isolated_node_ids() == ()
    assert graph.nodes["1"].row["resname"] == "ALA"
    assert graph.edges[0].source == "1"
    assert graph.edges[0].target == "2"
    assert graph.edges[0].edge_type == "protein_lipid"
    assert graph.edges[0].row["all_edge_types"] == "protein_lipid"
    assert graph.edges[0].row["n_edge_types"] == "1"


def test_load_contract_graph_reads_explicit_paths() -> None:
    graph = load_contract_graph(
        FIXTURE_ROOT / "tumor" / "nodes.csv",
        FIXTURE_ROOT / "tumor" / "edges.csv",
        condition="tumor",
    )

    assert graph.condition == "tumor"
    assert graph.node_ids == ("1", "2")
    assert graph.edges[0].edge_type == "protein_glycan"


def test_duplicate_edge_rows_are_kept_but_neighbors_are_unique(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2"), edge_row("1", "2")],
    )

    graph = load_contract_graph(nodes_path, edges_path, condition="normal")

    assert graph.n_edges == 2
    assert graph.neighbors("1") == frozenset({"2"})
    assert graph.degree("1") == 1


def test_isolated_node_ids_preserve_node_order(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1"), node_row("2"), node_row("3")],
        edges=[edge_row("1", "2")],
    )

    graph = load_contract_graph(nodes_path, edges_path, condition="normal")

    assert graph.adjacency["3"] == frozenset()
    assert graph.isolated_node_ids() == ("3",)


def test_neighbors_and_degree_reject_unknown_node() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )

    with pytest.raises(ContractGraphError, match="Unknown node ID"):
        graph.neighbors("missing")
    with pytest.raises(ContractGraphError, match="Unknown node ID"):
        graph.degree("missing")


def test_missing_nodes_file_fails(tmp_path: Path) -> None:
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, [])

    with pytest.raises(ContractGraphError, match="Missing nodes.csv"):
        load_contract_graph(tmp_path / "nodes.csv", edges_path, condition="normal")


def test_missing_edges_file_fails(tmp_path: Path) -> None:
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, [node_row("1")])

    with pytest.raises(ContractGraphError, match="Missing edges.csv"):
        load_contract_graph(nodes_path, tmp_path / "edges.csv", condition="normal")


def test_missing_required_node_columns_fail(tmp_path: Path) -> None:
    nodes_path = write_csv(
        tmp_path / "nodes.csv",
        ("resid", "condition"),
        [{"resid": "1", "condition": "normal"}],
    )
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, [])

    with pytest.raises(ContractGraphError, match="nodes.csv is missing required"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_missing_required_edge_columns_fail(tmp_path: Path) -> None:
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, [node_row("1")])
    edges_path = write_csv(
        tmp_path / "edges.csv",
        ("resid_i", "resid_j", "condition"),
        [{"resid_i": "1", "resid_j": "1", "condition": "normal"}],
    )

    with pytest.raises(ContractGraphError, match="edges.csv is missing required"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_empty_nodes_file_fails(tmp_path: Path) -> None:
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, [])
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, [])

    with pytest.raises(ContractGraphError, match="at least one node row"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_empty_node_resid_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("")],
        edges=[],
    )

    with pytest.raises(ContractGraphError, match="Empty node resid"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_duplicate_node_resid_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1"), node_row("1")],
        edges=[],
    )

    with pytest.raises(ContractGraphError, match="Duplicate node resid"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_node_condition_mismatch_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1", condition="tumor")],
        edges=[],
    )

    with pytest.raises(ContractGraphError, match="Node condition mismatch"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


@pytest.mark.parametrize(
    ("column", "match"),
    (
        ("resid_i", "Empty edge resid_i"),
        ("resid_j", "Empty edge resid_j"),
        ("edge_type", "Empty edge_type"),
    ),
)
def test_empty_required_edge_values_fail(
    tmp_path: Path,
    column: str,
    match: str,
) -> None:
    edge = edge_row("1", "2")
    edge[column] = ""
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge],
    )

    with pytest.raises(ContractGraphError, match=match):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_edge_condition_mismatch_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", condition="tumor")],
    )

    with pytest.raises(ContractGraphError, match="Edge condition mismatch"):
        load_contract_graph(nodes_path, edges_path, condition="normal")


def test_edge_referencing_missing_node_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_graph_csvs(
        tmp_path,
        nodes=[node_row("1")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(ContractGraphError, match="references missing node"):
        load_contract_graph(nodes_path, edges_path, condition="normal")
