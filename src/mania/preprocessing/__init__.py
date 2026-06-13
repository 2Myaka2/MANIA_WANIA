"""Typed contracts for future MANIA preprocessing inputs."""

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
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingTrajectoryLoadIssue,
)

__all__ = [
    "OptionalScientificDependencyStatus",
    "PreprocessingCheckedPath",
    "PreprocessingConditionLoadResult",
    "PreprocessingConditionResidueNames",
    "PreprocessingConditionRuntime",
    "PreprocessingConditionRuntimeInput",
    "PreprocessingConditionRuntimeMetadata",
    "PreprocessingInputManifest",
    "PreprocessingManifestLoadIssue",
    "PreprocessingManifestLoadResult",
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
    "PreprocessingRuntimeMetadataIssue",
    "PreprocessingTrajectoryLoadIssue",
    "ResolvedResidueLibraryManifestOptions",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "check_preprocessing_reference_package",
    "collect_condition_runtime_metadata",
    "collect_manifest_runtime_metadata",
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
    "validate_residue_library_from_manifest_options",
]
