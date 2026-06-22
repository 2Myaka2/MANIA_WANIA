import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_object_json_payload_contract.md"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "wania_graph_payload_v0_1.json"

REQUIRED_CAPABILITY_FLAGS = (
    "static_contact_graph",
    "rg_timeseries",
    "aggregate_contacts",
    "contacts_perframe",
    "typed_rin_interactions",
    "centrality_metrics",
    "community_detection",
    "node_structural_metrics",
    "conformational_states",
    "cross_condition_statistics",
    "temporal_rin",
    "inter_component_interactions",
    "cross_protein_comparison",
)

CURRENT_AVAILABLE_CAPABILITIES = (
    "static_contact_graph",
    "rg_timeseries",
    "aggregate_contacts",
    "contacts_perframe",
)

FUTURE_CAPABILITIES = (
    "typed_rin_interactions",
    "centrality_metrics",
    "community_detection",
    "node_structural_metrics",
    "conformational_states",
    "cross_condition_statistics",
    "temporal_rin",
    "inter_component_interactions",
    "cross_protein_comparison",
)


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def load_payload() -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_wania_object_json_payload_contract_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_wania_object_json_payload_contract_doc_contains_key_concepts() -> None:
    text = normalized(doc_text())

    for phrase in (
        "WANIA object JSON payload",
        "object JSON",
        "schema_version",
        "run",
        "protein_id",
        "protein_name",
        "run_name",
        "condition_names",
        "capabilities",
        "static_contact_graph",
        "typed_rin_interactions",
        "temporal_rin",
        "inter_component_interactions",
        "cross_protein_comparison",
        "artifacts",
        "diagnostics",
        "backend graph artifact",
        "not frontend/API payload",
    ):
        assert phrase in text


def test_wania_object_json_payload_contract_doc_keeps_stage_16_scope() -> None:
    text = normalized(doc_text())

    for phrase in (
        "does not implement FastAPI",
        "does not implement adapter",
        "does not change graph export",
        "does not compute typed RIN",
        "does not compute temporal RIN",
    ):
        assert phrase in text


def test_wania_object_json_payload_contract_doc_mentions_stage_16_1_adapter() -> None:
    text = normalized(doc_text())

    for phrase in (
        "Stage 16.1",
        "WANIA object JSON adapter",
        "build_wania_graph_payload_from_artifacts",
        "write_wania_graph_payload_json",
        "not FastAPI",
        "not upload/job API",
        "does not change backend graph/graph.json",
        "does not compute typed RIN",
        "does not compute temporal RIN",
        "does not inline large CSVs",
    ):
        assert phrase in text


def test_wania_payload_sample_is_valid_object_json() -> None:
    payload = load_payload()

    for key in (
        "schema_version",
        "run",
        "capabilities",
        "graph",
        "artifacts",
        "diagnostics",
    ):
        assert key in payload

    assert payload["schema_version"] == "wania_graph.v0.1"


def test_wania_payload_sample_run_metadata_is_protein_agnostic() -> None:
    payload = load_payload()
    run = payload["run"]

    assert isinstance(run, dict)
    for key in (
        "protein_id",
        "protein_name",
        "run_name",
        "condition_names",
    ):
        assert key in run

    assert run["protein_id"] == "napi2b"
    assert run["condition_names"] == ["normal", "tumor"]
    assert isinstance(run["condition_names"], list)

    text = normalized(doc_text())
    assert "protein_id\": \"egfr\"" in text
    assert "condition_names\": [\"wild_type\", \"mutant\"]" in text


def test_wania_payload_sample_graph_nodes_and_edges_are_objects() -> None:
    payload = load_payload()
    graph = payload["graph"]

    assert isinstance(graph, dict)
    assert isinstance(graph["nodes"], list)
    assert isinstance(graph["edges"], list)

    for node in graph["nodes"]:
        assert isinstance(node, dict)
        for key in (
            "id",
            "label",
            "condition",
            "residue",
            "metrics",
        ):
            assert key in node

    for edge in graph["edges"]:
        assert isinstance(edge, dict)
        for key in (
            "source",
            "target",
            "condition",
            "interaction",
            "metrics",
        ):
            assert key in edge

        interaction = edge["interaction"]
        assert isinstance(interaction, dict)
        assert "primary_type" in interaction
        assert "all_types" in interaction


def test_wania_payload_sample_does_not_use_compact_table_style() -> None:
    payload = load_payload()
    graph = payload["graph"]

    for compact_key in (
        "node_fields",
        "edge_fields",
    ):
        assert compact_key not in payload
        assert compact_key not in graph

    assert all(isinstance(node, dict) for node in graph["nodes"])
    assert all(isinstance(edge, dict) for edge in graph["edges"])


def test_wania_payload_sample_capabilities_are_consistent() -> None:
    payload = load_payload()
    capabilities = payload["capabilities"]

    assert isinstance(capabilities, dict)
    assert set(capabilities) == set(REQUIRED_CAPABILITY_FLAGS)

    for capability in CURRENT_AVAILABLE_CAPABILITIES:
        assert capabilities[capability] is True

    for capability in FUTURE_CAPABILITIES:
        assert capabilities[capability] is False
