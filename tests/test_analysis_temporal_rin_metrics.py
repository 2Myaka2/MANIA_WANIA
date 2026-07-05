import csv
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

import mania.analysis
from mania.analysis import (
    STATIC_RIN_COMMUNITY_ALGORITHM,
    TEMPORAL_RIN_METRICS_COLUMNS,
    TEMPORAL_RIN_STATUS_COMPUTED,
    TEMPORAL_RIN_STATUS_EMPTY_WINDOW,
    TEMPORAL_RIN_STATUS_NO_CONTACTS_PASSING_THRESHOLD,
    TEMPORAL_RIN_STATUS_SKIPPED_NO_EDGES,
    TEMPORAL_RIN_STATUS_SKIPPED_NO_NODES,
    TemporalContactRow,
    TemporalRinConfig,
    TemporalRinInput,
    TemporalRinWindowGraphBundle,
    TemporalRinWindowNode,
    build_temporal_rin_window_graphs,
    compute_temporal_rin_metrics,
    generate_temporal_windows,
    write_temporal_rin_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "analysis" / "temporal_rin_metrics.py"
)


def _row(
    frame_index: int,
    residue_index_i: int,
    residue_index_j: int,
) -> TemporalContactRow:
    identities = {
        1: ("10", "ALA", "A"),
        2: ("20", "GLY", "A"),
        3: ("30", "LYS", "A"),
        4: ("40", "SER", "B"),
    }
    resid_i, resname_i, segment_i = identities[residue_index_i]
    resid_j, resname_j, segment_j = identities[residue_index_j]
    return TemporalContactRow(
        condition="normal",
        frame_index=frame_index,
        time_ps=float(frame_index),
        residue_index_i=residue_index_i,
        resid_i=resid_i,
        resname_i=resname_i,
        segment_id_i=segment_i,
        residue_index_j=residue_index_j,
        resid_j=resid_j,
        resname_j=resname_j,
        segment_id_j=segment_j,
        edge_type="vdw",
        distance_A=4.0,
    )


def _bundle(
    frame_indexes: tuple[int, ...],
    rows: tuple[TemporalContactRow, ...],
    *,
    min_frequency: float = 0.5,
    window_size: int | None = None,
    step_size: int | None = None,
) -> TemporalRinWindowGraphBundle:
    size = window_size or len(frame_indexes)
    config = TemporalRinConfig(
        window_size=size,
        step_size=step_size or size,
        min_frequency=min_frequency,
    )
    temporal_input = TemporalRinInput(
        condition="normal",
        config=config,
        rows=rows,
        sampled_frame_indexes=frame_indexes,
        windows=generate_temporal_windows("normal", frame_indexes, config=config),
    )
    return build_temporal_rin_window_graphs(temporal_input)


def test_metrics_consume_stage22b_graph_and_preserve_window_identity() -> None:
    bundle = _bundle(
        (2, 100, 250, 900),
        (_row(2, 1, 2), _row(100, 1, 2), _row(250, 2, 3)),
    )
    graph = bundle.windows[0]

    assert graph.active_frame_count == 3
    result = compute_temporal_rin_metrics(bundle)
    row = result.windows[0]

    assert result.condition == row.condition == "normal"
    assert (
        row.window_id,
        row.frame_start,
        row.frame_end,
        row.sampled_frame_count,
        row.active_frame_count,
    ) == (0, 2, 900, 4, 3)
    assert row.frame_end - row.frame_start + 1 != row.sampled_frame_count
    assert (row.n_nodes, row.n_edges) == (2, 1)
    assert row.density == pytest.approx(1.0)
    assert row.mean_degree == pytest.approx(1.0)
    assert row.mean_strength == pytest.approx(0.5)
    assert row.betweenness_mean == pytest.approx(0.0)
    assert row.betweenness_max == pytest.approx(0.0)
    assert row.closeness_mean == pytest.approx(1.0)
    assert row.modularity == pytest.approx(0.0)
    assert row.n_communities == 1
    assert row.community_algorithm == STATIC_RIN_COMMUNITY_ALGORITHM
    assert row.status == TEMPORAL_RIN_STATUS_COMPUTED


def test_paths_and_communities_are_unweighted_with_disconnected_isolate() -> None:
    bundle = _bundle(
        (0, 1, 2, 3),
        (
            _row(0, 1, 2),
            _row(1, 1, 2),
            _row(0, 2, 3),
            _row(1, 2, 3),
            _row(2, 2, 3),
        ),
    )
    graph = bundle.windows[0]
    isolate = TemporalRinWindowNode(
        id="normal:4",
        condition="normal",
        residue_index=4,
        resid="40",
        resname="SER",
        segment_id="B",
    )
    graph_with_isolate = replace(graph, nodes=(*graph.nodes, isolate))
    bundle_with_isolate = replace(bundle, windows=(graph_with_isolate,))

    first = compute_temporal_rin_metrics(bundle_with_isolate).windows[0]
    changed_edges = tuple(
        replace(
            edge,
            interactions=(
                replace(
                    edge.primary_interaction,
                    window_contact_freq=0.25 if index == 0 else 0.5,
                ),
            ),
        )
        for index, edge in enumerate(graph_with_isolate.edges)
    )
    changed = compute_temporal_rin_metrics(
        replace(
            bundle_with_isolate,
            windows=(replace(graph_with_isolate, edges=changed_edges),),
        )
    ).windows[0]

    assert (first.n_nodes, first.n_edges) == (4, 2)
    assert first.density == pytest.approx(1.0 / 3.0)
    assert first.mean_degree == pytest.approx(1.0)
    assert first.mean_strength == pytest.approx(0.625)
    assert first.betweenness_mean == pytest.approx(1.0 / 12.0)
    assert first.betweenness_max == pytest.approx(1.0 / 3.0)
    assert first.closeness_mean == pytest.approx(7.0 / 18.0)
    assert first.n_communities == 2
    assert first.community_algorithm == "greedy_modularity_unweighted"
    assert "louvain" not in first.community_algorithm
    assert changed.mean_strength != first.mean_strength
    assert changed.betweenness_mean == first.betweenness_mean
    assert changed.betweenness_max == first.betweenness_max
    assert changed.closeness_mean == first.closeness_mean
    assert changed.modularity == first.modularity
    assert changed.n_communities == first.n_communities


def test_empty_no_passing_and_edgeless_windows_are_explicit() -> None:
    empty_bundle = _bundle((5,), ())
    empty = compute_temporal_rin_metrics(empty_bundle).windows[0]
    assert empty.status == TEMPORAL_RIN_STATUS_EMPTY_WINDOW
    assert empty.active_frame_count == 0

    no_passing_bundle = _bundle((0, 1, 2, 3), (_row(0, 1, 2),))
    no_passing = compute_temporal_rin_metrics(no_passing_bundle).windows[0]
    assert no_passing.status == TEMPORAL_RIN_STATUS_NO_CONTACTS_PASSING_THRESHOLD
    assert no_passing.active_frame_count == 1

    no_nodes_graph = replace(
        empty_bundle.windows[0],
        status=TEMPORAL_RIN_STATUS_COMPUTED,
    )
    no_nodes = compute_temporal_rin_metrics(
        replace(empty_bundle, windows=(no_nodes_graph,))
    ).windows[0]
    assert no_nodes.status == TEMPORAL_RIN_STATUS_SKIPPED_NO_NODES

    isolate = TemporalRinWindowNode(
        id="normal:4",
        condition="normal",
        residue_index=4,
        resid="40",
        resname="SER",
        segment_id="B",
    )
    isolate_graph = replace(
        empty_bundle.windows[0],
        status=TEMPORAL_RIN_STATUS_COMPUTED,
        nodes=(isolate,),
    )
    edgeless = compute_temporal_rin_metrics(
        replace(empty_bundle, windows=(isolate_graph,))
    ).windows[0]
    assert edgeless.status == TEMPORAL_RIN_STATUS_SKIPPED_NO_EDGES

    for row in (empty, no_passing, no_nodes, edgeless):
        assert row.density is None
        assert row.mean_degree is None
        assert row.mean_strength is None
        assert row.betweenness_mean is None
        assert row.betweenness_max is None
        assert row.closeness_mean is None
        assert row.modularity is None
        assert row.n_communities is None
        assert row.community_algorithm is None
        assert row.notes


def test_missing_window_weight_does_not_become_zero() -> None:
    bundle = _bundle((0, 1), (_row(0, 1, 2), _row(1, 1, 2)))
    graph = bundle.windows[0]
    edge = graph.edges[0]
    missing = replace(
        edge.primary_interaction,
        window_contact_freq=cast(Any, None),
    )
    missing_graph = replace(
        graph,
        edges=(replace(edge, interactions=(missing,)),),
    )

    row = compute_temporal_rin_metrics(
        replace(bundle, windows=(missing_graph,))
    ).windows[0]

    assert row.mean_strength is None
    assert "missing" in row.notes
    assert row.mean_degree == 1.0
    assert row.closeness_mean == 1.0


def test_temporal_csv_is_atomic_ordered_and_byte_deterministic(
    tmp_path: Path,
) -> None:
    bundle = _bundle(
        (0, 10, 20, 30),
        (
            _row(0, 1, 2),
            _row(10, 1, 2),
            _row(20, 2, 3),
            _row(30, 2, 3),
        ),
        window_size=2,
        step_size=2,
    )
    metrics = compute_temporal_rin_metrics(bundle)
    output_dir = tmp_path / "analysis" / "normal"
    output = write_temporal_rin_csv(metrics, output_dir)
    first_bytes = output.read_bytes()
    write_temporal_rin_csv(metrics, output_dir)

    assert output.name == "temporal_rin_normal.csv"
    assert output.read_bytes() == first_bytes
    assert not tuple(output_dir.glob("*.tmp"))
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(TEMPORAL_RIN_METRICS_COLUMNS)
    assert [row["window_id"] for row in rows] == ["0", "1"]
    assert [row["frame_start"] for row in rows] == ["0", "20"]
    assert rows[0]["density"] == "1"
    assert rows[0]["mean_strength"] == "1"
    assert rows[0]["status"] == TEMPORAL_RIN_STATUS_COMPUTED


def test_temporal_metrics_api_stays_within_stage22c_scope() -> None:
    assert (
        mania.analysis.compute_temporal_rin_metrics
        is compute_temporal_rin_metrics
    )
    assert mania.analysis.write_temporal_rin_csv is write_temporal_rin_csv
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "louvain",
        "fingerprint",
        "PCA",
        "k-means",
        "silhouette",
        "conformation",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source
