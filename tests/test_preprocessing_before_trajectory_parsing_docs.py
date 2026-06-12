from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
BRIDGE_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_residue_library_bridge.md"
)
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0001-optional-scientific-dependencies.md"

IMPLEMENTED_STAGE_10_APIS = (
    "load_residue_library_from_manifest_options",
    "resolve_residue_library_manifest_paths",
    "validate_residue_library_from_manifest_options",
    "run_residue_qc_from_manifest_options",
)
SAFE_USAGE_APIS = (
    "load_preprocessing_input_manifest",
    "validate_preprocessing_manifest_paths",
    "validate_residue_library_from_manifest_options",
    "run_residue_qc_from_manifest_options",
)
MISLEADING_IMPLEMENTATION_CLAIMS = (
    "Stage 11 is implemented",
    "trajectory loading is implemented",
    "MDAnalysis is required",
    "contacts are implemented",
    "Rg is implemented",
)


def boundary_text() -> str:
    return BOUNDARY_DOC_PATH.read_text(encoding="utf-8")


def test_boundary_doc_exists() -> None:
    assert BOUNDARY_DOC_PATH.is_file()


def test_boundary_doc_lists_implemented_stage_10_apis() -> None:
    text = boundary_text()

    for api_name in IMPLEMENTED_STAGE_10_APIS:
        assert api_name in text


def test_boundary_doc_states_explicit_residue_name_boundary() -> None:
    text = boundary_text()

    assert "explicit residue names" in text
    assert "topology/trajectory-derived residue names" in text
    assert "not implemented" in text
    assert "Stage 11" in text


def test_boundary_doc_states_topology_and_trajectory_non_goals() -> None:
    text = boundary_text()

    for phrase in (
        "topology loading",
        "trajectory loading",
        "residue extraction from topology/trajectory",
        "MDAnalysis",
        "Rg",
        "contacts",
    ):
        assert phrase in text


def test_boundary_doc_references_future_stages() -> None:
    text = boundary_text()

    for stage in ("Stage 11", "Stage 12", "Stage 13", "Stage 14", "Stage 15"):
        assert stage in text


def test_boundary_doc_includes_safe_usage_examples() -> None:
    text = boundary_text()

    for api_name in SAFE_USAGE_APIS:
        assert api_name in text


def test_boundary_doc_states_local_reference_data_policy() -> None:
    text = boundary_text()

    assert "data/reference" in text
    assert "Real MD data" in text
    assert "Default CI" in text


def test_bridge_doc_references_boundary_doc() -> None:
    text = BRIDGE_DOC_PATH.read_text(encoding="utf-8")

    assert "preprocessing_before_trajectory_parsing.md" in text


def test_adr_references_boundary_doc() -> None:
    text = ADR_PATH.read_text(encoding="utf-8")

    assert "preprocessing_before_trajectory_parsing.md" in text


def test_boundary_doc_does_not_claim_stage_11_is_implemented() -> None:
    text = boundary_text()

    for phrase in MISLEADING_IMPLEMENTATION_CLAIMS:
        assert phrase not in text
