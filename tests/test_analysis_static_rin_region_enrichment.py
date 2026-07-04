import csv
from copy import deepcopy
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    STATIC_RIN_COMMUNITIES_COLUMNS,
    STATIC_RIN_COMMUNITY_ALGORITHM,
    STATIC_RIN_REGION_ENRICHMENT_COLUMNS,
    STATIC_RIN_REGION_ENRICHMENT_METHOD,
    STATUS_COMPUTED,
    STATUS_SKIPPED_EMPTY_GRAPH,
    STATUS_SKIPPED_INSUFFICIENT_CONTINGENCY,
    STATUS_SKIPPED_INSUFFICIENT_GROUPS,
    STATUS_SKIPPED_NO_REGION_LABELS,
    StaticRinCommunities,
    StaticRinCommunityAssignment,
    StaticRinGraph,
    StaticRinNode,
    StaticRinRegionEnrichmentError,
    compute_static_rin_communities,
    compute_static_rin_region_enrichment_from_artifacts,
    write_static_rin_communities_csv,
    write_static_rin_graph_json,
    write_static_rin_region_enrichment_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "analysis"
    / "static_rin_region_enrichment.py"
)


def _node(
    residue_index: int,
    region: str | None,
    *,
    condition: str = "normal",
) -> StaticRinNode:
    return StaticRinNode(
        id=f"{condition}:{residue_index}",
        condition=condition,
        residue_index=residue_index,
        resid=str(residue_index * 10),
        resname="GLY" if residue_index == 2 else "ALA",
        segment_id="A" if residue_index < 5 else None,
        region=region,
        x_ca=None,
        y_ca=None,
        z_ca=None,
        tm_relative_z=None,
        rmsf_A=None,
        sasa_A2=None,
        ss=None,
    )


def _graph(
    regions: tuple[str | None, ...], *, condition: str = "normal"
) -> StaticRinGraph:
    return StaticRinGraph(
        condition=condition,
        nodes=tuple(
            _node(index, region, condition=condition)
            for index, region in enumerate(regions, start=1)
        ),
        edges=(),
        source_artifacts={"residue_table": f"residue_table_{condition}.csv"},
    )


def _communities(
    graph: StaticRinGraph,
    community_ids: tuple[int, ...],
    *,
    reverse: bool = False,
) -> StaticRinCommunities:
    sizes = {
        community_id: community_ids.count(community_id)
        for community_id in set(community_ids)
    }
    assignments = tuple(
        StaticRinCommunityAssignment(
            condition=graph.condition,
            node_id=node.id,
            residue_index=node.residue_index,
            resid=node.resid,
            resname=node.resname,
            segment_id=node.segment_id,
            community_id=community_id,
            community_size=sizes[community_id],
            algorithm=STATIC_RIN_COMMUNITY_ALGORITHM,
            modularity=0.25,
            n_communities=len(sizes),
        )
        for node, community_id in zip(graph.nodes, community_ids, strict=True)
    )
    return StaticRinCommunities(
        condition=graph.condition,
        assignments=tuple(reversed(assignments)) if reverse else assignments,
        algorithm=STATIC_RIN_COMMUNITY_ALGORITHM,
        modularity=0.25,
        n_communities=len(sizes),
    )


def _write_inputs(
    directory: Path,
    graph: StaticRinGraph,
    communities: StaticRinCommunities,
) -> tuple[Path, Path]:
    graph_path = write_static_rin_graph_json(graph, directory / "graph.json")
    communities_path = write_static_rin_communities_csv(communities, directory)
    return graph_path, communities_path


def test_loads_accepted_artifacts_computes_fisher_and_exports_stably(
    tmp_path: Path,
) -> None:
    graph = _graph(("ECD", "ECD", "ECD", "TM", "ECD", "TM", "TM", "TM"))
    original = deepcopy(graph.to_dict())
    first_inputs = _write_inputs(
        tmp_path / "first", graph, _communities(graph, (1, 1, 1, 1, 2, 2, 2, 2))
    )
    second_inputs = _write_inputs(
        tmp_path / "second",
        graph,
        _communities(graph, (1, 1, 1, 1, 2, 2, 2, 2), reverse=True),
    )

    first = compute_static_rin_region_enrichment_from_artifacts(*first_inputs)
    second = compute_static_rin_region_enrichment_from_artifacts(*second_inputs)
    output = write_static_rin_region_enrichment_csv(first, tmp_path / "analysis")
    first_bytes = output.read_bytes()
    write_static_rin_region_enrichment_csv(second, tmp_path / "analysis")

    assert graph.to_dict() == original
    assert first == second
    assert first.condition == "normal"
    assert output.name == "region_enrichment_normal.csv"
    assert output.read_bytes() == first_bytes
    assert [(row.community_id, row.region) for row in first.rows] == [
        (1, "ECD"),
        (1, "TM"),
        (2, "ECD"),
        (2, "TM"),
    ]
    row = first.rows[0]
    assert (
        row.region_count_in_community,
        row.non_region_count_in_community,
        row.region_count_outside_community,
        row.non_region_count_outside_community,
    ) == (3, 1, 1, 3)
    assert row.odds_ratio == pytest.approx(9.0)
    assert row.p_value == pytest.approx(17.0 / 35.0)
    assert row.method == STATIC_RIN_REGION_ENRICHMENT_METHOD
    assert row.status == STATUS_COMPUTED
    assert row.community_size == 4
    assert row.algorithm == STATIC_RIN_COMMUNITY_ALGORITHM
    assert row.n_communities == 2

    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(STATIC_RIN_REGION_ENRICHMENT_COLUMNS)
    assert rows[0]["p_value"] == "0.485714285714286"
    assert rows[0]["condition"] == "normal"
    assert rows[0]["method"] == STATIC_RIN_REGION_ENRICHMENT_METHOD


def test_uses_only_existing_labels_and_excludes_missing_nodes(
    tmp_path: Path,
) -> None:
    graph = _graph(("ECD", "ECD", None, "TM", "TM", None))
    graph_path, communities_path = _write_inputs(
        tmp_path, graph, _communities(graph, (1, 1, 1, 2, 2, 2))
    )

    result = compute_static_rin_region_enrichment_from_artifacts(
        graph_path, communities_path
    )

    assert {row.region for row in result.rows} == {"ECD", "TM"}
    assert {row.status for row in result.rows} == {STATUS_COMPUTED}
    assert {row.labeled_node_count for row in result.rows} == {4}
    assert {row.total_node_count for row in result.rows} == {6}
    first = result.rows[0]
    assert (
        first.region_count_in_community,
        first.non_region_count_in_community,
        first.region_count_outside_community,
        first.non_region_count_outside_community,
    ) == (2, 0, 0, 2)
    assert first.odds_ratio is None
    assert first.p_value == pytest.approx(1.0 / 3.0)


def test_missing_labels_emit_one_deterministic_skipped_row(tmp_path: Path) -> None:
    graph = _graph((None, None, None, None))
    graph_path, communities_path = _write_inputs(
        tmp_path, graph, _communities(graph, (1, 1, 2, 2))
    )

    result = compute_static_rin_region_enrichment_from_artifacts(
        graph_path, communities_path
    )
    output = write_static_rin_region_enrichment_csv(result, tmp_path)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.status == STATUS_SKIPPED_NO_REGION_LABELS
    assert row.region is None
    assert row.p_value is None
    assert row.method is None
    assert row.total_node_count == 4
    with output.open(encoding="utf-8", newline="") as csv_file:
        exported = next(csv.DictReader(csv_file))
    assert exported["region"] == ""
    assert exported["p_value"] == ""
    assert exported["status"] == STATUS_SKIPPED_NO_REGION_LABELS


@pytest.mark.parametrize(
    ("regions", "community_ids", "expected_status"),
    (
        (
            ("ECD", "TM", "ECD", "TM"),
            (1, 1, 1, 1),
            STATUS_SKIPPED_INSUFFICIENT_GROUPS,
        ),
        (
            ("ECD", "ECD", "ECD", "ECD"),
            (1, 1, 2, 2),
            STATUS_SKIPPED_INSUFFICIENT_CONTINGENCY,
        ),
    ),
)
def test_insufficient_group_or_region_margins_are_skipped(
    tmp_path: Path,
    regions: tuple[str | None, ...],
    community_ids: tuple[int, ...],
    expected_status: str,
) -> None:
    graph = _graph(regions)
    graph_path, communities_path = _write_inputs(
        tmp_path, graph, _communities(graph, community_ids)
    )

    result = compute_static_rin_region_enrichment_from_artifacts(
        graph_path, communities_path
    )

    assert result.rows
    assert {row.status for row in result.rows} == {expected_status}
    assert all(row.p_value is None and row.method is None for row in result.rows)


def test_isolated_nodes_keep_stage21c_identity_and_are_analyzed(
    tmp_path: Path,
) -> None:
    graph = _graph(("ECD", "ECD", "TM"))
    communities = compute_static_rin_communities(graph)
    graph_path, communities_path = _write_inputs(tmp_path, graph, communities)

    result = compute_static_rin_region_enrichment_from_artifacts(
        graph_path, communities_path
    )

    assert communities.n_communities == 3
    assert [(row.community_id, row.community_size) for row in result.rows] == [
        (1, 1),
        (1, 1),
        (2, 1),
        (2, 1),
        (3, 1),
        (3, 1),
    ]
    assert {row.status for row in result.rows} == {STATUS_COMPUTED}


def test_empty_graph_has_explicit_skipped_behavior(tmp_path: Path) -> None:
    graph_payload = {
        "schema_version": "mania.static_rin_graph.v0.1",
        "condition": "normal",
        "directed": False,
        "n_nodes": 0,
        "n_edges": 0,
        "nodes": [],
        "edges": [],
    }
    communities_path = tmp_path / "communities_normal.csv"
    with communities_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=STATIC_RIN_COMMUNITIES_COLUMNS,
        )
        writer.writeheader()

    result = compute_static_rin_region_enrichment_from_artifacts(
        graph_payload, communities_path
    )

    assert len(result.rows) == 1
    assert result.rows[0].status == STATUS_SKIPPED_EMPTY_GRAPH
    assert result.rows[0].total_node_count == 0


def test_rejects_community_identity_mismatch(tmp_path: Path) -> None:
    graph = _graph(("ECD", "TM"))
    graph_path, communities_path = _write_inputs(
        tmp_path, graph, _communities(graph, (1, 2))
    )
    with communities_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    rows[0]["node_id"] = "normal:999"
    with communities_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(
        StaticRinRegionEnrichmentError, match="node identity does not match"
    ):
        compute_static_rin_region_enrichment_from_artifacts(
            graph_path, communities_path
        )


def test_public_layer_is_dependency_free_and_wania_agnostic() -> None:
    assert (
        mania.analysis.compute_static_rin_region_enrichment_from_artifacts
        is compute_static_rin_region_enrichment_from_artifacts
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
    ):
        assert forbidden not in source
