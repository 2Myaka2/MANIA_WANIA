"""Load one preprocessing condition through the optional scientific runtime."""

from __future__ import annotations

from mania.preprocessing.scientific_runtime import (
    PreprocessingOptionalDependencyError,
    require_mdanalysis,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingTrajectoryLoadIssue,
)

MDANALYSIS_NAME = "MD" + "Analysis"


def load_single_condition_runtime(
    runtime_input: PreprocessingConditionRuntimeInput,
) -> PreprocessingConditionLoadResult:
    """Load one declared topology and its trajectories."""
    path_issues = _validate_paths(runtime_input)
    if path_issues:
        return _failed_result(runtime_input, path_issues)

    try:
        mda = require_mdanalysis()
    except PreprocessingOptionalDependencyError as exc:
        issue = PreprocessingTrajectoryLoadIssue(
            kind="missing_optional_dependency",
            field=MDANALYSIS_NAME,
            message=str(exc),
        )
        return _failed_result(runtime_input, (issue,))

    try:
        universe = mda.Universe(
            str(runtime_input.topology_path),
            *[str(path) for path in runtime_input.trajectory_paths],
        )
    except Exception:
        issue = PreprocessingTrajectoryLoadIssue(
            kind="load_error",
            field=f"{MDANALYSIS_NAME}.Universe",
            message=(
                "The scientific runtime could not load the declared "
                "topology and trajectory files."
            ),
            path=runtime_input.topology_path,
        )
        return _failed_result(runtime_input, (issue,))

    runtime = PreprocessingConditionRuntime(
        condition_name=runtime_input.condition_name,
        runtime_object=universe,
        runtime_type=_runtime_type(universe),
        topology_path=runtime_input.topology_path,
        trajectory_paths=runtime_input.trajectory_paths,
    )
    return PreprocessingConditionLoadResult(
        condition_name=runtime_input.condition_name,
        runtime_input=runtime_input,
        runtime=runtime,
        issues=(),
        status="loaded",
    )


def _validate_paths(
    runtime_input: PreprocessingConditionRuntimeInput,
) -> tuple[PreprocessingTrajectoryLoadIssue, ...]:
    issues: list[PreprocessingTrajectoryLoadIssue] = []
    topology_path = runtime_input.topology_path
    if not topology_path.exists():
        issues.append(
            PreprocessingTrajectoryLoadIssue(
                kind="missing_topology_path",
                field="topology_path",
                message="The declared topology path does not exist.",
                path=topology_path,
            )
        )
    elif not topology_path.is_file():
        issues.append(
            PreprocessingTrajectoryLoadIssue(
                kind="topology_not_file",
                field="topology_path",
                message="The declared topology path is not a file.",
                path=topology_path,
            )
        )

    if not runtime_input.trajectory_paths:
        issues.append(
            PreprocessingTrajectoryLoadIssue(
                kind="missing_trajectory_path",
                field="trajectory_paths",
                message="At least one trajectory path is required.",
            )
        )

    for index, trajectory_path in enumerate(runtime_input.trajectory_paths):
        field = f"trajectory_paths[{index}]"
        if not trajectory_path.exists():
            issues.append(
                PreprocessingTrajectoryLoadIssue(
                    kind="missing_trajectory_path",
                    field=field,
                    message="The declared trajectory path does not exist.",
                    path=trajectory_path,
                )
            )
        elif not trajectory_path.is_file():
            issues.append(
                PreprocessingTrajectoryLoadIssue(
                    kind="trajectory_not_file",
                    field=field,
                    message="The declared trajectory path is not a file.",
                    path=trajectory_path,
                )
            )

    return tuple(issues)


def _failed_result(
    runtime_input: PreprocessingConditionRuntimeInput,
    issues: tuple[PreprocessingTrajectoryLoadIssue, ...],
) -> PreprocessingConditionLoadResult:
    return PreprocessingConditionLoadResult(
        condition_name=runtime_input.condition_name,
        runtime_input=runtime_input,
        runtime=None,
        issues=issues,
        status="failed",
    )


def _runtime_type(runtime_object: object) -> str:
    cls = runtime_object.__class__
    return f"{cls.__module__}.{cls.__qualname__}"


__all__ = ["load_single_condition_runtime"]
