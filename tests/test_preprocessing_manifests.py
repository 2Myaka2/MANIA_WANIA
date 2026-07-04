import json
from pathlib import Path

import mania.preprocessing
from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing import (
    EDGE_SEMANTICS_FILENAME,
    MANIA_MANIFEST_FILENAME,
    MANIA_RESIDUE_LIBRARY_FILENAME,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    build_preprocessing_residue_library,
    write_preprocessing_manifest_artifacts,
    write_preprocessing_protein_contact_artifacts_csv,
    write_preprocessing_residue_tables_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_preprocessing_manifests.py"
)


def node(
    node_id: str,
    *,
    condition: str = "normal",
    residue_index: int = 0,
    resid: str = "10",
    resname: str = "ALA",
    segment_id: str | None = "A",
    coordinates: tuple[float, float, float] | None = (1.0, 2.0, 3.0),
) -> PreprocessingGraphNodeMappingRecord:
    x_ca, y_ca, z_ca = coordinates or (None, None, None)
    return PreprocessingGraphNodeMappingRecord(
        node_id=node_id,
        condition_name=condition,
        residue_index=residue_index,
        residue_id=resid,
        resname=resname,
        segid=segment_id,
        x_ca=x_ca,
        y_ca=y_ca,
        z_ca=z_ca,
    )


def mapping(
    *nodes: PreprocessingGraphNodeMappingRecord,
) -> PreprocessingGraphExportMappingResult:
    return PreprocessingGraphExportMappingResult(nodes=tuple(nodes), edges=())


def contacts(condition: str) -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name=condition,
        options=PreprocessingContactDetectionOptions(contact_selection="protein"),
        frame_results=(
            PreprocessingContactFrameResult(
                condition_name=condition,
                frame_index=0,
                time_ps=0.0,
                contacts=(),
            ),
        ),
        status="computed",
    )


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_writer_emits_three_deterministic_manifests(tmp_path: Path) -> None:
    assert callable(mania.preprocessing.write_preprocessing_manifest_artifacts)
    graph_mapping = mapping(node("normal|A|0|10|ALA"))
    residue_result = write_preprocessing_residue_tables_csv(graph_mapping, tmp_path)
    contact_result = write_preprocessing_protein_contact_artifacts_csv(
        contacts("normal"), tmp_path
    )

    first = write_preprocessing_manifest_artifacts(
        graph_mapping,
        tmp_path,
        residue_tables=residue_result,
        protein_contacts=contact_result,
    )
    first_bytes = {path.name: path.read_bytes() for path in first.paths}
    second = write_preprocessing_manifest_artifacts(
        graph_mapping,
        tmp_path,
        residue_tables=residue_result,
        protein_contacts=contact_result,
    )

    assert first.passed and second.passed
    assert [path.name for path in first.paths] == [
        EDGE_SEMANTICS_FILENAME,
        MANIA_RESIDUE_LIBRARY_FILENAME,
        MANIA_MANIFEST_FILENAME,
    ]
    assert {path.name: path.read_bytes() for path in second.paths} == first_bytes


def test_edge_semantics_reports_only_accepted_implemented_protein_types(
    tmp_path: Path,
) -> None:
    result = write_preprocessing_manifest_artifacts(
        mapping(node("normal|A|0|10|ALA")), tmp_path
    )
    manifest = read_json(tmp_path / EDGE_SEMANTICS_FILENAME)
    edge_types = manifest["edge_types"]
    assert isinstance(edge_types, list)

    assert manifest["edge_priority"] == list(EDGE_TYPE_PRIORITY)
    assert [edge["name"] for edge in edge_types] == list(EDGE_TYPE_PRIORITY)
    assert all(edge["implemented"] for edge in edge_types)
    assert all(edge["protein_protein"] for edge in edge_types)
    assert {
        "salt_bridge",
        "cation_pi",
        "aromatic_pi",
        "residue_contact",
    } <= {edge["canonical_backend_spelling"] for edge in edge_types}
    assert {
        "protein_lipid",
        "protein_glycan",
        "glycan_anchor",
        "protein_ligand",
    }.isdisjoint({edge["name"] for edge in edge_types})
    assert result.passed


def test_run_manifest_references_only_available_portable_artifacts(
    tmp_path: Path,
) -> None:
    graph_mapping = mapping(node("normal|A|0|10|ALA"))
    residue_result = write_preprocessing_residue_tables_csv(graph_mapping, tmp_path)
    contact_result = write_preprocessing_protein_contact_artifacts_csv(
        contacts("normal"), tmp_path
    )

    write_preprocessing_manifest_artifacts(
        graph_mapping,
        tmp_path,
        residue_tables=residue_result,
        protein_contacts=contact_result,
    )
    manifest = read_json(tmp_path / MANIA_MANIFEST_FILENAME)
    filenames = {
        artifact["filename"] for artifact in manifest["produced_artifacts"]
    }

    assert filenames == {
        EDGE_SEMANTICS_FILENAME,
        MANIA_MANIFEST_FILENAME,
        MANIA_RESIDUE_LIBRARY_FILENAME,
        "residue_table_normal.csv",
        "protein_contact_edges_undirected_normal.csv",
        "contacts_perframe_normal.csv",
    }
    assert manifest["provenance"] == {
        "contact_selection": "protein",
        "frame_sampling": None,
        "run_id": None,
        "sampled_frame_counts": None,
    }
    serialized = json.dumps(manifest, sort_keys=True)
    assert str(tmp_path) not in serialized
    for raw_suffix in (".tpr", ".xtc", ".gro", ".dcd", ".psf"):
        assert raw_suffix not in serialized


def test_residue_library_preserves_missing_values_and_reports_conflicts() -> None:
    graph_mapping = mapping(
        node("normal|A|0|10|ALA"),
        node(
            "normal||0|10A|GLY",
            residue_index=0,
            resid="10A",
            resname="GLY",
            segment_id=None,
            coordinates=None,
        ),
    )

    library = build_preprocessing_residue_library(graph_mapping)
    condition = library["conditions"][0]
    qc = condition["qc"]
    missing_residue = condition["residues"][1]

    assert condition["residue_count"] == 2
    assert not qc["passed"]
    assert qc["conflicting_residue_identity_count"] == 1
    assert qc["missing_coordinate_count"] == 1
    assert qc["missing_segment_count"] == 1
    assert qc["missing_structural_attribute_counts"] == {
        "region": 2,
        "rmsf_A": 2,
        "sasa_A2": 2,
        "ss": 2,
        "tm_relative_z": 2,
    }
    assert missing_residue["segment_id"] is None
    assert missing_residue["x_ca"] is None
    assert missing_residue["region"] is None


def test_manifest_module_is_dependency_free_and_wania_agnostic() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "pyarrow",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source
