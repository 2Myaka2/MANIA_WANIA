"""Stage 33.D source checks shared by assembly and offline reconstruction."""

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from mania.dataset_release_contract import REPLICA_KEY, WINDOW_KEY
from mania.dataset_release_csv import publication_number
from mania.dataset_release_inputs_io import DatasetReleasePublicationInputs
from mania.dataset_release_manifest import DatasetReleaseExportManifest, require_path
from mania.dataset_release_metadata import DatasetReleaseMetadataTables
from mania.dataset_release_science import publication_metadata_index
from mania.preprocessing.protein_edge_window_table import _effective_ns
from mania.replica_aggregation_manifest import ReplicaAggregationManifest
from mania.replica_aggregation_workflow import FAMILIES, load_replica_aggregation_inputs


def validate_release_canonical_source_authority(
    control: DatasetReleaseExportManifest,
    used: ReplicaAggregationManifest,
    canonical: Mapping[str, Any],
) -> None:
    """Compare complete strict input models before 33.C population filtering.

    The caller first verifies the Stage 31 inventory/provenance, exact manifest
    and every input binding. Its resolved manifest paths are then authoritative.
    No aggregate calculation is performed by the accepted input-only loader.
    """
    authoritative = load_replica_aggregation_inputs(used)
    for family in FAMILIES:
        if family.name not in authoritative:
            continue
        coverage = {
            key
            for binding in control.canonical_bindings
            if binding.family == family.name
            for key in binding.replica_keys
        }
        expected = family.canonical_table(
            tuple(
                row
                for row in authoritative[family.name].rows
                if row.replica_key in coverage
            )
        )
        if canonical[family.name] != expected:
            raise ValueError(
                f"Publication {family.name} canonical input differs from Stage 31"
            )


# Closed source-field contract. Counts and fractions are unitless (JSON null).
_COMMON_FIELDS: dict[str, str | None] = {
    "occupancy": None,
    "n_contact_frames": None,
    "n_contact_episodes": None,
    "mean_episode_length_ns": "ns",
    "max_episode_length_ns": "ns",
}
_FAMILY_FIELDS = {
    "protein": {**_COMMON_FIELDS, "edge_weight": None},
    "lipid": {
        **_COMMON_FIELDS,
        "distance_mean_A": "angstrom",
        "distance_min_A": "angstrom",
    },
    "glycan": {
        **_COMMON_FIELDS,
        "distance_mean_A": "angstrom",
        "distance_min_A": "angstrom",
    },
}


def validate_publication_metric_sources(
    inputs: DatasetReleasePublicationInputs,
    control: DatasetReleaseExportManifest,
    base: Path,
    metadata: DatasetReleaseMetadataTables,
) -> None:
    """Resolve selected metrics only through explicitly bound canonical CSVs.

    Record keys are compact UTF-8 JSON arrays of the accepted row_identity.
    These source types are window-scoped; no replica-global adapter is claimed.
    """
    families = {family.input_role: family for family in FAMILIES}
    windows = publication_metadata_index(metadata, "time_windows")
    sources: dict[tuple[str, str], Any] = {}
    for metric, field in zip(
        inputs.metrics, inputs.metric_source_value_fields, strict=True
    ):
        require_path(metric.source_artifact_path)
        family = families.get(metric.source_artifact_role)
        if family is None:
            raise ValueError("Unsupported publication metric source role")
        bindings = [
            binding
            for binding in control.canonical_bindings
            if binding.family == family.name
            and binding.path == metric.source_artifact_path
        ]
        if len(bindings) != 1:
            raise ValueError("Metric source must match exactly one canonical binding")
        if metric.window_id is None or metric.window_index is None:
            raise ValueError("Canonical metric sources require a physical window")
        units = _FAMILY_FIELDS[family.name]
        if field not in units or metric.unit != units[field]:
            raise ValueError("Unsupported metric numeric field or mismatching unit")
        source_key = (family.name, metric.source_artifact_path)
        if source_key not in sources:
            sources[source_key] = family.canonical_reader(
                base / metric.source_artifact_path
            )
        records = [
            row
            for row in sources[source_key].rows
            if json.dumps(row.row_identity, ensure_ascii=False, separators=(",", ":"))
            == metric.source_record_key
        ]
        if len(records) != 1:
            raise ValueError("Metric source key must resolve to exactly one record")
        row = records[0]
        if row.boundary_profile != metadata.boundary_profile:
            raise ValueError("Metric source temporal boundary profile differs")
        replica_key = tuple(getattr(metric, name) for name in REPLICA_KEY)
        if (
            row.replica_key != replica_key
            or replica_key not in bindings[0].replica_keys
        ):
            raise ValueError("Metric source replica identity differs")
        if (row.window_id, row.window_index) != (metric.window_id, metric.window_index):
            raise ValueError("Metric source window identity differs")
        window = windows[tuple(getattr(metric, name) for name in WINDOW_KEY)]
        for source_name, window_name in (
            ("requested_window_start_ns", "requested_window_start_ns"),
            ("requested_window_end_ns", "requested_window_end_ns"),
            ("right_endpoint_inclusive", "right_endpoint_inclusive"),
            ("requested_sample_count", "expected_sample_count"),
            ("resolved_frame_count", "resolved_sample_count"),
            ("missing_sample_count", "missing_sample_count"),
            ("coverage_fraction", "coverage_fraction"),
        ):
            value = getattr(row, source_name)
            expected = window[window_name]
            if (
                value if type(value) is bool else publication_number(value)
            ) != expected:
                raise ValueError("Metric source physical window evidence differs")
        for source_name, window_name in (
            ("effective_window_start_ns", "effective_start_ns"),
            ("effective_window_end_ns", "effective_end_ns"),
        ):
            # 33.B stores the exact ps float scaled to Decimal ns. Recover that
            # ps value by exponent shift and reuse Stage 28's accepted source
            # representation; direct float(ns) can differ at noisy boundaries.
            expected = window[window_name]
            if not isinstance(expected, Decimal):
                raise ValueError("Metric source effective window evidence differs")
            sign, digits, exponent = expected.as_tuple()
            assert isinstance(exponent, int)
            source_ps = float(Decimal((sign, digits, exponent + 3)))
            if getattr(row, source_name) != _effective_ns(source_ps):
                raise ValueError("Metric source effective window evidence differs")
        if publication_number(metric.metric_value) != publication_number(
            getattr(row, field)
        ):
            raise ValueError(
                "Metric value differs from the authoritative numeric field"
            )
