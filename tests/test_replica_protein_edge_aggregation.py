"""Stage 31.B scientific vectors, canonical boundaries and pure operation."""

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

from mania import replica_protein_edge_aggregation as m
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
)
from mania.preprocessing.protein_edge_window_table import DatasetProteinEdgeWindowTable
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    CompatibleReplicaAggregationGroup,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)

REFERENCE = load_default_napi2b_canonical_reference()
AGGREGATE_FIELDS = (
    "source_canonical_residue_number",
    "source_canonical_resname",
    "target_canonical_residue_number",
    "target_canonical_resname",
    "edge_type",
    "mean_occupancy",
    "std_occupancy",
    "median_occupancy",
    "n_replicates_available",
    "n_replicates_supporting",
    "support_fraction",
)


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


def row(replica_id="1", occupancy=0.7, edge=(311, 330, "hbond"), **changes):
    numerator, denominator = Decimal(str(occupancy)).as_integer_ratio()
    source, target, edge_type = edge
    return CanonicalProteinEdgeWindowRow(
        **{
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
            "source_residue_index": 10,
            "source_chain_id": "A",
            "source_resid": "311",
            "source_resname": "GLN",
            "source_canonical_residue_number": source,
            "source_canonical_resname": REFERENCE.residue_at(source).canonical_resname,
            "target_residue_index": 20,
            "target_chain_id": "A",
            "target_resid": "330",
            "target_resname": "THR",
            "target_canonical_residue_number": target,
            "target_canonical_resname": REFERENCE.residue_at(target).canonical_resname,
            "edge_type": edge_type,
            "n_contact_frames": numerator,
            "occupancy": occupancy,
            "n_contact_episodes": 1,
            "mean_episode_length_ns": 0.01,
            "max_episode_length_ns": 0.01,
            "edge_weight": occupancy,
            **changes,
        }
    )


def table(*rows):
    return CanonicalProteinEdgeWindowTable(
        tuple(sorted(rows, key=lambda r: r.row_order))
    )


def aggregate(values, statuses=None):
    request = group(statuses or ("available",) * len(values))
    source = table(*(row(str(i + 1), value) for i, value in enumerate(values) if value))
    return m.aggregate_canonical_protein_edges_across_replicas(request, source)


def edge_model(**changes):
    return m.CanonicalProteinEdgeReplicaAggregate(
        **{
            "source_canonical_residue_number": 311,
            "source_canonical_resname": "GLN",
            "target_canonical_residue_number": 330,
            "target_canonical_resname": "THR",
            "edge_type": "hbond",
            "mean_occupancy": 0.5,
            "std_occupancy": 0.3,
            "median_occupancy": 0.5,
            "n_replicates_available": 3,
            "n_replicates_supporting": 3,
            "support_fraction": 1.0,
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


def test_public_contract_and_reference_copy():
    assert m.CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_SCHEMA_VERSION == (
        "mania.canonical_protein_edge_replica_aggregation.v0.1"
    )
    assert m.CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_KIND == (
        "mania_canonical_protein_edge_replica_aggregation"
    )
    assert set(m.__all__) == {
        "CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_SCHEMA_VERSION",
        "CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_KIND",
        "CanonicalProteinEdgeReplicaAggregate",
        "CanonicalProteinEdgeReplicaAggregation",
        "ReplicaProteinEdgeAggregationError",
        "aggregate_canonical_protein_edges_across_replicas",
    }
    assert issubclass(m.ReplicaProteinEdgeAggregationError, ValueError)
    assert tuple(f.name for f in fields(edge_model())) == AGGREGATE_FIELDS
    root_fields = fields(m.CanonicalProteinEdgeReplicaAggregation)
    assert tuple(f.name for f in root_fields if f.init) == (
        "group",
        "edge_count",
        "edges",
    )
    assert tuple(f.name for f in root_fields if not f.init) == (
        "schema_version",
        "kind",
        "canonical_reference_id",
        "canonical_reference_sequence_sha256",
    )
    assert m._REFERENCE.to_dict() == REFERENCE.to_dict()
    assert m._REFERENCE.reference_id == REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
    # Test every endpoint, including positions outside any biological annotation.
    for number in range(1, 690):
        edge_model(
            source_canonical_residue_number=number,
            source_canonical_resname=REFERENCE.residue_at(number).canonical_resname,
            target_canonical_residue_number=number + 1,
            target_canonical_resname=REFERENCE.residue_at(number + 1).canonical_resname,
        )


def test_frozen_models_and_deterministic_independent_serialization():
    result = aggregate([0.2, 0.5, 0.8])
    for model in (result, result.edges[0]):
        with pytest.raises(FrozenInstanceError):
            setattr(model, fields(model)[0].name, None)
        data = model.to_dict()
        assert json.loads(encode(model)) == data
        data.clear()
        assert model.to_dict()
    assert encode(result) == encode(aggregate([0.2, 0.5, 0.8]))
    data = result.to_dict()
    data["group"]["members"].clear()
    data["edges"][0]["mean_occupancy"] = 0
    assert len(result.group.members) == 3
    assert result.edges[0].mean_occupancy == 0.5
    assert tuple(result.edges[0].to_dict()) == AGGREGATE_FIELDS
    assert tuple(result.to_dict()) == (
        "schema_version",
        "kind",
        "canonical_reference_id",
        "canonical_reference_sequence_sha256",
        "group",
        "edge_count",
        "edges",
    )


@pytest.mark.parametrize(
    ("values", "mean", "median", "std", "supporting"),
    [
        ([0.6], 0.6, 0.6, None, 1),
        ([0, 1], 0.5, 0.5, 0.7071067811865476, 1),
        ([0.2, 0.5, 0.8], 0.5, 0.5, 0.3, 3),
        ([0.7, 0, 0.2], 0.3, 0.2, 0.36055512754639896, 2),
        ([0.1, 0.4, 0.9], 0.4666666666666667, 0.4, 0.40414518843273806, 3),
        ([0.1, 0.4], 0.25, 0.25, 0.21213203435596426, 2),
        ([0.4, 0.4], 0.4, 0.4, 0.0, 2),
    ],
)
def test_frozen_scientific_vectors(values, mean, median, std, supporting):
    edge = aggregate(values).edges[0]
    assert edge.mean_occupancy == mean
    assert edge.median_occupancy == median
    assert edge.std_occupancy == std
    assert edge.n_replicates_available == len(values)
    assert edge.n_replicates_supporting == supporting
    with localcontext(Context(prec=50)):
        assert edge.support_fraction == float(
            Decimal(supporting) / Decimal(len(values))
        )


@pytest.mark.parametrize("status", ["unavailable", "excluded"])
def test_nonavailable_is_not_zero_even_with_scientific_rows(status):
    result = aggregate([0.7, 0, 0.2], ("available", "available", status))
    edge = result.edges[0]
    assert edge.mean_occupancy == 0.35
    assert edge.median_occupancy == 0.35
    assert edge.std_occupancy == 0.4949747468305833
    assert edge.n_replicates_available == 2
    assert edge.n_replicates_supporting == 1
    assert edge.support_fraction == 0.5
    assert edge.to_dict() == aggregate([0.7, 0]).edges[0].to_dict()
    changed_reason = replace(
        result.group,
        members=tuple(
            replace(member, availability_reason="Different upstream reason")
            if member.availability_status != "available"
            else member
            for member in result.group.members
        ),
    )
    assert (
        m.aggregate_canonical_protein_edges_across_replicas(
            changed_reason, table(row(), row("3", 0.2))
        ).edges
        == result.edges
    )


def test_single_available_with_unavailable_and_excluded_members():
    edge = aggregate([0.6, 0.9, 0.8], ("available", "unavailable", "excluded")).edges[0]
    assert (edge.mean_occupancy, edge.median_occupancy, edge.std_occupancy) == (
        0.6,
        0.6,
        None,
    )
    assert (
        edge.n_replicates_available,
        edge.n_replicates_supporting,
        edge.support_fraction,
    ) == (1, 1, 1.0)


@pytest.mark.parametrize(
    "statuses",
    [
        ("available", "available", "available"),
        ("unavailable", "excluded", "unavailable"),
    ],
)
def test_empty_table_is_valid_including_no_available_replicas(statuses):
    result = m.aggregate_canonical_protein_edges_across_replicas(
        group(statuses), table()
    )
    assert result.edge_count == 0
    assert result.edges == ()
    assert json.loads(encode(result))["edges"] == []


@pytest.mark.parametrize("status", ["unavailable", "excluded"])
def test_edges_only_in_nonavailable_members_never_enter_universe(status):
    result = aggregate([0, 0, 0.9], ("available", "available", status))
    assert (result.edge_count, result.edges) == (0, ())
    result = aggregate([0.7, 0.8, 0.9], (status,) * 3)
    assert (result.edge_count, result.edges) == (0, ())


def test_mixed_edge_universe_support_and_order_are_independent():
    source = table(
        row("1", 0.7, (311, 330, "hbond")),
        row("2", 0.2, (311, 330, "hbond")),
        row("3", 0.9, (1, 690, "contact")),
        row("1", 0.6, (330, 690, "hbond")),
        row("1", 0.3, (311, 690, "hbond")),
        row("4", 0.8, (1, 2, "excluded_only")),
    )
    result = m.aggregate_canonical_protein_edges_across_replicas(
        group(("available",) * 3 + ("excluded",)), source
    )
    assert [
        (
            e.edge_type,
            e.source_canonical_residue_number,
            e.target_canonical_residue_number,
        )
        for e in result.edges
    ] == [
        ("contact", 1, 690),
        ("hbond", 311, 330),
        ("hbond", 311, 690),
        ("hbond", 330, 690),
    ]
    assert [e.n_replicates_supporting for e in result.edges] == [1, 2, 1, 1]
    assert [e.mean_occupancy for e in result.edges] == [0.3, 0.3, 0.1, 0.2]
    assert [e.median_occupancy for e in result.edges] == [0, 0.2, 0, 0]
    assert all(e.n_replicates_available == 3 for e in result.edges)


def test_source_evidence_does_not_define_canonical_identity_t330m():
    request = group(variant_id="T330M")
    source = table(
        row("1", 0.7, variant_id="T330M", target_resname="MET"),
        row(
            "3",
            0.2,
            variant_id="T330M",
            target_resname="MET",
            source_residue_index=200,
            target_residue_index=100,
            source_resid="other-311",
            target_resid="other-330",
            source_chain_id="B",
            target_chain_id="B",
            source_resname="SYN",
        ),
    )
    result = m.aggregate_canonical_protein_edges_across_replicas(request, source)
    assert result.edge_count == 1
    edge = result.edges[0]
    assert (edge.source_canonical_residue_number, edge.source_canonical_resname) == (
        311,
        "GLN",
    )
    assert (edge.target_canonical_residue_number, edge.target_canonical_resname) == (
        330,
        "THR",
    )
    assert edge.mean_occupancy == 0.3
    assert "MET" not in json.dumps(edge.to_dict())
    assert set(edge.to_dict()) == set(AGGREGATE_FIELDS)


def test_same_source_evidence_different_canonical_edges_remain_distinct():
    result = m.aggregate_canonical_protein_edges_across_replicas(
        group(),
        table(
            row(),
            row("2", edge=(1, 690, "hbond")),
            row("3", edge=(311, 330, "contact")),
        ),
    )
    assert result.edge_count == 3
    assert all(e.n_replicates_supporting == 1 for e in result.edges)


def test_support_is_strictly_positive_without_epsilon_or_coverage_qc():
    tiny = 1e-20
    low_coverage = row(
        "1",
        tiny,
        requested_sample_count=10**21,
        missing_sample_count=9 * 10**20,
        coverage_fraction=0.1,
    )
    result = m.aggregate_canonical_protein_edges_across_replicas(
        group(), table(low_coverage)
    )
    edge = result.edges[0]
    assert edge.n_replicates_available == 3
    assert edge.n_replicates_supporting == 1
    assert edge.support_fraction == 1 / 3
    assert edge.mean_occupancy > 0
    assert edge.median_occupancy == 0


def test_none_condition_namd_group_and_decimal_equal_bounds():
    request = group(engine="namd", condition=None)
    source = table(
        row(
            engine="namd",
            condition=None,
            requested_window_start_ns=20,
            requested_window_end_ns=25,
        )
    )
    result = m.aggregate_canonical_protein_edges_across_replicas(request, source)
    assert result.group.spec.condition is None
    assert result.edges[0].n_replicates_available == 3


@pytest.mark.parametrize(
    "changes",
    [
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
        {"window_id": "other-label"},
        {"window_index": 1},
    ],
)
def test_unrelated_replica_keys_and_other_windows_are_ignored(changes):
    unrelated = row(
        **{
            "replica_id": "2",
            "occupancy": 0.9,
            "edge": (1, 690, "unrelated"),
            **changes,
        }
    )
    result = m.aggregate_canonical_protein_edges_across_replicas(
        group(), table(row(), unrelated)
    )
    assert result.edges == aggregate([0.7, 0, 0]).edges


@pytest.mark.parametrize("status", ["available", "unavailable", "excluded"])
@pytest.mark.parametrize(
    "changes",
    [
        {"engine": "namd"},
        {"variant_id": "T330M"},
        {"condition": None},
        {"condition": "OTHER"},
        {"disulfide_state": "reduced"},
        {"requested_window_start_ns": 22.5, "requested_window_end_ns": 27.5},
        {"requested_window_start_ns": 20.000000000000004},
        {"requested_window_end_ns": 25.000000000000004},
        {"right_endpoint_inclusive": True},
    ],
)
def test_matching_member_identity_or_window_mismatch_fails(status, changes):
    with pytest.raises(m.ReplicaProteinEdgeAggregationError, match="row .* must match"):
        m.aggregate_canonical_protein_edges_across_replicas(
            group(("available", "available", status)), table(row("3", **changes))
        )


@pytest.mark.parametrize(
    "name", ["canonical_reference_id", "canonical_reference_sequence_sha256"]
)
@pytest.mark.parametrize("target", ["table", "spec", "member"])
def test_reference_mismatch_fails_even_for_empty_tables(name, target):
    request, source = group(), table()
    if target == "table":
        source = tampered(source, **{name: "different-reference"})
    elif target == "spec":
        request = tampered(
            request, spec=tampered(request.spec, **{name: "different-reference"})
        )
    else:
        request = tampered(
            request,
            members=(
                tampered(request.members[0], **{name: "different-reference"}),
                *request.members[1:],
            ),
        )
    with pytest.raises(
        m.ReplicaProteinEdgeAggregationError, match="pinned Stage 30 reference"
    ):
        m.aggregate_canonical_protein_edges_across_replicas(request, source)


@pytest.mark.parametrize(
    "changes",
    [
        {"occupancy": 0.0},
        {"occupancy": float("nan")},
        {"occupancy": 0.8},
        {"occupancy": True},
        {"edge_weight": 0.1},
        {"n_contact_frames": 0},
        {"source_canonical_resname": "MET"},
        {"target_canonical_resname": "MET"},
        {"source_canonical_residue_number": 0},
        {"target_canonical_residue_number": 691},
        {"source_canonical_residue_number": 330, "source_canonical_resname": "THR"},
        {"source_resid": None},
        {"right_endpoint_inclusive": 1},
    ],
)
def test_tampered_present_rows_fail_without_redefining_occupancy(changes):
    valid = row()
    source = tampered(table(valid), rows=(tampered(valid, **changes),))
    with pytest.raises(m.ReplicaProteinEdgeAggregationError):
        m.aggregate_canonical_protein_edges_across_replicas(group(), source)


def test_duplicate_canonical_identity_fails_even_with_different_source_evidence():
    first = row()
    second = replace(first, source_resid="different", source_residue_index=11)
    source = tampered(table(first), rows=(first, second))
    with pytest.raises(m.ReplicaProteinEdgeAggregationError, match="duplicate"):
        m.aggregate_canonical_protein_edges_across_replicas(group(), source)


@pytest.mark.parametrize(
    "changes",
    [
        {"rows": []},
        {"rows": (object(),)},
        {"kind": "wrong"},
        {"schema_version": "wrong"},
    ],
)
def test_tampered_table_shape_and_fixed_metadata_fail(changes):
    with pytest.raises(m.ReplicaProteinEdgeAggregationError):
        m.aggregate_canonical_protein_edges_across_replicas(
            group(), tampered(table(), **changes)
        )


def test_exact_types_no_source_level_inputs_and_table_order():
    for source in (None, DatasetProteinEdgeWindowTable(()), (), {}):
        with pytest.raises(
            m.ReplicaProteinEdgeAggregationError,
            match="exact CanonicalProteinEdgeWindowTable",
        ):
            m.aggregate_canonical_protein_edges_across_replicas(group(), source)

    class TableSubclass(CanonicalProteinEdgeWindowTable):
        pass

    with pytest.raises(
        m.ReplicaProteinEdgeAggregationError,
        match="exact CanonicalProteinEdgeWindowTable",
    ):
        m.aggregate_canonical_protein_edges_across_replicas(group(), TableSubclass(()))
    with pytest.raises(
        m.ReplicaProteinEdgeAggregationError,
        match="exact CompatibleReplicaAggregationGroup",
    ):
        m.aggregate_canonical_protein_edges_across_replicas({}, table())
    source = table(row(), row("2"))
    with pytest.raises(
        m.ReplicaProteinEdgeAggregationError, match="deterministic canonical order"
    ):
        m.aggregate_canonical_protein_edges_across_replicas(
            group(), tampered(source, rows=source.rows[::-1])
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"source_canonical_residue_number": 0},
        {"source_canonical_residue_number": True},
        {"target_canonical_residue_number": 691},
        {"target_canonical_residue_number": 330.0},
        {"source_canonical_residue_number": 330, "source_canonical_resname": "THR"},
        {"source_canonical_residue_number": 690, "source_canonical_resname": "LEU"},
        {"source_canonical_resname": "MET"},
        {"target_canonical_resname": "MET"},
        {"edge_type": ""},
        {"edge_type": " hbond"},
        {"edge_type": None},
        {"mean_occupancy": -0.1},
        {"mean_occupancy": 1.1},
        {"mean_occupancy": float("nan")},
        {"median_occupancy": float("inf")},
        {"median_occupancy": 1.1},
        {"median_occupancy": True},
        {"support_fraction": 0.5},
        {"support_fraction": 1.1},
        {"std_occupancy": None},
        {"std_occupancy": -0.1},
        {"std_occupancy": float("inf")},
        {"std_occupancy": float("nan")},
        {"std_occupancy": True},
        {"n_replicates_available": 0},
        {"n_replicates_available": True},
        {"n_replicates_available": 3.0},
        {"n_replicates_supporting": 0},
        {"n_replicates_supporting": 4},
        {"n_replicates_supporting": True},
        {
            "n_replicates_available": 1,
            "n_replicates_supporting": 1,
            "std_occupancy": 0.0,
        },
        {
            "n_replicates_available": 1,
            "n_replicates_supporting": 1,
            "std_occupancy": None,
            "median_occupancy": 0.3,
        },
        {"n_replicates_supporting": 1, "support_fraction": 1 / 3},
        {
            "n_replicates_supporting": 1,
            "support_fraction": 1 / 3,
            "mean_occupancy": 0.2,
        },
    ],
)
def test_aggregate_row_validation(changes):
    with pytest.raises(m.ReplicaProteinEdgeAggregationError):
        edge_model(**changes)


def test_aggregate_root_validation():
    edge = edge_model()
    for changes in (
        {"group": {}},
        {"edge_count": True},
        {"edge_count": -1},
        {"edge_count": 2},
        {"edges": [edge]},
        {"edges": (object(),)},
        {"edge_count": 2, "edges": (edge, edge)},
        {"group": group(("available", "unavailable", "excluded"))},
        {"edges": (tampered(edge, mean_occupancy=2),)},
        {"edge_count": 2, "edges": (edge, replace(edge, edge_type="contact"))},
    ):
        with pytest.raises(m.ReplicaProteinEdgeAggregationError):
            m.CanonicalProteinEdgeReplicaAggregation(
                **{"group": group(), "edge_count": 1, "edges": (edge,), **changes}
            )


def test_decimal_context_does_not_affect_results_or_mutate_inputs():
    request, source = group(), table(row(), row("3", 0.2))
    before = encode(request), encode(source)
    baseline = m.aggregate_canonical_protein_edges_across_replicas(request, source)
    with localcontext(Context(prec=2, rounding=ROUND_UP)) as context:
        context.traps[Inexact] = True
        original_context = str(context)
        result = m.aggregate_canonical_protein_edges_across_replicas(request, source)
        assert str(context) == original_context
    assert encode(result) == encode(baseline)
    assert (encode(request), encode(source)) == before
    assert len(source.rows) == 2  # No materialized per-replica zero row.
    reordered = replace(
        request, spec=replace(request.spec, expected_replica_ids=("3", "1", "2"))
    )
    assert (
        m.aggregate_canonical_protein_edges_across_replicas(reordered, source).edges
        == result.edges
    )


def test_pure_api_blocks_filesystem_network_process_git_clock_and_mdanalysis(
    monkeypatch,
):
    request, source = group(), table(row(), row("3", 0.2))
    original_import = builtins.__import__

    def blocked(*args, **kwargs):
        raise AssertionError("external operation forbidden in pure aggregation")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] == "MDAnalysis":
            return blocked()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        for module, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (
                Path,
                (
                    "open",
                    "read_text",
                    "read_bytes",
                    "write_text",
                    "write_bytes",
                    "stat",
                ),
            ),
            (os, ("open", "stat", "listdir", "scandir", "system", "popen")),
            (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
            (socket, ("socket", "create_connection", "getaddrinfo")),
            (time, ("time", "monotonic", "perf_counter", "sleep")),
        ):
            for name in names:
                patch.setattr(module, name, blocked)
        patch.setattr(builtins, "__import__", guarded_import)
        result = m.aggregate_canonical_protein_edges_across_replicas(request, source)
        assert result.edges[0].mean_occupancy == 0.3
        assert edge_model().source_canonical_resname == "GLN"
        assert result.to_dict()["edge_count"] == 1


def test_module_has_no_io_workflow_qc_or_specialized_execution_imports():
    tree = ast.parse(inspect.getsource(m))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {
        "dataclasses",
        "decimal",
        "math",
        "mania.canonical_reference",
        "mania.canonical_residue_mapping",
        "mania.canonical_window_tables",
        "mania.preprocessing.protein_edge_window_table",
        "mania.replica_aggregation_contract",
    }
