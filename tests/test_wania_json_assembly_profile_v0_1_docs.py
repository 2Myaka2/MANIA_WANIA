from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_json_assembly_profile_v0_1.md"
REFERENCE_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "wania_mvp_contract_v0_1.md",
    REPO_ROOT / "docs" / "wania_required_fields_contract_v0_1.md",
    REPO_ROOT / "docs" / "wania_science_ui_boundary_v0_1.md",
    REPO_ROOT / "docs" / "wania_object_json_payload_contract.md",
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def doc_text() -> str:
    return normalized(DOC_PATH.read_text(encoding="utf-8"))


def test_wania_json_assembly_profile_v0_1_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_profile_defines_inputs_output_and_demo_ready_shape() -> None:
    text = doc_text()

    for phrase in (
        "WANIA JSON assembly profile",
        "demo-ready",
        "wania_graph_payload.json",
        "MANIA artifacts",
        "graph/graph.json",
        "graph.nodes",
        "graph.edges",
        "schema_version",
        "run",
        "capabilities",
        "artifacts",
        "diagnostics",
        "condition_names",
        "x/y/z",
        "interaction.primary_type",
    ):
        assert phrase in text


def test_profile_aligns_with_stage_17_and_optional_science() -> None:
    text = doc_text()

    for phrase in (
        "Stage 17.1",
        "Stage 17.2",
        "Stage 17.3",
        "required fields",
        "optional scientific",
        "backend-only",
        "future capabilities",
        "x_ca/y_ca/z_ca",
        "backbone",
        "aromatic_pi",
        "cation_pi",
        "analysis metrics",
        "communities",
        "progressive enhancements",
    ):
        assert phrase in text


def test_profile_defines_portable_artifact_and_backend_boundaries() -> None:
    text = doc_text()

    for phrase in (
        "artifact references",
        "relative paths",
        "portable",
        "must not be absolute paths",
        "local_md",
        "local_md_protein",
        "mania_output",
        "raw trajectory paths",
        "InteractionAccumulator",
        "atom cache",
        "not FastAPI",
        "not frontend implementation",
        "not notebook execution",
    ):
        assert phrase in text


def test_profile_records_mapping_and_demo_export_flow() -> None:
    text = doc_text()

    for phrase in (
        "Stage 18.1 defines the profile",
        "Stage 18.2 validates artifact-to-payload mapping",
        "Stage 18.3 provides the reproducible demo export flow",
        "mania wania build-payload",
        "--graph-json",
        "--output",
        "--output-dir",
        "--condition-name",
        "build_wania_graph_payload_from_artifacts",
        "write_wania_graph_payload_json",
        "does not duplicate payload construction",
        "Optional scientific artifacts are not required",
        "does not print the full payload by default",
        "not new scientific computation",
    ):
        assert phrase in text


def test_profile_is_linked_from_required_docs() -> None:
    for path in REFERENCE_PATHS:
        assert "wania_json_assembly_profile_v0_1.md" in path.read_text(
            encoding="utf-8"
        )
