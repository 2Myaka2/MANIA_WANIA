import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingContactDetectionOptions,
    PreprocessingFrameSamplingOptions,
    PreprocessingGraphWorkflowComputationIssue,
    PreprocessingGraphWorkflowComputationResult,
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
    compute_manifest_contacts,
    compute_manifest_rg,
    compute_preprocessing_graph_workflow_rg_contacts,
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


@dataclass(frozen=True)
class FakeComputationResult:
    passed: bool
    internal: object | None = None


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def wrapper_source() -> str:
    return inspect.getsource(
        workflow.compute_preprocessing_graph_workflow_rg_contacts
    )


def docs_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WORKFLOW_DOC_PATH, PARSING_DOC_PATH, ADR_PATH)
    )


def readiness_result(
    condition_names: tuple[str, ...] = ("normal", "tumor"),
) -> PreprocessingGraphWorkflowManifestReadinessResult:
    return PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=condition_names,
        expected_condition_count=len(condition_names),
    )


def runtime_loading_result(
    *,
    condition_names: tuple[str, ...] = ("normal", "tumor"),
    runtime_load_result: object | None = None,
    issues: tuple[PreprocessingGraphWorkflowRuntimeLoadingIssue, ...] = (),
) -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    if runtime_load_result is None:
        runtime_load_result = FakeRuntimeLoadResult(condition_names)
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(condition_names),
        condition_names=condition_names,
        expected_condition_names=condition_names,
        runtime_load_result=runtime_load_result,
        issues=issues,
    )


def missing_raw_runtime_loading_result(
) -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal", "tumor"),
        expected_condition_names=("normal", "tumor"),
        runtime_load_result=None,
    )


def issue_kinds(
    result: PreprocessingGraphWorkflowComputationResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def patch_computers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rg_result: object | None = None,
    contacts_result: object | None = None,
    rg_raises: Exception | None = None,
    contacts_raises: Exception | None = None,
) -> tuple[list[object], list[tuple[object, dict[str, object]]]]:
    rg_calls: list[object] = []
    contacts_calls: list[tuple[object, dict[str, object]]] = []

    def fake_rg(runtime_result: object, **kwargs: object) -> object:
        del kwargs
        rg_calls.append(runtime_result)
        if rg_raises is not None:
            raise rg_raises
        return rg_result or FakeComputationResult(passed=True)

    def fake_contacts(runtime_result: object, **kwargs: object) -> object:
        contacts_calls.append((runtime_result, kwargs))
        if contacts_raises is not None:
            raise contacts_raises
        return contacts_result or FakeComputationResult(passed=True)

    monkeypatch.setattr(workflow, "_manifest_rg_computer", lambda: fake_rg)
    monkeypatch.setattr(
        workflow,
        "_manifest_contacts_computer",
        lambda: fake_contacts,
    )
    return rg_calls, contacts_calls


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowComputationIssue is not None
    assert PreprocessingGraphWorkflowComputationResult is not None
    assert callable(compute_preprocessing_graph_workflow_rg_contacts)


def test_existing_stage_15_1_to_15_3_exports_still_work() -> None:
    for api in (
        PreprocessingGraphWorkflowOptions,
        PreprocessingGraphWorkflowOutputLayout,
        PreprocessingGraphWorkflowIssue,
        PreprocessingGraphWorkflowPlan,
        build_preprocessing_graph_workflow_plan,
        PreprocessingGraphWorkflowManifestReadinessIssue,
        PreprocessingGraphWorkflowManifestReadinessResult,
        check_preprocessing_graph_workflow_manifest_readiness,
        PreprocessingGraphWorkflowRuntimeLoadingIssue,
        PreprocessingGraphWorkflowRuntimeLoadingResult,
        load_preprocessing_graph_workflow_condition_runtimes,
    ):
        assert api is not None


def test_existing_rg_and_contacts_exports_still_work() -> None:
    assert callable(compute_manifest_rg)
    assert callable(compute_manifest_contacts)
    assert PreprocessingContactDetectionOptions is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_computation_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowComputationIssue(
        kind="rg_computation_failed",
        message="Rg failed.",
        stage="rg",
        condition_name="normal",
        field="rg_result",
        value="Fake",
    )

    assert_json_safe(issue.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("kind", ""),
        ("kind", " "),
        ("message", ""),
        ("message", " "),
        ("stage", ""),
        ("condition_name", ""),
        ("field", ""),
        ("value", ""),
    ),
)
def test_computation_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": "rg_computation_failed",
        "message": "Rg failed.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowComputationIssue(**kwargs)


def test_computation_result_validates_and_serializes() -> None:
    raw_rg = FakeComputationResult(passed=True, internal={"not_json": object()})
    raw_contacts = FakeComputationResult(passed=True, internal=object())
    result = PreprocessingGraphWorkflowComputationResult(
        runtime_loading=runtime_loading_result(),
        condition_names=("normal", "tumor"),
        include_rg=True,
        include_contacts=True,
        rg_result=raw_rg,
        contacts_result=raw_contacts,
    )

    payload = result.to_dict()

    assert result.passed is True
    assert result.issue_count == 0
    assert result.condition_count == 2
    assert result.rg_computed is True
    assert result.contacts_computed is True
    assert "not_json" not in json.dumps(payload)
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("runtime_loading", object()),
        ("condition_names", ["normal"]),
        ("condition_names", ("",)),
        ("include_rg", 1),
        ("include_contacts", 0),
        ("frame_sampling", object()),
        ("issues", [PreprocessingGraphWorkflowComputationIssue("x", "y")]),
        ("issues", (object(),)),
    ),
)
def test_computation_result_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "runtime_loading": runtime_loading_result(),
        "condition_names": ("normal", "tumor"),
        "include_rg": True,
        "include_contacts": True,
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowComputationResult(**kwargs)


def test_runtime_loading_failure_prevents_computations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(monkeypatch)
    failed_runtime = PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal",),
        expected_condition_names=("normal", "tumor"),
        runtime_load_result=FakeRuntimeLoadResult(("normal",)),
        issues=(
            PreprocessingGraphWorkflowRuntimeLoadingIssue(
                kind="expected_condition_not_loaded",
                message="Expected condition runtime was not loaded.",
            ),
        ),
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(failed_runtime)

    assert result.passed is False
    assert issue_kinds(result) == {"runtime_loading_failed"}
    assert rg_calls == []
    assert contacts_calls == []


def test_missing_raw_runtime_load_result_fails_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(monkeypatch)

    result = compute_preprocessing_graph_workflow_rg_contacts(
        missing_raw_runtime_loading_result()
    )

    assert result.passed is False
    assert issue_kinds(result) == {"runtime_load_result_missing"}
    assert rg_calls == []
    assert contacts_calls == []


def test_both_computations_disabled_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(monkeypatch)

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(),
        include_rg=False,
        include_contacts=False,
    )

    assert result.passed is False
    assert issue_kinds(result) == {"no_computation_targets_enabled"}
    assert rg_calls == []
    assert contacts_calls == []


def test_default_call_computes_both_and_retains_raw_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_runtime = FakeRuntimeLoadResult(("normal", "tumor"), internal=object())
    raw_rg = FakeComputationResult(passed=True, internal=object())
    raw_contacts = FakeComputationResult(passed=True, internal=object())
    rg_calls, contacts_calls = patch_computers(
        monkeypatch,
        rg_result=raw_rg,
        contacts_result=raw_contacts,
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(runtime_load_result=raw_runtime)
    )

    assert rg_calls == [raw_runtime]
    assert contacts_calls == [(raw_runtime, {})]
    assert result.passed is True
    assert result.rg_result is raw_rg
    assert result.contacts_result is raw_contacts
    assert result.to_dict()["rg_result_type"].endswith("FakeComputationResult")


def test_rg_only_and_contacts_only_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(monkeypatch)

    rg_only = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(),
        include_rg=True,
        include_contacts=False,
    )
    contacts_only = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(),
        include_rg=False,
        include_contacts=True,
    )

    assert rg_only.passed is True
    assert contacts_only.passed is True
    assert len(rg_calls) == 1
    assert len(contacts_calls) == 1


def test_rg_failure_is_reported_and_contacts_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(
        monkeypatch,
        rg_result=FakeComputationResult(passed=False),
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result()
    )

    assert result.passed is False
    assert issue_kinds(result) == {"rg_computation_failed"}
    assert len(rg_calls) == 1
    assert len(contacts_calls) == 1


def test_contacts_failure_is_reported_and_rg_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg_calls, contacts_calls = patch_computers(
        monkeypatch,
        contacts_raises=RuntimeError("boom"),
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result()
    )

    assert result.passed is False
    assert issue_kinds(result) == {"contacts_computation_failed"}
    assert len(rg_calls) == 1
    assert len(contacts_calls) == 1


def test_invalid_computation_result_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_computers(monkeypatch, rg_result=object(), contacts_result=object())

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result()
    )

    assert result.passed is False
    assert issue_kinds(result) == {"computation_result_invalid"}


def test_contact_options_are_passed_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, contacts_calls = patch_computers(monkeypatch)
    options = PreprocessingContactDetectionOptions(cutoff_distance=6.0)

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(),
        include_rg=False,
        contact_options=options,
    )

    assert result.passed is True
    assert contacts_calls[0][1]["options"] is options


def test_frame_sampling_is_passed_to_rg_and_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_runtime = FakeRuntimeLoadResult(("normal", "tumor"), internal=object())
    frame_sampling = PreprocessingFrameSamplingOptions(frame_stride=2)
    rg_kwargs: list[dict[str, object]] = []
    contacts_kwargs: list[dict[str, object]] = []

    def fake_rg(runtime_result: object, **kwargs: object) -> object:
        assert runtime_result is raw_runtime
        rg_kwargs.append(kwargs)
        return FakeComputationResult(passed=True)

    def fake_contacts(runtime_result: object, **kwargs: object) -> object:
        assert runtime_result is raw_runtime
        contacts_kwargs.append(kwargs)
        return FakeComputationResult(passed=True)

    monkeypatch.setattr(workflow, "_manifest_rg_computer", lambda: fake_rg)
    monkeypatch.setattr(
        workflow,
        "_manifest_contacts_computer",
        lambda: fake_contacts,
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(runtime_load_result=raw_runtime),
        frame_sampling=frame_sampling,
    )
    payload = result.to_dict()

    assert result.passed is True
    assert result.frame_sampling is frame_sampling
    assert rg_kwargs == [{"frame_sampling": frame_sampling}]
    assert contacts_kwargs == [{"frame_sampling": frame_sampling}]
    assert payload["frame_sampling"] == frame_sampling.to_dict()


def test_condition_names_are_preserved_from_runtime_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_computers(monkeypatch)
    runtime_loading = runtime_loading_result(
        condition_names=("tumor", "normal"),
        runtime_load_result=FakeRuntimeLoadResult(("tumor", "normal")),
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(runtime_loading)

    assert result.condition_names == ("tumor", "normal")


def test_result_to_dict_excludes_raw_runtime_rg_and_contacts_internals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_runtime = FakeRuntimeLoadResult(
        ("normal", "tumor"),
        internal={"sentinel_runtime": object()},
    )
    patch_computers(
        monkeypatch,
        rg_result=FakeComputationResult(
            passed=True,
            internal={"sentinel_rg": object()},
        ),
        contacts_result=FakeComputationResult(
            passed=True,
            internal={"sentinel_contacts": object()},
        ),
    )

    result = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading_result(runtime_load_result=raw_runtime)
    )
    payload_text = json.dumps(result.to_dict())

    assert "sentinel_runtime" not in payload_text
    assert "sentinel_rg" not in payload_text
    assert "sentinel_contacts" not in payload_text


def test_computation_function_does_not_create_files_or_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    patch_computers(monkeypatch)

    compute_preprocessing_graph_workflow_rg_contacts(runtime_loading_result())

    assert list(tmp_path.iterdir()) == []


def test_wrapper_does_not_load_manifest_or_runtimes() -> None:
    source = wrapper_source()

    for forbidden in (
        "load_preprocessing_input_manifest",
        "validate_preprocessing_manifest_paths",
        "check_preprocessing_graph_workflow_manifest_readiness",
        "load_preprocessing_graph_workflow_condition_runtimes",
        "load_manifest_condition_runtimes",
    ):
        assert forbidden not in source


def test_wrapper_does_not_write_csv_or_export_graph_artifacts() -> None:
    source = wrapper_source()

    for forbidden in (
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "validate_contacts_perframe_csv",
        "validate_contact_edges_csv",
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
    ):
        assert forbidden not in source


def test_wrapper_does_not_run_diagnostics_report_comparison_notebook_or_cli() -> None:
    source = wrapper_source()

    for forbidden in (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
        "nbconvert",
        "jupyter",
        "papermill",
        "mania.cli",
        "pipeline_steps",
    ):
        assert forbidden not in source


def test_dependency_free_imports() -> None:
    source = module_source()

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_docs_mention_stage_15_4_boundary_and_stage_15_5() -> None:
    text = docs_text()

    for phrase in (
        "Stage 15.4",
        "manifest-level Rg + contacts orchestration",
        "no CSV export",
        "no graph export",
        "no diagnostics",
        "no reference comparison",
        "no CLI",
        "Stage 15.3 runtime loading result feeds Stage 15.4",
        "Stage 15.4 does not load runtimes itself",
        "accepted Stage 12 Rg APIs",
        "accepted Stage 13 contacts APIs",
        "no new scientific algorithms",
        "Stage 15.5 will orchestrate graph export",
        "Stage 15.4 does not build graph artifacts",
    ):
        assert phrase in text


def test_docs_mention_ci_local_reference_and_future_boundaries() -> None:
    text = docs_text()

    for phrase in (
        "import/default CI does not require MDAnalysis",
        "local_md",
        "local-only",
        "not committed",
        "not required by default CI",
        "MANIA_analysis_v1_2",
        "notebook not executed",
        "reference comparison remains Stage 15.7 optional mode",
        "temporal RIN remains future scope",
        "WANIA frontend adapter/API payload remains future scope",
    ):
        assert phrase in text
