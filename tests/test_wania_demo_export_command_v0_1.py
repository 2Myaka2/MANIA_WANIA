import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "wania_assembly_artifacts_v0_1"
    / "graph"
    / "graph.json"
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


def run_mania(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mania", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_payload(path: Path) -> dict[str, Any]:
    def reject_non_json_number(value: str) -> None:
        raise ValueError(f"non-JSON number: {value}")

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


def assert_stage_17_required_fields(payload: dict[str, Any]) -> None:
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
        assert isinstance(interaction.get("primary_type"), str)
        assert interaction["primary_type"]

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


def command_metadata_args() -> tuple[str, ...]:
    return (
        "--run-name",
        "demo_wania_assembly",
        "--protein-id",
        "demo_protein",
        "--protein-name",
        "Demo Protein",
        "--condition-name",
        "normal",
        "--condition-name",
        "tumor",
    )


def test_build_payload_command_writes_demo_ready_json(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "wania_graph_payload.json"

    result = run_mania(
        "wania",
        "build-payload",
        "--graph-json",
        str(GRAPH_PATH),
        "--output",
        str(output_path),
        *command_metadata_args(),
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert f"WANIA payload written: {output_path}" in result.stdout
    assert '"schema_version"' not in result.stdout
    payload = load_payload(output_path)
    assert_json_safe(payload)
    json.dumps(payload, allow_nan=False)
    assert_stage_17_required_fields(payload)
    assert payload["run"]["condition_names"] == ["normal", "tumor"]
    assert payload["graph"]["nodes"]
    assert payload["graph"]["edges"]
    assert payload["artifacts"]["backend_graph_json"] == "graph/graph.json"
    assert isinstance(payload["diagnostics"]["passed"], bool)
    assert payload["diagnostics"]["passed"] is True

    null_diagnostics_payload = json.loads(json.dumps(payload))
    null_diagnostics_payload["diagnostics"]["passed"] = None
    with pytest.raises(AssertionError):
        assert_stage_17_required_fields(null_diagnostics_payload)

    payload_strings = [value.lower() for value in recursive_strings(payload)]
    for marker in BACKEND_ONLY_MARKERS:
        assert all(marker not in value for value in payload_strings)
    for value in payload_strings:
        assert not any(value.endswith(suffix) for suffix in RAW_ARTIFACT_SUFFIXES)


def test_build_payload_command_supports_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"

    result = run_mania(
        "wania",
        "build-payload",
        "--graph-json",
        str(GRAPH_PATH),
        "--output-dir",
        str(output_dir),
        *command_metadata_args(),
    )

    output_path = output_dir / "wania_graph_payload.json"
    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    assert load_payload(output_path)["capabilities"]["rg_timeseries"] is False


def test_build_payload_command_fails_for_missing_graph_json(tmp_path: Path) -> None:
    result = run_mania(
        "wania",
        "build-payload",
        "--graph-json",
        str(tmp_path / "missing" / "graph.json"),
        "--output",
        str(tmp_path / "wania_graph_payload.json"),
        *command_metadata_args(),
    )

    assert result.returncode != 0
    assert "WANIA payload build failed" in result.stderr
    assert "graph JSON artifact is missing" in result.stderr


def test_build_payload_command_requires_run_metadata(tmp_path: Path) -> None:
    result = run_mania(
        "wania",
        "build-payload",
        "--graph-json",
        str(GRAPH_PATH),
        "--output",
        str(tmp_path / "wania_graph_payload.json"),
        "--condition-name",
        "normal",
    )

    assert result.returncode == 2
    assert "--run-name" in result.stderr
    assert "--protein-id" in result.stderr
    assert "--protein-name" in result.stderr


def test_build_payload_command_rejects_duplicate_conditions(
    tmp_path: Path,
) -> None:
    result = run_mania(
        "wania",
        "build-payload",
        "--graph-json",
        str(GRAPH_PATH),
        "--output",
        str(tmp_path / "wania_graph_payload.json"),
        *command_metadata_args(),
        "--condition-name",
        "normal",
    )

    assert result.returncode != 0
    assert "condition names must be unique" in result.stderr
