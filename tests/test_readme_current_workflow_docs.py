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


def test_current_status_documents_completed_stage29_and_stage30_boundary() -> None:
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
        assert "Stage 27 physical-time sampling/window engine is complete" in text
        assert "Stage 27 is complete" in text
        assert "Stage 28 is complete" in text
        if name == "docs/architecture.md":
            assert "Stage 29.A molecular partner identification is implemented" in text
            assert "Stage 29.A is accepted" in text
            assert "Stage 29.B protein-lipid per-frame geometry is implemented" in text
            assert "Stage 29 remains incomplete" not in text
            assert "Stage 29.B is accepted" in text
            assert "Stage 29.C protein-glycan per-frame geometry is implemented" in text
            assert "Stage 29.C is accepted" in text
            assert "specialized_contact_window_contract.md" in text
            assert "protein_glycan_contact_contract.md" in text
            assert "molecular_partner_identification_contract.md" in text
            assert "protein_lipid_contact_contract.md" in text
            assert (
                "No lipid/glycan contact calculations or workflow integration" in text
            )
        assert "Stage 29 is complete" in text
        assert "pre-canonical" in text
        assert (
            "Stage 30 canonical mapping / biological annotations "
            "is next and has not started"
            in text
        )
        # Preserve accepted A/B/C history alongside completed D integration.
        if name == "docs/architecture.md":
            assert re.search(r"Stage 28\.A is accepted\b", text)
            assert "contact episode/lifetime engine" in text
            assert re.search(r"Stage 28\.B[^.;]*is accepted\b", text)
            assert re.search(r"Stage 28\.C[^.;]*is implemented\b", text)
            assert "Stage 28.C is accepted" in text
            assert "Stage 28.D workflow integration and acceptance is complete" in text
            assert "protein_edges_by_window_source.csv" in text
            assert "requiring Stage 30 canonical mapping" in text
            assert "adds zero trajectory passes" in text
        assert "95% exclusion policy remains Stage 32" in text
        assert (
            "scientific contract is frozen except for concrete NAMD condition" in text
        )
        assert "labels, which remain unresolved" in text
        assert "Dataset v1.0 remains unreleased" in text
        assert "Requested physical parameters remain inert" not in text
        assert "WANIA is unchanged" in text
        assert "Analysis Dataset-context propagation is outside Stage 26" in text
    assert "mania artifacts validate out --scope preprocessing" in readme_text()
    assert "docs/stage25_final_acceptance.md" in readme_text()


def test_stage29a_contract_documents_identification_and_scientific_boundary():
    text = " ".join((REPO_ROOT / "docs/molecular_partner_identification_contract.md")
                    .read_text(encoding="utf-8").split())
    for phrase in (
        "Stage 28 is complete",
        "Stage 29.A topology/entity identification is implemented",
        "Stage 29.A is accepted",
        "Stage 29.B protein-lipid per-frame geometry is implemented",
        "Stage 29 remains incomplete",
        "Stage 29.B is accepted",
        "Stage 29.C protein-glycan per-frame geometry is implemented",
        "Stage 29.D is next",
        "consumes accepted lipid partner identity directly",
        "without reclassifying or regrouping partners",
        "Classification is supplied metadata",
        "MANIA never classifies a lipid/glycan merely from resname patterns",
        "protein_residue_indexes",
        "external_metadata",
        "carrier_link_bond=None",
        "They are NOT cross-system canonical molecular identifiers",
        "Stage 29.C/29.D",
        "no distance calculation",
        "main protein graph changes",
        "The main dynRIN remains protein-only",
    ):
        assert phrase in text


def test_stage29b_contract_preserves_accepted_checkpoint_status():
    text = " ".join((REPO_ROOT / "docs/protein_lipid_contact_contract.md")
                    .read_text(encoding="utf-8").split())
    for phrase in (
        "Stage 28 is complete",
        "Stage 29.A is accepted",
        "Stage 29.B protein-lipid per-frame geometry is implemented",
        "Stage 29 remains incomplete",
        "Stage 29.B is accepted",
        "Stage 29.C protein-glycan per-frame geometry is implemented",
        "Stage 29.D is next",
        "Stage 29.D owns window aggregation",
    ):
        assert phrase in text


def test_stage29c_contract_preserves_accepted_checkpoint_status():
    text = " ".join((REPO_ROOT / "docs/protein_glycan_contact_contract.md")
                    .read_text(encoding="utf-8").split())
    for phrase in (
        "Stage 28 is complete",
        "Stage 29.A is accepted",
        "Stage 29.B is accepted",
        "Stage 29.C protein-glycan per-frame geometry is implemented",
        "Stage 29 remains incomplete",
        "Stage 29.D is next",
    ):
        assert phrase in text


def test_stage28c_source_table_docs_preserve_canonical_publication_boundary():
    text = " ".join((REPO_ROOT / "docs/protein_edge_window_table_contract.md")
                    .read_text(encoding="utf-8").split())
    for phrase in (
        "Stage 27 is complete", "Stage 28.A is accepted", "Stage 28.B is accepted",
        "Stage 28.C source-indexed table/export is implemented",
        "Stage 28 is complete",
        "Stage 28.D integration and real-data acceptance is complete",
        "protein_edges_by_window_source.csv", "source-indexed, canonical-ready",
        "This file is not yet Dataset v1.0 release-ready",
        "Stage 30 canonical mapping is required before release publication",
        "UniProt O95436 canonical numbering", "condition=None",
        "SEGID is not universally equivalent to a canonical biological chain "
        "identifier",
        "Window completeness remains in `temporal_execution.json`",
        "Unified validation delegates to `read_dataset_protein_edge_window_csv` once",
        "header-only table",
        "There is no analysis source-table role or input",
    ):
        assert phrase in text


def test_readme_links_stage25f_reproducibility_and_software_reference() -> None:
    text = readme_text()
    for path in ("docs/reproducibility.md", "docs/software_release_reference.md"):
        assert re.search(rf"\[[^\]]+\]\({re.escape(path)}\)", text)


def test_readme_documents_completed_runtime_pbc_artifacts_and_boundary():
    text = " ".join(readme_text().split())
    for path in (
        "<output>/runtime_metadata.json",
        "<output>/pbc_audit.json",
        "<output>/analysis/runtime_metadata.json",
    ):
        assert path in text
    assert "There is no new PBC CLI option" in text
    assert "`undeclared` automatically" in text
    assert "scientific PBC status remains `unresolved`" in text
    assert (
        "Failed scientific runs retain the existing Stage 25.B/C metadata boundary"
        in text
    )
    assert "docs/pbc_runtime_metadata.md" in text


def test_stage29d_contract_documents_formulas_metadata_and_release_boundary():
    text = " ".join(
        (REPO_ROOT / "docs/specialized_contact_window_contract.md")
        .read_text(encoding="utf-8")
        .split()
    )
    for phrase in (
        "Stage 29.D: PASS",
        "Stage 29: COMPLETE",
        "Classification is explicit metadata",
        "MANIA never auto-classifies lipids or glycans from resname",
        "Connectivity groups already classified components only",
        "molecular_partner_metadata_path",
        "mania.molecular_partner_metadata.v0.1",
        "molecular_partner_catalog.json",
        "protein_lipid_contacts_by_window_source.csv",
        "protein_glycan_contacts_by_window_source.csv",
        "compute_window_contact_episodes",
        "ordinary positive frames only",
        "standard_summary_excluded=True",
        "There is no specialized `edge_weight`",
        "header-only",
        "PRE-CANONICAL",
        "UniProt O95436",
        "Stage 30",
        "Stage 32",
        "no internal minimum-image correction",
        "condition",
        "checksum",
        "one",
        "source-topology-local",
    ):
        assert phrase in text
