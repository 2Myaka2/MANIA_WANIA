"""Optional MDAnalysis diagnostics; no real trajectory or production workflow."""

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis", reason="optional scientific dependency")
SCRIPT = Path(__file__).resolve().parents[1] / "tools/pbc_protocol_diagnostic.py"
spec = importlib.util.spec_from_file_location("pbc_protocol_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
BOX = np.array([100, 100, 100, 90, 90, 90], dtype=np.float32)


def system(x, *, bonds=((0, 1),), residues=None, resids=None, elements=None):
    n = len(x)
    u = mda.Universe.empty(n, n_residues=n, atom_resindex=np.arange(n), trajectory=True)
    for name, values in (
        ("names", ["C"] * n),
        ("ids", np.arange(n) + 100),
        ("resnames", residues or ["ALA"] * n),
        ("resids", resids or list(range(1, n + 1))),
        ("segids", ["TEST"]),
        ("elements", elements or ["C"] * n),
    ):
        u.add_TopologyAttr(name, values)
    if bonds is not None:
        u.add_TopologyAttr("bonds", bonds)
    u.atoms.positions = np.column_stack((x, np.full(n, 50), np.full(n, 50)))
    u.dimensions = BOX
    u.trajectory.ts.time = 5000
    return u


def evaluate(u, box=BOX):
    return diagnostic.evaluate_frame(
        u, diagnostic.topology_context(u), u.atoms.positions.copy(), box, 500, 5000
    )


def all_bonds(row):
    return row["bond_integrity"]["all_topology_bonds"]


def test_whole_molecule_all_variants_preserve_geometry_and_system():
    records = evaluate(system([49, 51]))
    for row in records:
        assert all(row["preservation_checks"].values())
        assert row["atom_count"] == 2
        assert row["actual_time_ps"] == 5000
        assert row["box_lengths_A"] == [100, 100, 100]
        assert all_bonds(row)["prepared_direct_disagreement_count"] == 0
        assert all_bonds(row)["prepared_periodic_reference_drift_count"] == 0
        for contact in row["contact_diagnostics"].values():
            assert all(
                t["lost_periodic_close"] == t["direct_only_close"] == 0
                for t in contact["thresholds"]
            )


def test_literal_boundary_counterexample_is_expected_failure():
    raw, literal, candidate = evaluate(system([99, 1]))
    for row in (raw, literal):
        report = all_bonds(row)
        assert report["prepared_direct_disagreement_count"] == 1
        example = report["examples"][0]
        assert example["direct_distance_A"] == pytest.approx(98)
        assert example["periodic_reference_distance_A"] == pytest.approx(2, abs=1e-5)
        assert example["discrepancy_type"] == "bonded_component_split"
        assert example["geometry_probe_threshold_A"] is None
        assert example["source_frame_index"] == 500
        assert example["variant"] == row["variant"]
        assert example["atoms"][0]["id"] == 100
        assert example["atoms"][0]["index"] == 0
        probes = row["contact_diagnostics"]["protein_protein"]["thresholds"]
        assert [p["lost_periodic_close"] for p in probes] == [1, 1]
    assert all_bonds(candidate)["prepared_direct_disagreement_count"] == 0
    steps = literal["transformation_parameters"]
    assert steps[1]["center"] == "geometry" and steps[1]["wrap"] is True
    assert steps[2]["compound"] == "atoms"
    steps = candidate["transformation_parameters"]
    assert steps[1]["wrap"] is False
    assert steps[2]["compound"] == "fragments" and steps[2]["center"] == "cog"
    print("Literal synthetic counterexample: direct 98 A; periodic approximately 2 A.")


def test_both_attached_branches_follow_topology_not_residue_names():
    u = system(
        [99, 1, 3, 98],
        bonds=((0, 1), (1, 2), (0, 3)),
        residues=["ASN", "ASN", "SUGAR-X", "UNCLASSIFIED-Y"],
        resids=[295, 308, 691, 703],
    )
    context = diagnostic.topology_context(u)
    assert len(set(context["components"])) == 1
    assert context["attached"].tolist() == [False, False, True, True]
    assert context["attachments"]["Asn295"]["topology_attachment_atom_pairs"] == [
        [0, 3]
    ]
    assert context["attachments"]["Asn308"]["topology_attachment_atom_pairs"] == [
        [1, 2]
    ]
    candidate = evaluate(u)[2]
    assert all_bonds(candidate)["prepared_direct_disagreement_count"] == 0
    for anchor in ("Asn295", "Asn308"):
        assert (
            candidate["bond_integrity"][f"{anchor}_attachment_bonds"]["bond_count"] == 1
        )
        assert (
            candidate["bond_integrity"][f"{anchor}_attached_branch_bonds"][
                "prepared_direct_disagreement_count"
            ]
            == 0
        )


def test_distinct_molecules_keep_periodic_contact_ambiguity():
    records = evaluate(
        system(
            [50, 51, 99, 98, 1, 2],
            bonds=((0, 1), (2, 3), (4, 5)),
            residues=["ALA", "ALA"] + ["ENV-X"] * 4,
        )
    )
    candidate = records[2]
    assert all_bonds(candidate)["prepared_direct_disagreement_count"] == 0
    probes = candidate["contact_diagnostics"]["environment_environment"]["thresholds"]
    assert [p["lost_periodic_close"] for p in probes] == [4, 4]
    assert [p["direct_only_close"] for p in probes] == [0, 0]
    coverage = candidate["checked_atom_set_coverage"]
    assert coverage["selected_environment_component_ids"] == [1, 2]
    assert coverage["subsets"]["representative_environment_heavy"] == {
        "atom_count": 4,
        "atom_index_ranges": [[2, 5]],
    }
    notes = []
    summary = diagnostic.conclude(records, notes)
    assert "8 lost_periodic_close" in summary
    assert any("Candidate still loses" in warning for warning in notes)
    assert "PBC PASSED" not in summary


def test_variants_reset_raw_coordinates_even_when_called_in_reverse_order():
    u = system([99, 1])
    raw = u.atoms.positions.copy()
    original = raw.copy()
    expected = {}
    for variant in diagnostic.VARIANTS:
        diagnostic.prepare_variant(u, raw, BOX, 5000, variant)
        expected[variant] = u.atoms.positions.copy()
    for variant in reversed(diagnostic.VARIANTS):
        u.atoms.positions += 1000
        diagnostic.prepare_variant(u, raw, BOX, 5000, variant)
        np.testing.assert_array_equal(u.atoms.positions, expected[variant])
    np.testing.assert_array_equal(raw, original)


@pytest.mark.parametrize(
    "box",
    [
        None,
        [0, 100, 100, 90, 90, 90],
        [-1, 100, 100, 90, 90, 90],
        [100, 100, 100, 180, 90, 90],
        [100, 100, 100, 10, 10, 170],
        [np.nan, 100, 100, 90, 90, 90],
        [100, 100, 100],
    ],
)
def test_missing_or_invalid_box_fails(box):
    with pytest.raises(ValueError, match="[Bb]ox"):
        evaluate(system([99, 1]), box)


def test_triclinic_cell_is_preserved_and_molecule_reconstructed():
    box = np.array([100, 90, 80, 80, 85, 75], np.float32)
    vector = mda.lib.mdamath.triclinic_vectors(box)[1]
    u = system([0, 0])
    u.atoms.positions = [0.99 * vector, 0.01 * vector]
    candidate = evaluate(u, box)[2]
    assert candidate["box_angles_deg"] == [80, 85, 75]
    assert all_bonds(candidate)["prepared_direct_disagreement_count"] == 0


@pytest.mark.parametrize("bonds", [None, ()])
def test_missing_bond_metadata_fails(bonds):
    with pytest.raises(ValueError, match="topology bonds"):
        diagnostic.topology_context(system([99, 1], bonds=bonds))


@pytest.mark.parametrize("mode", ["missing", "unknown", "guessed"])
def test_unavailable_element_evidence_skips_probes_without_guessing(mode):
    u = system([99, 1])
    if mode == "missing":
        u.del_TopologyAttr("elements")
    elif mode == "unknown":
        u.atoms.elements = ["", "X"]
    else:
        u._topology.elements._guessed = True
    context = diagnostic.topology_context(u)
    assert context["heavy"] is None
    assert context["warnings"]
    records = evaluate(u)
    assert records[2]["contact_diagnostics"] == {}
    assert all_bonds(records[2])["bond_count"] == 1
    assert "NOT ASSESSED" in diagnostic.conclude(records, [])


def test_heavy_classification_uses_only_authoritative_elements():
    u = system(
        [50, 51, 52, 53],
        bonds=((0, 1), (1, 2), (2, 3)),
        elements=["C", "H", "Na", "Cl"],
    )
    u.atoms.names = ["H", "C", "X", "X"]
    assert diagnostic.topology_context(u)["heavy"].tolist() == [True, False, True, True]


def test_nonfinite_coordinates_fail():
    u = system([99, np.nan])
    with pytest.raises(ValueError, match="nonfinite"):
        evaluate(u)


def test_direct_only_contacts_and_reference_drift_are_reported():
    u = system([50, 70])
    context = diagnostic.topology_context(u)
    raw = u.atoms.positions.copy()
    prepared = raw.copy()
    prepared[1, 0] = 51
    report = diagnostic.compare_contacts(
        u, context, raw, prepared, BOX, np.array([0]), np.array([1])
    )
    assert report["periodic_reference_drift_count_on_candidate_union"] == 1
    for threshold in report["thresholds"]:
        assert threshold["direct_only_close"] == 1
        assert threshold["lost_periodic_close"] == 0
        assert threshold["examples"][0]["discrepancy_type"] == "direct_only_close"


def test_chunked_neighbor_counts_match_independent_dense_small_oracle(monkeypatch):
    monkeypatch.setattr(diagnostic, "REFERENCE_BLOCK", 2)
    monkeypatch.setattr(diagnostic, "CONFIGURATION_BLOCK", 3)
    u = system([1, 2, 4, 96.25, 98.25, 99.25])
    context = diagnostic.topology_context(u)
    raw = u.atoms.positions.copy()
    report = diagnostic.compare_contacts(
        u, context, raw, raw, BOX, np.arange(6), np.arange(6), True
    )
    for result in report["thresholds"]:
        threshold = result["geometry_probe_threshold_A"]
        direct = [
            abs(float(raw[a, 0] - raw[b, 0])) for a in range(6) for b in range(a + 1, 6)
        ]
        periodic = [min(d, 100 - d) for d in direct]
        assert result["periodic_close_count"] == sum(d <= threshold for d in periodic)
        assert result["direct_close_count"] == sum(d <= threshold for d in direct)
        assert result["lost_periodic_close"] == sum(
            p <= threshold < d for p, d in zip(periodic, direct, strict=True)
        )
        assert len(result["examples"]) <= diagnostic.EXAMPLE_LIMIT


def test_environment_selection_is_bounded_and_topology_connected(monkeypatch):
    monkeypatch.setattr(diagnostic, "ENVIRONMENT_LIMIT", 1)
    u = system(
        [50, 51, 53, 54, 55, 56],
        bonds=((0, 1), (2, 3), (4, 5)),
        residues=["ALA"] * 2 + ["ENV-X"] * 4,
    )
    subsets, coverage = diagnostic.diagnostic_subsets(
        diagnostic.topology_context(u), u.atoms.positions, BOX
    )
    assert coverage["candidate_components_within_6_A"] == 2
    assert coverage["selected_environment_component_ids"] == [1]
    assert subsets["representative_environment_heavy"].tolist() == [2, 3]


class FakeReader:
    def __init__(self, time=5000):
        self.time = time
        self.seeks = []

    def __len__(self):
        return 521

    def seek(self, index):
        self.seeks.append(index)

    def read(self):
        return SimpleNamespace(
            time=self.time, x=np.array([[1, 2, 3]]), box=np.eye(3) * 10
        )


@pytest.mark.parametrize("actual", [4990, 5000.000001, float("nan")])
def test_exact_time_mismatch_fails_without_substitution(actual):
    reader = FakeReader(actual)
    with pytest.raises(ValueError, match="Selected time mismatch"):
        diagnostic.read_selected(reader, 500, 5000)
    assert reader.seeks == [500]


def test_selected_frame_unavailable_fails():
    reader = FakeReader()
    with pytest.raises(ValueError, match="unavailable"):
        diagnostic.read_selected(reader, 525, 5250)
    assert reader.seeks == []


def test_low_level_xtc_units_are_explicit():
    raw, box, actual = diagnostic.read_selected(FakeReader(), 500, 5000)
    np.testing.assert_array_equal(raw, [[10, 20, 30]])
    np.testing.assert_array_equal(box, BOX)
    assert actual == 5000


def test_normal_hash_guard_stops_before_real_reader(tmp_path, monkeypatch, capsys):
    topology, trajectory = tmp_path / "topology.tpr", tmp_path / "trajectory.xtc"
    topology.write_bytes(b"wrong topology")
    trajectory.write_bytes(b"not opened")

    def forbidden(*args, **kwargs):
        pytest.fail("Reader/parser must not be reached after hash mismatch")

    monkeypatch.setattr(diagnostic, "XTCFile", forbidden)
    monkeypatch.setattr(diagnostic, "TPRParser", forbidden)
    assert diagnostic.run(topology, trajectory, tmp_path / "out") == 1
    archive = next((tmp_path / "out").glob("*.zip"))
    with zipfile.ZipFile(archive) as bundle:
        result = json.loads(bundle.read(f"{archive.stem}/pbc_diagnostic.json"))
        observations = json.loads(
            bundle.read(f"{archive.stem}/input_observations.json")
        )
    assert "SHA256 differs" in result["error"]
    assert observations["trajectory_hash_computed"] is False
    assert "SEND THIS ARCHIVE:" in capsys.readouterr().out


def test_five_frame_runner_archive_and_input_protection(tmp_path, monkeypatch, capsys):
    topology, trajectory = tmp_path / "topology.tpr", tmp_path / "trajectory.xtc"
    topology.write_bytes(b"synthetic topology sentinel")
    monkeypatch.setattr(diagnostic, "NORMAL_TPR_SHA256", diagnostic.sha256(topology))
    u = system([99, 1])
    monkeypatch.setattr(
        diagnostic,
        "TPRParser",
        lambda path: SimpleNamespace(parse=lambda **kwargs: u._topology.copy()),
    )
    # Tiny synthetic trajectory in pytest's temporary directory, never a real run.
    with diagnostic.XTCFile(str(trajectory), "w") as writer:
        for i in range(521):
            writer.write(
                u.atoms.positions / 10,
                np.eye(3, dtype=np.float32) * 10,
                i,
                i * 10,
                1000,
            )
    before = {p.name: p.read_bytes() for p in (topology, trajectory)}
    read_frames = []
    read = diagnostic.read_selected

    def tracked_read(reader, frame_index, time_ps):
        read_frames.append(frame_index)
        return read(reader, frame_index, time_ps)

    monkeypatch.setattr(diagnostic, "read_selected", tracked_read)
    for _ in range(2):
        assert diagnostic.run(topology, trajectory, tmp_path / "out") == 0
    assert read_frames == list(diagnostic.FRAMES) * 2
    assert {p.name: p.read_bytes() for p in (topology, trajectory)} == before
    assert {p.name for p in tmp_path.iterdir()} == {
        "topology.tpr",
        "trajectory.xtc",
        "out",
    }
    archives = list((tmp_path / "out").glob("*.zip"))
    assert len(archives) == 2 and archives[0].name != archives[1].name
    for archive in archives:
        with zipfile.ZipFile(archive) as bundle:
            assert {Path(n).name for n in bundle.namelist()} == set(
                diagnostic.ARTIFACTS
            )
            assert not any(n.endswith((".tpr", ".xtc")) for n in bundle.namelist())
            result = json.loads(bundle.read(f"{archive.stem}/pbc_diagnostic.json"))
            summary = bundle.read(f"{archive.stem}/summary.txt").decode()
            assert result["execution_status"] == "completed_observations"
            assert result["production_protocol_approved"] is False
            assert len(result["records"]) == 15
            assert "Variant B bonded integrity: 5 bond/frame disagreements" in summary
    assert capsys.readouterr().out.count("SEND THIS ARCHIVE:") == 2


def test_cli_rejects_changed_checkpoint_frames(tmp_path):
    with pytest.raises(SystemExit) as error:
        diagnostic.main(
            [
                "--topology",
                "unused.tpr",
                "--trajectory",
                "unused.xtc",
                "--frames",
                "501",
                "--expected-times-ps",
                "5010",
                "--output",
                str(tmp_path),
            ]
        )
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == []
