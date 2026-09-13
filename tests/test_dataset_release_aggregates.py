"""QC-before-aggregation authority, exact group binding and copied statistics."""

import csv
import io
from dataclasses import replace

import pytest
from test_dataset_release_metadata import decision
from test_dataset_release_science import AGGREGATE_TYPES, damaged, make_science_case
from test_dataset_release_science import case as case

from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_release_aggregates import (
    DatasetReleaseAggregationAuthority,
    build_dataset_release_glycan_aggregates,
    build_dataset_release_lipid_aggregates,
    build_dataset_release_protein_aggregates,
)
from mania.dataset_release_csv import (
    build_publication_table,
    publication_csv_bytes,
    read_publication_csv,
    write_publication_csv,
)
from mania.dataset_release_science import build_dataset_release_scientific_tables

BUILDERS = (
    build_dataset_release_protein_aggregates,
    build_dataset_release_lipid_aggregates,
    build_dataset_release_glycan_aggregates,
)
SOURCE_NAMES = (
    "protein_aggregate_table",
    "lipid_aggregate_table",
    "glycan_aggregate_table",
)
STATS = (
    "mean_occupancy",
    "std_occupancy",
    "median_occupancy",
    "n_replicates_available",
    "n_replicates_supporting",
    "support_fraction",
)


def build(case, index, source=None, **changes):
    return BUILDERS[index](
        case[SOURCE_NAMES[index]] if source is None else source,
        **{
            "authority": case["aggregation_authority"],
            "metadata_tables": case["metadata_tables"],
            **changes,
        },
    )


def test_pre_qc_manifest_used_rejected_even_for_valid_looking_statistics(tmp_path):
    inputs, template = make_science_case(tmp_path)
    authority = inputs["aggregation_authority"]
    assert template != authority.qc_derived_aggregation_manifest
    with pytest.raises(ValueError, match="manifest used must equal"):
        replace(authority, aggregation_manifest_used=template)
    # Calling both manifests QC-derived cannot bypass the decision/availability check.
    with pytest.raises(ValueError, match="availability disagree"):
        DatasetReleaseAggregationAuthority(authority.decisions, template, template)
    for index in range(3):
        with pytest.raises(ValueError, match="authority"):
            build(inputs, index, authority=True)


@pytest.mark.parametrize("index", range(3))
def test_three_replica_statistics_are_copied_exactly(tmp_path, index):
    inputs, _ = make_science_case(tmp_path, outcomes=("available",) * 3)
    source = inputs[SOURCE_NAMES[index]]
    table = build(inputs, index)
    for original, output in zip(source.rows, table.records(), strict=True):
        assert tuple(output[n] for n in STATS) == (
            0.3,
            0.36055512754639896,
            0.2,
            3,
            2,
            2 / 3,
        )
        for column in table.spec.columns:
            assert output[column.name] == (
                source.canonical_reference_id
                if column.name == "canonical_reference_id"
                else getattr(original, column.name)
            )
        assert not set(output) & {
            "trajectory_id",
            "replica_id",
            "source_resid",
            "source_residue_index",
            "edge_weight",
            "distance_mean_A",
            "distance_min_A",
            "n_contact_frames",
            "n_contact_episodes",
            "mean_episode_length_ns",
            "max_episode_length_ns",
        }


@pytest.mark.parametrize("index", range(3))
def test_single_replica_std_is_blank_and_roundtrips_none(tmp_path, index):
    inputs, _ = make_science_case(tmp_path, unavailable=("3",))
    table = build(inputs, index)
    for row in table.records():
        assert tuple(row[n] for n in STATS) == (0.6, None, 0.6, 1, 1, 1.0)
    cells = tuple(csv.DictReader(io.StringIO(publication_csv_bytes(table).decode())))
    assert all(r["std_occupancy"] == "" for r in cells)
    path = write_publication_csv(table, tmp_path / table.relative_path)
    assert read_publication_csv(table.table_id, path) == table


def test_qc_projected_correspondence_and_repeated_windows(case):
    authority = case["aggregation_authority"]
    assert len(authority.qc_derived_aggregation_manifest.groups) == 2
    for group in authority.qc_derived_aggregation_manifest.groups:
        assert [m.availability_status for m in group.members] == [
            "available",
            "excluded",
            "available",
        ]
        for family in ("lipid", "glycan"):
            correspondence = getattr(
                group, f"{family}_correspondences"
            ).correspondences[0]
            assert [m.replica_id for m in correspondence.members] == ["1", "3"]
            assert [m.local_partner_id for m in correspondence.members] == [
                f"{family}:local:1",
                f"{family}:local:3",
            ]
    for index in range(3):
        table = build(case, index)
        assert table.row_count == 2
        assert {r["n_replicates_available"] for r in table.records()} == {2}
        assert len({(r["window_id"], r["window_index"]) for r in table.records()}) == 2


def test_pending_and_incomplete_qc_coverage_rejected(case):
    authority = case["aggregation_authority"]
    for decisions, pattern in (
        (
            DatasetQCDecisionSet(
                (
                    decision("1", "review", "pending_review"),
                    *authority.decisions.records[1:],
                )
            ),
            "Pending",
        ),
        (
            DatasetQCDecisionSet(authority.decisions.records[:-1]),
            "availability|coverage",
        ),
        (
            DatasetQCDecisionSet((*authority.decisions.records, decision("4"))),
            "coverage",
        ),
    ):
        with pytest.raises(ValueError, match=pattern):
            replace(authority, decisions=decisions)


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_id", "other"),
        ("window_index", 99),
        ("requested_window_start_ns", 0.3),
        ("engine", "gromacs"),
        ("dataset_id", "other"),
        ("system_id", "other"),
        ("condition", "other"),
        ("n_replicates_available", 3),
    ],
)
def test_exact_aggregate_group_metadata_and_denominator(case, field, value):
    source = case["protein_aggregate_table"]
    row = damaged(source.rows[0], **{field: value})
    with pytest.raises(ValueError):
        build(case, 0, damaged(source, rows=(row,)))


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize(
    "field,value",
    [
        ("partner_correspondence_id", "lipid:local:1"),
        ("partner_correspondence_id", "missing"),
        ("partner_name", "different"),
    ],
)
def test_specialized_correspondence_is_explicit(case, index, field, value):
    source = case[SOURCE_NAMES[index]]
    row = replace(source.rows[0], **{field: value})
    with pytest.raises(ValueError, match="correspondence"):
        build(case, index, type(source)((row,)))


@pytest.mark.parametrize("replica", ["1", "2"])
def test_simulations_aggregation_flags_must_match_authority(case, replica):
    metadata = case["metadata_tables"]
    rows = list(metadata.simulations.records())
    for row in rows:
        if row["replica_id"] == replica:
            row["included_in_replica_aggregation"] = not row[
                "included_in_replica_aggregation"
            ]
    altered = replace(
        metadata, simulations=build_publication_table("simulations", rows)
    )
    with pytest.raises(ValueError, match="aggregation inclusion"):
        build(case, 0, metadata_tables=altered)


@pytest.mark.parametrize("index", range(3))
def test_sparse_duplicates_reference_and_foreign_keys(case, index):
    source = case[SOURCE_NAMES[index]]
    assert build(case, index, AGGREGATE_TYPES[index](())).rows == ()
    with pytest.raises(ValueError, match="Duplicate"):
        build(case, index, damaged(source, rows=(source.rows[0],) * 2))
    with pytest.raises(ValueError, match="reference"):
        build(case, index, damaged(source, canonical_reference_id="wrong"))
    metadata = damaged(
        case["metadata_tables"], systems=build_publication_table("systems", ())
    )
    with pytest.raises(ValueError, match="systems.*foreign key"):
        build(case, index, metadata_tables=metadata)
    metadata = damaged(
        case["metadata_tables"], nodes=build_publication_table("nodes", ())
    )
    with pytest.raises(ValueError, match="nodes.*foreign key"):
        build(case, index, metadata_tables=metadata)


def test_zero_available_group_publishes_no_specialized_rows(tmp_path):
    inputs, _ = make_science_case(tmp_path, outcomes=("excluded",) * 3)
    bundle = build_dataset_release_scientific_tables(**inputs)
    assert all(t.row_count == 0 for t in bundle.tables)
    assert inputs["metadata_tables"].simulations.row_count == 3
    for g in inputs["aggregation_authority"].qc_derived_aggregation_manifest.groups:
        assert not g.lipid_correspondences.correspondences
        assert not g.glycan_correspondences.correspondences


def test_different_run_path_and_duplicate_group_cannot_claim_authority(case, tmp_path):
    authority = case["aggregation_authority"]
    manifest = authority.qc_derived_aggregation_manifest
    other = replace(manifest, protein_canonical_table_paths=(tmp_path / "other.csv",))
    with pytest.raises(ValueError, match="manifest used must equal"):
        replace(authority, aggregation_manifest_used=other)
    duplicated = damaged(manifest, groups=manifest.groups * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        DatasetReleaseAggregationAuthority(authority.decisions, duplicated, duplicated)
