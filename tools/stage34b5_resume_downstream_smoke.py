#!/usr/bin/env python3
"""Resume the pinned five-frame pilot through gates with supplied human authority.

No coordinates, RMSD, contacts, correspondence or biological annotations are
generated. Publication stops when complete system annotation authority is absent.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_contract import QCEvidenceRecord
from mania.dataset_qc_evidence_io import (
    read_replica_hard_qc_evidence,
    read_replica_review_qc_evidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import DatasetQCManifest, DatasetQCWorkflowReplica
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_qc_run import collect_dataset_qc_input_specs, run_dataset_qc
from mania.dataset_release_canonical import build_dataset_release_residue_annotations
from mania.dataset_review_qc import (
    ProteinEdgeEmptyWindowEvidence,
    ReplicaMADMetricObservation,
    ReplicaReviewQCEvidence,
    RMSDDriftAssessment,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.replica_aggregation_contract import (
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_aggregation_manifest_io import (
    read_replica_aggregation_manifest,
    write_replica_aggregation_manifest,
)
from mania.replica_aggregation_run import (
    collect_replica_aggregation_input_specs,
    run_replica_aggregation,
)
from mania.replica_aggregation_workflow import FAMILIES
from mania.replica_specialized_aggregation import SpecializedPartnerCorrespondences
from mania.validation.unified import validate_run_artifacts

_spec = importlib.util.spec_from_file_location(
    "accepted_rmsd_binding",
    Path(__file__).with_name("stage34b5_rmsd_review_evidence.py"),
)
accepted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(accepted)
require, dump, file_record = accepted.require, accepted.dump, accepted.file_record
RMSD_DIRECTORY = (
    "stage34b5_rmsd_review_20260922T192533Z_3e57caca620945fdadc9b736ade8f510"
)
REPLICA_KEY = tuple(
    accepted.IDENTITY[n]
    for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
)
FAMILY = "Egor NAMD source family"
SCOPE = "five-frame technical pilot only; NOT the full 100-ns trajectory"
LABEL = "Stage 34.B.5 single-replica downstream publication smoke"
ALLOWED_FILES = (
    "tools/stage34b5_resume_downstream_smoke.py",
    "tests/test_stage34b5_resume_downstream_smoke.py",
    "docs/stage34b5_resume_downstream_smoke.md",
)


def command(repo, work, argv):
    start = time.perf_counter()
    result = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
    path = work / "commands.json"
    records = json.loads(path.read_text()) if path.exists() else []
    records.append(
        dict(
            argv=argv,
            exit_code=result.returncode,
            output=result.stdout + result.stderr,
            wall_seconds=time.perf_counter() - start,
        )
    )
    dump(path, records)
    require(result.returncode == 0, f"Command failed: {argv}")
    return result.stdout.strip()


def checkpoint(repo, work):
    branch = command(repo, work, ["git", "branch", "--show-current"])
    head = command(repo, work, ["git", "rev-parse", "HEAD"])
    status = command(repo, work, ["git", "status", "--short"])
    require(branch == "FAIR", "Required branch FAIR")
    require(
        all(line[3:] in ALLOWED_FILES for line in status.splitlines()),
        "Unexpected working-tree changes; inspect before downstream work",
    )
    command(repo, work, ["git", "rev-parse", "develop"])
    for revision in ("develop", "b05f88b", "2b3c59a", "689bed7"):
        command(repo, work, ["git", "merge-base", "--is-ancestor", revision, "HEAD"])
    command(repo, work, ["git", "log", "--oneline", "--decorate", "-32"])
    for name in (
        "tools/stage34b5_rmsd_review_evidence.py",
        "tests/test_stage34b5_rmsd_review_evidence.py",
    ):
        command(repo, work, ["git", "ls-files", "--error-unmatch", name])
        command(repo, work, ["git", "cat-file", "-e", f"HEAD:{name}"])
        require(
            not command(repo, work, ["git", "status", "--porcelain", "--", name]),
            "RMSD evidence helper/tests must be committed and unchanged",
        )
    require(
        not command(repo, work, ["git", "diff", "--cached", "--name-only"]),
        "Nothing may be staged",
    )
    (work / "git_state.txt").write_text(
        json.dumps(
            dict(branch=branch, starting_head=head, starting_status=status), indent=2
        )
        + "\n"
    )
    return head


def archive_copy(base, name, target):
    content = (base / name).read_bytes()
    with zipfile.ZipFile(base.with_suffix(".zip")) as archive:
        require(content == archive.read(name), f"Accepted archive differs: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return file_record(base / name)


def validate_rmsd_method(method, binding, rows):
    require(
        {n: method["system_identity"][n] for n in accepted.IDENTITY}
        == accepted.IDENTITY,
        "RMSD system identity differs",
    )
    require(
        method["prepared_trajectory"] == binding["prepared"]
        and method["psf"] == binding["authority"]["psf"],
        "RMSD prepared trajectory/PSF binding differs",
    )
    require(
        method["pilot_interval_ns"] == [0.1, 0.5]
        and method["prepared_frames"] == method["source_frames"] == list(range(5))
        and method["scientific_times_ns"] == list(accepted.TIMES_NS),
        "RMSD pilot interval differs",
    )
    require(
        all(
            method[n] == accepted.SELECTION
            for n in ("atom_selection", "alignment_selection", "rmsd_selection")
        )
        and method["n_atoms_used"] == 690
        and method["reference_prepared_frame_index"] == 0
        and method["reference_scientific_time_ns"] == 0.1
        and method["alignment_method"].startswith(
            "Equal-weight least-squares rigid-body Kabsch fit;"
        )
        and method["internal_mic"] is False,
        "RMSD method binding differs",
    )
    require(len(rows) == 5, "RMSD requires five evidence rows")
    for index, row in enumerate(rows):
        require(
            int(row["prepared_frame_index"]) == index
            and int(row["source_dcd_frame_index"]) == index
            and float(row["scientific_time_ns"]) == accepted.TIMES_NS[index]
            and float(row["rmsd_A"]) == method["reproducibility"]["runs_A"][0][index]
            and row["atom_selection"] == accepted.SELECTION
            and int(row["n_atoms_used"]) == 690
            and int(row["reference_prepared_frame_index"]) == 0
            and float(row["reference_scientific_time_ns"]) == 0.1,
            "RMSD CSV/method association differs",
        )


def bind_accepted(root, work):
    b3, b4, rmsd = root / accepted.B3, root / accepted.B4, root / RMSD_DIRECTORY
    binding = accepted.bind_inputs(b3, b4)  # Hashes/evidence only; no coordinates.
    records = {}
    for name in ("rmsd_evidence.csv", "rmsd_evidence.png", "rmsd_method.json"):
        records[name] = archive_copy(rmsd, name, work / "review_basis" / name)
    method = json.loads((work / "review_basis/rmsd_method.json").read_text())
    with (work / "review_basis/rmsd_evidence.csv").open() as stream:
        validate_rmsd_method(method, binding, list(csv.DictReader(stream)))
    inventory = accepted.archived_json(rmsd, "evidence_inventory.json")
    for name, record in records.items():
        expected = next(r for r in inventory["files"] if r["path"] == name)
        require(record["sha256"] == expected["sha256"], "RMSD inventory differs")
    frozen = accepted.archived_json(b4, "b5/frozen_scientific_inputs.json")
    for role, record in frozen["inputs"].items():
        source = Path(record["path"])
        require(
            file_record(source)["sha256"] == record["sha256"],
            f"Historical input changed: {role}",
        )
        archive_copy(b4, "b5/" + record["frozen_path"], work / record["frozen_path"])
        require(
            file_record(work / record["frozen_path"])["sha256"] == record["sha256"],
            "Historical copy differs",
        )
    for name in (
        "stage32_qc_evidence.json",
        "stage32_qc_findings.json",
        "stage32_review_observations.json",
        "stage32_qc_pending_decision.json",
    ):
        archive_copy(b4, "b5/" + name, work / "historical" / name)
    protection = accepted.protected_snapshot(b3, b4, binding)
    protection.update(
        {str(p.resolve()): accepted.digest(p) for p in rmsd.rglob("*") if p.is_file()}
    )
    protection[str(rmsd.with_suffix(".zip").resolve())] = accepted.digest(
        rmsd.with_suffix(".zip")
    )
    dump(
        work / "accepted_evidence_bindings.json",
        dict(
            status="PASS",
            b3=str(b3),
            b4=str(b4),
            rmsd=str(rmsd),
            binding=binding,
            rmsd_basis=records,
            protected_sha256=protection,
            coordinate_reads=0,
            rmsd_recalculations=0,
        ),
    )
    return binding, records, protection


def validate_authority(authority):
    require(
        set(authority)
        == {
            "identity",
            "reviewer",
            "drift_detected",
            "scope",
            "pilot_interval_ns",
            "basis",
            "condition",
            "source_family",
            "pbc_protocol_approved",
            "authority_source",
        },
        "Explicit human authority fields required",
    )
    require(
        authority["identity"] == accepted.IDENTITY,
        "Human assessment must bind the exact historical replica",
    )
    require(
        type(authority["drift_detected"]) is bool,
        "No automatic drift decision inference",
    )
    require(
        type(authority["reviewer"]) is str and authority["reviewer"].strip(),
        "Named external human reviewer required",
    )
    require(
        authority["scope"] == SCOPE and authority["pilot_interval_ns"] == [0.1, 0.5],
        "Human review scope must remain five-frame pilot only",
    )
    require(
        authority["basis"] == "Stage 34.B.5 RMSD evidence",
        "Exact reviewed evidence basis required",
    )
    require(
        authority["condition"] == "PMm" and authority["source_family"] == FAMILY,
        "Condition authority must explicitly bind the Egor NAMD family",
    )
    require(
        authority["pbc_protocol_approved"] is True and authority["authority_source"],
        "Explicit protocol authority required",
    )


def bind_human_review(authority, basis, work):
    validate_authority(authority)
    provenance = dict(
        status="PASS",
        reviewer=authority["reviewer"],
        drift_detected=authority["drift_detected"],
        system_identity=authority["identity"],
        pilot_interval_ns=[0.1, 0.5],
        scope=SCOPE,
        basis=authority["basis"],
        basis_artifacts=basis,
        binding_time_utc=datetime.now(UTC).isoformat(),
        authority="external human authority, not an automatic MANIA decision",
        authority_source=authority["authority_source"],
        automatic_threshold=None,
        rmsd_recalculated=False,
        selection=accepted.SELECTION,
        atoms=690,
        reference_frame=0,
        reference_time_ns=0.1,
        alignment="equal-weight Kabsch",
    )
    dump(work / "rmsd_assessment_binding.json", provenance)
    evidence = QCEvidenceRecord(
        "human:rmsd:pilot-r1",
        "artifact",
        "rmsd_assessment_binding",
        "rmsd_assessment_binding.json",
        "window_0001",
        "drift_detected",
        str(authority["drift_detected"]).lower(),
        None,
        json.dumps(
            {
                **{
                    n: provenance[n]
                    for n in (
                        "reviewer",
                        "drift_detected",
                        "scope",
                        "authority",
                        "pilot_interval_ns",
                        "binding_time_utc",
                    )
                },
                "binding_sha256": file_record(work / "rmsd_assessment_binding.json")[
                    "sha256"
                ],
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    return RMSDDriftAssessment(
        authority["drift_detected"],
        "External human assessment of accepted RMSD evidence",
        (evidence,),
    )


def bind_condition(identity, authority):
    validate_authority(authority)
    require(
        identity.to_dict() == authority["identity"],
        "Condition cannot be inferred from filename or applied to another system",
    )
    return DatasetTrajectoryIdentity(**(identity.to_dict() | {"condition": "PMm"}))


def condition_inputs(hard, authority, work):
    identity = bind_condition(hard.identity, authority)
    artifacts, science, changes = [], {}, []
    by_family = dict(
        zip(("protein_edge", "protein_lipid", "protein_glycan"), FAMILIES, strict=True)
    )
    from mania import canonical_window_tables_io as io

    writers = (
        io.write_canonical_protein_edge_window_csv,
        io.write_canonical_protein_lipid_window_csv,
        io.write_canonical_protein_glycan_window_csv,
    )
    for artifact in hard.required_artifacts:
        if artifact.canonical_table is None:
            artifacts.append(artifact)
            continue
        family = by_family[artifact.canonical_family]
        original = artifact.canonical_table
        require(
            all(
                r.replica_key == REPLICA_KEY and r.condition is None
                for r in original.rows
            ),
            "Unexpected canonical metadata identity",
        )
        bound = type(original)(
            tuple(replace(r, condition=identity.condition) for r in original.rows)
        )
        require(
            type(original)(tuple(replace(r, condition=None) for r in bound.rows))
            == original,
            "Condition binding altered scientific values",
        )
        result = writers[FAMILIES.index(family)](bound, work / "bound")
        require(result.written, "Condition-bound canonical write failed")
        record = file_record(result.output_path)
        new_evidence = replace(
            artifact.evidence,
            artifact_path=result.output_path.relative_to(work).as_posix(),
            details="Only condition=null -> PMm changed, by explicit "
            "Egor authority; complete remaining model equality PASS. "
            f"SHA256 {record['sha256']}; condition_authority.json",
        )
        artifacts.append(
            replace(artifact, canonical_table=bound, evidence=new_evidence)
        )
        science[family.name] = (bound, result.output_path)
        changes.append(
            dict(
                family=family.name,
                bound=record,
                row_count=len(bound.rows),
                changed_fields=["condition"],
                scientific_model_equal=True,
                original_evidence=artifact.evidence.to_dict(),
            )
        )
    dump(
        work / "condition_authority.json",
        dict(
            authority_source=authority["authority_source"],
            source_family=FAMILY,
            original_identity=hard.identity.to_dict(),
            bound_identity=identity.to_dict(),
            inferred_from_filename=False,
            global_mapping_rule=False,
            other_families_authorized=False,
            canonical_bindings=changes,
        ),
    )
    return replace(
        hard, identity=identity, required_artifacts=tuple(artifacts)
    ), science


def record_pbc_approval(authority, binding, work):
    # The existing technical audit pins scientific_pbc_status="unresolved".
    from mania.preprocessing.pbc_audit import PBC_SCIENTIFIC_STATUS

    pbc = json.loads((work / "frozen/b3_pbc.json").read_text())
    require(PBC_SCIENTIFIC_STATUS == "unresolved", "Inspect changed PBC schema first")
    dump(
        work / "pbc_protocol_approval.json",
        dict(
            protocol_scientifically_approved=authority["pbc_protocol_approved"],
            authority_source=authority["authority_source"],
            engines=["gromacs", "namd"],
            steps=[
                "unwrap bonded fragments",
                "center on protein",
                "wrap complete bonded molecular fragments into the periodic box",
            ],
            wrapping_individual_atoms=False,
            external_preprocessing=True,
            internal_mic=False,
            every_trajectory_validated=False,
            prerequisite="Each trajectory must pass its applicable validation/evidence",
        ),
    )
    dump(
        work / "pbc_protocol_status_check.json",
        dict(
            status="PASS",
            protocol_approval_record="pbc_protocol_approval.json",
            scientific_pbc_status=PBC_SCIENTIFIC_STATUS,
            internal_mic=False,
            schema_limitation="Single fixed historical technical-audit field; "
            "no protocol-approval field. Approval is external provenance only.",
            trajectory_evidence=file_record(work / "frozen/b3_pbc.json"),
            trajectory_evidence_preserved=pbc,
            prepared_binding=binding["prepared"],
            past_unresolved_history_preserved=True,
        ),
    )


def review_input(hard, rmsd, work):
    observations = json.loads(
        (work / "historical/stage32_review_observations.json").read_text()
    )
    empty = observations["empty_windows"].copy()
    empty["evidence"] = tuple(QCEvidenceRecord(**e) for e in empty["evidence"])
    metric = observations["mad_observation"].copy()
    metric["evidence"] = tuple(QCEvidenceRecord(**e) for e in metric["evidence"])
    return ReplicaReviewQCEvidence(
        *hard.identity.replica_key,
        hard.identity.engine,
        rmsd,
        ProteinEdgeEmptyWindowEvidence(**empty),
        (ReplicaMADMetricObservation(**metric),),
    )


def aggregation_template(hard, temporal, protein_path):
    spec = temporal.bindings[0].dataset_spec.temporal
    window = temporal.bindings[0].window_plan.windows[0]
    require(
        len(temporal.bindings) == len(temporal.bindings[0].window_plan.windows) == 1
        and spec.production_start_ns == 0.1
        and spec.production_end_ns == 0.5
        and spec.frame_stride_ps == 100.0
        and temporal.bindings[0].sampling_plan.requested_sample_count == 5,
        "Smoke cannot claim a full 100-ns Dataset or other pilot contract",
    )
    definition = ReplicaAggregationWindowDefinition(
        window.window_id,
        window.window_index,
        spec.production_start_ns,
        spec.production_end_ns,
        0.1,
        0.5,
        True,
        spec.window_length_ns,
        spec.window_step_ns,
        spec.overlap_percent,
    )
    identity = hard.identity
    group = ReplicaAggregationGroupSpec(
        identity.dataset_id,
        identity.system_id,
        identity.engine,
        identity.variant_id,
        identity.condition,
        identity.disulfide_state,
        (identity.replica_id,),
        definition,
    )
    member = ReplicaAggregationMember(
        **identity.to_dict(),
        canonical_reference_id=group.canonical_reference_id,
        canonical_reference_sequence_sha256=group.canonical_reference_sequence_sha256,
        window=definition,
        availability_status="available",
        availability_reason=None,
    )
    # Technical input template, NOT an authoritative production manifest.
    return ReplicaAggregationManifest(
        (protein_path,),
        (),
        (),
        (
            ReplicaAggregationWorkflowGroup(
                group,
                (member,),
                SpecializedPartnerCorrespondences(()),
                SpecializedPartnerCorrespondences(()),
            ),
        ),
    )


def require_available(outputs):
    require(
        outputs.production_ready
        and outputs.derived_manifest is not None
        and len(outputs.decisions.records) == 1
        and outputs.decisions.records[0].release_decision == "available"
        and all(
            m.availability_status == "available"
            for g in outputs.derived_manifest.groups
            for m in g.members
        ),
        "QC decision gate STOP: n=1 included path requires authoritative available",
    )


def independent_protein_check(source, aggregate, manifest):
    """Direct n=1 identity/value reconstruction; no production aggregation API."""
    require(len(manifest.groups) == 1, "Independent checker supports one pilot window")
    group = manifest.groups[0]
    require(
        len(group.members) == 1 and group.members[0].availability_status == "available",
        "Independent checker requires one QC-available contributor",
    )
    member = group.members[0]
    expected = {}
    for row in source.rows:
        require(row.replica_key == member.replica_key, "Unexpected source replica")
        require(
            all(
                getattr(row, n) == getattr(member, n)
                for n in ("engine", "variant_id", "condition", "disulfide_state")
            )
            and all(
                getattr(row, n) == getattr(group.spec.window, n)
                for n in (
                    "window_id",
                    "window_index",
                    "requested_window_start_ns",
                    "requested_window_end_ns",
                    "right_endpoint_inclusive",
                )
            ),
            "Source identity/window differs from authoritative aggregation group",
        )
        require(
            row.resolved_frame_count == row.requested_sample_count == 5
            and row.missing_sample_count == 0
            and row.coverage_fraction == 1
            and row.occupancy == row.n_contact_frames / row.resolved_frame_count,
            "Source denominator/occupancy differs from the five-frame pilot",
        )
        key = (
            row.source_canonical_residue_number,
            row.target_canonical_residue_number,
            row.edge_type,
        )
        require(key not in expected, "Duplicate source aggregate identity")
        expected[key] = dict(
            **{
                n: getattr(member, n)
                for n in (
                    "dataset_id",
                    "system_id",
                    "engine",
                    "variant_id",
                    "condition",
                    "disulfide_state",
                )
            },
            **group.spec.window.to_dict(),
            source_canonical_residue_number=key[0],
            source_canonical_resname=row.source_canonical_resname,
            target_canonical_residue_number=key[1],
            target_canonical_resname=row.target_canonical_resname,
            edge_type=key[2],
            mean_occupancy=row.occupancy,
            std_occupancy=None,
            median_occupancy=row.occupancy,
            n_replicates_available=1,
            n_replicates_supporting=int(row.occupancy > 0),
            support_fraction=float(row.occupancy > 0),
        )
    observed = {r.entity_identity: r.to_dict() for r in aggregate.rows}
    mismatches = sum(
        expected.get(k) != observed.get(k) for k in expected.keys() | observed.keys()
    )
    return dict(
        status="PASS" if mismatches == 0 else "FAIL",
        aggregate_mismatches=mismatches,
        source_rows=len(source.rows),
        aggregate_rows=len(aggregate.rows),
        contributing_replica_keys=[list(member.replica_key)],
        n_replicates_available=1,
        std_occupancy=None,
        occupancy_denominator="five resolved source frames; one available replica",
        production_aggregator_called_by_independent_side=False,
        specialized_aggregation="NOT RUN: no authoritative partner correspondence",
    )


def require_stage31(check):
    require(
        check.get("status") == "PASS" and check.get("aggregate_mismatches") == 0,
        "Stage 33 cannot run before independently verified Stage 31",
    )


def publication_readiness(check, annotations):
    require_stage31(check)
    # Invoke the accepted mandatory Stage 33 authority gate; never synthesize sites.
    return build_dataset_release_residue_annotations(
        annotations, annotation_publication_system_keys=(REPLICA_KEY[:2],)
    )


def validate_run(root, scope, specs, path):
    result = validate_run_artifacts(
        root,
        scope=scope,
        input_artifact_paths={s.artifact_id: s.local_path for s in specs},
    )
    dump(path, result.to_dict())
    require(
        result.status == "passed" and result.complete, f"Incomplete {scope} validation"
    )
    return result


def run(root, work, authority_path):
    started, timings = time.perf_counter(), {}
    repo = Path(__file__).resolve().parents[1]
    head = checkpoint(repo, work)
    phase = "A: accepted evidence bindings"
    summary = dict(
        label=LABEL,
        starting_head=head,
        stage34b5_status="STOP",
        stage34b_status="INCOMPLETE",
        final_dataset_release=False,
        replicas_2_3_run=False,
        full_100ns_analysis=False,
        all_33_run=False,
        stage35_run=False,
        internal_mic=False,
    )
    try:
        phase_start = time.perf_counter()
        binding, basis, protection = bind_accepted(root, work)
        timings["accepted_binding_seconds"] = time.perf_counter() - phase_start
        phase = "B: external RMSD authority"
        authority = json.loads(authority_path.read_text())
        shutil.copyfile(authority_path, work / "human_authority_input.json")
        rmsd = bind_human_review(authority, basis, work)
        hard = read_replica_hard_qc_evidence(
            work / "historical/stage32_qc_evidence.json"
        )
        review = review_input(hard, rmsd, work)
        require(
            write_replica_review_qc_evidence(
                review, work / "authoritative_rmsd_assessment.json"
            ).written,
            "Review write failed",
        )
        require(
            read_replica_review_qc_evidence(work / "authoritative_rmsd_assessment.json")
            == review,
            "Strict review roundtrip differs",
        )
        phase = "C: condition authority"
        hard, science = condition_inputs(hard, authority, work)
        phase = "D: external PBC protocol approval"
        record_pbc_approval(authority, binding, work)
        phase = "E-F-G: accepted Stage 32 workflow and QC-derived manifest"
        phase_start = time.perf_counter()
        require(
            write_replica_hard_qc_evidence(
                hard, work / "stage32_qc_evidence.json"
            ).written,
            "Hard QC input write failed",
        )
        temporal = read_preprocessing_temporal_execution(work / "frozen/temporal.json")
        template = aggregation_template(hard, temporal, science["protein"][1])
        require(
            write_replica_aggregation_manifest(
                template, work / "aggregation_template.json"
            ).written,
            "Technical template write failed",
        )
        control = DatasetQCManifest(
            Path("aggregation_template.json"),
            (
                DatasetQCWorkflowReplica(
                    *REPLICA_KEY,
                    Path("stage32_qc_evidence.json"),
                    Path("authoritative_rmsd_assessment.json"),
                    None,
                ),
            ),
        )
        control_path = work / "dataset_qc_manifest.json"
        require(
            write_dataset_qc_manifest(control, control_path).written,
            "QC control write failed",
        )
        qc = run_dataset_qc(control_path, work / "qc", checksum_mode="sha256")
        dump(work / "stage32_run.json", qc.to_dict())
        decision = qc.outputs.decisions.records[0]
        shutil.copyfile(
            work / "qc/dataset_qc_decision_set.json", work / "stage32_qc_decision.json"
        )
        dump(work / "stage32_qc_findings.json", decision.to_dict())
        summary.update(
            qc_status=decision.qc_status,
            release_decision=decision.release_decision,
            decision_mode=decision.decision_mode,
            production_ready=qc.outputs.production_ready,
            reviewer=authority["reviewer"],
            drift_detected=authority["drift_detected"],
            review_scope=SCOPE,
            condition=hard.identity.condition,
        )
        require_available(qc.outputs)
        derived_path = work / "qc/replica_aggregation_manifest_qc_derived.json"
        manifest = read_replica_aggregation_manifest(derived_path)
        # Rebase a reviewable copy with the accepted writer, preserving input locations.
        require(
            write_replica_aggregation_manifest(
                manifest, work / "stage31_manifest.json"
            ).written,
            "Derived manifest copy failed",
        )
        require(
            read_replica_aggregation_manifest(work / "stage31_manifest.json")
            == manifest,
            "Derived manifest copy changed",
        )
        dump(
            work / "qc_decision_to_stage31_manifest.json",
            dict(
                status="PASS",
                decision=file_record(work / "qc/dataset_qc_decision_set.json"),
                derived_manifest=file_record(derived_path),
                actual_aggregation_manifest=file_record(derived_path),
                copied_manifest=file_record(work / "stage31_manifest.json"),
                release_decision=decision.release_decision,
                production_ready=qc.outputs.production_ready,
                canonical_sources=[
                    file_record(p) for p in manifest.protein_canonical_table_paths
                ],
            ),
        )
        validate_run(
            work / "qc",
            "dataset_qc",
            collect_dataset_qc_input_specs(control, control_path),
            work / "stage32_validation.json",
        )
        timings["stage32_seconds"] = time.perf_counter() - phase_start
        phase = "H: Stage 31 canonical source freeze"
        frozen = [
            dict(**file_record(p), row_count=len(FAMILIES[0].canonical_reader(p).rows))
            for p in manifest.protein_canonical_table_paths
        ]
        dump(
            work / "stage31_source_freeze.json",
            dict(
                status="PASS",
                inputs=frozen,
                after_qc=True,
                science_regenerated=False,
                condition_binding="condition_authority.json",
                historical_source=file_record(work / "frozen/protein_edge.csv"),
                specialized="NOT RUN: explicit partner correspondence is absent",
            ),
        )
        phase = "I: accepted n=1 Stage 31 aggregation"
        phase_start = time.perf_counter()
        result = run_replica_aggregation(
            derived_path, work / "aggregation", checksum_mode="sha256"
        )
        dump(work / "stage31_run.json", result.to_dict())
        timings["stage31_seconds"] = time.perf_counter() - phase_start
        phase = "J: independent n=1 aggregation verification"
        phase_start = time.perf_counter()
        check = independent_protein_check(
            FAMILIES[0].canonical_reader(manifest.protein_canonical_table_paths[0]),
            FAMILIES[0].reader(work / "aggregation" / FAMILIES[0].filename),
            manifest,
        )
        dump(work / "stage31_aggregation_check.json", check)
        require_stage31(check)
        require(
            all(file_record(Path(r["path"]))["sha256"] == r["sha256"] for r in frozen),
            "Frozen canonical source changed after aggregation",
        )
        validate_run(
            work / "aggregation",
            "replica_aggregation",
            collect_replica_aggregation_input_specs(manifest, derived_path),
            work / "stage31_validation.json",
        )
        timings["independent_and_stage31_validation_seconds"] = (
            time.perf_counter() - phase_start
        )
        summary["stage31"] = check
        phase = "K: Stage 33 publication authority"
        # No complete_for_system annotation input occurs in accepted B.3/B.4 controls.
        publication_readiness(check, ())
        raise ValueError(
            "Unexpected publication authority; explicit publication controls required"
        )
    except (ValueError, OSError, KeyError, TypeError) as error:
        summary.update(stop_gate=phase, reason=str(error))
        for name in (
            "qc_decision_to_stage31_manifest",
            "stage31_manifest",
            "stage31_source_freeze",
            "stage31_aggregation_check",
            "stage33_release_check",
            "stage33_f1_source_authority",
            "stage33_f2_metric_authority",
            "cross_table_validation",
            "release_validation",
        ):
            if not (work / f"{name}.json").exists():
                dump(
                    work / f"{name}_NOT_RUN.json",
                    dict(
                        status="NOT RUN",
                        blocker_gate=phase,
                        reason=str(error),
                        complete=False if name == "release_validation" else None,
                    ),
                )
    if "protection" in locals():
        unchanged = all(
            accepted.digest(Path(p)) == sha for p, sha in protection.items()
        )
        dump(
            work / "final_input_protection.json",
            dict(
                protected_files=len(protection),
                all_unchanged=unchanged,
                dcd_stat_unchanged=binding["dcd_stat"]
                == {
                    "size_bytes": Path(binding["source"]["dcd"]["path"]).stat().st_size,
                    "mtime_ns": Path(binding["source"]["dcd"]["path"])
                    .stat()
                    .st_mtime_ns,
                },
            ),
        )
        require(unchanged, "Historical evidence changed")
    timings["downstream_resume_seconds"] = time.perf_counter() - started
    timings.update(stage33_seconds=None, release_validation_seconds=None)
    dump(work / "timings.json", timings)
    summary.update(
        publication_artifact_counts=dict(csv=0, json=0, total=0),
        stage33_status="NOT RUN",
        release_validation_status="NOT RUN",
        release_validation_complete=False,
    )
    dump(work / "stage34b5_resume_summary.json", summary)
    (work / "warnings_limitations.txt").write_text(
        f"{LABEL}. {SCOPE}.\n{summary['stop_gate']}: {summary['reason']}\n"
        "Authoritative complete_for_system biological annotations are required "
        "before publication.\n"
        "Topology-local partners do not establish global partner correspondence.\n"
        "External PBC protocol approval does not validate all Dataset trajectories.\n"
        "Historical scientific_pbc_status remains unresolved; internal MIC=false.\n"
        "No metrics invented. No replicas 2/3, full 100 ns, all-33 or Stage 35 "
        "execution.\n"
    )
    return summary


def package(work):
    records = [
        dict(
            path=p.relative_to(work).as_posix(),
            size_bytes=p.stat().st_size,
            sha256=accepted.digest(p),
        )
        for p in sorted(work.rglob("*"))
        if p.is_file() and p.name != "evidence_inventory.json"
    ]
    dump(work / "evidence_inventory.json", dict(files=records, self_excluded=True))
    archive_path = work.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(work).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None, "Evidence ZIP CRC failure")
    return file_record(archive_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authority-input", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    work = root / (
        "stage34b5_resume_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_")
        + uuid4().hex
    )
    work.mkdir()
    summary = run(root, work, args.authority_input.resolve())
    archive = package(work)
    print(
        json.dumps(dict(summary=summary, evidence=str(work), archive=archive), indent=2)
    )
    return 2  # This reached-path helper does not claim a complete publication.


if __name__ == "__main__":
    sys.exit(main())
