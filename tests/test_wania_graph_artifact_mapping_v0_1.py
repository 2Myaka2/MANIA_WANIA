import json
import math
from pathlib import Path
from typing import Any

from mania.wania import (
    WaniaGraphPayloadArtifactPaths,
    WaniaGraphPayloadRunMetadata,
    build_wania_graph_payload_from_artifacts,
    write_wania_graph_payload_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    REPO_ROOT / "tests" / "fixtures" / "wania_assembly_artifacts_v0_1"
)
GRAPH_PATH = FIXTURE_ROOT / "graph" / "graph.json"
MINIMAL_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "wania_mvp_minimal_payload_v0_1.json"
)
RICH_PATH = REPO_ROOT / "tests" / "fixtures" / (
    "wania_graph_payload_frontend_sample_v0_1.json"
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
FORBIDDEN_PATH_PARTS = {"local_md", "local_md_protein", "mania_output"}
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
BACKEND_ONLY_MARKERS = {
    "interactionaccumulator",
    "atom_cache",
    "atomgroup",
    "residuegroup",
    "mdanalysis",
    "local_md",
    "local_md_protein",
    "mania_output",
    "raw trajectory",
    "notebook cell",
    "distance evaluation counter",
    "graph library internal",
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


def recursive_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            text
            for key, child in value.items()
            for text in (str(key), *recursive_strings(child))
        ]
    if isinstance(value, list):
        return [text for child in value for text in recursive_strings(child)]
    return []


def artifact_references(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            path
            for child in value.values()
            for path in artifact_references(child)
        ]
    if isinstance(value, list):
        return [
            path for child in value for path in artifact_references(child)
        ]
    return []


def assert_json_safe(value: object) -> None:
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        assert math.isfinite(value)
        return
    if isinstance(value, list):
        for child in value:
            assert_json_safe(child)
        return
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    for child in value.values():
        assert_json_safe(child)


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
            coordinate = node[field]
            assert isinstance(coordinate, int | float)
            assert not isinstance(coordinate, bool)
            assert math.isfinite(coordinate)

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
    for path_value in artifact_references(artifacts):
        path = Path(path_value)
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert not FORBIDDEN_PATH_PARTS & set(path.parts)
        assert path.suffix.lower() not in RAW_ARTIFACT_SUFFIXES

    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, dict)
    assert "passed" in diagnostics
    assert isinstance(diagnostics["passed"], bool)


def metadata() -> WaniaGraphPayloadRunMetadata:
    return WaniaGraphPayloadRunMetadata(
        job_id="stage_18_2_fixture",
        run_name="synthetic_mapping_run",
        protein_id="synthetic_protein",
        protein_name="Synthetic protein",
        condition_names=("normal", "tumor"),
    )


def all_artifact_paths() -> WaniaGraphPayloadArtifactPaths:
    return WaniaGraphPayloadArtifactPaths(
        graph_json_path=GRAPH_PATH,
        nodes_csv_path=FIXTURE_ROOT / "graph" / "nodes.csv",
        edges_csv_path=FIXTURE_ROOT / "graph" / "edges.csv",
        diagnostics_report_json_path=(
            FIXTURE_ROOT / "reports" / "graph_diagnostics_report.json"
        ),
        contact_edges_csv_path=(
            FIXTURE_ROOT / "contacts" / "contact_edges.csv"
        ),
        contacts_perframe_csv_path=(
            FIXTURE_ROOT / "contacts" / "contacts_perframe.csv"
        ),
        analysis_metrics_csv_paths={
            "normal": FIXTURE_ROOT / "analysis" / "metrics_normal.csv"
        },
        analysis_communities_csv_paths={
            "normal": FIXTURE_ROOT / "analysis" / "communities_normal.csv"
        },
        analysis_metrics_report_json_path=(
            FIXTURE_ROOT / "analysis" / "analysis_metrics_report.json"
        ),
    )


def test_maps_graph_artifacts_to_stage_17_wania_mvp_and_writes_json(
    tmp_path: Path,
) -> None:
    paths = all_artifact_paths()
    for path in (
        paths.graph_json_path,
        paths.nodes_csv_path,
        paths.edges_csv_path,
        paths.diagnostics_report_json_path,
        paths.contact_edges_csv_path,
        paths.contacts_perframe_csv_path,
        *paths.analysis_metrics_csv_paths.values(),
        *paths.analysis_communities_csv_paths.values(),
        paths.analysis_metrics_report_json_path,
    ):
        assert path is not None and path.is_file()

    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=paths,
        output_root=FIXTURE_ROOT,
    )

    assert result.passed is True
    assert result.issues == ()
    payload = result.payload
    assert isinstance(payload, dict)
    assert_required_fields_contract(payload)
    assert_json_safe(payload)
    json.dumps(payload, allow_nan=False)

    graph = payload["graph"]
    assert isinstance(graph, dict)
    nodes = graph["nodes"]
    edges = graph["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert nodes[0]["x_ca"] == 0.1
    assert nodes[0]["y_ca"] == 1.1
    assert nodes[0]["z_ca"] == 2.1
    assert edges[0]["interaction"] == {
        "primary_type": "backbone",
        "all_types": ["backbone", "residue_contact"],
    }
    assert edges[0]["metrics"] == {
        "contact_frequency": 0.75,
        "mean_distance_A": 3.8,
    }
    assert edges[1]["interaction"] == {
        "primary_type": "aromatic_pi",
        "all_types": ["aromatic_pi", "cation_pi"],
    }

    expected_references = {
        "graph/graph.json",
        "graph/nodes.csv",
        "graph/edges.csv",
        "reports/graph_diagnostics_report.json",
        "contacts/contact_edges.csv",
        "contacts/contacts_perframe.csv",
        "analysis/metrics_normal.csv",
        "analysis/communities_normal.csv",
        "analysis/analysis_metrics_report.json",
    }
    assert expected_references <= set(artifact_references(payload["artifacts"]))
    assert payload["diagnostics"] == {
        "passed": True,
        "report_path": "reports/graph_diagnostics_report.json",
    }

    serialized = json.dumps(payload, sort_keys=True, allow_nan=False)
    assert "csv_fixture_content_stage_18_2" not in serialized
    payload_strings = [value.lower() for value in recursive_strings(payload)]
    for marker in BACKEND_ONLY_MARKERS:
        assert all(marker not in value for value in payload_strings)
    for value in payload_strings:
        assert not any(value.endswith(suffix) for suffix in RAW_ARTIFACT_SUFFIXES)

    output_path = tmp_path / "wania_graph_payload.json"
    write_result = write_wania_graph_payload_json(payload, output_path)
    assert write_result.passed is True
    assert write_result.output_path == output_path
    loaded = load_payload(output_path)
    assert loaded == payload
    assert_required_fields_contract(loaded)
    assert_json_safe(loaded)


def test_mapping_remains_valid_without_optional_science(tmp_path: Path) -> None:
    backend_graph = load_payload(GRAPH_PATH)
    for node in backend_graph["nodes"]:
        for field in ("x_ca", "y_ca", "z_ca"):
            node.pop(field, None)
    for edge in backend_graph["edges"]:
        edge["edge_type"] = "residue_contact"
        for field in (
            "all_edge_types",
            "n_edge_types",
            "contact_freq",
            "mean_dist_A",
        ):
            edge.pop(field, None)

    output_root = tmp_path / "minimal_artifacts"
    graph_path = output_root / "graph" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps(backend_graph, indent=2) + "\n",
        encoding="utf-8",
    )
    diagnostics_path = output_root / "reports" / "graph_diagnostics_report.json"
    diagnostics_path.parent.mkdir(parents=True)
    diagnostics_path.write_text('{"passed": true}\n', encoding="utf-8")
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=WaniaGraphPayloadArtifactPaths(
            graph_json_path=graph_path,
            diagnostics_report_json_path=diagnostics_path,
        ),
        output_root=output_root,
    )

    assert result.passed is True
    assert result.issues == ()
    assert_required_fields_contract(result.payload)
    assert_json_safe(result.payload)
    graph = result.payload["graph"]
    assert isinstance(graph, dict)
    assert all(edge["metrics"] == {} for edge in graph["edges"])
    assert all(
        edge["interaction"]["primary_type"] == "residue_contact"
        for edge in graph["edges"]
    )
    assert "analysis" not in result.payload["artifacts"]
    assert result.payload["capabilities"]["centrality_metrics"] is False
    assert result.payload["capabilities"]["community_detection"] is False


def test_stage_17_minimal_and_stage_16_12_rich_regressions() -> None:
    minimal = load_payload(MINIMAL_PATH)
    rich = load_payload(RICH_PATH)

    assert_required_fields_contract(minimal)
    assert_required_fields_contract(rich)
    assert rich != minimal
    assert minimal["artifacts"] == {}
    assert all("x_ca" not in node for node in minimal["graph"]["nodes"])
    assert all(
        set(edge["interaction"]) == {"primary_type"}
        for edge in minimal["graph"]["edges"]
    )
    assert any("x_ca" in node for node in rich["graph"]["nodes"])
    assert any(
        "all_types" in edge["interaction"] for edge in rich["graph"]["edges"]
    )
    assert rich["artifacts"]
    assert "analysis" in rich["artifacts"]
