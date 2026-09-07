"""Completed preprocessing emits E.2 artifacts without changing scientific execution."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_artifact_inventory import (
    command,
    install_inventory_workflow,
)
from test_cli_preprocessing_graph_workflow import (
    END,
    STAGE15_ORDER,
    START,
    VERBOSE_STAGE_MESSAGES,
    install_fake_stage15,
    invoke_cli,
)
from test_preprocessing_artifact_inventory import make_runtime
from test_preprocessing_pbc_audit import BOX
from test_preprocessing_pbc_observation_integration import Runtime
from test_runtime_metadata import environment

import mania.cli as cli
from mania.preprocessing.pbc_audit_io import PbcAuditWriteResult, read_pbc_audit
from mania.runtime_metadata_io import RuntimeMetadataWriteResult, read_runtime_metadata
from mania.validation import validate_run_artifacts

TECHNICAL_ROLES = ("runtime_metadata", "pbc_audit", "artifact_inventory")


def install_smoke(monkeypatch, root, boxes):
    source = make_runtime(root)
    runtimes = [Runtime(boxes) for _ in source.condition_names]
    conditions = tuple(
        replace(item, runtime=replace(item.runtime, runtime_object=runtime))
        for item, runtime in zip(
            source.runtime_load_result.condition_results, runtimes, strict=True
        )
    )
    source = replace(
        source,
        runtime_load_result=replace(
            source.runtime_load_result,
            condition_results=conditions,
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_preprocessing_graph_workflow_condition_runtimes",
        Mock(return_value=source),
    )
    spies = {}
    for name in (
        "compute_preprocessing_graph_workflow_rg_contacts",
        "build_preprocessing_runtime_metadata",
        "write_runtime_metadata",
        "build_pbc_audit",
        "write_pbc_audit",
        "build_preprocessing_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_preprocessing_run_provenance",
        "write_run_provenance",
    ):
        spies[name] = Mock(wraps=getattr(cli, name))
        monkeypatch.setattr(cli, name, spies[name])
    spies["clock"] = Mock(side_effect=[START, END])
    spies["environment"] = Mock(return_value=environment())
    spies["identity"] = Mock(wraps=cli.get_software_identity)
    monkeypatch.setattr(cli, "_utc_now", spies["clock"])
    monkeypatch.setattr(cli, "collect_runtime_environment", spies["environment"])
    monkeypatch.setattr(cli, "get_software_identity", spies["identity"])
    return source, runtimes, spies


def smoke_command(root, *extra):
    return command(
        root,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--export-contacts-perframe",
        "--frame-start",
        "1",
        "--frame-stop",
        "7",
        "--frame-stride",
        "2",
        "--max-frames",
        "3",
        *extra,
    )


@pytest.mark.parametrize("mode", ["none", "sha256"])
@pytest.mark.parametrize("box_kind", ["missing", "varying"])
def test_real_completed_smoke_and_complete_technical_validation(
    monkeypatch,
    capsys,
    tmp_path,
    mode,
    box_kind,
):
    boxes = [None] * 8 if box_kind == "missing" else [BOX] * 8
    if box_kind == "varying":
        boxes[3] = (12, 18, 35, 85, 100, 95)
        boxes[5] = (11, 22, 25, 95, 80, 100)
        boxes[0] = (999, 999, 999, 99, 99, 99)
    source, runtimes, spies = install_smoke(monkeypatch, tmp_path, boxes)
    events = Mock()
    for name, spy in spies.items():
        events.attach_mock(spy, name)
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *smoke_command(
            tmp_path,
            "--artifact-checksum-mode",
            mode,
        ),
    )
    assert stderr == "" and json.loads(stdout)["passed"] is True
    root = tmp_path / "out"
    for name in TECHNICAL_ROLES + ("run_provenance",):
        assert (root / f"{name}.json").is_file()
    metadata = read_runtime_metadata(root / "runtime_metadata.json")
    assert metadata.run_id == "inventory-test"
    assert metadata.workflow == "preprocessing_graph_export"
    assert metadata.scope == "preprocessing" and metadata.environment == environment()
    assert metadata.performance.wall_clock_seconds == (END - START).total_seconds()
    assert metadata.performance.sampled_frame_count == 6
    assert metadata.performance.contact_frame_count == 6
    audit = read_pbc_audit(root / "pbc_audit.json")
    assert audit.mania_internal_minimum_image_correction_applied is False
    assert audit.external_pbc_preprocessing_status == "undeclared"
    assert audit.scientific_pbc_status == "unresolved"
    assert tuple(c.condition for c in audit.conditions) == source.condition_names
    for condition in audit.conditions:
        assert condition.sampled_frame_count == 3
        assert condition.metadata_status == (
            "unavailable" if box_kind == "missing" else "complete"
        )
        if box_kind == "varying":
            assert condition.box_varies is True
            assert condition.box_lengths_min_A == (10, 18, 25)
            assert condition.box_lengths_max_A == (12, 22, 35)
    for runtime in runtimes:
        assert runtime.trajectory.passes == 2
        assert runtime.trajectory.observed == [(1, i) for i in (1, 3, 5)]
    for key, spy in spies.items():
        if key == "clock":
            assert spy.call_count == 2
        else:
            spy.assert_called_once()
    computation_call = spies[
        "compute_preprocessing_graph_workflow_rg_contacts"
    ].call_args
    assert [call[0] for call in events.mock_calls] == [
        "clock",
        "identity",
        "compute_preprocessing_graph_workflow_rg_contacts",
        "clock",
        "environment",
        "build_preprocessing_runtime_metadata",
        "write_runtime_metadata",
        "build_pbc_audit",
        "write_pbc_audit",
        "build_preprocessing_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_preprocessing_run_provenance",
        "write_run_provenance",
    ]
    assert computation_call.kwargs["collect_pbc_observations"] is True
    assert computation_call.args[0] is source
    retained = spies["build_preprocessing_runtime_metadata"].call_args.kwargs[
        "computation"
    ]
    assert (
        metadata.performance.contact_observation_count
        == retained.contacts_result.contact_count
    )
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    entries = inventory["artifacts"]
    assert [entry["role"] for entry in entries[-2:]] == list(TECHNICAL_ROLES[:2])
    for entry in entries[-2:]:
        content = (root / entry["path"]).read_bytes()
        assert entry["byte_size"] == len(content)
        assert entry["sha256"] == (
            hashlib.sha256(content).hexdigest() if mode == "sha256" else None
        )
    assert all(
        e["role"] not in ("artifact_inventory", "run_provenance") for e in entries
    )
    refs = json.loads((root / "run_provenance.json").read_text())["artifact_references"]
    assert [r["role"] for r in refs[-3:]] == list(TECHNICAL_ROLES)
    assert all(not Path(r["path"]).is_absolute() for r in refs)
    specs = spies["build_preprocessing_artifact_inventory"].call_args.kwargs
    assert specs["runtime_metadata_path"] == root / "runtime_metadata.json"
    assert specs["pbc_audit_path"] == root / "pbc_audit.json"
    from mania.preprocessing.artifact_inventory import (
        collect_preprocessing_input_file_specs,
    )

    mappings = {
        s.artifact_id: s.local_path
        for s in collect_preprocessing_input_file_specs(source)
    }
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    assert all(
        r.status == "passed"
        for r in report.specialized_records
        if r.role in TECHNICAL_ROLES[:2]
    )
    partial = validate_run_artifacts(root, scope="preprocessing")
    assert partial.status == "partial" and partial.passed and not partial.complete


def test_stdout_verbose_stage_order_and_existing_arguments(
    monkeypatch, capsys, tmp_path
):
    calls, received = install_fake_stage15(monkeypatch)
    _, stdout, stderr = invoke_cli(monkeypatch, capsys, *command(tmp_path, "--verbose"))
    assert tuple(calls) == STAGE15_ORDER
    assert [line for line in stderr.splitlines() if "/7]" in line] == [
        f"{message}..." for message in VERBOSE_STAGE_MESSAGES
    ]
    assert received["collect_pbc_observations"] is True
    assert received["include_rg"] is True and received["include_contacts"] is True
    assert received["clock"].call_count == 2
    received["identity"].assert_called_once_with()
    for name in (
        "environment",
        "runtime_builder",
        "runtime_writer",
        "pbc_builder",
        "pbc_writer",
    ):
        received[name].assert_called_once()
    assert not any(role in stdout for role in TECHNICAL_ROLES)
    # The scientific summary itself is produced by the accepted helper unchanged.
    _, _ = install_fake_stage15(monkeypatch)
    _, baseline_stdout, baseline_stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path, "--verbose"),
    )
    assert stdout == baseline_stdout and stderr == baseline_stderr


@pytest.mark.parametrize(
    "failure,prefix,missing",
    [
        ("environment", "Runtime metadata build failed:", "runtime_metadata"),
        ("runtime_builder", "Runtime metadata build failed:", "runtime_metadata"),
        ("runtime_writer", "Runtime metadata write failed:", "runtime_metadata"),
        ("pbc_builder", "PBC audit build failed:", "pbc_audit"),
        ("pbc_writer", "PBC audit write failed:", "pbc_audit"),
    ],
)
@pytest.mark.parametrize("writer_result", [False, True])
def test_metadata_failure_preserves_science_and_attempts_inventory_provenance(
    monkeypatch,
    capsys,
    tmp_path,
    failure,
    prefix,
    missing,
    writer_result,
):
    _, received = install_inventory_workflow(monkeypatch, tmp_path)
    if writer_result and failure in ("runtime_writer", "pbc_writer"):
        model = (
            RuntimeMetadataWriteResult
            if failure == "runtime_writer"
            else PbcAuditWriteResult
        )
        received[failure].side_effect = None
        received[failure].return_value = model(
            tmp_path / "out" / f"{missing}.json",
            False,
            "Filesystem write failed.",
        )
    else:
        received[failure].side_effect = RuntimeError("private path")
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert stdout == "" and stderr.startswith(prefix)
    assert "private" not in stderr
    received["inventory_builder"].assert_called_once()
    received["inventory_writer"].assert_called_once()
    received["provenance_builder"].assert_called_once()
    received["provenance_writer"].assert_called_once()
    root = tmp_path / "out"
    assert (root / "graph/nodes.csv").read_bytes() == b"synthetic\n"
    assert not (root / f"{missing}.json").exists()
    entries = json.loads((root / "artifact_inventory.json").read_text())["artifacts"]
    provenance = json.loads((root / "run_provenance.json").read_text())
    refs = provenance["artifact_references"]
    assert provenance["status"] == "completed"
    assert missing not in [r["role"] for r in refs]
    assert missing not in [e["role"] for e in entries]
    successful = "pbc_audit" if missing == "runtime_metadata" else "runtime_metadata"
    assert successful in [r["role"] for r in refs]
    assert successful in [e["role"] for e in entries]


def test_scientific_failure_never_emits_e2_metadata(monkeypatch, capsys, tmp_path):
    _, received = install_inventory_workflow(
        monkeypatch, tmp_path, failure="computation"
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == "computation"
    assert "Runtime metadata" not in stderr and "PBC audit" not in stderr
    for key in (
        "environment",
        "runtime_builder",
        "runtime_writer",
        "pbc_builder",
        "pbc_writer",
    ):
        received[key].assert_not_called()
    received["failed_provenance_builder"].assert_called_once()
    assert not (tmp_path / "out/runtime_metadata.json").exists()
    assert not (tmp_path / "out/pbc_audit.json").exists()


def test_metadata_errors_precede_best_effort_inventory_and_provenance_errors(
    monkeypatch,
    capsys,
    tmp_path,
):
    _, received = install_inventory_workflow(monkeypatch, tmp_path)
    for name in (
        "runtime_builder",
        "pbc_writer",
        "inventory_builder",
        "provenance_writer",
    ):
        received[name].side_effect = RuntimeError("private details")
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path),
        expected_exit_code=1,
    )
    assert stdout == ""
    assert [line.split(":", 1)[0] for line in stderr.splitlines()] == [
        "Runtime metadata build failed",
        "PBC audit write failed",
        "Artifact inventory build failed",
        "Run provenance write failed",
    ]
    received["provenance_builder"].assert_called_once()
    refs = received["provenance_builder"].call_args.kwargs["artifact_references"]
    assert not any(ref.role in TECHNICAL_ROLES for ref in refs)
