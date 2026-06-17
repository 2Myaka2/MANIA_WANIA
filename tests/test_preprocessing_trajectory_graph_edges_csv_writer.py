import csv
import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.constants import EDGE_COLUMNS
from mania.preprocessing import (
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphEdgesCsvWriteIssue,
    PreprocessingGraphEdgesCsvWriteResult,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    write_preprocessing_graph_edges_csv,
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


def edge_record(
    edge_id: str,
    *,
    source_node_id: str = "normal|A|1|10|ALA",
    target_node_id: str = "normal|B|2|20|GLY",
    condition_name: str = "normal",
    contact_frequency: float | None = 0.5,
    mean_minimum_distance: float | None = 3.25,
    distance_unit: str | None = "angstrom",
) -> PreprocessingGraphEdgeMappingRecord:
    return PreprocessingGraphEdgeMappingRecord(
        edge_id=edge_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        condition_name=condition_name,
        contact_frame_count=2,
        total_frame_count=4,
        contact_frequency=contact_frequency,
        minimum_distance=2.0,
        mean_minimum_distance=mean_minimum_distance,
        distance_unit=distance_unit,
        atom_filter="heavy",
    )


def mapping_result(
    *edges: PreprocessingGraphEdgeMappingRecord,
    nodes: tuple[PreprocessingGraphNodeMappingRecord, ...] | None = None,
) -> PreprocessingGraphExportMappingResult:
    graph_nodes = nodes or (
        node_record("normal|A|1|10|ALA"),
        node_record(
            "normal|B|2|20|GLY",
            residue_index=2,
            residue_id="20",
            resname="GLY",
            segid="B",
        ),
    )
    return PreprocessingGraphExportMappingResult(
        nodes=graph_nodes,
        edges=tuple(edges),
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader.fieldnames or ()), list(reader)


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def test_public_exports_work() -> None:
    assert PreprocessingGraphEdgesCsvWriteIssue is not None
    assert PreprocessingGraphEdgesCsvWriteResult is not None
    assert write_preprocessing_graph_edges_csv is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphEdgesCsvWriteIssue(
        kind="write_failed",
        message="Could not write edges.",
        edge_id="normal|edge",
        field="output_path",
    )

    assert issue.kind == "write_failed"
    assert issue.message == "Could not write edges."
    assert issue.edge_id == "normal|edge"
    assert issue.field == "output_path"
    assert_json_safe(issue.to_dict())

    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteIssue(kind="", message="message")
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteIssue(kind="invalid_input", message="")
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteIssue(
            kind="invalid_input",
            message="message",
            edge_id="",
        )
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteIssue(
            kind="invalid_input",
            message="message",
            field=" ",
        )


def test_write_result_validates_and_serializes() -> None:
    result = PreprocessingGraphEdgesCsvWriteResult(
        output_path=Path("edges.csv"),
        rows_written=2,
    )

    assert result.passed is True
    assert result.issue_count == 0
    assert result.rows_written == 2
    assert result.to_dict()["output_path"] == "edges.csv"
    assert_json_safe(result.to_dict())

    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteResult(
            output_path=Path("edges.csv"),
            rows_written=-1,
        )
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteResult(
            output_path=Path("edges.csv"),
            rows_written=True,
        )
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteResult(
            output_path=Path("edges.csv"),
            rows_written=0,
            issues=("not-an-issue",),
        )
    with pytest.raises(ValueError):
        PreprocessingGraphEdgesCsvWriteResult(
            output_path=Path("edges.csv"),
            rows_written=0,
            issues=[],
        )


def test_writer_creates_header_only_edges_csv_for_empty_mapping(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "edges.csv"
    result = write_preprocessing_graph_edges_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    header, rows = read_csv(output_path)
    assert result.passed is True
    assert result.rows_written == 0
    assert output_path.exists()
    assert tuple(header) == EDGE_COLUMNS
    assert rows == []


def test_writer_writes_one_backend_edge_row(tmp_path: Path) -> None:
    edge = edge_record("edge-1")
    output_path = tmp_path / "edges.csv"

    result = write_preprocessing_graph_edges_csv(
        mapping_result(edge),
        output_path,
    )

    header, rows = read_csv(output_path)
    assert result.passed is True
    assert result.rows_written == 1
    assert tuple(header) == EDGE_COLUMNS
    assert rows == [
        {
            **{column: "" for column in EDGE_COLUMNS},
            "resid_i": "normal|A|1|10|ALA",
            "resid_j": "normal|B|2|20|GLY",
            "edge_type": "residue_contact",
            "condition": "normal",
            "contact_freq": "0.5",
            "mean_dist_A": "3.25",
        }
    ]


def test_writer_does_not_add_preprocessing_only_edge_columns(
    tmp_path: Path,
) -> None:
    edge = edge_record("edge-1")
    output_path = tmp_path / "edges.csv"

    write_preprocessing_graph_edges_csv(mapping_result(edge), output_path)

    header, _ = read_csv(output_path)
    for forbidden_column in (
        "edge_id",
        "source_node_id",
        "target_node_id",
        "contact_frame_count",
        "total_frame_count",
        "minimum_distance",
        "distance_unit",
        "atom_filter",
    ):
        assert forbidden_column not in header


def test_writer_writes_multiple_edges_deterministically(tmp_path: Path) -> None:
    normal_source = node_record("normal|A|1|10|ALA")
    normal_target = node_record(
        "normal|B|2|20|GLY",
        residue_index=2,
        residue_id="20",
        resname="GLY",
        segid="B",
    )
    tumor_source = node_record(
        "tumor|A|1|10|ALA",
        condition_name="tumor",
    )
    tumor_target = node_record(
        "tumor|B|2|20|GLY",
        condition_name="tumor",
        residue_index=2,
        residue_id="20",
        resname="GLY",
        segid="B",
    )
    normal = edge_record(
        "a-edge",
        source_node_id=normal_source.node_id,
        target_node_id=normal_target.node_id,
        condition_name="normal",
    )
    tumor = edge_record(
        "b-edge",
        source_node_id=tumor_source.node_id,
        target_node_id=tumor_target.node_id,
        condition_name="tumor",
    )
    output_path = tmp_path / "edges.csv"

    write_result = write_preprocessing_graph_edges_csv(
        mapping_result(
            tumor,
            normal,
            nodes=(tumor_source, tumor_target, normal_source, normal_target),
        ),
        output_path,
    )

    _, rows = read_csv(output_path)
    assert write_result.passed is True
    assert [row["resid_i"] for row in rows] == [
        "normal|A|1|10|ALA",
        "tumor|A|1|10|ALA",
    ]
    assert [row["condition"] for row in rows] == ["normal", "tumor"]


def test_writer_serializes_missing_optional_metadata_as_empty_strings(
    tmp_path: Path,
) -> None:
    edge = edge_record(
        "edge-1",
        contact_frequency=None,
        mean_minimum_distance=None,
        distance_unit=None,
    )
    output_path = tmp_path / "edges.csv"

    result = write_preprocessing_graph_edges_csv(mapping_result(edge), output_path)

    _, rows = read_csv(output_path)
    assert result.passed is True
    assert rows[0]["contact_freq"] == ""
    assert rows[0]["mean_dist_A"] == ""
    for unsupported_column in (
        "std_dist_A",
        "n_episodes",
        "mean_lifetime_frames",
        "max_lifetime_frames",
        "mean_lifetime_ns",
        "max_lifetime_ns",
        "formation_count",
        "breakage_count",
        "first_seen_frame",
        "last_seen_frame",
        "window_cv",
    ):
        assert rows[0][unsupported_column] == ""


def test_writer_does_not_put_non_angstrom_distance_in_mean_dist_a(
    tmp_path: Path,
) -> None:
    edge = edge_record(
        "edge-1",
        mean_minimum_distance=3.25,
        distance_unit="nanometer",
    )
    output_path = tmp_path / "edges.csv"

    result = write_preprocessing_graph_edges_csv(mapping_result(edge), output_path)

    _, rows = read_csv(output_path)
    assert result.passed is True
    assert rows[0]["mean_dist_A"] == ""


def test_writer_fails_on_invalid_input_type(tmp_path: Path) -> None:
    output_path = tmp_path / "edges.csv"

    result = write_preprocessing_graph_edges_csv(object(), output_path)

    assert result.passed is False
    assert result.rows_written == 0
    assert [issue.kind for issue in result.issues] == ["invalid_input"]
    assert not output_path.exists()


def test_writer_fails_when_mapping_result_has_issues(tmp_path: Path) -> None:
    output_path = tmp_path / "edges.csv"
    failed_mapping = PreprocessingGraphExportMappingResult(
        nodes=(),
        edges=(),
        issues=(
            PreprocessingGraphExportMappingIssue(
                kind="empty_contacts_result",
                message="No contacts.",
            ),
        ),
    )

    result = write_preprocessing_graph_edges_csv(failed_mapping, output_path)

    assert result.passed is False
    assert result.rows_written == 0
    assert [issue.kind for issue in result.issues] == ["mapping_result_failed"]
    assert not output_path.exists()


def test_writer_fails_when_output_path_is_directory(tmp_path: Path) -> None:
    result = write_preprocessing_graph_edges_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        tmp_path,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["output_path_is_directory"]


def test_writer_fails_when_parent_directory_is_missing(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "edges.csv"

    result = write_preprocessing_graph_edges_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["parent_directory_missing"]
    assert not output_path.parent.exists()


def test_writer_does_not_create_missing_parents(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "nested" / "edges.csv"

    result = write_preprocessing_graph_edges_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        output_path,
    )

    assert result.passed is False
    assert output_path.parents[0].exists() is False
    assert output_path.parents[1].exists() is False


def test_writer_fails_on_invalid_output_path_type() -> None:
    result = write_preprocessing_graph_edges_csv(
        PreprocessingGraphExportMappingResult(nodes=(), edges=()),
        123,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["invalid_output_path"]


def test_writer_is_dependency_free() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source


def test_writer_does_not_write_graph_json_or_run_graph_checks() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "write_graph_json",
        "json.dump",
        "validate_graph",
        "load_contract_graph",
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "GraphDiagnostics",
    ):
        assert forbidden not in source


def test_docs_state_stage_14_1c_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 14.1c",
        "backend graph edges.csv writer",
        "write_preprocessing_graph_edges_csv",
        "graph CSV validation remains Stage 14.1d",
        "graph.json remains Stage 14.1e",
    ):
        assert phrase in text


def test_docs_preserve_contact_edges_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "Stage 13 contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv is separate",
    ):
        assert phrase in text
