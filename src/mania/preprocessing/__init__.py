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

__all__ = [
    "PreprocessingCheckedPath",
    "PreprocessingInputManifest",
    "PreprocessingPathValidationIssue",
    "PreprocessingPathValidationReport",
    "PreprocessingReferencePackageIssue",
    "PreprocessingReferencePackageReport",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "check_preprocessing_reference_package",
    "load_preprocessing_input_manifest",
    "validate_preprocessing_manifest_paths",
]
