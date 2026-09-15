"""Synthetic checks for the standalone pilot; no real data or production reruns."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis", reason="optional scientific dependency")
SCRIPT = (
    Path(__file__).resolve().parents[1] / "tools/stage34a_specialized_normal_pilot.py"
)
spec = importlib.util.spec_from_file_location("stage34a_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
BOX = np.array([100, 100, 100, 90, 90, 90], dtype=np.float32)


def system():
    u = mda.Universe.empty(
        14,
        n_residues=12,
        atom_resindex=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 11],
        trajectory=True,
    )
    for name, values in (
        ("names", ["C"] * 14),
        ("ids", list(range(100, 114))),
        (
            "resnames",
            [
                "ASN",
                "SUGAR-X",
                "SUGAR-Y",
                "ASN",
                "SUGAR-X",
                "SUGAR-Y",
                "CER160",
                "BGAL",
                "POPC",
                "POPC",
                "TIP3",
                "SOD",
            ],
        ),
        ("resids", [295, 900, 901, 308, 902, 903, 990, 991, 992, 993, 994, 995]),
        ("segids", ["TEST"]),
        ("elements", ["C"] * 10 + ["O", "H", "H", "Na"]),
        ("bonds", [(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (10, 11), (10, 12)]),
    ):
        u.add_TopologyAttr(name, values)
    u.atoms.positions = np.array([[49 + i * 0.2, 50, 50] for i in range(14)])
    u.dimensions = BOX
    u.trajectory.ts.time = 5000
    return u


def inventory(u, tmp_path):
    return pilot.inventory_components(
        u, pilot.pbc.topology_context(u), pilot.require_elements(u), tmp_path
    )


def test_exact_source_to_prepared_mapping():
    rows = pilot.frame_map()
    assert [r["prepared_frame_index"] for r in rows] == [0, 1, 2, 3, 4]
    assert [r["source_frame_index"] for r in rows] == [500, 505, 510, 515, 520]
    assert [r["actual_time_ps"] for r in rows] == [5000, 5050, 5100, 5150, 5200]


def test_written_xtc_time_box_identity_and_bonds(tmp_path):
    u = system()
    context = pilot.pbc.topology_context(u)
    raw = u.atoms.positions.copy()
    raw_frames = [
        (raw, BOX, t, np.diag(np.array([10, 10, 10], dtype=np.float32)), i)
        for i, t in enumerate(pilot.TIMES_PS)
    ]
    path = tmp_path / "prepared.xtc"
    pilot.write_prepared_frames(u, raw_frames, path)
    reopened = mda.Universe(u._topology.copy(), str(path), to_guess=())
    try:
        assert len(reopened.trajectory) == 5
        for i, _ in enumerate(reopened.trajectory):
            result = pilot.check_persisted_identity(
                reopened, context["identity"], BOX, pilot.TIMES_PS[i]
            )
            assert result["passed"] and result["box_difference"] == [0] * 6
            integrity = pilot.pbc.bond_integrity(
                reopened, context, raw, reopened.atoms.positions, BOX, {}
            )
            assert (
                integrity["all_topology_bonds"]["prepared_direct_disagreement_count"]
                == 0
            )
    finally:
        reopened.trajectory.close()
    with pytest.raises(ValueError, match="already exists"):
        pilot.write_prepared_frames(u, raw_frames, path)


@pytest.mark.parametrize("change", ["time", "box", "identity", "coordinates"])
def test_persisted_mismatch_fails(change):
    u = system()
    before = pilot.pbc.identity(u)
    if change == "time":
        u.trajectory.ts.time = 5000.00001
    elif change == "box":
        u.dimensions = [100, 101, 100, 90, 90, 90]
    elif change == "identity":
        u.atoms.ids = np.arange(14)
    else:
        positions = u.atoms.positions
        positions[0, 0] = np.nan
        u.atoms.positions = positions
    assert not pilot.check_persisted_identity(u, before, BOX, 5000)["passed"]


def test_explicit_components_anchors_and_strict_catalog(tmp_path):
    u = system()
    partners = inventory(u, tmp_path)
    assert len(partners) == 5
    glycans = [p for p in partners if p["partner_kind"] == "glycan"]
    assert [p["carrier_residue"]["resid"] for p in glycans] == [295, 308]
    assert [p["first_sugar_atom_index"] for p in glycans] == [1, 4]
    assert [p["atom_indexes"] for p in glycans] == [[1, 2], [4, 5]]
    assert all(p["partner_name"] == "FA2G2S2" for p in glycans)
    lipids = [p for p in partners if p["partner_kind"] == "lipid"]
    multi = next(p for p in lipids if "CER160" in p["composition"])
    assert multi["atom_indexes"] == [6, 7] and len(multi["residues"]) == 2
    equal_names = [p for p in lipids if p["partner_name"] == "POPC"]
    assert len(equal_names) == 2
    assert equal_names[0]["partner_id"] != equal_names[1]["partner_id"]
    catalog = pilot.build_metadata(u, partners, tmp_path / "metadata.json")
    assert catalog.lipid_partner_count == 3 and catalog.glycan_partner_count == 2
    assert {p.component_atom_indexes for p in catalog.partners} == {
        (1, 2),
        (4, 5),
        (6, 7),
        (8,),
        (9,),
    }
    assert (
        sum(
            r["count"]
            for r in json.loads((tmp_path / "non_partner_inventory.json").read_text())
        )
        == 2
    )


def test_ambiguous_component_stops_and_retains_inventory(tmp_path):
    u = system()
    names = u.residues.resnames.copy()
    names[8] = "UNKNOWN"
    u.residues.resnames = names
    with pytest.raises(ValueError, match="Ambiguous components"):
        inventory(u, tmp_path)
    ambiguous = json.loads((tmp_path / "ambiguous_components.json").read_text())
    assert len(ambiguous) == 1 and ambiguous[0]["atom_indexes"] == [8]


def test_additional_attachment_stops(tmp_path):
    u = system()
    u.add_bonds([(0, 2)])
    with pytest.raises(ValueError, match="exactly one attachment"):
        inventory(u, tmp_path)


@pytest.mark.parametrize("mode", ["absent", "guessed", "unknown"])
def test_authoritative_elements_required(mode):
    u = system()
    if mode == "absent":
        u.del_TopologyAttr("elements")
    elif mode == "guessed":
        u._topology.elements._guessed = True
    else:
        u.atoms.elements = [""] + ["C"] * 13
    with pytest.raises(ValueError, match="element"):
        pilot.require_elements(u)


@pytest.mark.parametrize("kind,cutoff", [("lipid", 6.0), ("glycan", 4.5)])
def test_independent_cutoff_is_inclusive_without_tolerance(kind, cutoff):
    partner = {"carrier_residue": {"residue_index": 20}}
    for distance, expected in ((cutoff, True), (np.nextafter(cutoff, np.inf), False)):
        measured = pilot.minimum_distance([[0, 0, 0]], [[distance, 0, 0], [99, 99, 99]])
        assert pilot.ordinary_positive(kind, measured, 1, partner) is expected


def test_anchor_exclusion_keeps_other_residues():
    p = {"carrier_residue": {"residue_index": 0}}
    assert not pilot.ordinary_positive("glycan", 1.0, 0, p)
    assert pilot.ordinary_positive("glycan", 1.0, 1, p)


def rows(indexes, distances=None, excluded=False):
    return [
        {
            "partner_kind": "lipid",
            "protein_residue_index": 1,
            "partner_id": "membrane-1",
            "prepared_frame_index": i,
            "source_frame_index": pilot.FRAMES[i],
            "minimum_distance_A": d,
            "standard_summary_excluded": excluded,
        }
        for i, d in zip(indexes, distances or [3.0] * len(indexes), strict=True)
    ]


@pytest.mark.parametrize(
    "indexes,episodes,mean,max_length",
    [
        ([0], 1, 0.0, 0.0),
        ([0, 1, 2, 3, 4], 1, 0.2, 0.2),
        ([0, 1, 3, 4], 2, 0.05, 0.05),
        ([0, 2, 3, 4], 2, 0.05, 0.1),
    ],
)
def test_requested_adjacency_lifetimes_and_resolved_negatives(
    indexes, episodes, mean, max_length
):
    result = next(iter(pilot.aggregate_observations(rows(indexes)).values()))
    assert result["n_contact_frames"] == len(indexes)
    assert result["occupancy"] == len(indexes) / 5
    assert result["n_contact_episodes"] == episodes
    assert result["mean_episode_length_ns"] == pytest.approx(mean)
    assert result["max_episode_length_ns"] == pytest.approx(max_length)


def test_positive_only_distance_statistics_and_anchor_filtering():
    observations = rows([0, 3], [2.0, 4.0]) + rows([1], [0.1], excluded=True)
    result = next(iter(pilot.aggregate_observations(observations).values()))
    assert result["distance_mean_A"] == 3.0 and result["distance_min_A"] == 2.0
    assert result["n_contact_frames"] == 2 and result["occupancy"] == 0.4
    assert pilot.aggregate_observations(rows([1], excluded=True)) == {}


def test_metric_comparison_detects_strict_difference():
    expected = next(iter(pilot.aggregate_observations(rows([0, 1])).values()))
    actual = {key: str(value) for key, value in expected.items()}
    assert pilot.compare_metrics(expected, actual) == []
    actual["distance_mean_A"] = "3.0000000001"
    assert len(pilot.compare_metrics(expected, actual)) == 1


def test_source_canonical_values_and_explicit_identity_preserved():
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping import (
        CanonicalResidueMappingRecord,
        CanonicalResidueMappingTable,
    )

    reference = load_default_napi2b_canonical_reference()
    # Deliberately different source numbering: equality cannot infer the mapping.
    record = CanonicalResidueMappingRecord(
        "gromacs",
        "TEST",
        "999",
        "ALA",
        1,
        reference.residue_at(1).canonical_resname,
        "mapped",
    )
    mapping = CanonicalResidueMappingTable((record,))
    source = {
        "dataset_id": "d",
        "system_id": "s",
        "trajectory_id": "t",
        "replica_id": "r",
        "window_id": "w",
        "protein_residue_index": "8",
        "lipid_partner_id": "p",
        "engine": "gromacs",
        "protein_chain_id": "TEST",
        "protein_resid": "999",
        "protein_resname": "ALA",
        "occupancy": "0.4",
        "n_contact_frames": "2",
    }
    canonical = {
        **source,
        "canonical_residue_number": "1",
        "canonical_resname": record.canonical_resname,
    }
    assert pilot.compare_canonical([source], [canonical], "lipid", mapping) == []
    canonical["occupancy"] = "0.40000000000001"
    assert len(pilot.compare_canonical([source], [canonical], "lipid", mapping)) == 1
    assert pilot.compare_canonical([source], [], "lipid", mapping)
    with pytest.raises(ValueError, match="mapping"):
        pilot.compare_canonical(
            [source], [canonical], "lipid", CanonicalResidueMappingTable(())
        )


def test_cli_capture_preserves_production_result_and_restores_functions(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    import mania.cli as cli
    import mania.preprocessing.specialized_contact_execution as execution

    result = SimpleNamespace(
        contact_count=1,
        to_dict=lambda: {"frame_index": 0, "contacts": [{"distance": 4.5}]},
    )
    calls = []

    def geometry(frame):
        calls.append(frame)
        return result

    monkeypatch.setattr(execution, "compute_protein_glycan_contacts", geometry)
    original_lipid = execution.compute_protein_lipid_contacts
    frame = SimpleNamespace(frame_index=0)

    def main():
        assert execution.compute_protein_glycan_contacts(frame) is result

    monkeypatch.setattr(cli, "main", main)
    monkeypatch.setattr(pilot.sys, "argv", ["pilot"])
    pilot.dump(tmp_path / "commands.json", [])
    pilot.mania_worker(tmp_path, ["--version"])
    assert calls == [frame]
    assert execution.compute_protein_glycan_contacts is geometry
    assert execution.compute_protein_lipid_contacts is original_lipid
    trace = json.loads((tmp_path / "mania_specialized_per_frame.jsonl").read_text())
    assert trace == {"partner_kind": "glycan", **result.to_dict()}
    assert json.loads((tmp_path / "commands.json").read_text())[0]["argv"] == [
        "mania",
        "--version",
    ]
