"""Preprocessing runtime summaries reuse accepted in-memory counters only."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_preprocessing_pbc_observation_integration import SAMPLING, loading
from test_runtime_metadata import START, environment, guard_observation_io

from mania.preprocessing.runtime_metadata import (
    PreprocessingRuntimeMetadataBuildError,
    build_preprocessing_runtime_metadata,
)
from mania.preprocessing.trajectory_graph_workflow import (
    compute_preprocessing_graph_workflow_rg_contacts,
)


@pytest.mark.parametrize("contacts", [False, True])
def test_reuses_retained_counts_and_timestamps_without_io(monkeypatch, contacts):
    source, runtimes = loading()
    computation = compute_preprocessing_graph_workflow_rg_contacts(
        source,
        include_contacts=contacts,
        frame_sampling=SAMPLING,
        collect_pbc_observations=True,
    )
    before = computation.to_dict()
    for runtime in runtimes:
        runtime.trajectory = None
    with monkeypatch.context() as patch:
        forbidden = guard_observation_io(patch)
        model = build_preprocessing_runtime_metadata(
            run_id="run-1",
            started_at_utc=START,
            ended_at_utc=START + timedelta(seconds=12),
            environment=environment(),
            computation=computation,
        )
        forbidden.assert_not_called()
    assert computation.to_dict() == before
    assert model.run_id == "run-1" and model.workflow == "preprocessing_graph_export"
    assert (
        model.scope == "preprocessing"
        and model.metadata_path == "runtime_metadata.json"
    )
    assert model.performance.condition_count == 2
    assert (
        model.performance.sampled_frame_count == len(computation.pbc_observations) == 6
    )
    assert model.performance.wall_clock_seconds == 12
    assert model.performance.seconds_per_sampled_frame == 2
    assert model.performance.contact_frame_count == (
        computation.contacts_result.frame_count if contacts else None
    )
    assert model.performance.contact_observation_count == (
        computation.contacts_result.contact_count if contacts else None
    )


def test_incompatible_contacts_are_rejected_without_guessing():
    source, _ = loading()
    computation = compute_preprocessing_graph_workflow_rg_contacts(source)
    with pytest.raises(
        PreprocessingRuntimeMetadataBuildError, match="Retained contacts"
    ):
        build_preprocessing_runtime_metadata(
            run_id="run",
            started_at_utc=START,
            ended_at_utc=START,
            environment=environment(),
            computation=replace(computation, contacts_result=object()),
        )
