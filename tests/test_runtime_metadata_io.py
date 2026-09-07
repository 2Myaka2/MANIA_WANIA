"""Strict runtime round trips and atomic publication without recollection."""

import json
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, replace
from importlib import metadata
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_runtime_metadata import metadata_model

import mania.runtime_metadata_io as runtime_io


def forbid(*args, **kwargs):
    raise AssertionError("Unexpected metadata recollection or discovery")


def guard_io(patch):
    for owner, names in (
        (Path, ("glob", "rglob", "iterdir", "resolve")),
        (os, ("walk", "scandir", "listdir")),
        (subprocess, ("run", "Popen")),
        (time, ("time", "time_ns", "perf_counter", "monotonic")),
        (metadata, ("version",)),
    ):
        for name in names:
            patch.setattr(owner, name, forbid)


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
def test_exact_round_trip_formatting_and_no_observations(monkeypatch, tmp_path, scope):
    portable = ("analysis/" if scope == "analysis" else "") + "runtime_metadata.json"
    model = metadata_model(scope=scope, metadata_path=portable, run_id="run-α")
    before = model.to_dict()
    with monkeypatch.context() as patch:
        guard_io(patch)
        result = runtime_io.write_runtime_metadata(model, tmp_path)
        assert result.passed and result.output_path == tmp_path / portable
        restored = runtime_io.read_runtime_metadata(result.output_path)
    assert restored.to_dict() == before == model.to_dict()
    assert result.output_path.read_bytes() == (
        json.dumps(
            before, indent=2, sort_keys=False, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")
    assert result.to_dict() == dict(
        output_path=str(result.output_path), written=True, error=None, passed=True
    )
    with pytest.raises(FrozenInstanceError):
        result.written = False


def test_overwrite_preserves_then_atomically_replaces(monkeypatch, tmp_path):
    model = metadata_model()
    target = runtime_io.write_runtime_metadata(model, tmp_path).output_path
    before = target.read_bytes()
    changed = replace(model, run_id="replacement")
    refused = runtime_io.write_runtime_metadata(changed, tmp_path)
    assert not refused.passed and refused.error == "Target already exists."
    assert target.read_bytes() == before
    original = os.replace

    def publish(source, destination):
        assert Path(source).parent == target.parent
        assert target.read_bytes() == before
        assert runtime_io.read_runtime_metadata(source) == changed
        return original(source, destination)

    spy = Mock(side_effect=publish)
    monkeypatch.setattr(runtime_io.os, "replace", spy)
    assert runtime_io.write_runtime_metadata(changed, tmp_path, overwrite=True).passed
    spy.assert_called_once()
    assert runtime_io.read_runtime_metadata(target) == changed
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("overwrite", [False, True])
def test_failed_publication_cleans_temporary_files(monkeypatch, tmp_path, overwrite):
    target = tmp_path / "runtime_metadata.json"
    if overwrite:
        target.write_bytes(b"old bytes")
    monkeypatch.setattr(
        runtime_io.os,
        "replace" if overwrite else "link",
        Mock(side_effect=OSError("private path")),
    )
    result = runtime_io.write_runtime_metadata(
        metadata_model(), tmp_path, overwrite=overwrite
    )
    assert result.to_dict() == dict(
        output_path=str(target),
        written=False,
        error="Filesystem write failed.",
        passed=False,
    )
    assert target.read_bytes() == b"old bytes" if overwrite else not target.exists()
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    "content", [b"{", b"\xff", b"[]", b"null", b'{"kind":NaN}', b'{"a":1,"a":2}']
)
def test_malformed_json_is_rejected(tmp_path, content):
    path = tmp_path / "runtime_metadata.json"
    path.write_bytes(content)
    with pytest.raises(runtime_io.RuntimeMetadataReadError):
        runtime_io.read_runtime_metadata(path)


@pytest.mark.parametrize(
    "section,key,value",
    [
        (None, "schema_version", "future"),
        (None, "kind", "wrong"),
        (None, "metadata_path", "/runtime_metadata.json"),
        (None, "unexpected", None),
        (None, "run_id", 12),
        ("environment", "python_version", 3),
        ("environment", "numpy_version", ""),
        ("performance", "wall_clock_seconds", -1),
        ("performance", "sampled_frame_count", True),
        ("performance", "condition_count", "2"),
        ("performance", "seconds_per_sampled_frame", None),
    ],
)
def test_strict_fields(tmp_path, section, key, value):
    payload = metadata_model().to_dict()
    (payload if section is None else payload[section])[key] = value
    path = tmp_path / "runtime_metadata.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(runtime_io.RuntimeMetadataReadError):
        runtime_io.read_runtime_metadata(path)


def test_missing_fields_regular_file_and_write_result_contract(tmp_path):
    for path in (tmp_path, tmp_path / "missing.json"):
        with pytest.raises(runtime_io.RuntimeMetadataReadError):
            runtime_io.read_runtime_metadata(path)
    payload = metadata_model().to_dict()
    del payload["environment"]["numpy_version"]
    path = tmp_path / "runtime_metadata.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(runtime_io.RuntimeMetadataReadError):
        runtime_io.read_runtime_metadata(path)
    for written, error in ((True, "failure"), (False, None), (1, None), (False, "")):
        with pytest.raises(ValueError):
            runtime_io.RuntimeMetadataWriteResult(path, written, error)
