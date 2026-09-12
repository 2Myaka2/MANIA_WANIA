"""Strict deterministic manifest I/O with manifest-relative control paths."""

from dataclasses import dataclass
from pathlib import Path

from mania._dataset_qc_json import read_model, write_model
from mania.dataset_qc_manifest import DatasetQCManifest
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
)


def read_dataset_qc_manifest(path: str | Path) -> DatasetQCManifest:
    return read_model(path, DatasetQCManifest)


def write_dataset_qc_manifest(
    manifest: DatasetQCManifest,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_model(manifest, DatasetQCManifest, path, overwrite=overwrite)


@dataclass(frozen=True)
class DatasetQCManifestValidationReport:
    manifest_path: Path
    replica_count: int | None
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_dataset_qc_manifest(path: str | Path) -> DatasetQCManifestValidationReport:
    try:
        model = read_dataset_qc_manifest(path)
    except ValueError as exc:
        return DatasetQCManifestValidationReport(Path(path), None, (str(exc),))
    return DatasetQCManifestValidationReport(Path(path), len(model.replicas), ())
