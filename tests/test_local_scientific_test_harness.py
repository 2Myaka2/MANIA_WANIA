import importlib.util
import re
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

import mania.preprocessing

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
LOCAL_SCIENTIFIC_DIR = REPO_ROOT / "tests" / "local_scientific"
HARNESS_PATH = LOCAL_SCIENTIFIC_DIR / "_harness.py"
SMOKE_TEST_PATH = LOCAL_SCIENTIFIC_DIR / "test_harness_smoke.py"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"
DOC_PATHS = (
    REPO_ROOT / "docs" / "local_scientific_integration_tests.md",
    REPO_ROOT / "docs" / "default_ci_scientific_boundary.md",
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
)
REAL_MD_SUFFIXES = {
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


def load_pyproject() -> dict[str, object]:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mania_local_scientific_harness",
        HARNESS_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    assert match is not None
    return match.group(0).lower()


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


def test_pytest_markers_are_registered() -> None:
    pytest_config = load_pyproject()["tool"]["pytest"]["ini_options"]
    assert isinstance(pytest_config, dict)
    markers = pytest_config["markers"]
    assert isinstance(markers, list)
    marker_names = {
        marker.split(":", maxsplit=1)[0].strip()
        for marker in markers
        if isinstance(marker, str)
    }

    assert {
        "local_scientific",
        "requires_mdanalysis",
        "requires_real_md_data",
    }.issubset(marker_names)


def test_default_and_dev_dependencies_remain_lightweight() -> None:
    project = load_pyproject()["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    default_names = {
        dependency_name(requirement)
        for requirement in dependencies
        if isinstance(requirement, str)
    }
    assert "numpy" in default_names
    assert default_names.isdisjoint(
        {"mdanalysis", "pandas", "networkx", "pyarrow"}
    )

    optional_dependencies = project.get("optional-dependencies", {})
    assert isinstance(optional_dependencies, dict)
    dev_requirements = optional_dependencies.get("dev", [])
    assert isinstance(dev_requirements, list)
    dev_names = {
        dependency_name(requirement)
        for requirement in dev_requirements
        if isinstance(requirement, str)
    }
    dev_text = "\n".join(
        requirement
        for requirement in dev_requirements
        if isinstance(requirement, str)
    )
    assert "mdanalysis" not in dev_names
    assert ".[md]" not in dev_text
    assert ".[science]" not in dev_text


def test_local_harness_defaults_to_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MANIA_RUN_LOCAL_SCIENTIFIC", raising=False)

    assert load_harness().local_scientific_enabled() is False


@pytest.mark.parametrize("value", ["1", " TRUE ", "yes", "ON"])
def test_local_harness_accepts_documented_enabled_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MANIA_RUN_LOCAL_SCIENTIFIC", value)

    assert load_harness().local_scientific_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "disabled"])
def test_local_harness_rejects_other_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MANIA_RUN_LOCAL_SCIENTIFIC", value)

    assert load_harness().local_scientific_enabled() is False


def test_local_reference_package_is_optional(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    harness = load_harness()
    monkeypatch.delenv("MANIA_LOCAL_REFERENCE_PACKAGE", raising=False)
    assert harness.local_reference_package_path() is None
    assert harness.local_reference_package_available() is False

    local_package = tmp_path / "local-package"
    local_package.mkdir()
    monkeypatch.setenv(
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        str(local_package),
    )
    assert harness.local_reference_package_path() == local_package
    assert harness.local_reference_package_available() is True

    missing_package = tmp_path / "missing-package"
    monkeypatch.setenv(
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        str(missing_package),
    )
    assert harness.local_reference_package_path() == missing_package
    assert harness.local_reference_package_available() is False


def test_mdanalysis_availability_delegates_to_preprocessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_is_available() -> bool:
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(
        mania.preprocessing,
        "is_mdanalysis_available",
        fake_is_available,
    )

    assert load_harness().mdanalysis_available() is True
    assert calls == 1


def test_local_scientific_directory_contains_no_real_md_data() -> None:
    assert LOCAL_SCIENTIFIC_DIR.is_dir()

    real_data_paths = [
        path
        for path in LOCAL_SCIENTIFIC_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in REAL_MD_SUFFIXES
    ]
    assert real_data_paths == []


def test_local_smoke_tests_are_harness_only() -> None:
    smoke_source = SMOKE_TEST_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "MDAnalysis.Universe",
        "require_mdanalysis(",
        "select_atoms",
        "radius of gyration",
        "contacts",
    ):
        assert forbidden_text not in smoke_source


def test_default_ci_does_not_enable_local_scientific_tests() -> None:
    workflow_text = read_workflows()

    for forbidden_text in (
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        "tests/local_scientific",
        "-m local_scientific",
        ".[md]",
        ".[science]",
    ):
        assert forbidden_text not in workflow_text


def test_runtime_source_has_no_direct_scientific_imports() -> None:
    import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for source_path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py")):
        for line in source_path.read_text(encoding="utf-8").splitlines():
            assert import_pattern.match(line) is None


def test_documentation_references_local_scientific_harness() -> None:
    required_terms = (
        "MANIA_RUN_LOCAL_SCIENTIFIC",
        "MANIA_LOCAL_REFERENCE_PACKAGE",
        "local_scientific",
        "requires_mdanalysis",
        "requires_real_md_data",
    )

    for doc_path in DOC_PATHS:
        doc_text = doc_path.read_text(encoding="utf-8")
        for term in required_terms:
            assert term in doc_text
