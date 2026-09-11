import ast
import builtins
import inspect
import json
import os
import subprocess
import time
from dataclasses import fields, replace
from pathlib import Path

import pytest

from mania.preprocessing import (
    molecular_partner_entities,
    molecular_partner_identification,
)
from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition,
    IdentifiedMolecularPartner,
    MolecularPartnerComponentClassification,
    MolecularPartnerTopology,
    SourceTopologyBond,
    SourceTopologyResidue,
)
from mania.preprocessing.molecular_partner_identification import (
    MolecularPartnerIdentificationError,
    identify_molecular_partners,
)


def residue(index, atoms=None):
    return SourceTopologyResidue(
        index,
        1,
        "SOURCE-X",
        None,
        (index * 10, index * 10 + 1) if atoms is None else atoms,
    )


def topology(indexes, bonds=(), status="available"):
    return MolecularPartnerTopology(
        tuple(residue(i) for i in indexes),
        tuple(
            sorted(
                (SourceTopologyBond(*b) for b in bonds),
                key=lambda b: (b.atom_index_a, b.atom_index_b),
            )
        ),
        status,
    )


def classify(indexes, kind="lipid", name="LIPID-X"):
    return tuple(
        MolecularPartnerComponentClassification(i, kind, name) for i in indexes
    )


def identify(snapshot, classifications=(), protein=(), explicit=()):
    return identify_molecular_partners(
        snapshot,
        protein_residue_indexes=protein,
        classifications=classifications,
        explicit_partners=explicit,
    )


def glycan_topology():
    return topology((0, 1, 20, 21, 22), ((10, 200), (201, 210), (211, 220)))


def glycan_definition(**changes):
    return replace(
        ExplicitMolecularPartnerDefinition(
            "supplied-glycan",
            "glycan",
            "GLYCAN-X",
            (20, 21, 22),
            1,
            20,
        ),
        **changes,
    )


def test_unclassified_names_have_zero_classification_effect():
    snapshot = MolecularPartnerTopology(
        (
            replace(residue(0), resname="LIPID-LIKE", segid="LIPID"),
            replace(residue(1), resname="SUGAR-LIKE", segid="GLYCAN"),
        ),
        (SourceTopologyBond(1, 10),),
        "available",
    )
    assert identify(snapshot).partner_count == 0
    assert (
        identify(
            replace(snapshot, bonds=(), connectivity_status="unavailable")
        ).partner_count
        == 0
    )


@pytest.mark.parametrize("status", ["available", "unavailable"])
def test_single_residue_lipid_does_not_require_bonds(status):
    (partner,) = identify(topology((10,), status=status), classify((10,))).partners
    assert partner.partner_id == "lipid_0001"
    assert partner.component_residue_indexes == (10,)
    assert partner.component_atom_indexes == (100, 101)
    assert partner.identification_mode == "topology_connectivity"
    assert partner.carrier_residue_index is None


@pytest.mark.parametrize("status", ["available", "unavailable"])
def test_disconnected_lipids_do_not_merge_by_name_or_source_resid(status):
    catalog = identify(topology((10, 11, 12), status=status), classify((10, 11, 12)))
    assert [p.component_residue_indexes for p in catalog.partners] == [
        (10,),
        (11,),
        (12,),
    ]
    assert [p.partner_id for p in catalog.partners] == [
        "lipid_0001",
        "lipid_0002",
        "lipid_0003",
    ]


def test_connected_multiresidue_lipid_retains_exact_atom_union():
    snapshot = topology((10, 11), ((101, 110), (100, 101)))
    (partner,) = identify(snapshot, classify((10, 11))).partners
    assert partner.component_residue_indexes == (10, 11)
    assert partner.component_atom_indexes == (100, 101, 110, 111)
    assert partner.components == snapshot.residues


def test_connectivity_does_not_bridge_through_unclassified_or_other_kind_residues():
    snapshot = topology(
        (0, 10, 11, 20, 30), ((0, 200), (101, 200), (111, 201), (101, 300), (111, 301))
    )
    classifications = classify((10, 11)) + classify((20,), "glycan", "GLYCAN-X")
    catalog = identify(snapshot, classifications, (0,))
    assert [p.component_residue_indexes for p in catalog.partners] == [
        (10,),
        (11,),
        (20,),
    ]


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_conflicting_names_on_connected_same_kind_components_require_explicit_grouping(
    kind,
):
    snapshot = topology((0, 10, 11), ((0, 100), (101, 110)))
    with pytest.raises(
        MolecularPartnerIdentificationError, match="conflicting partner names"
    ):
        identify(
            snapshot, classify((10,), kind, "X") + classify((11,), kind, "Y"), (0,)
        )


def test_explicit_lipid_grouping_without_connectivity():
    definition = ExplicitMolecularPartnerDefinition(
        "caller-id", "lipid", "LIPID-X", (10, 11)
    )
    (partner,) = identify(
        topology((10, 11), status="unavailable"),
        classify((10, 11)),
        explicit=(definition,),
    ).partners
    assert partner.partner_id == "caller-id"
    assert partner.identification_mode == "explicit_mapping"
    assert partner.component_residue_indexes == (10, 11)


def test_explicit_precedence_covers_exact_components_only():
    snapshot = topology((10, 11, 12, 13), ((101, 110), (111, 120), (121, 130)))
    definition = ExplicitMolecularPartnerDefinition(
        "supplied", "lipid", "LIPID-X", (10, 11)
    )
    catalog = identify(snapshot, classify((10, 11, 12, 13)), explicit=(definition,))
    automatic, explicit = catalog.partners
    assert automatic.component_residue_indexes == (12, 13)
    assert automatic.identification_mode == "topology_connectivity"
    assert explicit.component_residue_indexes == (10, 11)
    assert explicit.identification_mode == "explicit_mapping"


def test_connected_glycan_retains_source_carrier_first_sugar_and_exact_bond():
    (partner,) = identify(
        glycan_topology(), classify((20, 21, 22), "glycan", "GLYCAN-X"), (0, 1)
    ).partners
    assert partner.partner_id == "glycan_0001"
    assert partner.component_residue_indexes == (20, 21, 22)
    assert partner.component_atom_indexes == (200, 201, 210, 211, 220, 221)
    assert partner.carrier_residue_index == 1
    assert partner.first_sugar_residue_index == 20
    assert partner.carrier_link_bond == SourceTopologyBond(10, 200)
    assert partner.linkage_evidence == "topology_connectivity"


@pytest.mark.parametrize("second_carrier_atom", [0, 10])
def test_disconnected_glycans_with_same_name_remain_distinct(second_carrier_atom):
    snapshot = topology(
        (0, 1, 20, 21, 22), ((0, 200), (201, 210), (second_carrier_atom, 220))
    )
    catalog = identify(snapshot, classify((20, 21, 22), "glycan", "GLYCAN-X"), (0, 1))
    assert [p.partner_id for p in catalog.partners] == ["glycan_0001", "glycan_0002"]
    assert [p.component_residue_indexes for p in catalog.partners] == [(20, 21), (22,)]
    assert [p.carrier_residue_index for p in catalog.partners] == [
        0,
        second_carrier_atom // 10,
    ]


@pytest.mark.parametrize(
    "bonds",
    [
        ((201, 210), (211, 220)),  # No carrier.
        ((0, 200), (10, 200), (201, 210), (211, 220)),  # Two carriers.
        ((10, 200), (10, 210), (201, 210), (211, 220)),  # Two first sugars.
        ((10, 200), (11, 201), (201, 210), (211, 220)),  # Two exact bonds.
    ],
)
def test_automatic_glycan_fails_without_unique_carrier_linkage(bonds):
    with pytest.raises(
        MolecularPartnerIdentificationError, match="exactly one unambiguous"
    ):
        identify(
            topology((0, 1, 20, 21, 22), bonds),
            classify((20, 21, 22), "glycan", "GLYCAN-X"),
            (0, 1),
        )


def test_non_glycan_neighbor_is_not_assumed_to_be_protein():
    with pytest.raises(
        MolecularPartnerIdentificationError, match="unambiguous protein"
    ):
        identify(glycan_topology(), classify((20, 21, 22), "glycan", "GLYCAN-X"), (0,))


def test_single_glycan_residue_with_carrier_is_valid():
    (partner,) = identify(
        topology((0, 20), ((0, 200),)), classify((20,), "glycan", "X"), (0,)
    ).partners
    assert partner.component_residue_indexes == (20,)


def test_first_sugar_is_determined_by_bond_not_minimum_component_index():
    snapshot = topology((0, 20, 21), ((0, 210), (201, 210)))
    (partner,) = identify(snapshot, classify((20, 21), "glycan", "X"), (0,)).partners
    assert partner.first_sugar_residue_index == 21


def test_carrier_bond_orientation_does_not_require_lower_protein_atom_index():
    snapshot = topology((20, 21, 30), ((200, 300), (201, 210)))
    partner, = identify(
        snapshot, classify((20, 21), "glycan", "X"), (30,)
    ).partners
    assert (partner.carrier_residue_index, partner.first_sugar_residue_index) == (
        30, 20
    )
    assert partner.carrier_link_bond == SourceTopologyBond(200, 300)


def test_explicit_glycan_validates_linkage_and_keeps_supplied_id():
    (partner,) = identify(
        glycan_topology(),
        classify((20, 21, 22), "glycan", "GLYCAN-X"),
        (0, 1),
        (glycan_definition(),),
    ).partners
    assert partner.partner_id == "supplied-glycan"
    assert partner.identification_mode == "explicit_mapping"
    assert partner.carrier_link_bond == SourceTopologyBond(10, 200)
    assert partner.linkage_evidence == "topology_connectivity"


def test_explicit_glycan_can_resolve_ambiguous_topology_pair_and_multiple_bonds():
    snapshot = topology(
        (0, 1, 20, 21, 22), ((0, 210), (10, 200), (11, 201), (201, 210), (211, 220))
    )
    (partner,) = identify(
        snapshot,
        classify((20, 21, 22), "glycan", "GLYCAN-X"),
        (0, 1),
        (glycan_definition(),),
    ).partners
    assert (partner.carrier_residue_index, partner.first_sugar_residue_index) == (1, 20)
    assert partner.carrier_link_bond == SourceTopologyBond(10, 200)


@pytest.mark.parametrize(
    ("definition", "protein", "error"),
    [
        (
            glycan_definition(
                carrier_residue_index=None, first_sugar_residue_index=None
            ),
            (0, 1),
            "requires carrier and first sugar",
        ),
        (glycan_definition(), (0,), "authoritative protein"),
        (glycan_definition(carrier_residue_index=99), (0, 1), "authoritative protein"),
        (
            glycan_definition(first_sugar_residue_index=21),
            (0, 1),
            "must have a topology bond",
        ),
    ],
)
def test_invalid_explicit_glycan_evidence_fails(definition, protein, error):
    with pytest.raises(MolecularPartnerIdentificationError, match=error):
        identify(
            glycan_topology(),
            classify((20, 21, 22), "glycan", "GLYCAN-X"),
            protein,
            (definition,),
        )


def test_namd_unavailable_connectivity_requires_explicit_external_evidence():
    snapshot = topology((0, 1, 20, 21, 22), status="unavailable")
    classifications = classify((20, 21, 22), "glycan", "GLYCAN-X")
    with pytest.raises(
        MolecularPartnerIdentificationError, match="connectivity unavailable"
    ):
        identify(snapshot, classifications, (0, 1))
    for evidence in (None, "topology_connectivity"):
        with pytest.raises(
            MolecularPartnerIdentificationError, match="explicit external_metadata"
        ):
            identify(
                snapshot,
                classifications,
                (0, 1),
                (glycan_definition(linkage_evidence=evidence),),
            )
    (partner,) = identify(
        snapshot,
        classifications,
        (0, 1),
        (glycan_definition(linkage_evidence="external_metadata"),),
    ).partners
    assert partner.component_residue_indexes == (20, 21, 22)
    assert partner.component_atom_indexes == (200, 201, 210, 211, 220, 221)
    assert partner.identification_mode == "explicit_mapping"
    assert partner.linkage_evidence == "external_metadata"
    assert partner.carrier_link_bond is None
    assert (partner.carrier_residue_index, partner.first_sugar_residue_index) == (1, 20)


@pytest.mark.parametrize("bonds", [(), ((201, 210),)])
def test_external_evidence_cannot_override_authoritative_missing_linkage(bonds):
    with pytest.raises(
        MolecularPartnerIdentificationError, match="must have a topology bond"
    ):
        identify(
            topology((0, 1, 20, 21, 22), bonds),
            classify((20, 21, 22), "glycan", "GLYCAN-X"),
            (0, 1),
            (glycan_definition(linkage_evidence="external_metadata"),),
        )


def test_external_attestation_with_authoritative_bond_records_topology_evidence():
    (partner,) = identify(
        glycan_topology(),
        classify((20, 21, 22), "glycan", "GLYCAN-X"),
        (0, 1),
        (glycan_definition(linkage_evidence="external_metadata"),),
    ).partners
    assert partner.linkage_evidence == "topology_connectivity"
    assert partner.carrier_link_bond == SourceTopologyBond(10, 200)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"topology": object()}, "topology must be"),
        ({"protein_residue_indexes": [0]}, "must be a tuple"),
        ({"protein_residue_indexes": (0, 0)}, "strictly increasing"),
        ({"protein_residue_indexes": (1, 0)}, "strictly increasing"),
        ({"protein_residue_indexes": (False,)}, "non-negative integers"),
        ({"protein_residue_indexes": (-1,)}, "non-negative integers"),
        ({"protein_residue_indexes": (0.0,)}, "non-negative integers"),
        ({"protein_residue_indexes": (99,)}, "must exist"),
        ({"classifications": []}, "tuple"),
        (
            {"classifications": (object(),)},
            "exact MolecularPartnerComponentClassification",
        ),
        ({"classifications": classify((99,))}, "classification residue must exist"),
        ({"classifications": classify((10, 10))}, "only one classification"),
        (
            {"classifications": classify((10,)) + classify((10,), "glycan", "Y")},
            "only one classification",
        ),
        (
            {"classifications": classify((10,)) + classify((10,), "lipid", "Y")},
            "only one classification",
        ),
        ({"classifications": classify((0,))}, "protein residues cannot"),
        ({"classifications": classify((0,), "glycan", "X")}, "protein residues cannot"),
        ({"explicit_partners": []}, "tuple"),
        (
            {"explicit_partners": (object(),)},
            "exact ExplicitMolecularPartnerDefinition",
        ),
    ],
)
def test_exact_input_validation(changes, error):
    kwargs = dict(
        topology=topology((0, 1, 10)),
        protein_residue_indexes=(0,),
        classifications=classify((10,)),
        explicit_partners=(),
    )
    kwargs.update(changes)
    with pytest.raises(MolecularPartnerIdentificationError, match=error):
        identify_molecular_partners(**kwargs)


@pytest.mark.parametrize(
    ("definitions", "error"),
    [
        (
            (ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (99,)),),
            "must exist",
        ),
        (
            (ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (12,)),),
            "matching kind/name",
        ),
        (
            (ExplicitMolecularPartnerDefinition("a", "glycan", "LIPID-X", (10,)),),
            "matching kind/name",
        ),
        (
            (ExplicitMolecularPartnerDefinition("a", "lipid", "WRONG", (10,)),),
            "matching kind/name",
        ),
        (
            (
                ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (10,)),
                ExplicitMolecularPartnerDefinition("b", "lipid", "LIPID-X", (10, 11)),
            ),
            "must not overlap",
        ),
        (
            (
                ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (10,)),
                ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (11,)),
            ),
            "IDs must be unique",
        ),
        (
            (
                ExplicitMolecularPartnerDefinition(
                    "lipid_0001", "lipid", "LIPID-X", (10,)
                ),
            ),
            "conflicts with explicit",
        ),
    ],
)
def test_explicit_classification_membership_and_id_errors(definitions, error):
    with pytest.raises(MolecularPartnerIdentificationError, match=error):
        identify(topology((10, 11, 12)), classify((10, 11)), explicit=definitions)


def test_generated_ids_follow_minimum_atom_before_residue_index():
    snapshot = MolecularPartnerTopology(
        (residue(10, (90,)), residue(11, (5,)), residue(12, (40,))), (), "available"
    )
    catalog = identify(snapshot, classify((10, 11, 12)))
    assert [(p.partner_id, p.component_residue_indexes) for p in catalog.partners] == [
        ("lipid_0001", (11,)),
        ("lipid_0002", (12,)),
        ("lipid_0003", (10,)),
    ]
    assert identify(snapshot, tuple(reversed(classify((10, 11, 12))))) == catalog


def test_definition_input_order_does_not_change_catalog():
    definitions = (
        ExplicitMolecularPartnerDefinition("z", "lipid", "LIPID-X", (10,)),
        ExplicitMolecularPartnerDefinition("a", "lipid", "LIPID-X", (11,)),
    )
    snapshot = topology((10, 11))
    assert identify(snapshot, classify((10, 11)), explicit=definitions) == identify(
        snapshot, classify((11, 10)), explicit=tuple(reversed(definitions))
    )


def test_mixed_lipid_glycan_smoke_is_byte_deterministic():
    snapshot = topology((0, 1, 10, 11, 20, 21), ((10, 200), (201, 210)))
    classifications = classify((10, 11)) + classify((20, 21), "glycan", "GLYCAN-X")
    catalog = identify(snapshot, classifications, (0, 1))
    assert (
        catalog.partner_count,
        catalog.lipid_partner_count,
        catalog.glycan_partner_count,
    ) == (3, 2, 1)
    assert [
        (p.partner_id, p.component_residue_indexes, p.component_atom_indexes)
        for p in catalog.partners
    ] == [
        ("lipid_0001", (10,), (100, 101)),
        ("lipid_0002", (11,), (110, 111)),
        ("glycan_0001", (20, 21), (200, 201, 210, 211)),
    ]
    glycan = catalog.partners[-1]
    assert (glycan.carrier_residue_index, glycan.first_sugar_residue_index) == (1, 20)
    assert glycan.carrier_link_bond == SourceTopologyBond(10, 200)
    expected = json.dumps(catalog.to_dict(), allow_nan=False, separators=(",", ":"))
    for _ in range(3):
        assert (
            json.dumps(
                identify(snapshot, classifications, (0, 1)).to_dict(),
                allow_nan=False,
                separators=(",", ":"),
            )
            == expected
        )
    for field in (
        "condition",
        "distance",
        "contact",
        "occupancy",
        "episode",
        "lifetime",
    ):
        assert field not in expected


def test_source_names_and_condition_do_not_control_identity_or_grouping():
    snapshot = topology((10, 11), ((101, 110),))
    renamed = replace(
        snapshot,
        residues=tuple(
            replace(r, resname="SUGAR-LIKE", residue_id="other", segid="different")
            for r in snapshot.residues
        ),
    )
    (original,) = identify(snapshot, classify((10, 11))).partners
    (other,) = identify(renamed, classify((10, 11))).partners
    assert (
        original.partner_id,
        original.component_residue_indexes,
        original.partner_kind,
    ) == (other.partner_id, other.component_residue_indexes, other.partner_kind)
    assert other.components == renamed.residues
    assert "condition" not in inspect.signature(identify_molecular_partners).parameters
    for cls in (
        SourceTopologyResidue,
        MolecularPartnerTopology,
        MolecularPartnerComponentClassification,
        ExplicitMolecularPartnerDefinition,
        IdentifiedMolecularPartner,
    ):
        assert "condition" not in {f.name for f in fields(cls)}


def test_public_errors_are_portable_and_deterministic():
    errors = []
    for name in ("metadata-X", "metadata-Y"):
        with pytest.raises(MolecularPartnerIdentificationError) as exc:
            identify(glycan_topology(), classify((20, 21, 22), "glycan", name))
        errors.append(str(exc.value))
    assert errors[0] == errors[1]
    assert "/" not in errors[0] and "\\" not in errors[0]
    assert issubclass(MolecularPartnerIdentificationError, ValueError)


def test_pure_modules_have_no_runtime_scientific_or_external_imports():
    allowed = {
        "dataclasses",
        "itertools",
        "typing",
        "mania.preprocessing.molecular_partner_entities",
    }
    for module in (molecular_partner_entities, molecular_partner_identification):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {
                    "open",
                    "exec",
                    "eval",
                    "__import__",
                    "compile",
                }
            elif isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "trajectory",
                    "positions",
                    "coordinates",
                    "dimensions",
                    "distance_array",
                }


def test_identification_and_serialization_do_not_access_external_state(monkeypatch):
    snapshot = glycan_topology()
    classifications = classify((20, 21, 22), "glycan", "GLYCAN-X")

    def forbidden(*args, **kwargs):
        pytest.fail("pure identification accessed external state")

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (os, ("open", "getenv", "getcwd")),
            (Path, ("open", "read_text", "read_bytes", "exists", "stat")),
            (subprocess, ("run", "Popen", "check_output")),
            (time, ("time", "monotonic", "perf_counter", "sleep")),
        ):
            for name in names:
                guard.setattr(owner, name, forbidden)
        # Install last: pytest itself imports inspect while installing patches.
        guard.setattr(builtins, "__import__", forbidden)
        catalog = identify(snapshot, classifications, (0, 1))
        encoded = json.dumps(catalog.to_dict(), allow_nan=False, separators=(",", ":"))
    assert catalog.partner_count == 1
    assert "glycan_0001" in encoded
