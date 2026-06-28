import json
from pathlib import Path
from typing import Any

import pytest

from mania.wania import (
    WaniaGraphPayloadArtifactPaths,
    WaniaGraphPayloadRunMetadata,
    WaniaGraphPayloadWriteResult,
    build_wania_graph_payload_from_artifacts,
    write_wania_graph_payload_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / (
    "wania_backend_graph_minimal.json"
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


def load_fixture_graph() -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def output_paths(
    tmp_path: Path,
    graph_payload: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    output_root = tmp_path / "napi2b_10ns_protein"
    graph_path = output_root / "graph" / "graph.json"
    write_json(graph_path, graph_payload or load_fixture_graph())
    return output_root, graph_path


def metadata(
    *,
    protein_id: str | None = "napi2b",
    protein_name: str | None = "NaPi2b",
    run_name: str | None = "napi2b_10ns_protein",
    condition_names: tuple[str, ...] = ("normal",),
) -> WaniaGraphPayloadRunMetadata:
    return WaniaGraphPayloadRunMetadata(
        job_id="job_001",
        protein_id=protein_id,
        protein_name=protein_name,
        run_name=run_name,
        condition_names=condition_names,
    )


def artifact_paths(
    output_root: Path,
    graph_path: Path,
    *,
    diagnostics_report_json_path: Path | None = None,
    rg_timeseries_csv_path: Path | None = None,
    contact_edges_csv_path: Path | None = None,
    contacts_perframe_csv_path: Path | None = None,
) -> WaniaGraphPayloadArtifactPaths:
    return WaniaGraphPayloadArtifactPaths(
        graph_json_path=graph_path,
        nodes_csv_path=output_root / "graph" / "nodes.csv",
        edges_csv_path=output_root / "graph" / "edges.csv",
        diagnostics_report_json_path=diagnostics_report_json_path,
        rg_timeseries_csv_path=rg_timeseries_csv_path,
        contact_edges_csv_path=contact_edges_csv_path,
        contacts_perframe_csv_path=contacts_perframe_csv_path,
    )


def build_payload(
    tmp_path: Path,
    *,
    graph_payload: dict[str, Any] | None = None,
    run_metadata: WaniaGraphPayloadRunMetadata | None = None,
    paths: WaniaGraphPayloadArtifactPaths | None = None,
) -> tuple[Path, dict[str, Any], list[str]]:
    output_root, graph_path = output_paths(tmp_path, graph_payload)
    artifacts = paths or artifact_paths(output_root, graph_path)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=run_metadata or metadata(),
        artifact_paths=artifacts,
        output_root=output_root,
    )
    assert json.dumps(result.to_dict(), allow_nan=False)
    return output_root, result.payload, [issue.kind for issue in result.issues]


def test_public_exports_exist() -> None:
    assert WaniaGraphPayloadArtifactPaths is not None
    assert WaniaGraphPayloadRunMetadata is not None
    assert WaniaGraphPayloadWriteResult is not None
    assert build_wania_graph_payload_from_artifacts is not None
    assert write_wania_graph_payload_json is not None


def test_builds_minimal_payload_from_synthetic_backend_graph_json(
    tmp_path: Path,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    rg_path = output_root / "rg" / "rg_timeseries.csv"
    contact_path = output_root / "contacts" / "contact_edges.csv"
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(
            output_root,
            graph_path,
            rg_timeseries_csv_path=rg_path,
            contact_edges_csv_path=contact_path,
        ),
        output_root=output_root,
    )

    assert result.passed is True
    assert result.payload["schema_version"] == "wania_graph.v0.1"
    assert result.payload["run"] == {
        "job_id": "job_001",
        "run_name": "napi2b_10ns_protein",
        "protein_id": "napi2b",
        "protein_name": "NaPi2b",
        "condition_names": ["normal"],
    }

    capabilities = result.payload["capabilities"]
    assert isinstance(capabilities, dict)
    assert capabilities["static_contact_graph"] is True
    assert capabilities["rg_timeseries"] is True
    assert capabilities["aggregate_contacts"] is True
    assert capabilities["contacts_perframe"] is False
    for capability in FUTURE_CAPABILITIES:
        assert capabilities[capability] is False

    graph = result.payload["graph"]
    assert isinstance(graph, dict)
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    assert all(isinstance(node, dict) for node in graph["nodes"])
    assert all(isinstance(edge, dict) for edge in graph["edges"])

    node = graph["nodes"][0]
    assert node["id"] == "normal|A|123|123|LYS"
    assert node["label"] == "LYS123"
    assert node["condition"] == "normal"
    assert node["residue"] == {
        "index": 123,
        "id": "123",
        "name": "LYS",
        "chain_id": "A",
    }
    assert node["metrics"] == {}

    edge = graph["edges"][0]
    assert edge["source"] == "normal|A|123|123|LYS"
    assert edge["target"] == "normal|A|150|150|ASP"
    assert edge["condition"] == "normal"
    assert edge["interaction"] == {
        "primary_type": "residue_contact",
        "all_types": ["residue_contact"],
    }
    assert edge["metrics"] == {
        "contact_frequency": 0.74,
        "mean_distance_A": 3.8,
    }


def test_builds_multi_condition_payload(tmp_path: Path) -> None:
    payload = load_fixture_graph()
    payload["condition"] = "normal"
    payload["nodes"].extend(
        [
            {
                "id": "tumor|A|123|123|LYS",
                "resid": "tumor|A|123|123|LYS",
                "resname": "LYS",
                "condition": "tumor",
            },
            {
                "id": "tumor|A|150|150|ASP",
                "resid": "tumor|A|150|150|ASP",
                "resname": "ASP",
                "condition": "tumor",
            },
        ]
    )
    payload["edges"].append(
        {
            "source": "tumor|A|123|123|LYS",
            "target": "tumor|A|150|150|ASP",
            "edge_type": "residue_contact",
            "all_edge_types": "residue_contact,vdw",
            "condition": "tumor",
            "contact_freq": "0.64",
        }
    )
    output_root, graph_path = output_paths(tmp_path, payload)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(condition_names=("normal", "tumor")),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert result.passed is True
    run = result.payload["run"]
    graph = result.payload["graph"]
    assert isinstance(run, dict)
    assert isinstance(graph, dict)
    assert run["condition_names"] == ["normal", "tumor"]
    assert graph["conditions"] == [
        {"id": "normal", "label": "normal"},
        {"id": "tumor", "label": "tumor"},
    ]
    assert {node["condition"] for node in graph["nodes"]} == {"normal", "tumor"}
    assert {edge["condition"] for edge in graph["edges"]} == {"normal", "tumor"}
    assert "condition" not in result.payload


def test_preserves_backbone_interaction_without_enabling_typed_rin(
    tmp_path: Path,
) -> None:
    backend_graph = load_fixture_graph()
    edge = backend_graph["edges"][0]
    edge["edge_type"] = "backbone"
    edge["all_edge_types"] = "backbone|vdw"
    edge["n_edge_types"] = "2"

    _, payload, issues = build_payload(tmp_path, graph_payload=backend_graph)

    assert issues == []
    graph = payload["graph"]
    assert graph["edges"][0]["interaction"] == {
        "primary_type": "backbone",
        "all_types": ["backbone", "vdw"],
    }
    assert payload["capabilities"]["typed_rin_interactions"] is False


def test_wania_nodes_preserve_json_safe_ca_coordinates(
    tmp_path: Path,
) -> None:
    payload = load_fixture_graph()
    payload["nodes"][0].update(
        {
            "x": 121.22,
            "y": 83.81,
            "z": 98.52,
            "x_ca": 121.22,
            "y_ca": 83.81,
            "z_ca": 98.52,
        }
    )

    _, wania_payload, issues = build_payload(tmp_path, graph_payload=payload)
    node = wania_payload["graph"]["nodes"][0]

    assert issues == []
    assert {
        field: node[field]
        for field in ("x", "y", "z", "x_ca", "y_ca", "z_ca")
    } == {
        "x": 121.22,
        "y": 83.81,
        "z": 98.52,
        "x_ca": 121.22,
        "y_ca": 83.81,
        "z_ca": 98.52,
    }
    json.dumps(node, allow_nan=False)


@pytest.mark.parametrize(
    ("run_metadata", "field"),
    (
        (metadata(protein_id=""), "run_metadata.protein_id"),
        (metadata(protein_name=""), "run_metadata.protein_name"),
        (metadata(run_name=""), "run_metadata.run_name"),
        (metadata(condition_names=()), "run_metadata.condition_names"),
    ),
)
def test_explicit_protein_metadata_is_required(
    tmp_path: Path,
    run_metadata: WaniaGraphPayloadRunMetadata,
    field: str,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=run_metadata,
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert result.passed is False
    assert result.payload == {}
    assert [
        (issue.kind, issue.field, issue.fatal)
        for issue in result.issues
        if issue.kind == "run_metadata_missing"
    ] == [("run_metadata_missing", field, True)]


def test_adapter_does_not_infer_protein_id_from_output_path(
    tmp_path: Path,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(protein_id=""),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert "napi2b_10ns" in str(graph_path)
    assert result.passed is False
    assert result.payload == {}
    assert any(
        issue.kind == "run_metadata_missing"
        and issue.field == "run_metadata.protein_id"
        for issue in result.issues
    )


def test_condition_mismatch_fails_deterministically(tmp_path: Path) -> None:
    payload = load_fixture_graph()
    payload["nodes"][0]["condition"] = "mutant"
    output_root, graph_path = output_paths(tmp_path, payload)

    first = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(condition_names=("normal",)),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )
    second = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(condition_names=("normal",)),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert first.passed is False
    assert [issue.to_dict() for issue in first.issues] == [
        issue.to_dict() for issue in second.issues
    ]
    assert any(
        issue.kind == "condition_mismatch"
        and issue.condition == "mutant"
        and issue.fatal
        for issue in first.issues
    )


def test_metadata_condition_absent_from_graph_is_non_fatal(
    tmp_path: Path,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(condition_names=("normal", "tumor")),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert result.passed is True
    assert [
        issue.to_dict()
        for issue in result.issues
        if issue.kind == "metadata_condition_absent_from_graph"
    ] == [
        {
            "kind": "metadata_condition_absent_from_graph",
            "message": (
                "Run metadata condition is not present in backend graph "
                "nodes or edges."
            ),
            "fatal": False,
            "field": "run_metadata.condition_names",
            "path": None,
            "condition": "tumor",
            "record_id": None,
        }
    ]


def test_artifact_paths_are_relative_and_missing_optional_paths_are_null(
    tmp_path: Path,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )

    assert result.passed is True
    artifacts = result.payload["artifacts"]
    assert isinstance(artifacts, dict)
    assert artifacts == {
        "backend_graph_json": "graph/graph.json",
        "nodes_csv": "graph/nodes.csv",
        "edges_csv": "graph/edges.csv",
        "rg_timeseries_csv": None,
        "contact_edges_csv": None,
        "contacts_perframe_csv": None,
        "diagnostics_report_json": None,
    }
    assert all(
        value is None or not Path(value).is_absolute()
        for value in artifacts.values()
    )


def test_payload_uses_object_json_style(tmp_path: Path) -> None:
    _, payload, _ = build_payload(tmp_path)
    graph = payload["graph"]
    assert isinstance(graph, dict)

    for compact_key in ("node_fields", "edge_fields"):
        assert compact_key not in payload
        assert compact_key not in graph
    assert all(isinstance(node, dict) for node in graph["nodes"])
    assert all(isinstance(edge, dict) for edge in graph["edges"])


def test_writer_creates_valid_json_and_respects_overwrite(
    tmp_path: Path,
) -> None:
    _, payload, _ = build_payload(tmp_path)
    output_path = tmp_path / "nested" / "wania_graph_payload.json"

    first = write_wania_graph_payload_json(payload, output_path)
    assert first.passed is True
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "wania_graph.v0.1"

    output_path.write_text('{"sentinel": true}\n', encoding="utf-8")
    second = write_wania_graph_payload_json(
        payload,
        output_path,
        overwrite=False,
    )
    assert second.passed is False
    assert [issue.kind for issue in second.issues] == ["write_failed"]
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "sentinel": True,
    }


def test_writer_reports_deterministic_issue_on_write_failure(
    tmp_path: Path,
) -> None:
    _, payload, _ = build_payload(tmp_path)
    output_dir = tmp_path / "already_dir"
    output_dir.mkdir()

    result = write_wania_graph_payload_json(payload, output_dir)

    assert result.passed is False
    assert [issue.to_dict() for issue in result.issues] == [
        {
            "kind": "write_failed",
            "message": "Output path is a directory.",
            "fatal": True,
            "field": "output_path",
            "path": str(output_dir),
            "condition": None,
            "record_id": None,
        }
    ]


def test_diagnostics_summary_is_parsed_and_missing_report_is_non_fatal(
    tmp_path: Path,
) -> None:
    output_root, graph_path = output_paths(tmp_path)
    diagnostics_path = output_root / "reports" / "graph_diagnostics_report.json"
    write_json(diagnostics_path, {"passed": True, "status": "passed"})
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(
            output_root,
            graph_path,
            diagnostics_report_json_path=diagnostics_path,
        ),
        output_root=output_root,
    )

    assert result.passed is True
    assert result.payload["diagnostics"] == {
        "passed": True,
        "report_path": "reports/graph_diagnostics_report.json",
    }

    missing_path = output_root / "reports" / "missing.json"
    missing = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(
            output_root,
            graph_path,
            diagnostics_report_json_path=missing_path,
        ),
        output_root=output_root,
    )
    assert missing.passed is True
    assert missing.payload["diagnostics"] == {
        "passed": None,
        "report_path": "reports/missing.json",
    }
    assert [issue.kind for issue in missing.issues] == [
        "diagnostics_report_missing"
    ]


def test_capabilities_follow_provided_artifact_paths(tmp_path: Path) -> None:
    output_root, graph_path = output_paths(tmp_path)
    no_optional = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(output_root, graph_path),
        output_root=output_root,
    )
    assert no_optional.capabilities["static_contact_graph"] is True
    assert no_optional.capabilities["rg_timeseries"] is False
    assert no_optional.capabilities["aggregate_contacts"] is False
    assert no_optional.capabilities["contacts_perframe"] is False

    all_optional = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=artifact_paths(
            output_root,
            graph_path,
            rg_timeseries_csv_path=output_root / "rg" / "rg_timeseries.csv",
            contact_edges_csv_path=output_root / "contacts" / "contact_edges.csv",
            contacts_perframe_csv_path=(
                output_root / "contacts" / "contacts_perframe.csv"
            ),
        ),
        output_root=output_root,
    )

    assert all_optional.capabilities["rg_timeseries"] is True
    assert all_optional.capabilities["aggregate_contacts"] is True
    assert all_optional.capabilities["contacts_perframe"] is True
    for capability in FUTURE_CAPABILITIES:
        assert all_optional.capabilities[capability] is False


def test_missing_and_invalid_graph_json_fail_clearly(tmp_path: Path) -> None:
    output_root = tmp_path / "napi2b_10ns_protein"
    missing_path = output_root / "graph" / "graph.json"
    missing = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=WaniaGraphPayloadArtifactPaths(
            graph_json_path=missing_path,
        ),
        output_root=output_root,
    )
    assert missing.passed is False
    assert [issue.kind for issue in missing.issues] == ["graph_json_missing"]

    invalid_path = output_root / "graph" / "invalid_graph.json"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_text("{not json", encoding="utf-8")
    invalid = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=WaniaGraphPayloadArtifactPaths(
            graph_json_path=invalid_path,
        ),
        output_root=output_root,
    )
    assert invalid.passed is False
    assert [issue.kind for issue in invalid.issues] == ["graph_json_invalid"]
