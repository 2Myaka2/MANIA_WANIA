"""Dataset planning uses actual times once and retains partial evidence."""

from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_preprocessing_trajectory_graph_workflow_computation import (
    runtime_loading_result,
)
from test_preprocessing_trajectory_rg_compute_manifest import make_load_result

from mania.dataset_identity import DatasetTrajectorySpec
from mania.preprocessing.dataset_binding import (
    PreprocessingDatasetBinding,
    PreprocessingDatasetContext,
)
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
    PreprocessingPhysicalTimeExecutionError,
    PreprocessingTemporalExecution,
    build_preprocessing_temporal_execution,
)
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadResult,
)


def dataset_spec(condition="normal", **temporal):
    return DatasetTrajectorySpec.model_validate(
        {
            "identity": {
                "dataset_id": "synthetic-stage27",
                "system_id": condition,
                "trajectory_id": "trajectory",
                "variant_id": "synthetic",
                "engine": "gromacs",
                "condition": condition,
                "replica_id": "replica",
            },
            "temporal": {
                "production_start_ns": 0,
                "production_end_ns": 1,
                "frame_stride_ps": 200,
                "window_length_ns": 0.4,
                "window_step_ns": 0.2,
                "overlap_percent": 50,
                **temporal,
            },
        }
    )


def context(names=("normal",), **temporal):
    return PreprocessingDatasetContext(
        bindings=tuple(
            PreprocessingDatasetBinding(
                execution_condition=name,
                source="inline_manifest",
                dataset_spec=dataset_spec(name, **temporal),
            )
            for name in names
        )
    )


class TimeOnlyFrame:
    def __init__(self, time):
        self.time = time

    def __getattr__(self, name):
        raise AssertionError(f"Planning must not access {name}")


class TimeAxis:
    def __init__(self, times):
        self.frames = [TimeOnlyFrame(t) for t in times]
        self.passes = 0

    def __iter__(self):
        self.passes += 1
        return iter(self.frames)


def loading(times=None, names=("normal",)):
    times = tuple(range(0, 1001, 100)) if times is None else times
    axes = [TimeAxis(times) for _ in names]
    source = PreprocessingManifestLoadResult(
        tuple(
            make_load_result(name, runtime_object=SimpleNamespace(trajectory=axis))
            for name, axis in zip(names, axes, strict=True)
        )
    )
    return runtime_loading_result(
        condition_names=names, runtime_load_result=source
    ), axes


@pytest.mark.parametrize("names", [("normal",), ("normal", "tumor")])
def test_complete_one_planning_pass_and_exact_indexes(names):
    source, axes = loading(names=names)
    requested = context(names)
    before = requested.to_dict()
    execution = build_preprocessing_temporal_execution(source, requested)
    assert requested.to_dict() == before
    assert execution.status == "complete"
    assert execution.selected_source_frame_indexes_by_condition() == {
        name: (0, 2, 4, 6, 8, 10) for name in names
    }
    assert [axis.passes for axis in axes] == [1] * len(names)
    for binding in execution.bindings:
        assert binding.window_plan.window_count == 4
        assert binding.sampling_plan.sampled_frame_count == 6
        assert binding.sampling_plan.missing_samples == ()
    assert list(execution.to_dict()) == ["schema_version", "kind", "status", "bindings"]
    with pytest.raises(FrozenInstanceError):
        execution.bindings = ()


def test_mixed_context_does_not_iterate_legacy_source():
    source, axes = loading(names=("normal", "legacy"))
    result = build_preprocessing_temporal_execution(source, context())
    assert list(result.selected_source_frame_indexes_by_condition()) == ["normal"]
    assert [a.passes for a in axes] == [1, 0]


@pytest.mark.parametrize("times", [(0, 200, 600, 1000), (0, 200)])
def test_partial_is_retained_without_exclusion(times):
    source, axes = loading(times)
    result = build_preprocessing_temporal_execution(source, context())
    assert result.status == "partial"
    assert result.bindings[0].sampling_plan.status == "partial"
    assert result.bindings[0].window_plan.status == "partial"
    assert result.bindings[0].sampling_plan.missing_samples
    assert axes[0].passes == 1


@pytest.mark.parametrize(
    "bad", [None, "100", "invalid", True, float("nan"), float("inf"), -1, object()]
)
def test_invalid_actual_time_has_no_fallback(bad):
    source, _ = loading([0, bad, 1000])
    with pytest.raises(
        PreprocessingPhysicalTimeExecutionError, match="Actual trajectory time axis"
    ):
        build_preprocessing_temporal_execution(source, context())


def test_raising_or_missing_time_is_portable():
    class Raising:
        @property
        def time(self):
            raise RuntimeError("/private/source.xtc")

    for frame in (object(), Raising()):
        source, axes = loading()
        axes[0].frames = [frame]
        with pytest.raises(PreprocessingPhysicalTimeExecutionError) as caught:
            build_preprocessing_temporal_execution(source, context())
        assert "/private" not in str(caught.value)


@pytest.mark.parametrize("times", [(), (0, 0, 200), (0, 200, 100), (2000, 3000)])
def test_failed_sampling_blocks_windows(monkeypatch, times):
    import mania.preprocessing.physical_time_execution as module

    planner = Mock(side_effect=AssertionError("Failed sampling must block windows"))
    monkeypatch.setattr(module, "plan_physical_time_windows", planner)
    source, _ = loading(times)
    with pytest.raises(
        PreprocessingPhysicalTimeExecutionError, match="sampling plan failed"
    ):
        build_preprocessing_temporal_execution(source, context())
    planner.assert_not_called()


def test_failed_windows_block_execution():
    source, _ = loading()
    with pytest.raises(
        PreprocessingPhysicalTimeExecutionError, match="window plan failed"
    ):
        build_preprocessing_temporal_execution(source, context(window_step_ns=0.5))


def test_request_mismatch_and_duplicate_bindings_rejected():
    source, _ = loading()
    result = build_preprocessing_temporal_execution(source, context())
    binding = result.bindings[0]
    with pytest.raises(ValueError, match="request"):
        replace(binding, dataset_spec=dataset_spec(frame_stride_ps=100))
    with pytest.raises(ValueError, match="request"):
        replace(binding, dataset_spec=dataset_spec(window_length_ns=0.8))
    with pytest.raises(ValueError, match="unique"):
        PreprocessingTemporalExecution((binding, binding))
    with pytest.raises(ValueError, match="non-empty"):
        PreprocessingTemporalExecution(())
    with pytest.raises(ValueError, match="exact"):
        PreprocessingConditionTemporalExecution(
            "normal", None, binding.sampling_plan, binding.window_plan
        )


def test_missing_runtime_binding_rejected():
    source, _ = loading()
    with pytest.raises(PreprocessingPhysicalTimeExecutionError, match="missing"):
        build_preprocessing_temporal_execution(source, context(("tumor",)))
