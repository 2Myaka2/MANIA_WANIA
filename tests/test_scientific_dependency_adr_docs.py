from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"
CROSS_REFERENCE_DOCS = (
    REPO_ROOT / "docs" / "preprocessing_local_reference_package.md",
    REPO_ROOT / "docs" / "preprocessing_residue_library_bridge.md",
    REPO_ROOT / "docs" / "preprocessing_input_contract.md",
)


def read_adr() -> str:
    return ADR_PATH.read_text(encoding="utf-8")


def test_optional_scientific_dependency_adr_exists() -> None:
    assert ADR_PATH.is_file()


def test_adr_states_optional_dependency_decision() -> None:
    adr_text = read_adr().lower()

    for term in ("optional", "core", "scientific"):
        assert term in adr_text


def test_adr_mentions_candidate_dependency_families() -> None:
    adr_text = read_adr()

    for package_name in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert package_name in adr_text


def test_adr_states_stage_9_1_non_goals() -> None:
    adr_text = read_adr()

    for term in (
        "does not",
        "pyproject.toml",
        "trajectory loading",
        "Rg",
        "contacts",
    ):
        assert term in adr_text


def test_adr_references_future_stages() -> None:
    adr_text = read_adr()

    for stage in ("Stage 9.2", "Stage 9.3", "Stage 9.4", "Stage 11"):
        assert stage in adr_text


def test_stage_8_docs_reference_optional_dependency_adr() -> None:
    for doc_path in CROSS_REFERENCE_DOCS:
        doc_text = doc_path.read_text(encoding="utf-8").lower()
        assert (
            "0001-optional-scientific-dependencies.md" in doc_text
            or "optional scientific dependencies" in doc_text
        )


def test_runtime_source_avoids_candidate_scientific_packages() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py"))
    )

    for package_name in ("MDAnalysis", "pandas", "networkx", "pyarrow"):
        assert package_name not in runtime_source
