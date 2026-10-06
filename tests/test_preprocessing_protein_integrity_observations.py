"""Normalize supported observations without overwriting producer bytes or issuing QC."""

import json

import pytest
from test_production_handoff import handoff_case

from mania.preprocessing.protein_integrity_observations import (
    read_protein_integrity,
    validate_protein_integrity,
)


def test_normalization_retains_original_and_distinct_unresolved_pbc(
    tmp_path, monkeypatch
):
    case = handoff_case(tmp_path, monkeypatch, produce=False)
    path = case.retained.source.compact_files["protein_integrity_observations"]
    evidence = read_protein_integrity(path)
    before = case.report.read_bytes()
    validate_protein_integrity(
        evidence, case.report, case.retained.source.compact_files["frame_evidence"]
    )
    assert case.report.read_bytes() == before
    assert evidence.scientific_pbc_status == "unresolved"
    assert evidence.protein_remains_broken is None
    assert evidence.protein_fragment_ids == [0]
    assert len(evidence.observations) == 41
    assert all(f.bond_representation_max_error_A == 0 for f in evidence.observations)


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate_frame",
        "frame_map",
        "nonfinite",
        "lineage",
        "unsourced_bool",
        "classification",
    ],
)
def test_strict_integrity_rejects_fabricated_observations(
    tmp_path, monkeypatch, damage
):
    case = handoff_case(tmp_path, monkeypatch, produce=False)
    path = case.retained.source.compact_files["protein_integrity_observations"]
    data = json.loads(path.read_text())
    if damage == "duplicate_frame":
        data["observations"][1] = data["observations"][0]
    if damage == "frame_map":
        data["observations"][1]["source_frame_index"] = 200
    if damage == "nonfinite":
        data["observations"][0]["protein_center_error_A"] = float("nan")
    if damage == "lineage":
        data["source_bindings"]["raw_trajectory"]["sha256"] = "f" * 64
    if damage == "unsourced_bool":
        data["protein_remains_broken"] = False
    if damage == "classification":
        data["scientific_pbc_status"] = "passed"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evidence = read_protein_integrity(path)
        validate_protein_integrity(
            evidence, case.report, case.retained.source.compact_files["frame_evidence"]
        )
