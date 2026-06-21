from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTACTS_MVP_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md"
CONTACTS_EXPORT_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_export.md"
CONTACTS_PERFORMANCE_PATH = (
    REPO_ROOT / "docs" / "preprocessing_contacts_performance_boundary.md"
)
PREPROCESSING_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
LOCAL_SCIENTIFIC_PATH = (
    REPO_ROOT / "docs" / "local_scientific_integration_tests.md"
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
    CONTACTS_PERFORMANCE_PATH,
    PREPROCESSING_BOUNDARY_PATH,
    LOCAL_SCIENTIFIC_PATH,
    ADR_PATH,
)
CORE_CONTACTS_DOC_PATHS = (
    CONTACTS_MVP_PATH,
    CONTACTS_EXPORT_PATH,
    CONTACTS_PERFORMANCE_PATH,
    PREPROCESSING_BOUNDARY_PATH,
)


def combined_text(paths: tuple[Path, ...] = UPDATED_DOC_PATHS) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_final_contacts_boundary_doc_exists() -> None:
    assert CONTACTS_MVP_PATH.is_file()


def test_final_contacts_boundary_mentions_completed_stage_13_flow() -> None:
    text = combined_text(CORE_CONTACTS_DOC_PATHS).lower()

    for phrase in (
        "loaded manifest runtimes",
        "contacts computation",
        "contacts export",
        "csv validation",
        "reference comparison",
        "performance boundary/sanity checks",
    ):
        assert phrase in text


def test_final_contacts_boundary_mentions_all_completed_public_apis() -> None:
    text = combined_text((CONTACTS_MVP_PATH, CONTACTS_EXPORT_PATH))

    for api_name in (
        "PreprocessingContactDefinition",
        "PreprocessingContactDetectionOptions",
        "PreprocessingContactComputationIssue",
        "PreprocessingContactPairResult",
        "PreprocessingContactFrameResult",
        "PreprocessingConditionContactsResult",
        "PreprocessingManifestContactsResult",
        "compute_condition_contacts",
        "compute_manifest_contacts",
        "PreprocessingContactsPerFrameCsvWriteIssue",
        "PreprocessingContactsPerFrameCsvWriteResult",
        "write_contacts_perframe_csv",
        "PreprocessingContactEdgesCsvWriteIssue",
        "PreprocessingContactEdgesCsvWriteResult",
        "write_contact_edges_csv",
        "PreprocessingContactsPerFrameCsvValidationIssue",
        "PreprocessingContactsPerFrameCsvValidationResult",
        "validate_contacts_perframe_csv",
        "PreprocessingContactEdgesCsvValidationIssue",
        "PreprocessingContactEdgesCsvValidationResult",
        "validate_contact_edges_csv",
        "PreprocessingContactsReferenceComparisonOptions",
        "PreprocessingContactsReferenceComparisonInput",
        "PreprocessingContactsReferenceComparisonIssue",
        "PreprocessingContactsReferenceComparisonInputValidationResult",
        "validate_contacts_reference_comparison_input",
        "PreprocessingContactsReferenceComparisonRowResult",
        "PreprocessingContactsReferenceComparisonResult",
        "compare_contacts_outputs",
    ):
        assert api_name in text


def test_final_contacts_boundary_names_accepted_csv_outputs() -> None:
    text = combined_text(CORE_CONTACTS_DOC_PATHS)

    assert "contacts_perframe.csv" in text
    assert "contact_edges.csv" in text
    assert "contact_edges.csv is an aggregate contacts table" in text


def test_final_contacts_boundary_preserves_graph_artifact_boundary() -> None:
    text = combined_text(CORE_CONTACTS_DOC_PATHS)
    lower_text = text.lower()

    for phrase in (
        "not backend graph `edges.csv`",
        "No graph export exists yet",
        "No backend graph `nodes.csv` is produced",
        "No backend graph `edges.csv` is produced",
        "No `graph.json` is produced",
        "Graph export belongs to a later stage",
        "graph diagnostics from real preprocessing",
    ):
        assert phrase.lower() in lower_text


def test_final_contacts_boundary_lists_remaining_non_goals() -> None:
    text = combined_text().lower()

    for phrase in (
        "contacts report bundle",
        "graph export",
        "backend graph `nodes.csv`",
        "backend graph `edges.csv`",
        "`graph.json`",
        "graph diagnostics from real preprocessing",
        "cli/workflow scientific mvp",
        "biological interpretation",
        "real-data ci",
    ):
        assert phrase in text


def test_local_scientific_and_default_ci_boundaries_remain_explicit() -> None:
    text = combined_text((LOCAL_SCIENTIFIC_PATH, ADR_PATH, CONTACTS_PERFORMANCE_PATH))
    lower_text = text.lower()

    for phrase in (
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        "local scientific tests are skipped by default",
        "default CI remains independent",
        "MDAnalysis remains optional",
        "real MD data",
        "local scientific performance gate",
        "real-data CI",
    ):
        assert phrase.lower() in lower_text


def test_final_contacts_boundary_does_not_claim_graph_or_report_api() -> None:
    text = combined_text().lower()

    for misleading_claim in (
        "contacts report bundle is implemented",
        "graph export is implemented",
        "backend graph export is implemented",
        "build_contacts_report_bundle",
        "write_contacts_graph",
        "write_graph_json",
    ):
        assert misleading_claim not in text
