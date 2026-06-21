import json
from pathlib import Path

from mania.preprocessing import (
    PreprocessingReferencePackageIssue,
    PreprocessingReferencePackageReport,
    check_preprocessing_reference_package,
)

VALID_MANIFEST = """\
output_root: output

residue_library:
  library_path: residue_library/mania_residue_library.json
  custom_residues_path: residue_library/custom_residues.json

conditions:
  - condition: normal
    topology_path: data/normal/topology.tpr
    trajectory_paths:
      - data/normal/trajectory.xtc
    reference_structure_path: data/normal/reference.pdb
"""


def write_manifest(
    package_root: Path,
    text: str = VALID_MANIFEST,
    *,
    manifest_name: str = "preprocessing_manifest.yaml",
) -> Path:
    manifest_path = package_root / manifest_name
    manifest_path.write_text(text, encoding="utf-8")
    return manifest_path


def create_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def create_declared_files(package_root: Path) -> None:
    create_file(package_root / "data" / "normal" / "topology.tpr")
    create_file(package_root / "data" / "normal" / "trajectory.xtc")
    create_file(package_root / "data" / "normal" / "reference.pdb")
    create_file(
        package_root
        / "residue_library"
        / "mania_residue_library.json"
    )
    create_file(package_root / "residue_library" / "custom_residues.json")


def test_valid_local_package_passes(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    create_declared_files(tmp_path)

    report = check_preprocessing_reference_package(tmp_path)

    assert isinstance(report, PreprocessingReferencePackageReport)
    assert report.passed is True
    assert report.manifest_loaded is True
    assert report.issues == ()
    assert report.path_validation is not None
    assert report.path_validation.passed is True


def test_missing_package_root_reports_issue(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"

    report = check_preprocessing_reference_package(missing_root)

    assert report.passed is False
    assert report.issues[0].kind == "missing_root"
    assert report.issues[0].field == "package_root"
    assert report.issues[0].path == missing_root
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_package_root_as_file_reports_issue(tmp_path: Path) -> None:
    package_file = create_file(tmp_path / "package")

    report = check_preprocessing_reference_package(package_file)

    assert report.issues[0].kind == "not_directory"
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_missing_manifest_reports_issue(tmp_path: Path) -> None:
    report = check_preprocessing_reference_package(tmp_path)

    assert report.issues[0].kind == "missing_manifest"
    assert report.issues[0].field == "manifest_path"
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_manifest_path_as_directory_reports_issue(tmp_path: Path) -> None:
    (tmp_path / "preprocessing_manifest.yaml").mkdir()

    report = check_preprocessing_reference_package(tmp_path)

    assert report.issues[0].kind == "manifest_not_file"
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_invalid_manifest_reports_load_error(tmp_path: Path) -> None:
    write_manifest(tmp_path, "conditions: [")

    report = check_preprocessing_reference_package(tmp_path)

    assert report.issues[0].kind == "manifest_load_error"
    assert report.issues[0].field == "manifest_path"
    assert report.issues[0].message
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_invalid_manifest_model_reports_load_error(tmp_path: Path) -> None:
    write_manifest(tmp_path, "output_root: output\nconditions: []\n")

    report = check_preprocessing_reference_package(tmp_path)

    assert report.issues[0].kind == "manifest_load_error"
    assert report.manifest_loaded is False
    assert report.path_validation is None


def test_loaded_manifest_reports_nested_missing_paths(tmp_path: Path) -> None:
    write_manifest(
        tmp_path,
        """\
output_root: output
conditions:
  - condition: normal
    topology_path: data/normal/topology.tpr
    trajectory_paths:
      - data/normal/trajectory.xtc
""",
    )

    report = check_preprocessing_reference_package(tmp_path)

    assert report.manifest_loaded is True
    assert report.issues == ()
    assert report.path_validation is not None
    assert report.path_validation.passed is False
    assert {
        issue.field for issue in report.path_validation.issues
    } == {
        "conditions[normal].topology_path",
        "conditions[normal].trajectory_paths[0]",
    }
    assert report.passed is False


def test_custom_manifest_name_works(tmp_path: Path) -> None:
    write_manifest(tmp_path, manifest_name="manifest.yaml")
    create_declared_files(tmp_path)

    report = check_preprocessing_reference_package(
        tmp_path,
        manifest_name="manifest.yaml",
    )

    assert report.passed is True
    assert report.manifest_name == "manifest.yaml"
    assert report.manifest_path == tmp_path / "manifest.yaml"


def test_output_root_behavior_is_delegated(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    create_declared_files(tmp_path)

    default_report = check_preprocessing_reference_package(tmp_path)
    output_report = check_preprocessing_reference_package(
        tmp_path,
        check_output_root=True,
    )

    assert default_report.path_validation is not None
    assert all(
        issue.field != "output_root"
        for issue in default_report.path_validation.issues
    )
    assert default_report.passed is True
    assert output_report.path_validation is not None
    assert any(
        issue.field == "output_root"
        for issue in output_report.path_validation.issues
    )
    assert output_report.passed is False


def test_report_to_dict_is_json_serializable(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    report = check_preprocessing_reference_package(tmp_path)

    payload = report.to_dict()
    json.dumps(payload)

    assert isinstance(payload["package_root"], str)
    assert isinstance(payload["manifest_path"], str)
    path_validation = payload["path_validation"]
    assert isinstance(path_validation, dict)
    assert isinstance(path_validation["checked_paths"][0]["path"], str)
    assert isinstance(path_validation["issues"][0]["resolved_path"], str)


def test_public_exports_work() -> None:
    assert PreprocessingReferencePackageIssue.__module__.endswith(
        "reference_package"
    )
    assert PreprocessingReferencePackageReport.__module__.endswith(
        "reference_package"
    )
    assert callable(check_preprocessing_reference_package)
