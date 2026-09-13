"""Normalized authoritative QC without reevaluation or loss of PASS evidence."""

import copy
from dataclasses import replace

import pytest
from test_dataset_release_metadata import decision

from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_qc_summary import build_dataset_qc_summary
from mania.dataset_release_qc import build_dataset_release_qc_tables


@pytest.mark.parametrize(
    "status,release,mode",
    [
        ("pass", "available", "automatic"),
        ("fail", "excluded", "automatic"),
        ("review", "excluded", "manual"),
        ("review", "available", "manual"),
    ],
)
def test_normalization_preserves_decisions_findings_and_evidence(status, release, mode):
    record = decision(status=status, release=release)
    decisions = DatasetQCDecisionSet((record,))
    tables = build_dataset_release_qc_tables(
        decisions, build_dataset_qc_summary(decisions)
    )
    assert tables.quality_control.row_count == 1
    row = tables.quality_control.records()[0]
    assert (row["qc_status"], row["release_decision"], row["decision_mode"]) == (
        status,
        release,
        mode,
    )
    for name in (
        "reviewer",
        "decision_note",
        "decision_reason_code",
        "human_readable_reason",
    ):
        assert row[name] == getattr(record, name)
    assert row["hard_qc_status"] == ("fail" if status == "fail" else "pass")
    assert row["review_qc_status"] == (None if status == "fail" else status)
    assert tables.quality_control_findings.row_count == len(record.findings)
    assert (
        sum(r["status"] == "pass" for r in tables.quality_control_findings.records())
        == 2
    )
    evidence = tables.quality_control_evidence.records()
    assert len(evidence) == sum(len(f.evidence) for f in record.findings)
    used = [r["evidence_id"] for r in evidence if r["used_for_decision"]]
    assert used == list(record.decision_evidence_ids)
    for finding in record.findings:
        for source in finding.evidence:
            published = next(
                r for r in evidence if r["evidence_id"] == source.evidence_id
            )
            assert all(published[n] == value for n, value in source.to_dict().items())
    if status == "pass":
        assert (
            row["decision_reason_code"]
            is row["reviewer"]
            is row["decision_note"]
            is None
        )


def test_pending_review_not_publishable():
    decisions = DatasetQCDecisionSet(
        (decision(status="review", release="pending_review"),)
    )
    with pytest.raises(ValueError, match="pending_review"):
        build_dataset_release_qc_tables(decisions, build_dataset_qc_summary(decisions))


@pytest.mark.parametrize(
    "change",
    [
        {"trajectory_id": "different"},
        {"total_check_count": 99},
        {"human_readable_reason": "Different explanation"},
        {"reviewer": "Other reviewer"},
        {"decision_note": "Other note"},
        {"release_decision": "excluded"},
        {"review_finding_count": 2},
    ],
)
def test_summary_disagreement_fails(change):
    decisions = DatasetQCDecisionSet((decision(status="review"),))
    summary = build_dataset_qc_summary(decisions)
    row = replace(summary.rows[0], **change)
    with pytest.raises(ValueError, match="disagree"):
        build_dataset_release_qc_tables(decisions, replace(summary, rows=(row,)))


@pytest.mark.parametrize("damage", ["unknown", "multiple", "unsafe_path"])
def test_damaged_decision_evidence_rejected(damage):
    record = copy.deepcopy(decision(status="review"))
    decisions = DatasetQCDecisionSet((record,))
    summary = build_dataset_qc_summary(decisions)
    if damage == "unknown":
        object.__setattr__(record, "decision_evidence_ids", ("missing",))
    elif damage == "multiple":
        object.__setattr__(record.findings[0].evidence[0], "evidence_id", "decision-1")
    else:
        object.__setattr__(
            record.findings[0].evidence[0], "artifact_path", "../private"
        )
    with pytest.raises(ValueError):
        build_dataset_release_qc_tables(decisions, summary)


def test_empty_release_qc_population_fails():
    decisions = DatasetQCDecisionSet(())
    with pytest.raises(ValueError, match="at least one"):
        build_dataset_release_qc_tables(decisions, build_dataset_qc_summary(decisions))
