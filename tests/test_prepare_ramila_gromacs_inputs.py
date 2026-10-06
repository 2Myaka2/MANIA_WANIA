"""Native full-axis preparation, representation tolerance and early storage gate."""

import importlib
from types import SimpleNamespace

import pytest
from test_ramila_gromacs_runtime import make_site, rt

prep = importlib.import_module("prepare_ramila_gromacs_inputs")


def native_site(tmp_path, monkeypatch):
    mda = pytest.importorskip("MDAnalysis")
    import numpy as np

    site = make_site(tmp_path)
    row = site.rows[0]
    row["dataset_spec"]["temporal"]["production_end_ns"] = 8.0
    u = mda.Universe.empty(
        12, n_residues=3, atom_resindex=[0] * 4 + [1] * 4 + [2] * 4, trajectory=True
    )
    u.add_TopologyAttr("resnames", ["ALA", "GLY", "LIP"])
    u.add_TopologyAttr("resids", [20, 80, 90])
    u.add_TopologyAttr("masses", [12.0] * 12)
    u.add_TopologyAttr(
        "bonds", [(i, i + 1) for i in range(7)] + [(8, 9), (9, 10), (10, 11)]
    )
    path = site.source / row["xtc_path"]
    path.unlink()
    with mda.Writer(str(path), n_atoms=12, precision=4) as writer:
        for n in range(16):
            u.trajectory.ts.positions = np.array(
                [[19.6 + i * 0.2, 4, 4] for i in range(8)]
                + [[-1 + i * 0.2, 9, 9] for i in range(4)],
                dtype=np.float32,
            )
            u.trajectory.ts.positions[:8, 0] %= 20
            u.trajectory.ts.dimensions = [20, 20 + n * 0.01, 20, 90, 90, 90]
            u.trajectory.ts.time = 5000 + n * 200
            writer.write(u.atoms)
    monkeypatch.setattr(mda, "Universe", lambda *a, **kw: u)
    monkeypatch.setattr(rt, "validate_topology", lambda *a: None)
    # Literal source identity and native file reading remain active.
    return site, row


def test_native_full_axis_unwrap_center_wrap_and_roundtrip(tmp_path, monkeypatch):
    site, row = native_site(tmp_path, monkeypatch)
    result = prep.prepare(site.source, site.output, row, runtime=site.runtime)
    assert result["full_axis_preserved"] is True
    assert result["source_frames"] == result["prepared_frames"] == 16
    assert result["source_frame_indexes"] == list(range(16))
    assert result["max_coordinate_component_error_A"] <= 0.001
    assert result["max_cell_component_error"] <= 0.001
    for field in (
        "atom_order_preserved",
        "frame_order_preserved",
        "exact_time_identity",
        "cells_preserved",
    ):
        assert result[field] is True
    assert not (site.output / "verification_coordinates.float32").exists()
    from MDAnalysis.lib.formats.libmdaxdr import XTCFile

    with XTCFile(str(site.output / "prepared.xtc"), "r") as reader:
        frames = list(reader)
    assert [f.time for f in frames] == list(range(5000, 8001, 200))
    import numpy as np

    # The broken source protein bond crosses the cell; preparation restores it.
    assert (
        max(np.linalg.norm(np.diff(f.x[:8], axis=0), axis=1).max() for f in frames)
        < 0.021
    )


def test_storage_fails_before_output_or_heavy_preparation(tmp_path, monkeypatch):
    site, row = native_site(tmp_path, monkeypatch)
    monkeypatch.setattr(prep.shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    with pytest.raises(ValueError, match="Insufficient storage BEFORE"):
        prep.prepare(site.source, site.output, row, runtime=site.runtime)
    assert not site.output.exists()


def test_storage_estimate_tracks_actual_atoms_frames_and_representation():
    small = prep.storage_budget(10000, 100, 12, 16, 16, 200)
    large = prep.storage_budget(10000, 100, 12, 100, 16, 200)
    assert large["verification_scratch_bytes"] == 12 * 12 * 100
    assert large["required_free_bytes"] > small["required_free_bytes"]
    assert small["required_free_bytes"] < 100000


def test_duplicate_native_axis_is_not_repaired(tmp_path):
    mda = pytest.importorskip("MDAnalysis")
    u = mda.Universe.empty(12, trajectory=True)
    u.dimensions = [20, 20, 20, 90, 90, 90]
    path = tmp_path / "duplicate.xtc"
    with mda.Writer(str(path), n_atoms=12, precision=4) as writer:
        for time in (5000, 5200, 5200, 5400):
            u.trajectory.ts.time = time
            writer.write(u.atoms)
    from test_ramila_gromacs_runtime import spec

    with pytest.raises(ValueError, match="BLOCKED"):
        rt.scan_xtc(path, atom_count=12, spec=spec(end=8))


@pytest.mark.parametrize("damage", ["cell", "atom_count", "truncated"])
def test_native_invalid_cell_atom_count_and_truncation_block(tmp_path, damage):
    mda = pytest.importorskip("MDAnalysis")
    from test_ramila_gromacs_runtime import spec

    u = mda.Universe.empty(12, trajectory=True)
    u.trajectory.ts.time = 5000
    if damage != "cell":
        u.dimensions = [20, 20, 20, 90, 90, 90]
    path = tmp_path / "invalid.xtc"
    with mda.Writer(str(path), n_atoms=12, precision=4) as writer:
        writer.write(u.atoms)
    if damage == "truncated":
        path.write_bytes(path.read_bytes()[:-5])
    with pytest.raises(ValueError):
        rt.scan_xtc(
            path, atom_count=13 if damage == "atom_count" else 12, spec=spec(end=8)
        )


def test_preparation_publishes_all_frame_integrity_and_original_report_stays_immutable(
    tmp_path, monkeypatch
):
    from mania.preprocessing.protein_integrity_observations import (
        read_protein_integrity,
    )

    site, row = native_site(tmp_path, monkeypatch)
    prep.prepare(site.source, site.output, row, runtime=site.runtime)
    before = (site.output / "preparation_complete.json").read_bytes()
    evidence = read_protein_integrity(
        site.output / "protein_integrity_observations.json"
    )
    assert len(evidence.observations) == 16
    assert evidence.scientific_pbc_status == "unresolved"
    assert evidence.protein_remains_broken is None
    assert evidence.protein_fragment_ids == [0]
    assert all(f.bond_representation_max_error_A < 1e-5 for f in evidence.observations)
    assert (site.output / "preparation_complete.json").read_bytes() == before
