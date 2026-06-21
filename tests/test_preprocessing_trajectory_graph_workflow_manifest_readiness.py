import json
from pathlib import Path

import pytest
import yaml

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingGraphWorkflowIssue,
    PreprocessingGraphWorkflowManifestReadinessIssue,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowPlan,
    build_preprocessing_graph_workflow_plan,
    check_preprocessing_graph_workflow_manifest_readiness,
    load_preprocessing_input_manifest,
    validate_preprocessing_manifest_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_graph_workflow.py"
)
WORKFLOW_DOC_PATH = REPO_ROOT / "docs" / "preprocessing_graph_workflow_contract.md"
PARSING_DOC_PATH = REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0001-optional-scientific-dependencies.md"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"


def create_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")
    return path


def write_manifest(
    path: Path,
    *,
    conditions: list[dict[str, object]] | None = None,
) -> Path:
    payload = {
        "output_root": "outputs/napi2b_10ns",
        "conditions": conditions
        if conditions is not None
        else [
            {
                "condition": "normal",
                "topology_path": "../normal/topology.tpr",
                "trajectory_paths": ["../normal/trajectory.xtc"],
            },
            {
                "condition": "tumor",
                "topology_path": "../tumor/topology.tpr",
                "trajectory_paths": ["../tumor/trajectory.xtc"],
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def create_normal_and_tumor_inputs(tmp_path: Path) -> None:
    for condition in ("normal", "tumor"):
        create_file(tmp_path / condition / "topology.tpr")
        create_file(tmp_path / condition / "trajectory.xtc")


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def docs_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WORKFLOW_DOC_PATH, PARSING_DOC_PATH, ADR_PATH)
    )


def issue_kinds(
    result: PreprocessingGraphWorkflowManifestReadinessResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowManifestReadinessIssue is not None
    assert PreprocessingGraphWorkflowManifestReadinessResult is not None
    assert callable(check_preprocessing_graph_workflow_manifest_readiness)


def test_existing_stage_15_1_exports_still_work() -> None:
    exported = (
        PreprocessingGraphWorkflowOptions,
        PreprocessingGraphWorkflowOutputLayout,
        PreprocessingGraphWorkflowIssue,
        PreprocessingGraphWorkflowPlan,
        build_preprocessing_graph_workflow_plan,
    )

    for api in exported:
        assert api is not None


def test_existing_manifest_apis_still_work() -> None:
    assert callable(load_preprocessing_input_manifest)
    assert callable(validate_preprocessing_manifest_paths)


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowManifestReadinessIssue(
        kind="local_path_missing",
        message="A local path is missing.",
        field="conditions[normal].topology_path",
        condition_name="normal",
        path=Path("../normal/topology.tpr"),
        value="normal",
    )

    payload = issue.to_dict()

    assert payload["path"] == "../normal/topology.tpr"
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("kind", ""),
        ("kind", " "),
        ("message", ""),
        ("message", " "),
        ("field", ""),
        ("field", " "),
        ("condition_name", ""),
        ("condition_name", " "),
        ("path", "../normal/topology.tpr"),
        ("value", ""),
        ("value", " "),
    ),
)
def test_issue_rejects_invalid_values(field_name: str, value: object) -> None:
    kwargs: dict[str, object] = {
        "kind": "local_path_missing",
        "message": "A local path is missing.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowManifestReadinessIssue(**kwargs)


def test_result_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowManifestReadinessIssue(
        kind="condition_missing",
        message="Expected condition is missing.",
        condition_name="tumor",
    )
    result = PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_loaded=True,
        manifest_paths_valid=False,
        condition_names=("normal",),
        expected_condition_count=2,
        input_paths=(Path("../normal/topology.tpr"),),
        issues=(issue,),
    )

    assert result.passed is False
    assert result.issue_count == 1
    assert result.condition_count == 1
    assert result.input_path_count == 1
    payload = result.to_dict()
    assert "manifest" not in payload
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("manifest_path", "local_md/manifest.yaml"),
        ("manifest_loaded", 1),
        ("manifest_paths_valid", 0),
        ("condition_names", ["normal"]),
        ("condition_names", ("",)),
        ("expected_condition_count", True),
        ("expected_condition_count", -1),
        ("input_paths", ["../normal/topology.tpr"]),
        ("issues", [object()]),
    ),
)
def test_result_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "manifest_path": Path("local_md/manifests/napi2b_10ns.yaml"),
        "manifest_loaded": True,
        "manifest_paths_valid": True,
        "condition_names": ("normal", "tumor"),
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowManifestReadinessResult(**kwargs)


def test_missing_manifest_path_fails_deterministically(tmp_path: Path) -> None:
    result = check_preprocessing_graph_workflow_manifest_readiness(
        tmp_path / "missing.yaml"
    )

    assert result.passed is False
    assert result.manifest_loaded is False
    assert result.manifest_paths_valid is False
    assert issue_kinds(result) == {"manifest_path_missing"}


def test_directory_manifest_path_fails_deterministically(tmp_path: Path) -> None:
    result = check_preprocessing_graph_workflow_manifest_readiness(tmp_path)

    assert result.passed is False
    assert issue_kinds(result) == {"manifest_path_is_directory"}


def test_invalid_manifest_content_fails_deterministically(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifests" / "napi2b_10ns.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text("{invalid", encoding="utf-8")

    result = check_preprocessing_graph_workflow_manifest_readiness(manifest_path)

    assert result.passed is False
    assert issue_kinds(result) in (
        {"manifest_load_failed"},
        {"manifest_contract_invalid"},
    )


def test_valid_synthetic_manifest_passes_readiness(tmp_path: Path) -> None:
    create_normal_and_tumor_inputs(tmp_path)
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")

    result = check_preprocessing_graph_workflow_manifest_readiness(manifest_path)

    assert result.passed is True
    assert result.manifest_loaded is True
    assert result.manifest_paths_valid is True
    assert result.condition_names == ("normal", "tumor")
    assert result.input_paths == (
        Path("../normal/topology.tpr"),
        Path("../normal/trajectory.xtc"),
        Path("../tumor/topology.tpr"),
        Path("../tumor/trajectory.xtc"),
    )
    assert result.input_path_count == 4
    assert_json_safe(result.to_dict())


def test_missing_local_input_path_fails_readiness(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "trajectory.xtc")
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")

    result = check_preprocessing_graph_workflow_manifest_readiness(manifest_path)

    assert result.passed is False
    assert "local_path_missing" in issue_kinds(result)
    assert result.manifest_loaded is True
    assert result.manifest_paths_valid is False


def test_expected_condition_missing_fails(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "trajectory.xtc")
    manifest_path = write_manifest(
        tmp_path / "manifests" / "one_condition.yaml",
        conditions=[
            {
                "condition": "normal",
                "topology_path": "../normal/topology.tpr",
                "trajectory_paths": ["../normal/trajectory.xtc"],
            }
        ],
    )

    result = check_preprocessing_graph_workflow_manifest_readiness(manifest_path)

    assert result.passed is False
    assert "condition_missing" in issue_kinds(result)
    assert "condition_count_mismatch" in issue_kinds(result)


def test_expected_condition_check_can_be_disabled(tmp_path: Path) -> None:
    create_file(tmp_path / "normal" / "topology.tpr")
    create_file(tmp_path / "normal" / "trajectory.xtc")
    manifest_path = write_manifest(
        tmp_path / "manifests" / "one_condition.yaml",
        conditions=[
            {
                "condition": "normal",
                "topology_path": "../normal/topology.tpr",
                "trajectory_paths": ["../normal/trajectory.xtc"],
            }
        ],
    )

    result = check_preprocessing_graph_workflow_manifest_readiness(
        manifest_path,
        expected_condition_names=None,
    )

    assert result.passed is True
    assert result.expected_condition_count is None
    assert result.condition_names == ("normal",)


def test_condition_ordering_preserves_manifest_order(tmp_path: Path) -> None:
    create_normal_and_tumor_inputs(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "manifests" / "napi2b_10ns.yaml",
        conditions=[
            {
                "condition": "tumor",
                "topology_path": "../tumor/topology.tpr",
                "trajectory_paths": ["../tumor/trajectory.xtc"],
            },
            {
                "condition": "normal",
                "topology_path": "../normal/topology.tpr",
                "trajectory_paths": ["../normal/trajectory.xtc"],
            },
        ],
    )

    result = check_preprocessing_graph_workflow_manifest_readiness(
        manifest_path,
        expected_condition_names=("tumor", "normal"),
    )

    assert result.passed is True
    assert result.condition_names == ("tumor", "normal")


def test_readiness_does_not_create_files_or_directories(tmp_path: Path) -> None:
    create_normal_and_tumor_inputs(tmp_path)
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    check_preprocessing_graph_workflow_manifest_readiness(manifest_path)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_readiness_does_not_load_trajectories() -> None:
    source = module_source()

    for forbidden in (
        "load_manifest_condition_runtimes",
        "load_single_condition_runtime",
        "trajectory_loader",
        "trajectory_runtime",
        "MDAnalysis",
    ):
        assert forbidden not in source


def test_readiness_does_not_compute_rg_or_contacts() -> None:
    source = module_source()

    for forbidden in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "compute_condition_contacts",
        "compute_manifest_contacts",
    ):
        assert forbidden not in source


def test_readiness_does_not_run_export_diagnostics_or_comparison() -> None:
    source = module_source()

    for forbidden in (
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
    ):
        assert forbidden not in source


def test_readiness_does_not_execute_notebook_or_call_cli_workflow() -> None:
    source = module_source()

    for forbidden in (
        "nbconvert",
        "jupyter",
        "papermill",
        "execute_notebook",
        "mania.cli",
        "mania.pipeline",
        "pipeline_steps",
        "workflow_runner",
    ):
        assert forbidden not in source


def test_dependency_free_implementation() -> None:
    source = module_source()

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_docs_mention_stage_15_2_boundary() -> None:
    text = docs_text()

    for phrase in (
        "Stage 15.2",
        "local manifest readiness",
        "existing manifest contract",
        "no new Stage 15 manifest format",
    ):
        assert phrase in text


def test_docs_mention_local_md_local_only_and_default_ci() -> None:
    text = docs_text()

    for phrase in (
        "local_md",
        "local-only",
        "not committed",
        "not required by default CI",
    ):
        assert phrase in text


def test_docs_mention_local_manifest_and_semantic_relative_paths() -> None:
    text = docs_text()

    for phrase in (
        "local_md/manifests/napi2b_10ns.yaml",
        "../normal/topology.tpr",
        "../normal/trajectory.xtc",
        "../tumor/topology.tpr",
        "../tumor/trajectory.xtc",
    ):
        assert phrase in text


def test_docs_mention_future_boundaries() -> None:
    text = docs_text()

    for phrase in (
        "Stage 15.3",
        "runtime loading",
        "MDAnalysis",
        "notebook is not executed",
        "reference comparison remains optional",
        "temporal RIN remains future scope",
    ):
        assert phrase in text


def test_local_md_ignore_guidance_exists() -> None:
    text = GITIGNORE_PATH.read_text(encoding="utf-8")

    for pattern in (
        "local_md/",
        "*.tpr",
        "*.xtc",
        "*.gro",
        "*.cpt",
        "*.edr",
        "*.log",
        "*.dcd",
        "*.psf",
    ):
        assert pattern in text
