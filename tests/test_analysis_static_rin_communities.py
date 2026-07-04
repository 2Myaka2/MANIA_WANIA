import csv
from copy import deepcopy
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    STATIC_RIN_COMMUNITIES_COLUMNS,
    STATIC_RIN_COMMUNITY_ALGORITHM,
    StaticRinEdge,
    StaticRinGraph,
    StaticRinInteraction,
    StaticRinNode,
    compute_static_rin_communities,
    compute_static_rin_communities_from_graph_json,
    write_static_rin_communities_csv,
    write_static_rin_graph_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "analysis" / "static_rin_communities.py"
)


def _node(residue_index: int, *, condition: str = "normal") -> StaticRinNode:
    return StaticRinNode(
        id=f"{condition}:{residue_index}",
        condition=condition,
        residue_index=residue_index,
        resid=str(residue_index * 10),
        resname="GLY" if residue_index == 2 else "ALA",
        segment_id="A" if residue_index < 5 else None,
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
    edge_specs: tuple[tuple[int, int, float | None], ...],
    *,
    condition: str = "normal",
) -> StaticRinGraph:
    return StaticRinGraph(
        condition=condition,
        nodes=tuple(_node(index, condition=condition) for index in node_indexes),
        edges=tuple(
            _edge(source, target, weight, condition=condition)
            for source, target, weight in edge_specs
        ),
        source_artifacts={"residue_table": f"residue_table_{condition}.csv"},
    )


def test_finds_deterministic_communities_and_preserves_stage21a_identity() -> None:
    graph = _graph(
        (1, 2, 3, 4, 5, 6),
        (
            (1, 2, 0.2),
            (1, 3, 0.4),
            (2, 3, 0.6),
            (4, 5, 0.3),
            (4, 6, 0.5),
            (5, 6, 0.7),
            (3, 4, 0.1),
        ),
    )
    original = deepcopy(graph.to_dict())

    result = compute_static_rin_communities(graph)
    rows = result.by_node_id

    assert graph.to_dict() == original
    assert result.condition == "normal"
    assert result.algorithm == "greedy_modularity_unweighted"
    assert result.algorithm == STATIC_RIN_COMMUNITY_ALGORITHM
    assert result.n_communities == 2
    assert result.modularity == pytest.approx(5.0 / 14.0)
    assert [row.node_id for row in result.assignments] == [
        "normal:1",
        "normal:2",
        "normal:3",
        "normal:4",
        "normal:5",
        "normal:6",
    ]
    assert rows["normal:1"].community_id == 1
    assert rows["normal:3"].community_id == 1
    assert rows["normal:4"].community_id == 2
    assert rows["normal:6"].community_id == 2
    assert {row.community_size for row in result.assignments} == {3}
    assert rows["normal:1"].residue_index == 1
    assert rows["normal:1"].resid == "10"
    assert rows["normal:2"].resname == "GLY"
    assert rows["normal:6"].segment_id is None


def test_loads_stage21a_json_and_exports_deterministic_communities_csv(
    tmp_path: Path,
) -> None:
    graph = _graph(
        (1, 2, 3, 4, 5, 6),
        (
            (1, 2, 0.2),
            (1, 3, 0.4),
            (2, 3, 0.6),
            (4, 5, 0.3),
            (4, 6, 0.5),
            (5, 6, 0.7),
            (3, 4, 0.1),
        ),
    )
    graph_path = write_static_rin_graph_json(
        graph, tmp_path / "analysis" / "normal" / "graph.json"
    )
    reordered = graph.to_dict()
    nodes = reordered["nodes"]
    edges = reordered["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    reordered["nodes"] = list(reversed(nodes))
    reordered["edges"] = list(reversed(edges))

    first = compute_static_rin_communities_from_graph_json(graph_path)
    second = compute_static_rin_communities_from_graph_json(reordered)
    output = write_static_rin_communities_csv(
        first, tmp_path / "analysis" / "normal"
    )
    first_bytes = output.read_bytes()
    write_static_rin_communities_csv(second, tmp_path / "analysis" / "normal")

    assert first == second
    assert output.name == "communities_normal.csv"
    assert output.read_bytes() == first_bytes
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(STATIC_RIN_COMMUNITIES_COLUMNS)
    assert [row["node_id"] for row in rows] == [
        "normal:1",
        "normal:2",
        "normal:3",
        "normal:4",
        "normal:5",
        "normal:6",
    ]
    assert rows[0]["condition"] == "normal"
    assert rows[0]["community_id"] == "1"
    assert rows[0]["community_size"] == "3"
    assert rows[0]["algorithm"] == STATIC_RIN_COMMUNITY_ALGORITHM
    assert rows[0]["modularity"] == "0.357142857142857"
    assert rows[0]["n_communities"] == "2"
    assert rows[5]["segment_id"] == ""


def test_disconnected_missing_weight_and_isolate_behavior_is_explicit() -> None:
    mixed_weights = _graph(
        (1, 2, 3, 4, 5, 6),
        ((1, 2, 0.25), (2, 3, None), (4, 5, None)),
    )
    changed_weights = _graph(
        (1, 2, 3, 4, 5, 6),
        ((1, 2, None), (2, 3, 1.0), (4, 5, 0.5)),
    )

    first = compute_static_rin_communities(mixed_weights)
    second = compute_static_rin_communities(changed_weights)
    rows = first.by_node_id

    assert first == second
    assert first.n_communities == 3
    assert first.modularity == pytest.approx(4.0 / 9.0)
    assert rows["normal:1"].community_id == 1
    assert rows["normal:2"].community_id == 1
    assert rows["normal:3"].community_id == 1
    assert rows["normal:4"].community_id == 2
    assert rows["normal:5"].community_id == 2
    assert rows["normal:6"].community_id == 3
    assert rows["normal:6"].community_size == 1
    assert "louvain" not in first.algorithm


def test_edgeless_graph_assigns_stable_singleton_communities() -> None:
    graph = _graph((2, 10, 11), ())

    result = compute_static_rin_communities(graph)

    assert result.n_communities == 3
    assert result.modularity == 0.0
    assert [row.community_id for row in result.assignments] == [1, 2, 3]
    assert [row.community_size for row in result.assignments] == [1, 1, 1]


def test_public_community_layer_is_dependency_free_and_stays_within_stage21c() -> None:
    assert (
        mania.analysis.compute_static_rin_communities
        is compute_static_rin_communities
    )
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "mania.wania",
        "wania_graph_payload",
        "enrichment",
        "comparison",
        "statistics",
        "temporal",
        "conformation",
    ):
        assert forbidden not in source
