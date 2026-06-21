from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_graph_export_boundary_before_workflow.md"
)


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_graph_export_boundary_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_doc_records_completed_stage_14_slices() -> None:
    text = doc_text()

    for phrase in (
        "Stage 14.1a",
        "Stage 14.1b",
        "Stage 14.1c",
        "Stage 14.1c-fix",
        "Stage 14.1d",
        "Stage 14.1e",
        "Stage 14.1f",
        "Stage 14.2a",
        "Stage 14.2b",
        "Stage 14.3a",
        "Stage 14.3b",
        "Stage 14.4a",
        "Stage 14.4b",
    ):
        assert phrase in text


def test_doc_lists_public_stage_14_api_surface() -> None:
    text = doc_text()

    for api_name in (
        "PreprocessingGraphNodeMappingRecord",
        "PreprocessingGraphEdgeMappingRecord",
        "PreprocessingGraphExportMappingIssue",
        "PreprocessingGraphExportMappingResult",
        "build_preprocessing_graph_export_mapping",
        "PreprocessingGraphNodesCsvWriteIssue",
        "PreprocessingGraphNodesCsvWriteResult",
        "write_preprocessing_graph_nodes_csv",
        "PreprocessingGraphEdgesCsvWriteIssue",
        "PreprocessingGraphEdgesCsvWriteResult",
        "write_preprocessing_graph_edges_csv",
        "PreprocessingGraphCsvValidationIssue",
        "PreprocessingGraphCsvValidationResult",
        "validate_preprocessing_graph_csvs",
        "PreprocessingGraphJsonWriteIssue",
        "PreprocessingGraphJsonWriteResult",
        "write_preprocessing_graph_json",
        "PreprocessingGraphExportBundleArtifact",
        "PreprocessingGraphExportBundleIssue",
        "PreprocessingGraphExportBundleResult",
        "build_preprocessing_graph_export_bundle",
        "PreprocessingGraphDiagnosticsRunIssue",
        "PreprocessingGraphDiagnosticsCheckResult",
        "PreprocessingGraphDiagnosticsRunResult",
        "run_preprocessing_graph_diagnostics",
        "PreprocessingGraphDiagnosticsReportSection",
        "PreprocessingGraphDiagnosticsReport",
        "build_preprocessing_graph_diagnostics_report",
        "PreprocessingGraphReferenceComparisonOptions",
        "PreprocessingGraphReferenceComparisonInput",
        "PreprocessingGraphReferenceComparisonIssue",
        "PreprocessingGraphReferenceComparisonInputValidationResult",
        "validate_preprocessing_graph_reference_comparison_input",
        "PreprocessingGraphReferenceComparisonMismatch",
        "PreprocessingGraphReferenceComparisonTargetResult",
        "PreprocessingGraphReferenceComparisonResult",
        "compare_preprocessing_graph_reference_artifacts",
    ):
        assert api_name in text


def test_doc_records_artifacts_and_schemas() -> None:
    text = doc_text()

    for phrase in (
        "nodes.csv",
        "edges.csv",
        "graph.json",
        "resid,resname,region,condition",
        "resid_i,resid_j,edge_type,all_edge_types,n_edge_types,condition",
        "schema_version",
        "CSV-derived node and edge row values are preserved as strings",
        "graph export bundle consumes existing graph artifacts",
    ):
        assert phrase in text


def test_doc_records_corrected_edge_schema_and_priority() -> None:
    text = doc_text()

    for phrase in (
        "EDGE_TYPE_PRIORITY",
        "hbond",
        "disulfide",
        "salt_bridge",
        "ionic",
        "cation_pi",
        "aromatic_pi",
        "hydrophobic",
        "vdw",
        "edge_type",
        "all_edge_types",
        "n_edge_types",
        "pipe-separated",
        "residue_contact",
        "valid for MVP generated graph edges",
    ):
        assert phrase in text


def test_doc_records_programmatic_sequence_before_workflow() -> None:
    text = doc_text()

    for phrase in (
        "Stage 13 contacts result / aggregate contacts",
        "build_preprocessing_graph_export_mapping",
        "write_preprocessing_graph_nodes_csv",
        "write_preprocessing_graph_edges_csv",
        "validate_preprocessing_graph_csvs",
        "write_preprocessing_graph_json",
        "build_preprocessing_graph_export_bundle",
        "run_preprocessing_graph_diagnostics",
        "build_preprocessing_graph_diagnostics_report",
        "validate_preprocessing_graph_reference_comparison_input",
        "compare_preprocessing_graph_reference_artifacts",
        "docs/preprocessing_graph_reference_mismatches.md",
        "No workflow or CLI orchestration exists yet",
    ):
        assert phrase in text


def test_doc_records_validation_diagnostics_and_comparison_boundaries() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "validates `nodes.csv` plus corrected backend graph `edges.csv`",
        "validates generated/reference readiness only",
        "do not perform biological interpretation",
        "does not run diagnostics, read files, write files",
        "CSV comparison is exact row-preserving string comparison",
        "graph.json comparison is structural, not byte-level",
        "Comparison reports mismatches",
        "does not classify whether a mismatch is expected",
    ):
        assert phrase in compact


def test_doc_records_reference_semantics_and_contact_boundary() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "MANIA_analysis_v1_2",
        "v1.1 reference artifacts remain historical",
        "v1.2 Cell 5 adds interaction priority",
        "v1.2 Cell 12 fixes temporal RIN export handling",
        "Temporal RIN export and temporal RIN comparison remain future scope",
        "Stage 13 `contact_edges.csv` is an aggregate contacts table",
        "It is not backend graph `edges.csv`",
        "Stage 14 backend graph `edges.csv` is a separate graph artifact",
    ):
        assert phrase in compact


def test_doc_records_future_boundaries_and_guardrails() -> None:
    compact = normalized(doc_text())

    for phrase in (
        "does not add source behavior",
        "new public APIs",
        "workflow/CLI integration",
        "automatic end-to-end graph export command",
        "real-data CI",
        "notebook cell-level comparison",
        "biochemical interaction classification beyond generic MVP contact semantics",
        "reuse accepted Stage 14 public APIs rather than duplicating logic",
        "preserve `MANIA_analysis_v1_2` as default graph reference semantics",
        "do not require MDAnalysis in default graph export docs or default tests",
        "do not modify `data/reference/**`",
        "Stage 15 - Workflow/CLI integration for preprocessing graph export",
    ):
        assert phrase in compact
