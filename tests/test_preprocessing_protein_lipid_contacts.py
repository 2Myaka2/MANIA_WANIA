import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from math import nextafter
from pathlib import Path

import pytest

import mania.preprocessing.protein_lipid_contacts as api
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
from mania.preprocessing.protein_lipid_contacts import (
    PROTEIN_LIPID_CONTACT_CUTOFF_A,
    PROTEIN_LIPID_CONTACT_KIND,
    PROTEIN_LIPID_CONTACT_SCHEMA_VERSION,
    PROTEIN_LIPID_DISTANCE_DEFINITION,
    PROTEIN_LIPID_DISTANCE_UNIT,
    ProteinLipidContactComputationError,
    ProteinLipidContactFrameInput,
    ProteinLipidContactFrameResult,
    ProteinLipidContactObservation,
    SourceAtomFrameCoordinate,
    compute_protein_lipid_contacts,
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
    lipid_indexes=(10,),
    bonds=(),
    glycan_indexes=(),
    explicit=(),
    connectivity="available",
):
    topology = MolecularPartnerTopology(residues, bonds, connectivity)
    classifications = tuple(
        MolecularPartnerComponentClassification(i, "lipid", "LIPID-X")
        for i in lipid_indexes
    ) + tuple(
        MolecularPartnerComponentClassification(i, "glycan", "GLYCAN-X")
        for i in glycan_indexes
    )
    catalog = identify_molecular_partners(
        topology,
        protein_residue_indexes=proteins,
        classifications=classifications,
        explicit_partners=explicit,
    )
    return ProteinLipidContactFrameInput(
        7, 12.5, topology, catalog, proteins, coordinates
    )


def basic_frame(distance=5.0):
    return make_frame(
        (residue(1, (0, 1)), residue(10, (2, 3))),
        (
            coordinate(0, 0.0),
            coordinate(1, 100.0, hydrogen=True),
            coordinate(2, distance),
            coordinate(3, 100.1, hydrogen=True),
        ),
    )


def basic_observation():
    return compute_protein_lipid_contacts(basic_frame()).contacts[0]


def multi_frame(nearest=16.0):
    return make_frame(
        (residue(1, (0, 1)), residue(10, (2,)), residue(11, (3,))),
        (
            coordinate(0, 0.0),
            coordinate(1, 10.0),
            coordinate(2, 20.0),
            coordinate(3, nearest),
        ),
        lipid_indexes=(10, 11),
        bonds=(SourceTopologyBond(2, 3),),
    )


def mixed_frame():
    return make_frame(
        (residue(1, (0,)), residue(10, (1,)), residue(20, (2,))),
        (coordinate(0, 0.0), coordinate(1, 5.0)),
        glycan_indexes=(20,),
        bonds=(SourceTopologyBond(0, 2),),
    )


def test_public_constants_and_api_are_exact():
    assert PROTEIN_LIPID_CONTACT_CUTOFF_A == 6.0
    assert PROTEIN_LIPID_CONTACT_KIND == "mania_protein_lipid_contacts"
    assert PROTEIN_LIPID_CONTACT_SCHEMA_VERSION == "mania.protein_lipid_contacts.v0.1"
    assert PROTEIN_LIPID_DISTANCE_UNIT == "angstrom"
    assert PROTEIN_LIPID_DISTANCE_DEFINITION == "minimum_heavy_atom_distance"
    assert api.__all__ == [
        "PROTEIN_LIPID_CONTACT_CUTOFF_A",
        "PROTEIN_LIPID_CONTACT_KIND",
        "PROTEIN_LIPID_CONTACT_SCHEMA_VERSION",
        "PROTEIN_LIPID_DISTANCE_DEFINITION",
        "PROTEIN_LIPID_DISTANCE_UNIT",
        "ProteinLipidContactComputationError",
        "ProteinLipidContactFrameInput",
        "ProteinLipidContactFrameResult",
        "ProteinLipidContactObservation",
        "SourceAtomFrameCoordinate",
        "compute_protein_lipid_contacts",
    ]
    assert issubclass(ProteinLipidContactComputationError, ValueError)
    assert list(inspect.signature(compute_protein_lipid_contacts).parameters) == [
        "frame"
    ]


@pytest.mark.parametrize(
    "model",
    [
        coordinate(0, 0.0),
        basic_frame(),
        basic_observation(),
        compute_protein_lipid_contacts(basic_frame()),
    ],
)
def test_all_public_models_are_frozen(model):
    for field in fields(model):
        with pytest.raises(FrozenInstanceError):
            setattr(model, field.name, None)


def test_exact_fields_key_order_and_json_serialization():
    frame = basic_frame()
    atom = frame.atom_coordinates[0]
    result = compute_protein_lipid_contacts(frame)
    observation = result.contacts[0]
    atom_keys = ["atom_index", "x_A", "y_A", "z_A", "is_hydrogen"]
    observation_keys = [
        "frame_index",
        "time_ps",
        "protein_residue_index",
        "protein_residue_id",
        "protein_resname",
        "protein_segid",
        "lipid_partner_id",
        "lipid_partner_name",
        "lipid_component_residue_indexes",
        "minimum_distance_A",
    ]
    result_keys = [
        "schema_version",
        "kind",
        "cutoff_A",
        "distance_unit",
        "distance_definition",
        "frame_index",
        "time_ps",
        "protein_residue_count",
        "lipid_partner_count",
        "evaluated_pair_count",
        "contact_count",
        "contacts",
    ]
    assert [f.name for f in fields(frame)] == [
        "frame_index",
        "time_ps",
        "topology",
        "partner_catalog",
        "protein_residue_indexes",
        "atom_coordinates",
    ]
    for model, keys in (
        (atom, atom_keys),
        (observation, observation_keys),
        (result, result_keys),
    ):
        assert [f.name for f in fields(model)] == keys
        assert list(model.to_dict()) == keys
        encoded = json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":"))
        assert json.loads(encoded) == model.to_dict()
        assert encoded == json.dumps(
            model.to_dict(), allow_nan=False, separators=(",", ":")
        )
    for name in result_keys[:5]:
        assert name not in inspect.signature(ProteinLipidContactFrameResult).parameters
    assert result.to_dict() == {
        "schema_version": "mania.protein_lipid_contacts.v0.1",
        "kind": "mania_protein_lipid_contacts",
        "cutoff_A": 6.0,
        "distance_unit": "angstrom",
        "distance_definition": "minimum_heavy_atom_distance",
        "frame_index": 7,
        "time_ps": 12.5,
        "protein_residue_count": 1,
        "lipid_partner_count": 1,
        "evaluated_pair_count": 1,
        "contact_count": 1,
        "contacts": [
            {
                "frame_index": 7,
                "time_ps": 12.5,
                "protein_residue_index": 1,
                "protein_residue_id": "source 7",
                "protein_resname": "SOURCE-X",
                "protein_segid": None,
                "lipid_partner_id": "lipid_0001",
                "lipid_partner_name": "LIPID-X",
                "lipid_component_residue_indexes": [10],
                "minimum_distance_A": 5.0,
            }
        ],
    }


def test_computation_is_repeatable_and_does_not_mutate_input_or_share_output_lists():
    frame = multi_frame()
    before = (
        frame.topology.to_dict(),
        frame.partner_catalog.to_dict(),
        frame.atom_coordinates,
    )
    outputs = [
        json.dumps(
            compute_protein_lipid_contacts(frame).to_dict(),
            allow_nan=False,
            separators=(",", ":"),
        )
        for _ in range(3)
    ]
    assert outputs[0] == outputs[1] == outputs[2]
    result = compute_protein_lipid_contacts(frame)
    result.to_dict()["contacts"][0]["lipid_component_residue_indexes"].append(99)
    assert result.contacts[0].lipid_component_residue_indexes == (10, 11)
    assert before == (
        frame.topology.to_dict(),
        frame.partner_catalog.to_dict(),
        frame.atom_coordinates,
    )


@pytest.mark.parametrize(
    ("distance", "count"),
    [
        (0.0, 1),
        (5.0, 1),
        (6.0, 1),
        (6.000001, 0),
        (nextafter(6.0, float("inf")), 0),
    ],
)
def test_inclusive_fixed_cutoff_without_tolerance(distance, count):
    result = compute_protein_lipid_contacts(basic_frame(distance))
    assert (
        result.protein_residue_count,
        result.lipid_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
    ) == (1, 1, 1, count)
    if count:
        assert result.contacts[0].minimum_distance_A == distance
    else:
        assert result.contacts == ()
        assert result.to_dict()["contacts"] == []


def test_hydrogen_smoke_then_move_only_heavy_atom_into_contact():
    frame = basic_frame(10.0)
    assert compute_protein_lipid_contacts(frame).contact_count == 0
    moved = replace(
        frame,
        atom_coordinates=tuple(
            replace(c, x_A=6.0) if c.atom_index == 2 else c
            for c in frame.atom_coordinates
        ),
    )
    assert compute_protein_lipid_contacts(moved).contacts[0].minimum_distance_A == 6.0
    print(
        "Hydrogen smoke: H-H 0.1 Å, heavy-heavy 10.0 Å -> 0 contacts; "
        "heavy-heavy 6.0 Å -> 1"
    )


def test_multi_residue_scientific_smoke_includes_last_component_and_all_pairs():
    frame = multi_frame()
    partner = frame.partner_catalog.partners[0]
    assert partner.component_residue_indexes == (10, 11)
    result = compute_protein_lipid_contacts(frame)
    assert result.evaluated_pair_count == result.contact_count == 1
    observation = result.contacts[0]
    assert observation.minimum_distance_A == 6.0
    assert observation.lipid_partner_id == partner.partner_id
    assert observation.lipid_partner_name == partner.partner_name
    assert observation.lipid_component_residue_indexes == (10, 11)
    assert compute_protein_lipid_contacts(multi_frame(16.000001)).contacts == ()
    print("Multi-residue smoke: minimum 6.0 Å -> 1 contact; minimum 6.000001 Å -> 0")


def test_true_minimum_is_neither_first_contact_nor_average_nor_representative():
    frame = make_frame(
        (residue(1, (0, 1)), residue(10, (2, 3)), residue(11, (4, 5))),
        tuple(
            coordinate(i, x) for i, x in enumerate((0.0, 10.0, 5.5, 30.0, 20.0, 13.0))
        ),
        lipid_indexes=(10, 11),
        bonds=(SourceTopologyBond(3, 4),),
    )
    (observation,) = compute_protein_lipid_contacts(frame).contacts
    assert observation.minimum_distance_A == 3.0
    assert observation.lipid_component_residue_indexes == (10, 11)


def test_distance_uses_all_three_cartesian_axes_in_angstrom():
    frame = make_frame(
        (residue(1, (0,)), residue(10, (1,))),
        (coordinate(0, -1.0, -2.0, -3.0), coordinate(1, 0.0, 0.0, -1.0)),
    )
    assert compute_protein_lipid_contacts(frame).contacts[0].minimum_distance_A == 3.0


def test_no_pbc_smoke_uses_supplied_coordinates_without_wrapping():
    frame = make_frame(
        (residue(1, (0,)), residue(10, (1,))),
        (coordinate(0, 0.1), coordinate(1, 9.9)),
    )
    assert frame.atom_coordinates[1].x_A - frame.atom_coordinates[0].x_A == 9.8
    assert compute_protein_lipid_contacts(frame).contacts == ()
    assert "box" not in inspect.signature(ProteinLipidContactFrameInput).parameters
    print("No-PBC smoke: Cartesian distance 9.8 Å -> 0 contacts; no box input")


def test_disconnected_same_name_lipids_remain_distinct_and_order_by_id_not_distance():
    frame = make_frame(
        (residue(1, (0,)), residue(10, (1,)), residue(11, (2,))),
        (coordinate(0, 0.0), coordinate(1, 5.0), coordinate(2, 1.0)),
        lipid_indexes=(10, 11),
    )
    result = compute_protein_lipid_contacts(frame)
    assert (
        result.contact_count
        == result.lipid_partner_count
        == result.evaluated_pair_count
        == 2
    )
    assert [c.lipid_partner_name for c in result.contacts] == ["LIPID-X", "LIPID-X"]
    assert [c.lipid_partner_id for c in result.contacts] == ["lipid_0001", "lipid_0002"]
    assert [c.minimum_distance_A for c in result.contacts] == [5.0, 1.0]


def test_multiple_proteins_evaluate_independently_and_sort_protein_then_partner():
    frame = make_frame(
        (
            residue(1, (0,)),
            residue(2, (1,)),
            residue(3, (2,)),
            residue(10, (3,)),
            residue(11, (4,)),
        ),
        tuple(coordinate(i, x) for i, x in enumerate((0.0, 10.0, 100.0, 5.0, 6.0))),
        proteins=(1, 2, 3),
        lipid_indexes=(10, 11),
    )
    result = compute_protein_lipid_contacts(frame)
    assert (
        result.protein_residue_count,
        result.lipid_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
    ) == (3, 2, 6, 4)
    assert [(c.protein_residue_index, c.lipid_partner_id) for c in result.contacts] == [
        (1, "lipid_0001"),
        (1, "lipid_0002"),
        (2, "lipid_0001"),
        (2, "lipid_0002"),
    ]
    assert [c.minimum_distance_A for c in result.contacts] == [5.0, 6.0, 5.0, 4.0]


def test_catalog_may_include_glycan_without_its_coordinates():
    frame = mixed_frame()
    assert frame.partner_catalog.glycan_partner_count == 1
    assert len(frame.atom_coordinates) == 2
    result = compute_protein_lipid_contacts(frame)
    assert (
        result.lipid_partner_count
        == result.evaluated_pair_count
        == result.contact_count
        == 1
    )
    supplied_glycan = replace(
        frame, atom_coordinates=frame.atom_coordinates + (coordinate(2, 0.0),)
    )
    assert compute_protein_lipid_contacts(supplied_glycan) == result


@pytest.mark.parametrize("glycans", [False, True])
def test_no_lipids_is_valid_with_empty_or_glycan_only_catalog(glycans):
    frame = mixed_frame()
    frame = replace(
        frame,
        partner_catalog=MolecularPartnerCatalog(
            tuple(
                p
                for p in frame.partner_catalog.partners
                if glycans and p.partner_kind == "glycan"
            )
        ),
        atom_coordinates=(frame.atom_coordinates[0],),
    )
    result = compute_protein_lipid_contacts(frame)
    assert (
        result.protein_residue_count,
        result.lipid_partner_count,
        result.evaluated_pair_count,
        result.contact_count,
        result.contacts,
    ) == (1, 0, 0, 0, ())


def test_unrelated_atoms_are_optional_and_ignored():
    frame = basic_frame()
    topology = replace(
        frame.topology, residues=frame.topology.residues + (residue(90, (99,)),)
    )
    without = replace(frame, topology=topology)
    with_extra = replace(
        without, atom_coordinates=frame.atom_coordinates + (coordinate(99, 0.0),)
    )
    assert compute_protein_lipid_contacts(without) == compute_protein_lipid_contacts(
        with_extra
    )


@pytest.mark.parametrize("resid", [None, -5, 0, "", " source 7 "])
@pytest.mark.parametrize("segid", [None, "source-chain"])
def test_source_identity_copied_verbatim_without_canonical_or_name_inference(
    resid, segid
):
    frame = make_frame(
        (
            residue(1, (0,), resid=resid, resname="H-LIPID-looking", segid=segid),
            residue(10, (1,), resname="PROTEIN-looking"),
        ),
        (coordinate(0, 0.0), coordinate(1, 5.0)),
    )
    (observation,) = compute_protein_lipid_contacts(frame).contacts
    assert observation.protein_residue_index == 1
    assert observation.protein_residue_id == resid
    assert observation.protein_resname == "H-LIPID-looking"
    assert observation.protein_segid == segid
    assert observation.lipid_partner_name == "LIPID-X"


def test_explicit_partner_identity_and_membership_are_authoritative_without_bonds():
    frame = make_frame(
        (residue(1, (0,)), residue(10, (1,)), residue(11, (2,))),
        (coordinate(0, 0.0), coordinate(1, 100.0), coordinate(2, 5.0)),
        lipid_indexes=(10, 11),
        connectivity="unavailable",
        explicit=(
            ExplicitMolecularPartnerDefinition(
                "supplied-identity", "lipid", "LIPID-X", (10, 11)
            ),
        ),
    )
    (observation,) = compute_protein_lipid_contacts(frame).contacts
    assert (
        observation.lipid_partner_id,
        observation.lipid_component_residue_indexes,
    ) == (
        "supplied-identity",
        (10, 11),
    )


@pytest.mark.parametrize("time", [None, 0.0, 999999.0])
def test_time_is_informational_and_does_not_affect_contact_or_partner_identity(time):
    result = compute_protein_lipid_contacts(
        replace(basic_frame(), frame_index=999, time_ps=time)
    )
    assert result.frame_index == result.contacts[0].frame_index == 999
    assert result.time_ps == result.contacts[0].time_ps == time
    assert result.contacts[0].lipid_partner_id == "lipid_0001"
    assert result.contacts[0].minimum_distance_A == 5.0


@pytest.mark.parametrize("bad", [-1, True, 1.0, "0", None])
def test_coordinate_rejects_invalid_atom_indexes(bad):
    with pytest.raises(ProteinLipidContactComputationError, match="atom_index"):
        coordinate(bad, 0.0)


@pytest.mark.parametrize("axis", ["x_A", "y_A", "z_A"])
@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), -float("inf"), True, "0", None, 10**400]
)
def test_coordinates_require_finite_numbers(axis, bad):
    with pytest.raises(ProteinLipidContactComputationError, match=axis):
        replace(coordinate(0, 0.0), **{axis: bad})


@pytest.mark.parametrize("bad", [None, 0, 1, "False", 0.0])
def test_hydrogen_flag_requires_exact_bool(bad):
    with pytest.raises(
        ProteinLipidContactComputationError, match="is_hydrogen must be exact bool"
    ):
        coordinate(0, 0.0, hydrogen=bad)


@pytest.mark.parametrize(
    "model",
    [basic_frame(), basic_observation(), compute_protein_lipid_contacts(basic_frame())],
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
    with pytest.raises(ProteinLipidContactComputationError, match=field):
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
    with pytest.raises(ProteinLipidContactComputationError, match=message):
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
            ProteinLipidContactComputationError, match="exact MolecularPartnerTopology"
        ):
            replace(frame, topology=bad)
    for bad in (None, object(), CatalogSubclass(frame.partner_catalog.partners)):
        with pytest.raises(
            ProteinLipidContactComputationError, match="exact MolecularPartnerCatalog"
        ):
            replace(frame, partner_catalog=bad)
    for bad in ([], (object(),), (CoordinateSubclass(0, 0.0, 0.0, 0.0, False),)):
        with pytest.raises(
            ProteinLipidContactComputationError, match="exact SourceAtomFrameCoordinate"
        ):
            replace(frame, atom_coordinates=bad)
    with pytest.raises(
        ProteinLipidContactComputationError, match="exact ProteinLipidContactFrameInput"
    ):
        compute_protein_lipid_contacts(object())


@pytest.mark.parametrize("missing_atom", [0, 1, 2, 3])
def test_every_required_atom_coordinate_is_mandatory_including_hydrogens(missing_atom):
    frame = basic_frame()
    with pytest.raises(
        ProteinLipidContactComputationError,
        match="every protein and lipid partner atom",
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
        "empty": ((), "every protein and lipid partner atom"),
    }[case]
    with pytest.raises(ProteinLipidContactComputationError, match=message):
        replace(frame, atom_coordinates=coordinates)


@pytest.mark.parametrize(
    ("atoms", "message"), [((0, 1), "protein residue"), ((2, 3), "lipid partner")]
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
        ProteinLipidContactComputationError,
        match=message + " must have at least one heavy atom",
    ):
        compute_protein_lipid_contacts(frame)


def test_no_lipids_does_not_excuse_an_invalid_protein_heavy_set():
    frame = basic_frame()
    frame = replace(
        frame,
        partner_catalog=MolecularPartnerCatalog(()),
        atom_coordinates=tuple(
            replace(c, is_hydrogen=True) for c in frame.atom_coordinates
        ),
    )
    with pytest.raises(
        ProteinLipidContactComputationError,
        match="protein residue must have at least one heavy atom",
    ):
        compute_protein_lipid_contacts(frame)


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
        ProteinLipidContactComputationError, match="source evidence must match topology"
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
        ProteinLipidContactComputationError,
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
        ProteinLipidContactComputationError, match="atom union must match topology"
    ):
        replace(frame, topology=topology)


@pytest.mark.parametrize("indexes", [(1, 10), (1, 20)])
def test_protein_cannot_overlap_any_partner_component(indexes):
    with pytest.raises(
        ProteinLipidContactComputationError, match="must not overlap protein residues"
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
        ("lipid_partner_id", ""),
        ("lipid_partner_id", " id"),
        ("lipid_partner_id", None),
        ("lipid_partner_name", ""),
        ("lipid_partner_name", "X "),
        ("lipid_partner_name", 3),
        ("lipid_component_residue_indexes", ()),
        ("lipid_component_residue_indexes", [10]),
        ("lipid_component_residue_indexes", (11, 10)),
        ("lipid_component_residue_indexes", (10, 10)),
        ("lipid_component_residue_indexes", (-1,)),
        ("lipid_component_residue_indexes", (False,)),
        ("lipid_component_residue_indexes", (10.0,)),
        ("lipid_component_residue_indexes", (1, 10)),
        ("minimum_distance_A", -1.0),
        ("minimum_distance_A", 6.000001),
        ("minimum_distance_A", float("nan")),
        ("minimum_distance_A", float("inf")),
        ("minimum_distance_A", True),
        ("minimum_distance_A", "5.0"),
    ],
)
def test_observation_rejects_invalid_source_identity_membership_or_distance(field, bad):
    with pytest.raises(ProteinLipidContactComputationError):
        replace(basic_observation(), **{field: bad})


@pytest.mark.parametrize(
    "field",
    [
        "protein_residue_count",
        "lipid_partner_count",
        "evaluated_pair_count",
        "contact_count",
    ],
)
@pytest.mark.parametrize("bad", [-1, True, 1.0])
def test_result_counts_require_nonnegative_integers(field, bad):
    with pytest.raises(ProteinLipidContactComputationError, match=field):
        replace(compute_protein_lipid_contacts(basic_frame()), **{field: bad})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"protein_residue_count": 0}, "must be positive"),
        ({"evaluated_pair_count": 2}, "must equal protein_residue_count"),
        ({"contact_count": 0}, "must equal contacts length"),
        (
            {"lipid_partner_count": 0, "evaluated_pair_count": 0},
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
    with pytest.raises(ProteinLipidContactComputationError, match=message):
        replace(compute_protein_lipid_contacts(basic_frame()), **changes)


def test_result_requires_unique_sorted_contact_identities_and_plausible_counts():
    observation = basic_observation()
    second_protein = replace(observation, protein_residue_index=2)
    second_lipid = replace(
        observation,
        lipid_partner_id="lipid_0002",
        lipid_component_residue_indexes=(11,),
    )
    for contacts in ((observation, observation), (second_protein, observation)):
        with pytest.raises(
            ProteinLipidContactComputationError, match="unique and ordered"
        ):
            ProteinLipidContactFrameResult(7, 12.5, 2, 1, 2, 2, contacts)
    with pytest.raises(ProteinLipidContactComputationError, match="unique and ordered"):
        ProteinLipidContactFrameResult(7, 12.5, 1, 2, 2, 2, (second_lipid, observation))
    for proteins, lipids, contacts in (
        (1, 2, (observation, second_protein)),
        (2, 1, (observation, second_lipid)),
    ):
        with pytest.raises(
            ProteinLipidContactComputationError, match="must not exceed declared counts"
        ):
            ProteinLipidContactFrameResult(7, 12.5, proteins, lipids, 2, 2, contacts)


def test_unrepresentable_minimum_distance_fails_with_public_portable_error():
    frame = make_frame(
        (residue(1, (0,)), residue(10, (1,))),
        (coordinate(0, -1e308), coordinate(1, 1e308)),
    )
    with pytest.raises(
        ProteinLipidContactComputationError,
        match="computed minimum_distance_A must be a finite number",
    ):
        compute_protein_lipid_contacts(frame)


def test_errors_do_not_echo_supplied_metadata_or_paths():
    frame = basic_frame()
    (partner,) = frame.partner_catalog.partners
    errors = []
    for text in ("/private/input/topology", "another-source"):
        catalog = MolecularPartnerCatalog(
            (
                replace(
                    partner,
                    components=(replace(partner.components[0], residue_id=text),),
                ),
            )
        )
        with pytest.raises(ProteinLipidContactComputationError) as error:
            replace(frame, partner_catalog=catalog)
        assert text not in str(error.value)
        errors.append(str(error.value))
    assert errors == ["partner component source evidence must match topology"] * 2


def test_pure_geometry_imports_and_calls_have_no_runtime_or_integration_dependencies():
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
    }
    forbidden_calls = {
        "open",
        "eval",
        "exec",
        "__import__",
        "getattr_box",
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
                assert node.func.id not in forbidden_calls
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
    for model in (
        SourceAtomFrameCoordinate,
        ProteinLipidContactFrameInput,
        ProteinLipidContactObservation,
        ProteinLipidContactFrameResult,
    ):
        assert not {f.name for f in fields(model)} & {
            "condition",
            "dataset_id",
            "trajectory_id",
            "replica_id",
            "box",
            "canonical_residue_id",
            "canonical_residue_index",
            "occupancy",
            "episodes",
            "lifetime",
            "distance_mean_A",
            "distance_min_A",
        }


def test_compute_needs_no_filesystem_clock_subprocess_or_classification(monkeypatch):
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
        result = compute_protein_lipid_contacts(frame)
    assert result.contact_count == 1
