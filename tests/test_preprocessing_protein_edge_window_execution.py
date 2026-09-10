"""Stage 28.D routes retained evidence and delegates all scientific transformation."""

import builtins
import io
import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_preprocessing_protein_edge_window_table import pair, table_input

from mania.preprocessing import physical_time_execution, physical_time_sampling
from mania.preprocessing import protein_edge_window_execution as execution
from mania.preprocessing import trajectory_contacts as contacts
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.protein_edge_window_table import (
    DatasetProteinEdgeWindowTableInput,
    build_dataset_protein_edge_window_table,
)
from mania.preprocessing.protein_edge_window_table_io import (
    read_dataset_protein_edge_window_csv,
    write_dataset_protein_edge_window_csv,
)
from mania.preprocessing.protein_edge_windows import aggregate_protein_edges_by_window

build = execution.build_preprocessing_protein_edge_window_source_table
Error = execution.PreprocessingProteinEdgeWindowExecutionError


def retained(*, route=None, positive=(0, 1, 3, 4), **kwargs):
    binding = table_input(**kwargs).temporal_execution
    if route is not None:
        binding = replace(binding, execution_condition=route)
    result = contacts.PreprocessingConditionContactsResult(
        condition_name=binding.execution_condition,
        options=contacts.PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
        status="computed",
        frame_results=tuple(
            contacts.PreprocessingContactFrameResult(
                condition_name=binding.execution_condition,
                frame_index=sample.source_frame_index,
                time_ps=sample.actual_time_ps,
                contacts=(pair(),) if sample.requested_sample_index in positive else (),
            )
            for sample in binding.sampling_plan.selected_samples
        ),
    )
    return binding, result


def manifest(*results):
    return contacts.PreprocessingManifestContactsResult(tuple(results))


def direct(temporal, contact_results):
    results = {c.condition_name: c for c in contact_results.condition_results}
    return build_dataset_protein_edge_window_table(
        tuple(
            DatasetProteinEdgeWindowTableInput(
                b,
                aggregate_protein_edges_by_window(
                    b.sampling_plan,
                    b.window_plan,
                    contacts_result=results[b.execution_condition],
                ),
            )
            for b in temporal.bindings
        )
    )


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("legacy", [False, True])
def test_exact_delegation_replica_identity_and_determinism(
    monkeypatch, tmp_path, count, legacy
):
    # Nullable scientific condition is shared across replicas; routing is separate.
    pairs = [
        retained(
            condition=None,
            engine="namd",
            route=f"route-{i}",
            replica_id=str(i),
            trajectory_id=f"trajectory-{i}",
        )
        for i in range(count)
    ]
    temporal = PreprocessingTemporalExecution(tuple(b for b, _ in pairs))
    results = [r for _, r in reversed(pairs)]
    if legacy:
        results.append(retained(condition="legacy-only")[1])
    contact_results = manifest(*results)
    expected = direct(temporal, contact_results)
    aggregate = Mock(wraps=execution.aggregate_protein_edges_by_window)
    transform = Mock(wraps=execution.build_dataset_protein_edge_window_table)
    monkeypatch.setattr(execution, "aggregate_protein_edges_by_window", aggregate)
    monkeypatch.setattr(execution, "build_dataset_protein_edge_window_table", transform)
    actual = build(temporal, contact_results)
    assert actual.to_dict() == expected.to_dict()
    assert aggregate.call_count == count
    transform.assert_called_once()
    for call, (binding, result) in zip(aggregate.call_args_list, pairs, strict=True):
        assert call.args == (binding.sampling_plan, binding.window_plan)
        assert call.kwargs == {"contacts_result": result}
    assert {r.replica_id for r in actual.rows} == {str(i) for i in range(count)}
    assert all(r.condition is None for r in actual.rows)
    paths = [
        write_dataset_protein_edge_window_csv(t, tmp_path / str(i)).output_path
        for i, t in enumerate((actual, expected, build(temporal, contact_results)))
    ]
    assert paths[0].read_bytes() == paths[1].read_bytes() == paths[2].read_bytes()
    assert json.dumps(actual.to_dict()) == json.dumps(
        build(temporal, contact_results).to_dict()
    )


@pytest.mark.parametrize("missing,occupancy", [((), 0.8), ((2,), 1.0)])
def test_missing_and_resolved_negative_through_final_csv(tmp_path, missing, occupancy):
    binding, result = retained(missing=missing)
    table = build(PreprocessingTemporalExecution((binding,)), manifest(result))
    written = write_dataset_protein_edge_window_csv(table, tmp_path)
    assert written.passed
    row = read_dataset_protein_edge_window_csv(written.output_path).rows[0]
    assert row.requested_sample_count == 5 and row.resolved_frame_count == 5 - len(
        missing
    )
    assert row.n_contact_frames == 4
    assert row.occupancy == row.edge_weight == occupancy
    assert row.n_contact_episodes == 2
    assert row.mean_episode_length_ns == row.max_episode_length_ns == 0.05


def test_sparse_empty_and_backbone_exclusion(tmp_path):
    binding, result = retained(positive=())
    table = build(PreprocessingTemporalExecution((binding,)), manifest(result))
    assert table.rows == ()
    path = write_dataset_protein_edge_window_csv(table, tmp_path).output_path
    assert len(path.read_text().splitlines()) == 1
    assert read_dataset_protein_edge_window_csv(path).rows == ()


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "failed", "nonprotein", "coverage"]
)
def test_invalid_contact_evidence_is_portable(damage):
    binding, result = retained()
    if damage == "failed":
        result = replace(result, status="not_computed")
    if damage == "nonprotein":
        result = replace(
            result, options=contacts.PreprocessingContactDetectionOptions()
        )
    if damage == "coverage":
        result = replace(result, frame_results=result.frame_results[:-1])
    results = manifest(result)
    if damage == "missing":
        results = manifest(retained(condition="wrong-route")[1])
    if damage == "duplicate":
        object.__setattr__(results, "condition_results", (result, result))
    with pytest.raises(Error) as caught:
        build(PreprocessingTemporalExecution((binding,)), results)
    assert "/" not in str(caught.value) and "Traceback" not in str(caught.value)


@pytest.mark.parametrize("wrong", [None, (), object()])
def test_exact_root_types(wrong):
    binding, result = retained()
    with pytest.raises(Error, match="exact"):
        build(wrong, manifest(result))
    with pytest.raises(Error, match="exact"):
        build(PreprocessingTemporalExecution((binding,)), wrong)


def test_pure_integration_has_no_runtime_or_io(monkeypatch):
    binding, result = retained()
    temporal, results = PreprocessingTemporalExecution((binding,)), manifest(result)
    forbidden = Mock(side_effect=AssertionError("Unexpected runtime/I/O"))
    for owner, names in (
        (builtins, ("open",)),
        (io, ("open",)),
        (Path, ("open", "stat", "iterdir")),
        (subprocess, ("run", "Popen")),
        (time, ("time", "monotonic", "perf_counter")),
        (physical_time_execution, ("collect_runtime_physical_time_source_frames",)),
        (physical_time_sampling, ("resolve_physical_time_sampling",)),
        (contacts, ("compute_condition_contacts", "compute_manifest_contacts")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    assert build(temporal, results).rows[0].occupancy == 0.8
    forbidden.assert_not_called()
