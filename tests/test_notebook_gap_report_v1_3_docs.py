from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "notebook_gap_report_v1_3.md"


def normalized_doc_text() -> str:
    return " ".join(DOC_PATH.read_text(encoding="utf-8").split())


def test_notebook_gap_report_v1_3_exists() -> None:
    assert DOC_PATH.is_file()


def test_notebook_gap_report_v1_3_records_stage_16_8_scope_and_gaps() -> None:
    text = normalized_doc_text()

    for phrase in (
        "MANIA_preprocessing_v1_2",
        "MANIA_analysis_v1_3",
        "Cα coordinates",
        "representative coordinates",
        "full Kabsch parity",
        "backbone edge type",
        "EDGE_PRIORITY",
        "implemented in Stage 16.6",
        "BACKBONE_MAX_CA_DIST_A = 4.5",
        "690 continuous protein residues",
        "approximately 689 backbone edges",
        "InteractionAccumulator",
        "InteractionAccumulator is implemented in Stage 16.7",
        "build_atom_cache",
        "build_atom_cache is implemented in Stage 16.8",
        "Stage 16.6",
        "Per-frame contact parity remains deferred to Stage 16.9",
        (
            "Richer aromatic/cation-pi chemistry remains deferred to "
            "Stage 16.10"
        ),
        "Analysis metrics parity remains deferred to Stage 16.11",
        "no new neighbor-search backend",
        "accepted output schemas",
        "WANIA object JSON contract remain unchanged",
    ):
        assert phrase in text
