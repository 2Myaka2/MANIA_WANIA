"""Synthetic Stage 28.A scientific semantics, model validation, and purity."""

import ast
import builtins
import inspect
import io
import json
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path

import pytest

from mania.dataset_identity import DatasetTemporalParameters
from mania.preprocessing import contact_episodes as engine
from mania.preprocessing import physical_time_sampling as sampling
from mania.preprocessing import physical_time_windows as windows
from mania.preprocessing.contact_episodes import (
    CONTACT_EPISODE_GAP_TOLERANCE,
    CONTACT_EPISODE_KIND,
    CONTACT_EPISODE_SCHEMA_VERSION,
    ContactEpisode,
    ContactEpisodeComputationError,
    WindowContactEpisodeSummary,
    compute_window_contact_episodes,
)


def plans(count=5, *, missing=(), indexes=None, times=None, length=None, step=None):
    duration = Decimal(count - 1) * Decimal("0.05")
    # Keep default synthetic bounds away from the temporal model's binary-float
    # length limit, while including every target and requesting no extra sample.
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
        sampling.PhysicalTimeSourceFrame(frame, actual)
        for i, (frame, actual) in enumerate(zip(indexes, times, strict=True))
        if i not in missing
    )
    plan = sampling.resolve_physical_time_sampling(source, temporal=temporal)
    return plan, windows.plan_physical_time_windows(plan, temporal=temporal)


def compute(plan, window, contacts):
    return compute_window_contact_episodes(
        plan, window, contact_source_frame_indexes=contacts
    )


def episode():
    return ContactEpisode(0, 0, 2, 500, 510, 3, 5000.0, 5100.0, 0.1, (500, 505, 510))


def summary():
    return WindowContactEpisodeSummary(
        window_id="window_0001",
        window_index=0,
        n_contact_frames=3,
        n_contact_episodes=1,
        mean_episode_length_ns=0.1,
        max_episode_length_ns=0.1,
        contact_source_frame_indexes=(500, 505, 510),
        episodes=(episode(),),
    )


def serialized(result):
    return json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))


def test_constants_and_exact_public_api() -> None:
    assert CONTACT_EPISODE_SCHEMA_VERSION == "mania.contact_episode_summary.v0.1"
    assert CONTACT_EPISODE_KIND == "mania_contact_episode_summary"
    assert CONTACT_EPISODE_GAP_TOLERANCE == 0
    assert issubclass(ContactEpisodeComputationError, ValueError)
    assert engine.__all__ == [
        "CONTACT_EPISODE_GAP_TOLERANCE",
        "CONTACT_EPISODE_KIND",
        "CONTACT_EPISODE_SCHEMA_VERSION",
        "ContactEpisode",
        "ContactEpisodeComputationError",
        "WindowContactEpisodeSummary",
        "compute_window_contact_episodes",
    ]
    parameters = inspect.signature(compute_window_contact_episodes).parameters
    assert tuple(parameters) == (
        "sampling_plan",
        "window",
        "contact_source_frame_indexes",
    )
    assert (
        parameters["contact_source_frame_indexes"].kind
        == inspect.Parameter.KEYWORD_ONLY
    )


def test_frozen_models_field_order_and_independent_json_dictionary() -> None:
    expected_episode = (
        "episode_index",
        "start_requested_sample_index",
        "end_requested_sample_index",
        "start_source_frame_index",
        "end_source_frame_index",
        "contact_frame_count",
        "start_actual_time_ps",
        "end_actual_time_ps",
        "episode_length_ns",
        "source_frame_indexes",
    )
    expected_summary = (
        "schema_version",
        "kind",
        "window_id",
        "window_index",
        "gap_tolerance",
        "n_contact_frames",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
        "contact_source_frame_indexes",
        "episodes",
    )
    for record, expected in (
        (episode(), expected_episode),
        (summary(), expected_summary),
    ):
        assert tuple(f.name for f in fields(record)) == expected
        assert tuple(record.to_dict()) == expected
        with pytest.raises(FrozenInstanceError):
            setattr(record, expected[0], "changed")
        assert serialized(record) == serialized(record)
    result = summary()
    assert (result.schema_version, result.kind, result.gap_tolerance) == (
        CONTACT_EPISODE_SCHEMA_VERSION,
        CONTACT_EPISODE_KIND,
        0,
    )
    data = result.to_dict()
    assert data["contact_source_frame_indexes"] == [500, 505, 510]
    assert tuple(data["episodes"][0]) == expected_episode
    data["episodes"][0]["source_frame_indexes"].clear()
    data["contact_source_frame_indexes"].clear()
    assert result == summary()
    for name in ("schema_version", "kind", "gap_tolerance"):
        with pytest.raises(ValueError, match="init=False"):
            replace(result, **{name: "changed"})


@pytest.mark.parametrize("indexes", [(500, 505, 510), (7, 800, 9000), (0, 1, 2)])
def test_consecutive_requested_contacts_ignore_source_stride(indexes) -> None:
    plan, window_plan = plans(3, indexes=indexes)
    result = compute(plan, window_plan.windows[0], indexes)
    assert result.n_contact_frames == 3
    assert result.n_contact_episodes == 1
    actual = result.episodes[0]
    assert (actual.start_requested_sample_index, actual.end_requested_sample_index) == (
        0,
        2,
    )
    assert (actual.start_source_frame_index, actual.end_source_frame_index) == (
        indexes[0],
        indexes[-1],
    )
    assert actual.source_frame_indexes == indexes
    assert actual.contact_frame_count == 3
    assert actual.episode_length_ns == 0.1
    assert actual.start_actual_time_ps == 5000
    assert actual.end_actual_time_ps == 5100


def test_single_contact_is_a_real_zero_duration_episode() -> None:
    plan, window_plan = plans()
    result = compute(plan, window_plan.windows[0], (510,))
    assert (result.n_contact_frames, result.n_contact_episodes) == (1, 1)
    assert result.episodes == (
        ContactEpisode(0, 2, 2, 510, 510, 1, 5100, 5100, 0.0, (510,)),
    )
    assert result.mean_episode_length_ns == result.max_episode_length_ns == 0.0


@pytest.mark.parametrize("missing", [(), (2,), (0, 1, 2, 3, 4)])
def test_no_contact_has_null_lifetimes_including_empty_windows(missing) -> None:
    plan, window_plan = plans(missing=missing)
    result = compute(plan, window_plan.windows[0], ())
    assert (result.n_contact_frames, result.n_contact_episodes) == (0, 0)
    assert result.episodes == result.contact_source_frame_indexes == ()
    assert result.mean_episode_length_ns is result.max_episode_length_ns is None
    assert '"mean_episode_length_ns":null,"max_episode_length_ns":null' in serialized(
        result
    )


@pytest.mark.parametrize("missing", [(), (2,)])
def test_resolved_absence_and_missing_requested_sample_break(missing) -> None:
    plan, window_plan = plans(4, missing=missing)
    window = window_plan.windows[0]
    result = compute(plan, window, (500, 505, 515))
    assert result.n_contact_frames == 3
    assert result.n_contact_episodes == 2
    assert [e.source_frame_indexes for e in result.episodes] == [(500, 505), (515,)]
    assert [e.episode_length_ns for e in result.episodes] == [0.05, 0.0]
    assert window.missing_requested_sample_indexes == missing
    assert window.sampled_frame_count == 4 - len(missing)
    assert result.mean_episode_length_ns == 0.025
    assert result.max_episode_length_ns == 0.05


def test_partial_window_missing_smoke_has_two_equal_episodes_without_qc() -> None:
    plan, window_plan = plans(missing=(2,))
    window = window_plan.windows[0]
    assert window.coverage_fraction == 0.8
    assert window.status == "partial"
    result = compute(plan, window, (500, 505, 515, 520))
    assert [e.episode_length_ns for e in result.episodes] == [0.05, 0.05]
    assert (result.n_contact_frames, result.n_contact_episodes) == (4, 2)
    assert result.mean_episode_length_ns == result.max_episode_length_ns == 0.05


def test_multiple_episode_indexes_mean_and_max() -> None:
    plan, window_plan = plans(9)
    result = compute(plan, window_plan.windows[0], (500, 505, 510, 520, 535, 540))
    assert [e.episode_index for e in result.episodes] == [0, 1, 2]
    assert [e.episode_length_ns for e in result.episodes] == [0.1, 0.0, 0.05]
    assert (result.n_contact_frames, result.n_contact_episodes) == (6, 3)
    assert result.mean_episode_length_ns == float(Decimal("0.15") / 3) == 0.05
    assert result.max_episode_length_ns == 0.1


def test_actual_time_offsets_define_duration_not_requested_stride() -> None:
    times = (5000.0000001, 5050.0000002, 5100.0000003)
    plan, window_plan = plans(3, times=times)
    result = compute(plan, window_plan.windows[0], (500, 505, 510))
    actual = result.episodes[0]
    assert actual.start_actual_time_ps == times[0]
    assert actual.end_actual_time_ps == times[-1]
    expected = float((Decimal(str(times[-1])) - Decimal(str(times[0]))) / 1000)
    assert actual.episode_length_ns == expected == 0.1000000002
    assert actual.episode_length_ns != 2 * plan.requested_frame_stride_ps / 1000


def test_decimal_arithmetic_ignores_caller_precision_and_traps() -> None:
    plan, window_plan = plans(8)
    window = window_plan.windows[0]
    positives = (500, 505, 515, 525, 530, 535)
    expected = serialized(compute(plan, window, positives))
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert serialized(compute(plan, window, positives)) == expected
        tiny = ContactEpisode(0, 0, 1, 0, 1, 2, 0.0, 1e-200, 1e-203, (0, 1))
        assert tiny.episode_length_ns == 1e-203


def test_adjacent_windows_and_replicas_have_no_shared_episode_state() -> None:
    plan, window_plan = plans(length=0.1)
    first, second = window_plan.windows
    left = compute(plan, first, first.source_frame_indexes)
    right = compute(plan, second, second.source_frame_indexes)
    assert [
        left.episodes[0].source_frame_indexes,
        right.episodes[0].source_frame_indexes,
    ] == [
        (500, 505),
        (510, 515, 520),
    ]
    assert [left.max_episode_length_ns, right.max_episode_length_ns] == [0.05, 0.1]
    assert right.episodes[0].episode_index == 0
    other_plan, other_windows = plans(length=0.1)
    assert compute(other_plan, other_windows.windows[0], ()).episodes == ()
    assert serialized(compute(plan, first, first.source_frame_indexes)) == serialized(
        left
    )


def test_overlapping_windows_independently_retain_shared_contacts() -> None:
    plan, window_plan = plans(length=0.1, step=0.05)
    results = [compute(plan, w, w.source_frame_indexes) for w in window_plan.windows]
    assert [r.episodes[0].source_frame_indexes for r in results] == [
        (500, 505),
        (505, 510),
        (510, 515, 520),
    ]
    assert [r.window_index for r in results] == [0, 1, 2]
    assert [r.window_id for r in results] == [
        "window_0001",
        "window_0002",
        "window_0003",
    ]
    assert all(
        r.n_contact_episodes == 1 and r.episodes[0].episode_index == 0 for r in results
    )


@pytest.mark.parametrize(
    "contacts",
    [
        [500],
        {500},
        None,
        (500, 500),
        (505, 500),
        (True,),
        (-1,),
        (500.0,),
        ("500",),
        (501,),
        (510,),
        (520,),
    ],
)
def test_invalid_or_unresolved_or_outside_window_contacts_rejected(contacts) -> None:
    plan, window_plan = plans(missing=(2,), length=0.1)
    with pytest.raises(ContactEpisodeComputationError):
        compute(plan, window_plan.windows[0], contacts)


@pytest.mark.parametrize(
    "which", ["plan", "window", "plan_subclass", "window_subclass"]
)
def test_only_exact_accepted_model_types(which) -> None:
    plan, window_plan = plans()
    window = window_plan.windows[0]
    if which.endswith("subclass"):
        record = plan if which == "plan_subclass" else window
        derived = type("Derived", (type(record),), {})
        replacement = derived(
            **{f.name: getattr(record, f.name) for f in fields(record)}
        )
    else:
        replacement = [plan] if which == "plan" else window.to_dict()
    with pytest.raises(ContactEpisodeComputationError, match="must be exact"):
        compute(
            replacement if which.startswith("plan") else plan,
            replacement if which.startswith("window") else window,
            (),
        )


@pytest.mark.parametrize("change", ["unknown", "source", "order", "selected", "times"])
def test_sampling_window_mismatch_is_rejected_even_without_contacts(change) -> None:
    plan, window_plan = plans(missing=(2,))
    window = window_plan.windows[0]
    changes = {
        "unknown": {
            "requested_sample_indexes": (0, 1, 2, 3, 99),
            "selected_requested_sample_indexes": (0, 1, 3, 99),
        },
        "source": {"source_frame_indexes": (500, 505, 515, 999)},
        "order": {"source_frame_indexes": (505, 500, 515, 520)},
        "selected": {
            "selected_requested_sample_indexes": (0, 1, 2, 4),
            "missing_requested_sample_indexes": (3,),
        },
        "times": {"effective_start_time_ps": 5001},
    }
    with pytest.raises(ContactEpisodeComputationError, match="window"):
        compute(plan, replace(window, **changes[change]), ())


def test_window_missing_record_must_also_be_missing_in_supplied_plan() -> None:
    complete_plan, _ = plans()
    _, partial_windows = plans(missing=(2,))
    with pytest.raises(ContactEpisodeComputationError, match="window missing indexes"):
        compute(complete_plan, partial_windows.windows[0], ())


def test_nonmonotonic_contact_source_order_is_not_silently_repaired() -> None:
    plan, window_plan = plans(3, indexes=(510, 505, 500))
    window = window_plan.windows[0]
    assert plan.status == "complete"  # Stage 27 permits nonmonotonic source labels.
    assert compute(plan, window, ()).n_contact_episodes == 0
    with pytest.raises(
        ContactEpisodeComputationError, match="preserve requested sample order"
    ):
        compute(plan, window, (500, 505, 510))


@pytest.mark.parametrize(
    "name",
    [
        "episode_index",
        "start_requested_sample_index",
        "end_requested_sample_index",
        "start_source_frame_index",
        "end_source_frame_index",
        "contact_frame_count",
    ],
)
@pytest.mark.parametrize("invalid", [-1, True, 1.5, "1", None])
def test_episode_index_fields_reject_invalid_types_and_values(name, invalid) -> None:
    with pytest.raises(ContactEpisodeComputationError):
        replace(episode(), **{name: invalid})


@pytest.mark.parametrize(
    "name", ["start_actual_time_ps", "end_actual_time_ps", "episode_length_ns"]
)
@pytest.mark.parametrize(
    "invalid", [-1, True, float("nan"), float("inf"), "1", 10**400]
)
def test_episode_numbers_must_be_finite_nonnegative(name, invalid) -> None:
    with pytest.raises(ContactEpisodeComputationError):
        replace(episode(), **{name: invalid})


@pytest.mark.parametrize(
    "changes",
    [
        {"source_frame_indexes": ()},
        {"source_frame_indexes": [500, 505, 510]},
        {"source_frame_indexes": (500, 500, 510)},
        {"source_frame_indexes": (500, 510, 505)},
        {"source_frame_indexes": (True, 505, 510)},
        {"source_frame_indexes": (-1, 505, 510)},
        {"contact_frame_count": 0},
        {"contact_frame_count": 2},
        {"start_source_frame_index": 499},
        {"end_source_frame_index": 511},
        {"start_requested_sample_index": 3},
        {"end_requested_sample_index": 3},
        {"end_actual_time_ps": 4999},
        {"episode_length_ns": 0.15},
        {"episode_length_ns": 0.10000001},
    ],
)
def test_inconsistent_episode_fields_rejected(changes) -> None:
    with pytest.raises(ContactEpisodeComputationError):
        replace(episode(), **changes)


def test_single_frame_cannot_claim_time_between_distinct_observations() -> None:
    with pytest.raises(ContactEpisodeComputationError, match="equal actual time"):
        ContactEpisode(0, 0, 0, 500, 500, 1, 5000, 5050, 0.05, (500,))


@pytest.mark.parametrize(
    "changes",
    [
        {"window_id": ""},
        {"window_id": " window_0001"},
        {"window_id": None},
        {"window_index": -1},
        {"window_index": True},
        {"n_contact_frames": True},
        {"n_contact_episodes": True},
        {"n_contact_episodes": 0},
        {"n_contact_frames": 2},
        {"episodes": []},
        {"episodes": ({},)},
        {"episodes": ()},
        {"episodes": (replace(episode(), episode_index=1),)},
        {"contact_source_frame_indexes": (500, 505, 515)},
        {"contact_source_frame_indexes": (500, 500, 510)},
        {"contact_source_frame_indexes": [500, 505, 510]},
        {"mean_episode_length_ns": None},
        {"max_episode_length_ns": None},
        {"mean_episode_length_ns": float("nan")},
        {"max_episode_length_ns": float("inf")},
        {"mean_episode_length_ns": True},
        {"max_episode_length_ns": -1},
        {"mean_episode_length_ns": 0.0},
        {"max_episode_length_ns": 0.2},
    ],
)
def test_inconsistent_summary_fields_rejected(changes) -> None:
    with pytest.raises(ContactEpisodeComputationError):
        replace(summary(), **changes)


@pytest.mark.parametrize("name", ["mean_episode_length_ns", "max_episode_length_ns"])
def test_no_contact_cannot_be_encoded_as_zero_lifetime(name) -> None:
    plan, window_plan = plans()
    result = compute(plan, window_plan.windows[0], ())
    with pytest.raises(ContactEpisodeComputationError):
        replace(result, **{name: 0.0})


@pytest.mark.parametrize("next_requested", [1, 3])
def test_summary_rejects_overlapping_or_unnecessarily_split_episodes(
    next_requested,
) -> None:
    second = ContactEpisode(
        1, next_requested, next_requested, 515, 515, 1, 5150, 5150, 0.0, (515,)
    )
    with pytest.raises(ContactEpisodeComputationError, match="requested-position gap"):
        replace(
            summary(),
            episodes=(episode(), second),
            n_contact_frames=4,
            n_contact_episodes=2,
            contact_source_frame_indexes=(500, 505, 510, 515),
            mean_episode_length_ns=0.05,
        )


def test_identical_calls_are_byte_identical_and_do_not_mutate_inputs() -> None:
    plan, window_plan = plans()
    window = window_plan.windows[0]
    before = (serialized(plan), serialized(window))
    result = compute(plan, window, (500, 505, 510, 520))
    assert [e.episode_length_ns for e in result.episodes] == [0.1, 0.0]
    assert (result.n_contact_frames, result.n_contact_episodes) == (4, 2)
    assert result.mean_episode_length_ns == 0.05
    assert result.max_episode_length_ns == 0.1
    for _ in range(3):
        assert serialized(compute(plan, window, (500, 505, 510, 520))) == serialized(
            result
        )
    assert (serialized(plan), serialized(window)) == before
    assert "occupancy" not in result.to_dict()
    assert "edge_weight" not in result.to_dict()


def test_pure_computation_without_io_runtime_matching_or_window_replanning(
    monkeypatch,
) -> None:
    plan, window_plan = plans(missing=(2,))
    source = inspect.getsource(engine)
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= {
        "dataclasses",
        "decimal",
        "itertools",
        "math",
        "mania.preprocessing.physical_time_sampling",
        "mania.preprocessing.physical_time_windows",
    }  # No trajectory, contact-distance, PBC, optional stack, Git or clock imports.

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "episode engine attempted an operation outside its pure boundary"
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
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        result = compute(plan, window_plan.windows[0], (500, 505, 515, 520))
        empty = compute(plan, window_plan.windows[0], ())
        assert result.n_contact_episodes == 2
        assert empty.n_contact_episodes == 0
        assert serialized(result) == serialized(result)
