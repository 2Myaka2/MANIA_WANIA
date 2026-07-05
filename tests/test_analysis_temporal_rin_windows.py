import csv
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    TEMP_MIN_FREQ,
    TEMP_STEP,
    TEMP_WINDOW,
    TEMPORAL_RIN_STATUS_COMPUTED,
    TEMPORAL_RIN_STATUS_EMPTY_INPUT,
    TEMPORAL_RIN_STATUS_EMPTY_WINDOW,
    TEMPORAL_RIN_STATUS_NO_CONTACTS_PASSING_THRESHOLD,
    TemporalRinConfig,
    TemporalRinInput,
    TemporalRinInputError,
    build_temporal_rin_window_graphs,
    generate_temporal_windows,
    load_temporal_rin_input,
)
from mania.preprocessing.trajectory_protein_contact_export import (
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "analysis" / "temporal_rin_windows.py"
)
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)


def _contact_row(
    *,
    frame_index: int,
    edge_type: str = "vdw",
    residue_index_i: int = 1,
    residue_index_j: int = 2,
    distance_A: object = 4.0,
    reverse: bool = False,
) -> dict[str, object]:
    identities = {
        1: ("10", "ALA", "A"),
        2: ("20", "GLY", "A"),
        3: ("30", "LYS", "B"),
        4: ("40", "PHE", "B"),
        5: ("50", "VAL", "C"),
        6: ("60", "SER", "C"),
    }
    if reverse:
        residue_index_i, residue_index_j = residue_index_j, residue_index_i
    resid_i, resname_i, segment_id_i = identities[residue_index_i]
    resid_j, resname_j, segment_id_j = identities[residue_index_j]
    return {
        "condition": "normal",
        "frame_index": frame_index,
        "time_ps": frame_index * 2.0,
        "residue_index_i": residue_index_i,
        "resid_i": resid_i,
        "resname_i": resname_i,
        "segment_id_i": segment_id_i,
        "residue_index_j": residue_index_j,
        "resid_j": resid_j,
        "resname_j": resname_j,
        "segment_id_j": segment_id_j,
        "edge_type": edge_type,
        "distance_A": distance_A,
    }


def _write_contacts(
    path: Path,
    rows: list[dict[str, object]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=PROTEIN_CONTACT_PERFRAME_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _load_and_build(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    config: TemporalRinConfig | None = None,
):
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        rows,
    )
    temporal_input = load_temporal_rin_input(
        path,
        condition="normal",
        config=config,
    )
    return build_temporal_rin_window_graphs(temporal_input)


def test_builds_typed_window_graph_with_sampled_frame_denominator(
    tmp_path: Path,
) -> None:
    config = TemporalRinConfig(window_size=4, step_size=4, min_frequency=0.5)
    bundle = _load_and_build(
        tmp_path,
        [
            _contact_row(
                frame_index=900,
                edge_type="hydrophobic",
                residue_index_i=3,
                residue_index_j=4,
            ),
            _contact_row(
                frame_index=100,
                edge_type="vdw",
                distance_A=6.0,
            ),
            _contact_row(
                frame_index=2,
                edge_type="vdw",
                distance_A=4.0,
                reverse=True,
            ),
            _contact_row(
                frame_index=250,
                edge_type="hbond",
                distance_A=4.0,
            ),
            _contact_row(
                frame_index=2,
                edge_type="hbond",
                distance_A=2.0,
            ),
            _contact_row(
                frame_index=100,
                edge_type="hbond",
                distance_A="",
            ),
        ],
        config=config,
    )

    assert bundle.condition == "normal"
    assert bundle.status == TEMPORAL_RIN_STATUS_COMPUTED
    assert bundle.config is config
    assert len(bundle.windows) == 1
    graph = bundle.windows[0]
    assert (
        graph.condition,
        graph.window_id,
        graph.frame_start,
        graph.frame_end,
        graph.sampled_frame_count,
        graph.frame_indexes,
        graph.status,
    ) == (
        "normal",
        0,
        2,
        900,
        4,
        (2, 100, 250, 900),
        TEMPORAL_RIN_STATUS_COMPUTED,
    )
    assert graph.sampled_frame_count != graph.frame_end - graph.frame_start + 1
    assert [node.residue_index for node in graph.nodes] == [1, 2]
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert (edge.residue_index_i, edge.residue_index_j) == (1, 2)
    assert edge.primary_edge_type == "hbond"
    assert edge.all_edge_types == ("hbond", "vdw")
    assert edge.window_contact_freq == edge.contact_freq == edge.weight == 0.75
    hbond, vdw = edge.interactions
    assert (
        hbond.observed_frame_count,
        hbond.sampled_frame_count,
        hbond.window_contact_freq,
    ) == (3, 4, 0.75)
    assert (
        hbond.mean_dist_A,
        hbond.std_dist_A,
        hbond.min_dist_A,
        hbond.max_dist_A,
    ) == (3.0, 1.0, 2.0, 4.0)
    assert (
        vdw.observed_frame_count,
        vdw.sampled_frame_count,
        vdw.window_contact_freq,
        vdw.mean_dist_A,
        vdw.std_dist_A,
    ) == (2, 4, 0.5, 5.0, 1.0)
    assert "hydrophobic" not in edge.all_edge_types


def test_inclusive_threshold_and_no_passing_contact_status(tmp_path: Path) -> None:
    inclusive = _load_and_build(
        tmp_path,
        [
            _contact_row(frame_index=0, residue_index_i=1, residue_index_j=2),
            _contact_row(frame_index=10, residue_index_i=3, residue_index_j=4),
        ],
        config=TemporalRinConfig(
            window_size=2,
            step_size=2,
            min_frequency=0.5,
        ),
    )
    assert [edge.window_contact_freq for edge in inclusive.windows[0].edges] == [
        0.5,
        0.5,
    ]

    dropped = _load_and_build(
        tmp_path,
        [
            _contact_row(frame_index=0, residue_index_i=1, residue_index_j=2),
            _contact_row(frame_index=10, residue_index_i=3, residue_index_j=4),
        ],
        config=TemporalRinConfig(
            window_size=2,
            step_size=2,
            min_frequency=0.75,
        ),
    )
    graph = dropped.windows[0]
    assert graph.status == TEMPORAL_RIN_STATUS_NO_CONTACTS_PASSING_THRESHOLD
    assert graph.nodes == ()
    assert graph.edges == ()


def test_uses_overlapping_windows_and_emits_partial_trailing_window(
    tmp_path: Path,
) -> None:
    bundle = _load_and_build(
        tmp_path,
        [
            _contact_row(frame_index=0),
            _contact_row(frame_index=10),
            _contact_row(frame_index=20),
            _contact_row(frame_index=30),
        ],
        config=TemporalRinConfig(
            window_size=3,
            step_size=2,
            min_frequency=0.0,
        ),
    )

    assert [window.window_id for window in bundle.windows] == [0, 1]
    assert [window.frame_indexes for window in bundle.windows] == [
        (0, 10, 20),
        (20, 30),
    ]
    assert [window.sampled_frame_count for window in bundle.windows] == [3, 2]
    assert [window.edges[0].observed_frame_count for window in bundle.windows] == [
        3,
        2,
    ]
    assert [window.edges[0].window_contact_freq for window in bundle.windows] == [
        1.0,
        1.0,
    ]


def test_default_config_one_frame_and_header_only_input(tmp_path: Path) -> None:
    one_frame = _load_and_build(
        tmp_path,
        [_contact_row(frame_index=42, distance_A="")],
    )

    assert one_frame.config.to_dict() == {
        "window_size": TEMP_WINDOW,
        "step_size": TEMP_STEP,
        "min_frequency": TEMP_MIN_FREQ,
    }
    assert len(one_frame.windows) == 1
    graph = one_frame.windows[0]
    assert (graph.frame_start, graph.frame_end, graph.sampled_frame_count) == (
        42,
        42,
        1,
    )
    assert graph.edges[0].window_contact_freq == 1.0
    assert graph.edges[0].primary_interaction.mean_dist_A is None
    assert graph.edges[0].primary_interaction.std_dist_A is None

    empty = _load_and_build(tmp_path, [])
    assert empty.status == TEMPORAL_RIN_STATUS_EMPTY_INPUT
    assert empty.windows == ()


def test_window_with_no_rows_is_retained_as_empty_graph() -> None:
    config = TemporalRinConfig()
    windows = generate_temporal_windows("normal", [5], config=config)
    temporal_input = TemporalRinInput(
        condition="normal",
        config=config,
        rows=(),
        sampled_frame_indexes=(5,),
        windows=windows,
    )

    bundle = build_temporal_rin_window_graphs(temporal_input)

    assert bundle.status == TEMPORAL_RIN_STATUS_COMPUTED
    assert len(bundle.windows) == 1
    assert bundle.windows[0].status == TEMPORAL_RIN_STATUS_EMPTY_WINDOW
    assert bundle.windows[0].nodes == ()
    assert bundle.windows[0].edges == ()


def test_stage22a_duplicate_rejection_prevents_frequency_inflation(
    tmp_path: Path,
) -> None:
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [
            _contact_row(frame_index=5),
            _contact_row(frame_index=5, reverse=True, distance_A=3.0),
        ],
    )

    with pytest.raises(TemporalRinInputError, match="duplicate frame"):
        load_temporal_rin_input(path, condition="normal")


def test_window_graphs_are_deterministic_and_public(tmp_path: Path) -> None:
    rows = [
        _contact_row(frame_index=10, edge_type="vdw"),
        _contact_row(frame_index=0, edge_type="hbond", reverse=True),
        _contact_row(
            frame_index=10,
            edge_type="salt_bridge",
            residue_index_i=3,
            residue_index_j=4,
        ),
    ]
    first = _load_and_build(tmp_path, rows)
    second = _load_and_build(tmp_path, list(reversed(rows)))

    assert first.to_dict() == second.to_dict()
    assert (
        mania.analysis.build_temporal_rin_window_graphs
        is build_temporal_rin_window_graphs
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "temporal_rin_{condition}.csv",
        "centrality",
        "modularity",
        "fingerprint",
        "k-means",
        "silhouette",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source


def test_stage22b_scope_and_threshold_are_documented() -> None:
    text = " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in DOC_PATHS
    )

    for phrase in (
        "Stage 22.B",
        "sampled_frame_count",
        "window_contact_freq >= min_frequency",
        "EDGE_TYPE_PRIORITY",
        "does not compute temporal graph metrics",
        "export `temporal_rin_{condition}.csv`",
        "WANIA payload contract remain unchanged",
    ):
        assert phrase in text
