"""Synthetic Stage 32.D controls shared by the integration acceptance tests."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from test_dataset_hard_qc import inputs, plan
from test_dataset_review_qc import review
from test_replica_aggregation_manifest import control, make_manifest
from test_replica_protein_edge_aggregation import group

from mania.dataset_hard_qc import evaluate_replica_hard_qc
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_evidence_io import (
    ReplicaHardQCEvidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import (
    DatasetQCManifest,
    DatasetQCWorkflowReplica,
    QCManualReviewResolution,
)
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_review_qc import evaluate_dataset_review_qc
from mania.replica_aggregation_manifest_io import write_replica_aggregation_manifest


def make_qc_case(
    root,
    *,
    outcomes=("fail", "pass", "manual_available"),
    specialized=True,
    complete=False,
    unavailable=False,
    windows=False,
    multiple=False,
):
    template, template_path = make_manifest(root, specialized=specialized)
    first = template.groups[0]
    if unavailable:
        first = control(
            group(("available", "available", "unavailable")), specialized=specialized
        )
    groups = [first]
    outcome_by_system = {first.spec.system_id: outcomes}
    if complete:
        for system, statuses, engine, condition, results in (
            (
                "other-system",
                ("available", "available", "unavailable"),
                "gromacs",
                "NORM",
                ("manual_excluded", "pass", "fail"),
            ),
            ("namd-none", ("available",), "namd", None, ("pass",)),
        ):
            groups.append(
                control(
                    group(
                        statuses, system_id=system, engine=engine, condition=condition
                    ),
                    specialized=specialized,
                )
            )
            outcome_by_system[system] = results
    if multiple:
        revised = []
        for g in groups:
            changes = {}
            for family in ("lipid", "glycan"):
                source = getattr(g, f"{family}_correspondences")
                extras = tuple(
                    replace(
                        c,
                        partner_correspondence_id=c.partner_correspondence_id
                        + "_extra",
                        members=tuple(
                            replace(m, local_partner_id=m.local_partner_id + "_x")
                            for m in c.members
                        ),
                    )
                    for c in source.correspondences
                )
                changes[f"{family}_correspondences"] = replace(
                    source,
                    correspondences=tuple(
                        sorted(
                            source.correspondences + extras,
                            key=lambda c: c.partner_correspondence_id,
                        )
                    ),
                )
            revised.append(replace(g, **changes))
        groups = revised
    if windows:
        g = groups[0]
        window = replace(
            g.spec.window,
            window_id="window_0002",
            window_index=1,
            requested_window_start_ns=22.5,
            requested_window_end_ns=27.5,
        )
        changes = {}
        for family in ("lipid", "glycan"):
            source = getattr(g, f"{family}_correspondences")
            changes[f"{family}_correspondences"] = replace(
                source,
                correspondences=tuple(
                    replace(
                        c,
                        members=tuple(
                            replace(m, local_partner_id=m.local_partner_id + "_w")
                            for m in c.members
                        ),
                    )
                    for c in source.correspondences
                ),
            )
        groups.append(
            replace(
                g,
                spec=replace(g.spec, window=window),
                members=tuple(replace(m, window=window) for m in g.members),
                **changes,
            )
        )
    template = replace(template, groups=tuple(groups))
    assert write_replica_aggregation_manifest(
        template, template_path, overwrite=True
    ).written
    members = {m.replica_key: m for g in groups for m in g.members}
    controls, hard_inputs, review_inputs = [], {}, {}
    for index, (key, member) in enumerate(sorted(members.items())):
        outcome = outcome_by_system[member.system_id][int(member.replica_id) - 1]
        values = inputs(
            sampling_plan=plan(expected=100, resolved=94)
            if outcome == "fail"
            else plan(expected=2, resolved=2)
        )
        identity_values = dict(
            zip(
                ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                key,
                strict=True,
            )
        )
        values["identity"] = DatasetTrajectoryIdentity(
            **(
                values["identity"].to_dict()
                | identity_values
                | dict(engine=member.engine, condition=member.condition)
            )
        )
        values["mapping_binding"] = replace(
            values["mapping_binding"], **identity_values
        )
        hard = evaluate_replica_hard_qc(**values)
        review_evidence = review(
            key,
            drift=outcome
            in (
                "pending",
                "manual_available",
                "manual_excluded",
                "fail",
            ),
            engine=member.engine,
        )
        resolution = None
        if outcome.startswith("manual_"):
            evaluated = evaluate_dataset_review_qc((hard,), (review_evidence,))
            finding = next(
                c for c in evaluated.evaluations[0].checks if c.status == "review"
            )
            resolution = QCManualReviewResolution(
                outcome.removeprefix("manual_"),
                finding.reason_code,
                "Synthetic reviewer assessment.",
                tuple(e.evidence_id for e in finding.evidence),
                "Synthetic Reviewer",
                "Explicit synthetic resolution; no real evidence.",
            )
        hard_path = Path(f"hard/{index:04d}.json")
        review_path = Path(f"review/{index:04d}.json")
        hard_inputs[key] = ReplicaHardQCEvidence(**values)
        review_inputs[key] = review_evidence
        assert write_replica_hard_qc_evidence(
            hard_inputs[key], root / hard_path
        ).written
        assert write_replica_review_qc_evidence(
            review_evidence, root / review_path
        ).written
        controls.append(
            DatasetQCWorkflowReplica(*key, hard_path, review_path, resolution)
        )
    manifest = DatasetQCManifest(Path(template_path.name), tuple(reversed(controls)))
    path = root / "dataset_qc_manifest.json"
    assert write_dataset_qc_manifest(manifest, path).written
    return manifest, path, template, hard_inputs, review_inputs


def test_models_are_frozen_sorted_and_exact(tmp_path):
    manifest, _, _, _, _ = make_qc_case(tmp_path)
    assert tuple(r.replica_key for r in manifest.replicas) == tuple(
        sorted(r.replica_key for r in manifest.replicas)
    )
    with pytest.raises(FrozenInstanceError):
        manifest.kind = "changed"
    for changes in (
        {"replicas": ()},
        {"replicas": manifest.replicas * 2},
        {"aggregation_manifest_template_path": Path("../template.json")},
        {"aggregation_manifest_template_path": Path("/template.json")},
    ):
        with pytest.raises(ValueError):
            replace(manifest, **changes)


@pytest.mark.parametrize(
    "field,value",
    [
        ("release_decision", "pending_review"),
        ("release_decision", True),
        ("decision_reason_code", "PROTEIN_PBC_BROKEN"),
        ("human_readable_reason", ""),
        ("reviewer", ""),
        ("reviewer", None),
        ("decision_note", ""),
        ("decision_evidence_ids", ()),
        ("decision_evidence_ids", ("x", "x")),
        ("decision_evidence_ids", ["x"]),
    ],
)
def test_manual_control_cannot_be_anonymous(field, value):
    valid = QCManualReviewResolution(
        "excluded",
        "RMSD_DRIFT_REVIEW",
        "Reason",
        ("rmsd:evidence:0",),
        "Reviewer",
        "Note",
    )
    with pytest.raises(ValueError):
        replace(valid, **{field: value})
