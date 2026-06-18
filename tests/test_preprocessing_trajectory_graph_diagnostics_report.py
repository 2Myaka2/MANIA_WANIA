import ast
import csv
import inspect
import json
import math
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS, EDGE_TYPE_PRIORITY, NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
    PreprocessingGraphDiagnosticsCheckResult,
    PreprocessingGraphDiagnosticsReport,
    PreprocessingGraphDiagnosticsReportSection,
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
    build_preprocessing_graph_diagnostics_report,
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


def make_issue(
    *,
    kind: str = "diagnostic_failed",
    message: str = "Expected diagnostics issue.",
    check_name: str | None = None,
    field: str | None = "graph",
    value: str | None = "value",
) -> PreprocessingGraphDiagnosticsRunIssue:
    return PreprocessingGraphDiagnosticsRunIssue(
        kind=kind,
        message=message,
        check_name=check_name,
        field=field,
        value=value,
    )


def make_check(
    name: str = "graph_export_bundle",
    *,
    passed: bool = True,
    issues: tuple[PreprocessingGraphDiagnosticsRunIssue, ...] = (),
    summary: dict[str, str | int | float | bool | None] | None = None,
) -> PreprocessingGraphDiagnosticsCheckResult:
    return PreprocessingGraphDiagnosticsCheckResult(
        name=name,
        passed=passed,
        summary=summary
        or {
            "node_count": 2,
            "edge_count": 1,
            "schema_version": "0.1",
        },
        issues=issues,
    )


def make_run_result(
    *,
    checks: tuple[PreprocessingGraphDiagnosticsCheckResult, ...] | None = None,
    issues: tuple[PreprocessingGraphDiagnosticsRunIssue, ...] = (),
) -> PreprocessingGraphDiagnosticsRunResult:
    return PreprocessingGraphDiagnosticsRunResult(
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        graph_json_path=Path("graph.json"),
        node_count=2,
        edge_count=1,
        checks=checks or (make_check(),),
        issues=issues,
    )


def section(
    report: PreprocessingGraphDiagnosticsReport,
    title: str,
) -> PreprocessingGraphDiagnosticsReportSection:
    return next(item for item in report.sections if item.title == title)


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


def valid_graph_payload() -> dict[str, object]:
    nodes = []
    for resid, resname in (("n1", "ALA"), ("n2", "GLY")):
        node = {column: "" for column in NODE_COLUMNS}
        node.update(
            {
                "id": resid,
                "resid": resid,
                "resname": resname,
                "condition": "normal",
            }
        )
        nodes.append(node)
    edge = {column: "" for column in EDGE_COLUMNS}
    edge.update(
        {
            "source": "n1",
            "target": "n2",
            "resid_i": "n1",
            "resid_j": "n2",
            "edge_type": "hbond",
            "all_edge_types": "hbond|hydrophobic|vdw",
            "n_edge_types": "3",
            "condition": "normal",
        }
    )
    return {
        "condition": "normal",
        "n_nodes": 2,
        "n_edges": 1,
        "directed": False,
        "schema_version": "0.1",
        "nodes": nodes,
        "edges": [edge],
    }


def write_valid_bundle_files(tmp_path: Path) -> tuple[Path, Path, Path]:
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
    write_csv(
        edges_path,
        EDGE_COLUMNS,
        [
            edge_row(
                edge_type="hbond",
                all_edge_types="hbond|hydrophobic|vdw",
                n_edge_types="3",
            )
        ],
    )
    graph_path.write_text(
        json.dumps(valid_graph_payload(), indent=2) + "\n",
        encoding="utf-8",
    )
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
    assert write_preprocessing_graph_json(nodes_path, edges_path, graph_path).passed
    return nodes_path, edges_path, graph_path


def test_public_exports_work() -> None:
    assert PreprocessingGraphDiagnosticsReportSection is not None
    assert PreprocessingGraphDiagnosticsReport is not None
    assert build_preprocessing_graph_diagnostics_report is not None


def test_existing_stage_14_1a_through_14_2a_exports_still_work() -> None:
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
    assert PreprocessingGraphDiagnosticsRunIssue is not None
    assert PreprocessingGraphDiagnosticsCheckResult is not None
    assert PreprocessingGraphDiagnosticsRunResult is not None
    assert run_preprocessing_graph_diagnostics is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_report_section_validates_and_serializes() -> None:
    report_section = PreprocessingGraphDiagnosticsReportSection(
        title="overview",
        status="passed",
        summary={"passed": True, "node_count": 2},
        details=({"name": "graph_export_bundle", "passed": True},),
    )

    assert report_section.title == "overview"
    assert_json_safe(report_section.to_dict())

    invalid_kwargs = (
        {"title": "", "status": "passed", "summary": {}},
        {"title": "overview", "status": "bad", "summary": {}},
        {"title": "overview", "status": "passed", "summary": {"bad": []}},
        {"title": "overview", "status": "passed", "summary": {"bad": math.nan}},
        {"title": "overview", "status": "passed", "summary": {}, "details": []},
        {
            "title": "overview",
            "status": "passed",
            "summary": {},
            "details": ("bad",),
        },
        {
            "title": "overview",
            "status": "passed",
            "summary": {},
            "details": ({"bad": []},),
        },
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphDiagnosticsReportSection(**kwargs)


def test_report_validates_and_serializes() -> None:
    report_section = PreprocessingGraphDiagnosticsReportSection(
        title="overview",
        status="passed",
        summary={"passed": True},
    )
    report = PreprocessingGraphDiagnosticsReport(
        passed=True,
        status="passed",
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        graph_json_path=Path("graph.json"),
        node_count=2,
        edge_count=1,
        check_count=1,
        failed_check_count=0,
        issue_count=0,
        sections=(report_section,),
    )

    assert report.section_count == 1
    assert_json_safe(report.to_dict())

    invalid_kwargs = (
        {"passed": "yes"},
        {"status": ""},
        {"node_count": -1},
        {"edge_count": True},
        {"check_count": -1},
        {"failed_check_count": False},
        {"issue_count": -1},
        {"sections": ("bad",)},
        {"reference_semantics": ""},
        {"edge_schema": ""},
    )
    base = {
        "passed": True,
        "status": "passed",
        "nodes_csv_path": Path("nodes.csv"),
        "edges_csv_path": Path("edges.csv"),
        "graph_json_path": Path("graph.json"),
        "node_count": 2,
        "edge_count": 1,
        "check_count": 1,
        "failed_check_count": 0,
        "issue_count": 0,
        "sections": (report_section,),
    }
    for overrides in invalid_kwargs:
        kwargs = dict(base)
        kwargs.update(overrides)
        with pytest.raises(ValueError):
            PreprocessingGraphDiagnosticsReport(**kwargs)


def test_report_builder_accepts_passing_diagnostics_result() -> None:
    result = make_run_result()

    report = build_preprocessing_graph_diagnostics_report(result)

    assert report.passed is True
    assert report.status == "passed"
    assert report.node_count == result.node_count
    assert report.edge_count == result.edge_count
    assert report.check_count == result.check_count
    assert report.failed_check_count == result.failed_check_count
    assert report.issue_count == 0


def test_failed_diagnostics_result_produces_failed_report() -> None:
    check_issue = make_issue(check_name="graph_structure_diagnostics")
    failed_check = make_check(
        "graph_structure_diagnostics",
        passed=False,
        issues=(check_issue,),
    )

    report = build_preprocessing_graph_diagnostics_report(
        make_run_result(checks=(make_check(), failed_check))
    )

    assert report.passed is False
    assert report.status == "failed"
    assert report.failed_check_count == 1
    assert section(report, "issues").details[0]["kind"] == "diagnostic_failed"


def test_report_has_required_sections_in_deterministic_order() -> None:
    report = build_preprocessing_graph_diagnostics_report(make_run_result())

    assert [item.title for item in report.sections] == [
        "overview",
        "artifacts",
        "checks",
        "issues",
        "schema_reference_context",
        "boundaries",
    ]


def test_artifacts_section_preserves_paths() -> None:
    report = build_preprocessing_graph_diagnostics_report(make_run_result())
    artifacts = section(report, "artifacts")

    assert artifacts.summary["nodes_csv_path"] == "nodes.csv"
    assert artifacts.summary["edges_csv_path"] == "edges.csv"
    assert artifacts.summary["graph_json_path"] == "graph.json"


def test_checks_section_summarizes_checks() -> None:
    failed_issue = make_issue(check_name="contract_graph_load")
    checks = (
        make_check("graph_export_bundle"),
        make_check("contract_graph_load", passed=False, issues=(failed_issue,)),
    )

    checks_section = section(
        build_preprocessing_graph_diagnostics_report(
            make_run_result(checks=checks)
        ),
        "checks",
    )

    assert checks_section.summary["total_checks"] == 2
    assert checks_section.summary["passed_checks"] == 1
    assert checks_section.summary["failed_checks"] == 1
    assert [detail["name"] for detail in checks_section.details] == [
        "graph_export_bundle",
        "contract_graph_load",
    ]
    assert [detail["issue_count"] for detail in checks_section.details] == [0, 1]


def test_issues_section_summarizes_top_level_and_check_issues() -> None:
    top_issue = make_issue(kind="bundle_failed", check_name="graph_export_bundle")
    check_issue = make_issue(check_name="graph_json_validation")
    result = make_run_result(
        checks=(
            make_check(
                "graph_json_validation",
                passed=False,
                issues=(check_issue,),
            ),
        ),
        issues=(top_issue,),
    )

    issues = section(build_preprocessing_graph_diagnostics_report(result), "issues")

    assert issues.summary == {
        "issue_count": 2,
        "top_level_issue_count": 1,
        "check_issue_count": 1,
    }
    assert [detail["scope"] for detail in issues.details] == ["top_level", "check"]
    assert [detail["check_name"] for detail in issues.details] == [
        "graph_export_bundle",
        "graph_json_validation",
    ]


def test_schema_reference_section_documents_v1_2_semantics() -> None:
    schema = section(
        build_preprocessing_graph_diagnostics_report(make_run_result()),
        "schema_reference_context",
    )

    assert schema.summary["reference_semantics"] == "MANIA_analysis_v1_2"
    assert schema.summary["edge_schema"] == "corrected_multi_type_edges"
    assert schema.summary["edge_type_field"] == "edge_type"
    assert schema.summary["all_edge_types_field"] == "all_edge_types"
    assert schema.summary["n_edge_types_field"] == "n_edge_types"
    assert schema.summary["edge_type_priority"] == "|".join(EDGE_TYPE_PRIORITY)
    assert "future scope" in str(schema.summary["temporal_rin"])


def test_boundaries_section_preserves_future_stages() -> None:
    boundaries = section(
        build_preprocessing_graph_diagnostics_report(make_run_result()),
        "boundaries",
    )
    text = " ".join(str(value) for value in boundaries.summary.values())

    assert "report-shape-only" in text
    assert "Stage 14.3 handles reference comparison" in text
    assert "Stage 14.4 handles expected mismatches / semantic differences" in text
    assert boundaries.summary["workflow_cli_integration"] == "not implemented"
    assert boundaries.summary["temporal_rin_export"] == "future scope"
    assert boundaries.summary["biological_interpretation"] == "not implemented"


def test_report_output_is_deterministic() -> None:
    result = make_run_result()

    first = build_preprocessing_graph_diagnostics_report(result)
    second = build_preprocessing_graph_diagnostics_report(result)

    assert first.to_dict() == second.to_dict()


def test_builder_rejects_invalid_input_type() -> None:
    with pytest.raises(TypeError):
        build_preprocessing_graph_diagnostics_report(object())  # type: ignore[arg-type]


def test_builder_does_not_run_diagnostics_or_bundle_boundary() -> None:
    tree = ast.parse(inspect.getsource(build_preprocessing_graph_diagnostics_report))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    for forbidden in (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_export_bundle",
        "validate_graph_json",
        "load_contract_graph",
        "compute_graph_qc",
    ):
        assert forbidden not in call_names


def test_builder_does_not_read_or_write_files() -> None:
    source = inspect.getsource(build_preprocessing_graph_diagnostics_report)

    for forbidden in (
        "open(",
        "read_text",
        "write_text",
        "json.load",
        "json.dump",
        "csv.reader",
        "csv.writer",
    ):
        assert forbidden not in source


def test_builder_does_not_perform_comparison_cli_workflow_or_temporal_export() -> None:
    source = inspect.getsource(build_preprocessing_graph_diagnostics_report)

    for forbidden in (
        "contract_subset",
        "notebook",
        "compare",
        "mania.cli",
        "pipeline",
        "workflow",
        "temporal_rin",
    ):
        assert forbidden not in source


def test_report_code_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden not in source


def test_report_from_real_synthetic_diagnostics_run(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)

    diagnostics = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )
    report = build_preprocessing_graph_diagnostics_report(diagnostics)
    payload = report.to_dict()

    assert report.passed is True
    assert report.edge_count == 1
    assert [item.title for item in report.sections] == [
        "overview",
        "artifacts",
        "checks",
        "issues",
        "schema_reference_context",
        "boundaries",
    ]
    assert section(report, "schema_reference_context").summary["edge_schema"] == (
        "corrected_multi_type_edges"
    )
    assert "nodes" not in payload
    assert "edges" not in payload


def test_report_from_writer_generated_synthetic_diagnostics_run(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path, graph_path = writer_generated_bundle_files(tmp_path)

    report = build_preprocessing_graph_diagnostics_report(
        run_preprocessing_graph_diagnostics(nodes_path, edges_path, graph_path)
    )

    assert report.passed is True
    assert report.node_count == 2
    assert report.edge_count == 1


def test_report_from_failed_bundle_diagnostics_run(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph_path.write_text("{not json", encoding="utf-8")

    diagnostics = run_preprocessing_graph_diagnostics(
        nodes_path,
        edges_path,
        graph_path,
    )
    report = build_preprocessing_graph_diagnostics_report(diagnostics)

    assert report.passed is False
    assert section(report, "checks").details[0]["name"] == "graph_export_bundle"
    assert section(report, "issues").details[0]["kind"] == "bundle_failed"


def test_docs_state_stage_14_2b_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.2b",
        "diagnostics report shape",
        "consumes an already computed Stage 14.2a diagnostics",
        "does not run diagnostics again",
        "Reference comparison remains Stage 14.3",
    ):
        assert phrase in text


def test_docs_preserve_multi_type_edge_semantics() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in ("edge_type", "all_edge_types", "n_edge_types"):
        assert phrase in text


def test_docs_preserve_contact_edges_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)
    normalized = " ".join(text.split())

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv, graph.json, diagnostics, and diagnostics "
        "report are Stage 14 graph artifacts",
    ):
        assert phrase in normalized


def test_docs_preserve_v1_2_semantics_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "MANIA_analysis_v1_2",
        "v1.2 Cell 5 interaction priority",
        "v1.2 Cell 12 temporal RIN export fix",
        "temporal RIN export remains future scope",
    ):
        assert phrase in text


def test_builder_uses_module_public_api() -> None:
    assert (
        trajectory_graph_diagnostics.build_preprocessing_graph_diagnostics_report
        is build_preprocessing_graph_diagnostics_report
    )
