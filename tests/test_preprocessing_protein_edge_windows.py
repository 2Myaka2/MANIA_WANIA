"""Synthetic scientific regressions for pure Stage 28.B protein-edge windows."""

import ast
import builtins
import inspect
import io
import json
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, Rounded, localcontext
from math import nextafter
from pathlib import Path
from typing import get_args

import pytest

from mania.dataset_identity import DatasetTemporalParameters
from mania.preprocessing import contact_episodes as episodes
from mania.preprocessing import physical_time_sampling as sampling
from mania.preprocessing import physical_time_windows as windows
from mania.preprocessing import protein_edge_windows as aggregation
from mania.preprocessing import trajectory_contacts as contacts
from mania.preprocessing.protein_edge_windows import (
    PROTEIN_EDGE_WINDOW_KIND,
    PROTEIN_EDGE_WINDOW_SCHEMA_VERSION,
    ProteinEdgeWindowAggregation,
    ProteinEdgeWindowAggregationError,
    ProteinEdgeWindowAggregationStatus,
    ProteinEdgeWindowMetric,
    WindowProteinEdgeStatistics,
    aggregate_protein_edges_by_window,
)


def plans(count=5, *, missing=(), times=None, indexes=None, length=None, step=None):
    duration = Decimal(count - 1) * Decimal("0.05")
    production_duration = duration
    if length is None:
        length = float(duration + Decimal("0.01"))
        production_duration += Decimal("0.02")
    step = length if step is None else step
    temporal = DatasetTemporalParameters(
        production_start_ns=5,
        production_end_ns=float(Decimal(5) + production_duration),
        frame_stride_ps=50,
        window_length_ns=length,
        window_step_ns=step,
        overlap_percent=(1 - step / length) * 100,
    )
    indexes = tuple(500 + i * 5 for i in range(count)) if indexes is None else indexes
    times = tuple(5000.0 + i * 50 for i in range(count)) if times is None else times
    source = tuple(
        sampling.PhysicalTimeSourceFrame(index, actual)
        for i, (index, actual) in enumerate(zip(indexes, times, strict=True))
        if i not in missing
    )
    plan = sampling.resolve_physical_time_sampling(source, temporal=temporal)
    return plan, windows.plan_physical_time_windows(plan, temporal=temporal)


def pair(**changes):
    return contacts.PreprocessingContactPairResult(
        **{
            "source_residue_index": 1,
            "target_residue_index": 7,
            "source_residue_id": -2,
            "target_residue_id": "7A",
            "source_resname": "ALA",
            "target_resname": "LYS",
            "source_segid": "A",
            "target_segid": "B",
            "minimum_distance": 3.0,
            **changes,
        }
    )


def reverse(contact):
    return replace(
        contact,
        **{
            f"{side}_{name}": getattr(contact, f"{other}_{name}")
            for name in ("residue_index", "residue_id", "resname", "segid")
            for side, other in (("source", "target"), ("target", "source"))
        },
    )


def contact_result(plan, observations=None, **changes):
    # Observation keys are requested positions, deliberately unlike source indexes.
    if observations is None:
        observations = {
            s.requested_sample_index: (pair(),) for s in plan.selected_samples
        }
    return contacts.PreprocessingConditionContactsResult(
        **{
            "condition_name": "legacy-routing-name",
            "options": contacts.PreprocessingContactDetectionOptions(
                contact_selection="protein"
            ),
            "status": "computed",
            "frame_results": tuple(
                contacts.PreprocessingContactFrameResult(
                    condition_name="legacy-routing-name",
                    frame_index=sample.source_frame_index,
                    # Deliberately unrelated to lifetime authority, including None.
                    time_ps=None if sample.requested_sample_index % 2 else 90000.0,
                    contacts=observations.get(sample.requested_sample_index, ()),
                )
                for sample in plan.selected_samples
            ),
            **changes,
        }
    )


def aggregate(plan, window_plan, result=None):
    return aggregate_protein_edges_by_window(
        plan,
        window_plan,
        contacts_result=contact_result(plan) if result is None else result,
    )


def serialized(result):
    return json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))


def metric():
    return ProteinEdgeWindowMetric(
        "window_0001",
        0,
        1,
        7,
        -2,
        "7A",
        "ALA",
        "LYS",
        "A",
        "B",
        "residue_contact",
        5,
        4,
        0.8,
        2,
        0.05,
        0.1,
        0.8,
    )


def statistics():
    return WindowProteinEdgeStatistics("window_0001", 0, 5, 5, 0, 1.0, 1, (metric(),))


def root():
    return ProteinEdgeWindowAggregation("complete", "legacy", 1, 1, (statistics(),))


def test_public_constants_types_and_api() -> None:
    assert PROTEIN_EDGE_WINDOW_KIND == "mania_protein_edge_window_aggregation"
    assert PROTEIN_EDGE_WINDOW_SCHEMA_VERSION == (
        "mania.protein_edge_window_aggregation.v0.1"
    )
    assert issubclass(ProteinEdgeWindowAggregationError, ValueError)
    assert get_args(ProteinEdgeWindowAggregationStatus) == ("complete", "partial")
    assert aggregation.__all__ == [
        "PROTEIN_EDGE_WINDOW_KIND",
        "PROTEIN_EDGE_WINDOW_SCHEMA_VERSION",
        "ProteinEdgeWindowAggregation",
        "ProteinEdgeWindowAggregationError",
        "ProteinEdgeWindowAggregationStatus",
        "ProteinEdgeWindowMetric",
        "WindowProteinEdgeStatistics",
        "aggregate_protein_edges_by_window",
    ]
    signature = inspect.signature(aggregate_protein_edges_by_window)
    assert tuple(signature.parameters) == (
        "sampling_plan",
        "window_plan",
        "contacts_result",
    )
    assert (
        signature.parameters["contacts_result"].kind == inspect.Parameter.KEYWORD_ONLY
    )


def test_frozen_models_field_order_and_json_independence() -> None:
    expected_metric = (
        "window_id",
        "window_index",
        "source_residue_index",
        "target_residue_index",
        "source_residue_id",
        "target_residue_id",
        "source_resname",
        "target_resname",
        "source_segid",
        "target_segid",
        "edge_type",
        "n_resolved_frames_in_window",
        "n_contact_frames",
        "occupancy",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
        "edge_weight",
    )
    expected_window = (
        "window_id",
        "window_index",
        "requested_sample_count",
        "resolved_frame_count",
        "missing_sample_count",
        "coverage_fraction",
        "edge_count",
        "edges",
    )
    expected_root = (
        "schema_version",
        "kind",
        "status",
        "execution_condition",
        "window_count",
        "observed_edge_row_count",
        "windows",
    )
    for record, expected in (
        (metric(), expected_metric),
        (statistics(), expected_window),
        (root(), expected_root),
    ):
        assert tuple(f.name for f in fields(record)) == expected
        assert tuple(record.to_dict()) == expected
        with pytest.raises(FrozenInstanceError):
            setattr(record, expected[0], "changed")
        assert serialized(record) == serialized(record)
    original = root()
    data = original.to_dict()
    assert tuple(data["windows"][0]) == expected_window
    assert tuple(data["windows"][0]["edges"][0]) == expected_metric
    data["windows"][0]["edges"].clear()
    assert original == root()
    for name in ("schema_version", "kind"):
        with pytest.raises(ValueError, match="init=False"):
            replace(root(), **{name: "changed"})


@pytest.mark.parametrize(
    ("missing", "positive", "denominator", "occupancy", "mean", "maximum"),
    [
        ((), (0, 1, 2, 4), 5, 0.8, 0.05, 0.1),  # Scientific smoke.
        ((2,), (0, 1, 3, 4), 4, 1.0, 0.05, 0.05),
        ((), (0, 1, 3, 4), 5, 0.8, 0.05, 0.05),
    ],
)
def test_missing_and_resolved_absence_scientific_smoke(
    missing,
    positive,
    denominator,
    occupancy,
    mean,
    maximum,
) -> None:
    plan, window_plan = plans(missing=missing)
    result = aggregate(
        plan, window_plan, contact_result(plan, {i: (pair(),) for i in positive})
    )
    window = result.windows[0]
    (edge,) = window.edges
    assert (window.requested_sample_count, window.resolved_frame_count) == (
        5,
        denominator,
    )
    assert window.missing_sample_count == len(missing)
    assert window.coverage_fraction == denominator / 5
    assert edge.n_resolved_frames_in_window == denominator
    assert edge.n_contact_frames == 4
    assert edge.occupancy == edge.edge_weight == occupancy
    assert edge.n_contact_episodes == 2
    assert edge.mean_episode_length_ns == mean
    assert edge.max_episode_length_ns == maximum
    assert result.status == ("partial" if missing else "complete")


def test_all_positive_source_stride_does_not_break_episode() -> None:
    plan, window_plan = plans(indexes=(2, 40, 300, 550, 900))
    result = aggregate(plan, window_plan)
    (edge,) = result.windows[0].edges
    assert result.status == "complete"
    assert result.execution_condition == "legacy-routing-name"
    assert (edge.n_contact_frames, edge.n_contact_episodes) == (5, 1)
    assert edge.occupancy == edge.edge_weight == 1.0
    assert edge.mean_episode_length_ns == edge.max_episode_length_ns == 0.2


def test_single_frame_episode_has_zero_lifetime() -> None:
    plan, window_plan = plans()
    result = aggregate(plan, window_plan, contact_result(plan, {2: (pair(),)}))
    (edge,) = result.windows[0].edges
    assert (edge.n_contact_frames, edge.n_contact_episodes) == (1, 1)
    assert edge.occupancy == edge.edge_weight == 0.2
    assert edge.mean_episode_length_ns == edge.max_episode_length_ns == 0.0


def test_no_contact_is_sparse_empty_scientific_absence() -> None:
    plan, window_plan = plans()
    result = aggregate(plan, window_plan, contact_result(plan, {}))
    assert result.status == "complete"
    assert result.observed_edge_row_count == 0
    assert result.windows[0].resolved_frame_count == 5
    assert result.windows[0].edge_count == 0
    assert result.windows[0].edges == ()
    assert result.to_dict()["windows"][0]["edges"] == []


def test_edge_in_first_window_does_not_create_second_window_zero_row() -> None:
    plan, window_plan = plans(9, length=0.2)
    result = aggregate(plan, window_plan, contact_result(plan, {3: (pair(),)}))
    assert result.window_count == 2
    assert result.observed_edge_row_count == 1
    assert result.windows[0].edges[0].occupancy == 0.25
    assert result.windows[1].edges == ()


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        (0.2, ((4, 2, 0.5, 0.05), (5, 2, 0.4, 0.05))),
        (0.1, ((4, 2, 0.5, 0.05), (4, 4, 1.0, 0.15), (5, 2, 0.4, 0.05))),
    ],
)
def test_window_boundaries_and_overlap_are_independent(step, expected) -> None:
    plan, window_plan = plans(9, length=0.2, step=step)
    result = aggregate(
        plan, window_plan, contact_result(plan, {i: (pair(),) for i in (2, 3, 4, 5)})
    )
    assert tuple(w.window_id for w in result.windows) == tuple(
        w.window_id for w in window_plan.windows
    )
    for window, (denominator, positive, occupancy, lifetime) in zip(
        result.windows, expected, strict=True
    ):
        (edge,) = window.edges
        assert edge.n_resolved_frames_in_window == denominator
        assert edge.n_contact_frames == positive
        assert edge.occupancy == edge.edge_weight == occupancy
        assert edge.n_contact_episodes == 1
        assert edge.mean_episode_length_ns == edge.max_episode_length_ns == lifetime


def test_interaction_types_remain_separate_with_independent_presence() -> None:
    plan, window_plan = plans()
    hbond = pair(edge_type="hbond")
    result = aggregate(
        plan,
        window_plan,
        contact_result(
            plan,
            {
                0: (pair(), hbond),
                1: (pair(),),
                2: (hbond,),
            },
        ),
    )
    hydrogen, generic = result.windows[0].edges
    assert (hydrogen.edge_type, generic.edge_type) == ("hbond", "residue_contact")
    assert hydrogen.occupancy == generic.occupancy == 0.4
    assert (hydrogen.n_contact_episodes, generic.n_contact_episodes) == (2, 1)
    assert hydrogen.max_episode_length_ns == 0.0
    assert generic.max_episode_length_ns == 0.05


def test_reverse_orientation_and_duplicate_records_are_frame_presence() -> None:
    plan, window_plan = plans()
    original = pair()
    duplicate = replace(original, minimum_distance=1.0)
    result = aggregate(
        plan,
        window_plan,
        contact_result(
            plan,
            {
                0: (reverse(original), original, duplicate),
                1: (reverse(duplicate),),
                2: (original,),
            },
        ),
    )
    (edge,) = result.windows[0].edges
    assert edge.n_contact_frames == 3
    assert edge.occupancy == 0.6
    assert edge.n_contact_episodes == 1
    for name in (
        "source_residue_index",
        "target_residue_index",
        "source_residue_id",
        "target_residue_id",
        "source_resname",
        "target_resname",
        "source_segid",
        "target_segid",
    ):
        assert getattr(edge, name) == getattr(original, name)


def test_equal_residue_ids_across_segments_do_not_merge_internal_pairs() -> None:
    plan, window_plan = plans()
    first = pair(source_residue_id=1, target_residue_id=2)
    second = replace(
        first,
        source_residue_index=11,
        target_residue_index=17,
        source_segid="C",
        target_segid="D",
    )
    result = aggregate(plan, window_plan, contact_result(plan, {0: (second, first)}))
    assert [
        (e.source_residue_index, e.target_residue_index)
        for e in result.windows[0].edges
    ] == [(1, 7), (11, 17)]


@pytest.mark.parametrize("same_frame", [True, False])
@pytest.mark.parametrize(
    "changes",
    [
        {"source_residue_id": 3},
        {"target_residue_id": "3"},
        {"source_resname": "VAL"},
        {"target_resname": "VAL"},
        {"source_segid": None},
        {"target_segid": "C"},
    ],
)
def test_conflicting_metadata_fails_within_and_across_frames(
    same_frame, changes
) -> None:
    plan, window_plan = plans()
    conflicting = reverse(pair(**changes))
    observed = (
        {0: (pair(), conflicting)}
        if same_frame
        else {
            0: (pair(),),
            1: (conflicting,),
        }
    )
    with pytest.raises(ProteinEdgeWindowAggregationError, match="metadata must agree"):
        aggregate(plan, window_plan, contact_result(plan, observed))


def test_detection_and_frame_order_do_not_affect_serialization() -> None:
    plan, window_plan = plans()
    observations = (
        pair(edge_type="ionic"),
        pair(target_residue_index=9),
        pair(source_residue_index=0),
        pair(),
        pair(edge_type="hbond"),
    )
    result = contact_result(plan, {0: observations, 1: tuple(reversed(observations))})
    reordered = replace(
        result,
        frame_results=tuple(
            replace(frame, contacts=tuple(reversed(frame.contacts)))
            for frame in reversed(result.frame_results)
        ),
    )
    actual = aggregate(plan, window_plan, result)
    assert serialized(actual) == serialized(aggregate(plan, window_plan, reordered))
    assert [
        (e.edge_type, e.source_residue_index, e.target_residue_index)
        for e in actual.windows[0].edges
    ] == [
        ("hbond", 1, 7),
        ("ionic", 1, 7),
        ("residue_contact", 0, 7),
        ("residue_contact", 1, 7),
        ("residue_contact", 1, 9),
    ]


@pytest.mark.parametrize("missing", [(0, 1, 2), (0, 1)])
def test_no_95_percent_release_rule(missing) -> None:
    plan, window_plan = plans(50, missing=missing)
    result = aggregate(plan, window_plan)
    assert result.status == "partial"
    assert result.windows[0].coverage_fraction == (50 - len(missing)) / 50
    assert result.windows[0].edges[0].occupancy == 1.0


def test_partial_sampling_with_complete_window_plan_stays_partial() -> None:
    plan, window_plan = plans(5, missing=(4,), length=0.15)
    assert (plan.status, window_plan.status) == ("partial", "complete")
    assert aggregate(plan, window_plan).status == "partial"


def test_empty_resolved_window_preserves_missing_coverage() -> None:
    plan, window_plan = plans(5, missing=(0, 1), length=0.1)
    result = aggregate(plan, window_plan)
    empty = result.windows[0]
    assert result.status == "partial"
    assert (
        empty.requested_sample_count,
        empty.resolved_frame_count,
        empty.missing_sample_count,
        empty.coverage_fraction,
    ) == (2, 0, 2, 0.0)
    assert empty.edge_count == 0
    assert empty.edges == ()


def test_zero_requested_targets_use_accepted_zero_coverage() -> None:
    plan, window_plan = plans(5, length=0.02)
    assert plan.status == "complete"
    assert window_plan.status == "partial"
    result = aggregate(plan, window_plan)
    assert result.status == "partial"
    empty = next(w for w in result.windows if not w.requested_sample_count)
    assert empty.resolved_frame_count == empty.missing_sample_count == 0
    assert empty.coverage_fraction == 0.0
    assert empty.edges == ()


@pytest.mark.parametrize("case", ["missing", "extra", "same_count_wrong_index"])
def test_exact_selected_frame_coverage_required(case) -> None:
    plan, window_plan = plans()
    result = contact_result(plan)
    extra = replace(result.frame_results[0], frame_index=999)
    frames = {
        "missing": result.frame_results[:-1],
        "extra": (*result.frame_results, extra),
        "same_count_wrong_index": (*result.frame_results[:-1], extra),
    }[case]
    with pytest.raises(
        ProteinEdgeWindowAggregationError, match="exactly match selected"
    ):
        aggregate(plan, window_plan, replace(result, frame_results=frames))


@pytest.mark.parametrize("status", ["not_computed", "partial", "failed"])
def test_noncomputed_condition_status_is_not_scientific_absence(status) -> None:
    plan, window_plan = plans()
    with pytest.raises(ProteinEdgeWindowAggregationError, match="computed and passed"):
        aggregate(plan, window_plan, contact_result(plan, {}, status=status))


@pytest.mark.parametrize("scope", ["condition", "frame"])
def test_computation_issues_including_limits_are_not_absence(scope) -> None:
    plan, window_plan = plans()
    result = contact_result(plan, {})
    issue = contacts.PreprocessingContactComputationIssue(
        "computation_limit", "frame", "Untrusted detail /private/trajectory.xtc"
    )
    if scope == "condition":
        result = replace(result, issues=(issue,))
    else:
        result = replace(
            result,
            frame_results=(
                replace(result.frame_results[0], issues=(issue,)),
                *result.frame_results[1:],
            ),
        )
    with pytest.raises(ProteinEdgeWindowAggregationError) as error:
        aggregate(plan, window_plan, result)
    assert str(error.value) == (
        "contact computation must be computed and passed for every selected frame"
    )


def test_generic_all_selection_rejected() -> None:
    plan, window_plan = plans()
    result = contact_result(
        plan, options=contacts.PreprocessingContactDetectionOptions()
    )
    with pytest.raises(
        ProteinEdgeWindowAggregationError, match="contact_selection protein"
    ):
        aggregate(plan, window_plan, result)


@pytest.mark.parametrize("failed_input", ["sampling", "windows"])
def test_failed_physical_plans_rejected(failed_input) -> None:
    plan, window_plan = plans()
    failed_sampling, failed_windows = plans(missing=tuple(range(5)))
    with pytest.raises(ProteinEdgeWindowAggregationError, match="must not be failed"):
        aggregate(
            failed_sampling if failed_input == "sampling" else plan,
            failed_windows if failed_input == "windows" else window_plan,
            contact_result(plan),
        )


@pytest.mark.parametrize("name", ["sampling_plan", "window_plan", "contacts_result"])
@pytest.mark.parametrize("subclass", [False, True])
def test_exact_public_input_types_required(name, subclass) -> None:
    plan, window_plan = plans()
    inputs = dict(
        sampling_plan=plan,
        window_plan=window_plan,
        contacts_result=contact_result(plan),
    )
    if subclass:
        original = inputs[name]
        derived = type("Derived", (type(original),), {})
        inputs[name] = derived(
            **{f.name: getattr(original, f.name) for f in fields(original) if f.init}
        )
    else:
        inputs[name] = {}
    with pytest.raises(ProteinEdgeWindowAggregationError, match="must be exact"):
        aggregate_protein_edges_by_window(**inputs)


@pytest.mark.parametrize("change", ["sources", "effective_time", "missing", "bounds"])
def test_window_sampling_mismatch_fails_even_with_no_edges(change) -> None:
    plan, window_plan = plans()
    if change == "missing":
        _, window_plan = plans(missing=(2,))
    elif change == "bounds":
        window_plan = replace(window_plan, requested_production_end_ns=5.23)
    else:
        window = window_plan.windows[0]
        changes = {
            "sources": {"source_frame_indexes": (501, 505, 510, 515, 520)},
            "effective_time": {"effective_start_time_ps": 5000.000001},
        }[change]
        window_plan = replace(window_plan, windows=(replace(window, **changes),))
    with pytest.raises(ProteinEdgeWindowAggregationError):
        aggregate(plan, window_plan, contact_result(plan, {}))


def test_backbone_observations_never_enter_dynamic_edges() -> None:
    plan, window_plan = plans()
    result = contact_result(plan, {0: (pair(),)})
    backbone = contacts.PreprocessingBackboneObservation(1, 2, "ALA", "GLY", 3.5)
    augmented = replace(
        result,
        frame_results=tuple(
            replace(frame, backbone_observations=(backbone,))
            for frame in result.frame_results
        ),
    )
    assert serialized(aggregate(plan, window_plan, augmented)) == serialized(
        aggregate(plan, window_plan, result)
    )
    only_backbone = replace(
        augmented,
        frame_results=tuple(
            replace(frame, contacts=()) for frame in augmented.frame_results
        ),
    )
    assert aggregate(plan, window_plan, only_backbone).windows[0].edges == ()


def test_actual_times_and_episode_engine_reuse(monkeypatch) -> None:
    actual_times = (5000.000001, 5050.000002, 5100.000003, 5150.000004, 5200.000005)
    plan, window_plan = plans(times=actual_times)
    result = contact_result(plan, {i: (pair(),) for i in (0, 1, 2, 4)})
    before = tuple(serialized(model) for model in (plan, window_plan, result))
    calls = []

    def observed_engine(sampling_plan, window, *, contact_source_frame_indexes):
        summary = episodes.compute_window_contact_episodes(
            sampling_plan,
            window,
            contact_source_frame_indexes=contact_source_frame_indexes,
        )
        calls.append((window.window_id, contact_source_frame_indexes, summary))
        return summary

    monkeypatch.setattr(aggregation, "compute_window_contact_episodes", observed_engine)
    aggregated = aggregate(plan, window_plan, result)
    (edge,) = aggregated.windows[0].edges
    assert any(not indexes for _, indexes, _ in calls)
    (summary,) = (
        summary for _, indexes, summary in calls if indexes == (500, 505, 510, 520)
    )
    for name in (
        "n_contact_frames",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
    ):
        assert getattr(edge, name) == getattr(summary, name)
    assert edge.max_episode_length_ns == 0.100000002
    assert edge.mean_episode_length_ns == 0.050000001
    assert tuple(serialized(model) for model in (plan, window_plan, result)) == before


def test_decimal_ratio_independent_of_caller_context_and_exact_validation() -> None:
    plan, window_plan = plans(3)
    result = contact_result(plan, {0: (pair(),)})
    expected = serialized(aggregate(plan, window_plan, result))
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        context.clear_flags()
        actual = aggregate(plan, window_plan, result)
        assert serialized(actual) == expected
        assert not context.flags[Inexact]
        assert not context.flags[Rounded]
    (edge,) = actual.windows[0].edges
    assert edge.occupancy == edge.edge_weight == 1 / 3
    for occupancy in (nextafter(edge.occupancy, 0), nextafter(edge.occupancy, 1)):
        with pytest.raises(ProteinEdgeWindowAggregationError, match="Decimal"):
            replace(edge, occupancy=occupancy, edge_weight=occupancy)


@pytest.mark.parametrize(
    "changes",
    [
        {"window_id": ""},
        {"window_id": " window_0001"},
        {"window_id": None},
        {"window_index": -1},
        {"window_index": True},
        {"source_residue_index": -1},
        {"source_residue_index": True},
        {"target_residue_index": 1},
        {"target_residue_index": 0},
        {"target_residue_index": False},
        {"target_residue_index": 2.0},
        {"source_residue_id": True},
        {"target_residue_id": 1.5},
        {"source_residue_id": " "},
        {"target_residue_id": " 1"},
        {"source_resname": ""},
        {"target_resname": " LYS"},
        {"source_segid": ""},
        {"target_segid": 1},
        {"edge_type": ""},
        {"edge_type": " hbond"},
        {"n_resolved_frames_in_window": 0},
        {"n_resolved_frames_in_window": True},
        {"n_resolved_frames_in_window": -1},
        {"n_contact_frames": 0},
        {"n_contact_frames": 6},
        {"n_contact_frames": True},
        {"occupancy": 0},
        {"occupancy": 1.1},
        {"occupancy": 0.7},
        {"occupancy": float("nan")},
        {"occupancy": True},
        {"n_contact_episodes": 0},
        {"n_contact_episodes": 5},
        {"n_contact_episodes": True},
        {"mean_episode_length_ns": None},
        {"max_episode_length_ns": None},
        {"mean_episode_length_ns": -1},
        {"mean_episode_length_ns": True},
        {"max_episode_length_ns": float("inf")},
        {"mean_episode_length_ns": float("nan")},
        {"max_episode_length_ns": 10**400},
        {"max_episode_length_ns": 0.01},
        {"edge_weight": 0.81},
        {"edge_weight": float("nan")},
        {"edge_weight": True},
    ],
)
def test_invalid_metric_models_rejected(changes) -> None:
    with pytest.raises(ProteinEdgeWindowAggregationError):
        replace(metric(), **changes)


@pytest.mark.parametrize("residue_id", [None, -5, 0, "12A"])
def test_optional_residue_metadata_preserves_int_string_none(residue_id) -> None:
    edge = replace(
        metric(),
        source_residue_id=residue_id,
        target_residue_id=residue_id,
        source_segid=None,
        target_segid=None,
    )
    assert edge.to_dict()["source_residue_id"] == residue_id
    assert edge.to_dict()["target_residue_id"] == residue_id
    assert edge.to_dict()["source_segid"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"window_id": "window_0002"},
        {"window_index": True},
        {"requested_sample_count": 6},
        {"resolved_frame_count": 4},
        {"missing_sample_count": -1},
        {"edge_count": True},
        {"edge_count": 0},
        {"coverage_fraction": 0.8},
        {"coverage_fraction": float("nan")},
        {"coverage_fraction": True},
        {"edges": []},
        {"edges": ({},)},
        {"edges": (replace(metric(), window_index=1),)},
        {
            "edges": (
                replace(
                    metric(), n_resolved_frames_in_window=4, occupancy=1, edge_weight=1
                ),
            )
        },
        {"edge_count": 2, "edges": (metric(), metric())},
        {"edge_count": 2, "edges": (metric(), replace(metric(), edge_type="hbond"))},
        {
            "requested_sample_count": 0,
            "resolved_frame_count": 0,
            "coverage_fraction": 0,
        },
    ],
)
def test_invalid_window_statistics_rejected(changes) -> None:
    with pytest.raises(ProteinEdgeWindowAggregationError):
        replace(statistics(), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"execution_condition": " "},
        {"window_count": True},
        {"window_count": 2},
        {"observed_edge_row_count": True},
        {"observed_edge_row_count": 0},
        {"windows": []},
        {"windows": ({},)},
        {
            "window_count": 2,
            "observed_edge_row_count": 2,
            "windows": (statistics(), statistics()),
        },
    ],
)
def test_invalid_root_models_rejected(changes) -> None:
    with pytest.raises(ProteinEdgeWindowAggregationError):
        replace(root(), **changes)


def test_root_window_order_rejected() -> None:
    plan, window_plan = plans(9, length=0.2)
    result = aggregate(plan, window_plan)
    with pytest.raises(ProteinEdgeWindowAggregationError, match="consecutive Stage 27"):
        replace(result, windows=tuple(reversed(result.windows)))


def test_pure_aggregation_without_io_detection_matching_or_replanning(
    monkeypatch,
) -> None:
    plan, window_plan = plans(missing=(2,))
    result = contact_result(plan)
    empty = contact_result(plan, {})
    imports = set()
    for node in ast.walk(ast.parse(inspect.getsource(aggregation))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= {
        "dataclasses",
        "decimal",
        "math",
        "typing",
        "mania.preprocessing.contact_episodes",
        "mania.preprocessing.physical_time_sampling",
        "mania.preprocessing.physical_time_windows",
        "mania.preprocessing.trajectory_contacts",
    }

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "aggregation attempted an operation outside its pure boundary"
        )

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "MDAnalysis",
            "numpy",
            "subprocess",
            "time",
            "datetime",
        }:
            forbidden()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "__import__", guarded_import)
        for target, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (Path, ("open",)),
            (subprocess, ("Popen", "run", "check_output")),
            (time, ("time", "monotonic", "perf_counter", "sleep")),
            (
                sampling,
                ("resolve_physical_time_sampling", "_matches", "_requested_times"),
            ),
            (windows, ("plan_physical_time_windows", "_make_window")),
            (
                contacts,
                (
                    "compute_condition_contacts",
                    "_minimum_distance",
                    "observe_pbc_timestep_dimensions",
                ),
            ),
            (
                contacts.trajectory_manifest_loader,
                ("load_manifest_condition_runtimes",),
            ),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        actual = aggregate(plan, window_plan, result)
        assert actual.windows[0].edges[0].occupancy == 1.0
        assert actual.windows[0].edges[0].n_contact_episodes == 2
        assert aggregate(plan, window_plan, empty).windows[0].edges == ()
        assert serialized(actual) == serialized(actual)
