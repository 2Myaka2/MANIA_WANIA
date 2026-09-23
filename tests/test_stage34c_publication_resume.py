"""Synthetic publication-only guards; no local real evidence prerequisite."""

import copy
import hashlib
import importlib.util
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_replica_protein_edge_aggregation import row as protein_row
from test_replica_specialized_aggregation import row as specialized_row

from mania import canonical_window_tables_io as canonical_io
from mania.dataset_release_csv import build_publication_table, publication_table_spec
from mania.dataset_release_manifest import ReleaseCanonicalBinding

spec = importlib.util.spec_from_file_location(
    "c4_resume", Path(__file__).parents[1] / "tools/stage34c_publication_resume.py"
)
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


def source(family, replica="1", condition=None):
    changes = resume.c2.identity(replica, condition) | dict(
        requested_window_start_ns=0.1,
        requested_window_end_ns=0.5,
        effective_window_start_ns=0.1,
        effective_window_end_ns=0.5,
        requested_sample_count=5,
        resolved_frame_count=5,
        right_endpoint_inclusive=True,
    )
    row = (
        protein_row(occupancy=0.6, **changes)
        if family == "protein"
        else specialized_row(kind=family, occupancy=0.6, **changes)
    )
    model = next(f for f in resume.FAMILIES if f.name == family)
    return model.canonical_table((row,))


@pytest.mark.parametrize(
    "family,replica", [(f, r) for f in resume.SOURCE_HASHES for r in resume.REPLICAS]
)
def test_exact_hash_guards(tmp_path, family, replica):
    path = tmp_path / "canonical.csv"
    path.write_text("substituted science")
    with pytest.raises(ValueError, match="Frozen hash"):
        resume.pinned(path, resume.SOURCE_HASHES[family][replica])
    assert (
        resume.pinned(path, hashlib.sha256(path.read_bytes()).hexdigest())["size_bytes"]
        > 0
    )


@pytest.mark.parametrize(
    "digest", [resume.MANIFEST_SHA, resume.QC_SHA, resume.AGGREGATE_SHA]
)
def test_frozen_chain_hashes_required(tmp_path, digest):
    path = tmp_path / "frozen"
    path.write_text("changed")
    with pytest.raises(ValueError, match="Frozen hash"):
        resume.pinned(path, digest)


@pytest.mark.parametrize("family", ["lipid", "glycan"])
@pytest.mark.parametrize("replica", resume.REPLICAS)
def test_condition_only_copy_roundtrip(tmp_path, family, replica):
    original = source(family, replica)
    candidate = type(original)(
        tuple(replace(r, condition="PMm") for r in original.rows)
    )
    writer = getattr(canonical_io, f"write_canonical_protein_{family}_window_csv")
    written = writer(candidate, tmp_path)
    assert written.written
    bound = next(f for f in resume.FAMILIES if f.name == family).canonical_reader(
        written.output_path
    )
    check = resume.compare_condition_models(original, bound)
    assert check["complete_model_mismatches"] == 0
    assert check["changed_fields"] == ["condition"]
    assert original.rows[0].condition is None


@pytest.mark.parametrize("family", ["lipid", "glycan"])
@pytest.mark.parametrize(
    "mutation", ["metric", "partner", "window", "population", "chain"]
)
def test_rebinding_rejects_any_science_change(family, mutation):
    original = source(family)
    row = replace(original.rows[0], condition="PMm")
    changes = {
        "metric": dict(distance_mean_A=row.distance_mean_A + 0.1),
        "partner": {f"{family}_partner_id": "substituted-partner"},
        "window": dict(window_id="window_0002", window_index=1),
        "chain": dict(protein_chain_id="other"),
    }
    rows = () if mutation == "population" else (replace(row, **changes[mutation]),)
    with pytest.raises(ValueError, match="non-condition"):
        resume.compare_condition_models(original, type(original)(rows))


def coverage_case(tmp_path):
    bindings, freezes = [], {}
    for family in resume.FAMILIES:
        for replica in resume.REPLICAS:
            writer = getattr(
                canonical_io,
                "write_canonical_protein_"
                + ("edge" if family.name == "protein" else family.name)
                + "_window_csv",
            )
            result = writer(source(family.name, replica), tmp_path / replica)
            relative = result.output_path.relative_to(tmp_path).as_posix()
            bindings.append(
                ReleaseCanonicalBinding(
                    family.name, relative, (resume.c2.key(replica),)
                )
            )
            freezes[relative] = dict(resume.file_record(result.output_path), rows=1)
    return SimpleNamespace(
        canonical_bindings=tuple(bindings),
        scientific_release_replica_keys=tuple(
            resume.c2.key(r) for r in resume.REPLICAS
        ),
    ), freezes


@pytest.mark.parametrize("defect", [None, "missing", "fake_empty"])
def test_frozen_coverage_all_nine_required(tmp_path, defect):
    control, freezes = coverage_case(tmp_path)
    if defect == "missing":
        control.canonical_bindings = control.canonical_bindings[:-1]
    if defect == "fake_empty":
        binding = control.canonical_bindings[-1]
        empty = resume.FAMILIES[2].canonical_table(())
        result = canonical_io.write_canonical_protein_glycan_window_csv(
            empty, (tmp_path / binding.path).parent, overwrite=True
        )
        freezes[binding.path] = dict(resume.file_record(result.output_path), rows=0)
    result = resume.c3.coverage_readiness(
        control, tmp_path, set(control.scientific_release_replica_keys), freezes
    )
    assert result["status"] == ("PASS" if defect is None else "STOP")


@pytest.mark.parametrize(
    "defect", [None, "lipid_path", "glycan_path", "correspondence"]
)
def test_no_specialized_aggregation_or_correspondence(defect):
    control = SimpleNamespace(lipid_aggregate_path=None, glycan_aggregate_path=None)
    correspondence = SimpleNamespace(correspondences=())
    used = SimpleNamespace(
        lipid_canonical_table_paths=(),
        glycan_canonical_table_paths=(),
        groups=(
            SimpleNamespace(
                lipid_correspondences=correspondence,
                glycan_correspondences=correspondence,
            ),
        ),
    )
    if defect == "lipid_path":
        control.lipid_aggregate_path = "invented.csv"
    elif defect == "glycan_path":
        used.glycan_canonical_table_paths = ("invented.csv",)
    elif defect:
        correspondence.correspondences = ("invented-global-id",)
    if defect:
        with pytest.raises(ValueError, match="unauthorized"):
            resume.no_specialized_aggregation(control, used)
    else:
        resume.no_specialized_aggregation(control, used)


def emitted_table(model, table_id):
    schema = publication_table_spec(table_id)
    return build_publication_table(
        table_id,
        [
            {
                c.name: model.canonical_reference_id
                if c.name == "canonical_reference_id"
                else getattr(row, c.name)
                for c in schema.columns
            }
            for row in model.rows
        ],
    )


@pytest.mark.parametrize("family", list(resume.TABLES))
@pytest.mark.parametrize(
    "defect", [None, "numeric", "identity", "missing", "extra", "null"]
)
def test_every_published_science_field_compared(family, defect):
    model = source(family, condition="PMm")
    table = emitted_table(model, resume.TABLES[family])
    rows = list(table.records())
    if defect == "numeric":
        rows[0]["occupancy"] += 1
    elif defect == "identity":
        rows[0]["trajectory_id"] = "other"
    elif defect == "missing":
        rows.clear()
    elif defect == "extra":
        rows.append(dict(rows[0]))
    elif defect == "null":
        rows[0]["mean_episode_length_ns"] = None
    persisted = SimpleNamespace(
        spec=table.spec, records=lambda: rows, row_count=len(rows)
    )
    result = resume.compare_emitted_fields(model, persisted)
    assert result["status"] == ("PASS" if defect is None else "FAIL")
    assert result["checked_fields"] == [c.name for c in table.spec.columns]


@pytest.fixture(scope="module")
def release_case(tmp_path_factory):
    from test_dataset_release_workflow import make_release_case

    from mania.dataset_release_workflow import build_dataset_release

    path, control = make_release_case(
        tmp_path_factory.mktemp("c4-synthetic"), mode="sha256"
    )
    return path, control, build_dataset_release(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mean_occupancy", 99),
        ("n_replicates_available", 99),
        ("std_occupancy", None),
        ("condition", "other"),
    ],
)
def test_aggregate_tampering_rejected(release_case, field, value):
    path, control, bundle = release_case
    aggregate = resume.FAMILIES[0].reader(path.parent / control.protein_aggregate_path)
    table = bundle.science.protein_edges_by_window_replica_aggregation
    assert resume.compare_emitted_fields(aggregate, table)["status"] == "PASS"
    rows = table.records()
    rows[0][field] = value
    bad = SimpleNamespace(spec=table.spec, records=lambda: rows, row_count=len(rows))
    assert resume.compare_emitted_fields(aggregate, bad)["status"] == "FAIL"


def test_accepted_f1_rejects_protein_substitution(release_case):
    path, control, bundle = release_case
    used = bundle.aggregation_authority.aggregation_manifest_used
    from mania.replica_aggregation_workflow import load_replica_aggregation_inputs

    canonical = load_replica_aggregation_inputs(used)
    original = canonical["protein"]
    row = original.rows[0]
    changed = replace(row, source_chain_id="substituted")
    canonical["protein"] = type(original)((changed, *original.rows[1:]))
    with pytest.raises(ValueError, match="differs from Stage 31"):
        resume.validate_release_canonical_source_authority(control, used, canonical)


def test_accepted_f2_missing_source_and_empty_path(release_case):
    path, control, bundle = release_case
    inputs = resume.read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    empty = replace(inputs, metrics=(), metric_source_value_fields=())
    resume.validate_publication_metric_sources(
        empty, control, path.parent, bundle.metadata
    )
    assert empty.metrics == ()
    metric = replace(inputs.metrics[0], source_artifact_path="missing.csv")
    bad = replace(
        inputs,
        metrics=(metric,),
        metric_source_value_fields=inputs.metric_source_value_fields[:1],
    )
    with pytest.raises(ValueError, match="exactly one canonical binding"):
        resume.validate_publication_metric_sources(
            bad, control, path.parent, bundle.metadata
        )


def pilot_records():
    return dict(
        simulations=[resume.c2.identity(r) for r in resume.REPLICAS],
        systems=[resume.c2.identity("1")],
        time_windows=[
            dict(
                replica_id=r,
                requested_window_start_ns=resume.publication_number(0.1),
                requested_window_end_ns=resume.publication_number(0.5),
                expected_sample_count=5,
                resolved_sample_count=5,
                missing_sample_count=0,
            )
            for r in resume.REPLICAS
        ],
        metrics=[],
        protein_lipid_contacts_by_window_replica_aggregation=[],
        protein_glycan_contacts_by_window_replica_aggregation=[],
    )


@pytest.mark.parametrize(
    "defect", [None, "fourth", "missing", "100ns", "metric", "specialized"]
)
def test_exact_three_simulation_pilot_and_empty_metrics(defect):
    records = pilot_records()
    if defect == "fourth":
        records["simulations"].append(dict(records["simulations"][0], replica_id="4"))
    elif defect == "missing":
        records["simulations"].pop()
    elif defect == "100ns":
        records["time_windows"][0]["requested_window_end_ns"] = 100
    elif defect == "metric":
        records["metrics"] = ["fake centrality"]
    elif defect == "specialized":
        records["protein_lipid_contacts_by_window_replica_aggregation"] = ["fake"]
    if defect:
        with pytest.raises(ValueError):
            resume.inspect_identity(records)
    else:
        resume.inspect_identity(records)


@pytest.mark.parametrize(
    "flag",
    [
        "is_glycosylation_site",
        "is_disulfide_variant_site",
        "is_cysteine_variant_site",
        "is_ecd",
        "is_mx35_region",
    ],
)
def test_complete_annotation_output_checked(flag):
    sites = {
        "is_glycosylation_site": {295, 308},
        "is_disulfide_variant_site": {303, 322, 328, 350},
        "is_cysteine_variant_site": set(),
        "is_ecd": set(range(234, 362)),
        "is_mx35_region": set(range(311, 342)),
    }
    rows = [
        dict(canonical_residue_number=n, **{f: n in s for f, s in sites.items()})
        for n in range(1, 691)
    ]
    table = SimpleNamespace(records=lambda: rows)
    assert resume.publication.annotation_output_check(table)["status"] == "PASS"
    rows[0][flag] = not rows[0][flag]
    with pytest.raises(ValueError, match="annotation differs"):
        resume.publication.annotation_output_check(table)


@pytest.mark.parametrize(
    "status,complete,unsupported",
    [
        ("passed", False, 0),
        ("failed", True, 0),
        ("passed", True, 1),
        ("passed", True, 0),
    ],
)
def test_partial_release_never_passes(status, complete, unsupported):
    report = SimpleNamespace(
        status=status, complete=complete, unsupported_count=unsupported
    )
    if (status, complete, unsupported) == ("passed", True, 0):
        resume.require_complete(report)
    else:
        with pytest.raises(ValueError, match="Complete"):
            resume.require_complete(report)


def test_stop_before_publication_never_executes_upstream(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "checkpoint", lambda *_: "test-head")
    monkeypatch.setattr(
        resume, "bind_history", Mock(side_effect=ValueError("frozen mismatch"))
    )
    forbidden = Mock(side_effect=AssertionError("Upstream execution forbidden"))
    for name in ("run_dataset_qc", "run_replica_aggregation", "prepare_qc"):
        monkeypatch.setattr(resume.c2, name, forbidden)
    publish = Mock(side_effect=AssertionError("Publication should stop"))
    monkeypatch.setattr(resume, "run_dataset_release", publish)
    result = resume.run(tmp_path, tmp_path)
    assert result["stage34c4_status"] == "STOP"
    assert result["stage34_status"] == "IN PROGRESS"
    for gate in resume.GATES:
        assert resume.read(tmp_path / f"{gate}.json")["status"] == "NOT RUN"
    forbidden.assert_not_called()
    publish.assert_not_called()


def test_specialized_f1_checks_frozen_models(tmp_path, monkeypatch):
    control, _ = coverage_case(tmp_path)
    specialized = {
        f.name: {r: source(f.name, r) for r in resume.REPLICAS}
        for f in resume.FAMILIES[1:]
    }
    canonical = resume.c3.frozen_coverage_gate(
        control, tmp_path, set(control.scientific_release_replica_keys)
    )
    # The production F1's protein part is independently tested above; this isolates
    # C.4's supplemental frozen-specialized comparison without fake Stage 31 input.
    monkeypatch.setattr(
        resume, "validate_release_canonical_source_authority", lambda *_: None
    )
    for binding in control.canonical_bindings:
        if binding.family == "protein":
            continue
        original = specialized[binding.family][binding.replica_keys[0][-1]]
        writer = getattr(
            canonical_io, f"write_canonical_protein_{binding.family}_window_csv"
        )
        writer(
            type(original)(tuple(replace(r, condition="PMm") for r in original.rows)),
            (tmp_path / binding.path).parent,
            overwrite=True,
        )
    canonical = resume.c3.frozen_coverage_gate(
        control, tmp_path, set(control.scientific_release_replica_keys)
    )
    authority = SimpleNamespace(aggregation_manifest_used=None)
    assert (
        resume.validate_f1(control, authority, canonical, specialized, tmp_path)[
            "status"
        ]
        == "PASS"
    )
    substituted = copy.copy(canonical)
    table = canonical["lipid"]
    substituted["lipid"] = type(table)(
        (replace(table.rows[0], distance_mean_A=3.1), *table.rows[1:])
    )
    with pytest.raises(ValueError, match="F1 specialized"):
        resume.validate_f1(control, authority, substituted, specialized, tmp_path)


@pytest.mark.parametrize(
    "defect", [None, "reviewer", "artifact", "replica", "duplicate"]
)
def test_manual_review_uses_accepted_finding_id_and_exact_evidence(defect):
    human = dict(
        evidence_id="human:rmsd:pilot-r2",
        evidence_type="artifact",
        artifact_path="r2_manual_rmsd_assessment.json",
        details='{"reviewer":"Andrey","replica_id":"2"}',
    )
    published = [
        dict(human, check_id="rmsd_drift", evidence_id="rmsd_drift:evidence:2")
    ]
    if defect == "reviewer":
        published[0]["details"] = '{"reviewer":"automatic group reviewer"}'
    elif defect == "artifact":
        published[0]["artifact_path"] = "substitution.json"
    elif defect == "replica":
        published[0]["details"] = '{"reviewer":"Andrey","replica_id":"3"}'
    elif defect == "duplicate":
        published.append(dict(published[0]))
    if defect:
        with pytest.raises(ValueError, match="Manual reviewer"):
            resume.retained_manual_evidence(human, published)
    else:
        assert (
            resume.retained_manual_evidence(human, published)["evidence_id"]
            == "rmsd_drift:evidence:2"
        )
