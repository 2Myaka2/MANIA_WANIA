import json
from pathlib import Path

import pytest

from mania.preprocessing import (
    PreprocessingCheckedPath,
    PreprocessingInputManifest,
    PreprocessingPathValidationIssue,
    PreprocessingPathValidationReport,
    load_preprocessing_input_manifest,
    validate_preprocessing_manifest_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MINIMAL_EXAMPLE_PATH = (
    REPO_ROOT / "examples" / "preprocessing" / "minimal_manifest.yaml"
)


def make_manifest(
    *,
    topology_path: str | Path = "normal/topology.tpr",
    trajectory_paths: tuple[str | Path, ...] = ("normal/traj.xtc",),
    reference_structure_path: str | Path | None = None,
    library_path: str | Path | None = None,
    custom_residues_path: str | Path | None = None,
    output_root: str | Path = "output",
) -> PreprocessingInputManifest:
    condition: dict[str, object] = {
        "condition": "normal",
        "topology_path": topology_path,
        "trajectory_paths": trajectory_paths,
    }
    if reference_structure_path is not None:
        condition["reference_structure_path"] = reference_structure_path

    return PreprocessingInputManifest(
        output_root=output_root,
        conditions=[condition],
        residue_library={
            "library_path": library_path,
            "custom_residues_path": custom_residues_path,
        },
    )


def create_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")
    return path


def issue_by_field(
    report: PreprocessingPathValidationReport,
    field: str,
) -> PreprocessingPathValidationIssue:
    return next(issue for issue in report.issues if issue.field == field)


def test_valid_local_files_pass(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")
    create_file(tmp_path / "normal" / "reference.pdb")
    create_file(tmp_path / "residue_library" / "mania_residue_library.json")
    create_file(tmp_path / "residue_library" / "custom_residues.json")
    manifest = make_manifest(
        reference_structure_path="normal/reference.pdb",
        library_path="residue_library/mania_residue_library.json",
        custom_residues_path="residue_library/custom_residues.json",
        output_root="missing-output",
    )

    report = validate_preprocessing_manifest_paths(manifest, base_dir=tmp_path)

    assert isinstance(report, PreprocessingPathValidationReport)
    assert report.passed is True
    assert report.issues == ()
    assert tuple(checked.field for checked in report.checked_paths) == (
        "conditions[normal].topology_path",
        "conditions[normal].trajectory_paths[0]",
        "conditions[normal].reference_structure_path",
        "residue_library.library_path",
        "residue_library.custom_residues_path",
    )
    assert all(
        checked.required_type == "file" for checked in report.checked_paths
    )


def test_missing_files_are_reported(tmp_path: Path) -> None:
    manifest = make_manifest()

    report = validate_preprocessing_manifest_paths(manifest, base_dir=tmp_path)

    assert report.passed is False
    topology_issue = issue_by_field(
        report,
        "conditions[normal].topology_path",
    )
    trajectory_issue = issue_by_field(
        report,
        "conditions[normal].trajectory_paths[0]",
    )
    assert topology_issue.kind == "missing"
    assert topology_issue.condition == "normal"
    assert trajectory_issue.kind == "missing"
    assert trajectory_issue.condition == "normal"


@pytest.mark.parametrize(
    ("field", "path"),
    (
        ("conditions[normal].topology_path", "normal/topology.tpr"),
        ("conditions[normal].trajectory_paths[0]", "normal/traj.xtc"),
    ),
)
def test_directories_where_files_are_expected_are_reported(
    tmp_path: Path,
    field: str,
    path: str,
) -> None:
    (tmp_path / path).mkdir(parents=True)
    manifest = make_manifest()

    report = validate_preprocessing_manifest_paths(manifest, base_dir=tmp_path)

    assert issue_by_field(report, field).kind == "not_file"


def test_optional_reference_structure_is_skipped_when_absent(
    tmp_path: Path,
) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")

    report = validate_preprocessing_manifest_paths(
        make_manifest(),
        base_dir=tmp_path,
    )

    assert all(
        "reference_structure_path" not in checked.field
        for checked in report.checked_paths
    )


def test_residue_library_paths_are_checked_only_when_provided(
    tmp_path: Path,
) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")

    without_paths = validate_preprocessing_manifest_paths(
        make_manifest(),
        base_dir=tmp_path,
    )
    with_paths = validate_preprocessing_manifest_paths(
        make_manifest(
            library_path="residue_library/library.json",
            custom_residues_path="residue_library/custom.json",
        ),
        base_dir=tmp_path,
    )

    assert all(
        not checked.field.startswith("residue_library.")
        for checked in without_paths.checked_paths
    )
    assert issue_by_field(
        with_paths,
        "residue_library.library_path",
    ).kind == "missing"
    assert issue_by_field(
        with_paths,
        "residue_library.custom_residues_path",
    ).kind == "missing"


def test_base_dir_resolves_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files_dir = tmp_path / "files"
    empty_dir = tmp_path / "empty"
    create_file(files_dir / "normal" / "topology.tpr")
    create_file(files_dir / "normal" / "traj.xtc")
    empty_dir.mkdir()
    manifest = make_manifest()

    with_base = validate_preprocessing_manifest_paths(
        manifest,
        base_dir=files_dir,
    )
    monkeypatch.chdir(empty_dir)
    without_base = validate_preprocessing_manifest_paths(manifest)

    assert with_base.passed is True
    assert without_base.passed is False
    assert all(
        checked.resolved_path == checked.path
        for checked in without_base.checked_paths
    )


def test_absolute_paths_remain_absolute(tmp_path: Path) -> None:
    topology_path = create_file(tmp_path / "normal" / "topology.tpr")
    trajectory_path = create_file(tmp_path / "normal" / "traj.xtc")
    manifest = make_manifest(
        topology_path=topology_path,
        trajectory_paths=(trajectory_path,),
    )

    report = validate_preprocessing_manifest_paths(
        manifest,
        base_dir=tmp_path / "unrelated",
    )

    assert report.passed is True
    assert tuple(checked.resolved_path for checked in report.checked_paths) == (
        topology_path,
        trajectory_path,
    )


def test_output_root_is_not_checked_by_default(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")
    manifest = make_manifest(output_root="missing-output")

    report = validate_preprocessing_manifest_paths(manifest, base_dir=tmp_path)

    assert all(issue.field != "output_root" for issue in report.issues)
    assert all(checked.field != "output_root" for checked in report.checked_paths)
    assert not (tmp_path / "missing-output").exists()


def test_check_output_root_reports_missing_directory(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")

    report = validate_preprocessing_manifest_paths(
        make_manifest(output_root="missing-output"),
        base_dir=tmp_path,
        check_output_root=True,
    )

    assert issue_by_field(report, "output_root").kind == "missing"
    output_check = next(
        checked for checked in report.checked_paths if checked.field == "output_root"
    )
    assert output_check.required_type == "directory"


def test_check_output_root_rejects_file(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")
    create_file(tmp_path / "output")

    report = validate_preprocessing_manifest_paths(
        make_manifest(),
        base_dir=tmp_path,
        check_output_root=True,
    )

    assert issue_by_field(report, "output_root").kind == "not_directory"


def test_check_output_root_accepts_directory(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "traj.xtc")
    (tmp_path / "output").mkdir()

    report = validate_preprocessing_manifest_paths(
        make_manifest(),
        base_dir=tmp_path,
        check_output_root=True,
    )

    assert report.passed is True
    assert all(issue.field != "output_root" for issue in report.issues)


def test_report_to_dict_is_json_serializable(tmp_path: Path) -> None:
    report = validate_preprocessing_manifest_paths(
        make_manifest(),
        base_dir=tmp_path,
    )

    payload = report.to_dict()
    json.dumps(payload)

    checked_paths = payload["checked_paths"]
    issues = payload["issues"]
    assert isinstance(checked_paths, list)
    assert isinstance(issues, list)
    assert isinstance(checked_paths[0]["path"], str)
    assert isinstance(checked_paths[0]["resolved_path"], str)
    assert isinstance(issues[0]["path"], str)
    assert isinstance(issues[0]["resolved_path"], str)


def test_loader_still_does_not_validate_declared_file_existence() -> None:
    manifest = load_preprocessing_input_manifest(MINIMAL_EXAMPLE_PATH)

    report = validate_preprocessing_manifest_paths(
        manifest,
        base_dir=MINIMAL_EXAMPLE_PATH.parent,
    )

    assert manifest.condition_names() == ("normal",)
    assert report.passed is False
    assert {
        issue.field for issue in report.issues
    } == {
        "conditions[normal].topology_path",
        "conditions[normal].trajectory_paths[0]",
    }


def test_public_exports_work() -> None:
    assert PreprocessingCheckedPath.__module__.endswith("path_validation")
    assert PreprocessingPathValidationIssue.__module__.endswith("path_validation")
    assert PreprocessingPathValidationReport.__module__.endswith("path_validation")
    assert callable(validate_preprocessing_manifest_paths)
