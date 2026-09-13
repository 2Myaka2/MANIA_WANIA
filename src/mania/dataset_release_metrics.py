"""Explicit authoritative long-form publication metrics; no metric computation."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Decimal

from mania.dataset_release_csv import (
    DatasetReleaseTable,
    build_publication_table,
    publication_number,
)
from mania.dataset_release_metadata import DatasetReleaseMetadataTables
from mania.dataset_release_science import (
    DatasetReleaseScienceError,
    validate_dataset_release_scientific_relationships,
)


@dataclass(frozen=True)
class AuthoritativePublicationMetric:
    """One supplied source record, with the exact frozen Stage 33.A fields.

    metric_id and source_record_key are explicit, deterministic source identities.
    This primary-science API requires a finite value even though the low-level
    frozen schema permits an upstream-authorized null. No QC evidence is promoted.
    """

    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    metric_id: str
    window_id: str | None
    window_index: int | None
    metric_name: str
    metric_value: float | int | Decimal
    unit: str | None
    source_artifact_role: str
    source_artifact_path: str
    source_record_key: str

    def __post_init__(self) -> None:
        if (self.window_id is None) != (self.window_index is None):
            raise DatasetReleaseScienceError("Metric window fields must pair")
        publication_number(self.metric_value)
        build_publication_table("metrics", (asdict(self),))


def build_dataset_release_metrics(
    metrics: Iterable[AuthoritativePublicationMetric],
    *,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    """Publish explicit selections; unknown or unincluded replicas are errors."""
    rows = []
    for metric in metrics:
        if type(metric) is not AuthoritativePublicationMetric:
            raise DatasetReleaseScienceError("Expected explicit publication metric")
        metric.__post_init__()
        rows.append(asdict(metric))
    table = build_publication_table("metrics", rows)
    validate_dataset_release_scientific_relationships((table,), metadata_tables)
    return table
