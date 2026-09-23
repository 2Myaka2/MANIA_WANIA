"""Synthetic authority/stop regressions; never assert real scientific authority."""

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_dataset_qc_manifest import make_qc_case
from test_replica_protein_edge_aggregation import group, row, table

from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_workflow import execute_dataset_qc_manifest
from mania.dataset_release_canonical import DatasetReleaseCanonicalError
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_aggregation_tables import (
    build_canonical_protein_edge_replica_aggregation_table,
)
from mania.replica_protein_edge_aggregation import (
    aggregate_canonical_protein_edges_across_replicas,
)
from mania.replica_specialized_aggregation import SpecializedPartnerCorrespondences

spec = importlib.util.spec_from_file_location(
    "stage34b5_resume",
    Path(__file__).parents[1] / "tools/stage34b5_resume_downstream_smoke.py",
)
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


@pytest.fixture
def authority():
    return dict(
        identity=resume.accepted.IDENTITY.copy(),
        reviewer="\u0420\u0430\u043c\u0438\u043b\u044f "
        "\u0410\u0445\u043c\u0435\u0442\u043e\u0432\u043d\u0430",
        drift_detected=False,
        scope=resume.SCOPE,
        pilot_interval_ns=[0.1, 0.5],
        basis="Stage 34.B.5 RMSD evidence",
        condition="PMm",
        source_family=resume.FAMILY,
        pbc_protocol_approved=True,
        authority_source="Synthetic test of explicit human-input transport",
    )


def test_human_review_retains_authority_without_recalculation(
    authority, tmp_path, monkeypatch
):
    forbidden = Mock(side_effect=AssertionError("RMSD recalculation forbidden"))
    monkeypatch.setattr(resume.accepted, "aligned_rmsd", forbidden)
    basis = {
        "rmsd_evidence.csv": {"path": str(tmp_path / "accepted.csv"), "sha256": "test"}
    }
    assessment = resume.bind_human_review(authority, basis, tmp_path)
    assert assessment.drift_detected is False
    record = json.loads((tmp_path / "rmsd_assessment_binding.json").read_text())
    assert record["reviewer"] == authority["reviewer"]
    assert record["basis_artifacts"] == basis
    assert record["scope"] == resume.SCOPE
    assert record["automatic_threshold"] is None
    assert record["rmsd_recalculated"] is False
    assert record["binding_time_utc"]
    assert record["authority"].startswith("external human authority")
    details = json.loads(assessment.evidence[0].details)
    assert details["reviewer"] == record["reviewer"]
    assert details["scope"] == record["scope"]
    assert (
        details["binding_sha256"]
        == resume.file_record(tmp_path / "rmsd_assessment_binding.json")["sha256"]
    )
    assert str(tmp_path) not in assessment.evidence[0].details
    forbidden.assert_not_called()


@pytest.mark.parametrize("value", [None, "false", 0])
def test_absent_or_coerced_drift_is_not_inferred(authority, value):
    authority["drift_detected"] = value
    with pytest.raises(ValueError, match="No automatic"):
        resume.validate_authority(authority)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "full trajectory"),
        ("pilot_interval_ns", [0, 100]),
        ("reviewer", ""),
        ("source_family", "Alina NAMD source family"),
        ("condition", None),
    ],
)
def test_authority_cannot_expand_or_lose_scope(authority, field, value):
    authority[field] = value
    with pytest.raises(ValueError):
        resume.validate_authority(authority)


def test_condition_only_changes_explicit_existing_field(authority):
    identity = DatasetTrajectoryIdentity(**resume.accepted.IDENTITY)
    bound = resume.bind_condition(identity, authority)
    assert bound.condition == "PMm"
    assert bound.to_dict() | {"condition": None} == identity.to_dict()
    assert (bound.disulfide_state, bound.replica_id, bound.engine) == (
        "2SS",
        "1",
        "namd",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"system_id": "Alina-PMm"},
        {"trajectory_id": "file-PMm.xtc"},
        {"replica_id": "2"},
        {"engine": "gromacs"},
    ],
)
def test_filename_membrane_or_engine_cannot_supply_condition(authority, change):
    identity = DatasetTrajectoryIdentity(**(resume.accepted.IDENTITY | change))
    with pytest.raises(ValueError, match="cannot be inferred"):
        resume.bind_condition(identity, authority)


@pytest.fixture
def rmsd_case():
    binding = dict(
        prepared={"sha256": "prepared"}, authority={"psf": {"sha256": "psf"}}
    )
    method = dict(
        system_identity=resume.accepted.IDENTITY,
        prepared_trajectory=binding["prepared"],
        psf=binding["authority"]["psf"],
        pilot_interval_ns=[0.1, 0.5],
        prepared_frames=list(range(5)),
        source_frames=list(range(5)),
        scientific_times_ns=list(resume.accepted.TIMES_NS),
        atom_selection=resume.accepted.SELECTION,
        alignment_selection=resume.accepted.SELECTION,
        rmsd_selection=resume.accepted.SELECTION,
        n_atoms_used=690,
        reference_prepared_frame_index=0,
        reference_scientific_time_ns=0.1,
        alignment_method="Equal-weight least-squares rigid-body Kabsch fit; test",
        internal_mic=False,
        reproducibility={"runs_A": [[0, 1, 2, 3, 4]]},
    )
    rows = [
        dict(
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            scientific_time_ns=t,
            rmsd_A=i,
            atom_selection=resume.accepted.SELECTION,
            n_atoms_used=690,
            reference_prepared_frame_index=0,
            reference_scientific_time_ns=0.1,
        )
        for i, t in enumerate(resume.accepted.TIMES_NS)
    ]
    return method, binding, rows


def test_exact_rmsd_method_and_csv_binding(rmsd_case):
    resume.validate_rmsd_method(*rmsd_case)


@pytest.mark.parametrize(
    "mutation", ["prepared", "time", "selection", "atoms", "reference", "mic"]
)
def test_changed_rmsd_binding_rejected(rmsd_case, mutation):
    method, binding, rows = rmsd_case
    if mutation == "prepared":
        method["prepared_trajectory"] = {"sha256": "other"}
    elif mutation == "time":
        rows[1]["scientific_time_ns"] = 99
    elif mutation == "selection":
        method["atom_selection"] = "all"
    elif mutation == "atoms":
        method["n_atoms_used"] = 689
    elif mutation == "reference":
        method["reference_prepared_frame_index"] = 1
    else:
        method["internal_mic"] = True
    with pytest.raises(ValueError):
        resume.validate_rmsd_method(method, binding, rows)


def test_archive_binding_rejects_changed_evidence(tmp_path):
    base = tmp_path / "accepted"
    base.mkdir()
    (base / "evidence.csv").write_text("original")
    with resume.zipfile.ZipFile(base.with_suffix(".zip"), "w") as archive:
        archive.writestr("evidence.csv", "original")
    (base / "evidence.csv").write_text("changed")
    with pytest.raises(ValueError, match="archive differs"):
        resume.archive_copy(base, "evidence.csv", tmp_path / "copy")
    assert not (tmp_path / "copy").exists()


def test_protocol_approval_preserves_trajectory_history(authority, tmp_path):
    (tmp_path / "frozen").mkdir()
    path = tmp_path / "frozen/b3_pbc.json"
    history = dict(
        scientific_pbc_status="unresolved",
        cutoff_boundary_flips=7,
        trajectory_failures=["explicit historical example"],
    )
    path.write_text(json.dumps(history))
    before = path.read_bytes()
    resume.record_pbc_approval(authority, {"prepared": {"sha256": "test"}}, tmp_path)
    check = json.loads((tmp_path / "pbc_protocol_status_check.json").read_text())
    protocol = json.loads((tmp_path / "pbc_protocol_approval.json").read_text())
    assert path.read_bytes() == before
    assert check["trajectory_evidence_preserved"] == history
    assert check["scientific_pbc_status"] == "unresolved"
    assert check["internal_mic"] is False
    assert protocol["every_trajectory_validated"] is False
    assert protocol["protocol_scientifically_approved"] is True
    assert protocol["wrapping_individual_atoms"] is False


@pytest.mark.parametrize(
    "outcome,decision", [("pending", "pending_review"), ("fail", "excluded")]
)
def test_accepted_qc_workflow_blocks_unavailable_decision(tmp_path, outcome, decision):
    control, path, *_ = make_qc_case(
        tmp_path, outcomes=(outcome,) * 3, specialized=False
    )
    outputs = execute_dataset_qc_manifest(control, path)
    assert all(r.release_decision == decision for r in outputs.decisions.records)
    with pytest.raises(ValueError, match="QC decision gate STOP"):
        resume.require_available(outputs)


def test_available_manifest_comes_from_accepted_workflow(tmp_path):
    control, path, *_ = make_qc_case(
        tmp_path, outcomes=("pass",) * 3, specialized=False
    )
    # Preserve only the first explicitly declared replica in this synthetic n=1 case.
    template_path = path.parent / control.aggregation_manifest_template_path
    template = resume.read_replica_aggregation_manifest(template_path)
    first = template.groups[0]
    first = replace(
        first,
        spec=replace(first.spec, expected_replica_ids=("1",)),
        members=(first.members[0],),
    )
    template = replace(template, groups=(first,))
    assert resume.write_replica_aggregation_manifest(
        template, template_path, overwrite=True
    ).written
    control = replace(control, replicas=(control.replicas[0],))
    outputs = execute_dataset_qc_manifest(control, path)
    resume.require_available(outputs)
    assert outputs.decisions.records[0].decision_mode == "automatic"
    assert (
        outputs.derived_manifest.groups[0].members[0].availability_status == "available"
    )


@pytest.fixture
def aggregate_case(tmp_path):
    compatible = group(("available",))
    source = table(row(occupancy=0.6))  # Exactly three of five frames.
    result = aggregate_canonical_protein_edges_across_replicas(compatible, source)
    aggregate = build_canonical_protein_edge_replica_aggregation_table((result,))
    workflow = ReplicaAggregationWorkflowGroup(
        compatible.spec,
        compatible.members,
        SpecializedPartnerCorrespondences(()),
        SpecializedPartnerCorrespondences(()),
    )
    manifest = ReplicaAggregationManifest(
        (tmp_path / "source.csv",), (), (), (workflow,)
    )
    return source, aggregate, manifest


def test_independent_n1_null_std_and_no_production_call(aggregate_case, monkeypatch):
    monkeypatch.setattr(
        "mania.replica_protein_edge_aggregation.aggregate_canonical_protein_edges_across_replicas",
        Mock(side_effect=AssertionError("Independent side called production")),
    )
    result = resume.independent_protein_check(*aggregate_case)
    assert result["aggregate_mismatches"] == 0
    assert result["std_occupancy"] is None and result["n_replicates_available"] == 1


def test_independent_aggregation_detects_altered_numeric_value(aggregate_case):
    source, aggregate, manifest = aggregate_case
    altered = replace(
        aggregate,
        rows=(replace(aggregate.rows[0], mean_occupancy=0.4, median_occupancy=0.4),),
    )
    result = resume.independent_protein_check(source, altered, manifest)
    assert result["aggregate_mismatches"] == 1
    with pytest.raises(ValueError, match="before independently verified"):
        resume.require_stage31(result)


def test_stage33_cannot_run_before_stage31():
    with pytest.raises(ValueError, match="Stage 33 cannot run"):
        resume.publication_readiness({}, ())


def test_stage33_requires_authoritative_complete_annotations():
    with pytest.raises(DatasetReleaseCanonicalError, match="complete_for_system"):
        resume.publication_readiness({"status": "PASS", "aggregate_mismatches": 0}, ())


def test_smoke_cannot_claim_full_100ns_dataset():
    temporal = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                dataset_spec=SimpleNamespace(
                    temporal=SimpleNamespace(
                        production_start_ns=0, production_end_ns=100
                    )
                ),
                window_plan=SimpleNamespace(windows=(object(),)),
            ),
        )
    )
    with pytest.raises(ValueError, match="Smoke cannot claim"):
        resume.aggregation_template(None, temporal, Path("protein.csv"))


@pytest.fixture(scope="module")
def release_case(tmp_path_factory):
    from test_dataset_release_workflow import make_release_case

    from mania.dataset_release_workflow import build_dataset_release

    path, control = make_release_case(tmp_path_factory.mktemp("resume-f1-f2"))
    return path, control, build_dataset_release(path)


def test_f1_rejects_complete_canonical_model_mismatch(release_case):
    from mania.dataset_release_source_authority import (
        validate_release_canonical_source_authority,
    )
    from mania.replica_aggregation_workflow import load_replica_aggregation_inputs

    _, control, bundle = release_case
    used = bundle.aggregation_authority.aggregation_manifest_used
    canonical = load_replica_aggregation_inputs(used)
    protein = canonical["protein"]
    canonical["protein"] = replace(protein, rows=protein.rows[1:])
    with pytest.raises(ValueError, match="differs from Stage 31"):
        validate_release_canonical_source_authority(control, used, canonical)


def test_f2_missing_source_record_rejected_and_empty_metrics_allowed(release_case):
    from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
    from mania.dataset_release_source_authority import (
        validate_publication_metric_sources,
    )

    path, control, bundle = release_case
    inputs = read_dataset_release_publication_inputs(
        path.parent / control.publication_inputs_path
    )
    altered = replace(
        inputs, metrics=(replace(inputs.metrics[0], source_record_key="[]"),)
    )
    with pytest.raises(ValueError, match="exactly one record"):
        validate_publication_metric_sources(
            altered, control, path.parent, bundle.metadata
        )
    empty = replace(inputs, metrics=(), metric_source_value_fields=())
    validate_publication_metric_sources(empty, control, path.parent, bundle.metadata)
    assert empty.metrics == ()
