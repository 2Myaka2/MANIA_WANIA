import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingConditionRgResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    PreprocessingGraphWorkflowScientificCsvExportIssue,
    PreprocessingGraphWorkflowScientificCsvExportResult,
    PreprocessingManifestContactsResult,
    PreprocessingManifestRgResult,
    PreprocessingRgFrameResult,
    export_preprocessing_graph_workflow_scientific_csvs,
)
from mania.preprocessing import trajectory_graph_workflow as workflow


@dataclass(frozen=True)
class FakeRuntimeLoadResult:
    loaded_condition_names: tuple[str, ...] = ("normal",)
    passed: bool = True


@dataclass(frozen=True)
class FakeValidationResult:
    csv_path: Path
    passed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "csv_path": str(self.csv_path),
            "passed": self.passed,
            "issues": [
                {
                    "kind": "forced_validation_failure",
                    "field": "csv_path",
                    "message": "Forced validation failure.",
                }
            ],
        }


_UNSET = object()


def assert_json_safe(payload: object) -> None:
    json.dumps(payload, sort_keys=True)


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


def readiness_result() -> PreprocessingGraphWorkflowManifestReadinessResult:
    return PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=("normal",),
        expected_condition_count=1,
    )


def runtime_loading_result() -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=Path("local_md/manifests/napi2b_10ns.yaml"),
        manifest_readiness=readiness_result(),
        condition_names=("normal",),
        expected_condition_names=("normal",),
        runtime_load_result=FakeRuntimeLoadResult(),
    )


def rg_result() -> PreprocessingManifestRgResult:
    return PreprocessingManifestRgResult(
        condition_results=(
            PreprocessingConditionRgResult(
                condition_name="normal",
                status="computed",
                runtime_type="synthetic",
                topology_path=None,
                trajectory_paths=(),
                frame_time_ps=1.0,
                rg_unit="angstrom",
                frame_results=(
                    PreprocessingRgFrameResult(
                        condition_name="normal",
                        frame_index=0,
                        time_ps=0.0,
                        rg_value=12.5,
                        rg_unit="angstrom",
                    ),
                ),
            ),
        )
    )


def contacts_result() -> PreprocessingManifestContactsResult:
    contact = PreprocessingContactPairResult(
        source_residue_index=1,
        target_residue_index=2,
        source_resname="ALA",
        target_resname="GLY",
        minimum_distance=3.1,
        distance_unit="angstrom",
        atom_filter="heavy",
        source_residue_id=10,
        target_residue_id=11,
        source_segid="A",
        target_segid="A",
    )
    frame = PreprocessingContactFrameResult(
        condition_name="normal",
        frame_index=0,
        time_ps=0.0,
        contacts=(contact,),
    )
    return PreprocessingManifestContactsResult(
        condition_results=(
            PreprocessingConditionContactsResult(
                condition_name="normal",
                options=PreprocessingContactDetectionOptions(),
                frame_results=(frame,),
                status="computed",
            ),
        )
    )


def computation_result(
    *,
    rg_source: object | None = _UNSET,
    contacts_source: object | None = _UNSET,
    include_rg: bool = True,
    include_contacts: bool = True,
) -> PreprocessingGraphWorkflowComputationResult:
    if rg_source is _UNSET:
        rg_source = rg_result()
    if contacts_source is _UNSET:
        contacts_source = contacts_result()
    return PreprocessingGraphWorkflowComputationResult(
        runtime_loading=runtime_loading_result(),
        condition_names=("normal",),
        include_rg=include_rg,
        include_contacts=include_contacts,
        rg_result=rg_source,
        contacts_result=contacts_source,
    )


def issue_kinds(
    result: PreprocessingGraphWorkflowScientificCsvExportResult,
) -> set[str]:
    return {issue.kind for issue in result.issues}


def test_public_exports_work() -> None:
    assert PreprocessingGraphWorkflowScientificCsvExportIssue is not None
    assert PreprocessingGraphWorkflowScientificCsvExportResult is not None
    assert callable(export_preprocessing_graph_workflow_scientific_csvs)
    assert mania.preprocessing.export_preprocessing_graph_workflow_scientific_csvs


def test_scientific_csv_export_skips_by_default(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "out"),
    )

    assert result.passed
    assert result.skipped
    assert result.to_dict()["paths"] == {}
    assert not (tmp_path / "out" / "rg").exists()
    assert not (tmp_path / "out" / "contacts").exists()
    assert_json_safe(result.to_dict())


def test_rg_timeseries_csv_written_when_enabled(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "out"),
        export_rg_timeseries=True,
    )
    payload = result.to_dict()

    assert result.passed
    assert result.rg_timeseries_written
    assert (tmp_path / "out" / "rg" / "rg_timeseries.csv").is_file()
    assert not (tmp_path / "out" / "contacts").exists()
    assert payload["validation"]["rg_timeseries"] is not None
    assert_json_safe(payload)


def test_contact_edges_csv_written_when_enabled(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "out"),
        export_contact_edges=True,
    )
    payload = result.to_dict()

    assert result.passed
    assert result.contact_edges_written
    assert (tmp_path / "out" / "contacts" / "contact_edges.csv").is_file()
    assert not (tmp_path / "out" / "contacts" / "contacts_perframe.csv").exists()
    assert not (tmp_path / "out" / "graph" / "edges.csv").exists()
    assert payload["validation"]["contact_edges"] is not None
    assert_json_safe(payload)


def test_contacts_perframe_csv_requires_explicit_enable(
    tmp_path: Path,
) -> None:
    safe_result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "safe"),
        export_rg_timeseries=True,
        export_contact_edges=True,
        export_contacts_perframe=False,
    )
    full_result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "full"),
        export_contacts_perframe=True,
    )

    assert safe_result.passed
    assert not (
        tmp_path / "safe" / "contacts" / "contacts_perframe.csv"
    ).exists()
    assert full_result.passed
    assert full_result.contacts_perframe_written
    assert (
        tmp_path / "full" / "contacts" / "contacts_perframe.csv"
    ).is_file()
    assert full_result.to_dict()["validation"]["contacts_perframe"] is not None


def test_missing_rg_result_gives_clear_issue(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(rg_source=None),
        output_layout(tmp_path / "out"),
        export_rg_timeseries=True,
    )

    assert not result.passed
    assert "rg_result_missing" in issue_kinds(result)
    assert not (tmp_path / "out" / "rg" / "rg_timeseries.csv").exists()
    assert_json_safe(result.to_dict())


def test_missing_contacts_result_gives_clear_issue(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(contacts_source=None),
        output_layout(tmp_path / "out"),
        export_contact_edges=True,
        export_contacts_perframe=True,
    )

    assert not result.passed
    assert "contacts_result_missing" in issue_kinds(result)
    assert not (tmp_path / "out" / "contacts" / "contact_edges.csv").exists()
    assert not (tmp_path / "out" / "contacts" / "contacts_perframe.csv").exists()
    assert_json_safe(result.to_dict())


def test_writer_failure_gives_clear_issue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def failing_writer(source_result: object, output_path: str | Path) -> object:
        raise OSError("forced writer failure")

    monkeypatch.setattr(
        workflow,
        "_rg_timeseries_csv_writer",
        lambda: failing_writer,
    )

    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "out"),
        export_rg_timeseries=True,
    )

    assert not result.passed
    assert "rg_timeseries_write_failed" in issue_kinds(result)
    assert not (tmp_path / "out" / "rg" / "rg_timeseries.csv").exists()
    assert_json_safe(result.to_dict())


def test_validation_failure_gives_clear_issue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def failing_validator(csv_path: str | Path) -> FakeValidationResult:
        return FakeValidationResult(Path(csv_path), passed=False)

    monkeypatch.setattr(
        workflow,
        "_rg_timeseries_csv_validator",
        lambda: failing_validator,
    )

    result = export_preprocessing_graph_workflow_scientific_csvs(
        computation_result(),
        output_layout(tmp_path / "out"),
        export_rg_timeseries=True,
    )
    payload = result.to_dict()
    validation_payload = payload["validation"]["rg_timeseries"]

    assert not result.passed
    assert "rg_timeseries_validation_failed" in issue_kinds(result)
    assert (tmp_path / "out" / "rg" / "rg_timeseries.csv").is_file()
    assert isinstance(validation_payload, dict)
    assert validation_payload["issues"][0]["kind"] == "forced_validation_failure"
    assert_json_safe(payload)
