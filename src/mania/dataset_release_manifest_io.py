"""Strict deterministic release JSON, using accepted atomic UTF-8 persistence."""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from mania.dataset_release_manifest import (
    DatasetReleaseExportManifest,
    DatasetReleaseManifest,
    ReleaseAnnotationBinding,
    ReleaseCanonicalBinding,
    ReleaseInputBinding,
    ReleaseUpstreamRun,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    exact_fields,
    json_array,
    read_strict_json,
    write_atomic_text,
)

_Model = TypeVar("_Model", DatasetReleaseExportManifest, DatasetReleaseManifest)


def release_json_text(payload: object) -> str:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def model_fields(data: Any, model: type) -> dict[str, Any]:
    values = exact_fields(data, {f.name for f in fields(model)})
    for item in fields(model):
        if not item.init:
            expected = json.loads(release_json_text(item.default))
            value = values.pop(item.name)
            if type(value) is not type(expected) or value != expected:
                raise ValueError("Incorrect fixed release contract field")
    return values


def _keys(value: Any) -> tuple[tuple[Any, ...], ...]:
    return tuple(tuple(json_array(key)) for key in json_array(value))


def _run(data: Any) -> ReleaseUpstreamRun:
    values = model_fields(data, ReleaseUpstreamRun)
    values["input_bindings"] = tuple(
        ReleaseInputBinding(**model_fields(v, ReleaseInputBinding))
        for v in json_array(values["input_bindings"])
    )
    return ReleaseUpstreamRun(**values)


def read_dataset_release_export_manifest(
    path: str | Path,
) -> DatasetReleaseExportManifest:
    try:
        values = model_fields(read_strict_json(path), DatasetReleaseExportManifest)
        for name in ("stage32_run", "stage31_run"):
            values[name] = _run(values[name])
        canonical = []
        for value in json_array(values["canonical_bindings"]):
            binding = model_fields(value, ReleaseCanonicalBinding)
            binding["replica_keys"] = _keys(binding["replica_keys"])
            canonical.append(ReleaseCanonicalBinding(**binding))
        values["canonical_bindings"] = tuple(canonical)
        values["annotation_bindings"] = tuple(
            ReleaseAnnotationBinding(**model_fields(v, ReleaseAnnotationBinding))
            for v in json_array(values["annotation_bindings"])
        )
        values["temporal_evidence_paths"] = tuple(
            json_array(values["temporal_evidence_paths"])
        )
        for name in (
            "scientific_release_replica_keys",
            "annotation_publication_system_keys",
        ):
            values[name] = _keys(values[name])
        return DatasetReleaseExportManifest(**values)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError(
            "Invalid or unreadable release export control manifest"
        ) from None


def read_dataset_release_manifest(path: str | Path) -> DatasetReleaseManifest:
    try:
        data = read_strict_json(path)
        data = exact_fields(
            data,
            {
                *(f.name for f in fields(DatasetReleaseManifest)),
                "publication_artifacts",
            },
        )
        registry = data.pop("publication_artifacts")
        model = DatasetReleaseManifest(**model_fields(data, DatasetReleaseManifest))
        # JSON representations also distinguish true/1 and exact nested field sets.
        if release_json_text(registry) != release_json_text(
            model.to_dict()["publication_artifacts"]
        ):
            raise ValueError("Incorrect frozen publication artifact registry")
        return model
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("Invalid or unreadable publication dataset manifest") from None


def _write(
    model: _Model, path: str | Path, overwrite: bool
) -> SpecializedArtifactWriteResult:
    model.__post_init__()
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be boolean")
    return write_atomic_text(
        release_json_text(model.to_dict()),
        Path(path),
        overwrite=overwrite,
    )


def write_dataset_release_export_manifest(
    model: DatasetReleaseExportManifest,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    if type(model) is not DatasetReleaseExportManifest:
        raise ValueError("Expected exact release export control manifest")
    return _write(model, path, overwrite)


def write_dataset_release_manifest(
    model: DatasetReleaseManifest,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    if type(model) is not DatasetReleaseManifest:
        raise ValueError("Expected exact publication dataset manifest")
    return _write(model, path, overwrite)
