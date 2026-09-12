"""Separate run metadata, opt-in streaming checksums and failed output evidence."""

import hashlib
import json
from dataclasses import replace

import pytest
from test_replica_aggregation_manifest import make_manifest
from test_replica_specialized_aggregation import collection

from mania import replica_aggregation_run as run
from mania.artifact_inventory_io import read_artifact_inventory
from mania.run_provenance_io import read_run_provenance
from mania.validation.unified import validate_run_artifacts


def completed_run(tmp_path, mode="none", **options):
    manifest, path = make_manifest(tmp_path / "inputs", **options)
    output = tmp_path / "aggregate"
    result = run.run_replica_aggregation(path, output, checksum_mode=mode)
    mappings = {
        s.artifact_id: s.local_path
        for s in run.collect_replica_aggregation_input_specs(manifest, path)
    }
    return manifest, path, output, result, mappings


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_complete_inventory_provenance_and_reconstruction(tmp_path, mode, monkeypatch):
    if mode == "none":

        def forbidden(*args, **kwargs):
            raise AssertionError("none must never invoke content hashing")

        monkeypatch.setattr("mania.artifact_inventory_io.stream_file_sha256", forbidden)
        monkeypatch.setattr(
            "mania.validation.run_artifacts.stream_file_sha256", forbidden
        )
    manifest, path, output, result, mappings = completed_run(
        tmp_path,
        mode,
        complete=True,
    )
    inventory = read_artifact_inventory(output / "artifact_inventory.json")
    provenance = read_run_provenance(output / "run_provenance.json")
    assert inventory.workflow == provenance.workflow == "replica_aggregation"
    assert provenance.to_dict()["resolved_configuration"] == (
        run.replica_aggregation_configuration(manifest, mode)
    )
    assert provenance.resolved_configuration["group_count"] == 5
    assert provenance.sampling_by_condition == ()
    assert provenance.conditions == ("NORM",)
    assert None in provenance.resolved_configuration["scientific_conditions"]
    assert "groups" not in provenance.resolved_configuration
    assert len(inventory.artifacts) == 9  # manifest + 5 canonical inputs + 3 outputs
    assert len(provenance.artifact_references) == 4
    for entry in inventory.artifacts:
        local = (
            mappings[entry.artifact_id]
            if entry.direction == "input"
            else (output / entry.path)
        )
        assert entry.byte_size == local.stat().st_size
        assert entry.sha256 == (
            hashlib.sha256(local.read_bytes()).hexdigest() if mode == "sha256" else None
        )
        assert entry.condition is None
        assert entry.path not in ("artifact_inventory.json", "run_provenance.json")
    for file in ("run_provenance.json", "artifact_inventory.json"):
        text = (output / file).read_text()
        assert str(tmp_path) not in text
        assert "pbc_audit" not in text and "runtime_metadata" not in text
        assert "temporal_execution" not in text
    report = validate_run_artifacts(
        output,
        scope="replica_aggregation",
        input_artifact_paths=mappings,
    )
    assert report.status == "passed", report.to_dict()
    assert report.complete is True
    assert all(r.status == "passed" for r in report.specialized_records)
    assert result.to_dict()["trajectory_passes"] == 0
    assert path.exists()


def test_output_write_failure_preserves_only_written_references(tmp_path, monkeypatch):
    manifest, path = make_manifest(tmp_path / "inputs")
    output = tmp_path / "out"

    def broken(*args, **kwargs):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(
        run,
        "FAMILIES",
        (
            run.FAMILIES[0],
            replace(run.FAMILIES[1], writer=broken),
            run.FAMILIES[2],
        ),
    )
    with pytest.raises(run.ReplicaAggregationRunError, match="export write failed"):
        run.run_replica_aggregation(path, output)
    provenance = read_run_provenance(output / "run_provenance.json")
    assert provenance.status == "failed"
    assert [r.role for r in provenance.artifact_references] == [
        run.FAMILIES[0].output_role,
        "artifact_inventory",
    ]
    mappings = {
        s.artifact_id: s.local_path
        for s in run.collect_replica_aggregation_input_specs(manifest, path)
    }
    report = validate_run_artifacts(
        output, scope="replica_aggregation", input_artifact_paths=mappings
    )
    assert report.status == "passed", report.to_dict()
    assert (
        "private filesystem detail" not in (output / "run_provenance.json").read_text()
    )


def test_scientific_failure_writes_no_aggregate_csv(tmp_path, monkeypatch):
    _, path = make_manifest(tmp_path / "inputs")
    output = tmp_path / "out"

    def broken(*args, **kwargs):
        raise ValueError("Scientific binding mismatch")

    monkeypatch.setattr(run, "build_replica_aggregation_tables", broken)
    with pytest.raises(
        run.ReplicaAggregationRunError, match="Replica aggregation failed:"
    ):
        run.run_replica_aggregation(path, output)
    assert all(not (output / f.filename).exists() for f in run.FAMILIES)
    assert read_run_provenance(output / "run_provenance.json").status == "failed"


def test_overwrite_preserves_inputs_and_other_workflow(tmp_path):
    _, path, output, _, mappings = completed_run(tmp_path)
    before = {p: p.read_bytes() for p in mappings.values()}
    with pytest.raises(run.ReplicaAggregationRunError):
        run.run_replica_aggregation(path, output)
    run.run_replica_aggregation(path, output, overwrite=True)
    assert before == {p: p.read_bytes() for p in mappings.values()}
    provenance = output / "run_provenance.json"
    data = json.loads(provenance.read_text())
    data["workflow"] = "preprocessing"
    provenance.write_text(json.dumps(data))
    with pytest.raises(run.ReplicaAggregationRunError):
        run.run_replica_aggregation(path, output, overwrite=True)
    assert json.loads(provenance.read_text())["workflow"] == "preprocessing"


def test_specialized_only_and_observed_inputs_without_correspondence(tmp_path):
    from mania.replica_aggregation_manifest_io import write_replica_aggregation_manifest

    manifest, path = make_manifest(tmp_path / "inputs")
    manifest = replace(manifest, protein_canonical_table_paths=())
    assert write_replica_aggregation_manifest(manifest, path, overwrite=True).written
    output = tmp_path / "specialized"
    result = run.run_replica_aggregation(path, output)
    assert set(result.tables) == {"lipid", "glycan"}
    assert not (output / run.FAMILIES[0].filename).exists()
    manifest = replace(
        manifest,
        groups=(
            replace(
                manifest.groups[0],
                lipid_correspondences=collection(),
                glycan_correspondences=collection(),
            ),
        ),
    )
    assert write_replica_aggregation_manifest(manifest, path, overwrite=True).written
    result = run.run_replica_aggregation(path, tmp_path / "no-correspondence")
    assert all(table.row_count == 0 for table in result.tables.values())
    for family in run.FAMILIES[1:]:
        target = result.output_dir / family.filename
        assert target.exists() and len(target.read_text().splitlines()) == 1


def test_later_scientific_family_failure_publishes_no_csv(tmp_path):
    from mania.canonical_window_tables_io import (
        write_canonical_protein_glycan_window_csv,
    )

    _, path = make_manifest(tmp_path / "inputs")
    family = run.FAMILIES[2]
    input_path = path.parent / "protein_glycan_contacts_by_window_canonical.csv"
    original = family.canonical_reader(input_path)
    changed = replace(
        original,
        rows=tuple(replace(row, condition="different") for row in original.rows),
    )
    assert write_canonical_protein_glycan_window_csv(
        changed,
        input_path.parent,
        overwrite=True,
    ).written
    output = tmp_path / "out"
    with pytest.raises(
        run.ReplicaAggregationRunError, match="Replica aggregation failed"
    ):
        run.run_replica_aggregation(path, output)
    assert all(not (output / f.filename).exists() for f in run.FAMILIES)
    assert read_run_provenance(output / "run_provenance.json").status == "failed"
