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

__all__ = [
    "PreprocessingCheckedPath",
    "PreprocessingInputManifest",
    "PreprocessingPathValidationIssue",
    "PreprocessingPathValidationReport",
    "PreprocessingReferencePackageIssue",
    "PreprocessingReferencePackageReport",
    "PreprocessingResidueLibraryBridgeError",
    "PreprocessingResidueLibraryValidationIssue",
    "PreprocessingResidueLibraryValidationReport",
    "PreprocessingResidueQCIssue",
    "PreprocessingResidueQCReport",
    "ResolvedResidueLibraryManifestOptions",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "check_preprocessing_reference_package",
    "load_preprocessing_input_manifest",
    "load_residue_library_from_manifest_options",
    "resolve_residue_library_manifest_paths",
    "run_residue_qc_from_manifest_options",
    "validate_preprocessing_manifest_paths",
    "validate_residue_library_from_manifest_options",
]
