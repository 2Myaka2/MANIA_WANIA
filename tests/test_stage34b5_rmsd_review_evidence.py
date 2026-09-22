"""Focused software checks for the standalone, observation-only RMSD helper."""

import copy
import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "rmsd_review", Path(__file__).parents[1] / "tools/stage34b5_rmsd_review_evidence.py"
)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def frame_records():
    return [
        dict(
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            requested_sample_index=i,
            authoritative_time_ps=(i + 1) * 100.0,
        )
        for i in range(5)
    ]


def tetrahedron():
    return np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)


def binding(tmp_path):
    psf = tmp_path / "source.psf"
    prepared = tmp_path / "prepared.xtc"
    psf.write_bytes(b"synthetic topology binding")
    prepared.write_bytes(b"synthetic prepared binding")
    return {
        "authority": {"psf": review.file_record(psf)},
        "prepared": review.file_record(prepared),
    }


def test_exact_frame_and_scientific_time_contract():
    review.validate_frames(frame_records())
    assert review.FRAMES == (0, 1, 2, 3, 4)
    assert review.TIMES_NS == (0.1, 0.2, 0.3, 0.4, 0.5)


def test_temporal_schema_envelope_preserves_exact_contract():
    manifest_spec = {
        "identity": review.IDENTITY,
        "temporal": {"production_start_ns": 0.1, "production_end_ns": 0.5},
    }
    execution_spec = {
        "schema_version": "mania.dataset_trajectory_spec.v0.1",
        "kind": "mania_dataset_trajectory_spec",
        **copy.deepcopy(manifest_spec),
    }
    review.validate_temporal_binding([{"dataset_spec": execution_spec}], manifest_spec)
    execution_spec["temporal"]["production_end_ns"] = 0.6
    with pytest.raises(ValueError, match="Time contract differs"):
        review.validate_temporal_binding(
            [{"dataset_spec": execution_spec}], manifest_spec
        )


@pytest.mark.parametrize("count", [0, 4, 6])
def test_other_frame_counts_rejected(count):
    with pytest.raises(ValueError, match="five"):
        review.validate_frames((frame_records() * 2)[:count])
    with pytest.raises(ValueError, match="five"):
        review.calculate_twice(np.zeros((count, 4, 3)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("prepared_frame_index", 4),
        ("source_dcd_frame_index", 999),
        ("requested_sample_index", 1),
        ("authoritative_time_ps", 100.00000029814058),
    ],
)
def test_changed_mapping_or_raw_time_rejected(field, value):
    records = frame_records()
    records[0][field] = value
    with pytest.raises(ValueError, match="mapping/scientific times"):
        review.validate_frames(records)


def test_prepared_hash_guard(tmp_path):
    path = tmp_path / "prepared.xtc"
    path.write_bytes(b"synthetic accepted bytes")
    assert review.require_hash(path, review.digest(path)) == review.file_record(path)
    assert review.PREPARED_SHA256 == (
        "3f9ac9353ad0a6c551845d166651a0ade0436ee5b815c297ff45f9dfa3d0b28c"
    )
    with pytest.raises(ValueError, match="SHA256"):
        review.require_hash(path, review.PREPARED_SHA256)


def test_kabsch_known_transform_scaling_and_reflection():
    reference = tetrahedron()
    rotated = reference @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]) + [4, -7, 9]
    assert review.aligned_rmsd(rotated, reference) < 1e-12
    assert review.aligned_rmsd(reference * 2, reference) == pytest.approx(np.sqrt(3))
    # A mirror image must not be superposed using an improper rotation.
    assert review.aligned_rmsd(reference * [-1, 1, 1], reference) == pytest.approx(2)


def test_same_atoms_fixed_first_reference_repeat_and_no_mutation(monkeypatch):
    coords = np.stack([tetrahedron() * (i + 1) for i in range(5)])
    before = coords.copy()
    coords.setflags(write=False)
    original = review.aligned_rmsd
    observed = []

    def observe(mobile, reference):
        observed.append((mobile.copy(), reference.copy()))
        return original(mobile, reference)

    monkeypatch.setattr(review, "aligned_rmsd", observe)
    runs, difference = review.calculate_twice(coords)
    assert len(observed) == 10
    for i, (mobile, reference) in enumerate(observed):
        np.testing.assert_array_equal(mobile, before[i % 5])
        np.testing.assert_array_equal(reference, before[0])
    np.testing.assert_array_equal(coords, before)
    assert runs[0] == runs[1] and difference == 0
    assert runs[0][0] == original(before[0], before[0])
    assert runs[0][0] < 1e-10


def test_self_reference_value_is_not_overwritten(monkeypatch):
    monkeypatch.setattr(review, "aligned_rmsd", lambda *_: 3e-14)
    runs, _ = review.calculate_twice(np.stack([tetrahedron()] * 5))
    assert runs[0][0] == 3e-14


def test_nonfinite_coordinates_rejected():
    coords = tetrahedron()
    coords[0, 0] = np.nan
    with pytest.raises(ValueError, match="Invalid atoms"):
        review.aligned_rmsd(coords, tetrahedron())


def test_run_preserves_pending_state_and_never_invokes_downstream(
    tmp_path, monkeypatch
):
    pytest.importorskip("matplotlib")
    local = tmp_path / "local_md"
    local.mkdir()
    pending_path = local / "pending.json"
    pending = {
        "replica_key": [
            review.IDENTITY[k]
            for k in ("dataset_id", "system_id", "trajectory_id", "replica_id")
        ],
        "status": "pending_review",
        "production_ready": False,
        "reviewer": None,
        "authoritative_release_decision": None,
    }
    summary = {
        "hard_qc_status": "pass",
        "qc_decision_status": "pending_review",
        "production_ready": False,
        "qc_derived_stage31_manifest": "NOT RUN",
        "stage31_aggregation": "NOT RUN",
        "stage33_publication": "NOT RUN",
    }
    originals = copy.deepcopy((pending, summary))
    review.validate_pending(pending, summary)
    assert (pending, summary) == originals
    review.dump(pending_path, pending)
    before = pending_path.read_bytes()
    source = binding(local)
    dcd = local / "source.dcd"
    dcd.write_bytes(b"do not read coordinates")
    source.update(
        source={"dcd": {"path": str(dcd)}},
        dcd_stat={"size_bytes": dcd.stat().st_size, "mtime_ns": dcd.stat().st_mtime_ns},
    )
    monkeypatch.setattr(review, "bind_inputs", lambda *_: source)
    monkeypatch.setattr(
        review,
        "protected_snapshot",
        lambda *_: {str(pending_path): review.digest(pending_path)},
    )
    monkeypatch.setattr(
        review,
        "load_coordinates",
        lambda *_: (
            np.stack([tetrahedron() * (i + 1) for i in range(5)]),
            [{}] * 4,
            [],
        ),
    )
    monkeypatch.setattr(review, "CONTRACT_SOURCES", {})
    commands = []

    def git_only(argv, **kwargs):
        assert argv[0] == "git", "Only read-only repository inspection may run"
        assert argv[1] in {
            "branch",
            "rev-parse",
            "status",
            "merge-base",
            "log",
            "diff",
            "check-ignore",
        }
        commands.append(argv)
        output = "FAIR\n" if argv[1] == "branch" else ""
        if argv[1:3] == ["rev-parse", "HEAD"]:
            output = "synthetic-head\n"
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(review.subprocess, "run", git_only)
    work = review.run(tmp_path)
    assert pending_path.read_bytes() == before
    assert commands
    with (work / "rmsd_evidence.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5
    assert [float(r["scientific_time_ns"]) for r in rows] == list(review.TIMES_NS)
    assert [int(r["source_dcd_frame_index"]) for r in rows] == list(review.FRAMES)
    assert {r["reference_prepared_frame_index"] for r in rows} == {"0"}
    method = json.loads((work / "rmsd_method.json").read_text())
    assert method["alignment_selection"] == method["rmsd_selection"] == review.SELECTION
    assert method["method_status"] == "documented_review_fallback"
    assert method["statements"] == [
        "no automatic RMSD threshold applied",
        "no drift decision made",
    ]
    assert method["scientific_pbc_status"] == "unresolved"
    assert method["internal_mic"] is False
    for path in work.glob("*.json"):
        text = path.read_text()
        assert '"drift_detected"' not in text
        assert '"rmsd_threshold"' not in text
        assert '"drift_threshold"' not in text
    assert (work / "rmsd_evidence.png").read_bytes().startswith(b"\x89PNG")
    assert work.with_suffix(".zip").is_file()


def test_binding_failure_stops_before_coordinates_or_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review.subprocess,
        "run",
        lambda argv, **_: SimpleNamespace(
            returncode=0, stdout="FAIR" if argv[1] == "branch" else "", stderr=""
        ),
    )
    monkeypatch.setattr(
        review, "bind_inputs", Mock(side_effect=ValueError("binding differs"))
    )
    reader = Mock(
        side_effect=AssertionError("No coordinate reads after binding failure")
    )
    monkeypatch.setattr(review, "load_coordinates", reader)
    with pytest.raises(ValueError, match="binding differs"):
        review.run(tmp_path)
    reader.assert_not_called()
    assert not list(tmp_path.iterdir())
