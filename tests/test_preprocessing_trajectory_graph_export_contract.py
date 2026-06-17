import json
import math
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactComputationIssue,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingManifestContactsResult,
    build_preprocessing_graph_export_mapping,
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

NORMAL_SOURCE_NODE_ID = "normal|A|0|10|ALA"
NORMAL_TARGET_NODE_ID = "normal|B|1|20|GLY"
NORMAL_EDGE_ID = (
    "normal|normal\\|A\\|0\\|10\\|ALA|"
    "normal\\|B\\|1\\|20\\|GLY|angstrom|heavy"
)


def node_record(node_id: str = "n1") -> PreprocessingGraphNodeMappingRecord:
    return PreprocessingGraphNodeMappingRecord(
        node_id=node_id,
        condition_name="normal",
        residue_index=1,
        residue_id="1",
        resname="ALA",
        segid="A",
    )


def edge_record(edge_id: str = "e1") -> PreprocessingGraphEdgeMappingRecord:
    return PreprocessingGraphEdgeMappingRecord(
        edge_id=edge_id,
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        contact_frame_count=1,
        total_frame_count=2,
        contact_frequency=0.5,
        minimum_distance=3.0,
        mean_minimum_distance=3.0,
        distance_unit="angstrom",
        atom_filter="heavy",
    )


def make_pair(
    source_index: int = 0,
    target_index: int = 1,
    *,
    source_residue_id: int | str | None = 10,
    target_residue_id: int | str | None = 20,
    source_resname: str = "ALA",
    target_resname: str = "GLY",
    source_segid: str | None = "A",
    target_segid: str | None = "B",
    minimum_distance: float = 3.0,
    distance_unit: str = "angstrom",
    atom_filter: str = "heavy",
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=source_index,
        target_residue_index=target_index,
        source_residue_id=source_residue_id,
        target_residue_id=target_residue_id,
        source_resname=source_resname,
        target_resname=target_resname,
        source_segid=source_segid,
        target_segid=target_segid,
        minimum_distance=minimum_distance,
        distance_unit=distance_unit,
        atom_filter=atom_filter,
    )


def make_frame(
    condition_name: str,
    frame_index: int,
    *,
    contacts: tuple[PreprocessingContactPairResult, ...] = (),
    issues: tuple[PreprocessingContactComputationIssue, ...] = (),
) -> PreprocessingContactFrameResult:
    return PreprocessingContactFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        contacts=contacts,
        issues=issues,
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frame_results: tuple[PreprocessingContactFrameResult, ...],
    status: str = "computed",
    issues: tuple[PreprocessingContactComputationIssue, ...] = (),
) -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=PreprocessingContactDetectionOptions(),
        frame_results=frame_results,
        issues=issues,
        status=status,
    )


def assert_json_safe(payload: object) -> None:
    json.dumps(payload)


def test_public_exports_work() -> None:
    assert PreprocessingGraphNodeMappingRecord is not None
    assert PreprocessingGraphEdgeMappingRecord is not None
    assert PreprocessingGraphExportMappingIssue is not None
    assert PreprocessingGraphExportMappingResult is not None
    assert build_preprocessing_graph_export_mapping is not None


def test_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_node_record_validates_and_serializes() -> None:
    record = node_record()

    assert record.node_id == "n1"
    assert record.condition_name == "normal"
    assert record.residue_index == 1
    assert record.residue_id == "1"
    assert record.resname == "ALA"
    assert record.segid == "A"
    assert record.node_kind == "residue"
    assert record.source == "preprocessing_contacts"
    assert_json_safe(record.to_dict())


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("node_id", ""),
        ("condition_name", " "),
        ("residue_index", -1),
        ("residue_index", True),
        ("residue_id", ""),
        ("resname", " "),
        ("node_kind", ""),
        ("source", " "),
    ),
)
def test_node_record_rejects_invalid_values(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "node_id": "n1",
        "condition_name": "normal",
        "residue_index": 1,
        "residue_id": "1",
        "resname": "ALA",
        "segid": "A",
        "node_kind": "residue",
        "source": "preprocessing_contacts",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        PreprocessingGraphNodeMappingRecord(**kwargs)


def test_edge_record_validates_and_serializes() -> None:
    record = edge_record()

    assert record.edge_id == "e1"
    assert record.source_node_id == "n1"
    assert record.target_node_id == "n2"
    assert record.condition_name == "normal"
    assert record.edge_kind == "residue_contact"
    assert record.source == "preprocessing_contacts"
    assert record.contact_frame_count == 1
    assert record.total_frame_count == 2
    assert record.contact_frequency == 0.5
    assert record.minimum_distance == 3.0
    assert record.mean_minimum_distance == 3.0
    assert record.distance_unit == "angstrom"
    assert record.atom_filter == "heavy"
    assert_json_safe(record.to_dict())


@pytest.mark.parametrize(
    "overrides",
    (
        {"edge_id": ""},
        {"source_node_id": " "},
        {"target_node_id": ""},
        {"source_node_id": "n1", "target_node_id": "n1"},
        {"condition_name": " "},
        {"contact_frame_count": -1},
        {"total_frame_count": -1},
        {"contact_frame_count": True},
        {"total_frame_count": False},
        {"contact_frame_count": 2, "total_frame_count": 1},
        {"contact_frequency": -0.1},
        {"contact_frequency": math.inf},
        {"minimum_distance": -1.0},
        {"minimum_distance": math.nan},
        {"mean_minimum_distance": -1.0},
        {"mean_minimum_distance": math.inf},
        {"edge_kind": ""},
        {"source": " "},
    ),
)
def test_edge_record_rejects_invalid_values(
    overrides: dict[str, object],
) -> None:
    kwargs: dict[str, object] = {
        "edge_id": "e1",
        "source_node_id": "n1",
        "target_node_id": "n2",
        "condition_name": "normal",
        "edge_kind": "residue_contact",
        "source": "preprocessing_contacts",
        "contact_frame_count": 1,
        "total_frame_count": 2,
        "contact_frequency": 0.5,
        "minimum_distance": 3.0,
        "mean_minimum_distance": 3.0,
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError):
        PreprocessingGraphEdgeMappingRecord(**kwargs)


def test_issue_record_validates_and_serializes() -> None:
    issue = PreprocessingGraphExportMappingIssue(
        kind="empty_contacts_result",
        message="No contacts.",
        record_id="normal",
        field="contacts_result",
    )

    assert issue.to_dict() == {
        "kind": "empty_contacts_result",
        "message": "No contacts.",
        "record_id": "normal",
        "field": "contacts_result",
    }
    assert_json_safe(issue.to_dict())
    with pytest.raises(ValueError):
        PreprocessingGraphExportMappingIssue(kind="", message="No contacts.")
    with pytest.raises(ValueError):
        PreprocessingGraphExportMappingIssue(kind="invalid_input", message="")


def test_mapping_result_validates_and_serializes() -> None:
    nodes = (node_record("n2"), node_record("n1"))
    edge = edge_record("e1")

    result = PreprocessingGraphExportMappingResult(nodes=nodes, edges=(edge,))

    assert result.passed is True
    assert result.node_count == 2
    assert result.edge_count == 1
    assert [node.node_id for node in result.nodes] == ["n1", "n2"]
    assert_json_safe(result.to_dict())


def test_mapping_result_rejects_duplicate_nodes() -> None:
    with pytest.raises(ValueError, match="Duplicate node IDs"):
        PreprocessingGraphExportMappingResult(
            nodes=(node_record("n1"), node_record("n1")),
            edges=(),
        )


def test_mapping_result_rejects_duplicate_edges() -> None:
    with pytest.raises(ValueError, match="Duplicate edge IDs"):
        PreprocessingGraphExportMappingResult(
            nodes=(node_record("n1"), node_record("n2")),
            edges=(edge_record("e1"), edge_record("e1")),
        )


def test_mapping_result_detects_edge_endpoint_missing() -> None:
    with pytest.raises(ValueError, match="missing from nodes"):
        PreprocessingGraphExportMappingResult(
            nodes=(node_record("n1"),),
            edges=(edge_record("e1"),),
        )


def test_single_condition_mapping_creates_nodes_and_edges() -> None:
    condition = make_condition(
        frame_results=(
            make_frame("normal", 0, contacts=(make_pair(),)),
            make_frame("normal", 1),
        ),
    )

    result = build_preprocessing_graph_export_mapping(condition)

    assert result.passed is True
    assert result.node_count == 2
    assert result.edge_count == 1
    assert [node.node_id for node in result.nodes] == [
        NORMAL_SOURCE_NODE_ID,
        NORMAL_TARGET_NODE_ID,
    ]
    edge = result.edges[0]
    assert edge.edge_id == NORMAL_EDGE_ID
    assert edge.source_node_id == NORMAL_SOURCE_NODE_ID
    assert edge.target_node_id == NORMAL_TARGET_NODE_ID
    assert edge.contact_frame_count == 1
    assert edge.total_frame_count == 2
    assert edge.contact_frequency == 0.5
    assert edge.minimum_distance == 3.0
    assert edge.mean_minimum_distance == 3.0


def test_manifest_mapping_preserves_condition_scope() -> None:
    normal = make_condition(
        "normal",
        frame_results=(make_frame("normal", 0, contacts=(make_pair(),)),),
    )
    tumor = make_condition(
        "tumor",
        frame_results=(make_frame("tumor", 0, contacts=(make_pair(),)),),
    )
    manifest = PreprocessingManifestContactsResult(
        condition_results=(tumor, normal),
    )

    result = build_preprocessing_graph_export_mapping(manifest)

    assert result.passed is True
    assert result.node_count == 4
    assert result.edge_count == 2
    node_ids = [node.node_id for node in result.nodes]
    edge_condition_names = [edge.condition_name for edge in result.edges]
    assert "normal|A|0|10|ALA" in node_ids
    assert "tumor|A|0|10|ALA" in node_ids
    assert edge_condition_names == ["normal", "tumor"]
    assert all(
        edge.source_node_id.startswith(edge.condition_name)
        for edge in result.edges
    )


def test_mapping_aggregates_repeated_pair_across_frames() -> None:
    condition = make_condition(
        frame_results=(
            make_frame("normal", 0, contacts=(make_pair(minimum_distance=3.0),)),
            make_frame("normal", 1),
            make_frame("normal", 2, contacts=(make_pair(minimum_distance=5.0),)),
        ),
    )

    result = build_preprocessing_graph_export_mapping(condition)

    assert result.passed is True
    assert result.edge_count == 1
    edge = result.edges[0]
    assert edge.contact_frame_count == 2
    assert edge.total_frame_count == 3
    assert edge.contact_frequency == pytest.approx(2 / 3)
    assert edge.minimum_distance == 3.0
    assert edge.mean_minimum_distance == 4.0


def test_mapping_skips_failed_frames_consistently() -> None:
    frame_issue = PreprocessingContactComputationIssue(
        kind="frame_error",
        field="frame",
        message="Frame failed.",
    )
    condition = make_condition(
        frame_results=(
            make_frame("normal", 0, contacts=(make_pair(),)),
            make_frame(
                "normal",
                1,
                contacts=(make_pair(minimum_distance=1.0),),
                issues=(frame_issue,),
            ),
        ),
        status="partial",
    )

    result = build_preprocessing_graph_export_mapping(condition)

    assert result.passed is False
    assert result.edge_count == 1
    assert result.edges[0].contact_frame_count == 1
    assert result.edges[0].total_frame_count == 1
    assert result.edges[0].minimum_distance == 3.0
    assert [issue.kind for issue in result.issues] == [
        "mapping_failed",
        "mapping_failed",
    ]


def test_empty_contacts_result_behavior_is_deterministic() -> None:
    empty_condition = make_condition(frame_results=())
    empty_manifest = PreprocessingManifestContactsResult()

    condition_result = build_preprocessing_graph_export_mapping(empty_condition)
    manifest_result = build_preprocessing_graph_export_mapping(empty_manifest)

    assert condition_result.passed is False
    assert condition_result.node_count == 0
    assert condition_result.edge_count == 0
    assert [issue.kind for issue in condition_result.issues] == [
        "empty_contacts_result"
    ]
    assert manifest_result.passed is False
    assert [issue.kind for issue in manifest_result.issues] == [
        "empty_contacts_result"
    ]


def test_unsupported_input_type_returns_issue() -> None:
    result = build_preprocessing_graph_export_mapping(object())

    assert result.passed is False
    assert result.node_count == 0
    assert result.edge_count == 0
    assert [issue.kind for issue in result.issues] == ["unsupported_input_type"]


def test_mapping_output_order_is_deterministic() -> None:
    normal = make_condition(
        "normal",
        frame_results=(
            make_frame(
                "normal",
                0,
                contacts=(
                    make_pair(5, 6, source_residue_id=50, target_residue_id=60),
                    make_pair(),
                ),
            ),
        ),
    )
    tumor = make_condition(
        "tumor",
        frame_results=(make_frame("tumor", 0, contacts=(make_pair(),)),),
    )
    manifest = PreprocessingManifestContactsResult(
        condition_results=(tumor, normal),
    )

    result = build_preprocessing_graph_export_mapping(manifest)

    node_ids = [node.node_id for node in result.nodes]
    edge_ids = [edge.edge_id for edge in result.edges]
    assert node_ids == sorted(node_ids)
    assert edge_ids == sorted(edge_ids)


def test_graph_mapping_is_not_file_export() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "write_graph_nodes_csv",
        "write_graph_edges_csv",
        "write_graph_json",
        "open(",
        "csv.writer",
        "json.dump",
    ):
        assert forbidden not in source


def test_graph_mapping_does_not_call_graph_diagnostics_or_validators() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "validate_graph",
        "load_contract_graph",
        "run_condition_graph_diagnostics",
        "run_output_graph_diagnostics",
        "GraphDiagnostics",
    ):
        assert forbidden not in source


def test_contact_edges_boundary_is_documented() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "contact_edges.csv is aggregate contacts table",
        "backend graph edges.csv remains separate/future",
        "Stage 14.1a maps contacts into graph edge records",
    ):
        assert phrase in text


def test_docs_say_graph_writers_are_future() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)

    for phrase in (
        "nodes.csv writer is Stage 14.1b",
        "backend graph edges.csv writer is Stage 14.1c",
        "graph.json writer is Stage 14.1e",
    ):
        assert phrase in text


def test_no_forbidden_dependencies() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source
