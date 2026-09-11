"""Synthetic topology authority and a single shared selected-frame geometry pass."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_preprocessing_molecular_partner_metadata_io import metadata
from test_preprocessing_protein_edge_window_table import table_input

from mania.preprocessing import specialized_contact_execution as execution
from mania.preprocessing.molecular_partner_catalog_io import (
    read_molecular_partner_catalog,
    validate_molecular_partner_catalog,
    write_molecular_partner_catalog,
)
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution


class Trajectory:
    def __init__(self, runtime, binding, positions=None):
        self.runtime, self.binding, self.positions = runtime, binding, positions
        self.passes = 0
        self.visited = []

    def __iter__(self):
        self.passes += 1
        for sample in self.binding.sampling_plan.selected_samples:
            index = sample.source_frame_index
            self.visited.append(index)
            if self.positions:
                for residue, position in zip(
                    self.runtime.residues,
                    self.positions[sample.requested_sample_index],
                    strict=True,
                ):
                    residue.atoms[0].position = position
            yield SimpleNamespace(time=sample.actual_time_ps)


def runtime(binding=None, *, external=False, positions=None):
    binding = binding or table_input(condition=None, engine="namd").temporal_execution
    residues = [
        SimpleNamespace(
            ix=i,
            resid=10 + i,
            resname=name,
            segid=None,
            atoms=[
                SimpleNamespace(
                    index=i, element="C", name="H-misleading", position=position
                )
            ],
        )
        for i, (name, position) in enumerate(
            zip(
                ("ALA", "GLY", "UNKNOWN-X", "UNKNOWN-X"),
                ((0, 0, 0), (3, 0, 0), (2, 0, 0), (1, 0, 0)),
                strict=True,
            )
        )
    ]
    value = SimpleNamespace(residues=residues)
    value.select_atoms = Mock(return_value=SimpleNamespace(residues=residues[:2]))
    if not external:
        value.bonds = [SimpleNamespace(indices=(0, 3))]
    value.trajectory = Trajectory(value, binding, positions)
    return value, binding


def retained(*, external=False, lipid=True, glycan=True, binding=None, positions=None):
    rt, binding = runtime(binding, external=external, positions=positions)
    result = execution.execute_specialized_contact_condition(
        rt, binding, metadata(lipid=lipid, glycan=glycan, external=external)
    )
    return rt, binding, result


@pytest.mark.parametrize(
    "lipid,glycan", [(True, False), (False, True), (True, True), (False, False)]
)
@pytest.mark.parametrize("external", [False, True])
def test_layer_catalogs_and_exactly_one_shared_pass(
    lipid, glycan, external, monkeypatch
):
    lipid_spy = Mock(wraps=execution.compute_protein_lipid_contacts)
    glycan_spy = Mock(wraps=execution.compute_protein_glycan_contacts)
    monkeypatch.setattr(execution, "compute_protein_lipid_contacts", lipid_spy)
    monkeypatch.setattr(execution, "compute_protein_glycan_contacts", glycan_spy)
    rt, binding, result = retained(external=external, lipid=lipid, glycan=glycan)
    assert rt.trajectory.passes == int(lipid or glycan)
    rt.select_atoms.assert_called_once_with("protein")
    selected = binding.selected_source_frame_indexes
    assert tuple(f.frame_index for f in result.lipid_frame_results) == (
        selected if lipid else ()
    )
    assert tuple(f.frame_index for f in result.glycan_frame_results) == (
        selected if glycan else ()
    )
    assert lipid_spy.call_count == len(selected) * lipid
    assert glycan_spy.call_count == len(selected) * glycan
    if lipid and glycan:
        for lipid_call, glycan_call in zip(
            lipid_spy.call_args_list, glycan_spy.call_args_list, strict=True
        ):
            assert (
                lipid_call.args[0].atom_coordinates
                is glycan_call.args[0].atom_coordinates
            )
    before = rt.trajectory.passes
    root = execution.PreprocessingSpecializedContactExecution((result,))
    tables = execution.build_specialized_contact_source_tables(
        root, PreprocessingTemporalExecution((binding,))
    )
    assert rt.trajectory.passes == before
    assert all(row.condition is None for table in tables for row in table.rows)
    assert "coordinates" not in json.dumps(root.to_dict())
    assert result.topology_connectivity_status == (
        "unavailable" if external else "available"
    )


@pytest.mark.parametrize(
    "damage",
    [
        "no_element",
        "blank_element",
        "unknown_element",
        "contradictory",
        "bad_number",
        "no_protein",
        "bad_source",
        "bad_bond",
        "short_trajectory",
    ],
)
def test_runtime_authority_and_geometry_failures(damage):
    rt, binding = runtime()
    atom = rt.residues[0].atoms[0]
    if damage == "no_element":
        del atom.element
        atom.name, atom.mass, atom.type = "C", 12.0, "C"
    elif damage == "blank_element":
        atom.element = ""
    elif damage == "unknown_element":
        atom.element = "XX"
    elif damage == "contradictory":
        atom.atomic_number = 1
    elif damage == "bad_number":
        atom.atomic_number = True
    elif damage == "no_protein":
        rt.select_atoms.return_value = SimpleNamespace(residues=[])
    elif damage == "bad_source":
        rt.residues[1].ix = 7
    elif damage == "bad_bond":
        rt.bonds = [SimpleNamespace(indices=(0, 999))]
    else:
        rt.trajectory = []
    error = (
        execution.MolecularPartnerIdentificationExecutionError
        if damage in ("no_protein", "bad_source", "bad_bond")
        else execution.SpecializedContactComputationError
    )
    with pytest.raises(error):
        execution.execute_specialized_contact_condition(rt, binding, metadata())


def test_atomic_number_authority_and_unavailable_bond_api():
    atom = SimpleNamespace(atomic_number=6, name="H", mass=1, type="hydrogen")
    assert execution.authoritative_is_hydrogen(atom) is False
    assert execution.authoritative_is_hydrogen(SimpleNamespace(atomic_number=1)) is True
    assert execution.authoritative_is_hydrogen(SimpleNamespace(element="H")) is True
    rt, binding = runtime(external=True)
    result = execution.execute_specialized_contact_condition(
        rt, binding, metadata(external=True)
    )
    assert result.partner_catalog.partners[1].carrier_link_bond is None
    assert all(
        c.carrier_link_atom_index is None
        for f in result.glycan_frame_results
        for c in f.contacts
    )


def test_catalog_strict_roundtrip_and_no_coordinates(tmp_path):
    _, _, result = retained()
    catalog = execution.PreprocessingSpecializedContactExecution((result,)).catalog()
    written = write_molecular_partner_catalog(catalog, tmp_path)
    assert (
        written.passed
        and read_molecular_partner_catalog(written.output_path) == catalog
    )
    assert validate_molecular_partner_catalog(written.output_path).passed
    data = json.loads(written.output_path.read_text())
    assert "coordinates" not in json.dumps(data)
    data["bindings"][0]["partner_catalog"]["partner_count"] = True
    written.output_path.write_text(json.dumps(data))
    assert not validate_molecular_partner_catalog(written.output_path).passed


def test_runtime_condition_result_rejects_duplicate_and_absent_kind_frames():
    _, _, result = retained(lipid=True, glycan=False)
    with pytest.raises(ValueError):
        replace(result, lipid_frame_results=result.lipid_frame_results * 2)
    _, _, glycan = retained(lipid=False, glycan=True)
    with pytest.raises(ValueError):
        replace(result, glycan_frame_results=glycan.glycan_frame_results)


def test_guessed_elements_fail_and_guessed_bonds_use_explicit_fallback():
    rt, binding = runtime()
    rt._topology = SimpleNamespace(elements=SimpleNamespace(is_guessed=True))
    with pytest.raises(execution.SpecializedContactComputationError):
        execution.execute_specialized_contact_condition(rt, binding, metadata())
    rt, binding = runtime()
    rt.bonds[0].is_guessed = True
    result = execution.execute_specialized_contact_condition(
        rt, binding, metadata(external=True)
    )
    assert result.topology_connectivity_status == "unavailable"
    assert result.partner_catalog.partners[1].linkage_evidence == "external_metadata"


def test_empty_catalog_skips_atom_typing_and_geometry_but_retains_identification():
    rt, binding = runtime()
    for residue in rt.residues:
        del residue.atoms[0].element
    result = execution.execute_specialized_contact_condition(
        rt, binding, metadata(lipid=False, glycan=False)
    )
    assert result.partner_catalog.partner_count == 0 and rt.trajectory.passes == 0
