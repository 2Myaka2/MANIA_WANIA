"""Strict complete annotation controls: portable failures and atomic publication."""

import json

import pytest
from test_biological_annotations import glyco, metadata, variant

from mania import biological_annotations_io as io


def test_round_trip_deterministic_and_overwrite(tmp_path):
    data = metadata(glycosylation_sites=(glyco(),), cysteine_variant_sites=(variant(),))
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    for path in (first, second):
        assert io.write_dataset_system_biological_annotations(data, path).passed
        assert io.read_dataset_system_biological_annotations(path) == data
        assert io.validate_dataset_system_biological_annotations(path).passed
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes().endswith(b"\n")
    assert not first.read_bytes().endswith(b"\n\n")
    before = first.read_bytes()
    assert not io.write_dataset_system_biological_annotations(metadata(), first).passed
    assert first.read_bytes() == before
    assert io.write_dataset_system_biological_annotations(
        metadata(), first, overwrite=True
    ).passed
    assert io.read_dataset_system_biological_annotations(first) == metadata()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version="wrong"),
        lambda d: d.update(kind="wrong"),
        lambda d: d.update(extra=1),
        lambda d: d.pop("system_id"),
        lambda d: d.update(annotation_scope="partial"),
        lambda d: d.update(glycosylation_sites=None),
        lambda d: d["glycosylation_sites"][0].update(canonical_resname="MET"),
        lambda d: d["glycosylation_sites"][0].update(canonical_residue_number=0),
        lambda d: d["glycosylation_sites"][0].update(canonical_residue_number=691),
        lambda d: d["glycosylation_sites"][0].update(canonical_residue_number=True),
        lambda d: d["glycosylation_sites"][0].update(present_in_topology="true"),
        lambda d: d["glycosylation_sites"][0].update(extra=1),
        lambda d: d["glycosylation_sites"][0].pop("glycan_name"),
        lambda d: d["glycosylation_sites"][0].pop("source"),
        lambda d: d["glycosylation_sites"][0].pop("verifier"),
        lambda d: d["glycosylation_sites"].append(d["glycosylation_sites"][0]),
        lambda d: d["cysteine_variant_sites"].append(d["cysteine_variant_sites"][0]),
    ],
)
def test_corruption(tmp_path, mutation):
    path = tmp_path / "metadata.json"
    io.write_dataset_system_biological_annotations(
        metadata(glycosylation_sites=(glyco(),), cysteine_variant_sites=(variant(),)),
        path,
    )
    payload = json.loads(path.read_text())
    mutation(payload)
    path.write_text(json.dumps(payload))
    with pytest.raises(io.BiologicalAnnotationReadError, match="Invalid or unreadable"):
        io.read_dataset_system_biological_annotations(path)
    assert not io.validate_dataset_system_biological_annotations(path).passed


@pytest.mark.parametrize(
    "payload", [b"{", b"[]", b"null", b"\xff", b'{"a":1,"a":2}', b"NaN"]
)
def test_malformed(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    assert not io.validate_dataset_system_biological_annotations(path).passed


def test_atomic_failure_preserves_existing_file(tmp_path, monkeypatch):
    import os

    path = tmp_path / "metadata.json"
    io.write_dataset_system_biological_annotations(metadata(), path)
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("private path must not leak")

    monkeypatch.setattr(os, "replace", fail)
    result = io.write_dataset_system_biological_annotations(
        metadata(), path, overwrite=True
    )
    assert not result.passed
    assert "private" not in result.error
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_unicode_preserved_and_invalid_utf8_serialization_portable(tmp_path):
    path = tmp_path / "metadata.json"
    data = metadata(glycosylation_sites=(glyco(source="controlled \u00e9 evidence"),))
    assert io.write_dataset_system_biological_annotations(data, path).passed
    assert io.read_dataset_system_biological_annotations(path) == data
    before = path.read_bytes()
    invalid = metadata(glycosylation_sites=(glyco(source="\ud800"),))
    result = io.write_dataset_system_biological_annotations(
        invalid, path, overwrite=True
    )
    assert not result.passed and result.error == "JSON serialization failed."
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
