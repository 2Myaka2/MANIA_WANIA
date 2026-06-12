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

__all__ = [
    "PreprocessingCheckedPath",
    "PreprocessingInputManifest",
    "PreprocessingPathValidationIssue",
    "PreprocessingPathValidationReport",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "load_preprocessing_input_manifest",
    "validate_preprocessing_manifest_paths",
]
