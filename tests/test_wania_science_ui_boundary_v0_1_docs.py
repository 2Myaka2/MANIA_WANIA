from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_science_ui_boundary_v0_1.md"
REFERENCE_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "wania_mvp_contract_v0_1.md",
    REPO_ROOT / "docs" / "wania_required_fields_contract_v0_1.md",
    REPO_ROOT / "docs" / "wania_object_json_payload_contract.md",
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def doc_text() -> str:
    return normalized(DOC_PATH.read_text(encoding="utf-8"))


def test_wania_science_ui_boundary_v0_1_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_boundary_defines_layers_and_display_contract() -> None:
    text = doc_text()

    for phrase in (
        "Science vs UI boundary",
        "UI-facing",
        "optional scientific annotations",
        "backend-only",
        "future capabilities",
        "display model",
        "computational model",
        "node.id",
        "node.condition",
        "node.residue.index",
        "node.residue.name",
        "node.x",
        "node.y",
        "node.z",
        "edge.interaction.primary_type",
        "diagnostics.passed",
        "artifacts",
    ):
        assert phrase in text


def test_boundary_keeps_scientific_annotations_optional() -> None:
    text = doc_text()

    for phrase in (
        "x_ca/y_ca/z_ca",
        "all_edge_types",
        "contact_frequency",
        "distance statistics",
        "backbone",
        "aromatic_pi",
        "cation_pi",
        "centrality metrics",
        "community",
        "Rg artifact references",
        "contact artifact references",
        "analysis artifact references",
        "must not be required for MVP validity",
        "must not be required for basic graph rendering",
    ):
        assert phrase in text


def test_boundary_records_backend_only_details() -> None:
    text = doc_text()

    for phrase in (
        "InteractionAccumulator",
        "atom cache",
        "contact engine internals",
        "chemistry helper internals",
        "aromatic_pi geometry algorithm",
        "cation_pi geometry algorithm",
        "AtomGroup",
        "MDAnalysis",
        "frame iteration internals",
        "distance evaluation counters",
        "NetworkX",
        "notebook parity implementation details",
        "local_md",
        "local_md_protein",
        "mania_output",
        "raw trajectory paths",
    ):
        assert phrase in text


def test_boundary_records_future_and_stage_limits() -> None:
    text = doc_text()

    for phrase in (
        "temporal RIN",
        "typed RIN full schema",
        "formal statistics",
        "conformational clustering",
        "cross-protein comparison",
        "FastAPI/upload/job API",
        "Stage 16.12 frontend sample",
        "Stage 17.1",
        "Stage 17.2",
        "not schema redesign",
        "not frontend implementation",
        "not runtime validator",
    ):
        assert phrase in text


def test_boundary_separates_values_from_implementation() -> None:
    text = doc_text()

    for phrase in (
        "chemistry detection algorithm is backend-only",
        "Metrics/community values are optional scientific annotations",
        "Metric/community computation methods are backend-only",
        "Artifact file internals are backend/scientific",
        "Backend internals must not become capabilities",
        "rich illustrative payload",
        "not the minimal MVP contract",
    ):
        assert phrase in text


def test_boundary_is_linked_from_required_docs() -> None:
    for path in REFERENCE_PATHS:
        assert "wania_science_ui_boundary_v0_1.md" in path.read_text(
            encoding="utf-8"
        )


def test_stage23a_defines_wania_rin_profile_and_unchanged_render_contract(
) -> None:
    text = doc_text()

    for phrase in (
        "Stage 23.A WANIA RIN profile",
        "MANIA = backend/scientific RIN preprocessing and analysis artifacts",
        "WANIA = stable frontend-facing JSON contract for graph rendering",
        "WANIA base render contract is unchanged",
        "WANIA required fields are unchanged",
        "graph.nodes",
        "graph.edges",
        "x`, `y`, `z` render coordinates",
        "interaction.primary_type",
        "capabilities",
        "artifacts",
        "diagnostics.passed",
    ):
        assert phrase in text


def test_stage23a_distinguishes_static_temporal_and_conformation_artifacts(
) -> None:
    text = doc_text()

    for phrase in (
        "wania_graph_payload.json != analysis/{condition}/graph.json",
        "MANIA backend/scientific static RIN artifact",
        (
            "wania_graph_payload.json != "
            "analysis/{condition}/temporal_rin_{condition}.csv"
        ),
        "MANIA backend/scientific per-window metrics artifact",
        (
            "wania_graph_payload.json != "
            "analysis/{condition}/conformation_pca_{condition}.csv"
        ),
        "!= analysis/{condition}/conformation_labels_{condition}.csv",
        "computed PCA is not implemented",
        "n_components = 0",
        "fingerprint-based clustering labels",
        "PCA-based clustering is not claimed",
        "notebook PCA-to-k-means parity is not claimed",
    ):
        assert phrase in text


def test_stage23a_freezes_optional_scientific_artifact_boundary() -> None:
    text = doc_text()

    for phrase in (
        "Scientific artifacts may be referenced",
        (
            "Scientific artifacts must not be inlined into the base WANIA "
            "graph payload"
        ),
        "Scientific artifacts must not become required for base graph rendering",
        "centrality values",
        "community IDs",
        "region-enrichment values",
        "temporal window rows",
        "PCA coordinates",
        "conformation labels",
        "selected_k",
        "silhouette_score",
        "representative-frame flags",
        "raw per-frame contact rows",
        "Louvain is not implemented",
        "full statistical parity is not claimed",
    ):
        assert phrase in text


def test_stage23a_preserves_later_stage_and_runtime_boundaries() -> None:
    text = doc_text()

    for phrase in (
        "Stage 23.A defines no reference mapping",
        "Capabilities alignment belongs to Stage 23.B",
        (
            "artifact-reference alignment and demo payload policy belong "
            "to Stage 23.C"
        ),
        "WANIA contract-test updates belong to Stage 23.D",
        "documentation acceptance checklist belongs to Stage 23.E",
        "Capabilities are not changed",
        "artifact references are not changed",
        "demo payload is not regenerated",
        (
            "Stages 20, 21, and 22 artifact schemas and scientific behavior "
            "remain unchanged"
        ),
        "No numerical backend dependency is added",
        "Stage 24 has not started",
        (
            "API, Docker, database, frontend implementation, and production "
            "workers remain unimplemented"
        ),
    ):
        assert phrase in text
