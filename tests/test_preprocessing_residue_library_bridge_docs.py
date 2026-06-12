from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_residue_library_bridge.md"
)
INPUT_CONTRACT_PATH = REPO_ROOT / "docs" / "preprocessing_input_contract.md"
EXAMPLES_README_PATH = REPO_ROOT / "examples" / "preprocessing" / "README.md"
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"

COMPETING_PREPROCESSING_FIELD_NAMES = (
    "user_overlay_path",
    "user_residue_library_path",
)
CANONICAL_FIELDS = (
    "library_path",
    "custom_residues_path",
    "skip_resnames",
    "allow_user_overrides",
)
PROPOSED_FUNCTION_NAME = "load_residue_library_from_manifest_options"


def test_bridge_planning_doc_exists_and_mentions_canonical_fields() -> None:
    assert BRIDGE_DOC_PATH.is_file()
    bridge_text = BRIDGE_DOC_PATH.read_text(encoding="utf-8")

    for field_name in CANONICAL_FIELDS:
        assert field_name in bridge_text


def test_bridge_planning_doc_avoids_competing_field_names() -> None:
    bridge_text = BRIDGE_DOC_PATH.read_text(encoding="utf-8")

    for field_name in COMPETING_PREPROCESSING_FIELD_NAMES:
        assert field_name not in bridge_text


def test_input_contract_links_to_bridge_doc() -> None:
    contract_text = INPUT_CONTRACT_PATH.read_text(encoding="utf-8")

    assert "preprocessing_residue_library_bridge.md" in contract_text


def test_examples_readme_describes_placeholder_residue_library_paths() -> None:
    readme_text = EXAMPLES_README_PATH.read_text(encoding="utf-8")

    assert "Residue-library paths" in readme_text
    assert "placeholder contract fields" in readme_text
    assert "do not load" in readme_text
    assert "parse, or validate residue-library content" in readme_text
    assert "not expected to exist" in readme_text


def test_proposed_bridge_api_is_documentation_only() -> None:
    bridge_text = BRIDGE_DOC_PATH.read_text(encoding="utf-8")
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py"))
    )

    assert PROPOSED_FUNCTION_NAME in bridge_text
    assert PROPOSED_FUNCTION_NAME not in runtime_source
