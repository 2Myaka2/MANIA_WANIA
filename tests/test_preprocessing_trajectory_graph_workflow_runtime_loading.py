import json
from dataclasses import dataclass
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
    PreprocessingGraphWorkflowRuntimeLoadingIssue,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    build_preprocessing_graph_workflow_plan,
    check_preprocessing_graph_workflow_manifest_readiness,
    load_manifest_condition_runtimes,
    load_preprocessing_graph_workflow_condition_runtimes,
)
from mania.preprocessing import trajectory_graph_workflow as workflow

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


@dataclass(frozen=True)
class FakeRuntimeLoadResult:
    loaded_condition_names: tuple[str, ...]
    passed: bool = True
    internal: object | None = None


def create_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")
    return path


def create_inputs(tmp_path: Path, *condition_names: str) -> None:
    for condition_name in condition_names:
        create_file(tmp_path / condition_name / "topology.tpr")
        create_file(tmp_path / condition_name / "trajectory.xtc")


def write_manifest(
    path: Path,
    *,
    condition_names: tuple[str, ...] = ("normal", "tumor"),
) -> Path:
    payload = {
        "output_root": "outputs/napi2b_10ns",
        "conditions": [
            {
                "condition": condition_name,
                "topology_path": f"../{condition_name}/topology.tpr",
                "trajectory_paths": [
                    f"../{condition_name}/trajectory.xtc",
                ],
            }
            for condition_name in condition_names
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


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
    result: PreprocessingGraphWorkflowRuntimeLoadingResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def readiness_result() -> PreprocessingGraphWorkflowManifestReadinessResult:
    return PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=("normal", "tumor"),
        expected_condition_count=2,
    )


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowRuntimeLoadingIssue is not None
    assert PreprocessingGraphWorkflowRuntimeLoadingResult is not None
    assert callable(load_preprocessing_graph_workflow_condition_runtimes)


def test_existing_stage_15_1_and_15_2_exports_still_work() -> None:
    exported = (
        PreprocessingGraphWorkflowOptions,
        PreprocessingGraphWorkflowOutputLayout,
        PreprocessingGraphWorkflowIssue,
        PreprocessingGraphWorkflowPlan,
        build_preprocessing_graph_workflow_plan,
        PreprocessingGraphWorkflowManifestReadinessIssue,
        PreprocessingGraphWorkflowManifestReadinessResult,
        check_preprocessing_graph_workflow_manifest_readiness,
    )

    for api in exported:
        assert api is not None


def test_existing_stage_11_manifest_runtime_loader_export_still_works() -> None:
    assert callable(load_manifest_condition_runtimes)


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_runtime_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowRuntimeLoadingIssue(
        kind="expected_condition_not_loaded",
        message="Expected condition runtime was not loaded.",
        field="condition_runtime",
        condition_name="tumor",
        path=Path("local_md/manifests/napi2b_10ns.yaml"),
        value="tumor",
    )

    payload = issue.to_dict()

    assert payload["path"] == "local_md/manifests/napi2b_10ns.yaml"
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
        ("path", "manifest.yaml"),
        ("value", ""),
        ("value", " "),
    ),
)
def test_runtime_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": "runtime_load_failed",
        "message": "Runtime loading failed.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowRuntimeLoadingIssue(**kwargs)


def test_runtime_result_validates_and_serializes() -> None:
    raw_result = FakeRuntimeLoadResult(
        loaded_condition_names=("normal", "tumor"),
        internal=object(),
    )
    result = PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal", "tumor"),
        expected_condition_names=("normal", "tumor"),
        runtime_load_result=raw_result,
    )

    payload = result.to_dict()

    assert result.passed is True
    assert result.issue_count == 0
    assert result.condition_count == 2
    assert result.runtime_loaded is True
    assert payload["runtime_load_result_type"].endswith("FakeRuntimeLoadResult")
    assert "internal" not in payload
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("manifest_path", "manifest.yaml"),
        ("manifest_readiness", object()),
        ("condition_names", ["normal"]),
        ("condition_names", ("",)),
        ("expected_condition_names", ["normal"]),
        ("expected_condition_names", ("",)),
        ("issues", [object()]),
    ),
)
def test_runtime_result_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "manifest_path": Path("local_md/manifests/napi2b_10ns.yaml"),
        "manifest_readiness": readiness_result(),
        "condition_names": ("normal", "tumor"),
        "expected_condition_names": ("normal", "tumor"),
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowRuntimeLoadingResult(**kwargs)


def test_readiness_failure_prevents_runtime_loading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = False

    def fake_runtime_loader() -> object:
        nonlocal called
        called = True
        return lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(())

    monkeypatch.setattr(workflow, "_manifest_runtime_loader", fake_runtime_loader)

    result = load_preprocessing_graph_workflow_condition_runtimes(
        tmp_path / "missing.yaml"
    )

    assert result.passed is False
    assert result.runtime_loaded is False
    assert issue_kinds(result) == {"manifest_readiness_failed"}
    assert called is False


def test_valid_readiness_calls_stage_11_manifest_runtime_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal", "tumor")
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")
    calls: list[tuple[tuple[str, ...], Path | None]] = []
    raw_result = FakeRuntimeLoadResult(("normal", "tumor"))

    def fake_load(manifest: object, *, base_dir: str | Path | None = None) -> object:
        calls.append((manifest.condition_names(), Path(base_dir)))
        return raw_result

    monkeypatch.setattr(workflow, "_manifest_runtime_loader", lambda: fake_load)

    result = load_preprocessing_graph_workflow_condition_runtimes(manifest_path)

    assert calls == [(("normal", "tumor"), manifest_path.parent)]
    assert result.passed is True
    assert result.runtime_load_result is raw_result
    assert result.condition_names == ("normal", "tumor")


def test_runtime_loader_failure_is_reported_deterministically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal", "tumor")
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")

    def fake_load(manifest: object, *, base_dir: str | Path | None = None) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(workflow, "_manifest_runtime_loader", lambda: fake_load)

    result = load_preprocessing_graph_workflow_condition_runtimes(manifest_path)

    assert result.passed is False
    assert issue_kinds(result) == {"runtime_load_failed"}


def test_expected_condition_missing_in_readiness_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal")
    manifest_path = write_manifest(
        tmp_path / "manifests" / "one_condition.yaml",
        condition_names=("normal",),
    )
    called = False

    def fake_runtime_loader() -> object:
        nonlocal called
        called = True
        return lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(("normal",))

    monkeypatch.setattr(workflow, "_manifest_runtime_loader", fake_runtime_loader)

    result = load_preprocessing_graph_workflow_condition_runtimes(manifest_path)

    assert result.passed is False
    assert issue_kinds(result) == {"manifest_readiness_failed"}
    assert called is False


def test_expected_condition_not_loaded_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal", "tumor")
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")

    monkeypatch.setattr(
        workflow,
        "_manifest_runtime_loader",
        lambda: lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(
            ("normal",)
        ),
    )

    result = load_preprocessing_graph_workflow_condition_runtimes(manifest_path)

    assert result.passed is False
    assert "expected_condition_not_loaded" in issue_kinds(result)


def test_expected_condition_check_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal")
    manifest_path = write_manifest(
        tmp_path / "manifests" / "one_condition.yaml",
        condition_names=("normal",),
    )

    monkeypatch.setattr(
        workflow,
        "_manifest_runtime_loader",
        lambda: lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(
            ("normal",)
        ),
    )

    result = load_preprocessing_graph_workflow_condition_runtimes(
        manifest_path,
        expected_condition_names=None,
    )

    assert result.passed is True
    assert result.expected_condition_names is None
    assert result.condition_names == ("normal",)


def test_condition_ordering_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal", "tumor")
    manifest_path = write_manifest(
        tmp_path / "manifests" / "napi2b_10ns.yaml",
        condition_names=("tumor", "normal"),
    )

    monkeypatch.setattr(
        workflow,
        "_manifest_runtime_loader",
        lambda: lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(
            ("tumor", "normal")
        ),
    )

    result = load_preprocessing_graph_workflow_condition_runtimes(
        manifest_path,
        expected_condition_names=("tumor", "normal"),
    )

    assert result.condition_names == ("tumor", "normal")


def test_to_dict_excludes_raw_runtime_object_internals() -> None:
    result = PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal", "tumor"),
        expected_condition_names=("normal", "tumor"),
        runtime_load_result=FakeRuntimeLoadResult(
            ("normal", "tumor"),
            internal={"not_json_safe": object()},
        ),
    )

    payload = result.to_dict()

    assert_json_safe(payload)
    assert "not_json_safe" not in json.dumps(payload)


def test_runtime_loading_function_does_not_create_files_or_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_inputs(tmp_path, "normal", "tumor")
    manifest_path = write_manifest(tmp_path / "manifests" / "napi2b_10ns.yaml")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    monkeypatch.setattr(
        workflow,
        "_manifest_runtime_loader",
        lambda: lambda manifest, *, base_dir=None: FakeRuntimeLoadResult(
            ("normal", "tumor")
        ),
    )

    load_preprocessing_graph_workflow_condition_runtimes(manifest_path)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_runtime_loading_function_does_not_compute_rg_or_contacts() -> None:
    source = module_source()

    for forbidden in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "compute_condition_contacts",
        "compute_manifest_contacts",
    ):
        assert forbidden not in source


def test_runtime_loading_function_does_not_export_graph_artifacts() -> None:
    source = module_source()

    for forbidden in (
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
    ):
        assert forbidden not in source


def test_runtime_loading_function_does_not_run_diagnostics_or_comparison() -> None:
    source = module_source()

    for forbidden in (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
    ):
        assert forbidden not in source


def test_runtime_loading_function_does_not_execute_notebook() -> None:
    source = module_source()

    for forbidden in ("nbconvert", "jupyter", "papermill", "execute_notebook"):
        assert forbidden not in source


def test_runtime_loading_function_does_not_call_cli_or_workflow() -> None:
    source = module_source()

    for forbidden in (
        "mania.cli",
        "mania.pipeline",
        "pipeline_steps",
        "workflow_runner",
    ):
        assert forbidden not in source


def test_dependency_free_imports() -> None:
    source = module_source()

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_docs_mention_stage_15_3_boundary() -> None:
    text = docs_text()

    for phrase in (
        "Stage 15.3",
        "manifest-driven runtime loading",
        "two conditions",
        "no Rg/contacts/graph/diagnostics/reference/CLI",
    ):
        assert phrase in text


def test_docs_mention_readiness_first_and_stage_11_reuse() -> None:
    text = docs_text()

    for phrase in (
        "readiness is called before runtime loading",
        "readiness failure prevents runtime loading",
        "existing Stage 11 runtime/manifest loading APIs",
        "no new runtime loader",
    ):
        assert phrase in text


def test_docs_mention_ci_local_and_future_boundaries() -> None:
    text = docs_text()

    for phrase in (
        "import/default CI does not require MDAnalysis",
        "real runtime loading remains optional/local/scientific",
        "local_md",
        "local-only",
        "not committed",
        "not required by default CI",
        "Stage 15.4 will orchestrate manifest-level Rg + contacts",
        "Stage 15.3 does not compute them",
        "MANIA_analysis_v1_2",
        "notebook not executed",
        "reference comparison remains Stage 15.7 optional mode",
        "temporal RIN remains future scope",
        "WANIA frontend adapter/API payload remains future scope",
    ):
        assert phrase in text
