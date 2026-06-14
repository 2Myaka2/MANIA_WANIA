"""Typed contracts for future MANIA preprocessing inputs."""

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

__all__ = [
    "OptionalScientificDependencyStatus",
    "PreprocessingCheckedPath",
    "PreprocessingConditionContactsResult",
    "PreprocessingContactComputationIssue",
    "PreprocessingContactDefinition",
    "PreprocessingContactDetectionOptions",
    "PreprocessingContactFrameResult",
    "PreprocessingContactPairResult",
    "PreprocessingConditionLoadResult",
    "PreprocessingConditionRgResult",
    "PreprocessingConditionResidueNames",
    "PreprocessingConditionRuntime",
    "PreprocessingConditionRuntimeInput",
    "PreprocessingConditionRuntimeMetadata",
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
    "build_rg_report_bundle",
    "collect_condition_runtime_metadata",
    "collect_manifest_runtime_metadata",
    "compare_rg_timeseries_csv",
    "compute_condition_contacts",
    "compute_condition_rg",
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
    "validate_preprocessing_manifest_paths",
    "validate_rg_reference_comparison_input",
    "validate_rg_timeseries_csv",
    "validate_residue_library_from_manifest_options",
    "write_rg_timeseries_csv",
]
