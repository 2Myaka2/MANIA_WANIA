"""Strict controls and publication manifest roundtrips and portability."""

import json
from dataclasses import replace

import pytest
from test_dataset_release_workflow import make_release_case

from mania.dataset_release_manifest import DatasetReleaseManifest
from mania.dataset_release_manifest_io import (
    read_dataset_release_export_manifest,
    read_dataset_release_manifest,
    write_dataset_release_export_manifest,
    write_dataset_release_manifest,
)


@pytest.fixture(scope="module")
def control(tmp_path_factory):
    return make_release_case(tmp_path_factory.mktemp("manifest-inputs"))[1]


def test_control_roundtrip_determinism_and_overwrite(control, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert write_dataset_release_export_manifest(control, a).written
    assert read_dataset_release_export_manifest(a) == control
    assert write_dataset_release_export_manifest(control, b).written
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes().endswith(b"\n")
    assert not write_dataset_release_export_manifest(control, a).written
    assert write_dataset_release_export_manifest(control, a, overwrite=True).written


@pytest.mark.parametrize(
    "field,value",
    [
        ("unknown", 1),
        ("dataset_id", True),
        ("schema_version", "wrong"),
        ("kind", "wrong"),
        ("decision_set_path", None),
        ("canonical_bindings", {}),
        ("scientific_release_replica_keys", [["short"]]),
        ("qc_summary_path", "/absolute/file.csv"),
        ("qc_summary_path", "../file.csv"),
        ("qc_summary_path", "~/file.csv"),
        ("qc_summary_path", "$HOME/file.csv"),
        ("qc_summary_path", "a\\file.csv"),
        ("qc_summary_path", "C:/file.csv"),
    ],
)
def test_strict_export_control_fields(control, tmp_path, field, value):
    payload = control.to_dict() | {field: value}
    path = tmp_path / "control.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        read_dataset_release_export_manifest(path)


@pytest.mark.parametrize(
    "slot", ["stage31_run", "stage32_run", "canonical_bindings", "annotation_bindings"]
)
def test_nested_unknown_fields_rejected(control, tmp_path, slot):
    payload = json.loads(json.dumps(control.to_dict()))
    target = payload[slot][0] if isinstance(payload[slot], list) else payload[slot]
    target["unrecognized"] = 1
    path = tmp_path / "control.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        read_dataset_release_export_manifest(path)


def test_duplicate_json_keys_and_nonfinite(control, tmp_path):
    path = tmp_path / "control.json"
    for content in ('{"dataset_id": "a", "dataset_id": "b"}', '{"dataset_id": NaN}'):
        path.write_text(content)
        with pytest.raises(ValueError):
            read_dataset_release_export_manifest(path)
    with pytest.raises(ValueError):
        replace(
            control,
            scientific_release_replica_keys=control.scientific_release_replica_keys * 2,
        )


def release_manifest():
    return DatasetReleaseManifest(
        "dataset",
        "qc/decisions.json",
        "qc/derived.json",
        "aggregate/run_provenance.json",
    )


def test_publication_manifest_roundtrip_and_registry(tmp_path):
    model = release_manifest()
    path = tmp_path / "dataset_manifest.json"
    assert write_dataset_release_manifest(model, path).written
    assert read_dataset_release_manifest(path) == model
    payload = json.loads(path.read_text())
    assert len(payload["publication_artifacts"]) == 20
    assert payload["release_version"] == "1.0"
    assert "sha256" not in payload
    assert not write_dataset_release_manifest(model, path).written


@pytest.mark.parametrize(
    "field,value",
    [
        ("release_version", "0.1"),
        ("unknown", 1),
        ("canonical_reference_id", "wrong"),
        ("canonical_reference_sequence_sha256", "0" * 64),
        ("production_execution_dag", ["27", "28", "29", "30", "31", "32", "33"]),
        ("publication_artifacts", []),
        ("release_table_count", 17.0),
        ("release_json_count", True),
        ("authoritative_stage31_aggregation_source", "/local/run.json"),
    ],
)
def test_publication_manifest_strict_fields(tmp_path, field, value):
    path = tmp_path / "dataset_manifest.json"
    path.write_text(json.dumps(release_manifest().to_dict() | {field: value}))
    with pytest.raises(ValueError):
        read_dataset_release_manifest(path)
