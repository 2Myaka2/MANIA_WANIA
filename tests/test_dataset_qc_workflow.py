"""Accepted evaluator equality, authority rules, and correspondence projection."""

import copy
from dataclasses import fields, replace

import pytest
from test_dataset_qc_manifest import make_qc_case

from mania.dataset_hard_qc import evaluate_replica_hard_qc
from mania.dataset_qc_contract import (
    ReplicaQCDecisionRecord,
    build_dataset_qc_decision_set,
)
from mania.dataset_qc_workflow import (
    build_qc_derived_replica_aggregation_manifest,
    execute_dataset_qc_manifest,
)
from mania.dataset_review_qc import evaluate_dataset_review_qc
from mania.replica_aggregation_manifest_io import (
    read_replica_aggregation_manifest,
    replica_aggregation_manifest_payload,
    write_replica_aggregation_manifest,
)
from mania.replica_specialized_aggregation import SpecializedPartnerCorrespondences


def directly_evaluated_decisions(manifest, hard_inputs, review_inputs):
    hard = tuple(
        evaluate_replica_hard_qc(**{f.name: getattr(e, f.name) for f in fields(e)})
        for e in hard_inputs.values()
    )
    reviews = evaluate_dataset_review_qc(hard, tuple(review_inputs.values()))
    by_key = {r.replica_key: r for r in reviews.evaluations}
    controls = {r.replica_key: r for r in manifest.replicas}
    records = []
    for result in hard:
        findings = result.checks
        if result.hard_qc_status == "pass":
            findings += by_key[result.replica_key].checks
        primary = next((f for f in findings if f.status != "pass"), None)
        manual = controls[result.replica_key].manual_resolution
        if manual is not None:
            record = ReplicaQCDecisionRecord(
                *result.replica_key,
                "review",
                findings,
                manual.release_decision,
                "manual",
                manual.decision_reason_code,
                manual.human_readable_reason,
                manual.decision_evidence_ids,
                manual.reviewer,
                manual.decision_note,
            )
        elif primary is not None:
            record = ReplicaQCDecisionRecord(
                *result.replica_key,
                primary.status,
                findings,
                "excluded" if primary.status == "fail" else "pending_review",
                "automatic",
                primary.reason_code,
                primary.human_readable_reason,
                tuple(e.evidence_id for e in primary.evidence),
                None,
                None,
            )
        else:
            record = ReplicaQCDecisionRecord(
                *result.replica_key,
                "pass",
                findings,
                "available",
                "automatic",
                None,
                None,
                (),
                None,
                None,
            )
        records.append(record)
    return build_dataset_qc_decision_set(tuple(records))


@pytest.mark.parametrize("family", ["protein_only", "lipid", "glycan", "both"])
def test_projection_and_accepted_stage31_roundtrip(tmp_path, family):
    manifest, path, template, hard, reviews = make_qc_case(
        tmp_path,
        specialized=family != "protein_only",
        multiple=True,
        windows=True,
    )
    if family in ("lipid", "glycan"):
        other = "glycan" if family == "lipid" else "lipid"
        template = replace(
            template,
            groups=tuple(
                replace(
                    g,
                    **{
                        f"{other}_correspondences": SpecializedPartnerCorrespondences(
                            ()
                        )
                    },
                )
                for g in template.groups
            ),
        )
        assert write_replica_aggregation_manifest(
            template,
            path.parent / manifest.aggregation_manifest_template_path,
            overwrite=True,
        ).written
    original_model = copy.deepcopy(template)
    template_path = path.parent / manifest.aggregation_manifest_template_path
    original_bytes = template_path.read_bytes()
    outputs = execute_dataset_qc_manifest(manifest, path)
    assert outputs.production_ready
    direct = directly_evaluated_decisions(manifest, hard, reviews)
    assert outputs.decisions == direct
    derived = build_qc_derived_replica_aggregation_manifest(template, direct)
    assert outputs.derived_manifest == derived
    for before, after in zip(template.groups, derived.groups, strict=True):
        assert after.spec == before.spec
        assert [m.availability_status for m in after.members] == [
            "excluded",
            "available",
            "available",
        ]
        assert after.members[0].availability_reason.startswith(
            "QC exclusion [PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT]: "
        )
        for kind in ("lipid", "glycan"):
            source = getattr(before, f"{kind}_correspondences").correspondences
            target = getattr(after, f"{kind}_correspondences").correspondences
            assert len(source) == len(target)
            for a, b in zip(source, target, strict=True):
                assert b.to_dict() | {"members": a.to_dict()["members"]} == a.to_dict()
                assert b.members == tuple(m for m in a.members if m.replica_id != "1")
                assert {m.replica_key for m in b.members} == {
                    m.replica_key
                    for m in after.members
                    if m.availability_status == "available"
                }
    # Exact requested lipid example before any window-local changes.
    if family in ("lipid", "both"):
        c = derived.groups[0].lipid_correspondences.correspondences[0]
        assert [(m.replica_id, m.local_partner_id) for m in c.members] == [
            ("2", "lipid_0007"),
            ("3", "lipid_0011"),
        ]
    assert template == original_model
    assert template_path.read_bytes() == original_bytes
    assert replica_aggregation_manifest_payload(template, template_path) == (
        replica_aggregation_manifest_payload(original_model, template_path)
    )
    output_path = tmp_path / "derived.json"
    assert write_replica_aggregation_manifest(derived, output_path).written
    assert read_replica_aggregation_manifest(output_path) == derived


@pytest.mark.parametrize(
    "outcomes", [("fail", "fail", "fail"), ("manual_excluded",) * 3]
)
def test_all_excluded_uses_empty_collections(tmp_path, outcomes):
    manifest, path, _, _, _ = make_qc_case(tmp_path, outcomes=outcomes, multiple=True)
    outputs = execute_dataset_qc_manifest(manifest, path)
    assert outputs.production_ready
    g = outputs.derived_manifest.groups[0]
    assert all(m.availability_status == "excluded" for m in g.members)
    assert g.lipid_correspondences.correspondences == ()
    assert g.glycan_correspondences.correspondences == ()


def test_technical_unavailable_is_preserved_and_not_added(tmp_path):
    manifest, path, template, _, _ = make_qc_case(
        tmp_path,
        unavailable=True,
        outcomes=("fail", "pass", "fail"),
    )
    result = execute_dataset_qc_manifest(manifest, path)
    g = result.derived_manifest.groups[0]
    assert [m.availability_status for m in g.members] == [
        "excluded",
        "available",
        "unavailable",
    ]
    assert g.members[2] == template.groups[0].members[2]
    for kind in ("lipid", "glycan"):
        assert [
            m.replica_id
            for m in getattr(g, f"{kind}_correspondences").correspondences[0].members
        ] == ["2"]


@pytest.mark.parametrize("pending_unavailable", [False, True])
def test_pending_is_valid_but_bridge_forbids_generation(tmp_path, pending_unavailable):
    manifest, path, template, hard, reviews = make_qc_case(
        tmp_path,
        outcomes=("pass", "pass", "pending"),
        unavailable=pending_unavailable,
    )
    outputs = execute_dataset_qc_manifest(manifest, path)
    assert not outputs.production_ready and outputs.derived_manifest is None
    assert outputs.decisions == directly_evaluated_decisions(manifest, hard, reviews)
    record = outputs.decisions.records[-1]
    assert (record.qc_status, record.release_decision, record.decision_mode) == (
        "review",
        "pending_review",
        "automatic",
    )
    with pytest.raises(ValueError, match="Pending review"):
        build_qc_derived_replica_aggregation_manifest(template, outputs.decisions)


def test_defensive_missing_retained_binding_is_not_inferred(tmp_path):
    manifest, path, template, _, _ = make_qc_case(tmp_path)
    outputs = execute_dataset_qc_manifest(manifest, path)
    damaged = copy.deepcopy(template)
    collection = damaged.groups[0].lipid_correspondences
    c = collection.correspondences[0]
    object.__setattr__(c, "members", c.members[:-1])
    with pytest.raises(ValueError, match="cover exactly"):
        build_qc_derived_replica_aggregation_manifest(damaged, outputs.decisions)


def test_complete_system_identity_and_unique_replica_authority(tmp_path):
    manifest, path, template, hard, reviews = make_qc_case(
        tmp_path,
        complete=True,
        windows=True,
        multiple=True,
    )
    result = execute_dataset_qc_manifest(manifest, path)
    assert len(result.decisions.records) == 7
    assert len(result.summary.rows) == 7
    assert result.decisions == directly_evaluated_decisions(manifest, hard, reviews)
    assert result.production_ready
    groups = {g.spec.system_id: g for g in result.derived_manifest.groups}
    assert groups["namd-none"].spec.condition is None
    assert groups["wt-norm"].spec.condition == groups["other-system"].spec.condition
    wt = {r.replica_id: r for r in result.decisions.records if r.system_id == "wt-norm"}
    other = {
        r.replica_id: r
        for r in result.decisions.records
        if r.system_id == "other-system"
    }
    assert wt["1"].qc_status == "fail" and other["1"].qc_status == "review"
    assert wt["3"].release_decision == "available"
    assert other["3"].release_decision == "excluded"
    assert groups["other-system"].members[2].availability_status == "unavailable"
    for family in ("protein", "lipid", "glycan"):
        assert getattr(result.derived_manifest, f"{family}_canonical_table_paths") == (
            getattr(template, f"{family}_canonical_table_paths")
        )


def test_first_fail_and_first_review_are_the_accepted_order(tmp_path):
    from mania.dataset_qc_evidence_io import (
        write_replica_hard_qc_evidence,
        write_replica_review_qc_evidence,
    )

    manifest, path, _, hard, reviews = make_qc_case(
        tmp_path,
        outcomes=("fail", "pending", "pass"),
    )
    failed, pending = manifest.replicas[:2]
    evidence = hard[failed.replica_key]
    evidence = replace(
        evidence,
        protein_pbc=replace(
            evidence.protein_pbc,
            protein_remains_broken=True,
        ),
    )
    assert write_replica_hard_qc_evidence(
        evidence,
        path.parent / failed.hard_qc_evidence_path,
        overwrite=True,
    ).written
    review = reviews[pending.replica_key]
    review = replace(
        review,
        protein_edge_empty_windows=replace(
            review.protein_edge_empty_windows,
            empty_window_count=2,
        ),
    )
    assert write_replica_review_qc_evidence(
        review,
        path.parent / pending.review_qc_evidence_path,
        overwrite=True,
    ).written
    result = execute_dataset_qc_manifest(manifest, path)
    fail_record, review_record = result.decisions.records[:2]
    assert sum(c.status == "fail" for c in fail_record.findings) == 2
    assert fail_record.decision_reason_code == "PROTEIN_PBC_BROKEN"
    assert sum(c.status == "review" for c in review_record.findings) == 2
    assert review_record.decision_reason_code == "RMSD_DRIFT_REVIEW"
    for record in (fail_record, review_record):
        primary = next(f for f in record.findings if f.status == record.qc_status)
        assert record.human_readable_reason == primary.human_readable_reason
        assert record.decision_evidence_ids == tuple(
            e.evidence_id for e in primary.evidence
        )


def test_manual_resolution_can_select_another_review_but_not_other_reason_evidence(
    tmp_path,
):
    from mania.dataset_qc_evidence_io import write_replica_review_qc_evidence
    from mania.dataset_qc_manifest import QCManualReviewResolution

    manifest, path, _, _, reviews = make_qc_case(
        tmp_path,
        outcomes=("pass", "pending", "pass"),
    )
    control = manifest.replicas[1]
    evidence = reviews[control.replica_key]
    evidence = replace(
        evidence,
        protein_edge_empty_windows=replace(
            evidence.protein_edge_empty_windows,
            empty_window_count=2,
        ),
    )
    assert write_replica_review_qc_evidence(
        evidence,
        path.parent / control.review_qc_evidence_path,
        overwrite=True,
    ).written
    result = execute_dataset_qc_manifest(manifest, path)
    findings = [f for f in result.decisions.records[1].findings if f.status == "review"]
    resolution = QCManualReviewResolution(
        "available",
        findings[1].reason_code,
        "Explicit review of empty windows.",
        tuple(e.evidence_id for e in findings[1].evidence),
        "Reviewer",
        "Clearance",
    )
    revised = replace(
        manifest,
        replicas=(
            manifest.replicas[0],
            replace(control, manual_resolution=resolution),
            manifest.replicas[2],
        ),
    )
    output = execute_dataset_qc_manifest(revised, path)
    assert output.production_ready
    assert output.decisions.records[1].decision_reason_code == findings[1].reason_code
    bad = replace(
        resolution, decision_evidence_ids=(findings[0].evidence[0].evidence_id,)
    )
    with pytest.raises(ValueError, match="Dataset QC decision failed:"):
        execute_dataset_qc_manifest(
            replace(
                revised,
                replicas=(
                    revised.replicas[0],
                    replace(control, manual_resolution=bad),
                    revised.replicas[2],
                ),
            ),
            path,
        )


@pytest.mark.parametrize("collision", ["check", "evidence"])
def test_combined_collisions_are_not_renamed(tmp_path, monkeypatch, collision):
    import mania.dataset_qc_workflow as workflow

    manifest, path, _, _, _ = make_qc_case(tmp_path)
    accepted = workflow.evaluate_dataset_review_qc

    def colliding(hard, evidence):
        result = accepted(hard, evidence)
        review = result.evaluations[0]
        matching_hard = next(h for h in hard if h.replica_key == review.replica_key)
        check = review.checks[0]
        if collision == "check":
            check = replace(check, check_id=matching_hard.checks[0].check_id)
        else:
            check = replace(
                check,
                evidence=(
                    replace(
                        check.evidence[0],
                        evidence_id=matching_hard.checks[0].evidence[0].evidence_id,
                    ),
                    *check.evidence[1:],
                ),
            )
        review = replace(review, checks=(check, *review.checks[1:]))
        return replace(result, evaluations=(review, *result.evaluations[1:]))

    monkeypatch.setattr(workflow, "evaluate_dataset_review_qc", colliding)
    with pytest.raises(ValueError, match="Dataset QC decision failed:"):
        execute_dataset_qc_manifest(manifest, path)


def test_workflow_reuses_dataset_mad_cohort_with_hard_failed_replica_skipped(tmp_path):
    from test_dataset_review_qc import observation

    from mania.dataset_qc_evidence_io import write_replica_review_qc_evidence

    manifest, path, _, hard, reviews = make_qc_case(
        tmp_path,
        outcomes=("pass", "pass", "pass"),
    )
    for control, value in zip(manifest.replicas, (0, 0, 100), strict=True):
        evidence = replace(
            reviews[control.replica_key],
            mad_metrics=(observation(value=value, key=control.replica_key),),
        )
        reviews[control.replica_key] = evidence
        assert write_replica_review_qc_evidence(
            evidence,
            path.parent / control.review_qc_evidence_path,
            overwrite=True,
        ).written
    result = execute_dataset_qc_manifest(manifest, path)
    assert result.decisions == directly_evaluated_decisions(manifest, hard, reviews)
    assert any(r.release_decision == "pending_review" for r in result.decisions.records)
