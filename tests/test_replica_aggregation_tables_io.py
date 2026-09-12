"""Exact CSV round trips, blank singleton SD and strict scalar failures."""

import csv
import io

import pytest
from test_replica_aggregation_manifest import make_manifest

from mania.replica_aggregation_tables_io import ReplicaAggregationCsvReadError
from mania.replica_aggregation_workflow import (
    FAMILIES,
    execute_replica_aggregation_manifest,
)


@pytest.mark.parametrize("empty", [False, True])
def test_csv_roundtrip_determinism_and_overwrite(tmp_path, empty):
    manifest, _ = make_manifest(tmp_path, complete=not empty, empty=empty)
    tables = execute_replica_aggregation_manifest(manifest)
    for family in FAMILIES:
        table = tables[family.name]
        first = family.writer(table, tmp_path / "one")
        second = family.writer(table, tmp_path / "two")
        assert first.written and second.written
        data = first.output_path.read_bytes()
        assert data == second.output_path.read_bytes()
        assert data.endswith(b"\n") and b"\r\n" not in data
        assert family.reader(first.output_path) == table
        assert not family.writer(table, tmp_path / "one").written
        assert family.writer(table, tmp_path / "one", overwrite=True).written
        rows = list(csv.DictReader(io.StringIO(data.decode())))
        if empty:
            assert rows == []
        for row in rows:
            if row["n_replicates_available"] == "1":
                assert row["std_occupancy"] == ""
            if row["system_id"] == "namd-none":
                assert row["condition"] == ""


@pytest.mark.parametrize(
    "field,value",
    [
        ("std_occupancy", "None"),
        ("std_occupancy", "null"),
        ("std_occupancy", "NA"),
        ("mean_occupancy", "NaN"),
        ("mean_occupancy", "inf"),
        ("right_endpoint_inclusive", "False"),
        ("right_endpoint_inclusive", "0"),
        ("n_replicates_available", "3.0"),
        ("n_replicates_available", "true"),
        ("support_fraction", "0.9"),
        ("std_occupancy", ""),
        ("source_canonical_resname", "FAKE"),
    ],
)
def test_strict_csv_mutations(tmp_path, field, value):
    manifest, _ = make_manifest(tmp_path, specialized=False)
    family = FAMILIES[0]
    target = family.writer(
        execute_replica_aggregation_manifest(manifest)["protein"], tmp_path / "out"
    ).output_path
    rows = list(csv.reader(io.StringIO(target.read_text())))
    rows[1][rows[0].index(field)] = value
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    target.write_text(stream.getvalue())
    with pytest.raises(ReplicaAggregationCsvReadError):
        family.reader(target)
