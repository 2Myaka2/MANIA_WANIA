import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "wania_graph_payload_frontend_sample_v0_1.json"
)
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "wania_object_json_payload_contract.md",
    REPO_ROOT / "docs" / "preprocessing_graph_workflow_contract.md",
    REPO_ROOT
    / "docs"
    / "preprocessing_graph_workflow_boundary_before_frontend_api.md",
    REPO_ROOT / "docs" / "notebook_gap_report_v1_3.md",
)


def reject_non_json_number(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")


def load_sample() -> dict[str, Any]:
    payload = json.loads(
        SAMPLE_PATH.read_text(encoding="utf-8"),
        parse_constant=reject_non_json_number,
    )
    assert isinstance(payload, dict)
    return payload


def artifact_paths(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            path
            for child in value.values()
            for path in artifact_paths(child)
        ]
    return []


def test_frontend_sample_is_compact_valid_current_object_json() -> None:
    payload = load_sample()

    assert SAMPLE_PATH.stat().st_size < 20_000
    assert payload["schema_version"] == "wania_graph.v0.1"
    assert set(("run", "capabilities", "graph", "artifacts", "diagnostics")) <= (
        payload.keys()
    )
    assert payload["run"]["condition_names"] == ["normal", "tumor"]
    assert payload["graph"]["node_count"] == len(payload["graph"]["nodes"])
    assert payload["graph"]["edge_count"] == len(payload["graph"]["edges"])


def test_frontend_sample_nodes_have_identity_and_json_safe_ca_coordinates() -> None:
    nodes = load_sample()["graph"]["nodes"]
    coordinate_fields = ("x", "y", "z", "x_ca", "y_ca", "z_ca")

    assert {node["condition"] for node in nodes} == {"normal", "tumor"}
    for node in nodes:
        assert "id" in node
        assert {"id", "index", "name", "chain_id"} <= node["residue"].keys()
        for field in coordinate_fields:
            value = node[field]
            assert value is None or (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(value)
            )

    normal = next(node for node in nodes if node["id"] == "normal|A|10|10|PHE")
    tumor = next(node for node in nodes if node["id"] == "tumor|A|10|10|PHE")
    assert (normal["x_ca"], normal["y_ca"], normal["z_ca"]) != (
        tumor["x_ca"],
        tumor["y_ca"],
        tumor["z_ca"],
    )


def test_frontend_sample_demonstrates_interactions_and_edge_priority() -> None:
    edges = load_sample()["graph"]["edges"]
    primary_types = {
        edge["interaction"]["primary_type"]
        for edge in edges
    }

    assert {"backbone", "residue_contact", "aromatic_pi", "cation_pi"} <= (
        primary_types
    )
    overlap = next(
        edge
        for edge in edges
        if edge["id"] == "edge_normal_backbone_overlap"
    )
    assert overlap["interaction"] == {
        "primary_type": "backbone",
        "all_types": ["backbone", "vdw"],
    }
    for edge in edges:
        all_types = edge["interaction"]["all_types"]
        assert edge["interaction"]["primary_type"] == all_types[0]
        assert len(all_types) == len(set(all_types))


def test_frontend_sample_capabilities_remain_honest() -> None:
    payload = load_sample()
    capabilities = payload["capabilities"]

    assert capabilities["centrality_metrics"] is True
    assert capabilities["community_detection"] is True
    for capability in (
        "typed_rin_interactions",
        "temporal_rin",
        "temporal_interactions",
        "analysis_statistics",
        "cross_condition_statistics",
        "conformational_states",
    ):
        assert capabilities.get(capability, False) is False
    assert payload["temporal"] == {"available": False, "windows": []}


def test_frontend_sample_artifact_references_are_relative_and_safe() -> None:
    artifacts = load_sample()["artifacts"]
    paths = artifact_paths(artifacts)

    assert {
        "graph/graph.json",
        "graph/nodes.csv",
        "graph/edges.csv",
        "rg/rg_timeseries.csv",
        "contacts/contact_edges.csv",
        "contacts/contacts_perframe.csv",
        "reports/graph_diagnostics_report.json",
        "analysis/metrics_normal.csv",
        "analysis/metrics_tumor.csv",
        "analysis/communities_normal.csv",
        "analysis/communities_tumor.csv",
        "analysis/analysis_metrics_report.json",
    } <= set(paths)
    for path_value in paths:
        path = Path(path_value)
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert not {"local_md", "local_md_protein", "mania_output"} & set(
            path.parts
        )


def test_stage_16_12_docs_record_sample_and_boundaries() -> None:
    texts = {
        path: " ".join(path.read_text(encoding="utf-8").split())
        for path in DOC_PATHS
    }
    combined = " ".join(texts.values())

    assert all("Stage 16.12" in text for text in texts.values())
    for phrase in (
        "compact frontend-ready WANIA sample payload",
        "synthetic",
        "aromatic_pi",
        "cation_pi",
        "analysis artifact references",
        "not a real-MD benchmark",
        "not an API response guarantee beyond the documented payload contract",
        "FastAPI/upload/job API remains future scope",
        "Temporal RIN remains future scope",
        "Formal statistics remain future scope",
        "Conformational clustering remains future scope",
    ):
        assert phrase in combined
