"""RMSD measurements never become an implicit scientific PASS assessment."""

import shutil

import pytest
from test_dataset_review_qc import evidence, hard
from test_production_handoff import handoff_case

from mania.dataset_measurement_review import (
    ExplicitRMSDAssessment,
    build_replica_review_evidence,
    build_rmsd_drift_assessment,
    present_rmsd_review,
    save_review_assessment,
)
from mania.dataset_review_qc import (
    ProteinEdgeEmptyWindowEvidence,
    evaluate_dataset_review_qc,
)


def assessment(drift=False):
    return ExplicitRMSDAssessment(
        schema_version="mania.production_review_assessment.v0.1",
        drift_detected=drift,
        assessment_method="Explicit scientific curve inspection",
        reviewer="Reviewer",
        decision_note="Synthetic assessment solely for workflow verification",
    )


def test_measurements_and_no_assessment_cannot_create_pass(tmp_path, monkeypatch):
    case = handoff_case(tmp_path, monkeypatch)
    shutil.rmtree(case.preparation)
    display = present_rmsd_review(case.root)
    assert display["automatic_drift_classification"] is False
    assert display["assessment_state"] == "explicit_assessment_required"
    assert "drift_detected" not in display
    with pytest.raises(ValueError, match="alone"):
        build_rmsd_drift_assessment(case.root, None)


@pytest.mark.parametrize("drift,status", [(False, "pass"), (True, "review")])
def test_explicit_assessment_preserves_existing_stage32_behavior(
    tmp_path, monkeypatch, drift, status
):
    case = handoff_case(tmp_path, monkeypatch)
    review = build_replica_review_evidence(
        case.root,
        assessment(drift),
        empty_windows=ProteinEdgeEmptyWindowEvidence(2, 0, (evidence(),)),
    )
    result = evaluate_dataset_review_qc((hard(review.replica_key),), (review,))
    assert result.evaluations[0].review_qc_status == status
    assert review.rmsd_drift.drift_detected is drift
    assert all("sha256=" in e.details for e in review.rmsd_drift.evidence)
    destination = case.root / "postproduction/attempt_0001/assessment.json"
    save_review_assessment(case.root, assessment(drift), destination)
    assert destination.is_file()
    with pytest.raises(ValueError, match="Protected"):
        save_review_assessment(case.root, assessment(drift), destination)


@pytest.mark.parametrize(
    "change",
    [
        {"drift_detected": "False"},
        {"drift_detected": 0},
        {"assessment_method": ""},
        {"reviewer": " "},
    ],
)
def test_no_hidden_default_or_coerced_assessment(change):
    values = assessment().model_dump(mode="json")
    values.update(change)
    with pytest.raises(ValueError):
        ExplicitRMSDAssessment.model_validate(values).require_authority()


def test_saved_review_binds_sealed_measurements_and_requires_new_namespace(
    tmp_path, monkeypatch
):
    import json

    from mania.dataset_measurement_review import load_review_assessment

    case = handoff_case(tmp_path, monkeypatch)
    value = assessment()
    destination = case.root / "postproduction/attempt_0001/review.json"
    save_review_assessment(case.root, value, destination)
    assert load_review_assessment(case.root, destination) == value
    data = json.loads(destination.read_text())
    data["measurement_bindings"]["protein_rmsd_measurement.json"] = "f" * 64
    destination.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="sealed"):
        load_review_assessment(case.root, destination)
    with pytest.raises(ValueError, match="postproduction"):
        save_review_assessment(
            case.root, value, case.root / "preprocessing/review.json"
        )
