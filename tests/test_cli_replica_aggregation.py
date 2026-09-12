"""Narrow Dataset command parsing, successful runs and portable phase failures."""

import json
import sys

import pytest
from test_replica_aggregation_manifest import make_manifest

from mania import cli
from mania.replica_aggregation_workflow import FAMILIES


def invoke(monkeypatch, path, output, *args):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "dataset",
            "aggregate-replicas",
            "--manifest",
            str(path),
            "--output",
            str(output),
            *args,
        ],
    )
    cli.main()


@pytest.mark.parametrize(
    "specialized,mode", [(False, "none"), (True, "none"), (True, "sha256")]
)
def test_cli_success(tmp_path, monkeypatch, capsys, specialized, mode):
    _, path = make_manifest(tmp_path / "inputs", complete=True, specialized=specialized)
    output = tmp_path / "out"

    def forbidden(*args, **kwargs):
        raise AssertionError("Trajectory runtime must not be used")

    for name in (
        "load_preprocessing_graph_workflow_condition_runtimes",
        "compute_preprocessing_graph_workflow_rg_contacts",
        "execute_preprocessing_specialized_contacts",
    ):
        monkeypatch.setattr(cli, name, forbidden)
    invoke(monkeypatch, path, output, "--artifact-checksum-mode", mode)
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "completed" and summary["trajectory_passes"] == 0
    assert len(summary["group_outputs"]) == (3 if specialized else 1)
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, path, output)
    assert exc.value.code == 1
    capsys.readouterr()
    invoke(monkeypatch, path, output, "--overwrite")
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


@pytest.mark.parametrize(
    "failure", ["manifest", "input", "aggregation", "export write"]
)
def test_cli_failure_prefixes(tmp_path, monkeypatch, capsys, failure):
    import mania.replica_aggregation_run as run

    manifest, path = make_manifest(tmp_path / "inputs")
    output = tmp_path / "out"
    if failure == "manifest":
        path.write_text("{}")
    elif failure == "input":
        manifest.protein_canonical_table_paths[0].unlink()
    elif failure == "aggregation":

        def broken(*args, **kwargs):
            raise ValueError("private detail")

        monkeypatch.setattr(run, "build_replica_aggregation_tables", broken)
    else:
        output.mkdir()
        (output / FAMILIES[0].filename).write_text("existing")
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, path, output)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    prefix = (
        "Replica aggregation failed:"
        if failure == "aggregation"
        else (f"Replica aggregation {failure} failed:")
    )
    assert prefix in captured.err
    assert "Traceback" not in captured.err and "private detail" not in captured.err
    assert captured.out == ""


def test_exact_command_options():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dataset",
            "aggregate-replicas",
            "--manifest",
            "manifest.json",
            "--output",
            "out",
        ]
    )
    assert args.artifact_checksum_mode == "none" and args.overwrite is False
    for option in ("--stride", "--condition", "--contact-cutoff", "--estimator"):
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "dataset",
                    "aggregate-replicas",
                    "--manifest",
                    "m",
                    "--output",
                    "out",
                    option,
                    "1",
                ]
            )
