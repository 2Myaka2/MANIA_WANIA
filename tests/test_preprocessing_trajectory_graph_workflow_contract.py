import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRgResult,
    PreprocessingContactComputationLimits,
    PreprocessingContactDefinition,
    PreprocessingContactDetectionOptions,
    PreprocessingGraphDiagnosticsReport,
    PreprocessingGraphExportBundleResult,
    PreprocessingGraphReferenceComparisonInput,
    PreprocessingGraphWorkflowIssue,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowPlan,
    PreprocessingManifestLoadResult,
    build_preprocessing_graph_diagnostics_report,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    build_preprocessing_graph_workflow_plan,
    compare_preprocessing_graph_reference_artifacts,
    compute_condition_contacts,
    compute_condition_rg,
    compute_manifest_contacts,
    compute_manifest_rg,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
    run_preprocessing_graph_diagnostics,
    validate_preprocessing_graph_reference_comparison_input,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_graph_workflow.py"
)
DOC_PATH = REPO_ROOT / "docs" / "preprocessing_graph_workflow_contract.md"


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def options(**overrides: object) -> PreprocessingGraphWorkflowOptions:
    kwargs: dict[str, object] = {
        "manifest_path": Path("local_md/manifests/napi2b_10ns.yaml"),
        "output_dir": Path("outputs/napi2b_10ns"),
    }
    kwargs.update(overrides)
    return PreprocessingGraphWorkflowOptions(**kwargs)


def output_layout(**overrides: object) -> PreprocessingGraphWorkflowOutputLayout:
    root = Path("outputs/napi2b_10ns")
    kwargs: dict[str, object] = {
        "output_dir": root,
        "run_name": "preprocessing_graph_export",
        "rg_timeseries_csv_path": root / "rg" / "rg_timeseries.csv",
        "contacts_perframe_csv_path": (
            root / "contacts" / "contacts_perframe.csv"
        ),
        "contact_edges_csv_path": root / "contacts" / "contact_edges.csv",
        "graph_nodes_csv_path": root / "graph" / "nodes.csv",
        "graph_edges_csv_path": root / "graph" / "edges.csv",
        "graph_json_path": root / "graph" / "graph.json",
        "diagnostics_report_json_path": (
            root / "reports" / "graph_diagnostics_report.json"
        ),
        "reference_comparison_json_path": (
            root / "reports" / "graph_reference_comparison.json"
        ),
    }
    kwargs.update(overrides)
    return PreprocessingGraphWorkflowOutputLayout(**kwargs)


def issue(**overrides: object) -> PreprocessingGraphWorkflowIssue:
    kwargs: dict[str, object] = {
        "kind": "stage_disabled",
        "message": "A stage was disabled.",
    }
    kwargs.update(overrides)
    return PreprocessingGraphWorkflowIssue(**kwargs)


def plan(**overrides: object) -> PreprocessingGraphWorkflowPlan:
    kwargs: dict[str, object] = {
        "options": options(),
        "output_layout": output_layout(),
        "planned_steps": ("load_manifest",),
        "issues": (),
    }
    kwargs.update(overrides)
    return PreprocessingGraphWorkflowPlan(**kwargs)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowOptions is not None
    assert PreprocessingGraphWorkflowOutputLayout is not None
    assert PreprocessingGraphWorkflowIssue is not None
    assert PreprocessingGraphWorkflowPlan is not None
    assert build_preprocessing_graph_workflow_plan is not None


def test_existing_stage_11_to_14_exports_still_work() -> None:
    exported = (
        PreprocessingConditionLoadResult,
        PreprocessingManifestLoadResult,
        load_single_condition_runtime,
        load_manifest_condition_runtimes,
        PreprocessingConditionRgResult,
        compute_condition_rg,
        compute_manifest_rg,
        PreprocessingContactComputationLimits,
        PreprocessingContactDefinition,
        compute_condition_contacts,
        compute_manifest_contacts,
        PreprocessingGraphExportBundleResult,
        build_preprocessing_graph_export_mapping,
        build_preprocessing_graph_export_bundle,
        PreprocessingGraphDiagnosticsReport,
        run_preprocessing_graph_diagnostics,
        build_preprocessing_graph_diagnostics_report,
        PreprocessingGraphReferenceComparisonInput,
        validate_preprocessing_graph_reference_comparison_input,
        compare_preprocessing_graph_reference_artifacts,
    )

    for api in exported:
        assert api is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_options_validate_and_serialize() -> None:
    workflow_options = options()

    assert isinstance(workflow_options.manifest_path, Path)
    assert isinstance(workflow_options.output_dir, Path)
    assert workflow_options.reference_semantics == "MANIA_analysis_v1_2"
    assert workflow_options.enable_reference_comparison is False
    assert workflow_options.contact_computation_limits == (
        PreprocessingContactComputationLimits()
    )
    assert workflow_options.contact_detection_options == (
        PreprocessingContactDetectionOptions()
    )
    payload = workflow_options.to_dict()
    assert payload["manifest_path"] == "local_md/manifests/napi2b_10ns.yaml"
    assert payload["output_dir"] == "outputs/napi2b_10ns"
    assert payload["contact_detection_options"] == (
        PreprocessingContactDetectionOptions().to_dict(
            include_contact_selection=True
        )
    )
    assert payload["contact_computation_limits"] == (
        PreprocessingContactComputationLimits().to_dict()
    )
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("manifest_path", "manifest.yaml"),
        ("output_dir", "outputs"),
        ("run_name", ""),
        ("run_name", " "),
        ("overwrite", 1),
        ("include_rg", 1),
        ("include_contacts", 0),
        ("include_graph_export", "yes"),
        ("include_diagnostics", None),
        ("enable_reference_comparison", "false"),
        ("reference_nodes_csv_path", "nodes.csv"),
        ("reference_edges_csv_path", "edges.csv"),
        ("reference_graph_json_path", "graph.json"),
        ("reference_semantics", ""),
        ("reference_semantics", " "),
        ("contact_detection_options", object()),
        ("contact_computation_limits", object()),
    ),
)
def test_options_reject_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        options(**{field_name: value})


def test_output_layout_validates_and_serializes() -> None:
    layout = output_layout()

    assert layout.output_dir == Path("outputs/napi2b_10ns")
    assert layout.graph_nodes_csv_path == Path(
        "outputs/napi2b_10ns/graph/nodes.csv"
    )
    assert_json_safe(layout.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("output_dir", "outputs"),
        ("run_name", ""),
        ("rg_timeseries_csv_path", "rg_timeseries.csv"),
        ("contacts_perframe_csv_path", "contacts_perframe.csv"),
        ("contact_edges_csv_path", "contact_edges.csv"),
        ("graph_nodes_csv_path", "nodes.csv"),
        ("graph_edges_csv_path", "edges.csv"),
        ("graph_json_path", "graph.json"),
        ("diagnostics_report_json_path", "report.json"),
        ("reference_comparison_json_path", "comparison.json"),
    ),
)
def test_output_layout_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        output_layout(**{field_name: value})


def test_issue_validates_and_serializes() -> None:
    workflow_issue = issue(field="include_graph_export", value="False")

    assert workflow_issue.kind == "stage_disabled"
    assert workflow_issue.message == "A stage was disabled."
    assert workflow_issue.field == "include_graph_export"
    assert workflow_issue.value == "False"
    assert_json_safe(workflow_issue.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("kind", ""),
        ("kind", " "),
        ("message", ""),
        ("message", " "),
        ("field", ""),
        ("field", " "),
        ("value", ""),
        ("value", " "),
        ("value", 1),
    ),
)
def test_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        issue(**{field_name: value})


def test_plan_validates_and_serializes() -> None:
    workflow_plan = plan()

    assert workflow_plan.passed is True
    assert workflow_plan.issue_count == 0
    assert workflow_plan.planned_step_count == 1
    assert_json_safe(workflow_plan.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("options", object()),
        ("output_layout", object()),
        ("planned_steps", ["load_manifest"]),
        ("planned_steps", (1,)),
        ("planned_steps", ("",)),
        ("issues", [issue()]),
        ("issues", (object(),)),
    ),
)
def test_plan_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        plan(**{field_name: value})


def test_plan_builder_creates_deterministic_output_layout() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(options())
    layout = workflow_plan.output_layout

    assert layout.rg_timeseries_csv_path == Path(
        "outputs/napi2b_10ns/rg/rg_timeseries.csv"
    )
    assert layout.contacts_perframe_csv_path == Path(
        "outputs/napi2b_10ns/contacts/contacts_perframe.csv"
    )
    assert layout.contact_edges_csv_path == Path(
        "outputs/napi2b_10ns/contacts/contact_edges.csv"
    )
    assert layout.graph_nodes_csv_path == Path(
        "outputs/napi2b_10ns/graph/nodes.csv"
    )
    assert layout.graph_edges_csv_path == Path(
        "outputs/napi2b_10ns/graph/edges.csv"
    )
    assert layout.graph_json_path == Path(
        "outputs/napi2b_10ns/graph/graph.json"
    )
    assert layout.diagnostics_report_json_path == Path(
        "outputs/napi2b_10ns/reports/graph_diagnostics_report.json"
    )
    assert layout.reference_comparison_json_path == Path(
        "outputs/napi2b_10ns/reports/graph_reference_comparison.json"
    )


def test_plan_builder_does_not_create_directories_or_files(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "planned-output"

    build_preprocessing_graph_workflow_plan(
        options(output_dir=output_dir)
    )

    assert not output_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_default_planned_steps_include_core_workflow_steps() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(options())

    for step in (
        "load_manifest",
        "validate_manifest_paths",
        "load_condition_runtimes",
        "compute_rg",
        "compute_contacts",
        "build_graph_mapping",
        "write_graph_nodes_csv",
        "write_graph_edges_csv",
        "validate_graph_csvs",
        "write_graph_json",
        "build_graph_export_bundle",
        "run_graph_diagnostics",
        "build_graph_diagnostics_report",
    ):
        assert step in workflow_plan.planned_steps


def test_reference_comparison_disabled_by_default() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(options())

    assert "validate_reference_comparison_input" not in workflow_plan.planned_steps
    assert "compare_reference_graph_artifacts" not in workflow_plan.planned_steps


def test_reference_comparison_enabled_requires_explicit_reference_paths() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(enable_reference_comparison=True)
    )

    assert workflow_plan.passed is False
    assert "reference_paths_required" in {
        workflow_issue.kind for workflow_issue in workflow_plan.issues
    }


def test_reference_comparison_enabled_with_paths_plans_comparison_steps() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(
            enable_reference_comparison=True,
            reference_nodes_csv_path=Path("reference/nodes.csv"),
            reference_edges_csv_path=Path("reference/edges.csv"),
            reference_graph_json_path=Path("reference/graph.json"),
        )
    )

    assert workflow_plan.passed is True
    assert "validate_reference_comparison_input" in workflow_plan.planned_steps
    assert "compare_reference_graph_artifacts" in workflow_plan.planned_steps


def test_disabling_rg_removes_rg_step_only() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(include_rg=False)
    )

    assert "compute_rg" not in workflow_plan.planned_steps
    assert "compute_contacts" in workflow_plan.planned_steps
    assert "build_graph_mapping" in workflow_plan.planned_steps


def test_disabling_contacts_while_graph_export_enabled_fails() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(include_contacts=False, include_graph_export=True)
    )

    assert workflow_plan.passed is False
    assert _has_issue_message(
        workflow_plan,
        kind="stage_disabled",
        message_part="graph export depends on contacts",
    )


def test_disabling_graph_export_removes_graph_steps() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(
            include_graph_export=False,
            include_diagnostics=False,
            enable_reference_comparison=False,
        )
    )

    assert workflow_plan.passed is True
    assert "build_graph_mapping" not in workflow_plan.planned_steps
    assert "write_graph_json" not in workflow_plan.planned_steps


def test_diagnostics_require_graph_export() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(include_graph_export=False, include_diagnostics=True)
    )

    assert workflow_plan.passed is False
    assert _has_issue_message(
        workflow_plan,
        kind="stage_disabled",
        message_part="diagnostics depend on graph export",
    )


def test_reference_comparison_requires_graph_export() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(
            include_graph_export=False,
            enable_reference_comparison=True,
            reference_nodes_csv_path=Path("reference/nodes.csv"),
            reference_edges_csv_path=Path("reference/edges.csv"),
            reference_graph_json_path=Path("reference/graph.json"),
        )
    )

    assert workflow_plan.passed is False
    assert _has_issue_message(
        workflow_plan,
        kind="stage_disabled",
        message_part="reference comparison depends on graph export",
    )


def test_disabling_diagnostics_removes_diagnostics_steps() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(include_diagnostics=False)
    )

    assert "run_graph_diagnostics" not in workflow_plan.planned_steps
    assert "build_graph_diagnostics_report" not in workflow_plan.planned_steps


def test_all_workflow_targets_disabled_fails() -> None:
    workflow_plan = build_preprocessing_graph_workflow_plan(
        options(
            include_rg=False,
            include_contacts=False,
            include_graph_export=False,
            include_diagnostics=False,
            enable_reference_comparison=False,
        )
    )

    assert workflow_plan.passed is False
    assert "no_workflow_targets_enabled" in {
        workflow_issue.kind for workflow_issue in workflow_plan.issues
    }


def test_plan_output_is_deterministic() -> None:
    first_plan = build_preprocessing_graph_workflow_plan(options())
    second_plan = build_preprocessing_graph_workflow_plan(options())

    assert first_plan.to_dict() == second_plan.to_dict()


def test_reference_comparison_does_not_auto_search_artifacts() -> None:
    source = module_source()

    for forbidden in (
        "data/reference",
        "notebooks_libraries",
        ".ipynb",
        "glob(",
        "rglob(",
    ):
        assert forbidden not in source


def test_notebook_is_not_executed() -> None:
    source = module_source()

    for forbidden in ("nbconvert", "jupyter", "papermill", "execute_notebook"):
        assert forbidden not in source


def test_plan_builder_does_not_load_manifest() -> None:
    source = module_source()

    for forbidden in (
        "load_preprocessing_input_manifest",
        "safe_load",
        "yaml",
        "validate_preprocessing_manifest_paths",
    ):
        assert forbidden not in source


def test_plan_builder_does_not_load_runtimes() -> None:
    source = module_source()

    for forbidden in (
        "load_manifest_condition_runtimes",
        "load_single_condition_runtime",
        "trajectory_loader",
        "trajectory_runtime",
    ):
        assert forbidden not in source


def test_plan_builder_does_not_compute_rg_or_contacts() -> None:
    source = module_source()

    for forbidden in (
        "compute_condition_rg",
        "compute_manifest_rg",
        "compute_condition_contacts",
        "compute_manifest_contacts",
    ):
        assert forbidden not in source


def test_plan_builder_does_not_export_graph_artifacts() -> None:
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


def test_plan_builder_does_not_run_diagnostics_or_comparison() -> None:
    source = module_source()

    for forbidden in (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
    ):
        assert forbidden not in source


def test_no_cli_workflow_integration_yet() -> None:
    source = module_source()

    for forbidden in (
        "mania.cli",
        "mania.pipeline",
        "pipeline_steps",
        "workflow_runner",
    ):
        assert forbidden not in source


def test_no_temporal_rin() -> None:
    source = module_source()

    for forbidden in ("temporal_rin", "temporal RIN", "temporal-rin"):
        assert forbidden not in source


def test_dependency_free_source() -> None:
    source = module_source()

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_docs_mention_stage_15_1_boundary() -> None:
    text = doc_text()

    for phrase in (
        "Stage 15.1",
        "workflow contract",
        "run options",
        "output layout",
        "no execution",
    ):
        assert phrase in text


def test_docs_mention_local_md_local_only() -> None:
    text = doc_text()

    for phrase in ("local_md", "local-only", "not required by default CI"):
        assert phrase in text


def test_docs_mention_no_cli_until_15_8() -> None:
    text = doc_text()

    for phrase in (
        "Stage 15.8",
        "CLI boundary later",
        "no CLI in Stage 15.1",
    ):
        assert phrase in text


def test_docs_mention_reference_comparison_disabled_by_default() -> None:
    text = doc_text()

    for phrase in (
        "reference comparison disabled by default",
        "explicit reference artifact paths",
        "notebook is not executed",
    ):
        assert phrase in text


def test_docs_mention_future_temporal_rin_and_wania_frontend_scope() -> None:
    text = doc_text()

    assert "temporal RIN remains future scope" in text
    assert "WANIA frontend adapter/API payload remains future scope" in text


def _has_issue_message(
    workflow_plan: PreprocessingGraphWorkflowPlan,
    *,
    kind: str,
    message_part: str,
) -> bool:
    return any(
        workflow_issue.kind == kind
        and message_part in workflow_issue.message
        for workflow_issue in workflow_plan.issues
    )
