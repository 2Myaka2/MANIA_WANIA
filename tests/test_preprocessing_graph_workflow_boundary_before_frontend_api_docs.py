from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = (
    REPO_ROOT
    / "docs"
    / "preprocessing_graph_workflow_boundary_before_frontend_api.md"
)
LINKED_DOC_PATHS = (
    REPO_ROOT / "docs" / "preprocessing_graph_workflow_contract.md",
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md",
)


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_boundary_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_stage_15_10_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "Stage 15.10",
        "frontend/API",
        "workflow boundary",
    ):
        assert phrase in text


def test_accepted_stage_15_sequence_is_documented() -> None:
    text = doc_text()

    for stage in (
        "15.1",
        "15.2",
        "15.3",
        "15.4",
        "15.5",
        "15.6",
        "15.7",
        "15.8",
        "15.9",
        "15.10",
    ):
        assert stage in text


def test_cli_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "mania preprocessing run-graph-export",
        "--manifest",
        "--output",
        "opt-in",
        "no broad CLI framework",
    ):
        assert phrase in text


def test_accepted_graph_artifacts_are_documented() -> None:
    text = doc_text()

    for phrase in (
        "graph/nodes.csv",
        "graph/edges.csv",
        "graph/graph.json",
        "reports/graph_diagnostics_report.json",
        "reports/graph_reference_comparison.json",
    ):
        assert phrase in text


def test_non_produced_outputs_are_documented() -> None:
    text = doc_text()

    for phrase in (
        "rg/rg_timeseries.csv",
        "contacts/contacts_perframe.csv",
        "contacts/contact_edges.csv",
        "not produced by Stage 15 workflow CLI",
    ):
        assert phrase in text


def test_contact_edges_and_backend_graph_edges_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "Stage 13 `contact_edges.csv`",
        "aggregate contacts table",
        "backend graph edges.csv",
    ):
        assert phrase in text


def test_corrected_edge_schema_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "edge_type",
        "all_edge_types",
        "n_edge_types",
    ):
        assert phrase in text


def test_reference_comparison_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "disabled by default",
        "explicit reference artifact paths",
        "no automatic reference artifact search",
        "no notebook execution",
        "MANIA_analysis_v1_2",
        "v1.1 historical",
        "no programmatic expected mismatch classification",
    ):
        assert phrase in text


def test_local_smoke_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_RUN_LOCAL_MD_SMOKE",
        "local_md/manifests/napi2b_10ns.yaml",
        "skipped by default",
        "not default CI",
        "Raw MD files must not be committed",
    ):
        assert phrase in text


def test_optional_dependency_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "MDAnalysis",
        "optional scientific dependencies",
        "Default CI does not require real MD data",
        "Importing or CLI help does not require MDAnalysis",
    ):
        assert phrase in text


def test_future_frontend_api_boundary_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "not yet a frontend/API contract",
        "WANIA",
        "adapter",
        "payload",
        "future scope",
    ):
        assert phrase in text


def test_temporal_rin_future_scope_is_documented() -> None:
    text = doc_text()

    for phrase in (
        "temporal RIN",
        "future scope",
    ):
        assert phrase in text


def test_existing_docs_link_to_new_boundary_doc() -> None:
    for path in LINKED_DOC_PATHS:
        compact = normalized(path.read_text(encoding="utf-8"))
        assert (
            "docs/preprocessing_graph_workflow_boundary_before_frontend_api.md"
            in compact
        )
