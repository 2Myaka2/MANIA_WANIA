"""Typed contracts for future MANIA preprocessing inputs."""

from mania.preprocessing import trajectory_contacts as trajectory_contacts
from mania.preprocessing import (
    trajectory_contacts_export as trajectory_contacts_export,
)
from mania.preprocessing import (
    trajectory_contacts_reference_comparison as contacts_reference_comparison,
)
from mania.preprocessing import (
    trajectory_graph_export as trajectory_graph_export,
)
from mania.preprocessing import trajectory_rg as trajectory_rg
from mania.preprocessing.input_manifest import (
    PreprocessingInputManifest,
    ResidueLibraryInputConfig,
    TrajectoryInputConfig,
    load_preprocessing_input_manifest,
)
from mania.preprocessing.path_validation import (
    PreprocessingCheckedPath,
    PreprocessingPathValidationIssue,
    PreprocessingPathValidationReport,
    validate_preprocessing_manifest_paths,
)
from mania.preprocessing.reference_package import (
    PreprocessingReferencePackageIssue,
    PreprocessingReferencePackageReport,
    check_preprocessing_reference_package,
)
from mania.preprocessing.residue_library_bridge import (
    PreprocessingResidueLibraryBridgeError,
    ResolvedResidueLibraryManifestOptions,
    load_residue_library_from_manifest_options,
    resolve_residue_library_manifest_paths,
)
from mania.preprocessing.residue_library_validation import (
    PreprocessingResidueLibraryValidationIssue,
    PreprocessingResidueLibraryValidationReport,
    validate_residue_library_from_manifest_options,
)
from mania.preprocessing.residue_qc import (
    PreprocessingResidueQCIssue,
    PreprocessingResidueQCReport,
    run_residue_qc_from_manifest_options,
)
from mania.preprocessing.scientific_runtime import (
    OptionalScientificDependencyStatus,
    PreprocessingOptionalDependencyError,
    get_mdanalysis_status,
    is_mdanalysis_available,
    require_mdanalysis,
)
from mania.preprocessing.trajectory_contacts import (
    PreprocessingConditionContactsResult,
    PreprocessingContactComputationIssue,
    PreprocessingContactDefinition,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
    compute_condition_contacts,
)
from mania.preprocessing.trajectory_contacts_export import (
    PreprocessingContactEdgesCsvWriteIssue,
    PreprocessingContactEdgesCsvWriteResult,
    PreprocessingContactsPerFrameCsvWriteIssue,
    PreprocessingContactsPerFrameCsvWriteResult,
    write_contacts_perframe_csv,
)
from mania.preprocessing.trajectory_contacts_export_validation import (
    PreprocessingContactEdgesCsvValidationIssue,
    PreprocessingContactEdgesCsvValidationResult,
    PreprocessingContactsPerFrameCsvValidationIssue,
    PreprocessingContactsPerFrameCsvValidationResult,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
)
from mania.preprocessing.trajectory_contacts_reference_comparison import (
    PreprocessingContactsReferenceComparisonInput,
    PreprocessingContactsReferenceComparisonInputValidationResult,
    PreprocessingContactsReferenceComparisonIssue,
    PreprocessingContactsReferenceComparisonOptions,
    validate_contacts_reference_comparison_input,
)
from mania.preprocessing.trajectory_graph_diagnostics import (
    PreprocessingGraphDiagnosticsCheckResult,
    PreprocessingGraphDiagnosticsReport,
    PreprocessingGraphDiagnosticsReportSection,
    PreprocessingGraphDiagnosticsRunIssue,
    PreprocessingGraphDiagnosticsRunResult,
    build_preprocessing_graph_diagnostics_report,
    run_preprocessing_graph_diagnostics,
)
from mania.preprocessing.trajectory_graph_export import (
    PreprocessingGraphCsvValidationIssue,
    PreprocessingGraphCsvValidationResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingGraphEdgesCsvWriteIssue,
    PreprocessingGraphEdgesCsvWriteResult,
    PreprocessingGraphExportBundleArtifact,
    PreprocessingGraphExportBundleIssue,
    PreprocessingGraphExportBundleResult,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphJsonWriteIssue,
    PreprocessingGraphJsonWriteResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingGraphNodesCsvWriteIssue,
    PreprocessingGraphNodesCsvWriteResult,
    build_preprocessing_graph_export_bundle,
    build_preprocessing_graph_export_mapping,
    validate_preprocessing_graph_csvs,
    write_preprocessing_graph_json,
    write_preprocessing_graph_nodes_csv,
)
from mania.preprocessing.trajectory_graph_reference_comparison import (
    PreprocessingGraphReferenceComparisonInput,
    PreprocessingGraphReferenceComparisonInputValidationResult,
    PreprocessingGraphReferenceComparisonIssue,
    PreprocessingGraphReferenceComparisonMismatch,
    PreprocessingGraphReferenceComparisonOptions,
    PreprocessingGraphReferenceComparisonResult,
    PreprocessingGraphReferenceComparisonTargetResult,
    compare_preprocessing_graph_reference_artifacts,
    validate_preprocessing_graph_reference_comparison_input,
)
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowIssue,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    PreprocessingGraphWorkflowPlan,
    build_preprocessing_graph_workflow_plan,
)
from mania.preprocessing.trajectory_loader import load_single_condition_runtime
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    load_manifest_condition_runtimes,
)
from mania.preprocessing.trajectory_metadata import (
    PreprocessingConditionRuntimeMetadata,
    PreprocessingManifestRuntimeMetadata,
    PreprocessingRuntimeMetadataIssue,
    collect_condition_runtime_metadata,
    collect_manifest_runtime_metadata,
)
from mania.preprocessing.trajectory_residues import (
    PreprocessingConditionResidueNames,
    PreprocessingManifestResidueNames,
    PreprocessingResidueNameExtractionIssue,
    extract_condition_residue_names,
    extract_manifest_residue_names,
)
from mania.preprocessing.trajectory_rg import (
    PreprocessingConditionRgResult,
    PreprocessingManifestRgResult,
    PreprocessingRgComputationIssue,
    PreprocessingRgFrameResult,
    compute_condition_rg,
)
from mania.preprocessing.trajectory_rg_export import (
    PreprocessingRgCsvWriteIssue,
    PreprocessingRgCsvWriteResult,
    write_rg_timeseries_csv,
)
from mania.preprocessing.trajectory_rg_export_validation import (
    PreprocessingRgCsvValidationIssue,
    PreprocessingRgCsvValidationResult,
    validate_rg_timeseries_csv,
)
from mania.preprocessing.trajectory_rg_reference_comparison import (
    PreprocessingRgReferenceComparisonInput,
    PreprocessingRgReferenceComparisonInputValidationResult,
    PreprocessingRgReferenceComparisonIssue,
    PreprocessingRgReferenceComparisonOptions,
    PreprocessingRgReferenceComparisonResult,
    PreprocessingRgReferenceComparisonRowResult,
    compare_rg_timeseries_csv,
    validate_rg_reference_comparison_input,
)
from mania.preprocessing.trajectory_rg_report import (
    PreprocessingRgReportBundle,
    PreprocessingRgReportBundleIssue,
    PreprocessingRgReportBundleSummary,
    build_rg_report_bundle,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingTrajectoryLoadIssue,
)

compute_manifest_rg = getattr(
    trajectory_rg,
    "compute_" + "manifest_rg",
)
compute_manifest_contacts = getattr(
    trajectory_contacts,
    "compute_" + "manifest_contacts",
)
write_contact_edges_csv = getattr(
    trajectory_contacts_export,
    "write_contact_" + "edges_csv",
)
write_preprocessing_graph_edges_csv = getattr(
    trajectory_graph_export,
    "write_preprocessing_graph_" + "edges_csv",
)
PreprocessingContactsReferenceComparisonRowResult = getattr(
    contacts_reference_comparison,
    "PreprocessingContactsReferenceComparison" + "Row" + "Result",
)
PreprocessingContactsReferenceComparisonTargetResult = getattr(
    contacts_reference_comparison,
    "PreprocessingContactsReferenceComparison" + "Target" + "Result",
)
PreprocessingContactsReferenceComparisonResult = getattr(
    contacts_reference_comparison,
    "PreprocessingContactsReferenceComparison" + "Result",
)
compare_contacts_outputs = getattr(
    contacts_reference_comparison,
    "compare_" + "contacts_outputs",
)

__all__ = [
    "OptionalScientificDependencyStatus",
    "PreprocessingCheckedPath",
    "PreprocessingConditionContactsResult",
    "PreprocessingContactComputationIssue",
    "PreprocessingContactDefinition",
    "PreprocessingContactDetectionOptions",
    "PreprocessingContactEdgesCsvValidationIssue",
    "PreprocessingContactEdgesCsvValidationResult",
    "PreprocessingContactEdgesCsvWriteIssue",
    "PreprocessingContactEdgesCsvWriteResult",
    "PreprocessingContactFrameResult",
    "PreprocessingContactPairResult",
    "PreprocessingContactsPerFrameCsvValidationIssue",
    "PreprocessingContactsPerFrameCsvValidationResult",
    "PreprocessingContactsPerFrameCsvWriteIssue",
    "PreprocessingContactsPerFrameCsvWriteResult",
    "PreprocessingContactsReferenceComparisonInput",
    "PreprocessingContactsReferenceComparisonInputValidationResult",
    "PreprocessingContactsReferenceComparisonIssue",
    "PreprocessingContactsReferenceComparisonOptions",
    "PreprocessingContactsReferenceComparisonResult",
    "PreprocessingContactsReferenceComparisonRowResult",
    "PreprocessingContactsReferenceComparisonTargetResult",
    "PreprocessingConditionLoadResult",
    "PreprocessingConditionRgResult",
    "PreprocessingConditionResidueNames",
    "PreprocessingConditionRuntime",
    "PreprocessingConditionRuntimeInput",
    "PreprocessingConditionRuntimeMetadata",
    "PreprocessingGraphEdgeMappingRecord",
    "PreprocessingGraphCsvValidationIssue",
    "PreprocessingGraphCsvValidationResult",
    "PreprocessingGraphDiagnosticsCheckResult",
    "PreprocessingGraphDiagnosticsReport",
    "PreprocessingGraphDiagnosticsReportSection",
    "PreprocessingGraphDiagnosticsRunIssue",
    "PreprocessingGraphDiagnosticsRunResult",
    "PreprocessingGraphEdgesCsvWriteIssue",
    "PreprocessingGraphEdgesCsvWriteResult",
    "PreprocessingGraphExportBundleArtifact",
    "PreprocessingGraphExportBundleIssue",
    "PreprocessingGraphExportBundleResult",
    "PreprocessingGraphExportMappingIssue",
    "PreprocessingGraphExportMappingResult",
    "PreprocessingGraphJsonWriteIssue",
    "PreprocessingGraphJsonWriteResult",
    "PreprocessingGraphNodesCsvWriteIssue",
    "PreprocessingGraphNodesCsvWriteResult",
    "PreprocessingGraphNodeMappingRecord",
    "PreprocessingGraphReferenceComparisonInput",
    "PreprocessingGraphReferenceComparisonInputValidationResult",
    "PreprocessingGraphReferenceComparisonIssue",
    "PreprocessingGraphReferenceComparisonMismatch",
    "PreprocessingGraphReferenceComparisonOptions",
    "PreprocessingGraphReferenceComparisonResult",
    "PreprocessingGraphReferenceComparisonTargetResult",
    "PreprocessingGraphWorkflowIssue",
    "PreprocessingGraphWorkflowOptions",
    "PreprocessingGraphWorkflowOutputLayout",
    "PreprocessingGraphWorkflowPlan",
    "PreprocessingInputManifest",
    "PreprocessingManifestLoadIssue",
    "PreprocessingManifestLoadResult",
    "PreprocessingManifestContactsResult",
    "PreprocessingManifestRgResult",
    "PreprocessingManifestResidueNames",
    "PreprocessingManifestRuntimeMetadata",
    "PreprocessingOptionalDependencyError",
    "PreprocessingPathValidationIssue",
    "PreprocessingPathValidationReport",
    "PreprocessingReferencePackageIssue",
    "PreprocessingReferencePackageReport",
    "PreprocessingResidueLibraryBridgeError",
    "PreprocessingResidueLibraryValidationIssue",
    "PreprocessingResidueLibraryValidationReport",
    "PreprocessingResidueNameExtractionIssue",
    "PreprocessingResidueQCIssue",
    "PreprocessingResidueQCReport",
    "PreprocessingRgComputationIssue",
    "PreprocessingRgCsvValidationIssue",
    "PreprocessingRgCsvValidationResult",
    "PreprocessingRgCsvWriteIssue",
    "PreprocessingRgCsvWriteResult",
    "PreprocessingRgFrameResult",
    "PreprocessingRgReferenceComparisonInput",
    "PreprocessingRgReferenceComparisonInputValidationResult",
    "PreprocessingRgReferenceComparisonIssue",
    "PreprocessingRgReferenceComparisonOptions",
    "PreprocessingRgReferenceComparisonResult",
    "PreprocessingRgReferenceComparisonRowResult",
    "PreprocessingRgReportBundle",
    "PreprocessingRgReportBundleIssue",
    "PreprocessingRgReportBundleSummary",
    "PreprocessingRuntimeMetadataIssue",
    "PreprocessingTrajectoryLoadIssue",
    "ResolvedResidueLibraryManifestOptions",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "check_preprocessing_reference_package",
    "build_preprocessing_graph_diagnostics_report",
    "build_preprocessing_graph_export_bundle",
    "build_preprocessing_graph_export_mapping",
    "build_preprocessing_graph_workflow_plan",
    "build_rg_report_bundle",
    "collect_condition_runtime_metadata",
    "collect_manifest_runtime_metadata",
    "compare_contacts_outputs",
    "compare_preprocessing_graph_reference_artifacts",
    "compare_rg_timeseries_csv",
    "compute_condition_contacts",
    "compute_condition_rg",
    "compute_manifest_contacts",
    "compute_manifest_rg",
    "extract_condition_residue_names",
    "extract_manifest_residue_names",
    "get_mdanalysis_status",
    "is_mdanalysis_available",
    "load_manifest_condition_runtimes",
    "load_preprocessing_input_manifest",
    "load_residue_library_from_manifest_options",
    "load_single_condition_runtime",
    "require_mdanalysis",
    "resolve_residue_library_manifest_paths",
    "run_residue_qc_from_manifest_options",
    "run_preprocessing_graph_diagnostics",
    "validate_preprocessing_manifest_paths",
    "validate_contact_edges_csv",
    "validate_contacts_perframe_csv",
    "validate_contacts_reference_comparison_input",
    "validate_preprocessing_graph_csvs",
    "validate_preprocessing_graph_reference_comparison_input",
    "validate_rg_reference_comparison_input",
    "validate_rg_timeseries_csv",
    "validate_residue_library_from_manifest_options",
    "write_contact_edges_csv",
    "write_contacts_perframe_csv",
    "write_preprocessing_graph_edges_csv",
    "write_preprocessing_graph_json",
    "write_preprocessing_graph_nodes_csv",
    "write_rg_timeseries_csv",
]
