import re
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


def test_readme_documents_frame_sampling() -> None:
    text = readme_text()

    for phrase in (
        "Frame Sampling",
        "--frame-start",
        "--frame-stop",
        "--frame-stride",
        "--max-frames",
        "computes every trajectory frame",
        "frame_time_ps",
        "not stride",
        "Sampling affects Rg, contacts, graph outputs",
        "optional scientific CSV exports",
        "does not change the WANIA object JSON",
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


def test_readme_documents_stage25_software_identity() -> None:
    text = " ".join(readme_text().split())

    assert re.search(
        r"Stage 25\b[^.]*reproducibility and publication hardening",
        text,
        flags=re.IGNORECASE,
    )
    for phrase in ("get_software_identity", "mania --version", "_version.py"):
        assert phrase in text
    assert re.search(r"FastAPI\s+(?:remains|is)\s+postponed", text)


def test_readme_does_not_assign_minimal_api_to_stage25() -> None:
    sections = re.split(r"(?m)^## ", readme_text())
    current_status = next(
        section for section in sections if section.startswith("Stage 25.A ")
    )
    text = " ".join(current_status.split()).lower()

    assert "reproducibility and publication hardening" in text
    assert "minimal api" not in text


def test_readme_documents_completed_stage25b_and_separate_provenance() -> None:
    text = " ".join(readme_text().split())
    assert re.search(r"Stage 25\.B[^.]*\bis complete\b", text)
    assert "<output>/run_provenance.json" in text
    assert "<output>/analysis/run_provenance.json" in text
    assert "successful and covered failed analysis" in text.lower()
    assert "successful and covered failed preprocessing" in text.lower()
    for record in ("RunMeta", "mania_manifest.json", "analysis/extended_metrics.json"):
        assert record in text
    assert "mania analyze" in text
    assert re.search(r"Stage 25\.C[^.;]*\bis (?:the )?next\b", text)
    assert re.search(r"FastAPI\s+(?:remains|is)\s+postponed", text)
    assert re.search(r"Stage 25 as a whole remains incomplete", text)
    assert not re.search(r"Stage 25(?: as a whole)?\s+is complete\b", text)


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
