import csv
import json
from pathlib import Path

from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing import (
    EDGE_SEMANTICS_FILENAME,
    MANIA_MANIFEST_FILENAME,
    MANIA_RESIDUE_LIBRARY_FILENAME,
    PROTEIN_CONTACT_EDGE_COLUMNS,
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
    RESIDUE_TABLE_COLUMNS,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    write_preprocessing_manifest_artifacts,
    write_preprocessing_protein_contact_artifacts_csv,
    write_preprocessing_residue_tables_csv,
)

STAGE20_FILENAMES = {
    "residue_table_normal.csv",
    "protein_contact_edges_undirected_normal.csv",
    "contacts_perframe_normal.csv",
    EDGE_SEMANTICS_FILENAME,
    MANIA_MANIFEST_FILENAME,
    MANIA_RESIDUE_LIBRARY_FILENAME,
}
DEFERRED_NON_PROTEIN_TYPES = {
    "protein_lipid",
    "protein_glycan",
    "glycan_anchor",
    "protein_ligand",
}


def _mapping() -> PreprocessingGraphExportMappingResult:
    return PreprocessingGraphExportMappingResult(
        nodes=(
            PreprocessingGraphNodeMappingRecord(
                node_id="normal|A|1|10A|PHE",
                condition_name="normal",
                residue_index=1,
                residue_id="10A",
                resname="PHE",
                segid="A",
                x_ca=1.0,
                y_ca=2.0,
                z_ca=3.0,
            ),
            PreprocessingGraphNodeMappingRecord(
                node_id="normal|B|4|20|LYS",
                condition_name="normal",
                residue_index=4,
                residue_id="20",
                resname="LYS",
                segid="B",
                x_ca=None,
                y_ca=None,
                z_ca=None,
            ),
        ),
        edges=(),
    )


def _pair(*, reverse: bool, distance: float) -> PreprocessingContactPairResult:
    endpoints = (
        (4, "20", "LYS", "B", 1, "10A", "PHE", "A")
        if reverse
        else (1, "10A", "PHE", "A", 4, "20", "LYS", "B")
    )
    return PreprocessingContactPairResult(
        source_residue_index=endpoints[0],
        source_residue_id=endpoints[1],
        source_resname=endpoints[2],
        source_segid=endpoints[3],
        target_residue_index=endpoints[4],
        target_residue_id=endpoints[5],
        target_resname=endpoints[6],
        target_segid=endpoints[7],
        minimum_distance=distance,
    )


def _contacts() -> PreprocessingConditionContactsResult:
    frames = (
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=0,
            time_ps=0.0,
            contacts=(_pair(reverse=False, distance=3.0),),
        ),
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=2,
            time_ps=5.0,
            contacts=(_pair(reverse=True, distance=5.0),),
        ),
        PreprocessingContactFrameResult(
            condition_name="normal", frame_index=4, time_ps=10.0
        ),
        PreprocessingContactFrameResult(
            condition_name="normal", frame_index=6, time_ps=15.0
        ),
    )
    return PreprocessingConditionContactsResult(
        condition_name="normal",
        options=PreprocessingContactDetectionOptions(contact_selection="protein"),
        frame_results=frames,
        status="computed",
    )


def _write_bundle(output_dir: Path) -> dict[str, bytes]:
    mapping = _mapping()
    residue_tables = write_preprocessing_residue_tables_csv(mapping, output_dir)
    contacts = write_preprocessing_protein_contact_artifacts_csv(
        _contacts(), output_dir
    )
    manifests = write_preprocessing_manifest_artifacts(
        mapping,
        output_dir,
        residue_tables=residue_tables,
        protein_contacts=contacts,
    )
    assert residue_tables.passed and contacts.passed and manifests.passed
    assert {path.name for path in output_dir.iterdir()} == STAGE20_FILENAMES
    return {
        path.name: path.read_bytes()
        for path in sorted(output_dir.iterdir())
    }


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_stage20_artifacts_are_cross_consistent_and_deterministic(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_bytes = _write_bundle(first_dir)
    second_bytes = _write_bundle(second_dir)

    assert first_bytes == second_bytes

    residue_header, residue_rows = _read_csv(
        first_dir / "residue_table_normal.csv"
    )
    edge_header, edge_rows = _read_csv(
        first_dir / "protein_contact_edges_undirected_normal.csv"
    )
    perframe_header, perframe_rows = _read_csv(
        first_dir / "contacts_perframe_normal.csv"
    )

    assert residue_header == RESIDUE_TABLE_COLUMNS
    assert edge_header == PROTEIN_CONTACT_EDGE_COLUMNS
    assert perframe_header == PROTEIN_CONTACT_PERFRAME_COLUMNS
    assert [(row["residue_index"], row["resid"]) for row in residue_rows] == [
        ("1", "10A"),
        ("4", "20"),
    ]
    assert residue_rows[1]["segment_id"] == "B"
    assert all(residue_rows[1][field] == "" for field in ("x_ca", "y_ca", "z_ca"))
    assert all(
        row[field] == ""
        for row in residue_rows
        for field in ("region", "tm_relative_z", "rmsf_A", "sasa_A2", "ss")
    )

    edge = edge_rows[0]
    assert (edge["residue_index_i"], edge["residue_index_j"]) == ("1", "4")
    assert (edge["resid_i"], edge["resid_j"]) == ("10A", "20")
    assert edge["edge_type"] == "residue_contact"
    assert edge["contact_frame_count"] == "2"
    assert edge["sampled_frame_count"] == "4"
    assert edge["contact_freq"] == edge["weight"] == "0.5"
    assert edge["mean_dist_A"] == "4.0"
    assert edge["std_dist_A"] == "1.0"
    assert [row["frame_index"] for row in perframe_rows] == ["0", "2"]
    assert [row["time_ps"] for row in perframe_rows] == ["0.0", "5.0"]
    assert all(row["residue_index_i"] == "1" for row in perframe_rows)
    assert all(row["residue_index_j"] == "4" for row in perframe_rows)
    assert [row["distance_A"] for row in perframe_rows] == ["3.0", "5.0"]


def test_stage20_manifests_validate_semantics_provenance_and_deferral(
    tmp_path: Path,
) -> None:
    _write_bundle(tmp_path)
    semantics = _read_json(tmp_path / EDGE_SEMANTICS_FILENAME)
    manifest = _read_json(tmp_path / MANIA_MANIFEST_FILENAME)
    library = _read_json(tmp_path / MANIA_RESIDUE_LIBRARY_FILENAME)

    edge_types = semantics["edge_types"]
    assert semantics["edge_priority"] == list(EDGE_TYPE_PRIORITY)
    assert [edge["name"] for edge in edge_types] == list(EDGE_TYPE_PRIORITY)
    assert all(
        edge["canonical_backend_spelling"] == edge["name"]
        for edge in edge_types
    )
    assert all(edge["implemented"] and edge["protein_protein"] for edge in edge_types)
    assert all(edge["known_limitations"] for edge in edge_types)
    assert set(semantics["deferred_non_protein_edge_types"]) == (
        DEFERRED_NON_PROTEIN_TYPES
    )
    assert DEFERRED_NON_PROTEIN_TYPES.isdisjoint(
        {edge["name"] for edge in edge_types}
    )

    produced = manifest["produced_artifacts"]
    assert {artifact["filename"] for artifact in produced} == STAGE20_FILENAMES
    assert all(
        Path(artifact["filename"]).name == artifact["filename"]
        for artifact in produced
    )
    assert manifest["provenance"] == {
        "contact_selection": "protein",
        "frame_sampling": None,
        "run_id": None,
        "sampled_frame_counts": None,
    }
    serialized_manifest = json.dumps(manifest, sort_keys=True)
    assert str(tmp_path) not in serialized_manifest
    assert "non_protein_nodes" not in serialized_manifest
    assert "np_contact_edges" not in serialized_manifest
    assert not any(
        suffix in serialized_manifest
        for suffix in (".tpr", ".xtc", ".gro", ".cpt", ".edr", ".dcd", ".psf")
    )

    condition = library["conditions"][0]
    assert condition["condition"] == "normal"
    assert [residue["residue_index"] for residue in condition["residues"]] == [1, 4]
    assert condition["residues"][1]["segment_id"] == "B"
    assert condition["residues"][1]["x_ca"] is None
    assert condition["qc"]["missing_coordinate_count"] == 1
    assert condition["qc"]["missing_segment_count"] == 0
    assert condition["qc"]["missing_structural_attribute_counts"] == {
        "region": 2,
        "rmsf_A": 2,
        "sasa_A2": 2,
        "ss": 2,
        "tm_relative_z": 2,
    }
