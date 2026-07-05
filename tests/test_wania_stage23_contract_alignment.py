import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from mania.wania import (
    WaniaGraphPayloadArtifactPaths,
    WaniaGraphPayloadRunMetadata,
    build_wania_graph_payload_from_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
ASSEMBLY_ROOT = FIXTURE_ROOT / "wania_assembly_artifacts_v0_1"
MINIMAL_PATH = FIXTURE_ROOT / "wania_mvp_minimal_payload_v0_1.json"
RICH_PATH = FIXTURE_ROOT / "wania_graph_payload_frontend_sample_v0_1.json"
BOUNDARY_DOC_PATH = REPO_ROOT / "docs" / "wania_science_ui_boundary_v0_1.md"

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
REQUIRED_NODE_FIELDS = {"id", "condition", "residue", "x", "y", "z"}
REQUIRED_EDGE_FIELDS = {
    "id",
    "source",
    "target",
    "condition",
    "interaction",
}
CURRENT_CAPABILITIES = {
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
}
FORBIDDEN_NODE_FIELDS = {
    "centrality",
    "community_id",
    "region_enrichment",
    "temporal_window",
    "temporal_rin",
    "contacts_perframe_rows",
    "pca_pc1",
    "pca_pc2",
    "pca_pc3",
    "conformation_label",
    "selected_k",
    "silhouette_score",
    "is_representative",
}
FORBIDDEN_EDGE_FIELDS = {
    "temporal_window",
    "temporal_frequency_series",
    "contacts_perframe_rows",
    "centrality",
    "community_id",
}
FORBIDDEN_PAYLOAD_CLAIMS = {
    "computed_pca",
    "pca_based_clustering",
    "notebook_pca_kmeans_parity",
    "louvain",
    "mwu",
    "fdr_bh",
    "bootstrap_ci",
    "api_endpoint",
    "frontend_route",
    "database_table",
    "worker_job",
}
SCIENTIFIC_COORDINATE_FIELDS = {
    "x_ca",
    "y_ca",
    "z_ca",
    "tm_relative_z",
    "rmsf_A",
    "sasa_A2",
    "ss",
}


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for child in value.values() for key in recursive_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in recursive_keys(child)}
    return set()


def artifact_reference_leaves(value: object) -> list[object]:
    if isinstance(value, dict):
        return [
            leaf
            for child in value.values()
            for leaf in artifact_reference_leaves(child)
        ]
    return [value]


def metadata() -> WaniaGraphPayloadRunMetadata:
    return WaniaGraphPayloadRunMetadata(
        job_id="stage_23d_contract",
        run_name="synthetic_stage_23d",
        protein_id="synthetic_protein",
        protein_name="Synthetic protein",
        condition_names=("normal", "tumor"),
    )


def build_payload(
    *, include_optional_science: bool
) -> tuple[dict[str, Any], bool]:
    paths = WaniaGraphPayloadArtifactPaths(
        graph_json_path=ASSEMBLY_ROOT / "graph" / "graph.json",
        diagnostics_report_json_path=(
            ASSEMBLY_ROOT / "reports" / "graph_diagnostics_report.json"
        ),
        rg_timeseries_csv_path=(
            ASSEMBLY_ROOT / "rg" / "rg_timeseries.csv"
            if include_optional_science
            else None
        ),
        contact_edges_csv_path=(
            ASSEMBLY_ROOT / "contacts" / "contact_edges.csv"
            if include_optional_science
            else None
        ),
        contacts_perframe_csv_path=(
            ASSEMBLY_ROOT / "contacts" / "contacts_perframe.csv"
            if include_optional_science
            else None
        ),
        analysis_metrics_csv_paths=(
            {"normal": ASSEMBLY_ROOT / "analysis" / "metrics_normal.csv"}
            if include_optional_science
            else None
        ),
        analysis_communities_csv_paths=(
            {
                "normal": (
                    ASSEMBLY_ROOT / "analysis" / "communities_normal.csv"
                )
            }
            if include_optional_science
            else None
        ),
        analysis_metrics_report_json_path=(
            ASSEMBLY_ROOT / "analysis" / "analysis_metrics_report.json"
            if include_optional_science
            else None
        ),
    )
    result = build_wania_graph_payload_from_artifacts(
        run_metadata=metadata(),
        artifact_paths=paths,
        output_root=ASSEMBLY_ROOT,
    )
    assert isinstance(result.payload, dict)
    return result.payload, result.passed


def assert_no_inline_science(payload: dict[str, Any]) -> None:
    graph = payload["graph"]
    assert isinstance(graph, dict)
    for node in graph["nodes"]:
        assert FORBIDDEN_NODE_FIELDS.isdisjoint(node)
    for edge in graph["edges"]:
        assert FORBIDDEN_EDGE_FIELDS.isdisjoint(edge)
    assert FORBIDDEN_PAYLOAD_CLAIMS.isdisjoint(recursive_keys(payload))


def test_required_fields_and_render_coordinates_remain_stable() -> None:
    payload = load_payload(MINIMAL_PATH)

    assert set(payload) == REQUIRED_TOP_LEVEL_FIELDS
    assert set(payload["run"]) == REQUIRED_RUN_FIELDS
    assert payload["capabilities"] == {"static_contact_graph": True}
    assert set(payload["graph"]) == {"nodes", "edges"}
    assert payload["artifacts"] == {}
    assert isinstance(payload["diagnostics"]["passed"], bool)

    for node in payload["graph"]["nodes"]:
        assert set(node) == REQUIRED_NODE_FIELDS
        assert set(node["residue"]) == {"index", "name"}
        assert SCIENTIFIC_COORDINATE_FIELDS.isdisjoint(node)
        assert all(isinstance(node[axis], int | float) for axis in ("x", "y", "z"))
    for edge in payload["graph"]["edges"]:
        assert set(edge) == REQUIRED_EDGE_FIELDS
        assert set(edge["interaction"]) == {"primary_type"}

    assert_no_inline_science(payload)


def test_optional_science_is_not_required_for_a_valid_base_payload() -> None:
    payload, passed = build_payload(include_optional_science=False)

    assert passed is True
    assert REQUIRED_TOP_LEVEL_FIELDS <= payload.keys()
    assert set(payload["capabilities"]) == CURRENT_CAPABILITIES
    assert payload["capabilities"]["static_contact_graph"] is True
    for capability in CURRENT_CAPABILITIES - {"static_contact_graph"}:
        assert payload["capabilities"][capability] is False
    assert payload["diagnostics"]["passed"] is True
    assert "analysis" not in payload["artifacts"]
    assert payload["artifacts"] == {
        "backend_graph_json": "graph/graph.json",
        "nodes_csv": None,
        "edges_csv": None,
        "rg_timeseries_csv": None,
        "contact_edges_csv": None,
        "contacts_perframe_csv": None,
        "diagnostics_report_json": "reports/graph_diagnostics_report.json",
    }
    assert_no_inline_science(payload)


def test_artifacts_are_file_references_and_never_embedded_rows() -> None:
    payload, passed = build_payload(include_optional_science=True)

    assert passed is True
    leaves = artifact_reference_leaves(payload["artifacts"])
    assert leaves
    assert all(leaf is None or isinstance(leaf, str) for leaf in leaves)
    references = [leaf for leaf in leaves if isinstance(leaf, str)]
    assert references
    assert all(Path(reference).suffix in {".csv", ".json"} for reference in references)
    assert all(not Path(reference).is_absolute() for reference in references)
    assert payload["capabilities"]["centrality_metrics"] is True
    assert payload["capabilities"]["community_detection"] is True
    assert payload["capabilities"]["temporal_rin"] is False
    assert payload["capabilities"]["conformational_states"] is False
    assert payload["capabilities"]["cross_condition_statistics"] is False
    assert_no_inline_science(payload)


def test_demo_payload_remains_conservative_and_contains_no_scientific_tables(
) -> None:
    payload = load_payload(RICH_PATH)

    assert_no_inline_science(payload)
    assert payload["capabilities"]["conformational_states"] is False
    assert payload["capabilities"]["cross_condition_statistics"] is False
    assert payload["capabilities"]["temporal_rin"] is False
    for node in payload["graph"]["nodes"]:
        assert FORBIDDEN_NODE_FIELDS.isdisjoint(node)
    for leaf in artifact_reference_leaves(payload["artifacts"]):
        assert isinstance(leaf, str)

    serialized = json.dumps(payload, sort_keys=True).lower()
    for claim in FORBIDDEN_PAYLOAD_CLAIMS:
        assert claim not in serialized
    for marker in ("local_md", "local_md_protein", "mania_output", ".xtc", ".tpr"):
        assert marker not in serialized


def test_demo_export_is_deterministic_without_fixture_regeneration(
    tmp_path: Path,
) -> None:
    outputs = (tmp_path / "first.json", tmp_path / "second.json")
    command_prefix = (
        sys.executable,
        "-m",
        "mania",
        "wania",
        "build-payload",
        "--graph-json",
        str(ASSEMBLY_ROOT / "graph" / "graph.json"),
        "--run-name",
        "synthetic_stage_23d",
        "--protein-id",
        "synthetic_protein",
        "--protein-name",
        "Synthetic protein",
        "--condition-name",
        "normal",
        "--condition-name",
        "tumor",
    )

    for output in outputs:
        result = subprocess.run(
            (*command_prefix, "--output", str(output)),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    payload = load_payload(outputs[0])
    assert isinstance(payload["diagnostics"]["passed"], bool)
    assert_no_inline_science(payload)


def test_stage23a_to_stage23c_policy_language_remains_authoritative() -> None:
    text = " ".join(BOUNDARY_DOC_PATH.read_text(encoding="utf-8").split())

    for phrase in (
        "MANIA = backend/scientific RIN preprocessing and analysis artifacts",
        "WANIA = stable frontend-facing JSON contract for graph rendering",
        "Scientific artifacts may be referenced",
        "Scientific artifacts must not be inlined into the base WANIA graph payload",
        "Scientific artifacts must not become required for base graph rendering",
        "boolean-only and payload-specific",
        "artifact reference != artifact content",
        "every MANIA scientific artifact reference inside it is optional",
        "Missing optional science is not a diagnostics failure",
        "Stage 23.C is policy-only",
    ):
        assert phrase in text

    for limitation in (
        "computed PCA and PCA coordinates are unavailable",
        "notebook PCA-to-k-means parity is not claimed",
        "Louvain is not implemented",
        "does not claim full statistical notebook parity",
    ):
        assert limitation in text
