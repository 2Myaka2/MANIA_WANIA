import ast
import csv
import inspect
import json
import math
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
    PreprocessingGraphDiagnosticsCheckResult,
    PreprocessingGraphDiagnosticsRunIssue,
    PreprocessingGraphDiagnosticsRunResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphEdgesCsvWriteIssue,
    PreprocessingGraphEdgesCsvWriteResult,
    PreprocessingGraphExportBundleArtifact,
    PreprocessingGraphExportBundleIssue,
    PreprocessingGraphExportBundleResult,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphJsonWriteIssue,
    PreprocessingGraphJsonWriteResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingGraphNodesCsvWriteIssue,
    PreprocessingGraphNodesCsvWriteResult,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    run_preprocessing_graph_diagnostics,
    trajectory_graph_diagnostics,
    validate_preprocessing_graph_csvs,
    write_preprocessing_graph_edges_csv,
    write_preprocessing_graph_json,
    write_preprocessing_graph_nodes_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "preprocessing" / (
    "trajectory_graph_diagnostics.py"
)
DOC_PATHS = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_export.md",
    REPO_ROOT / "docs" / "adr" / "0001-optional-scientific-dependencies.md",
)


def assert_json_safe(payload: object) -> None:
    json.dumps(payload, allow_nan=False)


def write_csv(
    path: Path,
    header: tuple[str, ...],
    rows: list[list[str]] | None = None,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows or [])


def row_values(columns: tuple[str, ...], values: dict[str, str]) -> list[str]:
    row = {column: "" for column in columns}
    row.update(values)
    return [row[column] for column in columns]


def node_row(**overrides: str) -> list[str]:
    values = {
        "resid": "n1",
        "resname": "ALA",
        "condition": "normal",
    }
    values.update(overrides)
    return row_values(NODE_COLUMNS, values)


def edge_row(**overrides: str) -> list[str]:
    values = {
        "resid_i": "n1",
        "resid_j": "n2",
        "edge_type": "residue_contact",
        "all_edge_types": "residue_contact",
        "n_edge_types": "1",
        "condition": "normal",
    }
    values.update(overrides)
    return row_values(EDGE_COLUMNS, values)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def valid_graph_payload(
    *,
    nodes: list[dict[str, str]] | None = None,
    edges: list[dict[str, str]] | None = None,
    condition: str = "normal",
) -> dict[str, object]:
    graph_nodes = nodes
    if graph_nodes is None:
        first = {column: "" for column in NODE_COLUMNS}
        first.update(
            {
                "id": "n1",
                "resid": "n1",
                "resname": "ALA",
                "condition": condition,
            }
        )
        second = {column: "" for column in NODE_COLUMNS}
        second.update(
            {
                "id": "n2",
                "resid": "n2",
                "resname": "GLY",
                "condition": condition,
            }
        )
        graph_nodes = [first, second]
    graph_edges = edges
    if graph_edges is None:
        edge = {column: "" for column in EDGE_COLUMNS}
        edge.update(
            {
                "source": "n1",
                "target": "n2",
                "resid_i": "n1",
                "resid_j": "n2",
                "edge_type": "residue_contact",
                "all_edge_types": "residue_contact",
                "n_edge_types": "1",
                "condition": condition,
            }
        )
        graph_edges = [edge]
    return {
        "condition": condition,
        "n_nodes": len(graph_nodes),
        "n_edges": len(graph_edges),
        "directed": False,
        "schema_version": "0.1",
        "nodes": graph_nodes,
        "edges": graph_edges,
    }


def write_valid_bundle_files(
    tmp_path: Path,
    *,
    edge_rows: list[list[str]] | None = None,
    graph: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    graph_path = tmp_path / "graph.json"
    write_csv(
        nodes_path,
        NODE_COLUMNS,
        [
            node_row(resid="n1", resname="ALA"),
            node_row(resid="n2", resname="GLY"),
        ],
    )
    write_csv(edges_path, EDGE_COLUMNS, edge_rows or [edge_row()])
    write_json(graph_path, graph or valid_graph_payload())
    return nodes_path, edges_path, graph_path


def writer_generated_bundle_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = PreprocessingGraphNodeMappingRecord(
        node_id="n1",
        condition_name="normal",
        residue_index=1,
        residue_id="1",
        resname="ALA",
    )
    target = PreprocessingGraphNodeMappingRecord(
        node_id="n2",
        condition_name="normal",
        residue_index=2,
        residue_id="2",
        resname="GLY",
    )
    edge = PreprocessingGraphEdgeMappingRecord(
        edge_id="e1",
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        edge_kind="residue_contact",
        contact_frame_count=1,
        total_frame_count=2,
        contact_frequency=0.5,
        minimum_distance=3.0,
        mean_minimum_distance=3.25,
        distance_unit="angstrom",
        atom_filter="heavy",
    )
    mapping = PreprocessingGraphExportMappingResult(
        nodes=(source, target),
        edges=(edge,),
    )
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    graph_path = tmp_path / "graph.json"
    assert write_preprocessing_graph_nodes_csv(mapping, nodes_path).passed is True
    assert write_preprocessing_graph_edges_csv(mapping, edges_path).passed is True
    assert (
        write_preprocessing_graph_json(nodes_path, edges_path, graph_path).passed
        is True
    )
    return nodes_path, edges_path, graph_path


def check_names(result: PreprocessingGraphDiagnosticsRunResult) -> list[str]:
    return [check.name for check in result.checks]


def issue_kinds(result: PreprocessingGraphDiagnosticsRunResult) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_work() -> None:
    assert PreprocessingGraphDiagnosticsRunIssue is not None
    assert PreprocessingGraphDiagnosticsCheckResult is not None
    assert PreprocessingGraphDiagnosticsRunResult is not None
    assert run_preprocessing_graph_diagnostics is not None


def test_existing_stage_14_1_exports_still_work() -> None:
    assert PreprocessingGraphNodeMappingRecord is not None
    assert PreprocessingGraphEdgeMappingRecord is not None
    assert PreprocessingGraphExportMappingIssue is not None
    assert PreprocessingGraphExportMappingResult is not None
    assert build_preprocessing_graph_export_mapping is not None
    assert PreprocessingGraphNodesCsvWriteIssue is not None
    assert PreprocessingGraphNodesCsvWriteResult is not None
    assert write_preprocessing_graph_nodes_csv is not None
    assert PreprocessingGraphEdgesCsvWriteIssue is not None
    assert PreprocessingGraphEdgesCsvWriteResult is not None
    assert write_preprocessing_graph_edges_csv is not None
    assert PreprocessingGraphCsvValidationIssue is not None
    assert PreprocessingGraphCsvValidationResult is not None
    assert validate_preprocessing_graph_csvs is not None
    assert PreprocessingGraphJsonWriteIssue is not None
    assert PreprocessingGraphJsonWriteResult is not None
    assert write_preprocessing_graph_json is not None
    assert PreprocessingGraphExportBundleArtifact is not None
    assert PreprocessingGraphExportBundleIssue is not None
    assert PreprocessingGraphExportBundleResult is not None
    assert build_preprocessing_graph_export_bundle is not None


def test_import_safety_without_scientific_runtime() -> None:
    assert mania.preprocessing is not None


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphDiagnosticsRunIssue(
        kind="bundle_failed",
        message="Bundle failed.",
        check_name="graph_export_bundle",
        field="path",
        value="",
    )

    assert issue.value == ""
    assert_json_safe(issue.to_dict())

    invalid_kwargs = (
        {"kind": "", "message": "message"},
        {"kind": "kind", "message": ""},
        {"kind": "kind", "message": "message", "check_name": ""},
        {"kind": "kind", "message": "message", "field": " "},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphDiagnosticsRunIssue(**kwargs)


def test_check_result_validates_and_serializes() -> None:
    issue = PreprocessingGraphDiagnosticsRunIssue(
        kind="diagnostic_failed",
        message="Diagnostic failed.",
    )
    result = PreprocessingGraphDiagnosticsCheckResult(
        name="graph_structure_diagnostics",
        passed=False,
        summary={"node_count": 2, "edge_count": 1, "passed_basic_qc": False},
        issues=(issue,),
    )

    assert result.to_dict()["issue_count"] == 1
    assert result.to_dict()["name"] == "graph_structure_diagnostics"
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"name": "", "passed": True, "summary": {}},
        {"name": "check", "passed": "yes", "summary": {}},
        {"name": "check", "passed": True, "summary": {"bad": []}},
        {"name": "check", "passed": True, "summary": {"bad": math.nan}},
        {"name": "check", "passed": True, "summary": {}, "issues": ("bad",)},
        {"name": "check", "passed": True, "summary": {}, "issues": []},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphDiagnosticsCheckResult(**kwargs)


def test_run_result_validates_and_serializes() -> None:
    check = PreprocessingGraphDiagnosticsCheckResult(
        name="graph_export_bundle",
        passed=True,
        summary={"node_count": 2},
    )
    result = PreprocessingGraphDiagnosticsRunResult(
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        graph_json_path=Path("graph.json"),
        node_count=2,
        edge_count=1,
        checks=(check,),
    )

    assert result.passed is True
    assert result.check_count == 1
    assert result.failed_check_count == 0
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"node_count": -1, "edge_count": 0, "checks": (check,)},
        {"node_count": True, "edge_count": 0, "checks": (check,)},
        {"node_count": 0, "edge_count": -1, "checks": (check,)},
        {"node_count": 0, "edge_count": False, "checks": (check,)},
        {"node_count": 0, "edge_count": 0, "checks": ("bad",)},
        {"node_count": 0, "edge_count": 0, "checks": []},
        {"node_count": 0, "edge_count": 0, "checks": (), "issues": ("bad",)},
        {"node_count": 0, "edge_count": 0, "checks": (), "issues": []},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphDiagnosticsRunResult(
                nodes_csv_path=Path("nodes.csv"),
                edges_csv_path=Path("edges.csv"),
                graph_json_path=Path("graph.json"),
                **kwargs,
            )


def test_valid_writer_generated_artifacts_run_diagnostics(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path, graph_path = writer_generated_bundle_files(tmp_path)

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is True
    assert result.node_count == 2
    assert result.edge_count == 1
    assert check_names(result) == [
        "graph_export_bundle",
        "graph_json_validation",
        "contract_graph_load",
        "graph_structure_diagnostics",
    ]
    assert all(check.passed for check in result.checks)
    assert_json_safe(result.to_dict())


def test_header_only_graph_artifacts_are_deterministic(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    graph_path = tmp_path / "graph.json"
    write_csv(nodes_path, NODE_COLUMNS)
    write_csv(edges_path, EDGE_COLUMNS)
    assert (
        write_preprocessing_graph_json(nodes_path, edges_path, graph_path).passed
        is True
    )

    first = run_preprocessing_graph_diagnostics(nodes_path, edges_path, graph_path)
    second = run_preprocessing_graph_diagnostics(nodes_path, edges_path, graph_path)

    assert first.to_dict() == second.to_dict()
    assert first.passed is False
    assert first.node_count == 0
    assert first.edge_count == 0
    failed_issue_kinds = {
        issue.kind for check in first.checks for issue in check.issues
    }
    assert "diagnostic_unavailable" in failed_issue_kinds


def test_bundle_failure_prevents_diagnostics(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph_path.write_text("{not json", encoding="utf-8")

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is False
    assert issue_kinds(result) == ["bundle_failed"]
    assert check_names(result) == ["graph_export_bundle"]
    assert result.checks[0].passed is False


def test_missing_graph_json_fails_deterministically(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph_path.unlink()

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is False
    assert "bundle_failed" in issue_kinds(result)
    assert check_names(result) == ["graph_export_bundle"]


def test_invalid_corrected_edges_schema_fails_before_diagnostics(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    old_header = tuple(
        column
        for column in EDGE_COLUMNS
        if column not in {"all_edge_types", "n_edge_types"}
    )
    write_csv(edges_path, old_header, [edge_row()])

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is False
    assert "bundle_failed" in issue_kinds(result)
    assert check_names(result) == ["graph_export_bundle"]


def test_multi_type_edge_graph_passes_diagnostics(tmp_path: Path) -> None:
    graph = valid_graph_payload()
    edge = dict(graph["edges"][0])  # type: ignore[index]
    edge.update(
        {
            "edge_type": "hbond",
            "all_edge_types": "hbond|hydrophobic|vdw",
            "n_edge_types": "3",
        }
    )
    graph["edges"] = [edge]
    nodes_path, edges_path, graph_path = write_valid_bundle_files(
        tmp_path,
        edge_rows=[
            edge_row(
                edge_type="hbond",
                all_edge_types="hbond|hydrophobic|vdw",
                n_edge_types="3",
            )
        ],
        graph=graph,
    )

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is True
    assert result.edge_count == 1


def test_generic_residue_contact_graph_passes_diagnostics(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is True
    assert result.checks[-1].summary["passed_basic_qc"] is True


def test_diagnostics_result_is_deterministic(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = writer_generated_bundle_files(tmp_path)

    first = run_preprocessing_graph_diagnostics(nodes_path, edges_path, graph_path)
    second = run_preprocessing_graph_diagnostics(nodes_path, edges_path, graph_path)

    assert first.to_dict() == second.to_dict()


def test_runner_does_not_write_files(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = writer_generated_bundle_files(tmp_path)
    before = {
        path: path.read_text(encoding="utf-8")
        for path in (nodes_path, edges_path, graph_path)
    }

    result = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is True
    assert {
        path: path.read_text(encoding="utf-8")
        for path in (nodes_path, edges_path, graph_path)
    } == before

    implementation = inspect.getsource(run_preprocessing_graph_diagnostics)
    for forbidden in ("csv.writer", 'open(', '"w"', "write_text", "json.dump"):
        assert forbidden not in implementation


def test_runner_does_not_generate_artifacts() -> None:
    tree = ast.parse(inspect.getsource(run_preprocessing_graph_diagnostics))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "build_preprocessing_graph_export_bundle" in call_names
    for forbidden in (
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_mapping",
    ):
        assert forbidden not in call_names


def test_runner_does_not_call_stage13_comparison_cli_or_workflow() -> None:
    source = inspect.getsource(run_preprocessing_graph_diagnostics)

    for forbidden in (
        "compute_condition_contacts",
        "compute_manifest_contacts",
        "write_contact_edges_csv",
        "validate_contact_edges_csv",
        "contract_subset",
        "notebook",
        "mania.cli",
        "pipeline",
        "workflow",
        "temporal_rin",
    ):
        assert forbidden not in source


def test_bridge_module_does_not_add_scientific_dependencies() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden not in source


def test_docs_state_stage_14_2a_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.2a",
        "runs existing graph validators/diagnostics on generated graph artifacts",
        "uses Stage 14.1f bundle boundary",
        "diagnostics report shape remains Stage 14.2b",
        "reference comparison remains Stage 14.3",
    ):
        assert phrase in text


def test_docs_preserve_multi_type_edge_semantics() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in ("edge_type", "all_edge_types", "n_edge_types"):
        assert phrase in text


def test_docs_preserve_contact_edges_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv, graph.json, and diagnostics are Stage 14 "
        "graph artifacts",
    ):
        assert phrase in text


def test_docs_preserve_v1_2_semantics_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "MANIA_analysis_v1_2",
        "v1.2 Cell 5 interaction priority",
        "v1.2 Cell 12 temporal RIN export fix",
        "temporal RIN export remains future scope",
    ):
        assert phrase in text


def test_runner_uses_module_public_api() -> None:
    assert (
        trajectory_graph_diagnostics.run_preprocessing_graph_diagnostics
        is run_preprocessing_graph_diagnostics
    )
