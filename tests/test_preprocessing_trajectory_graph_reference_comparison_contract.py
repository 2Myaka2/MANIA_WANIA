import csv
import json
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
    PreprocessingGraphReferenceComparisonInput,
    PreprocessingGraphReferenceComparisonInputValidationResult,
    PreprocessingGraphReferenceComparisonIssue,
    PreprocessingGraphReferenceComparisonOptions,
    build_preprocessing_graph_diagnostics_report,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    run_preprocessing_graph_diagnostics,
    validate_preprocessing_graph_csvs,
    validate_preprocessing_graph_reference_comparison_input,
    write_preprocessing_graph_edges_csv,
    write_preprocessing_graph_json,
    write_preprocessing_graph_nodes_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_graph_reference_comparison.py"
)
DOC_PATHS = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_export.md",
    REPO_ROOT / "docs" / "adr" / "0001-optional-scientific-dependencies.md",
)


def assert_json_safe(payload: object) -> None:
    assert json.loads(json.dumps(payload)) == payload


def write_csv(
    path: Path,
    header: tuple[str, ...],
    rows: list[list[str]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def row_values(columns: tuple[str, ...], values: dict[str, str]) -> list[str]:
    row = {column: "" for column in columns}
    row.update(values)
    return [row[column] for column in columns]


def node_row(resid: str, *, condition: str = "normal") -> list[str]:
    return row_values(
        NODE_COLUMNS,
        {
            "resid": resid,
            "resname": "ALA" if resid.endswith("1") else "GLY",
            "condition": condition,
        },
    )


def edge_row(
    resid_i: str = "n1",
    resid_j: str = "n2",
    *,
    condition: str = "normal",
    contact_freq: str = "0.75",
    edge_type: str = "residue_contact",
    all_edge_types: str = "residue_contact",
    n_edge_types: str = "1",
) -> list[str]:
    return row_values(
        EDGE_COLUMNS,
        {
            "resid_i": resid_i,
            "resid_j": resid_j,
            "edge_type": edge_type,
            "all_edge_types": all_edge_types,
            "n_edge_types": n_edge_types,
            "condition": condition,
            "contact_freq": contact_freq,
            "mean_dist_A": "4.2",
        },
    )


def graph_payload(
    *,
    node_ids: tuple[str, str] = ("n1", "n2"),
    condition: str = "normal",
    schema_version: str = "0.1",
    contact_freq: str = "0.75",
    edge_type: str = "residue_contact",
    all_edge_types: str = "residue_contact",
    n_edge_types: str = "1",
) -> dict[str, object]:
    nodes = [
        {
            **{column: "" for column in NODE_COLUMNS},
            "id": node_id,
            "resid": node_id,
            "resname": "ALA" if index == 0 else "GLY",
            "condition": condition,
        }
        for index, node_id in enumerate(node_ids)
    ]
    edges = [
        {
            **{column: "" for column in EDGE_COLUMNS},
            "source": node_ids[0],
            "target": node_ids[1],
            "resid_i": node_ids[0],
            "resid_j": node_ids[1],
            "edge_type": edge_type,
            "all_edge_types": all_edge_types,
            "n_edge_types": n_edge_types,
            "condition": condition,
            "contact_freq": contact_freq,
            "mean_dist_A": "4.2",
        }
    ]
    return {
        "condition": condition,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "directed": False,
        "schema_version": schema_version,
        "nodes": nodes,
        "edges": edges,
    }


def write_graph_bundle(
    root: Path,
    *,
    node_ids: tuple[str, str] = ("n1", "n2"),
    condition: str = "normal",
    schema_version: str = "0.1",
    contact_freq: str = "0.75",
    edge_type: str = "residue_contact",
    all_edge_types: str = "residue_contact",
    n_edge_types: str = "1",
) -> tuple[Path, Path, Path]:
    root.mkdir()
    nodes_path = root / "nodes.csv"
    edges_path = root / "edges.csv"
    graph_path = root / "graph.json"
    write_csv(
        nodes_path,
        NODE_COLUMNS,
        [node_row(node_id, condition=condition) for node_id in node_ids],
    )
    write_csv(
        edges_path,
        EDGE_COLUMNS,
        [
            edge_row(
                node_ids[0],
                node_ids[1],
                condition=condition,
                contact_freq=contact_freq,
                edge_type=edge_type,
                all_edge_types=all_edge_types,
                n_edge_types=n_edge_types,
            )
        ],
    )
    graph_path.write_text(
        json.dumps(
            graph_payload(
                node_ids=node_ids,
                condition=condition,
                schema_version=schema_version,
                contact_freq=contact_freq,
                edge_type=edge_type,
                all_edge_types=all_edge_types,
                n_edge_types=n_edge_types,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return nodes_path, edges_path, graph_path


def make_input(
    tmp_path: Path,
    *,
    generated_node_ids: tuple[str, str] = ("n1", "n2"),
    reference_node_ids: tuple[str, str] = ("n1", "n2"),
    generated_condition: str = "normal",
    reference_condition: str = "normal",
    generated_schema_version: str = "0.1",
    reference_schema_version: str = "0.1",
    generated_contact_freq: str = "0.75",
    reference_contact_freq: str = "0.75",
    options: PreprocessingGraphReferenceComparisonOptions | None = None,
) -> PreprocessingGraphReferenceComparisonInput:
    generated_paths = write_graph_bundle(
        tmp_path / "generated",
        node_ids=generated_node_ids,
        condition=generated_condition,
        schema_version=generated_schema_version,
        contact_freq=generated_contact_freq,
    )
    reference_paths = write_graph_bundle(
        tmp_path / "reference",
        node_ids=reference_node_ids,
        condition=reference_condition,
        schema_version=reference_schema_version,
        contact_freq=reference_contact_freq,
    )
    return PreprocessingGraphReferenceComparisonInput(
        generated_nodes_csv_path=generated_paths[0],
        generated_edges_csv_path=generated_paths[1],
        generated_graph_json_path=generated_paths[2],
        reference_nodes_csv_path=reference_paths[0],
        reference_edges_csv_path=reference_paths[1],
        reference_graph_json_path=reference_paths[2],
        options=options or PreprocessingGraphReferenceComparisonOptions(),
    )


def issue_kinds(
    result: PreprocessingGraphReferenceComparisonInputValidationResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingGraphReferenceComparisonOptions is not None
    assert PreprocessingGraphReferenceComparisonInput is not None
    assert PreprocessingGraphReferenceComparisonIssue is not None
    assert (
        PreprocessingGraphReferenceComparisonInputValidationResult is not None
    )
    assert validate_preprocessing_graph_reference_comparison_input is not None


def test_existing_stage_14_exports_still_work() -> None:
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
    assert PreprocessingGraphDiagnosticsReport is not None
    assert PreprocessingGraphDiagnosticsReportSection is not None
    assert build_preprocessing_graph_diagnostics_report is not None


def test_options_validate_and_serialize() -> None:
    options = PreprocessingGraphReferenceComparisonOptions()

    assert options.reference_semantics == "MANIA_analysis_v1_2"
    assert options.compare_nodes is True
    assert options.compare_edges is True
    assert options.compare_graph_json is True
    assert_json_safe(options.to_dict())

    for kwargs in (
        {"reference_semantics": ""},
        {"condition": ""},
        {"require_matching_condition": 1},
        {"require_matching_schema_version": "true"},
        {"compare_nodes": 0},
        {"compare_edges": None},
        {"compare_graph_json": "false"},
    ):
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonOptions(**kwargs)


def test_input_validates_and_serializes(tmp_path: Path) -> None:
    paths = write_graph_bundle(tmp_path / "generated")
    ref_paths = write_graph_bundle(tmp_path / "reference")
    comparison_input = PreprocessingGraphReferenceComparisonInput(
        generated_nodes_csv_path=paths[0],
        generated_edges_csv_path=paths[1],
        generated_graph_json_path=paths[2],
        reference_nodes_csv_path=ref_paths[0],
        reference_edges_csv_path=ref_paths[1],
        reference_graph_json_path=ref_paths[2],
    )

    assert comparison_input.generated_nodes_csv_path == paths[0]
    assert_json_safe(comparison_input.to_dict())

    with pytest.raises(ValueError):
        PreprocessingGraphReferenceComparisonInput(
            generated_nodes_csv_path="nodes.csv",
            generated_edges_csv_path=paths[1],
            generated_graph_json_path=paths[2],
            reference_nodes_csv_path=ref_paths[0],
            reference_edges_csv_path=ref_paths[1],
            reference_graph_json_path=ref_paths[2],
        )
    with pytest.raises(ValueError):
        PreprocessingGraphReferenceComparisonInput(
            generated_nodes_csv_path=paths[0],
            generated_edges_csv_path=paths[1],
            generated_graph_json_path=paths[2],
            reference_nodes_csv_path=ref_paths[0],
            reference_edges_csv_path=ref_paths[1],
            reference_graph_json_path=ref_paths[2],
            options={},
        )


def test_issue_validates_and_serializes() -> None:
    issue = PreprocessingGraphReferenceComparisonIssue(
        kind="path_missing",
        message="Artifact is missing.",
        artifact_group="generated",
        artifact_kind="nodes_csv",
        field="generated_nodes_csv_path",
        value="",
    )

    assert_json_safe(issue.to_dict())

    for kwargs in (
        {"kind": "", "message": "message"},
        {"kind": "kind", "message": ""},
        {"kind": "kind", "message": "message", "artifact_group": ""},
        {"kind": "kind", "message": "message", "artifact_kind": " "},
        {"kind": "kind", "message": "message", "field": ""},
        {"kind": "kind", "message": "message", "value": 1},
    ):
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonIssue(**kwargs)


def test_validation_result_validates_and_serializes(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    result = PreprocessingGraphReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        generated_node_count=2,
        generated_edge_count=1,
        reference_node_count=2,
        reference_edge_count=1,
        generated_condition="normal",
        reference_condition="normal",
        generated_schema_version="0.1",
        reference_schema_version="0.1",
    )

    assert result.passed is True
    assert result.issue_count == 0
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"generated_node_count": -1},
        {"generated_edge_count": True},
        {"reference_node_count": -1},
        {"reference_edge_count": False},
        {"issues": (object(),)},
        {"issues": []},
        {"comparison_input": object()},
    )
    for kwargs in invalid_kwargs:
        result_kwargs = {
            "comparison_input": comparison_input,
            "generated_node_count": 2,
            "generated_edge_count": 1,
            "reference_node_count": 2,
            "reference_edge_count": 1,
        }
        result_kwargs.update(kwargs)
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonInputValidationResult(
                **result_kwargs,
            )


def test_valid_generated_reference_artifacts_pass_input_validation(
    tmp_path: Path,
) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(tmp_path)
    )

    assert result.passed is True
    assert result.generated_node_count == 2
    assert result.generated_edge_count == 1
    assert result.reference_node_count == 2
    assert result.reference_edge_count == 1
    assert result.generated_condition == "normal"
    assert result.reference_condition == "normal"
    assert result.generated_schema_version == "0.1"
    assert result.reference_schema_version == "0.1"
    assert result.issues == ()


def test_missing_generated_artifact_fails(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    comparison_input.generated_nodes_csv_path.unlink()

    result = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert "path_missing" in issue_kinds(result)
    assert any(
        issue.artifact_group == "generated"
        and issue.artifact_kind == "nodes_csv"
        for issue in result.issues
    )


def test_missing_reference_artifact_fails(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    comparison_input.reference_graph_json_path.unlink()

    result = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert "path_missing" in issue_kinds(result)
    assert any(
        issue.artifact_group == "reference"
        and issue.artifact_kind == "graph_json"
        for issue in result.issues
    )


def test_invalid_generated_bundle_fails(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    old_edge_columns = tuple(
        column
        for column in EDGE_COLUMNS
        if column not in {"all_edge_types", "n_edge_types"}
    )
    write_csv(
        comparison_input.generated_edges_csv_path,
        old_edge_columns,
        [
            row_values(
                old_edge_columns,
                {
                    "resid_i": "n1",
                    "resid_j": "n2",
                    "edge_type": "residue_contact",
                    "condition": "normal",
                    "contact_freq": "0.75",
                },
            )
        ],
    )

    result = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert "generated_bundle_invalid" in issue_kinds(result)


def test_invalid_reference_bundle_fails(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    comparison_input.reference_graph_json_path.write_text(
        "not json",
        encoding="utf-8",
    )

    result = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert "reference_bundle_invalid" in issue_kinds(result)


def test_validation_rejects_invalid_input_type() -> None:
    with pytest.raises(ValueError):
        validate_preprocessing_graph_reference_comparison_input({})


def test_v1_1_semantics_are_rejected_by_default(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            options=PreprocessingGraphReferenceComparisonOptions(
                reference_semantics="MANIA_analysis_v1_1"
            ),
        )
    )

    assert "reference_semantics_invalid" in issue_kinds(result)


def test_all_comparison_targets_disabled_fails(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            options=PreprocessingGraphReferenceComparisonOptions(
                compare_nodes=False,
                compare_edges=False,
                compare_graph_json=False,
            ),
        )
    )

    assert "comparison_target_disabled" in issue_kinds(result)


def test_condition_mismatch_fails_when_required(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(tmp_path, reference_condition="tumor")
    )

    assert "condition_mismatch" in issue_kinds(result)


def test_condition_mismatch_allowed_when_disabled(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            reference_condition="tumor",
            options=PreprocessingGraphReferenceComparisonOptions(
                require_matching_condition=False
            ),
        )
    )

    assert result.passed is True


def test_explicit_condition_is_required(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            reference_condition="tumor",
            options=PreprocessingGraphReferenceComparisonOptions(
                condition="normal",
                require_matching_condition=False,
            ),
        )
    )

    assert "condition_mismatch" in issue_kinds(result)


def test_schema_version_mismatch_fails_when_required(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(tmp_path, reference_schema_version="0.2")
    )

    assert "schema_version_mismatch" in issue_kinds(result)


def test_schema_version_mismatch_allowed_when_disabled(
    tmp_path: Path,
) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            reference_schema_version="0.2",
            options=PreprocessingGraphReferenceComparisonOptions(
                require_matching_schema_version=False
            ),
        )
    )

    assert result.passed is True


@pytest.mark.parametrize(
    ("edge_type", "all_edge_types", "n_edge_types"),
    [
        ("hbond", "hbond|hydrophobic|vdw", "3"),
        ("residue_contact", "residue_contact", "1"),
    ],
)
def test_corrected_edge_artifacts_are_accepted(
    tmp_path: Path,
    edge_type: str,
    all_edge_types: str,
    n_edge_types: str,
) -> None:
    generated_paths = write_graph_bundle(
        tmp_path / "generated",
        edge_type=edge_type,
        all_edge_types=all_edge_types,
        n_edge_types=n_edge_types,
    )
    reference_paths = write_graph_bundle(
        tmp_path / "reference",
        edge_type=edge_type,
        all_edge_types=all_edge_types,
        n_edge_types=n_edge_types,
    )

    result = validate_preprocessing_graph_reference_comparison_input(
        PreprocessingGraphReferenceComparisonInput(
            generated_nodes_csv_path=generated_paths[0],
            generated_edges_csv_path=generated_paths[1],
            generated_graph_json_path=generated_paths[2],
            reference_nodes_csv_path=reference_paths[0],
            reference_edges_csv_path=reference_paths[1],
            reference_graph_json_path=reference_paths[2],
        )
    )

    assert result.passed is True


def test_input_validation_does_not_compare_node_rows(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2"),
            reference_node_ids=("r1", "r2"),
        )
    )

    assert result.passed is True
    assert not any("row" in issue.kind for issue in result.issues)


def test_input_validation_does_not_compare_edge_rows(tmp_path: Path) -> None:
    result = validate_preprocessing_graph_reference_comparison_input(
        make_input(
            tmp_path,
            generated_contact_freq="0.1",
            reference_contact_freq="0.9",
        )
    )

    assert result.passed is True


def test_validation_result_is_deterministic(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)

    first = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )
    second = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert first.to_dict() == second.to_dict()


def test_validation_does_not_write_files(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    paths = (
        comparison_input.generated_nodes_csv_path,
        comparison_input.generated_edges_csv_path,
        comparison_input.generated_graph_json_path,
        comparison_input.reference_nodes_csv_path,
        comparison_input.reference_edges_csv_path,
        comparison_input.reference_graph_json_path,
    )
    before = {path: path.read_text(encoding="utf-8") for path in paths}

    result = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )

    assert result.passed is True
    assert {path: path.read_text(encoding="utf-8") for path in paths} == before


def test_source_boundary_does_not_write_or_run_diagnostics() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        'open(',
        '"w"',
        "write_text",
        "json.dump",
        "csv.writer",
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "compute_graph_qc",
    ):
        assert forbidden not in source


def test_source_boundary_does_not_call_workflow_or_forbidden_dependencies() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "RowComparison",
        "contract_subset",
        "notebook_export",
        "mania.cli",
        "pipeline",
        "workflow",
        "temporal_rin",
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert forbidden not in source


def test_docs_state_stage_14_3a_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.3a",
        "reference graph comparison input contract",
        "validates generated/reference artifact readiness",
        "does not perform comparison",
        "actual comparison remains Stage 14.3b",
    ):
        assert phrase in text


def test_docs_preserve_v1_2_and_edge_boundaries() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "MANIA_analysis_v1_2",
        "v1.1 historical reference",
        "v1.2 Cell 5 interaction priority",
        "v1.2 Cell 12 temporal RIN export fix",
        "temporal RIN export remains future scope",
        "edge_type",
        "all_edge_types",
        "n_edge_types",
        "EDGE_TYPE_PRIORITY",
        "Stage 13 contact_edges.csv is aggregate contacts table",
        (
            "backend graph edges.csv, graph.json, diagnostics, and "
            "comparison inputs are Stage 14 graph artifacts"
        ),
    ):
        assert phrase in text
    assert EDGE_TYPE_PRIORITY is not None
