"""Stage 26 acceptance: Dataset metadata remains inert in real synthetic science."""

import json
import shutil
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_artifact_inventory import (
    command,
    install_inventory_workflow,
)
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_runtime_pbc_metadata import install_smoke, smoke_command
from test_preprocessing_dataset_binding import reference, spec, write_table

import mania.cli as cli
from mania.preprocessing.artifact_inventory import (
    collect_preprocessing_input_file_specs,
)
from mania.preprocessing.input_manifest import load_preprocessing_input_manifest
from mania.validation import validate_run_artifacts

TECHNICAL_FILES = {
    "run_provenance.json",
    "artifact_inventory.json",
    "runtime_metadata.json",
    "pbc_audit.json",
}


def dataset_manifest(source, mode):
    entries = []
    specs = []
    for ordinal, result in enumerate(source.runtime_load_result.condition_results):
        inputs = result.runtime_input
        value = spec(condition=None, engine="namd", replica_id=str(ordinal))
        specs.append(value)
        entry = {
            "condition": inputs.condition_name,
            "topology_path": str(inputs.topology_path),
            "trajectory_paths": [str(p) for p in inputs.trajectory_paths],
            "reference_structure_path": str(inputs.reference_structure_path),
        }
        if mode in ("inline", "both"):
            entry["dataset_spec"] = value.model_dump(mode="json")
        if mode in ("table", "both"):
            entry["dataset_ref"] = reference(value)
        entries.append(entry)
    payload = {"output_root": "out", "conditions": entries}
    table = None
    if mode in ("table", "both"):
        table = write_table(
            source.manifest_path.parent / "private-parameters.csv", *specs
        )
        payload["dataset_parameter_table_path"] = table.name
    source.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return table, specs


@pytest.mark.parametrize("checksum_mode", ["none", "sha256"])
def test_legacy_inline_table_scientific_byte_acceptance(
    monkeypatch, capsys, tmp_path, checksum_mode
):
    snapshots = []
    samplings = []
    stdout_values = []
    stderr_values = []
    scientific_calls = []
    for mode in ("legacy", "inline", "table"):
        with monkeypatch.context() as patch:
            source, runtimes, spies = install_smoke(patch, tmp_path, [None] * 8)
            table, requested_specs = dataset_manifest(source, mode)
            resolver = Mock(wraps=cli.resolve_preprocessing_dataset_context)
            patch.setattr(cli, "resolve_preprocessing_dataset_context", resolver)
            args = smoke_command(
                tmp_path,
                "--artifact-checksum-mode",
                checksum_mode,
                "--verbose",
            )
            _, stdout, stderr = invoke_cli(patch, capsys, *args)
            resolver.assert_called_once_with(
                load_preprocessing_input_manifest(source.manifest_path),
                base_dir=source.manifest_path.parent,
            )
            stdout_values.append(stdout)
            stderr_values.append(stderr)
            root = tmp_path / "out"
            snapshots.append(
                {
                    p.relative_to(root).as_posix(): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file() and p.name not in TECHNICAL_FILES
                }
            )
            provenance = json.loads((root / "run_provenance.json").read_text())
            inventory = json.loads((root / "artifact_inventory.json").read_text())
            samplings.append(provenance["sampling_by_condition"])
            context = provenance["resolved_configuration"].get("dataset_context")
            inventory_call = spies[
                "build_preprocessing_artifact_inventory"
            ].call_args.kwargs
            assert inventory_call["parameter_table_local_path"] == table
            provenance_call = spies[
                "build_completed_preprocessing_run_provenance"
            ].call_args.kwargs
            table_entries = [
                e
                for e in inventory["artifacts"]
                if e["role"] == "dataset_parameter_table"
            ]
            if mode == "legacy":
                assert "dataset_context" not in provenance["resolved_configuration"]
                assert provenance_call["dataset_context"] is None
            else:
                assert provenance_call["dataset_context"].to_dict() == context
                assert [b["source"] for b in context["bindings"]] == [
                    "inline_manifest" if mode == "inline" else "parameter_table"
                ] * 2
                assert [b["dataset_spec"] for b in context["bindings"]] == [
                    s.to_dict() for s in requested_specs
                ]
                assert all(
                    b["dataset_spec"]["identity"]["condition"] is None
                    for b in context["bindings"]
                )
                assert str(tmp_path) not in json.dumps(context)
                assert "private-parameters.csv" not in json.dumps(context)
            assert len(table_entries) == (1 if mode == "table" else 0)
            assert str(tmp_path) not in json.dumps(inventory)
            assert "private-parameters.csv" not in json.dumps(inventory)
            computation_call = spies[
                "compute_preprocessing_graph_workflow_rg_contacts"
            ].call_args
            assert computation_call.args == (source,)
            assert set(computation_call.kwargs) == {
                "include_rg",
                "include_contacts",
                "frame_sampling",
                "contact_options",
                "progress_callback",
                "collect_pbc_observations",
            }
            scientific_calls.append(
                {
                    k: v
                    for k, v in computation_call.kwargs.items()
                    if k != "progress_callback"
                }
            )
            for runtime in runtimes:
                assert runtime.trajectory.passes == 2
                assert runtime.trajectory.observed == [(1, i) for i in (1, 3, 5)]
            mappings = {
                item.artifact_id: item.local_path
                for item in collect_preprocessing_input_file_specs(
                    source, parameter_table_local_path=table
                )
            }
            report = validate_run_artifacts(
                root, scope="preprocessing", input_artifact_paths=mappings
            )
            assert report.status == "passed" and report.complete is True, (
                report.to_dict()
            )
            assert report.unsupported_count == 0
            if table is not None:
                assert mappings["input:dataset_parameter_table"] == table
                assert any(
                    r.role == "dataset_parameter_table" and r.status == "passed"
                    for r in report.specialized_records
                )
                mapping_args = [
                    argument
                    for artifact_id, path in mappings.items()
                    for argument in (
                        "--input-artifact-path", f"{artifact_id}={path}",
                    )
                ]
                _, validation_stdout, validation_stderr = invoke_cli(
                    patch, capsys, "artifacts", "validate", str(root),
                    "--scope", "preprocessing", *mapping_args,
                )
                validation_payload = json.loads(validation_stdout)
                assert validation_payload["status"] == "passed"
                assert validation_payload["complete"] is True
                assert validation_stderr == ""
            if mode != "table":
                shutil.rmtree(root)
    assert len(snapshots[0]) == 16
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert samplings[0] == samplings[1] == samplings[2]
    assert scientific_calls[0] == scientific_calls[1] == scientific_calls[2]
    assert stdout_values[0] == stdout_values[1] == stdout_values[2]
    assert stderr_values[0] == stderr_values[1] == stderr_values[2]
    print(
        f"Stage 26 acceptance ({checksum_mode}): {len(snapshots[0])} scientific files "
        "byte-identical; mapped validation passed, complete=true"
    )


@pytest.mark.parametrize("mode", ["inline", "table", "both"])
@pytest.mark.parametrize(
    "failure_stage", ["runtime_loading", "computation", "graph_export"]
)
def test_failed_scientific_run_keeps_resolved_context_and_input_lineage(
    monkeypatch, capsys, tmp_path, mode, failure_stage
):
    _, received = install_inventory_workflow(
        monkeypatch, tmp_path, failure=failure_stage
    )
    source = received["runtime"]
    table, requested = dataset_manifest(source, mode)
    _, stdout, _ = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == failure_stage
    root = tmp_path / "out"
    provenance = json.loads((root / "run_provenance.json").read_text())
    assert provenance["status"] == "failed"
    bindings = provenance["resolved_configuration"]["dataset_context"]["bindings"]
    assert [b["dataset_spec"] for b in bindings] == [s.to_dict() for s in requested]
    assert {b["source"] for b in bindings} == {
        {
            "inline": "inline_manifest",
            "table": "parameter_table",
            "both": "inline_and_parameter_table",
        }[mode]
    }
    received["failed_provenance_builder"].assert_called_once()
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    assert all(e["direction"] == "input" for e in inventory["artifacts"])
    assert len(
        [e for e in inventory["artifacts"] if e["role"] == "dataset_parameter_table"]
    ) == (0 if table is None else 1)
    assert str(tmp_path) not in json.dumps(
        provenance["resolved_configuration"]["dataset_context"]
    )


@pytest.mark.parametrize(
    "failure", ["missing_table", "temporal_conflict", "missing_key", "condition"]
)
def test_binding_failure_stops_before_runtime_and_science(
    monkeypatch, capsys, tmp_path, failure
):
    source, _, spies = install_smoke(monkeypatch, tmp_path, [None] * 8)
    table, specs = dataset_manifest(
        source, "both" if failure == "temporal_conflict" else "table"
    )
    if failure == "missing_table":
        table.unlink()
    elif failure == "temporal_conflict":
        table.write_bytes(table.read_bytes().replace(b"17.3", b"19.3"))
    elif failure == "missing_key":
        write_table(table, spec(condition=None, replica_id="absent"))
    else:
        changed = [
            spec(condition="unmatched", replica_id=s.identity.replica_id) for s in specs
        ]
        write_table(table, *changed)
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *smoke_command(tmp_path), expected_exit_code=1
    )
    assert stdout == ""
    assert stderr.startswith("Dataset specification binding failed:")
    assert "Traceback" not in stderr and str(table) not in stderr
    cli.load_preprocessing_graph_workflow_condition_runtimes.assert_not_called()
    for name in (
        "compute_preprocessing_graph_workflow_rg_contacts",
        "build_preprocessing_artifact_inventory",
        "build_completed_preprocessing_run_provenance",
        "write_run_provenance",
    ):
        spies[name].assert_not_called()
    assert not (tmp_path / "out").exists()
