"""Observe retained preprocessing sampling results without computation or I/O."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from math import fsum, isclose, isfinite
from typing import Literal

from mania.preprocessing.dataset_binding import PreprocessingDatasetContext
from mania.preprocessing.trajectory_contacts import (
    PreprocessingConditionContactsResult,
    PreprocessingContactFrameResult,
    PreprocessingManifestContactsResult,
)
from mania.preprocessing.trajectory_frame_sampling import (
    PreprocessingFrameSamplingOptions,
)
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowComputationResult,
)
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadResult,
)
from mania.preprocessing.trajectory_metadata import collect_condition_runtime_metadata
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
    EffectiveFrameSampling,
    PortableArtifactReference,
    RequestedFrameSampling,
    RunProvenance,
    RunProvenanceIssue,
    RunProvenanceIssueSeverity,
    TimeSpacingStatus,
)
from mania.software_identity import SoftwareIdentity

PREPROCESSING_RUN_PROVENANCE_WORKFLOW = "preprocessing_graph_export"
PREPROCESSING_SAMPLING_STAGE = "preprocessing_sampling"
PREPROCESSING_SAMPLING_TIME_REL_TOL = 1e-9
PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS = 1e-9

PreprocessingRunFailureStage = Literal[
    "plan",
    "runtime_loading",
    "computation",
    "graph_export",
    "analysis_input_export",
    "scientific_csv_export",
    "diagnostics",
    "reference_comparison",
    "protein_edge_window_export",
    "specialized_contact_export",
    "canonical_table_export",
    "annotated_table_export",
]
PREPROCESSING_RUN_FAILURE_STAGES: tuple[PreprocessingRunFailureStage, ...] = (
    "plan",
    "runtime_loading",
    "computation",
    "graph_export",
    "analysis_input_export",
    "scientific_csv_export",
    "diagnostics",
    "reference_comparison",
    "protein_edge_window_export",
    "specialized_contact_export",
    "canonical_table_export",
    "annotated_table_export",
)

_Observations = tuple[tuple[int, float | None], ...]


class PreprocessingRunProvenanceBuildError(ValueError):
    """Preprocessing metadata cannot form a valid portable passport."""


def build_completed_preprocessing_run_provenance(
    computation: PreprocessingGraphWorkflowComputationResult,
    *,
    run_id: str,
    started_at_utc: datetime,
    ended_at_utc: datetime,
    software_identity: SoftwareIdentity,
    command: tuple[str, ...],
    resolved_configuration: Mapping[str, object],
    artifact_references: tuple[PortableArtifactReference, ...],
    dataset_context: PreprocessingDatasetContext | None = None,
) -> RunProvenance:
    """Combine caller snapshots and retained sampling, without time or file I/O."""
    if type(computation) is not PreprocessingGraphWorkflowComputationResult:
        raise PreprocessingRunProvenanceBuildError(
            "computation must be PreprocessingGraphWorkflowComputationResult"
        )
    if not computation.passed:
        raise PreprocessingRunProvenanceBuildError("Computation must have passed.")
    sampling = collect_preprocessing_sampling_provenance(computation)
    if not sampling.passed:
        raise PreprocessingRunProvenanceBuildError(
            "Sampling collection contains errors."
        )
    try:
        return RunProvenance(
            run_id=run_id,
            workflow=PREPROCESSING_RUN_PROVENANCE_WORKFLOW,
            status="completed",
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            software_identity=software_identity,
            command=command,
            resolved_configuration=_dataset_configuration(
                resolved_configuration, dataset_context
            ),
            conditions=computation.condition_names,
            sampling_by_condition=sampling.sampling_by_condition,
            artifact_references=artifact_references,
            issues=sampling.issues,
        )
    except (TypeError, ValueError):
        raise PreprocessingRunProvenanceBuildError(
            "Completed run metadata is invalid."
        ) from None


def build_failed_preprocessing_run_provenance(
    *,
    run_id: str,
    failure_stage: PreprocessingRunFailureStage,
    started_at_utc: datetime,
    ended_at_utc: datetime,
    software_identity: SoftwareIdentity,
    command: tuple[str, ...],
    resolved_configuration: Mapping[str, object],
    conditions: tuple[str, ...],
    frame_sampling: PreprocessingFrameSamplingOptions,
    artifact_references: tuple[PortableArtifactReference, ...] = (),
    computation: PreprocessingGraphWorkflowComputationResult | None = None,
    dataset_context: PreprocessingDatasetContext | None = None,
) -> RunProvenance:
    """Record a workflow failure and any retained observations without I/O."""
    if failure_stage not in PREPROCESSING_RUN_FAILURE_STAGES:
        raise PreprocessingRunProvenanceBuildError(
            "Unsupported preprocessing failure stage."
        )
    if not isinstance(frame_sampling, PreprocessingFrameSamplingOptions):
        raise PreprocessingRunProvenanceBuildError(
            "frame_sampling must be PreprocessingFrameSamplingOptions"
        )
    if computation is not None and (
        type(computation) is not PreprocessingGraphWorkflowComputationResult
    ):
        raise PreprocessingRunProvenanceBuildError(
            "computation must be PreprocessingGraphWorkflowComputationResult"
        )
    try:
        if computation is None:
            requested = RequestedFrameSampling(
                frame_start=frame_sampling.frame_start,
                frame_stop=frame_sampling.frame_stop,
                frame_stride=frame_sampling.frame_stride,
                max_frames=frame_sampling.max_frames,
            )
            sampling = PreprocessingSamplingProvenanceResult(
                tuple(
                    ConditionSamplingProvenance(condition, requested, None)
                    for condition in conditions
                ),
                tuple(
                    _issue(
                        condition, "warning", "effective_sampling_unavailable",
                        "No retained frame observations are available.",
                    )
                    for condition in conditions
                ),
            )
        else:
            sampling = collect_preprocessing_sampling_provenance(computation)
        failure = RunProvenanceIssue(
            severity="error",
            code="preprocessing_stage_failed",
            message=f"Preprocessing workflow failed during {failure_stage}.",
            stage=failure_stage,
            condition=None,
        )
        return RunProvenance(
            run_id=run_id,
            workflow=PREPROCESSING_RUN_PROVENANCE_WORKFLOW,
            status="failed",
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            software_identity=software_identity,
            command=command,
            resolved_configuration=_dataset_configuration(
                resolved_configuration, dataset_context
            ),
            conditions=conditions,
            sampling_by_condition=sampling.sampling_by_condition,
            artifact_references=artifact_references,
            issues=(failure, *sampling.issues),
        )
    except (TypeError, ValueError):
        raise PreprocessingRunProvenanceBuildError(
            "Failed run metadata is invalid."
        ) from None


def _dataset_configuration(
    configuration: Mapping[str, object], context: PreprocessingDatasetContext | None,
) -> Mapping[str, object]:
    """Add only portable resolved context; preserve the legacy snapshot otherwise."""
    if context is None:
        return configuration
    if type(context) is not PreprocessingDatasetContext:
        raise ValueError("dataset_context must be PreprocessingDatasetContext")
    return {**configuration, "dataset_context": context.to_dict()}


@dataclass(frozen=True)
class PreprocessingSamplingProvenanceResult:
    """Immutable condition sampling snapshots and deterministic collection issues."""

    sampling_by_condition: tuple[ConditionSamplingProvenance, ...]
    issues: tuple[RunProvenanceIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.sampling_by_condition, tuple) or not all(
            isinstance(item, ConditionSamplingProvenance)
            for item in self.sampling_by_condition
        ):
            raise ValueError(
                "sampling_by_condition must be a tuple of ConditionSamplingProvenance"
            )
        names = [item.condition for item in self.sampling_by_condition]
        if len(set(names)) != len(names):
            raise ValueError("sampling condition names must be unique")
        if not isinstance(self.issues, tuple) or not all(
            isinstance(issue, RunProvenanceIssue) for issue in self.issues
        ):
            raise ValueError("issues must be a tuple of RunProvenanceIssue")

    @property
    def passed(self) -> bool:
        """Warnings alone do not fail collection."""
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        """Return fresh JSON-safe values in the adapter contract's key order."""
        return {
            "sampling_by_condition": [
                item.to_dict() for item in self.sampling_by_condition
            ],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
        }


class _ObservationError(ValueError):
    """A known observation failure with a portable, fixed message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def collect_preprocessing_sampling_provenance(
    computation: PreprocessingGraphWorkflowComputationResult,
) -> PreprocessingSamplingProvenanceResult:
    """Collect selected/attempted frames, preserving condition and record order."""
    if type(computation) is not PreprocessingGraphWorkflowComputationResult:
        raise ValueError(
            "computation must be PreprocessingGraphWorkflowComputationResult"
        )
    options = computation.frame_sampling
    requested = RequestedFrameSampling(
        frame_start=options.frame_start,
        frame_stop=options.frame_stop,
        frame_stride=options.frame_stride,
        max_frames=options.max_frames,
    )
    sampling: list[ConditionSamplingProvenance] = []
    issues: list[RunProvenanceIssue] = []
    for condition in computation.condition_names:
        source_count = _source_frame_count(computation, condition)
        if source_count is None:
            issues.append(
                _issue(
                    condition,
                    "warning",
                    "source_frame_count_unavailable",
                    "Source trajectory frame count is unavailable.",
                )
            )
        effective = None
        try:
            contacts = _frame_observations(computation.contacts_result, condition, True)
            rg = _frame_observations(computation.rg_result, condition, False)
            for observations in (contacts, rg):
                if observations is not None:
                    _validate_indexes(observations, requested)
                    _validate_source_count(observations, source_count)
                    _validate_times(observations)
            observations = _reconcile(contacts, rg)
            if observations is None:
                issues.append(
                    _issue(
                        condition,
                        "warning",
                        "effective_sampling_unavailable",
                        "No retained frame observations are available.",
                    )
                )
            else:
                effective = _effective_sampling(observations, source_count)
        except _ObservationError as error:
            issues.append(_issue(condition, "error", error.code, error.message))
        sampling.append(ConditionSamplingProvenance(condition, requested, effective))
    return PreprocessingSamplingProvenanceResult(tuple(sampling), tuple(issues))


def _issue(
    condition: str,
    severity: RunProvenanceIssueSeverity,
    code: str,
    message: str,
) -> RunProvenanceIssue:
    return RunProvenanceIssue(
        severity,
        code,
        message,
        stage=PREPROCESSING_SAMPLING_STAGE,
        condition=condition,
    )


def _source_frame_count(
    computation: PreprocessingGraphWorkflowComputationResult,
    condition: str,
) -> int | None:
    loaded = computation.runtime_loading.runtime_load_result
    if not isinstance(loaded, PreprocessingManifestLoadResult):
        return None
    for result in loaded.condition_results:
        if (
            isinstance(result, PreprocessingConditionLoadResult)
            and result.condition_name == condition
            and isinstance(result.runtime, PreprocessingConditionRuntime)
            and isinstance(result.runtime_input, PreprocessingConditionRuntimeInput)
        ):
            # The helper uses count attributes or len(), never frame iteration.
            # Unrelated metadata issues do not discard a successfully read count.
            return collect_condition_runtime_metadata(result).frame_count
    return None


def _frame_observations(
    source: object | None,
    condition: str,
    contacts: bool,
) -> _Observations | None:
    if source is None:
        return None
    manifest_type = (
        PreprocessingManifestContactsResult
        if contacts
        else PreprocessingManifestRgResult
    )
    condition_type = (
        PreprocessingConditionContactsResult
        if contacts
        else PreprocessingConditionRgResult
    )
    frame_type = (
        PreprocessingContactFrameResult if contacts else PreprocessingRgFrameResult
    )
    invalid = _ObservationError(
        "invalid_frame_observation_source",
        "Retained frame observation source is invalid.",
    )
    if not isinstance(source, manifest_type):
        raise invalid
    matches = []
    for result in source.condition_results:
        if not isinstance(result, condition_type):
            raise invalid
        if result.condition_name == condition:
            matches.append(result)
    if not matches:
        return None
    if len(matches) != 1:
        raise invalid
    frames = matches[0].frame_results
    if not isinstance(frames, tuple) or not all(
        isinstance(frame, frame_type) for frame in frames
    ):
        raise invalid
    return tuple((frame.frame_index, frame.time_ps) for frame in frames)


def _validate_indexes(
    observations: _Observations,
    requested: RequestedFrameSampling,
) -> None:
    previous = -1
    invalid = _ObservationError(
        "invalid_effective_frame_sequence",
        "Observed frame indexes do not satisfy the requested sampling constraints.",
    )
    if requested.max_frames is not None and len(observations) > requested.max_frames:
        raise invalid
    for index, _ in observations:
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index <= previous
            or index < requested.frame_start
            or (requested.frame_stop is not None and index >= requested.frame_stop)
            or (index - requested.frame_start) % requested.frame_stride != 0
        ):
            raise invalid
        previous = index


def _validate_source_count(observations: _Observations, count: int | None) -> None:
    if count is not None and (
        len(observations) > count or any(index >= count for index, _ in observations)
    ):
        raise _ObservationError(
            "source_frame_count_inconsistent",
            "Observed frames exceed the available source trajectory frame count.",
        )


def _validate_times(observations: _Observations) -> None:
    for _, time in observations:
        if time is None:
            continue
        try:
            valid = (
                not isinstance(time, bool)
                and isinstance(time, (int, float))
                and isfinite(time)
                and time >= 0
            )
        except OverflowError:
            valid = False
        if not valid:
            raise _ObservationError(
                "invalid_effective_sampling",
                "Observed times must be finite and non-negative when available.",
            )


def _close(left: float, right: float) -> bool:
    return isclose(
        left,
        right,
        rel_tol=PREPROCESSING_SAMPLING_TIME_REL_TOL,
        abs_tol=PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS,
    )


def _reconcile(
    contacts: _Observations | None,
    rg: _Observations | None,
) -> _Observations | None:
    if contacts is None:
        return rg
    if rg is None:
        return contacts
    if tuple(index for index, _ in contacts) != tuple(index for index, _ in rg):
        raise _ObservationError(
            "frame_observation_mismatch",
            "Contact and Rg frame index sequences disagree.",
        )
    reconciled = []
    for (index, contact_time), (_, rg_time) in zip(contacts, rg, strict=True):
        if contact_time is None:
            time = rg_time
        elif rg_time is None:
            time = contact_time
        elif _close(contact_time, rg_time):
            # A symmetric deterministic choice, independent of source preference.
            time = min(contact_time, rg_time)
        else:
            raise _ObservationError(
                "frame_time_mismatch",
                "Contact and Rg frame times disagree.",
            )
        reconciled.append((index, time))
    return tuple(reconciled)


def _effective_sampling(
    observations: _Observations,
    source_count: int | None,
) -> EffectiveFrameSampling:
    status: TimeSpacingStatus = "unavailable"
    spacing = None
    times = [time for _, time in observations if time is not None]
    try:
        if len(times) == len(observations) and len(times) >= 2:
            differences = [
                right - left for left, right in zip(times, times[1:], strict=False)
            ]
            if all(
                isfinite(delta) and delta > 0 and _close(delta, differences[0])
                for delta in differences
            ):
                status = "uniform"
                spacing = fsum(differences) / len(differences)
            else:
                status = "non_uniform"
        return EffectiveFrameSampling(
            source_frame_count=source_count,
            sampled_frame_count=len(observations),
            first_source_frame_index=observations[0][0] if observations else None,
            last_source_frame_index=observations[-1][0] if observations else None,
            first_time_ps=observations[0][1] if observations else None,
            last_time_ps=observations[-1][1] if observations else None,
            time_spacing_status=status,
            observed_time_spacing_ps=spacing,
        )
    except (ValueError, OverflowError):
        raise _ObservationError(
            "invalid_effective_sampling",
            "Observed sampling cannot satisfy the effective sampling contract.",
        ) from None


__all__ = [
    "PREPROCESSING_SAMPLING_STAGE",
    "PREPROCESSING_SAMPLING_TIME_REL_TOL",
    "PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS",
    "PreprocessingSamplingProvenanceResult",
    "collect_preprocessing_sampling_provenance",
    "PREPROCESSING_RUN_PROVENANCE_WORKFLOW",
    "PreprocessingRunProvenanceBuildError",
    "build_completed_preprocessing_run_provenance",
    "PREPROCESSING_RUN_FAILURE_STAGES",
    "PreprocessingRunFailureStage",
    "build_failed_preprocessing_run_provenance",
]
