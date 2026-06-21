from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "preprocessing_graph_reference_mismatches.md"
CROSS_REFERENCE_PATHS = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_export.md",
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md",
)


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_graph_reference_mismatch_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_doc_records_stage_and_reference_semantics() -> None:
    text = doc_text()
    compact = normalized(text)

    for phrase in (
        "Stage 14.4a",
        "MANIA_analysis_v1_2",
        "v1.1 reference artifacts are historical",
        "Cell 5 adds interaction priority",
        "Cell 12 fixes temporal RIN export",
        "temporal RIN fix is reference context",
    ):
        assert phrase in compact


def test_doc_records_stage_14_3b_comparison_behavior() -> None:
    text = doc_text()
    compact = normalized(text)

    for phrase in (
        "Stage 14.3b",
        "Stage 14.3a readiness validator",
        "nodes.csv",
        "corrected edges.csv",
        "graph.json",
        "CSV values compare exactly as strings",
        "graph.json comparison is structural, not byte-level",
        "deterministic JSON-safe mismatch",
        "does not decide whether a mismatch is expected",
    ):
        assert phrase in compact


def test_doc_preserves_contact_edges_artifact_boundary() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "contact_edges.csv is an aggregate contacts table from Stage 13.",
        "backend graph edges.csv is a Stage 14 graph artifact.",
        (
            "Stage 14 graph comparison compares backend graph edges.csv, "
            "not Stage 13 contact_edges.csv."
        ),
    ):
        assert phrase in compact


def test_doc_lists_node_edge_and_graph_mismatch_categories() -> None:
    text = doc_text()

    for phrase in (
        "missing or extra node rows",
        "different `resid` identity representation",
        "different `resname` formatting",
        "different `condition` naming",
        "degree",
        "betweenness",
        "pagerank",
        "community_id",
        "x_ca",
        "tm_relative_z",
        "rmsf_A",
        "sasa_A2",
        "ss",
        "missing or extra edge rows",
        "different edge endpoint identity",
        "different primary `edge_type`",
        "different `all_edge_types`",
        "different `n_edge_types`",
        "different `contact_freq`",
        "different `mean_dist_A`",
        "n_episodes",
        "mean_lifetime_frames",
        "formation_count",
        "window_cv",
        "top-level count mismatch",
        "schema version mismatch",
        "condition mismatch",
        "missing or extra node items",
        "missing or extra edge items",
    ):
        assert phrase in text


def test_doc_records_corrected_multi_type_edge_schema() -> None:
    text = doc_text()

    for phrase in (
        "edge_type",
        "all_edge_types",
        "n_edge_types",
        "EDGE_TYPE_PRIORITY",
        "hbond",
        "salt_bridge",
        "hydrophobic",
        "vdw",
        "pipe-separated string",
        "row-preserving graph artifacts",
    ):
        assert phrase in text


def test_doc_records_generic_residue_contact_boundary() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "residue_contact",
        "valid for MVP generated graph artifacts",
        "not automatically a bug",
        "requires interpretation",
        "known semantic difference",
        "future scientific validation",
    ):
        assert phrase in compact


def test_doc_distinguishes_non_bugs_from_investigations() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "What is not a bug by itself",
        "JSON indentation or key-order differences",
        "empty optional graph metric fields",
        "absence of temporal RIN artifacts",
        "What requires investigation",
        "mismatched required identity fields",
        "schema version mismatch when matching schema is required",
        "unexpected loss of `edge_type`, `all_edge_types`, or `n_edge_types`",
        "mismatch in `contact_freq` or `mean_dist_A`",
    ):
        assert phrase in compact


def test_doc_preserves_future_boundaries() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "Temporal RIN export and temporal RIN comparison remain future scope",
        "Stage 14.4a documents expected mismatches",
        "Stage 14.4b remains final graph export boundary docs before workflow",
        "no CLI/workflow integration",
        "no temporal RIN export or comparison",
        "no biological interpretation",
        "no real-data CI",
        "does not change comparison logic",
        "does not add expected mismatch classification code",
        "semantic-difference classification code",
    ):
        assert phrase in compact


def test_required_docs_cross_reference_mismatch_doc() -> None:
    for path in CROSS_REFERENCE_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "docs/preprocessing_graph_reference_mismatches.md" in text
        assert "Stage 14.4a" in text
