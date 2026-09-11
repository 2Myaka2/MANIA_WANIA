import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from math import hypot, nextafter
from pathlib import Path

import pytest

import mania.preprocessing.protein_glycan_contacts as api
from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition,
    MolecularPartnerCatalog,
    MolecularPartnerComponentClassification,
    MolecularPartnerTopology,
    SourceTopologyBond,
    SourceTopologyResidue,
)
from mania.preprocessing.molecular_partner_identification import (
    identify_molecular_partners,
)
from mania.preprocessing.protein_glycan_contacts import (
    PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON,
    ProteinGlycanContactComputationError,
    ProteinGlycanContactFrameInput,
    ProteinGlycanContactFrameResult,
    ProteinGlycanContactObservation,
    compute_protein_glycan_contacts,
)
from mania.preprocessing.protein_lipid_contacts import (
    ProteinLipidContactComputationError,
    SourceAtomFrameCoordinate,
)


def residue(index, atoms, *, resid="source 7", resname="SOURCE-X", segid=None):
    return SourceTopologyResidue(index, resid, resname, segid, atoms)


def coordinate(index, x, y=0.0, z=0.0, hydrogen=False):
    return SourceAtomFrameCoordinate(index, x, y, z, hydrogen)


def make_frame(
    residues,
    coordinates,
    *,
    proteins=(1,),
    glycans=(20,),
    lipids=(),
    bonds=None,
    connectivity="available",
    explicit=(),
):
    if bonds is None:
        bonds = (SourceTopologyBond(0, 2),)
    topology = MolecularPartnerTopology(residues, bonds, connectivity)
    catalog = identify_molecular_partners(
        topology,
        protein_residue_indexes=proteins,
        classifications=tuple(
            MolecularPartnerComponentClassification(i, "glycan", "GLYCAN-X")
            for i in glycans
        )
        + tuple(
            MolecularPartnerComponentClassification(i, "lipid", "LIPID-X")
            for i in lipids
        ),
        explicit_partners=explicit,
    )
    return ProteinGlycanContactFrameInput(
        7, 12.5, topology, catalog, proteins, coordinates
    )


def basic_frame(distance=4.0):
    return make_frame(
        (residue(1, (0, 1)), residue(20, (2, 3))),
        (
            coordinate(0, 0.0),
            coordinate(1, 100.0, hydrogen=True),
            coordinate(2, distance),
            coordinate(3, 100.1, hydrogen=True),
        ),
    )


def basic_observation():
    return compute_protein_glycan_contacts(basic_frame()).contacts[0]


def multi_frame(first=4.5, distal=10.0):
    return make_frame(
        (residue(1, (0,)), residue(20, (2,)), residue(21, (3,))),
        (coordinate(0, 0.0), coordinate(2, first), coordinate(3, distal)),
        glycans=(20, 21),
        bonds=(SourceTopologyBond(0, 2), SourceTopologyBond(2, 3)),
    )


def external_frame():
    return make_frame(
        (residue(1, (0,)), residue(20, (2,)), residue(21, (3,))),
        (coordinate(0, 0.0), coordinate(2, 4.5), coordinate(3, 10.0)),
        glycans=(20, 21),
        bonds=(),
        connectivity="unavailable",
        explicit=(
            ExplicitMolecularPartnerDefinition(
                "supplied-glycan",
                "glycan",
                "GLYCAN-X",
                (20, 21),
                1,
                20,
                "external_metadata",
            ),
        ),
    )


def mixed_frame():
    return make_frame(
        (residue(1, (0,)), residue(10, (1,)), residue(20, (2,))),
        (coordinate(0, 0.0), coordinate(2, 4.0)),
        lipids=(10,),
    )


def test_exact_constants_public_api_and_coordinate_reuse():
    constants = {
        "PROTEIN_GLYCAN_CONTACT_CUTOFF_A": 4.5,
        "PROTEIN_GLYCAN_CONTACT_KIND": "mania_protein_glycan_contacts",
        "PROTEIN_GLYCAN_CONTACT_SCHEMA_VERSION": "mania.protein_glycan_contacts.v0.1",
        "PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON": (
            "covalent_carrier_first_sugar_linkage"
        ),
        "PROTEIN_GLYCAN_DISTANCE_DEFINITION": "minimum_heavy_atom_distance",
        "PROTEIN_GLYCAN_DISTANCE_UNIT": "angstrom",
    }
    for name, expected in constants.items():
        assert getattr(api, name) == expected
    assert api.__all__ == list(constants) + [
        "ProteinGlycanContactComputationError",
        "ProteinGlycanContactFrameInput",
        "ProteinGlycanContactFrameResult",
        "ProteinGlycanContactObservation",
        "compute_protein_glycan_contacts",
    ]
    assert api.SourceAtomFrameCoordinate is SourceAtomFrameCoordinate
    assert issubclass(ProteinGlycanContactComputationError, ValueError)
    assert list(inspect.signature(compute_protein_glycan_contacts).parameters) == [
        "frame"
    ]


@pytest.mark.parametrize(
    "model",
    [
        basic_frame(),
        basic_observation(),
        compute_protein_glycan_contacts(basic_frame()),
    ],
)
def test_models_are_frozen(model):
    for field in fields(model):
        with pytest.raises(FrozenInstanceError):
            setattr(model, field.name, None)


def test_exact_field_order_serialization_and_counts():
    frame = basic_frame()
    result = compute_protein_glycan_contacts(frame)
    assert [f.name for f in fields(frame)] == [
        "frame_index",
        "time_ps",
        "topology",
        "partner_catalog",
        "protein_residue_indexes",
        "atom_coordinates",
    ]
    observation = {
        "frame_index": 7,
        "time_ps": 12.5,
        "protein_residue_index": 1,
        "protein_residue_id": "source 7",
        "protein_resname": "SOURCE-X",
        "protein_segid": None,
        "glycan_partner_id": "glycan_0001",
        "glycan_partner_name": "GLYCAN-X",
        "glycan_component_residue_indexes": [20],
        "carrier_residue_index": 1,
        "first_sugar_residue_index": 20,
        "linkage_evidence": "topology_connectivity",
        "carrier_link_atom_index": 0,
        "first_sugar_link_atom_index": 2,
        "standard_summary_excluded": True,
        "standard_summary_exclusion_reason": "covalent_carrier_first_sugar_linkage",
        "minimum_distance_A": 4.0,
    }
    expected = {
        "schema_version": "mania.protein_glycan_contacts.v0.1",
        "kind": "mania_protein_glycan_contacts",
        "cutoff_A": 4.5,
        "distance_unit": "angstrom",
        "distance_definition": "minimum_heavy_atom_distance",
        "frame_index": 7,
        "time_ps": 12.5,
        "protein_residue_count": 1,
        "glycan_partner_count": 1,
        "evaluated_pair_count": 1,
        "contact_count": 1,
        "excluded_contact_count": 1,
        "contacts": [observation],
    }
    for model, data in ((result.contacts[0], observation), (result, expected)):
        assert [f.name for f in fields(model)] == list(data)
        assert list(model.to_dict()) == list(data)
        assert model.to_dict() == data
    for field in fields(result)[:5]:
        assert not field.init
        with pytest.raises(TypeError):
            ProteinGlycanContactFrameResult(**{field.name: None})
    before = (
        frame.topology.to_dict(),
        frame.partner_catalog.to_dict(),
        frame.atom_coordinates,
    )
    outputs = [
        json.dumps(
            compute_protein_glycan_contacts(frame).to_dict(),
            allow_nan=False,
            separators=(",", ":"),
        )
        for _ in range(3)
    ]
    assert outputs == [json.dumps(expected, allow_nan=False, separators=(",", ":"))] * 3
    assert before == (
        frame.topology.to_dict(),
        frame.partner_catalog.to_dict(),
        frame.atom_coordinates,
    )
    result.to_dict()["contacts"].clear()
    assert result.contact_count == 1
    assert result.contacts[0].to_dict()["glycan_component_residue_indexes"] == [20]


@pytest.mark.parametrize(
    "distance, count",
    [
        (0.0, 1),
        (4.0, 1),
        (4.5, 1),
        (4.500001, 0),
        (nextafter(4.5, 5.0), 0),
    ],
)
def test_fixed_inclusive_cutoff_without_epsilon(distance, count):
    result = compute_protein_glycan_contacts(basic_frame(distance))
    assert result.evaluated_pair_count == 1
    assert result.contact_count == result.excluded_contact_count == count
    if count:
        assert result.contacts[0].minimum_distance_A == distance
    else:
        assert result.contacts == ()


@pytest.mark.parametrize("first, distal, minimum", [(4.5, 10.0, 4.5), (10.0, 1.0, 1.0)])
def test_carrier_raw_minimum_keeps_first_sugar_link_atoms_and_whole_partner(
    first, distal, minimum
):
    frame = multi_frame(first, distal)
    (contact,) = compute_protein_glycan_contacts(frame).contacts
    assert contact.minimum_distance_A == minimum
    assert contact.glycan_component_residue_indexes == (20, 21)
    assert contact.standard_summary_excluded is True
    assert (
        contact.standard_summary_exclusion_reason
        == PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON
    )
    assert (contact.carrier_link_atom_index, contact.first_sugar_link_atom_index) == (
        0,
        2,
    )


def test_scientific_smoke_exact_above_and_noncarrier():
    assert (
        compute_protein_glycan_contacts(multi_frame()).contacts[0].minimum_distance_A
        == 4.5
    )
    assert compute_protein_glycan_contacts(multi_frame(4.500001)).contacts == ()
    frame = make_frame(
        (residue(1, (0,)), residue(2, (1,)), residue(20, (2,)), residue(21, (3,))),
        (
            coordinate(0, 0.0),
            coordinate(1, 0.0, 4.0),
            coordinate(2, 4.5),
            coordinate(3, 0.0, 5.0),
        ),
        proteins=(1, 2),
        glycans=(20, 21),
        bonds=(SourceTopologyBond(0, 2), SourceTopologyBond(2, 3)),
    )
    result = compute_protein_glycan_contacts(frame)
    assert (
        result.evaluated_pair_count,
        result.contact_count,
        result.excluded_contact_count,
    ) == (2, 2, 1)
    carrier, noncarrier = result.contacts
    assert (carrier.minimum_distance_A, carrier.standard_summary_excluded) == (
        4.5,
        True,
    )
    assert (
        noncarrier.minimum_distance_A,
        noncarrier.standard_summary_excluded,
        noncarrier.standard_summary_exclusion_reason,
    ) == (1.0, False, None)


def test_multiple_protein_atoms_and_three_glycan_components_use_global_3d_minimum():
    frame = make_frame(
        (residue(1, (0, 1)), residue(20, (2,)), residue(21, (3,)), residue(22, (4, 5))),
        (
            coordinate(0, 0.0),
            coordinate(1, 10.0, 2.0, 3.0),
            coordinate(2, 50.0),
            coordinate(3, 40.0),
            coordinate(4, 30.0),
            coordinate(5, 11.0, 4.0, 5.0),
        ),
        glycans=(20, 21, 22),
        bonds=(
            SourceTopologyBond(0, 2),
            SourceTopologyBond(2, 3),
            SourceTopologyBond(3, 4),
        ),
    )
    (contact,) = compute_protein_glycan_contacts(frame).contacts
    assert contact.minimum_distance_A == 3.0
    assert contact.glycan_component_residue_indexes == (20, 21, 22)


def test_same_name_glycans_stay_independent_and_order_by_source_index_then_id():
    frame = make_frame(
        (residue(1, (0,)), residue(2, (1,)), residue(20, (2,)), residue(21, (3,))),
        (
            coordinate(0, 0.0),
            coordinate(1, 1.0),
            coordinate(2, 3.0),
            coordinate(3, 2.0),
        ),
        proteins=(1, 2),
        glycans=(20, 21),
        bonds=(SourceTopologyBond(0, 2), SourceTopologyBond(1, 3)),
    )
    result = compute_protein_glycan_contacts(frame)
    assert (
        result.protein_residue_count,
        result.glycan_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
        result.excluded_contact_count,
    ) == (2, 2, 4, 4, 2)
    assert [
        (c.protein_residue_index, c.glycan_partner_id) for c in result.contacts
    ] == [
        (1, "glycan_0001"),
        (1, "glycan_0002"),
        (2, "glycan_0001"),
        (2, "glycan_0002"),
    ]
    assert {c.glycan_partner_name for c in result.contacts} == {"GLYCAN-X"}
    assert [c.standard_summary_excluded for c in result.contacts] == [
        True,
        False,
        False,
        True,
    ]


@pytest.mark.parametrize("carrier_atom, sugar_atom", [(0, 2), (2, 0)])
def test_directional_link_atoms_use_topology_ownership_not_canonical_bond_order(
    carrier_atom, sugar_atom
):
    frame = make_frame(
        (residue(1, (carrier_atom,)), residue(20, (sugar_atom,))),
        (coordinate(0, 0.0), coordinate(2, 4.0)),
    )
    bond = frame.partner_catalog.partners[0].carrier_link_bond
    assert (bond.atom_index_a, bond.atom_index_b) == (0, 2)
    contact = compute_protein_glycan_contacts(frame).contacts[0]
    assert (contact.carrier_link_atom_index, contact.first_sugar_link_atom_index) == (
        carrier_atom,
        sugar_atom,
    )


def test_first_sugar_need_not_be_lowest_component():
    frame = multi_frame()
    topology = replace(
        frame.topology, bonds=(SourceTopologyBond(0, 3), SourceTopologyBond(2, 3))
    )
    catalog = identify_molecular_partners(
        topology,
        protein_residue_indexes=(1,),
        classifications=tuple(
            MolecularPartnerComponentClassification(i, "glycan", "GLYCAN-X")
            for i in (20, 21)
        ),
    )
    result = compute_protein_glycan_contacts(
        replace(frame, topology=topology, partner_catalog=catalog)
    )
    assert result.contacts[0].first_sugar_residue_index == 21
    assert result.contacts[0].first_sugar_link_atom_index == 3
    assert result.contacts[0].minimum_distance_A == 4.5


def test_external_linkage_smoke_preserves_identity_and_exclusion_without_bond_atoms():
    frame = external_frame()
    result = compute_protein_glycan_contacts(frame)
    (contact,) = result.contacts
    assert frame.topology.connectivity_status == "unavailable"
    assert frame.topology.bonds == ()
    assert frame.partner_catalog.partners[0].carrier_link_bond is None
    assert (contact.glycan_partner_id, contact.glycan_component_residue_indexes) == (
        "supplied-glycan",
        (20, 21),
    )
    assert (
        contact.carrier_residue_index,
        contact.first_sugar_residue_index,
        contact.linkage_evidence,
    ) == (1, 20, "external_metadata")
    assert (
        contact.carrier_link_atom_index is contact.first_sugar_link_atom_index is None
    )
    assert contact.minimum_distance_A == 4.5
    assert contact.standard_summary_excluded is True
    assert result.excluded_contact_count == 1


def test_hydrogens_cannot_establish_contact_but_moving_heavy_atom_can():
    assert compute_protein_glycan_contacts(basic_frame(10.0)).contacts == ()
    assert compute_protein_glycan_contacts(basic_frame(4.0)).contact_count == 1
    frame = basic_frame(10.0)
    for atom_index, x in ((1, 10.0), (3, 0.0)):
        changed = replace(
            frame,
            atom_coordinates=tuple(
                replace(c, x_A=x) if c.atom_index == atom_index else c
                for c in frame.atom_coordinates
            ),
        )
        assert compute_protein_glycan_contacts(changed).contacts == ()


def test_no_pbc_correction_raw_cartesian_distance_is_9_8(monkeypatch):
    frame = basic_frame(9.9)
    frame = replace(
        frame, atom_coordinates=(coordinate(0, 0.1),) + frame.atom_coordinates[1:]
    )
    distances = []

    def record_distance(*deltas):
        value = hypot(*deltas)
        distances.append(value)
        return value

    monkeypatch.setattr(api, "hypot", record_distance)
    assert compute_protein_glycan_contacts(frame).contacts == ()
    assert distances == [9.8]


def test_mixed_catalog_does_not_require_or_use_lipid_coordinates():
    frame = mixed_frame()
    result = compute_protein_glycan_contacts(frame)
    assert (
        result.glycan_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
    ) == (1, 1, 1)
    with_lipid = replace(
        frame,
        atom_coordinates=(coordinate(0, 0.0), coordinate(1, 0.0), coordinate(2, 4.0)),
    )
    assert compute_protein_glycan_contacts(with_lipid) == result


@pytest.mark.parametrize("lipids", [False, True])
def test_no_glycans_is_valid_empty_result(lipids):
    frame = mixed_frame()
    frame = replace(
        frame,
        partner_catalog=MolecularPartnerCatalog(
            tuple(
                p
                for p in frame.partner_catalog.partners
                if lipids and p.partner_kind == "lipid"
            )
        ),
        atom_coordinates=(coordinate(0, 0.0),),
    )
    result = compute_protein_glycan_contacts(frame)
    assert (
        result.protein_residue_count,
        result.glycan_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
        result.excluded_contact_count,
        result.contacts,
    ) == (1, 0, 0, 0, 0, ())


def test_unrelated_topology_coordinates_are_optional_and_ignored():
    frame = basic_frame()
    frame = replace(
        frame,
        topology=replace(
            frame.topology, residues=frame.topology.residues + (residue(90, (99,)),)
        ),
    )
    supplied = replace(
        frame, atom_coordinates=frame.atom_coordinates + (coordinate(99, 0.0),)
    )
    assert compute_protein_glycan_contacts(frame) == compute_protein_glycan_contacts(
        supplied
    )


@pytest.mark.parametrize("resid", [None, -5, 0, "", " source 7 "])
@pytest.mark.parametrize("segid", [None, "source-chain"])
def test_source_identity_preserved_without_name_or_canonical_inference(resid, segid):
    frame = make_frame(
        (
            residue(1, (0,), resid=resid, resname="H-GLYCAN-looking", segid=segid),
            residue(20, (2,), resname="PROTEIN-looking"),
        ),
        (coordinate(0, 0.0), coordinate(2, 4.0)),
    )
    contact = compute_protein_glycan_contacts(frame).contacts[0]
    assert (
        contact.protein_residue_index,
        contact.protein_residue_id,
        contact.protein_resname,
        contact.protein_segid,
    ) == (1, resid, "H-GLYCAN-looking", segid)
    assert contact.glycan_partner_name == "GLYCAN-X"


@pytest.mark.parametrize("time", [None, 0.0, 999999.0])
def test_time_is_informational_only(time):
    result = compute_protein_glycan_contacts(
        replace(basic_frame(), frame_index=999, time_ps=time)
    )
    assert result.frame_index == result.contacts[0].frame_index == 999
    assert result.time_ps == result.contacts[0].time_ps == time
    assert (
        replace(result.contacts[0], frame_index=7, time_ps=12.5) == basic_observation()
    )


@pytest.mark.parametrize(
    "model",
    [
        basic_frame(),
        basic_observation(),
        compute_protein_glycan_contacts(basic_frame()),
    ],
)
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("frame_index", -1),
        ("frame_index", True),
        ("frame_index", 1.0),
        ("time_ps", -0.1),
        ("time_ps", True),
        ("time_ps", "1"),
        ("time_ps", float("nan")),
        ("time_ps", float("inf")),
        ("time_ps", 10**400),
    ],
)
def test_frame_evidence_is_validated_in_all_models(model, field, bad):
    with pytest.raises(ProteinGlycanContactComputationError, match=field):
        replace(model, **{field: bad})


@pytest.mark.parametrize(
    ("indexes", "message"),
    [
        ((), "non-empty tuple"),
        ([1], "non-empty tuple"),
        ((True,), "non-negative integer"),
        ((1.0,), "non-negative integer"),
        ((-1,), "non-negative integer"),
        ((1, 1), "strictly increasing"),
        ((10, 1), "strictly increasing"),
        ((999,), "exist in topology"),
    ],
)
def test_protein_set_requires_explicit_ordered_nonempty_topology_indexes(
    indexes, message
):
    with pytest.raises(ProteinGlycanContactComputationError, match=message):
        replace(basic_frame(), protein_residue_indexes=indexes)


def test_exact_accepted_input_types_are_required():
    class TopologySubclass(MolecularPartnerTopology):
        pass

    class CatalogSubclass(MolecularPartnerCatalog):
        pass

    class CoordinateSubclass(SourceAtomFrameCoordinate):
        pass

    frame = basic_frame()
    for bad in (
        None,
        object(),
        TopologySubclass(frame.topology.residues, (), "available"),
    ):
        with pytest.raises(
            ProteinGlycanContactComputationError, match="exact MolecularPartnerTopology"
        ):
            replace(frame, topology=bad)
    for bad in (None, object(), CatalogSubclass(frame.partner_catalog.partners)):
        with pytest.raises(
            ProteinGlycanContactComputationError, match="exact MolecularPartnerCatalog"
        ):
            replace(frame, partner_catalog=bad)
    for bad in ([], (object(),), (CoordinateSubclass(0, 0.0, 0.0, 0.0, False),)):
        with pytest.raises(
            ProteinGlycanContactComputationError,
            match="exact SourceAtomFrameCoordinate",
        ):
            replace(frame, atom_coordinates=bad)
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="exact ProteinGlycanContactFrameInput",
    ):
        compute_protein_glycan_contacts(object())


@pytest.mark.parametrize("missing_atom", [0, 1, 2, 3])
def test_every_required_atom_coordinate_is_mandatory_including_hydrogens(missing_atom):
    frame = basic_frame()
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="every protein and glycan partner atom",
    ):
        replace(
            frame,
            atom_coordinates=tuple(
                c for c in frame.atom_coordinates if c.atom_index != missing_atom
            ),
        )


@pytest.mark.parametrize("case", ["duplicate", "out_of_order", "unknown", "empty"])
def test_coordinate_membership_validation(case):
    frame = basic_frame()
    coordinates, message = {
        "duplicate": (
            (frame.atom_coordinates[0],) + frame.atom_coordinates,
            "strictly increasing and unique",
        ),
        "out_of_order": (
            tuple(reversed(frame.atom_coordinates)),
            "strictly increasing and unique",
        ),
        "unknown": (
            frame.atom_coordinates + (coordinate(99, 0.0),),
            "exist in topology",
        ),
        "empty": ((), "every protein and glycan partner atom"),
    }[case]
    with pytest.raises(ProteinGlycanContactComputationError, match=message):
        replace(frame, atom_coordinates=coordinates)


@pytest.mark.parametrize(
    ("atoms", "message"), [((0, 1), "protein residue"), ((2, 3), "glycan partner")]
)
def test_empty_heavy_atom_set_fails_instead_of_reporting_absence(atoms, message):
    frame = basic_frame()
    frame = replace(
        frame,
        atom_coordinates=tuple(
            replace(c, is_hydrogen=True) if c.atom_index in atoms else c
            for c in frame.atom_coordinates
        ),
    )
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match=message + " must have at least one heavy atom",
    ):
        compute_protein_glycan_contacts(frame)


def test_no_glycans_does_not_excuse_an_invalid_protein_heavy_set():
    frame = basic_frame()
    frame = replace(
        frame,
        partner_catalog=MolecularPartnerCatalog(()),
        atom_coordinates=tuple(
            replace(c, is_hydrogen=True) for c in frame.atom_coordinates
        ),
    )
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="protein residue must have at least one heavy atom",
    ):
        compute_protein_glycan_contacts(frame)


@pytest.mark.parametrize("glycan", [False, True])
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("residue_id", "tampered"),
        ("resname", "tampered"),
        ("segid", "tampered"),
    ],
)
def test_individually_valid_catalog_with_mismatched_source_evidence_fails(
    glycan, field, bad
):
    frame = mixed_frame()
    partners = list(frame.partner_catalog.partners)
    i = int(glycan)
    partners[i] = replace(
        partners[i], components=(replace(partners[i].components[0], **{field: bad}),)
    )
    catalog = MolecularPartnerCatalog(tuple(partners))
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="source evidence must match topology",
    ):
        replace(frame, partner_catalog=catalog)


@pytest.mark.parametrize("glycan", [False, True])
def test_catalog_component_missing_from_other_valid_topology_fails(glycan):
    frame = mixed_frame()
    missing = 20 if glycan else 10
    topology = MolecularPartnerTopology(
        tuple(r for r in frame.topology.residues if r.residue_index != missing),
        (),
        "available",
    )
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="partner component residue must exist",
    ):
        replace(frame, topology=topology)


def test_catalog_atom_union_mismatch_with_other_valid_topology_fails():
    frame = basic_frame()
    topology = replace(
        frame.topology,
        residues=(
            frame.topology.residues[0],
            replace(frame.topology.residues[1], atom_indexes=(2, 3, 4)),
        ),
    )
    with pytest.raises(
        ProteinGlycanContactComputationError, match="atom union must match topology"
    ):
        replace(frame, topology=topology)


@pytest.mark.parametrize("indexes", [(1, 10), (1, 20)])
def test_protein_cannot_overlap_any_partner_component(indexes):
    with pytest.raises(
        ProteinGlycanContactComputationError, match="must not overlap protein residues"
    ):
        replace(mixed_frame(), protein_residue_indexes=indexes)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("protein_residue_index", -1),
        ("protein_residue_index", True),
        ("protein_residue_index", 1.0),
        ("protein_residue_id", False),
        ("protein_residue_id", 1.5),
        ("protein_residue_id", []),
        ("protein_resname", ""),
        ("protein_resname", " X"),
        ("protein_resname", None),
        ("protein_segid", ""),
        ("protein_segid", 4),
        ("protein_segid", "X "),
        ("glycan_partner_id", ""),
        ("glycan_partner_id", " id"),
        ("glycan_partner_id", None),
        ("glycan_partner_name", ""),
        ("glycan_partner_name", "X "),
        ("glycan_partner_name", 3),
        ("glycan_component_residue_indexes", ()),
        ("glycan_component_residue_indexes", [10]),
        ("glycan_component_residue_indexes", (11, 10)),
        ("glycan_component_residue_indexes", (10, 10)),
        ("glycan_component_residue_indexes", (-1,)),
        ("glycan_component_residue_indexes", (False,)),
        ("glycan_component_residue_indexes", (10.0,)),
        ("glycan_component_residue_indexes", (1, 10)),
        ("minimum_distance_A", -1.0),
        ("minimum_distance_A", 4.500001),
        ("minimum_distance_A", float("nan")),
        ("minimum_distance_A", float("inf")),
        ("minimum_distance_A", True),
        ("minimum_distance_A", "5.0"),
    ],
)
def test_observation_rejects_invalid_source_identity_membership_or_distance(field, bad):
    with pytest.raises(ProteinGlycanContactComputationError):
        replace(basic_observation(), **{field: bad})


@pytest.mark.parametrize(
    "field",
    [
        "protein_residue_count",
        "glycan_partner_count",
        "evaluated_pair_count",
        "contact_count",
        "excluded_contact_count",
    ],
)
@pytest.mark.parametrize("bad", [-1, True, 1.0])
def test_result_counts_require_nonnegative_integers(field, bad):
    with pytest.raises(ProteinGlycanContactComputationError, match=field):
        replace(compute_protein_glycan_contacts(basic_frame()), **{field: bad})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"protein_residue_count": 0}, "must be positive"),
        ({"evaluated_pair_count": 2}, "must equal protein_residue_count"),
        ({"contact_count": 0}, "must equal contacts length"),
        (
            {"glycan_partner_count": 0, "evaluated_pair_count": 0},
            "not exceed evaluated_pair_count",
        ),
        ({"contacts": []}, "tuple of exact"),
        ({"contacts": (object(),)}, "tuple of exact"),
        (
            {"contacts": (replace(basic_observation(), frame_index=8),)},
            "result frame and time",
        ),
        (
            {"contacts": (replace(basic_observation(), time_ps=None),)},
            "result frame and time",
        ),
    ],
)
def test_result_rejects_inconsistent_counts_records_or_frame(changes, message):
    with pytest.raises(ProteinGlycanContactComputationError, match=message):
        replace(compute_protein_glycan_contacts(basic_frame()), **changes)


@pytest.mark.parametrize("axis", ["x_A", "y_A", "z_A"])
@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), -float("inf"), True, 10**400]
)
def test_shared_coordinate_contract_rejects_invalid_numbers(axis, bad):
    with pytest.raises(ProteinLipidContactComputationError, match=axis):
        replace(coordinate(0, 0.0), **{axis: bad})


@pytest.mark.parametrize("bad", [None, 0, 1, "False"])
def test_shared_coordinate_contract_requires_explicit_exact_hydrogen_bool(bad):
    with pytest.raises(ProteinLipidContactComputationError, match="is_hydrogen"):
        coordinate(0, 0.0, hydrogen=bad)


@pytest.mark.parametrize(
    "field",
    [
        "carrier_residue_index",
        "first_sugar_residue_index",
        "carrier_link_atom_index",
        "first_sugar_link_atom_index",
    ],
)
@pytest.mark.parametrize("bad", [-1, True, 1.0, None])
def test_observation_linkage_indexes_must_be_nonnegative_integers(field, bad):
    with pytest.raises(ProteinGlycanContactComputationError, match=field):
        replace(basic_observation(), **{field: bad})


@pytest.mark.parametrize(
    "changes",
    [
        {"carrier_residue_index": 20},
        {"first_sugar_residue_index": 99},
        {"first_sugar_link_atom_index": 0},
        {"linkage_evidence": "unknown"},
        {"linkage_evidence": None},
        {"linkage_evidence": "external_metadata"},
        {"carrier_link_atom_index": None, "first_sugar_link_atom_index": None},
        {"standard_summary_excluded": False},
        {"standard_summary_excluded": 1},
        {"standard_summary_exclusion_reason": None},
        {"standard_summary_exclusion_reason": "another_reason"},
        {"protein_residue_index": 2},
        {"protein_residue_index": 2, "standard_summary_excluded": False},
        {"protein_residue_index": 2, "standard_summary_exclusion_reason": None},
        {
            "protein_residue_index": 2,
            "standard_summary_excluded": 0,
            "standard_summary_exclusion_reason": None,
        },
    ],
)
def test_observation_rejects_inconsistent_linkage_and_exact_exclusion(changes):
    with pytest.raises(ProteinGlycanContactComputationError):
        replace(basic_observation(), **changes)


def test_result_rejects_wrong_excluded_count():
    result = compute_protein_glycan_contacts(basic_frame())
    for count in (0, 2):
        with pytest.raises(
            ProteinGlycanContactComputationError, match="excluded_contact_count"
        ):
            replace(result, excluded_contact_count=count)


def test_result_requires_sorted_unique_identities_and_plausible_counts():
    contact = basic_observation()
    noncarrier = replace(
        contact,
        protein_residue_index=2,
        standard_summary_excluded=False,
        standard_summary_exclusion_reason=None,
    )
    another_glycan = replace(contact, glycan_partner_id="glycan_0002")
    for contacts, excluded in (
        ((contact, contact), 2),
        ((noncarrier, contact), 1),
        ((another_glycan, contact), 2),
    ):
        with pytest.raises(
            ProteinGlycanContactComputationError, match="unique and ordered"
        ):
            ProteinGlycanContactFrameResult(7, 12.5, 2, 1, 2, 2, excluded, contacts)
    for proteins, glycans, contacts, excluded in (
        (1, 2, (contact, noncarrier), 1),
        (2, 1, (contact, another_glycan), 2),
    ):
        with pytest.raises(
            ProteinGlycanContactComputationError,
            match="must not exceed declared counts",
        ):
            ProteinGlycanContactFrameResult(
                7, 12.5, proteins, glycans, 2, 2, excluded, contacts
            )


def test_carrier_absent_from_protein_set_fails():
    frame = basic_frame()
    topology = replace(
        frame.topology,
        residues=(
            frame.topology.residues[0],
            residue(2, (99,)),
            frame.topology.residues[1],
        ),
    )
    with pytest.raises(
        ProteinGlycanContactComputationError, match="carrier must belong"
    ):
        replace(frame, topology=topology, protein_residue_indexes=(2,))


def test_catalog_carrier_missing_from_topology_fails():
    frame = basic_frame()
    partner = replace(frame.partner_catalog.partners[0], carrier_residue_index=99)
    with pytest.raises(
        ProteinGlycanContactComputationError, match="carrier must exist"
    ):
        replace(frame, partner_catalog=MolecularPartnerCatalog((partner,)))


@pytest.mark.parametrize("connectivity", ["available", "unavailable"])
def test_topology_linkage_requires_accepted_bond_still_present(connectivity):
    frame = basic_frame()
    with pytest.raises(
        ProteinGlycanContactComputationError, match="accepted carrier bond"
    ):
        replace(
            frame,
            topology=replace(
                frame.topology, bonds=(), connectivity_status=connectivity
            ),
        )


def test_individually_valid_bond_to_wrong_carrier_cannot_pass_frame_validation():
    frame = basic_frame()
    topology = replace(
        frame.topology,
        residues=(
            frame.topology.residues[0],
            residue(2, (99,)),
            frame.topology.residues[1],
        ),
    )
    partner = replace(frame.partner_catalog.partners[0], carrier_residue_index=2)
    with pytest.raises(
        ProteinGlycanContactComputationError, match="endpoints must belong"
    ):
        replace(
            frame,
            topology=topology,
            partner_catalog=MolecularPartnerCatalog((partner,)),
            protein_residue_indexes=(1, 2),
        )


def test_first_sugar_outside_component_is_rejected_by_authoritative_model():
    partner = basic_frame().partner_catalog.partners[0]
    with pytest.raises(ValueError, match="first sugar must belong"):
        replace(partner, first_sugar_residue_index=99)


def test_external_linkage_cannot_bypass_new_authoritative_topology():
    frame = external_frame()
    with pytest.raises(
        ProteinGlycanContactComputationError, match="unavailable connectivity"
    ):
        replace(
            frame, topology=replace(frame.topology, connectivity_status="available")
        )


def test_explicit_topology_linkage_retains_accepted_bond_without_regrouping():
    frame = make_frame(
        (residue(1, (0, 1)), residue(20, (2,)), residue(21, (3,))),
        (
            coordinate(0, 0.0),
            coordinate(1, 20.0),
            coordinate(2, 10.0),
            coordinate(3, 4.0),
        ),
        glycans=(20, 21),
        bonds=(SourceTopologyBond(0, 2), SourceTopologyBond(1, 2)),
        explicit=(
            ExplicitMolecularPartnerDefinition(
                "source-glycan", "glycan", "GLYCAN-X", (20, 21), 1, 20
            ),
        ),
    )
    # Accepted explicit grouping needs no internal sugar bond. Stage 29.A selects
    # the lowest canonical carrier bond when the specified residue pair has several.
    contact = compute_protein_glycan_contacts(frame).contacts[0]
    assert (
        contact.glycan_partner_id,
        contact.glycan_component_residue_indexes,
        contact.minimum_distance_A,
    ) == ("source-glycan", (20, 21), 4.0)
    assert (contact.carrier_link_atom_index, contact.first_sugar_link_atom_index) == (
        0,
        2,
    )


def test_unrepresentable_minimum_fails_with_portable_public_error():
    frame = basic_frame(1e308)
    frame = replace(
        frame, atom_coordinates=(coordinate(0, -1e308),) + frame.atom_coordinates[1:]
    )
    with pytest.raises(
        ProteinGlycanContactComputationError,
        match="computed minimum_distance_A must be a finite number",
    ):
        compute_protein_glycan_contacts(frame)


def test_errors_do_not_echo_supplied_metadata_or_paths():
    frame = basic_frame()
    partner = frame.partner_catalog.partners[0]
    messages = []
    for text in ("/private/input/topology", "another-source"):
        catalog = MolecularPartnerCatalog(
            (
                replace(
                    partner,
                    components=(replace(partner.components[0], residue_id=text),),
                ),
            )
        )
        with pytest.raises(ProteinGlycanContactComputationError) as error:
            replace(frame, partner_catalog=catalog)
        assert text not in str(error.value)
        messages.append(str(error.value))
    assert messages == ["partner component source evidence must match topology"] * 2


def test_purity_import_boundary_and_absence_of_condition_canonical_or_summary_fields():
    tree = ast.parse(inspect.getsource(api))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {
        "dataclasses",
        "itertools",
        "math",
        "mania.preprocessing.molecular_partner_entities",
        "mania.preprocessing.protein_lipid_contacts",
    }
    forbidden = {
        "open",
        "eval",
        "exec",
        "__import__",
        "iter_frames",
        "Universe",
        "minimum_image",
        "unwrap",
        "center",
        "compact",
        "system",
        "Popen",
        "now",
        "time",
        "identify_molecular_partners",
        "_connected_groups",
        "compute_contact_episodes",
        "aggregate_protein_edge_windows",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden
    for model in (
        SourceAtomFrameCoordinate,
        ProteinGlycanContactFrameInput,
        ProteinGlycanContactObservation,
        ProteinGlycanContactFrameResult,
    ):
        assert not {f.name for f in fields(model)} & {
            "condition",
            "dataset_id",
            "trajectory_id",
            "replica_id",
            "box",
            "dimensions",
            "canonical_residue_id",
            "canonical_residue_index",
            "occupancy",
            "episodes",
            "lifetime",
            "distance_mean_A",
            "distance_min_A",
            "windows",
        }


def test_compute_needs_no_filesystem_clock_subprocess_or_identification(monkeypatch):
    import builtins
    import subprocess
    import time

    import mania.preprocessing.molecular_partner_identification as identification

    frame = basic_frame()

    def forbidden(*args, **kwargs):
        pytest.fail("pure geometry attempted an external operation")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(Path, "open", forbidden)
        guard.setattr(subprocess, "run", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(time, "time", forbidden)
        guard.setattr(identification, "identify_molecular_partners", forbidden)
        result = compute_protein_glycan_contacts(frame)
    assert result.contact_count == 1
