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


def test_stage23b_defines_boolean_capability_semantics() -> None:
    text = doc_text()

    for phrase in (
        "Stage 23.B capability alignment",
        "boolean-only and payload-specific",
        "The boolean model cannot encode `partial` by itself",
        "A capability may indicate backend/scientific artifact availability",
        (
            "A capability does not mean scientific contents are embedded in "
            "the base WANIA graph payload"
        ),
        "does not make a scientific artifact required for base graph rendering",
        "does not change the existing boolean keys",
        "Artifact-reference mapping and demo-payload policy remain Stage 23.C",
    ):
        assert phrase in text


def test_stage23b_aligns_every_current_adapter_capability() -> None:
    text = doc_text()

    for capability in (
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
    ):
        assert f"`{capability}`" in text

    for phrase in (
        "available when its existing optional path is supplied",
        "backend semantics available; current WANIA capability unavailable",
        "available with a limited deterministic fallback",
        "limited backend availability; current WANIA capability unavailable",
        "partial/limited backend availability",
        "unavailable/deferred",
        "unavailable/future scope",
    ):
        assert phrase in text


def test_stage23b_preserves_partial_and_unavailable_limitations() -> None:
    text = doc_text()

    for phrase in (
        "Louvain is not implemented",
        "computed PCA and PCA coordinates are unavailable",
        "Clustering does not use PCA coordinates",
        "notebook PCA-to-k-means parity is not claimed",
        "does not support MWU, bootstrap CI, p-values, FDR-BH, NMI/ARI",
        "does not claim full statistical notebook parity",
        "does not redefine WANIA render `x/y/z`",
        "No inter-component or full heterograph support is claimed",
        (
            "Cross-protein identity, alignment, and comparison support are "
            "not implemented"
        ),
        (
            "API, Docker, database, frontend implementation, and production "
            "workers are not implemented"
        ),
        "Stage 24 has not started",
    ):
        assert phrase in text


def test_stage23b_keeps_science_out_of_required_render_fields() -> None:
    text = doc_text()

    for phrase in (
        "Centrality values do not become required `graph.nodes` fields",
        "community IDs are not required node fields",
        "Raw per-frame rows are not embedded in `graph.nodes` or `graph.edges`",
        "Its rows are not inlined in nodes or edges",
        "does not redefine WANIA render `x/y/z`",
        "The required WANIA fields remain unchanged",
        "Scientific contents are not inlined into the base payload",
        "scientific artifacts are not required for base rendering",
        (
            "changes no artifact reference, demo payload, or Stage 20–22 "
            "artifact/schema behavior"
        ),
    ):
        assert phrase in text


def test_stage23c_defines_optional_non_inline_reference_semantics() -> None:
    text = doc_text()

    for phrase in (
        "Stage 23.C artifact references and demo payload policy",
        "artifact reference != artifact content",
        "WANIA payload artifact reference != MANIA artifact file contents",
        "WANIA base graph render validity != full scientific artifact availability",
        "every MANIA scientific artifact reference inside it is optional",
        "Scientific CSV rows, JSON tables, and other artifact contents",
        "must not be copied into `artifacts`, `graph.nodes`, or `graph.edges`",
        "fixed reference slots are relative path strings or `null`",
        "condition-keyed maps",
        "adds no adapter input, payload key, alias, or runtime mapping",
    ):
        assert phrase in text


def test_stage23c_classifies_condition_and_run_level_references() -> None:
    text = doc_text()

    for artifact in (
        "residue_table_{condition}.csv",
        "protein_contact_edges_undirected_{condition}.csv",
        "contacts_perframe_{condition}.csv",
        "analysis/{condition}/graph.json",
        "analysis/{condition}/centrality_{condition}.csv",
        "analysis/{condition}/communities_{condition}.csv",
        "analysis/{condition}/region_enrichment_{condition}.csv",
        "analysis/{condition}/temporal_rin_{condition}.csv",
        "analysis/{condition}/conformation_pca_{condition}.csv",
        "analysis/{condition}/conformation_labels_{condition}.csv",
        "edge_semantics.json",
        "mania_manifest.json",
        "mania_residue_library.json",
        "analysis/comparison.csv",
        "analysis/stats.csv",
    ):
        assert f"`{artifact}`" in text

    for phrase in (
        "No condition is required to provide every artifact",
        "does not affect base-render validity",
        "run metadata links, not node or edge fields",
        "Stage 23.C adds no runtime mapping for them",
    ):
        assert phrase in text


def test_stage23c_defines_missing_and_capability_behavior() -> None:
    text = doc_text()

    for phrase in (
        "unsupplied fixed slot remains `null`",
        "unsupplied condition-keyed analysis group is omitted",
        "must not invent a path, use a placeholder path",
        "most optional scientific paths are not existence-validated",
        "Missing optional science is not a diagnostics failure",
        "no absolute paths, parent traversal, raw trajectory paths",
        "API endpoint URLs",
        "References point to files; they do not embed file contents",
        "Stage 23.B remains authoritative for capability meaning",
        "does not make centrality values required node fields",
        "does not inline temporal rows",
        "does not claim computed PCA",
        "boolean model still cannot represent `partial` directly",
    ):
        assert phrase in text


def test_stage23c_defines_authoritative_fixture_and_regeneration_policy(
) -> None:
    text = doc_text()

    for phrase in (
        "authoritative required fixture shape is the Stage 17.2 minimal fixture",
        "wania_mvp_minimal_payload_v0_1.json",
        "authoritative rich illustrative sample",
        "wania_graph_payload_frontend_sample_v0_1.json",
        "A generated `wania_graph_payload.json` is an export product",
        "Regenerate a committed fixture only when an explicitly accepted contract",
        "accepted deterministic writer or demo export flow",
        "documentation-only policy change is not a reason to regenerate",
        "synthetic, small, deterministic, and safe for default CI",
        "must not contain real MD output",
        "heavy generated scientific artifacts",
        "inlined CSV rows or scientific tables",
        "Synthetic Stage 20–22 artifact references are deferred",
        "Stage 23.C is policy-only",
        "remain unchanged",
    ):
        assert phrase in text


def test_stage23c_preserves_scientific_runtime_and_later_stage_limits() -> None:
    text = doc_text()

    for phrase in (
        "Computed PCA and PCA coordinates remain unavailable",
        "Conformation labels are fingerprint-based",
        "PCA-based clustering and notebook PCA-to-k-means parity are not claimed",
        "Louvain is not implemented",
        "MWU, bootstrap CI, p-values, and FDR-BH are not implemented",
        "cross-condition statistics remain limited",
        "Non-protein heterograph support remains deferred",
        "API, Docker, database, frontend implementation",
        "No dependency is added",
        "Stage 20, Stage 21, and Stage 22 artifacts",
        "Stage 23.D and Stage 23.E have not started",
        "Stage 24 has not started",
    ):
        assert phrase in text
