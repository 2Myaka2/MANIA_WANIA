import re
import tomllib
from pathlib import Path

import mania.preprocessing

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"
SCIENTIFIC_PACKAGES = (
    "MDAnalysis",
    "numpy",
    "pandas",
    "networkx",
    "pyarrow",
)


def load_optional_dependencies() -> dict[str, list[str]]:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    return pyproject["project"]["optional-dependencies"]


def dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    assert match is not None
    return match.group(0).lower()


def direct_dependency_names(requirements: list[str]) -> set[str]:
    return {dependency_name(requirement) for requirement in requirements}


def test_md_and_science_optional_extras_exist() -> None:
    optional_dependencies = load_optional_dependencies()

    assert "md" in optional_dependencies
    assert "science" in optional_dependencies


def test_md_extra_includes_mdanalysis() -> None:
    optional_dependencies = load_optional_dependencies()

    assert "mdanalysis" in direct_dependency_names(optional_dependencies["md"])


def test_science_extra_includes_mdanalysis() -> None:
    optional_dependencies = load_optional_dependencies()

    assert "mdanalysis" in direct_dependency_names(
        optional_dependencies["science"]
    )


def test_optional_extras_exclude_non_immediate_dependencies() -> None:
    optional_dependencies = load_optional_dependencies()
    configured_names = {
        name
        for requirements in optional_dependencies.values()
        for name in direct_dependency_names(requirements)
    }

    assert configured_names.isdisjoint(
        {"numpy", "pandas", "networkx", "pyarrow"}
    )


def test_runtime_source_does_not_import_scientific_packages() -> None:
    import_pattern = re.compile(
        rf"^\s*(?:import|from)\s+"
        rf"(?:{'|'.join(map(re.escape, SCIENTIFIC_PACKAGES))})"
        rf"(?:\.|\s|$)"
    )

    for source_path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py")):
        for line in source_path.read_text(encoding="utf-8").splitlines():
            assert import_pattern.match(line) is None


def test_preprocessing_import_remains_lightweight() -> None:
    assert mania.preprocessing is not None


def test_adr_documents_stage_9_2_extras_decision() -> None:
    adr_text = ADR_PATH.read_text(encoding="utf-8")
    adr_text_lower = adr_text.lower()

    for term in ("Stage 9.2", "MDAnalysis"):
        assert term in adr_text
    for term in ("md", "science", "optional", "core"):
        assert term in adr_text_lower

    assert "does not implement scientific runtime code" in adr_text
    assert "does not make real MD data part" in adr_text
    assert "default CI" in adr_text
    assert "default test suite" in adr_text


def test_adr_documents_excluded_direct_dependencies() -> None:
    adr_text = ADR_PATH.read_text(encoding="utf-8")

    for package_name in ("numpy", "pandas", "networkx", "pyarrow"):
        assert package_name in adr_text
    assert "does not add" in adr_text
    assert "explicitly" in adr_text
