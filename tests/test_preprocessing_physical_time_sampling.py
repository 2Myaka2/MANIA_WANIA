"""Synthetic Stage 27.A sampling, validation, determinism, and purity regressions."""

import ast
import builtins
import inspect
import io
import json
import math
import os
import random
import subprocess
import time
from collections.abc import Iterable
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import get_args

import pytest

from mania.dataset_identity import DatasetTemporalParameters
from mania.preprocessing import physical_time_sampling as sampling
from mania.preprocessing.physical_time_sampling import (
    PHYSICAL_TIME_MATCH_ABS_TOLERANCE_PS,
    PHYSICAL_TIME_MATCH_REL_TOLERANCE,
    MissingPhysicalTimeSample,
    PhysicalTimeSamplingIssue,
    PhysicalTimeSamplingStatus,
    PhysicalTimeSourceFrame,
    ResolvedPhysicalTimeSample,
    ResolvedPhysicalTimeSamplingPlan,
    resolve_physical_time_sampling,
)


def temporal(**changes: float) -> DatasetTemporalParameters:
    return DatasetTemporalParameters.model_validate(
        {
            "production_start_ns": 0.0,
            "production_end_ns": 1.0,
            "frame_stride_ps": 100.0,
            "window_length_ns": 0.1,
            "window_step_ns": 0.05,
            "overlap_percent": 50.0,
        }
        | changes
    )


def axis(
    times: Iterable[float] = range(0, 1001, 100),
) -> tuple[PhysicalTimeSourceFrame, ...]:
    return tuple(PhysicalTimeSourceFrame(i, float(t)) for i, t in enumerate(times))


def resolve(source=None, **changes: float) -> ResolvedPhysicalTimeSamplingPlan:
    return resolve_physical_time_sampling(
        axis() if source is None else source, temporal=temporal(**changes)
    )


def requested_times(plan: ResolvedPhysicalTimeSamplingPlan) -> list[float]:
    records = (*plan.selected_samples, *plan.missing_samples)
    return [
        r.requested_time_ps
        for r in sorted(records, key=lambda r: r.requested_sample_index)
    ]


def test_closed_interval_and_complete_plan() -> None:
    source = axis()
    plan = resolve(source)
    assert plan.status == "complete"
    assert plan.requested_sample_count == plan.sampled_frame_count == 11
    assert plan.source_frame_count == 11
    assert plan.missing_sample_count == 0
    assert plan.missing_samples == plan.issues == ()
    assert plan.coverage_fraction == 1.0
    assert (plan.source_start_time_ps, plan.source_end_time_ps) == (0.0, 1000.0)
    assert (plan.effective_start_time_ps, plan.effective_end_time_ps) == (0.0, 1000.0)
    assert plan.effective_stride_ps == 100.0
    assert [s.source_frame_index for s in plan.selected_samples] == list(range(11))
    assert [s.actual_time_ps for s in plan.selected_samples] == requested_times(plan)
    assert all(s.time_delta_ps == 0.0 for s in plan.selected_samples)
    assert source == axis()


def test_decimal_grid_has_no_accumulated_float_drift_or_context_dependency() -> None:
    expected = [i / 10 for i in range(1000, 10001)]
    source = axis(expected)
    request = temporal(production_start_ns=0.1, frame_stride_ps=0.1)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        plan = resolve_physical_time_sampling(source, temporal=request)
        assert context.prec == 2
        assert not context.flags[Inexact]
    assert plan.status == "complete"
    assert plan.requested_sample_count == 9001
    assert requested_times(plan) == expected
    assert plan == resolve_physical_time_sampling(source, temporal=request)


def test_end_is_not_added_or_changed_when_not_grid_aligned() -> None:
    plan = resolve(frame_stride_ps=300.0)
    assert requested_times(plan) == [0.0, 300.0, 600.0, 900.0]
    assert plan.requested_production_end_ns == 1.0
    assert plan.effective_end_time_ps == 900.0
    assert plan.status == "complete"


@pytest.mark.parametrize("target", [0.0, 100.0, 1_000_000.0])
@pytest.mark.parametrize("factor", [0.99, 1.01])
@pytest.mark.parametrize("direction", [-1, 1])
def test_public_absolute_and_relative_tolerance(target, factor, direction) -> None:
    if target == 0 and direction == -1:
        return  # Negative source times are invalid, independently of matching.
    tolerance = max(1e-6, 1e-9 * target)
    actual = target + direction * factor * tolerance
    plan = resolve(
        axis([actual]),
        production_start_ns=target / 1000,
        production_end_ns=target / 1000 + 1,
        frame_stride_ps=2000,
    )
    assert plan.sampled_frame_count == (1 if factor < 1 else 0)
    if factor < 1:
        assert plan.selected_samples[0].time_delta_ps == actual - target
        assert plan.effective_start_time_ps == plan.effective_end_time_ps == actual
    else:
        assert plan.status == "failed"
        assert plan.missing_samples == (MissingPhysicalTimeSample(0, target),)


def test_effective_stride_observes_actual_spacing() -> None:
    plan = resolve(axis([0, 100.0000005, 200.0000008]), production_end_ns=0.2)
    assert plan.status == "complete"
    assert plan.effective_stride_ps == 100.0000004
    assert plan.effective_stride_ps != plan.requested_frame_stride_ps


@pytest.mark.parametrize("times", [[0, 100, 100], [200, 100, 0], [1e-7, 0]])
def test_source_time_must_increase_strictly_without_sorting(times) -> None:
    source = axis(times)
    plan = resolve(source)
    assert plan.status == "failed"
    assert plan.sampled_frame_count == 0
    assert plan.missing_sample_count == plan.requested_sample_count == 11
    issue = next(i for i in plan.issues if i.code == "non_monotonic_source_time")
    assert issue.severity == "error"
    assert issue.frame_index == (2 if times == [0, 100, 100] else 1)
    assert plan.source_start_time_ps == min(times)
    assert plan.source_end_time_ps == max(times)
    assert source == axis(times)


def test_duplicate_source_indexes_are_fatal() -> None:
    plan = resolve((PhysicalTimeSourceFrame(7, 0), PhysicalTimeSourceFrame(7, 100)))
    assert plan.status == "failed"
    assert not plan.selected_samples
    assert plan.issues[0].code == "duplicate_source_frame_index"
    assert plan.issues[0].frame_index == 7


def test_missing_middle_target_is_explicit_and_stride_is_absent() -> None:
    plan = resolve(axis(t for t in range(0, 1001, 100) if t != 500))
    assert plan.status == "partial"
    assert (plan.requested_sample_count, plan.sampled_frame_count) == (11, 10)
    assert plan.missing_sample_count == 1
    assert plan.coverage_fraction == 10 / 11
    assert plan.missing_samples == (MissingPhysicalTimeSample(5, 500.0),)
    assert plan.effective_stride_ps is None
    assert [i.code for i in plan.issues] == ["requested_samples_missing"]


def test_request_partly_outside_source_is_not_clamped() -> None:
    plan = resolve(
        axis(range(60_000, 90_001, 500)),
        production_start_ns=50,
        production_end_ns=100,
        frame_stride_ps=500,
    )
    assert plan.status == "partial"
    assert (plan.requested_production_start_ns, plan.requested_production_end_ns) == (
        50,
        100,
    )
    assert plan.requested_sample_count == 101
    assert plan.sampled_frame_count == 61
    assert plan.missing_sample_count == 40
    assert plan.coverage_fraction == 61 / 101
    assert (plan.effective_start_time_ps, plan.effective_end_time_ps) == (
        60_000,
        90_000,
    )
    assert [s.requested_time_ps for s in plan.missing_samples] == [
        *range(50_000, 60_000, 500),
        *range(90_500, 100_001, 500),
    ]
    assert plan.effective_stride_ps is None


def test_entire_request_outside_source_keeps_every_missing_target() -> None:
    plan = resolve(axis([2000, 2100]))
    assert plan.status == "failed"
    assert plan.coverage_fraction == plan.sampled_frame_count == 0
    assert plan.missing_sample_count == 11
    assert requested_times(plan) == list(range(0, 1001, 100))
    assert plan.effective_start_time_ps is plan.effective_end_time_ps is None
    assert plan.effective_stride_ps is None
    assert [i.code for i in plan.issues] == [
        "requested_samples_missing",
        "no_requested_samples_resolved",
    ]


def test_incompatible_stride_does_not_snap_to_adjacent_frames() -> None:
    plan = resolve(frame_stride_ps=250)
    assert plan.status == "partial"
    assert [s.actual_time_ps for s in plan.selected_samples] == [0, 500, 1000]
    assert [s.requested_time_ps for s in plan.missing_samples] == [250, 750]
    assert plan.requested_frame_stride_ps == 250
    assert plan.effective_stride_ps is None


def test_indexes_need_not_be_contiguous_or_increasing() -> None:
    indexes = (700, 11, 42)
    source = tuple(
        PhysicalTimeSourceFrame(i, t)
        for i, t in zip(indexes, (0, 100, 200), strict=True)
    )
    plan = resolve(source, production_end_ns=0.2)
    assert plan.status == "complete"
    assert tuple(s.source_frame_index for s in plan.selected_samples) == indexes


def test_one_requested_target_has_no_effective_stride() -> None:
    plan = resolve(axis([0, 100, 200]), frame_stride_ps=2000)
    assert plan.status == "complete"
    assert plan.requested_sample_count == plan.sampled_frame_count == 1
    assert plan.effective_stride_ps is None
    assert plan.source_frame_count == 3


def test_source_outside_production_is_retained_in_source_extent_only() -> None:
    plan = resolve(axis(range(0, 2001, 100)), production_start_ns=0.5)
    assert plan.status == "complete"
    assert plan.source_frame_count == 21
    assert (plan.source_start_time_ps, plan.source_end_time_ps) == (0, 2000)
    assert plan.sampled_frame_count == 6
    assert (plan.effective_start_time_ps, plan.effective_end_time_ps) == (500, 1000)


def test_empty_source_is_deterministic_failed_report() -> None:
    plan = resolve(())
    assert plan.status == "failed"
    assert plan.source_frame_count == plan.sampled_frame_count == 0
    assert plan.coverage_fraction == 0
    assert plan.source_start_time_ps is plan.source_end_time_ps is None
    assert plan.missing_sample_count == 11
    assert [i.code for i in plan.issues] == [
        "empty_source_time_axis",
        "requested_samples_missing",
        "no_requested_samples_resolved",
    ]
    assert plan.to_dict() == resolve(()).to_dict()


def test_multiple_frames_matching_one_target_are_fatal_without_arbitrary_selection():
    plan = resolve(axis([0, 99.9999995, 100.0000005, 200]), production_end_ns=0.2)
    assert plan.status == "failed"
    assert [s.actual_time_ps for s in plan.selected_samples] == [0, 200]
    assert plan.missing_samples == (MissingPhysicalTimeSample(1, 100),)
    assert plan.coverage_fraction == 2 / 3
    assert plan.issues[0].code == "ambiguous_time_match"
    assert plan.issues[0].requested_sample_index == 1


@pytest.mark.parametrize("times", [[0.0000005], [0, 0.0000015, 10]])
def test_one_source_matching_multiple_targets_is_never_reused(times) -> None:
    plan = resolve(
        axis(times), production_end_ns=2e-9, frame_stride_ps=1e-6, window_length_ns=1e-9
    )
    assert plan.status == "failed"
    assert not plan.selected_samples
    assert plan.missing_sample_count == 3
    assert any(i.code == "ambiguous_time_match" for i in plan.issues)


@pytest.mark.parametrize("missing_count", [6, 4])
def test_coverage_around_95_percent_does_not_apply_qc(missing_count) -> None:
    plan = resolve(axis(range(missing_count * 100, 10_000, 100)), production_end_ns=9.9)
    assert plan.requested_sample_count == 100
    assert plan.coverage_fraction == (100 - missing_count) / 100
    assert plan.status == "partial"
    assert [i.severity for i in plan.issues] == ["warning"]


def test_window_requests_are_preserved_and_operationally_inert() -> None:
    a = temporal()
    b = temporal(window_length_ns=0.7, window_step_ns=0.9, overlap_percent=91)
    before_a, before_b = a.to_dict(), b.to_dict()
    assert resolve_physical_time_sampling(axis(), temporal=a) == (
        resolve_physical_time_sampling(axis(), temporal=b)
    )
    assert a.to_dict() == before_a
    assert b.to_dict() == before_b


@pytest.mark.parametrize("value", [-1, True, False, 1.1, "1"])
def test_record_indexes_are_nonnegative_integers(value) -> None:
    for constructor in (
        lambda: PhysicalTimeSourceFrame(value, 0),
        lambda: MissingPhysicalTimeSample(value, 0),
        lambda: ResolvedPhysicalTimeSample(value, 0, 0, 0, 0),
        lambda: ResolvedPhysicalTimeSample(0, 0, value, 0, 0),
        lambda: PhysicalTimeSamplingIssue("error", "test", "Test.", frame_index=value),
        lambda: PhysicalTimeSamplingIssue(
            "error", "test", "Test.", requested_sample_index=value
        ),
    ):
        with pytest.raises(ValueError):
            constructor()


@pytest.mark.parametrize(
    "value", [-1, True, False, math.nan, math.inf, -math.inf, "1", None]
)
def test_times_are_nonnegative_finite_numbers_not_bool(value) -> None:
    for constructor in (
        lambda: PhysicalTimeSourceFrame(0, value),
        lambda: MissingPhysicalTimeSample(0, value),
        lambda: ResolvedPhysicalTimeSample(0, value, 0, 0, 0),
        lambda: ResolvedPhysicalTimeSample(0, 0, 0, value, 0),
    ):
        with pytest.raises(ValueError):
            constructor()


@pytest.mark.parametrize("delta", [True, math.nan, math.inf, -math.inf, "0", None, 0.5])
def test_sample_delta_is_finite_non_bool_and_equals_actual_minus_requested(delta):
    with pytest.raises(ValueError):
        ResolvedPhysicalTimeSample(0, 100, 0, 100, delta)


def test_sample_pair_must_match_and_signed_deltas_are_valid() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        ResolvedPhysicalTimeSample(0, 100, 0, 101, 1)
    for actual in (99.9999995, 100, 100.0000005):
        assert (
            ResolvedPhysicalTimeSample(0, 100, 5, actual, actual - 100).actual_time_ps
            == actual
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "info"},
        {"code": ""},
        {"code": 5},
        {"message": " "},
        {"message": None},
        {"requested_sample_index": -1},
    ],
)
def test_issue_validation(changes) -> None:
    with pytest.raises(ValueError):
        PhysicalTimeSamplingIssue(
            **({"severity": "error", "code": "test", "message": "Test."} | changes)
        )


def test_none_indexes_are_allowed_only_for_issues() -> None:
    assert PhysicalTimeSamplingIssue("warning", "test", "Test.").frame_index is None
    for constructor in (
        lambda: PhysicalTimeSourceFrame(None, 0),
        lambda: MissingPhysicalTimeSample(None, 0),
        lambda: ResolvedPhysicalTimeSample(None, 0, 0, 0, 0),
        lambda: ResolvedPhysicalTimeSample(0, 0, None, 0, 0),
    ):
        with pytest.raises(ValueError):
            constructor()


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "partial"},
        {"status": "failed"},
        {"status": "unknown"},
        {"source_frame_count": 1},
        {"source_frame_count": True},
        {"requested_sample_count": 0},
        {"requested_sample_count": 12},
        {"sampled_frame_count": 10},
        {"missing_sample_count": 1},
        {"coverage_fraction": 0.96},
        {"coverage_fraction": math.nan},
        {"coverage_fraction": True},
        {"coverage_fraction": 1.1},
        {"source_start_time_ps": None},
        {"source_end_time_ps": 900},
        {"source_start_time_ps": 1001},
        {"effective_start_time_ps": None},
        {"effective_end_time_ps": 900},
        {"effective_stride_ps": 99},
        {"effective_stride_ps": None},
        {"effective_stride_ps": True},
        {"requested_production_start_ns": -1},
        {"requested_production_end_ns": 0},
        {"requested_frame_stride_ps": 0},
        {"requested_frame_stride_ps": 300},
        {"match_abs_tolerance_ps": 0.001},
        {"match_rel_tolerance": 0.01},
        {"selected_samples": []},
        {"missing_samples": []},
        {"issues": []},
        {"issues": ("invalid",)},
        {
            "issues": (
                PhysicalTimeSamplingIssue(
                    "warning", "test", "Test.", requested_sample_index=11
                ),
            )
        },
    ],
)
def test_plan_rejects_inconsistent_fields(changes) -> None:
    with pytest.raises(ValueError):
        replace(resolve(), **changes)


def test_plan_rejects_wrong_grid_order_duplicate_selection_and_record_times() -> None:
    plan = resolve()
    for records in (
        tuple(reversed(plan.selected_samples)),
        (plan.selected_samples[0],) + plan.selected_samples[:-1],
        (replace(plan.selected_samples[0], source_frame_index=1),)
        + plan.selected_samples[1:],
        (ResolvedPhysicalTimeSample(0, 1e-7, 0, 0, -1e-7),) + plan.selected_samples[1:],
    ):
        with pytest.raises(ValueError):
            replace(plan, selected_samples=records)
    partial = resolve(axis([0]))
    with pytest.raises(ValueError):
        replace(partial, status="complete")
    with pytest.raises(ValueError):
        replace(partial, effective_stride_ps=100)
    failed = resolve(())
    with pytest.raises(ValueError):
        replace(failed, status="partial")
    with pytest.raises(ValueError):
        replace(failed, source_start_time_ps=0)
    with pytest.raises(ValueError):
        replace(plan, issues=(PhysicalTimeSamplingIssue("error", "test", "Test."),))


def test_models_are_frozen_and_serialization_is_independent_and_ordered() -> None:
    plan = resolve()
    records = (
        PhysicalTimeSourceFrame(0, 0),
        plan.selected_samples[0],
        MissingPhysicalTimeSample(1, 100),
        PhysicalTimeSamplingIssue("warning", "test", "Test."),
        plan,
    )
    for record in records:
        with pytest.raises(FrozenInstanceError):
            setattr(record, fields(record)[0].name, None)
        assert list(record.to_dict()) == [field.name for field in fields(record)]
    payload = plan.to_dict()
    payload["selected_samples"][0]["actual_time_ps"] = 42
    assert plan.selected_samples[0].actual_time_ps == 0
    encoded = json.dumps(plan.to_dict(), allow_nan=False, separators=(",", ":"))
    assert encoded == json.dumps(
        resolve().to_dict(), allow_nan=False, separators=(",", ":")
    )
    assert json.loads(encoded) == plan.to_dict()
    assert json.dumps(
        PhysicalTimeSourceFrame(8, 12.5).to_dict(), separators=(",", ":")
    ) == ('{"frame_index":8,"time_ps":12.5}')


def test_api_types_and_exports() -> None:
    assert PHYSICAL_TIME_MATCH_ABS_TOLERANCE_PS == 1e-6
    assert PHYSICAL_TIME_MATCH_REL_TOLERANCE == 1e-9
    assert get_args(PhysicalTimeSamplingStatus) == ("complete", "partial", "failed")
    assert set(sampling.__all__) == {
        "PHYSICAL_TIME_MATCH_ABS_TOLERANCE_PS",
        "PHYSICAL_TIME_MATCH_REL_TOLERANCE",
        "MissingPhysicalTimeSample",
        "PhysicalTimeSamplingIssue",
        "PhysicalTimeSamplingStatus",
        "PhysicalTimeSourceFrame",
        "ResolvedPhysicalTimeSample",
        "ResolvedPhysicalTimeSamplingPlan",
        "resolve_physical_time_sampling",
    }
    for invalid in ([], {}, None, (0,), ({"frame_index": 0, "time_ps": 0},)):
        with pytest.raises(ValueError, match="source_frames"):
            resolve_physical_time_sampling(invalid, temporal=temporal())

    class TemporalSubclass(DatasetTemporalParameters):
        pass

    for invalid in (
        None,
        temporal().to_dict(),
        TemporalSubclass(**temporal().to_dict()),
    ):
        with pytest.raises(ValueError, match="exact DatasetTemporalParameters"):
            resolve_physical_time_sampling(axis(), temporal=invalid)


def test_matching_agrees_with_independent_exhaustive_oracle() -> None:
    rng = random.Random(27)
    # Include overlapping tolerance bands as well as ordinary sparse trajectories.
    for step in (100.0, 1e-6):
        targets = [float(i * Decimal(str(step))) for i in range(11)]
        for _ in range(20):
            times = sorted(
                {
                    max(0, rng.choice(targets) + rng.choice([-5e-7, 0, 5e-7]))
                    for _ in range(16)
                }
            )
            matches = [
                [
                    i
                    for i, actual in enumerate(times)
                    if math.isclose(actual, target, rel_tol=1e-9, abs_tol=1e-6)
                ]
                for target in targets
            ]
            expected = [
                (i, candidates[0])
                for i, candidates in enumerate(matches)
                if len(candidates) == 1
                and sum(candidates[0] in others for others in matches) == 1
            ]
            plan = resolve(
                axis(times),
                production_end_ns=float(Decimal(str(step)) / 100),
                frame_stride_ps=step,
                window_length_ns=step / 1000,
            )
            assert [
                (s.requested_sample_index, s.source_frame_index)
                for s in plan.selected_samples
            ] == expected
            assert plan.sampled_frame_count + plan.missing_sample_count == 11


def test_purity_and_trajectory_rejection(monkeypatch) -> None:
    source, request = axis(), temporal()
    module_ast = ast.parse(inspect.getsource(sampling))
    imports = {
        node.module for node in ast.walk(module_ast) if isinstance(node, ast.ImportFrom)
    }
    assert imports <= {
        "collections",
        "dataclasses",
        "decimal",
        "itertools",
        "math",
        "typing",
        "mania.dataset_identity",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(module_ast))

    def forbidden(*args, **kwargs):
        raise AssertionError("Pure resolver must not access external state")

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(
            (
                "MDAnalysis",
                "mania.preprocessing.trajectory",
                "mania.preprocessing.scientific_runtime",
            )
        ):
            forbidden()
        return real_import(name, *args, **kwargs)

    class Trajectory:
        def __iter__(self):
            forbidden()

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        for owner, names in (
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
        plan = resolve_physical_time_sampling(source, temporal=request)
        assert plan.status == "complete"
        json.dumps(plan.to_dict(), allow_nan=False)
        assert resolve_physical_time_sampling((), temporal=request).status == "failed"
        with pytest.raises(ValueError, match="source_frames"):
            resolve_physical_time_sampling(Trajectory(), temporal=request)
