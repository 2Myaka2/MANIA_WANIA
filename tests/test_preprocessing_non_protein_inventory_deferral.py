import json
from pathlib import Path

from mania.preprocessing import (
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    build_edge_semantics_manifest,
    build_preprocessing_run_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md"
GAP_MATRIX_PATH = REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md"


def _mapping() -> PreprocessingGraphExportMappingResult:
    return PreprocessingGraphExportMappingResult(
        nodes=(
            PreprocessingGraphNodeMappingRecord(
                node_id="normal|A|0|10|ALA",
                condition_name="normal",
                residue_index=0,
                residue_id="10",
                resname="ALA",
                segid="A",
                x_ca=1.0,
                y_ca=2.0,
                z_ca=3.0,
            ),
        ),
        edges=(),
    )


def test_stage_20e_docs_explicitly_defer_both_optional_artifacts() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SCOPE_PATH, GAP_MATRIX_PATH)
    )

    for artifact in (
        "non_protein_nodes_{cond}.csv",
        "np_contact_edges_{cond}.csv",
    ):
        assert artifact in text
    assert "Explicitly deferred at Stage 20.E" in text
    assert "production emits neither" in text
    assert "not a WANIA render requirement" in text


def test_stage_20e_artifacts_are_not_reported_as_produced_or_implemented() -> None:
    run_manifest = build_preprocessing_run_manifest(_mapping())
    produced_filenames = {
        artifact["filename"] for artifact in run_manifest["produced_artifacts"]
    }
    serialized_manifest = json.dumps(run_manifest, sort_keys=True)

    assert not any(name.startswith("non_protein_nodes_") for name in produced_filenames)
    assert not any(name.startswith("np_contact_edges_") for name in produced_filenames)
    assert "non_protein_nodes" not in serialized_manifest
    assert "np_contact_edges" not in serialized_manifest

    semantics = build_edge_semantics_manifest()
    implemented_types = {edge["name"] for edge in semantics["edge_types"]}
    deferred_types = set(semantics["deferred_non_protein_edge_types"])
    expected_deferred = {
        "protein_lipid",
        "protein_glycan",
        "glycan_anchor",
        "protein_ligand",
    }

    assert expected_deferred == deferred_types
    assert expected_deferred.isdisjoint(implemented_types)
