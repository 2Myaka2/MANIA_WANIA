"""Atomic writes use fixed passports and temporary directories only."""

import builtins
import hashlib
import json
import os
import subprocess
import time
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

import mania
import mania.run_provenance_io as provenance_io
from mania.run_provenance import RUN_PROVENANCE_FILENAME, RunProvenance
from mania.run_provenance_io import RunProvenanceWriteResult, write_run_provenance
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
    assert provenance_io.__all__ == ["RunProvenanceWriteResult", "write_run_provenance"]
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
