"""Stage 32.A severity, provenance, immutable structure and pure contract smokes."""

import ast
import builtins
import datetime
import inspect
import io
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, fields, replace
from itertools import product
from pathlib import Path
from typing import get_args

import pytest

from mania import dataset_qc_contract as m
from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)

HARD_CODES = (
    "TOPOLOGY_UNREADABLE",
    "TRAJECTORY_UNREADABLE",
    "TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH",
    "TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH",
    "CANONICAL_MAPPING_INCOMPLETE",
    "PROTEIN_PBC_BROKEN",
    "FRAME_TIME_NOT_STRICTLY_INCREASING",
    "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
    "REQUIRED_METADATA_MISSING",
    "REQUIRED_ARTIFACT_MISSING",
    "SCHEMA_INVALID",
    "CANONICAL_REFERENCE_MISMATCH",
    "FORBIDDEN_SELF_LOOP",
    "DUPLICATE_RECORD",
    "OCCUPANCY_OUT_OF_RANGE",
)
REVIEW_CODES = (
    "RMSD_DRIFT_REVIEW",
    "PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT",
    "EDGE_COUNT_MAD_OUTLIER_REVIEW",
    "CONTACT_FRACTION_MAD_OUTLIER_REVIEW",
    "BASIC_METRIC_MAD_OUTLIER_REVIEW",
    "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW",
)
EVIDENCE_FIELDS = (
    "evidence_id",
    "evidence_type",
    "artifact_role",
    "artifact_path",
    "window_id",
    "metric_name",
    "observed_value",
    "expected_or_threshold",
    "details",
)
CHECK_FIELDS = (
    "check_id",
    "status",
    "reason_code",
    "human_readable_reason",
    "evidence",
)
DECISION_FIELDS = (
    "dataset_id",
    "system_id",
    "trajectory_id",
    "replica_id",
    "qc_status",
    "findings",
    "release_decision",
    "decision_mode",
    "decision_reason_code",
    "human_readable_reason",
    "decision_evidence_ids",
    "reviewer",
    "decision_note",
)


def evidence(**changes):
    return m.QCEvidenceRecord(
        **{
            "evidence_id": "e1",
            "evidence_type": "metric",
            "artifact_role": None,
            "artifact_path": None,
            "window_id": None,
            "metric_name": "production_frame_coverage",
            "observed_value": "1.0",
            "expected_or_threshold": ">=0.95",
            "details": None,
            **changes,
        }
    )


def bare_evidence(evidence_type, **payload):
    return evidence(
        **{
            "evidence_type": evidence_type,
            "metric_name": None,
            "observed_value": None,
            "expected_or_threshold": None,
            **payload,
        }
    )


def finding(status="pass", **changes):
    code = {
        "pass": None,
        "review": "RMSD_DRIFT_REVIEW",
        "fail": "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
    }[status]
    return m.ReplicaQCCheckResult(
        **{
            "check_id": "check-1",
            "status": status,
            "reason_code": code,
            "human_readable_reason": None
            if status == "pass"
            else "Supplied QC observation.",
            "evidence": (
                evidence(observed_value="0.94" if status == "fail" else "1.0"),
            ),
            **changes,
        }
    )


def decision(status="pass", **changes):
    check = finding(status)
    return m.ReplicaQCDecisionRecord(
        **{
            "dataset_id": "napi2b-v1-test",
            "system_id": "wt-norm",
            "trajectory_id": "traj-1",
            "replica_id": "1",
            "qc_status": status,
            "findings": (check,),
            "release_decision": {
                "pass": "available",
                "review": "pending_review",
                "fail": "excluded",
            }[status],
            "decision_mode": "automatic",
            "decision_reason_code": check.reason_code,
            "human_readable_reason": check.human_readable_reason,
            "decision_evidence_ids": () if status == "pass" else ("e1",),
            "reviewer": None,
            "decision_note": None,
            **changes,
        }
    )


def manual_decision(release="excluded", **changes):
    return decision(
        "review",
        **{
            "release_decision": release,
            "decision_mode": "manual",
            "reviewer": "verifier-7",
            "decision_note": "Examined supplied evidence.",
            **changes,
        },
    )


def encode(model):
    return json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":"))


def test_constants_literals_and_pinned_non_init_reference():
    assert (
        m.DATASET_QC_DECISION_SET_SCHEMA_VERSION == "mania.dataset_qc_decision_set.v0.1"
    )
    assert m.DATASET_QC_DECISION_SET_KIND == "mania_dataset_qc_decision_set"
    assert get_args(m.QCStatus) == ("pass", "review", "fail")
    assert get_args(m.QCReleaseDecision) == ("available", "pending_review", "excluded")
    assert get_args(m.QCDecisionMode) == ("automatic", "manual")
    assert get_args(m.QCReasonCode) == HARD_CODES + REVIEW_CODES
    assert get_args(m.QCEvidenceType) == (
        "artifact",
        "metric",
        "window",
        "mapping",
        "pbc",
        "manual_review",
    )
    model = m.DatasetQCDecisionSet(())
    assert model.schema_version == m.DATASET_QC_DECISION_SET_SCHEMA_VERSION
    assert model.kind == m.DATASET_QC_DECISION_SET_KIND
    assert model.canonical_reference_id == CANONICAL_RESIDUE_MAPPING_REFERENCE_ID
    assert model.canonical_reference_id == "uniprotkb:O95436-1:sequence-v3"
    assert (
        model.canonical_reference_sequence_sha256
        == CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256
    )
    assert model.canonical_reference_sequence_sha256 == (
        "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
    )
    for item in fields(model)[1:]:
        assert not item.init
        with pytest.raises(TypeError):
            m.DatasetQCDecisionSet((), **{item.name: "override"})


@pytest.mark.parametrize("code", HARD_CODES + REVIEW_CODES)
def test_every_reason_has_exact_severity_and_accepts_only_that_check_status(code):
    expected = "fail" if code in HARD_CODES else "review"
    assert m.expected_qc_status(code) == expected
    check = finding(expected, reason_code=code)
    record = decision(expected, findings=(check,), decision_reason_code=code)
    assert record.release_decision == (
        "excluded" if expected == "fail" else "pending_review"
    )
    for status in {"pass", "review", "fail"} - {expected}:
        with pytest.raises(m.DatasetQCContractError):
            replace(check, status=status)


@pytest.mark.parametrize(
    "code",
    [None, "", "OTHER", "pass", "rmsd_drift_review", " RMSD_DRIFT_REVIEW ", 1, []],
)
def test_unknown_reason_codes_rejected(code):
    with pytest.raises(m.DatasetQCContractError):
        m.expected_qc_status(code)


@pytest.mark.parametrize(
    "factory, names",
    [
        (evidence, EVIDENCE_FIELDS),
        (finding, CHECK_FIELDS),
        (decision, DECISION_FIELDS),
        (
            lambda: m.DatasetQCDecisionSet(()),
            (
                "records",
                "schema_version",
                "kind",
                "canonical_reference_id",
                "canonical_reference_sequence_sha256",
            ),
        ),
    ],
)
def test_exact_field_order_frozen_models_and_deterministic_json(factory, names):
    model = factory()
    assert tuple(item.name for item in fields(model)) == names
    assert tuple(model.to_dict()) == names
    for name in names:
        with pytest.raises(FrozenInstanceError):
            setattr(model, name, None)
    with pytest.raises(FrozenInstanceError):
        delattr(model, names[0])
    assert encode(model) == encode(factory())
    assert json.loads(encode(model)) == model.to_dict()
    model.to_dict().clear()
    assert encode(model) == encode(factory())


@pytest.mark.parametrize(
    "kind, payload",
    [
        (
            "artifact",
            {"artifact_role": "required_table", "artifact_path": "tables/input.csv"},
        ),
        ("metric", {"metric_name": "coverage", "observed_value": "0"}),
        ("window", {"window_id": "w1", "metric_name": "edge_count"}),
        ("window", {"window_id": "w1", "observed_value": "0"}),
        ("window", {"window_id": "w1", "details": "Valid sparse window."}),
        ("mapping", {"artifact_role": "mapping", "artifact_path": "mapping.json"}),
        ("mapping", {"details": "Explicit supplied mapping observation."}),
        ("pbc", {"artifact_role": "pbc_audit", "artifact_path": "pbc_audit.json"}),
        ("pbc", {"observed_value": "broken"}),
        ("pbc", {"details": "Supplied PBC observation."}),
        ("manual_review", {"details": "Human review of supplied evidence."}),
    ],
)
def test_evidence_type_minimum_structure(kind, payload):
    model = bare_evidence(kind, **payload)
    assert model.evidence_type == kind
    for name, value in payload.items():
        assert getattr(model, name) == value


@pytest.mark.parametrize("kind", get_args(m.QCEvidenceType))
@pytest.mark.parametrize("payload", [{}, {"expected_or_threshold": "reference only"}])
def test_evidence_requires_meaningful_type_specific_payload(kind, payload):
    with pytest.raises(m.DatasetQCContractError, match="structured payload"):
        bare_evidence(kind, **payload)


@pytest.mark.parametrize(
    "kind, payload",
    [
        ("artifact", {"artifact_role": "table"}),
        ("artifact", {"artifact_path": "table.csv"}),
        ("artifact", {"details": "A description alone is insufficient."}),
        ("metric", {"metric_name": "coverage"}),
        ("metric", {"observed_value": "1.0"}),
        ("window", {"window_id": "w1"}),
        ("window", {"details": "Window identity missing."}),
        ("mapping", {"artifact_role": "mapping"}),
        ("mapping", {"artifact_path": "mapping.json"}),
        ("pbc", {"artifact_role": "pbc_audit"}),
        ("pbc", {"artifact_path": "pbc_audit.json"}),
        ("manual_review", {"observed_value": "cleared"}),
    ],
)
def test_incomplete_evidence_structures_rejected(kind, payload):
    with pytest.raises(m.DatasetQCContractError, match="structured payload"):
        bare_evidence(kind, **payload)


@pytest.mark.parametrize("name", ["evidence_id", *EVIDENCE_FIELDS[2:]])
@pytest.mark.parametrize("value", ["", " \t\n ", 0, False, [], {}])
def test_evidence_text_is_never_silently_invented_or_coerced(name, value):
    with pytest.raises(m.DatasetQCContractError, match="non-empty string"):
        evidence(**{name: value})


@pytest.mark.parametrize("value", ["other", "Artifact", " metric ", None, [], 1])
def test_evidence_type_is_exact(value):
    with pytest.raises(m.DatasetQCContractError, match="evidence_type"):
        evidence(evidence_type=value)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/evidence.csv",
        "/home/reviewer/evidence.csv",
        "//server/share/file.csv",
        "C:/Users/reviewer/file.csv",
        "C:file.csv",
        "C:\\Users\\reviewer\\file.csv",
        "tables\\file.csv",
        "../file.csv",
        "tables/../file.csv",
        "tables/..",
        "..",
        "~/file.csv",
        "~reviewer/file.csv",
        "tables/~/file.csv",
        "$HOME/file.csv",
        "${DATA_ROOT}/file.csv",
        "%USERPROFILE%/file.csv",
        "file:///tmp/file.csv",
        "https://example.invalid/file.csv",
        ".",
        "./file.csv",
        "tables/./file.csv",
        "tables//file.csv",
        "tables/",
        "tables/fi\x00le.csv",
        "tables/fi\nle.csv",
    ],
)
def test_artifact_paths_are_portable_without_traversal_or_environment_leakage(path):
    with pytest.raises(m.DatasetQCContractError, match="portable relative"):
        evidence(artifact_path=path)


@pytest.mark.parametrize("path", ["file.csv", "tables/file.csv", "run 1/a-b_v1.2.csv"])
def test_portable_paths_are_retained_without_filesystem_resolution(path):
    assert evidence(artifact_path=path).artifact_path == path


def test_strip_only_normalization_preserves_prose_case_and_optional_none():
    model = evidence(
        evidence_id=" e1 ",
        artifact_path=" tables/x.csv ",
        details="  Reviewed Case: A  B.\nSecond line.  ",
    )
    assert model.evidence_id == "e1"
    assert model.artifact_path == "tables/x.csv"
    assert model.details == "Reviewed Case: A  B.\nSecond line."
    assert model.artifact_role is None
    record = manual_decision(
        dataset_id=" Dataset A ",
        system_id=" System B ",
        trajectory_id=" T1 ",
        replica_id=" 1 ",
        reviewer=" verifier opaque ",
        decision_note=" Note  A. ",
        human_readable_reason=" Human  rationale. ",
        decision_evidence_ids=(" e1 ",),
        findings=(
            finding(
                "review", check_id=" check-1 ", human_readable_reason=" Check  A. "
            ),
        ),
    )
    assert record.replica_key == ("Dataset A", "System B", "T1", "1")
    assert record.reviewer == "verifier opaque"
    assert record.decision_note == "Note  A."
    assert record.human_readable_reason == "Human  rationale."
    assert record.findings[0].human_readable_reason == "Check  A."
    assert record.findings[0].check_id == "check-1"
    assert record.decision_evidence_ids == ("e1",)


@pytest.mark.parametrize("status", ["pass", "review", "fail"])
@pytest.mark.parametrize("value", [(), [], (None,), ("e1",)])
def test_every_check_including_pass_requires_typed_nonempty_evidence(status, value):
    with pytest.raises(m.DatasetQCContractError, match="evidence"):
        finding(status, evidence=value)


@pytest.mark.parametrize("value", [None, "", "  ", 1])
def test_check_id_required(value):
    with pytest.raises(m.DatasetQCContractError, match="check_id"):
        finding(check_id=value)


@pytest.mark.parametrize("value", ["PASS", " pass ", "pending_review", None, []])
def test_check_status_is_exact(value):
    with pytest.raises(m.DatasetQCContractError, match="status"):
        replace(finding(), status=value)


@pytest.mark.parametrize(
    "name, value",
    [
        ("reason_code", "RMSD_DRIFT_REVIEW"),
        ("reason_code", "OCCUPANCY_OUT_OF_RANGE"),
        ("human_readable_reason", "Looks fine"),
        ("human_readable_reason", ""),
    ],
)
def test_pass_check_forbids_reason_code_and_prose(name, value):
    with pytest.raises(m.DatasetQCContractError, match="PASS"):
        finding(**{name: value})


@pytest.mark.parametrize("status", ["review", "fail"])
@pytest.mark.parametrize(
    "name, value",
    [
        ("reason_code", None),
        ("reason_code", "UNKNOWN"),
        ("human_readable_reason", None),
        ("human_readable_reason", ""),
        ("human_readable_reason", "   "),
        ("human_readable_reason", 2),
    ],
)
def test_nonpass_check_requires_reason_and_prose(status, name, value):
    with pytest.raises(m.DatasetQCContractError):
        finding(status, **{name: value})


def test_duplicate_evidence_within_check_rejected_after_normalization():
    with pytest.raises(m.DatasetQCContractError, match="unique within a check"):
        finding(
            evidence=(evidence(), evidence(evidence_id=" e1 ", observed_value="0.9"))
        )


@pytest.mark.parametrize(
    "name", ["dataset_id", "system_id", "trajectory_id", "replica_id"]
)
@pytest.mark.parametrize("value", [None, "", " \t ", 1, []])
def test_full_replica_identity_fields_required(name, value):
    with pytest.raises(m.DatasetQCContractError, match=name):
        decision(**{name: value})


def test_replica_key_and_condition_absent_from_authority():
    record = decision()
    assert record.replica_key == ("napi2b-v1-test", "wt-norm", "traj-1", "1")
    assert "condition" not in DECISION_FIELDS
    assert not hasattr(record, "condition")
    assert "condition" not in record.to_dict()
    with pytest.raises(TypeError):
        decision(condition="NORM")


@pytest.mark.parametrize("findings", [(), [], (None,), (evidence(),)])
def test_decision_requires_nonempty_exact_findings(findings):
    with pytest.raises(m.DatasetQCContractError, match="findings"):
        decision(findings=findings)


def test_duplicate_check_ids_and_global_evidence_ids_rejected():
    with pytest.raises(m.DatasetQCContractError, match="check IDs must be unique"):
        decision(findings=(finding(), finding(evidence=(evidence(evidence_id="e2"),))))
    with pytest.raises(
        m.DatasetQCContractError, match="evidence IDs must be unique across"
    ):
        decision(findings=(finding(), finding(check_id="check-2")))


@pytest.mark.parametrize(
    "statuses",
    [
        ("pass",),
        ("review",),
        ("fail",),
        ("pass", "review"),
        ("review", "pass"),
        ("pass", "fail"),
        ("review", "fail"),
        ("fail", "review", "pass"),
    ],
)
def test_overall_status_uses_fail_then_review_then_pass_precedence(statuses):
    expected = (
        "fail" if "fail" in statuses else "review" if "review" in statuses else "pass"
    )
    checks = tuple(
        finding(status, check_id=f"c{i}", evidence=(evidence(evidence_id=f"e{i}"),))
        for i, status in enumerate(statuses)
    )
    selected = next(check for check in checks if check.status == expected)
    record = decision(
        expected,
        findings=checks,
        decision_evidence_ids=(
            () if expected == "pass" else (selected.evidence[0].evidence_id,)
        ),
    )
    assert record.qc_status == expected
    for other in {"pass", "review", "fail"} - {expected}:
        with pytest.raises(m.DatasetQCContractError, match="derived from findings"):
            replace(record, qc_status=other)


@pytest.mark.parametrize(
    "status, release, mode",
    product(
        ("pass", "review", "fail"),
        ("available", "pending_review", "excluded"),
        ("automatic", "manual"),
    ),
)
def test_complete_release_policy_matrix(status, release, mode):
    allowed = {
        ("pass", "available", "automatic"),
        ("fail", "excluded", "automatic"),
        ("review", "pending_review", "automatic"),
        ("review", "available", "manual"),
        ("review", "excluded", "manual"),
    }
    changes = {
        "release_decision": release,
        "decision_mode": mode,
        "reviewer": "verifier" if mode == "manual" else None,
        "decision_note": "Explicit resolution." if mode == "manual" else None,
    }
    if (status, release, mode) in allowed:
        assert decision(status, **changes).release_decision == release
    else:
        with pytest.raises(m.DatasetQCContractError):
            decision(status, **changes)


@pytest.mark.parametrize(
    "name, value",
    [
        ("qc_status", "PASS"),
        ("qc_status", None),
        ("qc_status", []),
        ("release_decision", "unavailable"),
        ("release_decision", " available "),
        ("release_decision", None),
        ("release_decision", []),
        ("decision_mode", "AUTO"),
        ("decision_mode", None),
        ("decision_mode", []),
    ],
)
def test_decision_literals_are_exact_and_unavailable_is_separate(name, value):
    with pytest.raises(m.DatasetQCContractError, match=name):
        decision(**{name: value})


@pytest.mark.parametrize(
    "name, value",
    [
        ("decision_reason_code", "RMSD_DRIFT_REVIEW"),
        ("human_readable_reason", "Clear."),
        ("decision_evidence_ids", ("e1",)),
        ("reviewer", "verifier"),
        ("decision_note", "Note."),
    ],
)
def test_pass_decision_has_exactly_empty_decision_provenance(name, value):
    with pytest.raises(m.DatasetQCContractError, match="PASS"):
        decision(**{name: value})


@pytest.mark.parametrize("status", ["review", "fail"])
@pytest.mark.parametrize("name", ["reviewer", "decision_note"])
@pytest.mark.parametrize("value", ["supplied", ""])
def test_automatic_decisions_forbid_manual_provenance(status, name, value):
    with pytest.raises(m.DatasetQCContractError, match="automatic decisions forbid"):
        decision(status, **{name: value})


@pytest.mark.parametrize("release", ["available", "excluded"])
@pytest.mark.parametrize(
    "missing, value",
    [
        ("reviewer", None),
        ("reviewer", ""),
        ("reviewer", "  "),
        ("reviewer", 1),
        ("decision_note", None),
        ("decision_note", ""),
        ("decision_note", "  "),
        ("decision_note", 1),
        ("decision_reason_code", None),
        ("human_readable_reason", None),
        ("human_readable_reason", ""),
        ("human_readable_reason", "  "),
        ("decision_evidence_ids", ()),
    ],
)
def test_anonymous_manual_exclusion_and_clearance_always_fail(release, missing, value):
    with pytest.raises(m.DatasetQCContractError):
        manual_decision(release, **{missing: value})


@pytest.mark.parametrize("status", ["review", "fail"])
@pytest.mark.parametrize(
    "name, value",
    [
        ("decision_reason_code", None),
        ("human_readable_reason", None),
        ("human_readable_reason", " "),
        ("decision_evidence_ids", ()),
    ],
)
def test_nonpass_automatic_decision_cannot_omit_provenance(status, name, value):
    with pytest.raises(m.DatasetQCContractError):
        decision(status, **{name: value})


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        ["e1"],
        (None,),
        ("",),
        (1,),
        ("missing",),
        ("e1", "missing"),
        ("e1", " e1 "),
    ],
)
def test_invalid_duplicate_and_unknown_decision_evidence_rejected(value):
    with pytest.raises(m.DatasetQCContractError):
        decision("review", decision_evidence_ids=value)


@pytest.mark.parametrize(
    "status, code",
    [
        ("fail", "OCCUPANCY_OUT_OF_RANGE"),
        ("fail", "RMSD_DRIFT_REVIEW"),
        ("review", "EDGE_COUNT_MAD_OUTLIER_REVIEW"),
        ("review", "TOPOLOGY_UNREADABLE"),
        ("review", "UNKNOWN"),
    ],
)
def test_decision_reason_must_be_present_in_finding_with_matching_status(status, code):
    with pytest.raises(m.DatasetQCContractError, match="reason"):
        decision(status, decision_reason_code=code)


@pytest.mark.parametrize(
    "status, unrelated",
    [
        ("fail", finding("fail", reason_code="OCCUPANCY_OUT_OF_RANGE")),
        ("fail", finding("review")),
        ("fail", finding()),
        ("review", finding("review", reason_code="EDGE_COUNT_MAD_OUTLIER_REVIEW")),
        ("review", finding()),
    ],
)
@pytest.mark.parametrize("ids", [("unrelated",), ("e1", "unrelated")])
def test_all_decision_evidence_must_belong_to_findings_carrying_selected_reason(
    status, unrelated, ids
):
    unrelated = replace(
        unrelated, check_id="unrelated", evidence=(evidence(evidence_id="unrelated"),)
    )
    with pytest.raises(m.DatasetQCContractError, match="carrying the decision reason"):
        decision(
            status, findings=(finding(status), unrelated), decision_evidence_ids=ids
        )


def test_decision_can_reference_multiple_findings_with_same_reason():
    checks = (
        finding("review"),
        finding(
            "review",
            check_id="check-2",
            evidence=(
                bare_evidence("manual_review", evidence_id="e2", details="Reviewed."),
            ),
        ),
    )
    record = manual_decision(findings=checks, decision_evidence_ids=("e1", "e2"))
    assert record.decision_evidence_ids == ("e1", "e2")


def test_mandatory_hard_fail_coverage_smoke_records_supplied_094_without_calculation():
    record = decision("fail")
    assert record.replica_key == ("napi2b-v1-test", "wt-norm", "traj-1", "1")
    assert (record.qc_status, record.release_decision, record.decision_mode) == (
        "fail",
        "excluded",
        "automatic",
    )
    assert record.decision_reason_code == "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT"
    check = record.findings[0]
    assert check.reason_code == record.decision_reason_code
    assert record.decision_evidence_ids == (check.evidence[0].evidence_id,)
    assert check.evidence[0].metric_name == "production_frame_coverage"
    assert check.evidence[0].observed_value == "0.94"
    assert check.evidence[0].expected_or_threshold == ">=0.95"


def test_mandatory_review_and_mad_zero_smokes():
    unresolved = decision("review")
    assert unresolved.release_decision == "pending_review"
    assert unresolved.decision_reason_code == "RMSD_DRIFT_REVIEW"
    assert manual_decision("available").release_decision == "available"
    assert manual_decision("excluded").release_decision == "excluded"
    code = "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW"
    mad_zero = replace(
        unresolved,
        findings=(finding("review", reason_code=code),),
        decision_reason_code=code,
    )
    assert mad_zero.release_decision == "pending_review"
    with pytest.raises(m.DatasetQCContractError):
        replace(mad_zero, release_decision="excluded")


def test_contract_does_not_interpret_metric_thresholds_or_prose_as_machine_identity():
    check = finding(evidence=(evidence(observed_value="0.94"),))
    assert decision(findings=(check,)).qc_status == "pass"
    record = decision("review", human_readable_reason="Fail and exclude immediately.")
    assert record.release_decision == "pending_review"
    assert evidence(observed_value="not evaluated").observed_value == "not evaluated"


@pytest.mark.parametrize(
    "factory", [m.DatasetQCDecisionSet, m.build_dataset_qc_decision_set]
)
def test_decision_set_sorts_full_identity_and_preserves_distinct_bare_replica_ids(
    factory,
):
    records = (
        decision(system_id="B"),
        decision(system_id="A", trajectory_id="traj-2"),
        decision(system_id="A", replica_id="2"),
        decision(system_id="A"),
        decision(dataset_id="A"),
    )
    original = tuple(record.replica_key for record in records)
    model = factory(records)
    assert tuple(record.replica_key for record in model.records) == tuple(
        sorted(original)
    )
    assert tuple(record.replica_key for record in records) == original
    assert len(model.records) == 5
    assert encode(model) == encode(factory(tuple(reversed(records))))
    assert factory(()).records == ()
    with pytest.raises(m.DatasetQCContractError, match="replica keys must be unique"):
        factory((decision(), decision(replica_id=" 1 ")))


@pytest.mark.parametrize("records", [[], [decision()], (None,), (finding(),)])
def test_decision_set_requires_exact_typed_tuple(records):
    with pytest.raises(m.DatasetQCContractError, match="records"):
        m.build_dataset_qc_decision_set(records)


def test_tuple_subclasses_are_not_accepted():
    class TupleSubclass(tuple):
        pass

    for factory, changes in (
        (finding, {"evidence": TupleSubclass((evidence(),))}),
        (decision, {"findings": TupleSubclass((finding(),))}),
        (decision, {"decision_evidence_ids": TupleSubclass(())}),
        (m.DatasetQCDecisionSet, {"records": TupleSubclass(())}),
    ):
        with pytest.raises(m.DatasetQCContractError):
            factory(**changes)


def test_builder_and_serialization_do_not_mutate_input_tuples_or_nested_evidence():
    items = (evidence(evidence_id=" e1 "),)
    checks = (finding("review", evidence=items),)
    record = manual_decision(findings=checks)
    records = (replace(record, system_id="B"), replace(record, system_id="A"))
    before = tuple(encode(item) for item in records)
    model = m.build_dataset_qc_decision_set(records)
    assert checks[0].evidence is items
    assert record.findings is checks
    exported = model.to_dict()
    exported["records"][0]["findings"][0]["evidence"][0]["details"] = "tampered"
    exported["records"][0]["decision_evidence_ids"].append("tampered")
    assert tuple(encode(item) for item in records) == before
    assert model.records[0].findings[0].evidence[0].details is None
    assert model.records[0].decision_evidence_ids == ("e1",)


def test_module_has_only_pure_contract_imports():
    tree = ast.parse(inspect.getsource(m))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"dataclasses", "typing", "mania.canonical_residue_mapping"}


def test_pure_smokes_without_filesystem_network_git_subprocess_clock_or_mdanalysis(
    monkeypatch,
):
    def blocked(*args, **kwargs):
        raise AssertionError("QC contract attempted external access")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "MDAnalysis",
            "socket",
            "subprocess",
            "time",
            "datetime",
            "git",
        }:
            return blocked()
        return original_import(name, *args, **kwargs)

    class NoClock:
        now = utcnow = today = blocked

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "__import__", guarded_import)
        guard.setattr(builtins, "open", blocked)
        guard.setattr(io, "open", blocked)
        for name in ("open", "stat", "resolve", "read_text", "read_bytes", "exists"):
            guard.setattr(Path, name, blocked)
        for name in (
            "open",
            "stat",
            "listdir",
            "scandir",
            "getenv",
            "getcwd",
            "system",
            "popen",
        ):
            guard.setattr(os, name, blocked)
        guard.setattr(os, "environ", {})
        guard.setattr(socket, "socket", blocked)
        guard.setattr(socket, "create_connection", blocked)
        for name in ("Popen", "run", "call", "check_call", "check_output"):
            guard.setattr(subprocess, name, blocked)
        for name in ("time", "time_ns", "monotonic", "perf_counter", "sleep"):
            guard.setattr(time, name, blocked)
        guard.setattr(datetime, "datetime", NoClock)
        guard.setattr(datetime, "date", NoClock)
        guard.setitem(sys.modules, "MDAnalysis", None)
        assert decision().release_decision == "available"
        test_mandatory_hard_fail_coverage_smoke_records_supplied_094_without_calculation()
        test_mandatory_review_and_mad_zero_smokes()
        for release in ("available", "excluded"):
            for name, value in (
                ("reviewer", None),
                ("decision_note", None),
                ("human_readable_reason", None),
                ("decision_evidence_ids", ()),
            ):
                test_anonymous_manual_exclusion_and_clearance_always_fail(
                    release, name, value
                )
        records = (decision(system_id="B"), decision(system_id="A"))
        model = m.build_dataset_qc_decision_set(records)
        assert len(model.records) == 2
        assert encode(model) == encode(m.build_dataset_qc_decision_set(records[::-1]))
