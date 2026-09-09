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
        section for section in sections if section.startswith("Stage 25 ")
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
    assert re.search(r"Stage 25\.G[^.;]*\bis complete\b", text)
    assert re.search(r"FastAPI\s+(?:remains|is)\s+postponed", text)
    assert "Stage 25 is complete" in text
    assert "Stage 25 as a whole remains incomplete" not in text


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


def test_readme_stage25c_inventory_and_scientific_boundary() -> None:
    text = " ".join(readme_text().split())
    assert re.search(r"Stage 25\.C[^.;]*\bis complete\b", text)
    assert "<output>/artifact_inventory.json" in text
    assert "<output>/analysis/artifact_inventory.json" in text
    assert "default size-only mode" in text
    assert "--artifact-checksum-mode none" in text
    assert "exact byte sizes without reading contents for integrity metadata" in text
    assert "SHA256 is explicit opt-in" in text
    assert "streams every inventoried input and output in bounded chunks" in text
    assert "--artifact-checksum-mode sha256" in text
    assert re.search(
        r"Stage 25\.D unified technical artifact validation is complete", text
    )
    assert "Stage 25 is complete" in text
    assert "FastAPI remains postponed" in text


def test_current_status_documents_completed_stage25g_and_stage26_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (
        "README.md", "AGENTS.md", "docs/architecture.md", "docs/code_review.md",
        "docs/decisions.md", "docs/git_workflow.md",
    ):
        text = " ".join((root / name).read_text(encoding="utf-8").split())
        for stage in ("A", "B", "C"):
            assert re.search(rf"Stage 25\.{stage}[^.;]*is complete", text)
        assert "Stage 25.D unified technical artifact validation is complete" in text
        assert re.search(r"Stage 25\.E[^.;]*observation-only[^.;]*is complete", text)
        assert re.search(r"Stage 25\.F[^.;]*FAIR² bridge[^.;]*is complete", text)
        assert re.search(r"Stage 25\.G[^.;]*acceptance[^.;]*is complete", text)
        assert not re.search(r"Stage 25\.[EFG][^.;]*is next", text)
        assert "scientific PBC protocol remains unresolved" in text
        assert "no internal minimum-image correction" in text
        assert "Stage 25 is complete" in text
        assert "FastAPI remains postponed" in text
        assert "Stage 25 as a whole remains incomplete" not in text
        assert "Stage 26 is complete" in text
        assert re.search(r"Stage 26\.A and 26\.B are accepted", text)
        assert "Stage 27 physical-time sampling/window engine is next" in text
        assert "no Stage 27 sampling or window behavior is implemented yet" in text
        assert (
            "scientific contract is frozen except for concrete NAMD condition" in text
        )
        assert "labels, which remain unresolved" in text
        assert "Dataset v1.0 remains unreleased" in text
        assert "Requested physical parameters remain inert" in text
        assert "WANIA is unchanged" in text
        assert "Analysis Dataset-context propagation is outside Stage 26" in text
    assert "mania artifacts validate out --scope preprocessing" in readme_text()
    assert "docs/stage25_final_acceptance.md" in readme_text()


def test_readme_links_stage25f_reproducibility_and_software_reference() -> None:
    text = readme_text()
    for path in ("docs/reproducibility.md", "docs/software_release_reference.md"):
        assert re.search(rf"\[[^\]]+\]\({re.escape(path)}\)", text)


def test_readme_documents_completed_runtime_pbc_artifacts_and_boundary():
    text = " ".join(readme_text().split())
    for path in ("<output>/runtime_metadata.json", "<output>/pbc_audit.json",
                 "<output>/analysis/runtime_metadata.json"):
        assert path in text
    assert "There is no new PBC CLI option" in text
    assert "`undeclared` automatically" in text
    assert "scientific PBC status remains `unresolved`" in text
    assert (
        "Failed scientific runs retain the existing Stage 25.B/C metadata boundary"
        in text
    )
    assert "docs/pbc_runtime_metadata.md" in text
