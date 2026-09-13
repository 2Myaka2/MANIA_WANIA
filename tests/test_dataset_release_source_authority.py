"""Release authority regressions, including schema-valid historical releases."""

import csv
import json
import shutil
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_dataset_release_run import validate
from test_dataset_release_workflow import make_release_case

from mania import canonical_window_tables_io as canonical_io
from mania import dataset_release_workflow as workflow
from mania.dataset_release_csv import build_publication_table
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_run import run_dataset_release
from mania.dataset_release_source_authority import validate_publication_metric_sources
from mania.dataset_release_workflow import DatasetReleaseError
from mania.replica_aggregation_workflow import FAMILIES
from mania.validation.run_artifacts import validate_run_artifact_integrity


@pytest.fixture(scope="module", params=["none", "sha256"])
def authority_case(request, tmp_path_factory):
    root = tmp_path_factory.mktemp(f"source-authority-{request.param}")
    path, control = make_release_case(root, mode=request.param)
    return path, control, request.param


@pytest.fixture
def case(authority_case, tmp_path):
    path, control, mode = authority_case
    root = tmp_path / "inputs"
    shutil.copytree(path.parent, root)
    return root / path.name, control, mode


def publication_inputs(path, control, mutate):
    target = path.parent / control.publication_inputs_path
    data = json.loads(target.read_text())
    mutate(data)
    target.write_text(json.dumps(data))


def replace_canonical(path, control, family_name, mutation="occupancy"):
    family = next(f for f in FAMILIES if f.name == family_name)
    binding = next(b for b in control.canonical_bindings if b.family == family_name)
    table = family.canonical_reader(path.parent / binding.path)
    row = next(
        r for r in table.rows if r.replica_id == "1" and r.resolved_frame_count == 3
    )
    assert row.occupancy == 2 / 3
    aggregate = family.reader(
        path.parent / getattr(control, f"{family_name}_aggregate_path")
    )
    assert any(
        r.window_id == row.window_id and r.mean_occupancy == 2 / 3
        for r in aggregate.rows
    )
    changes = dict(
        n_contact_frames=1,
        occupancy=1 / 3,
        mean_episode_length_ns=0.0,
        max_episode_length_ns=0.0,
    )
    if family_name == "protein":
        changes["edge_weight"] = 1 / 3
    else:
        changes["distance_mean_A"] = row.distance_min_A
    if mutation == "lifetime":
        changes = dict(
            mean_episode_length_ns=row.mean_episode_length_ns + 0.01,
            max_episode_length_ns=row.max_episode_length_ns + 0.01,
        )
    elif mutation == "distance":
        changes = dict(distance_mean_A=row.distance_mean_A + 0.01)
    elif mutation == "episodes":
        changes = dict(
            n_contact_episodes=2, mean_episode_length_ns=0.0, max_episode_length_ns=0.0
        )
    elif mutation == "source_identity":
        changes = {
            "source_chain_id" if family_name == "protein" else "protein_chain_id": "Z"
        }
    elif mutation == "partner":
        changes = {f"{family_name}_partner_id": "other-partner"}
    elif mutation == "denominator":
        changes = dict(
            requested_sample_count=6,
            resolved_frame_count=6,
            missing_sample_count=0,
            coverage_fraction=1.0,
            n_contact_frames=4,
            occupancy=row.occupancy,
        )
    elif mutation == "requested_window":
        changes = dict(requested_window_end_ns=row.requested_window_end_ns + 0.01)
    elif mutation == "canonical_identity":
        from mania.dataset_release_canonical import build_dataset_release_nodes

        node = build_dataset_release_nodes().records()[330]
        prefix = "target_" if family_name == "protein" else ""
        changes = {
            f"{prefix}canonical_residue_number": node["canonical_residue_number"],
            f"{prefix}canonical_resname": node["canonical_resname"],
        }
    replacement = replace(row, **changes)
    rows = tuple(replacement if r == row else r for r in table.rows)
    if mutation == "removed":
        rows = tuple(r for r in table.rows if r != row)
    elif mutation == "empty":
        rows = ()
    elif mutation == "added":
        extra = replace(
            row,
            **(
                {"edge_type": "additional-contact"}
                if family_name == "protein"
                else {f"{family_name}_partner_id": "additional-partner"}
            ),
        )
        rows = (*table.rows, extra)
    writer = getattr(
        canonical_io,
        "write_canonical_protein_"
        + {"protein": "edge", "lipid": "lipid", "glycan": "glycan"}[family_name]
        + "_window_csv",
    )
    result = writer(
        type(table)(tuple(sorted(rows, key=lambda r: r.row_order))),
        path.parent / "substitute",
    )
    assert result.written
    changed = replace(
        binding, path=result.output_path.relative_to(path.parent).as_posix()
    )
    control = replace(
        control,
        canonical_bindings=tuple(
            changed if b == binding else b for b in control.canonical_bindings
        ),
    )
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written
    return control


@pytest.mark.parametrize("family", ["protein", "lipid", "glycan"])
@pytest.mark.parametrize(
    "mutation",
    [
        "lifetime",
        "episodes",
        "source_identity",
        "denominator",
        "requested_window",
        "canonical_identity",
        "removed",
        "added",
        "empty",
    ],
)
def test_f1_complete_model_mismatch(case, tmp_path, family, mutation):
    path, control, mode = case
    publication_inputs(path, control, lambda data: data.update(metrics=[]))
    replace_canonical(path, control, family, mutation)
    output = tmp_path / "rejected"
    with pytest.raises(DatasetReleaseError, match="canonical source authority failed"):
        run_dataset_release(path, output, checksum_mode=mode)
    assert not output.exists()


@pytest.mark.parametrize("family", ["lipid", "glycan"])
@pytest.mark.parametrize("mutation", ["distance", "partner"])
def test_f1_specialized_model_mismatch(case, tmp_path, family, mutation):
    path, control, mode = case
    publication_inputs(path, control, lambda data: data.update(metrics=[]))
    replace_canonical(path, control, family, mutation)
    with pytest.raises(DatasetReleaseError, match="canonical source authority failed"):
        run_dataset_release(path, tmp_path / "rejected", checksum_mode=mode)


def copy_source(path, control, family_name="protein", serialization="identical"):
    binding = next(b for b in control.canonical_bindings if b.family == family_name)
    source = path.parent / binding.path
    target = path.parent / "copied" / source.name
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(source, target)
    if serialization == "model_identical":
        # A different accepted float serialization reconstructs the same model.
        with target.open(newline="") as stream:
            rows = list(csv.reader(stream))
        index = rows[0].index("occupancy")
        for row in rows[1:]:
            row[index] = format(float(row[index]), ".18e")
        with target.open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows(rows)
        assert source.read_bytes() != target.read_bytes()
    changed = replace(binding, path=target.relative_to(path.parent).as_posix())
    control = replace(
        control,
        canonical_bindings=tuple(
            changed if b == binding else b for b in control.canonical_bindings
        ),
    )
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written

    def move_metrics(data):
        for metric in data["metrics"]:
            if metric["source_artifact_path"] == binding.path:
                metric["source_artifact_path"] = changed.path

    publication_inputs(path, control, move_metrics)
    return control, target


@pytest.mark.parametrize("family", ["protein", "lipid", "glycan"])
@pytest.mark.parametrize("serialization", ["identical", "model_identical"])
def test_f1_copied_source_passes(case, tmp_path, family, serialization):
    path, control, mode = case
    copy_source(path, control, family, serialization)
    output = tmp_path / "release"
    run_dataset_release(path, output, checksum_mode=mode)
    report = validate(output, path)
    assert report.passed and report.complete, report.to_dict()


@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_f1_empty_authoritative_source_passes(tmp_path, mode):
    path, control = make_release_case(tmp_path / "inputs", mode=mode, empty=True)
    for family in ("protein", "lipid", "glycan"):
        control, _ = copy_source(path, control, family)
    output = tmp_path / "release"
    result = run_dataset_release(path, output, checksum_mode=mode)
    assert all(table.row_count == 0 for table in result.bundle.science.tables)
    report = validate(output, path)
    assert report.passed and report.complete


def test_f1_input_coverage_can_omit_excluded_replica(case, tmp_path):
    path, control, mode = case
    bindings = []
    for family in FAMILIES:
        binding = next(b for b in control.canonical_bindings if b.family == family.name)
        table = family.canonical_reader(path.parent / binding.path)
        assert any(r.replica_id == "2" for r in table.rows)
        subset = family.canonical_table(
            tuple(r for r in table.rows if r.replica_id != "2")
        )
        writer = getattr(
            canonical_io,
            "write_canonical_protein_"
            + {
                "protein": "edge",
                "lipid": "lipid",
                "glycan": "glycan",
            }[family.name]
            + "_window_csv",
        )
        result = writer(subset, path.parent / "selected-inputs")
        assert result.written
        bindings.append(
            replace(
                binding,
                path=result.output_path.relative_to(path.parent).as_posix(),
                replica_keys=tuple(k for k in binding.replica_keys if k[-1] != "2"),
            )
        )
    control = replace(control, canonical_bindings=tuple(bindings))
    assert write_dataset_release_export_manifest(control, path, overwrite=True).written
    publication_inputs(path, control, lambda data: data.update(metrics=[]))
    output = tmp_path / "release"
    result = run_dataset_release(path, output, checksum_mode=mode)
    assert result.bundle.metadata.simulations.row_count == 3
    assert all(
        r["replica_id"] != "2"
        for r in result.bundle.science.protein_edges_by_window.records()
    )
    report = validate(output, path)
    assert report.passed and report.complete


@pytest.mark.parametrize("family", ["protein", "lipid", "glycan"])
def test_duplicate_source_rows_rejected(case, tmp_path, family):
    path, control, mode = case
    _, target = copy_source(path, control, family)
    lines = target.read_text().splitlines(keepends=True)
    target.write_text("".join([*lines[:2], *lines[1:]]))
    with pytest.raises(DatasetReleaseError):
        run_dataset_release(path, tmp_path / "rejected", checksum_mode=mode)


METRIC_MUTATIONS = (
    "missing_record",
    "wrong_role",
    "unsupported_role",
    "wrong_field",
    "missing_field",
    "value",
    "replica",
    "trajectory",
    "system",
    "dataset",
    "window_id",
    "window_index",
    "global",
    "unit",
    "unsafe_path",
    "unbound",
)


def mutate_metric(path, control, mutation):
    def mutate(data):
        metric = data["metrics"][0]
        changes = {
            "missing_record": {"source_record_key": "nonexistent-record"},
            "wrong_role": {
                "source_artifact_role": "canonical_protein_lipid_window_table"
            },
            "unsupported_role": {"source_artifact_role": "legacy_centrality"},
            "wrong_field": {"source_value_field": "canonical_residue_number"},
            "value": {"metric_value": 987654321.0},
            "replica": {"replica_id": "3"},
            "trajectory": {"trajectory_id": "trajectory-3"},
            "system": {"system_id": "different-system"},
            "dataset": {"dataset_id": "different-dataset"},
            "window_id": {"window_id": "another-window"},
            "window_index": {"window_index": metric["window_index"] + 1},
            "global": {"window_id": None, "window_index": None},
            "unit": {"unit": "percent"},
            "unsafe_path": {"source_artifact_path": "../escape.csv"},
        }
        if mutation == "missing_field":
            del metric["source_value_field"]
        elif mutation == "unbound":
            target = path.parent / "unbound.csv"
            shutil.copyfile(path.parent / metric["source_artifact_path"], target)
            metric["source_artifact_path"] = target.name
        else:
            metric.update(changes[mutation])

    publication_inputs(path, control, mutate)


@pytest.mark.parametrize("mutation", METRIC_MUTATIONS)
def test_f2_false_source_rejected_before_write(case, tmp_path, mutation):
    path, control, mode = case
    mutate_metric(path, control, mutation)
    output = tmp_path / "rejected"
    phase = (
        "input"
        if mutation in ("missing_field", "unsafe_path")
        else "metric source authority"
    )
    with pytest.raises(DatasetReleaseError, match=f"{phase} failed"):
        run_dataset_release(path, output, checksum_mode=mode)
    assert not output.exists()


def test_f2_missing_bound_source_rejected(case, tmp_path):
    path, control, mode = case
    _, target = copy_source(path, control)
    output = tmp_path / "valid-before-removal"
    run_dataset_release(path, output, checksum_mode=mode)
    target.unlink()
    integrity = validate_run_artifact_integrity(output, scope="dataset_release")
    assert integrity.passed and integrity.complete
    assert not validate(output, path).passed
    output = tmp_path / "rejected"
    with pytest.raises(DatasetReleaseError):
        run_dataset_release(path, output, checksum_mode=mode)
    assert not output.exists()


@pytest.mark.parametrize(
    "family,field,unit",
    [
        ("protein", "occupancy", None),
        ("protein", "edge_weight", None),
        ("protein", "n_contact_frames", None),
        ("protein", "n_contact_episodes", None),
        ("protein", "mean_episode_length_ns", "ns"),
        ("lipid", "distance_mean_A", "angstrom"),
        ("glycan", "distance_min_A", "angstrom"),
    ],
)
def test_f2_supported_source_passes(case, tmp_path, family, field, unit):
    path, control, mode = case
    binding = next(b for b in control.canonical_bindings if b.family == family)
    adapter = next(f for f in FAMILIES if f.name == family)
    source = adapter.canonical_reader(path.parent / binding.path)
    row = next(r for r in source.rows if r.replica_id == "1")

    def select(data):
        data["metrics"][0].update(
            source_artifact_path=binding.path,
            source_artifact_role=adapter.input_role,
            source_record_key=json.dumps(
                row.row_identity, ensure_ascii=False, separators=(",", ":")
            ),
            source_value_field=field,
            metric_value=getattr(row, field),
            unit=unit,
            window_id=row.window_id,
            window_index=row.window_index,
            # Deliberately unrelated to the source field: never infer from name.
            metric_name="explicit source selection",
        )

    publication_inputs(path, control, select)
    output = tmp_path / "release"
    result = run_dataset_release(path, output, checksum_mode=mode)
    assert result.bundle.science.metrics.row_count == 1
    metric = result.bundle.science.metrics.records()[0]
    assert float(metric["metric_value"]) == getattr(row, field)
    assert "source_value_field" not in metric
    report = validate(output, path)
    assert report.passed and report.complete


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_record",
        "value",
        "replica",
        "window_index",
        "unit",
        "wrong_role",
        "unsupported_role",
        "unbound",
        "global",
    ],
)
def test_f2_historical_false_source_independently_rejected(
    case, tmp_path, monkeypatch, mutation
):
    path, control, mode = case
    # Other pure-builder invariants must remain valid during historical authoring.
    if mutation in ("replica", "window_index"):
        # Resolve a different real source record, retaining valid publication FKs.
        def wrong_record(data):
            metric = data["metrics"][0]
            source = FAMILIES[0].canonical_reader(
                path.parent / metric["source_artifact_path"]
            )
            row = next(
                r
                for r in source.rows
                if (
                    r.replica_id == "3"
                    if mutation == "replica"
                    else r.window_index != metric["window_index"]
                )
            )
            metric["source_record_key"] = json.dumps(
                row.row_identity, separators=(",", ":")
            )

        publication_inputs(path, control, wrong_record)
    else:
        mutate_metric(path, control, mutation)
    output = tmp_path / "historical"
    with monkeypatch.context() as patch:
        patch.setattr(
            workflow, "validate_publication_metric_sources", lambda *args: None
        )
        run_dataset_release(path, output, checksum_mode=mode)
    integrity = validate_run_artifact_integrity(output, scope="dataset_release")
    assert integrity.passed and integrity.complete
    report = validate(output, path)
    assert not report.passed and not report.complete
    assert any(i.code == "dataset_release_reconstruction_failed" for i in report.issues)


@pytest.mark.parametrize(
    "name",
    [
        "requested_window_start_ns",
        "requested_window_end_ns",
        "right_endpoint_inclusive",
        "expected_sample_count",
        "resolved_sample_count",
        "missing_sample_count",
        "coverage_fraction",
        "effective_start_ns",
        "effective_end_ns",
    ],
)
def test_f2_checks_physical_evidence_beyond_window_labels(case, name):
    path, control, _ = case
    bundle = workflow.build_dataset_release(path)
    inputs = read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    rows = bundle.metadata.time_windows.records()
    metric = inputs.metrics[0]
    row = next(
        r
        for r in rows
        if r["replica_id"] == metric.replica_id and r["window_id"] == metric.window_id
    )
    # Deliberately false evidence must not leak Decimal flags into later tests.
    with localcontext():
        row[name] = not row[name] if type(row[name]) is bool else row[name] + 1
    metadata = replace(
        bundle.metadata, time_windows=build_publication_table("time_windows", rows)
    )
    with pytest.raises(ValueError, match="window evidence differs"):
        validate_publication_metric_sources(inputs, control, path.parent, metadata)


def test_f2_accepted_effective_time_representation(case):
    from mania.preprocessing.protein_edge_window_table import _effective_ns

    path, control, _ = case
    control, target = copy_source(path, control)
    bundle = workflow.build_dataset_release(path)
    inputs = read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    metric = inputs.metrics[0]
    source = canonical_io.read_canonical_protein_edge_window_csv(target)
    row = next(
        r
        for r in source.rows
        if r.replica_id == metric.replica_id and r.window_id == metric.window_id
    )
    ps = row.effective_window_start_ns * 1000 + 0.0001
    changed = replace(row, effective_window_start_ns=_effective_ns(ps))
    table = type(source)(tuple(changed if r == row else r for r in source.rows))
    assert canonical_io.write_canonical_protein_edge_window_csv(
        table, target.parent, overwrite=True
    ).written
    sign, digits, exponent = Decimal.from_float(ps).as_tuple()
    exact_ns = Decimal((sign, digits, exponent - 3))
    rows = bundle.metadata.time_windows.records()
    window = next(
        r
        for r in rows
        if r["replica_id"] == metric.replica_id and r["window_id"] == metric.window_id
    )
    window["effective_start_ns"] = exact_ns
    metadata = replace(
        bundle.metadata, time_windows=build_publication_table("time_windows", rows)
    )
    validate_publication_metric_sources(inputs, control, path.parent, metadata)


@pytest.mark.parametrize("family", ["protein", "lipid", "glycan"])
def test_f1_mismatch_rejected_before_write(case, tmp_path, family):
    path, control, mode = case
    publication_inputs(path, control, lambda data: data.update(metrics=[]))
    replace_canonical(path, control, family)
    output = tmp_path / "rejected"
    with pytest.raises(DatasetReleaseError):
        run_dataset_release(path, output, checksum_mode=mode)
    assert not output.exists()


def test_f2_missing_source_rejected_before_write(case, tmp_path):
    path, control, mode = case

    def missing(data):
        data["metrics"][0].update(
            source_artifact_path="missing_metric_source/centrality.csv",
            source_record_key="nonexistent-record",
            metric_value=987654321.0,
        )

    publication_inputs(path, control, missing)
    output = tmp_path / "rejected"
    with pytest.raises(DatasetReleaseError):
        run_dataset_release(path, output, checksum_mode=mode)
    assert not output.exists()


@pytest.mark.parametrize("defect", ["protein", "lipid", "glycan", "metric"])
def test_historical_release_independently_rejected(case, tmp_path, monkeypatch, defect):
    path, control, mode = case
    if defect != "metric":
        publication_inputs(path, control, lambda data: data.update(metrics=[]))
        replace_canonical(path, control, defect)
    else:

        def missing(data):
            data["metrics"][0].update(
                source_artifact_path="missing_metric_source/centrality.csv",
                source_record_key="nonexistent-record",
                metric_value=987654321.0,
            )

        publication_inputs(path, control, missing)
    output = tmp_path / "historical"
    # Only historical authoring bypasses the corrective guard. Reconstruction
    # below runs with the real guard restored and correct inventory/checksums.
    with monkeypatch.context() as patch:
        for name in (
            "validate_release_canonical_source_authority",
            "validate_publication_metric_sources",
        ):
            patch.setattr(workflow, name, lambda *args, **kwargs: None, raising=False)
        run_dataset_release(path, output, checksum_mode=mode)
    integrity = validate_run_artifact_integrity(output, scope="dataset_release")
    assert integrity.passed and integrity.complete
    report = validate(output, path)
    assert not report.passed and not report.complete, report.to_dict()
