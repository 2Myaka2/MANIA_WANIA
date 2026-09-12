"""Authoritative accepted decision model serialization and traceability."""

import json

import pytest
from test_dataset_qc_manifest import make_qc_case

from mania.dataset_qc_decision_io import (
    dataset_qc_decision_set_bytes,
    read_dataset_qc_decision_set,
    write_dataset_qc_decision_set,
)
from mania.dataset_qc_workflow import execute_dataset_qc_manifest


def test_decision_json_exact_roundtrip(tmp_path):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    decisions = execute_dataset_qc_manifest(manifest, path).decisions
    target = tmp_path / "decisions.json"
    assert write_dataset_qc_decision_set(decisions, target).written
    assert read_dataset_qc_decision_set(target) == decisions
    assert target.read_bytes() == dataset_qc_decision_set_bytes(decisions)
    assert not write_dataset_qc_decision_set(decisions, target).written
    assert write_dataset_qc_decision_set(decisions, target, overwrite=True).written
    assert target.read_bytes().endswith(b"\n")


@pytest.mark.parametrize(
    "mutation",
    [
        "reason",
        "release",
        "evidence",
        "unknown",
        "duplicate_check",
        "duplicate_evidence",
        "reference",
        "reviewer",
        "note",
        "scalar",
    ],
)
def test_decision_strict_damage(tmp_path, mutation):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    target = tmp_path / "decisions.json"
    decisions = execute_dataset_qc_manifest(manifest, path).decisions
    assert write_dataset_qc_decision_set(decisions, target).written
    data = json.loads(target.read_text())
    record = data["records"][0]
    if mutation == "reason":
        record["decision_reason_code"] = "RMSD_DRIFT_REVIEW"
    elif mutation == "release":
        record["release_decision"] = "available"
    elif mutation == "evidence":
        record["decision_evidence_ids"] = ["unknown-evidence"]
    elif mutation == "unknown":
        record["condition"] = "NORM"
    elif mutation == "duplicate_check":
        record["findings"].append(record["findings"][0])
    elif mutation == "duplicate_evidence":
        record["findings"][1]["evidence"][0]["evidence_id"] = record["findings"][0][
            "evidence"
        ][0]["evidence_id"]
    elif mutation == "reference":
        data["canonical_reference_id"] = "bad"
    elif mutation == "reviewer":
        data["records"][-1]["reviewer"] = None
    elif mutation == "note":
        data["records"][-1]["decision_note"] = ""
    else:
        record["findings"][0]["evidence"][0]["observed_value"] = 1
    target.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_dataset_qc_decision_set(target)
