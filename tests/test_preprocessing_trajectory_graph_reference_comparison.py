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
    PreprocessingGraphReferenceComparisonMismatch,
    PreprocessingGraphReferenceComparisonOptions,
    PreprocessingGraphReferenceComparisonResult,
    PreprocessingGraphReferenceComparisonTargetResult,
    build_preprocessing_graph_diagnostics_report,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    compare_preprocessing_graph_reference_artifacts,
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


def node_fields(
    resid: str,
    *,
    condition: str = "normal",
    resname: str | None = None,
    region: str = "core",
) -> dict[str, str]:
    return {
        "resid": resid,
        "resname": resname or ("ALA" if resid.endswith("1") else "GLY"),
        "region": region,
        "condition": condition,
    }


def node_row(
    resid: str,
    *,
    condition: str = "normal",
    resname: str | None = None,
    region: str = "core",
) -> list[str]:
    return row_values(
        NODE_COLUMNS,
        node_fields(
            resid,
            condition=condition,
            resname=resname,
            region=region,
        ),
    )


def edge_fields(
    resid_i: str = "n1",
    resid_j: str = "n2",
    *,
    condition: str = "normal",
    contact_freq: str = "0.75",
    edge_type: str = "residue_contact",
    all_edge_types: str = "residue_contact",
    n_edge_types: str = "1",
) -> dict[str, str]:
    return {
        "resid_i": resid_i,
        "resid_j": resid_j,
        "edge_type": edge_type,
        "all_edge_types": all_edge_types,
        "n_edge_types": n_edge_types,
        "condition": condition,
        "contact_freq": contact_freq,
        "mean_dist_A": "4.2",
    }


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
        edge_fields(
            resid_i,
            resid_j,
            condition=condition,
            contact_freq=contact_freq,
            edge_type=edge_type,
            all_edge_types=all_edge_types,
            n_edge_types=n_edge_types,
        ),
    )


def graph_payload(
    *,
    node_ids: tuple[str, ...] = ("n1", "n2"),
    edge_specs: tuple[dict[str, str], ...] | None = None,
    condition: str = "normal",
    schema_version: str = "0.1",
    directed: bool = False,
    node_overrides: dict[str, dict[str, str]] | None = None,
    edge_overrides: dict[int, dict[str, str]] | None = None,
) -> dict[str, object]:
    node_overrides = node_overrides or {}
    nodes: list[dict[str, str]] = []
    for node_id in node_ids:
        row = {column: "" for column in NODE_COLUMNS}
        row.update(node_fields(node_id, condition=condition))
        row.update(node_overrides.get(node_id, {}))
        nodes.append({"id": row["resid"], **row})

    specs = edge_specs or (
        edge_fields("n1", "n2", condition=condition),
    )
    edge_overrides = edge_overrides or {}
    edges: list[dict[str, str]] = []
    for index, spec in enumerate(specs):
        row = {column: "" for column in EDGE_COLUMNS}
        row.update(spec)
        row.update(edge_overrides.get(index, {}))
        edges.append(
            {
                "source": row["resid_i"],
                "target": row["resid_j"],
                **row,
            }
        )

    return {
        "condition": condition,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "directed": directed,
        "schema_version": schema_version,
        "nodes": nodes,
        "edges": edges,
    }


def write_graph_bundle(
    root: Path,
    *,
    node_ids: tuple[str, ...] = ("n1", "n2"),
    edge_specs: tuple[dict[str, str], ...] | None = None,
    condition: str = "normal",
    schema_version: str = "0.1",
    directed: bool = False,
    node_overrides: dict[str, dict[str, str]] | None = None,
    edge_overrides: dict[int, dict[str, str]] | None = None,
) -> tuple[Path, Path, Path]:
    root.mkdir()
    nodes_path = root / "nodes.csv"
    edges_path = root / "edges.csv"
    graph_path = root / "graph.json"
    write_csv(
        nodes_path,
        NODE_COLUMNS,
        [
            node_row(node_id, condition=condition)
            for node_id in node_ids
        ],
    )
    specs = edge_specs or (
        edge_fields("n1", "n2", condition=condition),
    )
    write_csv(
        edges_path,
        EDGE_COLUMNS,
        [
            row_values(EDGE_COLUMNS, spec)
            for spec in specs
        ],
    )
    graph_path.write_text(
        json.dumps(
            graph_payload(
                node_ids=node_ids,
                edge_specs=specs,
                condition=condition,
                schema_version=schema_version,
                directed=directed,
                node_overrides=node_overrides,
                edge_overrides=edge_overrides,
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
    generated_node_ids: tuple[str, ...] = ("n1", "n2"),
    reference_node_ids: tuple[str, ...] = ("n1", "n2"),
    generated_edge_specs: tuple[dict[str, str], ...] | None = None,
    reference_edge_specs: tuple[dict[str, str], ...] | None = None,
    generated_schema_version: str = "0.1",
    reference_schema_version: str = "0.1",
    generated_directed: bool = False,
    reference_directed: bool = False,
    generated_node_overrides: dict[str, dict[str, str]] | None = None,
    reference_node_overrides: dict[str, dict[str, str]] | None = None,
    generated_edge_overrides: dict[int, dict[str, str]] | None = None,
    reference_edge_overrides: dict[int, dict[str, str]] | None = None,
    options: PreprocessingGraphReferenceComparisonOptions | None = None,
) -> PreprocessingGraphReferenceComparisonInput:
    generated_paths = write_graph_bundle(
        tmp_path / "generated",
        node_ids=generated_node_ids,
        edge_specs=generated_edge_specs,
        schema_version=generated_schema_version,
        directed=generated_directed,
        node_overrides=generated_node_overrides,
        edge_overrides=generated_edge_overrides,
    )
    reference_paths = write_graph_bundle(
        tmp_path / "reference",
        node_ids=reference_node_ids,
        edge_specs=reference_edge_specs,
        schema_version=reference_schema_version,
        directed=reference_directed,
        node_overrides=reference_node_overrides,
        edge_overrides=reference_edge_overrides,
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


def rewrite_nodes(
    path: Path,
    node_ids: tuple[str, ...],
    *,
    overrides: dict[str, dict[str, str]] | None = None,
) -> None:
    overrides = overrides or {}
    write_csv(
        path,
        NODE_COLUMNS,
        [
            row_values(
                NODE_COLUMNS,
                {**node_fields(node_id), **overrides.get(node_id, {})},
            )
            for node_id in node_ids
        ],
    )


def rewrite_edges(
    path: Path,
    edge_specs: tuple[dict[str, str], ...],
) -> None:
    write_csv(
        path,
        EDGE_COLUMNS,
        [row_values(EDGE_COLUMNS, spec) for spec in edge_specs],
    )


def rewrite_graph(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def target_result(
    result: PreprocessingGraphReferenceComparisonResult,
    target: str,
) -> PreprocessingGraphReferenceComparisonTargetResult:
    for item in result.target_results:
        if item.target == target:
            return item
    raise AssertionError(f"missing target result: {target}")


def mismatch_kinds(
    result: PreprocessingGraphReferenceComparisonResult,
    target: str | None = None,
) -> list[str]:
    return [
        mismatch.kind
        for mismatch in result.mismatches
        if target is None or mismatch.target == target
    ]


def docs_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)


def test_public_exports_work() -> None:
    assert PreprocessingGraphReferenceComparisonMismatch is not None
    assert PreprocessingGraphReferenceComparisonTargetResult is not None
    assert PreprocessingGraphReferenceComparisonResult is not None
    assert compare_preprocessing_graph_reference_artifacts is not None


def test_existing_stage_14_3a_exports_still_work() -> None:
    assert PreprocessingGraphReferenceComparisonOptions is not None
    assert PreprocessingGraphReferenceComparisonInput is not None
    assert PreprocessingGraphReferenceComparisonIssue is not None
    assert PreprocessingGraphReferenceComparisonInputValidationResult is not None
    assert validate_preprocessing_graph_reference_comparison_input is not None


def test_existing_stage_14_1_to_14_2_exports_still_work() -> None:
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


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_mismatch_validates_and_serializes() -> None:
    mismatch = PreprocessingGraphReferenceComparisonMismatch(
        kind="field_value_mismatch",
        message="Different.",
        target="nodes_csv",
        key="n1",
        field="resname",
        generated_value="ALA",
        reference_value="GLY",
    )

    assert mismatch.kind == "field_value_mismatch"
    assert_json_safe(mismatch.to_dict())

    for kwargs in (
        {"kind": "", "message": "message", "target": "nodes_csv"},
        {"kind": "kind", "message": "", "target": "nodes_csv"},
        {"kind": "kind", "message": "message", "target": ""},
        {"kind": "kind", "message": "message", "target": "nodes", "key": ""},
        {"kind": "kind", "message": "message", "target": "nodes", "field": ""},
        {
            "kind": "kind",
            "message": "message",
            "target": "nodes",
            "generated_value": {"not": "scalar"},
        },
        {
            "kind": "kind",
            "message": "message",
            "target": "nodes",
            "reference_value": ["not", "scalar"],
        },
        {
            "kind": "kind",
            "message": "message",
            "target": "nodes",
            "generated_value": float("nan"),
        },
    ):
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonMismatch(**kwargs)


def test_target_result_validates_and_serializes() -> None:
    mismatch = PreprocessingGraphReferenceComparisonMismatch(
        kind="count_mismatch",
        message="Different counts.",
        target="nodes_csv",
    )
    target = PreprocessingGraphReferenceComparisonTargetResult(
        target="nodes_csv",
        enabled=True,
        passed=False,
        generated_count=1,
        reference_count=2,
        matched_count=1,
        mismatches=(mismatch,),
    )

    assert target.mismatch_count == 1
    assert_json_safe(target.to_dict())

    valid = {
        "target": "nodes_csv",
        "enabled": True,
        "passed": True,
        "generated_count": 1,
        "reference_count": 1,
        "matched_count": 1,
        "mismatches": (),
    }
    for kwargs in (
        {"target": ""},
        {"enabled": "true"},
        {"passed": 1},
        {"generated_count": -1},
        {"reference_count": True},
        {"matched_count": False},
        {"mismatches": []},
        {"mismatches": (object(),)},
    ):
        params = dict(valid)
        params.update(kwargs)
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonTargetResult(**params)


def test_comparison_result_validates_and_serializes(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    input_validation = validate_preprocessing_graph_reference_comparison_input(
        comparison_input
    )
    target = PreprocessingGraphReferenceComparisonTargetResult(
        target="nodes_csv",
        enabled=True,
        passed=True,
        generated_count=2,
        reference_count=2,
        matched_count=2,
    )
    result = PreprocessingGraphReferenceComparisonResult(
        comparison_input=comparison_input,
        input_validation=input_validation,
        target_results=(target,),
        generated_condition="normal",
        reference_condition="normal",
        generated_schema_version="0.1",
        reference_schema_version="0.1",
    )

    assert result.passed is True
    assert result.target_count == 1
    assert result.failed_target_count == 0
    assert result.mismatch_count == 0
    assert_json_safe(result.to_dict())

    valid = {
        "comparison_input": comparison_input,
        "input_validation": input_validation,
        "target_results": (target,),
    }
    for kwargs in (
        {"comparison_input": object()},
        {"input_validation": object()},
        {"target_results": []},
        {"target_results": (object(),)},
        {"mismatches": []},
        {"mismatches": (object(),)},
        {"reference_semantics": ""},
        {"generated_condition": ""},
    ):
        params = dict(valid)
        params.update(kwargs)
        with pytest.raises(ValueError):
            PreprocessingGraphReferenceComparisonResult(**params)


def test_identical_generated_reference_artifacts_pass(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(make_input(tmp_path))

    assert result.passed is True
    assert result.input_validation.passed is True
    assert result.mismatch_count == 0
    assert target_result(result, "nodes_csv").passed is True
    assert target_result(result, "edges_csv").passed is True
    assert target_result(result, "graph_json").passed is True


def test_input_validation_failure_prevents_comparison(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    comparison_input.reference_graph_json_path.unlink()

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert result.passed is False
    assert result.target_results == ()
    assert mismatch_kinds(result) == ["input_validation_failed"]


def test_nodes_missing_in_generated_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2"),
            reference_node_ids=("n1", "n2", "n3"),
        )
    )

    assert "missing_generated_row" in mismatch_kinds(result, "nodes_csv")


def test_extra_generated_node_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2", "n3"),
            reference_node_ids=("n1", "n2"),
        )
    )

    assert "extra_generated_row" in mismatch_kinds(result, "nodes_csv")


def test_node_field_mismatch_detected(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)
    rewrite_nodes(
        comparison_input.reference_nodes_csv_path,
        ("n1", "n2"),
        overrides={"n1": {"resname": "SER", "region": "loop"}},
    )

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert "field_value_mismatch" in mismatch_kinds(result, "nodes_csv")
    assert any(
        mismatch.field in {"resname", "region"}
        for mismatch in target_result(result, "nodes_csv").mismatches
    )


def test_edges_missing_in_generated_detected(tmp_path: Path) -> None:
    generated_edges = (edge_fields("n1", "n2"),)
    reference_edges = (
        edge_fields("n1", "n2"),
        edge_fields("n2", "n3"),
    )
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2", "n3"),
            reference_node_ids=("n1", "n2", "n3"),
            generated_edge_specs=generated_edges,
            reference_edge_specs=reference_edges,
        )
    )

    assert "missing_generated_row" in mismatch_kinds(result, "edges_csv")


def test_extra_generated_edge_detected(tmp_path: Path) -> None:
    generated_edges = (
        edge_fields("n1", "n2"),
        edge_fields("n2", "n3"),
    )
    reference_edges = (edge_fields("n1", "n2"),)
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2", "n3"),
            reference_node_ids=("n1", "n2", "n3"),
            generated_edge_specs=generated_edges,
            reference_edge_specs=reference_edges,
        )
    )

    assert "extra_generated_row" in mismatch_kinds(result, "edges_csv")


def test_edge_field_mismatch_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_edge_specs=(edge_fields(contact_freq="0.25"),),
            reference_edge_specs=(edge_fields(contact_freq="0.75"),),
        )
    )

    assert "field_value_mismatch" in mismatch_kinds(result, "edges_csv")
    assert any(
        mismatch.field == "contact_freq"
        for mismatch in target_result(result, "edges_csv").mismatches
    )


def test_multi_type_edge_field_mismatch_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_edge_specs=(
                edge_fields(
                    edge_type="hbond",
                    all_edge_types="hbond|hydrophobic",
                    n_edge_types="2",
                ),
            ),
            reference_edge_specs=(
                edge_fields(
                    edge_type="hbond",
                    all_edge_types="hbond|hydrophobic|vdw",
                    n_edge_types="3",
                ),
            ),
        )
    )

    fields = {
        mismatch.field
        for mismatch in target_result(result, "edges_csv").mismatches
    }
    assert {"all_edge_types", "n_edge_types"} <= fields


def test_generic_residue_contact_artifacts_compare_successfully(
    tmp_path: Path,
) -> None:
    result = compare_preprocessing_graph_reference_artifacts(make_input(tmp_path))

    assert result.passed is True


def test_corrected_multi_type_edge_artifacts_compare_successfully(
    tmp_path: Path,
) -> None:
    multi_type_edge = edge_fields(
        edge_type="hbond",
        all_edge_types="hbond|hydrophobic|vdw",
        n_edge_types="3",
    )
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_edge_specs=(multi_type_edge,),
            reference_edge_specs=(multi_type_edge,),
        )
    )

    assert result.passed is True


def test_graph_json_top_level_mismatch_detected(tmp_path: Path) -> None:
    options = PreprocessingGraphReferenceComparisonOptions(
        compare_nodes=False,
        compare_edges=False,
        compare_graph_json=True,
        require_matching_schema_version=False,
    )
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2"),
            reference_node_ids=("n1", "n2", "n3"),
            generated_edge_specs=(edge_fields("n1", "n2"),),
            reference_edge_specs=(
                edge_fields("n1", "n2"),
                edge_fields("n2", "n3"),
            ),
            reference_schema_version="0.2",
            reference_directed=True,
            options=options,
        )
    )

    fields = {
        mismatch.field
        for mismatch in target_result(result, "graph_json").mismatches
        if mismatch.kind == "json_top_level_mismatch"
    }
    assert {"n_nodes", "n_edges", "directed", "schema_version"} <= fields


def test_graph_json_missing_generated_node_detected(tmp_path: Path) -> None:
    options = PreprocessingGraphReferenceComparisonOptions(
        compare_nodes=False,
        compare_edges=False,
        compare_graph_json=True,
    )
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2"),
            reference_node_ids=("n1", "n2", "n3"),
            options=options,
        )
    )

    assert "json_missing_generated_item" in mismatch_kinds(
        result,
        "graph_json",
    )


def test_graph_json_extra_generated_node_detected(tmp_path: Path) -> None:
    options = PreprocessingGraphReferenceComparisonOptions(
        compare_nodes=False,
        compare_edges=False,
        compare_graph_json=True,
    )
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_node_ids=("n1", "n2", "n3"),
            reference_node_ids=("n1", "n2"),
            options=options,
        )
    )

    assert "json_extra_generated_item" in mismatch_kinds(result, "graph_json")


def test_graph_json_node_field_mismatch_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            reference_node_overrides={"n1": {"resname": "SER"}},
        )
    )

    assert any(
        mismatch.kind == "json_field_value_mismatch"
        and mismatch.field == "resname"
        for mismatch in target_result(result, "graph_json").mismatches
    )


def test_graph_json_edge_field_mismatch_detected(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            reference_edge_overrides={0: {"contact_freq": "0.50"}},
        )
    )

    assert any(
        mismatch.kind == "json_field_value_mismatch"
        and mismatch.field == "contact_freq"
        for mismatch in target_result(result, "graph_json").mismatches
    )


def test_graph_json_multi_type_edge_fields_compared(tmp_path: Path) -> None:
    result = compare_preprocessing_graph_reference_artifacts(
        make_input(
            tmp_path,
            generated_edge_specs=(
                edge_fields(
                    edge_type="hbond",
                    all_edge_types="hbond|hydrophobic",
                    n_edge_types="2",
                ),
            ),
            reference_edge_specs=(
                edge_fields(
                    edge_type="hbond",
                    all_edge_types="hbond|hydrophobic|vdw",
                    n_edge_types="3",
                ),
            ),
        )
    )

    fields = {
        mismatch.field
        for mismatch in target_result(result, "graph_json").mismatches
        if mismatch.kind == "json_field_value_mismatch"
    }
    assert {"all_edge_types", "n_edge_types"} <= fields


def test_disabled_nodes_target_is_skipped(tmp_path: Path) -> None:
    comparison_input = make_input(
        tmp_path,
        options=PreprocessingGraphReferenceComparisonOptions(
            compare_nodes=False,
            compare_edges=True,
            compare_graph_json=True,
        ),
    )
    rewrite_nodes(
        comparison_input.generated_nodes_csv_path,
        ("n1", "n2"),
        overrides={"n1": {"resname": "SER"}},
    )

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert result.passed is True
    assert target_result(result, "nodes_csv").enabled is False


def test_disabled_edges_target_is_skipped(tmp_path: Path) -> None:
    comparison_input = make_input(
        tmp_path,
        options=PreprocessingGraphReferenceComparisonOptions(
            compare_nodes=True,
            compare_edges=False,
            compare_graph_json=True,
        ),
    )
    rewrite_edges(
        comparison_input.generated_edges_csv_path,
        (edge_fields(contact_freq="0.25"),),
    )

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert result.passed is True
    assert target_result(result, "edges_csv").enabled is False


def test_disabled_graph_json_target_is_skipped(tmp_path: Path) -> None:
    comparison_input = make_input(
        tmp_path,
        options=PreprocessingGraphReferenceComparisonOptions(
            compare_nodes=True,
            compare_edges=True,
            compare_graph_json=False,
        ),
    )
    rewrite_graph(
        comparison_input.generated_graph_json_path,
        graph_payload(edge_overrides={0: {"contact_freq": "0.25"}}),
    )

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert result.passed is True
    assert target_result(result, "graph_json").enabled is False


def test_comparison_result_is_deterministic(tmp_path: Path) -> None:
    comparison_input = make_input(tmp_path)

    first = compare_preprocessing_graph_reference_artifacts(comparison_input)
    second = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert first.to_dict() == second.to_dict()


def test_mismatch_ordering_is_deterministic(tmp_path: Path) -> None:
    comparison_input = make_input(
        tmp_path,
        generated_node_ids=("n1", "n2", "n4"),
        reference_node_ids=("n1", "n2", "n3"),
        generated_edge_specs=(edge_fields("n1", "n2", contact_freq="0.25"),),
        reference_edge_specs=(edge_fields("n1", "n2", contact_freq="0.75"),),
        reference_node_overrides={"n1": {"resname": "SER"}},
    )

    first = compare_preprocessing_graph_reference_artifacts(comparison_input)
    second = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert first.to_dict() == second.to_dict()
    assert [item.target for item in first.target_results] == [
        "nodes_csv",
        "edges_csv",
        "graph_json",
    ]
    assert [mismatch.target for mismatch in first.mismatches[:3]] == [
        "nodes_csv",
        "nodes_csv",
        "edges_csv",
    ]


def test_comparison_does_not_write_files(tmp_path: Path) -> None:
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

    result = compare_preprocessing_graph_reference_artifacts(comparison_input)

    assert result.passed is True
    assert {path: path.read_text(encoding="utf-8") for path in paths} == before

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in ("write_text", "json.dump", "csv.writer"):
        assert forbidden not in source
    assert 'open("w"' not in source
    assert "open('w'" not in source


def test_comparison_does_not_run_diagnostics() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "compute_graph_qc",
    ):
        assert forbidden not in source


def test_comparison_does_not_call_cli_or_workflow() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("mania.cli", "pipeline", "workflow"):
        assert forbidden not in source


def test_comparison_does_not_implement_temporal_rin() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "temporal_rin" not in source
    assert "temporal RIN export" not in source


def test_comparison_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_comparison_uses_stage_14_3a_input_validation() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "validate_preprocessing_graph_reference_comparison_input(" in source


def test_docs_state_stage_14_3b_boundary() -> None:
    text = docs_text()

    for phrase in (
        "Stage 14.3b",
        "compares generated graph artifacts with notebook reference artifacts v1.2",
        "uses Stage 14.3a input contract",
        "expected mismatch documentation remains Stage 14.4a",
    ):
        assert phrase in text


def test_docs_preserve_v1_2_reference_semantics() -> None:
    text = docs_text()

    for phrase in (
        "MANIA_analysis_v1_2",
        "v1.1 historical reference",
        "v1.2 Cell 5 interaction priority",
        "v1.2 Cell 12 temporal RIN export fix",
        "temporal RIN export remains future scope",
    ):
        assert phrase in text


def test_docs_preserve_multi_type_edge_semantics() -> None:
    text = docs_text()

    for phrase in (
        "edge_type",
        "all_edge_types",
        "n_edge_types",
        "EDGE_TYPE_PRIORITY",
    ):
        assert phrase in text
    assert EDGE_TYPE_PRIORITY is not None


def test_docs_preserve_contact_edges_boundary() -> None:
    text = docs_text()

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        (
            "backend graph edges.csv, graph.json, diagnostics, and "
            "comparison are Stage 14 graph artifacts"
        ),
    ):
        assert phrase in text
