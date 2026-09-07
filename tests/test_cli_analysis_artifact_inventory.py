"""Analysis inventory CLI ordering, integrity modes, failures, and root isolation."""

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_analysis_artifact_inventory import (
    forbid_discovery,
    write_custom_stage20_root,
)
from test_analysis_run_provenance import END, IDENTITY, START
from test_cli_analysis_run_provenance import invoke

import mania.artifact_inventory_io as inventory_io
import mania.cli as cli
from mania.analysis.orchestration import AnalyzeError, AnalyzeRequest
from mania.artifact_inventory_io import ArtifactInventoryWriteResult
from mania.run_provenance import PortableArtifactReference

INVENTORY_REFERENCE = PortableArtifactReference(
    "artifact_inventory", "analysis/artifact_inventory.json"
)


@pytest.fixture
def execution(tmp_path, monkeypatch):
    request = AnalyzeRequest(
        tmp_path / "prepared", tmp_path / "out", ("tumor", "normal")
    )
    write_custom_stage20_root(request.input_root, request.conditions)
    spies = {}
    for name in (
        "resolve_analysis_input_paths",
        "run_analysis",
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
    monkeypatch.setattr(cli, "_utc_now", spies["clock"])
    monkeypatch.setattr(cli, "get_software_identity", spies["identity"])
    return request, spies


@pytest.mark.parametrize("mode", [None, "none", "sha256"])
def test_parser_accepts_modes_without_observations(monkeypatch, mode):
    forbidden = Mock(side_effect=AssertionError("Parser must not observe or hash"))
    monkeypatch.setattr(cli, "get_software_identity", forbidden)
    monkeypatch.setattr(cli, "_utc_now", forbidden)
    monkeypatch.setattr(inventory_io, "stream_file_sha256", forbidden)
    monkeypatch.setattr(cli, "resolve_analysis_input_paths", forbidden)
    argv = ["analyze", "--input", "in", "--output", "out", "--condition", "normal"]
    if mode is not None:
        argv += ["--artifact-checksum-mode", mode]
    assert cli.build_parser().parse_args(argv).artifact_checksum_mode == (
        mode or "none"
    )
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "argv,code",
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
                "--artifact-checksum-mode",
                "auto",
            ],
            2,
        ),
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
def test_parser_boundaries_do_not_enter_inventory(
    monkeypatch, capsys, execution, argv, code
):
    _, spies = execution
    hashing = Mock(side_effect=AssertionError("No parser hashing"))
    monkeypatch.setattr(inventory_io, "stream_file_sha256", hashing)
    monkeypatch.setattr(sys, "argv", ["mania", *argv])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == code
    captured = capsys.readouterr()
    if "--help" in argv:
        help_text = " ".join(captured.out.split())
        assert "--artifact-checksum-mode {none,sha256}" in help_text
        assert (
            "none records exact sizes without reading file contents "
            "for integrity metadata" in help_text
        )
        assert (
            "sha256 explicitly streams every inventoried analysis input and output"
            in help_text
        )
        # One option appears in usage and once in the options description.
        assert help_text.count("--artifact-checksum-mode") == 2
        assert "--checksum" not in help_text
    for spy in (*spies.values(), hashing):
        spy.assert_not_called()


def test_default_call_order_preserves_context_and_stdout(
    monkeypatch, capsys, execution
):
    request, spies = execution
    events = Mock()
    for name, spy in spies.items():
        events.attach_mock(spy, name)
    hashing = Mock(side_effect=AssertionError("Default integrity must not hash"))
    monkeypatch.setattr(inventory_io, "stream_file_sha256", hashing)
    captured = invoke(monkeypatch, capsys, request)
    resolver = spies["resolve_analysis_input_paths"]
    resolver.assert_called_once_with(request)
    run = spies["run_analysis"]
    run.assert_called_once()
    resolved = run.call_args.kwargs["resolved_input_paths"]
    builder = spies["build_analysis_artifact_inventory"]
    builder.assert_called_once()
    assert builder.call_args.kwargs["resolved_input_paths"] is resolved
    assert builder.call_args.kwargs["request"] == request
    assert builder.call_args.kwargs["checksum_mode"] == "none"
    result = builder.call_args.kwargs["result"]
    writer = spies["write_artifact_inventory"]
    writer.assert_called_once()
    assert writer.call_args.args[1] == request.output_root
    assert writer.call_args.kwargs == {"overwrite": True}
    completed = spies["build_completed_analysis_run_provenance"]
    completed.assert_called_once()
    assert completed.call_args.kwargs["additional_artifact_references"] == (
        PortableArtifactReference("runtime_metadata", "analysis/runtime_metadata.json"),
        INVENTORY_REFERENCE,
    )
    assert (
        completed.call_args.kwargs["resolved_configuration"]["artifact_checksum_mode"]
        == "none"
    )
    assert "--artifact-checksum-mode" not in completed.call_args.kwargs["command"]
    assert completed.call_args.kwargs["run_id"] == builder.call_args.kwargs["run_id"]
    assert completed.call_args.kwargs["started_at_utc"] == START
    assert completed.call_args.kwargs["ended_at_utc"] == END
    assert completed.call_args.kwargs["software_identity"] is IDENTITY
    spies["identity"].assert_called_once_with()
    assert spies["clock"].call_count == 2
    assert [call[0] for call in events.mock_calls] == [
        "clock",
        "identity",
        "resolve_analysis_input_paths",
        "run_analysis",
        "clock",
        "build_analysis_artifact_inventory",
        "write_artifact_inventory",
        "build_completed_analysis_run_provenance",
        "write_run_provenance",
    ]
    assert captured.out == json.dumps(result.to_summary(), sort_keys=True) + "\n"
    assert json.loads(captured.out)["artifacts"]["count"] == 17
    assert captured.err == ""
    spies["build_failed_analysis_run_provenance"].assert_not_called()
    hashing.assert_not_called()


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_real_inventory_smoke_sizes_hashes_stale_files_and_collision(
    monkeypatch, capsys, tmp_path, mode
):
    request = AnalyzeRequest(tmp_path, tmp_path, ("tumor", "normal"))
    write_custom_stage20_root(tmp_path, request.conditions)
    sentinels = {
        tmp_path / "artifact_inventory.json": b"preprocessing inventory sentinel\n",
        tmp_path / "run_provenance.json": b"preprocessing provenance sentinel\n",
    }
    for path, content in sentinels.items():
        path.write_bytes(content)
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "stale.csv").write_bytes(b"old output")
    # A previous inventory is overwritten only in the analysis directory.
    (analysis_root / "artifact_inventory.json").write_bytes(b"previous inventory")
    monkeypatch.setattr(cli, "get_software_identity", Mock(return_value=IDENTITY))
    monkeypatch.setattr(cli, "_utc_now", Mock(side_effect=[START, END]))
    captured_specs = []
    generic = inventory_io.build_artifact_inventory

    def build(**kwargs):
        captured_specs.extend(kwargs["file_specs"])
        return generic(**kwargs)

    import mania.analysis.artifact_inventory as adapter

    monkeypatch.setattr(adapter, "build_artifact_inventory", build)
    hashing = Mock(wraps=inventory_io.stream_file_sha256)
    monkeypatch.setattr(inventory_io, "stream_file_sha256", hashing)
    read_sizes = []
    open_file = Path.open

    class BoundedReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size=-1):
            assert 0 < size <= inventory_io.ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE
            read_sizes.append(size)
            return self.stream.read(size)

    def open_bounded(path, mode="r", *args, **kwargs):
        stream = open_file(path, mode, *args, **kwargs)
        return BoundedReader(stream) if mode == "rb" else stream

    with monkeypatch.context() as patch:
        forbidden = forbid_discovery(patch, resolve=False)
        patch.setattr(Path, "open", open_bounded)
        options = ("--artifact-checksum-mode", "sha256") if mode == "sha256" else ()
        captured = invoke(monkeypatch, capsys, request, options=options)
        forbidden.assert_not_called()
    assert captured.err == ""
    summary = json.loads(captured.out)
    inventory_path = analysis_root / "artifact_inventory.json"
    payload = json.loads(inventory_path.read_text())
    assert payload["checksum_mode"] == mode
    assert payload["workflow"] == "analysis"
    assert payload["inventory_path"] == "analysis/artifact_inventory.json"
    assert payload["input_artifact_count"] == 9
    assert payload["output_artifact_count"] == 18
    assert payload["artifact_count"] == 27
    assert summary["artifacts"]["count"] == 17
    assert [
        a["path"] for a in payload["artifacts"] if a["direction"] == "output"
    ] == summary["artifacts"]["written"] + ["analysis/runtime_metadata.json"]
    for entry, spec in zip(payload["artifacts"], captured_specs, strict=True):
        content = spec.local_path.read_bytes()
        assert entry["byte_size"] == len(content)
        assert entry["sha256"] == (
            hashlib.sha256(content).hexdigest() if mode == "sha256" else None
        )
        assert spec.local_path.name not in {
            "artifact_inventory.json",
            "run_provenance.json",
            "stale.csv",
        }
    assert any(
        e["artifact_id"] == "output:extended_metrics" for e in payload["artifacts"]
    )
    assert hashing.call_count == (27 if mode == "sha256" else 0)
    assert bool(read_sizes) == (mode == "sha256")
    if mode == "sha256":
        assert [c.args[0] for c in hashing.call_args_list] == [
            s.local_path for s in captured_specs
        ]
    provenance = json.loads((analysis_root / "run_provenance.json").read_text())
    assert provenance["artifact_references"][-1] == INVENTORY_REFERENCE.to_dict()
    assert provenance["run_id"] == payload["run_id"]
    assert provenance["resolved_configuration"]["artifact_checksum_mode"] == mode
    if mode == "sha256":
        assert provenance["command"][-2:] == ["--artifact-checksum-mode", "sha256"]
    assert "artifact_inventory" not in captured.out
    assert not (tmp_path / "checksums.sha256").exists()
    assert not (analysis_root / "checksums.sha256").exists()
    assert not (analysis_root / "analysis").exists()
    for path, content in sentinels.items():
        assert path.read_bytes() == content


def fail_analysis(request, *, resolved_input_paths):
    partial = request.output_root / "analysis/partial.csv"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"partial scientific output")
    raise AnalyzeError("deterministic scientific failure")


def test_failed_analysis_inventories_only_resolved_inputs(
    monkeypatch, capsys, execution
):
    request, spies = execution
    request.output_root.mkdir()
    root_metadata = [
        request.output_root / name
        for name in ("artifact_inventory.json", "run_provenance.json")
    ]
    for path in root_metadata:
        path.write_bytes(b"preprocessing sentinel")
    spies["run_analysis"].side_effect = fail_analysis
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == "Analyze failed: deterministic scientific failure\n"
    assert spies["build_analysis_artifact_inventory"].call_args.kwargs["result"] is None
    inventory = json.loads(
        (request.output_root / "analysis/artifact_inventory.json").read_text()
    )
    assert inventory["input_artifact_count"] == 9
    assert inventory["output_artifact_count"] == 0
    assert all(e["direction"] == "input" for e in inventory["artifacts"])
    failed = spies["build_failed_analysis_run_provenance"]
    failed.assert_called_once()
    assert failed.call_args.kwargs["additional_artifact_references"] == (
        INVENTORY_REFERENCE,
    )
    provenance = json.loads(
        (request.output_root / "analysis/run_provenance.json").read_text()
    )
    assert provenance["status"] == "failed"
    assert provenance["artifact_references"] == [INVENTORY_REFERENCE.to_dict()]
    assert (
        request.output_root / "analysis/partial.csv"
    ).read_bytes() == b"partial scientific output"
    assert all(p.read_bytes() == b"preprocessing sentinel" for p in root_metadata)
    assert spies["clock"].call_count == 2
    spies["identity"].assert_called_once_with()


def test_resolution_failure_skips_inventory_but_emits_failed_provenance(
    monkeypatch, capsys, execution
):
    request, spies = execution
    spies["resolve_analysis_input_paths"].side_effect = AnalyzeError(
        "resolution failed"
    )
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == "Analyze failed: resolution failed\n"
    for name in (
        "run_analysis",
        "build_analysis_artifact_inventory",
        "write_artifact_inventory",
    ):
        spies[name].assert_not_called()
    failed = spies["build_failed_analysis_run_provenance"]
    failed.assert_called_once()
    assert failed.call_args.kwargs["additional_artifact_references"] == ()
    assert not (request.output_root / "analysis/artifact_inventory.json").exists()
    provenance = json.loads(
        (request.output_root / "analysis/run_provenance.json").read_text()
    )
    assert provenance["status"] == "failed"
    assert provenance["artifact_references"] == []


@pytest.mark.parametrize("analysis_failed", [False, True])
@pytest.mark.parametrize("failure", ["build", "write_result", "write_exception"])
@pytest.mark.parametrize("provenance_failure", [None, "build", "write"])
def test_inventory_meta_failures_preserve_outputs_and_error_order(
    monkeypatch, capsys, execution, analysis_failed, failure, provenance_failure
):
    request, spies = execution
    root = request.output_root / "analysis"
    root.mkdir(parents=True)
    old_inventory = root / "artifact_inventory.json"
    old_inventory.write_bytes(b"old inventory must not be claimed")
    if analysis_failed:
        spies["run_analysis"].side_effect = fail_analysis
    if failure == "build":
        spies["build_analysis_artifact_inventory"].side_effect = ValueError(
            "private /secret/path"
        )
    elif failure == "write_exception":
        spies["write_artifact_inventory"].side_effect = OSError("private /secret/path")
    else:
        spies["write_artifact_inventory"].side_effect = lambda *args, **kwargs: (
            ArtifactInventoryWriteResult(
                old_inventory, False, "Filesystem write failed."
            )
        )
    builder = spies[
        "build_failed_analysis_run_provenance"
        if analysis_failed
        else "build_completed_analysis_run_provenance"
    ]
    if provenance_failure == "build":
        builder.side_effect = ValueError("private /secret/path")
    elif provenance_failure == "write":
        spies["write_run_provenance"].side_effect = OSError("private /secret/path")
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    expected = (
        ["Analyze failed: deterministic scientific failure"] if analysis_failed else []
    )
    expected.append(
        {
            "build": (
                "Analysis artifact inventory build failed: "
                "Inventory metadata is unavailable."
            ),
            "write_result": (
                "Analysis artifact inventory write failed: Filesystem write failed."
            ),
            "write_exception": (
                "Analysis artifact inventory write failed: Write operation failed."
            ),
        }[failure]
    )
    if provenance_failure:
        prefix = (
            "Failed analysis provenance"
            if analysis_failed
            else "Analysis run provenance"
        )
        message = (
            "Write operation failed."
            if provenance_failure == "write"
            else (
                "Failed analysis metadata is invalid."
                if analysis_failed
                else "Completed analysis metadata is invalid."
            )
        )
        expected.append(f"{prefix} {provenance_failure} failed: {message}")
    assert captured.err.splitlines() == expected
    builder.assert_called_once()
    assert builder.call_args.kwargs["additional_artifact_references"] == (
        () if analysis_failed else (
            PortableArtifactReference(
                "runtime_metadata", "analysis/runtime_metadata.json",
            ),
        )
    )
    if provenance_failure is None:
        provenance = json.loads((root / "run_provenance.json").read_text())
        assert provenance["status"] == ("failed" if analysis_failed else "completed")
        assert all(
            ref["role"] != "artifact_inventory"
            for ref in provenance["artifact_references"]
        )
    if failure == "build":
        spies["write_artifact_inventory"].assert_not_called()
    assert old_inventory.read_bytes() == b"old inventory must not be claimed"
    if analysis_failed:
        assert (root / "partial.csv").read_bytes() == b"partial scientific output"
    else:
        result = spies["build_analysis_artifact_inventory"].call_args.kwargs["result"]
        assert all(path.is_file() for path in result.artifacts)
    assert spies["clock"].call_count == 2
    spies["identity"].assert_called_once_with()


def test_request_construction_failure_never_attempts_inventory(
    monkeypatch, capsys, execution
):
    request, spies = execution
    monkeypatch.setattr(
        cli, "AnalyzeRequest", Mock(side_effect=ValueError("bad request"))
    )
    captured = invoke(monkeypatch, capsys, request, code=1)
    assert captured.out == ""
    assert captured.err == "Analyze failed: bad request\n"
    for name, spy in spies.items():
        if name not in {"clock", "identity"}:
            spy.assert_not_called()
    assert spies["clock"].call_count == 1
