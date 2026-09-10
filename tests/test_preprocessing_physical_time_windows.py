"""Synthetic contract and purity regressions for the standalone Stage 27.B API."""

import ast
import builtins
import copy
import inspect
import io
import json
import math
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path
from typing import get_args

import pytest

from mania.dataset_identity import DatasetTemporalParameters
from mania.preprocessing import physical_time_sampling as sampling
from mania.preprocessing import physical_time_windows as windows
from mania.preprocessing.physical_time_sampling import (
    MissingPhysicalTimeSample,
    PhysicalTimeSourceFrame,
    ResolvedPhysicalTimeSamplingPlan,
    resolve_physical_time_sampling,
)
from mania.preprocessing.physical_time_windows import (
    PHYSICAL_TIME_WINDOW_KIND,
    PHYSICAL_TIME_WINDOW_SCHEMA_VERSION,
    WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE,
    WINDOW_OVERLAP_PERCENT_REL_TOLERANCE,
    PhysicalTimeWindowPlanningIssue,
    PhysicalTimeWindowPlanStatus,
    PhysicalTimeWindowStatus,
    plan_physical_time_windows,
)


def temporal(**changes):
    return DatasetTemporalParameters(
        **{
            "production_start_ns": 0,
            "production_end_ns": 10,
            "frame_stride_ps": 1000,
            "window_length_ns": 5,
            "window_step_ns": 5,
            "overlap_percent": 0,
            **changes,
        }
    )


def axis(times=None):
    times = range(0, 10001, 1000) if times is None else times
    return tuple(PhysicalTimeSourceFrame(100 + i * 3, t) for i, t in enumerate(times))


def resolved(request=None, source=None):
    return resolve_physical_time_sampling(
        axis() if source is None else source,
        temporal=temporal() if request is None else request,
    )


def plan(request=None, source=None):
    request = temporal() if request is None else request
    return plan_physical_time_windows(resolved(request, source), temporal=request)


def boundaries(result):
    return [
        (w.requested_start_ns, w.requested_end_ns, w.right_endpoint_inclusive)
        for w in result.windows
    ]


def codes(result):
    return [issue.code for issue in result.issues]


def test_constants_statuses_and_public_api() -> None:
    assert PHYSICAL_TIME_WINDOW_SCHEMA_VERSION == "mania.physical_time_windows.v0.1"
    assert PHYSICAL_TIME_WINDOW_KIND == "mania_physical_time_windows"
    assert WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE == 1e-6
    assert WINDOW_OVERLAP_PERCENT_REL_TOLERANCE == 1e-9
    assert get_args(PhysicalTimeWindowStatus) == ("complete", "partial", "empty")
    assert get_args(PhysicalTimeWindowPlanStatus) == ("complete", "partial", "failed")
    assert set(windows.__all__) == {
        "PHYSICAL_TIME_WINDOW_SCHEMA_VERSION",
        "PHYSICAL_TIME_WINDOW_KIND",
        "WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE",
        "WINDOW_OVERLAP_PERCENT_REL_TOLERANCE",
        "PhysicalTimeWindowStatus",
        "PhysicalTimeWindowPlanStatus",
        "ResolvedPhysicalTimeWindow",
        "PhysicalTimeWindowPlanningIssue",
        "ResolvedPhysicalTimeWindowPlan",
        "plan_physical_time_windows",
    }


def test_zero_overlap_shared_boundary_and_final_endpoint() -> None:
    result = plan()
    assert result.status == "complete"
    assert not result.issues
    assert boundaries(result) == [(0, 5, False), (5, 10, True)]
    first, last = result.windows
    assert (first.window_index, first.window_id) == (0, "window_0001")
    assert (last.window_index, last.window_id) == (1, "window_0002")
    assert first.requested_sample_indexes == tuple(range(5))
    assert last.requested_sample_indexes == tuple(range(5, 11))
    assert first.selected_requested_sample_indexes == first.requested_sample_indexes
    assert last.selected_requested_sample_indexes == last.requested_sample_indexes
    assert not set(first.source_frame_indexes) & set(last.source_frame_indexes)
    assert result.total_window_sampled_frame_count == 11
    assert result.total_window_requested_sample_count == 11
    assert result.total_window_missing_sample_count == 0
    assert result.window_count == result.complete_window_count == 2
    assert result.windows_with_samples_count == 2
    assert result.partial_window_count == result.empty_window_count == 0


def test_half_overlap_intentionally_shares_source_frames() -> None:
    request = temporal(window_step_ns=2.5, overlap_percent=50)
    sampling_plan = resolved(request)
    result = plan_physical_time_windows(sampling_plan, temporal=request)
    assert result.status == "complete"
    assert result.implied_overlap_percent == result.requested_overlap_percent == 50
    assert boundaries(result) == [(0, 5, False), (2.5, 7.5, False), (5, 10, True)]
    assert [w.requested_sample_indexes for w in result.windows] == [
        (0, 1, 2, 3, 4),
        (3, 4, 5, 6, 7),
        (5, 6, 7, 8, 9, 10),
    ]
    assert (
        result.total_window_sampled_frame_count
        == 16
        > sampling_plan.sampled_frame_count
    )
    assert set(result.windows[0].source_frame_indexes) & set(
        result.windows[1].source_frame_indexes
    ) == {109, 112}


def test_quarter_overlap_omits_trailing_incomplete_window() -> None:
    result = plan(temporal(window_length_ns=4, window_step_ns=3, overlap_percent=25))
    assert result.status == "complete"
    assert boundaries(result) == [(0, 4, False), (3, 7, False), (6, 10, True)]
    assert result.window_count == 3
    assert result.windows[-1].requested_sample_indexes == (6, 7, 8, 9, 10)


def test_uncovered_tail_does_not_get_clamped_or_change_complete_status() -> None:
    result = plan(temporal(window_length_ns=4, window_step_ns=4))
    assert boundaries(result) == [(0, 4, False), (4, 8, False)]
    assert result.status == "complete"
    assert result.total_window_requested_sample_count == 8
    assert all(10 not in w.requested_sample_indexes for w in result.windows)


def test_decimal_starts_and_membership_ignore_caller_decimal_context() -> None:
    request = temporal(
        production_start_ns=0.1,
        production_end_ns=1,
        frame_stride_ps=100,
        window_length_ns=0.2,
        window_step_ns=0.1,
        overlap_percent=50,
    )
    sampling_plan = resolved(request, axis(range(100, 1001, 100)))
    expected = plan_physical_time_windows(sampling_plan, temporal=request)
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        result = plan_physical_time_windows(sampling_plan, temporal=request)
    assert result == expected
    assert [w.requested_start_ns for w in result.windows] == [
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
    ]
    assert boundaries(result)[-1] == (0.8, 1, True)
    assert result.windows[-1].requested_sample_indexes == (7, 8, 9)


@pytest.mark.parametrize(
    "length,step,overlap,code",
    [
        (5, 2.5, 25, "inconsistent_window_overlap"),
        (5, 6, 0, "invalid_window_step"),
    ],
)
def test_inconsistent_schedule_fails_without_rewriting(length, step, overlap, code):
    request = temporal(
        window_length_ns=length, window_step_ns=step, overlap_percent=overlap
    )
    result = plan(request)
    assert result.status == "failed"
    assert result.windows == ()
    assert result.window_count == 0
    assert codes(result) == [code]
    assert (
        result.requested_window_length_ns,
        result.requested_window_step_ns,
        result.requested_overlap_percent,
    ) == (length, step, overlap)
    assert result.implied_overlap_percent == (50 if step == 2.5 else None)
    json.dumps(result.to_dict(), allow_nan=False)


def test_zero_step_is_rejected_by_temporal_and_defensively_by_planner() -> None:
    with pytest.raises(ValueError):
        temporal(window_step_ns=0)
    # model_copy explicitly bypasses Pydantic validation; no accepted model changes.
    request = temporal().model_copy(update={"window_step_ns": 0})
    result = plan_physical_time_windows(resolved(), temporal=request)
    assert result.status == "failed"
    assert codes(result) == ["invalid_window_step"]
    assert result.requested_window_step_ns == 0
    assert result.implied_overlap_percent is None
    assert not result.windows


@pytest.mark.parametrize(
    "offset,expected", [(0.99e-6, "complete"), (1.01e-6, "failed")]
)
def test_overlap_tolerance_only_handles_representation(offset, expected) -> None:
    request = temporal(window_step_ns=2.5, overlap_percent=50 + offset)
    result = plan(request)
    assert result.status == expected
    assert result.requested_overlap_percent == request.overlap_percent
    assert result.requested_window_step_ns == 2.5
    assert result.requested_window_length_ns == 5
    assert result.implied_overlap_percent == 50


@pytest.mark.parametrize(
    "change",
    [
        {"production_start_ns": 1},
        {"production_end_ns": 11},
        {"frame_stride_ps": 500},
        {"production_end_ns": 10.0000000001},
    ],
)
def test_sampling_contract_mismatch_is_exact_and_serializable(change) -> None:
    result = plan_physical_time_windows(resolved(), temporal=temporal(**change))
    assert result.status == "failed"
    assert codes(result) == ["sampling_contract_mismatch"]
    assert result.windows == ()
    json.dumps(result.to_dict(), allow_nan=False)


def test_normalized_integer_and_float_request_values_agree() -> None:
    result = plan_physical_time_windows(
        resolved(),
        temporal=temporal(
            production_start_ns=0.0,
            production_end_ns=10.0,
            frame_stride_ps=1000.0,
        ),
    )
    assert result.status == "complete"


def test_no_full_windows_under_exact_decimal_duration() -> None:
    # Binary subtraction admits this length in the unchanged temporal model;
    # the exact requested Decimal interval is shorter than the requested length.
    request = temporal(
        production_start_ns=0.3,
        production_end_ns=0.4,
        frame_stride_ps=100,
        window_length_ns=0.10000000000000002,
        window_step_ns=0.10000000000000002,
    )
    result = plan(request, axis([300, 400]))
    assert result.status == "failed"
    assert codes(result) == ["no_full_windows"]
    assert result.windows == ()


@pytest.mark.parametrize("missing_index,affected", [(2, [0]), (5, [1]), (10, [1])])
def test_one_missing_sample_affects_only_its_assigned_window(missing_index, affected):
    result = plan(
        source=axis(t for t in range(0, 10001, 1000) if t != missing_index * 1000)
    )
    assert result.status == "partial"
    assert result.partial_window_count == 1
    assert codes(result) == ["partial_windows_present"]
    assert [w.window_index for w in result.windows if w.status == "partial"] == affected
    window = result.windows[affected[0]]
    assert window.missing_requested_sample_indexes == (missing_index,)
    assert missing_index in window.requested_sample_indexes
    assert missing_index not in window.selected_requested_sample_indexes
    assert window.missing_sample_count == 1
    assert window.coverage_fraction == (window.requested_sample_count - 1) / (
        window.requested_sample_count
    )


def test_missing_target_in_overlap_affects_multiple_windows() -> None:
    request = temporal(window_step_ns=2.5, overlap_percent=50)
    result = plan(request, axis(t for t in range(0, 10001, 1000) if t != 4000))
    assert [w.status for w in result.windows] == ["partial", "partial", "complete"]
    assert [w.missing_requested_sample_indexes for w in result.windows] == [
        (4,),
        (4,),
        (),
    ]
    assert result.total_window_missing_sample_count == 2
    assert boundaries(result) == boundaries(plan(request))


def test_empty_window_with_missing_targets_retains_full_schedule() -> None:
    result = plan(source=axis(range(5000, 10001, 1000)))
    assert result.status == "partial"
    first, last = result.windows
    assert first.status == "empty"
    assert first.requested_sample_count == first.missing_sample_count == 5
    assert first.sampled_frame_count == first.coverage_fraction == 0
    assert first.effective_start_time_ps is first.effective_end_time_ps is None
    assert first.requested_sample_indexes == first.missing_requested_sample_indexes
    assert first.source_frame_indexes == first.selected_requested_sample_indexes == ()
    assert last.status == "complete"
    assert result.empty_window_count == 1
    assert codes(result) == ["empty_windows_present"]


def test_zero_target_windows_are_kept_and_have_zero_coverage() -> None:
    request = temporal(frame_stride_ps=10000, window_length_ns=2, window_step_ns=2)
    result = plan(request)
    assert result.window_count == 5
    assert [w.status for w in result.windows] == [
        "complete",
        "empty",
        "empty",
        "empty",
        "complete",
    ]
    assert result.status == "partial"
    for window in result.windows[1:-1]:
        assert (
            window.requested_sample_count,
            window.sampled_frame_count,
            window.missing_sample_count,
            window.coverage_fraction,
        ) == (0, 0, 0, 0)
        assert window.requested_sample_indexes == ()
        assert window.effective_start_time_ps is window.effective_end_time_ps is None


@pytest.mark.parametrize("source", [(), axis([20000])])
def test_all_windows_without_selected_samples_fail(source) -> None:
    result = plan(source=source)
    assert result.status == "failed"
    assert result.window_count == result.empty_window_count == 2
    assert result.windows_with_samples_count == 0
    assert codes(result) == ["empty_windows_present", "no_resolved_window_samples"]
    assert result.total_window_missing_sample_count == 11
    json.dumps(result.to_dict(), allow_nan=False)


def test_selected_sampling_frame_in_uncovered_tail_cannot_rescue_windows() -> None:
    request = temporal(window_length_ns=4, window_step_ns=4)
    sampling_plan = resolved(request, axis([10000]))
    assert sampling_plan.sampled_frame_count == 1
    result = plan_physical_time_windows(sampling_plan, temporal=request)
    assert result.status == "failed"
    assert result.total_window_sampled_frame_count == 0
    assert "no_resolved_window_samples" in codes(result)


def test_requested_membership_ignores_actual_float_noise_and_keeps_effective_bounds():
    times = [float(t) for t in range(0, 10001, 1000)]
    times[0] += 5e-7
    times[5] -= 5e-7
    times[10] += 5e-7
    result = plan(source=axis(times))
    assert boundaries(result) == [(0, 5, False), (5, 10, True)]
    first, last = result.windows
    assert first.requested_sample_indexes == tuple(range(5))
    assert last.requested_sample_indexes == tuple(range(5, 11))
    assert (first.effective_start_time_ps, first.effective_end_time_ps) == (
        times[0],
        4000,
    )
    assert (last.effective_start_time_ps, last.effective_end_time_ps) == (
        times[5],
        times[10],
    )
    assert last.source_frame_indexes[0] == 115


def test_requested_boundaries_are_not_broadened_by_sampling_tolerance() -> None:
    request = temporal(production_end_ns=10.0000000001)
    result = plan(request)
    assert boundaries(result) == [(0, 5, False), (5, 10, False)]
    assert result.windows[-1].requested_sample_indexes == tuple(range(5, 10))


def test_effective_bounds_observe_missing_endpoints_and_single_selected_sample() -> (
    None
):
    result = plan(source=axis([2000, 7000]))
    for window, time_ps in zip(result.windows, (2000, 7000), strict=True):
        assert window.status == "partial"
        assert window.effective_start_time_ps == window.effective_end_time_ps == time_ps
    assert boundaries(result) == [(0, 5, False), (5, 10, True)]


def test_non_contiguous_non_increasing_source_indexes_are_preserved() -> None:
    indexes = (900, 3, 78, 50, 6, 89, 27, 45, 60, 71, 83)
    source = tuple(
        PhysicalTimeSourceFrame(i, t)
        for i, t in zip(
            indexes,
            range(0, 10001, 1000),
            strict=True,
        )
    )
    result = plan(source=source)
    assert result.windows[0].source_frame_indexes == indexes[:5]
    assert result.windows[1].source_frame_indexes == indexes[5:]


def test_window_request_does_not_mutate_or_change_sampling_resolution() -> None:
    request = temporal()
    sampling_plan = resolved(request)
    before = copy.deepcopy(sampling_plan.to_dict())
    changed = temporal(window_step_ns=2.5, overlap_percent=50)
    assert resolved(changed) == sampling_plan
    assert plan_physical_time_windows(sampling_plan, temporal=request).window_count == 2
    assert plan_physical_time_windows(sampling_plan, temporal=changed).window_count == 3
    assert sampling_plan.to_dict() == before
    assert request.to_dict() == temporal().to_dict()


@pytest.mark.parametrize("sampled_count", [94, 96])
def test_no_95_percent_qc_threshold(sampled_count) -> None:
    request = temporal(production_end_ns=99, window_length_ns=99, window_step_ns=99)
    result = plan(request, axis(range(0, sampled_count * 1000, 1000)))
    assert result.status == result.windows[0].status == "partial"
    assert result.windows[0].coverage_fraction == sampled_count / 100
    assert codes(result) == ["partial_windows_present"]


def napi_request():
    return temporal(
        production_start_ns=50,
        production_end_ns=100,
        frame_stride_ps=500,
        window_length_ns=5,
        window_step_ns=2.5,
        overlap_percent=50,
    )


def test_napi2b_complete_window_smoke() -> None:
    request = napi_request()
    sampling_plan = resolved(request, axis(range(50000, 100001, 500)))
    before = sampling_plan.to_dict()
    result = plan_physical_time_windows(sampling_plan, temporal=request)
    expected_count = (
        int((Decimal("100") - Decimal("50") - Decimal("5")) // Decimal("2.5")) + 1
    )
    assert expected_count == 19
    assert result.window_count == result.complete_window_count == expected_count
    assert [w.requested_start_ns for w in result.windows] == [
        float(Decimal("50") + i * Decimal("2.5")) for i in range(expected_count)
    ]
    assert boundaries(result)[0] == (50, 55, False)
    assert boundaries(result)[-1] == (95, 100, True)
    assert result.windows[-1].requested_sample_indexes == tuple(range(90, 101))
    assert result.total_window_sampled_frame_count == 191
    assert sampling_plan.sampled_frame_count == 101
    assert sampling_plan.to_dict() == before


def test_napi2b_missing_frame_smoke() -> None:
    request = napi_request()
    source = axis(range(50000, 100001, 500))
    complete = resolved(request, source)
    sampling_plan = resolved(request, tuple(s for s in source if s.time_ps != 57500))
    assert sampling_plan.missing_samples == (MissingPhysicalTimeSample(15, 57500),)
    before = sampling_plan.to_dict()
    result = plan_physical_time_windows(sampling_plan, temporal=request)
    baseline = plan_physical_time_windows(complete, temporal=request)
    assert boundaries(result) == boundaries(baseline)
    assert result.partial_window_count == 2
    assert result.complete_window_count == 17
    assert result.total_window_missing_sample_count == 2
    assert result.total_window_sampled_frame_count == 189
    assert [w.window_index for w in result.windows if w.status == "partial"] == [2, 3]
    for actual, expected in zip(result.windows, baseline.windows, strict=True):
        if 15 in expected.requested_sample_indexes:
            assert actual.missing_requested_sample_indexes == (15,)
            assert actual.source_frame_indexes == tuple(
                i for i in expected.source_frame_indexes if i != source[15].frame_index
            )
        else:
            assert actual == expected
    assert result.windows[3].requested_start_ns == 57.5
    assert result.windows[3].effective_start_time_ps == 58000
    assert sampling_plan.to_dict() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"window_index": -1},
        {"window_index": True},
        {"window_index": 0.5},
        {"window_id": ""},
        {"window_id": " window_0001 "},
        {"window_id": 1},
        {"requested_start_ns": -1},
        {"requested_start_ns": True},
        {"requested_end_ns": 0},
        {"requested_end_ns": math.inf},
        {"right_endpoint_inclusive": 0},
        {"right_endpoint_inclusive": None},
        {"requested_sample_count": True},
        {"requested_sample_count": 4},
        {"sampled_frame_count": 4},
        {"missing_sample_count": 1},
        {"coverage_fraction": math.nan},
        {"coverage_fraction": True},
        {"coverage_fraction": 1.1},
        {"coverage_fraction": 0.9},
        {"effective_start_time_ps": None},
        {"effective_end_time_ps": None},
        {"effective_start_time_ps": 5000},
        {"effective_end_time_ps": math.inf},
        {"effective_end_time_ps": True},
        {"requested_sample_indexes": [0, 1, 2, 3, 4]},
        {"requested_sample_indexes": (0, 1, 2, 4, 3)},
        {"selected_requested_sample_indexes": (0, 1, 2, 3, 5)},
        {"selected_requested_sample_indexes": (0, 1, 2, 3, 3)},
        {"missing_requested_sample_indexes": (0,)},
        {"source_frame_indexes": (100, 100, 106, 109, 112)},
        {"source_frame_indexes": (True, 103, 106, 109, 112)},
        {"source_frame_indexes": (100,)},
        {"status": "partial"},
        {"status": "unknown"},
    ],
)
def test_window_rejects_invalid_fields(changes) -> None:
    with pytest.raises(ValueError):
        replace(plan().windows[0], **changes)


def test_window_partition_and_empty_invariants() -> None:
    partial = plan(source=axis([0, 1000, 3000, 4000])).windows[0]
    for changes in (
        {"missing_requested_sample_indexes": (3,)},
        {"selected_requested_sample_indexes": (0, 3, 1, 4)},
        {"status": "complete"},
        {"status": "empty"},
    ):
        with pytest.raises(ValueError):
            replace(partial, **changes)
    empty = plan(source=()).windows[0]
    for changes in (
        {"status": "complete"},
        {"effective_start_time_ps": 0},
        {"effective_end_time_ps": 0},
        {"coverage_fraction": 1},
    ):
        with pytest.raises(ValueError):
            replace(empty, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"status": "unknown"},
        {"window_count": True},
        {"window_count": 3},
        {"complete_window_count": 1},
        {"partial_window_count": 1},
        {"empty_window_count": 1},
        {"windows_with_samples_count": 1},
        {"total_window_requested_sample_count": 10},
        {"total_window_sampled_frame_count": 10},
        {"total_window_missing_sample_count": 1},
        {"requested_production_start_ns": -1},
        {"requested_production_end_ns": 0},
        {"requested_window_length_ns": 0},
        {"requested_window_step_ns": math.nan},
        {"requested_overlap_percent": 100},
        {"implied_overlap_percent": 1},
        {"implied_overlap_percent": True},
        {"windows": []},
        {"windows": ("bad",)},
        {"issues": []},
        {"issues": ("bad",)},
        {"issues": (PhysicalTimeWindowPlanningIssue("warning", "test", "Test.", 2),)},
    ],
)
def test_plan_rejects_inconsistent_fields(changes) -> None:
    with pytest.raises(ValueError):
        replace(plan(), **changes)


def test_plan_validates_window_ids_order_schedule_errors_and_fatal_status() -> None:
    result = plan()
    for changed_windows in (
        tuple(reversed(result.windows)),
        (replace(result.windows[0], window_id="custom"), result.windows[1]),
    ):
        with pytest.raises(ValueError):
            replace(result, windows=changed_windows)
    with pytest.raises(ValueError):
        replace(
            result, issues=(PhysicalTimeWindowPlanningIssue("error", "test", "Test."),)
        )
    invalid = plan(temporal(window_step_ns=6))
    with pytest.raises(ValueError):
        replace(invalid, issues=())
    with pytest.raises(ValueError):
        replace(invalid, windows=result.windows)


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "fatal"},
        {"code": ""},
        {"code": " x"},
        {"message": " "},
        {"message": 2},
        {"window_index": True},
        {"window_index": -1},
    ],
)
def test_issue_validation(changes) -> None:
    with pytest.raises(ValueError):
        replace(PhysicalTimeWindowPlanningIssue("warning", "test", "Test."), **changes)


def test_frozen_models_json_roundtrip_independence_and_explicit_field_order() -> None:
    result = plan()
    issue = PhysicalTimeWindowPlanningIssue("warning", "test", "Test.")
    for record in (result, result.windows[0], issue):
        with pytest.raises(FrozenInstanceError):
            setattr(record, fields(record)[0].name, None)
        assert list(record.to_dict()) == [f.name for f in fields(record)]
    assert list(result.to_dict()) == [
        "schema_version",
        "kind",
        "status",
        "requested_production_start_ns",
        "requested_production_end_ns",
        "requested_window_length_ns",
        "requested_window_step_ns",
        "requested_overlap_percent",
        "implied_overlap_percent",
        "window_count",
        "complete_window_count",
        "partial_window_count",
        "empty_window_count",
        "windows_with_samples_count",
        "total_window_requested_sample_count",
        "total_window_sampled_frame_count",
        "total_window_missing_sample_count",
        "windows",
        "issues",
    ]
    assert list(result.windows[0].to_dict()) == [
        "window_index",
        "window_id",
        "requested_start_ns",
        "requested_end_ns",
        "right_endpoint_inclusive",
        "requested_sample_count",
        "sampled_frame_count",
        "missing_sample_count",
        "coverage_fraction",
        "effective_start_time_ps",
        "effective_end_time_ps",
        "requested_sample_indexes",
        "selected_requested_sample_indexes",
        "missing_requested_sample_indexes",
        "source_frame_indexes",
        "status",
    ]
    assert list(issue.to_dict()) == ["severity", "code", "message", "window_index"]
    payload = result.to_dict()
    payload["windows"][0]["source_frame_indexes"].append(999)
    assert 999 not in result.windows[0].source_frame_indexes
    encoded = json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))
    assert json.loads(encoded) == result.to_dict()
    assert encoded == json.dumps(
        plan().to_dict(), allow_nan=False, separators=(",", ":")
    )
    with pytest.raises(ValueError, match="init=False"):
        replace(result, schema_version="other")  # Non-init identity cannot be supplied.


def test_exact_api_types_are_required() -> None:
    class TemporalSubclass(DatasetTemporalParameters):
        pass

    class SamplingSubclass(ResolvedPhysicalTimeSamplingPlan):
        pass

    sampling_plan = resolved()
    subclass = SamplingSubclass(
        **{f.name: getattr(sampling_plan, f.name) for f in fields(sampling_plan)}
    )
    for invalid in (None, {}, (), sampling_plan.to_dict(), subclass):
        with pytest.raises(ValueError, match="exact ResolvedPhysicalTimeSamplingPlan"):
            plan_physical_time_windows(invalid, temporal=temporal())
    for invalid in (
        None,
        temporal().to_dict(),
        TemporalSubclass(**temporal().to_dict()),
    ):
        with pytest.raises(ValueError, match="exact DatasetTemporalParameters"):
            plan_physical_time_windows(sampling_plan, temporal=invalid)


@pytest.mark.parametrize("damage", ["duplicate", "gap", "out_of_range"])
def test_planner_defensively_checks_authoritative_index_partition(damage) -> None:
    sampling_plan = copy.copy(resolved())
    # Deliberately bypass frozen construction solely to exercise defensive input checks.
    records = sampling_plan.selected_samples
    if damage == "duplicate":
        records = (records[0],) + records[:-1]
    elif damage == "gap":
        records = records[1:]
    else:
        records = records[:-1] + (replace(records[-1], requested_sample_index=11),)
    object.__setattr__(sampling_plan, "selected_samples", records)
    result = plan_physical_time_windows(sampling_plan, temporal=temporal())
    assert result.status == "failed"
    assert codes(result) == ["sampling_contract_mismatch"]
    assert not result.windows


def test_purity_no_second_matching_or_scientific_metrics(monkeypatch) -> None:
    request = temporal(window_step_ns=2.5, overlap_percent=50)
    sampling_plan = resolved(request)
    source_ast = ast.parse(inspect.getsource(windows))
    imports = {
        node.module for node in ast.walk(source_ast) if isinstance(node, ast.ImportFrom)
    }
    assert imports <= {
        "bisect",
        "dataclasses",
        "decimal",
        "itertools",
        "math",
        "typing",
        "mania.dataset_identity",
        "mania.preprocessing.physical_time_sampling",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(source_ast))
    accepted_import = next(
        node
        for node in ast.walk(source_ast)
        if isinstance(node, ast.ImportFrom)
        and node.module == "mania.preprocessing.physical_time_sampling"
    )
    assert {alias.name for alias in accepted_import.names} == {
        "MissingPhysicalTimeSample",
        "ResolvedPhysicalTimeSample",
        "ResolvedPhysicalTimeSamplingPlan",
    }

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Window planner must only consume accepted sampling records"
        )

    with monkeypatch.context() as patch:
        for owner, names in (
            (
                sampling,
                ("resolve_physical_time_sampling", "_requested_times", "_matches"),
            ),
            (builtins, ("open",)),
            (io, ("open",)),
            (
                Path,
                (
                    "open",
                    "glob",
                    "rglob",
                    "iterdir",
                    "stat",
                    "exists",
                    "resolve",
                    "cwd",
                ),
            ),
            (subprocess, ("run", "Popen", "check_output")),
            (time, ("time", "monotonic", "perf_counter", "sleep")),
            (os, ("getenv", "getcwd", "listdir", "scandir", "stat")),
        ):
            for name in names:
                patch.setattr(owner, name, forbidden)
        result = plan_physical_time_windows(sampling_plan, temporal=request)
        assert result.status == "complete"
        encoded = json.dumps(result.to_dict(), allow_nan=False)
    assert not any(
        term in encoded for term in ("occupancy", "lifetime", "episode", "edge_weight")
    )
