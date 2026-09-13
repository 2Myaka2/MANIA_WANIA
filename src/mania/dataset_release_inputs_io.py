"""One narrow control for supplied contact, software and metric publication data."""

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from mania.dataset_release_csv import DatasetReleaseTable
from mania.dataset_release_manifest import require_text
from mania.dataset_release_manifest_io import release_json_text
from mania.dataset_release_metadata import (
    build_dataset_release_contact_definition,
    build_dataset_release_software_versions,
)
from mania.dataset_release_metrics import AuthoritativePublicationMetric
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    exact_fields,
    json_array,
    read_strict_json,
    write_atomic_text,
)

PUBLICATION_INPUT_SCHEMA_VERSION = "mania.dataset_release_publication_input.v0.1"
PUBLICATION_INPUT_KIND = "mania_dataset_release_publication_input"


@dataclass(frozen=True)
class DatasetReleasePublicationInputs:
    contact_definitions: tuple[DatasetReleaseTable, ...]
    software_versions: DatasetReleaseTable
    metrics: tuple[AuthoritativePublicationMetric, ...]
    metric_source_value_fields: tuple[str, ...]


def publication_inputs_from_payload(data: Any) -> DatasetReleasePublicationInputs:
    data = exact_fields(
        data,
        {
            "schema_version",
            "kind",
            "contact_definitions",
            "software_versions",
            "metrics",
        },
    )
    if data["schema_version"] != PUBLICATION_INPUT_SCHEMA_VERSION or (
        data["kind"] != PUBLICATION_INPUT_KIND
    ):
        raise ValueError("Incorrect publication input contract")
    contacts = []
    for definition in json_array(data["contact_definitions"]):
        values = exact_fields(
            definition,
            {
                "replica_key",
                "contact_definition_id",
                "contact_layer",
                "interaction_type",
                "parameters",
                "source_artifact_role",
                "source_artifact_path",
                "units",
            },
        )
        values["replica_key"] = tuple(json_array(values["replica_key"]))
        if type(values["units"]) is not dict or any(
            type(k) is not str or type(v) is not str or not v
            for k, v in values["units"].items()
        ):
            raise ValueError("Explicit contact units must be a text mapping")
        contacts.append(build_dataset_release_contact_definition(**values))
    software = build_dataset_release_software_versions(
        json_array(data["software_versions"])
    )
    metrics = []
    source_fields = []
    for row in json_array(data["metrics"]):
        values = exact_fields(
            row,
            {f.name for f in fields(AuthoritativePublicationMetric)}
            | {"source_value_field"},
        )
        source_field = values.pop("source_value_field")
        require_text(source_field)
        source_fields.append(source_field)
        metrics.append(AuthoritativePublicationMetric(**values))
    return DatasetReleasePublicationInputs(
        tuple(contacts), software, tuple(metrics), tuple(source_fields)
    )


def read_dataset_release_publication_inputs(
    path: str | Path,
) -> DatasetReleasePublicationInputs:
    try:
        return publication_inputs_from_payload(read_strict_json(path))
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("Invalid or unreadable explicit publication inputs") from None


def write_dataset_release_publication_inputs(
    payload: dict[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    publication_inputs_from_payload(payload)
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be boolean")
    return write_atomic_text(
        release_json_text(payload), Path(path), overwrite=overwrite
    )
