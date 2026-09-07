"""Atomic PBC audit I/O preserves observations and rejects scientific claims."""

import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_preprocessing_pbc_audit import BOX, audit, observe
from test_runtime_metadata_io import guard_io

import mania.preprocessing.pbc_audit_io as pbc_io


@pytest.mark.parametrize(
    "boxes,status",
    [
        ((), "unavailable"),
        ((None, None), "unavailable"),
        ((BOX, None), "partial"),
        ((BOX, BOX), "complete"),
        (((-1, 20, 30, 90, 90, 90),), "invalid"),
    ],
)
def test_round_trip_observation_statuses(monkeypatch, tmp_path, boxes, status):
    model = audit(
        observations=tuple(observe(box, index=i) for i, box in enumerate(boxes))
    )
    before = model.to_dict()
    with monkeypatch.context() as patch:
        guard_io(patch)
        result = pbc_io.write_pbc_audit(model, tmp_path)
        restored = pbc_io.read_pbc_audit(result.output_path)
    assert result.passed and result.output_path == tmp_path / "pbc_audit.json"
    assert before == restored.to_dict() == model.to_dict()
    assert restored.conditions[0].metadata_status == status
    assert restored.mania_internal_minimum_image_correction_applied is False
    assert restored.scientific_pbc_status == "unresolved"
    assert (
        result.output_path.read_bytes()
        == (
            json.dumps(
                before, indent=2, sort_keys=False, ensure_ascii=False, allow_nan=False
            )
            + "\n"
        ).encode()
    )
    assert result.to_dict() == dict(
        output_path=str(result.output_path), written=True, error=None, passed=True
    )
    with pytest.raises(FrozenInstanceError):
        result.error = "failure"


def test_overwrite_and_atomic_failure_cleanup(monkeypatch, tmp_path):
    model = audit()
    target = pbc_io.write_pbc_audit(model, tmp_path).output_path
    before = target.read_bytes()
    replacement = replace(model, run_id="replacement")
    assert not pbc_io.write_pbc_audit(replacement, tmp_path).passed
    assert target.read_bytes() == before
    original = os.replace

    def publish(source, destination):
        assert Path(source).parent == target.parent
        assert target.read_bytes() == before
        assert pbc_io.read_pbc_audit(source) == replacement
        return original(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(pbc_io.os, "replace", publish)
        assert pbc_io.write_pbc_audit(replacement, tmp_path, overwrite=True).passed
    monkeypatch.setattr(pbc_io.os, "replace", Mock(side_effect=OSError("private")))
    failed = pbc_io.write_pbc_audit(model, tmp_path, overwrite=True)
    assert failed.error == "Filesystem write failed."
    assert pbc_io.read_pbc_audit(target) == replacement
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "future"),
        ("kind", "wrong"),
        ("mania_internal_minimum_image_correction_applied", True),
        ("mania_internal_minimum_image_correction_applied", 0),
        ("scientific_pbc_status", "approved"),
        ("scientific_pbc_status", "resolved"),
        ("distance_semantics", "minimum_image"),
        ("external_pbc_preprocessing_status", "inferred"),
        ("audit_path", "../pbc_audit.json"),
        ("conditions", {}),
    ],
)
def test_rejects_invalid_root_and_scientific_claims(tmp_path, field, value):
    payload = audit().to_dict()
    payload[field] = value
    path = tmp_path / "pbc_audit.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(pbc_io.PbcAuditReadError):
        pbc_io.read_pbc_audit(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sampled_frame_count", "1"),
        ("dimensions_valid_frame_count", False),
        ("metadata_status", "invalid"),
        ("box_varies", True),
        ("box_lengths_min_A", [0, 20, 30]),
        ("box_angles_max_deg", "90,90,90"),
        ("extra", None),
    ],
)
def test_rejects_invalid_condition_without_coercion(tmp_path, field, value):
    payload = audit().to_dict()
    payload["conditions"][0][field] = value
    path = tmp_path / "pbc_audit.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(pbc_io.PbcAuditReadError):
        pbc_io.read_pbc_audit(path)


@pytest.mark.parametrize(
    "content", [b"{", b"\xff", b"[]", b"null", b'{"kind":Infinity}', b'{"a":1,"a":2}']
)
def test_malformed_json(tmp_path, content):
    path = tmp_path / "pbc_audit.json"
    path.write_bytes(content)
    with pytest.raises(pbc_io.PbcAuditReadError):
        pbc_io.read_pbc_audit(path)


def test_regular_file_and_write_result_contract(tmp_path):
    for path in (tmp_path, tmp_path / "missing.json"):
        with pytest.raises(pbc_io.PbcAuditReadError):
            pbc_io.read_pbc_audit(path)
    for written, error in ((True, "failure"), (False, None), (1, None), (False, "")):
        with pytest.raises(ValueError):
            pbc_io.PbcAuditWriteResult(tmp_path / "pbc_audit.json", written, error)
