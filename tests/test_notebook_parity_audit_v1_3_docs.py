from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "notebook_parity_audit_v1_3.md"


def normalized_doc_text() -> str:
    return " ".join(DOC_PATH.read_text(encoding="utf-8").split())


def test_notebook_parity_audit_v1_3_exists() -> None:
    assert DOC_PATH.is_file()


def test_notebook_parity_audit_v1_3_records_required_scope() -> None:
    text = normalized_doc_text()

    for phrase in (
        "MANIA_preprocessing_v1_2",
        "MANIA_analysis_v1_3",
        "Stage 16.2",
        "Stage 16.3",
        "Stage 16.4",
        "Stage 16.5",
        "Stage 16.6",
        "Stage 16.7",
        "Stage 16.8",
        "Stage 16.9",
        "Stage 16.10",
        "Stage 16.11",
        "Stage 16.12",
        "representative Cα coordinates",
        "not full Kabsch parity",
        "InteractionAccumulator",
        "build_atom_cache",
        "backbone",
        "EDGE_PRIORITY",
        "aromatic_pi",
        "cation_pi",
        "analysis graph metrics",
        "WANIA frontend sample",
        "formal statistics deferred",
        "temporal RIN deferred",
        "conformational clustering deferred",
        "YaDisk notebook/reference only",
        "no real MD data in default CI",
    ):
        assert phrase in text
