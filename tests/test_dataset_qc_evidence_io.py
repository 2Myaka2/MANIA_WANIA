"""Strict adapters reconstruct every accepted hard/review evidence model."""

import json
from dataclasses import fields
from typing import get_type_hints

import pytest
from test_dataset_hard_qc import artifact, inputs, row
from test_dataset_review_qc import observation, review

from mania.dataset_hard_qc import evaluate_replica_hard_qc
from mania.dataset_qc_evidence_io import (
    ReplicaHardQCEvidence,
    read_replica_hard_qc_evidence,
    read_replica_review_qc_evidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)


@pytest.mark.parametrize("family", ["protein_edge", "protein_lipid", "protein_glycan"])
def test_hard_evidence_exact_public_inputs_and_roundtrip(tmp_path, family):
    hints = get_type_hints(evaluate_replica_hard_qc)
    del hints["return"]
    assert get_type_hints(ReplicaHardQCEvidence) == hints
    evidence = ReplicaHardQCEvidence(
        **inputs(required_artifacts=(artifact(family, rows=(row(family),)),))
    )
    path = tmp_path / "hard.json"
    assert write_replica_hard_qc_evidence(evidence, path).written
    restored = read_replica_hard_qc_evidence(path)
    assert restored == evidence
    assert (
        evaluate_replica_hard_qc(
            **{f.name: getattr(restored, f.name) for f in fields(restored)}
        ).hard_qc_status
        == "pass"
    )
    assert not write_replica_hard_qc_evidence(evidence, path).written


def test_review_nested_metrics_roundtrip(tmp_path):
    evidence = review(
        metrics=(observation(value=1.25, unit="nm", metric_family="basic_metric"),)
    )
    path = tmp_path / "review.json"
    assert write_replica_review_qc_evidence(evidence, path).written
    assert read_replica_review_qc_evidence(path) == evidence
    assert not write_replica_review_qc_evidence(evidence, path).written


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "bool_int",
        "count_string",
        "time_string",
        "bad_reference",
        "identity",
        "bad_row",
        "nonfinite",
        "null_raw",
    ],
)
def test_hard_evidence_rejects_json_damage(tmp_path, mutation):
    path = tmp_path / "hard.json"
    value = ReplicaHardQCEvidence(
        **inputs(required_artifacts=(artifact(rows=(row(),)),))
    )
    assert write_replica_hard_qc_evidence(value, path).written
    data = json.loads(path.read_text())
    if mutation == "unknown":
        data["raw_integrity"]["extra"] = True
    elif mutation == "missing":
        del data["required_metadata"]
    elif mutation == "bool_int":
        data["raw_integrity"]["topology_readable"] = 1
    elif mutation == "count_string":
        data["raw_integrity"]["topology_atom_count"] = "10000"
    elif mutation == "time_string":
        data["sampling_plan"]["selected_samples"][0]["actual_time_ps"] = "50000"
    elif mutation == "bad_reference":
        data["mapping_binding"]["mapping_table"]["canonical_reference_id"] = "bad"
    elif mutation == "identity":
        del data["identity"]["condition"]
    elif mutation == "bad_row":
        data["required_artifacts"][0]["canonical_table"]["rows"][0]["occupancy"] = True
    elif mutation == "nonfinite":
        data["sampling_plan"]["coverage_fraction"] = float("nan")
    else:
        data["raw_integrity"] = None
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_replica_hard_qc_evidence(path)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "bool_int",
        "number_string",
        "count_bool",
        "metric_key",
        "infinity",
    ],
)
def test_review_evidence_rejects_json_damage(tmp_path, mutation):
    path = tmp_path / "review.json"
    assert write_replica_review_qc_evidence(
        review(metrics=(observation(),)), path
    ).written
    data = json.loads(path.read_text())
    if mutation == "unknown":
        data["rmsd_drift"]["threshold"] = 1
    elif mutation == "missing":
        del data["rmsd_drift"]
    elif mutation == "bool_int":
        data["rmsd_drift"]["drift_detected"] = 0
    elif mutation == "number_string":
        data["mad_metrics"][0]["value"] = "1.0"
    elif mutation == "count_bool":
        data["protein_edge_empty_windows"]["empty_window_count"] = False
    elif mutation == "metric_key":
        data["mad_metrics"][0]["system_id"] = "another-system"
    else:
        data["mad_metrics"][0]["value"] = float("inf")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_replica_review_qc_evidence(path)
