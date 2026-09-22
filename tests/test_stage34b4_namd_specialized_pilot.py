"""Bounded NAMD continuation gates; all scientific inputs here are synthetic."""

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")
spec = importlib.util.spec_from_file_location(
    "stage34b4_pilot",
    Path(__file__).parents[1] / "tools/stage34b4_namd_specialized_pilot.py",
)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


@pytest.mark.parametrize(
    "field",
    [
        "prepared_frame_index",
        "source_dcd_frame_index",
        "requested_sample_index",
        "authoritative_time_ps",
        "passed",
        "checks",
    ],
)
def test_changed_accepted_frame_map_stops(field):
    records = [
        {**r, "passed": True, "checks": {"identity": True}}
        for r in pilot.b3.frame_map()
    ]
    pilot.validate_frame_records(records)
    records[0][field] = (
        {"identity": False}
        if field == "checks"
        else False
        if field == "passed"
        else 999
    )
    with pytest.raises(ValueError):
        pilot.validate_frame_records(records)


def test_exact_source_block_retains_patch_and_line_evidence(tmp_path):
    path = tmp_path / "source.str"
    path.write_text(
        "RESI X 0 ! synthetic\nATOM C CT 0\nBOND C H\n"
        "PRES P 0\nDELE ATOM 1H\nATOM 1C CX 0\nBOND 1C 2O\nEND\n"
    )
    block = pilot.source_blocks(path, "PRES", "P")[0]
    assert block["line"] == 4 and block["atoms"] == {"1C": "CX"}
    assert block["delete"] == ["1H"] and block["bonds"] == [["1C", "2O"]]
    assert block["source"]["sha256"] == pilot.file_record(path)["sha256"]
    with pytest.raises(ValueError, match="Missing source declaration"):
        pilot.source_blocks(path, "RESI", "MISSING")


def definitions():
    return {
        "POPC": [{"atoms": {"A": "TYPE"}, "line": 1}],
        "BGLC": [{"atoms": {"O1": "OX", "HO1": "HY"}, "line": 2}],
        "CER160": [{"atoms": {"C1S": "CX", "O1": "OX", "HO1": "HY"}, "line": 3}],
        "CERB": [{"atoms": {"1O1": "NEW"}, "delete": ["1HO1", "2O1", "2HO1"]}],
    }


def test_name_alone_never_classifies():
    with pytest.raises(ValueError, match="membership mismatch"):
        pilot.classify_component(
            [{"resname": "POPC", "atom_types": {"A": "WRONG"}}], [], definitions()
        )
    with pytest.raises(ValueError, match="Unreviewed"):
        pilot.classify_component(
            [{"resname": "UNKNOWN", "atom_types": {}}], [], definitions()
        )


@pytest.mark.parametrize("change", [None, "membership", "bond", "extra_residue"])
def test_complete_connected_ceramide_glucose_patch(change):
    residues = [
        {"resname": "BGLC", "atom_types": {"O1": "NEW"}},
        {"resname": "CER160", "atom_types": {"C1S": "CX"}},
    ]
    bonds = [(("BGLC", "O1"), ("CER160", "C1S"))]
    if change == "membership":
        residues[0]["atom_types"]["HO1"] = "HY"
    elif change == "bond":
        bonds = []
    elif change == "extra_residue":
        residues.append({"resname": "BGLC", "atom_types": {"O1": "NEW"}})
    if change:
        with pytest.raises(ValueError):
            pilot.classify_component(residues, bonds, definitions())
    else:
        assert pilot.classify_component(residues, bonds, definitions())[:2] == (
            "lipid",
            "BGLC:1+CER160:1",
        )


def synthetic(tmp_path):
    from mania.dataset_identity import DatasetTrajectoryIdentity, DatasetTrajectorySpec
    from mania.preprocessing.physical_time_execution import (
        PreprocessingConditionTemporalExecution,
        PreprocessingTemporalExecution,
    )

    u = mda.Universe.empty(
        6, n_residues=6, atom_resindex=list(range(6)), trajectory=True
    )
    for name, values in (
        ("ids", list(range(1, 7))),
        ("names", ["C"] * 6),
        ("resnames", ["ASN", "ASN", "SUGAR-X", "SUGAR-Y", "LIP-X", "LIP-X"]),
        ("resids", [295, 308, 1001, 1002, 2001, 2002]),
        ("segids", ["PROA"]),
        ("elements", ["C"] * 6),
        ("bonds", [(0, 2), (1, 3)]),
    ):
        u.add_TopologyAttr(name, values)
    coords = np.asarray(
        [
            [[0, 0, 0], [20, 0, 0], [1, 0, 0], [21, 0, 0], [d, 0, 0], [50, 0, 0]]
            for d in (6, 7, 6, 7, 6)
        ],
        dtype=np.float32,
    )
    u.load_new(coords, format=mda.coordinates.memory.MemoryReader, dt=100)
    # MemoryReader uses frame * dt; explicit test-only axis starts at 100 ps.
    u.trajectory.ts.data["time_offset"] = 100
    context = pilot.b3.pbc.topology_context(u)
    partners = pilot.shared.glycan_components(u, context, context["heavy"])
    for i in (4, 5):
        p = pilot.shared.component_record(u, [i], i, context["heavy"])
        p.update(
            partner_id=f"lipid_{i}", partner_kind="lipid", partner_name="synthetic"
        )
        partners.append(p)
    for p in partners:
        p["heavy_atom_indexes"] = p["atom_indexes"]
    pilot.shared.build_metadata(
        u, partners, tmp_path / "molecular_partner_metadata.json"
    )
    temporal, samples, windows = pilot.b3.sampling_contract()
    identity = DatasetTrajectoryIdentity(
        dataset_id="synthetic",
        system_id="synthetic",
        trajectory_id="synthetic",
        variant_id="WT",
        engine="namd",
        condition=None,
        replica_id="1",
        disulfide_state="2SS",
    )
    binding = PreprocessingConditionTemporalExecution(
        "synthetic",
        DatasetTrajectorySpec(identity=identity, temporal=temporal),
        samples,
        windows,
    )
    return u, partners, PreprocessingTemporalExecution((binding,))


def test_five_frame_production_independent_and_export(tmp_path):
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping import (
        CanonicalResidueMappingRecord,
        CanonicalResidueMappingTable,
    )

    u, partners, temporal = synthetic(tmp_path)
    execution, tables = pilot.execute_science(u, temporal, tmp_path)
    observations = pilot.independent_observations(u, partners)
    report = pilot.compare_independent(
        observations, execution.condition_results[0], tables
    )
    assert report["status"] == "PASS"
    assert len(observations) == 13  # three inclusive-cutoff lipids + ten anchors
    assert len(tables[0].rows) == 1 and not tables[1].rows
    row = tables[0].rows[0]
    assert (row.occupancy, row.n_contact_episodes, row.max_episode_length_ns) == (
        0.6,
        3,
        0,
    )
    reference = load_default_napi2b_canonical_reference()
    mapping = CanonicalResidueMappingTable(
        tuple(
            CanonicalResidueMappingRecord(
                "namd",
                "PROA",
                str(n),
                "ASN",
                n,
                reference.residue_at(n).canonical_resname,
                "mapped",
            )
            for n in (295, 308)
        )
    )
    canonical, technical = pilot.export_validate(
        execution, tables, mapping, temporal, tmp_path
    )
    assert canonical["lipid"]["scientific_value_mismatches"] == 0
    assert technical["status"] == "passed" and technical["complete"]
    damaged = list(observations)
    damaged[0] = {**damaged[0], "minimum_distance_A": 999}
    assert (
        pilot.compare_independent(damaged, execution.condition_results[0], tables)[
            "status"
        ]
        == "FAIL"
    )


def test_full_stride_episode_and_anchor_exclusion():
    rows = [
        {
            "prepared_frame_index": i,
            "partner_kind": "glycan",
            "partner_id": "x",
            "protein_residue_index": 0,
            "minimum_distance_A": 2,
            "standard_summary_excluded": False,
        }
        for i in range(5)
    ]
    value = pilot.shared.aggregate_observations(rows, times=pilot.b3.TIMES_PS)
    assert value[("glycan", 0, "x")]["max_episode_length_ns"] == 0.4
    assert value[("glycan", 0, "x")]["n_contact_episodes"] == 1
    assert (
        pilot.shared.aggregate_observations(
            [{**r, "standard_summary_excluded": True} for r in rows],
            times=pilot.b3.TIMES_PS,
        )
        == {}
    )


@pytest.mark.parametrize("phase", ["binding", "catalog"])
def test_gate_failure_stops_all_science_and_packages(tmp_path, monkeypatch, phase):
    monkeypatch.setattr(pilot, "checkpoint", lambda *_: "test")
    if phase == "binding":
        monkeypatch.setattr(
            pilot, "bind_accepted", Mock(side_effect=ValueError("changed binding"))
        )
    else:
        monkeypatch.setattr(pilot, "bind_accepted", lambda *_: (None,) * 5)
        monkeypatch.setattr(
            pilot, "inventory", Mock(side_effect=ValueError("unresolved component"))
        )
    forbidden = Mock(side_effect=AssertionError("Science passed a blocked gate"))
    monkeypatch.setattr(pilot, "execute_science", forbidden)
    result = pilot.run(tmp_path, tmp_path)
    assert result["stage34b4_status"] == "BLOCKED"
    assert result["stage34b5_status"] == result["stage34c_prep_status"] == "NOT RUN"
    forbidden.assert_not_called()
    assert (
        json.loads((tmp_path / "downstream_not_run.json").read_text())[
            "stage31_32_33_executed"
        ]
        is False
    )


def test_unknown_and_conflicting_elements_fail():
    u = mda.Universe.empty(1, trajectory=True)
    u.add_TopologyAttr("types", ["UNKNOWN"])
    with pytest.raises(KeyError):
        pilot.b3.attach_elements(u, {})
    u.add_TopologyAttr("elements", ["O"])
    with pytest.raises(ValueError, match="Conflicting"):
        pilot.b3.attach_elements(u, {"UNKNOWN": "C"})


def test_duplicate_or_wrong_denominator_rejected(tmp_path):
    u, partners, temporal = synthetic(tmp_path)
    execution, tables = pilot.execute_science(u, temporal, tmp_path)
    observations = pilot.independent_observations(u, partners)
    with pytest.raises(ValueError, match="Duplicate independent"):
        pilot.compare_independent(
            observations + observations[:1], execution.condition_results[0], tables
        )
    row = tables[0].rows[0]
    damaged = replace(
        row,
        resolved_frame_count=4,
        missing_sample_count=1,
        coverage_fraction=0.8,
        occupancy=0.75,
    )
    with pytest.raises(ValueError, match="denominator"):
        pilot.compare_independent(
            observations,
            execution.condition_results[0],
            (replace(tables[0], rows=(damaged,)), tables[1]),
        )
