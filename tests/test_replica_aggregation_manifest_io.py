"""Strict JSON, pinned controls and relative path round trips."""

import json
from copy import deepcopy

import pytest
from test_replica_aggregation_manifest import make_manifest

from mania.replica_aggregation_manifest_io import (
    ReplicaAggregationManifestReadError,
    read_replica_aggregation_manifest,
    validate_replica_aggregation_manifest,
    write_replica_aggregation_manifest,
)


def test_manifest_roundtrip_portable_deterministic(tmp_path):
    manifest, path = make_manifest(tmp_path, complete=True)
    original = path.read_bytes()
    assert read_replica_aggregation_manifest(path) == manifest
    assert validate_replica_aggregation_manifest(path).group_count == 5
    assert original.endswith(b"\n") and not original.endswith(b"\n\n")
    assert str(tmp_path).encode() not in original
    assert not write_replica_aggregation_manifest(manifest, path).written
    assert write_replica_aggregation_manifest(manifest, path, overwrite=True).written
    assert path.read_bytes() == original
    assert read_replica_aggregation_manifest(path).groups[1].spec.condition is None


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_root",
        "missing_root",
        "reference",
        "unknown_spec",
        "unknown_member",
        "unknown_window",
        "unknown_correspondence",
        "unknown_binding",
        "bool_integer",
        "string_float",
        "invalid_bool",
        "missing_expected",
        "empty_paths",
        "null_paths",
        "path_number",
        "reference_member",
        "reference_spec",
        "incomplete_lipid",
        "incomplete_glycan",
        "mixed_engine",
        "bounds",
        "nonfinite",
    ],
)
def test_strict_manifest_rejections(tmp_path, mutation):
    _, path = make_manifest(tmp_path)
    data = json.loads(path.read_text())
    g = data["groups"][0]
    if mutation.startswith("unknown_"):
        target = {
            "root": data,
            "spec": g["spec"],
            "member": g["members"][0],
            "window": g["spec"]["window"],
            "correspondence": g["lipid_correspondences"]["correspondences"][0],
            "binding": g["lipid_correspondences"]["correspondences"][0]["members"][0],
        }[mutation.removeprefix("unknown_")]
        target["unknown"] = 1
    elif mutation == "missing_root":
        del data["groups"]
    elif mutation.startswith("reference"):
        target = (
            data
            if mutation == "reference"
            else (g["spec"] if mutation == "reference_spec" else g["members"][0])
        )
        target["canonical_reference_sequence_sha256"] = "0" * 64
    elif mutation == "bool_integer":
        g["spec"]["window"]["window_index"] = True
    elif mutation == "string_float":
        g["spec"]["window"]["window_length_ns"] = "5.0"
    elif mutation == "invalid_bool":
        g["spec"]["window"]["right_endpoint_inclusive"] = 0
    elif mutation == "missing_expected":
        g["members"].pop()
    elif mutation == "empty_paths":
        for f in ("protein", "lipid", "glycan"):
            data[f"{f}_canonical_table_paths"] = []
    elif mutation == "null_paths":
        data["protein_canonical_table_paths"] = None
    elif mutation == "path_number":
        data["protein_canonical_table_paths"] = [42]
    elif mutation.startswith("incomplete_"):
        kind = mutation.removeprefix("incomplete_")
        g[f"{kind}_correspondences"]["correspondences"][0]["members"].pop()
    elif mutation == "mixed_engine":
        g["members"][0]["engine"] = "namd"
    elif mutation == "bounds":
        g["members"][0]["window"].update(
            requested_window_start_ns=22.5,
            requested_window_end_ns=27.5,
        )
    else:
        g["spec"]["window"]["window_length_ns"] = float("nan")
    path.write_text(json.dumps(data))
    with pytest.raises(ReplicaAggregationManifestReadError):
        read_replica_aggregation_manifest(path)
    assert not validate_replica_aggregation_manifest(path).passed


def test_duplicate_json_key_and_wrong_collection_type(tmp_path):
    _, path = make_manifest(tmp_path)
    data = path.read_text()
    path.write_text(data.replace('"groups":', '"groups": [], "groups":', 1))
    assert not validate_replica_aggregation_manifest(path).passed
    payload = deepcopy(json.loads(data))
    payload["groups"][0]["lipid_correspondences"] = []
    path.write_text(json.dumps(payload))
    assert not validate_replica_aggregation_manifest(path).passed
