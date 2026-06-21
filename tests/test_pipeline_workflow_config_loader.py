import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsWorkflowConfig,
    load_notebook_export_graph_diagnostics_workflow_config,
    run_notebook_export_graph_diagnostics_pipeline_from_config,
    run_notebook_export_graph_diagnostics_pipeline_from_config_file,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
CONDITIONS = ("normal", "tumor")


def write_json_config(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def minimal_config_payload(tmp_path: Path) -> dict[str, object]:
    return {
        "source_dir": "notebook_export",
        "output_dir": str(tmp_path / "mania_output"),
        "diagnostics_output_dir": str(tmp_path / "diagnostics"),
        "frame_time_ps": 100.0,
    }


def workflow_config_payload(tmp_path: Path) -> dict[str, object]:
    return {
        "source_dir": str(NOTEBOOK_FIXTURE_DIR),
        "output_dir": str(tmp_path / "mania_output"),
        "diagnostics_output_dir": str(tmp_path / "diagnostics"),
        "conditions": ["normal", "tumor"],
        "frame_time_ps": 100.0,
    }


def test_workflow_config_loader_loads_minimal_json_config(tmp_path: Path) -> None:
    path = write_json_config(
        tmp_path / "workflow.json",
        minimal_config_payload(tmp_path),
    )

    config = load_notebook_export_graph_diagnostics_workflow_config(path)

    assert isinstance(config, NotebookExportGraphDiagnosticsWorkflowConfig)
    assert config.source_dir == Path("notebook_export")
    assert config.output_dir == tmp_path / "mania_output"
    assert config.diagnostics_output_dir == tmp_path / "diagnostics"
    assert config.conditions is None
    assert config.abs_tol == 1e-6
    assert config.weight_column == "contact_freq"
    assert config.degree_column == "degree"
    assert config.strength_column == "strength"


def test_workflow_config_loader_loads_full_json_config(tmp_path: Path) -> None:
    payload = workflow_config_payload(tmp_path)
    payload.update(
        {
            "conditions": [" normal ", " tumor "],
            "abs_tol": 1e-5,
            "weight_column": " mean_dist_A ",
            "degree_column": " exported_degree ",
            "strength_column": " exported_strength ",
        }
    )
    path = write_json_config(tmp_path / "workflow.json", payload)

    config = load_notebook_export_graph_diagnostics_workflow_config(path)

    assert config.conditions == CONDITIONS
    assert config.abs_tol == 1e-5
    assert config.weight_column == "mean_dist_A"
    assert config.degree_column == "exported_degree"
    assert config.strength_column == "exported_strength"


def test_workflow_config_loader_loads_yaml_config(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(
        "\n".join(
            [
                f"source_dir: {NOTEBOOK_FIXTURE_DIR.as_posix()}",
                f"output_dir: {(tmp_path / 'mania_output').as_posix()}",
                "diagnostics_output_dir: diagnostics",
                "conditions:",
                "  - ' normal '",
                "  - ' tumor '",
                "frame_time_ps: 100.0",
            ]
        ),
        encoding="utf-8",
    )

    config = load_notebook_export_graph_diagnostics_workflow_config(path)

    assert config.source_dir == NOTEBOOK_FIXTURE_DIR
    assert config.conditions == CONDITIONS


def test_workflow_config_loader_unsupported_suffix_fails(tmp_path: Path) -> None:
    path = write_json_config(
        tmp_path / "workflow.txt",
        minimal_config_payload(tmp_path),
    )

    with pytest.raises(ValueError):
        load_notebook_export_graph_diagnostics_workflow_config(path)


def test_workflow_config_loader_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_notebook_export_graph_diagnostics_workflow_config(
            tmp_path / "missing.json"
        )


def test_workflow_config_loader_directory_path_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_notebook_export_graph_diagnostics_workflow_config(tmp_path)


def test_workflow_config_loader_invalid_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_notebook_export_graph_diagnostics_workflow_config(path)


@pytest.mark.parametrize("payload", (["not", "an", "object"], "not-object"))
def test_workflow_config_loader_non_object_payload_fails(
    tmp_path: Path,
    payload: object,
) -> None:
    path = write_json_config(tmp_path / "workflow.json", payload)

    with pytest.raises(ValueError):
        load_notebook_export_graph_diagnostics_workflow_config(path)


def test_workflow_config_loader_model_validation_errors_propagate(
    tmp_path: Path,
) -> None:
    payload = minimal_config_payload(tmp_path)
    payload["frame_time_ps"] = 0
    path = write_json_config(tmp_path / "workflow.json", payload)

    with pytest.raises(ValidationError):
        load_notebook_export_graph_diagnostics_workflow_config(path)


def test_loaded_workflow_config_can_run_workflow(tmp_path: Path) -> None:
    path = write_json_config(
        tmp_path / "workflow.json",
        workflow_config_payload(tmp_path),
    )

    config = load_notebook_export_graph_diagnostics_workflow_config(path)
    result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

    assert result.conditions == CONDITIONS
    assert result.passed is False
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert (tmp_path / "mania_output" / "normal" / "nodes.csv").exists()
    assert result.diagnostics_result.summary_path is not None
    assert result.diagnostics_result.summary_path.exists()


def test_workflow_config_file_runner_works(tmp_path: Path) -> None:
    path = write_json_config(
        tmp_path / "workflow.json",
        workflow_config_payload(tmp_path),
    )

    result = run_notebook_export_graph_diagnostics_pipeline_from_config_file(path)

    assert result.conditions == CONDITIONS
    assert result.passed is False
    assert result.diagnostics_result.summary_path is not None
    assert result.diagnostics_result.summary_path.exists()
