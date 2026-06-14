from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_runtime_boundary_before_rg.md"
)
PREPROCESSING_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
EXPORT_GUIDE_PATH = REPO_ROOT / "docs" / "preprocessing_rg_export.md"
LOCAL_SCIENTIFIC_PATH = (
    REPO_ROOT / "docs" / "local_scientific_integration_tests.md"
)
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
CORE_BOUNDARY_PATHS = (
    RUNTIME_BOUNDARY_PATH,
    PREPROCESSING_BOUNDARY_PATH,
    EXPORT_GUIDE_PATH,
)
ALL_BOUNDARY_PATHS = (*CORE_BOUNDARY_PATHS, LOCAL_SCIENTIFIC_PATH, ADR_PATH)


def combined_text(paths: tuple[Path, ...] = ALL_BOUNDARY_PATHS) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_final_rg_boundary_docs_mention_all_core_stage_12_apis() -> None:
    text = combined_text(CORE_BOUNDARY_PATHS)

    for api_name in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
        "compare_rg_timeseries_csv",
        "build_rg_report_bundle",
    ):
        assert api_name in text


def test_runtime_boundary_lists_complete_stage_12_public_surface() -> None:
    text = RUNTIME_BOUNDARY_PATH.read_text(encoding="utf-8")

    for api_name in (
        "PreprocessingRgComputationIssue",
        "PreprocessingRgFrameResult",
        "PreprocessingConditionRgResult",
        "PreprocessingManifestRgResult",
        "PreprocessingRgCsvWriteIssue",
        "PreprocessingRgCsvWriteResult",
        "PreprocessingRgCsvValidationIssue",
        "PreprocessingRgCsvValidationResult",
        "PreprocessingRgReferenceComparisonOptions",
        "PreprocessingRgReferenceComparisonInput",
        "PreprocessingRgReferenceComparisonIssue",
        "PreprocessingRgReferenceComparisonInputValidationResult",
        "PreprocessingRgReferenceComparisonRowResult",
        "PreprocessingRgReferenceComparisonResult",
        "PreprocessingRgReportBundleIssue",
        "PreprocessingRgReportBundleSummary",
        "PreprocessingRgReportBundle",
    ):
        assert api_name in text


def test_docs_name_rg_csv_and_conceptual_python_flow() -> None:
    text = combined_text(CORE_BOUNDARY_PATHS)

    assert "rg_timeseries.csv" in text
    for phrase in (
        "manifest -> load runtimes -> compute Rg",
        "compare with reference CSV",
        "build report bundle",
        "conceptual Python API flow",
        "not a CLI command",
        "workflow wrapper",
        "persistent output directory manager",
    ):
        assert phrase.lower() in text.lower()


def test_docs_describe_local_scientific_rg_smoke_coverage() -> None:
    text = combined_text(
        (RUNTIME_BOUNDARY_PATH, EXPORT_GUIDE_PATH, LOCAL_SCIENTIFIC_PATH)
    )

    for phrase in (
        "local scientific Rg computation smoke",
        "local scientific Rg export smoke",
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE_PACKAGE",
    ):
        assert phrase.lower() in text.lower()


def test_docs_preserve_default_ci_boundary() -> None:
    text = combined_text().lower()

    for phrase in (
        "mdanalysis remains optional",
        "default ci does not require real md data",
        "local scientific tests are skipped by default",
        "fake",
        "synthetic",
        "report bundle",
    ):
        assert phrase in text


def test_docs_list_supported_outputs_and_missing_file_writers() -> None:
    text = combined_text(CORE_BOUNDARY_PATHS).lower()

    for phrase in (
        "in-memory rg dataclass results",
        "csv validation report",
        "reference comparison report",
        "in-memory report bundle",
        "report json file writer",
        "report markdown writer",
        "report html writer",
        "workflow output directory manager",
    ):
        assert phrase in text


def test_docs_record_stage_12_out_of_scope_boundary() -> None:
    text = combined_text(CORE_BOUNDARY_PATHS).lower()

    for phrase in (
        "contacts computation",
        "contacts export",
        "graph generation",
        "cli or workflow integration",
        "real md data",
        "automatic reference package discovery",
        "configurable atom selections",
        "unit conversion",
        "notebook parity guarantees",
        "performance optimization",
        "broad trajectory preprocessing pipeline",
    ):
        assert phrase in text


def test_docs_direct_stage_13_to_separate_contacts_modules() -> None:
    text = combined_text(
        (RUNTIME_BOUNDARY_PATH, PREPROCESSING_BOUNDARY_PATH, ADR_PATH)
    ).lower()

    for phrase in (
        "stage 13",
        "contacts extraction",
        "separate contacts-specific modules",
        "contact options and output contracts",
        "minimal per-frame contacts extraction",
        "contacts export, validation, and comparison",
        "graph integration after contacts are stable",
    ):
        assert phrase in text


def test_docs_do_not_claim_contacts_or_graph_are_complete() -> None:
    text = combined_text().lower()

    for misleading_claim in (
        "contacts are complete",
        "graph is complete",
        "contacts implementation is complete",
        "graph implementation is complete",
    ):
        assert misleading_claim not in text


def test_rg_export_docs_record_in_memory_bundle_without_file_writer() -> None:
    text = EXPORT_GUIDE_PATH.read_text(encoding="utf-8").lower()

    assert "build_rg_report_bundle" in text
    assert "in-memory report bundle" in text
    assert "does not provide a report json file writer" in text


def test_local_scientific_docs_forbid_persistent_generated_csv() -> None:
    text = LOCAL_SCIENTIFIC_PATH.read_text(encoding="utf-8").lower()

    assert "pytest temp directory" in text
    assert "no committed generated csv" in text
    assert "no real md data" in text
