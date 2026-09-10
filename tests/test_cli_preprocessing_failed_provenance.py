"""Failed workflow emission preserves scientific failures and observes no new data."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_graph_workflow import (
    END,
    FIXED_IDENTITY,
    START,
    install_fake_stage15,
    invoke_cli,
)
from test_preprocessing_run_provenance import (
    computation as make_computation,
)
from test_preprocessing_run_provenance import contact_source, rg_source

import mania.cli as cli
from mania.preprocessing.run_provenance import (
    PREPROCESSING_RUN_FAILURE_STAGES,
    build_failed_preprocessing_run_provenance,
)
from mania.preprocessing.trajectory_frame_sampling import (
    PreprocessingFrameSamplingOptions,
)
from mania.run_provenance_io import RunProvenanceWriteResult, write_run_provenance

GRAPH_ROLES = ("graph_nodes", "graph_edges", "graph_json")
BEFORE_FAILURE_ROLES = {
    "plan": (),
    "runtime_loading": (),
    "computation": (),
    "graph_export": (),
    "analysis_input_export": GRAPH_ROLES,
    "scientific_csv_export": (*GRAPH_ROLES, "preprocessing_manifest"),
    "diagnostics": (
        *GRAPH_ROLES,
        "preprocessing_manifest",
        "rg_timeseries",
        "contact_edges",
        "contacts_perframe",
    ),
    "reference_comparison": (
        *GRAPH_ROLES,
        "preprocessing_manifest",
        "rg_timeseries",
        "contact_edges",
        "contacts_perframe",
        "graph_diagnostics_report",
    ),
}


def install_failure(monkeypatch, tmp_path, stage, *, real_writer=False):
    calls, received = install_fake_stage15(monkeypatch, failing_stage=stage)
    sampling = PreprocessingFrameSamplingOptions(2, 9, 3, 2)
    computation = make_computation(
        contacts=contact_source(((2, 2.0), (5, 5.0))),
        rg=rg_source(((2, 2.0), (5, 5.0))),
        options=sampling,
        source_count=None if stage == "computation" else 10,
    )
    fake_compute = cli.compute_preprocessing_graph_workflow_rg_contacts

    def compute(*args, **kwargs):
        fake_compute(*args, **kwargs)
        return computation

    monkeypatch.setattr(
        cli, "compute_preprocessing_graph_workflow_rg_contacts", compute
    )
    builder = Mock(wraps=build_failed_preprocessing_run_provenance)
    received["failed_provenance_builder"] = builder
    monkeypatch.setattr(cli, "build_failed_preprocessing_run_provenance", builder)
    if real_writer:
        received["provenance_writer"] = Mock(wraps=write_run_provenance)
        monkeypatch.setattr(cli, "write_run_provenance", received["provenance_writer"])
    received["retained_computation"] = computation
    return calls, received


def command(tmp_path, *extra):
    return (
        "preprocessing",
        "run-graph-export",
        "--manifest",
        str(tmp_path / "manifest.yaml"),
        "--output",
        str(tmp_path / "output"),
        "--run-name",
        "failed-test",
        "--expected-condition",
        "expected-b",
        "--expected-condition",
        "expected-a",
        "--frame-start",
        "2",
        "--frame-stop",
        "9",
        "--frame-stride",
        "3",
        "--max-frames",
        "2",
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--export-contacts-perframe",
        "--enable-reference-comparison",
        *extra,
    )


# Dataset-only Stage 28 failure coverage lives in the source-export integration suite.
@pytest.mark.parametrize("stage", PREPROCESSING_RUN_FAILURE_STAGES[:-1])
@pytest.mark.parametrize("verbose", [False, True])
def test_each_failure_emits_once_with_preserved_output(
    monkeypatch, capsys, tmp_path, stage, verbose
):
    extra = ("--verbose",) if verbose else ()
    calls, received = install_failure(monkeypatch, tmp_path, stage)
    # Save the exact existing scientific summaries before swapping only provenance.
    clock = received["clock"]
    writer = received["provenance_writer"]
    builder = received["failed_provenance_builder"]
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path, *extra), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == stage and not json.loads(stdout)["passed"]
    builder.assert_called_once()
    writer.assert_called_once()
    received["identity"].assert_called_once_with()
    assert clock.call_count == 2
    supplied = builder.call_args.kwargs
    assert supplied["failure_stage"] == stage and supplied["run_id"] == "failed-test"
    assert supplied["started_at_utc"] == START <= supplied["ended_at_utc"] == END
    assert supplied["software_identity"] is FIXED_IDENTITY
    assert supplied["frame_sampling"] == PreprocessingFrameSamplingOptions(2, 9, 3, 2)
    payload = writer.call_args.args[0]
    assert payload.status == "failed" and payload.issues[0].stage == stage
    assert writer.call_args.args[1] == tmp_path / "output"
    assert writer.call_args.kwargs == {"overwrite": False}
    assert (
        tuple(ref.role for ref in payload.artifact_references)
        == BEFORE_FAILURE_ROLES[stage]
    )
    assert all(
        set(ref.to_dict()) == {"role", "path"} for ref in payload.artifact_references
    )
    if stage in ("plan", "runtime_loading"):
        assert supplied["computation"] is None
        assert payload.conditions == ("expected-b", "expected-a")
        assert all(item.effective is None for item in payload.sampling_by_condition)
        assert "compute_preprocessing_graph_workflow_rg_contacts" not in calls
    else:
        assert supplied["computation"] is received["retained_computation"]
        assert payload.conditions == ("sample",)
        assert payload.sampling_by_condition[0].effective.sampled_frame_count == 2
        assert calls.count("compute_preprocessing_graph_workflow_rg_contacts") == 1
    # Repeat identical mocked scientific failure with no-op provenance collaborators.
    install_failure(monkeypatch, tmp_path, stage)
    monkeypatch.setattr(
        cli, "build_failed_preprocessing_run_provenance", Mock(return_value=payload)
    )
    _, baseline_stdout, baseline_stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path, *extra), expected_exit_code=1
    )
    assert stdout == baseline_stdout and stderr == baseline_stderr
    assert "provenance" not in stderr.lower()
    assert "Writing final summary" in stderr if verbose else "[1/" not in stderr


@pytest.mark.parametrize("with_computation", [False, True])
def test_conditions_prefer_computation_then_loading(
    monkeypatch, capsys, tmp_path, with_computation
):
    stage = "graph_export" if with_computation else "runtime_loading"
    _, received = install_failure(monkeypatch, tmp_path, stage)
    fake_load = cli.load_preprocessing_graph_workflow_condition_runtimes

    def load(*args, **kwargs):
        result = fake_load(*args, **kwargs)
        return SimpleNamespace(
            condition_names=("loaded-b", "loaded-a"),
            passed=result.passed,
            to_dict=result.to_dict,
        )

    monkeypatch.setattr(
        cli, "load_preprocessing_graph_workflow_condition_runtimes", load
    )
    invoke_cli(monkeypatch, capsys, *command(tmp_path), expected_exit_code=1)
    assert received["failed_provenance_builder"].call_args.kwargs["conditions"] == (
        ("sample",) if with_computation else ("loaded-b", "loaded-a")
    )


@pytest.mark.parametrize("conditions", [("repeat", "repeat"), ["list"], ("bad ",)])
def test_invalid_known_conditions_are_not_silently_repaired(
    monkeypatch, capsys, tmp_path, conditions
):
    _, received = install_failure(monkeypatch, tmp_path, "runtime_loading")
    monkeypatch.setattr(
        cli,
        "load_preprocessing_graph_workflow_condition_runtimes",
        lambda *a, **k: SimpleNamespace(
            condition_names=conditions, passed=False, to_dict=lambda: {"passed": False}
        ),
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == "runtime_loading"
    assert (
        stderr
        == "Failed-run provenance build failed: Failed run metadata is invalid.\n"
    )
    assert (
        received["failed_provenance_builder"].call_args.kwargs["conditions"]
        is conditions
    )
    received["provenance_writer"].assert_not_called()


@pytest.mark.parametrize("stage", ["plan", "computation", "reference_comparison"])
def test_real_failed_builder_and_writer(monkeypatch, capsys, tmp_path, stage):
    _, received = install_failure(monkeypatch, tmp_path, stage, real_writer=True)
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == stage and stderr == ""
    root = tmp_path / "output"
    target = root / "run_provenance.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["status"] == "failed" and payload["run_id"] == "failed-test"
    assert payload["issues"][0] == {
        "severity": "error",
        "code": "preprocessing_stage_failed",
        "stage": stage,
        "condition": None,
        "message": f"Preprocessing workflow failed during {stage}.",
    }
    assert payload["command"][:5] == [
        "mania",
        "preprocessing",
        "run-graph-export",
        "--manifest",
        "manifest.yaml",
    ]
    assert payload["command"][5:7] == ["--output", "."]
    assert payload["resolved_configuration"]["manifest_name"] == "manifest.yaml"
    assert payload["resolved_configuration"]["output_root"] == "."
    assert str(tmp_path) not in json.dumps(payload)
    assert payload["sampling_by_condition"][0]["requested"]["frame_stride"] == 3
    effective = payload["sampling_by_condition"][0]["effective"]
    assert (
        effective is None if stage == "plan" else effective["sampled_frame_count"] == 2
    )
    assert list(root.iterdir()) == [target]
    received["identity"].assert_called_once_with()


@pytest.mark.parametrize("failure", ["builder", "writer_result", "writer_raise"])
@pytest.mark.parametrize(
    "exception", [ValueError, TypeError, OSError, RuntimeError, AttributeError]
)
def test_emission_failure_preserves_original_result(
    monkeypatch, capsys, tmp_path, failure, exception
):
    _, received = install_failure(monkeypatch, tmp_path, "diagnostics")
    _, baseline_stdout, baseline_stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    _, received = install_failure(monkeypatch, tmp_path, "diagnostics")
    artifact = tmp_path / "scientific.csv"
    artifact.write_bytes(b"retained")
    if failure == "builder":
        received["failed_provenance_builder"].side_effect = exception(
            "private/path\ntraceback"
        )
        diagnostic = (
            "Failed-run provenance build failed: Failed run metadata is invalid.\n"
        )
    elif failure == "writer_result":
        received["provenance_writer"].side_effect = None
        received["provenance_writer"].return_value = RunProvenanceWriteResult(
            tmp_path / "output/run_provenance.json", False, "Filesystem write failed."
        )
        diagnostic = "Failed-run provenance write failed: Filesystem write failed.\n"
    else:
        received["provenance_writer"].side_effect = exception("private/path\ntraceback")
        diagnostic = "Failed-run provenance write failed: Write operation failed.\n"
    with monkeypatch.context() as guard:
        guard.setattr(Path, "unlink", Mock(side_effect=AssertionError("No deletion")))
        guard.setattr(Path, "rmdir", Mock(side_effect=AssertionError("No deletion")))
        _, stdout, stderr = invoke_cli(
            monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
        )
    assert stdout == baseline_stdout and stderr == baseline_stderr + diagnostic
    assert artifact.read_bytes() == b"retained"
    if failure == "builder":
        received["provenance_writer"].assert_not_called()
    assert received["clock"].call_count == 2


@pytest.mark.parametrize("overwrite", [False, True])
def test_existing_target_and_overwrite(monkeypatch, capsys, tmp_path, overwrite):
    _, received = install_failure(monkeypatch, tmp_path, "plan", real_writer=True)
    target = tmp_path / "output/run_provenance.json"
    target.parent.mkdir()
    target.write_bytes(b"previous")
    original_options = cli._build_preprocessing_graph_workflow_options
    monkeypatch.setattr(
        cli,
        "_build_preprocessing_graph_workflow_options",
        lambda args: replace(original_options(args), overwrite=overwrite),
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == "plan"
    if overwrite:
        assert json.loads(target.read_text())["status"] == "failed" and stderr == ""
    else:
        assert target.read_bytes() == b"previous"
        assert stderr == "Failed-run provenance write failed: Target already exists.\n"
    assert list(target.parent.iterdir()) == [target]
    assert received["provenance_writer"].call_args.kwargs == {"overwrite": overwrite}


@pytest.mark.parametrize(
    "extra,roles",
    [
        (("--skip-diagnostics",), BEFORE_FAILURE_ROLES["diagnostics"]),
        (("--no-write-diagnostics-report",), BEFORE_FAILURE_ROLES["diagnostics"]),
    ],
)
def test_failed_references_follow_report_flags(
    monkeypatch, capsys, tmp_path, extra, roles
):
    _, received = install_failure(monkeypatch, tmp_path, "reference_comparison")
    invoke_cli(monkeypatch, capsys, *command(tmp_path, *extra), expected_exit_code=1)
    assert (
        tuple(
            ref.role
            for ref in received["provenance_writer"]
            .call_args.args[0]
            .artifact_references
        )
        == roles
    )


@pytest.mark.parametrize(
    "arguments,code",
    [
        (("--frame-stride", "0"), 2),
        (("--skip-contacts",), 2),
        (("--contact-selection", "all"), 2),
        (("--help",), 0),
    ],
)
def test_preexecution_validation_has_no_provenance(
    monkeypatch, capsys, tmp_path, arguments, code
):
    _, received = install_failure(monkeypatch, tmp_path, "plan")
    monkeypatch.setattr(sys, "argv", ["mania", *command(tmp_path, *arguments)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == code
    capsys.readouterr()
    for name in ("clock", "identity", "failed_provenance_builder", "provenance_writer"):
        received[name].assert_not_called()


@pytest.mark.parametrize(
    "arguments,code",
    [
        (("preprocessing", "run-graph-export"), 2),
        (("--help",), 0),
        (("--version",), 0),
    ],
)
def test_parser_help_version_do_not_observe_execution(
    monkeypatch, capsys, tmp_path, arguments, code
):
    _, received = install_failure(monkeypatch, tmp_path, "plan")
    cli.build_parser()
    monkeypatch.setattr(sys, "argv", ["mania", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == code
    capsys.readouterr()
    for name in ("clock", "identity", "failed_provenance_builder", "provenance_writer"):
        received[name].assert_not_called()
