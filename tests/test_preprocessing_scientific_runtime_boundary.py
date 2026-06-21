import importlib.metadata
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

import mania.preprocessing
from mania.preprocessing import (
    OptionalScientificDependencyStatus,
    PreprocessingOptionalDependencyError,
    get_mdanalysis_status,
    is_mdanalysis_available,
    require_mdanalysis,
    scientific_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "scientific_runtime.py"
)
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"


def test_public_preprocessing_import_does_not_require_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_public_scientific_runtime_exports_work() -> None:
    assert OptionalScientificDependencyStatus is not None
    assert PreprocessingOptionalDependencyError is not None
    assert get_mdanalysis_status is not None
    assert is_mdanalysis_available is not None
    assert require_mdanalysis is not None


def test_status_reports_unavailable_dependency_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scientific_runtime.importlib.util, "find_spec", lambda _: None)

    def fail_version_lookup(_: str) -> str:
        raise AssertionError("version lookup should not run when unavailable")

    monkeypatch.setattr(
        scientific_runtime.importlib.metadata,
        "version",
        fail_version_lookup,
    )

    status = get_mdanalysis_status()

    assert isinstance(status, OptionalScientificDependencyStatus)
    assert status.available is False
    assert status.package_name == "MDAnalysis"
    assert status.import_name == "MDAnalysis"
    assert status.version is None
    assert ".[md]" in status.install_hint or ".[science]" in status.install_hint
    json.dumps(status.to_dict())


def test_is_mdanalysis_available_returns_false_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scientific_runtime.importlib.util, "find_spec", lambda _: None)

    assert is_mdanalysis_available() is False


def test_discovery_error_is_treated_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_discovery_error(_: str) -> None:
        raise ImportError("discovery failed")

    monkeypatch.setattr(
        scientific_runtime.importlib.util,
        "find_spec",
        raise_discovery_error,
    )

    assert is_mdanalysis_available() is False


def test_require_mdanalysis_raises_project_error_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing_dependency(_: str) -> ModuleType:
        raise ModuleNotFoundError(name="MDAnalysis")

    monkeypatch.setattr(
        scientific_runtime.importlib,
        "import_module",
        raise_missing_dependency,
    )

    with pytest.raises(PreprocessingOptionalDependencyError) as exc_info:
        require_mdanalysis()

    message = str(exc_info.value)
    assert "MDAnalysis" in message
    assert "topology/trajectory loading" in message
    assert ".[md]" in message or ".[science]" in message
    assert "default/core install intentionally does not require it" in message
    assert "Traceback" not in message


def test_require_mdanalysis_does_not_hide_missing_transitive_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing_dependency(_: str) -> ModuleType:
        raise ModuleNotFoundError(name="missing_transitive_package")

    monkeypatch.setattr(
        scientific_runtime.importlib,
        "import_module",
        raise_missing_dependency,
    )

    with pytest.raises(ModuleNotFoundError) as exc_info:
        require_mdanalysis()

    assert exc_info.value.name == "missing_transitive_package"


def test_require_mdanalysis_returns_module_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = ModuleType("MDAnalysis")
    monkeypatch.setattr(
        scientific_runtime.importlib,
        "import_module",
        lambda _: fake_module,
    )

    assert require_mdanalysis() is fake_module


def test_status_reports_available_dependency_with_fake_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scientific_runtime.importlib.util,
        "find_spec",
        lambda _: object(),
    )
    monkeypatch.setattr(
        scientific_runtime.importlib.metadata,
        "version",
        lambda _: "9.9.9",
    )

    status = get_mdanalysis_status()

    assert status.available is True
    assert status.version == "9.9.9"
    json.dumps(status.to_dict())


def test_status_remains_robust_if_version_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scientific_runtime.importlib.util,
        "find_spec",
        lambda _: object(),
    )

    def raise_missing_metadata(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError("MDAnalysis")

    monkeypatch.setattr(
        scientific_runtime.importlib.metadata,
        "version",
        raise_missing_metadata,
    )

    status = get_mdanalysis_status()

    assert status.available is True
    assert status.version is None


def test_runtime_module_has_no_direct_mdanalysis_import() -> None:
    source_lines = RUNTIME_MODULE_PATH.read_text(encoding="utf-8").splitlines()

    assert not any(
        re.match(r"^\s*import\s+MDAnalysis(?:\.|\s|$)", line)
        or re.match(r"^\s*from\s+MDAnalysis(?:\.|\s)\s*import\s+", line)
        for line in source_lines
    )


def test_runtime_source_has_no_direct_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for source_path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py")):
        for line in source_path.read_text(encoding="utf-8").splitlines():
            assert forbidden_import_pattern.match(line) is None


def test_existing_preprocessing_boundary_apis_remain_importable() -> None:
    assert mania.preprocessing.load_preprocessing_input_manifest is not None
    assert mania.preprocessing.validate_preprocessing_manifest_paths is not None
    assert mania.preprocessing.check_preprocessing_reference_package is not None
    assert (
        mania.preprocessing.load_residue_library_from_manifest_options
        is not None
    )
    assert (
        mania.preprocessing.validate_residue_library_from_manifest_options
        is not None
    )
    assert mania.preprocessing.run_residue_qc_from_manifest_options is not None
