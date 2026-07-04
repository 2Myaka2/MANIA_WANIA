from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)


def test_stage20_docs_record_each_accepted_outcome() -> None:
    text = _text()

    for phrase in (
        "Stage 20.A implements",
        "Stage 20.B implements",
        "Stage 20.C implements",
        "Stage 20.D implements",
        "Stage 20.E explicitly defers",
        "Stage 20.F validates",
        "residue_table_{cond}.csv",
        "protein_contact_edges_undirected_{cond}.csv",
        "contacts_perframe_{cond}.csv",
        "edge_semantics.json",
        "mania_manifest.json",
        "mania_residue_library.json",
    ):
        assert phrase in text


def test_stage20_docs_preserve_future_and_wania_boundaries() -> None:
    text = _text()

    for phrase in (
        "does not implement Stage 21",
        "temporal RIN",
        "non-protein inventory",
        "full heterograph",
        "WANIA typed-RIN schema",
        "accepted WANIA JSON contract",
    ):
        assert phrase in text
