import ast
import csv
import inspect
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
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
        "contact_freq": "0.75",
        "mean_dist_A": "4.2",
    }
    values.update(overrides)
    return row_values(EDGE_COLUMNS, values)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def valid_graph_payload(
    *,
    nodes: list[dict[str, str]] | None = None,
    edges: list[dict[str, str]] | None = None,
    n_nodes: int | None = None,
    n_edges: int | None = None,
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
                "contact_freq": "0.75",
                "mean_dist_A": "4.2",
            }
        )
        graph_edges = [edge]
    return {
        "condition": condition,
        "n_nodes": len(graph_nodes) if n_nodes is None else n_nodes,
        "n_edges": len(graph_edges) if n_edges is None else n_edges,
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


def issue_kinds(result: PreprocessingGraphExportBundleResult) -> list[str]:
    return [issue.kind for issue in result.issues]


def build_valid_bundle(tmp_path: Path) -> PreprocessingGraphExportBundleResult:
    nodes_path, edges_path, graph_path = writer_generated_bundle_files(tmp_path)
    return build_preprocessing_graph_export_bundle(
        nodes_path,
        edges_path,
        graph_path,
    )


def test_public_exports_work() -> None:
    assert PreprocessingGraphExportBundleArtifact is not None
    assert PreprocessingGraphExportBundleIssue is not None
    assert PreprocessingGraphExportBundleResult is not None
    assert build_preprocessing_graph_export_bundle is not None


def test_existing_stage_14_1a_through_14_1e_exports_still_work() -> None:
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


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_artifact_record_validates_and_serializes() -> None:
    artifact = PreprocessingGraphExportBundleArtifact(
        kind="nodes_csv",
        path=Path("nodes.csv"),
        exists=True,
        size_bytes=10,
    )

    assert artifact.kind == "nodes_csv"
    assert artifact.to_dict()["path"] == "nodes.csv"
    assert_json_safe(artifact.to_dict())

    invalid_kwargs = (
        {"kind": "", "path": Path("nodes.csv"), "exists": True},
        {"kind": "nodes_csv", "path": "nodes.csv", "exists": True},
        {"kind": "nodes_csv", "path": Path("nodes.csv"), "exists": "yes"},
        {
            "kind": "nodes_csv",
            "path": Path("nodes.csv"),
            "exists": True,
            "size_bytes": -1,
        },
        {
            "kind": "nodes_csv",
            "path": Path("nodes.csv"),
            "exists": True,
            "size_bytes": True,
        },
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphExportBundleArtifact(**kwargs)


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphExportBundleIssue(
        kind="path_missing",
        message="Missing.",
        artifact_kind="graph_json",
        field="path",
        value="",
    )

    assert issue.value == ""
    assert_json_safe(issue.to_dict())

    invalid_kwargs = (
        {"kind": "", "message": "message"},
        {"kind": "kind", "message": ""},
        {"kind": "kind", "message": "message", "artifact_kind": ""},
        {"kind": "kind", "message": "message", "field": " "},
    )
    for kwargs in invalid_kwargs:
        with pytest.raises(ValueError):
            PreprocessingGraphExportBundleIssue(**kwargs)


def test_result_validates_and_serializes() -> None:
    artifact = PreprocessingGraphExportBundleArtifact(
        kind="nodes_csv",
        path=Path("nodes.csv"),
        exists=True,
    )
    result = PreprocessingGraphExportBundleResult(
        nodes_csv_path=Path("nodes.csv"),
        edges_csv_path=Path("edges.csv"),
        graph_json_path=Path("graph.json"),
        artifacts=(artifact,),
        node_count=2,
        edge_count=1,
        schema_version="0.1",
        condition="normal",
        csv_validation_passed=True,
        csv_validation_issue_count=0,
    )

    assert result.passed is True
    assert result.artifact_count == 1
    assert result.to_dict()["nodes_csv_path"] == "nodes.csv"
    assert_json_safe(result.to_dict())

    invalid_kwargs = (
        {"node_count": -1, "edge_count": 0},
        {"node_count": True, "edge_count": 0},
        {"node_count": 0, "edge_count": -1},
        {"node_count": 0, "edge_count": False},
        {"node_count": 0, "edge_count": 0, "artifacts": ("bad",)},
        {"node_count": 0, "edge_count": 0, "artifacts": []},
        {
            "node_count": 0,
            "edge_count": 0,
            "issues": ("bad",),
        },
        {
            "node_count": 0,
            "edge_count": 0,
            "csv_validation_issue_count": -1,
        },
        {
            "node_count": 0,
            "edge_count": 0,
            "csv_validation_issue_count": True,
        },
    )
    for kwargs in invalid_kwargs:
        base_artifacts = kwargs.pop("artifacts", (artifact,))
        with pytest.raises(ValueError):
            PreprocessingGraphExportBundleResult(
                nodes_csv_path=Path("nodes.csv"),
                edges_csv_path=Path("edges.csv"),
                graph_json_path=Path("graph.json"),
                artifacts=base_artifacts,
                **kwargs,
            )


def test_valid_writer_generated_artifacts_produce_passing_bundle(
    tmp_path: Path,
) -> None:
    result = build_valid_bundle(tmp_path)

    assert result.passed is True
    assert result.artifact_count == 3
    assert [artifact.kind for artifact in result.artifacts] == [
        "nodes_csv",
        "edges_csv",
        "graph_json",
    ]
    assert result.node_count == 2
    assert result.edge_count == 1
    assert result.schema_version == "0.1"
    assert result.condition == "normal"
    assert result.csv_validation_passed is True
    assert result.csv_validation_issue_count == 0
    assert_json_safe(result.to_dict())


def test_header_only_graph_artifacts_produce_passing_bundle(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    graph_path = tmp_path / "graph.json"
    write_csv(nodes_path, NODE_COLUMNS)
    write_csv(edges_path, EDGE_COLUMNS)
    assert (
        write_preprocessing_graph_json(nodes_path, edges_path, graph_path).passed
        is True
    )

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert result.passed is True
    assert result.node_count == 0
    assert result.edge_count == 0


def test_missing_artifact_paths_fail(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)

    missing_nodes = build_preprocessing_graph_export_bundle(
        tmp_path / "missing_nodes.csv",
        edges_path,
        graph_path,
    )
    assert missing_nodes.passed is False
    assert missing_nodes.artifacts[0].exists is False
    assert any(
        kind in issue_kinds(missing_nodes)
        for kind in ("path_missing", "csv_validation_failed")
    )

    missing_edges = build_preprocessing_graph_export_bundle(
        nodes_path,
        tmp_path / "missing_edges.csv",
        graph_path,
    )
    assert missing_edges.passed is False
    assert missing_edges.artifacts[1].exists is False

    missing_graph = build_preprocessing_graph_export_bundle(
        nodes_path,
        edges_path,
        tmp_path / "missing_graph.json",
    )
    assert missing_graph.passed is False
    assert "path_missing" in issue_kinds(missing_graph)
    assert missing_graph.artifacts[2].exists is False


def test_directory_path_fails(tmp_path: Path) -> None:
    _, edges_path, graph_path = write_valid_bundle_files(tmp_path)

    result = build_preprocessing_graph_export_bundle(tmp_path, edges_path, graph_path)

    assert result.passed is False
    assert "path_is_directory" in issue_kinds(result)


def test_invalid_csv_validation_fails_bundle(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    graph_path = tmp_path / "graph.json"
    write_csv(nodes_path, NODE_COLUMNS, [node_row(resid="n1"), node_row(resid="n2")])
    write_csv(
        edges_path,
        tuple(column for column in EDGE_COLUMNS if column != "all_edge_types"),
        [edge_row()],
    )
    write_json(graph_path, valid_graph_payload())

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert result.passed is False
    assert "csv_validation_failed" in issue_kinds(result)


def test_invalid_graph_json_parse_fails(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph_path.write_text("{not json", encoding="utf-8")

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert "graph_json_parse_failed" in issue_kinds(result)


def test_missing_graph_json_top_level_keys_fail(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    write_json(graph_path, {"condition": "normal"})

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert "graph_json_missing_key" in issue_kinds(result)


def test_graph_json_nodes_and_edges_must_be_lists(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph = valid_graph_payload()
    graph["nodes"] = {}
    write_json(graph_path, graph)

    nodes_result = build_preprocessing_graph_export_bundle(
        nodes_path,
        edges_path,
        graph_path,
    )
    assert "graph_json_invalid_field" in issue_kinds(nodes_result)

    graph = valid_graph_payload()
    graph["edges"] = {}
    write_json(graph_path, graph)
    edges_result = build_preprocessing_graph_export_bundle(
        nodes_path,
        edges_path,
        graph_path,
    )
    assert "graph_json_invalid_field" in issue_kinds(edges_result)


@pytest.mark.parametrize(
    "graph_overrides",
    (
        {"n_nodes": 1},
        {"n_edges": 2},
    ),
)
def test_graph_json_count_mismatches_fail(
    tmp_path: Path,
    graph_overrides: dict[str, int],
) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph = valid_graph_payload(**graph_overrides)
    write_json(graph_path, graph)

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert "graph_json_count_mismatch" in issue_kinds(result)


@pytest.mark.parametrize("field", ("edge_type", "all_edge_types", "n_edge_types"))
def test_graph_json_missing_corrected_edge_fields_fail(
    tmp_path: Path,
    field: str,
) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    graph = valid_graph_payload()
    edge = dict(graph["edges"][0])  # type: ignore[index]
    edge.pop(field)
    graph["edges"] = [edge]
    write_json(graph_path, graph)

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert "graph_json_missing_edge_field" in issue_kinds(result)


def test_graph_json_preserves_generic_residue_contact(tmp_path: Path) -> None:
    result = build_valid_bundle(tmp_path)

    assert result.passed is True


def test_graph_json_preserves_multi_type_edge_fields(tmp_path: Path) -> None:
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

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert result.passed is True


def test_bundle_does_not_write_files(tmp_path: Path) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    before = {
        path: path.read_text(encoding="utf-8")
        for path in (nodes_path, edges_path, graph_path)
    }

    result = build_preprocessing_graph_export_bundle(nodes_path, edges_path, graph_path)

    assert result.passed is True
    assert {
        path: path.read_text(encoding="utf-8")
        for path in (nodes_path, edges_path, graph_path)
    } == before

    implementation = inspect.getsource(build_preprocessing_graph_export_bundle)
    for forbidden in ("csv.writer", 'open(', '"w"', "write_text", "json.dump"):
        assert forbidden not in implementation


def test_bundle_does_not_call_writers_mapping_contacts_diagnostics_or_comparison(
) -> None:
    tree = ast.parse(inspect.getsource(build_preprocessing_graph_export_bundle))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    for forbidden in (
        "write_preprocessing_graph_json",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "build_preprocessing_graph_export_mapping",
        "compute_condition_contacts",
        "compute_manifest_contacts",
        "write_contact_edges_csv",
        "validate_contact_edges_csv",
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "compare_contract_subset",
        "compare_artifact_sets",
        "compare_contacts_outputs",
    ):
        assert forbidden not in call_names


def test_bundle_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_bundle_uses_validation_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    nodes_path, edges_path, graph_path = write_valid_bundle_files(tmp_path)
    calls: list[str] = []

    def fake_validate(
        nodes_csv_path: str | Path,
        edges_csv_path: str | Path,
    ) -> PreprocessingGraphCsvValidationResult:
        calls.append(f"{nodes_csv_path}:{edges_csv_path}")
        return PreprocessingGraphCsvValidationResult(
            nodes_csv_path=Path(nodes_csv_path),
            edges_csv_path=Path(edges_csv_path),
            node_count=2,
            edge_count=1,
        )

    monkeypatch.setattr(
        graph_export,
        "validate_preprocessing_graph_csvs",
        fake_validate,
    )

    result = graph_export.build_preprocessing_graph_export_bundle(
        nodes_path,
        edges_path,
        graph_path,
    )

    assert result.passed is True
    assert len(calls) == 1


def test_docs_state_stage_14_1f_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.1f",
        "graph export bundle boundary",
        "bundle consumes existing nodes.csv, corrected edges.csv, and graph.json",
        "bundle does not run diagnostics",
        "diagnostics remain Stage 14.2a",
    ):
        assert phrase in text


def test_docs_mention_multi_type_edge_bundle_preservation() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in ("edge_type", "all_edge_types", "n_edge_types"):
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
