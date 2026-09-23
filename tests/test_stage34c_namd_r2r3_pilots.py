"""Synthetic orchestration gates; no local real inputs are used by tests."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from test_namd_authority import config_log, time_control

mda = pytest.importorskip("MDAnalysis")
spec = importlib.util.spec_from_file_location(
    "stage34c_pilots", Path(__file__).parents[1] / "tools/stage34c_namd_r2r3_pilots.py"
)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def bound_control(tmp_path, replica):
    paths = pilot.source_paths(tmp_path, replica)
    paths["conf"].parent.mkdir(parents=True, exist_ok=True)
    config, log = config_log(paths["conf"].parent)
    config.rename(paths["conf"])
    log.rename(paths["out"])
    paths["dcd"].write_bytes(b"synthetic header binding")
    raw = pilot.DCDIdentity(
        path=str(paths["dcd"]),
        size_bytes=paths["dcd"].stat().st_size,
        atom_count=4,
        frame_count=1000,
        istart=50000,
        nsavc=50000,
        delta=0.04090965911746025,
        dt_ps=100.00000029814058,
        unit_cell=True,
        remarks="FILENAME=original.dcd CREATED BY NAMD",
        observed_times=tuple(
            pilot.RawFrameTime(frame=i, time_ps=(i + 1) * 100.00000029814058)
            for i in range(5)
        ),
    )
    return paths, time_control(paths["conf"], paths["out"], raw)


@pytest.mark.parametrize("replica", ["2", "3"])
def test_exact_source_paths_and_independent_time(tmp_path, replica):
    paths, control = bound_control(tmp_path, replica)
    pilot.validate_replica_time(control, paths["dcd"], replica)
    assert paths["dcd"].parent.name == "raw"
    assert paths["dcd"].parent.parent.name == "egor_2ss_r1"
    assert paths["dcd"].name == f"MD_2_bonds_W_I_PMm_100_ns_{replica}.dcd"
    assert control.scientific_times_ps[:5] == (
        "100.0",
        "200.0",
        "300.0",
        "400.0",
        "500.0",
    )
    assert control.dcd.observed_times[0].time_ps == 100.00000029814058
    paths["out"].write_text(
        paths["out"].read_text().replace("TIMESTEP 2", "TIMESTEP 3")
    )
    with pytest.raises(ValueError, match="Stale source"):
        pilot.validate_replica_time(control, paths["dcd"], replica)


@pytest.mark.parametrize("replica", ["1", "4", "", 2])
def test_other_replicas_forbidden(tmp_path, replica):
    with pytest.raises(ValueError, match="Only new replicas"):
        pilot.source_paths(tmp_path, replica)


def test_wrong_replica_time_control_rejected(tmp_path):
    paths, control = bound_control(tmp_path, "2")
    with pytest.raises(ValueError, match="Wrong-replica"):
        pilot.validate_replica_time(control, paths["dcd"], "3")


def test_intake_exact_source_hash_blocks_before_header(tmp_path, monkeypatch):
    paths = pilot.source_paths(tmp_path, "2")
    paths["conf"].parent.mkdir(parents=True)
    paths["conf"].write_text("changed")
    intake = tmp_path / "intake"
    intake.mkdir()
    pilot.dump(intake / "per_replica_time_authority_check.json", {"2": {}})
    monkeypatch.setattr(
        pilot.b3,
        "csv_rows",
        lambda _: [
            {
                "replica_id": "2",
                "configuration_path": str(paths["conf"]),
                "configuration_sha256": "0" * 64,
            }
        ],
    )
    header = Mock(side_effect=AssertionError("DCD access forbidden"))
    monkeypatch.setattr(pilot, "dcd_header", header)
    with pytest.raises(ValueError, match="Wrong conf SHA256"):
        pilot.bind_sources(tmp_path, "2", intake)
    header.assert_not_called()


def test_shared_psf_must_match_before_topology_open(tmp_path, monkeypatch):
    intake = tmp_path / "intake"
    intake.mkdir()
    pilot.dump(
        intake / "input_compatibility.json",
        {"canonical_mapping": {"binding": {"sha256": "0" * 64}}},
    )
    psf = tmp_path / "namd/egor_2ss_r1/raw/MD_2_bonds_NPT_W_I_PMm_100_ns.psf"
    psf.parent.mkdir(parents=True)
    psf.write_bytes(b"wrong topology")
    universe = Mock(side_effect=AssertionError("Topology open forbidden"))
    monkeypatch.setattr(pilot.mda, "Universe", universe)
    with pytest.raises(ValueError, match="Wrong.*SHA256"):
        pilot.shared_authority(tmp_path, intake, tmp_path)
    universe.assert_not_called()


def test_header_parser_no_coordinate_initialization_and_five_only(tmp_path):
    path = tmp_path / "tiny.dcd"
    u = mda.Universe.empty(4, trajectory=True)
    u.dimensions = [10, 10, 10, 90, 90, 90]
    with mda.Writer(str(path), n_atoms=4, dt=100, nsavc=50000, istart=50000) as writer:
        for i in range(6):
            u.atoms.positions = np.full((4, 3), i, dtype=np.float32)
            writer.write(u)
    h = pilot.dcd_header(path)
    assert h["frame_count"] == 6 and h["atom_count"] == 4
    intake = tmp_path / "intake"
    intake.mkdir()
    pilot.dump(
        intake / "selected_frame_box_readiness.json",
        {
            "replicas": {
                "2": {"frames": [{"box_A_degrees": [10, 10, 10, 90, 90, 90]}] * 5}
            }
        },
    )
    control = SimpleNamespace(
        scientific_times_ps=pilot.TIMES_PS,
        dcd=SimpleNamespace(
            observed_times=[SimpleNamespace(time_ps=t) for t in pilot.TIMES_PS]
        ),
    )
    frames = pilot.read_selected(h, control, intake, "2", tmp_path)
    assert len(frames) == 5
    for i, (coords, _, actual) in enumerate(frames):
        assert np.all(coords == i) and actual == pilot.TIMES_PS[i]
    ledger = pilot.read(tmp_path / "selected_frames.json")
    assert ledger["source_coordinate_read_indexes"] == [0, 1, 2, 3, 4]
    assert ledger["initialization_reads"] == ledger["indexing_scans"] == []


@pytest.mark.parametrize("times", [(0, 100, 200, 300, 400), (100, 200, 300, 400, 501)])
def test_changed_five_frame_contract_rejected(times):
    with pytest.raises(ValueError, match="freeze"):
        pilot.b3.sampling_contract(times)


def test_manifests_preserve_science_with_separate_replica_paths(tmp_path):
    entries = []
    for replica in ("2", "3"):
        work = tmp_path / f"replica{replica}"
        entry = pilot.pilot_manifest(
            replica,
            tmp_path / "source.psf",
            work / "prepared_variant_c.xtc",
            tmp_path / "map.json",
            work,
        )["conditions"][0]
        entries.append(entry)
        assert entry["dataset_spec"]["identity"]["replica_id"] == replica
        assert entry["dataset_spec"]["identity"]["condition"] is None
        assert entry["metadata"]["source_membrane_label"] == "PMm"
        assert entry["dataset_spec"]["temporal"]["frame_stride_ps"] == 100
        assert "molecular_partner_metadata_path" not in entry
    assert entries[0]["trajectory_paths"] != entries[1]["trajectory_paths"]
    assert (
        entries[0]["dataset_spec"]["temporal"] == entries[1]["dataset_spec"]["temporal"]
    )


@pytest.mark.parametrize(
    "phase", ["variant_c_pbc_diagnostic", "persisted_pbc_validation"]
)
@pytest.mark.parametrize("gate", ["bonds", "protein", "centroids", "hbond_geometry"])
def test_substantive_mismatch_stops_before_mania(tmp_path, monkeypatch, phase, gate):
    monkeypatch.setattr(pilot, "validate_replica_time", lambda *_: None)
    good = dict(
        bonds={"all_topology_bonds": {"prepared_direct_disagreement_count": 0}},
        protein={"substantive_mismatches": 0},
        centroids={"substantive_mismatches": 0},
        hbond_geometry={"substantive_mismatches": 0},
    )
    for name in ("variant_c_pbc_diagnostic", "persisted_pbc_validation"):
        row = json.loads(json.dumps(good))
        if name == phase:
            if gate == "bonds":
                row[gate]["all_topology_bonds"][
                    "prepared_direct_disagreement_count"
                ] = 1
            else:
                row[gate]["substantive_mismatches"] = 1
        pilot.dump(tmp_path / f"{name}.json", {"frames": [row] * 5})
    science = Mock(side_effect=AssertionError("MANIA forbidden"))
    monkeypatch.setattr(pilot.b3, "run_mania", science)
    with pytest.raises(ValueError):
        pilot.run_protein(
            "2",
            None,
            None,
            None,
            SimpleNamespace(dcd=SimpleNamespace(path="source.dcd")),
            None,
            tmp_path,
            {},
        )
    science.assert_not_called()
    assert not (tmp_path / "science_started.json").exists()


def test_frozen_artifact_tampering_blocks_hard_qc(tmp_path, monkeypatch):
    source, frozen = tmp_path / "source.csv", tmp_path / "frozen/source.csv"
    frozen.parent.mkdir()
    source.write_text("measured real-science role in synthetic test")
    records = {"protein_edge": pilot.qc.freeze_file(source, frozen)}
    pilot.dump(tmp_path / "frozen_science.json", records)
    pilot.validate_freeze(tmp_path, records)
    frozen.write_text("changed after freeze")
    evaluator = Mock(side_effect=AssertionError("QC forbidden"))
    monkeypatch.setattr(pilot.qc, "hard_findings", evaluator)
    with pytest.raises(ValueError, match="Frozen size differs"):
        pilot.hard_qc(tmp_path, records, "2")
    evaluator.assert_not_called()


def test_r1_rmsd_authority_cannot_be_reused(tmp_path):
    pilot.dump(tmp_path / "authority.json", {"replica_id": "1"})
    with pytest.raises(ValueError, match="RMSD authority replica differs"):
        pilot.rmsd_evidence("2", None, None, tmp_path, "head")


def test_real_rmsd_writer_no_drift_decision(tmp_path):
    psf = tmp_path / "tiny.psf"
    psf.write_text(
        "PSF EXT\n\n         1 !NTITLE\n REMARKS synthetic CA\n\n"
        "       690 !NATOM\n"
        + "".join(
            f"{i:10d} {'PROA':<8} {i:<8} {'ALA':<8} {'CA':<8} {'C':<8} "
            f"{0.0:14.6f} {12.0:14.4f} {0:8d}\n"
            for i in range(1, 691)
        )
        + "\n         0 !NBOND: bonds\n"
    )
    prepared = tmp_path / "prepared.xtc"
    coords = np.random.default_rng(34).normal(size=(690, 3)).astype(np.float32)
    with pilot.b3.XTCFile(str(prepared), "w") as writer:
        for i, t in enumerate(pilot.TIMES_PS):
            writer.write(
                coords * (1 + i / 100) / 10,
                np.eye(3, dtype=np.float32) * 10,
                i,
                t,
                precision=1_000_000,
            )
    pilot.dump(tmp_path / "authority.json", {"replica_id": "2"})
    pilot.dump(
        tmp_path / "prepared_trajectory_identity.json", pilot.file_record(prepared)
    )
    method = pilot.rmsd_evidence("2", psf, prepared, tmp_path, "synthetic-head")
    assert method["replica_id"] == method["reference_replica_id"] == "2"
    assert method["n_atoms_used"] == 690
    assert len(method["rmsd_values_A"]) == 5
    assert (
        method["threshold"] is None
        and method["manual_review_status"] == "pending_review"
    )
    assert "drift_detected" not in json.dumps(method)
    assert (tmp_path / "rmsd_evidence.png").read_bytes().startswith(b"\x89PNG")
    assert len(pilot.b3.csv_rows(tmp_path / "rmsd_evidence.csv")) == 5


def test_no_stage31_or_stage33_entry_points():
    source = Path(pilot.__file__).read_text()
    for forbidden in (
        "run_replica_aggregation",
        "run_dataset_release",
        "aggregate-replicas",
        "export-publication",
        "run_dataset_qc",
    ):
        assert forbidden not in source
    # The only scientific executor is the accepted protein preprocessing helper.
    import inspect

    assert "b3.run_mania" in inspect.getsource(pilot.run_protein)


def test_archive_excludes_coordinates_and_raw_sources(tmp_path):
    work = tmp_path / "evidence"
    work.mkdir()
    (work / "prepared.xtc").write_bytes(b"coordinates")
    (work / "source.psf").write_bytes(b"topology")
    pilot.dump(work / "evidence.json", {"status": "test"})
    archive = pilot.package(work)
    with pilot.zipfile.ZipFile(archive) as stream:
        assert set(stream.namelist()) == {"evidence.json", "evidence_inventory.json"}


def test_protein_pipeline_freeze_and_hard_qc_end_to_end(tmp_path, monkeypatch):
    """Real production CSV/temporal readers feed hard QC on tiny synthetic data."""
    import test_stage34b_namd_real_pilot as baseline

    from mania import dataset_release_run, replica_aggregation_run

    forbidden = Mock(side_effect=AssertionError("Downstream execution forbidden"))
    monkeypatch.setattr(dataset_release_run, "run_dataset_release", forbidden)
    monkeypatch.setattr(replica_aggregation_run, "run_replica_aggregation", forbidden)
    monkeypatch.setattr(baseline, "pilot", pilot.b3)
    monkeypatch.setattr(
        pilot.b3, "manifest_payload", lambda *args: pilot.pilot_manifest("2", *args)
    )
    baseline.test_complete_synthetic_protein_pipeline(monkeypatch, tmp_path)
    mapping_path = tmp_path / "mapping.json"
    mapping = pilot.b3.read_canonical_residue_mapping(mapping_path)
    prepared = tmp_path / "prepared.xtc"
    pilot.dump(
        tmp_path / "prepared_trajectory_identity.json",
        {
            **pilot.file_record(prepared),
            "frames": [
                dict(passed=True, checks={"pointwise_atom_order": True})
                for _ in range(5)
            ],
        },
    )
    pilot.dump(
        tmp_path / "authority.json",
        dict(
            replica_id="2",
            shared=dict(
                atoms_covered=4,
                required_source_keys=[r.source_key for r in mapping.mappings],
            ),
        ),
    )
    pilot.dump(tmp_path / "selected_frames.json", {"frames": [{"atom_count": 4}] * 5})
    pilot.dump(
        tmp_path / "persisted_pbc_validation.json",
        {
            "frames": [
                {
                    "bonds": {
                        "all_topology_bonds": {"prepared_direct_disagreement_count": 0}
                    },
                    "protein": {"substantive_mismatches": 0},
                    "centroids": {"substantive_mismatches": 0},
                    "hbond_geometry": {"substantive_mismatches": 0},
                }
            ]
            * 5
        },
    )
    pilot.dump(
        tmp_path / "science_check.json",
        dict(
            status="PASS",
            per_frame=pilot.read(tmp_path / "protein_per_frame_independent_check.json"),
            window=pilot.read(tmp_path / "protein_window_independent_check.json"),
            canonical=pilot.read(tmp_path / "canonicalization_check.json"),
        ),
    )
    pilot.dump(tmp_path / "namd_time_authority.json", {"synthetic_metadata": True})
    elements = tmp_path / "elements.json"
    pilot.dump(elements, {"synthetic_metadata": True})
    records = pilot.freeze_science(tmp_path, mapping_path, elements)
    hard, partial, pending = pilot.hard_qc(tmp_path, records, "2")
    assert hard.hard_qc_status == "pass"
    assert len(hard.checks) == 26
    assert pending["status"] == "pending_review"
    assert pending["authoritative_release_decision"] is None
    assert pending["production_ready"] is False
    assert partial["empty_window_fraction"] == "0"
    assert partial["accepted_partial_mad_finding"]["status"] == "pass"
    assert "drift_detected" not in pending
    forbidden.assert_not_called()
