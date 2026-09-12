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
        if name == "docs/architecture.md":
            assert "Stage 30.A local canonical reference is implemented" in text
            assert "Stage 30.A is accepted" in text
            assert "canonical_napi2b_reference_contract.md" in text
            assert "Stage 30.B explicit source mapping is implemented" in text
            assert "canonical_residue_mapping_contract.md" in text
            assert "Stage 30 is complete" in text
            assert "Stage 30.B is accepted" in text
            assert (
                "Stage 30.C canonicalized intermediate tables are implemented" in text
            )
            assert (
                "Stage 30.D biological annotations and workflow integration "
                "are complete" in text
            )
            assert "canonical_window_table_contract.md" in text
            assert "biological_annotation_contract.md" in text
            assert "Stage 30 adds zero trajectory passes" in text
            assert "carries no mapping authority" in text
        assert "Stage 30 is complete" in text
        if name == "docs/architecture.md":
            assert (
                "Stage 31.A compatible canonical replica/window grouping is implemented"
                in text
            )
            assert "replica_aggregation_contract.md" in text
            assert "Stage 31 is complete" in text
            assert (
                "Stage 31.B pure canonical protein-edge replica aggregation "
                "is implemented"
                in text
            )
            assert "Stage 31.A is accepted" in text
            assert "replica_protein_edge_aggregation_contract.md" in text
            assert (
                "Stage 31.C specialized lipid/glycan replica aggregation is implemented"
                in text
            )
            assert "Stage 31.B is accepted" in text
            assert "Stage 31.C is accepted" in text
            assert "replica_specialized_aggregation_contract.md" in text
            assert "Historical Stage 30 checkpoint wording" in text
        else:
            assert "Stage 31 is complete" in text
        if name == "docs/architecture.md":
            assert (
                "Stage 32.A QC model, severity and release-decision contract "
                "is implemented" in text
            )
            assert "dataset_qc_contract.md" in text
            assert "Stage 32 remains incomplete" in text
            assert "Stage 32.B hard QC is next" in text
        else:
            # These unchanged files retain the accepted Stage 31 checkpoint.
            assert "Stage 32 Dataset QC / exclusion is next and has not started" in text
        assert "Stage 34 multi-engine pilot" in text
        assert "Stage 35 full production remain later" in text
        assert "Stage 33 publication export remains later" in text
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


def test_stage32a_contract_documents_current_status():
    text = " ".join(
        (REPO_ROOT / "docs/dataset_qc_contract.md")
        .read_text(encoding="utf-8").split()
    )
    assert "Stage 31 is complete" in text
    assert "Stage 32.A QC contract is implemented" in text
    assert "Stage 32 remains incomplete" in text
    assert "Stage 32.B hard QC is next" in text


def test_stage31a_contract_documents_current_status():
    text = " ".join(
        (REPO_ROOT / "docs/replica_aggregation_contract.md")
        .read_text(encoding="utf-8").split()
    )
    assert "Stage 30 is complete" in text
    assert "Stage 31.A group/window contract is implemented" in text
    assert "Stage 31 is complete" in text
    assert "Stage 31.A is accepted" in text
    assert (
        "Stage 31.B pure canonical protein-edge replica aggregation is implemented"
        in text
    )
    assert (
        "Stage 31.C specialized lipid/glycan replica aggregation is implemented"
        in text
    )
    assert "Stage 31.B is accepted" in text
    assert "Stage 31.C is accepted" in text


def test_stage31b_contract_documents_current_status():
    text = " ".join(
        (REPO_ROOT / "docs/replica_protein_edge_aggregation_contract.md")
        .read_text(encoding="utf-8").split()
    )
    assert "Stage 30 is complete" in text
    assert "Stage 31.A is accepted" in text
    assert (
        "Stage 31.B pure canonical protein-edge replica aggregation is implemented"
        in text
    )
    assert "Stage 31 is complete" in text
    assert (
        "Stage 31.C specialized lipid/glycan replica aggregation is implemented"
        in text
    )
    assert "Stage 31.B is accepted" in text
    assert "Stage 31.C is accepted" in text


def test_stage31c_contract_documents_current_status():
    text = " ".join(
        (REPO_ROOT / "docs/replica_specialized_aggregation_contract.md")
        .read_text(encoding="utf-8").split()
    )
    assert "Stage 30 is complete" in text
    assert "Stage 31.A is accepted" in text
    assert "Stage 31.B is accepted" in text
    assert (
        "Stage 31.C specialized lipid/glycan replica aggregation is implemented"
        in text
    )
    assert "Stage 31 is complete" in text
    assert "Stage 31.C is accepted" in text


def test_stage31d_workflow_documents_explicit_controls_and_reconstruction(tmp_path):
    from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest

    text = (REPO_ROOT / "docs/replica_aggregation_workflow.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(text.split())
    for phrase in (
        "Stage 31.D: PASS", "Stage 31: COMPLETE", "zero trajectory passes",
        "canonical", "explicit control metadata", "ddof=1", "empty CSV cell",
        "Stage 32", "No directory scan", "exact models", "deterministic CSV bytes",
        "Input family present", "condition=null", "header-only", "MDAnalysis",
        "protein_edges_by_window_canonical_replica_aggregation.csv",
        "protein_lipid_contacts_by_window_canonical_replica_aggregation.csv",
        "protein_glycan_contacts_by_window_canonical_replica_aggregation.csv",
        "dfe614cada83b91cf8015df89c1ea551960b1113",
    ):
        assert phrase in normalized
    example_section = text.split("## Exact synthetic manifest example", 1)[1]
    example = re.search(r"```json\n(.*?)\n```", example_section, re.DOTALL)
    assert example is not None
    path = tmp_path / "replica_aggregation_manifest.json"
    path.write_text(example.group(1), encoding="utf-8")
    manifest = read_replica_aggregation_manifest(path)
    assert manifest.groups[0].spec.condition is None
    assert len(manifest.groups[0].lipid_correspondences.correspondences) == 1
    assert len(manifest.groups[0].glycan_correspondences.correspondences) == 1
    assert "mania dataset aggregate-replicas" in readme_text()
    assert "docs/replica_aggregation_workflow.md" in readme_text()


def test_stage30a_contract_documents_offline_reference_and_mapping_boundary():
    text = " ".join(
        (REPO_ROOT / "docs/canonical_napi2b_reference_contract.md")
        .read_text(encoding="utf-8").split()
    )
    for phrase in (
        "Stage 29 is complete", "Stage 30.A canonical reference is implemented",
        "Stage 30.A is accepted", "Stage 30.B explicit source mapping is implemented",
        "Stage 30 is complete", "Stage 30.B is accepted",
        "Stage 30.C canonicalized intermediate tables are implemented",
        "Stage 30.D biological annotations/integration is complete",
        "uses the local pinned reference as validation authority",
        "no live UniProt dependency was introduced",
        "canonical_residue_mapping_contract.md",
        "NaPi2b-only contract", "O95436-1", "NPT2B_HUMAN", "SLC34A2", "Homo sapiens",
        "690 aa", "2010-11-30", "16C21D07D36DC8B416EA72769F0B0280",
        "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9",
        "uniprotkb:O95436-1:sequence-v3", "slc34a2_o95436_reference.json",
        "importlib.resources", "Production runs never fetch UniProt",
        "It is not a live dependency", "ASCII sequence bytes with no newline",
        "source_resid != canonical_residue_number",
        "Numeric equality carries zero mapping authority", "source_resid = 311",
        "explicit, validated Stage 30.B mapping record", "canonical = source + offset",
        "uppercase standard three-letter amino-acid code",
        "CanonicalReferenceReadError", "Stage 30.C applies validated mapping",
        "Stage 30.D adds biological annotations",
        "unified validation, analysis, dependencies, and WANIA remain unchanged",
    ):
        assert phrase in text

def test_stage30b_contract_documents_explicit_mapping_and_application_status():
    text = " ".join(
        (REPO_ROOT / "docs/canonical_residue_mapping_contract.md")
        .read_text(encoding="utf-8").split()
    )
    for phrase in (
        "Stage 29 is complete", "Stage 30.A is accepted",
        "Stage 30.B explicit source mapping is implemented",
        "Stage 30 is complete", "Stage 30.B is accepted",
        "Stage 30.C canonicalized intermediate tables are implemented",
        "Stage 30.D biological annotations/integration is complete",
        "uniprotkb:O95436-1:sequence-v3",
        "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9",
        "source_resid != canonical_residue_number",
        "Numeric equality gives no authority",
        "(source_engine, source_chain_id, source_resid, source_resname)",
        "source_resname` may differ from `canonical_resname",
        "T330M", "MET", "THR", "JSON `null`", "Missing explicit mapping",
        "synthetic namespace proof, not a biological NaPi2b mapping claim",
        "no residue-number or chain offsets", "sequence alignment",
        "residue-name matching heuristics", "web/API lookup",
        "self-describing JSON", "Later publication tables remain CSV",
        "canonical_residue_mapping.json", "mania.canonical_residue_mapping.v0.1",
        "canonical_reference_sequence_sha256", "mapping_count",
        "find_source_residue_mapping", "require_source_residue_mapping",
        "require_mapped_source_residue", "canonical_residue_for_mapping",
        "Empty and sparse tables are structurally valid",
        "does not bind mapping to a Dataset trajectory "
        "and does not modify source tables",
        "Stage 30.C applies explicit mapping", "Stage 30.D integrates mapping",
    ):
        assert phrase in text

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


def test_stage30c_contract_current_status_and_next_stage():
    text = " ".join(
        (REPO_ROOT / "docs/canonical_window_table_contract.md")
        .read_text(encoding="utf-8").split()
    )
    for phrase in (
        "Stage 29 is complete", "Stage 30.A is accepted", "Stage 30.B is accepted",
        "Stage 30.C canonicalized intermediate tables are implemented",
        "Stage 30 is complete", "Stage 30.D biological annotations",
        "workflow/provenance/validation integration are complete",
        "Dataset v1.0 remains unreleased",
    ):
        assert phrase in text

def test_stage30d_complete_annotation_and_workflow_contract():
    text = " ".join(
        (REPO_ROOT / "docs/biological_annotation_contract.md")
        .read_text(encoding="utf-8")
        .split()
    )
    for phrase in (
        "234..361",
        "311..341",
        "complete_for_system",
        "exhaustive lists",
        "Without complete metadata there are no system-supplied annotated outputs",
        "canonical_residue_mapping_path",
        "biological_annotation_metadata_path",
        "(dataset_id, system_id, trajectory_id, replica_id)",
        "(dataset_id, system_id)",
        "condition=None",
        "zero additional trajectory passes",
        "protein_edges_by_window_canonical_annotated.csv",
        "protein_lipid_contacts_by_window_canonical_annotated.csv",
        "protein_glycan_contacts_by_window_canonical_annotated.csv",
        "Exact model equality is required",
        "canonical_reference",
        "canonical_residue_mapping_bindings",
        "biological_annotation_bindings",
        "site annotations only",
        "Stage 33 owns publication bundles",
        "Dependencies, version 0.1.0, WANIA",
        "never fabricated",
    ):
        assert phrase in text
    for module in (
        "biological_annotations",
        "biological_annotations_io",
        "annotated_window_tables",
        "annotated_window_tables_io",
    ):
        assert module in text
