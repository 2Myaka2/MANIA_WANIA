"""Authoritative portable specifications, with synthetic retained workflow state."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_analysis_inputs import _graph_export_result

import mania.artifact_inventory_io as inventory_io
import mania.preprocessing.artifact_inventory as adapter
from mania.preprocessing.run_provenance import PREPROCESSING_RUN_PROVENANCE_WORKFLOW
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowDiagnosticsResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowReferenceComparisonResult,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    PreprocessingGraphWorkflowScientificCsvExportResult,
    export_preprocessing_graph_workflow_analysis_inputs,
)
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadResult,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
)


def write_small(path, content=b"synthetic\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def make_runtime(root, conditions=("normal", "tumor"), *, failed=False):
    manifest = write_small(root / "source/manifest.yaml", b"not parsed by inventory\n")
    results = []
    for number, name in enumerate(conditions):
        directory = root / f"source/{number}"
        source = PreprocessingConditionRuntimeInput(
            name,
            write_small(directory / "topology.TPR", b"topology\n"),
            (
                write_small(directory / "part-b/trajectory.xtc", b"first\n"),
                write_small(directory / "part-a/trajectory.xtc", b"second\n"),
            ),
            write_small(directory / "reference.pdb", b"structure\n"),
        )
        runtime = PreprocessingConditionRuntime(
            name,
            SimpleNamespace(trajectory=SimpleNamespace(n_frames=10)),
            "synthetic",
            source.topology_path,
            source.trajectory_paths,
        )
        results.append(
            PreprocessingConditionLoadResult(
                name,
                source,
                None if failed else runtime,
                status="failed" if failed else "loaded",
            )
        )
    readiness = PreprocessingGraphWorkflowManifestReadinessResult(
        manifest,
        True,
        True,
        conditions,
        len(conditions),
    )
    return PreprocessingGraphWorkflowRuntimeLoadingResult(
        manifest,
        readiness,
        () if failed else conditions,
        conditions,
        PreprocessingManifestLoadResult(tuple(results)),
    )


def make_stages(root, runtime):
    conditions = runtime.manifest_readiness.condition_names
    graph = _graph_export_result(root, conditions)
    graph = replace(
        graph, computation=replace(graph.computation, runtime_loading=runtime)
    )
    for path in (
        graph.graph_nodes_csv_path,
        graph.graph_edges_csv_path,
        graph.graph_json_path,
    ):
        write_small(path)
    analysis = export_preprocessing_graph_workflow_analysis_inputs(graph)
    assert analysis.passed
    layout = graph.output_layout
    good = SimpleNamespace(passed=True)
    scientific = PreprocessingGraphWorkflowScientificCsvExportResult(
        graph.computation,
        layout,
        True,
        True,
        True,
        write_small(layout.rg_timeseries_csv_path),
        write_small(layout.contact_edges_csv_path),
        write_small(layout.contacts_perframe_csv_path),
        good,
        good,
        good,
        good,
        good,
        good,
    )
    diagnostics = PreprocessingGraphWorkflowDiagnosticsResult(
        graph,
        good,
        {},
        write_small(layout.diagnostics_report_json_path),
        True,
    )
    references = tuple(
        write_small(root.parent / f"reference/{name}")
        for name in (
            "nodes.csv",
            "edges.csv",
            "graph.json",
        )
    )
    options = PreprocessingGraphWorkflowOptions(
        runtime.manifest_path,
        root,
        enable_reference_comparison=True,
        reference_nodes_csv_path=references[0],
        reference_edges_csv_path=references[1],
        reference_graph_json_path=references[2],
    )
    reference = PreprocessingGraphWorkflowReferenceComparisonResult(
        graph,
        options,
        layout,
        True,
        reference_comparison_result=good,
        reference_comparison_json_path=write_small(
            layout.reference_comparison_json_path
        ),
        reference_comparison_json_written=True,
    )
    return dict(
        graph_export=graph,
        analysis_input_export=analysis,
        scientific_csv_export=scientific,
        diagnostics=diagnostics,
        reference_comparison=reference,
    )


def forbid(*args, **kwargs):
    raise AssertionError("Unexpected file content access, discovery, or resolution")


def guard_discovery(patch):
    for method in ("glob", "rglob", "iterdir", "resolve"):
        patch.setattr(Path, method, forbid)
    patch.setattr(os, "walk", forbid)


def test_inputs_preserve_order_identity_and_never_read(monkeypatch, tmp_path):
    runtime = make_runtime(tmp_path, ("z odd / condition", "α beta"))
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        patch.setattr(Path, "open", forbid)
        patch.setattr(Path, "stat", forbid)
        specs = adapter.collect_preprocessing_input_file_specs(runtime)
    assert specs[0].artifact_id == "input:manifest"
    assert specs[0].path == "inputs/manifest/manifest.yaml"
    assert specs[0].role == "input_manifest" and specs[0].condition is None
    assert len(specs) == 9
    for ordinal, condition in enumerate(runtime.manifest_readiness.condition_names, 1):
        group = specs[1 + (ordinal - 1) * 4 : 1 + ordinal * 4]
        assert [s.artifact_id for s in group] == [
            f"input:condition:{ordinal:04d}:{suffix}"
            for suffix in (
                "topology",
                "trajectory:0001",
                "trajectory:0002",
                "reference_structure",
            )
        ]
        prefix = f"inputs/conditions/{ordinal:04d}"
        assert [s.path for s in group] == [
            f"{prefix}/topology/topology.TPR",
            f"{prefix}/trajectories/0001/trajectory.xtc",
            f"{prefix}/trajectories/0002/trajectory.xtc",
            f"{prefix}/reference_structure/reference.pdb",
        ]
        assert [s.format for s in group] == ["tpr", "xtc", "xtc", "pdb"]
        assert all(s.condition == condition for s in group)
        assert all(
            condition not in s.path and condition not in s.artifact_id for s in group
        )
        assert "part-b" in str(group[1].local_path)
        assert "part-a" in str(group[2].local_path)
    assert len({s.path for s in specs}) == len(specs)


@pytest.mark.parametrize("enabled", [False, True])
def test_reference_inputs_only_when_enabled(tmp_path, enabled):
    runtime = make_runtime(tmp_path)
    paths = [tmp_path / name / "same.csv" for name in ("nodes", "edges", "graph")]
    specs = adapter.collect_preprocessing_input_file_specs(
        runtime,
        include_reference_inputs=enabled,
        reference_nodes_path=paths[0],
        reference_edges_path=paths[1],
        reference_graph_path=paths[2],
    )
    refs = [s for s in specs if s.role.startswith("reference_")]
    assert len(refs) == (3 if enabled else 0)
    for spec, name in zip(refs, ("nodes", "edges", "graph"), strict=enabled):
        assert spec.artifact_id == f"input:reference:{name}"
        assert spec.path == f"inputs/reference/{name}/same.csv"
        assert spec.role == f"reference_{name}" and spec.condition is None


def test_optional_structure_absent(tmp_path):
    runtime = make_runtime(tmp_path, ("normal",))
    loaded = runtime.runtime_load_result
    source = replace(
        loaded.condition_results[0].runtime_input, reference_structure_path=None
    )
    runtime = replace(
        runtime,
        runtime_load_result=replace(
            loaded,
            condition_results=(
                replace(loaded.condition_results[0], runtime_input=source),
            ),
        ),
    )
    assert len(adapter.collect_preprocessing_input_file_specs(runtime)) == 4


@pytest.mark.parametrize("filename", ["no_suffix", "file.", "file.µ", "bad\\file.xtc"])
def test_bad_input_filename_errors_are_portable(tmp_path, filename):
    runtime = replace(make_runtime(tmp_path), manifest_path=tmp_path / filename)
    with pytest.raises(adapter.PreprocessingArtifactInventoryError) as error:
        adapter.collect_preprocessing_input_file_specs(runtime)
    assert str(error.value) == "Invalid input file metadata for 'input:manifest'."
    assert str(tmp_path) not in str(error.value)


def test_complete_inputs_survive_failed_load(tmp_path):
    runtime = make_runtime(tmp_path, failed=True)
    assert not runtime.runtime_load_result.passed
    specs = adapter.collect_preprocessing_input_file_specs(runtime)
    assert len(specs) == 9


@pytest.mark.parametrize("missing", ["record", "input", "all", "mismatch", "duplicate"])
def test_incomplete_inputs_are_rejected(tmp_path, missing):
    runtime = make_runtime(tmp_path)
    loaded = runtime.runtime_load_result
    records = loaded.condition_results
    if missing == "record":
        records = records[:1]
    elif missing == "input":
        records = (replace(records[0], runtime_input=None), records[1])
    elif missing == "mismatch":
        records = (
            replace(records[0], runtime_input=records[1].runtime_input),
            records[1],
        )
    elif missing == "duplicate":
        records = (records[0], records[0])
    runtime = replace(
        runtime,
        runtime_load_result=(
            None if missing == "all" else replace(loaded, condition_results=records)
        ),
    )
    with pytest.raises(adapter.PreprocessingArtifactInventoryError, match="Complete"):
        adapter.collect_preprocessing_input_file_specs(runtime)


def test_all_authoritative_outputs_in_stage_order(tmp_path, monkeypatch):
    runtime = make_runtime(tmp_path)
    root = tmp_path / "out"
    stages = make_stages(root, runtime)
    write_small(root / "unrelated.csv")
    before = {name: value.to_dict() for name, value in stages.items()}
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        patch.setattr(Path, "stat", forbid)
        patch.setattr(Path, "open", forbid)
        specs = adapter.collect_preprocessing_output_file_specs(
            output_root=root, **stages
        )
    assert [s.role for s in specs] == [
        "graph_nodes",
        "graph_edges",
        "graph_json",
        "residue_table",
        "residue_table",
        "protein_contact_edges",
        "protein_contact_edges",
        "protein_contacts_perframe",
        "protein_contacts_perframe",
        "edge_semantics",
        "residue_library",
        "preprocessing_manifest",
        "rg_timeseries",
        "contact_edges",
        "contacts_perframe",
        "graph_diagnostics_report",
        "reference_comparison_report",
    ]
    for spec in specs:
        assert spec.path == spec.local_path.relative_to(root).as_posix()
        assert spec.path not in (
            "artifact_inventory.json",
            "run_provenance.json",
            "unrelated.csv",
        )
    assert [s.condition for s in specs[3:9]] == ["normal", "tumor"] * 3
    assert specs[4].artifact_id == "output:condition:0002:residue_table"
    assert before == {name: value.to_dict() for name, value in stages.items()}


@pytest.mark.parametrize(
    "name",
    [
        "graph_export",
        "analysis_input_export",
        "scientific_csv_export",
        "diagnostics",
        "reference_comparison",
    ],
)
def test_failed_stage_never_claims_partial_files(tmp_path, name):
    stages = make_stages(tmp_path / "out", make_runtime(tmp_path))
    stage = stages[name]
    # Every result gates passed on its issue tuple; paths and partial writes remain.
    failed = replace(
        stage,
        **{
            "graph_export": {"nodes_csv_write_result": SimpleNamespace(passed=False)},
            "analysis_input_export": {"manifest_artifacts_result": None},
            "scientific_csv_export": {"contact_edges_write_result": None},
            "diagnostics": {"diagnostics_run_result": None},
            "reference_comparison": {"reference_comparison_result": None},
        }[name],
    )
    assert not failed.passed
    assert (
        adapter.collect_preprocessing_output_file_specs(
            output_root=tmp_path / "out",
            **{name: failed},
        )
        == ()
    )
    assert (
        adapter.collect_preprocessing_output_file_specs(output_root=tmp_path / "out")
        == ()
    )


@pytest.mark.parametrize(
    "name,field",
    [
        ("diagnostics", "diagnostics_report_json"),
        ("reference_comparison", "reference_comparison_json"),
    ],
)
def test_reports_require_write_setting(tmp_path, name, field):
    stages = make_stages(tmp_path / "out", make_runtime(tmp_path))
    stage = replace(stages[name], **{f"{field}_path": None, f"{field}_written": False})
    assert stage.passed
    assert (
        adapter.collect_preprocessing_output_file_specs(
            output_root=tmp_path / "out",
            **{name: stage},
        )
        == ()
    )


def test_scientific_exports_only_requested_outputs(tmp_path):
    stages = make_stages(tmp_path / "out", make_runtime(tmp_path))
    stage = replace(
        stages["scientific_csv_export"],
        export_contact_edges=False,
        export_contacts_perframe=False,
    )
    specs = adapter.collect_preprocessing_output_file_specs(
        output_root=tmp_path / "out",
        scientific_csv_export=stage,
    )
    assert [s.role for s in specs] == ["rg_timeseries"]


@pytest.mark.parametrize(
    "path",
    [
        "../elsewhere.csv",
        "nested/../../elsewhere.csv",
        "run_provenance.json",
        "artifact_inventory.json",
    ],
)
def test_output_path_rejections(tmp_path, path):
    graph = _graph_export_result(tmp_path, ("normal",))
    graph = replace(graph, graph_nodes_csv_path=tmp_path / path)
    with pytest.raises(
        adapter.PreprocessingArtifactInventoryError, match="Output path"
    ):
        adapter.collect_preprocessing_output_file_specs(
            output_root=tmp_path, graph_export=graph
        )


def test_relative_layout_and_symlink_are_not_resolved(tmp_path, monkeypatch):
    graph = _graph_export_result(Path("out"), ("normal",))
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        specs = adapter.collect_preprocessing_output_file_specs(
            output_root=Path("out"),
            graph_export=graph,
        )
    assert specs[0].path == "graph/nodes.csv"
    runtime = make_runtime(tmp_path)
    target = write_small(tmp_path / "external.csv")
    link = tmp_path / "out/graph/nodes.csv"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    graph = replace(
        graph,
        graph_nodes_csv_path=link,
        graph_edges_csv_path=write_small(link.parent / "edges.csv"),
        graph_json_path=write_small(link.parent / "graph.json"),
    )
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        inventory = adapter.build_preprocessing_artifact_inventory(
            run_id="symlink",
            runtime_loading=runtime,
            output_root=tmp_path / "out",
            graph_export=graph,
        )
    assert inventory.artifacts[-3].path == "graph/nodes.csv"


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_builder_delegates_without_changing_science(tmp_path, monkeypatch, mode):
    runtime = make_runtime(tmp_path)
    stages = make_stages(tmp_path / "out", runtime)
    generic = Mock(wraps=inventory_io.build_artifact_inventory)
    monkeypatch.setattr(adapter, "build_artifact_inventory", generic)
    hashed = (
        Mock(wraps=inventory_io.stream_file_sha256)
        if mode == "sha256"
        else Mock(side_effect=forbid)
    )
    monkeypatch.setattr(inventory_io, "stream_file_sha256", hashed)
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        if mode == "none":
            patch.setattr(Path, "open", forbid)
        inventory = adapter.build_preprocessing_artifact_inventory(
            run_id="experiment",
            runtime_loading=runtime,
            output_root=tmp_path / "out",
            checksum_mode=mode,
            **stages,
        )
    generic.assert_called_once()
    args = generic.call_args.kwargs
    assert args["checksum_mode"] == mode
    assert inventory.run_id == "experiment"
    assert inventory.workflow == PREPROCESSING_RUN_PROVENANCE_WORKFLOW
    assert inventory.inventory_path == "artifact_inventory.json"
    assert [s.direction for s in args["file_specs"]] == ["input"] * 9 + ["output"] * 17
    assert hashed.call_count == (inventory.artifact_count if mode == "sha256" else 0)
    for spec, entry in zip(args["file_specs"], inventory.artifacts, strict=True):
        assert entry.byte_size == spec.local_path.stat().st_size
        assert entry.sha256 == (
            hashlib.sha256(spec.local_path.read_bytes()).hexdigest()
            if mode == "sha256"
            else None
        )


@pytest.mark.parametrize("runtime,pbc", [(True, True), (True, False), (False, True)])
def test_explicit_technical_output_paths_are_appended_without_discovery(
    monkeypatch, tmp_path, runtime, pbc,
):
    root = tmp_path / "out"
    known = {
        "runtime_metadata_path": root / "runtime_metadata.json" if runtime else None,
        "pbc_audit_path": root / "pbc_audit.json" if pbc else None,
    }
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        patch.setattr(Path, "stat", forbid)
        patch.setattr(Path, "open", forbid)
        specs = adapter.collect_preprocessing_output_file_specs(
            output_root=root, **known,
        )
    roles = (["runtime_metadata"] if runtime else []) + (["pbc_audit"] if pbc else [])
    assert [s.role for s in specs] == roles
    for spec in specs:
        assert spec.artifact_id == f"output:{spec.role}"
        assert spec.path == f"{spec.role}.json" and spec.format == "json"
        assert spec.local_path is known[f"{spec.role}_path"]
        assert spec.condition is None
    assert adapter.collect_preprocessing_output_file_specs(output_root=root) == ()


@pytest.mark.parametrize("field", ["runtime_metadata_path", "pbc_audit_path"])
def test_technical_outputs_reject_noncanonical_paths(tmp_path, field):
    role = field.removesuffix("_path")
    with pytest.raises(adapter.PreprocessingArtifactInventoryError):
        adapter.collect_preprocessing_output_file_specs(
            output_root=tmp_path, **{field: tmp_path / "nested" / f"{role}.json"},
        )


@pytest.mark.parametrize("mode", ["none", "sha256"])
@pytest.mark.parametrize("failed", [False, True])
def test_dataset_table_explicit_portable_input_and_checksum(
    tmp_path, monkeypatch, mode, failed
):
    from test_preprocessing_dataset_binding import spec, write_table

    runtime = make_runtime(tmp_path, failed=failed)
    table = write_table(tmp_path / "private-source-name.csv", spec())
    content = table.read_bytes()
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if mode == "none" and path == table:
            raise AssertionError("Size-only inventory must not reread table content")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    inventory = adapter.build_preprocessing_artifact_inventory(
        run_id="dataset",
        runtime_loading=runtime,
        output_root=tmp_path / "out",
        checksum_mode=mode,
        parameter_table_local_path=table,
    )
    matches = [
        entry
        for entry in inventory.artifacts
        if entry.role == "dataset_parameter_table"
    ]
    assert len(matches) == 1
    item = matches[0]
    assert item.artifact_id == "input:dataset_parameter_table"
    assert item.path == "inputs/dataset/parameter_table.csv"
    assert item.direction == "input" and item.format == "csv" and item.condition is None
    assert item.byte_size == len(content)
    assert item.sha256 == (
        hashlib.sha256(content).hexdigest() if mode == "sha256" else None
    )
    assert str(table) not in str(inventory.to_dict())
    assert table.name not in str(inventory.to_dict())
    assert all(entry.direction == "input" for entry in inventory.artifacts)
    plain = adapter.collect_preprocessing_input_file_specs(runtime)
    assert "dataset_parameter_table" not in [entry.role for entry in plain]


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_source_table_exact_supplied_path_order_checksum_and_no_scan(
    tmp_path, monkeypatch, mode
):
    runtime = make_runtime(tmp_path)
    root = tmp_path / "out"
    path = write_small(
        root / "protein_edges_by_window_source.csv", b"controlled source table\n"
    )
    temporal = write_small(root / "temporal_execution.json")
    before = adapter.build_preprocessing_artifact_inventory(
        run_id="test",
        runtime_loading=runtime,
        output_root=root,
        checksum_mode=mode,
    ).to_dict()
    if mode == "none":
        monkeypatch.setattr(
            inventory_io, "stream_file_sha256", Mock(side_effect=AssertionError)
        )
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        value = adapter.build_preprocessing_artifact_inventory(
            run_id="test",
            runtime_loading=runtime,
            output_root=root,
            checksum_mode=mode,
            protein_edges_by_window_source_path=path,
            temporal_execution_path=temporal,
        )
        without = adapter.build_preprocessing_artifact_inventory(
            run_id="test",
            runtime_loading=runtime,
            output_root=root,
            checksum_mode=mode,
        )
    assert (
        without.to_dict() == before
    )  # An existing unrequested table is never scanned in.
    entry = value.artifacts[-2]
    assert entry.artifact_id == "output:protein_edges_by_window_source"
    assert entry.role == "protein_edges_by_window_source" and entry.format == "csv"
    assert (
        entry.path == path.name
        and entry.condition is None
        and entry.direction == "output"
    )
    assert entry.byte_size == path.stat().st_size
    assert entry.sha256 == (
        hashlib.sha256(path.read_bytes()).hexdigest() if mode == "sha256" else None
    )
    assert value.artifacts[-1].role == "temporal_execution"
    with pytest.raises(adapter.PreprocessingArtifactInventoryError):
        adapter.collect_preprocessing_output_file_specs(
            output_root=root,
            protein_edges_by_window_source_path=root / "other.csv",
        )
