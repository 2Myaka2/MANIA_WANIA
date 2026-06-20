import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingGraphWorkflowComputationIssue,
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowGraphExportIssue,
    PreprocessingGraphWorkflowGraphExportResult,
    PreprocessingGraphWorkflowIssue,
    PreprocessingGraphWorkflowManifestReadinessIssue,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowPlan,
    PreprocessingGraphWorkflowRuntimeLoadingIssue,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    build_preprocessing_graph_workflow_plan,
    check_preprocessing_graph_workflow_manifest_readiness,
    compute_preprocessing_graph_workflow_rg_contacts,
    export_preprocessing_graph_workflow_artifacts,
    load_preprocessing_graph_workflow_condition_runtimes,
    validate_preprocessing_graph_csvs,
    write_preprocessing_graph_edges_csv,
    write_preprocessing_graph_json,
    write_preprocessing_graph_nodes_csv,
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

STAGE_14_CALL_ORDER = (
    "build_preprocessing_graph_export_mapping",
    "write_preprocessing_graph_nodes_csv",
    "write_preprocessing_graph_edges_csv",
    "validate_preprocessing_graph_csvs",
    "write_preprocessing_graph_json",
    "build_preprocessing_graph_export_bundle",
)


@dataclass(frozen=True)
class FakeRuntimeLoadResult:
    loaded_condition_names: tuple[str, ...]
    passed: bool = True


@dataclass(frozen=True)
class FakeContactsResult:
    passed: bool | None = None
    internal: object | None = None


@dataclass(frozen=True)
class FakeStage14Result:
    step: str
    passed: bool = True
    internal: object | None = None


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def wrapper_source() -> str:
    return inspect.getsource(
        workflow.export_preprocessing_graph_workflow_artifacts
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
    condition_names: tuple[str, ...] = ("normal", "tumor"),
) -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(condition_names),
        condition_names=condition_names,
        expected_condition_names=condition_names,
        runtime_load_result=FakeRuntimeLoadResult(condition_names),
    )


def computation_result(
    *,
    contacts_result: object | None = None,
    include_contacts: bool = True,
    issues: tuple[PreprocessingGraphWorkflowComputationIssue, ...] = (),
) -> PreprocessingGraphWorkflowComputationResult:
    if contacts_result is None and include_contacts:
        contacts_result = FakeContactsResult(internal={"raw": object()})
    return PreprocessingGraphWorkflowComputationResult(
        runtime_loading=runtime_loading_result(),
        condition_names=("normal", "tumor"),
        include_rg=False,
        include_contacts=include_contacts,
        contacts_result=contacts_result,
        issues=issues,
    )


def output_layout(root: Path) -> PreprocessingGraphWorkflowOutputLayout:
    return PreprocessingGraphWorkflowOutputLayout(
        output_dir=root,
        run_name="preprocessing_graph_export",
        rg_timeseries_csv_path=root / "rg" / "rg_timeseries.csv",
        contacts_perframe_csv_path=root / "contacts" / "contacts_perframe.csv",
        contact_edges_csv_path=root / "contacts" / "contact_edges.csv",
        graph_nodes_csv_path=root / "graph" / "nodes.csv",
        graph_edges_csv_path=root / "graph" / "edges.csv",
        graph_json_path=root / "graph" / "graph.json",
        diagnostics_report_json_path=(
            root / "reports" / "graph_diagnostics_report.json"
        ),
        reference_comparison_json_path=(
            root / "reports" / "graph_reference_comparison.json"
        ),
    )


def graph_export_result(
    root: Path,
    *,
    stage_result_passed: bool = True,
    issues: tuple[PreprocessingGraphWorkflowGraphExportIssue, ...] = (),
) -> PreprocessingGraphWorkflowGraphExportResult:
    raw = FakeStage14Result("raw", passed=stage_result_passed)
    layout = output_layout(root)
    return PreprocessingGraphWorkflowGraphExportResult(
        computation=computation_result(),
        output_layout=layout,
        graph_nodes_csv_path=layout.graph_nodes_csv_path,
        graph_edges_csv_path=layout.graph_edges_csv_path,
        graph_json_path=layout.graph_json_path,
        mapping_result=raw,
        nodes_csv_write_result=raw,
        edges_csv_write_result=raw,
        csv_validation_result=raw,
        graph_json_write_result=raw,
        graph_export_bundle_result=raw,
        issues=issues,
    )


def issue_kinds(
    result: PreprocessingGraphWorkflowGraphExportResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def patch_stage_14_apis(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failed_step: str | None = None,
    create_files: bool = False,
) -> tuple[list[str], dict[str, FakeStage14Result]]:
    calls: list[str] = []
    results = {
        step: FakeStage14Result(
            step,
            passed=step != failed_step,
            internal={"not_json": object()},
        )
        for step in STAGE_14_CALL_ORDER
    }

    def fake_mapping(contacts_result: object) -> object:
        calls.append("build_preprocessing_graph_export_mapping")
        assert contacts_result is not None
        return results["build_preprocessing_graph_export_mapping"]

    def fake_nodes(mapping_result: object, output_path: str | Path) -> object:
        calls.append("write_preprocessing_graph_nodes_csv")
        assert mapping_result is results["build_preprocessing_graph_export_mapping"]
        if create_files:
            Path(output_path).write_text("node_id\nn1\n", encoding="utf-8")
        return results["write_preprocessing_graph_nodes_csv"]

    def fake_edges(mapping_result: object, output_path: str | Path) -> object:
        calls.append("write_preprocessing_graph_edges_csv")
        assert mapping_result is results["build_preprocessing_graph_export_mapping"]
        if create_files:
            Path(output_path).write_text("edge_id\ne1\n", encoding="utf-8")
        return results["write_preprocessing_graph_edges_csv"]

    def fake_validation(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
    ) -> object:
        calls.append("validate_preprocessing_graph_csvs")
        assert Path(nodes_csv_path).name == "nodes.csv"
        assert Path(edges_csv_path).name == "edges.csv"
        return results["validate_preprocessing_graph_csvs"]

    def fake_json(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
        output_path: str | Path,
    ) -> object:
        calls.append("write_preprocessing_graph_json")
        assert Path(nodes_csv_path).name == "nodes.csv"
        assert Path(edges_csv_path).name == "edges.csv"
        if create_files:
            Path(output_path).write_text('{"nodes":[],"edges":[]}\n', encoding="utf-8")
        return results["write_preprocessing_graph_json"]

    def fake_bundle(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
        graph_json_path: str | Path,
    ) -> object:
        calls.append("build_preprocessing_graph_export_bundle")
        assert Path(nodes_csv_path).name == "nodes.csv"
        assert Path(edges_csv_path).name == "edges.csv"
        assert Path(graph_json_path).name == "graph.json"
        return results["build_preprocessing_graph_export_bundle"]

    monkeypatch.setattr(workflow, "_graph_export_mapping_builder", lambda: fake_mapping)
    monkeypatch.setattr(workflow, "_graph_nodes_csv_writer", lambda: fake_nodes)
    monkeypatch.setattr(workflow, "_graph_edges_csv_writer", lambda: fake_edges)
    monkeypatch.setattr(workflow, "_graph_csv_validator", lambda: fake_validation)
    monkeypatch.setattr(workflow, "_graph_json_writer", lambda: fake_json)
    monkeypatch.setattr(
        workflow,
        "_graph_export_bundle_builder",
        lambda: fake_bundle,
    )
    return calls, results


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowGraphExportIssue is not None
    assert PreprocessingGraphWorkflowGraphExportResult is not None
    assert callable(export_preprocessing_graph_workflow_artifacts)


def test_existing_stage_15_1_to_15_4_exports_still_work() -> None:
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
        PreprocessingGraphWorkflowComputationIssue,
        PreprocessingGraphWorkflowComputationResult,
        compute_preprocessing_graph_workflow_rg_contacts,
    ):
        assert api is not None


def test_existing_stage_14_graph_exports_still_work() -> None:
    for api in (
        build_preprocessing_graph_export_mapping,
        write_preprocessing_graph_nodes_csv,
        write_preprocessing_graph_edges_csv,
        validate_preprocessing_graph_csvs,
        write_preprocessing_graph_json,
        build_preprocessing_graph_export_bundle,
    ):
        assert api is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_graph_export_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowGraphExportIssue(
        kind="graph_mapping_failed",
        message="Mapping failed.",
        stage="graph_mapping",
        field="mapping_result",
        path=Path("outputs/graph/nodes.csv"),
        value="Fake",
    )

    assert issue.to_dict()["path"] == "outputs/graph/nodes.csv"
    assert_json_safe(issue.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("kind", ""),
        ("kind", " "),
        ("message", ""),
        ("message", " "),
        ("stage", ""),
        ("field", ""),
        ("value", ""),
        ("path", "outputs/graph/nodes.csv"),
    ),
)
def test_graph_export_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": "graph_mapping_failed",
        "message": "Mapping failed.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowGraphExportIssue(**kwargs)


def test_graph_export_result_validates_and_serializes(tmp_path: Path) -> None:
    result = graph_export_result(tmp_path / "out")
    payload = result.to_dict()

    assert result.passed
    assert result.issue_count == 0
    assert result.mapping_built
    assert result.nodes_csv_written
    assert result.edges_csv_written
    assert result.csv_validated
    assert result.graph_json_written
    assert result.bundle_built
    assert payload["graph_nodes_csv_path"].endswith("graph/nodes.csv")
    assert payload["graph_edges_csv_path"].endswith("graph/edges.csv")
    assert payload["graph_json_path"].endswith("graph/graph.json")
    assert "mapping_result_type" in payload
    assert_json_safe(payload)


def test_graph_export_result_failed_when_raw_stage_result_failed(
    tmp_path: Path,
) -> None:
    result = graph_export_result(tmp_path / "out", stage_result_passed=False)

    assert not result.passed
    assert not result.mapping_built
    assert result.issue_count == 0


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("computation", object()),
        ("output_layout", object()),
        ("graph_nodes_csv_path", "nodes.csv"),
        ("graph_edges_csv_path", "edges.csv"),
        ("graph_json_path", "graph.json"),
        ("issues", [PreprocessingGraphWorkflowGraphExportIssue("k", "m")]),
        ("issues", (object(),)),
    ),
)
def test_graph_export_result_rejects_invalid_values(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    layout = output_layout(tmp_path / "out")
    kwargs: dict[str, object] = {
        "computation": computation_result(),
        "output_layout": layout,
        "graph_nodes_csv_path": layout.graph_nodes_csv_path,
        "graph_edges_csv_path": layout.graph_edges_csv_path,
        "graph_json_path": layout.graph_json_path,
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowGraphExportResult(**kwargs)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"computation": object()}, "computation"),
        ({"output_layout": object()}, "output_layout"),
        ({"create_parent_directories": "yes"}, "create_parent_directories"),
    ),
)
def test_graph_export_function_rejects_invalid_arguments(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    call_kwargs: dict[str, object] = {
        "computation": computation_result(),
        "output_layout": output_layout(tmp_path / "out"),
        "create_parent_directories": True,
    }
    call_kwargs.update(kwargs)

    with pytest.raises(ValueError, match=message):
        export_preprocessing_graph_workflow_artifacts(**call_kwargs)


def test_failed_computation_prevents_graph_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch)
    issue = PreprocessingGraphWorkflowComputationIssue(
        kind="contacts_computation_failed",
        message="Contacts failed.",
        stage="contacts",
    )
    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(issues=(issue,)),
        output_layout(tmp_path / "out"),
    )

    assert not result.passed
    assert issue_kinds(result) == {"computation_failed"}
    assert calls == []
    assert not (tmp_path / "out" / "graph").exists()


def test_missing_contacts_result_prevents_graph_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch)
    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(contacts_result=None, include_contacts=False),
        output_layout(tmp_path / "out"),
    )

    assert not result.passed
    assert issue_kinds(result) == {"contacts_result_missing"}
    assert calls == []
    assert not (tmp_path / "out" / "graph").exists()


def test_invalid_contacts_result_prevents_graph_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch)
    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(contacts_result=FakeContactsResult(passed=False)),
        output_layout(tmp_path / "out"),
    )

    assert not result.passed
    assert issue_kinds(result) == {"contacts_result_invalid"}
    assert calls == []


def test_invalid_output_layout_prevents_graph_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch)
    root = tmp_path / "out"
    layout = PreprocessingGraphWorkflowOutputLayout(
        output_dir=root,
        run_name="preprocessing_graph_export",
        rg_timeseries_csv_path=root / "rg" / "rg_timeseries.csv",
        contacts_perframe_csv_path=root / "contacts" / "contacts_perframe.csv",
        contact_edges_csv_path=root / "contacts" / "contact_edges.csv",
        graph_nodes_csv_path=root / "elsewhere" / "nodes.csv",
        graph_edges_csv_path=root / "graph" / "edges.csv",
        graph_json_path=root / "graph" / "graph.json",
        diagnostics_report_json_path=(
            root / "reports" / "graph_diagnostics_report.json"
        ),
        reference_comparison_json_path=(
            root / "reports" / "graph_reference_comparison.json"
        ),
    )

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        layout,
    )

    assert not result.passed
    assert issue_kinds(result) == {"output_layout_invalid"}
    assert calls == []
    assert not (root / "graph").exists()


def test_graph_output_directory_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch)
    output_dir = tmp_path / "out"
    output_dir.write_text("not a directory", encoding="utf-8")

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        output_layout(output_dir),
    )

    assert not result.passed
    assert issue_kinds(result) == {"graph_output_directory_failed"}
    assert calls == []


def test_successful_graph_export_calls_stage_14_apis_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, results = patch_stage_14_apis(monkeypatch, create_files=True)
    layout = output_layout(tmp_path / "out")
    raw_contacts = FakeContactsResult(internal={"secret": object()})

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(contacts_result=raw_contacts),
        layout,
    )

    assert result.passed
    assert calls == list(STAGE_14_CALL_ORDER)
    assert result.mapping_result is results["build_preprocessing_graph_export_mapping"]
    assert (
        result.nodes_csv_write_result
        is results["write_preprocessing_graph_nodes_csv"]
    )
    assert (
        result.edges_csv_write_result
        is results["write_preprocessing_graph_edges_csv"]
    )
    assert result.csv_validation_result is results["validate_preprocessing_graph_csvs"]
    assert result.graph_json_write_result is results["write_preprocessing_graph_json"]
    assert (
        result.graph_export_bundle_result
        is results["build_preprocessing_graph_export_bundle"]
    )
    assert result.graph_nodes_csv_path == layout.graph_nodes_csv_path
    assert result.graph_edges_csv_path == layout.graph_edges_csv_path
    assert result.graph_json_path == layout.graph_json_path
    assert_json_safe(result.to_dict())


def test_graph_parent_directory_is_created_only_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch, create_files=False)
    enabled_layout = output_layout(tmp_path / "enabled")

    enabled_result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        enabled_layout,
        create_parent_directories=True,
    )

    assert enabled_result.passed
    assert calls == list(STAGE_14_CALL_ORDER)
    assert enabled_layout.graph_nodes_csv_path.parent.exists()

    calls.clear()
    disabled_layout = output_layout(tmp_path / "disabled")
    disabled_result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        disabled_layout,
        create_parent_directories=False,
    )

    assert disabled_result.passed
    assert calls == list(STAGE_14_CALL_ORDER)
    assert not disabled_layout.graph_nodes_csv_path.parent.exists()


def test_only_graph_directory_and_graph_files_are_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_stage_14_apis(monkeypatch, create_files=True)
    layout = output_layout(tmp_path / "out")

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        layout,
    )

    assert result.passed
    assert layout.graph_nodes_csv_path.is_file()
    assert layout.graph_edges_csv_path.is_file()
    assert layout.graph_json_path.is_file()
    assert not (layout.output_dir / "rg").exists()
    assert not (layout.output_dir / "contacts").exists()
    assert not (layout.output_dir / "reports").exists()


@pytest.mark.parametrize(
    ("failed_step", "expected_issue", "expected_calls"),
    (
        (
            "build_preprocessing_graph_export_mapping",
            "graph_mapping_failed",
            ("build_preprocessing_graph_export_mapping",),
        ),
        (
            "write_preprocessing_graph_nodes_csv",
            "graph_nodes_csv_write_failed",
            (
                "build_preprocessing_graph_export_mapping",
                "write_preprocessing_graph_nodes_csv",
            ),
        ),
        (
            "write_preprocessing_graph_edges_csv",
            "graph_edges_csv_write_failed",
            (
                "build_preprocessing_graph_export_mapping",
                "write_preprocessing_graph_nodes_csv",
                "write_preprocessing_graph_edges_csv",
            ),
        ),
        (
            "validate_preprocessing_graph_csvs",
            "graph_csv_validation_failed",
            (
                "build_preprocessing_graph_export_mapping",
                "write_preprocessing_graph_nodes_csv",
                "write_preprocessing_graph_edges_csv",
                "validate_preprocessing_graph_csvs",
            ),
        ),
        (
            "write_preprocessing_graph_json",
            "graph_json_write_failed",
            (
                "build_preprocessing_graph_export_mapping",
                "write_preprocessing_graph_nodes_csv",
                "write_preprocessing_graph_edges_csv",
                "validate_preprocessing_graph_csvs",
                "write_preprocessing_graph_json",
            ),
        ),
        (
            "build_preprocessing_graph_export_bundle",
            "graph_bundle_failed",
            STAGE_14_CALL_ORDER,
        ),
    ),
)
def test_stage_14_failures_stop_downstream_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_step: str,
    expected_issue: str,
    expected_calls: tuple[str, ...],
) -> None:
    calls, _ = patch_stage_14_apis(monkeypatch, failed_step=failed_step)

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(),
        output_layout(tmp_path / "out"),
    )

    assert not result.passed
    assert issue_kinds(result) == {expected_issue}
    assert calls == list(expected_calls)


def test_backend_graph_edges_csv_is_used_not_contacts_edge_export() -> None:
    source = wrapper_source()

    assert "_graph_edges_csv_writer" in source
    assert "write_contact_edges_csv" not in source
    assert "trajectory_contacts_export" not in source


def test_result_to_dict_excludes_raw_internals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, results = patch_stage_14_apis(monkeypatch)
    sentinel = "RAW_SENTINEL_SHOULD_NOT_APPEAR"
    raw_contacts = FakeContactsResult(internal={"secret": sentinel})
    for step in STAGE_14_CALL_ORDER:
        results[step] = FakeStage14Result(
            step,
            passed=True,
            internal={"secret": sentinel},
        )

    result = export_preprocessing_graph_workflow_artifacts(
        computation_result(contacts_result=raw_contacts),
        output_layout(tmp_path / "out"),
    )
    encoded = json.dumps(result.to_dict())

    assert result.passed
    assert calls == list(STAGE_14_CALL_ORDER)
    assert sentinel not in encoded


def test_graph_export_function_does_not_load_manifests_or_runtimes() -> None:
    source = wrapper_source()
    forbidden = (
        "load_preprocessing_input_manifest",
        "validate_preprocessing_manifest_paths",
        "check_preprocessing_graph_workflow_manifest_readiness",
        "load_preprocessing_graph_workflow_condition_runtimes",
        "load_manifest_condition_runtimes",
    )

    for name in forbidden:
        assert name not in source


def test_graph_export_function_does_not_compute_rg_or_contacts() -> None:
    source = wrapper_source()
    forbidden = (
        "compute_manifest_rg",
        "compute_condition_rg",
        "compute_manifest_contacts",
        "compute_condition_contacts",
        "compute_preprocessing_graph_workflow_rg_contacts",
    )

    for name in forbidden:
        assert name not in source


def test_graph_export_function_does_not_write_rg_or_contacts_csv() -> None:
    source = wrapper_source()
    forbidden = (
        "write_rg_timeseries_csv",
        "validate_rg_timeseries_csv",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "validate_contacts_perframe_csv",
        "validate_contact_edges_csv",
    )

    for name in forbidden:
        assert name not in source


def test_graph_export_function_does_not_run_diagnostics_or_comparison() -> None:
    source = wrapper_source()
    forbidden = (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
    )

    for name in forbidden:
        assert name not in source


def test_graph_export_function_does_not_execute_notebooks() -> None:
    source = wrapper_source()
    forbidden = ("nbconvert", "jupyter", "papermill", "notebook")

    for name in forbidden:
        assert name not in source


def test_graph_export_function_does_not_call_cli_or_broad_workflow() -> None:
    source = wrapper_source()
    forbidden = ("mania.cli", "pipeline_steps", "pipeline modules")

    for name in forbidden:
        assert name not in source


def test_workflow_module_has_dependency_free_imports() -> None:
    source = module_source()
    forbidden = ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow")

    for name in forbidden:
        assert name not in source


def test_docs_mention_stage_15_5_boundary() -> None:
    text = docs_text()
    required = (
        "Stage 15.5",
        "graph export orchestration",
        "mapping",
        "nodes.csv",
        "corrected edges.csv",
        "CSV validation",
        "graph.json",
        "bundle",
        "no diagnostics",
        "no reference comparison",
        "no CLI",
    )

    for phrase in required:
        assert phrase in text


def test_docs_mention_stage_15_4_and_stage_14_boundaries() -> None:
    text = docs_text()
    required = (
        "Stage 15.4 computation result feeds Stage 15.5",
        "Stage 15.5 does not compute Rg/contacts",
        "accepted Stage 14 graph export APIs",
        "no new graph semantics",
        "edge_type",
        "all_edge_types",
        "n_edge_types",
    )

    for phrase in required:
        assert phrase in text


def test_docs_mention_contacts_and_future_stage_boundaries() -> None:
    text = docs_text()
    required = (
        "contact_edges.csv",
        "aggregate contacts table",
        "backend graph edges.csv",
        "Stage 15.5 writes backend graph edges.csv",
        "Stage 15.6 will orchestrate diagnostics + diagnostics report",
        "Stage 15.5 does not run diagnostics",
        "Stage 15.7",
        "local_md",
        "default CI",
        "MDAnalysis",
        "notebook",
        "Temporal RIN",
        "WANIA frontend",
    )

    for phrase in required:
        assert phrase in text
