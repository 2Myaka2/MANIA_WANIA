"""Dataset row identities, deterministic ordering and copied statistics."""

from dataclasses import fields, replace

import pytest
from test_replica_aggregation_manifest import make_manifest

from mania.replica_aggregation_workflow import execute_replica_aggregation_manifest


def test_exact_occupancy_only_columns(tmp_path):
    manifest, _ = make_manifest(tmp_path)
    for family, table in execute_replica_aggregation_manifest(manifest).items():
        names = tuple(f.name for f in fields(table.rows[0]))
        assert names[:16] == (
            "dataset_id",
            "system_id",
            "engine",
            "variant_id",
            "condition",
            "disulfide_state",
            "window_id",
            "window_index",
            "requested_production_start_ns",
            "requested_production_end_ns",
            "requested_window_start_ns",
            "requested_window_end_ns",
            "right_endpoint_inclusive",
            "window_length_ns",
            "window_step_ns",
            "overlap_percent",
        )
        assert names[-6:] == (
            "mean_occupancy",
            "std_occupancy",
            "median_occupancy",
            "n_replicates_available",
            "n_replicates_supporting",
            "support_fraction",
        )
        assert names[16:-6] == (
            (
                "source_canonical_residue_number",
                "source_canonical_resname",
                "target_canonical_residue_number",
                "target_canonical_resname",
                "edge_type",
            )
            if family == "protein"
            else (
                "canonical_residue_number",
                "canonical_resname",
                "partner_correspondence_id",
                "partner_name",
            )
        )
        assert table.row_count == 1
        with pytest.raises(ValueError, match="Duplicate"):
            replace(table, rows=table.rows * 2)
        with pytest.raises(ValueError):
            replace(table.rows[0], support_fraction=0.9)
        with pytest.raises(ValueError):
            replace(table.rows[0], mean_occupancy=float("inf"))


def test_group_metadata_not_identity_and_order(tmp_path):
    manifest, _ = make_manifest(tmp_path, complete=True)
    table = execute_replica_aggregation_manifest(manifest)["protein"]
    with pytest.raises(ValueError, match="order"):
        replace(table, rows=tuple(reversed(table.rows)))
    row = table.rows[0]
    assert replace(row, condition="another label").row_identity == row.row_identity
