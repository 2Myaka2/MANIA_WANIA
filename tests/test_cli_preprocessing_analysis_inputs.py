import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import mania.cli as cli
from mania.preprocessing import (
    EDGE_SEMANTICS_FILENAME,
    MANIA_MANIFEST_FILENAME,
    MANIA_RESIDUE_LIBRARY_FILENAME,
    PROTEIN_CONTACT_EDGE_COLUMNS,
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
    RESIDUE_TABLE_COLUMNS,
    PreprocessingCaCoordinate,
    PreprocessingConditionContactsResult,
    PreprocessingConditionRgResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingFrameSamplingOptions,
    PreprocessingGraphWorkflowAnalysisInputExportIssue,
    PreprocessingGraphWorkflowAnalysisInputExportResult,
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowGraphExportResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    PreprocessingManifestContactsResult,
    PreprocessingManifestRgResult,
    PreprocessingRgFrameResult,
    build_preprocessing_graph_export_mapping,
    export_preprocessing_graph_workflow_analysis_inputs,
)
from mania.preprocessing import trajectory_graph_workflow as workflow


@dataclass(frozen=True)
class FakeRuntimeLoadResult:
    loaded_condition_names: tuple[str, ...]
    passed: bool = True


@dataclass(frozen=True)
class FakeStageResult:
    passed: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed}


@dataclass(frozen=True)
class FakeWriteResult:
    passed: bool
    label: str

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "label": self.label,
            "issues": [] if self.passed else [{"kind": f"{self.label}_failed"}],
        }


def invoke_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
    expected_exit_code: int = 0,
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["mania", *args])
    if expected_exit_code == 0:
        cli.main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err

    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    captured = capsys.readouterr()
    assert exc_info.value.code == expected_exit_code
    return int(exc_info.value.code), captured.out, captured.err


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _runtime_loading_result(
    manifest_path: Path,
    conditions: tuple[str, ...],
) -> PreprocessingGraphWorkflowRuntimeLoadingResult:
    readiness = PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=manifest_path,
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=conditions,
        expected_condition_count=len(conditions),
    )
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest_path=manifest_path,
        manifest_readiness=readiness,
        condition_names=conditions,
        expected_condition_names=conditions,
        runtime_load_result=FakeRuntimeLoadResult(conditions),
    )


def _rg_result(conditions: tuple[str, ...]) -> PreprocessingManifestRgResult:
    return PreprocessingManifestRgResult(
        condition_results=tuple(
            PreprocessingConditionRgResult(
                condition_name=condition,
                status="computed",
                runtime_type="synthetic",
                topology_path=None,
                trajectory_paths=(),
                frame_time_ps=1.0,
                rg_unit="angstrom",
                frame_results=tuple(
                    PreprocessingRgFrameResult(
                        condition_name=condition,
                        frame_index=frame.frame_index,
                        time_ps=frame.time_ps,
                        rg_value=12.5,
                        rg_unit="angstrom",
                    )
                    for frame in _condition_contacts(condition).frame_results
                ),
            )
            for condition in conditions
        )
    )


def _pair(
    residue_i: int,
    residue_j: int,
    edge_type: str,
    distance_a: float,
) -> PreprocessingContactPairResult:
    identities = {
        1: (10, "ALA", "A"),
        2: (20, "GLY", "A"),
        3: (30, "LYS", "A"),
    }
    resid_i, resname_i, segid_i = identities[residue_i]
    resid_j, resname_j, segid_j = identities[residue_j]
    return PreprocessingContactPairResult(
        source_residue_index=residue_i,
        target_residue_index=residue_j,
        source_residue_id=resid_i,
        target_residue_id=resid_j,
        source_resname=resname_i,
        target_resname=resname_j,
        source_segid=segid_i,
        target_segid=segid_j,
        minimum_distance=distance_a,
        distance_unit="angstrom",
        atom_filter="heavy",
        edge_type=edge_type,
    )


def _condition_contacts(
    condition: str,
    *,
    contact_selection: str = "protein",
) -> PreprocessingConditionContactsResult:
    features = (
        (1, 2, "vdw", 3.3),
        (1, 2, "hbond", 2.8),
        (1, 3, "vdw", 3.4),
        (2, 3, "hbond", 2.9),
        (2, 3, "ionic", 3.1),
    )
    patterns = (
        (1, 0, 0, 0, 0),
        (0, 1, 0, 0, 0),
        (0, 0, 1, 0, 0),
        (0, 0, 0, 1, 0),
        (0, 0, 0, 0, 1),
        (1, 1, 1, 1, 1),
    )
    frames = []
    for frame_index, pattern in enumerate(patterns):
        contacts = tuple(
            _pair(residue_i, residue_j, edge_type, distance)
            for present, (residue_i, residue_j, edge_type, distance) in zip(
                pattern,
                features,
                strict=True,
            )
            if present
        )
        frames.append(
            PreprocessingContactFrameResult(
                condition_name=condition,
                frame_index=frame_index,
                time_ps=float(frame_index),
                contacts=contacts,
            )
        )
    return PreprocessingConditionContactsResult(
        condition_name=condition,
        options=PreprocessingContactDetectionOptions(
            contact_selection=contact_selection
        ),
        representative_ca_coordinates=(
            PreprocessingCaCoordinate(
                residue_index=1,
                residue_id=10,
                resname="ALA",
                segid="A",
                x_ca=0.0,
                y_ca=0.0,
                z_ca=0.0,
            ),
            PreprocessingCaCoordinate(
                residue_index=2,
                residue_id=20,
                resname="GLY",
                segid="A",
                x_ca=3.8,
                y_ca=0.0,
                z_ca=0.0,
            ),
            PreprocessingCaCoordinate(
                residue_index=3,
                residue_id=30,
                resname="LYS",
                segid="A",
                x_ca=7.6,
                y_ca=0.0,
                z_ca=0.0,
            ),
        ),
        frame_results=tuple(frames),
        status="computed",
    )


def _contacts_result(
    conditions: tuple[str, ...],
    *,
    contact_selection: str = "protein",
) -> PreprocessingManifestContactsResult:
    return PreprocessingManifestContactsResult(
        condition_results=tuple(
            _condition_contacts(
                condition,
                contact_selection=contact_selection,
            )
            for condition in conditions
        )
    )


def _output_layout(root: Path) -> PreprocessingGraphWorkflowOutputLayout:
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


def _computation_result(
    output_root: Path,
    conditions: tuple[str, ...],
    *,
    contact_selection: str = "protein",
) -> PreprocessingGraphWorkflowComputationResult:
    runtime_loading = _runtime_loading_result(
        Path("manifest.yaml"),
        conditions,
    )
    return PreprocessingGraphWorkflowComputationResult(
        runtime_loading=runtime_loading,
        condition_names=conditions,
        include_rg=True,
        include_contacts=True,
        frame_sampling=PreprocessingFrameSamplingOptions(),
        contact_detection_options=PreprocessingContactDetectionOptions(
            contact_selection=contact_selection
        ),
        rg_result=_rg_result(conditions),
        contacts_result=_contacts_result(
            conditions,
            contact_selection=contact_selection,
        ),
    )


def _graph_export_result(
    output_root: Path,
    conditions: tuple[str, ...],
    *,
    contact_selection: str = "protein",
) -> PreprocessingGraphWorkflowGraphExportResult:
    computation = _computation_result(
        output_root,
        conditions,
        contact_selection=contact_selection,
    )
    layout = _output_layout(output_root)
    stage_result = FakeStageResult()
    return PreprocessingGraphWorkflowGraphExportResult(
        computation=computation,
        output_layout=layout,
        graph_nodes_csv_path=layout.graph_nodes_csv_path,
        graph_edges_csv_path=layout.graph_edges_csv_path,
        graph_json_path=layout.graph_json_path,
        mapping_result=build_preprocessing_graph_export_mapping(
            computation.contacts_result
        ),
        nodes_csv_write_result=stage_result,
        edges_csv_write_result=stage_result,
        csv_validation_result=stage_result,
        graph_json_write_result=stage_result,
        graph_export_bundle_result=stage_result,
    )


def _install_synthetic_preprocessing_runtime(
    monkeypatch: pytest.MonkeyPatch,
    conditions: tuple[str, ...],
) -> None:
    def fake_load(
        manifest_path: str | Path,
        *,
        expected_condition_names: tuple[str, ...],
    ) -> PreprocessingGraphWorkflowRuntimeLoadingResult:
        assert expected_condition_names == conditions
        return _runtime_loading_result(Path(manifest_path), conditions)

    def fake_compute(
        runtime_loading: PreprocessingGraphWorkflowRuntimeLoadingResult,
        *,
        include_rg: bool,
        include_contacts: bool,
        frame_sampling: PreprocessingFrameSamplingOptions,
        contact_options: PreprocessingContactDetectionOptions,
        contact_computation_limits: object | None = None,
        progress_callback: object | None = None,
    ) -> PreprocessingGraphWorkflowComputationResult:
        assert include_rg is True
        assert include_contacts is True
        assert contact_options.contact_selection == "protein"
        return PreprocessingGraphWorkflowComputationResult(
            runtime_loading=runtime_loading,
            condition_names=conditions,
            include_rg=include_rg,
            include_contacts=include_contacts,
            frame_sampling=frame_sampling,
            contact_detection_options=contact_options,
            rg_result=_rg_result(conditions),
            contacts_result=_contacts_result(conditions),
        )

    monkeypatch.setattr(
        cli,
        "load_preprocessing_graph_workflow_condition_runtimes",
        fake_load,
    )
    monkeypatch.setattr(
        cli,
        "compute_preprocessing_graph_workflow_rg_contacts",
        fake_compute,
    )


def _run_preprocessing_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output_root: Path,
    conditions: tuple[str, ...],
    *extra_args: str,
) -> dict[str, Any]:
    manifest_path = output_root.parent / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("conditions: []\n", encoding="utf-8")
    _install_synthetic_preprocessing_runtime(monkeypatch, conditions)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        "preprocessing",
        "run-graph-export",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_root),
        *(
            item
            for condition in conditions
            for item in ("--expected-condition", condition)
        ),
        "--contact-selection",
        "protein",
        "--skip-diagnostics",
        *extra_args,
    )

    assert stderr == ""
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def _analyze(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    root: Path,
    conditions: tuple[str, ...],
    *extra_args: str,
) -> dict[str, Any]:
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        "analyze",
        "--input",
        str(root),
        "--output",
        str(root),
        *(item for condition in conditions for item in ("--condition", condition)),
        *extra_args,
    )
    assert stderr == ""
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def _stage20_names(condition: str) -> set[str]:
    return {
        f"residue_table_{condition}.csv",
        f"protein_contact_edges_undirected_{condition}.csv",
        f"contacts_perframe_{condition}.csv",
    }


def test_public_analysis_input_export_contract_is_json_safe(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(tmp_path / "out", ("normal",)),
    )

    assert PreprocessingGraphWorkflowAnalysisInputExportIssue is not None
    assert PreprocessingGraphWorkflowAnalysisInputExportResult is not None
    assert result.passed
    json.dumps(result.to_dict(), sort_keys=True)


def test_preprocessing_cli_exports_one_condition_and_analyze_accepts_same_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "missing" / "out"
    payload = _run_preprocessing_cli(
        monkeypatch,
        capsys,
        output_root,
        ("normal",),
        "--export-analysis-inputs",
    )

    assert payload["passed"] is True
    assert payload["analysis_input_export"]["requested"] is True
    assert payload["analysis_input_export"]["passed"] is True
    expected = _stage20_names("normal") | {
        EDGE_SEMANTICS_FILENAME,
        MANIA_MANIFEST_FILENAME,
        MANIA_RESIDUE_LIBRARY_FILENAME,
    }
    assert expected.issubset({path.name for path in output_root.iterdir()})
    assert (output_root / "graph" / "graph.json").is_file()
    assert _analyze(monkeypatch, capsys, output_root, ("normal",))["passed"] is True


def test_preprocessing_cli_exports_two_conditions_and_pca_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "out"
    output_root.mkdir()
    sentinel = output_root / "unrelated.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    payload = _run_preprocessing_cli(
        monkeypatch,
        capsys,
        output_root,
        ("normal", "tumor"),
        "--export-analysis-inputs",
    )

    assert payload["passed"] is True
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert (_stage20_names("normal") | _stage20_names("tumor")).issubset(
        {path.name for path in output_root.iterdir()}
    )
    manifest = _read_json(output_root / MANIA_MANIFEST_FILENAME)
    assert manifest["conditions"] == ["normal", "tumor"]
    produced = manifest["produced_artifacts"]
    assert [item["condition"] for item in produced if "condition" in item] == [
        "normal",
        "tumor",
        "normal",
        "tumor",
        "normal",
        "tumor",
    ]
    assert _analyze(
        monkeypatch,
        capsys,
        output_root,
        ("normal", "tumor"),
        "--enable-pca",
    )["passed"] is True
    pca_cluster = _analyze(
        monkeypatch,
        capsys,
        output_root,
        ("normal", "tumor"),
        "--enable-pca",
        "--clustering-basis",
        "pca",
        "--pca-components-for-clustering",
        "1",
    )
    assert pca_cluster["passed"] is True
    assert pca_cluster["clustering"]["basis"] == "pca"


def test_safe_condition_filename_export_preserves_identity_and_analyzes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "out"

    _run_preprocessing_cli(
        monkeypatch,
        capsys,
        output_root,
        ("treated group",),
        "--export-analysis-inputs",
    )

    assert (output_root / "residue_table_treated_group.csv").is_file()
    assert (
        output_root / "protein_contact_edges_undirected_treated_group.csv"
    ).is_file()
    assert (output_root / "contacts_perframe_treated_group.csv").is_file()
    _, residue_rows = _read_csv(output_root / "residue_table_treated_group.csv")
    _, contact_rows = _read_csv(output_root / "contacts_perframe_treated_group.csv")
    assert {row["condition"] for row in residue_rows} == {"treated group"}
    assert {row["condition"] for row in contact_rows} == {"treated group"}
    manifest = _read_json(output_root / MANIA_MANIFEST_FILENAME)
    filenames = {
        item["filename"]
        for item in manifest["produced_artifacts"]
        if item.get("condition") == "treated group"
    }
    assert filenames == {
        "residue_table_treated_group.csv",
        "protein_contact_edges_undirected_treated_group.csv",
        "contacts_perframe_treated_group.csv",
    }
    assert _analyze(
        monkeypatch,
        capsys,
        output_root,
        ("treated group",),
    )["passed"] is True


def test_default_preprocessing_does_not_write_analysis_input_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "out"

    payload = _run_preprocessing_cli(
        monkeypatch,
        capsys,
        output_root,
        ("normal",),
    )

    assert payload["analysis_input_export"] == {
        "passed": True,
        "requested": False,
        "skipped": True,
        "stage": "analysis_input_export",
    }
    assert not (output_root / "residue_table_normal.csv").exists()
    assert not (output_root / "contacts_perframe_normal.csv").exists()
    assert (output_root / "graph" / "graph.json").is_file()


def test_legacy_contacts_perframe_and_analysis_inputs_coexist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "out"

    _run_preprocessing_cli(
        monkeypatch,
        capsys,
        output_root,
        ("normal",),
        "--export-analysis-inputs",
        "--export-contacts-perframe",
    )

    legacy = output_root / "contacts" / "contacts_perframe.csv"
    analysis_ready = output_root / "contacts_perframe_normal.csv"
    assert legacy.is_file()
    assert analysis_ready.is_file()
    legacy_header, _ = _read_csv(legacy)
    analysis_header, _ = _read_csv(analysis_ready)
    assert legacy_header != analysis_header
    assert analysis_header == PROTEIN_CONTACT_PERFRAME_COLUMNS


def test_analysis_input_export_writer_failures_stop_later_writers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def residue_failure(mapping_result: object, output_dir: str | Path) -> object:
        calls.append("residue")
        return FakeWriteResult(False, "residue")

    def protein_writer(contacts_result: object, output_dir: str | Path) -> object:
        calls.append("protein")
        return FakeWriteResult(True, "protein")

    def manifest_writer(
        mapping_result: object,
        output_dir: str | Path,
        *,
        residue_tables: object | None = None,
        protein_contacts: object | None = None,
    ) -> object:
        calls.append("manifest")
        return FakeWriteResult(True, "manifest")

    monkeypatch.setattr(workflow, "_residue_tables_csv_writer", lambda: residue_failure)
    monkeypatch.setattr(
        workflow,
        "_protein_contact_artifacts_csv_writer",
        lambda: protein_writer,
    )
    monkeypatch.setattr(workflow, "_manifest_artifacts_writer", lambda: manifest_writer)

    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(tmp_path / "out", ("normal",)),
    )

    assert not result.passed
    assert calls == ["residue"]
    assert result.to_dict()["manifests"] is None
    assert result.issues[0].kind == "residue_table_export_failed"


def test_analysis_input_export_protein_failure_reports_residue_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    real_residue_writer = workflow._residue_tables_csv_writer()

    def residue_writer(mapping_result: object, output_dir: str | Path) -> object:
        calls.append("residue")
        return real_residue_writer(mapping_result, output_dir)

    def protein_failure(contacts_result: object, output_dir: str | Path) -> object:
        calls.append("protein")
        return FakeWriteResult(False, "protein")

    def manifest_writer(
        mapping_result: object,
        output_dir: str | Path,
        *,
        residue_tables: object | None = None,
        protein_contacts: object | None = None,
    ) -> object:
        calls.append("manifest")
        return FakeWriteResult(True, "manifest")

    monkeypatch.setattr(workflow, "_residue_tables_csv_writer", lambda: residue_writer)
    monkeypatch.setattr(
        workflow,
        "_protein_contact_artifacts_csv_writer",
        lambda: protein_failure,
    )
    monkeypatch.setattr(workflow, "_manifest_artifacts_writer", lambda: manifest_writer)

    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(tmp_path / "out", ("normal",)),
    )
    payload = result.to_dict()

    assert not result.passed
    assert calls == ["residue", "protein"]
    assert (tmp_path / "out" / "residue_table_normal.csv").is_file()
    assert payload["residue_tables"]["passed"] is True
    assert payload["manifests"] is None
    assert result.issues[0].kind == "protein_contact_export_failed"


def test_analysis_input_export_manifest_failure_reports_csv_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    real_residue_writer = workflow._residue_tables_csv_writer()
    real_protein_writer = workflow._protein_contact_artifacts_csv_writer()

    def residue_writer(mapping_result: object, output_dir: str | Path) -> object:
        calls.append("residue")
        return real_residue_writer(mapping_result, output_dir)

    def protein_writer(contacts_result: object, output_dir: str | Path) -> object:
        calls.append("protein")
        return real_protein_writer(contacts_result, output_dir)

    def manifest_failure(
        mapping_result: object,
        output_dir: str | Path,
        *,
        residue_tables: object | None = None,
        protein_contacts: object | None = None,
    ) -> object:
        calls.append("manifest")
        assert residue_tables is not None
        assert protein_contacts is not None
        return FakeWriteResult(False, "manifest")

    monkeypatch.setattr(workflow, "_residue_tables_csv_writer", lambda: residue_writer)
    monkeypatch.setattr(
        workflow,
        "_protein_contact_artifacts_csv_writer",
        lambda: protein_writer,
    )
    monkeypatch.setattr(
        workflow,
        "_manifest_artifacts_writer",
        lambda: manifest_failure,
    )

    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(tmp_path / "out", ("normal",)),
    )
    payload = result.to_dict()

    assert not result.passed
    assert calls == ["residue", "protein", "manifest"]
    assert (tmp_path / "out" / "residue_table_normal.csv").is_file()
    assert (tmp_path / "out" / "contacts_perframe_normal.csv").is_file()
    assert payload["protein_contacts"]["passed"] is True
    assert payload["manifests"]["passed"] is False
    assert result.issues[0].kind == "manifest_artifact_export_failed"


def test_analysis_input_export_rejects_non_protein_contacts_without_manifest(
    tmp_path: Path,
) -> None:
    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(
            tmp_path / "out",
            ("normal",),
            contact_selection="all",
        ),
    )

    assert not result.passed
    assert result.residue_tables_written
    assert not result.protein_contacts_written
    assert result.manifest_artifacts_result is None
    assert not (tmp_path / "out" / MANIA_MANIFEST_FILENAME).exists()
    assert result.issues[0].kind == "protein_contact_export_failed"


def test_stage20_csv_headers_are_real_writer_schemas(tmp_path: Path) -> None:
    result = export_preprocessing_graph_workflow_analysis_inputs(
        _graph_export_result(tmp_path / "out", ("normal",)),
    )

    assert result.passed
    residue_header, _ = _read_csv(tmp_path / "out" / "residue_table_normal.csv")
    edge_header, _ = _read_csv(
        tmp_path / "out" / "protein_contact_edges_undirected_normal.csv"
    )
    perframe_header, _ = _read_csv(tmp_path / "out" / "contacts_perframe_normal.csv")
    assert residue_header == RESIDUE_TABLE_COLUMNS
    assert edge_header == PROTEIN_CONTACT_EDGE_COLUMNS
    assert perframe_header == PROTEIN_CONTACT_PERFRAME_COLUMNS
