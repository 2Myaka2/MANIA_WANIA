import json
import math
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRgResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingFrameSamplingOptions,
    PreprocessingTrajectoryLoadIssue,
    compute_condition_rg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RG_MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_rg.py"
)


class FakeTimestep:
    def __init__(self, time: object = None, *, has_time: bool = True) -> None:
        if has_time:
            self.time = time


class FakeAtoms:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.call_count = 0

    def radius_of_gyration(self) -> object:
        outcome = self.outcomes[self.call_count]
        self.call_count += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeRuntime:
    def __init__(self, atoms: object, trajectory: object) -> None:
        self.atoms = atoms
        self.trajectory = trajectory


class FailingBeforeTrajectory:
    def __iter__(self) -> Iterator[object]:
        raise RuntimeError("private iteration details")


class FailingAfterTrajectory:
    def __iter__(self) -> Iterator[object]:
        yield FakeTimestep(0.0)
        raise RuntimeError("private iteration details")


def make_runtime_input(
    *,
    frame_time_ps: float | None = 2.5,
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
        frame_time_ps=frame_time_ps,
    )


def make_loaded_result(
    runtime_object: object,
    *,
    frame_time_ps: float | None = 2.5,
) -> PreprocessingConditionLoadResult:
    runtime_input = make_runtime_input(frame_time_ps=frame_time_ps)
    runtime = PreprocessingConditionRuntime(
        condition_name="normal",
        runtime_object=runtime_object,
        runtime_type="tests.FakeRuntime",
        topology_path=runtime_input.topology_path,
        trajectory_paths=runtime_input.trajectory_paths,
    )
    return PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=runtime,
        status="loaded",
    )


def test_public_export_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert compute_condition_rg is not None


def test_failed_condition_avoids_runtime_object_introspection() -> None:
    class ExplodingRuntimeObject:
        def __getattribute__(self, name: str) -> object:
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError("failed runtime object must remain opaque")

    loaded = make_loaded_result(ExplodingRuntimeObject())
    failed = PreprocessingConditionLoadResult(
        condition_name=loaded.condition_name,
        runtime_input=loaded.runtime_input,
        runtime=loaded.runtime,
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="runtime",
                message="Expected load failure.",
            ),
        ),
        status="failed",
    )

    result = compute_condition_rg(failed)

    assert isinstance(result, PreprocessingConditionRgResult)
    assert result.status == "failed"
    assert result.passed is False
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "condition_not_loaded"
    ]
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_loaded_like_result_without_runtime_reports_runtime_missing() -> None:
    result = compute_condition_rg(
        PreprocessingConditionLoadResult(
            condition_name="normal",
            runtime_input=make_runtime_input(),
            runtime=None,
            status="loaded",
        )
    )

    assert result.status == "failed"
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == ["runtime_missing"]


def test_loaded_wrapper_without_runtime_object_reports_runtime_missing() -> None:
    result = compute_condition_rg(make_loaded_result(None))

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == ["runtime_missing"]


def test_missing_atoms_reports_atom_group_missing() -> None:
    result = compute_condition_rg(make_loaded_result(object()))

    assert result.status == "failed"
    assert result.passed is False
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "atom_group_missing"
    ]


def test_missing_trajectory_reports_frame_iteration_error() -> None:
    class RuntimeWithoutTrajectory:
        atoms = FakeAtoms([10.0])

    result = compute_condition_rg(
        make_loaded_result(RuntimeWithoutTrajectory())
    )

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]
    assert result.issues[0].message == "Runtime object has no trajectory."


def test_successful_runtime_computes_per_frame_rg() -> None:
    atoms = FakeAtoms([10.0, 11.0, 12.0])
    runtime = FakeRuntime(
        atoms,
        [FakeTimestep(), FakeTimestep(), FakeTimestep()],
    )

    result = compute_condition_rg(make_loaded_result(runtime))

    assert result.status == "computed"
    assert result.passed is True
    assert result.frame_count == 3
    assert [frame.frame_index for frame in result.frame_results] == [0, 1, 2]
    assert [frame.rg_value for frame in result.frame_results] == [
        10.0,
        11.0,
        12.0,
    ]
    assert [frame.rg_unit for frame in result.frame_results] == [
        "angstrom",
        "angstrom",
        "angstrom",
    ]
    assert atoms.call_count == 3
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_frame_stride_computes_sampled_source_frames_only() -> None:
    atoms = FakeAtoms([10.0, 12.0])
    runtime = FakeRuntime(
        atoms,
        [
            FakeTimestep(has_time=False),
            FakeTimestep(has_time=False),
            FakeTimestep(has_time=False),
            FakeTimestep(has_time=False),
        ],
    )

    result = compute_condition_rg(
        make_loaded_result(runtime, frame_time_ps=2.5),
        frame_sampling=PreprocessingFrameSamplingOptions(frame_stride=2),
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.frame_count == 2
    assert [frame.frame_index for frame in result.frame_results] == [0, 2]
    assert [frame.time_ps for frame in result.frame_results] == [0.0, 5.0]
    assert [frame.rg_value for frame in result.frame_results] == [10.0, 12.0]
    assert atoms.call_count == 2


def test_frame_time_ps_sets_deterministic_times() -> None:
    runtime = FakeRuntime(
        FakeAtoms([10.0, 11.0, 12.0]),
        [FakeTimestep(100.0), FakeTimestep(200.0), FakeTimestep(300.0)],
    )

    result = compute_condition_rg(
        make_loaded_result(runtime, frame_time_ps=2.5)
    )

    assert [frame.time_ps for frame in result.frame_results] == [
        0.0,
        2.5,
        5.0,
    ]


def test_timestep_time_is_used_without_frame_time() -> None:
    runtime = FakeRuntime(
        FakeAtoms([10.0, 11.0, 12.0]),
        [FakeTimestep(1.0), FakeTimestep(3.5), FakeTimestep(8.0)],
    )

    result = compute_condition_rg(
        make_loaded_result(runtime, frame_time_ps=None)
    )

    assert [frame.time_ps for frame in result.frame_results] == [
        1.0,
        3.5,
        8.0,
    ]


def test_missing_time_is_allowed() -> None:
    runtime = FakeRuntime(
        FakeAtoms([10.0, 11.0]),
        [
            FakeTimestep(has_time=False),
            FakeTimestep(has_time=False),
        ],
    )

    result = compute_condition_rg(
        make_loaded_result(runtime, frame_time_ps=None)
    )

    assert result.status == "computed"
    assert result.passed is True
    assert [frame.time_ps for frame in result.frame_results] == [None, None]
    assert all(frame.issues == () for frame in result.frame_results)


def test_invalid_time_creates_issue_and_later_frames_continue() -> None:
    atoms = FakeAtoms([10.0, 11.0])
    runtime = FakeRuntime(
        atoms,
        [FakeTimestep(math.nan), FakeTimestep(4.0)],
    )

    result = compute_condition_rg(
        make_loaded_result(runtime, frame_time_ps=None)
    )

    assert result.status == "partial"
    assert result.passed is False
    assert result.frame_count == 2
    assert result.frame_results[0].time_ps is None
    assert [issue.kind for issue in result.frame_results[0].issues] == [
        "invalid_time_ps"
    ]
    assert result.frame_results[1].passed is True
    assert atoms.call_count == 2


def test_per_frame_rg_error_creates_failed_frame_and_continues() -> None:
    atoms = FakeAtoms([10.0, RuntimeError("private details"), 12.0])
    runtime = FakeRuntime(
        atoms,
        [FakeTimestep(), FakeTimestep(), FakeTimestep()],
    )

    result = compute_condition_rg(make_loaded_result(runtime))

    assert result.status == "partial"
    assert result.passed is False
    assert result.frame_count == 3
    assert result.frame_results[1].rg_value is None
    assert [issue.kind for issue in result.frame_results[1].issues] == [
        "rg_computation_error"
    ]
    assert result.frame_results[2].rg_value == 12.0
    assert atoms.call_count == 3


@pytest.mark.parametrize("invalid_value", [math.nan, -1.0, "not-a-number"])
def test_invalid_rg_value_creates_failed_frame(invalid_value: object) -> None:
    runtime = FakeRuntime(
        FakeAtoms([invalid_value]),
        [FakeTimestep()],
    )

    result = compute_condition_rg(make_loaded_result(runtime))

    assert result.status == "partial"
    assert result.frame_results[0].rg_value is None
    assert [issue.kind for issue in result.frame_results[0].issues] == [
        "invalid_rg_value"
    ]


def test_missing_rg_method_reports_computation_error() -> None:
    runtime = FakeRuntime(object(), [FakeTimestep()])

    result = compute_condition_rg(make_loaded_result(runtime))

    assert result.status == "failed"
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "rg_computation_error"
    ]
    assert (
        result.issues[0].field
        == "runtime_object.atoms.radius_of_gyration"
    )


def test_iteration_error_before_frames_returns_failed() -> None:
    result = compute_condition_rg(
        make_loaded_result(
            FakeRuntime(FakeAtoms([10.0]), FailingBeforeTrajectory())
        )
    )

    assert result.status == "failed"
    assert result.passed is False
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]


def test_iteration_error_after_frames_preserves_partial_results() -> None:
    result = compute_condition_rg(
        make_loaded_result(
            FakeRuntime(FakeAtoms([10.0]), FailingAfterTrajectory())
        )
    )

    assert result.status == "partial"
    assert result.passed is False
    assert result.frame_count == 1
    assert result.frame_results[0].rg_value == 10.0
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]


def test_custom_rg_unit_is_propagated() -> None:
    runtime = FakeRuntime(FakeAtoms([10.0]), [FakeTimestep()])

    result = compute_condition_rg(
        make_loaded_result(runtime),
        rg_unit="test_unit",
    )

    assert result.rg_unit == "test_unit"
    assert result.frame_results[0].rg_unit == "test_unit"


def test_empty_trajectory_fails_deterministically() -> None:
    result = compute_condition_rg(
        make_loaded_result(FakeRuntime(FakeAtoms([]), []))
    )

    assert result.status == "failed"
    assert result.passed is False
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]
    assert result.issues[0].message == "Runtime trajectory produced no frames."


def test_runtime_object_is_not_serialized() -> None:
    runtime = FakeRuntime(FakeAtoms([10.0]), [FakeTimestep()])

    payload = compute_condition_rg(make_loaded_result(runtime)).to_dict()

    assert "runtime_object" not in payload
    assert repr(runtime) not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_source_has_only_condition_scoped_rg_computation() -> None:
    source_text = RG_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "require_mdanalysis",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "collect_condition_runtime_metadata",
        "collect_manifest_runtime_metadata",
        "extract_condition_residue_names",
        "extract_manifest_residue_names",
        "run_residue_qc_from_manifest_options",
        "compute_manifest_rg",
        "compute_manifest_condition_rg",
        "compute_manifest_rgs",
        "rg_timeseries",
        "comparison",
        "tolerance",
        "contacts",
        "graph",
        "edges",
        "nodes",
        "select_atoms",
        ".positions",
        ".coordinates",
    ):
        assert forbidden_text not in source_text


def test_source_has_no_forbidden_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in RG_MODULE_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None


def test_explicit_selection_matches_legacy_science_and_pbc():
    from test_preprocessing_pbc_observation_integration import SAMPLING, loading

    from mania.preprocessing.trajectory_frame_sampling import (
        PreprocessingFrameSamplingOptions,
    )

    source, runtimes = loading(names=("normal",))
    condition = source.runtime_load_result.condition_results[0]
    before = compute_condition_rg(condition, frame_sampling=SAMPLING)
    observations = []
    after = compute_condition_rg(
        condition,
        source_frame_indexes=(1, 3, 5),
        pbc_observation_callback=observations.append,
    )
    assert before.passed and after.passed
    assert before.to_dict() == after.to_dict()
    assert [f.frame_index for f in after.frame_results] == [1, 3, 5]
    assert [o.frame_index for o in observations] == [1, 3, 5]
    assert runtimes[0].trajectory.passes == 2
    with pytest.raises(ValueError, match="mutually exclusive"):
        compute_condition_rg(
            condition,
            frame_sampling=PreprocessingFrameSamplingOptions(),
            source_frame_indexes=(1, 3, 5),
        )
