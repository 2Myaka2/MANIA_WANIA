"""Strict offline, atomic JSON controls for complete system annotations."""

import json
from dataclasses import dataclass, fields
from pathlib import Path

from mania.biological_annotations import (
    BiologicalAnnotationError,
    CanonicalVariantSiteAnnotation,
    DatasetSystemBiologicalAnnotations,
    GlycosylationSiteAnnotation,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    exact_fields,
    json_array,
    read_strict_json,
    write_atomic_text,
)

BIOLOGICAL_ANNOTATION_SCHEMA_VERSION = (
    "mania.dataset_system_biological_annotations.v0.1"
)
BIOLOGICAL_ANNOTATION_KIND = "mania_dataset_system_biological_annotations"
BIOLOGICAL_ANNOTATION_FILENAME = "biological_annotations.json"


class BiologicalAnnotationReadError(BiologicalAnnotationError):
    """Invalid or unreadable complete annotation JSON."""


@dataclass(frozen=True)
class BiologicalAnnotationValidationReport:
    annotation_path: Path
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def read_dataset_system_biological_annotations(
    path: str | Path,
) -> DatasetSystemBiologicalAnnotations:
    try:
        data = exact_fields(
            read_strict_json(path),
            {
                "schema_version",
                "kind",
                *(item.name for item in fields(DatasetSystemBiologicalAnnotations)),
            },
        )
        if (
            data.pop("schema_version") != BIOLOGICAL_ANNOTATION_SCHEMA_VERSION
            or data.pop("kind") != BIOLOGICAL_ANNOTATION_KIND
        ):
            raise ValueError("Unsupported biological annotation contract")
        for name, model in (
            ("glycosylation_sites", GlycosylationSiteAnnotation),
            ("disulfide_variant_sites", CanonicalVariantSiteAnnotation),
            ("cysteine_variant_sites", CanonicalVariantSiteAnnotation),
        ):
            data[name] = tuple(
                model(**exact_fields(row, {item.name for item in fields(model)}))
                for row in json_array(data[name])
            )
        return DatasetSystemBiologicalAnnotations(**data)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise BiologicalAnnotationReadError(
            "Invalid or unreadable biological annotation metadata."
        ) from None


def write_dataset_system_biological_annotations(
    annotations: DatasetSystemBiologicalAnnotations,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    if type(annotations) is not DatasetSystemBiologicalAnnotations:
        raise BiologicalAnnotationError("annotations must be exact system metadata")
    annotations.__post_init__()
    if type(overwrite) is not bool:
        raise BiologicalAnnotationError("overwrite must be an exact bool")
    if not isinstance(path, (str, Path)) or path == "":
        raise BiologicalAnnotationError("path must be a Path or non-empty string")
    payload = {
        "schema_version": BIOLOGICAL_ANNOTATION_SCHEMA_VERSION,
        "kind": BIOLOGICAL_ANNOTATION_KIND,
        **annotations.to_dict(),
    }
    try:
        return write_atomic_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            Path(path),
            overwrite=overwrite,
        )
    except (TypeError, ValueError, OverflowError):
        return SpecializedArtifactWriteResult(
            Path(path), False, "JSON serialization failed."
        )


def validate_dataset_system_biological_annotations(
    path: str | Path,
) -> BiologicalAnnotationValidationReport:
    target = Path(path)
    try:
        read_dataset_system_biological_annotations(target)
    except BiologicalAnnotationReadError as exc:
        return BiologicalAnnotationValidationReport(target, (str(exc),))
    return BiologicalAnnotationValidationReport(target, ())
