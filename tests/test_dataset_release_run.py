"""Final release tree, checksum graph, deterministic bytes and failure boundaries."""

import builtins
import hashlib
import json
import shutil
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from test_dataset_release_workflow import make_release_case

from mania.artifact_inventory_io import read_artifact_inventory
from mania.dataset_release_contract import PUBLICATION_ARTIFACT_REGISTRY
from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_run import EXPORT_CONTROL_ARTIFACT_ID, run_dataset_release
from mania.dataset_release_workflow import DatasetReleaseError
from mania.validation.unified import validate_run_artifacts


def validate(output, path):
    return validate_run_artifacts(
        output,
        scope="dataset_release",
        input_artifact_paths={EXPORT_CONTROL_ARTIFACT_ID: path},
    )


@pytest.fixture(scope="module")
def accepted_case(tmp_path_factory):
    root = tmp_path_factory.mktemp("release-source")
    return make_release_case(root)


@pytest.fixture
def copied_case(accepted_case, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(accepted_case[0].parent, root)
    return root / accepted_case[0].name, accepted_case[1]


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_exact_tree_inventory_and_unified(copied_case, tmp_path, mode):
    path, _ = copied_case
    output = tmp_path / "release"
    result = run_dataset_release(path, output, checksum_mode=mode)
    expected = {a.relative_path for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts}
    assert {
        p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()
    } == expected
    inventory = read_artifact_inventory(output / "release/artifact_inventory.json")
    assert inventory.artifact_count == inventory.output_artifact_count == 18
    assert inventory.input_artifact_count == 0
    for entry in inventory.artifacts:
        content = (output / entry.path).read_bytes()
        assert entry.byte_size == len(content)
        assert entry.sha256 == (
            hashlib.sha256(content).hexdigest() if mode == "sha256" else None
        )
    assert not {"release/artifact_inventory.json", "release/provenance.json"} & {
        e.path for e in inventory.artifacts
    }
    report = validate(output, path)
    assert report.passed and report.complete, report.to_dict()
    assert report.specialized_passed_count == 17
    assert result.to_dict()["production_aggregate_lineage_verified"] is True
    assert result.to_dict()["trajectory_passes"] == 0


def test_determinism_no_hashing_and_upstream_unchanged(
    copied_case, tmp_path, monkeypatch
):
    path, _ = copied_case
    before = {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}

    def denied(*args, **kwargs):
        pytest.fail("Checksum none must not invoke content hashing")

    monkeypatch.setattr("mania.artifact_inventory_io.stream_file_sha256", denied)
    monkeypatch.setattr("mania.validation.run_artifacts.stream_file_sha256", denied)
    first, second = tmp_path / "first", tmp_path / "second"
    run_dataset_release(path, first)
    run_dataset_release(path, second)
    for artifact in PUBLICATION_ARTIFACT_REGISTRY.artifacts:
        name = artifact.relative_path
        if name == "release/provenance.json":
            left, right = (
                json.loads((root / name).read_text()) for root in (first, second)
            )
            for field in ("started_at_utc", "ended_at_utc", "duration_seconds"):
                left.pop(field, None)
                right.pop(field, None)
            assert left == right
        else:
            assert (first / name).read_bytes() == (second / name).read_bytes()
        assert str(tmp_path).encode() not in (first / name).read_bytes()
    assert validate(first, path).complete
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize(
    "outcomes,unavailable,empty",
    [
        (("available", "excluded", "available"), (), False),
        (("available", "available", "available"), ("3",), False),
        (("available", "available", "available"), (), False),
        (("available",), (), False),
        (("available", "excluded", "available"), (), True),
    ],
)
def test_complete_population_variants(tmp_path, outcomes, unavailable, empty):
    path, _ = make_release_case(
        tmp_path / "inputs", outcomes=outcomes, unavailable=unavailable, empty=empty
    )
    output = tmp_path / "release"
    result = run_dataset_release(path, output)
    metadata, science = result.bundle.metadata, result.bundle.science
    assert metadata.simulations.row_count == len(outcomes)
    assert metadata.quality_control.row_count == len(outcomes)
    assert all(r["condition"] is None for r in metadata.systems.records())
    for row in metadata.simulations.records():
        index = int(row["replica_id"]) - 1
        assert row["release_decision"] == outcomes[index]
        if row["replica_id"] in unavailable:
            assert row["included_in_replica_aggregation"] is False
            assert row["aggregation_availability_status"] == "unavailable"
        if outcomes[index] == "excluded":
            assert row["included_in_scientific_release"] is False
            for table in (
                metadata.quality_control_findings,
                metadata.quality_control_evidence,
            ):
                assert any(
                    r["replica_id"] == row["replica_id"] for r in table.records()
                )
            assert all(
                r["replica_id"] != row["replica_id"]
                for r in science.protein_edges_by_window.records()
            )
    for table in science.tables:
        for row in table.records():
            if "n_replicates_available" in row:
                assert row["n_replicates_available"] == sum(
                    v == "available" and str(i) not in unavailable
                    for i, v in enumerate(outcomes, 1)
                )
            for number, name in (
                ("target_canonical_residue_number", "target_canonical_resname"),
                ("canonical_residue_number", "canonical_resname"),
            ):
                if row.get(number) == 330:
                    assert row[name] == "THR"
    if len(outcomes) == 1:
        assert all(
            r["std_occupancy"] is None
            for r in science.protein_edges_by_window_replica_aggregation.records()
        )
    if empty:
        assert all(t.row_count == 0 for t in science.tables)
        assert all(
            (output / t.relative_path).read_bytes().count(b"\n") == 1
            for t in science.tables
        )
    assert validate(output, path).passed


def test_no_runtime_or_upstream_science_during_release(
    copied_case, tmp_path, monkeypatch
):
    path, _ = copied_case
    original_import, original_open = builtins.__import__, Path.open

    def denied(*args, **kwargs):
        raise AssertionError(
            "Release accessed a forbidden runtime/scientific operation"
        )

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"MDAnalysis", "pandas", "pyarrow", "fastparquet"}:
            denied()
        return original_import(name, *args, **kwargs)

    def guarded_open(file, *args, **kwargs):
        if file.suffix.lower() in {
            ".pdb",
            ".psf",
            ".dcd",
            ".xtc",
            ".trr",
            ".gro",
            ".tpr",
        }:
            denied()
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)
    for target in (
        "mania.preprocessing.physical_time_sampling.resolve_physical_time_sampling",
        "mania.preprocessing.physical_time_windows.plan_physical_time_windows",
        "mania.dataset_qc_workflow.execute_dataset_qc_manifest",
        "mania.dataset_hard_qc.evaluate_replica_hard_qc",
        "mania.dataset_review_qc.evaluate_dataset_review_qc",
        "mania.replica_aggregation_workflow.build_replica_aggregation_tables",
        "mania.replica_aggregation_run.run_replica_aggregation",
        "mania.dataset_qc_run.run_dataset_qc",
    ):
        monkeypatch.setattr(target, denied)
    output = tmp_path / "release"
    run_dataset_release(path, output)
    assert validate(output, path).passed


def test_build_failure_writes_nothing(copied_case, tmp_path):
    path, control = copied_case
    control = replace(control, annotation_publication_system_keys=())
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written
    output = tmp_path / "release"
    with pytest.raises(DatasetReleaseError, match="validation failed"):
        run_dataset_release(path, output)
    assert not output.exists()


def test_same_condition_systems_stay_distinct(tmp_path):
    path, _ = make_release_case(
        tmp_path / "inputs", systems=("T330M", "separate-system"), condition="NORM"
    )
    output = tmp_path / "release"
    result = run_dataset_release(path, output)
    metadata = result.bundle.metadata
    assert metadata.systems.row_count == 2
    assert metadata.simulations.row_count == 6
    assert metadata.residue_annotations.row_count == 1380
    assert {r["condition"] for r in metadata.systems.records()} == {"NORM"}
    for table in result.bundle.science.tables[:-1]:
        assert {r["system_id"] for r in table.records()} == {"T330M", "separate-system"}
    assert validate(output, path).passed


def test_exact_accepted_three_replica_values(tmp_path):
    path, _ = make_release_case(
        tmp_path / "inputs", outcomes=("available",) * 3, occupancies=(0.7, 0.0, 0.2)
    )
    output = tmp_path / "release"
    result = run_dataset_release(path, output)
    for table in result.bundle.science.tables[3:6]:
        row = table.records()[0]
        assert row["mean_occupancy"] == 0.3
        assert row["median_occupancy"] == 0.2
        assert row["std_occupancy"] == 0.36055512754639896
        assert row["n_replicates_available"] == 3
        assert row["n_replicates_supporting"] == 2
        assert row["support_fraction"] == 2 / 3
    assert validate(output, path).passed


@pytest.mark.parametrize("phase", ["csv", "manifest", "inventory", "provenance"])
def test_writer_failure_never_claims_complete(
    copied_case, tmp_path, monkeypatch, phase
):
    path, _ = copied_case
    from mania import dataset_release_run as run

    def failed(*args, **kwargs):
        raise OSError("controlled writer failure")

    monkeypatch.setattr(
        run,
        {
            "csv": "write_publication_csv",
            "manifest": "write_dataset_release_manifest",
            "inventory": "write_artifact_inventory",
            "provenance": "write_atomic_text",
        }[phase],
        failed,
    )
    output = tmp_path / "release"
    with pytest.raises(DatasetReleaseError, match="write failed"):
        run.run_dataset_release(path, output)
    assert not (output / "release/dataset_manifest.json").exists()
    assert not validate(output, path).passed


def test_overwrite_and_unknown_output_protection(copied_case, tmp_path):
    path, _ = copied_case
    output = tmp_path / "release"
    run_dataset_release(path, output)
    with pytest.raises(DatasetReleaseError, match="write failed"):
        run_dataset_release(path, output)
    assert validate(output, path).passed
    run_dataset_release(path, output, overwrite=True)
    assert validate(output, path).passed
    (output / "extra.csv").write_text("unknown\n")
    assert not validate(output, path).passed
    with pytest.raises(DatasetReleaseError, match="write failed"):
        run_dataset_release(path, output, overwrite=True)
    assert (output / "extra.csv").read_text() == "unknown\n"


def test_upstream_sha256_is_checked(tmp_path):
    path, control = make_release_case(tmp_path / "inputs", mode="sha256")
    output = tmp_path / "release"
    run_dataset_release(path, output)
    assert validate(output, path).passed
    target = path.parent / control.canonical_bindings[0].path
    before = target.read_bytes()
    after = before.replace(b"MET", b"GLY", 1)
    assert before != after and len(before) == len(after)
    target.write_bytes(after)
    with pytest.raises(DatasetReleaseError, match="lineage failed"):
        run_dataset_release(path, tmp_path / "mutated")
    assert not validate(output, path).passed


def test_missing_excluded_time_windows_are_not_fabricated(copied_case, tmp_path):
    path, control = copied_case
    control = replace(
        control,
        temporal_evidence_paths=tuple(
            p for p in control.temporal_evidence_paths if "/2/" not in p
        ),
    )
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written
    output = tmp_path / "release"
    result = run_dataset_release(path, output)
    assert result.bundle.metadata.simulations.row_count == 3
    assert not any(
        r["replica_id"] == "2" for r in result.bundle.metadata.time_windows.records()
    )
    assert validate(output, path).passed


def test_software_and_contact_authority_is_copied(copied_case, tmp_path):
    path, _ = copied_case
    result = run_dataset_release(path, tmp_path / "release")
    software = {
        r["component_name"]: r["version"]
        for r in result.bundle.metadata.software_versions.records()
    }
    assert software == {"mania-wania": "0.1.0", "NAMD": None}
    rows = result.bundle.metadata.contact_definitions.records()
    cutoffs = {
        (r["contact_layer"], r["number_value"])
        for r in rows
        if r["parameter_path"] == "$/cutoff/value"
    }
    assert ("protein-lipid", 6) in cutoffs and ("protein-glycan", 4.5) in cutoffs
    assert all(
        r["boolean_value"] is False
        for r in rows
        if r["parameter_path"].endswith(
            "mania_internal_minimum_image_correction_applied"
        )
    )
