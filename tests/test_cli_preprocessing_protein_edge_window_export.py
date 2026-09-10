"""Automatic source export, legacy compatibility, and complete technical gates."""

import hashlib
import json
from dataclasses import replace
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_artifact_inventory import command
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_physical_time_execution import (
    install_physical,
    physical_command,
    scientific_snapshot,
)
from test_preprocessing_protein_edge_window_execution import direct

import mania.cli as cli
from mania.preprocessing.protein_edge_window_table_io import (
    DatasetProteinEdgeWindowCsvWriteResult,
    read_dataset_protein_edge_window_csv,
    validate_dataset_protein_edge_window_csv,
    write_dataset_protein_edge_window_csv,
)
from mania.validation import validate_run_artifacts

ROLE = "protein_edges_by_window_source"
FILENAME = f"{ROLE}.csv"


def install_export(monkeypatch, root, **kwargs):
    source, runtimes, spies, mappings = install_physical(monkeypatch, root, **kwargs)
    for name in (
        "build_preprocessing_protein_edge_window_source_table",
        "write_dataset_protein_edge_window_csv",
    ):
        spies[name] = Mock(wraps=getattr(cli, name))
        monkeypatch.setattr(cli, name, spies[name])
    return source, runtimes, spies, mappings


def records(root):
    return (
        json.loads((root / "artifact_inventory.json").read_text()),
        json.loads((root / "run_provenance.json").read_text()),
    )


def assert_absent(root):
    inventory, provenance = records(root)
    assert not (root / FILENAME).exists()
    assert all(e["role"] != ROLE for e in inventory["artifacts"])
    assert all(r["role"] != ROLE for r in provenance["artifact_references"])


@pytest.mark.parametrize("mode", ["inline", "table", "mixed"])
@pytest.mark.parametrize("checksum", ["none", "sha256"])
def test_automatic_export_exact_pure_parity_lineage_and_three_passes(
    monkeypatch, capsys, tmp_path, mode, checksum
):
    _, runtimes, spies, mappings = install_export(monkeypatch, tmp_path, mode=mode)
    if checksum == "none":
        import mania.artifact_inventory_io as inventory_io
        import mania.validation.run_artifacts as integrity

        forbidden = Mock(side_effect=AssertionError("No content hashing in none mode"))
        monkeypatch.setattr(inventory_io, "stream_file_sha256", forbidden)
        monkeypatch.setattr(integrity, "stream_file_sha256", forbidden)
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(
            tmp_path,
            "--artifact-checksum-mode",
            checksum,
        ),
    )
    assert json.loads(stdout)["passed"] and stderr == ""
    builder = spies["build_preprocessing_protein_edge_window_source_table"]
    writer = spies["write_dataset_protein_edge_window_csv"]
    builder.assert_called_once()
    writer.assert_called_once()
    root = tmp_path / "out"
    assert writer.call_args.args[1] == root
    assert writer.call_args.kwargs == {"overwrite": False}
    expected = direct(*builder.call_args.args)
    actual = read_dataset_protein_edge_window_csv(root / FILENAME)
    assert actual.to_dict() == expected.to_dict() and actual.row_count > 0
    assert validate_dataset_protein_edge_window_csv(root / FILENAME).passed
    pure_path = write_dataset_protein_edge_window_csv(
        expected, tmp_path / "pure"
    ).output_path
    content = (root / FILENAME).read_bytes()
    assert content == pure_path.read_bytes()
    inventory, provenance = records(root)
    entries = [e for e in inventory["artifacts"] if e["role"] == ROLE]
    assert entries == [
        {
            "artifact_id": f"output:{ROLE}",
            "direction": "output",
            "role": ROLE,
            "path": FILENAME,
            "format": "csv",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest()
            if checksum == "sha256"
            else None,
            "condition": None,
        }
    ]
    assert [e["role"] for e in inventory["artifacts"][-4:]] == [
        ROLE,
        "temporal_execution",
        "runtime_metadata",
        "pbc_audit",
    ]
    assert [r for r in provenance["artifact_references"] if r["role"] == ROLE] == [
        {"role": ROLE, "path": FILENAME},
    ]
    assert (
        spies["build_preprocessing_artifact_inventory"].call_args.kwargs[f"{ROLE}_path"]
        == root / FILENAME
    )
    assert [r.trajectory.passes for r in runtimes] == (
        [3, 2] if mode == "mixed" else [3, 3]
    )
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    if checksum == "sha256":
        (root / FILENAME).write_bytes(content.replace(b"ALA", b"GLY", 1))
        report = validate_run_artifacts(
            root, scope="preprocessing", input_artifact_paths=mappings
        )
        assert report.status == "failed"
        assert next(r for r in report.specialized_records if r.role == ROLE).status == (
            "skipped_integrity_failure"
        )


@pytest.mark.parametrize("case", ["legacy", "disabled", "all"])
def test_conditional_skips_preserve_existing_workflow(
    monkeypatch, capsys, tmp_path, case
):
    _, _, spies, mappings = install_export(
        monkeypatch,
        tmp_path,
        mode="legacy" if case == "legacy" else "inline",
    )
    extra = (
        ("--skip-contacts",)
        if case == "disabled"
        else (
            "--contact-selection",
            "all" if case == "all" else "protein",
        )
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path, *extra),
        expected_exit_code=1 if case == "disabled" else 0,
    )
    # Existing graph export needs contacts, so disabled contacts retain that failure.
    assert json.loads(stdout)["passed"] is (case != "disabled")
    assert "Protein edge window export" not in stderr
    for name in (
        "build_preprocessing_protein_edge_window_source_table",
        "write_dataset_protein_edge_window_csv",
    ):
        spies[name].assert_not_called()
    if case == "disabled":
        assert json.loads(stdout)["stage"] == "plan"
        assert not (tmp_path / "out" / FILENAME).exists()
        provenance = json.loads((tmp_path / "out/run_provenance.json").read_text())
        assert (
            provenance["status"] == "failed" and not provenance["artifact_references"]
        )
        spies["compute_preprocessing_graph_workflow_rg_contacts"].assert_not_called()
        return
    assert_absent(tmp_path / "out")
    call = spies["compute_preprocessing_graph_workflow_rg_contacts"].call_args
    assert call.kwargs["include_contacts"] is (case != "disabled")
    if case == "all":
        assert call.kwargs["contact_options"].contact_selection == "all"
    report = validate_run_artifacts(
        tmp_path / "out", scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()


def test_header_only_success_and_condition_none(monkeypatch, capsys, tmp_path):
    source, _, spies, mappings = install_export(monkeypatch, tmp_path, mode="inline")
    payload = json.loads(source.manifest_path.read_text())
    for entry in payload["conditions"]:
        entry["dataset_spec"]["identity"]["condition"] = None
        entry["dataset_spec"]["identity"]["engine"] = "namd"
    source.manifest_path.write_text(json.dumps(payload))
    original = cli.build_preprocessing_protein_edge_window_source_table._mock_wraps

    def no_edges(temporal, contacts):
        contacts = replace(
            contacts,
            condition_results=tuple(
                replace(
                    c,
                    frame_results=tuple(
                        replace(f, contacts=()) for f in c.frame_results
                    ),
                )
                for c in contacts.condition_results
            ),
        )
        return original(temporal, contacts)

    spies["build_preprocessing_protein_edge_window_source_table"].side_effect = no_edges
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    assert len((root / FILENAME).read_text().splitlines()) == 1
    assert read_dataset_protein_edge_window_csv(root / FILENAME).row_count == 0
    assert any(r["role"] == ROLE for r in records(root)[1]["artifact_references"])
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete


@pytest.mark.parametrize(
    "failure", ["aggregation", "writer", "writer_exception", "existing"]
)
def test_failed_export_preserves_science_temporal_and_failed_lineage(
    monkeypatch, capsys, tmp_path, failure
):
    _, _, spies, mappings = install_export(monkeypatch, tmp_path)
    root = tmp_path / "out"
    path = root / FILENAME
    if failure == "aggregation":
        original = spies[
            "build_preprocessing_protein_edge_window_source_table"
        ]._mock_wraps

        def invalid_coverage(temporal, contacts):
            first, *rest = contacts.condition_results
            first = replace(first, frame_results=first.frame_results[:-1])
            return original(
                temporal, replace(contacts, condition_results=(first, *rest))
            )

        spies[
            "build_preprocessing_protein_edge_window_source_table"
        ].side_effect = invalid_coverage
    elif failure == "writer":
        spies[
            "write_dataset_protein_edge_window_csv"
        ].return_value = DatasetProteinEdgeWindowCsvWriteResult(
            path, False, "Controlled failure."
        )
    elif failure == "writer_exception":
        spies["write_dataset_protein_edge_window_csv"].side_effect = OSError(
            "private/path"
        )
    else:
        root.mkdir()
        path.write_bytes(b"prior user content")
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    prefix = "Protein edge window export" + (
        "" if failure == "aggregation" else " write"
    )
    assert stdout == "" and stderr.startswith(prefix + " failed:")
    assert "private/path" not in stderr and "Traceback" not in stderr
    assert len(scientific_snapshot(root)) == 15
    assert (root / "temporal_execution.json").is_file()
    inventory, provenance = records(root)
    assert provenance["status"] == "failed"
    assert any(
        r["role"] == "temporal_execution" for r in provenance["artifact_references"]
    )
    assert all(e["role"] != ROLE for e in inventory["artifacts"])
    assert all(r["role"] != ROLE for r in provenance["artifact_references"])
    if failure == "existing":
        assert path.read_bytes() == b"prior user content"
    else:
        assert not path.exists()
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()


def test_repeated_runs_deterministic_and_windows_only_change_new_science(
    monkeypatch, capsys, tmp_path
):
    snapshots, tables, temporal_bytes = [], [], []
    for i, temporal in enumerate(
        ({}, {}, {"window_length_ns": 0.8, "window_step_ns": 0.4})
    ):
        with monkeypatch.context() as patch:
            work = tmp_path / str(i)
            install_export(patch, work, temporal=temporal)
            invoke_cli(patch, capsys, *physical_command(work))
            root = work / "out"
            snapshots.append(scientific_snapshot(root))
            tables.append((root / FILENAME).read_bytes())
            temporal_bytes.append((root / "temporal_execution.json").read_bytes())
    assert len(snapshots[0]) == 15 and snapshots[0] == snapshots[1] == snapshots[2]
    assert tables[0] == tables[1] != tables[2]
    assert temporal_bytes[0] == temporal_bytes[1] != temporal_bytes[2]


@pytest.mark.parametrize("missing", [False, True])
def test_cli_final_csv_distinguishes_missing_samples_from_resolved_negatives(
    monkeypatch, capsys, tmp_path, missing
):
    temporal = {
        "production_end_ns": 0.8,
        "window_length_ns": 0.8,
        "window_step_ns": 0.4,
    }
    times = tuple(range(0, 801, 100))
    if missing:
        times = (*times[:4], 450, *times[5:])
    _, _, spies, mappings = install_export(
        monkeypatch, tmp_path, temporal=temporal, times=times
    )
    compute = spies["compute_preprocessing_graph_workflow_rg_contacts"]
    original = compute._mock_wraps

    def controlled_presence(*args, **kwargs):
        result = original(*args, **kwargs)
        contact_result = replace(
            result.contacts_result,
            condition_results=tuple(
                replace(
                    c,
                    frame_results=tuple(
                        replace(f, contacts=()) if f.time_ps == 400 else f
                        for f in c.frame_results
                    ),
                )
                for c in result.contacts_result.condition_results
            ),
        )
        return replace(result, contacts_result=contact_result)

    compute.side_effect = controlled_presence
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    table = read_dataset_protein_edge_window_csv(root / FILENAME)
    assert table.row_count > 0
    for row in table.rows:
        assert row.requested_sample_count == 5
        assert row.resolved_frame_count == (4 if missing else 5)
        assert row.n_contact_frames == 4
        assert row.occupancy == row.edge_weight == (1.0 if missing else 0.8)
        assert row.n_contact_episodes == 2
        assert row.mean_episode_length_ns == row.max_episode_length_ns == 0.2
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete


def test_nonempty_source_preserves_nullable_condition_through_cli(
    monkeypatch, capsys, tmp_path
):
    source, _, _, mappings = install_export(monkeypatch, tmp_path, mode="inline")
    payload = json.loads(source.manifest_path.read_text())
    for entry in payload["conditions"]:
        entry["dataset_spec"]["identity"]["condition"] = None
        entry["dataset_spec"]["identity"]["engine"] = "namd"
    source.manifest_path.write_text(json.dumps(payload))
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    table = read_dataset_protein_edge_window_csv(root / FILENAME)
    assert table.row_count > 0 and all(row.condition is None for row in table.rows)
    assert len({row.system_id for row in table.rows}) == 2
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete
