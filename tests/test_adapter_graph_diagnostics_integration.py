import json
from pathlib import Path

import pytest

from mania.adapters.notebook_export import export_notebook_contract_subset
from mania.analysis.graph_diagnostics import (
    GraphDiagnosticsError,
    run_and_write_output_graph_diagnostics,
    run_and_write_output_graph_diagnostics_report_bundle,
    run_multi_condition_graph_diagnostics,
    run_output_graph_diagnostics,
    write_multi_condition_graph_diagnostics_bundle,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
CONDITIONS = ("normal", "tumor")


def _export_tiny_contract_subset(
    output_root: Path,
    *,
    conditions: tuple[str, ...] = CONDITIONS,
) -> None:
    export_notebook_contract_subset(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_root,
        conditions=conditions,
        frame_time_ps=100.0,
    )


def _run_adapter_graph_diagnostics(tmp_path: Path):
    output_root = tmp_path / "mania_output"
    _export_tiny_contract_subset(output_root)
    return run_multi_condition_graph_diagnostics(
        output_root,
        conditions=CONDITIONS,
    )


def test_adapter_output_can_run_multi_condition_graph_diagnostics(
    tmp_path: Path,
) -> None:
    diagnostics = _run_adapter_graph_diagnostics(tmp_path)

    assert diagnostics.conditions == CONDITIONS
    assert set(diagnostics.condition_diagnostics) == {"normal", "tumor"}

    normal = diagnostics.condition_diagnostics["normal"]
    tumor = diagnostics.condition_diagnostics["tumor"]
    assert normal.graph.n_nodes == 2
    assert normal.graph.n_edges == 1
    assert tumor.graph.n_nodes == 2
    assert tumor.graph.n_edges == 1
    assert normal.passed_basic_qc is True
    assert tumor.passed_basic_qc is True
    assert normal.passed_topology_consistency is False
    assert tumor.passed_topology_consistency is False
    assert diagnostics.passed is False
    assert diagnostics.failed_conditions == CONDITIONS
    assert diagnostics.passed_conditions == ()


def test_adapter_output_diagnostics_bundle_can_be_written(tmp_path: Path) -> None:
    diagnostics = _run_adapter_graph_diagnostics(tmp_path)

    paths = write_multi_condition_graph_diagnostics_bundle(
        diagnostics,
        tmp_path / "diagnostics",
    )

    expected_paths = (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics.json",
        tmp_path / "diagnostics" / "normal" / "graph_diagnostics.json",
        tmp_path / "diagnostics" / "normal" / "graph_qc.json",
        tmp_path / "diagnostics" / "normal" / "graph_topology_metrics.json",
        tmp_path / "diagnostics" / "normal" / "graph_topology_consistency.json",
        tmp_path / "diagnostics" / "tumor" / "graph_diagnostics.json",
        tmp_path / "diagnostics" / "tumor" / "graph_qc.json",
        tmp_path / "diagnostics" / "tumor" / "graph_topology_metrics.json",
        tmp_path / "diagnostics" / "tumor" / "graph_topology_consistency.json",
    )

    assert paths
    assert all(path.exists() for path in paths)
    for path in expected_paths:
        assert path.exists()
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))


def test_adapter_output_can_run_and_write_output_graph_diagnostics(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "mania_output"
    _export_tiny_contract_subset(output_root)

    result = run_and_write_output_graph_diagnostics(
        output_root,
        tmp_path / "diagnostics",
    )

    assert result.diagnostics.conditions == CONDITIONS
    assert result.passed is False
    assert result.diagnostics.failed_conditions == CONDITIONS
    assert all(path.exists() for path in result.written_paths)
    assert result.diagnostics.condition_diagnostics[
        "normal"
    ].topology_consistency.mismatches
    assert result.diagnostics.condition_diagnostics[
        "tumor"
    ].topology_consistency.mismatches


def test_adapter_output_can_run_and_write_graph_diagnostics_report_bundle(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "mania_output"
    _export_tiny_contract_subset(output_root)

    result = run_and_write_output_graph_diagnostics_report_bundle(
        output_root,
        tmp_path / "diagnostics",
    )

    assert result.diagnostics.conditions == CONDITIONS
    assert result.summary.conditions == CONDITIONS
    assert result.passed is False
    assert result.summary.failed_conditions == CONDITIONS
    assert all(path.exists() for path in result.written_paths)
    assert result.diagnostics.condition_diagnostics[
        "normal"
    ].topology_consistency.mismatches
    assert result.diagnostics.condition_diagnostics[
        "tumor"
    ].topology_consistency.mismatches


def test_adapter_output_diagnostics_to_dict_is_json_serializable(
    tmp_path: Path,
) -> None:
    diagnostics = _run_adapter_graph_diagnostics(tmp_path)

    payload = diagnostics.to_dict()
    json.dumps(payload)

    assert {
        "conditions",
        "passed",
        "failed_conditions",
        "condition_diagnostics",
    }.issubset(payload)
    assert payload["conditions"] == ["normal", "tumor"]
    assert payload["failed_conditions"] == ["normal", "tumor"]


def test_adapter_output_can_run_graph_diagnostics_from_run_meta(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "mania_output"
    _export_tiny_contract_subset(output_root)

    diagnostics = run_output_graph_diagnostics(output_root)

    assert diagnostics.conditions == CONDITIONS
    assert diagnostics.passed is False
    assert diagnostics.failed_conditions == CONDITIONS
    assert diagnostics.condition_diagnostics["normal"].passed_basic_qc is True
    assert diagnostics.condition_diagnostics["tumor"].passed_basic_qc is True


def test_missing_generated_condition_directory_raises_diagnostics_error(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "mania_output"
    _export_tiny_contract_subset(output_root, conditions=("normal",))

    with pytest.raises(GraphDiagnosticsError):
        run_multi_condition_graph_diagnostics(
            output_root,
            conditions=CONDITIONS,
        )
