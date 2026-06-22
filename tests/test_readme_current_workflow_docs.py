from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"


def readme_text() -> str:
    return README_PATH.read_text(encoding="utf-8")


def test_readme_mentions_accepted_cli_command() -> None:
    text = readme_text()

    for phrase in (
        "mania preprocessing run-graph-export",
        "--manifest",
        "--output",
        "--verbose",
    ):
        assert phrase in text


def test_readme_documents_local_raw_data_layout() -> None:
    text = readme_text()

    for phrase in (
        "local_md",
        "manifests",
        "napi2b_10ns.yaml",
        "normal",
        "tumor",
        "trajectory.xtc",
    ):
        assert phrase in text


def test_readme_includes_local_development_install_commands() -> None:
    text = readme_text()

    for phrase in (
        "python -m venv .venv",
        'python -m pip install -e ".[dev,md]"',
    ):
        assert phrase in text


def test_readme_includes_manifest_readiness_check() -> None:
    assert (
        "check_preprocessing_graph_workflow_manifest_readiness" in readme_text()
    )


def test_readme_documents_expected_graph_outputs() -> None:
    text = readme_text()

    for phrase in (
        "graph/nodes.csv",
        "graph/edges.csv",
        "graph/graph.json",
        "reports/graph_diagnostics_report.json",
    ):
        assert phrase in text


def test_readme_documents_non_produced_outputs() -> None:
    text = readme_text()

    for phrase in (
        "temporal RIN",
        "WANIA",
    ):
        assert phrase in text


def test_readme_documents_optional_scientific_csv_exports() -> None:
    text = readme_text()

    for phrase in (
        "--export-scientific-csvs",
        "--export-rg-timeseries",
        "--export-contact-edges",
        "--export-contacts-perframe",
        "rg/rg_timeseries.csv",
        "contacts/contact_edges.csv",
        "contacts/contacts_perframe.csv",
        "contacts_perframe.csv requires --export-contacts-perframe",
        "Stage 13 `contact_edges.csv`",
        "aggregate contacts table",
        "graph/edges.csv",
        "backend graph edge table",
    ):
        assert phrase in text


def test_readme_documents_raw_data_boundary() -> None:
    text = readme_text()

    for phrase in (
        "*.tpr",
        "*.xtc",
        "*.gro",
        "*.dcd",
        "*.psf",
        "must not be committed",
    ):
        assert phrase in text


def test_readme_documents_frontend_api_future_scope() -> None:
    text = readme_text()

    for phrase in (
        "FastAPI",
        "Stage 16",
        "frontend",
        "API",
        "future scope",
    ):
        assert phrase in text


def test_readme_links_wania_object_json_payload_contract() -> None:
    text = readme_text()

    for phrase in (
        "Stage 16.0 documents the future WANIA object JSON payload contract",
        "object JSON",
        "protein-agnostic",
        "graph/graph.json",
        "docs/wania_object_json_payload_contract.md",
    ):
        assert phrase in text


def test_readme_documents_protein_agnostic_boundary() -> None:
    text = readme_text()

    for phrase in (
        "protein-agnostic",
        "NaPi2b is only the current local sample dataset",
        "protein_id",
        "protein_name",
        "run_name",
        "condition_names",
        "Stage 16",
        "future scope",
        "docs/wania_api_protein_agnostic_boundary.md",
    ):
        assert phrase in text
