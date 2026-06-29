import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_required_fields_contract_v0_1.md"
MINIMAL_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "wania_mvp_minimal_payload_v0_1.json"
)
RICH_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "wania_graph_payload_frontend_sample_v0_1.json"
)
REFERENCE_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "wania_mvp_contract_v0_1.md",
    REPO_ROOT / "docs" / "wania_object_json_payload_contract.md",
)

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "run",
    "capabilities",
    "graph",
    "artifacts",
    "diagnostics",
}
REQUIRED_RUN_FIELDS = {
    "run_name",
    "protein_id",
    "protein_name",
    "condition_names",
}
FUTURE_CAPABILITIES = {
    "typed_rin_interactions",
    "temporal_interactions",
    "temporal_rin",
    "analysis_statistics",
    "conformational_states",
    "cross_protein_comparison",
}
FORBIDDEN_ARTIFACT_PARTS = {
    "local_md",
    "local_md_protein",
    "mania_output",
}
RAW_ARTIFACT_SUFFIXES = {
    ".tpr",
    ".xtc",
    ".gro",
    ".cpt",
    ".edr",
    ".log",
    ".dcd",
    ".psf",
}


def reject_non_json_number(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_non_json_number,
    )
    assert isinstance(payload, dict)
    return payload


def normalized(text: str) -> str:
    return " ".join(text.split())


def artifact_paths(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            path
            for child in value.values()
            for path in artifact_paths(child)
        ]
    if isinstance(value, list):
        return [path for child in value for path in artifact_paths(child)]
    return []


def assert_required_fields_contract(payload: dict[str, Any]) -> None:
    assert REQUIRED_TOP_LEVEL_FIELDS <= payload.keys()
    assert payload["schema_version"] == "wania_graph.v0.1"

    run = payload["run"]
    assert isinstance(run, dict)
    assert REQUIRED_RUN_FIELDS <= run.keys()
    for field in ("run_name", "protein_id", "protein_name"):
        assert isinstance(run[field], str) and run[field]
    condition_names = run["condition_names"]
    assert isinstance(condition_names, list) and condition_names
    assert all(
        isinstance(condition, str) and condition for condition in condition_names
    )
    assert len(condition_names) == len(set(condition_names))

    capabilities = payload["capabilities"]
    assert isinstance(capabilities, dict)
    assert isinstance(capabilities.get("static_contact_graph"), bool)
    assert all(isinstance(value, bool) for value in capabilities.values())
    for capability in FUTURE_CAPABILITIES:
        assert capabilities.get(capability, False) is False

    graph = payload["graph"]
    assert isinstance(graph, dict)
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    assert isinstance(nodes, list)
    assert isinstance(edges, list)

    node_ids: set[str] = set()
    for node in nodes:
        assert isinstance(node, dict)
        assert {"id", "condition", "residue", "x", "y", "z"} <= node.keys()
        assert isinstance(node["id"], str) and node["id"]
        assert node["id"] not in node_ids
        node_ids.add(node["id"])
        assert node["condition"] in condition_names
        residue = node["residue"]
        assert isinstance(residue, dict)
        assert {"index", "name"} <= residue.keys()
        assert residue["index"] is not None
        assert isinstance(residue["name"], str) and residue["name"]
        for field in ("x", "y", "z"):
            value = node[field]
            assert isinstance(value, int | float) and not isinstance(value, bool)
            assert math.isfinite(value)

    for edge in edges:
        assert isinstance(edge, dict)
        assert {"id", "source", "target", "condition", "interaction"} <= (
            edge.keys()
        )
        assert isinstance(edge["id"], str) and edge["id"]
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
        assert edge["condition"] in condition_names
        interaction = edge["interaction"]
        assert isinstance(interaction, dict)
        primary_type = interaction.get("primary_type")
        assert isinstance(primary_type, str) and primary_type

    artifacts = payload["artifacts"]
    assert isinstance(artifacts, dict)
    for path_value in artifact_paths(artifacts):
        path = Path(path_value)
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert not FORBIDDEN_ARTIFACT_PARTS & set(path.parts)
        assert path.suffix.lower() not in RAW_ARTIFACT_SUFFIXES

    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, dict)
    assert "passed" in diagnostics
    assert diagnostics["passed"] is None or isinstance(diagnostics["passed"], bool)
    if "issues" in diagnostics:
        assert isinstance(diagnostics["issues"], list)
    if not nodes:
        assert diagnostics.get("issues")


def test_required_fields_contract_document_exists_and_defines_statuses() -> None:
    text = normalized(DOC_PATH.read_text(encoding="utf-8"))

    assert DOC_PATH.is_file()
    for phrase in (
        "Required WANIA fields",
        "required",
        "optional",
        "backend-only",
        "future",
        "schema_version",
        "run",
        "capabilities",
        "graph.nodes",
        "graph.edges",
        "node `id`",
        "node `condition`",
        "residue display identity",
        "x/y/z",
        "coordinate-based",
        "x_ca/y_ca/z_ca",
        "interaction.primary_type",
        "artifacts",
        "diagnostics",
    ):
        assert phrase in text


def test_required_fields_contract_records_capability_and_stage_boundaries() -> None:
    text = normalized(DOC_PATH.read_text(encoding="utf-8"))

    for phrase in (
        "capabilities are availability signals",
        "capability true does not make optional blocks required",
        "Stage 16.12 rich frontend sample",
        "minimal MVP fixture",
        "backbone` as a specific interaction type",
        "aromatic_pi` as a specific interaction type",
        "cation_pi` as a specific interaction type",
        "analysis metrics and communities",
        "InteractionAccumulator` internals",
        "atom cache",
        "temporal RIN",
        "formal statistics",
        "conformational clustering",
        "not schema redesign",
        "not FastAPI",
        "not an upload/job API",
    ):
        assert phrase in text


def test_required_fields_contract_is_linked_from_required_docs() -> None:
    for path in REFERENCE_PATHS:
        assert "wania_required_fields_contract_v0_1.md" in path.read_text(
            encoding="utf-8"
        )


def test_minimal_fixture_passes_required_fields_contract() -> None:
    payload = load_payload(MINIMAL_PATH)

    assert_required_fields_contract(payload)
    assert set(payload) == REQUIRED_TOP_LEVEL_FIELDS
    assert set(payload["run"]) == REQUIRED_RUN_FIELDS
    assert payload["capabilities"] == {"static_contact_graph": True}
    assert set(payload["graph"]) == {"nodes", "edges"}
    assert payload["artifacts"] == {}
    assert payload["diagnostics"] == {"passed": True}


def test_minimal_fixture_omits_optional_science() -> None:
    payload = load_payload(MINIMAL_PATH)
    serialized = json.dumps(payload, sort_keys=True)

    for node in payload["graph"]["nodes"]:
        assert set(node) == {"id", "condition", "residue", "x", "y", "z"}
        assert set(node["residue"]) == {"index", "name"}
    for edge in payload["graph"]["edges"]:
        assert set(edge["interaction"]) == {"primary_type"}

    for optional_name in (
        "x_ca",
        "y_ca",
        "z_ca",
        "chain_id",
        "all_edge_types",
        "all_types",
        "n_edge_types",
        "contact_frequency",
        "backbone",
        "aromatic_pi",
        "cation_pi",
        "metrics",
        "communities",
        "contacts_perframe",
        "analysis",
        "temporal",
    ):
        assert f'"{optional_name}"' not in serialized


def test_minimal_fixture_has_no_unsafe_or_generated_paths() -> None:
    payload = load_payload(MINIMAL_PATH)
    serialized = json.dumps(payload, sort_keys=True)

    assert artifact_paths(payload["artifacts"]) == []
    for forbidden in (*FORBIDDEN_ARTIFACT_PARTS, *RAW_ARTIFACT_SUFFIXES):
        assert forbidden not in serialized


def test_stage_16_12_rich_sample_passes_as_nonminimal_superset() -> None:
    minimal = load_payload(MINIMAL_PATH)
    rich = load_payload(RICH_PATH)

    assert_required_fields_contract(rich)
    assert rich != minimal
    assert any("x_ca" in node for node in rich["graph"]["nodes"])
    assert any("all_types" in edge["interaction"] for edge in rich["graph"]["edges"])
    assert rich["artifacts"]
    assert "analysis" in rich["artifacts"]
