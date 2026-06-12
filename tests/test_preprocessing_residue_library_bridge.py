import json
import re
from pathlib import Path

import pytest

import mania.residue_library as residue_library_module
from mania.preprocessing import (
    PreprocessingResidueLibraryBridgeError,
    ResolvedResidueLibraryManifestOptions,
    load_residue_library_from_manifest_options,
    resolve_residue_library_manifest_paths,
)
from mania.preprocessing.input_manifest import ResidueLibraryInputConfig
from mania.residue_library import ResidueLibrary, ResidueLibraryValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"

FORBIDDEN_SCIENTIFIC_IMPORTS = (
    r"^\s*import\s+MDAnalysis(?:\s|$)",
    r"^\s*from\s+MDAnalysis\s+import\s+",
    r"^\s*import\s+numpy(?:\s|$)",
    r"^\s*from\s+numpy\s+import\s+",
    r"^\s*import\s+pandas(?:\s|$)",
    r"^\s*from\s+pandas\s+import\s+",
    r"^\s*import\s+networkx(?:\s|$)",
    r"^\s*from\s+networkx\s+import\s+",
    r"^\s*import\s+pyarrow(?:\s|$)",
    r"^\s*from\s+pyarrow\s+import\s+",
)


def make_library_payload(
    resname: str,
    *,
    category: str,
    source_file: str,
) -> dict[str, object]:
    return {
        "format": "MANIA_residue_library",
        "format_version": "0.1",
        "topology_files": [source_file],
        "stats": {"residues_total": 1, "patches_total": 0},
        "residues": {
            resname: {
                "resname": resname,
                "block_type": "residue",
                "category": category,
                "source_file": source_file,
                "atoms": [{"name": "C1", "type": "CT1", "charge": 0.0}],
            }
        },
        "patches": {},
    }


def write_library(
    path: Path,
    resname: str,
    *,
    category: str = "protein",
    source_file: str = "tiny.rtf",
) -> Path:
    payload = make_library_payload(
        resname,
        category=category,
        source_file=source_file,
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_residue_library_from_manifest_options(tmp_path: Path) -> None:
    write_library(tmp_path / "residue_library.json", "ALA")
    options = ResidueLibraryInputConfig(library_path="residue_library.json")

    library = load_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert isinstance(library, ResidueLibrary)
    assert library.has_residue("ALA")


def test_missing_library_path_fails_deterministically() -> None:
    options = ResidueLibraryInputConfig(library_path=None)

    with pytest.raises(
        PreprocessingResidueLibraryBridgeError,
        match=r"residue_library\.library_path",
    ):
        load_residue_library_from_manifest_options(options)


def test_relative_paths_resolve_against_base_dir(tmp_path: Path) -> None:
    options = ResidueLibraryInputConfig(
        library_path="libraries/base.json",
        custom_residues_path="libraries/custom.json",
    )

    resolved = resolve_residue_library_manifest_paths(
        options,
        base_dir=tmp_path,
    )

    assert resolved.library_path == tmp_path / "libraries" / "base.json"
    assert (
        resolved.custom_residues_path
        == tmp_path / "libraries" / "custom.json"
    )


def test_absolute_paths_remain_absolute(tmp_path: Path) -> None:
    library_path = write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(library_path=library_path)

    resolved = resolve_residue_library_manifest_paths(
        options,
        base_dir=tmp_path / "unrelated",
    )

    assert resolved.library_path == library_path


def test_custom_residues_are_applied_through_existing_extension(
    tmp_path: Path,
) -> None:
    write_library(tmp_path / "base.json", "ALA")
    write_library(
        tmp_path / "custom.json",
        "USER1",
        category="custom",
        source_file="custom.rtf",
    )
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=False,
    )

    library = load_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert library.has_residue("USER1")
    assert library.classify_residue("USER1") == "custom"


def test_custom_override_is_rejected_when_not_allowed(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA", category="protein")
    write_library(tmp_path / "custom.json", "ALA", category="custom")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=False,
    )

    with pytest.raises(
        ResidueLibraryValidationError,
        match="custom residue would override existing residue: ALA",
    ):
        load_residue_library_from_manifest_options(
            options,
            base_dir=tmp_path,
        )


def test_custom_override_is_applied_when_allowed(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA", category="protein")
    write_library(
        tmp_path / "custom.json",
        "ALA",
        category="custom",
        source_file="custom.rtf",
    )
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=True,
    )

    library = load_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    ala = library.get_residue("ALA")

    assert ala is not None
    assert ala.category == "custom"
    assert ala.source_file == "custom.rtf"


def test_skip_resnames_are_preserved_without_qc() -> None:
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        skip_resnames=[" cla ", "CLA", "sod"],
    )

    resolved = resolve_residue_library_manifest_paths(options)

    assert resolved.skip_resnames == ("CLA", "SOD")


def test_bridge_does_not_run_residue_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(library_path="base.json")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("run_residue_library_qc must not be called")

    monkeypatch.setattr(
        residue_library_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    library = load_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert library.has_residue("ALA")


def test_public_exports_work() -> None:
    assert issubclass(PreprocessingResidueLibraryBridgeError, ValueError)
    assert ResolvedResidueLibraryManifestOptions.__module__ == (
        "mania.preprocessing.residue_library_bridge"
    )
    assert callable(load_residue_library_from_manifest_options)
    assert callable(resolve_residue_library_manifest_paths)


def test_resolved_options_to_dict_is_json_serializable(tmp_path: Path) -> None:
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        skip_resnames=["cla"],
        allow_user_overrides=True,
    )
    resolved = resolve_residue_library_manifest_paths(
        options,
        base_dir=tmp_path,
    )

    payload = resolved.to_dict()

    assert json.loads(json.dumps(payload)) == {
        "library_path": str(tmp_path / "base.json"),
        "custom_residues_path": str(tmp_path / "custom.json"),
        "skip_resnames": ["CLA"],
        "allow_user_overrides": True,
    }


def test_runtime_source_does_not_import_scientific_packages() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py"))
    )

    for pattern in FORBIDDEN_SCIENTIFIC_IMPORTS:
        assert re.search(pattern, runtime_source, flags=re.MULTILINE) is None
