import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowGraphExportIssue,
    PreprocessingGraphWorkflowGraphExportResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowReferenceComparisonIssue,
    PreprocessingGraphWorkflowReferenceComparisonResult,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    compare_preprocessing_graph_workflow_reference_artifacts,
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


@dataclass(frozen=True)
class FakeStageResult:
    name: str
    passed: bool = True
    internal: object | None = None


@dataclass(frozen=True)
class FakeInputValidation:
    passed: bool = True
    issue_count: int = 0
    generated_node_count: int = 2
    generated_edge_count: int = 1
    reference_node_count: int = 2
    reference_edge_count: int = 1


@dataclass(frozen=True)
class FakeReferenceComparisonResult:
    passed: bool = True
    internal: object | None = None
    reference_semantics: str = "MANIA_analysis_v1_2"
    generated_condition: str = "normal"
    reference_condition: str = "normal"
    generated_schema_version: str = "0.1"
    reference_schema_version: str = "0.1"
    target_count: int = 3
    failed_target_count: int = 0
    mismatch_count: int = 0
    input_validation: FakeInputValidation = field(
        default_factory=FakeInputValidation
    )


def assert_json_safe(payload: object) -> None:
    json.dumps(payload, allow_nan=False)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def wrapper_source() -> str:
    return inspect.getsource(
        workflow.compare_preprocessing_graph_workflow_reference_artifacts
    )


def docs_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WORKFLOW_DOC_PATH, PARSING_DOC_PATH, ADR_PATH)
    )


def readiness_result() -> PreprocessingGraphWorkflowManifestReadinessResult:
    return PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=("normal", "tumor"),
        expected_condition_count=2,
    )


def runtime_loading_result() -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal", "tumor"),
        expected_condition_names=("normal", "tumor"),
        runtime_load_result=FakeRuntimeLoadResult(("normal", "tumor")),
    )


def computation_result() -> PreprocessingGraphWorkflowComputationResult:
    return PreprocessingGraphWorkflowComputationResult(
        runtime_loading=runtime_loading_result(),
        condition_names=("normal", "tumor"),
        include_rg=False,
        include_contacts=True,
        contacts_result=FakeStageResult("contacts"),
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


def workflow_options(
    *,
    output_dir: Path,
    enable_reference_comparison: bool = False,
    reference_nodes_csv_path: Path | None = None,
    reference_edges_csv_path: Path | None = None,
    reference_graph_json_path: Path | None = None,
) -> PreprocessingGraphWorkflowOptions:
    return PreprocessingGraphWorkflowOptions(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        output_dir=output_dir,
        enable_reference_comparison=enable_reference_comparison,
        reference_nodes_csv_path=reference_nodes_csv_path,
        reference_edges_csv_path=reference_edges_csv_path,
        reference_graph_json_path=reference_graph_json_path,
    )


def graph_export_result(
    root: Path,
    *,
    issues: tuple[PreprocessingGraphWorkflowGraphExportIssue, ...] = (),
) -> PreprocessingGraphWorkflowGraphExportResult:
    raw = FakeStageResult("stage14", internal={"secret": object()})
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
    result: PreprocessingGraphWorkflowReferenceComparisonResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def enabled_options(root: Path) -> PreprocessingGraphWorkflowOptions:
    return workflow_options(
        output_dir=root,
        enable_reference_comparison=True,
        reference_nodes_csv_path=Path("reference/nodes.csv"),
        reference_edges_csv_path=Path("reference/edges.csv"),
        reference_graph_json_path=Path("reference/graph.json"),
    )


def test_public_exports_work() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingGraphWorkflowReferenceComparisonIssue is not None
    assert PreprocessingGraphWorkflowReferenceComparisonResult is not None
    assert callable(compare_preprocessing_graph_workflow_reference_artifacts)


def test_reference_comparison_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowReferenceComparisonIssue(
        kind="reference_paths_required",
        message="Reference paths are required.",
        stage="reference_comparison_input",
        field="reference_nodes_csv_path",
        path=Path("reference/nodes.csv"),
        value="missing",
    )

    assert issue.to_dict()["path"] == "reference/nodes.csv"
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
        ("path", "reference/nodes.csv"),
    ),
)
def test_reference_comparison_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": "reference_paths_required",
        "message": "Reference paths are required.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowReferenceComparisonIssue(**kwargs)


def test_reference_comparison_result_validates_and_serializes(
    tmp_path: Path,
) -> None:
    layout = output_layout(tmp_path / "out")
    result = PreprocessingGraphWorkflowReferenceComparisonResult(
        graph_export=graph_export_result(tmp_path / "out"),
        options=workflow_options(output_dir=layout.output_dir),
        output_layout=layout,
        reference_comparison_enabled=False,
        reference_comparison_skipped=True,
    )
    payload = result.to_dict()

    assert result.passed
    assert result.reference_comparison_skipped
    assert result.reference_comparison_ran is False
    assert payload["reference_comparison_skipped"] is True
    assert_json_safe(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("graph_export", object()),
        ("options", object()),
        ("output_layout", object()),
        ("reference_comparison_enabled", "yes"),
        ("reference_comparison_skipped", "no"),
        ("reference_comparison_json_path", "report.json"),
        ("reference_comparison_json_written", "yes"),
        (
            "issues",
            [PreprocessingGraphWorkflowReferenceComparisonIssue("k", "m")],
        ),
        ("issues", (object(),)),
    ),
)
def test_reference_comparison_result_rejects_invalid_values(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    layout = output_layout(tmp_path / "out")
    kwargs: dict[str, object] = {
        "graph_export": graph_export_result(tmp_path / "out"),
        "options": workflow_options(output_dir=layout.output_dir),
        "output_layout": layout,
        "reference_comparison_enabled": False,
        "reference_comparison_skipped": True,
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowReferenceComparisonResult(**kwargs)


def test_reference_comparison_disabled_skips_without_stage_14_or_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: calls.append("compare"),
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(
            tmp_path / "out",
            issues=(PreprocessingGraphWorkflowGraphExportIssue("failed", "Failed."),),
        ),
        workflow_options(output_dir=layout.output_dir),
        layout,
    )

    assert result.passed
    assert result.reference_comparison_skipped
    assert result.graph_export_passed is False
    assert result.reference_comparison_ran is False
    assert calls == []
    assert not layout.reference_comparison_json_path.exists()
    assert_json_safe(result.to_dict())


def test_reference_comparison_requires_explicit_paths_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: calls.append("compare"),
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(tmp_path / "out"),
        workflow_options(
            output_dir=layout.output_dir,
            enable_reference_comparison=True,
        ),
        layout,
    )

    assert not result.passed
    assert issue_kinds(result) == {"reference_paths_required"}
    assert result.reference_paths_provided is False
    assert result.reference_comparison_ran is False
    assert calls == []
    assert not layout.reference_comparison_json_path.exists()


def test_failed_graph_export_prevents_reference_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: calls.append("compare"),
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(
            tmp_path / "out",
            issues=(PreprocessingGraphWorkflowGraphExportIssue("failed", "Failed."),),
        ),
        enabled_options(layout.output_dir),
        layout,
    )

    assert not result.passed
    assert issue_kinds(result) == {"graph_export_failed"}
    assert result.reference_comparison_ran is False
    assert calls == []
    assert not layout.reference_comparison_json_path.exists()


def test_reference_comparison_calls_stage_14_with_explicit_paths_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    received: dict[str, Path] = {}
    comparison_result = FakeReferenceComparisonResult()

    def fake_compare(comparison_input: object) -> object:
        stage_14_input = cast(Any, comparison_input)
        calls.append("compare_preprocessing_graph_reference_artifacts")
        received["generated_nodes_csv_path"] = (
            stage_14_input.generated_nodes_csv_path
        )
        received["generated_edges_csv_path"] = (
            stage_14_input.generated_edges_csv_path
        )
        received["generated_graph_json_path"] = (
            stage_14_input.generated_graph_json_path
        )
        received["reference_nodes_csv_path"] = (
            stage_14_input.reference_nodes_csv_path
        )
        received["reference_edges_csv_path"] = (
            stage_14_input.reference_edges_csv_path
        )
        received["reference_graph_json_path"] = (
            stage_14_input.reference_graph_json_path
        )
        return comparison_result

    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: fake_compare,
    )
    layout = output_layout(tmp_path / "out")
    export = graph_export_result(tmp_path / "out")

    result = compare_preprocessing_graph_workflow_reference_artifacts(
        export,
        enabled_options(layout.output_dir),
        layout,
    )
    payload = json.loads(layout.reference_comparison_json_path.read_text())

    assert result.passed
    assert calls == ["compare_preprocessing_graph_reference_artifacts"]
    assert result.reference_comparison_result is comparison_result
    assert result.reference_comparison_json_written
    assert received["generated_nodes_csv_path"] == export.graph_nodes_csv_path
    assert received["generated_edges_csv_path"] == export.graph_edges_csv_path
    assert received["generated_graph_json_path"] == export.graph_json_path
    assert received["reference_nodes_csv_path"] == Path("reference/nodes.csv")
    assert received["reference_edges_csv_path"] == Path("reference/edges.csv")
    assert received["reference_graph_json_path"] == Path("reference/graph.json")
    assert payload["reference_comparison_passed"] is True
    assert payload["comparison_metadata"]["target_count"] == 3
    assert not layout.diagnostics_report_json_path.exists()
    assert_json_safe(result.to_dict())


def test_reference_comparison_mismatch_does_not_write_failed_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_result = FakeReferenceComparisonResult(
        passed=False,
        failed_target_count=1,
        mismatch_count=2,
    )
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: comparison_result,
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(tmp_path / "out"),
        enabled_options(layout.output_dir),
        layout,
    )

    assert not result.passed
    assert issue_kinds(result) == {"reference_comparison_mismatch"}
    assert result.reference_comparison_json_written is False
    assert not layout.reference_comparison_json_path.exists()
    assert not layout.diagnostics_report_json_path.exists()


def test_reference_comparison_report_writing_can_be_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: FakeReferenceComparisonResult(),
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(tmp_path / "out"),
        enabled_options(layout.output_dir),
        layout,
        write_report_json=False,
    )

    assert result.passed
    assert result.reference_comparison_json_path is None
    assert result.reference_comparison_json_written is False
    assert not layout.reference_comparison_json_path.exists()


def test_reference_comparison_result_to_dict_excludes_raw_internals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "RAW_SENTINEL_SHOULD_NOT_APPEAR"
    comparison_result = FakeReferenceComparisonResult(
        internal={"secret": sentinel}
    )
    monkeypatch.setattr(
        workflow,
        "_graph_reference_comparator",
        lambda: lambda comparison_input: comparison_result,
    )
    layout = output_layout(tmp_path / "out")
    result = compare_preprocessing_graph_workflow_reference_artifacts(
        graph_export_result(tmp_path / "out"),
        enabled_options(layout.output_dir),
        layout,
    )
    encoded = json.dumps(result.to_dict())

    assert result.reference_comparison_ran
    assert sentinel not in encoded


def test_reference_comparison_function_rejects_invalid_arguments(
    tmp_path: Path,
) -> None:
    layout = output_layout(tmp_path / "out")
    export = graph_export_result(tmp_path / "out")
    options = workflow_options(output_dir=layout.output_dir)

    with pytest.raises(ValueError, match="graph_export"):
        compare_preprocessing_graph_workflow_reference_artifacts(
            object(),
            options,
            layout,
        )
    with pytest.raises(ValueError, match="options"):
        compare_preprocessing_graph_workflow_reference_artifacts(
            export,
            object(),
            layout,
        )
    with pytest.raises(ValueError, match="output_layout"):
        compare_preprocessing_graph_workflow_reference_artifacts(
            export,
            options,
            object(),
        )
    with pytest.raises(ValueError, match="write_report_json"):
        compare_preprocessing_graph_workflow_reference_artifacts(
            export,
            options,
            layout,
            write_report_json="yes",
        )
    with pytest.raises(ValueError, match="create_parent_directories"):
        compare_preprocessing_graph_workflow_reference_artifacts(
            export,
            options,
            layout,
            create_parent_directories="yes",
        )


def test_reference_comparison_function_does_not_load_manifests_or_runtimes() -> None:
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


def test_reference_comparison_function_does_not_compute_or_export() -> None:
    source = wrapper_source()
    forbidden = (
        "compute_manifest_rg",
        "compute_manifest_contacts",
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
        "run_preprocessing_graph_workflow_diagnostics",
    )

    for name in forbidden:
        assert name not in source


def test_reference_comparison_function_does_not_search_or_execute_notebooks() -> None:
    source = wrapper_source()
    forbidden = (
        "data/reference",
        "glob",
        "rglob",
        "nbconvert",
        "jupyter",
        "papermill",
        "notebook",
        "temporal",
        "temporal_rin",
        "WANIA",
        "frontend",
        "mania.cli",
        "pipeline_steps",
    )

    for name in forbidden:
        assert name not in source


def test_workflow_module_has_dependency_free_imports() -> None:
    source = module_source()
    forbidden = ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow")

    for name in forbidden:
        assert name not in source


def test_docs_mention_stage_15_7_boundary() -> None:
    text = docs_text()
    required = (
        "Stage 15.7",
        "optional reference comparison",
        "disabled by default",
        "deterministic skipped success",
        "explicit reference artifact paths",
        "accepted Stage 14.3a",
        "accepted Stage 14.3b",
        "no new comparison algorithm",
        "no programmatic expected mismatch classification",
        "reports/graph_reference_comparison.json",
        "no notebook execution",
        "no automatic reference artifact search",
        "no temporal RIN",
        "no CLI",
        "WANIA frontend",
        "dependency-free",
        "no MDAnalysis",
        "no real MD data",
    )

    for phrase in required:
        assert phrase in text
