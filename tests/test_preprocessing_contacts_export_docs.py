import runpy
from pathlib import Path

from mania.preprocessing import (
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_export.md"
CONTACTS_MVP_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md"
PREPROCESSING_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
EXAMPLES_README_PATH = REPO_ROOT / "examples" / "preprocessing" / "README.md"
EXAMPLE_SCRIPT_PATH = (
    REPO_ROOT / "examples" / "preprocessing" / "contacts_export_usage.py"
)
PERFRAME_EXAMPLE_CSV_PATH = (
    REPO_ROOT / "examples" / "preprocessing" / "contacts_perframe.example.csv"
)
EDGES_EXAMPLE_CSV_PATH = (
    REPO_ROOT / "examples" / "preprocessing" / "contact_edges.example.csv"
)
PERFRAME_HEADER = (
    "condition_name,frame_index,time_ps,source_residue_index,"
    "target_residue_index,source_residue_id,target_residue_id,"
    "source_resname,target_resname,source_segid,target_segid,"
    "minimum_distance,distance_unit,atom_filter,frame_passed"
)
EDGES_HEADER = (
    "condition_name,source_residue_index,target_residue_index,"
    "source_residue_id,target_residue_id,source_resname,target_resname,"
    "source_segid,target_segid,contact_frame_count,total_frame_count,"
    "contact_frequency,minimum_distance,mean_minimum_distance,"
    "distance_unit,atom_filter"
)


def guide_text() -> str:
    return GUIDE_PATH.read_text(encoding="utf-8")


def test_contacts_export_guide_exists() -> None:
    assert GUIDE_PATH.is_file()


def test_guide_mentions_accepted_public_apis() -> None:
    text = guide_text()

    for api_name in (
        "PreprocessingConditionContactsResult",
        "PreprocessingManifestContactsResult",
        "compute_condition_contacts",
        "compute_manifest_contacts",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "validate_contacts_perframe_csv",
        "validate_contact_edges_csv",
    ):
        assert api_name in text


def test_guide_documents_exact_csv_headers_and_aggregate_fields() -> None:
    text = guide_text()

    assert PERFRAME_HEADER in text
    assert EDGES_HEADER in text
    for field_name in (
        "contact_frame_count",
        "total_frame_count",
        "contact_frequency",
        "minimum_distance",
        "mean_minimum_distance",
    ):
        assert field_name in text


def test_guide_documents_failed_frame_and_header_only_policy() -> None:
    text = guide_text()

    for phrase in (
        "header-only file",
        "Failed frames are skipped by default",
        "include_failed_frames=True",
        "frame_passed` set to `false",
        "do not contribute to `total_frame_count`",
    ):
        assert phrase in text


def test_guide_documents_validation_and_graph_boundaries() -> None:
    text = guide_text()

    for phrase in (
        "read-only",
        "dependency-free",
        "exact-header validators",
        "type/range validators",
        "not reference comparison",
        "not graph validation",
        "contact_edges.csv is an aggregate contacts table",
        "It is not backend graph edges.csv",
        "contact_edges.csv is not nodes.csv",
        "contact_edges.csv is not backend graph edges.csv",
        "contact_edges.csv is not graph.json",
        "Graph export belongs to a later stage",
    ):
        assert phrase in text


def test_guide_documents_stage_boundaries_and_future_stages() -> None:
    text = guide_text()

    for phrase in (
        "source behavior changes",
        "local scientific export smoke",
        "reference comparison",
        "report bundle",
        "graph export",
        "CLI/workflow integration",
        "real-data CI",
        "biological interpretation",
        "Stage 13.3e",
        "Stage 13.4",
    ):
        assert phrase in text


def test_examples_readme_references_contacts_export() -> None:
    text = EXAMPLES_README_PATH.read_text(encoding="utf-8")

    for phrase in (
        "contacts_perframe.csv",
        "contact_edges.csv",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "validate_contacts_perframe_csv",
        "validate_contact_edges_csv",
        "docs/preprocessing_contacts_export.md",
        "contacts_export_usage.py",
        "contacts_perframe.example.csv",
        "contact_edges.example.csv",
    ):
        assert phrase in text


def test_example_script_is_dependency_free_and_safe() -> None:
    source_text = EXAMPLE_SCRIPT_PATH.read_text(encoding="utf-8")

    for required_import in (
        "PreprocessingContactPairResult",
        "PreprocessingContactFrameResult",
        "PreprocessingConditionContactsResult",
        "PreprocessingManifestContactsResult",
        "PreprocessingContactDetectionOptions",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "validate_contacts_perframe_csv",
        "validate_contact_edges_csv",
    ):
        assert required_import in source_text

    assert "TemporaryDirectory" in source_text
    assert "MDAnalysis" not in source_text
    assert "MANIA_LOCAL_REFERENCE_PACKAGE" not in source_text
    assert "load_manifest_condition_runtimes" not in source_text
    assert "load_preprocessing_input_manifest" not in source_text
    assert "compute_condition_contacts" not in source_text
    assert "compute_manifest_contacts" not in source_text
    assert "graph.json" not in source_text
    runpy.run_path(str(EXAMPLE_SCRIPT_PATH), run_name="__main__")


def test_synthetic_example_csvs_have_exact_headers_and_validate() -> None:
    perframe_first_line = PERFRAME_EXAMPLE_CSV_PATH.read_text(
        encoding="utf-8"
    ).splitlines()[0]
    edges_first_line = EDGES_EXAMPLE_CSV_PATH.read_text(
        encoding="utf-8"
    ).splitlines()[0]

    perframe_result = validate_contacts_perframe_csv(
        PERFRAME_EXAMPLE_CSV_PATH
    )
    edges_result = validate_contact_edges_csv(EDGES_EXAMPLE_CSV_PATH)

    assert perframe_first_line == PERFRAME_HEADER
    assert edges_first_line == EDGES_HEADER
    assert perframe_result.passed is True
    assert edges_result.passed is True
    assert perframe_result.row_count == 2
    assert edges_result.row_count == 1


def test_boundary_docs_record_stage_13_3d() -> None:
    for path in (
        CONTACTS_MVP_PATH,
        PREPROCESSING_BOUNDARY_PATH,
        ADR_PATH,
    ):
        text = path.read_text(encoding="utf-8")
        assert "Stage 13.3d" in text

    contacts_text = CONTACTS_MVP_PATH.read_text(encoding="utf-8")
    assert "contacts export documentation and synthetic examples" in contacts_text
