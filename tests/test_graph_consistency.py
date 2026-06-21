import csv
import json
from pathlib import Path

import pytest

from mania.analysis.contract_graph import (
    ContractGraph,
    load_contract_graph,
    load_contract_graph_from_condition_dir,
)
from mania.analysis.graph_consistency import (
    GraphConsistencyError,
    GraphTopologyConsistencyReport,
    check_graph_topology_consistency,
    write_graph_topology_consistency_report,
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


def node_row(
    resid: str,
    *,
    condition: str = "normal",
    degree: str = "1",
    strength: str = "0.5",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    row = {column: "" for column in NODE_COLUMNS}
    row.update(
        {
            "resid": resid,
            "resname": "ALA",
            "region": "TM1",
            "condition": condition,
            "degree": degree,
            "strength": strength,
        }
    )
    if extra is not None:
        row.update(extra)
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
    node_columns: tuple[str, ...] = NODE_COLUMNS,
    condition: str = "normal",
) -> ContractGraph:
    nodes_path = write_csv(tmp_path / "nodes.csv", node_columns, nodes)
    edges_path = write_csv(tmp_path / "edges.csv", EDGE_COLUMNS, edges)
    return load_contract_graph(nodes_path, edges_path, condition=condition)


def test_normal_fixture_reports_current_strength_mismatch() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )

    report = check_graph_topology_consistency(graph)

    assert isinstance(report, GraphTopologyConsistencyReport)
    assert report.condition == "normal"
    assert report.n_nodes == 2
    assert report.checked_metrics == ("degree", "strength")
    assert report.passed is False
    assert report.n_mismatches == 2
    assert tuple(mismatch.metric for mismatch in report.mismatches) == (
        "strength",
        "strength",
    )


def test_tumor_fixture_reports_current_strength_mismatch() -> None:
    graph = load_contract_graph_from_condition_dir(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )

    report = check_graph_topology_consistency(graph)

    assert report.condition == "tumor"
    assert report.passed is False
    assert report.n_mismatches == 2
    assert all(mismatch.metric == "strength" for mismatch in report.mismatches)


def test_synthetic_graph_passes_consistency_check(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph)

    assert report.passed is True
    assert report.n_mismatches == 0
    assert report.mismatches == ()


def test_degree_mismatch_is_reported_not_raised(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree="0"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph)

    assert report.passed is False
    assert report.n_mismatches == 1
    mismatch = report.mismatches[0]
    assert mismatch.metric == "degree"
    assert mismatch.node_id == "1"
    assert mismatch.expected == 0.0
    assert mismatch.actual == 1.0


def test_strength_mismatch_is_reported_not_raised(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", strength="0.0"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph)

    assert report.passed is False
    assert report.n_mismatches == 1
    mismatch = report.mismatches[0]
    assert mismatch.metric == "strength"
    assert mismatch.node_id == "1"


def test_small_strength_drift_within_tolerance_passes(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", strength="0.5000005"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph, abs_tol=1e-6)

    assert report.passed is True


def test_strength_drift_outside_tolerance_fails(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", strength="0.500002"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph, abs_tol=1e-6)

    assert report.passed is False
    assert report.mismatches[0].metric == "strength"


def test_degree_accepts_integer_like_float_string(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree="1.0"), node_row("2", degree="1.0")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph)

    assert report.passed is True


def test_custom_node_metric_columns_work(tmp_path: Path) -> None:
    node_columns = (*NODE_COLUMNS, "exported_degree", "exported_strength")
    graph = load_graph_from_rows(
        tmp_path,
        node_columns=node_columns,
        nodes=[
            node_row(
                "1",
                degree="99",
                strength="99",
                extra={"exported_degree": "1", "exported_strength": "0.5"},
            ),
            node_row(
                "2",
                degree="99",
                strength="99",
                extra={"exported_degree": "1", "exported_strength": "0.5"},
            ),
        ],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(
        graph,
        degree_column="exported_degree",
        strength_column="exported_strength",
    )

    assert report.passed is True
    assert report.checked_metrics == ("degree", "strength")


def test_custom_weight_column_works(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", strength="7.25"), node_row("2", strength="7.25")],
        edges=[
            edge_row("1", "2", contact_freq="0.5", mean_dist_a="7.25"),
        ],
    )

    report = check_graph_topology_consistency(graph, weight_column="mean_dist_A")

    assert report.passed is True


def test_missing_degree_column_raises(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Missing exported degree"):
        check_graph_topology_consistency(graph, degree_column="missing_degree")


def test_missing_strength_column_raises(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Missing exported strength"):
        check_graph_topology_consistency(graph, strength_column="missing_strength")


def test_empty_exported_metric_raises(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree=""), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Empty exported degree"):
        check_graph_topology_consistency(graph)


def test_non_numeric_exported_metric_raises(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree="abc"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Invalid exported degree"):
        check_graph_topology_consistency(graph)


@pytest.mark.parametrize("strength", ("nan", "inf", "-inf"))
def test_non_finite_exported_metric_raises(
    tmp_path: Path,
    strength: str,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", strength=strength), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Non-finite exported strength"):
        check_graph_topology_consistency(graph)


@pytest.mark.parametrize("abs_tol", (-1.0, float("nan"), float("inf")))
def test_invalid_abs_tol_raises(tmp_path: Path, abs_tol: float) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphConsistencyError, match="Invalid abs_tol"):
        check_graph_topology_consistency(graph, abs_tol=abs_tol)


def test_invalid_edge_weight_is_translated_to_consistency_error(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="abc")],
    )

    with pytest.raises(GraphConsistencyError, match="Invalid topology metric input"):
        check_graph_topology_consistency(graph)


def test_mismatches_by_metric_filters_reported_mismatches(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree="0", strength="0.0"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    report = check_graph_topology_consistency(graph)

    degree_mismatches = report.mismatches_by_metric("degree")
    strength_mismatches = report.mismatches_by_metric("strength")
    assert len(degree_mismatches) == 1
    assert degree_mismatches[0].metric == "degree"
    assert len(strength_mismatches) == 1
    assert strength_mismatches[0].metric == "strength"


def test_to_dict_is_json_serializable(tmp_path: Path) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1", degree="0"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )
    report = check_graph_topology_consistency(graph)

    payload = report.to_dict()

    assert {"condition", "n_nodes", "checked_metrics", "passed", "mismatches"}.issubset(
        payload
    )
    assert json.loads(json.dumps(payload)) == {
        "condition": "normal",
        "n_nodes": 2,
        "checked_metrics": ["degree", "strength"],
        "passed": False,
        "n_mismatches": 1,
        "mismatches": [
            {
                "node_id": "1",
                "metric": "degree",
                "expected": 0.0,
                "actual": 1.0,
                "abs_diff": 1.0,
                "abs_tol": 1e-6,
                "message": (
                    "degree mismatch for node 1: expected 0.0, actual 1.0, "
                    "abs_diff 1.0 exceeds abs_tol 1e-06"
                ),
            }
        ],
    }


def test_write_graph_topology_consistency_report_creates_json_file(
    tmp_path: Path,
) -> None:
    graph = load_graph_from_rows(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )
    report = check_graph_topology_consistency(graph)

    path = write_graph_topology_consistency_report(
        report,
        tmp_path / "qc" / "topology_consistency.json",
    )

    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["condition"] == report.condition
    assert path.read_text(encoding="utf-8").endswith("\n")
