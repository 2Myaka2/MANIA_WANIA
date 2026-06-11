import json
from pathlib import Path

import pytest

from mania.adapters.notebook_export import NotebookExportAdapterError
from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsPipelineResult,
    run_notebook_export_graph_diagnostics_pipeline,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
CONDITIONS = ("normal", "tumor")
CONDITION_ARTIFACTS = (
    "rg_timeseries.csv",
    "centrality.csv",
    "communities.csv",
    "nodes.csv",
    "edges.csv",
    "graph.json",
)
DIAGNOSTICS_ARTIFACTS = (
    "graph_diagnostics.json",
    "graph_qc.json",
    "graph_topology_metrics.json",
    "graph_topology_consistency.json",
)


def expected_backend_paths(output_dir: Path) -> set[Path]:
    return {
        output_dir / "run_meta.json",
        *(
            output_dir / condition / artifact
            for condition in CONDITIONS
            for artifact in CONDITION_ARTIFACTS
        ),
    }


def expected_diagnostics_paths(diagnostics_output_dir: Path) -> set[Path]:
    return {
        diagnostics_output_dir / "multi_condition_graph_diagnostics.json",
        diagnostics_output_dir / "multi_condition_graph_diagnostics_summary.json",
        *(
            diagnostics_output_dir / condition / artifact
            for condition in CONDITIONS
            for artifact in DIAGNOSTICS_ARTIFACTS
        ),
    }


def test_composed_pipeline_runs_export_and_diagnostics(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    diagnostics_output_dir = tmp_path / "diagnostics"

    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        diagnostics_output_dir=diagnostics_output_dir,
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    assert isinstance(result, NotebookExportGraphDiagnosticsPipelineResult)
    assert result.conditions == CONDITIONS
    assert result.export_result.output_dir == output_dir
    assert result.diagnostics_result.diagnostics_output_dir == diagnostics_output_dir
    assert result.export_result.written_paths
    assert all(path.exists() for path in result.export_result.written_paths)
    assert result.diagnostics_result.written_paths
    assert all(path.exists() for path in result.diagnostics_result.written_paths)
    assert result.diagnostics_result.summary_path is not None
    assert result.diagnostics_result.summary_path.exists()
    assert result.passed is False

    assert (output_dir / "run_meta.json").exists()
    assert (output_dir / "normal" / "nodes.csv").exists()
    assert (output_dir / "normal" / "edges.csv").exists()
    assert (output_dir / "tumor" / "nodes.csv").exists()
    assert (output_dir / "tumor" / "edges.csv").exists()
    assert (diagnostics_output_dir / "multi_condition_graph_diagnostics.json").exists()
    assert (
        diagnostics_output_dir / "multi_condition_graph_diagnostics_summary.json"
    ).exists()
    assert (diagnostics_output_dir / "normal" / "graph_diagnostics.json").exists()
    assert (diagnostics_output_dir / "tumor" / "graph_diagnostics.json").exists()


def test_composed_pipeline_can_infer_conditions_by_adapter(tmp_path: Path) -> None:
    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=None,
        frame_time_ps=100.0,
    )

    assert result.conditions == CONDITIONS
    assert result.diagnostics_result.conditions == CONDITIONS


def test_composed_pipeline_explicit_single_condition_works(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"
    diagnostics_output_dir = tmp_path / "diagnostics"

    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        diagnostics_output_dir=diagnostics_output_dir,
        conditions=("normal",),
        frame_time_ps=100.0,
    )

    assert result.conditions == ("normal",)
    assert (output_dir / "normal").is_dir()
    assert not (output_dir / "tumor").exists()
    assert (diagnostics_output_dir / "normal" / "graph_diagnostics.json").exists()
    assert not (diagnostics_output_dir / "tumor").exists()


def test_composed_pipeline_normalizes_condition_whitespace(
    tmp_path: Path,
) -> None:
    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=(" normal ", " tumor "),
        frame_time_ps=100.0,
    )

    assert result.conditions == CONDITIONS
    assert result.diagnostics_result.conditions == CONDITIONS


def test_composed_pipeline_invalid_explicit_condition_propagates(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        run_notebook_export_graph_diagnostics_pipeline(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            conditions=("normal", " normal "),
            frame_time_ps=100.0,
        )


def test_composed_pipeline_missing_source_directory_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    diagnostics_output_dir = tmp_path / "diagnostics"

    with pytest.raises(NotebookExportAdapterError):
        run_notebook_export_graph_diagnostics_pipeline(
            source_dir=tmp_path / "missing",
            output_dir=output_dir,
            diagnostics_output_dir=diagnostics_output_dir,
            conditions=CONDITIONS,
            frame_time_ps=100.0,
        )

    assert not diagnostics_output_dir.exists()
    assert not (output_dir / "run_meta.json").exists()


def test_composed_pipeline_to_dict_is_json_serializable(tmp_path: Path) -> None:
    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    payload = result.to_dict()
    json.dumps(payload)

    assert {
        "conditions",
        "passed",
        "export_result",
        "diagnostics_result",
    }.issubset(payload)


def test_composed_pipeline_writes_no_extra_unrelated_files(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"
    diagnostics_output_dir = tmp_path / "diagnostics"

    run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        diagnostics_output_dir=diagnostics_output_dir,
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    assert not (output_dir / "multi_condition_graph_diagnostics.json").exists()
    assert not (output_dir / "multi_condition_graph_diagnostics_summary.json").exists()
    assert not any(output_dir.glob("*/graph_diagnostics.json"))
    assert not (diagnostics_output_dir / "run_meta.json").exists()
    assert not any(diagnostics_output_dir.glob("*/nodes.csv"))
    assert not any(diagnostics_output_dir.glob("*/edges.csv"))

    backend_paths = {
        path
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    diagnostics_paths = {
        path
        for path in diagnostics_output_dir.rglob("*")
        if path.is_file()
    }
    assert backend_paths == expected_backend_paths(output_dir)
    assert diagnostics_paths == expected_diagnostics_paths(diagnostics_output_dir)


def test_composed_pipeline_accepts_default_diagnostics_parameters(
    tmp_path: Path,
) -> None:
    result = run_notebook_export_graph_diagnostics_pipeline(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    assert result.diagnostics_result.conditions == CONDITIONS
    assert result.passed is False
