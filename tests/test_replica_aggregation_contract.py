"""Stage 31.A membership, requested-window compatibility and purity regressions."""

import ast
import builtins
import inspect
import io
import json
import math
import os
import socket
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path
from typing import get_args

import pytest

from mania import replica_aggregation_contract as m
from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.preprocessing.physical_time_windows import (
    WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE,
    WINDOW_OVERLAP_PERCENT_REL_TOLERANCE,
)


def window(**changes):
    return m.ReplicaAggregationWindowDefinition(
        **{
            "window_id": "window_0001",
            "window_index": 0,
            "requested_production_start_ns": 20.0,
            "requested_production_end_ns": 30.0,
            "requested_window_start_ns": 20.0,
            "requested_window_end_ns": 25.0,
            "right_endpoint_inclusive": False,
            "window_length_ns": 5.0,
            "window_step_ns": 2.5,
            "overlap_percent": 50.0,
            **changes,
        }
    )


def spec(**changes):
    return m.ReplicaAggregationGroupSpec(
        **{
            "dataset_id": "napi2b-v1-test",
            "system_id": "wt-norm",
            "engine": "gromacs",
            "variant_id": "WT",
            "condition": "NORM",
            "disulfide_state": None,
            "expected_replica_ids": ("1", "2", "3"),
            "window": window(),
            **changes,
        }
    )


def member(replica_id="1", **changes):
    return m.ReplicaAggregationMember(
        **{
            "dataset_id": "napi2b-v1-test",
            "system_id": "wt-norm",
            "trajectory_id": f"trajectory-{replica_id}",
            "replica_id": replica_id,
            "variant_id": "WT",
            "engine": "gromacs",
            "condition": "NORM",
            "disulfide_state": None,
            "canonical_reference_id": m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
            "canonical_reference_sequence_sha256": (
                m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
            ),
            "window": window(),
            "availability_status": "available",
            "availability_reason": None,
            **changes,
        }
    )


def members(**third_changes):
    return (
        member("1"),
        member("2"),
        member(
            "3",
            **{
                "availability_status": "unavailable",
                "availability_reason": "Requested replica data unavailable",
                **third_changes,
            },
        ),
    )


def group():
    return m.build_compatible_replica_aggregation_group(spec(), members())


def test_constants_and_public_api():
    assert (
        m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
        == (CANONICAL_RESIDUE_MAPPING_REFERENCE_ID)
        == "uniprotkb:O95436-1:sequence-v3"
    )
    assert (
        m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
        == (CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256)
        == "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
    )
    assert get_args(m.ReplicaWindowAvailabilityStatus) == (
        "available",
        "unavailable",
        "excluded",
    )
    assert issubclass(m.ReplicaAggregationContractError, ValueError)
    assert set(m.__all__) == {
        "REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID",
        "REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256",
        "ReplicaWindowAvailabilityStatus",
        "ReplicaAggregationWindowDefinition",
        "ReplicaAggregationGroupSpec",
        "ReplicaAggregationMember",
        "CompatibleReplicaAggregationGroup",
        "ReplicaAggregationContractError",
        "build_compatible_replica_aggregation_group",
    }


@pytest.mark.parametrize("factory", [window, spec, member, group])
def test_frozen_models_and_independent_deterministic_json(factory):
    record = factory()
    with pytest.raises(FrozenInstanceError):
        setattr(record, fields(record)[0].name, None)
    encoded = json.dumps(record.to_dict(), allow_nan=False, separators=(",", ":"))
    assert encoded == json.dumps(
        factory().to_dict(), allow_nan=False, separators=(",", ":")
    )
    data = record.to_dict()
    data.clear()
    assert record.to_dict()
    assert json.loads(encoded) == record.to_dict()


def test_keys_use_dataset_system_engine_requested_window_and_dataset_replica():
    request = spec()
    assert request.group_key == (
        "napi2b-v1-test",
        "wt-norm",
        "gromacs",
        window().physical_window_key,
    )
    identity = DatasetTrajectoryIdentity(
        **{
            name: getattr(member(), name)
            for name in DatasetTrajectoryIdentity.model_fields
        }
    )
    assert (
        member().replica_key
        == identity.replica_key
        == (
            "napi2b-v1-test",
            "wt-norm",
            "trajectory-1",
            "1",
        )
    )
    for name, value in (
        ("condition", "TUMOR"),
        ("variant_id", "T330M"),
        ("disulfide_state", "2SS"),
    ):
        assert replace(request, **{name: value}).group_key == request.group_key
        assert replace(member(), **{name: value}).replica_key == member().replica_key
    assert spec(engine="namd").group_key != request.group_key


def test_primary_scientific_smoke_and_same_label_shifted_window_failure():
    result = group()
    assert (
        result.member_count,
        result.available_replica_count,
        result.unavailable_replica_count,
        result.excluded_replica_count,
    ) == (3, 2, 1, 0)
    assert result.available_members == members()[:2]
    assert result.unavailable_members == members()[2:]
    assert result.excluded_members == ()
    shifted = window(requested_window_start_ns=22.5, requested_window_end_ns=27.5)
    assert shifted.window_id == window().window_id
    with pytest.raises(m.ReplicaAggregationContractError, match="physical_window_key"):
        m.build_compatible_replica_aggregation_group(
            spec(), (member("1"), member("2", window=shifted), members()[2])
        )


def test_explicit_excluded_state_is_retained_without_qc_decision():
    records = members(
        availability_status="excluded", availability_reason="Upstream state"
    )
    result = m.build_compatible_replica_aggregation_group(spec(), records)
    assert result.member_count == 3
    assert result.available_replica_count == 2
    assert result.excluded_replica_count == 1
    assert result.unavailable_replica_count == 0
    assert result.excluded_members == records[2:]


def test_all_unavailable_or_excluded_is_valid_and_never_becomes_zero_or_exclusion():
    records = tuple(
        member(
            replica,
            availability_status=status,
            availability_reason="Explicit upstream state",
        )
        for replica, status in (
            ("1", "unavailable"),
            ("2", "excluded"),
            ("3", "unavailable"),
        )
    )
    result = m.build_compatible_replica_aggregation_group(spec(), records)
    assert result.available_members == ()
    assert result.available_replica_count == 0
    assert result.unavailable_replica_count == 2
    assert result.excluded_replica_count == 1
    assert result.members == records


def test_expected_order_is_authoritative_for_builder_and_direct_constructor():
    request = spec(expected_replica_ids=("3", "1", "2"))
    ordered = (members()[2], members()[0], members()[1])
    for build in (
        m.build_compatible_replica_aggregation_group,
        m.CompatibleReplicaAggregationGroup,
    ):
        result = build(request, tuple(reversed(members())))
        assert result.members == ordered
        assert result.available_members == ordered[1:]
        assert result.spec.expected_replica_ids == ("3", "1", "2")
        assert json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":")) == (
            json.dumps(
                build(request, members()).to_dict(),
                allow_nan=False,
                separators=(",", ":"),
            )
        )


@pytest.mark.parametrize(
    "records",
    [
        members()[:2],
        members() + (member("4"),),
        (member("1"), member("2"), member("1")),
        (member("1"), member("2"), member("1", trajectory_id="different")),
    ],
)
def test_missing_extra_duplicate_replica_records_fail_before_ordering(records):
    with pytest.raises(m.ReplicaAggregationContractError):
        m.build_compatible_replica_aggregation_group(spec(), records)


@pytest.mark.parametrize(
    "value", [(), [], ["1"], "1", None, (1,), ("",), (" ",), ("1", "1"), ("1", " 1 ")]
)
def test_expected_replicas_are_nonempty_normalized_unique_tuple(value):
    with pytest.raises(m.ReplicaAggregationContractError):
        spec(expected_replica_ids=value)


def test_dataset_normalization_preserves_internal_text_and_caller_order():
    request = spec(
        dataset_id=" Dataset ID ",
        system_id=" System A ",
        variant_id=" Variant A ",
        condition=" NORM ",
        disulfide_state=" Supplied state ",
        expected_replica_ids=(" 3 ", " 1 ", " 2 "),
    )
    assert (
        request.dataset_id,
        request.system_id,
        request.variant_id,
        request.condition,
        request.disulfide_state,
    ) == (
        "Dataset ID",
        "System A",
        "Variant A",
        "NORM",
        "Supplied state",
    )
    assert request.expected_replica_ids == ("3", "1", "2")
    assert member(" 1 ", trajectory_id=" trajectory A ").replica_key[-2:] == (
        "trajectory A",
        "1",
    )


@pytest.mark.parametrize(
    "name",
    [
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "variant_id",
        "condition",
        "disulfide_state",
    ],
)
@pytest.mark.parametrize("value", [1, True, "", " \t ", []])
def test_invalid_identifiers_and_optional_labels(name, value):
    with pytest.raises(m.ReplicaAggregationContractError, match=name):
        member(**{name: value})
    if name not in ("replica_id", "trajectory_id"):
        with pytest.raises(m.ReplicaAggregationContractError, match=name):
            spec(**{name: value})


def test_same_condition_different_systems_remain_separate():
    first = group()
    second = m.build_compatible_replica_aggregation_group(
        spec(system_id="other-system"),
        tuple(replace(record, system_id="other-system") for record in members()),
    )
    assert first.spec.condition == second.spec.condition == "NORM"
    assert first.spec.group_key != second.spec.group_key
    with pytest.raises(m.ReplicaAggregationContractError, match="system_id"):
        m.build_compatible_replica_aggregation_group(first.spec, second.members)


def test_namd_condition_none_and_disulfide_none_are_valid_and_not_inferred():
    result = m.build_compatible_replica_aggregation_group(
        spec(engine="namd", condition=None),
        tuple(replace(record, engine="namd", condition=None) for record in members()),
    )
    assert result.spec.condition is None
    assert result.spec.disulfide_state is None
    assert all(record.condition is None for record in result.members)
    assert result.to_dict()["spec"]["condition"] is None


@pytest.mark.parametrize(
    "name,value",
    [
        ("dataset_id", "different"),
        ("system_id", "different"),
        ("engine", "namd"),
        ("variant_id", "T330M"),
        ("condition", "TUMOR"),
        ("condition", None),
        ("disulfide_state", "2SS"),
    ],
)
def test_member_consistency_and_mixed_engine_regression(name, value):
    records = (member("1"), member("2", **{name: value}), members()[2])
    with pytest.raises(m.ReplicaAggregationContractError, match=f"member {name}"):
        m.build_compatible_replica_aggregation_group(spec(), records)


@pytest.mark.parametrize("value", ["GROMACS", " namd ", "amber", "", None, 1])
def test_engine_requires_exact_accepted_label(value):
    for factory in (spec, member):
        with pytest.raises(m.ReplicaAggregationContractError, match="engine"):
            factory(engine=value)


@pytest.mark.parametrize(
    "status,reason",
    [
        ("available", "Unexpected reason"),
        ("available", ""),
        ("unavailable", None),
        ("excluded", None),
        ("excluded", " "),
        ("unavailable", 1),
        ("missing", None),
        (None, None),
        (1, None),
        (" Available ", None),
    ],
)
def test_availability_status_and_reason_rules(status, reason):
    with pytest.raises(m.ReplicaAggregationContractError):
        member(availability_status=status, availability_reason=reason)


@pytest.mark.parametrize("status", ["unavailable", "excluded"])
def test_reason_is_preserved_after_surrounding_whitespace_normalization(status):
    reason = "  Explicit upstream state:  operator supplied.  "
    record = member(availability_status=status, availability_reason=reason)
    assert record.availability_reason == reason.strip()
    assert record.to_dict()["availability_reason"] == reason.strip()


@pytest.mark.parametrize(
    "reason",
    [
        "Missing /private/run/file",
        "Missing C:\\private\\run",
        "Missing ../data",
        "Missing ~/data",
        "Missing file:///data",
        "Line one\nline two",
        "A\x00B",
    ],
)
def test_reasons_and_errors_do_not_expose_local_paths_or_controls(reason):
    with pytest.raises(m.ReplicaAggregationContractError) as caught:
        member(availability_status="unavailable", availability_reason=reason)
    assert reason not in str(caught.value)
    assert "portable text" in str(caught.value)


@pytest.mark.parametrize(
    "name,value",
    [
        ("canonical_reference_id", "uniprotkb:other"),
        ("canonical_reference_id", " uniprotkb:O95436-1:sequence-v3"),
        ("canonical_reference_sequence_sha256", "0" * 64),
        ("canonical_reference_sequence_sha256", None),
    ],
)
def test_exact_canonical_reference_and_non_init_spec_reference(name, value):
    with pytest.raises(m.ReplicaAggregationContractError, match="pinned Stage 30"):
        member(**{name: value})
    with pytest.raises(TypeError):
        spec(**{name: value})


def test_physical_signature_exact_order_and_decimal_equivalence():
    assert window().physical_window_key == (
        Decimal("20"),
        Decimal("30"),
        Decimal("20"),
        Decimal("25"),
        False,
        Decimal("5"),
        Decimal("2.5"),
        Decimal("50"),
    )
    assert window(requested_production_start_ns=20).physical_window_key == (
        window().physical_window_key
    )
    assert str(window().physical_window_key[0]) == "2E+1"


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_window_start_ns": 22.5, "requested_window_end_ns": 27.5},
        {"window_step_ns": 5.0, "overlap_percent": 0.0},
        {"window_step_ns": math.nextafter(2.5, 0.0)},
        {"overlap_percent": math.nextafter(50.0, 100.0)},
        {"requested_production_start_ns": 19.0},
        {"requested_production_end_ns": 31.0},
        {"right_endpoint_inclusive": True},
        {"window_id": "window_0007"},
        {"window_index": 7},
    ],
)
def test_window_compatibility_requires_every_physical_field_and_both_labels(changes):
    alternate = window(**changes)
    if "window_id" in changes or "window_index" in changes:
        assert alternate.physical_window_key == window().physical_window_key
    else:
        assert alternate.physical_window_key != window().physical_window_key
    with pytest.raises(m.ReplicaAggregationContractError, match="member"):
        m.build_compatible_replica_aggregation_group(
            spec(), (member("1"), member("2", window=alternate), members()[2])
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_production_end_ns": 20.0},
        {"requested_window_end_ns": 20.0},
        {"requested_window_start_ns": 19.0},
        {"requested_window_end_ns": 31.0},
        {"window_length_ns": 4.0},  # Same bounds cannot have a different length.
        {"window_length_ns": math.nextafter(5.0, 0.0)},
        {"window_length_ns": 0.0},
        {"window_step_ns": 0.0},
        {"window_step_ns": 6.0},
        {"window_step_ns": 2.0},
        {"overlap_percent": 40.0},
        {"overlap_percent": 100.0},
        {"window_index": -1},
        {"window_index": True},
        {"window_index": 1.0},
        {"right_endpoint_inclusive": 1},
        {"right_endpoint_inclusive": "false"},
        {"window_id": " "},
        {"window_id": 1},
    ],
)
def test_invalid_requested_window_contract(changes):
    with pytest.raises(m.ReplicaAggregationContractError):
        window(**changes)


@pytest.mark.parametrize(
    "name",
    [
        "requested_production_start_ns",
        "requested_production_end_ns",
        "requested_window_start_ns",
        "requested_window_end_ns",
        "window_length_ns",
        "window_step_ns",
        "overlap_percent",
    ],
)
@pytest.mark.parametrize(
    "value",
    [True, "5.0", None, float("nan"), float("inf"), float("-inf"), -1.0, 10**400],
)
def test_all_physical_values_reject_invalid_numeric_inputs(name, value):
    with pytest.raises(m.ReplicaAggregationContractError, match=name):
        window(**{name: value})


def test_stage27_overlap_tolerance_is_reused_without_tolerant_grouping():
    assert (
        m.WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE == WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE
    )
    assert (
        m.WINDOW_OVERLAP_PERCENT_REL_TOLERANCE == WINDOW_OVERLAP_PERCENT_REL_TOLERANCE
    )
    near = window(overlap_percent=50 + WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE / 2)
    assert near.physical_window_key != window().physical_window_key
    with pytest.raises(m.ReplicaAggregationContractError, match="overlap_percent"):
        window(overlap_percent=50 + WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE * 2)


def test_decimal_duration_and_key_ignore_callers_decimal_context():
    changes = {
        "requested_production_start_ns": 0.0,
        "requested_production_end_ns": 1.0,
        "requested_window_start_ns": 0.1,
        "requested_window_end_ns": 0.3,
        "window_length_ns": 0.2,
        "window_step_ns": 0.1,
    }
    expected = window(**changes).physical_window_key
    assert 0.3 - 0.1 != 0.2
    with localcontext() as context:
        context.prec = 1
        context.Emax = 1
        context.Emin = -1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert window(**changes).physical_window_key == expected
        assert window().physical_window_key[1] == Decimal(30)
        with pytest.raises(m.ReplicaAggregationContractError, match="duration"):
            window(**{**changes, "window_length_ns": math.nextafter(0.2, 1.0)})


@pytest.mark.parametrize("value", [None, {}, [], (), window().to_dict()])
def test_exact_window_model_required(value):
    for factory in (spec, member):
        with pytest.raises(m.ReplicaAggregationContractError, match="exact"):
            factory(window=value)


def test_exact_spec_members_and_tuple_required_including_subclasses():
    class WindowSubclass(m.ReplicaAggregationWindowDefinition):
        pass

    class SpecSubclass(m.ReplicaAggregationGroupSpec):
        pass

    class MemberSubclass(m.ReplicaAggregationMember):
        pass

    with pytest.raises(m.ReplicaAggregationContractError, match="exact"):
        spec(window=WindowSubclass(**window().to_dict()))
    spec_values = {f.name: getattr(spec(), f.name) for f in fields(spec()) if f.init}
    member_values = {f.name: getattr(member(), f.name) for f in fields(member())}
    for request, records in (
        (None, members()),
        (spec().to_dict(), members()),
        (SpecSubclass(**spec_values), members()),
        (spec(), []),
        (spec(), ()),
        (spec(), list(members())),
        (spec(), (member().to_dict(),)),
        (spec(), (MemberSubclass(**member_values), member("2"), member("3"))),
    ):
        with pytest.raises(m.ReplicaAggregationContractError):
            m.build_compatible_replica_aggregation_group(request, records)


def test_fields_exclude_source_identity_effective_coverage_annotations_and_statistics():
    assert tuple(f.name for f in fields(m.ReplicaAggregationWindowDefinition)) == (
        "window_id",
        "window_index",
        "requested_production_start_ns",
        "requested_production_end_ns",
        "requested_window_start_ns",
        "requested_window_end_ns",
        "right_endpoint_inclusive",
        "window_length_ns",
        "window_step_ns",
        "overlap_percent",
    )
    forbidden = {
        "source_resid",
        "source_resname",
        "source_residue_index",
        "resolved_frame_count",
        "missing_sample_count",
        "coverage_fraction",
        "effective_start_time_ps",
        "effective_end_time_ps",
        "is_ecd",
        "is_mx35",
        "glycosylation_flags",
        "mean_occupancy",
        "std_occupancy",
        "median_occupancy",
        "n_replicates_supporting",
        "support_fraction",
        "qc_status",
        "rmsd",
        "mad",
        "pbc",
        "edge_count",
    }
    for model in (
        m.ReplicaAggregationWindowDefinition,
        m.ReplicaAggregationGroupSpec,
        m.ReplicaAggregationMember,
        m.CompatibleReplicaAggregationGroup,
    ):
        assert forbidden.isdisjoint(f.name for f in fields(model))
    for record in (spec(), member()):
        assert (
            record.canonical_reference_id
            == m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
        )
        assert record.canonical_reference_sequence_sha256 == (
            m.REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
        )
    # Conceptual evidence belongs outside 31.A; neither 94% nor 96% changes
    # compatibility, availability or exclusion. No Stage 32 threshold exists.
    effective_evidence = {
        "1": (94, 6, 0.94, 20.1, 24.9),
        "2": (96, 4, 0.96, 20.0, 24.8),
    }
    assert effective_evidence["1"] != effective_evidence["2"]
    result = group()
    assert result.available_replica_count == 2
    assert result.available_members[0].window == result.available_members[1].window


def test_no_filesystem_network_process_git_clock_or_environment(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Forbidden external access")

    # Imports are already resolved; the whole runtime contract must be pure.
    with monkeypatch.context() as patch:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (Path, ("open", "read_text", "read_bytes", "exists", "stat")),
            (socket, ("socket", "create_connection", "getaddrinfo")),
            (subprocess, ("Popen", "run", "check_output")),
            (os, ("getenv", "system", "popen", "stat", "listdir")),
            (time, ("time", "monotonic", "perf_counter")),
        ):
            for name in names:
                patch.setattr(owner, name, blocked)
        result = group()
        assert result.member_count == 3
        assert json.dumps(result.to_dict(), allow_nan=False)
        assert result.spec.group_key
        with pytest.raises(m.ReplicaAggregationContractError):
            m.build_compatible_replica_aggregation_group(spec(), members()[:2])
    tree = ast.parse(inspect.getsource(m))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports == {
        "dataclasses",
        "decimal",
        "math",
        "typing",
        "mania.canonical_residue_mapping",
        "mania.dataset_identity",
        "mania.preprocessing.physical_time_windows",
    }
