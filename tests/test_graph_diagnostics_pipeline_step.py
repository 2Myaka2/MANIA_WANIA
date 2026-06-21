import csv
import json
from pathlib import Path

import pytest

from mania.analysis.graph_diagnostics import GraphDiagnosticsError
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS
from mania.pipeline_steps import (
    GraphDiagnosticsPipelineStepResult,
    run_graph_diagnostics_pipeline_step,
)

FIXTURE_ROOT = Path("tests/fixtures/expected_contract_subset_tiny")


def write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def node_row(
    resid: str,
    *,
    condition: str = "normal",
    degree: str = "1",
    strength: str = "0.5",
) -> dict[str, str]:
    row = {column: "" for column in NODE_COLUMNS}
    row.update(
        {
            "resid": resid,
            "resname": "ALA",
            "region": "TM1",
            "condition": condition,
            "degree": degree,
            "strength": strength,
        }
    )
    return row


def edge_row(
    source: str,
    target: str,
    *,
    condition: str = "normal",
    contact_freq: str = "0.5",
) -> dict[str, str]:
    row = {column: "" for column in EDGE_COLUMNS}
    row.update(
        {
            "resid_i": source,
            "resid_j": target,
            "edge_type": "contact",
            "condition": condition,
            "contact_freq": contact_freq,
            "mean_dist_A": "7.25",
        }
    )
    return row


def write_condition_dir(
    output_root: Path,
    *,
    condition: str = "normal",
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> Path:
    condition_dir = output_root / condition
    condition_dir.mkdir()
    write_csv(condition_dir / "nodes.csv", NODE_COLUMNS, nodes)
    write_csv(condition_dir / "edges.csv", EDGE_COLUMNS, edges)
    return condition_dir


def write_run_meta(output_root: Path, conditions: list[str]) -> None:
    (output_root / "run_meta.json").write_text(
        json.dumps({"schema_version": "0.1", "conditions": conditions}),
        encoding="utf-8",
    )


def test_pipeline_step_runs_on_expected_fixture(tmp_path: Path) -> None:
    result = run_graph_diagnostics_pipeline_step(
        output_root=FIXTURE_ROOT,
        diagnostics_output_dir=tmp_path / "diagnostics",
    )

    assert isinstance(result, GraphDiagnosticsPipelineStepResult)
    assert result.output_root == FIXTURE_ROOT
    assert result.diagnostics_output_dir == tmp_path / "diagnostics"
    assert result.conditions == ("normal", "tumor")
    assert result.passed is False
    assert result.written_paths
    assert all(path.exists() for path in result.written_paths)
    assert result.summary_path is not None
    assert result.summary_path.name == "multi_condition_graph_diagnostics_summary.json"
    assert result.summary_path.exists()


def test_pipeline_step_supports_explicit_conditions(tmp_path: Path) -> None:
    result = run_graph_diagnostics_pipeline_step(
        output_root=FIXTURE_ROOT,
        diagnostics_output_dir=tmp_path / "diagnostics",
        conditions=("normal",),
    )

    assert result.conditions == ("normal",)
    assert (tmp_path / "diagnostics" / "normal" / "graph_diagnostics.json").exists()
    assert not (tmp_path / "diagnostics" / "tumor").exists()


def test_pipeline_step_synthetic_passing_output_returns_passed_true(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "mania_output"
    output_root.mkdir()
    write_run_meta(output_root, ["normal"])
    write_condition_dir(
        output_root,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    result = run_graph_diagnostics_pipeline_step(
        output_root=output_root,
        diagnostics_output_dir=tmp_path / "diagnostics",
    )

    assert result.conditions == ("normal",)
    assert result.passed is True


def test_pipeline_step_normal_diagnostic_failure_does_not_raise(
    tmp_path: Path,
) -> None:
    result = run_graph_diagnostics_pipeline_step(
        output_root=FIXTURE_ROOT,
        diagnostics_output_dir=tmp_path / "diagnostics",
    )

    assert result.passed is False


def test_pipeline_step_fatal_diagnostics_error_propagates(tmp_path: Path) -> None:
    output_root = tmp_path / "mania_output"
    output_root.mkdir()
    write_run_meta(output_root, ["normal"])

    with pytest.raises(GraphDiagnosticsError):
        run_graph_diagnostics_pipeline_step(
            output_root=output_root,
            diagnostics_output_dir=tmp_path / "diagnostics",
        )


def test_pipeline_step_to_dict_is_json_serializable(tmp_path: Path) -> None:
    result = run_graph_diagnostics_pipeline_step(
        output_root=FIXTURE_ROOT,
        diagnostics_output_dir=tmp_path / "diagnostics",
    )

    payload = result.to_dict()
    json.dumps(payload)

    assert {
        "output_root",
        "diagnostics_output_dir",
        "conditions",
        "passed",
        "written_paths",
        "summary_path",
    }.issubset(payload)
    assert isinstance(payload["output_root"], str)
    assert isinstance(payload["diagnostics_output_dir"], str)
    assert payload["conditions"] == ["normal", "tumor"]
    assert all(isinstance(path, str) for path in payload["written_paths"])
    assert isinstance(payload["summary_path"], str)


def test_pipeline_step_writes_only_report_bundle_files(tmp_path: Path) -> None:
    diagnostics_output_dir = tmp_path / "diagnostics"

    run_graph_diagnostics_pipeline_step(
        output_root=FIXTURE_ROOT,
        diagnostics_output_dir=diagnostics_output_dir,
    )

    written_relative_paths = {
        path.relative_to(diagnostics_output_dir)
        for path in diagnostics_output_dir.rglob("*")
        if path.is_file()
    }
    assert written_relative_paths == {
        Path("multi_condition_graph_diagnostics.json"),
        Path("multi_condition_graph_diagnostics_summary.json"),
        Path("normal/graph_diagnostics.json"),
        Path("normal/graph_qc.json"),
        Path("normal/graph_topology_metrics.json"),
        Path("normal/graph_topology_consistency.json"),
        Path("tumor/graph_diagnostics.json"),
        Path("tumor/graph_qc.json"),
        Path("tumor/graph_topology_metrics.json"),
        Path("tumor/graph_topology_consistency.json"),
    }
