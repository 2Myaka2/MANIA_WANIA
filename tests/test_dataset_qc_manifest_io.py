"""Strict, portable and atomic Stage 32 control serialization."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_dataset_qc_manifest import make_qc_case

from mania.dataset_qc_manifest_io import (
    read_dataset_qc_manifest,
    validate_dataset_qc_manifest,
    write_dataset_qc_manifest,
)


def test_manifest_roundtrip_atomic_order_and_cwd(tmp_path, monkeypatch):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    original = path.read_bytes()
    assert original.endswith(b"\n") and not original.endswith(b"\n\n")
    assert read_dataset_qc_manifest(path) == manifest
    assert validate_dataset_qc_manifest(path).passed
    assert not write_dataset_qc_manifest(manifest, path).written
    assert write_dataset_qc_manifest(
        replace(manifest, replicas=manifest.replicas[::-1]), path, overwrite=True
    ).written
    assert path.read_bytes() == original
    monkeypatch.chdir(tmp_path.parent)
    assert read_dataset_qc_manifest(path) == manifest
    import mania.preprocessing.molecular_partner_metadata_io as atomic

    monkeypatch.setattr(
        atomic.os, "replace", lambda *a: (_ for _ in ()).throw(OSError())
    )
    assert not write_dataset_qc_manifest(manifest, path, overwrite=True).written
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "bad",
    [
        "/absolute.json",
        "../escape.json",
        "a/../b.json",
        "./file.json",
        "a//b",
        "a\\b",
        "C:/file",
        "",
        1,
        "~user/file",
        "$ENV/file",
        "a\u0000b",
    ],
)
@pytest.mark.parametrize(
    "field",
    [
        "aggregation_manifest_template_path",
        "hard_qc_evidence_path",
        "review_qc_evidence_path",
    ],
)
def test_control_json_paths_are_strict(tmp_path, bad, field):
    _, path, _, _, _ = make_qc_case(tmp_path, specialized=False)
    data = json.loads(path.read_text())
    target = (
        data if field == "aggregation_manifest_template_path" else data["replicas"][0]
    )
    target[field] = bad
    path.write_text(json.dumps(data))
    assert not validate_dataset_qc_manifest(path).passed


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "nested_unknown",
        "duplicate",
        "schema",
        "reference",
        "nulls",
        "manual_mode",
        "replicas_string",
    ],
)
def test_control_json_exact_keys_and_types(tmp_path, mutation):
    _, path, _, _, _ = make_qc_case(tmp_path)
    data = json.loads(path.read_text())
    if mutation == "unknown":
        data["extra"] = False
    elif mutation == "missing":
        del data["replicas"][0]["manual_resolution"]
    elif mutation == "nested_unknown":
        data["replicas"][0]["condition"] = "NORM"
    elif mutation == "duplicate":
        path.write_text('{"kind":"x",' + path.read_text()[1:])
    elif mutation == "schema":
        data["schema_version"] = 1
    elif mutation == "reference":
        data["canonical_reference_sequence_sha256"] = "0" * 64
    elif mutation == "nulls":
        data["replicas"][0]["hard_qc_evidence_path"] = None
    elif mutation == "manual_mode":
        data["replicas"][-1]["manual_resolution"]["decision_mode"] = "manual"
    else:
        data["replicas"] = "replicas"
    if mutation != "duplicate":
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_dataset_qc_manifest(path)


def test_missing_control_file(tmp_path):
    assert not validate_dataset_qc_manifest(tmp_path / "absent.json").passed
    with pytest.raises(ValueError):
        read_dataset_qc_manifest(Path(tmp_path))
