"""Canonical-only Stage 31 execution: read all, aggregate all, then export."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mania import canonical_window_tables as canonical
from mania import canonical_window_tables_io as canonical_io
from mania import replica_aggregation_tables as tables
from mania import replica_aggregation_tables_io as table_io
from mania.replica_aggregation_contract import (
    build_compatible_replica_aggregation_group,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    require_fixed_metadata,
)
from mania.replica_protein_edge_aggregation import (
    aggregate_canonical_protein_edges_across_replicas,
)
from mania.replica_specialized_aggregation import (
    aggregate_canonical_protein_glycan_across_replicas,
    aggregate_canonical_protein_lipid_across_replicas,
)


@dataclass(frozen=True)
class ReplicaAggregationFamily:
    name: str
    input_role: str
    output_role: str
    filename: str
    canonical_reader: Callable[[str | Path], Any]
    canonical_table: type[Any]
    aggregate: Callable[..., Any]
    build_table: Callable[..., Any]
    reader: Callable[[str | Path], Any]
    writer: Callable[..., Any]


FAMILIES = (
    ReplicaAggregationFamily(
        "protein",
        "canonical_protein_edge_window_table",
        "canonical_protein_edge_replica_aggregation",
        tables.CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_CSV_FILENAME,
        canonical_io.read_canonical_protein_edge_window_csv,
        canonical.CanonicalProteinEdgeWindowTable,
        aggregate_canonical_protein_edges_across_replicas,
        tables.build_canonical_protein_edge_replica_aggregation_table,
        table_io.read_canonical_protein_edge_replica_aggregation_csv,
        table_io.write_canonical_protein_edge_replica_aggregation_csv,
    ),
    ReplicaAggregationFamily(
        "lipid",
        "canonical_protein_lipid_window_table",
        "canonical_protein_lipid_replica_aggregation",
        tables.CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_CSV_FILENAME,
        canonical_io.read_canonical_protein_lipid_window_csv,
        canonical.CanonicalProteinLipidWindowTable,
        aggregate_canonical_protein_lipid_across_replicas,
        tables.build_canonical_protein_lipid_replica_aggregation_table,
        table_io.read_canonical_protein_lipid_replica_aggregation_csv,
        table_io.write_canonical_protein_lipid_replica_aggregation_csv,
    ),
    ReplicaAggregationFamily(
        "glycan",
        "canonical_protein_glycan_window_table",
        "canonical_protein_glycan_replica_aggregation",
        tables.CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_CSV_FILENAME,
        canonical_io.read_canonical_protein_glycan_window_csv,
        canonical.CanonicalProteinGlycanWindowTable,
        aggregate_canonical_protein_glycan_across_replicas,
        tables.build_canonical_protein_glycan_replica_aggregation_table,
        table_io.read_canonical_protein_glycan_replica_aggregation_csv,
        table_io.write_canonical_protein_glycan_replica_aggregation_csv,
    ),
)


class ReplicaAggregationInputError(ValueError):
    """Listed canonical inputs could not be read and combined strictly."""


class ReplicaAggregationExecutionError(ValueError):
    """Accepted aggregation or export model construction failed."""


def load_replica_aggregation_inputs(
    manifest: ReplicaAggregationManifest,
    *,
    mapped_paths: Mapping[Path, Path] | None = None,
) -> dict[str, Any]:
    """Resolve only explicit paths; optional mappings support offline relocation."""
    if type(manifest) is not ReplicaAggregationManifest:
        raise ValueError("Expected exact aggregation manifest")
    manifest.__post_init__()
    combined = {}
    try:
        for family in FAMILIES:
            paths = getattr(manifest, f"{family.name}_canonical_table_paths")
            if not paths:
                continue
            rows = []
            for path in paths:
                target = path if mapped_paths is None else mapped_paths[path]
                table = family.canonical_reader(target)
                require_fixed_metadata(table)
                rows.extend(table.rows)
            # Accepted root rejects duplicates across files and pins reference.
            combined[family.name] = family.canonical_table(
                tuple(sorted(rows, key=lambda row: row.row_order))
            )
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        raise ReplicaAggregationInputError(
            "Listed canonical input tables must be valid and have unique rows."
        ) from None
    return combined


def build_replica_aggregation_tables(
    manifest: ReplicaAggregationManifest,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Reuse accepted A/B/C APIs, without writes or scientific reinterpretation."""
    manifest.__post_init__()
    expected = {
        f.name for f in FAMILIES if getattr(manifest, f"{f.name}_canonical_table_paths")
    }
    if set(inputs) != expected:
        raise ReplicaAggregationExecutionError(
            "Canonical family participation mismatch"
        )
    try:
        groups = tuple(
            build_compatible_replica_aggregation_group(g.spec, g.members)
            for g in manifest.groups
        )
        outputs = {}
        for family in FAMILIES:
            if family.name not in inputs:
                continue
            if type(inputs[family.name]) is not family.canonical_table:
                raise ValueError("Expected exact accepted canonical table type")
            inputs[family.name].__post_init__()
            require_fixed_metadata(inputs[family.name])
            results = []
            for control, group in zip(manifest.groups, groups, strict=True):
                if family.name == "protein":
                    results.append(family.aggregate(group, inputs[family.name]))
                else:
                    correspondences = getattr(control, f"{family.name}_correspondences")
                    if correspondences.correspondences:
                        results.append(
                            family.aggregate(
                                group,
                                inputs[family.name],
                                correspondences=correspondences,
                            )
                        )
            outputs[family.name] = family.build_table(tuple(results))
        return outputs
    except (ValueError, TypeError, OverflowError):
        raise ReplicaAggregationExecutionError(
            "Canonical rows must agree with explicit groups and correspondences."
        ) from None


def execute_replica_aggregation_manifest(
    manifest: ReplicaAggregationManifest,
    *,
    mapped_paths: Mapping[Path, Path] | None = None,
) -> dict[str, Any]:
    """Build every aggregate model before callers begin any output write."""
    inputs = load_replica_aggregation_inputs(manifest, mapped_paths=mapped_paths)
    return build_replica_aggregation_tables(manifest, inputs)
