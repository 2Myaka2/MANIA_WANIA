"""Synthetic downstream guards; no real-data assumptions or coordinate reads."""

import csv
import hashlib
import importlib.util
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_dataset_release_workflow import make_release_case
from test_replica_protein_edge_aggregation import group, row, table

from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_source_authority import (
    validate_publication_metric_sources,
    validate_release_canonical_source_authority,
)
from mania.dataset_release_workflow import build_dataset_release
from mania.replica_aggregation_tables import (
    build_canonical_protein_edge_replica_aggregation_table,
)
from mania.replica_aggregation_workflow import load_replica_aggregation_inputs
from mania.replica_protein_edge_aggregation import (
    aggregate_canonical_protein_edges_across_replicas,
)

spec = importlib.util.spec_from_file_location(
    "stage34c_downstream",
    Path(__file__).parents[1] / "tools/stage34c_three_replica_downstream.py",
)
downstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downstream)


@pytest.mark.parametrize("replica", ["2", "3"])
def test_manual_assessment_binds_only_exact_replica(replica):
    authority = downstream.manual_authority(replica)
    downstream.validate_manual(authority, replica)
    assert authority["drift_detected"] is False
    assert authority["reviewer"] == downstream.REVIEWER
    assert "NOT a stability assessment" in authority["scope"]
    other = "3" if replica == "2" else "2"
    with pytest.raises(ValueError, match="replica-specific"):
        downstream.validate_manual(authority, other)
    authority["system_identity"] = downstream.identity("1")
    authority["reviewer"] = "Ramilya Akhmetovna"
    with pytest.raises(ValueError, match="replica-specific"):
        downstream.validate_manual(authority, replica)


@pytest.mark.parametrize(
    "field,value",
    [
        ("drift_detected", None),
        ("drift_detected", 0),
        ("scope", "full trajectory"),
        ("pilot_interval_ns", [0, 100]),
        ("recorded_maximum_A", 2.0),
        ("basis", "another curve"),
    ],
)
def test_no_inferred_or_extended_manual_authority(field, value):
    authority = downstream.manual_authority("2") | {field: value}
    with pytest.raises(ValueError):
        downstream.validate_manual(authority, "2")


def rmsd_case(replica):
    values = downstream.RMSD_VALUES[replica]
    method = dict(
        replica_id=replica,
        reference_replica_id=replica,
        selection="protein and name CA",
        n_atoms_used=690,
        n_residues=690,
        reference_prepared_frame_index=0,
        reference_scientific_time_ns=0.1,
        alignment="equal-weight Kabsch proper rotation; same CA fit and measurement",
        rmsd_unit="angstrom",
        internal_mic=False,
        threshold=None,
        prepared_trajectory={"sha256": "prepared"},
        psf={"sha256": "shared"},
        selected_atoms=[
            dict(index=i, resid=i + 1, name="CA", segid="PROA") for i in range(690)
        ],
        rmsd_values_A=values,
        frames=[dict(frame=i, time_ps=(i + 1) * 100) for i in range(5)],
        source_frame_map=[
            dict(
                prepared_frame_index=i,
                source_dcd_frame_index=i,
                requested_sample_index=i,
                authoritative_time_ps=(i + 1) * 100,
            )
            for i in range(5)
        ],
    )
    rows = [
        dict(
            replica_id=replica,
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            scientific_time_ns=(i + 1) / 10,
            rmsd_A=v,
        )
        for i, v in enumerate(values)
    ]
    return method, rows


@pytest.mark.parametrize("replica", ["2", "3"])
def test_exact_rmsd_evidence_without_recalculation(replica, monkeypatch):
    forbidden = Mock(side_effect=AssertionError("RMSD computation forbidden"))
    monkeypatch.setattr(downstream.prior.accepted, "aligned_rmsd", forbidden)
    method, rows = rmsd_case(replica)
    downstream.validate_rmsd(
        replica, method, rows, method["prepared_trajectory"], method["psf"]
    )
    forbidden.assert_not_called()


@pytest.mark.parametrize("replica", ["2", "3"])
def test_manual_binding_enters_accepted_review_model(tmp_path, replica):
    method, rows = rmsd_case(replica)
    base = tmp_path / f"history/c1/replica{replica}"
    base.mkdir(parents=True)
    prepared = {"sha256": "prepared", "path": "prepared.xtc", "size_bytes": 12}
    method["prepared_trajectory"] = prepared
    for name, data in (
        ("rmsd_method.json", method),
        ("prepared_trajectory_identity.json", prepared),
        ("authority.json", {"shared": {"psf": method["psf"]}}),
    ):
        (base / name).write_text(json.dumps(data))
    (base / "rmsd_evidence.png").write_bytes(b"synthetic test image")
    with (base / "rmsd_evidence.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    assessment = downstream.bind_manual(replica, tmp_path)
    assert assessment.drift_detected is False
    assert assessment.evidence[0].evidence_type == "artifact"
    record = json.loads(
        (tmp_path / f"r{replica}_manual_rmsd_assessment.json").read_text()
    )
    assert record["automatic_threshold"] is None
    assert record["rmsd_recalculated"] is False
    assert record["system_identity"] == downstream.identity(replica)


@pytest.mark.parametrize("inventory", [False, True])
def test_pinned_historical_archive_with_or_without_inventory(tmp_path, inventory):
    base = tmp_path / "history"
    base.mkdir()
    content = b"accepted test evidence"
    (base / "record.txt").write_bytes(content)
    with zipfile.ZipFile(base.with_suffix(".zip"), "w") as archive:
        archive.writestr("record.txt", content)
        if inventory:
            archive.writestr(
                "evidence_inventory.json",
                json.dumps(
                    {
                        "files": [
                            dict(
                                path="record.txt",
                                sha256=hashlib.sha256(content).hexdigest(),
                            )
                        ]
                    }
                ),
            )
    digest = downstream.file_record(base.with_suffix(".zip"))["sha256"]
    target = tmp_path / "copy"
    downstream.verified_copy(base, digest, target, lambda n: True)
    assert (target / "record.txt").read_bytes() == content
    (base / "record.txt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact changed"):
        downstream.verified_copy(base, digest, target, lambda n: True)


def test_no_fake_optional_metric(tmp_path, monkeypatch):
    target = tmp_path / "history/publication"
    target.mkdir(parents=True)
    (target / "publication_inputs.json").write_text(json.dumps({"metrics": [{}]}))
    # Historical supplied metrics are no longer a construction input. The
    # constructor's authority guards are exercised in its dedicated tests.
    monkeypatch.setattr(
        downstream.publication, "construct_contact_definitions", lambda *_: []
    )
    monkeypatch.setattr(downstream, "publication_software", lambda *_: [])
    inputs = downstream.publication_inputs(tmp_path)
    assert inputs.metrics == ()
    payload = json.loads((tmp_path / "publication_inputs.json").read_text())
    assert payload["metrics"] == []


@pytest.mark.parametrize(
    "mutation",
    ["replica", "reference", "atom", "time", "value", "threshold", "prepared"],
)
def test_rmsd_binding_rejects_substitution(mutation):
    method, rows = rmsd_case("2")
    prepared = method["prepared_trajectory"].copy()
    if mutation == "replica":
        method["reference_replica_id"] = "1"
    elif mutation == "reference":
        method["reference_prepared_frame_index"] = 1
    elif mutation == "atom":
        method["selected_atoms"][0]["name"] = "CB"
    elif mutation == "time":
        rows[0]["scientific_time_ns"] = 0
    elif mutation == "value":
        rows[1]["rmsd_A"] = 2.0
    elif mutation == "threshold":
        method["threshold"] = 2.1
    else:
        prepared["sha256"] = "other"
    with pytest.raises(ValueError):
        downstream.validate_rmsd("2", method, rows, prepared, method["psf"])


def decisions():
    return SimpleNamespace(
        records=tuple(
            SimpleNamespace(
                replica_key=downstream.key(r),
                qc_status="pass",
                release_decision="available",
            )
            for r in downstream.REPLICAS
        )
    )


def test_three_available_decision_population():
    downstream.require_three_decisions(decisions())


@pytest.mark.parametrize(
    "state", ["pending_review", "excluded", "unknown", "unresolved"]
)
def test_nonavailable_decision_stops_before_manifest(state):
    value = decisions()
    value.records[1].release_decision = state
    with pytest.raises(ValueError, match="QC decision gate STOP"):
        downstream.require_three_decisions(value)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "system", "missing", "fourth", "not_ready"]
)
def test_group_population_rejected(mutation):
    value = decisions()
    if mutation == "duplicate":
        value.records = (value.records[0], value.records[0], value.records[2])
    elif mutation == "system":
        value.records[1].replica_key = ("other", *value.records[1].replica_key[1:])
    elif mutation == "missing":
        value.records = value.records[:2]
    elif mutation == "fourth":
        value.records += (value.records[0],)
    with pytest.raises(ValueError, match="QC decision gate STOP"):
        downstream.require_three_decisions(value, ready=mutation != "not_ready")


@pytest.mark.parametrize("mutation", [None, "duplicate", "cross_system", "pending"])
def test_manifest_exact_population_without_specialized_correspondence(
    tmp_path, mutation
):
    hards = [
        SimpleNamespace(identity=DatasetTrajectoryIdentity(**downstream.identity(r)))
        for r in downstream.REPLICAS
    ]
    temporal = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                dataset_spec=SimpleNamespace(
                    temporal=SimpleNamespace(
                        production_start_ns=0.1,
                        production_end_ns=0.5,
                        frame_stride_ps=100,
                        window_length_ns=0.4,
                        window_step_ns=0.4,
                        overlap_percent=0,
                    )
                ),
                window_plan=SimpleNamespace(
                    windows=(SimpleNamespace(window_id="window_0001", window_index=0),)
                ),
                sampling_plan=SimpleNamespace(requested_sample_count=5),
            ),
        )
    )
    qc = decisions()
    if mutation == "duplicate":
        hards[1] = hards[0]
    elif mutation == "cross_system":
        hards[1].identity = hards[1].identity.model_copy(update={"system_id": "other"})
    elif mutation == "pending":
        qc.records[1].release_decision = "pending_review"

    def build():
        return downstream.group_template(
            hards,
            [temporal] * 3,
            [tmp_path / f"r{r}.csv" for r in downstream.REPLICAS],
            qc,
        )

    if mutation:
        with pytest.raises(ValueError):
            build()
    else:
        manifest = build()
        assert manifest.groups[0].spec.expected_replica_ids == ("1", "2", "3")
        assert [m.replica_key for m in manifest.groups[0].members] == [
            downstream.key(r) for r in downstream.REPLICAS
        ]
        assert all(
            m.availability_status == "available" for m in manifest.groups[0].members
        )
        assert not manifest.groups[0].lipid_correspondences.correspondences
        assert not manifest.groups[0].glycan_correspondences.correspondences
        assert (
            manifest.lipid_canonical_table_paths
            == manifest.glycan_canonical_table_paths
            == ()
        )


def aggregate_case(statuses=("available",) * 3):
    request = group(statuses)
    source = table(row("1", 0.6), row("2", 0.2))
    production = aggregate_canonical_protein_edges_across_replicas(request, source)
    aggregate = build_canonical_protein_edge_replica_aggregation_table((production,))
    expected, vectors = downstream.reconstruct((source,), request)
    return expected, vectors, [r.to_dict() for r in aggregate.rows]


def test_available_sparse_zero_mean_median_support_sample_sd():
    expected, vectors, observed = aggregate_case()
    assert downstream.compare_aggregate(expected, observed)["status"] == "PASS"
    assert vectors[0]["vector"] == [0.6, 0.2, 0]
    assert vectors[0]["n_replicates_available"] == 3
    assert vectors[0]["median_occupancy"] == 0.2
    assert vectors[0]["n_replicates_supporting"] == 2
    assert vectors[0]["support_fraction"] == 2 / 3
    assert vectors[0]["std_occupancy"] == pytest.approx(0.30550504633038933)
    assert vectors[0]["std_occupancy"] != pytest.approx(0.2494438257849294)


@pytest.mark.parametrize("state", ["excluded", "unavailable"])
def test_excluded_or_unavailable_never_zero_or_denominator(state):
    expected, vectors, observed = aggregate_case(("available", state, "available"))
    assert vectors[0]["vector"] == [0.6, 0]
    assert vectors[0]["n_replicates_available"] == 2
    assert vectors[0]["mean_occupancy"] == vectors[0]["median_occupancy"] == 0.3
    assert downstream.compare_aggregate(expected, observed)["status"] == "PASS"


def test_single_available_null_sd():
    expected, vectors, observed = aggregate_case(
        ("available", "excluded", "unavailable")
    )
    assert vectors[0]["std_occupancy"] is None
    assert vectors[0]["vector"] == [0.6]
    assert downstream.compare_aggregate(expected, observed)["status"] == "PASS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("mean_occupancy", 0.4),
        ("median_occupancy", 0.6),
        ("std_occupancy", 0.2494438257849294),
        ("std_occupancy", None),
        ("n_replicates_available", 2),
        ("n_replicates_supporting", 1),
        ("support_fraction", 1.0),
        ("condition", "OTHER"),
    ],
)
def test_aggregate_tampering_detected(field, value):
    expected, _, observed = aggregate_case()
    observed[0][field] = value
    check = downstream.compare_aggregate(expected, observed)
    assert check["status"] == "FAIL" and check["aggregate_mismatches"] == 1
    with pytest.raises(ValueError, match="before independent"):
        downstream.require_verified(check)


def test_missing_extra_and_duplicate_aggregate_rows():
    expected, _, observed = aggregate_case()
    assert downstream.compare_aggregate(expected, [])["missing_rows"] == 1
    assert downstream.compare_aggregate({}, observed)["extra_rows"] == 1
    assert downstream.compare_aggregate(expected, observed * 2)["extra_rows"] == 1


def test_stage33_cannot_run_before_verification(tmp_path, monkeypatch):
    called = Mock(side_effect=AssertionError("Publication must not start"))
    monkeypatch.setattr(downstream, "run_dataset_release", called)
    with pytest.raises(ValueError, match="before independent"):
        downstream.publish({}, None, None, None, None, None, None, None, tmp_path, {})
    called.assert_not_called()


@pytest.fixture(scope="module")
def release_case(tmp_path_factory):
    root = tmp_path_factory.mktemp("c2-release")
    path, control = make_release_case(root)
    bundle = build_dataset_release(path)
    return path, control, bundle


def test_f1_source_substitution_rejected(release_case):
    path, control, bundle = release_case
    used = bundle.aggregation_authority.aggregation_manifest_used
    canonical = load_replica_aggregation_inputs(used)
    canonical["protein"] = type(canonical["protein"])(())
    with pytest.raises(ValueError, match="canonical"):
        validate_release_canonical_source_authority(control, used, canonical)


def test_f2_missing_metric_source_rejected(release_case):
    path, control, bundle = release_case
    inputs = read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    metric = replace(inputs.metrics[0], source_artifact_path="unbound.csv")
    inputs = replace(
        inputs,
        metrics=(metric,),
        metric_source_value_fields=(inputs.metric_source_value_fields[0],),
    )
    with pytest.raises(ValueError, match="canonical binding"):
        validate_publication_metric_sources(
            inputs, control, path.parent, bundle.metadata
        )


def test_missing_specialized_coverage_cannot_be_invented(release_case):
    path, control, _ = release_case
    changed = replace(
        control,
        canonical_bindings=tuple(
            b for b in control.canonical_bindings if b.family == "protein"
        ),
    )
    with pytest.raises(ValueError, match="Dataset release input failed"):
        other = path.parent / "missing_specialized.json"
        assert write_dataset_release_export_manifest(changed, other).written
        build_dataset_release(other)


def test_pilot_cannot_claim_full_trajectory():
    temporal = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                dataset_spec=SimpleNamespace(
                    identity=SimpleNamespace(
                        to_dict=lambda: downstream.identity("2", None)
                    ),
                    temporal=SimpleNamespace(
                        production_start_ns=0.1,
                        production_end_ns=100,
                        frame_stride_ps=100,
                    ),
                )
            ),
        )
    )
    with pytest.raises(ValueError, match="full 100-ns"):
        downstream.pilot_temporal(temporal, "2")


def test_stopped_release_has_no_implied_validation_pass(tmp_path):
    timings = {}
    downstream.finalize_gate_records(
        tmp_path, {"stop_gate": "publication", "reason": "missing evidence"}, timings
    )
    for name in (
        "stage33_f1_source_authority",
        "stage33_f2_metric_authority",
        "release_validation",
        "independent_publication_check",
    ):
        result = json.loads((tmp_path / f"{name}.json").read_text())
        assert result["status"] == "NOT RUN" and result["complete"] is False
    assert timings["f1_f2_validation_seconds"] is None


@pytest.mark.parametrize(
    "status,allowed",
    [
        (" M docs/stage34c_namd_three_replica.md", True),
        ("?? tools/stage34c_three_replica_downstream.py", True),
        ("?? tests/test_stage34c_three_replica_downstream.py", True),
        (" M Stage_34.md", False),
    ],
)
def test_checkpoint_handles_stripped_git_status(tmp_path, monkeypatch, status, allowed):
    def command(repo, work, argv):
        if argv == ["git", "branch", "--show-current"]:
            return "FAIR"
        if argv == ["git", "rev-parse", "HEAD"]:
            return "checkpoint"
        if argv == ["git", "status", "--short"]:
            return status.strip()  # Accepted command helper strips outer whitespace.
        return ""

    monkeypatch.setattr(downstream.prior, "command", command)
    if allowed:
        assert downstream.checkpoint(tmp_path, tmp_path) == "checkpoint"
    else:
        with pytest.raises(ValueError, match="Unexpected working-tree change"):
            downstream.checkpoint(tmp_path, tmp_path)
