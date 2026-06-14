import runpy
from pathlib import Path

from mania.preprocessing import validate_rg_timeseries_csv

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = REPO_ROOT / "docs" / "preprocessing_rg_export.md"
RUNTIME_BOUNDARY_PATH = (
    REPO_ROOT / "docs" / "preprocessing_runtime_boundary_before_rg.md"
)
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
    REPO_ROOT / "examples" / "preprocessing" / "rg_export_usage.py"
)
EXAMPLE_CSV_PATH = (
    REPO_ROOT / "examples" / "preprocessing" / "rg_timeseries.example.csv"
)
CSV_HEADER = (
    "condition_name,frame_index,time_ps,rg_value,rg_unit,frame_passed"
)


def guide_text() -> str:
    return GUIDE_PATH.read_text(encoding="utf-8")


def test_rg_export_guide_exists() -> None:
    assert GUIDE_PATH.is_file()


def test_guide_mentions_accepted_public_apis() -> None:
    text = guide_text()

    for api_name in (
        "load_preprocessing_input_manifest",
        "load_manifest_condition_runtimes",
        "compute_manifest_rg",
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
    ):
        assert api_name in text


def test_guide_documents_exact_csv_header_and_fields() -> None:
    text = guide_text()

    assert CSV_HEADER in text
    for field_name in (
        "condition_name",
        "frame_index",
        "time_ps",
        "rg_value",
        "rg_unit",
        "frame_passed",
    ):
        assert field_name in text
    assert "empty when time is missing" in text
    assert "empty for a failed frame" in text
    assert "empty when missing" in text


def test_guide_documents_failed_frame_policy() -> None:
    text = guide_text()

    assert "Passed frames are written by default" in text
    assert "include_failed_frames=True" in text
    assert "Failed rows" in text
    assert "empty `rg_value`" in text


def test_guide_documents_validation_behavior() -> None:
    text = guide_text()

    for phrase in (
        "validates the exact header",
        "passed-frame consistency",
        "non-monotonic frame indexes",
        "allows repeated frame indexes",
        "does not mutate CSV files",
    ):
        assert phrase in text


def test_guide_documents_stage_boundaries() -> None:
    text = guide_text()

    for phrase in (
        "local scientific export smoke test",
        "Reference comparison remains Stage 12.3",
        "report bundle",
        "contacts",
        "graph",
        "CLI or workflow integration",
    ):
        assert phrase in text


def test_examples_readme_references_rg_export() -> None:
    text = EXAMPLES_README_PATH.read_text(encoding="utf-8")

    for phrase in (
        "rg_timeseries.csv",
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
        "docs/preprocessing_rg_export.md",
        "rg_export_usage.py",
        "rg_timeseries.example.csv",
    ):
        assert phrase in text


def test_example_script_is_dependency_free_and_safe() -> None:
    source_text = EXAMPLE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "TemporaryDirectory" in source_text
    assert "MDAnalysis" not in source_text
    assert "MANIA_LOCAL_REFERENCE_PACKAGE" not in source_text
    assert "load_manifest_condition_runtimes" not in source_text
    assert "load_preprocessing_input_manifest" not in source_text
    runpy.run_path(str(EXAMPLE_SCRIPT_PATH), run_name="__main__")


def test_synthetic_example_csv_has_exact_header_and_validates() -> None:
    assert EXAMPLE_CSV_PATH.is_file()
    first_line = EXAMPLE_CSV_PATH.read_text(encoding="utf-8").splitlines()[0]

    result = validate_rg_timeseries_csv(EXAMPLE_CSV_PATH)

    assert first_line == CSV_HEADER
    assert result.passed is True
    assert result.row_count == 2


def test_boundary_docs_record_stage_12_2c() -> None:
    for path in (
        RUNTIME_BOUNDARY_PATH,
        PREPROCESSING_BOUNDARY_PATH,
        ADR_PATH,
    ):
        text = path.read_text(encoding="utf-8")
        assert "Stage 12.2c" in text

    runtime_text = RUNTIME_BOUNDARY_PATH.read_text(encoding="utf-8")
    for phrase in (
        "Rg export guide",
        "Stage 12.2d",
        "Stage 12.3",
        "Stage 12.4",
    ):
        assert phrase in runtime_text
