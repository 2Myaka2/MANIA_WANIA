"""Narrow CLI options, successful pending review, and phase-specific failures."""

import json
import sys

import pytest
from test_dataset_qc_manifest import make_qc_case
from test_dataset_qc_run import stable_software_identity as stable_software_identity

from mania.cli import build_parser, main
from mania.dataset_qc_run import (
    DERIVED_ROLE,
    OUTPUT_FILES,
    collect_dataset_qc_input_specs,
)


@pytest.mark.parametrize("pending", [False, True])
def test_cli_completed_summary_and_unified_scope(
    tmp_path, monkeypatch, capsys, pending
):
    manifest, path, _, _, _ = make_qc_case(
        tmp_path / "inputs",
        outcomes=("fail", "pending" if pending else "pass", "manual_excluded"),
    )
    output = tmp_path / "qc"
    monkeypatch.setattr(
        sys,
        "argv",
        ["mania", "dataset", "qc", "--manifest", str(path), "--output", str(output)],
    )
    main()
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["production_ready"] is not pending
    assert result["replica_count"] == 3
    assert result["fail_count"] == 1
    assert result["excluded_count"] == 2
    assert result["review_count"] == 1 + int(pending)
    assert result["pending_review_count"] == int(pending)
    assert (DERIVED_ROLE in result["outputs"]) is not pending
    argv = ["mania", "artifacts", "validate", str(output), "--scope", "dataset_qc"]
    for spec in collect_dataset_qc_input_specs(manifest, path):
        argv.extend(["--input-artifact-path", f"{spec.artifact_id}={spec.local_path}"])
    monkeypatch.setattr(sys, "argv", argv)
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed" and report["complete"]


@pytest.mark.parametrize(
    "phase,prefix",
    [
        ("manifest", "Dataset QC manifest failed:"),
        ("evidence", "Dataset QC evidence failed:"),
        ("hard", "Dataset hard QC failed:"),
        ("review", "Dataset review QC failed:"),
        ("decision", "Dataset QC decision failed:"),
        ("bridge", "Dataset QC aggregation bridge failed:"),
        ("write", "Dataset QC export write failed:"),
    ],
)
def test_cli_phase_errors_are_readable(tmp_path, monkeypatch, capsys, phase, prefix):
    manifest, path, _, _, _ = make_qc_case(tmp_path / "inputs")
    output = tmp_path / "qc"

    def fail(*args, **kwargs):
        raise ValueError("Synthetic phase failure")

    if phase == "manifest":
        path.write_text("{}")
    elif phase == "evidence":
        (path.parent / manifest.replicas[0].hard_qc_evidence_path).write_text("{}")
    elif phase == "write":
        output.mkdir()
        (output / next(iter(OUTPUT_FILES.values()))).write_text("existing")
    else:
        function = {
            "hard": "evaluate_replica_hard_qc",
            "review": "evaluate_dataset_review_qc",
            "decision": "build_replica_qc_decision",
            "bridge": "require_qc_coverage",
        }[phase]
        monkeypatch.setattr(f"mania.dataset_qc_workflow.{function}", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        ["mania", "dataset", "qc", "--manifest", str(path), "--output", str(output)],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith(prefix)
    assert "Traceback" not in captured.err and captured.out == ""


@pytest.mark.parametrize(
    "option",
    ["--coverage-threshold", "--mad-scale", "--rmsd-threshold", "--force-exclude"],
)
def test_no_scientific_overrides(option):
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["dataset", "qc", "--manifest", "qc.json", "--output", "qc", option, "1"]
        )
