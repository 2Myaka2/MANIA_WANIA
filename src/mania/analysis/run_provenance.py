"""Pure construction of portable passports for existing analysis executions."""

from collections.abc import Mapping
from datetime import UTC, datetime

from mania.analysis.orchestration import AnalyzeRequest, AnalyzeRunResult
from mania.run_provenance import (
    PortableArtifactReference,
    RunProvenance,
    RunProvenanceIssue,
)
from mania.software_identity import SoftwareIdentity

ANALYSIS_RUN_PROVENANCE_WORKFLOW = "analysis"
ANALYSIS_RUN_PROVENANCE_DIRNAME = "analysis"
ANALYSIS_RUN_FAILURE_STAGE = "analysis_execution"
ANALYSIS_RUN_ID_PREFIX = "analysis"


class AnalysisRunProvenanceBuildError(ValueError):
    """Analysis metadata cannot form a valid portable passport."""


def analysis_run_id_from_started_at(started_at_utc: datetime) -> str:
    """Name the current analysis execution using a supplied aware timestamp."""
    if not isinstance(started_at_utc, datetime) or started_at_utc.utcoffset() is None:
        raise AnalysisRunProvenanceBuildError(
            "started_at_utc must be a timezone-aware datetime"
        )
    try:
        value = started_at_utc.astimezone(UTC)
    except (ValueError, OverflowError):
        raise AnalysisRunProvenanceBuildError("Start timestamp is invalid.") from None
    return (
        f"{ANALYSIS_RUN_ID_PREFIX}-{value.year:04d}{value.month:02d}{value.day:02d}T"
        f"{value.hour:02d}{value.minute:02d}{value.second:02d}{value.microsecond:06d}Z"
    )


def collect_analysis_artifact_references(
    result: AnalyzeRunResult,
) -> tuple[PortableArtifactReference, ...]:
    """Link known result paths lexically, without observing files or symlinks."""
    if type(result) is not AnalyzeRunResult:
        raise AnalysisRunProvenanceBuildError("result must be AnalyzeRunResult")
    try:
        paths = [
            (role, path)
            for condition in result.condition_results
            for role, path in (
                ("analysis_graph", condition.graph_json),
                ("analysis_centrality", condition.centrality_csv),
                ("analysis_communities", condition.communities_csv),
                ("analysis_region_enrichment", condition.region_enrichment_csv),
                ("analysis_temporal_rin", condition.temporal_rin_csv),
                ("analysis_conformation_pca", condition.conformation_pca_csv),
                ("analysis_conformation_labels", condition.conformation_labels_csv),
            )
        ]
        paths.extend(
            (
                ("analysis_comparison", result.comparison_csv),
                ("analysis_stats", result.stats_csv),
            )
        )
        if result.extended_metrics_json is not None:
            paths.append(("analysis_manifest", result.extended_metrics_json))
        if any(path.name == "run_provenance.json" for _, path in paths):
            raise ValueError("Provenance is not an analysis artifact.")
        return tuple(
            PortableArtifactReference(
                role, path.relative_to(result.request.output_root).as_posix()
            )
            for role, path in paths
        )
    except (AttributeError, TypeError, ValueError):
        raise AnalysisRunProvenanceBuildError(
            "Analysis artifact paths must be portable and inside the output root."
        ) from None


def build_completed_analysis_run_provenance(
    result: AnalyzeRunResult,
    *,
    run_id: str,
    started_at_utc: datetime,
    ended_at_utc: datetime,
    software_identity: SoftwareIdentity,
    command: tuple[str, ...],
    resolved_configuration: Mapping[str, object],
    additional_artifact_references: tuple[PortableArtifactReference, ...] = (),
) -> RunProvenance:
    """Describe existing analysis outputs; upstream sampling stays upstream."""
    if type(result) is not AnalyzeRunResult:
        raise AnalysisRunProvenanceBuildError("result must be AnalyzeRunResult")
    references = collect_analysis_artifact_references(result)
    try:
        return RunProvenance(
            run_id=run_id,
            workflow=ANALYSIS_RUN_PROVENANCE_WORKFLOW,
            status="completed",
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            software_identity=software_identity,
            command=command,
            resolved_configuration=resolved_configuration,
            conditions=result.request.conditions,
            sampling_by_condition=(),
            artifact_references=references + additional_artifact_references,
        )
    except (AttributeError, TypeError, ValueError, OverflowError):
        raise AnalysisRunProvenanceBuildError(
            "Completed analysis metadata is invalid."
        ) from None


def build_failed_analysis_run_provenance(
    request: AnalyzeRequest,
    *,
    run_id: str,
    started_at_utc: datetime,
    ended_at_utc: datetime,
    software_identity: SoftwareIdentity,
    command: tuple[str, ...],
    resolved_configuration: Mapping[str, object],
    additional_artifact_references: tuple[PortableArtifactReference, ...] = (),
) -> RunProvenance:
    """Record failure without claiming partial outputs or copying exception text."""
    if type(request) is not AnalyzeRequest:
        raise AnalysisRunProvenanceBuildError("request must be AnalyzeRequest")
    try:
        return RunProvenance(
            run_id=run_id,
            workflow=ANALYSIS_RUN_PROVENANCE_WORKFLOW,
            status="failed",
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            software_identity=software_identity,
            command=command,
            resolved_configuration=resolved_configuration,
            conditions=request.conditions,
            sampling_by_condition=(),
            artifact_references=additional_artifact_references,
            issues=(
                RunProvenanceIssue(
                    severity="error",
                    code="analysis_execution_failed",
                    message="Analysis workflow failed.",
                    stage=ANALYSIS_RUN_FAILURE_STAGE,
                    condition=None,
                ),
            ),
        )
    except (TypeError, ValueError, OverflowError):
        raise AnalysisRunProvenanceBuildError(
            "Failed analysis metadata is invalid."
        ) from None


__all__ = [
    "ANALYSIS_RUN_FAILURE_STAGE",
    "ANALYSIS_RUN_ID_PREFIX",
    "ANALYSIS_RUN_PROVENANCE_DIRNAME",
    "ANALYSIS_RUN_PROVENANCE_WORKFLOW",
    "AnalysisRunProvenanceBuildError",
    "analysis_run_id_from_started_at",
    "build_completed_analysis_run_provenance",
    "build_failed_analysis_run_provenance",
    "collect_analysis_artifact_references",
]
