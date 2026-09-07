"""Completed analysis runtime metadata is separate from scientific counts and roots."""

import hashlib
import json
from unittest.mock import Mock

import pytest
from test_analysis_artifact_inventory import write_custom_stage20_root
from test_analysis_run_provenance import END, IDENTITY, START
from test_cli_analysis_run_provenance import invoke
from test_runtime_metadata import environment

import mania.cli as cli
from mania.analysis.artifact_inventory import collect_analysis_input_file_specs
from mania.analysis.orchestration import AnalyzeError, AnalyzeRequest
from mania.runtime_metadata_io import RuntimeMetadataWriteResult, read_runtime_metadata
from mania.validation import validate_run_artifacts


@pytest.fixture
def execution(monkeypatch, tmp_path):
    request = AnalyzeRequest(tmp_path, tmp_path, ("tumor", "normal"))
    write_custom_stage20_root(tmp_path, request.conditions)
    sentinels = {
        tmp_path / f"{name}.json": f"preprocessing {name}".encode()
        for name in (
            "runtime_metadata",
            "pbc_audit",
            "artifact_inventory",
            "run_provenance",
        )
    }
    for path, content in sentinels.items():
        path.write_bytes(content)
    spies = {}
    for name in (
        "run_analysis",
        "build_runtime_metadata",
        "build_runtime_performance",
        "write_runtime_metadata",
        "build_analysis_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_analysis_run_provenance",
        "build_failed_analysis_run_provenance",
        "write_run_provenance",
    ):
        spies[name] = Mock(wraps=getattr(cli, name))
        monkeypatch.setattr(cli, name, spies[name])
    spies["clock"] = Mock(side_effect=[START, END])
    spies["identity"] = Mock(return_value=IDENTITY)
    spies["environment"] = Mock(return_value=environment())
    monkeypatch.setattr(cli, "_utc_now", spies["clock"])
    monkeypatch.setattr(cli, "get_software_identity", spies["identity"])
    monkeypatch.setattr(cli, "collect_runtime_environment", spies["environment"])
    return request, spies, sentinels


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_completed_analysis_runtime_inventory_provenance_and_validation(
    monkeypatch,
    capsys,
    execution,
    mode,
):
    request, spies, sentinels = execution
    events = Mock()
    for name, spy in spies.items():
        events.attach_mock(spy, name)
    captured = invoke(
        monkeypatch, capsys, request, options=("--artifact-checksum-mode", mode)
    )
    assert captured.err == ""
    root = request.output_root
    path = root / "analysis/runtime_metadata.json"
    model = read_runtime_metadata(path)
    assert (
        model.scope == "analysis"
        and model.metadata_path == "analysis/runtime_metadata.json"
    )
    assert model.workflow == "analysis" and model.environment == environment()
    assert model.performance.to_dict() == dict(
        wall_clock_seconds=(END - START).total_seconds(),
        condition_count=2,
        sampled_frame_count=None,
        seconds_per_sampled_frame=None,
        contact_frame_count=None,
        contact_observation_count=None,
    )
    assert (
        model.run_id
        == spies["build_completed_analysis_run_provenance"].call_args.kwargs["run_id"]
    )
    assert spies["clock"].call_count == 2
    for name in (
        "environment",
        "identity",
        "build_runtime_metadata",
        "build_runtime_performance",
        "write_runtime_metadata",
    ):
        spies[name].assert_called_once()
    assert [call[0] for call in events.mock_calls] == [
        "clock",
        "identity",
        "run_analysis",
        "clock",
        "environment",
        "build_runtime_performance",
        "build_runtime_metadata",
        "write_runtime_metadata",
        "build_analysis_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_analysis_run_provenance",
        "write_run_provenance",
    ]
    assert spies["write_runtime_metadata"].call_args.args[1] == root
    assert spies["write_runtime_metadata"].call_args.kwargs == {"overwrite": True}
    kwargs = spies["build_analysis_artifact_inventory"].call_args.kwargs
    assert kwargs["runtime_metadata_path"] == path
    result = kwargs["result"]
    assert captured.out == json.dumps(result.to_summary(), sort_keys=True) + "\n"
    assert json.loads(captured.out)["artifacts"]["count"] == 17
    assert "runtime_metadata" not in captured.out
    inventory = json.loads((root / "analysis/artifact_inventory.json").read_text())
    entry = inventory["artifacts"][-1]
    assert entry["artifact_id"] == "output:runtime_metadata"
    assert entry["role"] == "runtime_metadata"
    assert entry["path"] == "analysis/runtime_metadata.json"
    assert entry["condition"] is None and entry["format"] == "json"
    assert entry["byte_size"] == len(path.read_bytes())
    assert entry["sha256"] == (
        hashlib.sha256(path.read_bytes()).hexdigest() if mode == "sha256" else None
    )
    refs = json.loads((root / "analysis/run_provenance.json").read_text())[
        "artifact_references"
    ]
    assert refs[-2:] == [
        {"role": "runtime_metadata", "path": "analysis/runtime_metadata.json"},
        {"role": "artifact_inventory", "path": "analysis/artifact_inventory.json"},
    ]
    specs = collect_analysis_input_file_specs(
        request=request,
        resolved_input_paths=kwargs["resolved_input_paths"],
    )
    report = validate_run_artifacts(
        root,
        scope="analysis",
        input_artifact_paths={spec.artifact_id: spec.local_path for spec in specs},
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    assert [
        (r.validator, r.status)
        for r in report.specialized_records
        if r.role == "runtime_metadata"
    ] == [("read_runtime_metadata", "passed")]
    assert validate_run_artifacts(root, scope="analysis").status == "partial"
    assert not (root / "analysis/pbc_audit.json").exists()
    assert all(path.read_bytes() == content for path, content in sentinels.items())


@pytest.mark.parametrize(
    "failure",
    [
        "environment",
        "build_runtime_performance",
        "build_runtime_metadata",
        "write_runtime_metadata",
        "write_result",
    ],
)
def test_runtime_failure_keeps_science_and_best_effort_metadata(
    monkeypatch,
    capsys,
    execution,
    failure,
):
    request, spies, sentinels = execution
    if failure == "write_result":
        spies["write_runtime_metadata"].side_effect = None
        spies["write_runtime_metadata"].return_value = RuntimeMetadataWriteResult(
            request.output_root / "analysis/runtime_metadata.json",
            False,
            "Filesystem write failed.",
        )
    else:
        spies[failure].side_effect = RuntimeError("private details")
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    stage = "write" if failure.startswith("write") else "build"
    assert captured.err.startswith(f"Analysis runtime metadata {stage} failed:")
    assert "private" not in captured.err
    for name in (
        "build_analysis_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_analysis_run_provenance",
        "write_run_provenance",
    ):
        spies[name].assert_called_once()
    kwargs = spies["build_analysis_artifact_inventory"].call_args.kwargs
    assert "runtime_metadata_path" not in kwargs
    assert all(path.exists() for path in kwargs["result"].current_run_artifacts)
    root = request.output_root / "analysis"
    assert not (root / "runtime_metadata.json").exists()
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    provenance = json.loads((root / "run_provenance.json").read_text())
    assert provenance["status"] == "completed"
    assert all(e["role"] != "runtime_metadata" for e in inventory["artifacts"])
    assert all(
        r["role"] != "runtime_metadata" for r in provenance["artifact_references"]
    )
    assert provenance["artifact_references"][-1]["role"] == "artifact_inventory"
    assert all(path.read_bytes() == content for path, content in sentinels.items())


def test_failed_analysis_retains_existing_input_only_boundary(
    monkeypatch, capsys, execution
):
    request, spies, sentinels = execution
    spies["run_analysis"].side_effect = AnalyzeError("synthetic scientific failure")
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == "Analyze failed: synthetic scientific failure\n"
    for name in (
        "environment",
        "build_runtime_metadata",
        "build_runtime_performance",
        "write_runtime_metadata",
    ):
        spies[name].assert_not_called()
    spies["build_failed_analysis_run_provenance"].assert_called_once()
    inventory = json.loads(
        (request.output_root / "analysis/artifact_inventory.json").read_text()
    )
    assert inventory["output_artifact_count"] == 0
    assert not (request.output_root / "analysis/runtime_metadata.json").exists()
    assert all(path.read_bytes() == content for path, content in sentinels.items())


def test_runtime_error_precedes_later_inventory_and_provenance_errors(
    monkeypatch,
    capsys,
    execution,
):
    request, spies, _ = execution
    for name in (
        "build_runtime_metadata",
        "write_artifact_inventory",
        "write_run_provenance",
    ):
        spies[name].side_effect = RuntimeError("private details")
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert [line.split(":", 1)[0] for line in captured.err.splitlines()] == [
        "Analysis runtime metadata build failed",
        "Analysis artifact inventory write failed",
        "Analysis run provenance write failed",
    ]
    builder = spies["build_completed_analysis_run_provenance"]
    builder.assert_called_once()
    assert builder.call_args.kwargs["additional_artifact_references"] == ()
