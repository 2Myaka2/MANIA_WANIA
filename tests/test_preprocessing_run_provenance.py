"""Deterministic sampling observations from accepted models and in-memory runtimes."""

import builtins
import datetime
import io
import json
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from math import fsum
from pathlib import Path
from types import SimpleNamespace

import pytest

import mania.preprocessing
import mania.preprocessing.run_provenance as adapter
import mania.software_identity as identity
from mania.preprocessing.run_provenance import (
    PREPROCESSING_SAMPLING_STAGE,
    PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS,
    PREPROCESSING_SAMPLING_TIME_REL_TOL,
    PreprocessingSamplingProvenanceResult,
    collect_preprocessing_sampling_provenance,
)
from mania.preprocessing.trajectory_contacts import (
    PreprocessingConditionContactsResult,
    PreprocessingContactComputationIssue,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingManifestContactsResult,
)
from mania.preprocessing.trajectory_frame_sampling import (
    PreprocessingFrameSamplingOptions,
)
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowComputationResult,
    PreprocessingGraphWorkflowManifestReadinessResult,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
)
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadResult,
)
from mania.preprocessing.trajectory_rg import (
    PreprocessingConditionRgResult,
    PreprocessingManifestRgResult,
    PreprocessingRgFrameResult,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
)
from mania.run_provenance import (
    ConditionSamplingProvenance,
    RequestedFrameSampling,
    RunProvenanceIssue,
)


class CountOnlyTrajectory:
    def __init__(self, count: int) -> None:
        self.n_frames = count
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        raise AssertionError("Trajectory iteration is forbidden")

    def __getitem__(self, key):
        raise AssertionError("Trajectory frame access is forbidden")


def runtime_result(condition="sample", runtime_object=None, source_count=10):
    if runtime_object is None:
        runtime_object = SimpleNamespace(trajectory=CountOnlyTrajectory(source_count))
    runtime_input = PreprocessingConditionRuntimeInput(
        condition,
        Path("topology.fake"),
        (Path("trajectory.fake"),),
    )
    runtime = PreprocessingConditionRuntime(
        condition,
        runtime_object,
        "fake",
        runtime_input.topology_path,
        runtime_input.trajectory_paths,
    )
    return PreprocessingConditionLoadResult(
        condition,
        runtime_input,
        runtime,
        status="loaded",
    )


def computation(
    *,
    contacts=None,
    rg=None,
    options=None,
    conditions=("sample",),
    source_count=10,
    runtime_object=None,
):
    loaded = (
        None
        if source_count is None
        else PreprocessingManifestLoadResult(
            tuple(
                runtime_result(name, runtime_object, source_count)
                for name in conditions
            )
        )
    )
    readiness = PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=Path("manifest.fake"),
        manifest_loaded=True,
        manifest_paths_valid=True,
        condition_names=conditions,
        expected_condition_count=len(conditions),
    )
    loading = PreprocessingGraphWorkflowRuntimeLoadingResult(
        readiness.manifest_path,
        readiness,
        conditions,
        conditions,
        runtime_load_result=loaded,
    )
    return PreprocessingGraphWorkflowComputationResult(
        loading,
        conditions,
        rg is not None,
        contacts is not None,
        frame_sampling=options or PreprocessingFrameSamplingOptions(),
        contacts_result=contacts,
        rg_result=rg,
    )


def contact_source(observations, condition="sample", failed=False):
    issues = (
        ()
        if not failed
        else (
            PreprocessingContactComputationIssue(
                kind="frame_iteration_error",
                field="frame",
                message="Frame attempt failed.",
            ),
        )
    )
    return PreprocessingManifestContactsResult(
        (
            PreprocessingConditionContactsResult(
                condition_name=condition,
                options=PreprocessingContactDetectionOptions(),
                frame_results=tuple(
                    PreprocessingContactFrameResult(
                        condition, index, time_ps, issues=issues
                    )
                    for index, time_ps in observations
                ),
                status="partial" if failed else "computed",
            ),
        )
    )


def rg_source(observations, condition="sample", failed=False):
    return PreprocessingManifestRgResult(
        (
            PreprocessingConditionRgResult(
                condition_name=condition,
                status="partial" if failed else "computed",
                runtime_type="fake",
                topology_path=Path("topology.fake"),
                trajectory_paths=(Path("trajectory.fake"),),
                frame_time_ps=None,
                rg_unit="A",
                frame_results=tuple(
                    PreprocessingRgFrameResult(
                        condition,
                        index,
                        time_ps,
                        None if failed else 1.0,
                        "A",
                    )
                    for index, time_ps in observations
                ),
            ),
        )
    )


def collect_source(source, observations, **kwargs):
    factory = contact_source if source == "contacts" else rg_source
    return collect_preprocessing_sampling_provenance(
        computation(
            **{source: factory(observations)},
            **kwargs,
        )
    )


def assert_error(result, code, condition="sample"):
    assert not result.passed
    assert result.sampling_by_condition[0].effective is None
    errors = [issue for issue in result.issues if issue.severity == "error"]
    assert [(issue.code, issue.stage, issue.condition) for issue in errors] == [
        (code, PREPROCESSING_SAMPLING_STAGE, condition),
    ]
    json.dumps(result.to_dict(), allow_nan=False)


def test_public_boundary_and_constants():
    assert adapter.__all__ == [
        "PREPROCESSING_SAMPLING_STAGE",
        "PREPROCESSING_SAMPLING_TIME_REL_TOL",
        "PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS",
        "PreprocessingSamplingProvenanceResult",
        "collect_preprocessing_sampling_provenance",
    ]
    assert PREPROCESSING_SAMPLING_STAGE == "preprocessing_sampling"
    assert PREPROCESSING_SAMPLING_TIME_REL_TOL == 1e-9
    assert PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS == 1e-9
    assert not hasattr(mania.preprocessing, "PreprocessingSamplingProvenanceResult")
    assert not hasattr(mania.preprocessing, "collect_preprocessing_sampling_provenance")


@pytest.mark.parametrize(
    "severity,passed", [(None, True), ("warning", True), ("error", False)]
)
def test_result_contract(severity, passed):
    issues = (
        ()
        if severity is None
        else (RunProvenanceIssue(severity, "test", "Test issue."),)
    )
    entry = ConditionSamplingProvenance("sample", RequestedFrameSampling(), None)
    result = PreprocessingSamplingProvenanceResult((entry,), issues)
    assert result.passed is passed
    with pytest.raises(FrozenInstanceError):
        result.issues = ()
    payload = result.to_dict()
    assert list(payload) == ["sampling_by_condition", "issues", "passed"]
    assert payload == {
        "sampling_by_condition": [entry.to_dict()],
        "issues": [issue.to_dict() for issue in issues],
        "passed": passed,
    }
    json.dumps(payload, allow_nan=False)
    payload["sampling_by_condition"][0]["requested"]["frame_start"] = 99
    assert result.to_dict()["sampling_by_condition"][0]["requested"]["frame_start"] == 0


@pytest.mark.parametrize(
    "sampling,issues", [([], ()), ((object(),), ()), ((), []), ((), (object(),))]
)
def test_result_rejects_incorrect_nested_types(sampling, issues):
    with pytest.raises(ValueError):
        PreprocessingSamplingProvenanceResult(sampling, issues)


def test_result_rejects_duplicate_conditions():
    entry = ConditionSamplingProvenance("sample", RequestedFrameSampling(), None)
    with pytest.raises(ValueError, match="unique"):
        PreprocessingSamplingProvenanceResult((entry, entry))


@pytest.mark.parametrize(
    "invalid", [None, object(), SimpleNamespace(condition_names=())]
)
def test_collection_requires_accepted_computation_type(invalid):
    with pytest.raises(ValueError, match="PreprocessingGraphWorkflowComputationResult"):
        collect_preprocessing_sampling_provenance(invalid)


def test_collection_rejects_computation_subclass():
    class OtherComputation(PreprocessingGraphWorkflowComputationResult):
        pass

    original = computation()
    other = OtherComputation(
        **{field.name: getattr(original, field.name) for field in fields(original)}
    )
    with pytest.raises(ValueError, match="PreprocessingGraphWorkflowComputationResult"):
        collect_preprocessing_sampling_provenance(other)


@pytest.mark.parametrize(
    "options,expected",
    [
        (
            PreprocessingFrameSamplingOptions(),
            {
                "frame_start": 0,
                "frame_stop": None,
                "frame_stride": 1,
                "max_frames": None,
            },
        ),
        (
            PreprocessingFrameSamplingOptions(2, 10, 3, 2),
            {"frame_start": 2, "frame_stop": 10, "frame_stride": 3, "max_frames": 2},
        ),
    ],
)
def test_requested_snapshot_is_exact_shared_and_independent(options, expected):
    # Keep the controlled later mutation local to this test invocation.
    options = replace(options)
    original = computation(options=options, conditions=("zeta", "alpha"))
    before = original.to_dict()
    result = collect_preprocessing_sampling_provenance(original)
    assert [item.condition for item in result.sampling_by_condition] == [
        "zeta",
        "alpha",
    ]
    assert all(
        item.requested.to_dict() == expected for item in result.sampling_by_condition
    )
    assert (
        result.sampling_by_condition[0].requested
        is result.sampling_by_condition[1].requested
    )
    assert options.to_dict() == expected
    assert original.to_dict() == before
    assert [field.name for field in fields(options)] == list(expected)
    with pytest.raises(FrozenInstanceError):
        options.frame_start = 99
    object.__setattr__(options, "frame_start", 99)
    assert result.sampling_by_condition[0].requested.to_dict() == expected


@pytest.mark.parametrize("source", ["contacts", "rg"])
@pytest.mark.parametrize(
    "observations,status,spacing",
    [
        ((), "unavailable", None),
        (((3, 7.0),), "unavailable", None),
        (((3, None),), "unavailable", None),
        (((0, 0.0), (2, 5.0), (4, 10.0)), "uniform", 5.0),
        (((0, 0.0), (2, 5.0), (4, 11.0)), "non_uniform", None),
        (((0, 0.0), (2, None), (4, 10.0)), "unavailable", None),
        (((0, None), (2, 5.0), (4, 10.0)), "unavailable", None),
        (((0, 0.0), (2, 5.0), (4, None)), "unavailable", None),
    ],
)
def test_single_source_observations(source, observations, status, spacing):
    result = collect_source(source, observations)
    assert result.passed and result.issues == ()
    effective = result.sampling_by_condition[0].effective
    assert effective.to_dict() == {
        "source_frame_count": 10,
        "sampled_frame_count": len(observations),
        "first_source_frame_index": observations[0][0] if observations else None,
        "last_source_frame_index": observations[-1][0] if observations else None,
        "first_time_ps": observations[0][1] if observations else None,
        "last_time_ps": observations[-1][1] if observations else None,
        "time_spacing_status": status,
        "observed_time_spacing_ps": spacing,
    }


@pytest.mark.parametrize(
    "source,factory", [("contacts", contact_source), ("rg", rg_source)]
)
def test_failed_scientific_rows_are_observations(source, factory):
    manifest = factory(((0, 0.0), (1, 2.0)), failed=True)
    assert not any(
        frame.passed for frame in manifest.condition_results[0].frame_results
    )
    result = collect_preprocessing_sampling_provenance(
        computation(**{source: manifest})
    )
    assert result.passed
    assert result.sampling_by_condition[0].effective.sampled_frame_count == 2


@pytest.mark.parametrize(
    "contact_times,rg_times,expected",
    [
        ((), (), ()),
        ((None, None), (None, None), (None, None)),
        ((0.0, 2.0), (0.0, 2.0), (0.0, 2.0)),
        ((None, 2.0), (0.0, None), (0.0, 2.0)),
        ((0.0, 2.0), (None, None), (0.0, 2.0)),
        ((5e-10, 2.0), (0.0, 2.0 + 1e-9), (0.0, 2.0)),
        ((1e9 + 0.5, 1e9 + 10.5), (1e9, 1e9 + 10), (1e9, 1e9 + 10)),
    ],
)
def test_reconciliation_is_symmetric_and_retains_available_times(
    contact_times, rg_times, expected
):
    contacts = tuple(enumerate(contact_times))
    rg = tuple(enumerate(rg_times))
    result = collect_preprocessing_sampling_provenance(
        computation(
            contacts=contact_source(contacts),
            rg=rg_source(rg),
        )
    )
    swapped = collect_preprocessing_sampling_provenance(
        computation(
            contacts=contact_source(rg),
            rg=rg_source(contacts),
        )
    )
    assert result.passed and result.to_dict() == swapped.to_dict()
    effective = result.sampling_by_condition[0].effective
    assert effective.sampled_frame_count == len(expected)
    assert effective.first_time_ps == (expected[0] if expected else None)
    assert effective.last_time_ps == (expected[-1] if expected else None)


@pytest.mark.parametrize(
    "contacts,rg,code",
    [
        (((0, 0.0), (2, 2.0)), ((0, 0.0), (3, 2.0)), "frame_observation_mismatch"),
        ((), ((0, 0.0),), "frame_observation_mismatch"),
        (((0, 0.0),), (), "frame_observation_mismatch"),
        (((0, 0.0), (1, 2.0)), ((0, 0.0), (1, 3.0)), "frame_time_mismatch"),
    ],
)
def test_reconciliation_rejects_conflicts(contacts, rg, code):
    result = collect_preprocessing_sampling_provenance(
        computation(
            contacts=contact_source(contacts),
            rg=rg_source(rg),
        )
    )
    assert_error(result, code)


def controlled_source(source, observations):
    """Inject malformed records only at the adapter boundary, retaining accepted types.

    Bypass constructor validation on test-owned dataclasses; production checks
    must still require the accepted manifest, condition and frame classes.
    """
    factory = contact_source if source == "contacts" else rg_source
    manifest = factory(((0, 0.0),))
    template = manifest.condition_results[0].frame_results[0]
    frames = []
    for index, time_ps in observations:
        frame = replace(template)
        object.__setattr__(frame, "frame_index", index)
        object.__setattr__(frame, "time_ps", time_ps)
        frames.append(frame)
    object.__setattr__(manifest.condition_results[0], "frame_results", tuple(frames))
    return manifest


@pytest.mark.parametrize("source", ["contacts", "rg"])
@pytest.mark.parametrize(
    "indexes,options",
    [
        ((-1,), PreprocessingFrameSamplingOptions()),
        ((False,), PreprocessingFrameSamplingOptions()),
        ((1.0,), PreprocessingFrameSamplingOptions()),
        (("1",), PreprocessingFrameSamplingOptions()),
        ((0, 0), PreprocessingFrameSamplingOptions()),
        ((2, 1), PreprocessingFrameSamplingOptions()),
        ((1,), PreprocessingFrameSamplingOptions(frame_start=2)),
        ((3,), PreprocessingFrameSamplingOptions(frame_stop=3)),
        ((4,), PreprocessingFrameSamplingOptions(frame_stop=3)),
        ((1,), PreprocessingFrameSamplingOptions(frame_stride=2)),
        ((0, 1), PreprocessingFrameSamplingOptions(max_frames=1)),
    ],
)
def test_invalid_indexes_are_rejected_safely(source, indexes, options):
    manifest = controlled_source(source, tuple((index, None) for index in indexes))
    result = collect_preprocessing_sampling_provenance(
        computation(
            **{source: manifest},
            options=options,
        )
    )
    assert_error(result, "invalid_effective_frame_sequence")


def test_no_missing_frame_inference_or_order_normalization():
    result = collect_source(
        "contacts",
        ((5, 10.0), (9, 20.0)),
        source_count=20,
        options=PreprocessingFrameSamplingOptions(1, 20, 2, 8),
    )
    assert result.passed and result.issues == ()
    assert result.sampling_by_condition[0].effective.sampled_frame_count == 2
    result = collect_preprocessing_sampling_provenance(
        computation(
            contacts=contact_source(((0, None), (1, None))),
            rg=rg_source(((1, None), (0, None))),
        )
    )
    assert_error(result, "invalid_effective_frame_sequence")


@pytest.mark.parametrize(
    "count,observations,passed",
    [
        (0, (), True),
        (10, ((9, 1.0),), True),
        (10, ((10, 1.0),), False),
        (1, ((0, 0.0), (1, 1.0)), False),
    ],
)
def test_source_count_bounds(count, observations, passed):
    result = collect_source("contacts", observations, source_count=count)
    if passed:
        assert result.passed
        assert result.sampling_by_condition[0].effective.source_frame_count == count
    else:
        assert_error(result, "source_frame_count_inconsistent")


class LengthOnlyTrajectory:
    def __len__(self):
        return 7

    def __iter__(self):
        raise AssertionError("Trajectory iteration is forbidden")


def test_runtime_count_helper_preserves_count_despite_unrelated_missing_metadata():
    trajectory = CountOnlyTrajectory(7)
    original = computation(
        contacts=contact_source(((6, 12.0),)),
        runtime_object=SimpleNamespace(trajectory=trajectory),
    )
    result = collect_preprocessing_sampling_provenance(original)
    assert result.passed and result.issues == ()
    assert result.sampling_by_condition[0].effective.source_frame_count == 7
    assert trajectory.iterations == 0


def test_source_count_can_use_len_without_iteration():
    result = collect_source(
        "rg",
        ((6, None),),
        runtime_object=SimpleNamespace(
            trajectory=LengthOnlyTrajectory(),
        ),
    )
    assert result.passed and result.issues == ()
    assert result.sampling_by_condition[0].effective.source_frame_count == 7


class BrokenCountTrajectory:
    @property
    def n_frames(self):
        raise RuntimeError("Private runtime diagnostic must not escape")


@pytest.mark.parametrize(
    "runtime",
    [
        object(),
        SimpleNamespace(trajectory=object()),
        SimpleNamespace(trajectory=SimpleNamespace(n_frames=-1)),
        SimpleNamespace(trajectory=BrokenCountTrajectory()),
    ],
)
def test_unavailable_runtime_count_preserves_other_metadata(runtime):
    result = collect_source("contacts", ((0, 2.0),), runtime_object=runtime)
    assert result.passed
    assert [issue.code for issue in result.issues] == ["source_frame_count_unavailable"]
    effective = result.sampling_by_condition[0].effective
    assert effective.source_frame_count is None
    assert effective.sampled_frame_count == 1 and effective.first_time_ps == 2.0


@pytest.mark.parametrize(
    "times,status,spacing",
    [
        ((0.0, 1.0, 2.0), "uniform", 1.0),
        ((0.0, 1.0, 2.0 + 5e-10), "uniform", fsum((1.0, 1.0 + 5e-10)) / 2),
        ((0.0, 1e9, 2e9 + 0.5), "uniform", fsum((1e9, 1e9 + 0.5)) / 2),
        ((0.0, 1.0, 2.0 + 1e-7), "non_uniform", None),
        ((0.0, 0.0, 1.0), "non_uniform", None),
        ((0.0, 2.0, 1.0, 3.0), "non_uniform", None),
        ((0.0, None, 2.0), "unavailable", None),
        ((0.0, 1.0), "uniform", 1.0),
        ((0.0, 8e307, 1.6e308), "uniform", 8e307),
        ((1.0,), "unavailable", None),
        ((), "unavailable", None),
    ],
)
def test_time_spacing_classification_and_deterministic_mean(times, status, spacing):
    result = collect_source("contacts", tuple(enumerate(times)))
    assert result.passed
    effective = result.sampling_by_condition[0].effective
    assert effective.time_spacing_status == status
    assert effective.observed_time_spacing_ps == spacing
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("source", ["contacts", "rg"])
@pytest.mark.parametrize(
    "invalid_time", [-1.0, True, float("nan"), float("inf"), "1", 10**400]
)
def test_invalid_intermediate_times_are_not_hidden(source, invalid_time):
    manifest = controlled_source(source, ((0, 0.0), (1, invalid_time), (2, 2.0)))
    result = collect_preprocessing_sampling_provenance(
        computation(**{source: manifest})
    )
    assert_error(result, "invalid_effective_sampling")


def test_endpoint_time_reversal_reports_existing_model_constraint():
    result = collect_source("rg", ((0, 2.0), (1, 1.0)))
    assert_error(result, "invalid_effective_sampling")


@pytest.mark.parametrize("source_count", [None, 10])
def test_absent_sources_are_unavailable_not_zero(source_count):
    result = collect_preprocessing_sampling_provenance(
        computation(source_count=source_count)
    )
    assert result.passed and result.sampling_by_condition[0].effective is None
    expected = [] if source_count is not None else ["source_frame_count_unavailable"]
    assert [issue.code for issue in result.issues] == expected + [
        "effective_sampling_unavailable"
    ]
    assert all(issue.severity == "warning" for issue in result.issues)


def test_condition_absent_from_valid_manifests_is_unavailable():
    result = collect_preprocessing_sampling_provenance(
        computation(
            contacts=contact_source((), "another"),
            rg=rg_source((), "another"),
        )
    )
    assert result.passed and result.sampling_by_condition[0].effective is None
    assert [issue.code for issue in result.issues] == ["effective_sampling_unavailable"]


@pytest.mark.parametrize("source", ["contacts", "rg"])
@pytest.mark.parametrize("other_valid", [False, True])
def test_invalid_manifest_source_is_not_silently_replaced(source, other_valid):
    sources = {source: SimpleNamespace(condition_results=())}
    if other_valid:
        other = "rg" if source == "contacts" else "contacts"
        sources[other] = (rg_source if other == "rg" else contact_source)(((0, 0.0),))
    result = collect_preprocessing_sampling_provenance(computation(**sources))
    assert_error(result, "invalid_frame_observation_source")


@pytest.mark.parametrize("source", ["contacts", "rg"])
@pytest.mark.parametrize("level", ["condition", "frame"])
def test_invalid_nested_source_types_are_rejected(source, level):
    manifest = (contact_source if source == "contacts" else rg_source)(((0, None),))
    if level == "condition":
        object.__setattr__(manifest, "condition_results", (object(),))
    else:
        object.__setattr__(manifest.condition_results[0], "frame_results", (object(),))
    result = collect_preprocessing_sampling_provenance(
        computation(**{source: manifest})
    )
    assert_error(result, "invalid_frame_observation_source")


def test_condition_matching_and_issue_order_are_deterministic():
    contacts = PreprocessingManifestContactsResult(
        (
            contact_source(((0, None),), "alpha").condition_results[0],
            contact_source((), "zeta").condition_results[0],
        )
    )
    result = collect_preprocessing_sampling_provenance(
        computation(
            conditions=("zeta", "alpha", "missing"),
            contacts=contacts,
            rg=rg_source(((1, None),), "alpha"),
            source_count=None,
        )
    )
    assert [entry.condition for entry in result.sampling_by_condition] == [
        "zeta",
        "alpha",
        "missing",
    ]
    assert result.sampling_by_condition[0].effective.sampled_frame_count == 0
    assert result.sampling_by_condition[1].effective is None
    assert result.sampling_by_condition[2].effective is None
    assert [(issue.condition, issue.code) for issue in result.issues] == [
        ("zeta", "source_frame_count_unavailable"),
        ("alpha", "source_frame_count_unavailable"),
        ("alpha", "frame_observation_mismatch"),
        ("missing", "source_frame_count_unavailable"),
        ("missing", "effective_sampling_unavailable"),
    ]
    assert all(issue.stage == PREPROCESSING_SAMPLING_STAGE for issue in result.issues)


def test_empty_computation_has_empty_successful_result():
    result = collect_preprocessing_sampling_provenance(computation(conditions=()))
    assert result.to_dict() == {
        "sampling_by_condition": [],
        "issues": [],
        "passed": True,
    }


def test_collection_has_no_side_effects_and_preserves_existing_serialization(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    contacts = contact_source(((0, 0.0), (2, 4.0)))
    rg = rg_source(((0, 0.0), (2, 4.0)))
    trajectory = CountOnlyTrajectory(10)
    original = computation(
        contacts=contacts,
        rg=rg,
        options=PreprocessingFrameSamplingOptions(0, 8, 2, 3),
        runtime_object=SimpleNamespace(trajectory=trajectory),
    )
    before = (original.to_dict(), contacts.to_dict(), rg.to_dict())
    source_frames = (
        contacts.condition_results[0].frame_results,
        rg.condition_results[0].frame_results,
    )
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append("forbidden side effect")
        raise AssertionError("Collection attempted a forbidden side effect")

    class NoClock(datetime.datetime):
        now = today = utcnow = forbidden

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "MDAnalysis" or name.startswith("MDAnalysis."):
            forbidden()
        return real_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(identity, "get_software_identity", forbidden)
        guard.setattr(datetime, "datetime", NoClock)
        guard.setattr(builtins, "__import__", guarded_import)
        for module, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (subprocess, ("Popen", "run", "check_output", "call", "check_call")),
            (os, ("open", "system", "popen", "stat", "lstat", "scandir", "listdir")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (
                Path,
                (
                    "open",
                    "read_text",
                    "read_bytes",
                    "write_text",
                    "write_bytes",
                    "stat",
                    "exists",
                    "resolve",
                ),
            ),
        ):
            for name in names:
                guard.setattr(module, name, forbidden)
        result = collect_preprocessing_sampling_provenance(original)
    assert forbidden_calls == [] and trajectory.iterations == 0
    assert result.passed
    assert (original.to_dict(), contacts.to_dict(), rg.to_dict()) == before
    assert contacts.condition_results[0].frame_results is source_frames[0]
    assert rg.condition_results[0].frame_results is source_frames[1]
    assert list(source_frames[0][0].to_dict()) == [
        "condition_name",
        "frame_index",
        "time_ps",
        "contact_count",
        "contacts",
        "backbone_observation_count",
        "backbone_observations",
        "issues",
        "passed",
    ]
    assert list(source_frames[1][0].to_dict()) == [
        "condition_name",
        "frame_index",
        "time_ps",
        "rg_value",
        "rg_unit",
        "passed",
        "issues",
    ]
    assert not (tmp_path / "run_provenance.json").exists()
    assert list(tmp_path.iterdir()) == []
