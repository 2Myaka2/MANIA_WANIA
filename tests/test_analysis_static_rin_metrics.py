import csv
from pathlib import Path

import pytest

import mania.analysis
import mania.analysis.static_rin_metrics as static_rin_metrics
from mania.analysis import (
    STATIC_RIN_METRICS_COLUMNS,
    StaticRinEdge,
    StaticRinGraph,
    StaticRinInteraction,
    StaticRinNode,
    compute_static_rin_metrics,
    compute_static_rin_metrics_from_graph_json,
    write_static_rin_graph_json,
    write_static_rin_metrics_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "analysis" / "static_rin_metrics.py"


def _node(residue_index: int, *, condition: str = "normal") -> StaticRinNode:
    return StaticRinNode(
        id=f"{condition}:{residue_index}",
        condition=condition,
        residue_index=residue_index,
        resid=str(residue_index * 10),
        resname="ALA" if residue_index != 2 else "GLY",
        segment_id="A" if residue_index < 4 else None,
        region=None,
        x_ca=None,
        y_ca=None,
        z_ca=None,
        tm_relative_z=None,
        rmsf_A=None,
        sasa_A2=None,
        ss=None,
    )


def _edge(
    source_index: int,
    target_index: int,
    weight: float | None,
    *,
    condition: str = "normal",
) -> StaticRinEdge:
    source = _node(source_index, condition=condition)
    target = _node(target_index, condition=condition)
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


def _graph(
    node_indexes: tuple[int, ...],
    edges: tuple[StaticRinEdge, ...],
    *,
    condition: str = "normal",
) -> StaticRinGraph:
    return StaticRinGraph(
        condition=condition,
        nodes=tuple(_node(index, condition=condition) for index in node_indexes),
        edges=edges,
        source_artifacts={"residue_table": f"residue_table_{condition}.csv"},
    )


def test_path_metrics_preserve_stage21a_identity_and_use_unweighted_paths() -> None:
    graph = _graph(
        (1, 2, 3),
        (_edge(1, 2, 0.25), _edge(2, 3, 0.75)),
    )

    result = compute_static_rin_metrics(graph)
    rows = result.by_node_id

    assert result.condition == "normal"
    assert [row.node_id for row in result.node_metrics] == [
        "normal:1",
        "normal:2",
        "normal:3",
    ]
    assert rows["normal:1"].residue_index == 1
    assert rows["normal:1"].resid == "10"
    assert rows["normal:2"].resname == "GLY"
    assert rows["normal:1"].segment_id == "A"
    assert [rows[f"normal:{index}"].degree for index in (1, 2, 3)] == [1, 2, 1]
    assert rows["normal:1"].strength == pytest.approx(0.25)
    assert rows["normal:2"].strength == pytest.approx(1.0)
    assert rows["normal:3"].strength == pytest.approx(0.75)
    assert rows["normal:2"].betweenness == pytest.approx(1.0)
    assert rows["normal:1"].betweenness == pytest.approx(0.0)
    assert rows["normal:2"].closeness == pytest.approx(1.0)
    assert rows["normal:1"].closeness == pytest.approx(2.0 / 3.0)
    assert rows["normal:2"].eigenvector == pytest.approx(2**-0.5, abs=1e-9)
    assert sum(float(row.pagerank) for row in result.node_metrics) == pytest.approx(1.0)
    assert {row.kcore for row in result.node_metrics} == {1}


def test_missing_weights_disconnected_components_and_isolate_are_explicit() -> None:
    graph = _graph(
        (1, 2, 3, 4, 5, 6),
        (
            _edge(1, 2, 0.25),
            _edge(2, 3, None),
            _edge(4, 5, None),
        ),
    )

    result = compute_static_rin_metrics(graph)
    rows = result.by_node_id

    assert rows["normal:1"].strength == pytest.approx(0.25)
    assert rows["normal:2"].strength == pytest.approx(0.25)
    assert rows["normal:3"].strength is None
    assert rows["normal:4"].strength is None
    assert rows["normal:5"].strength is None
    assert rows["normal:6"].degree == 0
    assert rows["normal:6"].strength == 0.0
    assert rows["normal:6"].betweenness == 0.0
    assert rows["normal:6"].closeness == 0.0
    assert rows["normal:6"].kcore == 0
    assert rows["normal:2"].betweenness == pytest.approx(0.1)
    assert rows["normal:2"].closeness == pytest.approx(0.4)
    assert rows["normal:4"].closeness == pytest.approx(0.2)


def test_loads_accepted_graph_json_and_exports_deterministic_centrality_csv(
    tmp_path: Path,
) -> None:
    graph = _graph(
        (1, 2, 3, 4),
        (_edge(1, 2, 0.5), _edge(2, 3, None)),
    )
    graph_path = write_static_rin_graph_json(
        graph, tmp_path / "analysis" / "normal" / "graph.json"
    )

    first = compute_static_rin_metrics_from_graph_json(graph_path)
    second = compute_static_rin_metrics_from_graph_json(graph.to_dict())
    output = write_static_rin_metrics_csv(first, tmp_path / "analysis" / "normal")
    first_bytes = output.read_bytes()
    write_static_rin_metrics_csv(second, tmp_path / "analysis" / "normal")

    assert first == second
    assert output.name == "centrality_normal.csv"
    assert output.read_bytes() == first_bytes
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(STATIC_RIN_METRICS_COLUMNS)
    assert [row["node_id"] for row in rows] == [
        "normal:1",
        "normal:2",
        "normal:3",
        "normal:4",
    ]
    assert rows[2]["strength"] == ""
    assert rows[3]["degree"] == "0"
    assert rows[3]["strength"] == "0"
    assert rows[0]["condition"] == "normal"


def test_iterative_metric_failure_uses_deterministic_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph((1, 2), (_edge(1, 2, 0.5),))

    def fail(_adjacency: object) -> dict[str, float]:
        raise ArithmeticError("synthetic non-convergence")

    monkeypatch.setattr(static_rin_metrics, "_eigenvector_centrality", fail)
    monkeypatch.setattr(static_rin_metrics, "_pagerank", fail)

    first = compute_static_rin_metrics(graph)
    second = compute_static_rin_metrics(graph)

    assert first == second
    assert all(row.eigenvector is None for row in first.node_metrics)
    assert all(row.pagerank is None for row in first.node_metrics)


def test_public_metrics_layer_is_dependency_free_and_stays_within_stage21b() -> None:
    assert mania.analysis.compute_static_rin_metrics is compute_static_rin_metrics
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "mania.wania",
        "wania_graph_payload",
        "community",
        "enrichment",
        "comparison",
        "statistics",
        "temporal",
        "conformation",
    ):
        assert forbidden not in source
