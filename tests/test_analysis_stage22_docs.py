from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)


def _text() -> str:
    content = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)
    return " ".join(content.split())


def test_stage22_docs_record_each_accepted_outcome_and_validation() -> None:
    text = _text()

    for phrase in (
        "Stage 22.A",
        "TEMP_WINDOW = 10",
        "TEMP_STEP = 10",
        "TEMP_MIN_FREQ = 0.25",
        "contacts_perframe_{condition}.csv",
        "Stage 22.B",
        "window_contact_freq",
        "sampled_frame_count",
        "Stage 22.C",
        "temporal_rin_{condition}.csv",
        "greedy_modularity_unweighted",
        "Stage 22.D",
        "binary contact fingerprint",
        "Stage 22.E",
        "conformation_pca_{condition}.csv",
        "pca_unavailable",
        "Stage 22.F",
        "deterministic dependency-free k-means",
        "conformation_labels_{condition}.csv",
        "Stage 22.G",
        "cross-artifact",
        "schema",
        "deterministic",
    ):
        assert phrase in text


def test_stage22_docs_preserve_pca_clustering_and_future_boundaries() -> None:
    text = _text()

    for phrase in (
        "NumPy is now an accepted direct dependency",
        "computed PCA is available only when",
        "enable_pca=True",
        "does not use PCA coordinates",
        "does not claim notebook PCA",
        "Stage 24.B",
        "clustering_basis=\"pca\"",
        "`fingerprint` remains the default",
        "PCA clustering uses all successfully computed components",
        "PCA is not silently enabled",
        "no silent fallback to fingerprints",
        "PCA-based clustering over the accepted MANIA projection artifact",
        "does not claim exact notebook parity",
        "WANIA temporal animation",
        "WANIA conformation UI",
        "WANIA typed-RIN schema",
        "API, Docker, database, frontend, and production workers",
        "cross-protein comparison",
        "non-protein heterograph support",
        "accepted WANIA payload contract remains unchanged",
        "Stage 25 Minimal API is postponed",
    ):
        assert phrase in text

    for forbidden_claim in (
        "notebook PCA-to-k-means parity is achieved",
        "Louvain is implemented",
        "WANIA temporal UI is implemented",
        "WANIA conformation UI is implemented",
        "mania analyze is implemented",
        "extended_metrics.json is implemented",
        "Stage 25 Minimal API is implemented",
    ):
        assert forbidden_claim not in text
