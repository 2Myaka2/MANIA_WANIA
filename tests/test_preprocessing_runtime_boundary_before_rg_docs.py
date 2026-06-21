from pathlib import Path

from mania.preprocessing import (
    OptionalScientificDependencyStatus,
    PreprocessingConditionLoadResult,
    PreprocessingConditionResidueNames,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingConditionRuntimeMetadata,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingManifestResidueNames,
    PreprocessingManifestRuntimeMetadata,
    PreprocessingOptionalDependencyError,
    PreprocessingResidueNameExtractionIssue,
    PreprocessingRuntimeMetadataIssue,
    PreprocessingTrajectoryLoadIssue,
    collect_condition_runtime_metadata,
    collect_manifest_runtime_metadata,
    extract_condition_residue_names,
    extract_manifest_residue_names,
    get_mdanalysis_status,
    is_mdanalysis_available,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
    require_mdanalysis,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_runtime_boundary_before_rg.md"
)
PREPROCESSING_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
LOCAL_SCIENTIFIC_DOC_PATH = (
    REPO_ROOT / "docs" / "local_scientific_integration_tests.md"
)
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
RUNTIME_PATHS = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "scientific_runtime.py",
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_runtime.py",
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_loader.py",
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_manifest_loader.py",
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_metadata.py",
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_residues.py",
)
STAGE_11_PUBLIC_APIS = (
    "get_mdanalysis_status",
    "is_mdanalysis_available",
    "require_mdanalysis",
    "OptionalScientificDependencyStatus",
    "PreprocessingOptionalDependencyError",
    "PreprocessingTrajectoryLoadIssue",
    "PreprocessingConditionRuntimeInput",
    "PreprocessingConditionRuntime",
    "PreprocessingConditionLoadResult",
    "load_single_condition_runtime",
    "load_manifest_condition_runtimes",
    "PreprocessingManifestLoadIssue",
    "PreprocessingManifestLoadResult",
    "collect_condition_runtime_metadata",
    "collect_manifest_runtime_metadata",
    "PreprocessingRuntimeMetadataIssue",
    "PreprocessingConditionRuntimeMetadata",
    "PreprocessingManifestRuntimeMetadata",
    "extract_condition_residue_names",
    "extract_manifest_residue_names",
    "PreprocessingResidueNameExtractionIssue",
    "PreprocessingConditionResidueNames",
    "PreprocessingManifestResidueNames",
)
DOCUMENTED_PATHS = (
    BOUNDARY_DOC_PATH,
    PREPROCESSING_DOC_PATH,
    LOCAL_SCIENTIFIC_DOC_PATH,
    ADR_PATH,
)


def boundary_text() -> str:
    return BOUNDARY_DOC_PATH.read_text(encoding="utf-8")


def test_boundary_doc_exists() -> None:
    assert BOUNDARY_DOC_PATH.is_file()


def test_boundary_doc_lists_complete_stage_11_public_api() -> None:
    text = boundary_text()

    for api_name in STAGE_11_PUBLIC_APIS:
        assert api_name in text


def test_boundary_doc_describes_local_scientific_harness() -> None:
    text = boundary_text()

    for term in (
        "local_scientific",
        "requires_mdanalysis",
        "requires_real_md_data",
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE_PACKAGE",
    ):
        assert term in text


def test_boundary_doc_marks_scientific_features_as_non_goals() -> None:
    text = boundary_text()
    non_goal_section = text.split(
        "## What is explicitly not implemented before Rg",
        maxsplit=1,
    )[1].split("## Stage 12 handoff", maxsplit=1)[0]

    assert "does not implement" in non_goal_section
    for term in (
        "Rg",
        "contacts",
        "graph export",
        "CLI integration",
        "workflow integration",
    ):
        assert term in non_goal_section


def test_boundary_doc_states_runtime_objects_are_opaque() -> None:
    text = boundary_text()

    assert "opaque" in text
    assert "not serialized" in text
    assert "to_dict()" in text


def test_boundary_doc_separates_metadata_and_residue_names() -> None:
    text = boundary_text()

    assert "metadata and residue-name layers are separate" in text
    assert "collect_manifest_runtime_metadata(...)" in text
    assert "extract_manifest_residue_names(...)" in text


def test_existing_preprocessing_doc_references_stage_11_boundary() -> None:
    text = PREPROCESSING_DOC_PATH.read_text(encoding="utf-8")

    assert "Stage 11.8" in text
    assert "preprocessing_runtime_boundary_before_rg.md" in text


def test_adr_records_stage_11_8_boundary() -> None:
    text = ADR_PATH.read_text(encoding="utf-8")

    for term in (
        "Stage 11.8",
        "Stage 12",
        "Rg",
        "MDAnalysis remains optional",
    ):
        assert term in text


def test_local_scientific_doc_records_completed_coverage() -> None:
    text = LOCAL_SCIENTIFIC_DOC_PATH.read_text(encoding="utf-8")

    for term in (
        "Stage 11.8",
        "single-condition loading",
        "manifest loading",
        "metadata",
        "residue names",
    ):
        assert term in text


def test_docs_do_not_claim_rg_is_already_implemented() -> None:
    forbidden_claims = (
        "Rg is implemented",
        "Rg calculation exists",
        "Rg export exists",
        "Stage 11 implements Rg",
        "Stage 11 supports Rg",
    )

    for path in DOCUMENTED_PATHS:
        text = path.read_text(encoding="utf-8")
        for claim in forbidden_claims:
            assert claim not in text


def test_runtime_modules_have_no_future_scientific_implementation() -> None:
    for path in RUNTIME_PATHS:
        source_text = path.read_text(encoding="utf-8")
        for forbidden_text in (
            "radius_of_gyration",
            "select_atoms",
            "contacts",
            "graph export",
        ):
            assert forbidden_text not in source_text


def test_stage_11_public_exports_remain_importable() -> None:
    public_exports = (
        get_mdanalysis_status,
        is_mdanalysis_available,
        require_mdanalysis,
        OptionalScientificDependencyStatus,
        PreprocessingOptionalDependencyError,
        PreprocessingTrajectoryLoadIssue,
        PreprocessingConditionRuntimeInput,
        PreprocessingConditionRuntime,
        PreprocessingConditionLoadResult,
        load_single_condition_runtime,
        load_manifest_condition_runtimes,
        PreprocessingManifestLoadIssue,
        PreprocessingManifestLoadResult,
        collect_condition_runtime_metadata,
        collect_manifest_runtime_metadata,
        PreprocessingRuntimeMetadataIssue,
        PreprocessingConditionRuntimeMetadata,
        PreprocessingManifestRuntimeMetadata,
        extract_condition_residue_names,
        extract_manifest_residue_names,
        PreprocessingResidueNameExtractionIssue,
        PreprocessingConditionResidueNames,
        PreprocessingManifestResidueNames,
    )

    assert all(export is not None for export in public_exports)
