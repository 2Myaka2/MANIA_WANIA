"""Synthetic freeze/QC authority gates; never fabricate review clearance."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_dataset_hard_qc import inputs

pytest.importorskip("MDAnalysis")
spec = importlib.util.spec_from_file_location(
    "stage34b5_smoke",
    Path(__file__).parents[1] / "tools/stage34b5_single_replica_release_smoke.py",
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize("status", ["BLOCKED", "FAIL", "NOT RUN"])
def test_b4_failure_gates_every_downstream_step(status):
    with pytest.raises(ValueError, match="B.4 must completely PASS"):
        smoke.require_b4_pass({"stage34b4_status": status})


def test_b4_partial_technical_validation_blocks():
    with pytest.raises(ValueError, match="incomplete"):
        smoke.require_b4_pass(
            {
                "stage34b4_status": "PASS",
                "independent": {"status": "PASS"},
                "technical": {"status": "passed", "complete": False},
            }
        )


def test_freeze_detects_changed_science_before_copy(tmp_path):
    source, target = tmp_path / "source.csv", tmp_path / "frozen.csv"
    source.write_text("accepted science")
    expected = smoke.file_record(source)["sha256"]
    source.write_text("changed science")
    with pytest.raises(ValueError, match="binding changed"):
        smoke.freeze_file(source, target, expected)
    assert not target.exists()


def test_strict_real_adapter_and_pending_decision_have_no_clearance(tmp_path):
    value = smoke.ReplicaHardQCEvidence(**inputs())
    hard = smoke.hard_findings(value, tmp_path / "evidence.json")
    assert hard.hard_qc_status == "pass"
    pending = smoke.pending_decision(hard)
    assert pending["status"] == "pending_review"
    assert pending["authoritative_release_decision"] is None
    assert pending["reviewer"] is None and pending["production_ready"] is False
    assert not list(tmp_path.glob("*manifest*"))


def test_hard_exclusion_cannot_be_replaced_with_pending():
    hard = SimpleNamespace(hard_qc_status="fail")
    with pytest.raises(ValueError, match="hard exclusion"):
        smoke.pending_decision(hard)


@pytest.mark.parametrize("rows,triggered", [((), True), (("window_0001",), False)])
def test_empty_window_rule_and_singleton_mad_do_not_supply_rmsd(rows, triggered):
    value = smoke.ReplicaHardQCEvidence(**inputs())
    protein = SimpleNamespace(rows=tuple(SimpleNamespace(window_id=w) for w in rows))
    temporal = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                window_plan=SimpleNamespace(
                    windows=(SimpleNamespace(window_id="window_0001"),)
                )
            ),
        )
    )
    records = {"protein_edge": {"frozen_path": "frozen/protein.csv", "sha256": "test"}}
    result = smoke.partial_review_observations(
        value.identity, protein, temporal, records
    )
    assert result["empty_window_rule_triggered"] is triggered
    assert result["rmsd_drift"] is None
    assert result["complete_stage32c_evaluation"] == "NOT RUN"
    check = result["accepted_partial_mad_finding"]
    assert check["status"] == "pass"
    metrics = {e["metric_name"]: e["observed_value"] for e in check["evidence"]}
    assert metrics["comparison"] == "not_applicable_single_replica"
    assert metrics["mad"] == "0"
    assert result["partial_findings_authorize_release"] is False


def test_gate_failure_does_not_evaluate_qc(tmp_path, monkeypatch):
    monkeypatch.setattr(
        smoke, "freeze_inputs", Mock(side_effect=ValueError("B.4 failed"))
    )
    forbidden = Mock(side_effect=AssertionError("QC must not execute"))
    monkeypatch.setattr(smoke, "build_hard_evidence", forbidden)
    with pytest.raises(ValueError, match="B.4 failed"):
        smoke.run(tmp_path)
    forbidden.assert_not_called()
