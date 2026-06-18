import ast
import csv
import inspect
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS, EDGE_TYPE_PRIORITY, NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphEdgesCsvWriteIssue,
    PreprocessingGraphEdgesCsvWriteResult,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingGraphNodesCsvWriteIssue,
    PreprocessingGraphNodesCsvWriteResult,
    build_preprocessing_graph_export_mapping,
    validate_preprocessing_graph_csvs,
    write_preprocessing_graph_edges_csv,
    write_preprocessing_graph_nodes_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "preprocessing" / (
    "trajectory_graph_export.py"
)
DOC_PATHS = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md",
    REPO_ROOT / "docs" / "preprocessing_contacts_export.md",
    REPO_ROOT / "docs" / "adr" / "0001-optional-scientific-dependencies.md",
)


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def write_csv(
    path: Path,
    header: tuple[str, ...],
    rows: list[list[str]] | None = None,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows or [])


def row_values(
    columns: tuple[str, ...],
    values: dict[str, str],
) -> list[str]:
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


def write_valid_nodes(path: Path) -> None:
    write_csv(
        path,
        NODE_COLUMNS,
        [
            node_row(resid="n1", resname="ALA"),
            node_row(resid="n2", resname="GLY"),
        ],
    )


def write_valid_edges(path: Path, rows: list[list[str]] | None = None) -> None:
    write_csv(path, EDGE_COLUMNS, rows or [edge_row()])


def validate_files(
    tmp_path: Path,
    *,
    node_rows: list[list[str]] | None = None,
    edge_rows: list[list[str]] | None = None,
) -> PreprocessingGraphCsvValidationResult:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    write_csv(
        nodes_path,
        NODE_COLUMNS,
        node_rows
        if node_rows is not None
        else [
            node_row(resid="n1", resname="ALA"),
            node_row(resid="n2", resname="GLY"),
        ],
    )
    write_csv(edges_path, EDGE_COLUMNS, edge_rows if edge_rows is not None else [])
    return validate_preprocessing_graph_csvs(nodes_path, edges_path)


def issue_kinds(
    result: PreprocessingGraphCsvValidationResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def assert_has_issue(
    result: PreprocessingGraphCsvValidationResult,
    kind: str,
    *,
    csv_kind: str | None = None,
    column: str | None = None,
) -> None:
    assert any(
        issue.kind == kind
        and (csv_kind is None or issue.csv_kind == csv_kind)
        and (column is None or issue.column == column)
        for issue in result.issues
    )


def test_public_exports_work() -> None:
    assert PreprocessingGraphCsvValidationIssue is not None
    assert PreprocessingGraphCsvValidationResult is not None
    assert validate_preprocessing_graph_csvs is not None


def test_existing_graph_exports_still_work() -> None:
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
    assert EDGE_COLUMNS[:5] == (
        "resid_i",
        "resid_j",
        "edge_type",
        "all_edge_types",
        "n_edge_types",
    )
    assert EDGE_TYPE_PRIORITY == (
        "hbond",
        "disulfide",
        "salt_bridge",
        "ionic",
        "cation_pi",
        "aromatic_pi",
        "hydrophobic",
        "vdw",
    )


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphCsvValidationIssue(
        kind="missing_required_value",
        message="Required value is missing.",
        csv_kind="nodes",
        row_number=2,
        column="resid",
        value="",
    )

    assert issue.kind == "missing_required_value"
    assert issue.value == ""
    assert_json_safe(issue.to_dict())

    invalid_kwargs = (
        {"kind": "", "message": "message"},
        {"kind": "kind", "message": ""},
        {"kind": "kind", "message": "message", "row_number": 0},
        {"kind": "kind", "message": "message", "row_number": True},
        {"kind": "kind", "message": "message", "csv_kind": ""},
        {"kind": "kind", "message": "message", "column": " "},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphCsvValidationIssue(**kwargs)


def test_validation_result_validates_and_serializes() -> None:
    result = PreprocessingGraphCsvValidationResult(
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        node_count=2,
        edge_count=1,
    )

    assert result.passed is True
    assert result.issue_count == 0
    assert result.node_count == 2
    assert result.edge_count == 1
    assert result.to_dict()["nodes_csv_path"] == "nodes.csv"
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"node_count": -1, "edge_count": 0},
        {"node_count": True, "edge_count": 0},
        {"node_count": 0, "edge_count": -1},
        {"node_count": 0, "edge_count": False},
        {"node_count": 0, "edge_count": 0, "issues": ("not-an-issue",)},
        {"node_count": 0, "edge_count": 0, "issues": []},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphCsvValidationResult(
                nodes_csv_path=Path("nodes.csv"),
                edges_csv_path=Path("edges.csv"),
                **kwargs,
            )


def test_header_only_nodes_and_edges_pass(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    write_csv(nodes_path, NODE_COLUMNS)
    write_csv(edges_path, EDGE_COLUMNS)

    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)

    assert result.passed is True
    assert result.node_count == 0
    assert result.edge_count == 0


def test_writer_generated_nodes_and_corrected_edges_pass(tmp_path: Path) -> None:
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
        edge_kind="hydrophobic",
        all_edge_types=("vdw", "hbond", "hydrophobic"),
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

    nodes_write = write_preprocessing_graph_nodes_csv(mapping, nodes_path)
    edges_write = write_preprocessing_graph_edges_csv(mapping, edges_path)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)

    assert nodes_write.passed is True
    assert edges_write.passed is True
    assert result.passed is True
    assert result.node_count == nodes_write.rows_written
    assert result.edge_count == edges_write.rows_written


def test_missing_and_directory_paths_fail(tmp_path: Path) -> None:
    edges_path = tmp_path / "edges.csv"
    write_valid_edges(edges_path)

    missing_nodes = validate_preprocessing_graph_csvs(
        tmp_path / "missing_nodes.csv",
        edges_path,
    )
    assert_has_issue(missing_nodes, "path_missing", csv_kind="nodes")

    nodes_path = tmp_path / "nodes.csv"
    write_valid_nodes(nodes_path)
    missing_edges = validate_preprocessing_graph_csvs(
        nodes_path,
        tmp_path / "missing_edges.csv",
    )
    assert_has_issue(missing_edges, "path_missing", csv_kind="edges")

    directory_nodes = validate_preprocessing_graph_csvs(tmp_path, edges_path)
    assert_has_issue(directory_nodes, "path_is_directory", csv_kind="nodes")


def test_invalid_path_type_fails(tmp_path: Path) -> None:
    edges_path = tmp_path / "edges.csv"
    write_valid_edges(edges_path)

    result = validate_preprocessing_graph_csvs(123, edges_path)  # type: ignore[arg-type]

    assert_has_issue(result, "invalid_path", csv_kind="nodes")


def test_invalid_headers_fail(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"

    write_csv(nodes_path, ("wrong",))
    write_valid_edges(edges_path)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)
    assert_has_issue(result, "invalid_header", csv_kind="nodes")

    write_valid_nodes(nodes_path)
    old_edge_header = tuple(
        column
        for column in EDGE_COLUMNS
        if column not in {"all_edge_types", "n_edge_types"}
    )
    write_csv(edges_path, old_edge_header)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)
    assert_has_issue(result, "invalid_header", csv_kind="edges")

    wrong_order = (
        "resid_i",
        "resid_j",
        "all_edge_types",
        "edge_type",
        *EDGE_COLUMNS[4:],
    )
    write_csv(edges_path, wrong_order)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)
    assert_has_issue(result, "invalid_header", csv_kind="edges")


def test_row_column_count_mismatches_fail(tmp_path: Path) -> None:
    result = validate_files(
        tmp_path,
        node_rows=[node_row()[:-1], [*node_row(), "extra"]],
    )
    assert_has_issue(result, "row_column_count_mismatch", csv_kind="nodes")

    result = validate_files(
        tmp_path,
        edge_rows=[edge_row()[:-1], [*edge_row(), "extra"]],
    )
    assert_has_issue(result, "row_column_count_mismatch", csv_kind="edges")


@pytest.mark.parametrize(
    ("overrides", "column"),
    (
        ({"resid": ""}, "resid"),
        ({"resname": ""}, "resname"),
        ({"condition": ""}, "condition"),
    ),
)
def test_missing_node_required_values_fail(
    tmp_path: Path,
    overrides: dict[str, str],
    column: str,
) -> None:
    result = validate_files(tmp_path, node_rows=[node_row(**overrides)])

    assert_has_issue(result, "missing_required_value", csv_kind="nodes", column=column)


def test_duplicate_node_id_fails(tmp_path: Path) -> None:
    result = validate_files(
        tmp_path,
        node_rows=[
            node_row(resid="n1"),
            node_row(resid="n1", resname="GLY"),
        ],
    )

    assert_has_issue(result, "duplicate_node_id", csv_kind="nodes")


def test_edge_endpoint_self_edge_and_required_values_fail(tmp_path: Path) -> None:
    result = validate_files(
        tmp_path,
        edge_rows=[
            edge_row(resid_j="missing"),
            edge_row(resid_i="n1", resid_j="n1"),
            edge_row(edge_type=""),
            edge_row(all_edge_types=""),
            edge_row(n_edge_types=""),
            edge_row(condition=""),
        ],
    )

    for kind in (
        "edge_endpoint_missing",
        "self_edge",
        "missing_required_value",
    ):
        assert_has_issue(result, kind, csv_kind="edges")


def test_duplicate_edge_key_fails(tmp_path: Path) -> None:
    result = validate_files(tmp_path, edge_rows=[edge_row(), edge_row()])

    assert_has_issue(result, "duplicate_edge_key", csv_kind="edges")


@pytest.mark.parametrize(
    ("overrides", "kind"),
    (
        (
            {"edge_type": "hbond", "all_edge_types": "hydrophobic|vdw"},
            "edge_type_not_in_all_edge_types",
        ),
        (
            {
                "edge_type": "hbond",
                "all_edge_types": "hbond||vdw",
                "n_edge_types": "2",
            },
            "empty_edge_type_value",
        ),
        (
            {
                "edge_type": "hbond",
                "all_edge_types": "hbond|hbond|vdw",
                "n_edge_types": "2",
            },
            "duplicate_edge_type_value",
        ),
        (
            {
                "edge_type": "hbond",
                "all_edge_types": "hydrophobic|hbond|vdw",
                "n_edge_types": "3",
            },
            "invalid_edge_type_order",
        ),
        (
            {
                "edge_type": "hydrophobic",
                "all_edge_types": "hbond|hydrophobic|vdw",
                "n_edge_types": "3",
            },
            "invalid_primary_edge_type",
        ),
        (
            {
                "edge_type": "vdw",
                "all_edge_types": "vdw|residue_contact|custom_a",
                "n_edge_types": "3",
            },
            "invalid_edge_type_order",
        ),
        (
            {
                "edge_type": "hbond",
                "all_edge_types": "hbond|vdw",
                "n_edge_types": "3",
            },
            "invalid_edge_type_count",
        ),
    ),
)
def test_multi_type_edge_semantics_fail_deterministically(
    tmp_path: Path,
    overrides: dict[str, str],
    kind: str,
) -> None:
    result = validate_files(tmp_path, edge_rows=[edge_row(**overrides)])

    assert_has_issue(result, kind, csv_kind="edges")


def test_unknown_edge_types_are_allowed_after_known_types_alphabetically(
    tmp_path: Path,
) -> None:
    result = validate_files(
        tmp_path,
        edge_rows=[
            edge_row(
                edge_type="vdw",
                all_edge_types="vdw|custom_a|custom_b|residue_contact",
                n_edge_types="4",
            )
        ],
    )

    assert result.passed is True


@pytest.mark.parametrize("value", ("0", "-1", "1.5", "abc"))
def test_n_edge_types_must_be_positive_integer(
    tmp_path: Path,
    value: str,
) -> None:
    result = validate_files(tmp_path, edge_rows=[edge_row(n_edge_types=value)])

    assert_has_issue(result, "invalid_integer_value", csv_kind="edges")


def test_current_generic_residue_contact_edge_passes(tmp_path: Path) -> None:
    result = validate_files(tmp_path, edge_rows=[edge_row()])

    assert result.passed is True


@pytest.mark.parametrize(
    ("node_overrides", "edge_overrides", "kind"),
    (
        ({"x_ca": "not-a-number"}, {}, "invalid_numeric_value"),
        ({}, {"contact_freq": "nan"}, "invalid_numeric_value"),
        ({}, {"contact_freq": "inf"}, "invalid_numeric_value"),
        ({"kcore": "1.5"}, {}, "invalid_integer_value"),
        ({}, {"n_episodes": "x"}, "invalid_integer_value"),
    ),
)
def test_optional_numeric_fields_validate_when_present(
    tmp_path: Path,
    node_overrides: dict[str, str],
    edge_overrides: dict[str, str],
    kind: str,
) -> None:
    result = validate_files(
        tmp_path,
        node_rows=[
            node_row(resid="n1", **node_overrides),
            node_row(resid="n2"),
        ],
        edge_rows=[edge_row(**edge_overrides)],
    )

    assert_has_issue(result, kind)


def test_empty_optional_numeric_fields_pass(tmp_path: Path) -> None:
    result = validate_files(tmp_path, edge_rows=[edge_row()])

    assert result.passed is True


def test_header_only_cross_file_behavior(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"

    write_csv(nodes_path, NODE_COLUMNS)
    write_valid_edges(edges_path)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)
    assert_has_issue(result, "edge_endpoint_missing", csv_kind="edges")

    write_valid_nodes(nodes_path)
    write_csv(edges_path, EDGE_COLUMNS)
    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)
    assert result.passed is True
    assert result.node_count == 2
    assert result.edge_count == 0


def test_validation_does_not_write_files(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    write_valid_nodes(nodes_path)
    write_valid_edges(edges_path)
    before = {
        nodes_path: nodes_path.read_text(encoding="utf-8"),
        edges_path: edges_path.read_text(encoding="utf-8"),
    }

    result = validate_preprocessing_graph_csvs(nodes_path, edges_path)

    assert result.passed is True
    assert nodes_path.read_text(encoding="utf-8") == before[nodes_path]
    assert edges_path.read_text(encoding="utf-8") == before[edges_path]


def test_validation_source_stays_read_only_and_boundary_only() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    implementation = source[
        source.index("def validate_preprocessing_graph_csvs") : source.index(
            "def _condition_results"
        )
    ]

    for forbidden in (
        "csv.writer",
        "open(",
        "write_text",
        "json.dump",
        "write_graph_json",
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "GraphDiagnostics",
        "validate_contact_edges_csv",
    ):
        assert forbidden not in implementation


def test_validation_function_does_not_call_forbidden_apis() -> None:
    tree = ast.parse(inspect.getsource(validate_preprocessing_graph_csvs))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "json" not in call_names
    assert "write_graph_json" not in call_names
    assert "validate_contact_edges_csv" not in call_names


def test_validation_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_docs_state_stage_14_1d_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.1d",
        "graph CSV validation boundary",
        "validates generated nodes.csv and corrected edges.csv",
        "corrected edges.csv includes all_edge_types and n_edge_types",
        "graph.json remains Stage 14.1e",
        "diagnostics remain Stage 14.2a",
    ):
        assert phrase in text


def test_docs_preserve_contact_edges_and_v1_2_boundaries() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv is separate graph artifact",
        "MANIA_analysis_v1_2",
        "v1.2 Cell 5 interaction priority",
        "v1.2 Cell 12 temporal RIN export fix",
        "temporal RIN export remains future scope",
    ):
        assert phrase in text
