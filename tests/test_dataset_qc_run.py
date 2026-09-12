"""Run acceptance, output preflight, failed writes, and checksum boundaries."""

import builtins
import hashlib
import json
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from test_dataset_qc_manifest import make_qc_case

from mania.artifact_inventory_io import read_artifact_inventory
from mania.dataset_qc_evidence_io import write_replica_review_qc_evidence
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_qc_run import (
    DERIVED_ROLE,
    OUTPUT_FILES,
    collect_dataset_qc_input_specs,
    run_dataset_qc,
)
from mania.dataset_qc_workflow import DatasetQCWorkflowError
from mania.run_provenance_io import read_run_provenance
from mania.software_identity import SoftwareIdentity
from mania.validation.unified import validate_run_artifacts


@pytest.fixture(autouse=True)
def stable_software_identity(monkeypatch):
    # Keep the accepted provenance model's class identity across the existing
    # software-identity reload test elsewhere in the full suite.
    identity = SoftwareIdentity(
        "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
    )
    monkeypatch.setattr("mania.dataset_qc_run.get_software_identity", lambda: identity)


def completed_qc_run(root, *, mode="none", pending=False, **kwargs):
    options = dict(complete=True, windows=True, multiple=True)
    options.update(kwargs)
    if pending:
        options["outcomes"] = ("fail", "pending", "manual_available")
    manifest, path, template, hard, reviews = make_qc_case(root / "inputs", **options)
    output = root / "qc"
    result = run_dataset_qc(path, output, checksum_mode=mode)
    mappings = {
        s.artifact_id: s.local_path
        for s in collect_dataset_qc_input_specs(manifest, path)
    }
    return result, path, output, mappings


@pytest.mark.parametrize("mode", ["none", "sha256"])
@pytest.mark.parametrize("pending", [False, True])
def test_complete_run_inventory_provenance_and_validation(tmp_path, mode, pending):
    result, _, output, mappings = completed_qc_run(tmp_path, mode=mode, pending=pending)
    assert result.outputs.production_ready is not pending
    inventory = read_artifact_inventory(output / "artifact_inventory.json")
    provenance = read_run_provenance(output / "run_provenance.json")
    assert provenance.status == "completed" and provenance.workflow == "dataset_qc"
    config = provenance.to_dict()["resolved_configuration"]
    assert config["replica_count"] == 7
    assert config["hard_fail_count"] == 2
    assert config["production_ready"] is not pending
    assert config["pending_review_count"] == int(pending)
    assert not provenance.conditions and not provenance.sampling_by_condition
    for entry in inventory.artifacts:
        path = (
            mappings[entry.artifact_id]
            if entry.direction == "input"
            else output / entry.path
        )
        assert entry.byte_size == path.stat().st_size
        assert entry.sha256 == (
            hashlib.sha256(path.read_bytes()).hexdigest() if mode == "sha256" else None
        )
        assert not Path(entry.path).is_absolute() and ".." not in Path(entry.path).parts
        assert entry.role not in ("artifact_inventory", "run_provenance")
    assert {e.role for e in inventory.artifacts if e.direction == "output"} == (
        set(OUTPUT_FILES) - ({DERIVED_ROLE} if pending else set())
    )
    assert (output / OUTPUT_FILES[DERIVED_ROLE]).exists() is not pending
    report = validate_run_artifacts(
        output, scope="dataset_qc", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0


def test_identical_inputs_have_deterministic_outputs_and_none_never_hashes(
    tmp_path,
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected content hash")

    monkeypatch.setattr("mania.artifact_inventory_io.stream_file_sha256", forbidden)
    monkeypatch.setattr("mania.validation.run_artifacts.stream_file_sha256", forbidden)
    first, path, output, mappings = completed_qc_run(tmp_path)
    second = run_dataset_qc(path, tmp_path / "qc_again")
    assert first.outputs == second.outputs
    for filename in OUTPUT_FILES.values():
        assert (output / filename).read_bytes() == (
            second.output_dir / filename
        ).read_bytes()
    assert validate_run_artifacts(
        output, scope="dataset_qc", input_artifact_paths=mappings
    ).complete


def test_zero_runtime_access_and_manifest_relative_resolution(tmp_path, monkeypatch):
    manifest, path, template, _, _ = make_qc_case(tmp_path / "inputs", complete=True)
    real_import, real_open = builtins.__import__, Path.open
    canonical = set(
        template.protein_canonical_table_paths
        + template.lipid_canonical_table_paths
        + template.glycan_canonical_table_paths
    )

    def blocked_import(name, *args, **kwargs):
        if name == "MDAnalysis" or name.startswith("MDAnalysis."):
            pytest.fail("QC imported MDAnalysis")
        return real_import(name, *args, **kwargs)

    def guarded_open(file, *args, **kwargs):
        assert file.resolve() not in canonical, "QC reread canonical source science"
        assert file.suffix not in (".xtc", ".trr", ".dcd", ".pdb", ".psf")
        return real_open(file, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("QC accessed network or subprocess")

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.chdir(tmp_path.parent)
    result = run_dataset_qc(path, tmp_path / "qc")
    assert result.to_dict()["trajectory_passes"] == 0
    mappings = {
        s.artifact_id: s.local_path
        for s in collect_dataset_qc_input_specs(manifest, path)
    }
    assert validate_run_artifacts(
        result.output_dir, scope="dataset_qc", input_artifact_paths=mappings
    ).complete


@pytest.mark.parametrize(
    "mutation",
    [
        "hard_identity",
        "review_identity",
        "no_review",
        "manual_pass",
        "manual_fail",
        "manual_reason",
        "manual_evidence",
        "pre_excluded",
        "missing_key",
        "extra_key",
        "bad_hard",
        "bad_review",
    ],
)
def test_invalid_scientific_controls_write_no_scientific_outputs(tmp_path, mutation):
    manifest, path, _, _, reviews = make_qc_case(tmp_path / "inputs")
    controls = list(manifest.replicas)
    manual = controls[-1].manual_resolution
    if mutation in ("hard_identity", "review_identity", "bad_hard", "bad_review"):
        selected = controls[0]
        evidence_path = path.parent / (
            selected.hard_qc_evidence_path
            if "hard" in mutation
            else selected.review_qc_evidence_path
        )
        data = json.loads(evidence_path.read_text())
        if mutation == "hard_identity":
            data["identity"]["system_id"] = "other"
        elif mutation == "review_identity":
            data["system_id"] = "other"
        else:
            data["unexpected"] = True
        evidence_path.write_text(json.dumps(data))
    elif mutation == "no_review":
        controls[1] = replace(controls[1], review_qc_evidence_path=None)
    elif mutation in ("manual_pass", "manual_fail"):
        i = 1 if mutation == "manual_pass" else 0
        controls[i] = replace(controls[i], manual_resolution=manual)
    elif mutation in ("manual_reason", "manual_evidence"):
        resolution = replace(
            manual,
            **(
                {"decision_reason_code": "BASIC_METRIC_MAD_OUTLIER_REVIEW"}
                if mutation == "manual_reason"
                else {
                    "decision_evidence_ids": ("protein_edge_empty_windows:evidence:0",)
                }
            ),
        )
        controls[-1] = replace(controls[-1], manual_resolution=resolution)
    elif mutation == "pre_excluded":
        template_path = path.parent / manifest.aggregation_manifest_template_path
        data = json.loads(template_path.read_text())
        data["groups"][0]["members"][0].update(
            availability_status="excluded",
            availability_reason="Anonymous exclusion",
        )
        # A protein-only template makes the forbidden pre-exclusion otherwise valid.
        for family in ("lipid", "glycan"):
            data["groups"][0][f"{family}_correspondences"]["correspondences"] = []
        template_path.write_text(json.dumps(data))
    elif mutation == "missing_key":
        controls.pop()
    else:
        controls.append(replace(controls[0], replica_id="extra"))
    manifest = replace(manifest, replicas=tuple(controls))
    assert write_dataset_qc_manifest(manifest, path, overwrite=True).written
    output = tmp_path / "failed"
    with pytest.raises(DatasetQCWorkflowError, match="failed:"):
        run_dataset_qc(path, output)
    assert not any((output / f).exists() for f in OUTPUT_FILES.values())
    provenance = read_run_provenance(output / "run_provenance.json")
    assert provenance.status == "failed"
    assert all(r.role == "artifact_inventory" for r in provenance.artifact_references)


def test_hard_failure_without_review_and_unused_review_skips_cohort(tmp_path):
    manifest, path, _, _, reviews = make_qc_case(tmp_path / "inputs")
    failed = manifest.replicas[0]
    evidence = reviews[failed.replica_key]
    from test_dataset_review_qc import observation

    evidence = replace(evidence, mad_metrics=(observation(key=failed.replica_key),))
    assert write_replica_review_qc_evidence(
        evidence,
        path.parent / failed.review_qc_evidence_path,
        overwrite=True,
    ).written
    first = run_dataset_qc(path, tmp_path / "with_review")
    manifest = replace(
        manifest,
        replicas=(
            replace(failed, review_qc_evidence_path=None),
            *manifest.replicas[1:],
        ),
    )
    assert write_dataset_qc_manifest(manifest, path, overwrite=True).written
    second = run_dataset_qc(path, tmp_path / "without_review")
    assert first.outputs.decisions == second.outputs.decisions
    assert all(
        c.status != "review" for c in first.outputs.decisions.records[0].findings
    )


@pytest.mark.parametrize("role", ["decisions", "summary", "derived", "inventory"])
def test_writer_failure_claims_only_successful_outputs(tmp_path, monkeypatch, role):
    manifest, path, _, _, _ = make_qc_case(tmp_path / "inputs")
    functions = {
        "decisions": "write_dataset_qc_decision_set",
        "summary": "write_dataset_qc_summary_csv",
        "derived": "write_replica_aggregation_manifest",
        "inventory": "write_artifact_inventory",
    }

    def fail(*args, **kwargs):
        raise OSError("Synthetic writer failure")

    monkeypatch.setattr(f"mania.dataset_qc_run.{functions[role]}", fail)
    output = tmp_path / "failed"
    with pytest.raises(DatasetQCWorkflowError, match="Dataset QC export write failed:"):
        run_dataset_qc(path, output)
    provenance = read_run_provenance(output / "run_provenance.json")
    assert provenance.status == "failed"
    actual = {
        r.role for r in provenance.artifact_references if r.role != "artifact_inventory"
    }
    assert actual == {r for r, f in OUTPUT_FILES.items() if (output / f).exists()}
    assert (
        len(actual)
        == {"decisions": 0, "summary": 1, "derived": 2, "inventory": 3}[role]
    )
    if role != "inventory":
        inventory = read_artifact_inventory(output / "artifact_inventory.json")
        assert {
            e.role for e in inventory.artifacts if e.direction == "output"
        } == actual
        mappings = {
            s.artifact_id: s.local_path
            for s in collect_dataset_qc_input_specs(manifest, path)
        }
        report = validate_run_artifacts(
            output, scope="dataset_qc", input_artifact_paths=mappings
        )
        assert report.status == "failed" and not report.complete
        assert not any(i.code == "dataset_qc_lineage_mismatch" for i in report.issues)


def test_overwrite_protects_existing_and_preprocessing_roots(tmp_path):
    _, path, output, _ = completed_qc_run(tmp_path)
    snapshot = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(DatasetQCWorkflowError, match="preflight"):
        run_dataset_qc(path, output)
    assert snapshot == {p.name: p.read_bytes() for p in output.iterdir()}
    assert run_dataset_qc(path, output, overwrite=True).outputs.production_ready
    provenance_path = output / "run_provenance.json"
    data = json.loads(provenance_path.read_text())
    data["workflow"] = "preprocessing"
    provenance_path.write_text(json.dumps(data))
    snapshot = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(DatasetQCWorkflowError, match="preflight"):
        run_dataset_qc(path, output, overwrite=True)
    assert snapshot == {p.name: p.read_bytes() for p in output.iterdir()}
