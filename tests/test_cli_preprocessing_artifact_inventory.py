"""CLI inventory emission, explicit hashing, and conservative failure boundaries."""

import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_graph_workflow import (
    END,
    STAGE15_ORDER,
    STAGE15_ORDER_WITH_ANALYSIS_AND_SCIENTIFIC,
    START,
    VERBOSE_STAGE_MESSAGES,
    install_fake_stage15,
    invoke_cli,
)
from test_preprocessing_artifact_inventory import (
    forbid,
    guard_discovery,
    make_runtime,
    make_stages,
    write_small,
)

import mania.artifact_inventory_io as inventory_io
import mania.cli as cli
import mania.preprocessing.artifact_inventory as adapter
import mania.preprocessing.pbc_audit_io as cli_pbc_io
import mania.runtime_metadata_io as cli_runtime_io
from mania.preprocessing.pbc_audit_io import write_pbc_audit
from mania.preprocessing.run_provenance import (
    PREPROCESSING_RUN_FAILURE_STAGES,
    build_completed_preprocessing_run_provenance,
    build_failed_preprocessing_run_provenance,
)
from mania.preprocessing.runtime_metadata import build_preprocessing_runtime_metadata
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowRuntimeLoadingIssue,
)
from mania.run_provenance_io import RunProvenanceWriteResult, write_run_provenance
from mania.runtime_metadata_io import write_runtime_metadata

INVENTORY_REF = {"role": "artifact_inventory", "path": "artifact_inventory.json"}


def stub_legacy_manifest_load(monkeypatch, runtime):
    """Keep checksum guards scoped to inventory, as with the stubbed runtime load."""
    from mania.preprocessing.input_manifest import PreprocessingInputManifest

    manifest = PreprocessingInputManifest.model_validate({
        "output_root": "out",
        "conditions": [
            {
                "condition": result.condition_name,
                "topology_path": result.runtime_input.topology_path,
                "trajectory_paths": result.runtime_input.trajectory_paths,
            }
            for result in runtime.runtime_load_result.condition_results
        ],
    })
    monkeypatch.setattr(
        cli, "load_preprocessing_input_manifest", Mock(return_value=manifest)
    )


def command(root, *extra, all_stages=False):
    args = [
        "preprocessing",
        "run-graph-export",
        "--manifest",
        str(root / "source/manifest.yaml"),
        "--output",
        str(root / "out"),
        "--run-name",
        "inventory-test",
    ]
    if all_stages:
        args += [
            "--contact-selection",
            "protein",
            "--export-analysis-inputs",
            "--export-scientific-csvs",
            "--export-contacts-perframe",
            "--enable-reference-comparison",
            "--reference-nodes",
            str(root / "reference/nodes.csv"),
            "--reference-edges",
            str(root / "reference/edges.csv"),
            "--reference-graph-json",
            str(root / "reference/graph.json"),
        ]
    return (*args, *extra)


def install_inventory_workflow(monkeypatch, root, *, failure=None, incomplete=False):
    calls, received = install_fake_stage15(monkeypatch, failing_stage=failure)
    runtime = make_runtime(root, failed=failure == "runtime_loading")
    stages = make_stages(root / "out", runtime)
    computation = stages["graph_export"].computation
    if failure == "runtime_loading":
        runtime = replace(
            runtime,
            issues=(
                PreprocessingGraphWorkflowRuntimeLoadingIssue(
                    kind="runtime_load_failed",
                    message="Synthetic loading failure.",
                ),
            ),
        )
        if incomplete:
            runtime = replace(
                runtime,
                runtime_load_result=replace(
                    runtime.runtime_load_result,
                    condition_results=runtime.runtime_load_result.condition_results[:1],
                ),
            )
    if failure == "computation":
        computation = replace(computation, contacts_result=None)
    changes = {
        "graph_export": {"nodes_csv_write_result": None},
        "analysis_input_export": {"manifest_artifacts_result": None},
        "scientific_csv_export": {"contact_edges_write_result": None},
        "diagnostics": {"diagnostics_run_result": None},
        "reference_comparison": {"reference_comparison_result": None},
    }
    if failure in changes:
        stages[failure] = replace(stages[failure], **changes[failure])
    replacements = {
        "load_preprocessing_graph_workflow_condition_runtimes": runtime,
        "compute_preprocessing_graph_workflow_rg_contacts": computation,
        "export_preprocessing_graph_workflow_artifacts": stages["graph_export"],
        "export_preprocessing_graph_workflow_analysis_inputs": stages[
            "analysis_input_export"
        ],
        "export_preprocessing_graph_workflow_scientific_csvs": stages[
            "scientific_csv_export"
        ],
        "run_preprocessing_graph_workflow_diagnostics": stages["diagnostics"],
        "compare_preprocessing_graph_workflow_reference_artifacts": stages[
            "reference_comparison"
        ],
    }
    for name, result in replacements.items():
        original = getattr(cli, name)

        def stage(*args, _original=original, _result=result, **kwargs):
            _original(*args, **kwargs)
            return _result

        monkeypatch.setattr(cli, name, stage)
    for name, key, function in (
        ("build_preprocessing_runtime_metadata", "runtime_builder",
         build_preprocessing_runtime_metadata),
        ("write_runtime_metadata", "runtime_writer", write_runtime_metadata),
        ("write_pbc_audit", "pbc_writer", write_pbc_audit),
        (
            "build_preprocessing_artifact_inventory",
            "inventory_builder",
            adapter.build_preprocessing_artifact_inventory,
        ),
        (
            "write_artifact_inventory",
            "inventory_writer",
            inventory_io.write_artifact_inventory,
        ),
        (
            "build_completed_preprocessing_run_provenance",
            "provenance_builder",
            build_completed_preprocessing_run_provenance,
        ),
        (
            "build_failed_preprocessing_run_provenance",
            "failed_provenance_builder",
            build_failed_preprocessing_run_provenance,
        ),
        ("write_run_provenance", "provenance_writer", write_run_provenance),
    ):
        received[key] = Mock(wraps=function)
        monkeypatch.setattr(cli, name, received[key])
    received["runtime"] = runtime
    received["stages"] = stages
    return calls, received


def test_parser_defaults_choices_and_single_checksum_option(
    monkeypatch, capsys, tmp_path
):
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbid)
        patch.setattr(Path, "stat", forbid)
        patch.setattr(cli, "get_software_identity", forbid)
        patch.setattr(cli, "_utc_now", forbid)
        parser = cli.build_parser()
        assert parser.parse_args(command(tmp_path)).artifact_checksum_mode == "none"
        assert (
            parser.parse_args(
                command(tmp_path, "--artifact-checksum-mode", "sha256")
            ).artifact_checksum_mode
            == "sha256"
        )
        with pytest.raises(SystemExit) as error:
            parser.parse_args(command(tmp_path, "--artifact-checksum-mode", "md5"))
        assert error.value.code == 2
        capsys.readouterr()
        with pytest.raises(SystemExit) as error:
            parser.parse_args(["preprocessing", "run-graph-export", "--help"])
        assert error.value.code == 0
    help_text = capsys.readouterr().out
    normalized = " ".join(help_text.split())
    assert "none records exact sizes without reading file contents" in normalized
    assert "sha256 streams all inventoried files including trajectories" in normalized
    assert "expensive for large MD datasets" in normalized
    options = {
        word.split("=")[0] for word in help_text.split() if word.startswith("--")
    }
    assert {
        opt
        for opt in options
        if "checksum" in opt or "integrity" in opt or "publication" in opt
    } == {"--artifact-checksum-mode"}


@pytest.mark.parametrize(
    "extra",
    [
        ("--artifact-checksum-mode", "bad"),
        ("--frame-stride", "0"),
        ("--export-analysis-inputs", "--skip-contacts"),
        ("--export-analysis-inputs",),
    ],
)
def test_invalid_execution_never_builds_inventory(monkeypatch, capsys, tmp_path, extra):
    _, received = install_fake_stage15(monkeypatch)
    invoke_cli(monkeypatch, capsys, *command(tmp_path, *extra), expected_exit_code=2)
    for name in ("inventory_builder", "inventory_writer", "identity", "clock"):
        received[name].assert_not_called()
    assert not (tmp_path / "out/artifact_inventory.json").exists()


@pytest.mark.parametrize("overwrite", [False, True])
def test_default_run_preserves_stdout_order_verbose_and_timing(
    monkeypatch, capsys, tmp_path, overwrite
):
    calls, received = install_inventory_workflow(monkeypatch, tmp_path)
    stub_legacy_manifest_load(monkeypatch, received["runtime"])
    original_options = cli._build_preprocessing_graph_workflow_options
    monkeypatch.setattr(
        cli,
        "_build_preprocessing_graph_workflow_options",
        lambda args: replace(
            original_options(args),
            overwrite=overwrite,
        ),
    )
    events = []
    received["clock"].side_effect = lambda: (
        events.append(("clock", tuple(calls))) or (START if len(events) == 1 else END)
    )
    builder = received["inventory_builder"]

    def build(**kwargs):
        assert events == [("clock", ()), ("clock", STAGE15_ORDER)]
        assert received["provenance_builder"].call_count == 0
        return adapter.build_preprocessing_artifact_inventory(**kwargs)

    builder.side_effect = build
    hashed = Mock(side_effect=forbid)
    monkeypatch.setattr(inventory_io, "stream_file_sha256", hashed)
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        patch.setattr(Path, "open", forbid)
        _, stdout, stderr = invoke_cli(
            monkeypatch, capsys, *command(tmp_path, "--verbose")
        )
    assert tuple(calls) == STAGE15_ORDER
    assert [line for line in stderr.splitlines() if "/7]" in line] == [
        f"{message}..." for message in VERBOSE_STAGE_MESSAGES
    ]
    builder.assert_called_once()
    assert builder.call_args.kwargs["checksum_mode"] == "none"
    assert builder.call_args.kwargs["runtime_loading"] is received["runtime"]
    received["inventory_writer"].assert_called_once()
    assert received["inventory_writer"].call_args.args[1] == tmp_path / "out"
    assert received["inventory_writer"].call_args.kwargs == {"overwrite": overwrite}
    received["identity"].assert_called_once_with()
    assert received["clock"].call_count == 2
    hashed.assert_not_called()
    supplied = received["provenance_builder"].call_args.kwargs
    assert supplied["ended_at_utc"] == END
    assert supplied["artifact_references"][-1].to_dict() == INVENTORY_REF
    assert '"artifact_inventory"' not in stdout and '"checksum_mode"' not in stdout
    # Repeat the identical scientific workflow with the original no-I/O metadata fakes.
    _, baseline = install_inventory_workflow(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "write_runtime_metadata", Mock(return_value=
        cli_runtime_io.RuntimeMetadataWriteResult(
            tmp_path / "out/runtime_metadata.json", True)))
    monkeypatch.setattr(cli, "write_pbc_audit", Mock(return_value=
        cli_pbc_io.PbcAuditWriteResult(tmp_path / "out/pbc_audit.json", True)))

    monkeypatch.setattr(
        cli,
        "write_artifact_inventory",
        Mock(
            return_value=inventory_io.ArtifactInventoryWriteResult(
                tmp_path / "out/artifact_inventory.json", True
            )
        ),
    )
    monkeypatch.setattr(
        cli,
        "write_run_provenance",
        Mock(
            return_value=RunProvenanceWriteResult(
                tmp_path / "out/run_provenance.json", True
            )
        ),
    )
    _, baseline_stdout, baseline_stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path, "--verbose")
    )
    assert stdout == baseline_stdout and stderr == baseline_stderr


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_real_inventory_and_provenance_smoke(monkeypatch, capsys, tmp_path, mode):
    calls, received = install_inventory_workflow(monkeypatch, tmp_path)
    stub_legacy_manifest_load(monkeypatch, received["runtime"])
    root = tmp_path / "out"
    write_small(root / "unrelated.csv", b"unrelated")
    write_small(root / "analysis/old.json", b"old analysis")
    generic = Mock(wraps=inventory_io.build_artifact_inventory)
    monkeypatch.setattr(adapter, "build_artifact_inventory", generic)
    reads = []
    real_open = Path.open

    class BoundedReader(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= inventory_io.ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE
            reads.append(size)
            return super().read(size)

    def bounded_open(path, mode="r", *args, **kwargs):
        assert mode == "rb"
        assert path.name not in ("artifact_inventory.json", "run_provenance.json")
        with real_open(path, mode) as stream:
            return BoundedReader(stream.read())

    with monkeypatch.context() as patch:
        guard_discovery(patch)
        patch.setattr(Path, "open", bounded_open if mode == "sha256" else forbid)
        _, stdout, stderr = invoke_cli(
            monkeypatch,
            capsys,
            *command(tmp_path, "--artifact-checksum-mode", mode, all_stages=True),
        )
    assert stderr == "" and json.loads(stdout)["passed"] is True
    assert tuple(calls) == STAGE15_ORDER_WITH_ANALYSIS_AND_SCIENTIFIC
    assert generic.call_args.kwargs["checksum_mode"] == mode
    payload = json.loads((root / "artifact_inventory.json").read_text())
    assert payload["checksum_mode"] == mode
    specs = generic.call_args.kwargs["file_specs"]
    assert payload["artifact_count"] == len(specs) == 31
    assert (
        payload["input_artifact_count"] == 12 and payload["output_artifact_count"] == 19
    )
    for spec, entry in zip(specs, payload["artifacts"], strict=True):
        assert entry["byte_size"] == len(spec.local_path.read_bytes())
        assert entry["sha256"] == (
            hashlib.sha256(spec.local_path.read_bytes()).hexdigest()
            if mode == "sha256"
            else None
        )
        assert not entry["path"].startswith("/") and str(tmp_path) not in entry["path"]
    assert bool(reads) == (mode == "sha256")
    assert all(
        entry["path"]
        not in (
            "artifact_inventory.json",
            "run_provenance.json",
            "unrelated.csv",
            "analysis/old.json",
        )
        for entry in payload["artifacts"]
    )
    assert (
        INVENTORY_REF
        in json.loads((root / "run_provenance.json").read_text())["artifact_references"]
    )
    assert not (root / "checksums.sha256").exists()
    assert not list(root.glob(".artifact_inventory.json.*.tmp"))


@pytest.mark.parametrize("failure", ["build", "write", "write_exception", "exists"])
@pytest.mark.parametrize("provenance_failure", [None, "build", "write"])
def test_inventory_failure_after_scientific_success_attempts_completed_provenance(
    monkeypatch,
    capsys,
    tmp_path,
    failure,
    provenance_failure,
):
    _, received = install_inventory_workflow(monkeypatch, tmp_path)
    root = tmp_path / "out"
    if failure == "build":
        received["inventory_builder"].side_effect = ValueError(f"private {tmp_path}")
    elif failure == "write":
        original_link = inventory_io.os.link

        def fail_inventory_link(source, target):
            if Path(target).name == "artifact_inventory.json":
                raise OSError("private")
            return original_link(source, target)

        monkeypatch.setattr(inventory_io.os, "link", fail_inventory_link)
    elif failure == "write_exception":
        received["inventory_writer"].side_effect = OSError(f"private {tmp_path}")
    else:
        write_small(root / "artifact_inventory.json", b"existing inventory")
    if provenance_failure:
        received[
            f"provenance_{'builder' if provenance_failure == 'build' else 'writer'}"
        ].side_effect = RuntimeError("private")
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert stdout == ""
    lines = stderr.splitlines()
    expected = "build" if failure == "build" else "write"
    assert lines[0].startswith(f"Artifact inventory {expected} failed:")
    assert "private" not in stderr and str(tmp_path) not in stderr
    assert len(lines) == (2 if provenance_failure else 1)
    if provenance_failure:
        assert lines[1].startswith(f"Run provenance {provenance_failure} failed:")
    received["provenance_builder"].assert_called_once()
    if provenance_failure != "build":
        received["provenance_writer"].assert_called_once()
        passport = received["provenance_writer"].call_args.args[0]
        assert passport.status == "completed"
        assert INVENTORY_REF not in [r.to_dict() for r in passport.artifact_references]
    if failure == "exists":
        assert (root / "artifact_inventory.json").read_bytes() == b"existing inventory"
    else:
        assert not (root / "artifact_inventory.json").exists()
    assert (root / "graph/nodes.csv").read_bytes() == b"synthetic\n"
    assert not list(root.glob(".artifact_inventory.json.*.tmp"))


# Stage 28 failures use real Dataset execution in the dedicated export suite.
@pytest.mark.parametrize(
    "stage",
    tuple(
        stage
        for stage in PREPROCESSING_RUN_FAILURE_STAGES
        if stage
        not in (
            "protein_edge_window_export",
            "specialized_contact_export",
            "canonical_table_export",
            "annotated_table_export",
        )
    ),
)
@pytest.mark.parametrize("inventory_failure", [None, "build", "write"])
def test_failed_workflow_inventory_preserves_primary_failure(
    monkeypatch,
    capsys,
    tmp_path,
    stage,
    inventory_failure,
):
    _, received = install_inventory_workflow(monkeypatch, tmp_path, failure=stage)
    if inventory_failure == "build":
        received["inventory_builder"].side_effect = ValueError("private")
    elif inventory_failure == "write":
        received["inventory_writer"].side_effect = OSError("private")
    with monkeypatch.context() as patch:
        guard_discovery(patch)
        _, stdout, stderr = invoke_cli(
            monkeypatch,
            capsys,
            *command(tmp_path, all_stages=True),
            expected_exit_code=1,
        )
    for name in ("environment", "runtime_builder", "runtime_writer",
                 "pbc_builder", "pbc_writer"):
        received[name].assert_not_called()
    assert json.loads(stdout)["stage"] == stage
    assert json.loads(stdout)["passed"] is False
    received["failed_provenance_builder"].assert_called_once()
    received["provenance_writer"].assert_called_once()
    passport = received["provenance_writer"].call_args.args[0]
    assert passport.status == "failed" and passport.issues[0].stage == stage
    refs = [r.to_dict() for r in passport.artifact_references]
    expected_counts = dict(
        plan=0,
        runtime_loading=0,
        computation=0,
        graph_export=0,
        analysis_input_export=3,
        scientific_csv_export=12,
        diagnostics=15,
        reference_comparison=16,
    )
    target = tmp_path / "out/artifact_inventory.json"
    if stage == "plan":
        received["inventory_builder"].assert_not_called()
        assert not target.exists() and INVENTORY_REF not in refs
    else:
        received["inventory_builder"].assert_called_once()
        if inventory_failure:
            assert f"Artifact inventory {inventory_failure} failed:" in stderr
            assert INVENTORY_REF not in refs and not target.exists()
        else:
            payload = json.loads(target.read_text())
            assert payload["input_artifact_count"] == 12
            assert payload["output_artifact_count"] == expected_counts[stage]
            assert INVENTORY_REF in refs
            assert "Artifact inventory" not in stderr
    # Compare the exact original failure stdout and stderr to a metadata-free run.
    install_inventory_workflow(monkeypatch, tmp_path, failure=stage)
    monkeypatch.setattr(
        cli, "_preprocessing_inventory_inputs_available", lambda result: False
    )
    monkeypatch.setattr(
        cli,
        "write_run_provenance",
        Mock(
            return_value=RunProvenanceWriteResult(
                tmp_path / "out/run_provenance.json", True
            )
        ),
    )
    _, original_stdout, original_stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path, all_stages=True),
        expected_exit_code=1,
    )
    assert stdout == original_stdout
    assert "\n".join(
        line
        for line in stderr.splitlines()
        if not line.startswith("Artifact inventory")
    ) == original_stderr.rstrip("\n")


def test_incomplete_failed_loading_skips_inventory(monkeypatch, capsys, tmp_path):
    _, received = install_inventory_workflow(
        monkeypatch, tmp_path, failure="runtime_loading", incomplete=True
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *command(tmp_path), expected_exit_code=1
    )
    assert json.loads(stdout)["stage"] == "runtime_loading" and stderr == ""
    received["inventory_builder"].assert_not_called()
    received["inventory_writer"].assert_not_called()
    passport = json.loads((tmp_path / "out/run_provenance.json").read_text())
    assert (
        passport["status"] == "failed"
        and INVENTORY_REF not in passport["artifact_references"]
    )


def test_sha256_stdout_is_identical_to_default(monkeypatch, capsys, tmp_path):
    original_options = cli._build_preprocessing_graph_workflow_options
    monkeypatch.setattr(
        cli,
        "_build_preprocessing_graph_workflow_options",
        lambda args: replace(original_options(args), overwrite=True),
    )
    install_inventory_workflow(monkeypatch, tmp_path)
    _, default_stdout, default_stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path),
    )
    install_inventory_workflow(monkeypatch, tmp_path)
    _, sha_stdout, sha_stderr = invoke_cli(
        monkeypatch,
        capsys,
        *command(tmp_path, "--artifact-checksum-mode", "sha256"),
    )
    assert sha_stderr == default_stderr == ""
    assert sha_stdout == default_stdout
