import json
from pathlib import Path

import pytest

from mania.adapters.notebook_export import NotebookExportAdapterError
from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsPipelineResult,
    NotebookExportGraphDiagnosticsWorkflowConfig,
    run_notebook_export_graph_diagnostics_pipeline,
    run_notebook_export_graph_diagnostics_pipeline_from_config,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
CONDITIONS = ("normal", "tumor")


def make_config(
    tmp_path: Path,
    *,
    output_name: str = "mania_output",
    diagnostics_name: str = "diagnostics",
    conditions: tuple[str, ...] | None = CONDITIONS,
    source_dir: Path = NOTEBOOK_FIXTURE_DIR,
) -> NotebookExportGraphDiagnosticsWorkflowConfig:
    return NotebookExportGraphDiagnosticsWorkflowConfig(
        source_dir=source_dir,
        output_dir=tmp_path / output_name,
        diagnostics_output_dir=tmp_path / diagnostics_name,
        conditions=conditions,
        frame_time_ps=100.0,
    )


def test_config_driven_runner_executes_composed_workflow(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    assert isinstance(result, NotebookExportGraphDiagnosticsPipelineResult)
    assert result.conditions == CONDITIONS
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert (tmp_path / "mania_output" / "normal" / "nodes.csv").exists()
    assert (tmp_path / "mania_output" / "normal" / "edges.csv").exists()
    assert (tmp_path / "mania_output" / "tumor" / "nodes.csv").exists()
    assert (tmp_path / "mania_output" / "tumor" / "edges.csv").exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics.json"
    ).exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics_summary.json"
    ).exists()
    assert (tmp_path / "diagnostics" / "normal" / "graph_diagnostics.json").exists()
    assert (tmp_path / "diagnostics" / "tumor" / "graph_diagnostics.json").exists()
    assert result.passed is False


def test_config_driven_runner_supports_inferred_conditions(tmp_path: Path) -> None:
    config = make_config(tmp_path, conditions=None)

    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    assert result.conditions == CONDITIONS
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert result.diagnostics_result.summary_path is not None
    assert result.diagnostics_result.summary_path.exists()


def test_config_driven_runner_supports_single_condition(tmp_path: Path) -> None:
    config = make_config(tmp_path, conditions=("normal",))

    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    assert result.conditions == ("normal",)
    assert (tmp_path / "mania_output" / "normal").is_dir()
    assert not (tmp_path / "mania_output" / "tumor").exists()
    assert (tmp_path / "diagnostics" / "normal" / "graph_diagnostics.json").exists()
    assert not (tmp_path / "diagnostics" / "tumor").exists()


def test_config_normalization_flows_into_runner(tmp_path: Path) -> None:
    config = make_config(tmp_path, conditions=(" normal ", " tumor "))

    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    assert result.conditions == CONDITIONS
    assert result.diagnostics_result.conditions == CONDITIONS


def test_config_driven_runner_invalid_input_type_raises() -> None:
    with pytest.raises(TypeError):
        run_notebook_export_graph_diagnostics_pipeline_from_config(
            object()  # type: ignore[arg-type]
        )


def test_config_driven_runner_fatal_workflow_error_propagates(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path, source_dir=tmp_path / "missing")

    with pytest.raises(NotebookExportAdapterError):
        run_notebook_export_graph_diagnostics_pipeline_from_config(config)


def test_config_driven_runner_result_to_dict_is_json_serializable(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)

    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    json.dumps(result.to_dict())


def test_config_driven_runner_matches_direct_workflow_main_fields(
    tmp_path: Path,
) -> None:
    config_from_runner = make_config(
        tmp_path,
        output_name="runner_output",
        diagnostics_name="runner_diagnostics",
    )
    config_direct = make_config(
        tmp_path,
        output_name="direct_output",
        diagnostics_name="direct_diagnostics",
    )

    result_from_config = run_notebook_export_graph_diagnostics_pipeline_from_config(
        config_from_runner
    )
    result_direct = run_notebook_export_graph_diagnostics_pipeline(
        **config_direct.to_pipeline_kwargs()
    )

    assert result_from_config.conditions == result_direct.conditions
    assert result_from_config.passed == result_direct.passed
    assert result_from_config.export_result.written_paths
    assert result_direct.export_result.written_paths
    assert result_from_config.diagnostics_result.written_paths
    assert result_direct.diagnostics_result.written_paths
