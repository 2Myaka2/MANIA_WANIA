"""Portable reconstruction and mutations of publication and production lineage."""

import csv
import io
import json
import shutil
from dataclasses import replace

import pytest
from test_dataset_release_run import validate
from test_dataset_release_workflow import make_release_case

from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_run import run_dataset_release
from mania.dataset_release_workflow import DatasetReleaseError
from mania.validation.unified import validate_run_artifacts


@pytest.fixture(scope="module")
def accepted(tmp_path_factory):
    root = tmp_path_factory.mktemp("unified-release")
    path, control = make_release_case(root / "inputs")
    run_dataset_release(path, root / "release", checksum_mode="sha256")
    return root, control


@pytest.fixture
def case(accepted, tmp_path):
    root, control = accepted
    shutil.copytree(root, tmp_path / "relocated")
    base = tmp_path / "relocated"
    return (
        base / "inputs/dataset_release_export_manifest.json",
        base / "release",
        control,
    )


@pytest.mark.parametrize(
    "name",
    [
        "metadata/simulations.csv",
        "metadata/quality_control.csv",
        "metadata/quality_control_findings.csv",
        "metadata/quality_control_evidence.csv",
        "canonical/nodes.csv",
        "canonical/residue_annotations.csv",
        "science/protein_edges_by_window.csv",
        "science/protein_lipid_contacts_by_window.csv",
        "science/protein_glycan_contacts_by_window.csv",
        "aggregates/protein_edges_by_window_replica_aggregation.csv",
        "aggregates/protein_lipid_contacts_by_window_replica_aggregation.csv",
        "aggregates/protein_glycan_contacts_by_window_replica_aggregation.csv",
        "metrics/metrics.csv",
        "release/dataset_manifest.json",
    ],
)
def test_checksum_mutation_fails(case, name):
    path, output, _ = case
    target = output / name
    target.write_bytes(target.read_bytes() + b"\n")
    assert not validate(output, path).passed


@pytest.mark.parametrize("table", ["simulations", "quality_control"])
def test_excluded_removal_fails_even_without_hashes(case, table):
    path, output, _ = case
    run_dataset_release(path, output, overwrite=True)
    target = output / f"metadata/{table}.csv"
    rows = list(csv.DictReader(io.StringIO(target.read_text())))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(r for r in rows if r["replica_id"] != "2")
    target.write_text(stream.getvalue())
    assert not validate(output, path).passed


@pytest.mark.parametrize(
    "mutation",
    [
        "pre_qc",
        "aggregate_substitution",
        "decision_substitution",
        "manifest_input_binding",
        "stage31_provenance",
        "stage32_provenance",
        "derived_manifest",
        "missing_coverage",
    ],
)
def test_file_lineage_mutations_fail_before_write(case, tmp_path, mutation):
    path, _, control = case
    base = path.parent
    if mutation == "pre_qc":
        control = replace(
            control, aggregation_manifest_used_path="qc_input/template.json"
        )
    elif mutation in ("aggregate_substitution", "decision_substitution"):
        field = (
            "protein_aggregate_path"
            if mutation == "aggregate_substitution"
            else "decision_set_path"
        )
        source = base / getattr(control, field)
        destination = base / ("substitute" + source.suffix)
        shutil.copyfile(source, destination)
        control = replace(control, **{field: destination.name})
    elif mutation == "manifest_input_binding":
        control = replace(
            control,
            stage31_run=replace(
                control.stage31_run,
                input_bindings=tuple(
                    replace(b, path="qc_input/template.json")
                    if b.artifact_id == "input:replica_aggregation_manifest"
                    else b
                    for b in control.stage31_run.input_bindings
                ),
            ),
        )
    elif mutation in ("stage31_provenance", "stage32_provenance"):
        target = base / (
            control.stage31_run.provenance_path
            if mutation == "stage31_provenance"
            else control.stage32_run.provenance_path
        )
        payload = json.loads(target.read_text())
        payload["resolved_configuration"]["manifest_path"] = (
            "inputs/unrelated_manifest.json"
        )
        target.write_text(json.dumps(payload))
    elif mutation == "derived_manifest":
        target = base / control.qc_derived_manifest_path
        payload = json.loads(target.read_text())
        payload["groups"][0]["members"][1]["availability_reason"] = (
            "Changed exclusion authority"
        )
        target.write_text(json.dumps(payload))
    else:
        control = replace(
            control,
            canonical_bindings=tuple(
                b for b in control.canonical_bindings if b.family != "glycan"
            ),
        )
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written
    output = tmp_path / "new-output"
    with pytest.raises(DatasetReleaseError):
        run_dataset_release(path, output)
    assert not output.exists()


def test_explicit_control_and_relocation(case):
    path, output, _ = case
    assert validate(output, path).passed
    assert not validate_run_artifacts(output, scope="dataset_release").passed
    target = output / "release/dataset_manifest.json"
    payload = json.loads(target.read_text())
    payload["authoritative_stage31_aggregation_source"] = "another/run_provenance.json"
    target.write_text(json.dumps(payload))
    assert not validate(output, path).passed


def test_unknown_output_and_inventory_roles_fail(case):
    path, output, _ = case
    target = output / "release/artifact_inventory.json"
    payload = json.loads(target.read_text())
    payload["artifacts"][0]["role"] = "unregistered_publication_role"
    target.write_text(json.dumps(payload))
    assert not validate(output, path).passed


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_production_ready_requires_exact_true(case, tmp_path, value):
    path, _, control = case
    target = path.parent / control.stage32_run.provenance_path
    data = json.loads(target.read_text())
    data["resolved_configuration"]["production_ready"] = value
    target.write_text(json.dumps(data))
    with pytest.raises(DatasetReleaseError, match="lineage failed"):
        run_dataset_release(path, tmp_path / "rejected")
