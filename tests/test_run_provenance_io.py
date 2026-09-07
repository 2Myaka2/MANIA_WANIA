"""Atomic writes use fixed passports and temporary directories only."""

import builtins
import hashlib
import json
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import mania
import mania.run_provenance_io as provenance_io
from mania.run_provenance import (
    RUN_PROVENANCE_FILENAME,
    ConditionSamplingProvenance,
    EffectiveFrameSampling,
    PortableArtifactReference,
    RequestedFrameSampling,
    RunProvenance,
    RunProvenanceIssue,
)
from mania.run_provenance_io import (
    RunProvenanceReadError,
    RunProvenanceWriteResult,
    read_run_provenance,
    write_run_provenance,
)
from mania.software_identity import SoftwareIdentity


@pytest.fixture
def provenance():
    return RunProvenance(
        run_id="опыт-α",
        workflow="preprocessing_graph_export",
        status="completed",
        started_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        ended_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        software_identity=SoftwareIdentity(
            "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
        ),
        command=("mania", "preprocessing", "run-graph-export"),
        resolved_configuration={"output_root": "."},
        conditions=(),
    )


def test_public_boundary():
    assert provenance_io.__all__ == [
        "RunProvenanceReadError",
        "RunProvenanceWriteResult",
        "read_run_provenance",
        "write_run_provenance",
    ]
    assert not hasattr(mania, "RunProvenanceWriteResult")
    assert not hasattr(mania, "write_run_provenance")


@pytest.mark.parametrize("written,error", [(True, None), (False, "Write failed.")])
def test_result_contract(written, error):
    result = RunProvenanceWriteResult(Path(RUN_PROVENANCE_FILENAME), written, error)
    assert result.passed is written
    assert list(result.to_dict()) == ["output_path", "written", "error", "passed"]
    assert json.loads(json.dumps(result.to_dict())) == {
        "output_path": RUN_PROVENANCE_FILENAME,
        "written": written,
        "error": error,
        "passed": written,
    }
    with pytest.raises(FrozenInstanceError):
        result.written = False


@pytest.mark.parametrize(
    "path,written,error",
    [
        ("out", True, None),
        (None, True, None),
        (Path("out"), 1, None),
        (Path("out"), 0, "Failed."),
        (Path("out"), True, "Failed."),
        (Path("out"), False, None),
        (Path("out"), False, ""),
        (Path("out"), False, " "),
        (Path("out"), False, " Failed."),
        (Path("out"), False, "Failed.\n"),
        (Path("out"), False, 1),
    ],
)
def test_invalid_result(path, written, error):
    with pytest.raises(ValueError):
        RunProvenanceWriteResult(path, written, error)


def test_writer_creates_only_complete_ordered_utf8_json(provenance, tmp_path):
    before = provenance.to_dict()
    output = tmp_path / "missing" / "parents"
    result = write_run_provenance(provenance, str(output))
    assert result.passed and result.output_path == output / RUN_PROVENANCE_FILENAME
    data = result.output_path.read_bytes()
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
    text = data.decode("utf-8")
    assert "опыт-α" in text and "\\u" not in text
    assert (
        text
        == json.dumps(
            before, indent=2, sort_keys=False, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
    assert list(json.loads(text)) == list(before)
    assert json.loads(text) == before == provenance.to_dict()
    assert list(output.iterdir()) == [result.output_path]


@pytest.mark.parametrize("overwrite", [False, True])
def test_existing_target(provenance, tmp_path, overwrite):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_bytes(b"original\n")
    result = write_run_provenance(provenance, tmp_path, overwrite=overwrite)
    assert result.passed is overwrite
    if overwrite:
        assert json.loads(target.read_text()) == provenance.to_dict()
    else:
        assert result.error == "Target already exists."
        assert target.read_bytes() == b"original\n"
    assert list(tmp_path.iterdir()) == [target]


def test_output_directory_is_file(provenance, tmp_path):
    output = tmp_path / "file"
    output.write_bytes(b"original")
    result = write_run_provenance(provenance, output)
    assert not result.passed and result.error
    assert output.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [output]


def test_invalid_writer_arguments(provenance, tmp_path):
    class Derived(RunProvenance):
        pass

    for invalid in (None, {}, object(), object.__new__(Derived)):
        with pytest.raises(ValueError, match="provenance must"):
            write_run_provenance(invalid, tmp_path)
    with pytest.raises(ValueError, match="output_dir"):
        write_run_provenance(provenance, "")
    for invalid in (0, 1, None, "false"):
        with pytest.raises(ValueError, match="overwrite"):
            write_run_provenance(provenance, tmp_path, overwrite=invalid)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad_value", [float("nan"), object(), "\ud800"])
@pytest.mark.parametrize("existing", [False, True])
def test_serialization_failure_is_atomic(
    provenance, tmp_path, monkeypatch, bad_value, existing
):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    if existing:
        target.write_bytes(b"original")
    monkeypatch.setattr(RunProvenance, "to_dict", lambda _: {"bad": bad_value})
    result = write_run_provenance(provenance, tmp_path, overwrite=existing)
    assert result.error == "JSON serialization failed."
    assert list(tmp_path.iterdir()) == ([target] if existing else [])
    if existing:
        assert target.read_bytes() == b"original"


@pytest.mark.parametrize(
    "operation", ["mkdir", "temporary", "write", "replace", "link"]
)
def test_filesystem_failure_cleans_temporary_files(
    provenance, tmp_path, monkeypatch, operation
):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    overwrite = operation != "link"
    if overwrite:
        target.write_bytes(b"original")

    def fail(*args, **kwargs):
        raise OSError("Private local path and OS-specific diagnostic")

    real_temporary = provenance_io.tempfile.NamedTemporaryFile

    def broken_stream(*args, **kwargs):
        stream = real_temporary(*args, **kwargs)
        stream.write = fail
        return stream

    with monkeypatch.context() as patch:
        if operation == "mkdir":
            patch.setattr(Path, "mkdir", fail)
        elif operation == "temporary":
            patch.setattr(provenance_io.tempfile, "NamedTemporaryFile", fail)
        elif operation == "write":
            patch.setattr(provenance_io.tempfile, "NamedTemporaryFile", broken_stream)
        else:
            patch.setattr(os, operation, fail)
        result = write_run_provenance(provenance, tmp_path, overwrite=overwrite)
    assert result.error == "Filesystem write failed."
    assert list(tmp_path.iterdir()) == ([target] if overwrite else [])
    if overwrite:
        assert target.read_bytes() == b"original"


def test_no_overwrite_preserves_concurrently_created_target(
    provenance, tmp_path, monkeypatch
):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    link = os.link

    def race(source, destination):
        target.write_bytes(b"concurrent")
        link(source, destination)

    monkeypatch.setattr(os, "link", race)
    result = write_run_provenance(provenance, tmp_path)
    assert result.error == "Target already exists."
    assert target.read_bytes() == b"concurrent"
    assert list(tmp_path.iterdir()) == [target]


def test_writer_does_not_read_artifacts_hash_git_or_clock(
    provenance, tmp_path, monkeypatch
):
    before = provenance.to_dict()
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        raise AssertionError("External observation is forbidden")

    def guarded_import(name, *args, **kwargs):
        if name in ("datetime", "time", "subprocess", "hashlib"):
            forbidden()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        for module, names in (
            (subprocess, ("run", "Popen")),
            (hashlib, ("sha256", "file_digest", "new")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (Path, ("read_text", "read_bytes", "iterdir", "glob", "rglob", "resolve")),
        ):
            for name in names:
                patch.setattr(module, name, forbidden)
        result = write_run_provenance(provenance, tmp_path)
    assert result.passed and provenance.to_dict() == before
    assert list(tmp_path.iterdir()) == [result.output_path]


@pytest.mark.parametrize("overwrite", [False, True])
def test_publication_only_sees_complete_same_directory_temporary_json(
    provenance, tmp_path, monkeypatch, overwrite
):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    if overwrite:
        target.write_bytes(b"original")
    operation = "replace" if overwrite else "link"
    publish = getattr(os, operation)
    published = []

    def inspect_publication(source, destination):
        assert source.parent == target.parent and destination == target
        assert source != target
        assert json.loads(source.read_text(encoding="utf-8")) == provenance.to_dict()
        if overwrite:
            assert target.read_bytes() == b"original"
        else:
            assert not target.exists()
        publish(source, destination)
        published.append(destination)

    monkeypatch.setattr(os, operation, inspect_publication)
    assert write_run_provenance(provenance, tmp_path, overwrite=overwrite).passed
    assert published == [target] and list(tmp_path.iterdir()) == [target]


@pytest.fixture
def rich_provenance(provenance):
    return replace(
        provenance,
        conditions=("tumor", "normal"),
        command=("mania", "preprocessing", "--label", "with spaces", "--literal=$HOME"),
        resolved_configuration={"z": [None, True, 2, 1.5, "α"], "a": {"b": "value"}},
        sampling_by_condition=(
            ConditionSamplingProvenance(
                "normal",
                RequestedFrameSampling(1, 9, 2, 3),
                EffectiveFrameSampling(10, 3, 1, 5, 2.0, 10.0, "uniform", 4.0),
            ),
            ConditionSamplingProvenance("tumor", RequestedFrameSampling(), None),
        ),
        artifact_references=(
            PortableArtifactReference("graph", "normal/graph.json"),
            PortableArtifactReference("manifest", "mania_manifest.json"),
            PortableArtifactReference("artifact_inventory", "artifact_inventory.json"),
        ),
        issues=(
            RunProvenanceIssue(
                "warning", "first", "First issue.", "sampling", "normal"
            ),
            RunProvenanceIssue("error", "second", "Second issue.", None, "tumor"),
        ),
    )


@pytest.mark.parametrize("status", ["completed", "failed"])
@pytest.mark.parametrize("workflow", ["preprocessing_graph_export", "analysis"])
def test_reader_round_trip_preserves_order_and_values(
    rich_provenance,
    tmp_path,
    monkeypatch,
    status,
    workflow,
):
    import mania.software_identity as identity_module

    model = replace(rich_provenance, status=status, workflow=workflow)
    if workflow == "analysis":
        model = replace(model, sampling_by_condition=())
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_text(json.dumps(model.to_dict(), ensure_ascii=False), encoding="utf-8")
    before = target.read_bytes(), target.stat().st_mtime_ns

    def forbidden(*args, **kwargs):
        raise AssertionError("Runtime recollection or scanning is forbidden")

    class StoredDatetime(datetime):
        now = utcnow = today = forbidden

    with monkeypatch.context() as patch:
        patch.setattr(provenance_io, "datetime", StoredDatetime)
        patch.setattr(identity_module, "get_software_identity", forbidden)
        for module, names in (
            (subprocess, ("run", "Popen")),
            (time, ("time", "time_ns", "monotonic")),
            (os, ("listdir", "scandir", "walk", "getenv")),
            (Path, ("glob", "rglob", "iterdir", "resolve")),
        ):
            for name in names:
                patch.setattr(module, name, forbidden)
        actual = read_run_provenance(str(target))
    assert actual.to_dict() == model.to_dict()
    assert actual.artifact_references == model.artifact_references
    assert actual.issues == model.issues
    assert actual.conditions == model.conditions
    assert actual.sampling_by_condition == model.sampling_by_condition
    assert actual.command == model.command
    assert actual.started_at_utc.tzinfo == UTC
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before


@pytest.mark.parametrize(
    "payload,message",
    [
        (b"{", "valid UTF-8 JSON"),
        (b"\xff", "valid UTF-8 JSON"),
        (b'{"kind":1,"kind":2}', "valid UTF-8 JSON"),
        (b'{"invalid":Infinity}', "valid UTF-8 JSON"),
        (b"[]", "JSON object"),
        (b"null", "JSON object"),
    ],
)
def test_reader_invalid_json(tmp_path, payload, message):
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_bytes(payload)
    with pytest.raises(RunProvenanceReadError, match=message) as error:
        read_run_provenance(target)
    assert str(tmp_path) not in str(error.value)
    assert target.read_bytes() == payload


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "future"),
        ("kind", "other"),
        ("run_id", 2),
        ("workflow", None),
        ("status", "running"),
        ("conditions", "normal"),
        ("conditions", [1]),
        ("command", "mania"),
        ("command", ["mania", False]),
        ("resolved_configuration", []),
        ("sampling_by_condition", {}),
        ("artifact_references", {}),
        ("issues", {}),
        ("extra", "value"),
    ],
)
def test_reader_invalid_root_fields(provenance, tmp_path, field, value):
    data = provenance.to_dict()
    data[field] = value
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_text(json.dumps(data))
    message = field if field in ("schema_version", "kind") else "fields"
    with pytest.raises(RunProvenanceReadError, match=message):
        read_run_provenance(target)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "kind",
        "run_id",
        "workflow",
        "status",
        "started_at_utc",
        "ended_at_utc",
        "software_identity",
        "command",
        "resolved_configuration",
        "conditions",
        "sampling_by_condition",
        "artifact_references",
        "issues",
    ],
)
def test_reader_requires_all_serialized_fields(provenance, tmp_path, field):
    data = provenance.to_dict()
    del data[field]
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_text(json.dumps(data))
    with pytest.raises(RunProvenanceReadError):
        read_run_provenance(target)


@pytest.mark.parametrize("field", ["started_at_utc", "ended_at_utc"])
@pytest.mark.parametrize(
    "value", ["2026-01-02T00:00:00", "not-time", "2026-13-02T00:00:00Z", None, 5]
)
def test_reader_rejects_naive_or_invalid_timestamps(provenance, tmp_path, field, value):
    data = provenance.to_dict()
    data[field] = value
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_text(json.dumps(data))
    with pytest.raises(RunProvenanceReadError, match="fields"):
        read_run_provenance(target)


@pytest.mark.parametrize(
    "path,value",
    [
        (("software_identity", "version"), 1),
        (("software_identity", "software_name"), None),
        (("software_identity", "distribution_name"), []),
        (("software_identity", "commit_sha"), "bad"),
        (("software_identity", "commit_source"), "other"),
        (("software_identity", "working_tree_status"), False),
        (("sampling_by_condition", 0, "requested", "frame_stride"), True),
        (("sampling_by_condition", 0, "requested"), None),
        (("sampling_by_condition", 0, "effective", "sampled_frame_count"), -1),
        (("sampling_by_condition", 0, "effective", "first_time_ps"), "2"),
        (("sampling_by_condition", 0, "condition"), "unknown"),
        (("artifact_references", 0, "path"), "../private"),
        (("issues", 0, "severity"), "info"),
        (("issues", 0, "condition"), "unknown"),
        (("issues", 0), None),
    ],
)
def test_reader_rejects_invalid_nested_values(rich_provenance, tmp_path, path, value):
    data = rich_provenance.to_dict()
    nested = data
    for component in path[:-1]:
        nested = nested[component]
    nested[path[-1]] = value
    target = tmp_path / RUN_PROVENANCE_FILENAME
    target.write_text(json.dumps(data))
    with pytest.raises(RunProvenanceReadError, match="fields"):
        read_run_provenance(target)


@pytest.mark.parametrize("value", ["", None, 3, b"path"])
def test_reader_rejects_invalid_path_arguments(value):
    with pytest.raises(RunProvenanceReadError, match="path must"):
        read_run_provenance(value)


def test_reader_filesystem_errors(tmp_path, monkeypatch):
    with pytest.raises(RunProvenanceReadError, match="missing"):
        read_run_provenance(tmp_path / "missing")
    with pytest.raises(RunProvenanceReadError, match="regular file"):
        read_run_provenance(tmp_path)

    def inaccessible(*args, **kwargs):
        raise PermissionError("/private/secret")

    monkeypatch.setattr(Path, "stat", inaccessible)
    with pytest.raises(RunProvenanceReadError, match="cannot be read") as error:
        read_run_provenance(tmp_path)
    assert "/private" not in str(error.value)
