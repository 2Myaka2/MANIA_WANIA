from pathlib import Path

import pytest
from pydantic import ValidationError

from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsWorkflowConfig,
    run_notebook_export_graph_diagnostics_pipeline,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
EXPECTED_PIPELINE_KWARGS = {
    "source_dir",
    "output_dir",
    "diagnostics_output_dir",
    "conditions",
    "frame_time_ps",
    "abs_tol",
    "weight_column",
    "degree_column",
    "strength_column",
}


def test_minimal_valid_workflow_config_works(tmp_path: Path) -> None:
    config = NotebookExportGraphDiagnosticsWorkflowConfig(
        source_dir="notebook_export",
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        frame_time_ps=100.0,
    )

    assert config.source_dir == Path("notebook_export")
    assert config.output_dir == tmp_path / "mania_output"
    assert config.diagnostics_output_dir == tmp_path / "diagnostics"
    assert config.conditions is None
    assert config.abs_tol == 1e-6
    assert config.weight_column == "contact_freq"
    assert config.degree_column == "degree"
    assert config.strength_column == "strength"


def test_full_valid_workflow_config_works(tmp_path: Path) -> None:
    config = NotebookExportGraphDiagnosticsWorkflowConfig(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=(" normal ", " tumor "),
        frame_time_ps=100.0,
        abs_tol=1e-5,
        weight_column=" mean_dist_A ",
        degree_column=" exported_degree ",
        strength_column=" exported_strength ",
    )

    assert config.conditions == ("normal", "tumor")
    assert config.abs_tol == 1e-5
    assert config.weight_column == "mean_dist_A"
    assert config.degree_column == "exported_degree"
    assert config.strength_column == "exported_strength"
    assert EXPECTED_PIPELINE_KWARGS.issubset(config.to_pipeline_kwargs())


def test_workflow_config_strips_condition_whitespace(tmp_path: Path) -> None:
    config = NotebookExportGraphDiagnosticsWorkflowConfig(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=[" normal ", " tumor "],
        frame_time_ps=100.0,
    )

    assert config.conditions == ("normal", "tumor")


def test_workflow_config_plain_string_conditions_fail(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            conditions="normal",
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize("conditions", (["normal", ""], ["normal", " "]))
def test_workflow_config_empty_condition_fails(
    tmp_path: Path,
    conditions: list[str],
) -> None:
    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            conditions=conditions,
            frame_time_ps=100.0,
        )


def test_workflow_config_duplicate_condition_fails(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            conditions=["normal", " normal "],
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize("frame_time_ps", (0, -1.0, float("nan"), float("inf")))
def test_workflow_config_invalid_frame_time_ps_fails(
    tmp_path: Path,
    frame_time_ps: float,
) -> None:
    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            frame_time_ps=frame_time_ps,
        )


@pytest.mark.parametrize("abs_tol", (-1.0, float("nan"), float("inf")))
def test_workflow_config_invalid_abs_tol_fails(
    tmp_path: Path,
    abs_tol: float,
) -> None:
    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            diagnostics_output_dir=tmp_path / "diagnostics",
            frame_time_ps=100.0,
            abs_tol=abs_tol,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("weight_column", ""),
        ("weight_column", " "),
        ("degree_column", ""),
        ("degree_column", " "),
        ("strength_column", ""),
        ("strength_column", " "),
    ),
)
def test_workflow_config_empty_column_names_fail(
    tmp_path: Path,
    field_name: str,
    value: str,
) -> None:
    kwargs = {
        "source_dir": NOTEBOOK_FIXTURE_DIR,
        "output_dir": tmp_path / "mania_output",
        "diagnostics_output_dir": tmp_path / "diagnostics",
        "frame_time_ps": 100.0,
        field_name: value,
    }

    with pytest.raises(ValidationError):
        NotebookExportGraphDiagnosticsWorkflowConfig(**kwargs)


def test_workflow_config_to_pipeline_kwargs_can_call_composed_workflow(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"
    diagnostics_output_dir = tmp_path / "diagnostics"
    config = NotebookExportGraphDiagnosticsWorkflowConfig(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        diagnostics_output_dir=diagnostics_output_dir,
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    kwargs = config.to_pipeline_kwargs()
    result = run_notebook_export_graph_diagnostics_pipeline(**kwargs)

    assert result.conditions == ("normal", "tumor")
    assert result.passed is False
    assert (output_dir / "run_meta.json").exists()
    assert (output_dir / "normal" / "nodes.csv").exists()
    assert (output_dir / "tumor" / "edges.csv").exists()
    assert result.diagnostics_result.summary_path is not None
    assert result.diagnostics_result.summary_path.exists()
