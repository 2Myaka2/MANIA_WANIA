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


def test_stage24_docs_record_completion_workflow_and_boundaries() -> None:
    text = _text()

    for phrase in (
        "Stage 24.E validation and acceptance",
        "Completed Stage 24 acceptance checklist",
        "Completed through Stage 24.E",
        "Stage 24 closed",
        "mania analyze",
        "already generated Stage 20 preprocessing artifacts",
        "separate from preprocessing",
        "separate from WANIA",
        "does not read raw trajectories",
        "does not rerun preprocessing",
        "does not invoke WANIA payload assembly",
        "does not write `wania_graph_payload.json`",
        "--input ./mania_output",
        "--output ./mania_output",
        "--condition normal",
        "--condition tumor",
        "--enable-pca",
        "--clustering-basis pca",
        "Stage 25 has not started",
    ):
        assert phrase in text


def test_stage24_docs_record_pca_and_clustering_semantics() -> None:
    text = _text()

    for phrase in (
        "PCA is optional",
        "PCA is disabled by default",
        "PCA requires explicit enablement",
        "ContactFingerprintMatrix.values",
        "centered NumPy SVD",
        "component signs are stabilized deterministically",
        "Degenerate PCA inputs emit honest statuses",
        "No fake PCA values are emitted",
        "No NaN or Infinity values are emitted",
        "Fingerprint clustering remains default",
        "PCA clustering is explicit opt-in",
        "No silent clustering fallback occurs",
        "Fingerprint and PCA clustering answer different scientific questions",
        "not scientifically interchangeable",
        "direct binary residue-contact-pattern similarity",
        "proximity in reduced PCA feature space",
        "Representative frames use the active clustering space",
    ):
        assert phrase in text


def test_stage24_docs_record_output_layout_and_manifest_policy() -> None:
    text = _text()

    for phrase in (
        "<output>/analysis/",
        "extended_metrics.json",
        "analysis/extended_metrics.json",
        "comparison.csv",
        "stats.csv",
        "graph.json",
        "centrality_{condition}.csv",
        "communities_{condition}.csv",
        "region_enrichment_{condition}.csv",
        "temporal_rin_{condition}.csv",
        "conformation_pca_{condition}.csv",
        "conformation_labels_{condition}.csv",
        "mania.extended_metrics.v0.1",
        "MANIA-only",
        "AnalyzeRunResult",
        "current-run artifact ownership",
        "does not parse stdout",
        "does not scan arbitrary output files",
        "references only current-run artifacts",
        "paths relative to the run output root",
        "does not inline scientific tables",
        "stdout summary",
        "persisted Stage 24.D manifest",
    ):
        assert phrase in text


def test_stage24_docs_record_status_terms_and_notebook_non_claims() -> None:
    text = _text()

    for phrase in (
        "`pca_unavailable`",
        "`status = not_requested`",
        "Default-disabled PCA is not a failed numerical attempt",
        "single-condition",
        "`not_applicable`",
        "skipped/unavailable statuses",
        "PCA input preparation is aligned with centered, non-standardized",
        "Repository PCA uses centered NumPy SVD",
        "Repository clustering uses deterministic internal k-means",
        "Exact notebook PCA parity",
        "exact sklearn KMeans parity",
        "exact notebook label parity",
        "not claimed",
    ):
        assert phrase in text

    for forbidden_claim in (
        "exact scikit-learn PCA parity is claimed",
        "exact sklearn KMeans parity is claimed",
        "exact notebook label parity is claimed",
        "notebook label parity is achieved",
    ):
        assert forbidden_claim not in text


def test_stage24_acceptance_checklist_preserves_wania_and_future_boundaries(
) -> None:
    text = _text()

    for phrase in (
        "- [x] WANIA JSON is unchanged.",
        "- [x] WANIA runtime schema is unchanged.",
        "- [x] WANIA adapter/writer behavior is unchanged.",
        "- [x] WANIA capability derivation is unchanged.",
        "- [x] WANIA artifact mapping is unchanged.",
        "- [x] WANIA fixtures are unchanged.",
        "- [x] `wania_graph_payload.json` is unchanged.",
        "- [x] Stage 20 schemas are unchanged.",
        "- [x] Stage 21 schemas and algorithms are unchanged.",
        "- [x] Stage 22 schemas remain compatible.",
        "- [x] Stage 23 MANIA/WANIA boundary is preserved.",
        "- [x] Stage 25 has not started.",
        "- [x] No API, Docker, database, frontend, or worker work was added.",
        "- [x] No raw/local/generated MD outputs were committed.",
        "No scikit-learn, SciPy, or pandas dependency was added",
        "analysis/extended_metrics.json` is implemented",
        "PCA intent and computation status are distinguished",
    ):
        assert phrase in text
