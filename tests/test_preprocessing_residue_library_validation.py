import json
import re
from pathlib import Path

import pytest

import mania.residue_library as residue_library_module
from mania.preprocessing import (
    PreprocessingResidueLibraryValidationIssue,
    PreprocessingResidueLibraryValidationReport,
    validate_residue_library_from_manifest_options,
)
from mania.preprocessing.input_manifest import ResidueLibraryInputConfig

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
    category: str = "protein",
    source_file: str = "tiny.rtf",
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
    path.write_text(
        json.dumps(
            make_library_payload(
                resname,
                category=category,
                source_file=source_file,
            )
        ),
        encoding="utf-8",
    )
    return path


def only_issue(
    report: PreprocessingResidueLibraryValidationReport,
) -> PreprocessingResidueLibraryValidationIssue:
    assert len(report.issues) == 1
    return report.issues[0]


def test_valid_source_residue_library_passes(tmp_path: Path) -> None:
    write_library(tmp_path / "residue_library.json", "ALA")
    options = ResidueLibraryInputConfig(library_path="residue_library.json")

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert isinstance(report, PreprocessingResidueLibraryValidationReport)
    assert report.passed is True
    assert report.issues == ()
    assert report.library_loaded is True
    assert report.custom_residues_applied is False
    assert report.residue_count == 1


def test_missing_library_path_returns_deterministic_issue() -> None:
    options = ResidueLibraryInputConfig(library_path=None)

    report = validate_residue_library_from_manifest_options(options)
    issue = only_issue(report)

    assert report.passed is False
    assert report.resolved_options is None
    assert issue.kind == "missing_library_path"
    assert issue.field == "residue_library.library_path"
    assert issue.path is None
    assert issue.resolved_path is None


def test_missing_source_library_file_is_reported(tmp_path: Path) -> None:
    options = ResidueLibraryInputConfig(library_path="missing.json")

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "missing_file"
    assert issue.field == "residue_library.library_path"
    assert issue.path == Path("missing.json")
    assert issue.resolved_path == tmp_path / "missing.json"
    assert report.library_loaded is False


def test_source_library_directory_is_reported(tmp_path: Path) -> None:
    library_path = tmp_path / "library.json"
    library_path.mkdir()
    options = ResidueLibraryInputConfig(library_path="library.json")

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "not_file"
    assert issue.field == "residue_library.library_path"
    assert report.library_loaded is False


def test_invalid_source_library_is_reported(tmp_path: Path) -> None:
    (tmp_path / "invalid.json").write_text("{", encoding="utf-8")
    options = ResidueLibraryInputConfig(library_path="invalid.json")

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "load_error"
    assert issue.field == "residue_library.library_path"
    assert report.library_loaded is False
    assert report.passed is False


def test_valid_custom_residues_are_applied(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA")
    write_library(tmp_path / "custom.json", "USER1", category="custom")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert report.passed is True
    assert report.library_loaded is True
    assert report.custom_residues_applied is True
    assert report.residue_count == 2


def test_missing_custom_residue_file_is_reported(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="missing-custom.json",
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "missing_file"
    assert issue.field == "residue_library.custom_residues_path"
    assert report.library_loaded is True
    assert report.custom_residues_applied is False
    assert report.residue_count == 1
    assert report.passed is False


def test_custom_residue_directory_is_reported(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA")
    (tmp_path / "custom.json").mkdir()
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "not_file"
    assert issue.field == "residue_library.custom_residues_path"
    assert report.library_loaded is True


def test_invalid_custom_residue_file_is_reported(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA")
    (tmp_path / "custom.json").write_text("[]", encoding="utf-8")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "custom_load_error"
    assert report.library_loaded is True
    assert report.custom_residues_applied is False
    assert report.passed is False


def test_disallowed_custom_override_is_reported(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA", category="protein")
    write_library(tmp_path / "custom.json", "ALA", category="custom")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=False,
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    issue = only_issue(report)

    assert issue.kind == "extension_error"
    assert "override existing residue: ALA" in issue.message
    assert report.library_loaded is True
    assert report.custom_residues_applied is False
    assert report.residue_count == 1


def test_allowed_custom_override_passes(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA", category="protein")
    write_library(tmp_path / "custom.json", "ALA", category="custom")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=True,
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert report.passed is True
    assert report.custom_residues_applied is True
    assert report.residue_count == 1


def test_relative_paths_resolve_against_base_dir(tmp_path: Path) -> None:
    libraries_dir = tmp_path / "libraries"
    libraries_dir.mkdir()
    write_library(libraries_dir / "base.json", "ALA")
    options = ResidueLibraryInputConfig(
        library_path="libraries/base.json",
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert report.passed is True
    assert report.resolved_options is not None
    assert report.resolved_options.library_path == libraries_dir / "base.json"


def test_absolute_paths_remain_absolute(tmp_path: Path) -> None:
    library_path = write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(library_path=library_path)

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path / "unrelated",
    )

    assert report.passed is True
    assert report.resolved_options is not None
    assert report.resolved_options.library_path == library_path


def test_skip_resnames_are_preserved_without_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        skip_resnames=[" cla ", "CLA", "sod"],
    )

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("run_residue_library_qc must not be called")

    monkeypatch.setattr(
        residue_library_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )

    assert report.passed is True
    assert report.resolved_options is not None
    assert report.resolved_options.skip_resnames == ("CLA", "SOD")


def test_report_to_dict_is_json_serializable(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", "ALA")
    options = ResidueLibraryInputConfig(library_path="base.json")

    report = validate_residue_library_from_manifest_options(
        options,
        base_dir=tmp_path,
    )
    payload = report.to_dict()

    assert json.loads(json.dumps(payload)) == payload
    resolved_options = payload["resolved_options"]
    assert isinstance(resolved_options, dict)
    assert resolved_options["library_path"] == str(tmp_path / "base.json")
    assert "ResidueLibrary" not in repr(payload)


def test_public_exports_work() -> None:
    assert PreprocessingResidueLibraryValidationIssue.__module__.endswith(
        "residue_library_validation"
    )
    assert PreprocessingResidueLibraryValidationReport.__module__.endswith(
        "residue_library_validation"
    )
    assert callable(validate_residue_library_from_manifest_options)


def test_runtime_source_does_not_import_scientific_packages() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py"))
    )

    for pattern in FORBIDDEN_SCIENTIFIC_IMPORTS:
        assert re.search(pattern, runtime_source, flags=re.MULTILINE) is None
