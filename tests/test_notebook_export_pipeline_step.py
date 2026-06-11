import json
from pathlib import Path

import pytest

from mania.adapters.notebook_export import NotebookExportAdapterError
from mania.pipeline_steps import (
    NotebookContractExportPipelineStepResult,
    run_graph_diagnostics_pipeline_step,
    run_notebook_contract_export_pipeline_step,
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


def expected_output_paths(output_dir: Path) -> tuple[Path, ...]:
    return (
        output_dir / "run_meta.json",
        *(
            output_dir / condition / artifact
            for condition in CONDITIONS
            for artifact in CONDITION_ARTIFACTS
        ),
    )


def assert_expected_output_files_exist(output_dir: Path) -> None:
    for path in expected_output_paths(output_dir):
        assert path.exists()


def test_pipeline_step_exports_notebook_contract_subset(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    assert isinstance(result, NotebookContractExportPipelineStepResult)
    assert result.source_dir == NOTEBOOK_FIXTURE_DIR
    assert result.output_dir == output_dir
    assert result.conditions == CONDITIONS
    assert result.run_meta_path == output_dir / "run_meta.json"
    assert result.run_meta_path.exists()
    assert result.written_paths
    assert all(path.exists() for path in result.written_paths)
    assert_expected_output_files_exist(output_dir)


def test_pipeline_step_can_infer_conditions_by_adapter(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        conditions=None,
        frame_time_ps=100.0,
    )

    assert result.conditions == CONDITIONS
    assert_expected_output_files_exist(output_dir)


def test_pipeline_step_explicit_single_condition_works(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        conditions=("normal",),
        frame_time_ps=100.0,
    )

    assert result.conditions == ("normal",)
    for artifact in CONDITION_ARTIFACTS:
        assert (output_dir / "normal" / artifact).exists()
    assert not (output_dir / "tumor").exists()


def test_pipeline_step_strips_condition_whitespace(tmp_path: Path) -> None:
    result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=(" normal ", " tumor "),
        frame_time_ps=100.0,
    )

    assert result.conditions == CONDITIONS


def test_pipeline_step_duplicate_condition_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_notebook_contract_export_pipeline_step(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", " normal "),
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize("conditions", (("normal", ""), ("normal", " ")))
def test_pipeline_step_empty_condition_fails(
    tmp_path: Path,
    conditions: tuple[str, str],
) -> None:
    with pytest.raises(ValueError):
        run_notebook_contract_export_pipeline_step(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=conditions,
            frame_time_ps=100.0,
        )


def test_pipeline_step_string_conditions_input_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_notebook_contract_export_pipeline_step(
            source_dir=NOTEBOOK_FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions="normal",  # type: ignore[arg-type]
            frame_time_ps=100.0,
        )


def test_pipeline_step_missing_source_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        run_notebook_contract_export_pipeline_step(
            source_dir=tmp_path / "missing",
            output_dir=tmp_path / "mania_output",
            conditions=CONDITIONS,
            frame_time_ps=100.0,
        )


def test_pipeline_step_to_dict_is_json_serializable(tmp_path: Path) -> None:
    result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    payload = result.to_dict()
    json.dumps(payload)

    assert {
        "source_dir",
        "output_dir",
        "conditions",
        "written_paths",
        "run_meta_path",
    }.issubset(payload)
    assert isinstance(payload["source_dir"], str)
    assert isinstance(payload["output_dir"], str)
    assert payload["conditions"] == ["normal", "tumor"]
    assert all(isinstance(path, str) for path in payload["written_paths"])
    assert isinstance(payload["run_meta_path"], str)


def test_pipeline_step_result_can_feed_graph_diagnostics_step(
    tmp_path: Path,
) -> None:
    export_result = run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    diagnostics_result = run_graph_diagnostics_pipeline_step(
        output_root=export_result.output_dir,
        diagnostics_output_dir=tmp_path / "diagnostics",
    )

    assert diagnostics_result.conditions == CONDITIONS
    assert diagnostics_result.passed is False
    assert diagnostics_result.summary_path is not None
    assert diagnostics_result.summary_path.exists()


def test_pipeline_step_writes_only_adapter_output_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    run_notebook_contract_export_pipeline_step(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    written_relative_paths = {
        path.relative_to(output_dir)
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    expected_relative_paths = {
        path.relative_to(output_dir) for path in expected_output_paths(output_dir)
    }
    assert written_relative_paths == expected_relative_paths
