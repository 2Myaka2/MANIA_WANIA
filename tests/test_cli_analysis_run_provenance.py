"""Analysis CLI provenance is additive, portable, and isolated from preprocessing."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_analysis_artifact_inventory import declared_inputs
from test_analysis_run_provenance import END, IDENTITY, START, analysis_result
from test_cli_analyze import _write_stage20_root

import mania.cli as cli
from mania.analysis.orchestration import AnalyzeError, AnalyzeRequest
from mania.artifact_inventory_io import ArtifactInventoryWriteResult
from mania.run_provenance_io import RunProvenanceWriteResult


@pytest.fixture
def execution(monkeypatch, tmp_path):
    request = AnalyzeRequest(
        tmp_path / "prepared", tmp_path / "out", ("tumor", "normal")
    )
    result = analysis_result(request)
    clock = Mock(side_effect=[START, END])
    identity = Mock(return_value=IDENTITY)
    run = Mock(return_value=result)
    # Isolate Stage 25.B emission tests from C.3 I/O; the C.3 suite exercises
    # real resolution, inventories, and atomic writing separately.
    monkeypatch.setattr(
        cli, "resolve_analysis_input_paths", Mock(side_effect=declared_inputs)
    )
    monkeypatch.setattr(
        cli, "build_analysis_artifact_inventory", Mock(return_value=object())
    )
    monkeypatch.setattr(
        cli, "write_artifact_inventory",
        Mock(return_value=ArtifactInventoryWriteResult(
            request.output_root / "analysis/artifact_inventory.json", True,
        )),
    )
    completed = Mock(wraps=cli.build_completed_analysis_run_provenance)
    failed = Mock(wraps=cli.build_failed_analysis_run_provenance)
    writer = Mock(wraps=cli.write_run_provenance)
    for name, value in (
        ("_utc_now", clock),
        ("get_software_identity", identity),
        ("run_analysis", run),
        ("build_completed_analysis_run_provenance", completed),
        ("build_failed_analysis_run_provenance", failed),
        ("write_run_provenance", writer),
    ):
        monkeypatch.setattr(cli, name, value)
    forbidden = Mock(side_effect=AssertionError("Preprocessing must not run"))
    monkeypatch.setattr(cli, "build_completed_preprocessing_run_provenance", forbidden)
    monkeypatch.setattr(cli, "build_failed_preprocessing_run_provenance", forbidden)
    return request, result, clock, identity, run, completed, failed, writer


def invoke(monkeypatch, capsys, request, *, options=(), equals=False, code=0):
    paths = (
        [f"--input={request.input_root}", f"--output={request.output_root}"]
        if equals
        else ["--input", str(request.input_root), "--output", str(request.output_root)]
    )
    argv = ["/private/venv/bin/mania", "analyze", *paths]
    for condition in request.conditions:
        argv.extend(("--condition", condition))
    argv.extend(options)
    original = argv.copy()
    monkeypatch.setattr(sys, "argv", argv)
    if code:
        with pytest.raises(SystemExit) as error:
            cli.main()
        assert error.value.code == code
    else:
        cli.main()
    assert sys.argv == original
    return capsys.readouterr()


def assert_context(clock, identity, builder):
    assert clock.call_count == 2
    identity.assert_called_once_with()
    assert builder.call_count == 1
    supplied = builder.call_args.kwargs
    assert supplied["run_id"] == "analysis-20260906T120304123456Z"
    assert supplied["started_at_utc"] == START
    assert supplied["ended_at_utc"] == END
    assert supplied["software_identity"] is IDENTITY


@pytest.mark.parametrize("equals", [False, True])
@pytest.mark.parametrize("same_root", [False, True])
@pytest.mark.parametrize(
    "options,enable_pca,basis,components",
    [
        ((), False, "fingerprint", None),
        (("--enable-pca",), True, "fingerprint", None),
        (
            (
                "--enable-pca",
                "--clustering-basis",
                "pca",
                "--pca-components-for-clustering",
                "4",
            ),
            True,
            "pca",
            4,
        ),
    ],
)
def test_completed_real_writer_preserves_stdout_and_root(
    monkeypatch,
    capsys,
    execution,
    equals,
    same_root,
    options,
    enable_pca,
    basis,
    components,
):
    request, _, clock, identity, run, completed, failed, writer = execution
    request = replace(
        request,
        enable_pca=enable_pca,
        clustering_basis=basis,
        pca_components_for_clustering=components,
    )
    if same_root:
        request = replace(request, input_root=request.output_root)
    result = analysis_result(request)
    run.return_value = result
    request.output_root.mkdir()
    sentinel = request.output_root / "run_provenance.json"
    sentinel.write_bytes(b"existing preprocessing provenance\n")
    captured = invoke(monkeypatch, capsys, request, equals=equals, options=options)
    run.assert_called_once_with(request, resolved_input_paths=declared_inputs(request))
    assert_context(clock, identity, completed)
    failed.assert_not_called()
    assert writer.call_count == 1
    assert writer.call_args.args[1] == result.analysis_root
    assert writer.call_args.kwargs == {"overwrite": True}
    assert captured.out == json.dumps(result.to_summary(), sort_keys=True) + "\n"
    assert captured.err == ""
    summary = json.loads(captured.out)
    assert summary["artifacts"]["count"] == 17
    assert not any("run_provenance" in name for name in summary["artifacts"]["written"])
    target = result.analysis_root / "run_provenance.json"
    payload = json.loads(target.read_text())
    assert payload["workflow"] == "analysis"
    assert payload["status"] == "completed"
    assert payload["started_at_utc"] == "2026-09-06T12:03:04.123456Z"
    assert payload["ended_at_utc"] == "2026-09-06T12:03:09.123456Z"
    assert payload["sampling_by_condition"] == []
    assert len(payload["artifact_references"]) == 19
    assert payload["artifact_references"][-2] == {
        "role": "runtime_metadata", "path": "analysis/runtime_metadata.json",
    }
    assert payload["artifact_references"][-1] == {
        "role": "artifact_inventory", "path": "analysis/artifact_inventory.json",
    }
    assert all(
        ref["path"].startswith("analysis/") for ref in payload["artifact_references"]
    )
    input_label = "." if same_root else "prepared"
    expected_paths = (
        [f"--input={input_label}", "--output=."]
        if equals
        else ["--input", input_label, "--output", "."]
    )
    expected_command = (
        "mania",
        "analyze",
        *expected_paths,
        "--condition",
        "tumor",
        "--condition",
        "normal",
        *options,
    )
    assert completed.call_args.kwargs["command"] == expected_command
    assert isinstance(completed.call_args.kwargs["command"], tuple)
    assert payload["resolved_configuration"] == {
        "input_root": input_label,
        "output_root": ".",
        "analysis_root": "analysis",
        "conditions": ["tumor", "normal"],
        "enable_pca": enable_pca,
        "clustering_basis": basis,
        "pca_components_for_clustering": components,
        "artifact_checksum_mode": "none",
    }
    assert str(request.output_root) not in target.read_text()
    assert "/private/" not in target.read_text()
    assert set(result.analysis_root.iterdir()) == {
        target, result.analysis_root / "runtime_metadata.json",
    }
    assert sentinel.read_bytes() == b"existing preprocessing provenance\n"


def test_real_writer_creates_no_root_and_replaces_latest_analysis(
    monkeypatch,
    capsys,
    execution,
):
    request, result, _, _, _, _, _, _ = execution
    result.analysis_root.mkdir(parents=True)
    target = result.analysis_root / "run_provenance.json"
    target.write_bytes(b"previous analysis provenance")
    invoke(monkeypatch, capsys, request)
    assert json.loads(target.read_text())["status"] == "completed"
    assert not (request.output_root / "run_provenance.json").exists()
    assert set(result.analysis_root.iterdir()) == {
        target, result.analysis_root / "runtime_metadata.json",
    }


def test_portable_command_is_captured_before_execution(
    monkeypatch,
    capsys,
    execution,
):
    request, result, _, _, run, completed, _, _ = execution
    portable = Mock(wraps=cli._portable_analysis_command)
    monkeypatch.setattr(cli, "_portable_analysis_command", portable)

    def execute(received, *, resolved_input_paths):
        portable.assert_called_once()
        assert received == request
        # Changes after the capture cannot affect the emitted command snapshot.
        sys.argv[-1] = "changed-after-capture"
        return result

    run.side_effect = execute
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "analyze",
            "--input",
            str(request.input_root),
            "--output",
            str(request.output_root),
            "--condition",
            "tumor",
            "--condition",
            "normal",
        ],
    )
    cli.main()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert completed.call_args.kwargs["command"] == (
        "mania",
        "analyze",
        "--input",
        "prepared",
        "--output",
        ".",
        "--condition",
        "tumor",
        "--condition",
        "normal",
    )


@pytest.mark.parametrize(
    "error",
    [
        AnalyzeError("missing input /private/dataset"),
        RuntimeError("unexpected /private/dataset"),
    ],
)
def test_failed_real_writer_preserves_original_failure_and_root(
    monkeypatch,
    capsys,
    execution,
    error,
):
    request, result, clock, identity, run, completed, failed, writer = execution
    request = replace(request, input_root=request.output_root)
    request.output_root.mkdir()
    sentinel = request.output_root / "run_provenance.json"
    sentinel.write_bytes(b"preprocessing sentinel")
    result.analysis_root.mkdir()
    partial = result.analysis_root / "partial.csv"
    partial.write_bytes(b"partial scientific output")
    run.side_effect = error
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == f"Analyze failed: {error}\n"
    run.assert_called_once_with(request, resolved_input_paths=declared_inputs(request))
    assert_context(clock, identity, failed)
    completed.assert_not_called()
    assert writer.call_count == 1
    assert writer.call_args.args[1] == request.output_root / "analysis"
    assert writer.call_args.kwargs == {"overwrite": True}
    target = result.analysis_root / "run_provenance.json"
    payload = json.loads(target.read_text())
    assert payload["status"] == "failed"
    assert payload["workflow"] == "analysis"
    assert payload["sampling_by_condition"] == []
    assert payload["artifact_references"] == [
        {"role": "artifact_inventory", "path": "analysis/artifact_inventory.json"}
    ]
    assert payload["issues"] == [
        {
            "severity": "error",
            "code": "analysis_execution_failed",
            "message": "Analysis workflow failed.",
            "stage": "analysis_execution",
            "condition": None,
        }
    ]
    assert "/private/" not in target.read_text()
    assert payload["resolved_configuration"]["input_root"] == "."
    assert sentinel.read_bytes() == b"preprocessing sentinel"
    assert partial.read_bytes() == b"partial scientific output"
    assert set(result.analysis_root.iterdir()) == {target, partial}


@pytest.mark.parametrize("analysis_failed", [False, True])
@pytest.mark.parametrize("failure", ["builder", "writer_result", "writer_exception"])
def test_meta_failure_preserves_scientific_outputs_and_error_order(
    monkeypatch,
    capsys,
    execution,
    analysis_failed,
    failure,
):
    request, result, clock, identity, run, completed, failed, writer = execution
    result.analysis_root.mkdir(parents=True)
    scientific = result.analysis_root / "extended_metrics.json"
    scientific.write_bytes(b"existing scientific manifest")
    sentinel = request.output_root / "run_provenance.json"
    sentinel.write_bytes(b"preprocessing sentinel")
    builder = failed if analysis_failed else completed
    if analysis_failed:
        run.side_effect = AnalyzeError("original scientific failure")
    if failure == "builder":
        builder.side_effect = ValueError("private /secret/path")
    elif failure == "writer_result":
        writer.side_effect = None
        writer.return_value = RunProvenanceWriteResult(
            result.analysis_root / "run_provenance.json",
            False,
            "Filesystem write failed.",
        )
    else:
        writer.side_effect = OSError("private /secret/path")
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert_context(clock, identity, builder)
    assert captured.out == ""
    prefix = (
        "Failed analysis provenance" if analysis_failed else "Analysis run provenance"
    )
    if failure == "builder":
        writer.assert_not_called()
        message = (
            "Failed analysis metadata is invalid."
            if analysis_failed
            else "Completed analysis metadata is invalid."
        )
        meta_line = f"{prefix} build failed: {message}"
    else:
        assert writer.call_count == 1
        message = (
            "Filesystem write failed."
            if failure == "writer_result"
            else "Write operation failed."
        )
        meta_line = f"{prefix} write failed: {message}"
    expected = (
        ["Analyze failed: original scientific failure"] if analysis_failed else []
    )
    assert captured.err.splitlines() == [*expected, meta_line]
    assert scientific.read_bytes() == b"existing scientific manifest"
    assert sentinel.read_bytes() == b"preprocessing sentinel"
    expected_files = {scientific}
    if not analysis_failed:
        expected_files.add(result.analysis_root / "runtime_metadata.json")
    assert set(result.analysis_root.iterdir()) == expected_files


def test_real_atomic_writer_failure_leaves_no_temporary_file(
    monkeypatch,
    capsys,
    execution,
):
    import mania.run_provenance_io as writer_module

    request, result, _, _, _, _, _, _ = execution
    real_replace = writer_module.os.replace

    def fail_provenance_replace(source, destination):
        if Path(destination) == result.analysis_root / "run_provenance.json":
            raise OSError("private")
        return real_replace(source, destination)

    monkeypatch.setattr(
        writer_module.os, "replace", Mock(side_effect=fail_provenance_replace)
    )
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == (
        "Analysis run provenance write failed: Filesystem write failed.\n"
    )
    assert set(result.analysis_root.iterdir()) == {
        result.analysis_root / "runtime_metadata.json",
    }
    assert not (request.output_root / "run_provenance.json").exists()


@pytest.mark.parametrize("analysis_failed", [False, True])
def test_empty_input_filename_fails_portable_build_after_science(
    monkeypatch,
    capsys,
    execution,
    analysis_failed,
):
    request, _, _, _, run, completed, failed, writer = execution
    request = replace(request, input_root=Path("/"))
    run.return_value = analysis_result(request)
    if analysis_failed:
        run.side_effect = AnalyzeError("original error")
    captured = invoke(monkeypatch, capsys, request, code=1)
    run.assert_called_once_with(request, resolved_input_paths=declared_inputs(request))
    completed.assert_not_called()
    failed.assert_not_called()
    writer.assert_not_called()
    assert captured.out == ""
    if analysis_failed:
        assert captured.err == (
            "Analyze failed: original error\n"
            "Failed analysis provenance build failed: "
            "Failed analysis metadata is invalid.\n"
        )
    else:
        assert captured.err == (
            "Analysis run provenance build failed: "
            "Completed analysis metadata is invalid.\n"
        )


def test_request_construction_failure_does_not_invent_provenance(
    monkeypatch,
    capsys,
    execution,
):
    request, _, clock, identity, run, completed, failed, writer = execution
    monkeypatch.setattr(
        cli, "AnalyzeRequest", Mock(side_effect=ValueError("bad request"))
    )
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == "Analyze failed: bad request\n"
    assert clock.call_count == 1
    identity.assert_called_once_with()
    for call in (run, completed, failed, writer):
        call.assert_not_called()


@pytest.mark.parametrize(
    "args,code",
    [
        (["analyze", "--help"], 0),
        (["--version"], 0),
        (["analyze"], 2),
        (
            [
                "analyze",
                "--input",
                "in",
                "--output",
                "out",
                "--condition",
                "normal",
                "--pca-components-for-clustering",
                "bad",
            ],
            2,
        ),
    ],
)
def test_parser_boundary_reads_no_clock_or_identity(
    monkeypatch,
    capsys,
    execution,
    args,
    code,
):
    _, _, clock, identity, run, completed, failed, writer = execution
    cli.build_parser()
    monkeypatch.setattr(sys, "argv", ["mania", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == code
    captured = capsys.readouterr()
    if args == ["--version"]:
        assert captured.out == "mania-wania 0.1.0\n"
        assert captured.err == ""
    if "--help" in args:
        assert "provenance" not in captured.out
    for call in (clock, identity, run, completed, failed, writer):
        call.assert_not_called()


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_base_exceptions_are_not_caught(monkeypatch, capsys, execution, interruption):
    request, _, clock, _, run, completed, failed, writer = execution
    run.side_effect = interruption()
    with pytest.raises(interruption):
        invoke(monkeypatch, capsys, request)
    assert clock.call_count == 1
    for call in (completed, failed, writer):
        call.assert_not_called()


def test_synthetic_stage20_analysis_smoke_protects_shared_root(
    monkeypatch,
    capsys,
    tmp_path,
):
    _write_stage20_root(tmp_path, ("normal", "tumor"))
    sentinel = tmp_path / "run_provenance.json"
    sentinel.write_bytes(b"preprocessing sampling sentinel")
    monkeypatch.setattr(cli, "_utc_now", Mock(side_effect=[START, END]))
    monkeypatch.setattr(cli, "get_software_identity", Mock(return_value=IDENTITY))
    request = AnalyzeRequest(tmp_path, tmp_path, ("normal", "tumor"), enable_pca=True)
    captured = invoke(monkeypatch, capsys, request, options=("--enable-pca",))
    assert captured.err == ""
    summary = json.loads(captured.out)
    assert summary["artifacts"]["count"] == 17
    target = tmp_path / "analysis" / "run_provenance.json"
    payload = json.loads(target.read_text())
    assert payload["status"] == "completed"
    assert payload["workflow"] == "analysis"
    assert payload["sampling_by_condition"] == []
    assert {ref["path"] for ref in payload["artifact_references"]} == set(
        summary["artifacts"]["written"]
    ) | {"analysis/runtime_metadata.json", "analysis/artifact_inventory.json"}
    assert (tmp_path / "analysis" / "extended_metrics.json").is_file()
    assert sentinel.read_bytes() == b"preprocessing sampling sentinel"


def test_synthetic_stage20_failure_smoke_claims_no_partial_outputs(
    monkeypatch,
    capsys,
    tmp_path,
):
    _write_stage20_root(tmp_path, ("normal",))
    (tmp_path / "residue_table_normal.csv").unlink()
    sentinel = tmp_path / "run_provenance.json"
    sentinel.write_bytes(b"preprocessing sentinel")
    request = AnalyzeRequest(tmp_path, tmp_path, ("normal",))
    with pytest.raises(AnalyzeError) as original:
        cli.run_analysis(request)
    monkeypatch.setattr(cli, "_utc_now", Mock(side_effect=[START, END]))
    monkeypatch.setattr(cli, "get_software_identity", Mock(return_value=IDENTITY))
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == f"Analyze failed: {original.value}\n"
    target = tmp_path / "analysis" / "run_provenance.json"
    payload = json.loads(target.read_text())
    assert payload["status"] == "failed"
    assert payload["issues"][0]["code"] == "analysis_execution_failed"
    assert payload["artifact_references"] == []
    assert payload["sampling_by_condition"] == []
    assert list(target.parent.iterdir()) == [target]
    assert sentinel.read_bytes() == b"preprocessing sentinel"
