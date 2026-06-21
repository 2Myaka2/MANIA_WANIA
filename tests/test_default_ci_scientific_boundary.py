import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC_PATH = REPO_ROOT / "docs" / "default_ci_scientific_boundary.md"
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
LOCAL_STRATEGY_PATH = (
    REPO_ROOT / "docs" / "local_scientific_integration_tests.md"
)
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"
LOCAL_SCIENTIFIC_TEST_DIR = REPO_ROOT / "tests" / "local_scientific"
SCIENTIFIC_PACKAGES = (
    "MDAnalysis",
    "numpy",
    "pandas",
    "networkx",
    "pyarrow",
)


def read_boundary_doc() -> str:
    return BOUNDARY_DOC_PATH.read_text(encoding="utf-8")


def read_workflows() -> str:
    if not WORKFLOWS_DIR.is_dir():
        return ""

    workflow_paths = sorted(
        path
        for path in WORKFLOWS_DIR.rglob("*")
        if path.suffix in {".yml", ".yaml"}
    )
    return "\n".join(
        path.read_text(encoding="utf-8") for path in workflow_paths
    )


def load_pyproject() -> dict[str, object]:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    assert match is not None
    return match.group(0).lower()


def test_default_ci_scientific_boundary_doc_exists() -> None:
    assert BOUNDARY_DOC_PATH.is_file()


def test_boundary_doc_states_default_ci_non_requirements() -> None:
    boundary_text = read_boundary_doc().lower()

    for term in (
        "mdanalysis",
        "gromacs",
        "real topology",
        "real trajectory",
        "data/reference",
        "local reference package",
        "default ci",
    ):
        assert term in boundary_text


def test_boundary_doc_mentions_optional_extras() -> None:
    boundary_text = read_boundary_doc()

    for term in ("`md`", "`science`", "optional extras"):
        assert term in boundary_text
    assert "Default CI should not install" in boundary_text


def test_boundary_doc_states_stage_9_4_non_goals() -> None:
    boundary_text = read_boundary_doc()

    for term in (
        "does not modify CI workflows",
        "does not register pytest markers",
        "does not create `tests/local_scientific`",
        "does not add real MD data",
        "does not implement trajectory loading",
        "does not compute Rg",
        "does not compute contacts",
    ):
        assert term in boundary_text


def test_adr_references_stage_9_4_boundary_doc() -> None:
    adr_text = ADR_PATH.read_text(encoding="utf-8")

    assert "Stage 9.4" in adr_text
    assert "default_ci_scientific_boundary.md" in adr_text


def test_local_strategy_references_ci_boundary_doc() -> None:
    strategy_text = LOCAL_STRATEGY_PATH.read_text(encoding="utf-8")

    assert "default_ci_scientific_boundary.md" in strategy_text


def test_ci_workflows_do_not_install_scientific_extras() -> None:
    workflow_text = read_workflows()

    assert ".[md]" not in workflow_text
    assert ".[science]" not in workflow_text


def test_ci_workflows_do_not_reference_local_real_data_setup() -> None:
    workflow_text = read_workflows()

    for term in (
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        "data/reference",
        "local_scientific",
        "requires_real_md_data",
        "requires_mdanalysis",
    ):
        assert term not in workflow_text


def test_default_dependencies_exclude_scientific_packages() -> None:
    project = load_pyproject()["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    dependency_names = {
        dependency_name(requirement)
        for requirement in dependencies
        if isinstance(requirement, str)
    }

    assert dependency_names.isdisjoint(
        {"mdanalysis", "pandas", "networkx", "pyarrow"}
    )


def test_dev_extra_excludes_scientific_runtime_entries() -> None:
    project = load_pyproject()["project"]
    assert isinstance(project, dict)
    optional_dependencies = project.get("optional-dependencies", {})
    assert isinstance(optional_dependencies, dict)
    dev_requirements = optional_dependencies.get("dev", [])
    assert isinstance(dev_requirements, list)
    dev_text = "\n".join(
        requirement
        for requirement in dev_requirements
        if isinstance(requirement, str)
    )
    dev_names = {
        dependency_name(requirement)
        for requirement in dev_requirements
        if isinstance(requirement, str)
    }

    assert "mdanalysis" not in dev_names
    assert ".[md]" not in dev_text
    assert ".[science]" not in dev_text


def test_runtime_source_does_not_import_scientific_packages() -> None:
    import_pattern = re.compile(
        rf"^\s*(?:import|from)\s+"
        rf"(?:{'|'.join(map(re.escape, SCIENTIFIC_PACKAGES))})"
        rf"(?:\.|\s|$)"
    )

    for source_path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py")):
        for line in source_path.read_text(encoding="utf-8").splitlines():
            assert import_pattern.match(line) is None


def test_local_scientific_test_directory_contains_no_real_md_data() -> None:
    real_md_suffixes = {
        ".xtc",
        ".trr",
        ".tpr",
        ".gro",
        ".pdb",
        ".pqr",
        ".dcd",
        ".nc",
        ".h5",
        ".hdf5",
    }

    assert LOCAL_SCIENTIFIC_TEST_DIR.is_dir()
    assert not any(
        path.is_file() and path.suffix.lower() in real_md_suffixes
        for path in LOCAL_SCIENTIFIC_TEST_DIR.rglob("*")
    )


def test_boundary_doc_does_not_claim_scientific_ci_implementation() -> None:
    boundary_text = read_boundary_doc().lower()

    for forbidden_phrase in (
        "scientific ci job is implemented",
        "default ci installs .[md]",
        "default ci installs .[science]",
    ):
        assert forbidden_phrase not in boundary_text
