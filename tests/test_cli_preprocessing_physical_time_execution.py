"""Exercise physical selection through real synthetic science and technical gates."""

import hashlib
import json
import shutil
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_artifact_inventory import command
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_runtime_pbc_metadata import install_smoke
from test_preprocessing_dataset_binding import reference, write_table
from test_preprocessing_physical_time_execution import dataset_spec

import mania.cli as cli
from mania.preprocessing.artifact_inventory import (
    collect_preprocessing_input_file_specs,
)
from mania.preprocessing.physical_time_execution_io import (
    PreprocessingTemporalExecutionWriteResult,
    read_preprocessing_temporal_execution,
)
from mania.validation import validate_run_artifacts

TECHNICAL_ROLES = {
    "temporal_execution",
    "runtime_metadata",
    "pbc_audit",
    "artifact_inventory",
    "run_provenance",
    "graph_diagnostics_report",
}


def install_physical(monkeypatch, root, *, mode="table", temporal=None, times=None):
    times = tuple(range(0, 1001, 100)) if times is None else times
    source, runtimes, spies = install_smoke(monkeypatch, root, [None] * len(times))
    entries, specs = [], []
    for result, runtime in zip(
        source.runtime_load_result.condition_results, runtimes, strict=True
    ):
        runtime.trajectory.n_frames = len(times)
        for frame, time in zip(runtime.trajectory.frames, times, strict=True):
            frame.time = time
        value = dataset_spec(result.condition_name, **(temporal or {}))
        specs.append(value)
        inputs = result.runtime_input
        entry = {
            "condition": result.condition_name,
            "topology_path": str(inputs.topology_path),
            "trajectory_paths": [str(p) for p in inputs.trajectory_paths],
            "reference_structure_path": str(inputs.reference_structure_path),
        }
        if mode == "inline" or (mode == "mixed" and result.condition_name == "normal"):
            entry["dataset_spec"] = value.model_dump(mode="json")
        elif mode == "table":
            entry["dataset_ref"] = reference(value)
        entries.append(entry)
    payload = {"conditions": entries, "output_root": "out"}
    table = None
    if mode == "table":
        table = write_table(source.manifest_path.parent / "parameters.csv", *specs)
        payload["dataset_parameter_table_path"] = table.name
    source.manifest_path.write_text(json.dumps(payload))
    for name in (
        "build_preprocessing_temporal_execution",
        "write_preprocessing_temporal_execution",
    ):
        spies[name] = Mock(wraps=getattr(cli, name))
        monkeypatch.setattr(cli, name, spies[name])
    mappings = {
        s.artifact_id: s.local_path
        for s in collect_preprocessing_input_file_specs(
            source,
            parameter_table_local_path=table,
        )
    }
    return source, runtimes, spies, mappings


def physical_command(root, *extra):
    return command(
        root,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--export-contacts-perframe",
        *extra,
    )


def scientific_snapshot(root):
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    return {
        e["path"]: (root / e["path"]).read_bytes()
        for e in inventory["artifacts"]
        if e["direction"] == "output" and e["role"] not in TECHNICAL_ROLES
    }


@pytest.mark.parametrize("mode", ["inline", "table", "mixed"])
@pytest.mark.parametrize("checksum", ["none", "sha256"])
def test_complete_physical_run_and_mapped_validation(
    monkeypatch, capsys, tmp_path, mode, checksum
):
    if checksum == "none":
        import mania.artifact_inventory_io as inventory_io
        import mania.validation.run_artifacts as integrity

        forbidden_hash = Mock(
            side_effect=AssertionError("none must never hash content")
        )
        monkeypatch.setattr(inventory_io, "stream_file_sha256", forbidden_hash)
        monkeypatch.setattr(integrity, "stream_file_sha256", forbidden_hash)
    source, runtimes, spies, mappings = install_physical(
        monkeypatch, tmp_path, mode=mode
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(
            tmp_path,
            "--artifact-checksum-mode",
            checksum,
        ),
    )
    assert stderr == "" and json.loads(stdout)["passed"]
    root = tmp_path / "out"
    execution = read_preprocessing_temporal_execution(root / "temporal_execution.json")
    assert execution.status == "complete"
    selected = execution.selected_source_frame_indexes_by_condition()
    assert selected == {
        name: (0, 2, 4, 6, 8, 10)
        for name in (("normal",) if mode == "mixed" else ("normal", "tumor"))
    }
    for name in (
        "build_preprocessing_temporal_execution",
        "write_preprocessing_temporal_execution",
    ):
        spies[name].assert_called_once()
    call = spies["compute_preprocessing_graph_workflow_rg_contacts"].call_args
    assert call.args == (source,)
    assert call.kwargs["source_frame_indexes_by_condition"] == selected
    retained = spies["build_preprocessing_runtime_metadata"].call_args.kwargs[
        "computation"
    ]
    for name, runtime in zip(source.condition_names, runtimes, strict=True):
        indexes = selected.get(name, tuple(range(11)))
        assert runtime.trajectory.passes == (3 if name in selected else 2)
        canonical_pass = 2 if name in selected else 1
        assert runtime.trajectory.observed == [(canonical_pass, i) for i in indexes]
        for result in (retained.rg_result, retained.contacts_result):
            condition = next(
                c for c in result.condition_results if c.condition_name == name
            )
            assert tuple(f.frame_index for f in condition.frame_results) == indexes
    provenance = json.loads((root / "run_provenance.json").read_text())
    requested = provenance["resolved_configuration"]["dataset_context"]
    assert all("sampling_plan" not in b for b in requested["bindings"])
    assert [b["dataset_spec"] for b in requested["bindings"]] == [
        b.dataset_spec.to_dict() for b in execution.bindings
    ]
    assert provenance["artifact_references"][-4:] == [
        {"role": role, "path": f"{role}.json"}
        for role in (
            "temporal_execution",
            "runtime_metadata",
            "pbc_audit",
            "artifact_inventory",
        )
    ]
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    assert [e["role"] for e in inventory["artifacts"][-3:]] == [
        "temporal_execution",
        "runtime_metadata",
        "pbc_audit",
    ]
    entry = inventory["artifacts"][-3]
    content = (root / "temporal_execution.json").read_bytes()
    assert entry["artifact_id"] == "output:temporal_execution"
    assert entry["byte_size"] == len(content)
    assert entry["sha256"] == (
        hashlib.sha256(content).hexdigest() if checksum == "sha256" else None
    )
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    assert len(scientific_snapshot(root)) == 15


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--frame-start", "1"),
        ("--frame-stop", "11"),
        ("--frame-stride", "2"),
        ("--max-frames", "3"),
    ],
)
def test_dataset_legacy_control_conflict_blocks_planning_and_science(
    monkeypatch, capsys, tmp_path, flag, value
):
    _, runtimes, spies, _ = install_physical(monkeypatch, tmp_path, mode="mixed")
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(tmp_path, flag, value),
        expected_exit_code=1,
    )
    assert stdout == "" and stderr.startswith(
        "Physical-time sampling configuration failed:"
    )
    spies["build_preprocessing_temporal_execution"].assert_not_called()
    spies["compute_preprocessing_graph_workflow_rg_contacts"].assert_not_called()
    assert all(r.trajectory.passes == 0 for r in runtimes)


@pytest.mark.parametrize("failure", ["outside", "invalid_time", "failed_windows"])
def test_failed_planning_preserves_context_and_table_without_science(
    monkeypatch, capsys, tmp_path, failure
):
    times = tuple(range(0, 1001, 100)) if failure != "invalid_time" else (None,)
    temporal = (
        {"production_start_ns": 2, "production_end_ns": 3}
        if failure == "outside"
        else ({"window_step_ns": 0.5} if failure == "failed_windows" else {})
    )
    _, _, spies, mappings = install_physical(
        monkeypatch, tmp_path, temporal=temporal, times=times
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    assert stdout == "" and stderr.startswith(
        "Physical-time execution planning failed:"
    )
    assert "Traceback" not in stderr
    spies["compute_preprocessing_graph_workflow_rg_contacts"].assert_not_called()
    spies["write_preprocessing_temporal_execution"].assert_not_called()
    root = tmp_path / "out"
    assert not (root / "temporal_execution.json").exists()
    provenance = json.loads((root / "run_provenance.json").read_text())
    assert provenance["status"] == "failed"
    assert provenance["resolved_configuration"]["dataset_context"]
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    assert all(e["direction"] == "input" for e in inventory["artifacts"])
    assert any(e["role"] == "dataset_parameter_table" for e in inventory["artifacts"])
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()


def test_partial_plan_proceeds(monkeypatch, capsys, tmp_path):
    times = (0, 100, 200, 300, 450, 500, 600, 700, 800, 900, 1000)
    _, _, _, mappings = install_physical(monkeypatch, tmp_path, times=times)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    value = read_preprocessing_temporal_execution(root / "temporal_execution.json")
    assert value.status == "partial"
    assert value.bindings[0].selected_source_frame_indexes == (0, 2, 6, 8, 10)
    assert value.bindings[0].sampling_plan.missing_samples[0].requested_time_ps == 400
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete


def test_temporal_writer_failure_retains_science_without_false_claim(
    monkeypatch, capsys, tmp_path
):
    _, _, spies, _ = install_physical(monkeypatch, tmp_path)
    target = tmp_path / "out/temporal_execution.json"
    spies[
        "write_preprocessing_temporal_execution"
    ].return_value = PreprocessingTemporalExecutionWriteResult(
        target,
        False,
        "Controlled write failure.",
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    assert stdout == "" and stderr.startswith("Temporal execution write failed:")
    assert not target.exists()
    root = target.parent
    assert len(scientific_snapshot(root)) == 15
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    provenance = json.loads((root / "run_provenance.json").read_text())
    assert all(e["role"] != "temporal_execution" for e in inventory["artifacts"])
    assert all(
        e["role"] != "temporal_execution" for e in provenance["artifact_references"]
    )


def test_legacy_equivalent_physical_and_window_inert_scientific_bytes(
    monkeypatch, capsys, tmp_path
):
    snapshots, plans = [], []
    for mode, temporal in (
        ("legacy", {}),
        ("table", {}),
        (
            "table",
            {
                "window_length_ns": 0.8,
                "window_step_ns": 0.4,
            },
        ),
    ):
        with monkeypatch.context() as patch:
            _, runtimes, spies, _ = install_physical(
                patch, tmp_path, mode=mode, temporal=temporal
            )
            extra = (
                ("--frame-stop", "11", "--frame-stride", "2")
                if mode == "legacy"
                else ()
            )
            invoke_cli(patch, capsys, *physical_command(tmp_path, *extra))
            root = tmp_path / "out"
            snapshots.append(scientific_snapshot(root))
            if mode == "legacy":
                spies["build_preprocessing_temporal_execution"].assert_not_called()
                assert not (root / "temporal_execution.json").exists()
                assert all(r.trajectory.passes == 2 for r in runtimes)
            else:
                plans.append(
                    read_preprocessing_temporal_execution(
                        root / "temporal_execution.json"
                    )
                )
            shutil.rmtree(root)
    assert len(snapshots[0]) == 15
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert plans[0].bindings[0].sampling_plan == plans[1].bindings[0].sampling_plan
    assert plans[0].bindings[0].window_plan != plans[1].bindings[0].window_plan


def test_physical_output_downstream_analysis_and_complete_gate(
    monkeypatch, capsys, tmp_path
):
    from test_cli_preprocessing_graph_workflow import END, START

    from mania.analysis.artifact_inventory import collect_analysis_input_file_specs
    from mania.analysis.orchestration import (
        AnalyzeRequest,
        resolve_analysis_input_paths,
    )

    _, _, spies, _ = install_physical(monkeypatch, tmp_path)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    technical = {
        p.name: p.read_bytes() for p in root.glob("*.json") if p.stem in TECHNICAL_ROLES
    }
    spies["clock"].side_effect = [START, END]
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        "analyze",
        "--input",
        str(root),
        "--output",
        str(root),
        "--condition",
        "normal",
        "--condition",
        "tumor",
        "--enable-pca",
        "--artifact-checksum-mode",
        "none",
    )
    assert stderr == "" and stdout
    assert all(
        (root / name).read_bytes() == content for name, content in technical.items()
    )
    request = AnalyzeRequest(root, root, ("normal", "tumor"))
    mappings = {
        s.artifact_id: s.local_path
        for s in collect_analysis_input_file_specs(
            request=request,
            resolved_input_paths=resolve_analysis_input_paths(request),
        )
    }
    report = validate_run_artifacts(
        root, scope="analysis", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    inventory = json.loads((root / "analysis/artifact_inventory.json").read_text())
    assert (
        len(
            [
                e
                for e in inventory["artifacts"]
                if e["direction"] == "output" and e["role"] != "runtime_metadata"
            ]
        )
        == 17
    )
    assert all(e["role"] != "temporal_execution" for e in inventory["artifacts"])


def test_temporal_sha256_integrity_precedes_specialized_reader(
    monkeypatch, capsys, tmp_path
):
    _, _, _, mappings = install_physical(monkeypatch, tmp_path)
    invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(
            tmp_path,
            "--artifact-checksum-mode",
            "sha256",
        ),
    )
    root = tmp_path / "out"
    path = root / "temporal_execution.json"
    original = path.read_bytes()
    changed = original.replace(b'"complete"', b'"partial "', 1)
    assert changed != original and len(changed) == len(original)
    path.write_bytes(changed)
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "failed"
    record = next(
        r for r in report.specialized_records if r.role == "temporal_execution"
    )
    assert record.status == "skipped_integrity_failure"


def test_contact_only_physical_run_has_one_planning_and_one_scientific_pass(
    monkeypatch, capsys, tmp_path
):
    _, runtimes, _, mappings = install_physical(monkeypatch, tmp_path)
    invoke_cli(
        monkeypatch,
        capsys,
        *command(
            tmp_path,
            "--contact-selection",
            "protein",
            "--export-analysis-inputs",
            "--skip-rg",
        ),
    )
    for runtime in runtimes:
        assert runtime.trajectory.passes == 2
        assert runtime.trajectory.observed == [(2, i) for i in (0, 2, 4, 6, 8, 10)]
    report = validate_run_artifacts(
        tmp_path / "out",
        scope="preprocessing",
        input_artifact_paths=mappings,
    )
    assert report.status == "passed" and report.complete
