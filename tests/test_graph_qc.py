import csv
import json
from pathlib import Path

from mania.analysis.contract_graph import (
    load_contract_graph,
    load_contract_graph_from_condition_dir,
)
from mania.analysis.graph_qc import (
    GraphComponent,
    GraphQCReport,
    compute_graph_qc,
    write_graph_qc_report,
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


def load_graph_from_rows(
    tmp_path: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    condition: str = "normal",
):
    nodes_path = write_csv(tmp_path / "nodes.csv", NODE_COLUMNS, nodes)
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, edges)
    return load_contract_graph(nodes_path, edges_path, condition=condition)


def test_fixture_graph_passes_basic_qc() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )

    report = compute_graph_qc(graph)

    assert isinstance(report, GraphQCReport)
    assert report.condition == "normal"
    assert report.n_nodes == 2
    assert report.n_edges == 1
    assert report.n_isolated_nodes == 0
    assert report.isolated_node_ids == ()
    assert report.components == (
        GraphComponent(component_id=1, node_ids=("1", "2"), size=2),
    )
    assert report.n_components == 1
    assert report.largest_component_size == 2
    assert report.self_loop_edges == ()
    assert report.duplicate_undirected_edge_keys == ()
    assert not report.has_isolated_nodes
    assert not report.has_self_loops
    assert not report.has_duplicate_edges
    assert report.passed_basic_qc


def test_tumor_fixture_graph_passes_basic_qc() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )

    report = compute_graph_qc(graph)

    assert isinstance(report, GraphQCReport)
    assert report.condition == "tumor"
    assert report.n_nodes == 2
    assert report.n_edges == 1
    assert report.passed_basic_qc is True


def test_components_are_deterministic_and_preserve_node_order(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2"), node_row("3"), node_row("4")],
        edges=[edge_row("2", "1"), edge_row("4", "3")],
    )

    report = compute_graph_qc(graph)

    assert report.n_components == 2
    assert report.components == (
        GraphComponent(component_id=1, node_ids=("1", "2"), size=2),
        GraphComponent(component_id=2, node_ids=("3", "4"), size=2),
    )
    assert report.largest_component_size == 2
    assert report.passed_basic_qc


def test_isolated_nodes_are_reported_and_fail_basic_qc(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2"), node_row("3")],
        edges=[edge_row("1", "2")],
    )

    report = compute_graph_qc(graph)

    assert report.n_isolated_nodes == 1
    assert report.isolated_node_ids == ("3",)
    assert report.n_components == 2
    assert report.components[-1] == GraphComponent(
        component_id=2,
        node_ids=("3",),
        size=1,
    )
    assert report.has_isolated_nodes
    assert not report.passed_basic_qc


def test_self_loop_is_reported_and_not_considered_duplicate_once(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1")],
        edges=[edge_row("1", "1", edge_type="contact")],
    )

    report = compute_graph_qc(graph)

    assert report.self_loop_edges == (("1", "1", "contact"),)
    assert report.duplicate_undirected_edge_keys == ()
    assert report.has_self_loops
    assert not report.has_duplicate_edges
    assert not report.passed_basic_qc


def test_repeated_self_loop_is_also_duplicate(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1")],
        edges=[
            edge_row("1", "1", edge_type="contact"),
            edge_row("1", "1", edge_type="contact"),
        ],
    )

    report = compute_graph_qc(graph)

    assert report.self_loop_edges == (
        ("1", "1", "contact"),
        ("1", "1", "contact"),
    )
    assert report.duplicate_undirected_edge_keys == (("1", "1", "contact"),)
    assert report.has_duplicate_edges
    assert not report.passed_basic_qc


def test_duplicate_undirected_edge_keys_include_edge_type(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[
            edge_row("1", "2", edge_type="contact"),
            edge_row("2", "1", edge_type="contact"),
            edge_row("2", "1", edge_type="hydrogen_bond"),
        ],
    )

    report = compute_graph_qc(graph)

    assert report.duplicate_undirected_edge_keys == (("1", "2", "contact"),)
    assert report.has_duplicate_edges
    assert not report.passed_basic_qc


def test_same_pair_with_different_edge_type_is_not_duplicate(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[
            edge_row("1", "2", edge_type="contact"),
            edge_row("2", "1", edge_type="hydrogen_bond"),
        ],
    )

    report = compute_graph_qc(graph)

    assert report.duplicate_undirected_edge_keys == ()
    assert report.has_duplicate_edges is False


def test_component_ordering_is_stable_for_non_numeric_node_order(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("3"), node_row("1"), node_row("2"), node_row("4")],
        edges=[edge_row("1", "2")],
    )

    report_1 = compute_graph_qc(graph)
    report_2 = compute_graph_qc(graph)

    assert report_1.components == report_2.components
    assert tuple(component.node_ids for component in report_1.components) == (
        ("3",),
        ("1", "2"),
        ("4",),
    )


def test_to_dict_is_json_serializable(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2"), node_row("3")],
        edges=[edge_row("1", "2"), edge_row("2", "1")],
    )
    report = compute_graph_qc(graph)

    payload = report.to_dict()

    assert json.loads(json.dumps(payload)) == {
        "condition": "normal",
        "n_nodes": 3,
        "n_edges": 2,
        "n_isolated_nodes": 1,
        "isolated_node_ids": ["3"],
        "n_components": 2,
        "components": [
            {"component_id": 1, "node_ids": ["1", "2"], "size": 2},
            {"component_id": 2, "node_ids": ["3"], "size": 1},
        ],
        "largest_component_size": 2,
        "self_loop_edges": [],
        "duplicate_undirected_edge_keys": [["1", "2", "contact"]],
        "has_isolated_nodes": True,
        "has_self_loops": False,
        "has_duplicate_edges": True,
        "passed_basic_qc": False,
    }


def test_write_graph_qc_report_creates_json_file(tmp_path: Path) -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )
    report = compute_graph_qc(graph)

    output_path = write_graph_qc_report(report, tmp_path / "nested" / "qc.json")

    assert output_path == tmp_path / "nested" / "qc.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == report.to_dict()
    assert output_path.read_text(encoding="utf-8").endswith("\n")
