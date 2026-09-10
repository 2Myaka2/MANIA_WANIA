"""Synthetic Stage 28.C identity, temporal evidence, and metric preservation."""

import ast
import builtins
import inspect
import io
import json
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, Inexact, Rounded, localcontext
from math import nextafter
from pathlib import Path

import pytest

from mania.dataset_identity import (
    DatasetTemporalParameters,
    DatasetTrajectoryIdentity,
    DatasetTrajectorySpec,
)
from mania.preprocessing import contact_episodes, physical_time_execution
from mania.preprocessing import physical_time_sampling as sampling
from mania.preprocessing import physical_time_windows as windows
from mania.preprocessing import protein_edge_window_table as model
from mania.preprocessing import protein_edge_windows as aggregation
from mania.preprocessing import trajectory_contacts as contacts
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)
from mania.preprocessing.protein_edge_window_table import (
    DATASET_PROTEIN_EDGE_WINDOW_CSV_FILENAME,
    DATASET_PROTEIN_EDGE_WINDOW_TABLE_KIND,
    DATASET_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION,
    DatasetProteinEdgeWindowRow,
    DatasetProteinEdgeWindowTable,
    DatasetProteinEdgeWindowTableError,
    DatasetProteinEdgeWindowTableInput,
    build_dataset_protein_edge_window_table,
)

ROW_FIELDS = (
    "dataset_id",
    "system_id",
    "trajectory_id",
    "variant_id",
    "engine",
    "condition",
    "replica_id",
    "disulfide_state",
    "window_id",
    "window_index",
    "requested_window_start_ns",
    "requested_window_end_ns",
    "right_endpoint_inclusive",
    "effective_window_start_ns",
    "effective_window_end_ns",
    "requested_sample_count",
    "resolved_frame_count",
    "missing_sample_count",
    "coverage_fraction",
    "source_residue_index",
    "target_residue_index",
    "source_chain_id",
    "target_chain_id",
    "source_resid",
    "target_resid",
    "source_resname",
    "target_resname",
    "edge_type",
    "n_contact_frames",
    "occupancy",
    "n_contact_episodes",
    "mean_episode_length_ns",
    "max_episode_length_ns",
    "edge_weight",
)
METRIC_FIELDS = (
    "n_contact_frames",
    "occupancy",
    "n_contact_episodes",
    "mean_episode_length_ns",
    "max_episode_length_ns",
    "edge_weight",
)


def pair(**changes):
    return contacts.PreprocessingContactPairResult(
        **{
            "source_residue_index": 1,
            "target_residue_index": 7,
            "source_residue_id": 330,
            "target_residue_id": "440A",
            "source_resname": "ALA",
            "target_resname": "LYS",
            "source_segid": "A",
            "target_segid": "B",
            "minimum_distance": 3.0,
            **changes,
        }
    )


def table_input(
    *,
    count=5,
    missing=(),
    positive=(0, 1, 2, 4),
    observations=None,
    condition="NORM",
    engine="gromacs",
    trajectory_id="wt-test-r1",
    replica_id="1",
    disulfide_state=None,
    length=None,
    step=None,
    times=None,
):
    duration = Decimal(count - 1) * Decimal("0.05")
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
    identity = DatasetTrajectoryIdentity(
        dataset_id="napi2b-v1-test",
        system_id="wt-test",
        trajectory_id=trajectory_id,
        variant_id="WT",
        engine=engine,
        condition=condition,
        replica_id=replica_id,
        disulfide_state=disulfide_state,
    )
    times = tuple(5000.0 + i * 50 for i in range(count)) if times is None else times
    retained_times = tuple(actual for i, actual in enumerate(times) if i not in missing)
    source = tuple(
        sampling.PhysicalTimeSourceFrame(i, actual)
        for i, actual in enumerate(retained_times)
    )
    plan = sampling.resolve_physical_time_sampling(source, temporal=temporal)
    window_plan = windows.plan_physical_time_windows(plan, temporal=temporal)
    routing = condition if condition is not None else "legacy-namd-route"
    execution = PreprocessingConditionTemporalExecution(
        routing,
        DatasetTrajectorySpec(identity=identity, temporal=temporal),
        plan,
        window_plan,
    )
    if observations is None:
        observations = {i: (pair(),) for i in positive}
    result = contacts.PreprocessingConditionContactsResult(
        condition_name=routing,
        options=contacts.PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
        status="computed",
        frame_results=tuple(
            contacts.PreprocessingContactFrameResult(
                condition_name=routing,
                frame_index=sample.source_frame_index,
                time_ps=None,
                contacts=observations.get(sample.requested_sample_index, ()),
            )
            for sample in plan.selected_samples
        ),
    )
    aggregated = aggregation.aggregate_protein_edges_by_window(
        plan,
        window_plan,
        contacts_result=result,
    )
    return DatasetProteinEdgeWindowTableInput(execution, aggregated)


def table(**kwargs):
    return build_dataset_protein_edge_window_table((table_input(**kwargs),))


def serialized(value):
    return json.dumps(value.to_dict(), allow_nan=False, separators=(",", ":"))


def test_constants_public_api_frozen_models_and_field_order():
    assert (
        DATASET_PROTEIN_EDGE_WINDOW_CSV_FILENAME == "protein_edges_by_window_source.csv"
    )
    assert DATASET_PROTEIN_EDGE_WINDOW_TABLE_KIND == (
        "mania_dataset_protein_edges_by_window_source"
    )
    assert DATASET_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION == (
        "mania.dataset_protein_edges_by_window_source.v0.1"
    )
    assert issubclass(DatasetProteinEdgeWindowTableError, ValueError)
    assert model.__all__ == [
        "DATASET_PROTEIN_EDGE_WINDOW_CSV_FILENAME",
        "DATASET_PROTEIN_EDGE_WINDOW_TABLE_KIND",
        "DATASET_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION",
        "DatasetProteinEdgeWindowRow",
        "DatasetProteinEdgeWindowTable",
        "DatasetProteinEdgeWindowTableError",
        "DatasetProteinEdgeWindowTableInput",
        "build_dataset_protein_edge_window_table",
    ]
    item = table_input()
    result = build_dataset_protein_edge_window_table((item,))
    assert type(result.rows[0]) is DatasetProteinEdgeWindowRow
    assert tuple(f.name for f in fields(item)) == ("temporal_execution", "aggregation")
    assert tuple(f.name for f in fields(result.rows[0])) == ROW_FIELDS
    assert tuple(result.rows[0].to_dict()) == ROW_FIELDS
    assert tuple(result.to_dict()) == ("schema_version", "kind", "row_count", "rows")
    assert tuple(f.name for f in fields(result)) == ("rows", "schema_version", "kind")
    for value, name in (
        (item, "aggregation"),
        (result, "rows"),
        (result.rows[0], "condition"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, name, None)
    for name in ("schema_version", "kind"):
        with pytest.raises(ValueError, match="init=False"):
            replace(result, **{name: "changed"})
    assert result.schema_version == DATASET_PROTEIN_EDGE_WINDOW_TABLE_SCHEMA_VERSION
    assert result.kind == DATASET_PROTEIN_EDGE_WINDOW_TABLE_KIND
    data = result.to_dict()
    data["rows"][0]["condition"] = "changed"
    data["rows"].clear()
    assert serialized(result) == serialized(table())


@pytest.mark.parametrize(
    ("missing", "positive", "resolved", "occupancy", "mean", "maximum"),
    [((), (0, 1, 2, 4), 5, 0.8, 0.05, 0.1), ((2,), (0, 1, 3, 4), 4, 1.0, 0.05, 0.05)],
)
def test_scientific_source_smoke_and_exact_metric_preservation(
    missing,
    positive,
    resolved,
    occupancy,
    mean,
    maximum,
):
    item = table_input(missing=missing, positive=positive)
    before = (item.temporal_execution.to_dict(), item.aggregation.to_dict())
    result = build_dataset_protein_edge_window_table((item,))
    (row,) = result.rows
    edge = item.aggregation.windows[0].edges[0]
    assert row.n_contact_frames == 4
    assert row.occupancy == row.edge_weight == occupancy
    assert row.n_contact_episodes == 2
    assert (row.mean_episode_length_ns, row.max_episode_length_ns) == (mean, maximum)
    assert (
        row.requested_sample_count,
        row.resolved_frame_count,
        row.missing_sample_count,
        row.coverage_fraction,
    ) == (
        5,
        resolved,
        len(missing),
        resolved / 5,
    )
    assert item.aggregation.status == ("partial" if missing else "complete")
    for name in METRIC_FIELDS:
        assert getattr(row, name) == getattr(edge, name)
    assert before == (item.temporal_execution.to_dict(), item.aggregation.to_dict())
    assert serialized(result) == serialized(
        build_dataset_protein_edge_window_table((item,))
    )


@pytest.mark.parametrize(("engine", "condition"), [("gromacs", "NORM"), ("namd", None)])
def test_authoritative_dataset_identity_copied_exactly(engine, condition):
    item = table_input(engine=engine, condition=condition, disulfide_state="intact")
    row = build_dataset_protein_edge_window_table((item,)).rows[0]
    for name, value in item.temporal_execution.dataset_spec.identity.to_dict().items():
        assert getattr(row, name) == value
    assert row.condition == condition
    if condition is None:
        assert item.temporal_execution.execution_condition == "legacy-namd-route"


def test_same_condition_distinct_replica_inputs_survive_and_sort():
    first = table_input()
    second = table_input(trajectory_id="wt-test-r2", replica_id="2")
    result = build_dataset_protein_edge_window_table((second, first))
    assert [r.condition for r in result.rows] == ["NORM", "NORM"]
    assert [(r.trajectory_id, r.replica_id) for r in result.rows] == [
        ("wt-test-r1", "1"),
        ("wt-test-r2", "2"),
    ]
    assert serialized(result) == serialized(
        build_dataset_protein_edge_window_table((first, second))
    )


def test_duplicate_replica_inputs_rejected_even_without_rows_or_same_condition():
    first = table_input(observations={})
    second = table_input(observations={}, condition=None, engine="namd")
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="replica keys"):
        build_dataset_protein_edge_window_table((first, second))


def test_execution_condition_mismatch_rejected():
    item = table_input()
    with pytest.raises(
        DatasetProteinEdgeWindowTableError, match="execution conditions"
    ):
        replace(
            item, aggregation=replace(item.aggregation, execution_condition="other")
        )


@pytest.mark.parametrize("name", ["temporal_execution", "aggregation"])
def test_input_requires_exact_accepted_types(name):
    item = table_input()
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="must be exact"):
        replace(item, **{name: None})
    original = getattr(item, name)
    subclass = type("Subclass", (type(original),), {})
    child = subclass(
        **{f.name: getattr(original, f.name) for f in fields(original) if f.init}
    )
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="must be exact"):
        replace(item, **{name: child})


def test_failed_state_rejected():
    item = table_input()
    # Only malformed fixtures bypass frozen upstream validation.
    object.__setattr__(item.aggregation, "status", "failed")
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="must not be failed"):
        replace(item)


@pytest.mark.parametrize(
    "name",
    [
        "window_id",
        "window_index",
        "requested_sample_count",
        "resolved_frame_count",
        "missing_sample_count",
        "coverage_fraction",
    ],
)
def test_each_temporal_aggregation_window_field_is_cross_checked(name):
    item = table_input()
    window = item.aggregation.windows[0]
    value = getattr(window, name)
    object.__setattr__(window, name, "different" if name == "window_id" else value + 1)
    with pytest.raises(DatasetProteinEdgeWindowTableError, match=f"window {name}"):
        replace(item)


def test_window_count_and_order_cross_checked_even_for_sparse_windows():
    item = table_input(count=9, length=0.2, observations={})
    shortened = replace(
        item.aggregation, window_count=1, windows=item.aggregation.windows[:1]
    )
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="window count"):
        replace(item, aggregation=shortened)
    object.__setattr__(
        item.aggregation, "windows", tuple(reversed(item.aggregation.windows))
    )
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="window window_id"):
        replace(item)


@pytest.mark.parametrize(
    "name", ["window_id", "window_index", "n_resolved_frames_in_window"]
)
def test_edge_parent_links_cross_checked(name):
    item = table_input()
    edge = item.aggregation.windows[0].edges[0]
    object.__setattr__(edge, name, "other" if name == "window_id" else 100)
    with pytest.raises(
        DatasetProteinEdgeWindowTableError, match="parent window|denominator"
    ):
        replace(item)


@pytest.mark.parametrize("endpoint", [5200.0, nextafter(5200.0, float("inf"))])
def test_requested_effective_bounds_and_decimal_context_independence(endpoint):
    item = table_input(times=(5000.0, 5050.0, 5100.0, 5150.0, endpoint))
    window = item.temporal_execution.window_plan.windows[0]
    expected = float(Decimal(str(endpoint)) / Decimal("1000"))
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        row = build_dataset_protein_edge_window_table((item,)).rows[0]
    assert row.requested_window_start_ns == window.requested_start_ns == 5.0
    assert row.requested_window_end_ns == window.requested_end_ns == 5.21
    assert row.right_endpoint_inclusive is window.right_endpoint_inclusive is False
    assert row.effective_window_start_ns == 5.0
    assert row.effective_window_end_ns == expected
    assert row.effective_window_end_ns != row.requested_window_end_ns
    if endpoint != 5200.0:
        assert row.effective_window_end_ns != 5.2


@pytest.mark.parametrize(
    ("resid", "expected"), [(330, "330"), ("330A", "330A"), (None, None), (-2, "-2")]
)
def test_source_residue_references_are_strings_and_segid_is_preserved(resid, expected):
    result = table(
        observations={0: (pair(source_residue_id=resid, target_residue_id=resid),)}
    )
    (row,) = result.rows
    assert row.source_resid == row.target_resid == expected
    assert (row.source_chain_id, row.target_chain_id) == ("A", "B")
    assert (row.source_resname, row.target_resname) == ("ALA", "LYS")


def test_equal_source_resids_across_chains_and_internal_indexes_are_distinct():
    first = pair()
    second = pair(
        source_residue_index=11,
        target_residue_index=17,
        source_segid="C",
        target_segid="D",
    )
    rows = table(observations={0: (second, first)}).rows
    assert [
        (r.source_residue_index, r.source_chain_id, r.source_resid) for r in rows
    ] == [
        (1, "A", "330"),
        (11, "C", "330"),
    ]


def test_multiple_types_overlap_and_sparse_zero_edge_windows():
    observations = {3: (pair(edge_type="ionic"), pair(edge_type="hbond"))}
    result = table(count=9, length=0.2, step=0.1, observations=observations)
    assert [(r.window_id, r.edge_type) for r in result.rows] == [
        ("window_0001", "hbond"),
        ("window_0001", "ionic"),
        ("window_0002", "hbond"),
        ("window_0002", "ionic"),
    ]
    assert all(r.n_contact_frames == r.n_contact_episodes == 1 for r in result.rows)
    assert all(
        r.mean_episode_length_ns == r.max_episode_length_ns == 0 for r in result.rows
    )
    sparse = table(count=9, length=0.2, observations=observations)
    assert {r.window_id for r in sparse.rows} == {"window_0001"}
    inclusive = table(count=9, length=0.2, positive=(8,))
    assert inclusive.rows[0].right_endpoint_inclusive is True


def test_empty_table_and_empty_inputs_are_valid():
    empty = DatasetProteinEdgeWindowTable(())
    assert empty.row_count == 0
    assert empty.to_dict()["rows"] == []
    assert (
        empty == build_dataset_protein_edge_window_table(()) == table(observations={})
    )
    # A window with no resolved samples still generates no placeholder row.
    result = table(missing=(0, 1), length=0.1, positive=(3, 4))
    assert {r.window_id for r in result.rows} == {"window_0002"}


@pytest.mark.parametrize("bad", [[], None, (None,)])
def test_builder_and_root_require_tuple_and_exact_record_types(bad):
    with pytest.raises(DatasetProteinEdgeWindowTableError):
        build_dataset_protein_edge_window_table(bad)
    with pytest.raises(DatasetProteinEdgeWindowTableError):
        DatasetProteinEdgeWindowTable(bad)


def test_duplicate_row_identity_ignores_condition_and_order_is_required():
    (row,) = table().rows
    for duplicate in (row, replace(row, condition=None), replace(row, window_index=3)):
        with pytest.raises(DatasetProteinEdgeWindowTableError, match="identities"):
            DatasetProteinEdgeWindowTable((row, duplicate))
    other = replace(row, trajectory_id="z")
    with pytest.raises(DatasetProteinEdgeWindowTableError, match="order"):
        DatasetProteinEdgeWindowTable((other, row))


def test_exact_row_order_keys_without_condition_sorting():
    row = table().rows[0]
    ordered = (
        replace(row, dataset_id="a", condition="Z"),
        replace(row, system_id="a"),
        replace(row, trajectory_id="a"),
        replace(row, replica_id="0"),
        replace(row, edge_type="hbond", source_residue_index=0),
        replace(row, edge_type="hbond", target_residue_index=6),
        replace(row, edge_type="hbond"),
        replace(row, edge_type="ionic"),
        row,
        replace(row, window_id="window_0002", window_index=1),
    )
    assert DatasetProteinEdgeWindowTable(ordered).rows == ordered
    for i in range(len(ordered) - 1):
        swapped = (*ordered[:i], ordered[i + 1], ordered[i], *ordered[i + 2 :])
        with pytest.raises(DatasetProteinEdgeWindowTableError, match="order"):
            DatasetProteinEdgeWindowTable(swapped)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("dataset_id", ""),
        ("system_id", " a"),
        ("trajectory_id", 1),
        ("variant_id", " "),
        ("engine", "GROMACS"),
        ("engine", "other"),
        ("replica_id", ""),
        ("condition", ""),
        ("disulfide_state", " a "),
        ("window_id", ""),
        ("window_index", -1),
        ("window_index", True),
        ("window_index", 0.0),
        ("right_endpoint_inclusive", 1),
        ("requested_window_start_ns", -1),
        ("requested_window_end_ns", 5),
        ("effective_window_start_ns", None),
        ("effective_window_end_ns", 4),
        ("effective_window_end_ns", float("nan")),
        ("requested_sample_count", 0),
        ("requested_sample_count", 6),
        ("resolved_frame_count", 0),
        ("resolved_frame_count", True),
        ("missing_sample_count", -1),
        ("missing_sample_count", False),
        ("coverage_fraction", 0),
        ("coverage_fraction", 0.8),
        ("source_residue_index", -1),
        ("source_residue_index", 7),
        ("target_residue_index", 0),
        ("target_residue_index", True),
        ("source_chain_id", " "),
        ("target_chain_id", 1),
        ("source_resid", 330),
        ("target_resid", ""),
        ("source_resname", ""),
        ("target_resname", " LYS"),
        ("edge_type", ""),
        ("n_contact_frames", 0),
        ("n_contact_frames", 6),
        ("n_contact_frames", True),
        ("occupancy", 0),
        ("occupancy", 0.7),
        ("occupancy", 1.1),
        ("occupancy", nextafter(0.8, 1.0)),
        ("n_contact_episodes", 0),
        ("n_contact_episodes", 5),
        ("mean_episode_length_ns", -1),
        ("mean_episode_length_ns", 0.2),
        ("max_episode_length_ns", float("inf")),
        ("max_episode_length_ns", True),
        ("edge_weight", 0.7),
        ("edge_weight", nextafter(0.8, 1.0)),
    ],
)
def test_row_validation_rejects_invalid_contract_values(name, value):
    with pytest.raises(DatasetProteinEdgeWindowTableError):
        replace(table().rows[0], **{name: value})


def test_source_contract_has_no_canonical_or_distance_fields():
    assert not any(
        "canonical" in name or "mapping_status" in name or "distance" in name
        for name in ROW_FIELDS
    )
    assert tuple(table().rows[0].to_dict()) == ROW_FIELDS


def test_table_transformation_has_no_io_or_scientific_execution(monkeypatch):
    item = table_input()
    source = inspect.getsource(model)
    tree = ast.parse(source)
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert all(
        name
        in {
            "dataclasses",
            "decimal",
            "math",
            "typing",
            "mania.dataset_identity",
            "mania.preprocessing.physical_time_execution",
            "mania.preprocessing.protein_edge_windows",
        }
        for name in imports
    )
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected I/O or scientific computation")

    for owner, names in (
        (builtins, ("open",)),
        (io, ("open",)),
        (Path, ("open", "stat", "iterdir")),
        (subprocess, ("run", "Popen")),
        (time, ("time", "monotonic", "perf_counter")),
        (
            aggregation,
            ("aggregate_protein_edges_by_window", "compute_window_contact_episodes"),
        ),
        (contact_episodes, ("compute_window_contact_episodes",)),
        (sampling, ("resolve_physical_time_sampling",)),
        (windows, ("plan_physical_time_windows",)),
        (physical_time_execution, ("collect_runtime_physical_time_source_frames",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    assert build_dataset_protein_edge_window_table((item,)).rows[0].occupancy == 0.8
