"""Compose preprocessing runtime metadata from retained results and timestamps."""

from datetime import datetime

from mania.preprocessing.run_provenance import PREPROCESSING_RUN_PROVENANCE_WORKFLOW
from mania.preprocessing.trajectory_contacts import PreprocessingManifestContactsResult
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowComputationResult,
)
from mania.runtime_metadata import (
    RUNTIME_METADATA_FILENAME,
    RuntimeEnvironment,
    RuntimeMetadata,
    build_runtime_metadata,
    build_runtime_performance,
)

PREPROCESSING_RUNTIME_METADATA_PATH = RUNTIME_METADATA_FILENAME
PREPROCESSING_RUNTIME_METADATA_ROLE = "runtime_metadata"


class PreprocessingRuntimeMetadataBuildError(ValueError):
    """Retained computation cannot supply accepted runtime counters."""


def build_preprocessing_runtime_metadata(
    *,
    run_id: str,
    started_at_utc: datetime,
    ended_at_utc: datetime,
    environment: RuntimeEnvironment,
    computation: PreprocessingGraphWorkflowComputationResult,
) -> RuntimeMetadata:
    """Reuse the canonical observation count and aggregate contact counters."""
    if not isinstance(computation, PreprocessingGraphWorkflowComputationResult):
        raise PreprocessingRuntimeMetadataBuildError(
            "computation must be PreprocessingGraphWorkflowComputationResult"
        )
    contacts = computation.contacts_result
    if contacts is not None and not isinstance(
        contacts, PreprocessingManifestContactsResult
    ):
        raise PreprocessingRuntimeMetadataBuildError(
            "Retained contacts must be PreprocessingManifestContactsResult"
        )
    try:
        performance = build_runtime_performance(
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            condition_count=computation.condition_count,
            sampled_frame_count=len(computation.pbc_observations),
            contact_frame_count=None if contacts is None else contacts.frame_count,
            contact_observation_count=(
                None if contacts is None else contacts.contact_count
            ),
        )
        return build_runtime_metadata(
            run_id=run_id,
            workflow=PREPROCESSING_RUN_PROVENANCE_WORKFLOW,
            scope="preprocessing",
            metadata_path=PREPROCESSING_RUNTIME_METADATA_PATH,
            environment=environment,
            performance=performance,
        )
    except (TypeError, ValueError, AttributeError, OverflowError):
        raise PreprocessingRuntimeMetadataBuildError(
            "Runtime metadata inputs are invalid."
        ) from None


__all__ = [
    "PREPROCESSING_RUNTIME_METADATA_PATH",
    "PREPROCESSING_RUNTIME_METADATA_ROLE",
    "PreprocessingRuntimeMetadataBuildError",
    "build_preprocessing_runtime_metadata",
]
