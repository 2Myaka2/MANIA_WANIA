import csv
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import NODE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingGraphNodesCsvWriteIssue,
    PreprocessingGraphNodesCsvWriteResult,
    build_preprocessing_graph_export_mapping,
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


def mapping_result(
    *nodes: PreprocessingGraphNodeMappingRecord,
) -> PreprocessingGraphExportMappingResult:
    return PreprocessingGraphExportMappingResult(nodes=tuple(nodes), edges=())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader.fieldnames or ()), list(reader)


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def test_public_exports_work() -> None:
    assert PreprocessingGraphNodesCsvWriteIssue is not None
    assert PreprocessingGraphNodesCsvWriteResult is not None
    assert write_preprocessing_graph_nodes_csv is not None


def test_stage_14_1a_exports_still_work() -> None:
    assert PreprocessingGraphNodeMappingRecord is not None
    assert PreprocessingGraphEdgeMappingRecord is not None
    assert PreprocessingGraphExportMappingIssue is not None
    assert PreprocessingGraphExportMappingResult is not None
    assert build_preprocessing_graph_export_mapping is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphNodesCsvWriteIssue(
        kind="write_failed",
        message="Could not write nodes.",
        node_id="normal|A|1|10|ALA",
        field="output_path",
    )

    assert issue.kind == "write_failed"
    assert issue.message == "Could not write nodes."
    assert issue.node_id == "normal|A|1|10|ALA"
    assert issue.field == "output_path"
    assert_json_safe(issue.to_dict())

    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteIssue(kind="", message="message")
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteIssue(kind="invalid_input", message="")
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteIssue(
            kind="invalid_input",
            message="message",
            node_id="",
        )
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteIssue(
            kind="invalid_input",
            message="message",
            field=" ",
        )


def test_write_result_validates_and_serializes() -> None:
    result = PreprocessingGraphNodesCsvWriteResult(
        output_path=Path("nodes.csv"),
        rows_written=2,
    )

    assert result.passed is True
    assert result.issue_count == 0
    assert result.rows_written == 2
    assert result.to_dict()["output_path"] == "nodes.csv"
    assert_json_safe(result.to_dict())

    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteResult(
            output_path=Path("nodes.csv"),
            rows_written=-1,
        )
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteResult(
            output_path=Path("nodes.csv"),
            rows_written=True,
        )
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteResult(
            output_path=Path("nodes.csv"),
            rows_written=0,
            issues=("not-an-issue",),
        )
    with pytest.raises(ValueError):
        PreprocessingGraphNodesCsvWriteResult(
            output_path=Path("nodes.csv"),
            rows_written=0,
            issues=[],
        )


def test_writer_creates_header_only_nodes_csv_for_empty_mapping(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nodes.csv"
    result = write_preprocessing_graph_nodes_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    header, rows = read_csv(output_path)
    assert result.passed is True
    assert result.rows_written == 0
    assert output_path.exists()
    assert tuple(header) == NODE_COLUMNS
    assert rows == []


def test_writer_writes_one_node_row(tmp_path: Path) -> None:
    node = node_record("normal|A|1|10|ALA")
    output_path = tmp_path / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(mapping_result(node), output_path)

    header, rows = read_csv(output_path)
    assert result.passed is True
    assert result.rows_written == 1
    assert tuple(header) == NODE_COLUMNS
    assert rows == [
        {
            **{column: "" for column in NODE_COLUMNS},
            "resid": "normal|A|1|10|ALA",
            "resname": "ALA",
            "region": "preprocessing_contacts:residue",
            "condition": "normal",
        }
    ]


def test_writer_writes_multiple_nodes_deterministically(tmp_path: Path) -> None:
    result = mapping_result(
        node_record("tumor|B|2|20|GLY", condition_name="tumor"),
        node_record("normal|A|1|10|ALA"),
    )
    output_path = tmp_path / "nodes.csv"

    write_result = write_preprocessing_graph_nodes_csv(result, output_path)

    _, rows = read_csv(output_path)
    assert write_result.passed is True
    assert [row["resid"] for row in rows] == [
        "normal|A|1|10|ALA",
        "tumor|B|2|20|GLY",
    ]


def test_writer_serializes_optional_segid_as_part_of_node_id_or_empty(
    tmp_path: Path,
) -> None:
    node = node_record("normal||1|10|ALA", segid=None)
    output_path = tmp_path / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(mapping_result(node), output_path)

    _, rows = read_csv(output_path)
    assert result.passed is True
    assert rows[0]["resid"] == "normal||1|10|ALA"
    assert rows[0]["x_ca"] == ""


def test_writer_preserves_condition_scope(tmp_path: Path) -> None:
    normal = node_record("normal|A|1|10|ALA", condition_name="normal")
    tumor = node_record("tumor|A|1|10|ALA", condition_name="tumor")
    output_path = tmp_path / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(
        mapping_result(tumor, normal),
        output_path,
    )

    _, rows = read_csv(output_path)
    assert result.passed is True
    assert [row["resid"] for row in rows] == [
        "normal|A|1|10|ALA",
        "tumor|A|1|10|ALA",
    ]
    assert [row["condition"] for row in rows] == ["normal", "tumor"]


def test_writer_does_not_write_edge_rows(tmp_path: Path) -> None:
    source = node_record("normal|A|1|10|ALA")
    target = node_record("normal|B|2|20|GLY", residue_index=2, residue_id="20")
    edge = PreprocessingGraphEdgeMappingRecord(
        edge_id="edge-1",
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        condition_name="normal",
        contact_frame_count=1,
        total_frame_count=1,
        contact_frequency=1.0,
        minimum_distance=3.0,
        mean_minimum_distance=3.0,
        distance_unit="angstrom",
        atom_filter="heavy",
    )
    output_path = tmp_path / "nodes.csv"
    graph_mapping = PreprocessingGraphExportMappingResult(
        nodes=(source, target),
        edges=(edge,),
    )

    result = write_preprocessing_graph_nodes_csv(graph_mapping, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert result.passed is True
    assert result.rows_written == 2
    assert "edge-1" not in text
    for forbidden_column in (
        "edge_id",
        "contact_frame_count",
        "contact_frequency",
        "minimum_distance",
    ):
        assert forbidden_column not in text.splitlines()[0]


def test_writer_fails_on_invalid_input_type(tmp_path: Path) -> None:
    output_path = tmp_path / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(object(), output_path)

    assert result.passed is False
    assert result.rows_written == 0
    assert [issue.kind for issue in result.issues] == ["invalid_input"]
    assert not output_path.exists()


def test_writer_fails_when_mapping_result_has_issues(tmp_path: Path) -> None:
    output_path = tmp_path / "nodes.csv"
    failed_mapping = PreprocessingGraphExportMappingResult(
        nodes=(node_record("normal|A|1|10|ALA"),),
        edges=(),
        issues=(
            PreprocessingGraphExportMappingIssue(
                kind="empty_contacts_result",
                message="No contacts.",
            ),
        ),
    )

    result = write_preprocessing_graph_nodes_csv(failed_mapping, output_path)

    assert result.passed is False
    assert result.rows_written == 0
    assert [issue.kind for issue in result.issues] == ["mapping_result_failed"]
    assert not output_path.exists()


def test_writer_fails_when_output_path_is_directory(tmp_path: Path) -> None:
    result = write_preprocessing_graph_nodes_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        tmp_path,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["output_path_is_directory"]


def test_writer_fails_when_parent_directory_is_missing(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["parent_directory_missing"]
    assert not output_path.parent.exists()


def test_writer_does_not_create_missing_parents(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "nested" / "nodes.csv"

    result = write_preprocessing_graph_nodes_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    assert result.passed is False
    assert output_path.parents[0].exists() is False
    assert output_path.parents[1].exists() is False


def test_writer_fails_on_invalid_output_path_type() -> None:
    result = write_preprocessing_graph_nodes_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        123,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["invalid_output_path"]


def test_writer_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_writer_does_not_write_graph_edges_or_json() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "write_preprocessing_graph_edges_csv",
        "write_graph_edges_csv",
        "write_graph_json",
        "json.dump",
    ):
        assert forbidden not in source


def test_writer_does_not_run_graph_validators_or_diagnostics() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "validate_graph",
        "load_contract_graph",
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "GraphDiagnostics",
    ):
        assert forbidden not in source


def test_docs_state_stage_14_1b_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.1b",
        "nodes.csv writer",
        "backend graph edges.csv writer remains Stage 14.1c",
        "graph CSV validation remains Stage 14.1d",
        "graph.json remains Stage 14.1e",
    ):
        assert phrase in text


def test_docs_preserve_contact_edges_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv is separate/future",
    ):
        assert phrase in text
