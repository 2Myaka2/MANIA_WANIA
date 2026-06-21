import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowDiagnosticsIssue,
    PreprocessingGraphWorkflowDiagnosticsResult,
    PreprocessingGraphWorkflowGraphExportIssue,
    PreprocessingGraphWorkflowGraphExportResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowPlan,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    build_preprocessing_graph_diagnostics_report,
    build_preprocessing_graph_workflow_plan,
    check_preprocessing_graph_workflow_manifest_readiness,
    compute_preprocessing_graph_workflow_rg_contacts,
    export_preprocessing_graph_workflow_artifacts,
    load_preprocessing_graph_workflow_condition_runtimes,
    run_preprocessing_graph_diagnostics,
    run_preprocessing_graph_workflow_diagnostics,
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
class FakeDiagnosticsRunResult:
    passed: bool
    payload: dict[str, object]
    internal: object | None = None

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


@dataclass(frozen=True)
class FakeDiagnosticsReport:
    passed: bool = True
    internal: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "sections": [{"title": "overview", "status": "passed"}],
        }


def assert_json_safe(payload: object) -> None:
    json.dumps(payload, allow_nan=False)


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def wrapper_source() -> str:
    return inspect.getsource(
        workflow.run_preprocessing_graph_workflow_diagnostics
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


def patch_stage_14_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_result: object | None = None,
    report: object | None = None,
    run_raises: Exception | None = None,
    report_raises: Exception | None = None,
) -> tuple[list[str], dict[str, Path]]:
    calls: list[str] = []
    received: dict[str, Path] = {}
    diagnostics_result = run_result or FakeStageResult("diagnostics_run")
    diagnostics_report = report or FakeDiagnosticsReport()

    def fake_run(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
        graph_json_path: str | Path,
    ) -> object:
        calls.append("run_preprocessing_graph_diagnostics")
        received["nodes_csv_path"] = Path(nodes_csv_path)
        received["edges_csv_path"] = Path(edges_csv_path)
        received["graph_json_path"] = Path(graph_json_path)
        if run_raises is not None:
            raise run_raises
        return diagnostics_result

    def fake_report(diagnostics_run_result: object) -> object:
        calls.append("build_preprocessing_graph_diagnostics_report")
        assert diagnostics_run_result is diagnostics_result
        if report_raises is not None:
            raise report_raises
        return diagnostics_report

    monkeypatch.setattr(workflow, "_graph_diagnostics_runner", lambda: fake_run)
    monkeypatch.setattr(
        workflow,
        "_graph_diagnostics_report_builder",
        lambda: fake_report,
    )
    return calls, received


def issue_kinds(
    result: PreprocessingGraphWorkflowDiagnosticsResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowDiagnosticsIssue is not None
    assert PreprocessingGraphWorkflowDiagnosticsResult is not None
    assert callable(run_preprocessing_graph_workflow_diagnostics)


def test_existing_stage_15_1_to_15_5_exports_still_work() -> None:
    for api in (
        PreprocessingGraphWorkflowOptions,
        PreprocessingGraphWorkflowOutputLayout,
        PreprocessingGraphWorkflowPlan,
        build_preprocessing_graph_workflow_plan,
        PreprocessingGraphWorkflowManifestReadinessResult,
        check_preprocessing_graph_workflow_manifest_readiness,
        PreprocessingGraphWorkflowRuntimeLoadingResult,
        load_preprocessing_graph_workflow_condition_runtimes,
        PreprocessingGraphWorkflowComputationResult,
        compute_preprocessing_graph_workflow_rg_contacts,
        PreprocessingGraphWorkflowGraphExportResult,
        export_preprocessing_graph_workflow_artifacts,
    ):
        assert api is not None


def test_existing_stage_14_diagnostics_exports_still_work() -> None:
    assert callable(run_preprocessing_graph_diagnostics)
    assert callable(build_preprocessing_graph_diagnostics_report)


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_diagnostics_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphWorkflowDiagnosticsIssue(
        kind="diagnostics_run_failed",
        message="Diagnostics failed.",
        stage="graph_diagnostics",
        field="diagnostics_run_result",
        path=Path("reports/graph_diagnostics_report.json"),
        value="Fake",
    )

    assert issue.to_dict()["path"] == "reports/graph_diagnostics_report.json"
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
        ("path", "reports/graph_diagnostics_report.json"),
    ),
)
def test_diagnostics_issue_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": "diagnostics_run_failed",
        "message": "Diagnostics failed.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowDiagnosticsIssue(**kwargs)


def test_diagnostics_result_validates_and_serializes(tmp_path: Path) -> None:
    run_result = FakeDiagnosticsRunResult(
        passed=True,
        payload={
            "passed": True,
            "node_count": 123,
            "edge_count": 456,
            "check_count": 1,
            "failed_check_count": 0,
            "checks": [],
            "issues": [],
            "raw_internal": "RAW_SENTINEL_SHOULD_NOT_APPEAR",
        },
        internal={"raw": object()},
    )
    report = FakeDiagnosticsReport(internal={"raw": object()})
    result = PreprocessingGraphWorkflowDiagnosticsResult(
        graph_export=graph_export_result(tmp_path / "out"),
        diagnostics_run_result=run_result,
        diagnostics_report=report,
        diagnostics_report_json_path=(
            tmp_path / "out" / "reports" / "graph_diagnostics_report.json"
        ),
        diagnostics_report_json_written=True,
    )
    payload = result.to_dict()

    assert result.passed
    assert result.issue_count == 0
    assert result.diagnostics_ran
    assert result.diagnostics_passed
    assert result.diagnostics_report_built
    assert payload["diagnostics_run"] == {
        "passed": True,
        "node_count": 123,
        "edge_count": 456,
        "check_count": 1,
        "failed_check_count": 0,
        "checks": [],
        "issues": [],
    }
    assert payload["diagnostics_run_result_type"].endswith(
        "FakeDiagnosticsRunResult"
    )
    assert payload["diagnostics_report_type"].endswith("FakeDiagnosticsReport")
    assert_json_safe(payload)
    assert "raw" not in json.dumps(payload)


def test_diagnostics_result_to_dict_includes_failed_run_details(
    tmp_path: Path,
) -> None:
    run_payload = {
        "passed": False,
        "node_count": 123,
        "edge_count": 456,
        "check_count": 3,
        "failed_check_count": 1,
        "checks": [
            {
                "name": "edge_count_nonzero",
                "passed": False,
                "summary": "No graph edges passed diagnostics.",
                "issues": [
                    {
                        "kind": "empty_edges",
                        "message": "No edges found.",
                    }
                ],
            }
        ],
        "issues": [],
        "internal": "RAW_SENTINEL_SHOULD_NOT_APPEAR",
    }
    result = PreprocessingGraphWorkflowDiagnosticsResult(
        graph_export=graph_export_result(tmp_path / "out"),
        diagnostics_run_result=FakeDiagnosticsRunResult(
            passed=False,
            payload=run_payload,
        ),
        diagnostics_report=FakeDiagnosticsReport(passed=False),
        diagnostics_report_json_path=(
            tmp_path / "out" / "reports" / "graph_diagnostics_report.json"
        ),
        diagnostics_report_json_written=True,
        issues=(
            PreprocessingGraphWorkflowDiagnosticsIssue(
                kind="diagnostics_checks_failed",
                message="Stage 14 graph_diagnostics step did not pass.",
            ),
        ),
    )

    payload = result.to_dict()
    diagnostics_run = payload["diagnostics_run"]
    encoded = json.dumps(payload, allow_nan=False)

    assert not result.passed
    assert isinstance(diagnostics_run, dict)
    assert diagnostics_run["node_count"] == 123
    assert diagnostics_run["edge_count"] == 456
    assert diagnostics_run["failed_check_count"] == 1
    assert diagnostics_run["checks"] == run_payload["checks"]
    assert "RAW_SENTINEL_SHOULD_NOT_APPEAR" not in encoded


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("graph_export", object()),
        ("diagnostics_report_json_path", "report.json"),
        ("diagnostics_report_json_written", "yes"),
        ("issues", [PreprocessingGraphWorkflowDiagnosticsIssue("k", "m")]),
        ("issues", (object(),)),
    ),
)
def test_diagnostics_result_rejects_invalid_values(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "graph_export": graph_export_result(tmp_path / "out"),
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphWorkflowDiagnosticsResult(**kwargs)


def test_failed_graph_export_prevents_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(monkeypatch)
    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(
            tmp_path / "out",
            issues=(PreprocessingGraphWorkflowGraphExportIssue("failed", "Failed."),),
        )
    )

    assert not result.passed
    assert issue_kinds(result) == {"graph_export_failed"}
    assert calls == []
    assert not result.diagnostics_report_json_path.exists()


def test_successful_diagnostics_calls_stage_14_apis_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(monkeypatch)
    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )

    assert result.passed
    assert calls == [
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
    ]
    assert result.diagnostics_run_result is not None
    assert result.diagnostics_report is not None
    assert_json_safe(result.to_dict())


def test_workflow_to_dict_preserves_condition_aware_diagnostics_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_payload = {
        "passed": True,
        "node_count": 4,
        "edge_count": 2,
        "check_count": 6,
        "failed_check_count": 0,
        "detected_conditions": ["normal", "tumor"],
        "checks": [
            {"name": "graph_export_bundle", "passed": True},
            {"name": "graph_json_validation", "passed": True},
            {"name": "contract_graph_load:normal", "passed": True},
            {"name": "graph_structure_diagnostics:normal", "passed": True},
            {"name": "contract_graph_load:tumor", "passed": True},
            {"name": "graph_structure_diagnostics:tumor", "passed": True},
        ],
        "issues": [],
    }
    patch_stage_14_diagnostics(
        monkeypatch,
        run_result=FakeDiagnosticsRunResult(
            passed=True,
            payload=run_payload,
        ),
    )

    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )
    diagnostics_run = result.to_dict()["diagnostics_run"]

    assert result.passed
    assert isinstance(diagnostics_run, dict)
    assert diagnostics_run["detected_conditions"] == ["normal", "tumor"]
    assert diagnostics_run["checks"] == run_payload["checks"]
    checks = diagnostics_run["checks"]
    assert isinstance(checks, list)
    assert "contract_graph_load:tumor" in {
        check["name"] for check in checks if isinstance(check, dict)
    }


def test_diagnostics_runner_receives_graph_artifact_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, received = patch_stage_14_diagnostics(monkeypatch)
    export = graph_export_result(tmp_path / "out")

    result = run_preprocessing_graph_workflow_diagnostics(export)

    assert result.passed
    assert calls[0] == "run_preprocessing_graph_diagnostics"
    assert received["nodes_csv_path"] == export.graph_nodes_csv_path
    assert received["edges_csv_path"] == export.graph_edges_csv_path
    assert received["graph_json_path"] == export.graph_json_path


def test_failed_diagnostics_run_still_builds_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_payload = {
        "passed": False,
        "node_count": 123,
        "edge_count": 456,
        "check_count": 3,
        "failed_check_count": 1,
        "checks": [
            {
                "name": "edge_count_nonzero",
                "passed": False,
                "summary": "No graph edges passed diagnostics.",
                "issues": [
                    {
                        "kind": "empty_edges",
                        "message": "No edges found.",
                    }
                ],
            }
        ],
        "issues": [],
    }
    run_result = FakeDiagnosticsRunResult(
        passed=False,
        payload=run_payload,
    )
    calls, _ = patch_stage_14_diagnostics(
        monkeypatch,
        run_result=run_result,
    )
    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )
    payload = result.to_dict()

    assert not result.passed
    assert issue_kinds(result) == {"diagnostics_checks_failed"}
    assert calls == [
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
    ]
    assert result.diagnostics_run_result is run_result
    assert result.diagnostics_report is not None
    assert result.diagnostics_report_built is True
    assert payload["diagnostics_run"] == run_payload


def test_failed_diagnostics_run_still_writes_report_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_result = FakeDiagnosticsRunResult(
        passed=False,
        payload={
            "passed": False,
            "node_count": 2,
            "edge_count": 0,
            "check_count": 1,
            "failed_check_count": 1,
            "checks": [],
            "issues": [],
        },
    )
    patch_stage_14_diagnostics(
        monkeypatch,
        run_result=run_result,
        report=FakeDiagnosticsReport(passed=False),
    )
    export = graph_export_result(tmp_path / "out")

    result = run_preprocessing_graph_workflow_diagnostics(
        export,
        write_report_json=True,
    )
    report_payload = json.loads(
        export.output_layout.diagnostics_report_json_path.read_text()
    )

    assert not result.passed
    assert result.diagnostics_report_json_written is True
    assert report_payload == {
        "passed": False,
        "sections": [{"status": "passed", "title": "overview"}],
    }
    assert result.to_dict()["diagnostics_run"] == run_result.to_dict()


def test_diagnostics_runner_exception_is_hard_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(
        monkeypatch,
        run_raises=RuntimeError("boom"),
    )
    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )

    assert not result.passed
    assert issue_kinds(result) == {"diagnostics_run_failed"}
    assert calls == ["run_preprocessing_graph_diagnostics"]
    assert not result.diagnostics_report_json_path.exists()
    assert result.to_dict()["diagnostics_run"] is None


def test_diagnostics_report_builder_failure_is_reported_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(
        monkeypatch,
        report_raises=RuntimeError("boom"),
    )
    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )

    assert not result.passed
    assert issue_kinds(result) == {"diagnostics_report_failed"}
    assert calls == [
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
    ]
    assert not result.diagnostics_report_json_path.exists()


def test_report_json_is_written_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_stage_14_diagnostics(monkeypatch)
    export = graph_export_result(tmp_path / "out")

    result = run_preprocessing_graph_workflow_diagnostics(export)
    payload = json.loads(export.output_layout.diagnostics_report_json_path.read_text())

    assert result.passed
    assert result.diagnostics_report_json_written is True
    assert payload == {
        "passed": True,
        "sections": [{"status": "passed", "title": "overview"}],
    }


def test_report_json_writing_can_be_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(monkeypatch)
    export = graph_export_result(tmp_path / "out")

    result = run_preprocessing_graph_workflow_diagnostics(
        export,
        write_report_json=False,
    )

    assert result.passed
    assert calls == [
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
    ]
    assert result.diagnostics_report_json_path is None
    assert result.diagnostics_report_json_written is False
    assert not export.output_layout.diagnostics_report_json_path.exists()


def test_report_parent_directory_is_created_only_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_stage_14_diagnostics(monkeypatch)
    enabled_export = graph_export_result(tmp_path / "enabled")

    enabled_result = run_preprocessing_graph_workflow_diagnostics(
        enabled_export,
        create_parent_directories=True,
    )

    assert enabled_result.passed
    assert enabled_export.output_layout.diagnostics_report_json_path.parent.exists()

    disabled_export = graph_export_result(tmp_path / "disabled")
    disabled_result = run_preprocessing_graph_workflow_diagnostics(
        disabled_export,
        create_parent_directories=False,
    )

    assert not disabled_result.passed
    assert issue_kinds(disabled_result) == {"diagnostics_report_json_write_failed"}
    assert not (
        disabled_export.output_layout.diagnostics_report_json_path.parent.exists()
    )


def test_report_json_write_failure_is_reported_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_stage_14_diagnostics(monkeypatch)
    export = graph_export_result(tmp_path / "out")
    export.output_layout.output_dir.mkdir()
    export.output_layout.diagnostics_report_json_path.parent.write_text(
        "not a directory",
        encoding="utf-8",
    )

    result = run_preprocessing_graph_workflow_diagnostics(export)

    assert not result.passed
    assert issue_kinds(result) == {"diagnostics_report_json_write_failed"}


def test_only_diagnostics_report_json_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_stage_14_diagnostics(monkeypatch)
    layout = output_layout(tmp_path / "out")

    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )

    assert result.passed
    assert layout.diagnostics_report_json_path.is_file()
    assert not (layout.output_dir / "rg").exists()
    assert not (layout.output_dir / "contacts").exists()
    assert not (layout.output_dir / "graph").exists()
    assert not layout.reference_comparison_json_path.exists()


def test_result_to_dict_excludes_raw_internals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "RAW_SENTINEL_SHOULD_NOT_APPEAR"
    run_result = FakeStageResult("diagnostics", internal={"secret": sentinel})
    report = FakeDiagnosticsReport(internal={"secret": sentinel})
    patch_stage_14_diagnostics(
        monkeypatch,
        run_result=run_result,
        report=report,
    )

    result = run_preprocessing_graph_workflow_diagnostics(
        graph_export_result(tmp_path / "out")
    )
    encoded = json.dumps(result.to_dict())

    assert result.passed
    assert sentinel not in encoded


def test_diagnostics_function_rejects_invalid_arguments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="graph_export"):
        run_preprocessing_graph_workflow_diagnostics(object())
    with pytest.raises(ValueError, match="write_report_json"):
        run_preprocessing_graph_workflow_diagnostics(
            graph_export_result(tmp_path / "out"),
            write_report_json="yes",
        )
    with pytest.raises(ValueError, match="create_parent_directories"):
        run_preprocessing_graph_workflow_diagnostics(
            graph_export_result(tmp_path / "out"),
            create_parent_directories="yes",
        )


def test_invalid_report_output_layout_prevents_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(monkeypatch)
    root = tmp_path / "out"
    layout = PreprocessingGraphWorkflowOutputLayout(
        output_dir=root,
        run_name="preprocessing_graph_export",
        rg_timeseries_csv_path=root / "rg" / "rg_timeseries.csv",
        contacts_perframe_csv_path=root / "contacts" / "contacts_perframe.csv",
        contact_edges_csv_path=root / "contacts" / "contact_edges.csv",
        graph_nodes_csv_path=root / "graph" / "nodes.csv",
        graph_edges_csv_path=root / "graph" / "edges.csv",
        graph_json_path=root / "graph" / "graph.json",
        diagnostics_report_json_path=root / "elsewhere" / "report.json",
        reference_comparison_json_path=(
            root / "reports" / "graph_reference_comparison.json"
        ),
    )
    export = graph_export_result(root)
    object.__setattr__(export, "output_layout", layout)

    result = run_preprocessing_graph_workflow_diagnostics(export)

    assert not result.passed
    assert issue_kinds(result) == {"output_layout_invalid"}
    assert calls == []


def test_missing_graph_artifact_path_metadata_prevents_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = patch_stage_14_diagnostics(monkeypatch)
    export = graph_export_result(tmp_path / "out")
    object.__setattr__(
        export,
        "graph_nodes_csv_path",
        tmp_path / "out" / "elsewhere" / "nodes.csv",
    )

    result = run_preprocessing_graph_workflow_diagnostics(export)

    assert not result.passed
    assert issue_kinds(result) == {"graph_artifact_missing"}
    assert calls == []


def test_diagnostics_function_does_not_load_manifests_or_runtimes() -> None:
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


def test_diagnostics_function_does_not_compute_rg_or_contacts() -> None:
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


def test_diagnostics_function_does_not_export_graph_artifacts() -> None:
    source = wrapper_source()
    forbidden = (
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
        "export_preprocessing_graph_workflow_artifacts",
    )

    for name in forbidden:
        assert name not in source


def test_diagnostics_function_does_not_write_unrelated_files() -> None:
    source = wrapper_source()
    forbidden = (
        "write_rg_timeseries_csv",
        "write_contacts_perframe_csv",
        "write_contact_edges_csv",
        "graph_reference_comparison.json",
    )

    for name in forbidden:
        assert name not in source


def test_diagnostics_function_does_not_perform_reference_comparison() -> None:
    source = wrapper_source()
    forbidden = (
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
    )

    for name in forbidden:
        assert name not in source


def test_diagnostics_function_does_not_execute_notebooks() -> None:
    source = wrapper_source()
    forbidden = ("nbconvert", "jupyter", "papermill", "notebook")

    for name in forbidden:
        assert name not in source


def test_diagnostics_function_does_not_call_cli_or_workflow() -> None:
    source = wrapper_source()
    forbidden = ("mania.cli", "pipeline_steps", "pipeline modules")

    for name in forbidden:
        assert name not in source


def test_workflow_module_has_dependency_free_imports() -> None:
    source = module_source()
    forbidden = ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow")

    for name in forbidden:
        assert name not in source


def test_docs_mention_stage_15_6_boundary() -> None:
    text = docs_text()
    required = (
        "Stage 15.6",
        "diagnostics",
        "diagnostics report",
        "no reference comparison",
        "no CLI",
        "Stage 15.5 graph export result feeds Stage 15.6",
        "Stage 15.6 does not export graph artifacts",
        "accepted Stage 14 diagnostics runner",
        "accepted Stage 14 diagnostics report builder",
        "no new diagnostics algorithms",
        "reports/graph_diagnostics_report.json",
        "no reports/graph_reference_comparison.json",
        "Stage 15.7 will handle optional reference comparison",
        "Stage 15.6 does not perform reference comparison",
        "default CI",
        "optional dependency",
        "local_md",
        "notebook",
    )

    for phrase in required:
        assert phrase in text
