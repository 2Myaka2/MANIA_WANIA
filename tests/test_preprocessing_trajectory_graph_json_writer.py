import ast
import csv
import inspect
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS, GRAPH_REQUIRED_KEYS, NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphEdgesCsvWriteIssue,
    PreprocessingGraphEdgesCsvWriteResult,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphJsonWriteIssue,
    PreprocessingGraphJsonWriteResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingGraphNodesCsvWriteIssue,
    PreprocessingGraphNodesCsvWriteResult,
    build_preprocessing_graph_export_mapping,
    validate_preprocessing_graph_csvs,
    write_preprocessing_graph_edges_csv,
    write_preprocessing_graph_json,
    write_preprocessing_graph_nodes_csv,
)
from mania.preprocessing import trajectory_graph_export as graph_export

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
        "contact_freq": "0.75",
        "mean_dist_A": "4.2",
    }
    values.update(overrides)
    return row_values(EDGE_COLUMNS, values)


def write_valid_csvs(
    tmp_path: Path,
    *,
    node_rows: list[list[str]] | None = None,
    edge_rows: list[list[str]] | None = None,
) -> tuple[Path, Path]:
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
    return nodes_path, edges_path


def read_graph(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def issue_kinds(result: PreprocessingGraphJsonWriteResult) -> list[str]:
    return [issue.kind for issue in result.issues]


def node_record(
    node_id: str,
    *,
    condition_name: str = "normal",
    residue_index: int = 1,
    residue_id: str = "10",
    resname: str = "ALA",
    segid: str | None = "A",
) -> PreprocessingGraphNodeMappingRecord:
    return PreprocessingGraphNodeMappingRecord(
        node_id=node_id,
        condition_name=condition_name,
        residue_index=residue_index,
        residue_id=residue_id,
        resname=resname,
        segid=segid,
    )


def writer_generated_csvs(tmp_path: Path) -> tuple[Path, Path]:
    source = node_record("normal|A|1|10|ALA")
    target = node_record(
        "normal|B|2|20|GLY",
        residue_index=2,
        residue_id="20",
        resname="GLY",
        segid="B",
    )
    edge = PreprocessingGraphEdgeMappingRecord(
        edge_id="edge-1",
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        condition_name="normal",
        edge_kind="residue_contact",
        contact_frame_count=2,
        total_frame_count=4,
        contact_frequency=0.5,
        minimum_distance=2.0,
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
    assert write_preprocessing_graph_nodes_csv(mapping, nodes_path).passed is True
    assert write_preprocessing_graph_edges_csv(mapping, edges_path).passed is True
    return nodes_path, edges_path


def test_public_exports_work() -> None:
    assert PreprocessingGraphJsonWriteIssue is not None
    assert PreprocessingGraphJsonWriteResult is not None
    assert write_preprocessing_graph_json is not None


def test_existing_stage_14_1a_through_14_1d_exports_still_work() -> None:
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


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphJsonWriteIssue(
        kind="validation_failed",
        message="Validation failed.",
        field="validation.issues",
        csv_kind="edges",
        row_number=2,
    )

    assert issue.kind == "validation_failed"
    assert issue.csv_kind == "edges"
    assert_json_safe(issue.to_dict())

    invalid_kwargs = (
        {"kind": "", "message": "message"},
        {"kind": "kind", "message": ""},
        {"kind": "kind", "message": "message", "row_number": 0},
        {"kind": "kind", "message": "message", "row_number": True},
        {"kind": "kind", "message": "message", "field": ""},
        {"kind": "kind", "message": "message", "csv_kind": " "},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphJsonWriteIssue(**kwargs)


def test_write_result_validates_and_serializes() -> None:
    result = PreprocessingGraphJsonWriteResult(
        output_path=Path("graph.json"),
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        node_count=2,
        edge_count=1,
        validation_passed=True,
        validation_issue_count=0,
    )

    assert result.passed is True
    assert result.issue_count == 0
    assert result.node_count == 2
    assert result.edge_count == 1
    assert result.to_dict()["output_path"] == "graph.json"
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"node_count": -1, "edge_count": 0},
        {"node_count": True, "edge_count": 0},
        {"node_count": 0, "edge_count": -1},
        {"node_count": 0, "edge_count": False},
        {"node_count": 0, "edge_count": 0, "issues": ("not-an-issue",)},
        {"node_count": 0, "edge_count": 0, "issues": []},
        {"node_count": 0, "edge_count": 0, "validation_passed": "yes"},
        {"node_count": 0, "edge_count": 0, "validation_issue_count": -1},
        {"node_count": 0, "edge_count": 0, "validation_issue_count": True},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphJsonWriteResult(
                output_path=Path("graph.json"),
                nodes_csv_path=Path("nodes.csv"),
                edges_csv_path=Path("edges.csv"),
                **kwargs,
            )


def test_writer_creates_graph_json_from_header_only_csvs(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    output_path = tmp_path / "graph.json"
    write_csv(nodes_path, NODE_COLUMNS)
    write_csv(edges_path, EDGE_COLUMNS)

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    graph = read_graph(output_path)

    assert result.passed is True
    assert result.node_count == 0
    assert result.edge_count == 0
    assert tuple(graph) == GRAPH_REQUIRED_KEYS
    assert graph["condition"] == ""
    assert graph["n_nodes"] == 0
    assert graph["n_edges"] == 0
    assert graph["directed"] is False
    assert graph["schema_version"] == "0.1"
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_writer_creates_graph_json_from_writer_generated_csvs(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path = writer_generated_csvs(tmp_path)
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    graph = read_graph(output_path)

    assert result.passed is True
    assert result.node_count == 2
    assert result.edge_count == 1
    assert graph["condition"] == "normal"
    nodes = graph["nodes"]
    edges = graph["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert nodes[0]["id"] == "normal|A|1|10|ALA"
    for column in NODE_COLUMNS:
        assert column in nodes[0]
    assert edges[0]["source"] == "normal|A|1|10|ALA"
    assert edges[0]["target"] == "normal|B|2|20|GLY"
    for column in EDGE_COLUMNS:
        assert column in edges[0]


def test_writer_calls_validation_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path, edge_rows=[edge_row()])
    output_path = tmp_path / "graph.json"
    calls: list[str] = []

    def fake_validate(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
    ) -> PreprocessingGraphCsvValidationResult:
        calls.append("validate")
        return PreprocessingGraphCsvValidationResult(
            nodes_csv_path=Path(nodes_csv_path),
            edges_csv_path=Path(edges_csv_path),
            node_count=2,
            edge_count=1,
        )

    def fake_write(
        output: Path,
        graph: dict[str, object],
    ) -> PreprocessingGraphJsonWriteIssue | None:
        calls.append("write")
        output.write_text(json.dumps(graph), encoding="utf-8")
        return None

    monkeypatch.setattr(
        graph_export,
        "validate_preprocessing_graph_csvs",
        fake_validate,
    )
    monkeypatch.setattr(graph_export, "_write_graph_payload", fake_write)

    result = graph_export.write_preprocessing_graph_json(
        nodes_path,
        edges_path,
        output_path,
    )

    assert result.passed is True
    assert calls == ["validate", "write"]


def test_writer_refuses_to_write_when_validation_fails(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(
        tmp_path,
        edge_rows=[edge_row(resid_j="missing")],
    )
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)

    assert result.passed is False
    assert issue_kinds(result) == ["validation_failed"]
    assert result.validation_passed is False
    assert not output_path.exists()


def test_writer_refuses_old_edges_schema(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    output_path = tmp_path / "graph.json"
    write_csv(
        nodes_path,
        NODE_COLUMNS,
        [node_row(resid="n1"), node_row(resid="n2")],
    )
    old_header = tuple(
        column
        for column in EDGE_COLUMNS
        if column not in {"all_edge_types", "n_edge_types"}
    )
    write_csv(edges_path, old_header)

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)

    assert result.passed is False
    assert issue_kinds(result) == ["validation_failed"]
    assert not output_path.exists()


def test_writer_preserves_multi_type_edge_fields(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(
        tmp_path,
        edge_rows=[
            edge_row(
                edge_type="hbond",
                all_edge_types="hbond|hydrophobic|vdw",
                n_edge_types="3",
            )
        ],
    )
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    edge = read_graph(output_path)["edges"][0]

    assert result.passed is True
    assert edge["edge_type"] == "hbond"
    assert edge["all_edge_types"] == "hbond|hydrophobic|vdw"
    assert edge["n_edge_types"] == "3"


def test_writer_preserves_generic_residue_contact_edge(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path, edge_rows=[edge_row()])
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    edge = read_graph(output_path)["edges"][0]

    assert result.passed is True
    assert edge["edge_type"] == "residue_contact"
    assert edge["all_edge_types"] == "residue_contact"
    assert edge["n_edge_types"] == "1"


def test_writer_preserves_contact_freq_and_mean_dist_a(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(
        tmp_path,
        edge_rows=[edge_row(contact_freq="0.60", mean_dist_A="4.5")],
    )
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    edge = read_graph(output_path)["edges"][0]

    assert result.passed is True
    assert edge["contact_freq"] == "0.60"
    assert edge["mean_dist_A"] == "4.5"


def test_writer_preserves_empty_optional_metadata(tmp_path: Path) -> None:
    nodes_path, edges_path = writer_generated_csvs(tmp_path)
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)
    graph = read_graph(output_path)
    edge = graph["edges"][0]
    node = graph["nodes"][0]

    assert result.passed is True
    assert node["x_ca"] == ""
    assert edge["std_dist_A"] == ""
    assert edge["n_episodes"] == ""
    assert edge["window_cv"] == ""


def test_writer_output_is_deterministic(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path, edge_rows=[edge_row()])
    first_path = tmp_path / "first.graph.json"
    second_path = tmp_path / "second.graph.json"

    first = write_preprocessing_graph_json(nodes_path, edges_path, first_path)
    second = write_preprocessing_graph_json(nodes_path, edges_path, second_path)

    assert first.passed is True
    assert second.passed is True
    assert first_path.read_bytes() == second_path.read_bytes()


def test_writer_fails_on_missing_nodes_file(tmp_path: Path) -> None:
    _, edges_path = write_valid_csvs(tmp_path, edge_rows=[edge_row()])
    missing_nodes_path = tmp_path / "missing_nodes.csv"
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(
        missing_nodes_path,
        edges_path,
        output_path,
    )

    assert result.passed is False
    assert issue_kinds(result) == ["validation_failed"]
    assert not output_path.exists()


def test_writer_fails_on_missing_edges_file(tmp_path: Path) -> None:
    nodes_path, _ = write_valid_csvs(tmp_path)
    missing_edges_path = tmp_path / "missing_edges.csv"
    output_path = tmp_path / "graph.json"

    result = write_preprocessing_graph_json(
        nodes_path,
        missing_edges_path,
        output_path,
    )

    assert result.passed is False
    assert issue_kinds(result) == ["validation_failed"]
    assert not output_path.exists()


def test_writer_fails_when_output_path_is_directory(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path)

    result = write_preprocessing_graph_json(nodes_path, edges_path, tmp_path)

    assert result.passed is False
    assert issue_kinds(result) == ["output_path_is_directory"]


def test_writer_fails_when_output_parent_directory_is_missing(
    tmp_path: Path,
) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path)
    output_path = tmp_path / "missing" / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)

    assert result.passed is False
    assert issue_kinds(result) == ["parent_directory_missing"]
    assert not output_path.parent.exists()


def test_writer_does_not_create_missing_parent_directories(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path)
    output_path = tmp_path / "missing" / "nested" / "graph.json"

    result = write_preprocessing_graph_json(nodes_path, edges_path, output_path)

    assert result.passed is False
    assert not output_path.parents[0].exists()
    assert not output_path.parents[1].exists()


def test_writer_fails_on_invalid_output_path_type(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path)

    result = write_preprocessing_graph_json(nodes_path, edges_path, 123)  # type: ignore[arg-type]

    assert result.passed is False
    assert issue_kinds(result) == ["invalid_output_path"]


def test_writer_does_not_mutate_input_csvs(tmp_path: Path) -> None:
    nodes_path, edges_path = write_valid_csvs(tmp_path, edge_rows=[edge_row()])
    before = {
        nodes_path: nodes_path.read_text(encoding="utf-8"),
        edges_path: edges_path.read_text(encoding="utf-8"),
    }

    result = write_preprocessing_graph_json(
        nodes_path,
        edges_path,
        tmp_path / "graph.json",
    )

    assert result.passed is True
    assert nodes_path.read_text(encoding="utf-8") == before[nodes_path]
    assert edges_path.read_text(encoding="utf-8") == before[edges_path]


def test_writer_does_not_call_stage_13_contacts_code() -> None:
    implementation = inspect.getsource(write_preprocessing_graph_json)

    for forbidden in (
        "write_contact_edges_csv",
        "validate_contact_edges_csv",
        "compute_condition_contacts",
        "compute_manifest_contacts",
    ):
        assert forbidden not in implementation


def test_writer_does_not_call_mapping_builder_or_csv_writers() -> None:
    tree = ast.parse(inspect.getsource(write_preprocessing_graph_json))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "build_preprocessing_graph_export_mapping" not in call_names
    assert "write_preprocessing_graph_nodes_csv" not in call_names
    assert "write_preprocessing_graph_edges_csv" not in call_names


def test_writer_does_not_run_diagnostics_or_comparison() -> None:
    implementation = inspect.getsource(write_preprocessing_graph_json)

    for forbidden in (
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "GraphDiagnostics",
        "compare_contract_subset",
        "compare_artifact_sets",
        "compare_contacts_outputs",
    ):
        assert forbidden not in implementation


def test_writer_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_writer_uses_validation_api() -> None:
    tree = ast.parse(inspect.getsource(write_preprocessing_graph_json))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "validate_preprocessing_graph_csvs" in call_names


def test_docs_state_stage_14_1e_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.1e",
        "graph.json writer",
        "accepted/validated nodes.csv + corrected edges.csv",
        "graph export bundle remains Stage 14.1f",
        "diagnostics remain Stage 14.2a",
    ):
        assert phrase in text


def test_docs_mention_multi_type_edge_json_preservation() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "graph JSON preserves",
        "edge_type",
        "all_edge_types",
        "n_edge_types",
    ):
        assert phrase in text


def test_docs_preserve_contact_edges_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv and graph.json are Stage 14 graph artifacts",
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
