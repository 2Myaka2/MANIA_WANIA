"""Approved RMSD math, explicit mapping and production-roster/reference semantics."""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_preprocessing_physical_time_execution import dataset_spec

from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)
from mania.preprocessing.physical_time_windows import plan_physical_time_windows
from mania.preprocessing.trajectory_rmsd import (
    RMSDAccumulator,
    SelectedFrameObservation,
    fitted_rmsd,
    select_mapped_ca_atoms,
    validate_selection_mapping,
)

XYZ = np.array([[0, 0, 0], [3, 0, 0], [0, 4, 0], [1, 2, 5]], dtype=np.float64)


def mapped_universe(positions=(311, 330, 331, 332), *, substitution=False):
    reference = load_default_napi2b_canonical_reference()
    residues, records, atoms = [], [], []
    for i, position in enumerate(positions):
        canonical = reference.residue_at(position).canonical_resname
        source_name = "MET" if substitution and position == 330 else canonical
        residue = SimpleNamespace(
            ix=i, resid=900 + i, resname=source_name, segid="PROA"
        )
        atom = SimpleNamespace(
            index=i,
            id=100 + i,
            name="CA",
            element="C",
            residue=residue,
            position=XYZ[i % 4].copy(),
        )
        residue.atoms = [atom]
        residues.append(residue)
        atoms.append(atom)
        records.append(
            CanonicalResidueMappingRecord(
                "gromacs",
                "PROA",
                str(residue.resid),
                source_name,
                position,
                canonical,
                "mapped",
            )
        )
    records.sort(key=lambda r: r.source_key)
    universe = SimpleNamespace(
        residues=residues,
        atoms=atoms,
        select_atoms=lambda _: SimpleNamespace(residues=residues),
    )
    return universe, CanonicalResidueMappingTable(tuple(records))


def temporal_binding(times=None, *, end=8.0, spec=None):
    times = list(range(0, int(end * 1000) + 1, 200)) if times is None else times
    spec = spec or dataset_spec(
        production_start_ns=5.0,
        production_end_ns=end,
        window_length_ns=2.0,
        window_step_ns=1.0,
    )
    plan = resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, float(t)) for i, t in enumerate(times)),
        temporal=spec.temporal,
    )
    windows = plan_physical_time_windows(
        plan,
        temporal=spec.temporal,
        boundary_profile="mania.window_boundaries.inclusive.v1",
    )
    return PreprocessingConditionTemporalExecution(
        spec.identity.condition or "normal", spec, plan, windows
    )


def accumulator(binding=None):
    universe, mapping = mapped_universe()
    selection, _ = select_mapped_ca_atoms(universe, mapping, "gromacs")
    binding = binding or temporal_binding()
    return RMSDAccumulator(
        binding,
        selection,
        source_frame_map=tuple(range(binding.sampling_plan.source_frame_count)),
    )


def test_retained_selection_checked_against_exact_mapping():
    universe, mapping = mapped_universe()
    selection, _ = select_mapped_ca_atoms(universe, mapping, "gromacs")
    validate_selection_mapping(selection, mapping)
    changed = selection.model_copy(deep=True)
    changed.atoms[0] = changed.atoms[0].model_copy(
        update={"source_resid": "unrepresented"}
    )
    with pytest.raises(ValueError, match="explicit canonical mapping"):
        validate_selection_mapping(changed, mapping)


def test_model_and_reader_imports_preserve_lazy_scientific_boundary():
    script = """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in {'numpy', 'MDAnalysis'}:
        raise AssertionError('Scientific library imported before measurement')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
import mania.preprocessing.trajectory_rmsd
import mania.preprocessing.trajectory_rmsd_io
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("transform", ["self", "translation", "rotation"])
def test_self_and_rigid_motion_removed(transform):
    value = XYZ.copy()
    if transform == "translation":
        value += [100, -33, 2]
    if transform == "rotation":
        value = value @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]) + 10
    before = value.copy()
    assert fitted_rmsd(value, XYZ) < 1e-12
    np.testing.assert_array_equal(value, before)


def test_reflection_and_conformation_remain_and_repeat_exactly():
    reflected = XYZ * [-1, 1, 1]
    assert fitted_rmsd(reflected, XYZ) > 0.1
    displaced = XYZ.copy()
    displaced[-1, 2] += 2
    result = fitted_rmsd(displaced, XYZ)
    assert result > 0.1
    assert fitted_rmsd(displaced, XYZ) == result
    assert type(result) is float
    assert fitted_rmsd(displaced.astype(np.float32), XYZ.astype(np.float32)) == result


@pytest.mark.parametrize(
    "value",
    [
        np.full((4, 3), np.nan),
        np.full((4, 3), np.inf),
        [[1, 2]],
        np.zeros((4, 4)),
        np.zeros((4, 3)),
        np.zeros((2, 3)),
        "bad",
    ],
)
def test_reject_numerical_shape_and_alignment_domain(value):
    with pytest.raises(ValueError):
        fitted_rmsd(value, XYZ)


@pytest.mark.parametrize("substitution", [False, True])
def test_mapping_uses_complete_namespace_and_canonical_order(substitution):
    universe, mapping = mapped_universe((332, 330, 311, 331), substitution=substitution)
    selection, atoms = select_mapped_ca_atoms(universe, mapping, "gromacs")
    assert [a.canonical_residue_number for a in selection.atoms] == [311, 330, 331, 332]
    assert [a.residue.resid for a in atoms] == [902, 901, 903, 900]
    assert all(
        a.source_resid != str(a.canonical_residue_number) for a in selection.atoms
    )
    assert selection.atom_count == 4
    if substitution:
        assert selection.atoms[1].source_resname == "MET"
        assert selection.atoms[1].canonical_resname == "THR"


def test_explicit_deletion_and_684_roster_are_valid():
    positions = tuple(i for i in range(1, 691) if i not in range(331, 337))
    universe, mapping = mapped_universe(positions)
    selection, _ = select_mapped_ca_atoms(universe, mapping, "gromacs")
    assert selection.atom_count == 684
    assert selection.not_represented_canonical_positions == list(range(331, 337))


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "missing_ca",
        "multiple_ca",
        "element",
        "incomplete",
        "unmapped",
        "too_few",
    ],
)
def test_invalid_selection_is_not_inferred(damage):
    universe, mapping = mapped_universe()
    if damage == "duplicate":
        records = list(mapping.mappings)
        records[-1] = replace(
            records[-1],
            canonical_residue_number=records[0].canonical_residue_number,
            canonical_resname=records[0].canonical_resname,
        )
        mapping = CanonicalResidueMappingTable(tuple(records))
    if damage == "missing_ca":
        universe.residues[0].atoms = []
    if damage == "multiple_ca":
        universe.residues[0].atoms *= 2
    if damage == "element":
        universe.atoms[0].element = "N"
    if damage == "incomplete":
        mapping = CanonicalResidueMappingTable(mapping.mappings[:-1])
    if damage == "unmapped":
        mapping = CanonicalResidueMappingTable(
            (
                replace(
                    mapping.mappings[0],
                    mapping_status="unmapped",
                    canonical_residue_number=None,
                    canonical_resname=None,
                ),
                *mapping.mappings[1:],
            )
        )
    if damage == "too_few":
        universe.residues[:] = universe.residues[:2]
    with pytest.raises(ValueError):
        select_mapped_ca_atoms(universe, mapping, "gromacs")


@pytest.mark.parametrize("end,count", [(100.0, 476), (30.0, 126)])
def test_exact_production_roster_excludes_stabilization(end, count):
    value = accumulator(temporal_binding(end=end))
    assert value.binding.sampling_plan.requested_sample_count == count
    assert value.reference_sample.requested_time_ps == 5000
    assert (
        value.binding.sampling_plan.selected_samples[-1].requested_time_ps == end * 1000
    )
    for sample in value.binding.sampling_plan.selected_samples:
        value.observe(SelectedFrameObservation("normal", sample, XYZ, value.selection))
    rows = value.finalize()
    assert len(rows) == count
    assert rows[0].rmsd_A == fitted_rmsd(XYZ, XYZ)


def test_missing_first_request_preserved_no_neighbor_substitution():
    binding = temporal_binding([0, 4990, 5010, 5200, 5400, 8000])
    value = accumulator(binding)
    assert value.reference_sample.requested_sample_index == 1
    assert value.reference_sample.actual_time_ps == 5200
    for sample in binding.sampling_plan.selected_samples:
        value.observe(SelectedFrameObservation("normal", sample, XYZ, value.selection))
    rows = value.finalize()
    assert len(rows) == 16 and rows[0].state == "missing" and rows[0].rmsd_A is None
    assert rows[0].actual_time_ps is None and rows[1].rmsd_A < 1e-12
    assert sum(s.state == "resolved" for s in rows) == 3


def test_zero_resolved_and_incomplete_observations_fail():
    with pytest.raises(ValueError, match="resolved"):
        empty = SimpleNamespace(
            sampling_plan=SimpleNamespace(selected_samples=(), source_frame_count=1)
        )
        accumulator(empty)
    with pytest.raises(ValueError, match="Incomplete"):
        accumulator().finalize()


def test_reference_identity_fixed_and_live_roster_checked():
    value = accumulator()
    sample = value.binding.sampling_plan.selected_samples[1]
    with pytest.raises(ValueError, match="roster"):
        value.observe(SelectedFrameObservation("normal", sample, XYZ, value.selection))
    universe, mapping = mapped_universe()
    _, atoms = select_mapped_ca_atoms(universe, mapping, "gromacs")
    observer = value.selected_frame_observer(atoms)
    universe.atoms[0].name = "CB"
    sample = value.reference_sample
    with pytest.raises(ValueError, match="selection"):
        observer("normal", sample.source_frame_index, sample.actual_time_ps)


def test_changed_roster_is_rejected_even_when_supplied_model_is_mutated():
    value = accumulator()
    value.selection.atoms.reverse()
    with pytest.raises(ValueError, match="roster"):
        value.observe(
            SelectedFrameObservation(
                "normal", value.reference_sample, XYZ, value.selection
            )
        )


def test_kabsch_svd_receives_float64_from_float32_input(monkeypatch):
    original = np.linalg.svd
    dtypes = []

    def observed(value, *args, **kwargs):
        dtypes.append(value.dtype)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(np.linalg, "svd", observed)
    fitted_rmsd(XYZ.astype(np.float32), XYZ.astype(np.float32))
    assert dtypes and set(dtypes) == {np.dtype("float64")}
