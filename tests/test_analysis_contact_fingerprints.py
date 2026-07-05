import csv
from dataclasses import replace
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    CONTACT_FINGERPRINT_STATUS_COMPUTED,
    CONTACT_FINGERPRINT_STATUS_EMPTY_INPUT,
    CONTACT_FINGERPRINT_STATUS_ZERO_FEATURES,
    ContactFingerprintError,
    build_contact_fingerprint_matrix,
    generate_temporal_windows,
    load_temporal_rin_input,
)
from mania.analysis.temporal import TemporalRinInputError
from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing.trajectory_protein_contact_export import (
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "analysis" / "contact_fingerprints.py"
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)

_IDENTITIES = {
    1: ("10", "ALA", "A"),
    2: ("20", "GLY", "A"),
    3: ("30", "LYS", "B"),
}


def _contact_row(
    *,
    frame_index: int,
    residue_index_i: int = 1,
    residue_index_j: int = 2,
    edge_type: str = "vdw",
    time_ps: object = "",
    distance_A: object = 4.0,
    reverse: bool = False,
) -> dict[str, object]:
    if reverse:
        residue_index_i, residue_index_j = residue_index_j, residue_index_i
    resid_i, resname_i, segment_id_i = _IDENTITIES[residue_index_i]
    resid_j, resname_j, segment_id_j = _IDENTITIES[residue_index_j]
    return {
        "condition": "normal",
        "frame_index": frame_index,
        "time_ps": time_ps,
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


def _load_matrix(tmp_path: Path, rows: list[dict[str, object]]):
    temporal_input = load_temporal_rin_input(
        _write_contacts(tmp_path / "contacts_perframe_normal.csv", rows),
        condition="normal",
    )
    return temporal_input, build_contact_fingerprint_matrix(temporal_input)


def test_builds_binary_matrix_with_stable_frame_and_feature_identity(
    tmp_path: Path,
) -> None:
    temporal_input, matrix = _load_matrix(
        tmp_path,
        [
            _contact_row(
                frame_index=100,
                edge_type="vdw",
                time_ps=10.0,
                reverse=True,
            ),
            _contact_row(frame_index=2, edge_type="vdw", time_ps=2.0),
            _contact_row(frame_index=900, edge_type="hbond"),
            _contact_row(frame_index=2, edge_type="hbond", time_ps=2.0),
            _contact_row(
                frame_index=100,
                residue_index_j=3,
                edge_type="salt_bridge",
                time_ps=10.0,
            ),
        ],
    )

    assert matrix.condition == temporal_input.condition == "normal"
    assert matrix.status == CONTACT_FINGERPRINT_STATUS_COMPUTED
    assert matrix.shape == (3, 3)
    assert [frame.row_index for frame in matrix.frames] == [0, 1, 2]
    assert [frame.frame_index for frame in matrix.frames] == [2, 100, 900]
    assert [frame.time_ps for frame in matrix.frames] == [2.0, 10.0, None]
    assert 3 not in [frame.frame_index for frame in matrix.frames]
    assert [feature.column_index for feature in matrix.features] == [0, 1, 2]
    assert [
        (
            feature.residue_index_i,
            feature.residue_index_j,
            feature.edge_type,
        )
        for feature in matrix.features
    ] == [
        (1, 2, "hbond"),
        (1, 2, "vdw"),
        (1, 3, "salt_bridge"),
    ]
    assert [feature.edge_priority_rank for feature in matrix.features] == [
        EDGE_TYPE_PRIORITY.index("hbond"),
        EDGE_TYPE_PRIORITY.index("vdw"),
        EDGE_TYPE_PRIORITY.index("salt_bridge"),
    ]
    assert matrix.features[0].feature_id == "normal:1--2:hbond"
    assert matrix.features[0].resid_i == "10"
    assert matrix.features[0].resid_j == "20"
    assert matrix.values == (
        (1, 1, 0),
        (0, 1, 1),
        (1, 0, 0),
    )
    assert {value for row in matrix.values for value in row} == {0, 1}


def test_matrix_is_independent_of_input_order_orientation_and_distance(
    tmp_path: Path,
) -> None:
    rows = [
        _contact_row(frame_index=20, edge_type="vdw", distance_A=3.0),
        _contact_row(frame_index=2, edge_type="hbond", distance_A=2.5),
        _contact_row(frame_index=20, edge_type="hbond", distance_A=""),
    ]
    _, first = _load_matrix(tmp_path, rows)
    changed_rows = [
        _contact_row(
            frame_index=int(row["frame_index"]),
            edge_type=str(row["edge_type"]),
            distance_A=99.0,
            reverse=True,
        )
        for row in reversed(rows)
    ]
    _, second = _load_matrix(tmp_path, changed_rows)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.values == ((1, 0), (1, 1))
    assert [frame.frame_index for frame in first.frames] == [2, 20]
    assert first.shape == (2, 2)


def test_empty_one_feature_and_representable_zero_feature_inputs(
    tmp_path: Path,
) -> None:
    empty_input, empty = _load_matrix(tmp_path, [])
    assert empty.status == CONTACT_FINGERPRINT_STATUS_EMPTY_INPUT
    assert empty.shape == (0, 0)
    assert empty.frames == empty.features == empty.values == ()

    _, one = _load_matrix(tmp_path, [_contact_row(frame_index=42)])
    assert one.status == CONTACT_FINGERPRINT_STATUS_COMPUTED
    assert one.shape == (1, 1)
    assert one.values == ((1,),)

    frames = (5, 100)
    zero_feature_input = replace(
        empty_input,
        sampled_frame_indexes=frames,
        windows=generate_temporal_windows(
            "normal",
            frames,
            config=empty_input.config,
        ),
    )
    zero_features = build_contact_fingerprint_matrix(zero_feature_input)
    assert zero_features.status == CONTACT_FINGERPRINT_STATUS_ZERO_FEATURES
    assert zero_features.shape == (2, 0)
    assert [frame.frame_index for frame in zero_features.frames] == [5, 100]
    assert [frame.time_ps for frame in zero_features.frames] == [None, None]
    assert zero_features.features == ()
    assert zero_features.values == ((), ())


def test_duplicates_and_inconsistent_frame_times_fail_deterministically(
    tmp_path: Path,
) -> None:
    duplicate_path = _write_contacts(
        tmp_path / "duplicate.csv",
        [
            _contact_row(frame_index=5),
            _contact_row(frame_index=5, reverse=True, distance_A=3.0),
        ],
    )
    with pytest.raises(TemporalRinInputError, match="duplicate frame"):
        load_temporal_rin_input(duplicate_path, condition="normal")

    inconsistent_path = _write_contacts(
        tmp_path / "inconsistent_time.csv",
        [
            _contact_row(frame_index=5, edge_type="hbond", time_ps=10.0),
            _contact_row(frame_index=5, edge_type="vdw", time_ps=11.0),
        ],
    )
    temporal_input = load_temporal_rin_input(
        inconsistent_path,
        condition="normal",
    )
    with pytest.raises(ContactFingerprintError, match="inconsistent time_ps"):
        build_contact_fingerprint_matrix(temporal_input)


def test_public_fingerprint_layer_is_dependency_light_and_stage22d_only() -> None:
    assert (
        mania.analysis.build_contact_fingerprint_matrix
        is build_contact_fingerprint_matrix
    )
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "sklearn",
        "temporal_rin",
        "window_contact_freq",
        "distance_A",
        "PCA",
        "SVD",
        "k-means",
        "silhouette",
        "representative frame",
        "conformation_pca",
        "conformation_labels",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source


def test_stage22d_scope_and_matrix_semantics_are_documented() -> None:
    text = " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in DOC_PATHS
    )

    for phrase in (
        "Stage 22.D",
        "contacts_perframe_{condition}.csv",
        "binary contact fingerprint matrix",
        "sampled frames",
        "EDGE_TYPE_PRIORITY",
        "Values are exactly `1`",
        "does not implement PCA",
        "does not change `temporal_rin_{condition}.csv`",
        "accepted WANIA payload contract",
    ):
        assert phrase in text
