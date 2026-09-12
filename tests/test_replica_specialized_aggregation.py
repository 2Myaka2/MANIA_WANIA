"""Stage 31.C explicit correspondence, canonical statistics and pure operation."""

import ast
import builtins
import inspect
import io
import json
import os
import socket
import subprocess
import time
from copy import copy
from dataclasses import FrozenInstanceError, fields, replace
from decimal import ROUND_UP, Context, Decimal, Inexact, localcontext
from pathlib import Path

import pytest

from mania import replica_specialized_aggregation as m
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_window_tables import (
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
)
from mania.preprocessing.specialized_contact_window_tables import (
    ProteinLipidWindowTable,
)
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    CompatibleReplicaAggregationGroup,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)

KINDS = ("lipid", "glycan")
LOCAL_IDS = ("0003", "0007", "0002")
STAT_FIELDS = (
    "mean_occupancy",
    "std_occupancy",
    "median_occupancy",
    "n_replicates_available",
    "n_replicates_supporting",
    "support_fraction",
)
AGGREGATE_FIELDS = (
    "canonical_residue_number",
    "canonical_resname",
    "partner_correspondence_id",
    "partner_name",
    *STAT_FIELDS,
)
REFERENCE = load_default_napi2b_canonical_reference()


def group(statuses=("available", "available", "available"), **changes):
    window = ReplicaAggregationWindowDefinition(
        "window_0001", 0, 20.0, 30.0, 20.0, 25.0, False, 5.0, 2.5, 50.0
    )
    spec = ReplicaAggregationGroupSpec(
        **{
            "dataset_id": "napi2b-v1-test",
            "system_id": "wt-norm",
            "engine": "gromacs",
            "variant_id": "WT",
            "condition": "NORM",
            "disulfide_state": None,
            "expected_replica_ids": tuple(str(i + 1) for i in range(len(statuses))),
            "window": window,
            **changes,
        }
    )
    return CompatibleReplicaAggregationGroup(
        spec,
        tuple(
            ReplicaAggregationMember(
                spec.dataset_id,
                spec.system_id,
                f"trajectory-{i}",
                i,
                spec.variant_id,
                spec.engine,
                spec.condition,
                spec.disulfide_state,
                REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
                REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
                spec.window,
                status,
                None if status == "available" else "Explicit upstream member state",
            )
            for i, status in zip(spec.expected_replica_ids, statuses, strict=True)
        ),
    )


def correspondence(kind="lipid", request=None, local_ids=LOCAL_IDS, **changes):
    request = group() if request is None else request
    members = tuple(
        sorted(
            (
                m.ReplicaSpecializedPartnerCorrespondenceMember(
                    *member.replica_key,
                    f"{kind}_{local_ids[index]}",
                    f"{kind.upper()}-X",
                )
                for index, member in enumerate(request.members)
                if member.availability_status == "available"
            ),
            key=lambda member: member.replica_key,
        )
    )
    return m.SpecializedPartnerCorrespondence(
        **{
            "partner_correspondence_id": f"{kind}-correspondence-01",
            "partner_kind": kind,
            "partner_name": f"{kind.upper()}-X",
            "members": members,
            **changes,
        }
    )


def collection(*items):
    return m.SpecializedPartnerCorrespondences(
        tuple(sorted(items, key=lambda item: item.partner_correspondence_id))
    )


def row(kind="lipid", replica_id="1", occupancy=0.7, number=311, **changes):
    numerator, denominator = Decimal(str(occupancy)).as_integer_ratio()
    model = (
        CanonicalProteinLipidWindowRow
        if kind == "lipid"
        else CanonicalProteinGlycanWindowRow
    )
    values = {
        "dataset_id": "napi2b-v1-test",
        "system_id": "wt-norm",
        "trajectory_id": f"trajectory-{replica_id}",
        "replica_id": replica_id,
        "variant_id": "WT",
        "engine": "gromacs",
        "condition": "NORM",
        "disulfide_state": None,
        "window_id": "window_0001",
        "window_index": 0,
        "requested_window_start_ns": 20.0,
        "requested_window_end_ns": 25.0,
        "right_endpoint_inclusive": False,
        "effective_window_start_ns": 20.0,
        "effective_window_end_ns": 24.5,
        "requested_sample_count": denominator,
        "resolved_frame_count": denominator,
        "missing_sample_count": 0,
        "coverage_fraction": 1.0,
        "protein_residue_index": 10,
        "protein_chain_id": "A",
        "protein_resid": "311",
        "protein_resname": "GLN",
        "canonical_residue_number": number,
        "canonical_resname": REFERENCE.residue_at(number).canonical_resname,
        f"{kind}_partner_id": f"{kind}_{LOCAL_IDS[int(replica_id) - 1]}",
        f"{kind}_partner_name": f"{kind.upper()}-X",
        f"{kind}_component_residue_indexes": (40, 41),
        "n_contact_frames": numerator,
        "occupancy": occupancy,
        "n_contact_episodes": 1,
        "mean_episode_length_ns": 0.0 if numerator == 1 else 0.01,
        "max_episode_length_ns": 0.0 if numerator == 1 else 0.01,
        "distance_mean_A": 3.0,
        "distance_min_A": 3.0,
    }
    if kind == "glycan":
        values.update(
            carrier_residue_index=9,
            first_sugar_residue_index=40,
            linkage_evidence="external_metadata",
            carrier_link_atom_index=None,
            first_sugar_link_atom_index=None,
        )
    return model(**{**values, **changes})


def table(kind="lipid", *rows):
    model = (
        CanonicalProteinLipidWindowTable
        if kind == "lipid"
        else CanonicalProteinGlycanWindowTable
    )
    return model(tuple(sorted(rows, key=lambda item: item.row_order)))


def api(kind):
    return getattr(m, f"aggregate_canonical_protein_{kind}_across_replicas")


def aggregate(kind="lipid", values=(0.7, 0, 0.2), statuses=None):
    request = group(statuses or ("available",) * len(values))
    source = table(
        kind, *(row(kind, str(i + 1), value) for i, value in enumerate(values) if value)
    )
    return api(kind)(
        request, source, correspondences=collection(correspondence(kind, request))
    )


def aggregate_model(kind="lipid", **changes):
    model = getattr(m, f"CanonicalProtein{kind.title()}ReplicaAggregate")
    return model(
        **{
            "canonical_residue_number": 311,
            "canonical_resname": "GLN",
            "partner_correspondence_id": f"{kind}-correspondence-01",
            "partner_name": f"{kind.upper()}-X",
            "mean_occupancy": 0.3,
            "std_occupancy": 0.36055512754639896,
            "median_occupancy": 0.2,
            "n_replicates_available": 3,
            "n_replicates_supporting": 2,
            "support_fraction": 2 / 3,
            **changes,
        }
    )


def tampered(model, **changes):
    result = copy(model)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def encode(model):
    return json.dumps(model.to_dict(), allow_nan=False, separators=(",", ":"))


def stats(model):
    return tuple(getattr(model, name) for name in STAT_FIELDS)


def test_public_contract_and_reference_copy():
    assert issubclass(m.ReplicaSpecializedAggregationError, ValueError)
    assert m._REFERENCE.to_dict() == REFERENCE.to_dict()
    required = {
        "ReplicaSpecializedAggregationError",
        "ReplicaSpecializedPartnerCorrespondenceMember",
        "SpecializedPartnerCorrespondence",
        "SpecializedPartnerCorrespondences",
    }
    assert tuple(f.name for f in fields(correspondence().members[0])) == (
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "local_partner_id",
        "partner_name",
    )
    for kind in KINDS:
        required.update(
            {
                f"CANONICAL_PROTEIN_{kind.upper()}_REPLICA_AGGREGATION_SCHEMA_VERSION",
                f"CANONICAL_PROTEIN_{kind.upper()}_REPLICA_AGGREGATION_KIND",
                f"CanonicalProtein{kind.title()}ReplicaAggregate",
                f"CanonicalProtein{kind.title()}ReplicaAggregation",
                f"aggregate_canonical_protein_{kind}_across_replicas",
            }
        )
        result = aggregate(kind)
        assert (
            result.schema_version
            == f"mania.canonical_protein_{kind}_replica_aggregation.v0.1"
        )
        assert result.kind == f"mania_canonical_protein_{kind}_replica_aggregation"
        assert tuple(f.name for f in fields(result.rows[0])) == AGGREGATE_FIELDS
        assert tuple(f.name for f in fields(result) if f.init) == (
            "group",
            "correspondences",
            "row_count",
            "rows",
        )
        assert tuple(f.name for f in fields(result) if not f.init) == (
            "schema_version",
            "kind",
            "canonical_reference_id",
            "canonical_reference_sequence_sha256",
        )
        for number in range(1, 691):
            aggregate_model(
                kind,
                canonical_residue_number=number,
                canonical_resname=REFERENCE.residue_at(number).canonical_resname,
            )
    assert set(m.__all__) == required


@pytest.mark.parametrize("kind", KINDS)
def test_frozen_models_and_deterministic_independent_serialization(kind):
    result = aggregate(kind)
    correspondence = result.correspondences.correspondences[0]
    models = (
        result,
        result.rows[0],
        result.correspondences,
        correspondence,
        correspondence.members[0],
    )
    for model in models:
        with pytest.raises(FrozenInstanceError):
            setattr(model, fields(model)[0].name, None)
        data = model.to_dict()
        assert json.loads(encode(model)) == data
        data.clear()
        assert model.to_dict()
    data = result.to_dict()
    data["group"]["members"].clear()
    data["correspondences"]["correspondences"][0]["members"].clear()
    data["rows"][0]["mean_occupancy"] = 0
    assert encode(result) == encode(aggregate(kind))


@pytest.mark.parametrize(
    "name",
    (
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "local_partner_id",
        "partner_name",
    ),
)
@pytest.mark.parametrize("value", (None, "", " ", 1))
def test_correspondence_member_invalid_text(name, value):
    with pytest.raises(m.ReplicaSpecializedAggregationError):
        replace(correspondence().members[0], **{name: value})


def test_dataset_identifiers_follow_accepted_strip_semantics():
    member = correspondence().members[0]
    assert replace(member, dataset_id=f" {member.dataset_id} ") == member
    assert member.replica_key == group().members[0].replica_key


@pytest.mark.parametrize(
    "changes",
    (
        {"partner_correspondence_id": ""},
        {"partner_correspondence_id": " x"},
        {"partner_kind": "LIPID"},
        {"partner_kind": "glycolipid"},
        {"partner_kind": None},
        {"partner_name": ""},
        {"partner_name": "LIPID-Y"},
        {"members": []},
        {"members": (object(),)},
    ),
)
def test_invalid_correspondence(changes):
    with pytest.raises(m.ReplicaSpecializedAggregationError):
        replace(correspondence(), **changes)


def test_ambiguous_members_name_mismatch_and_order_fail():
    item = correspondence()
    first = item.members[0]
    for members in (
        (first, replace(first, local_partner_id="lipid_0009")),
        (replace(first, partner_name="DIFFERENT"), *item.members[1:]),
        item.members[::-1],
    ):
        with pytest.raises(m.ReplicaSpecializedAggregationError):
            replace(item, members=members)


def test_collection_unique_ids_local_bindings_kind_and_exact_lookup():
    first = correspondence()
    distinct = correspondence(local_ids=("0011", "0012", "0013"))
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="IDs must be unique"
    ):
        collection(first, distinct)
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="local partner"):
        collection(first, replace(first, partner_correspondence_id="second"))
    second = replace(distinct, partner_correspondence_id="second")
    items = collection(first, second)
    assert items.lookup("second") is second
    for key in ("LIPID-X", " second", "unknown", None):
        with pytest.raises(m.ReplicaSpecializedAggregationError):
            items.lookup(key)
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="deterministic"):
        m.SpecializedPartnerCorrespondences((second, first))
    for invalid in ([], (object(),)):
        with pytest.raises(m.ReplicaSpecializedAggregationError):
            m.SpecializedPartnerCorrespondences(invalid)
    # A shared literal local ID is allowed across different exact kinds.
    glycan = replace(first, partner_correspondence_id="glycan", partner_kind="glycan")
    assert len(collection(first, glycan).correspondences) == 2


@pytest.mark.parametrize("kind", KINDS)
def test_incomplete_correspondence_fails_before_sparse_zero_materialization(kind):
    item = correspondence(kind)
    incomplete = replace(item, members=item.members[:2])
    # Empty canonical science still fails: incompleteness is not occupancy zero.
    for source in (table(kind), table(kind, row(kind))):
        with pytest.raises(
            m.ReplicaSpecializedAggregationError, match="exactly all available"
        ):
            api(kind)(group(), source, correspondences=collection(incomplete))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("status", ("unavailable", "excluded"))
def test_correspondence_cannot_bind_unavailable_excluded_or_foreign_members(
    kind, status
):
    request = group(("available", "available", status))
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="exactly all available"
    ):
        api(kind)(
            request, table(kind), correspondences=collection(correspondence(kind))
        )
    item = correspondence(kind, request)
    wrong = replace(item.members[1], trajectory_id="foreign-trajectory")
    wrong_members = tuple(sorted((item.members[0], wrong), key=lambda x: x.replica_key))
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="exactly all available"
    ):
        api(kind)(
            request,
            table(kind),
            correspondences=collection(replace(item, members=wrong_members)),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_kind_must_match_call_and_root(kind):
    other = "glycan" if kind == "lipid" else "lipid"
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="kind must match"):
        api(kind)(
            group(), table(kind), correspondences=collection(correspondence(other))
        )
    result = aggregate(kind)
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="kind must match"):
        replace(result, correspondences=collection(correspondence(other)))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "values,expected",
    (
        ((0.7, 0, 0.2), (0.3, 0.36055512754639896, 0.2, 3, 2, 2 / 3)),
        ((0.5, 0.5, 0), (1 / 3, 0.28867513459481287, 0.5, 3, 2, 2 / 3)),
        ((0.6,), (0.6, None, 0.6, 1, 1, 1.0)),
        ((0, 1.0), (0.5, 0.7071067811865476, 0.5, 2, 1, 0.5)),
    ),
)
def test_scientific_smokes_and_sample_sd(kind, values, expected):
    result = aggregate(kind, values)
    assert result.row_count == 1
    assert stats(result.rows[0]) == expected
    assert result.rows[0].canonical_residue_number == 311
    assert result.rows[0].canonical_resname == "GLN"


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("status", ("unavailable", "excluded"))
def test_unavailable_excluded_are_not_zero_and_cannot_create_union(kind, status):
    request = group(("available", "available", status))
    source = table(kind, row(kind), row(kind, "3", 0.2), row(kind, "3", 0.9, 690))
    result = api(kind)(
        request, source, correspondences=collection(correspondence(kind, request))
    )
    assert result.row_count == 1
    assert stats(result.rows[0]) == (0.35, 0.4949747468305833, 0.35, 2, 1, 0.5)


@pytest.mark.parametrize("kind", KINDS)
def test_same_name_distinct_partner_does_not_match(kind):
    request = group(("available",))
    item = correspondence(kind, request, local_ids=("0002",))
    unrelated = row(kind, occupancy=0.9, **{f"{kind}_partner_id": f"{kind}_0001"})
    bound = row(kind, occupancy=0.6, **{f"{kind}_partner_id": f"{kind}_0002"})
    for rows, expected in (((unrelated,), ()), ((unrelated, bound), (0.6,))):
        result = api(kind)(
            request, table(kind, *rows), correspondences=collection(item)
        )
        assert tuple(r.mean_occupancy for r in result.rows) == expected


@pytest.mark.parametrize("kind", KINDS)
def test_same_local_id_without_correspondence_never_inferred(kind):
    source = table(
        kind,
        *(
            row(kind, str(i), **{f"{kind}_partner_id": f"{kind}_0001"})
            for i in (1, 2, 3)
        ),
    )
    result = api(kind)(group(), source, correspondences=collection())
    assert result.rows == ()
    assert result.row_count == 0


@pytest.mark.parametrize("kind", KINDS)
def test_union_order_and_source_evidence_are_independent_of_aggregate_identity(kind):
    request = group(variant_id="T330M")
    first = correspondence(kind)
    second = correspondence(
        kind, local_ids=("0001", "0001", "0001"), partner_correspondence_id="z-second"
    )
    changed = {f"{kind}_component_residue_indexes": (80, 81)}
    if kind == "glycan":
        changed.update(first_sugar_residue_index=80, carrier_residue_index=79)
    source = table(
        kind,
        row(kind, "1", 0.7, 330, variant_id="T330M", protein_resname="MET"),
        row(
            kind,
            "3",
            0.2,
            330,
            variant_id="T330M",
            protein_resname="SYN",
            protein_residue_index=30,
            protein_chain_id="B",
            protein_resid="other",
            **changed,
        ),
        row(kind, "2", 0.9, 1, variant_id="T330M"),
        row(
            kind,
            "1",
            0.6,
            690,
            variant_id="T330M",
            **{f"{kind}_partner_id": f"{kind}_0001"},
        ),
    )
    result = api(kind)(request, source, correspondences=collection(first, second))
    assert [
        (r.partner_correspondence_id, r.canonical_residue_number) for r in result.rows
    ] == [
        (first.partner_correspondence_id, 1),
        (first.partner_correspondence_id, 330),
        (second.partner_correspondence_id, 690),
    ]
    assert stats(result.rows[1]) == stats(aggregate(kind).rows[0])
    assert result.rows[1].canonical_resname == "THR"
    assert "MET" not in encode(result.rows[1])


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "changes",
    (
        {"dataset_id": "other-dataset"},
        {"system_id": "same-condition-other-system"},
        {"trajectory_id": "other-trajectory"},
        {"replica_id": "other-replica"},
        {"system_id": "other-engine-system", "engine": "namd"},
        {
            "window_id": "window_0002",
            "window_index": 1,
            "requested_window_start_ns": 22.5,
            "requested_window_end_ns": 27.5,
        },
    ),
)
def test_other_groups_engines_windows_ignored(kind, changes):
    unrelated = replace(row(kind, "2", 0.9, 690), **changes)
    source = table(kind, row(kind), unrelated)
    result = api(kind)(
        group(), source, correspondences=collection(correspondence(kind))
    )
    assert result.rows == aggregate(kind, (0.7, 0, 0)).rows


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("status", ("available", "unavailable", "excluded"))
@pytest.mark.parametrize(
    "changes",
    (
        {"engine": "namd"},
        {"variant_id": "T330M"},
        {"condition": None},
        {"condition": "OTHER"},
        {"disulfide_state": "reduced"},
        {"requested_window_start_ns": 22.5, "requested_window_end_ns": 27.5},
        {"requested_window_start_ns": 20.000000000000004},
        {"requested_window_end_ns": 25.000000000000004},
        {"right_endpoint_inclusive": True},
    ),
)
def test_relevant_member_and_same_label_window_mismatches_fail(kind, status, changes):
    request = group(("available", "available", status))
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="row .* must match"):
        api(kind)(
            request,
            table(kind, row(kind, "3", **changes)),
            correspondences=collection(correspondence(kind, request)),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_row_partner_name_must_match_supplied_correspondence(kind):
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="partner_name must exactly match"
    ):
        api(kind)(
            group(),
            table(kind, row(kind, **{f"{kind}_partner_name": "DIFFERENT"})),
            correspondences=collection(correspondence(kind)),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_none_condition_namd_and_decimal_equal_bounds(kind):
    request = group(engine="namd", condition=None)
    source = table(
        kind,
        row(
            kind,
            engine="namd",
            condition=None,
            requested_window_start_ns=20,
            requested_window_end_ns=25,
        ),
    )
    result = api(kind)(
        request, source, correspondences=collection(correspondence(kind, request))
    )
    assert result.group.spec.condition is None
    assert result.rows[0].n_replicates_available == 3


@pytest.mark.parametrize("kind", KINDS)
def test_zero_available_requires_empty_correspondences_and_returns_empty(kind):
    request = group(("unavailable", "excluded", "unavailable"))
    source = table(kind, row(kind))
    result = api(kind)(request, source, correspondences=collection())
    assert result.rows == () and result.row_count == 0
    for item in (correspondence(kind), correspondence(kind, request)):
        with pytest.raises(
            m.ReplicaSpecializedAggregationError, match="zero available"
        ):
            api(kind)(request, source, correspondences=collection(item))
    assert aggregate(kind, (0,)).rows == ()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "values",
    ((0.7, 0, 0.2), (0.5, 0.5, 0), (0.7, 0), (0.6,), (0.2, 0.5, 0.8), (1e-20, 0, 0)),
)
def test_exact_cross_layer_statistics_with_accepted_31b(kind, values):
    from test_replica_protein_edge_aggregation import aggregate as protein_aggregate

    assert stats(aggregate(kind, values).rows[0]) == stats(
        protein_aggregate(values).edges[0]
    )


@pytest.mark.parametrize("kind", KINDS)
def test_decimal_context_isolation_and_input_immutability(kind):
    request, source = group(), table(kind, row(kind), row(kind, "3", 0.2))
    items = collection(correspondence(kind))
    before = tuple(encode(value) for value in (request, source, items))
    expected = aggregate(kind)
    context = Context(prec=2, rounding=ROUND_UP)
    context.traps[Inexact] = True
    with localcontext(context) as active:
        context_before = str(active)
        result = api(kind)(request, source, correspondences=items)
        assert str(active) == context_before
    assert encode(result) == encode(expected)
    assert tuple(encode(value) for value in (request, source, items)) == before


@pytest.mark.parametrize("kind", KINDS)
def test_strict_positive_support_without_epsilon_or_qc(kind):
    low_coverage = row(
        kind,
        occupancy=1e-20,
        requested_sample_count=10**21,
        missing_sample_count=9 * 10**20,
        coverage_fraction=0.1,
    )
    result = api(kind)(
        group(),
        table(kind, low_coverage),
        correspondences=collection(correspondence(kind)),
    )
    assert result.rows[0].mean_occupancy > 0
    assert result.rows[0].n_replicates_supporting == 1
    assert result.rows[0].n_replicates_available == 3
    assert result.rows[0].support_fraction == 1 / 3


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "name", ("canonical_reference_id", "canonical_reference_sequence_sha256")
)
@pytest.mark.parametrize("target", ("table", "spec", "member", "root"))
def test_reference_mismatch_fails_even_for_empty_tables(kind, name, target):
    request, source = group(), table(kind)
    if target == "table":
        source = tampered(source, **{name: "different"})
    elif target == "spec":
        request = tampered(request, spec=tampered(request.spec, **{name: "different"}))
    elif target == "member":
        request = tampered(
            request,
            members=(
                tampered(request.members[0], **{name: "different"}),
                *request.members[1:],
            ),
        )
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="pinned Stage 30 reference"
    ):
        if target == "root":
            tampered(aggregate(kind), **{name: "different"}).__post_init__()
        else:
            api(kind)(request, source, correspondences=collection())


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "changes",
    (
        {"occupancy": 0.0},
        {"occupancy": float("nan")},
        {"occupancy": 0.8},
        {"occupancy": True},
        {"n_contact_frames": 0},
        {"canonical_resname": "MET"},
        {"canonical_residue_number": 0},
        {"canonical_residue_number": 691},
        {"canonical_residue_number": True},
        {"protein_resid": None},
        {"right_endpoint_inclusive": 1},
    ),
)
def test_tampered_relevant_canonical_row_fails(kind, changes):
    valid = row(kind)
    source = tampered(table(kind, valid), rows=(tampered(valid, **changes),))
    with pytest.raises(m.ReplicaSpecializedAggregationError):
        api(kind)(group(), source, correspondences=collection(correspondence(kind)))


@pytest.mark.parametrize("kind", KINDS)
def test_duplicate_relevant_row_with_different_source_evidence_fails(kind):
    first = row(kind)
    second = replace(first, protein_residue_index=11, protein_resid="different")
    source = tampered(table(kind, first), rows=(first, second))
    with pytest.raises(m.ReplicaSpecializedAggregationError, match="duplicate"):
        api(kind)(group(), source, correspondences=collection(correspondence(kind)))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "changes",
    (
        {"rows": []},
        {"rows": (object(),)},
        {"kind": "wrong"},
        {"schema_version": "wrong"},
    ),
)
def test_tampered_table_shape_and_fixed_metadata_fail(kind, changes):
    with pytest.raises(m.ReplicaSpecializedAggregationError):
        api(kind)(
            group(), tampered(table(kind), **changes), correspondences=collection()
        )


@pytest.mark.parametrize("kind", KINDS)
def test_exact_types_no_source_tables_and_deterministic_input_order(kind):
    for source in (
        None,
        ProteinLipidWindowTable(()),
        (),
        {},
        table("glycan" if kind == "lipid" else "lipid"),
    ):
        with pytest.raises(
            m.ReplicaSpecializedAggregationError, match="exact CanonicalProtein"
        ):
            api(kind)(group(), source, correspondences=collection())
    with pytest.raises(
        m.ReplicaSpecializedAggregationError,
        match="exact CompatibleReplicaAggregationGroup",
    ):
        api(kind)({}, table(kind), correspondences=collection())
    with pytest.raises(
        m.ReplicaSpecializedAggregationError,
        match="exact SpecializedPartnerCorrespondences",
    ):
        api(kind)(group(), table(kind), correspondences=())
    source = table(kind, row(kind), row(kind, "2"))
    with pytest.raises(
        m.ReplicaSpecializedAggregationError, match="deterministic canonical order"
    ):
        api(kind)(
            group(),
            tampered(source, rows=source.rows[::-1]),
            correspondences=collection(),
        )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "changes",
    (
        {"canonical_residue_number": 0},
        {"canonical_residue_number": True},
        {"canonical_residue_number": 691},
        {"canonical_residue_number": 311.0},
        {"canonical_resname": "MET"},
        {"partner_correspondence_id": ""},
        {"partner_name": ""},
        {"mean_occupancy": -0.1},
        {"mean_occupancy": 1.1},
        {"mean_occupancy": float("nan")},
        {"median_occupancy": float("inf")},
        {"median_occupancy": True},
        {"support_fraction": 0.5},
        {"std_occupancy": None},
        {"std_occupancy": -0.1},
        {"std_occupancy": float("nan")},
        {"std_occupancy": True},
        {"n_replicates_available": 0},
        {"n_replicates_available": True},
        {"n_replicates_supporting": 0},
        {"n_replicates_supporting": 4},
        {"n_replicates_supporting": True},
        {
            "n_replicates_available": 1,
            "n_replicates_supporting": 1,
            "support_fraction": 1.0,
        },
        {
            "n_replicates_available": 1,
            "n_replicates_supporting": 1,
            "support_fraction": 1.0,
            "std_occupancy": None,
        },
        {"n_replicates_supporting": 1, "support_fraction": 1 / 3},
        {"mean_occupancy": 0.9},
    ),
)
def test_aggregate_model_invariants(kind, changes):
    with pytest.raises(m.ReplicaSpecializedAggregationError):
        aggregate_model(kind, **changes)


@pytest.mark.parametrize("kind", KINDS)
def test_root_invariants(kind):
    result = aggregate(kind)
    first = result.rows[0]
    invalid = (
        {"row_count": True},
        {"row_count": 2},
        {"rows": []},
        {"rows": (object(),)},
        {"rows": (first, first), "row_count": 2},
        {"rows": (replace(first, partner_correspondence_id="unknown"),)},
        {"rows": (replace(first, partner_name="DIFFERENT"),)},
        {"rows": (tampered(first, canonical_resname="MET"),)},
        {
            "group": group(("available", "available", "unavailable")),
            "correspondences": collection(
                correspondence(kind, group(("available", "available", "unavailable")))
            ),
        },
        {
            "rows": (
                replace(first, canonical_residue_number=330, canonical_resname="THR"),
                first,
            ),
            "row_count": 2,
        },
        {"correspondences": collection()},
    )
    for changes in invalid:
        with pytest.raises(m.ReplicaSpecializedAggregationError):
            replace(result, **changes)
    assert replace(result, rows=(), row_count=0).rows == ()


@pytest.mark.parametrize("kind", KINDS)
def test_no_filesystem_network_git_subprocess_clock_or_mdanalysis(kind, monkeypatch):
    request = group()
    source = table(kind, row(kind), row(kind, "3", 0.2))
    items = collection(correspondence(kind))
    before = tuple(encode(value) for value in (request, source, items))
    original_import = builtins.__import__

    def blocked(*args, **kwargs):
        raise AssertionError("Pure Stage 31.C must not perform external operations")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"MDAnalysis", "git", "gitdb"}:
            blocked()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        for target, name in (
            (builtins, "open"),
            (io, "open"),
            (os, "open"),
            (os, "system"),
            (Path, "read_text"),
            (Path, "read_bytes"),
            (Path, "write_text"),
            (socket, "socket"),
            (socket, "create_connection"),
            (subprocess, "Popen"),
            (subprocess, "run"),
            (time, "time"),
            (time, "monotonic"),
            (time, "perf_counter"),
            (time, "sleep"),
        ):
            patch.setattr(target, name, blocked)
        result = api(kind)(request, source, correspondences=items)
        assert stats(result.rows[0]) == (0.3, 0.36055512754639896, 0.2, 3, 2, 2 / 3)
        replace(result.rows[0])
        replace(result)
        assert tuple(encode(value) for value in (request, source, items)) == before


def test_no_io_workflow_annotation_or_qc_imports():
    parsed = ast.parse(inspect.getsource(m))
    imports = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert set(imports) == {
        "dataclasses",
        "decimal",
        "math",
        "typing",
        "mania.canonical_reference",
        "mania.canonical_residue_mapping",
        "mania.canonical_window_tables",
        "mania.preprocessing.molecular_partner_entities",
        "mania.preprocessing.specialized_contact_window_tables",
        "mania.replica_aggregation_contract",
    }
