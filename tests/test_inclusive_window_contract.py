"""Stage 34.D.4c: explicit temporal profiles, with no MD coordinates."""

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from test_dataset_release_run import validate
from test_dataset_release_workflow import make_release_case
from test_preprocessing_protein_edge_windows import aggregate, contact_result, pair
from test_replica_aggregation_contract import member, spec

from mania.dataset_identity import DatasetTrajectorySpec
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest import DatasetReleaseManifest
from mania.dataset_release_manifest_io import (
    read_dataset_release_manifest,
    write_dataset_release_manifest,
)
from mania.dataset_release_run import run_dataset_release
from mania.dataset_release_source_authority import (
    validate_publication_metric_sources,
    validate_release_canonical_source_authority,
)
from mania.dataset_release_workflow import build_dataset_release
from mania.preprocessing.dataset_binding import (
    PreprocessingDatasetContext,
    resolve_preprocessing_dataset_context,
)
from mania.preprocessing.input_manifest import PreprocessingInputManifest
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
    PreprocessingTemporalExecution,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
    write_preprocessing_temporal_execution,
)
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)
from mania.preprocessing.physical_time_windows import plan_physical_time_windows
from mania.preprocessing.temporal_policy import (
    INCLUSIVE_BOUNDARY_PROFILE as INCLUSIVE,
)
from mania.preprocessing.temporal_policy import LEGACY_BOUNDARY_PROFILE as LEGACY
from mania.preprocessing.temporal_policy import PreprocessingTemporalPolicy
from mania.production_catalog import TechnicalRunManifest, load_production_catalog
from mania.replica_aggregation_contract import (
    ReplicaAggregationWindowDefinition,
    build_compatible_replica_aggregation_group,
)
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_aggregation_workflow import (
    FAMILIES,
    execute_replica_aggregation_manifest,
    load_replica_aggregation_inputs,
)


def execution(end=100, profile=INCLUSIVE, *, missing=(), extra_times=()):
    request = DatasetTrajectorySpec.model_validate(
        dict(
            identity=dict(
                dataset_id="synthetic-d4c",
                system_id="WT",
                trajectory_id="t1",
                replica_id="1",
                variant_id="WT",
                engine="namd",
                condition=None,
            ),
            temporal=dict(
                production_start_ns=5,
                production_end_ns=end,
                frame_stride_ps=200,
                window_length_ns=2,
                window_step_ns=1,
                overlap_percent=50,
            ),
        )
    )
    times = sorted(set(range(0, end * 1000 + 1, 200)) - set(missing) | set(extra_times))
    sampling = resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, t) for i, t in enumerate(times)),
        temporal=request.temporal,
    )
    return PreprocessingConditionTemporalExecution(
        "test",
        request,
        sampling,
        plan_physical_time_windows(
            sampling,
            temporal=request.temporal,
            boundary_profile=profile,
        ),
    )


def physical_window(binding, index=-1):
    plan = binding.window_plan
    window = plan.windows[index]
    return ReplicaAggregationWindowDefinition(
        window.window_id,
        window.window_index,
        plan.requested_production_start_ns,
        plan.requested_production_end_ns,
        window.requested_start_ns,
        window.requested_end_ns,
        window.right_endpoint_inclusive,
        plan.requested_window_length_ns,
        plan.requested_window_step_ns,
        plan.requested_overlap_percent,
        boundary_profile=plan.boundary_profile,
    )


@pytest.mark.parametrize(
    "end,samples,windows,last", [(100, 476, 94, 98), (30, 126, 24, 28)]
)
@pytest.mark.parametrize("profile", [LEGACY, INCLUSIVE])
def test_approved_schedules_and_exact_round_trip(
    tmp_path, end, samples, windows, last, profile
):
    binding = execution(end, profile)
    plan = binding.window_plan
    assert binding.sampling_plan.sampled_frame_count == samples
    assert plan.window_count == windows
    assert plan.boundary_profile == profile
    assert {w.requested_sample_count for w in plan.windows[:-1]} == (
        {11} if profile == INCLUSIVE else {10}
    )
    assert all(
        w.right_endpoint_inclusive == (profile == INCLUSIVE) for w in plan.windows[:-1]
    )
    terminal = plan.windows[-1]
    assert (terminal.requested_start_ns, terminal.requested_end_ns) == (last, end)
    assert terminal.requested_sample_count == 11 and terminal.right_endpoint_inclusive
    model = PreprocessingTemporalExecution((binding,))
    path = write_preprocessing_temporal_execution(model, tmp_path).output_path
    restored = read_preprocessing_temporal_execution(path)
    assert restored == model and restored.to_dict() == model.to_dict()
    assert write_preprocessing_temporal_execution(restored, tmp_path / "again").passed
    assert (
        path.read_bytes() == (tmp_path / "again/temporal_execution.json").read_bytes()
    )
    payload = model.to_dict()
    assert payload["schema_version"].endswith(
        "v0.2" if profile == INCLUSIVE else "v0.1"
    )
    stored = payload["bindings"][0]["window_plan"]
    assert ("boundary_profile" in stored) == (profile == INCLUSIVE)
    assert binding.sampling_plan == execution(end, LEGACY).sampling_plan


def test_adjacent_duration_overlap_and_requested_grid():
    plan = execution().window_plan
    first, second = plan.windows[:2]
    assert first.requested_sample_indexes == tuple(range(11))
    assert second.requested_sample_indexes == tuple(range(5, 16))
    assert (
        len(set(first.requested_sample_indexes) & set(second.requested_sample_indexes))
        == 6
    )
    assert plan.implied_overlap_percent == 50


def test_inclusive_off_grid_endpoints_are_not_manufactured():
    temporal = execution(30).dataset_spec.temporal.model_copy(
        update={"production_end_ns": 8.1, "frame_stride_ps": 300.0}
    )
    sampling = resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, i * 100) for i in range(82)),
        temporal=temporal,
    )
    plan = plan_physical_time_windows(
        sampling,
        temporal=temporal,
        boundary_profile=INCLUSIVE,
    )
    assert plan.window_count == 2
    assert [w.requested_sample_count for w in plan.windows] == [7, 7]
    assert plan.windows[-1].requested_end_ns == 8
    targets = {s.requested_time_ps for s in sampling.selected_samples}
    assert 7000 not in targets and 8100 not in targets and 8000 in targets


def test_committed_accepted_legacy_artifact_preserves_bytes_and_plan(tmp_path):
    path = Path(__file__).parent / "fixtures/temporal_execution_legacy_v01.json"
    model = read_preprocessing_temporal_execution(path)
    for binding in model.bindings:
        assert binding.window_plan.boundary_profile == LEGACY
        assert binding.window_plan == plan_physical_time_windows(
            binding.sampling_plan,
            temporal=binding.dataset_spec.temporal,
        )
    written = write_preprocessing_temporal_execution(model, tmp_path)
    assert written.passed and written.output_path.read_bytes() == path.read_bytes()


def test_terminal_identity_cannot_mix_even_with_identical_local_fields():
    old, new = physical_window(execution(profile=LEGACY)), physical_window(execution())
    assert replace(new, boundary_profile=LEGACY) == old
    assert old.physical_window_key != new.physical_window_key
    with pytest.raises(ValueError, match="physical_window_key"):
        build_compatible_replica_aggregation_group(
            spec(window=new),
            (member("1", window=new), member("2", window=new), member("3", window=old)),
        )
    with pytest.raises(ValueError, match="right-inclusive"):
        replace(new, right_endpoint_inclusive=False)


@pytest.mark.parametrize(
    "mutation", ["unknown", "missing", "hybrid", "legacy", "array"]
)
def test_publication_profile_version_is_strict(tmp_path, mutation):
    data = DatasetReleaseManifest(
        "test",
        "decisions.json",
        "groups.json",
        "aggregation.json",
        boundary_profile=INCLUSIVE,
    ).to_dict()
    if mutation == "unknown":
        data["boundary_profile"] = "unknown"
    elif mutation == "missing":
        del data["boundary_profile"]
    elif mutation == "hybrid":
        data["schema_version"] = "mania.dataset_release_manifest.v0.1"
    elif mutation == "legacy":
        data["boundary_profile"] = LEGACY
    else:
        data = []
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_dataset_release_manifest(path)


def test_missing_expected_sample_is_absent_and_breaks_episode():
    binding = execution(30, missing=(6000,), extra_times=(6001,))
    window = binding.window_plan.windows[0]
    assert (window.requested_sample_count, window.sampled_frame_count) == (11, 10)
    assert window.coverage_fraction == 10 / 11
    assert window.missing_requested_sample_indexes == (5,)
    assert all(s.actual_time_ps != 6001 for s in binding.sampling_plan.selected_samples)
    result = aggregate(binding.sampling_plan, binding.window_plan)
    metric = result.windows[0].edges[0]
    assert metric.n_contact_frames == metric.n_resolved_frames_in_window == 10
    assert metric.occupancy == 1
    assert metric.n_contact_episodes == 2
    assert metric.mean_episode_length_ns == pytest.approx(0.8)
    assert metric.max_episode_length_ns == pytest.approx(0.8)


def test_right_endpoint_contact_and_window_local_duplicates():
    new = execution(30)
    old = execution(30, LEGACY)
    contacts = contact_result(new.sampling_plan, {10: (pair(),)})  # Exactly 7 ns.
    current = aggregate(new.sampling_plan, new.window_plan, contacts)
    historical = aggregate(old.sampling_plan, old.window_plan, contacts)
    assert not historical.windows[0].edges
    for w in current.windows[:2]:
        metric = w.edges[0]
        assert metric.n_contact_frames == metric.n_contact_episodes == 1
        assert metric.occupancy == 1 / 11
        assert metric.mean_episode_length_ns == metric.max_episode_length_ns == 0
    continuous = aggregate(new.sampling_plan, new.window_plan).windows[0].edges[0]
    assert continuous.n_contact_episodes == 1 and continuous.max_episode_length_ns == 2


@pytest.mark.parametrize("profile", [LEGACY, INCLUSIVE])
@pytest.mark.parametrize(
    "mutation",
    [
        "root_version",
        "plan_version",
        "unknown_profile",
        "hybrid",
        "flags",
        "membership",
    ],
)
def test_strict_version_and_profile_rejections(tmp_path, profile, mutation):
    model = PreprocessingTemporalExecution((execution(30, profile),))
    data = model.to_dict()
    plan = data["bindings"][0]["window_plan"]
    if mutation == "root_version":
        data["schema_version"] = "unknown"
    elif mutation == "plan_version":
        plan["schema_version"] = "unknown"
    elif mutation == "unknown_profile":
        plan["boundary_profile"] = "unknown"
    elif mutation == "hybrid":
        if profile == LEGACY:
            plan["boundary_profile"] = LEGACY
        else:
            del plan["boundary_profile"]
    elif mutation == "flags":
        plan["windows"][0]["right_endpoint_inclusive"] = profile != INCLUSIVE
    else:
        other = execution(30, LEGACY if profile == INCLUSIVE else INCLUSIVE).window_plan
        data["bindings"][0]["window_plan"] = replace(
            other, boundary_profile=profile
        ).to_dict()
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_preprocessing_temporal_execution(path)


def test_request_carrier_separate_from_frozen_dataset_parameters():
    request = execution(30).dataset_spec
    config = dict(
        output_root="out",
        conditions=[
            dict(
                condition="test",
                topology_path="a.psf",
                trajectory_paths=["a.dcd"],
                dataset_spec=request,
            )
        ],
    )
    legacy = resolve_preprocessing_dataset_context(
        PreprocessingInputManifest(**config)
    ).context
    assert legacy.temporal_policy is None and "temporal_policy" not in legacy.to_dict()
    policy = PreprocessingTemporalPolicy(
        schema_version="mania.preprocessing_temporal_policy.v0.1",
        boundary_profile=INCLUSIVE,
    )
    manifest = PreprocessingInputManifest(**config, temporal_policy=policy)
    context = resolve_preprocessing_dataset_context(manifest).context
    assert context.schema_version == "mania.preprocessing_dataset_context.v0.2"
    assert PreprocessingDatasetContext.from_dict(context.to_dict()) == context
    assert len(type(request.temporal).model_fields) == 6
    assert context.bindings == legacy.bindings
    with pytest.raises(ValueError):
        PreprocessingTemporalPolicy(
            schema_version=policy.schema_version, boundary_profile="unknown"
        )
    with pytest.raises(ValueError):
        PreprocessingTemporalPolicy(
            **policy.model_dump(), right_endpoint_inclusive=True
        )


@pytest.mark.parametrize("empty", [False, True])
def test_stage32_stage31_publication_and_offline_reconstruction(tmp_path, empty):
    path, control = make_release_case(
        tmp_path / "source", boundary_profile=INCLUSIVE, empty=empty
    )
    bundle = build_dataset_release(path)
    derived = read_replica_aggregation_manifest(
        path.parent / control.qc_derived_manifest_path
    )
    assert derived.schema_version == "mania.replica_aggregation_manifest.v0.2"
    assert {g.spec.window.boundary_profile for g in derived.groups} == {INCLUSIVE}
    assert (
        bundle.metadata.boundary_profile
        == bundle.manifest.boundary_profile
        == INCLUSIVE
    )
    assert bundle.manifest.to_dict()["boundary_profile"] == INCLUSIVE
    assert all(
        r["right_endpoint_inclusive"] for r in bundle.metadata.time_windows.records()
    )
    assert {
        r["expected_sample_count"] for r in bundle.metadata.time_windows.records()
    } == {5}
    assert bundle.science.metrics.row_count == (0 if empty else 1)
    out = tmp_path / "release"
    run_dataset_release(path, out)
    report = validate(out, path)
    assert report.status == "passed", report.to_dict()
    manifest = read_dataset_release_manifest(out / "release/dataset_manifest.json")
    assert manifest.boundary_profile == INCLUSIVE
    assert write_dataset_release_manifest(manifest, tmp_path / "again.json").passed
    assert read_dataset_release_manifest(tmp_path / "again.json") == manifest


@pytest.mark.parametrize("family_name", ["protein", "lipid", "glycan"])
def test_f1_and_f2_reject_terminal_profile_substitution(tmp_path, family_name):
    path, control = make_release_case(tmp_path, boundary_profile=INCLUSIVE)
    bundle = build_dataset_release(path)
    used = bundle.aggregation_authority.aggregation_manifest_used
    canonical = load_replica_aggregation_inputs(used)
    family = next(f for f in FAMILIES if f.name == family_name)
    table = canonical[family_name]
    row = next(r for r in reversed(table.rows) if r.replica_id == "1")
    assert row.right_endpoint_inclusive and row.requested_window_end_ns == 1
    changed = replace(row, boundary_profile=LEGACY)
    altered = family.canonical_table(
        tuple(changed if r == row else r for r in table.rows)
    )
    with pytest.raises(ValueError, match="differs from Stage 31"):
        validate_release_canonical_source_authority(
            control, used, {**canonical, family_name: altered}
        )
    binding = next(b for b in control.canonical_bindings if b.family == family_name)
    inputs = read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    metric = replace(
        inputs.metrics[0],
        window_id=row.window_id,
        window_index=row.window_index,
        metric_value=row.occupancy,
        source_artifact_role=family.input_role,
        source_artifact_path=binding.path,
        source_record_key=json.dumps(
            row.row_identity, ensure_ascii=False, separators=(",", ":")
        ),
    )
    inputs = replace(
        inputs, metrics=(metric,), metric_source_value_fields=("occupancy",)
    )
    validate_publication_metric_sources(inputs, control, path.parent, bundle.metadata)
    kind = "edge" if family_name == "protein" else family_name
    writer = getattr(
        __import__("mania.canonical_window_tables_io", fromlist=[""]),
        f"write_canonical_protein_{kind}_window_csv",
    )
    assert writer(altered, (path.parent / binding.path).parent, overwrite=True).passed
    with pytest.raises(ValueError, match="boundary profile"):
        validate_publication_metric_sources(
            inputs, control, path.parent, bundle.metadata
        )
    with pytest.raises(ValueError, match="Canonical rows must agree"):
        execute_replica_aggregation_manifest(used)


def test_dataset_catalog_explicit_policy_and_unchanged_timing():
    root = Path(__file__).resolve().parents[1] / "production/dataset_v1"
    catalog = yaml.safe_load((root / "dataset.yaml").read_text())
    assert catalog["dataset_version"] == "1.0"
    assert catalog["temporal_policy"] == {
        "schema_version": "mania.preprocessing_temporal_policy.v0.1",
        "boundary_profile": INCLUSIVE,
    }
    policy = PreprocessingTemporalPolicy.model_validate(catalog["temporal_policy"])
    assert policy.boundary_profile == INCLUSIVE
    rows = list(csv.DictReader((root / "trajectories.csv").open()))
    assert len(rows) == 33
    assert {r["trajectory_id"] for r in rows if r["readiness_status"] == "READY"} == {
        "namd_egor_wt_0ss_r1"
    }
    assert {
        (
            r["production_start_ns"],
            r["production_end_ns"],
            r["frame_stride_ps"],
            r["window_length_ns"],
            r["window_step_ns"],
        )
        for r in rows
    } == {
        ("5", "100", "200", "2", "1"),
        ("5", "30", "200", "2", "1"),
    }
    loaded = load_production_catalog(root / "dataset.yaml")
    selected = loaded.trajectory("namd_egor_wt_0ss_r1")
    original_spec = selected.spec.model_dump()
    technical = TechnicalRunManifest(
        schema_version="mania.production_technical_run.v0.1",
        purpose="technical_validation",
        trajectory_id=selected.trajectory_id,
        start_ns=5,
        end_ns=8,
    ).execution_spec(selected)
    assert technical.temporal.production_start_ns == 5
    assert technical.temporal.production_end_ns == 8
    assert selected.spec.model_dump() == original_spec
    assert selected.spec.temporal.production_start_ns == 5
    assert selected.spec.temporal.production_end_ns == 100
    assert [trajectory.row for trajectory in loaded.trajectories] == rows
    assert loaded.temporal_policy == policy


def test_cli_policy_reaches_all_canonical_layers_and_offline_validation(
    monkeypatch,
    capsys,
    tmp_path,
):
    from test_cli_preprocessing_canonical_annotation_export import install_stage30
    from test_cli_preprocessing_graph_workflow import invoke_cli
    from test_cli_preprocessing_physical_time_execution import physical_command
    from test_cli_preprocessing_specialized_contact_export import assert_valid

    from mania import annotated_window_tables_io as annotated_io

    source, _, _, mappings = install_stage30(monkeypatch, tmp_path)
    data = json.loads(source.manifest_path.read_text())
    data["temporal_policy"] = dict(
        schema_version="mania.preprocessing_temporal_policy.v0.1",
        boundary_profile=INCLUSIVE,
    )
    source.manifest_path.write_text(json.dumps(data))
    _, stdout, stderr = invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    assert stderr == "" and json.loads(stdout)["passed"]
    root = tmp_path / "out"
    temporal = read_preprocessing_temporal_execution(root / "temporal_execution.json")
    assert all(b.window_plan.boundary_profile == INCLUSIVE for b in temporal.bindings)
    assert_valid(root, mappings)
    for family in FAMILIES:
        table = family.canonical_reader(
            root
            / {
                "protein": "protein_edges_by_window_canonical.csv",
                "lipid": "protein_lipid_contacts_by_window_canonical.csv",
                "glycan": "protein_glycan_contacts_by_window_canonical.csv",
            }[family.name]
        )
        assert table.rows and {r.boundary_profile for r in table.rows} == {INCLUSIVE}
        kind = "edge" if family.name == "protein" else family.name
        reader = getattr(
            annotated_io, f"read_annotated_canonical_protein_{kind}_window_csv"
        )
        filename = {
            "protein": "protein_edges",
            "lipid": "protein_lipid_contacts",
            "glycan": "protein_glycan_contacts",
        }[family.name] + "_by_window_canonical_annotated.csv"
        assert {r.boundary_profile for r in reader(root / filename).rows} == {INCLUSIVE}
