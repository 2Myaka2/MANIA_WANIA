from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)


def _text() -> str:
    content = "\n".join(
        path.read_text(encoding="utf-8") for path in DOC_PATHS
    )
    return " ".join(content.split())


def test_stage21_docs_record_each_accepted_outcome() -> None:
    text = _text()

    for phrase in (
        "Stage 21.A",
        "graph.json",
        "Stage 21.B",
        "centrality_{condition}.csv",
        "Stage 21.C",
        "communities_{condition}.csv",
        "greedy_modularity_unweighted",
        "Stage 21.D",
        "region_enrichment_{condition}.csv",
        "raw p-value",
        "Stage 21.E",
        "comparison.csv",
        "stats.csv",
        "skipped_unsupported_scope",
        "Stage 21.F",
        "validation",
        "cross-artifact",
    ):
        assert phrase in text


def test_stage21_docs_preserve_deferred_and_wania_boundaries() -> None:
    text = _text()

    for phrase in (
        "Stage 22 temporal RIN is not implemented",
        "Conformation/PCA/k-means/silhouette artifacts are not implemented",
        "WANIA typed-RIN schema is not implemented",
        "Full heterograph/non-protein inventory is not implemented",
        "Frontend/API/Docker/database/production API work is not implemented",
        "accepted WANIA JSON contract remains unchanged",
    ):
        assert phrase in text

    for forbidden_claim in (
        "Louvain is implemented",
        "FDR-BH is implemented",
        "p-value methods exist in stats.csv",
        "Stage 22 is implemented",
        "WANIA typed-RIN schema is implemented",
    ):
        assert forbidden_claim not in text
