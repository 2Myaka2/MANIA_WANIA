"""Synthetic fail-closed NAMD pilot gates; no local real inputs are accessed."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from test_cli_preprocessing_graph_workflow import FIXED_IDENTITY

mda = pytest.importorskip("MDAnalysis")
spec = importlib.util.spec_from_file_location(
    "stage34b_real_pilot",
    Path(__file__).parents[1] / "tools/stage34b_namd_real_pilot.py",
)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
BOX = np.asarray([10, 10, 10, 90, 90, 90], dtype=np.float32)


def bonded_system():
    u = mda.Universe.empty(
        12,
        n_residues=9,
        atom_resindex=[0, 1, 2, 3, 4, 5, 5, 6, 7, 7, 8, 8],
        trajectory=True,
    )
    for name, values in (
        ("ids", list(range(1, 13))),
        (
            "names",
            ["SG", "SG", "SG", "SG", "ND2", "C1", "C2", "ND2", "C1", "C2", "O", "H"],
        ),
        ("types", ["S"] * 4 + ["N", "C", "C", "N", "C", "C", "O", "H"]),
        ("elements", ["S"] * 4 + ["N", "C", "C", "N", "C", "C", "O", "H"]),
        ("masses", [12.0] * 12),
        (
            "resnames",
            ["CYS", "CYS", "CYS", "CYS", "ASN", "BGLCNA", "ASN", "BGLCNA", "TIP3"],
        ),
        ("resids", [303, 350, 322, 328, 295, 1, 308, 2, 3]),
        ("segids", ["PROA"]),
        ("bonds", [(0, 1), (2, 3), (4, 5), (5, 6), (7, 8), (8, 9), (10, 11)]),
    ):
        u.add_TopologyAttr(name, values)
    u.atoms.positions = np.asarray(
        [
            [9.5, 1, 1],
            [0.5, 1, 1],
            [9.5, 2, 1],
            [0.5, 2, 1],
            [9.5, 3, 1],
            [0.5, 3, 1],
            [1.5, 3, 1],
            [9.5, 4, 1],
            [0.5, 4, 1],
            [1.5, 4, 1],
            [9.5, 5, 1],
            [0.5, 5, 1],
        ],
        dtype=np.float32,
    )
    u.dimensions = BOX
    u.trajectory.ts.time = 100
    return u


@pytest.mark.parametrize("label", ["PSF", "elements", "time", "mapping"])
def test_exact_hash_guards_reject_changes(tmp_path, label):
    path = tmp_path / label
    path.write_bytes(b"accepted")
    sha = pilot.file_record(path)["sha256"]
    assert pilot.require_hash(path, sha, label)["sha256"] == sha
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match=f"Wrong {label} SHA256"):
        pilot.require_hash(path, sha, label)


def test_control_binding_checks_use_accepted_validators(monkeypatch, tmp_path):
    root = tmp_path
    paths = [
        root / "namd/egor_2ss_r1/raw/MD_2_bonds_NPT_W_I_PMm_100_ns.psf",
        root / pilot.AUTHORITY_DIRECTORY / "namd_atom_type_elements.json",
        root / pilot.AUTHORITY_DIRECTORY / "namd_time_authority.json",
        root / pilot.MAPPING_DIRECTORY / "namd_canonical_mapping.json",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("control")
    monkeypatch.setattr(pilot, "require_hash", lambda p, *_: pilot.file_record(p))
    accepted = Mock(side_effect=ValueError("Wrong PSF binding"))
    monkeypatch.setattr(pilot.mapping_authority, "accepted_inputs", accepted)
    forbidden = Mock(side_effect=AssertionError("Coordinates opened before authority"))
    monkeypatch.setattr(pilot.mda, "Universe", forbidden)
    with pytest.raises(ValueError, match="Wrong PSF binding"):
        pilot.validate_authorities(root, tmp_path)
    accepted.assert_called_once_with(paths[1].parent)
    forbidden.assert_not_called()


def test_five_frame_freeze_stage27_and_mapping():
    _, sampling, windows = pilot.sampling_contract()
    assert sampling.sampled_frame_count == 5
    assert sampling.missing_sample_count == 0 and sampling.coverage_fraction == 1
    assert [s.actual_time_ps for s in sampling.selected_samples] == [
        100,
        200,
        300,
        400,
        500,
    ]
    assert windows.windows[0].requested_start_ns == 0.1
    assert windows.windows[0].requested_end_ns == 0.5
    assert [r["source_dcd_frame_index"] for r in pilot.frame_map()] == list(range(5))
    assert [r["prepared_frame_index"] for r in pilot.frame_map()] == list(range(5))


@pytest.mark.parametrize(
    "times",
    [
        (0, 100, 200, 300, 400),
        (100, 200, 300, 400),
        (100, 200, 300, 400, 500, 600),
        (100.00001, 200, 300, 400, 500),
    ],
)
def test_wrong_frozen_axis_rejected(times):
    with pytest.raises(ValueError, match="freeze"):
        pilot.sampling_contract(times)


def test_variant_c_exact_order(monkeypatch):
    u = bonded_system()
    operations = []
    trans = pilot.pbc.trans
    original_unwrap, original_center = trans.unwrap, trans.center_in_box
    original_wrap = type(u.atoms).wrap

    def unwrap(*args, **kwargs):
        operations.append("unwrap")
        return original_unwrap(*args, **kwargs)

    def center(*args, **kwargs):
        operations.append(("center", kwargs["center"], kwargs["wrap"]))
        return original_center(*args, **kwargs)

    def wrap(group, *args, **kwargs):
        operations.append(("wrap", kwargs["compound"], kwargs["center"]))
        return original_wrap(group, *args, **kwargs)

    monkeypatch.setattr(trans, "unwrap", unwrap)
    monkeypatch.setattr(trans, "center_in_box", center)
    monkeypatch.setattr(type(u.atoms), "wrap", wrap)
    pilot.pbc.prepare_variant(
        u, u.atoms.positions.copy(), BOX, 100, pilot.pbc.VARIANTS[2]
    )
    assert operations == [
        "unwrap",
        ("center", "geometry", False),
        ("wrap", "fragments", "cog"),
    ]


def test_all_bonds_disulfides_anchors_and_branches():
    u = bonded_system()
    features = pilot.input_authority.topology_features(u)
    context = pilot.bond_context(u, features)
    raw = u.atoms.positions.copy()
    pilot.pbc.prepare_variant(u, raw, BOX, 100, pilot.pbc.VARIANTS[2])
    result = pilot.pbc.bond_integrity(u, context, raw, u.atoms.positions, BOX, {})
    assert result["all_topology_bonds"]["bond_count"] == 7
    for group in (
        "C303-C350",
        "C322-C328",
        "Asn295_attachment_bonds",
        "Asn308_attachment_bonds",
    ):
        assert result[group]["bond_count"] == 1
        assert result[group]["prepared_direct_disagreement_count"] == 0
    assert result["Asn295_attached_branch_bonds"]["bond_count"] == 2
    assert result["Asn308_attached_branch_bonds"]["bond_count"] == 2
    assert result["all_environment_bonds"]["bond_count"] == 1
    changed = u.atoms.positions.copy()
    changed[5, 0] += 10
    bad = pilot.pbc.bond_integrity(u, context, raw, changed, BOX, {})
    assert bad["all_topology_bonds"]["prepared_direct_disagreement_count"] == 2


def test_sparse_interfragment_mismatch_and_direct_only():
    raw = np.array([[0.1, 1, 1], [9.9, 1, 1]], dtype=np.float32)
    indexes, components = np.array([0, 1]), np.array([0, 1])
    result = pilot.protein_representation(raw, raw, BOX, indexes, components)
    assert result["pair_observations"] == 1
    assert result["interfragment_substantive_mismatches"] == 1
    assert result["thresholds"]["residue_contact"]["substantive_lost"] == 1
    other_box = np.array([100, 100, 100, 90, 90, 90], dtype=np.float32)
    direct = raw.copy()
    direct[1, 0] = 1.1
    result = pilot.protein_representation(raw, direct, other_box, indexes, components)
    assert result["thresholds"]["residue_contact"]["substantive_direct_only"] == 1


def test_boundary_flip_visible_not_substantive():
    result = pilot.classifications(np.array([4.49999]), np.array([4.50001]), 4.5)
    assert result["strict_lost"] == result["numerical_boundary_flips"] == 1
    assert result["substantive_lost"] == result["distance_disagreements"] == 0
    strict = pilot.classifications(np.array([6.0]), np.array([5.99999]), 6.0, "lt")
    assert strict["strict_direct_only"] == 1


@pytest.mark.parametrize("gate", ["bond", "protein", "centroid", "hydrogen"])
def test_representation_gate_stops_before_science(gate):
    rows = [
        {
            "bonds": {"all_topology_bonds": {"prepared_direct_disagreement_count": 0}},
            "protein": {"substantive_mismatches": 0},
            "centroids": {"substantive_mismatches": 0},
            "hbond_geometry": {"substantive_mismatches": 0},
        }
        for _ in range(5)
    ]
    if gate == "bond":
        rows[2]["bonds"]["all_topology_bonds"]["prepared_direct_disagreement_count"] = 1
    else:
        rows[2][
            {
                "protein": "protein",
                "centroid": "centroids",
                "hydrogen": "hbond_geometry",
            }[gate]
        ]["substantive_mismatches"] = 1
    science = Mock()
    with pytest.raises(ValueError, match="STOP before MANIA"):
        pilot.require_representation(rows)
        science()
    science.assert_not_called()


@pytest.mark.parametrize(
    "damage", [None, "time", "box", "atom_identity", "coordinate_order"]
)
def test_persisted_time_box_identity(damage):
    u = bonded_system()
    identity, expected = pilot.pbc.identity(u), u.atoms.positions.copy()
    if damage == "time":
        u.trajectory.ts.time += 0.0001
    elif damage == "box":
        u.dimensions = [11, 10, 10, 90, 90, 90]
    elif damage == "atom_identity":
        u.atoms.ids = u.atoms.ids[::-1]
    elif damage == "coordinate_order":
        u.atoms.positions = u.atoms.positions[::-1]
    assert pilot.validate_persisted(u, identity, expected, BOX, 100)["passed"] == (
        damage is None
    )


@pytest.mark.parametrize(
    "positives,episodes,mean,maximum",
    [
        ([0], 1, 0, 0),
        ([0, 1, 2, 3, 4], 1, 0.4, 0.4),
        ([0, 1, 3, 4], 2, 0.1, 0.1),
        ([0, 2, 3, 4], 2, 0.1, 0.2),
    ],
)
def test_independent_requested_sample_episodes(positives, episodes, mean, maximum):
    key = (0, 1, "vdw")
    rows = [{key: 3.1} if i in positives else {} for i in range(5)]
    result = pilot.reconstruct_windows(rows)[key]
    assert result["n_contact_episodes"] == episodes
    assert result["n_contact_frames"] == len(positives)
    assert result["mean_episode_length_ns"] == mean
    assert result["max_episode_length_ns"] == maximum
    assert result["occupancy"] == result["edge_weight"] == len(positives) / 5


def test_manifest_null_condition_and_no_specialized_controls(tmp_path):
    entry = pilot.manifest_payload(
        tmp_path / "a.psf", tmp_path / "a.xtc", tmp_path / "map.json", tmp_path
    )["conditions"][0]
    assert entry["dataset_spec"]["identity"]["condition"] is None
    assert entry["dataset_spec"]["identity"]["replica_id"] == "1"
    assert "molecular_partner_metadata_path" not in entry


def test_real_runner_stops_and_packages_blocker(monkeypatch, tmp_path):
    monkeypatch.setattr(pilot, "git_checkpoint", lambda *_: "head")
    monkeypatch.setattr(
        pilot, "validate_authorities", Mock(side_effect=ValueError("Wrong PSF binding"))
    )
    science = Mock(side_effect=AssertionError("science forbidden"))
    monkeypatch.setattr(pilot, "run_mania", science)
    result = pilot.run(tmp_path, tmp_path, Path(__file__).parents[1])
    assert result["stage34b3_status"] == "BLOCKED" and not result["mania_executed"]
    science.assert_not_called()
    assert tmp_path.with_suffix(".zip").is_file()
    for name in pilot.REQUIRED_EVIDENCE:
        assert (tmp_path / (name + ".json")).is_file()


def test_complete_synthetic_protein_pipeline(monkeypatch, tmp_path):
    """Actual accepted CLI/Stage 27/28/30 and unified validators, with a tiny PSF."""
    import mania.cli as cli
    from mania.canonical_residue_mapping import (
        CanonicalResidueMappingRecord,
        CanonicalResidueMappingTable,
    )
    from mania.canonical_residue_mapping_io import write_canonical_residue_mapping
    from mania.preprocessing import specialized_contact_execution as specialized

    # The existing identity reload test replaces the module's class object.
    # Use the same stable fixture as other full CLI integration tests.
    monkeypatch.setattr(cli, "get_software_identity", Mock(return_value=FIXED_IDENTITY))
    psf = tmp_path / "tiny.psf"
    psf.write_text(
        "PSF EXT\n\n         1 !NTITLE\n REMARKS synthetic pilot\n\n         4 !NATOM\n"
        + "".join(
            f"{i:10d} {'PROA':<8} {resid:<8} {'ALA':<8} {name:<8} {'C':<8} "
            f"{0.0:14.6f} {12.0:14.4f} {0:8d}\n"
            for i, resid, name in (
                (1, 1, "CA"),
                (2, 1, "CB"),
                (3, 2, "CA"),
                (4, 2, "CB"),
            )
        )
        + "\n         2 !NBOND: bonds\n         1         2         3         4\n"
    )
    u = mda.Universe(str(psf), to_guess=())
    coordinates = np.array(
        [[1, 1, 1], [1, 2, 1], [4.2, 1, 1], [4.2, 2, 1]], dtype=np.float32
    )
    prepared = tmp_path / "prepared.xtc"
    with pilot.XTCFile(str(prepared), "w") as writer:
        for i, t in enumerate(pilot.TIMES_PS):
            writer.write(
                coordinates / 10,
                np.diag(np.array([10, 10, 10], dtype=np.float32)),
                i,
                t,
                precision=1_000_000,
            )
    mapping = CanonicalResidueMappingTable(
        tuple(
            CanonicalResidueMappingRecord(
                "namd",
                "PROA",
                str(i),
                "ALA",
                i,
                pilot.load_default_napi2b_canonical_reference()
                .residue_at(i)
                .canonical_resname,
                "mapped",
            )
            for i in (1, 2)
        )
    )
    mapping_path = tmp_path / "mapping.json"
    assert write_canonical_residue_mapping(mapping, mapping_path).passed
    monkeypatch.setattr(pilot, "PSF_SHA256", pilot.pbc.sha256(psf))
    monkeypatch.setattr(pilot, "validate_time", lambda *_: pilot.TIMES_PS)
    forbidden = Mock(
        side_effect=AssertionError("Stage 29 specialized science forbidden")
    )
    monkeypatch.setattr(specialized, "compute_protein_lipid_contacts", forbidden)
    monkeypatch.setattr(specialized, "compute_protein_glycan_contacts", forbidden)
    control = SimpleNamespace(dcd=SimpleNamespace(path="unused.dcd"))
    loaded = pilot.run_mania(
        psf, prepared, {"C": "C"}, control, mapping_path, tmp_path, {}
    )
    report, windows, canonical = pilot.check_independent(
        psf, prepared, {"C": "C"}, mapping, tmp_path
    )
    assert (
        report["missing_rows"]
        == report["extra_rows"]
        == report["distance_mismatches"]
        == 0
    )
    assert windows["metric_mismatches"] == canonical["scientific_value_mismatches"] == 0
    validation = pilot.technical_validation(loaded, mapping_path, tmp_path)
    assert validation.status == "passed" and validation.complete
    forbidden.assert_not_called()
    source = pilot.csv_rows(tmp_path / "output/protein_edges_by_window_source.csv")
    canonical_rows = pilot.csv_rows(
        tmp_path / "output/protein_edges_by_window_canonical.csv"
    )
    canonical_rows[0]["occupancy"] = "0.99"
    assert (
        pilot.compare_canonical(source, canonical_rows, mapping)[
            "scientific_value_mismatches"
        ]
        == 1
    )
    assert len(u.atoms) == 4


def test_source_coordinate_access_stays_within_five(monkeypatch, tmp_path):
    u = bonded_system()
    dcd = tmp_path / "six.dcd"
    with mda.Writer(str(dcd), n_atoms=len(u.atoms), dt=100) as writer:
        for _ in range(6):
            writer.write(u.atoms)
    original = pilot.DCDReader
    with original(str(dcd)) as reader:
        raw_times = [
            SimpleNamespace(frame=i, time_ps=float(reader[i].time))
            for i in pilot.FRAMES
        ]
        dt = reader.dt
    reads = []

    class BoundedReader(original):
        def __getitem__(self, index):
            assert index in pilot.FRAMES
            reads.append(index)
            return super().__getitem__(index)

    monkeypatch.setattr(pilot, "DCDReader", BoundedReader)
    control = SimpleNamespace(
        dcd=SimpleNamespace(dt_ps=dt, observed_times=raw_times),
        scientific_times_ps=pilot.TIMES_PS,
    )
    frames = pilot.read_five(dcd, control, len(u.atoms), tmp_path)
    assert reads == list(pilot.FRAMES) and len(frames) == 5
    saved = json.loads((tmp_path / "selected_frames.json").read_text())
    assert saved["source_coordinate_read_indexes_including_initialization"] == [
        0,
        0,
        1,
        2,
        3,
        4,
    ]
    assert [r["raw_dcd_time_ps"] for r in saved["frames"]] == [
        r.time_ps for r in raw_times
    ]
    assert [r["authoritative_time_ps"] for r in saved["frames"]] == list(pilot.TIMES_PS)


def test_independent_all_enabled_typed_definitions():
    from mania.preprocessing.trajectory_contacts import compute_condition_contacts
    from mania.preprocessing.trajectory_runtime import (
        PreprocessingConditionLoadResult,
        PreprocessingConditionRuntime,
        PreprocessingConditionRuntimeInput,
    )

    ring_names = pilot.chemistry._AROMATIC_RING_ATOMS["PHE"]
    ring = [[np.cos(t), np.sin(t), 0] for t in np.arange(6) * np.pi / 3]
    definitions = [
        ("PHE", ring_names, ring),
        ("TYR", ring_names, (np.asarray(ring) + [0, 0, 5]).tolist()),
        ("LYS", ["NZ", "HZ1"], [[0, 0, 4], [0, 0, 3]]),
        ("ASP", ["OD1"], [[0, 0, 1]]),
        ("CYS", ["SG"], [[0, 20, 0]]),
        ("CYS", ["SG"], [[2, 20, 0]]),
        ("ALA", ["CB"], [[0, 30, 0]]),
        ("VAL", ["CB"], [[4, 30, 0]]),
    ]
    names = [n for _, ns, _ in definitions for n in ns]
    u = mda.Universe.empty(
        len(names),
        n_residues=len(definitions),
        atom_resindex=[i for i, (_, ns, _) in enumerate(definitions) for _ in ns],
        trajectory=True,
    )
    for key, value in (
        ("names", names),
        ("resnames", [r for r, _, _ in definitions]),
        ("resids", list(range(1, len(definitions) + 1))),
        ("segids", ["PROA"]),
        (
            "elements",
            [
                "H"
                if n == "HZ1"
                else "N"
                if n == "NZ"
                else "O"
                if n == "OD1"
                else "S"
                if n == "SG"
                else "C"
                for n in names
            ],
        ),
        ("bonds", [(12, 13)]),
    ):
        u.add_TopologyAttr(key, value)
    u.atoms.positions = np.asarray([p for _, _, xyz in definitions for p in xyz])
    u.trajectory.ts.time = 100
    runtime_input = PreprocessingConditionRuntimeInput(
        "test", Path("x.psf"), (Path("x.xtc"),)
    )
    loaded = PreprocessingConditionLoadResult(
        "test",
        runtime_input,
        PreprocessingConditionRuntime(
            "test", u, "MDAnalysis.Universe", Path("x.psf"), (Path("x.xtc"),)
        ),
        status="loaded",
    )
    actual = (
        compute_condition_contacts(
            loaded,
            options=pilot.PreprocessingContactDetectionOptions(
                contact_selection="protein"
            ),
            source_frame_indexes=(0,),
        )
        .frame_results[0]
        .contacts
    )
    expected, _ = pilot.independent_frame(u)
    population = {
        (
            r.source_residue_index,
            r.target_residue_index,
            r.edge_type,
        ): r.minimum_distance
        for r in actual
    }
    assert population.keys() == expected.keys()
    assert {k[2] for k in expected} == {
        "residue_contact",
        "vdw",
        "hbond",
        "disulfide",
        "hydrophobic",
        "ionic",
        "salt_bridge",
        "aromatic_pi",
        "cation_pi",
    }
    assert all(abs(population[k] - d) <= 1e-12 for k, d in expected.items())
