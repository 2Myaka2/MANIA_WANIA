import json
import re
from pathlib import Path

import pytest

import mania.preprocessing.residue_qc as residue_qc_module
from mania.preprocessing import (
    PreprocessingResidueQCIssue,
    PreprocessingResidueQCReport,
    run_residue_qc_from_manifest_options,
)
from mania.preprocessing.input_manifest import ResidueLibraryInputConfig
from mania.residue_library import ResidueLibraryQCError

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
    residues: dict[str, str],
    *,
    source_file: str = "tiny.rtf",
) -> dict[str, object]:
    return {
        "format": "MANIA_residue_library",
        "format_version": "0.1",
        "topology_files": [source_file],
        "stats": {
            "residues_total": len(residues),
            "patches_total": 0,
        },
        "residues": {
            resname: {
                "resname": resname,
                "block_type": "residue",
                "category": category,
                "source_file": source_file,
                "atoms": [{"name": "C1", "type": "CT1", "charge": 0.0}],
            }
            for resname, category in residues.items()
        },
        "patches": {},
    }


def write_library(
    path: Path,
    residues: dict[str, str],
    *,
    source_file: str = "tiny.rtf",
) -> Path:
    path.write_text(
        json.dumps(make_library_payload(residues, source_file=source_file)),
        encoding="utf-8",
    )
    return path


def only_issue(report: PreprocessingResidueQCReport) -> PreprocessingResidueQCIssue:
    assert len(report.issues) == 1
    return report.issues[0]


def test_valid_explicit_residue_names_pass(tmp_path: Path) -> None:
    write_library(
        tmp_path / "residue_library.json",
        {"ALA": "protein", "GLY": "protein"},
    )
    options = ResidueLibraryInputConfig(library_path="residue_library.json")

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA", "GLY"],
        base_dir=tmp_path,
    )

    assert isinstance(report, PreprocessingResidueQCReport)
    assert report.residue_library_validation.passed is True
    assert report.qc_report is not None
    assert report.passed is True
    assert json.loads(json.dumps(report.to_dict())) == report.to_dict()


def test_unknown_residue_follows_existing_qc_semantics(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA", "UNKNOWN"],
        base_dir=tmp_path,
    )
    payload = report.to_dict()

    assert report.qc_report is not None
    assert report.qc_report.has_errors() is True
    assert report.qc_report.unknown_resnames() == ("UNKNOWN",)
    assert report.passed is False
    assert payload["qc_report"]["unknown_resnames"] == ["UNKNOWN"]  # type: ignore[index]


def test_missing_library_path_prevents_qc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = ResidueLibraryInputConfig(library_path=None)

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(options, ["ALA"])

    assert report.residue_library_validation.passed is False
    assert only_issue(report).kind == "residue_library_validation_failed"
    assert report.qc_report is None


def test_invalid_residue_library_prevents_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "invalid.json").write_text("{", encoding="utf-8")
    options = ResidueLibraryInputConfig(library_path="invalid.json")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )

    assert report.residue_library_validation.passed is False
    assert only_issue(report).kind == "residue_library_validation_failed"
    assert report.qc_report is None


def test_empty_residue_names_return_deterministic_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        [],
        base_dir=tmp_path,
    )

    assert only_issue(report).kind == "empty_residue_names"
    assert report.qc_report is None


@pytest.mark.parametrize("residue_names", [[1], ["   "], "ALA"])
def test_invalid_residue_name_input_returns_deterministic_issue(
    tmp_path: Path,
    residue_names: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        residue_names,  # type: ignore[arg-type]
        base_dir=tmp_path,
    )

    assert only_issue(report).kind == "invalid_residue_name"
    assert report.qc_report is None


def test_residue_names_are_stripped(tmp_path: Path) -> None:
    write_library(
        tmp_path / "base.json",
        {"ALA": "protein", "GLY": "protein"},
    )
    options = ResidueLibraryInputConfig(library_path="base.json")

    report = run_residue_qc_from_manifest_options(
        options,
        [" ala ", " GLY"],
        base_dir=tmp_path,
    )

    assert report.residue_names == ("ala", "GLY")
    assert report.checked_residue_names == ("ala", "GLY")
    assert report.skipped_residue_names == ()
    assert report.passed is True


def test_skip_resnames_filter_names_before_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        skip_resnames=["cla"],
    )
    original_qc = residue_qc_module.run_residue_library_qc
    received_names: tuple[str, ...] = ()

    def record_qc(
        resnames_by_condition: dict[str, tuple[str, ...]],
        *args: object,
        **kwargs: object,
    ) -> object:
        nonlocal received_names
        received_names = resnames_by_condition["explicit"]
        return original_qc(resnames_by_condition, *args, **kwargs)

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        record_qc,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA", " cla "],
        base_dir=tmp_path,
    )

    assert report.residue_names == ("ALA", "cla")
    assert report.checked_residue_names == ("ALA",)
    assert report.skipped_residue_names == ("cla",)
    assert received_names == ("ALA",)
    assert report.passed is True


def test_all_names_skipped_returns_empty_input_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        skip_resnames=["cla", "sod"],
    )

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["CLA", " sod "],
        base_dir=tmp_path,
    )

    assert only_issue(report).kind == "empty_residue_names"
    assert report.skipped_residue_names == ("CLA", "sod")
    assert report.checked_residue_names == ()
    assert report.qc_report is None


def test_custom_residue_participates_in_qc(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    write_library(tmp_path / "custom.json", {"USER1": "custom"})
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["USER1"],
        base_dir=tmp_path,
    )

    assert report.residue_library_validation.passed is True
    assert report.qc_report is not None
    assert report.qc_report.unknown_resnames() == ()
    assert report.passed is True


def test_disallowed_override_fails_before_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    write_library(tmp_path / "custom.json", {"ALA": "custom"})
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=False,
    )

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("QC must not be called")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        fail_if_called,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )

    assert report.residue_library_validation.passed is False
    assert only_issue(report).kind == "residue_library_validation_failed"
    assert report.qc_report is None


def test_allowed_override_runs_qc(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    write_library(tmp_path / "custom.json", {"ALA": "custom"})
    options = ResidueLibraryInputConfig(
        library_path="base.json",
        custom_residues_path="custom.json",
        allow_user_overrides=True,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )

    assert report.residue_library_validation.passed is True
    assert report.qc_report is not None
    assert report.passed is True


def test_existing_qc_is_called_for_valid_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")
    original_qc = residue_qc_module.run_residue_library_qc
    called = False

    def record_qc(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        return original_qc(*args, **kwargs)

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        record_qc,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )

    assert called is True
    assert report.passed is True


def test_expected_qc_error_becomes_deterministic_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")

    def raise_qc_error(*args: object, **kwargs: object) -> None:
        raise ResidueLibraryQCError("expected local failure")

    monkeypatch.setattr(
        residue_qc_module,
        "run_residue_library_qc",
        raise_qc_error,
    )

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )

    issue = only_issue(report)
    assert issue.kind == "qc_error"
    assert issue.field == "residue_qc"
    assert "expected local failure" in issue.message
    assert report.qc_report is None


def test_report_to_dict_is_json_serializable(tmp_path: Path) -> None:
    write_library(tmp_path / "base.json", {"ALA": "protein"})
    options = ResidueLibraryInputConfig(library_path="base.json")

    report = run_residue_qc_from_manifest_options(
        options,
        ["ALA"],
        base_dir=tmp_path,
    )
    payload = report.to_dict()

    assert json.loads(json.dumps(payload)) == payload
    assert "ResidueLibrary" not in repr(payload)


def test_public_exports_work() -> None:
    assert PreprocessingResidueQCIssue.__module__.endswith("residue_qc")
    assert PreprocessingResidueQCReport.__module__.endswith("residue_qc")
    assert callable(run_residue_qc_from_manifest_options)


def test_runtime_source_does_not_import_scientific_packages() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py"))
    )

    for pattern in FORBIDDEN_SCIENTIFIC_IMPORTS:
        assert re.search(pattern, runtime_source, flags=re.MULTILINE) is None
