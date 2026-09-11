import json
from dataclasses import FrozenInstanceError, fields, replace
from typing import get_args

import pytest

from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition,
    IdentifiedMolecularPartner,
    MolecularPartnerCatalog,
    MolecularPartnerComponentClassification,
    MolecularPartnerIdentificationMode,
    MolecularPartnerKind,
    MolecularPartnerLinkageEvidence,
    MolecularPartnerTopology,
    SourceTopologyBond,
    SourceTopologyResidue,
    TopologyConnectivityStatus,
)


def residue(index=10, atoms=(4, 7)):
    return SourceTopologyResidue(index, 1, "SOURCE-X", None, atoms)


def lipid():
    return IdentifiedMolecularPartner(
        "lipid_0001",
        "lipid",
        "LIPID-X",
        "topology_connectivity",
        (10,),
        (4, 7),
        (residue(),),
        None,
        None,
        None,
    )


def glycan():
    return IdentifiedMolecularPartner(
        "glycan_0001",
        "glycan",
        "GLYCAN-X",
        "topology_connectivity",
        (20, 21),
        (2, 3, 8),
        (residue(20, (2, 8)), residue(21, (3,))),
        0,
        20,
        SourceTopologyBond(0, 2),
        "topology_connectivity",
    )


def test_public_literals_exclude_heuristic_modes():
    assert get_args(MolecularPartnerKind) == ("lipid", "glycan")
    assert get_args(MolecularPartnerIdentificationMode) == (
        "topology_connectivity",
        "explicit_mapping",
    )
    assert get_args(MolecularPartnerLinkageEvidence) == (
        "topology_connectivity",
        "external_metadata",
    )
    assert get_args(TopologyConnectivityStatus) == ("available", "unavailable")


@pytest.mark.parametrize(
    "model",
    [
        residue(),
        SourceTopologyBond(7, 4),
        MolecularPartnerTopology((residue(),), (), "available"),
        MolecularPartnerComponentClassification(10, "lipid", "LIPID-X"),
        ExplicitMolecularPartnerDefinition("supplied", "lipid", "LIPID-X", (10,)),
        lipid(),
        glycan(),
        MolecularPartnerCatalog((lipid(), glycan())),
    ],
)
def test_models_are_frozen_with_deterministic_json(model):
    with pytest.raises(FrozenInstanceError):
        setattr(model, fields(model)[0].name, None)
    first = json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":"))
    assert first == json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":"))
    assert json.loads(first) == model.to_dict()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("residue_index", -1),
        ("residue_index", True),
        ("residue_index", 1.0),
        ("residue_id", False),
        ("residue_id", 1.5),
        ("residue_id", []),
        ("resname", ""),
        ("resname", " X"),
        ("resname", "X "),
        ("resname", None),
        ("segid", ""),
        ("segid", " S"),
        ("segid", 3),
        ("atom_indexes", ()),
        ("atom_indexes", [4, 7]),
        ("atom_indexes", (7, 4)),
        ("atom_indexes", (4, 4)),
        ("atom_indexes", (-1, 4)),
        ("atom_indexes", (False, 4)),
        ("atom_indexes", (1.0, 4)),
    ],
)
def test_source_residue_rejects_invalid_identity(field, value):
    with pytest.raises(ValueError):
        replace(residue(), **{field: value})


@pytest.mark.parametrize("resid", [None, -1, 0, "", "source 1"])
def test_source_resid_is_retained_without_global_identity_assumptions(resid):
    record = replace(residue(), residue_id=resid, segid="source-segment")
    assert record.to_dict()["residue_id"] == resid
    assert record.to_dict()["segid"] == "source-segment"
    topology = MolecularPartnerTopology(
        (record, replace(record, residue_index=11, atom_indexes=(9,))), (), "available"
    )
    assert len(topology.residues) == 2


def test_bond_canonicalizes_orientation_only():
    assert SourceTopologyBond(7, 4) == SourceTopologyBond(4, 7)
    assert SourceTopologyBond(7, 4).to_dict() == {"atom_index_a": 4, "atom_index_b": 7}


@pytest.mark.parametrize(
    "endpoints", [(-1, 3), (True, 3), (2, False), (2, 2), (2, 3.0)]
)
def test_bond_rejects_invalid_endpoints(endpoints):
    with pytest.raises(ValueError):
        SourceTopologyBond(*endpoints)


@pytest.mark.parametrize(
    ("residues", "bonds", "status", "error"),
    [
        ((residue(), residue(10, (8,))), (), "available", "strictly increasing"),
        ((residue(11, (8,)), residue()), (), "available", "strictly increasing"),
        ((residue(), residue(11, (7, 8))), (), "available", "atom membership"),
        ((residue(),), (SourceTopologyBond(4, 9),), "available", "endpoint"),
        (
            (residue(),),
            (SourceTopologyBond(4, 7), SourceTopologyBond(7, 4)),
            "available",
            "duplicate",
        ),
        (
            (residue(10, (1, 2, 3)),),
            (SourceTopologyBond(2, 3), SourceTopologyBond(1, 2)),
            "available",
            "ordered",
        ),
        ((residue(),), (SourceTopologyBond(4, 7),), "unavailable", "empty bonds"),
        ((residue(),), (), "auto", "connectivity_status"),
        ([residue()], (), "available", "tuple"),
        ((residue(),), [], "available", "tuple"),
        ((object(),), (), "available", "exact SourceTopologyResidue"),
        ((residue(),), (object(),), "available", "exact SourceTopologyBond"),
    ],
)
def test_topology_requires_unique_membership_and_order(residues, bonds, status, error):
    with pytest.raises(ValueError, match=error):
        MolecularPartnerTopology(residues, bonds, status)


def test_empty_connectivity_requires_explicit_availability_declaration():
    with pytest.raises(TypeError, match="connectivity_status"):
        MolecularPartnerTopology((), ())
    available = MolecularPartnerTopology((), (), "available")
    unavailable = MolecularPartnerTopology((), (), "unavailable")
    assert available.to_dict() != unavailable.to_dict()


@pytest.mark.parametrize(
    ("index", "kind", "name"),
    [
        (-1, "lipid", "X"),
        (False, "lipid", "X"),
        (1, "protein", "X"),
        (1, "LIPID", "X"),
        (1, "glycan", ""),
        (1, "glycan", " X"),
        (1, "glycan", 3),
    ],
)
def test_classification_is_explicit_and_validated(index, kind, name):
    with pytest.raises(ValueError):
        MolecularPartnerComponentClassification(index, kind, name)


@pytest.mark.parametrize(
    "changes",
    [
        {"partner_id": ""},
        {"partner_id": " id"},
        {"partner_kind": "auto"},
        {"partner_name": "X "},
        {"component_residue_indexes": ()},
        {"component_residue_indexes": [20]},
        {"component_residue_indexes": (21, 20)},
        {"component_residue_indexes": (20, 20)},
        {"component_residue_indexes": (False, 20)},
        {"carrier_residue_index": 20, "first_sugar_residue_index": 21},
        {"carrier_residue_index": 0, "first_sugar_residue_index": 22},
        {"carrier_residue_index": 0},
        {"first_sugar_residue_index": 20},
        {"carrier_residue_index": True, "first_sugar_residue_index": 20},
        {"linkage_evidence": "guessed"},
        {"linkage_evidence": "external_metadata"},
    ],
)
def test_explicit_definition_validation(changes):
    definition = ExplicitMolecularPartnerDefinition("given", "glycan", "X", (20, 21))
    with pytest.raises(ValueError):
        replace(definition, **changes)


def test_raw_glycan_allows_absent_linkage_but_identified_glycan_does_not():
    assert ExplicitMolecularPartnerDefinition("given", "glycan", "X", (20, 21))
    with pytest.raises(ValueError, match="requires carrier"):
        replace(
            glycan(),
            carrier_residue_index=None,
            first_sugar_residue_index=None,
            carrier_link_bond=None,
            linkage_evidence=None,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"carrier_residue_index": 0, "first_sugar_residue_index": 10},
        {"linkage_evidence": "external_metadata"},
    ],
)
def test_explicit_lipid_linkage_forbidden(changes):
    with pytest.raises(ValueError):
        replace(
            ExplicitMolecularPartnerDefinition("given", "lipid", "X", (10,)), **changes
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"partner_id": " id"},
        {"partner_kind": "auto"},
        {"partner_name": ""},
        {"identification_mode": "auto"},
        {"component_residue_indexes": ()},
        {"component_residue_indexes": (11,)},
        {"component_atom_indexes": ()},
        {"component_atom_indexes": (4,)},
        {"component_atom_indexes": (4, 7, 8)},
        {"component_atom_indexes": (7, 4)},
        {"component_atom_indexes": (4, 4)},
        {"components": ()},
        {"components": [residue()]},
        {"carrier_residue_index": 0, "first_sugar_residue_index": 10},
        {"carrier_link_bond": SourceTopologyBond(0, 4)},
        {"linkage_evidence": "topology_connectivity"},
    ],
)
def test_identified_lipid_requires_exact_membership_and_no_linkage(changes):
    with pytest.raises(ValueError):
        replace(lipid(), **changes)


def test_identified_components_reject_duplicate_atom_ownership_and_wrong_order():
    with pytest.raises(ValueError, match="must not overlap"):
        replace(
            lipid(),
            component_residue_indexes=(10, 11),
            components=(residue(), residue(11, (7,))),
        )
    with pytest.raises(ValueError, match="match components exactly"):
        replace(glycan(), components=tuple(reversed(glycan().components)))


@pytest.mark.parametrize(
    "changes",
    [
        {"carrier_residue_index": 20},
        {"carrier_residue_index": False},
        {"first_sugar_residue_index": 25},
        {"carrier_link_bond": None},
        {"carrier_link_bond": object()},
        {"linkage_evidence": None},
        {"linkage_evidence": "guessed"},
        {"carrier_link_bond": SourceTopologyBond(2, 3)},
        {"carrier_link_bond": SourceTopologyBond(0, 3)},
        {"carrier_link_bond": SourceTopologyBond(0, 9)},
        {"linkage_evidence": "external_metadata"},
        {"linkage_evidence": "external_metadata", "carrier_link_bond": None},
    ],
)
def test_identified_glycan_requires_consistent_linkage(changes):
    with pytest.raises(ValueError):
        replace(glycan(), **changes)


def test_external_glycan_retains_evidence_without_invented_bond():
    partner = replace(
        glycan(),
        identification_mode="explicit_mapping",
        carrier_link_bond=None,
        linkage_evidence="external_metadata",
    )
    assert partner.to_dict()["carrier_link_bond"] is None
    assert partner.to_dict()["linkage_evidence"] == "external_metadata"
    assert partner.carrier_residue_index == 0
    assert partner.first_sugar_residue_index == 20


def test_catalog_counts_and_serialization():
    catalog = MolecularPartnerCatalog((lipid(), glycan()))
    assert (
        catalog.partner_count,
        catalog.lipid_partner_count,
        catalog.glycan_partner_count,
    ) == (2, 1, 1)
    assert catalog.to_dict() == {
        "partners": [lipid().to_dict(), glycan().to_dict()],
        "partner_count": 2,
        "lipid_partner_count": 1,
        "glycan_partner_count": 1,
    }
    assert list(lipid().to_dict()) == [
        "partner_id",
        "partner_kind",
        "partner_name",
        "identification_mode",
        "component_residue_indexes",
        "component_atom_indexes",
        "components",
        "carrier_residue_index",
        "first_sugar_residue_index",
        "carrier_link_bond",
        "linkage_evidence",
    ]


def test_empty_catalog_is_valid():
    assert MolecularPartnerCatalog(()).to_dict() == {
        "partners": [],
        "partner_count": 0,
        "lipid_partner_count": 0,
        "glycan_partner_count": 0,
    }


@pytest.mark.parametrize(
    ("partners", "error"),
    [
        ([lipid()], "tuple"),
        ((object(),), "exact IdentifiedMolecularPartner"),
        ((lipid(), replace(glycan(), partner_id="lipid_0001")), "IDs must be unique"),
        ((glycan(), lipid()), "ordered lipid then glycan"),
        (
            (replace(lipid(), partner_id="z"), replace(lipid(), partner_id="a")),
            "ordered",
        ),
        (
            (lipid(), replace(lipid(), partner_id="lipid_0002")),
            "component_residue_indexes",
        ),
        (
            (
                lipid(),
                replace(
                    lipid(),
                    partner_id="lipid_0002",
                    component_residue_indexes=(11,),
                    components=(residue(11),),
                ),
            ),
            "component_atom_indexes",
        ),
    ],
)
def test_catalog_rejects_duplicates_overlaps_and_wrong_order(partners, error):
    with pytest.raises(ValueError, match=error):
        MolecularPartnerCatalog(partners)


def test_serialization_does_not_expose_mutable_internal_membership():
    catalog = MolecularPartnerCatalog((lipid(),))
    output = catalog.to_dict()
    output["partners"][0]["components"][0]["atom_indexes"].append(99)
    assert catalog.partners[0].components[0].atom_indexes == (4, 7)
