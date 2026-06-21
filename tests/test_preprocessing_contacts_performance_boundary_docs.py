from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_contacts_performance_boundary.md"
)
CONTACTS_MVP_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md"
CONTACTS_EXPORT_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_export.md"
PREPROCESSING_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
UPDATED_DOC_PATHS = (
    CONTACTS_MVP_PATH,
    CONTACTS_EXPORT_PATH,
    PREPROCESSING_BOUNDARY_PATH,
    ADR_PATH,
)


def boundary_text() -> str:
    return BOUNDARY_DOC_PATH.read_text(encoding="utf-8")


def test_contacts_performance_boundary_doc_exists() -> None:
    assert BOUNDARY_DOC_PATH.is_file()


def test_performance_boundary_doc_mentions_current_mvp_scope() -> None:
    text = boundary_text().lower()

    for phrase in (
        "contacts computation",
        "contacts export",
        "contacts validation",
        "contacts comparison",
    ):
        assert phrase in text


def test_performance_boundary_doc_mentions_dependency_boundary() -> None:
    text = boundary_text()
    lower_text = text.lower()

    assert "default CI" in text
    assert "MDAnalysis remains optional" in text
    assert "real md data is not required by default" in lower_text


def test_performance_boundary_doc_forbids_hard_timing_benchmarks() -> None:
    text = boundary_text().lower()

    for phrase in (
        "no hard timing thresholds",
        "not a benchmark report",
        "lightweight sanity checks",
    ):
        assert phrase in text


def test_performance_boundary_doc_describes_stage_13_5b() -> None:
    text = boundary_text()
    lower_text = text.lower()

    assert "Stage 13.5b" in text
    assert "lightweight performance sanity checks" in lower_text
    assert "no hard timing benchmarks" in lower_text


def test_performance_boundary_doc_preserves_local_scientific_boundary() -> None:
    text = boundary_text().lower()

    for phrase in (
        "local scientific tests are opt-in",
        "local scientific tests are not benchmark gates",
    ):
        assert phrase in text


def test_performance_boundary_doc_preserves_graph_boundary() -> None:
    text = boundary_text().lower()

    for phrase in (
        "graph export remains future",
        "contact_edges.csv is not backend graph edges.csv",
    ):
        assert phrase in text


def test_existing_docs_reference_stage_13_5a_boundary_doc() -> None:
    for path in UPDATED_DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "Stage 13.5a" in text

    for path in (
        CONTACTS_MVP_PATH,
        CONTACTS_EXPORT_PATH,
        PREPROCESSING_BOUNDARY_PATH,
    ):
        text = path.read_text(encoding="utf-8")
        assert "docs/preprocessing_contacts_performance_boundary.md" in text


def test_existing_docs_preserve_no_benchmark_boundary() -> None:
    combined_text = "\n".join(
        path.read_text(encoding="utf-8") for path in UPDATED_DOC_PATHS
    ).lower()

    for phrase in (
        "no performance tests",
        "benchmark tests",
        "hard timing",
        "mdanalysis remains optional",
        "default ci remains independent",
        "graph remains future",
    ):
        assert phrase in combined_text
