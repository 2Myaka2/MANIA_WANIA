import csv
import json
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    STATIC_RIN_GRAPH_SCHEMA_VERSION,
    StaticRinGraphError,
    build_static_rin_graph,
    write_static_rin_graph_json,
)
from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing import (
    PROTEIN_CONTACT_EDGE_COLUMNS,
    RESIDUE_TABLE_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "analysis" / "static_rin_graph.py"


def _write_csv(
    path: Path,
    columns: tuple[str, ...],
    rows: list[dict[str, object]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _residue(
    residue_index: int,
    resid: str,
    resname: str,
    segment_id: str,
    *,
    condition: str = "normal",
    x_ca: object = "",
) -> dict[str, object]:
    row: dict[str, object] = {column: "" for column in RESIDUE_TABLE_COLUMNS}
    row.update(
        {
            "condition": condition,
            "residue_index": residue_index,
            "resid": resid,
            "resname": resname,
            "segment_id": segment_id,
            "x_ca": x_ca,
        }
    )
    return row


def _edge(
    residue_index_i: int,
    resid_i: str,
    resname_i: str,
    segment_id_i: str,
    residue_index_j: int,
    resid_j: str,
    resname_j: str,
    segment_id_j: str,
    edge_type: str,
    *,
    condition: str = "normal",
    contact_freq: object = "",
    mean_dist_A: object = "",
    std_dist_A: object = "",
    contact_frame_count: object = "",
    sampled_frame_count: object = "",
) -> dict[str, object]:
    row: dict[str, object] = {
        column: "" for column in PROTEIN_CONTACT_EDGE_COLUMNS
    }
    row.update(
        {
            "condition": condition,
            "residue_index_i": residue_index_i,
            "resid_i": resid_i,
            "resname_i": resname_i,
            "segment_id_i": segment_id_i,
            "residue_index_j": residue_index_j,
            "resid_j": resid_j,
            "resname_j": resname_j,
            "segment_id_j": segment_id_j,
            "edge_type": edge_type,
            "contact_frame_count": contact_frame_count,
            "sampled_frame_count": sampled_frame_count,
            "contact_freq": contact_freq,
            "mean_dist_A": mean_dist_A,
            "std_dist_A": std_dist_A,
            "weight": contact_freq,
        }
    )
    return row


def _write_stage20_support_artifacts(root: Path) -> tuple[Path, Path, Path]:
    edge_semantics = root / "edge_semantics.json"
    edge_semantics.write_text(
        json.dumps({"edge_priority": list(EDGE_TYPE_PRIORITY)}),
        encoding="utf-8",
    )
    manifest = root / "mania_manifest.json"
    manifest.write_text(
        json.dumps({"conditions": ["normal"]}),
        encoding="utf-8",
    )
    library = root / "mania_residue_library.json"
    library.write_text(
        json.dumps({"conditions": [{"condition": "normal"}]}),
        encoding="utf-8",
    )
    return edge_semantics, manifest, library


def _build_fixture_graph(root: Path, *, reverse_rows: bool = False):
    root.mkdir()
    residue_rows = [
        _residue(8, "80", "GLY", "B"),
        _residue(1, "10A", "PHE", "A", x_ca=1.25),
        _residue(4, "20", "LYS", "A"),
    ]
    edge_rows = [
        _edge(
            4,
            "20",
            "LYS",
            "A",
            1,
            "10A",
            "PHE",
            "A",
            "residue_contact",
            contact_freq=0.75,
            mean_dist_A=4.2,
            std_dist_A=0.3,
            contact_frame_count=3,
            sampled_frame_count=4,
        ),
        _edge(
            1,
            "10A",
            "PHE",
            "A",
            4,
            "20",
            "LYS",
            "A",
            "hbond",
            contact_freq=0.5,
            mean_dist_A=3.1,
            std_dist_A=0.2,
            contact_frame_count=2,
            sampled_frame_count=4,
        ),
        _edge(
            8,
            "80",
            "GLY",
            "B",
            4,
            "20",
            "LYS",
            "A",
            "vdw",
        ),
        _edge(
            1,
            "10A",
            "PHE",
            "A",
            4,
            "20",
            "LYS",
            "A",
            "vdw",
            contact_freq=1.0,
            mean_dist_A=3.8,
            std_dist_A=0.1,
            contact_frame_count=4,
            sampled_frame_count=4,
        ),
    ]
    if reverse_rows:
        residue_rows.reverse()
        edge_rows.reverse()
    residue_path = _write_csv(
        root / "residue_table_normal.csv",
        RESIDUE_TABLE_COLUMNS,
        residue_rows,
    )
    edge_path = _write_csv(
        root / "protein_contact_edges_undirected_normal.csv",
        PROTEIN_CONTACT_EDGE_COLUMNS,
        edge_rows,
    )
    semantics, manifest, library = _write_stage20_support_artifacts(root)
    return build_static_rin_graph(
        residue_path,
        edge_path,
        edge_semantics_path=semantics,
        mania_manifest_path=manifest,
        residue_library_path=library,
    )


def test_builds_deterministic_static_graph_and_preserves_stage20_identity(
    tmp_path: Path,
) -> None:
    first = _build_fixture_graph(tmp_path / "first")
    second = _build_fixture_graph(tmp_path / "second", reverse_rows=True)

    assert first.to_dict() == second.to_dict()
    assert first.condition == "normal"
    assert [node.residue_index for node in first.nodes] == [1, 4, 8]
    assert [node.id for node in first.nodes] == ["normal:1", "normal:4", "normal:8"]
    assert first.nodes[0].resid == "10A"
    assert first.nodes[0].resname == "PHE"
    assert first.nodes[0].segment_id == "A"
    assert first.nodes[0].x_ca == 1.25
    assert [
        (edge.residue_index_i, edge.residue_index_j) for edge in first.edges
    ] == [(1, 4), (4, 8)]
    assert first.edges[0].source == "normal:1"
    assert first.edges[0].target == "normal:4"
    assert first.edges[0].resid_i == "10A"
    assert first.edges[0].resid_j == "20"


def test_reuses_priority_selects_primary_and_preserves_all_typed_metrics(
    tmp_path: Path,
) -> None:
    graph = _build_fixture_graph(tmp_path / "bundle")
    payload = graph.to_dict()
    edge = payload["edges"][0]

    assert payload["edge_priority"] == list(EDGE_TYPE_PRIORITY)
    assert edge["edge_type"] == edge["primary_edge_type"] == "hbond"
    assert edge["all_edge_types"] == ["hbond", "vdw", "residue_contact"]
    assert edge["n_edge_types"] == 3
    assert edge["contact_freq"] == edge["weight"] == 0.5
    assert edge["mean_dist_A"] == 3.1
    assert edge["std_dist_A"] == 0.2
    assert [item["edge_type"] for item in edge["interactions"]] == [
        "hbond",
        "vdw",
        "residue_contact",
    ]
    assert [item["contact_freq"] for item in edge["interactions"]] == [
        0.5,
        1.0,
        0.75,
    ]
    assert edge["id"] == "normal:1--4:hbond"


def test_missing_optional_metrics_are_null_and_export_is_portable_and_stable(
    tmp_path: Path,
) -> None:
    graph = _build_fixture_graph(tmp_path / "bundle")
    missing_metrics_edge = graph.to_dict()["edges"][1]

    assert missing_metrics_edge["contact_freq"] is None
    assert missing_metrics_edge["weight"] is None
    assert missing_metrics_edge["mean_dist_A"] is None
    assert missing_metrics_edge["std_dist_A"] is None

    output = tmp_path / "analysis" / "normal" / "graph.json"
    assert write_static_rin_graph_json(graph, output) == output
    first_bytes = output.read_bytes()
    write_static_rin_graph_json(graph, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert output.read_bytes() == first_bytes
    assert payload["schema_version"] == STATIC_RIN_GRAPH_SCHEMA_VERSION
    assert payload["condition"] == "normal"
    assert payload["directed"] is False
    assert payload["n_nodes"] == 3
    assert payload["n_edges"] == 2
    assert payload["metadata"]["source_artifacts"] == {
        "edge_semantics": "edge_semantics.json",
        "mania_manifest": "mania_manifest.json",
        "protein_contact_edges": "protein_contact_edges_undirected_normal.csv",
        "residue_library": "mania_residue_library.json",
        "residue_table": "residue_table_normal.csv",
    }
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_rejects_cross_artifact_identity_or_priority_mismatch(
    tmp_path: Path,
) -> None:
    residue_path = _write_csv(
        tmp_path / "residue_table_normal.csv",
        RESIDUE_TABLE_COLUMNS,
        [_residue(1, "10", "ALA", "A"), _residue(2, "20", "GLY", "A")],
    )
    mismatched_edge = _edge(
        1,
        "WRONG",
        "ALA",
        "A",
        2,
        "20",
        "GLY",
        "A",
        "vdw",
        contact_freq=0.5,
    )
    edge_path = _write_csv(
        tmp_path / "protein_contact_edges_undirected_normal.csv",
        PROTEIN_CONTACT_EDGE_COLUMNS,
        [mismatched_edge],
    )

    with pytest.raises(StaticRinGraphError, match="identity does not match"):
        build_static_rin_graph(residue_path, edge_path)

    mismatched_edge["resid_i"] = "10"
    _write_csv(edge_path, PROTEIN_CONTACT_EDGE_COLUMNS, [mismatched_edge])
    semantics = tmp_path / "edge_semantics.json"
    semantics.write_text(json.dumps({"edge_priority": ["vdw"]}), encoding="utf-8")
    with pytest.raises(StaticRinGraphError, match="priority does not match"):
        build_static_rin_graph(
            residue_path,
            edge_path,
            edge_semantics_path=semantics,
        )


def test_public_api_is_dependency_free_and_wania_agnostic() -> None:
    assert mania.analysis.build_static_rin_graph is build_static_rin_graph
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "networkx",
        "numpy",
        "pandas",
        "pyarrow",
        "mania.wania",
        "wania_graph_payload",
        "centrality",
        "community",
        "temporal",
        "conformation",
    ):
        assert forbidden not in source
