#!/usr/bin/env python3
"""Pinned Stage 34.C.2 downstream pilot; no coordinate or RMSD calculation.

The only new authority is the supplied replica-specific human review. Accepted
Stage 32/31/33 APIs own policy and production execution. The independent side
reconstructs the frozen Stage 31 fields without invoking its aggregation API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import time
import zipfile
from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from pathlib import Path
from uuid import uuid4

from mania.canonical_window_tables_io import write_canonical_protein_edge_window_csv
from mania.dataset_hard_qc import evaluate_replica_hard_qc
from mania.dataset_qc_contract import QCEvidenceRecord, build_dataset_qc_decision_set
from mania.dataset_qc_evidence_io import (
    read_replica_hard_qc_evidence,
    read_replica_review_qc_evidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import DatasetQCManifest, DatasetQCWorkflowReplica
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_qc_run import collect_dataset_qc_input_specs, run_dataset_qc
from mania.dataset_qc_workflow import build_replica_qc_decision
from mania.dataset_release_csv import publication_number, read_publication_csv
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest import (
    DatasetReleaseExportManifest,
    ReleaseAnnotationBinding,
    ReleaseCanonicalBinding,
    ReleaseInputBinding,
    ReleaseUpstreamRun,
)
from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_run import run_dataset_release
from mania.dataset_release_source_authority import (
    validate_publication_metric_sources,
    validate_release_canonical_source_authority,
)
from mania.dataset_release_validation import validate_dataset_release_tables
from mania.dataset_release_workflow import load_release_authority
from mania.dataset_review_qc import (
    ProteinEdgeEmptyWindowEvidence,
    ReplicaMADMetricObservation,
    ReplicaReviewQCEvidence,
    RMSDDriftAssessment,
    evaluate_dataset_review_qc,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
    write_preprocessing_temporal_execution,
)
from mania.replica_aggregation_manifest import ReplicaAggregationManifest
from mania.replica_aggregation_manifest_io import (
    read_replica_aggregation_manifest,
    write_replica_aggregation_manifest,
)
from mania.replica_aggregation_run import (
    collect_replica_aggregation_input_specs,
    run_replica_aggregation,
)
from mania.replica_aggregation_workflow import FAMILIES
from mania.validation.unified import validate_run_artifacts

_spec = importlib.util.spec_from_file_location(
    "accepted_c2_publication",
    Path(__file__).with_name("stage34b5_publication_resume.py"),
)
publication = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publication)
prior = publication.prior
require, dump, file_record, read = (
    prior.require,
    prior.dump,
    prior.file_record,
    publication.read,
)
C1 = "stage34c_r2r3_pilots_20260923T152511Z_f535800b12ae449bb565fe823fbbc0c9"
C1_SHA = "be9f7f18d78fe4f9d0d148b97236daaab76ef4202fce28d6222aaa69cfc5e21e"
B5 = "stage34b5_publication_resume_20260923T131137Z_0e3f6851c19f4cc28f4fa451e425ce4f"
B5_SHA = "d30d6ff6d6e532548dbd64f446cdaaf8a9115abaa91b1a3dd5663ee5c081122c"
REPLICAS = ("1", "2", "3")
ROWS = {"1": 6514, "2": 6533, "3": 6575}
RMSD_VALUES = {
    "2": [
        1.3821246962040505e-14,
        1.2035287581748357,
        1.624146232262041,
        1.842332684695127,
        2.0765174977816443,
    ],
    "3": [
        2.3637072603787704e-14,
        1.3683574628232906,
        1.6386500761007827,
        1.9118922435287553,
        1.9755625384645457,
    ],
}
REVIEWER = "\u0410\u043d\u0434\u0440\u0435\u0439"
SCOPE = (
    "technical five-frame pilot only; "
    "NOT a stability assessment of the full 100-ns trajectory"
)
LABEL = "Stage 34.C real three-replica short pilot publication smoke"
ALLOWED_FILES = (
    "tools/stage34c_three_replica_downstream.py",
    "tests/test_stage34c_three_replica_downstream.py",
    "docs/stage34c_namd_three_replica.md",
)


def identity(replica, condition="PMm"):
    require(replica in REPLICAS, "Only the three accepted real replicas are authorized")
    return prior.accepted.IDENTITY | {
        "trajectory_id": f"egor-2ss-r{replica}-five-frames",
        "replica_id": replica,
        "condition": condition,
    }


def key(replica):
    value = identity(replica)
    return tuple(
        value[n] for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
    )


def checkpoint(repo, work):
    def command(argv):
        return prior.command(repo, work, argv)

    require(command(["git", "branch", "--show-current"]) == "FAIR", "Required FAIR")
    head = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--short"])
    require(
        all(
            line.split(maxsplit=1)[-1] in ALLOWED_FILES for line in status.splitlines()
        ),
        "Unexpected working-tree change",
    )
    command(["git", "rev-parse", "develop"])
    for revision in ("develop", "b52bad0", "1ea6683"):
        command(["git", "merge-base", "--is-ancestor", revision, "HEAD"])
    command(["git", "log", "--oneline", "--decorate", "-32"])
    for name in (
        "tools/stage34c_namd_r2r3_pilots.py",
        "tests/test_stage34c_namd_r2r3_pilots.py",
        "docs/stage34c_namd_three_replica.md",
    ):
        command(["git", "ls-files", "--error-unmatch", name])
        command(["git", "cat-file", "-e", f"HEAD:{name}"])
        if not name.startswith("docs/"):
            require(
                not command(["git", "status", "--porcelain", "--", name]),
                "Stage 34.C.1 code/tests must be committed and unchanged",
            )
    require(not command(["git", "diff", "--cached", "--name-only"]), "Nothing staged")
    dump(work / "git_state.txt", dict(starting_head=head, branch="FAIR", status=status))
    return head


def verified_copy(base, expected, target, select):
    """Check a pinned accepted ZIP and its live evidence; copy only compact inputs."""
    require(
        file_record(base.with_suffix(".zip"))["sha256"] == expected,
        f"Accepted archive binding differs: {base.name}",
    )
    with zipfile.ZipFile(base.with_suffix(".zip")) as archive:
        inventory = (
            json.loads(archive.read("evidence_inventory.json"))
            if "evidence_inventory.json" in archive.namelist()
            else {
                "files": [
                    dict(path=n, sha256=hashlib.sha256(archive.read(n)).hexdigest())
                    for n in archive.namelist()
                ]
            }
        )
        for item in inventory["files"]:
            name = item["path"]
            require(
                not Path(name).is_absolute() and ".." not in Path(name).parts,
                "Unsafe archive entry",
            )
            content = archive.read(name)
            require(
                hashlib.sha256(content).hexdigest()
                == item["sha256"]
                == file_record(base / name)["sha256"],
                f"Accepted artifact changed: {name}",
            )
            if select(name):
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
    return file_record(base.with_suffix(".zip"))


def bind_history(root, work):
    b5, c1 = root / B5, root / C1
    copies = {}
    copies["publication"] = verified_copy(
        b5,
        B5_SHA,
        work / "history/publication",
        lambda n: (
            n.startswith(("biological_annotations_", "contact_authority/"))
            or n == "publication_inputs.json"
        ),
    )
    links = read(b5 / "accepted_evidence_links.json")
    base = Path(links["prior"]["directory"])
    publication.check_frozen_hashes(base)
    copies["r1"] = verified_copy(
        base,
        links["prior"]["archive"]["sha256"],
        work / "history/r1",
        lambda n: (
            n.startswith(("bound/", "frozen/", "historical/"))
            or n
            in (
                "stage32_qc_evidence.json",
                "authoritative_rmsd_assessment.json",
                "rmsd_assessment_binding.json",
                "condition_authority.json",
                "pbc_protocol_approval.json",
                "qc/dataset_qc_decision_set.json",
            )
        ),
    )
    copies["b3"] = verified_copy(
        Path(links["b3"]["directory"]),
        links["b3"]["archive"]["sha256"],
        work / "history/b3",
        lambda n: (
            n
            in (
                "output/edge_semantics.json",
                "output/run_provenance.json",
                "accepted_authority_bindings.json",
                "source_input_observations.json",
            )
        ),
    )
    copies["c1"] = verified_copy(
        c1,
        C1_SHA,
        work / "history/c1",
        lambda n: (
            n.startswith(("replica2/", "replica3/"))
            and not n.endswith("mania_contact_result.json")
            and not n.startswith(("replica2/output/", "replica3/output/"))
            or n
            in tuple(
                f"replica{r}/output/{f}"
                for r in ("2", "3")
                for f in ("edge_semantics.json", "run_provenance.json")
            )
            or n in ("stage34c_r2r3_summary.json", "accepted_r1_binding.json")
        ),
    )
    require(
        read(c1 / "stage34c_r2r3_summary.json")["status"] == "PASS",
        "Stage 34.C.1 is not accepted",
    )
    for replica in ("2", "3"):
        directory = c1 / f"replica{replica}"
        for item in read(directory / "frozen_science.json").values():
            require(
                file_record(Path(item["path"]))["sha256"]
                == item["sha256"]
                == file_record(directory / item["frozen_path"])["sha256"],
                "Frozen scientific input changed",
            )
        prepared = read(directory / "prepared_trajectory_identity.json")
        require(
            file_record(Path(prepared["path"]))["sha256"] == prepared["sha256"],
            "Prepared trajectory hash changed",
        )
    controls = read(work / "history/b3/accepted_authority_bindings.json")
    for role in ("psf", "mapping", "elements"):
        require(
            file_record(Path(controls[role]["path"])) == controls[role],
            f"Shared authority changed: {role}",
        )
    prepared = read(work / "history/r1/frozen/b3_identity.json")
    require(
        file_record(Path(prepared["path"]))["sha256"] == prepared["sha256"],
        "Accepted r1 prepared trajectory changed",
    )
    dump(work / "accepted_artifact_bindings.json", copies)
    return copies


def manual_authority(replica):
    require(replica in RMSD_VALUES, "New manual assessment is only for r2/r3")
    return dict(
        system_identity=identity(replica),
        reviewer=REVIEWER,
        drift_detected=False,
        basis="accepted Stage 34.C.1 five-frame C-alpha RMSD evidence",
        scope=SCOPE,
        pilot_interval_ns=[0.1, 0.5],
        rationale="Curve is comparable in scale and behaviour to the already accepted "
        "replica-1 pilot and no other QC/PBC/scientific failure is present.",
        authority_source=(
            "User-supplied Stage 34.C.2 trajectory-specific manual assessment"
        ),
        recorded_maximum_A=max(RMSD_VALUES[replica]),
    )


def validate_manual(authority, replica):
    require(
        type(authority.get("drift_detected")) is bool
        and authority == manual_authority(replica),
        "Exact replica-specific manual authority required; no automatic RMSD threshold",
    )


def validate_rmsd(replica, method, rows, prepared, psf):
    require(replica in RMSD_VALUES, "Only r2/r3 evidence")
    require(
        method["replica_id"] == method["reference_replica_id"] == replica,
        "RMSD replica identity differs",
    )
    require(
        method["prepared_trajectory"] == prepared and method["psf"] == psf,
        "RMSD prepared trajectory/PSF binding differs",
    )
    require(
        method["selection"] == "protein and name CA"
        and method["n_atoms_used"] == method["n_residues"] == 690
        and method["reference_prepared_frame_index"] == 0
        and method["reference_scientific_time_ns"] == 0.1
        and method["alignment"]
        == "equal-weight Kabsch proper rotation; same CA fit and measurement"
        and method["rmsd_unit"] == "angstrom"
        and method["internal_mic"] is False
        and method["threshold"] is None,
        "RMSD method differs",
    )
    atoms = method["selected_atoms"]
    require(
        len(atoms) == 690
        and len({a["index"] for a in atoms}) == 690
        and {a["resid"] for a in atoms} == set(range(1, 691))
        and all(a["name"] == "CA" and a["segid"] == "PROA" for a in atoms),
        "RMSD atom selection differs",
    )
    require(
        method["rmsd_values_A"] == RMSD_VALUES[replica] and len(rows) == 5,
        "Accepted RMSD values differ",
    )
    for i, row in enumerate(rows):
        require(
            row["replica_id"] == replica
            and int(row["prepared_frame_index"]) == i
            and int(row["source_dcd_frame_index"]) == i
            and float(row["scientific_time_ns"]) == (i + 1) / 10
            and float(row["rmsd_A"]) == RMSD_VALUES[replica][i]
            and method["frames"][i]["frame"] == i
            and method["frames"][i]["time_ps"] == (i + 1) * 100
            and method["source_frame_map"][i]
            == dict(
                prepared_frame_index=i,
                source_dcd_frame_index=i,
                requested_sample_index=i,
                authoritative_time_ps=(i + 1) * 100.0,
            ),
            "RMSD exact five-frame association differs",
        )


def bind_manual(replica, work):
    base = work / f"history/c1/replica{replica}"
    method = read(base / "rmsd_method.json")
    with (base / "rmsd_evidence.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    prepared = read(base / "prepared_trajectory_identity.json")
    authority = read(base / "authority.json")
    validate_rmsd(
        replica,
        method,
        rows,
        {n: prepared[n] for n in ("path", "size_bytes", "sha256")},
        authority["shared"]["psf"],
    )
    supplied = manual_authority(replica)
    validate_manual(supplied, replica)
    artifact = work / f"r{replica}_manual_rmsd_assessment.json"
    dump(
        artifact,
        supplied
        | dict(
            rmsd_recalculated=False,
            automatic_threshold=None,
            method=method["alignment"],
            selection=method["selection"],
            atom_count=690,
            reference_frame=0,
            reference_time_ns=0.1,
            prepared_trajectory=method["prepared_trajectory"],
            scientific_times_ns=[(i + 1) / 10 for i in range(5)],
            rmsd_values_A=method["rmsd_values_A"],
            basis_artifacts={
                n: file_record(base / n)
                for n in ("rmsd_evidence.csv", "rmsd_evidence.png", "rmsd_method.json")
            },
        ),
    )
    evidence = QCEvidenceRecord(
        f"human:rmsd:pilot-r{replica}",
        "artifact",
        "rmsd_assessment_binding",
        artifact.name,
        "window_0001",
        "drift_detected",
        "false",
        None,
        json.dumps(
            supplied | {"binding_sha256": file_record(artifact)["sha256"]},
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    return RMSDDriftAssessment(
        False, "External human assessment of accepted RMSD evidence", (evidence,)
    )


def bind_condition(hard, replica, work):
    require(
        hard.identity.to_dict() == identity(replica, None), "Cross-system hard identity"
    )
    artifacts = []
    for artifact in hard.required_artifacts:
        if artifact.canonical_table is None:
            artifacts.append(artifact)
            continue
        original = artifact.canonical_table
        require(
            artifact.canonical_family == "protein_edge"
            and all(
                r.replica_key == key(replica) and r.condition is None
                for r in original.rows
            ),
            "Unexpected canonical identity/family",
        )
        bound = type(original)(
            tuple(replace(r, condition="PMm") for r in original.rows)
        )
        require(
            type(original)(tuple(replace(r, condition=None) for r in bound.rows))
            == original,
            "Condition projection changed science",
        )
        result = write_canonical_protein_edge_window_csv(
            bound, work / f"bound/r{replica}"
        )
        require(result.written, "Condition projection write failed")
        artifacts.append(
            replace(
                artifact,
                canonical_table=bound,
                evidence=replace(
                    artifact.evidence,
                    artifact_path=result.output_path.relative_to(work).as_posix(),
                    details=(
                        "Explicit user condition PMm; all remaining canonical "
                        "model fields equal."
                    ),
                ),
            )
        )
    return replace(
        hard,
        identity=hard.identity.model_copy(update={"condition": "PMm"}),
        required_artifacts=tuple(artifacts),
    )


def review_input(hard, rmsd, partial):
    def record(value, cls):
        return cls(
            **(
                value
                | {"evidence": tuple(QCEvidenceRecord(**e) for e in value["evidence"])}
            )
        )

    return ReplicaReviewQCEvidence(
        *hard.identity.replica_key,
        hard.identity.engine,
        rmsd,
        record(partial["empty_windows"], ProteinEdgeEmptyWindowEvidence),
        (record(partial["mad_observation"], ReplicaMADMetricObservation),),
    )


def require_three_decisions(decisions, ready=True):
    records = decisions.records
    require(
        ready
        and len(records) == 3
        and {r.replica_key for r in records} == {key(r) for r in REPLICAS}
        and all(
            r.release_decision == "available" and r.qc_status == "pass" for r in records
        ),
        "QC decision gate STOP: exactly three authoritative "
        "available/pass replicas required",
    )


def evaluate_reviews(hards, reviews):
    """Complete real accepted QC before constructing any Stage 31 template."""
    hard_results = tuple(
        evaluate_replica_hard_qc(**{f.name: getattr(h, f.name) for f in fields(h)})
        for h in hards
    )
    review_results = evaluate_dataset_review_qc(hard_results, tuple(reviews))
    by_key = {r.replica_key: r for r in review_results.evaluations}
    decisions = build_dataset_qc_decision_set(
        tuple(
            build_replica_qc_decision(h, by_key[h.replica_key], None)
            for h in hard_results
        )
    )
    return decisions, hard_results, review_results


def pilot_temporal(original, replica):
    require(len(original.bindings) == 1, "One temporal binding required")
    binding = original.bindings[0]
    require(
        binding.dataset_spec.identity.to_dict() == identity(replica, None),
        "Temporal replica identity differs",
    )
    spec = binding.dataset_spec.temporal
    require(
        (spec.production_start_ns, spec.production_end_ns, spec.frame_stride_ps)
        == (0.1, 0.5, 100)
        and binding.sampling_plan.requested_sample_count == 5
        and binding.sampling_plan.sampled_frame_count == 5,
        "Short pilot cannot be represented as full 100-ns release",
    )
    result = replace(
        original,
        bindings=(
            replace(
                binding,
                execution_condition="PMm",
                dataset_spec=binding.dataset_spec.model_copy(
                    update={
                        "identity": binding.dataset_spec.identity.model_copy(
                            update={"condition": "PMm"}
                        )
                    }
                ),
            ),
        ),
    )
    require(
        replace(
            result.bindings[0],
            execution_condition=binding.execution_condition,
            dataset_spec=binding.dataset_spec,
        )
        == binding,
        "Temporal science changed",
    )
    return result


def group_template(hards, temporals, paths, decisions):
    require_three_decisions(decisions)
    require(
        len(hards) == 3
        and {h.identity.replica_key for h in hards} == {key(r) for r in REPLICAS},
        "Duplicate or cross-system replica",
    )
    singles = [
        prior.aggregation_template(h, t, p)
        for h, t, p in zip(hards, temporals, paths, strict=True)
    ]
    first = singles[0].groups[0]
    for item, replica in zip(singles, REPLICAS, strict=True):
        member = item.groups[0].members[0]
        require(
            all(getattr(member, n) == v for n, v in identity(replica).items()),
            "Group identity differs",
        )
        require(
            item.groups[0].spec.window == first.spec.window, "Window contracts differ"
        )
    group = replace(
        first,
        spec=replace(first.spec, expected_replica_ids=REPLICAS),
        members=tuple(t.groups[0].members[0] for t in singles),
    )
    return ReplicaAggregationManifest(tuple(paths), (), (), (group,))


def independent_statistics(vector):
    """Independent Decimal implementation of the accepted occupancy-only fields."""
    with localcontext(Context(prec=50)):
        values = sorted(Decimal(str(x)) for x in vector)
        count = len(values)
        require(count > 0, "An unavailable group has no statistical vector")
        average = sum(values) / count
        center = (values[(count - 1) // 2] + values[count // 2]) / 2
        spread = (
            None
            if count == 1
            else (sum((x - average) ** 2 for x in values) / (count - 1)).sqrt()
        )
        positive = sum(x > 0 for x in values)
        return dict(
            mean_occupancy=float(average),
            median_occupancy=float(center),
            std_occupancy=None if spread is None else float(spread),
            n_replicates_available=count,
            n_replicates_supporting=positive,
            support_fraction=float(Decimal(positive) / count),
        )


def reconstruct(sources, group):
    """Reconstruct every aggregate field and each actual contributor population."""
    members = {m.replica_key: m for m in group.members}
    available = tuple(
        m.replica_key for m in group.members if m.availability_status == "available"
    )
    sparse, evidence = {}, {}
    for table in sources:
        for row in table.rows:
            require(row.replica_key in members, "Unexpected canonical replica")
            member = members[row.replica_key]
            require(
                all(getattr(row, n) == getattr(member, n) for n in identity("1")),
                "Canonical source/member identity differs",
            )
            require(
                all(
                    getattr(row, n) == getattr(group.spec.window, n)
                    for n in (
                        "window_id",
                        "window_index",
                        "requested_window_start_ns",
                        "requested_window_end_ns",
                        "right_endpoint_inclusive",
                    )
                ),
                "Canonical window differs",
            )
            entity = (
                row.source_canonical_residue_number,
                row.target_canonical_residue_number,
                row.edge_type,
            )
            values = sparse.setdefault(entity, {})
            require(row.replica_key not in values, "Duplicate canonical edge/replica")
            values[row.replica_key] = row.occupancy
            evidence[entity] = row
    expected, vectors = {}, []
    for entity, values in sorted(sparse.items()):
        if not any(k in values for k in available):
            continue
        row = evidence[entity]
        vector = [values.get(k, 0) for k in available]
        stats = independent_statistics(vector)
        expected[entity] = {
            **{
                n: getattr(group.spec, n)
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
            "source_canonical_residue_number": entity[0],
            "source_canonical_resname": row.source_canonical_resname,
            "target_canonical_residue_number": entity[1],
            "target_canonical_resname": row.target_canonical_resname,
            "edge_type": entity[2],
            **stats,
        }
        vectors.append(
            dict(
                entity=list(entity),
                available_replica_keys=[list(k) for k in available],
                sparse_presence={
                    m.replica_id: m.replica_key in values for m in group.members
                },
                vector=vector,
                **stats,
            )
        )
    return expected, vectors


def compare_aggregate(expected, observed):
    """Compare the complete schema, exact numerics, identities, counts and nulls."""
    actual = {}
    duplicates = 0
    for row in observed:
        entity = (
            row["source_canonical_residue_number"],
            row["target_canonical_residue_number"],
            row["edge_type"],
        )
        duplicates += entity in actual
        actual[entity] = row
    totals = dict(
        missing_rows=len(expected.keys() - actual.keys()),
        extra_rows=len(actual.keys() - expected.keys()) + duplicates,
        identity_mismatches=0,
        numeric_mismatches=0,
        denominator_availability_mismatches=0,
        null_semantics_mismatches=0,
    )
    numeric = set(independent_statistics([0.2, 0.4, 0.6]))
    differences = []
    for entity in expected.keys() & actual.keys():
        wanted, found = expected[entity], actual[entity]
        for name in wanted.keys() | found.keys():
            if name in wanted and name in found and wanted[name] == found[name]:
                continue
            category = (
                "null_semantics_mismatches"
                if name in wanted
                and name in found
                and (wanted[name] is None or found[name] is None)
                else "denominator_availability_mismatches"
                if name == "n_replicates_available"
                else "numeric_mismatches"
                if name in numeric
                else "identity_mismatches"
            )
            totals[category] += 1
            differences.append(
                dict(
                    entity=list(entity),
                    field=name,
                    expected=wanted.get(name),
                    actual=found.get(name),
                )
            )
    total = sum(totals.values())
    return dict(
        status="PASS" if total == 0 else "FAIL",
        aggregate_mismatches=total,
        **totals,
        aggregate_rows=len(actual),
        differences=differences[:50],
        checked_fields=sorted(next(iter(expected.values()))) if expected else [],
        comparison="exact equality of every emitted Stage 31 field",
        SD="sample standard deviation (n-1); null only for n=1",
        sparse_absence="zero for available replicas only",
        unavailable_excluded="omitted from vector and denominator",
        production_aggregator_called_by_independent_side=False,
    )


def require_verified(check):
    require(
        check.get("status") == "PASS" and check.get("aggregate_mismatches") == 0,
        "Stage 33 cannot run before independent aggregate verification",
    )


def bind_group(hards, work):
    controls = read(work / "history/b3/accepted_authority_bindings.json")
    records = [dict(replica_id="1", producer="NAMD 2.14", seed=2026040842)]
    for replica, seed in (("2", 2026051942), ("3", 2026083042)):
        authority = read(work / f"history/c1/replica{replica}/authority.json")
        require(
            authority["replica_id"] == replica
            and authority["producer"] == "NAMD 3.0.3"
            and authority["seed"] == seed,
            "Producer identity differs",
        )
        for role in ("psf", "mapping", "elements"):
            require(
                authority["shared"][role] == controls[role],
                "Shared construct authority differs",
            )
        records.append(
            dict(replica_id=replica, producer=authority["producer"], seed=seed)
        )
    require(
        [h.identity.to_dict() for h in hards] == [identity(r) for r in REPLICAS],
        "Group identity differs",
    )
    result = dict(
        status="PASS",
        engine="NAMD",
        protein="WT NaPi2b",
        condition="PMm",
        variant_id="WT",
        disulfide_state="2SS",
        replica_ids=list(REPLICAS),
        shared_psf=controls["psf"],
        canonical_mapping=controls["mapping"],
        producers=records,
        producer_version_heterogeneity=True,
        seed_limitation=(
            "Different seeds do not prove complete statistical independence."
        ),
    )
    dump(work / "three_replica_group_identity.json", result)
    return result


def prepare_qc(work):
    hards, reviews, paths, temporals = [], [], [], []
    for replica in REPLICAS:
        if replica == "1":
            base = work / "history/r1"
            hard = read_replica_hard_qc_evidence(base / "stage32_qc_evidence.json")
            review = read_replica_review_qc_evidence(
                base / "authoritative_rmsd_assessment.json"
            )
            path = base / "bound/protein_edges_by_window_canonical.csv"
            temporal_path = base / "frozen/temporal.json"
            require(
                hard.identity.to_dict() == identity(replica),
                "Frozen r1 identity differs",
            )
            old = read(base / "qc/dataset_qc_decision_set.json")
            require(
                len(old["records"]) == 1
                and old["records"][0]["release_decision"] == "available"
                and old["records"][0]["qc_status"] == "pass",
                "Frozen r1 QC differs",
            )
        else:
            base = work / f"history/c1/replica{replica}"
            assessment = bind_manual(replica, work)
            hard = bind_condition(
                read_replica_hard_qc_evidence(base / "stage32_hard_evidence.json"),
                replica,
                work,
            )
            review = review_input(
                hard, assessment, read(base / "stage32_partial_review.json")
            )
            path = work / f"bound/r{replica}/protein_edges_by_window_canonical.csv"
            temporal_path = base / "frozen/temporal_execution.json"
        hards.append(hard)
        reviews.append(review)
        paths.append(path)
        temporals.append(
            pilot_temporal(
                read_preprocessing_temporal_execution(temporal_path), replica
            )
        )
    decisions, hard_results, review_results = evaluate_reviews(hards, reviews)
    dump(work / "stage32_replica_decisions.json", decisions.to_dict())
    dump(
        work / "stage32_findings.json",
        dict(
            hard=[h.to_dict() for h in hard_results],
            review=review_results.to_dict(),
            historical_r1_decision="history/r1/qc/dataset_qc_decision_set.json",
            cohort_note=(
                "Accepted RMSD assessments unchanged; Stage 32 raw MAD "
                "now uses the real three-replica cohort."
            ),
            per_replica=[
                dict(
                    replica_id=d.replica_id,
                    qc_status=d.qc_status,
                    release_decision=d.release_decision,
                    production_ready=d.release_decision == "available",
                    hard_findings=len(h.checks),
                    review_findings=len(rv.checks),
                    unresolved_findings=sum(c.status != "pass" for c in d.findings),
                )
                for d, h, rv in zip(
                    decisions.records,
                    hard_results,
                    review_results.evaluations,
                    strict=True,
                )
            ],
        ),
    )
    require_three_decisions(decisions)
    return hards, reviews, paths, temporals, decisions


def freeze_sources(paths, work):
    records, sources = [], []
    for replica, path in zip(REPLICAS, paths, strict=True):
        table = FAMILIES[0].canonical_reader(path)
        require(
            len(table.rows) == ROWS[replica]
            and all(r.replica_key == key(replica) for r in table.rows),
            "Frozen canonical source identity/row count differs",
        )
        require(
            all(
                r.requested_sample_count == r.resolved_frame_count == 5
                and r.missing_sample_count == 0
                and r.coverage_fraction == 1
                and r.occupancy == r.n_contact_frames / 5
                for r in table.rows
            ),
            "Frozen canonical five-frame science differs",
        )
        original = (
            work / "history/r1/bound/protein_edges_by_window_canonical.csv"
            if replica == "1"
            else work
            / f"history/c1/replica{replica}/frozen"
            / "protein_edges_by_window_canonical.csv"
        )
        original_table = FAMILIES[0].canonical_reader(original)
        require(
            type(table)(tuple(replace(r, condition="PMm") for r in original_table.rows))
            == table,
            "Frozen scientific values changed",
        )
        sources.append(table)
        records.append(
            dict(
                replica_id=replica,
                **file_record(path),
                row_count=len(table.rows),
                scientific_input_identity=identity(replica),
                historical=file_record(original),
                condition_only_projection=replica != "1",
                scientific_model_equal=True,
            )
        )
    dump(work / "stage31_source_freeze.json", dict(status="PASS", sources=records))
    return sources


def run_qc_manifest(hards, reviews, paths, temporals, decisions, work):
    template = group_template(hards, temporals, paths, decisions)
    require(
        write_replica_aggregation_manifest(
            template, work / "aggregation_template.json"
        ).written,
        "QC technical template write failed",
    )
    replicas = []
    for hard, review in zip(hards, reviews, strict=True):
        replica = hard.identity.replica_id
        hp, rp = (
            Path(f"qc_inputs/r{replica}_hard.json"),
            Path(f"qc_inputs/r{replica}_review.json"),
        )
        require(
            write_replica_hard_qc_evidence(hard, work / hp).written,
            "Hard input write failed",
        )
        require(
            write_replica_review_qc_evidence(review, work / rp).written,
            "Review input write failed",
        )
        replicas.append(DatasetQCWorkflowReplica(*key(replica), hp, rp, None))
    control = DatasetQCManifest(Path("aggregation_template.json"), tuple(replicas))
    path = work / "dataset_qc_manifest.json"
    require(write_dataset_qc_manifest(control, path).written, "QC control write failed")
    result = run_dataset_qc(path, work / "qc", checksum_mode="sha256")
    require_three_decisions(result.outputs.decisions, result.outputs.production_ready)
    require(
        result.outputs.decisions == decisions,
        "QC workflow changed the authoritative evaluations",
    )
    dump(work / "stage32_run.json", result.to_dict())
    prior.validate_run(
        work / "qc",
        "dataset_qc",
        collect_dataset_qc_input_specs(control, path),
        work / "stage32_validation.json",
    )
    derived_path = work / "qc/replica_aggregation_manifest_qc_derived.json"
    manifest = read_replica_aggregation_manifest(derived_path)
    require(
        {m.replica_key for m in manifest.groups[0].members}
        == {key(r) for r in REPLICAS}
        and all(
            m.availability_status == "available" for m in manifest.groups[0].members
        ),
        "QC-derived population differs",
    )
    require(
        not manifest.lipid_canonical_table_paths
        and not manifest.glycan_canonical_table_paths
        and not manifest.groups[0].lipid_correspondences.correspondences
        and not manifest.groups[0].glycan_correspondences.correspondences,
        "Specialized correspondence must not be invented",
    )
    require(
        write_replica_aggregation_manifest(
            manifest, work / "qc_derived_stage31_manifest.json"
        ).written,
        "Review copy write failed",
    )
    dump(
        work / "stage32_to_stage31_lineage.json",
        dict(
            decision_set=file_record(work / "qc/dataset_qc_decision_set.json"),
            executed_manifest=file_record(derived_path),
            review_copy=file_record(work / "qc_derived_stage31_manifest.json"),
            entries=[
                dict(
                    replica_key=list(m.replica_key),
                    availability=m.availability_status,
                    decision="available",
                    canonical_source=file_record(p),
                )
                for m, p in zip(manifest.groups[0].members, paths, strict=True)
            ],
            manual_availability_override=False,
        ),
    )
    return control, derived_path, manifest


def publication_control(qc_control, manifest_path, manifest, paths, temporals, work):
    def upstream(directory, specs):
        return ReleaseUpstreamRun(
            f"{directory}/run_provenance.json",
            f"{directory}/artifact_inventory.json",
            tuple(
                ReleaseInputBinding(
                    s.artifact_id, s.local_path.resolve().relative_to(work).as_posix()
                )
                for s in specs
            ),
        )

    bindings = [
        ReleaseCanonicalBinding("protein", p.relative_to(work).as_posix(), (key(r),))
        for r, p in zip(REPLICAS, paths, strict=True)
    ]
    for family in FAMILIES[1:]:
        bindings.append(
            ReleaseCanonicalBinding(
                family.name,
                "history/r1/bound/"
                + family.filename.replace("_replica_aggregation", ""),
                (key("1"),),
            )
        )
    temporal_paths = []
    for replica, temporal in zip(REPLICAS, temporals, strict=True):
        target = work / f"temporal/r{replica}"
        require(
            write_preprocessing_temporal_execution(temporal, target).written,
            "Temporal write failed",
        )
        temporal_paths.append(f"temporal/r{replica}/temporal_execution.json")
    for name in (
        "biological_annotations_authority.json",
        "biological_annotations_provenance.json",
    ):
        shutil.copyfile(work / "history/publication" / name, work / name)
    publication.validate_annotation_authority(
        work / "biological_annotations_authority.json",
        read(work / "biological_annotations_provenance.json"),
    )
    used = manifest_path.relative_to(work).as_posix()
    return DatasetReleaseExportManifest(
        key("1")[0],
        upstream(
            "qc",
            collect_dataset_qc_input_specs(
                qc_control, work / "dataset_qc_manifest.json"
            ),
        ),
        upstream(
            "aggregation",
            collect_replica_aggregation_input_specs(manifest, manifest_path),
        ),
        "qc/dataset_qc_decision_set.json",
        "qc/dataset_qc_summary.csv",
        used,
        used,
        "aggregation/" + FAMILIES[0].filename,
        None,
        None,
        tuple(bindings),
        tuple(temporal_paths),
        (
            ReleaseAnnotationBinding(
                *key("1")[:2], "biological_annotations_authority.json"
            ),
        ),
        "publication_inputs.json",
        tuple(key(r) for r in REPLICAS),
        (key("1")[:2],),
    )


def publication_inputs(work):
    original = read(work / "history/publication/publication_inputs.json")
    require(not original["metrics"], "No additional publication metrics authorized")
    contacts = []
    for replica in REPLICAS:
        for definition in original["contact_definitions"]:
            protein = definition["contact_layer"] == "protein-protein"
            # The accepted protein layer spelling is retained from its definition.
            protein = (
                protein or definition["contact_definition_id"] == "residue_contact"
            )
            if replica != "1" and not protein:
                continue
            source = (
                (
                    "history/b3/output/edge_semantics.json"
                    if replica == "1"
                    else f"history/c1/replica{replica}/output/edge_semantics.json"
                )
                if protein
                else ("history/publication/" + definition["source_artifact_path"])
            )
            if protein and replica != "1":
                require(
                    read(work / source)
                    == read(work / "history/b3/output/edge_semantics.json"),
                    "Contact semantics differ across replicas",
                )
            contacts.append(
                definition
                | {"replica_key": list(key(replica)), "source_artifact_path": source}
            )
    software = []
    for directory in (
        "history/b3/output",
        "history/c1/replica2/output",
        "history/c1/replica3/output",
        "qc",
        "aggregation",
    ):
        provenance = read(work / directory / "run_provenance.json")
        software.append(
            dict(
                dataset_id=key("1")[0],
                run_id=provenance["run_id"],
                component_name="mania-wania",
                component_role="package",
                version="0.1.0",
                source_artifact_role="run_provenance",
                source_artifact_path=f"{directory}/run_provenance.json",
            )
        )
    for replica, version, path in (
        ("1", "2.14", "history/b3/source_input_observations.json"),
        ("2", "3.0.3", "history/c1/replica2/authority.json"),
        ("3", "3.0.3", "history/c1/replica3/authority.json"),
    ):
        software.append(
            dict(
                dataset_id=key(replica)[0],
                run_id=None,
                component_name="NAMD",
                component_role="engine",
                version=version,
                source_artifact_role="accepted_namd_source_evidence",
                source_artifact_path=path,
            )
        )
    dump(
        work / "publication_inputs.json",
        original | {"contact_definitions": contacts, "software_versions": software},
    )
    result = read_dataset_release_publication_inputs(work / "publication_inputs.json")
    require(not result.metrics, "No fake metric")
    return result


def independent_publication(bundle, sources, expected, work):
    root = work / "publication"
    tables = {
        t.table_id: read_publication_csv(t.table_id, root / t.relative_path)
        for t in bundle.tables
    }
    records = {name: table.records() for name, table in tables.items()}
    simulations = records["simulations"]
    require(
        len(simulations) == 3
        and {
            tuple(
                r[n] for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
            )
            for r in simulations
        }
        == {key(r) for r in REPLICAS},
        "Publication simulation population differs",
    )
    require(
        all(
            r["qc_status"] == "pass" and r["release_decision"] == "available"
            for r in simulations
        ),
        "Publication decisions differ",
    )
    systems = records["systems"]
    require(
        len(systems) == 1
        and all(
            systems[0][n] == identity("1")[n]
            for n in ("engine", "variant_id", "condition", "disulfide_state")
        ),
        "Publication group identity differs",
    )
    windows = records["time_windows"]
    require(
        len(windows) == 3
        and {r["replica_id"] for r in windows} == set(REPLICAS)
        and all(
            r["requested_window_start_ns"] == publication_number(0.1)
            and r["requested_window_end_ns"] == publication_number(0.5)
            and r["expected_sample_count"] == r["resolved_sample_count"] == 5
            and r["missing_sample_count"] == 0
            for r in windows
        ),
        "Publication must retain exact short-pilot decimal/window contract",
    )
    for replica, source in zip(REPLICAS, sources, strict=True):
        publication.compare_published_rows(
            source.rows,
            [
                r
                for r in records["protein_edges_by_window"]
                if r["replica_id"] == replica
            ],
        )
    aggregate_table = records["protein_edges_by_window_replica_aggregation"]
    names = set(next(iter(expected.values()))) & set(aggregate_table[0])

    def normalize(row):
        return tuple(
            publication_number(row[n]) if type(row[n]) in (int, float) else row[n]
            for n in sorted(names)
        )

    require(
        len(expected) == len(aggregate_table)
        and sorted(normalize(r) for r in expected.values())
        == sorted(normalize(r) for r in aggregate_table),
        "Published aggregate differs from independent reconstruction",
    )
    specialized = {}
    for family, table_id in (
        (FAMILIES[1], "protein_lipid_contacts_by_window"),
        (FAMILIES[2], "protein_glycan_contacts_by_window"),
    ):
        source = family.canonical_reader(
            work
            / "history/r1/bound"
            / family.filename.replace("_replica_aggregation", "")
        )
        publication.compare_published_rows(source.rows, records[table_id])
        require(
            all(r["replica_id"] == "1" for r in records[table_id]),
            "Unexpected specialized replica",
        )
        require(
            not records[table_id + "_replica_aggregation"],
            "Invented specialized aggregation",
        )
        specialized[family.name] = len(source.rows)
    require(not records["metrics"], "No fake metric")
    annotations = publication.annotation_output_check(tables["residue_annotations"])
    dump(work / "biological_annotation_output_check.json", annotations)
    return dict(
        status="PASS",
        simulations=3,
        decisions="available x3",
        source_rows=ROWS,
        aggregate_rows=len(expected),
        specialized_r1_rows=specialized,
        metrics=0,
        interval_ns=[0.1, 0.5],
        requested_samples_per_replica=5,
        final_dataset_release=False,
        full_100ns_analysis=False,
        decimal_contract="unchanged exact-value publication_number; no rounding",
        table_counts={n: t.row_count for n, t in tables.items()},
        header_only=[n for n, t in tables.items() if t.row_count == 0],
    )


def publish(
    check,
    qc_control,
    manifest_path,
    manifest,
    paths,
    temporals,
    sources,
    expected,
    work,
    timings,
):
    require_verified(check)
    control = publication_control(
        qc_control, manifest_path, manifest, paths, temporals, work
    )
    inputs = publication_inputs(work)
    missing_coverage = [
        dict(family=f.name, replica_id=r)
        for f in FAMILIES
        for r in REPLICAS
        if not any(
            b.family == f.name and key(r) in b.replica_keys
            for b in control.canonical_bindings
        )
    ]
    dump(
        work / "stage33_publication_input_coverage.json",
        dict(
            missing=missing_coverage,
            policy=(
                "Frozen Stage 33 requires all three canonical families "
                "for each selected replica."
            ),
            placeholder_authority_invented=False,
        ),
    )
    path = work / "dataset_release_export_manifest.json"
    require(
        write_dataset_release_export_manifest(control, path).written,
        "Release control write failed",
    )
    authority, _, _ = load_release_authority(control, work)
    canonical = {
        "protein": FAMILIES[0].canonical_table(
            tuple(
                sorted(
                    (r for table in sources for r in table.rows),
                    key=lambda r: r.row_order,
                )
            )
        )
    }
    for family in FAMILIES[1:]:
        canonical[family.name] = family.canonical_reader(
            work
            / next(
                b.path for b in control.canonical_bindings if b.family == family.name
            )
        )
    tick = time.perf_counter()
    try:
        result = run_dataset_release(path, work / "publication", checksum_mode="sha256")
    except ValueError as exc:
        dump(
            work / "stage33_release_check.json",
            dict(
                status="STOP",
                complete=False,
                reason=str(exc),
                missing_canonical_coverage=missing_coverage,
                scientific_contract_changed=False,
                validator_bypass=False,
            ),
        )
        raise
    finally:
        timings["stage33_publication_seconds"] = time.perf_counter() - tick
    dump(work / "stage33_release_check.json", result.to_dict())
    tick = time.perf_counter()
    validate_release_canonical_source_authority(control, manifest, canonical)
    dump(
        work / "stage33_f1_source_authority.json",
        dict(
            status="PASS",
            comparison="complete canonical-model equality",
            source_rows=ROWS,
            sources=read(work / "stage31_source_freeze.json")["sources"],
        ),
    )
    validate_publication_metric_sources(inputs, control, work, result.bundle.metadata)
    dump(
        work / "stage33_f2_metric_authority.json",
        dict(status="PASS", emitted_metrics=0, article_metric_readiness=False),
    )
    validate_dataset_release_tables(
        result.bundle.metadata, result.bundle.science, authority, control
    )
    dump(
        work / "cross_table_validation.json",
        dict(
            status="PASS",
            tables=[t.table_id for t in result.bundle.tables],
            bypasses=False,
        ),
    )
    report = validate_run_artifacts(
        work / "publication",
        scope="dataset_release",
        input_artifact_paths={"input:dataset_release_export_manifest": path},
    )
    dump(work / "release_validation.json", report.to_dict())
    require(
        report.status == "passed" and report.complete, "Release validation incomplete"
    )
    timings["f1_f2_validation_seconds"] = time.perf_counter() - tick
    tick = time.perf_counter()
    inspection = independent_publication(result.bundle, sources, expected, work)
    dump(work / "independent_publication_check.json", inspection)
    timings["independent_publication_seconds"] = time.perf_counter() - tick
    return inspection


def run(root, work):
    start, timings = time.perf_counter(), {}
    summary = dict(
        label=LABEL,
        stage34c1_status="PASS",
        stage34c2_status="STOP",
        stage34c_status="INCOMPLETE",
        stage34_status="IN PROGRESS",
        per_replica_science_rerun=False,
        rmsd_recalculated=False,
        full_100ns_analysis=False,
        stage29_r2_r3=False,
        stage35_run=False,
        final_dataset_release=False,
        interval_ns=[0.1, 0.5],
        internal_mic=False,
    )
    phase = "repository checkpoint"
    try:
        summary["starting_head"] = checkpoint(Path(__file__).resolve().parents[1], work)
        phase = "exact historical binding"
        tick = time.perf_counter()
        bind_history(root, work)
        timings["historical_binding_seconds"] = time.perf_counter() - tick
        phase = "manual review and QC decision gate"
        tick = time.perf_counter()
        hards, reviews, paths, temporals, decisions = prepare_qc(work)
        timings["manual_review_qc_binding_seconds"] = time.perf_counter() - tick
        phase = "group identity, canonical freeze, QC-derived manifest"
        tick = time.perf_counter()
        bind_group(hards, work)
        sources = freeze_sources(paths, work)
        qc_control, manifest_path, manifest = run_qc_manifest(
            hards, reviews, paths, temporals, decisions, work
        )
        timings["group_manifest_seconds"] = time.perf_counter() - tick
        phase = "Stage 31 protein aggregation"
        tick = time.perf_counter()
        aggregation = run_replica_aggregation(
            manifest_path, work / "aggregation", checksum_mode="sha256"
        )
        dump(work / "stage31_run.json", aggregation.to_dict())
        timings["stage31_aggregation_seconds"] = time.perf_counter() - tick
        phase = "independent aggregate gate"
        tick = time.perf_counter()
        expected, vectors = reconstruct(sources, manifest.groups[0])
        aggregate = FAMILIES[0].reader(work / "aggregation" / FAMILIES[0].filename)
        check = compare_aggregate(expected, [r.to_dict() for r in aggregate.rows])
        dump(work / "stage31_aggregate_check.json", check)
        dump(work / "stage31_vectors.json", vectors)
        examples = {}
        for population in (3, 2, 1):
            candidates = [
                v for v in vectors if sum(v["sparse_presence"].values()) == population
            ]
            candidates.sort(key=lambda v: (len(set(v["vector"])) == 1, v["entity"]))
            examples[str(population)] = dict(
                real_case_count=len(candidates),
                example=candidates[0] if candidates else None,
            )
        dump(work / "stage31_real_examples.json", examples)
        require_verified(check)
        summary.update(
            stage31_status="PASS",
            aggregate_rows=len(expected),
            independent_aggregate_mismatches=0,
            stage32_decisions="available x3",
            production_ready=True,
        )
        timings["independent_aggregation_seconds"] = time.perf_counter() - tick
        tick = time.perf_counter()
        prior.validate_run(
            work / "aggregation",
            "replica_aggregation",
            collect_replica_aggregation_input_specs(manifest, manifest_path),
            work / "stage31_validation.json",
        )
        timings["stage31_validation_seconds"] = time.perf_counter() - tick
        phase = "Stage 33 publication, F1, F2, cross-table and release validation"
        inspection = publish(
            check,
            qc_control,
            manifest_path,
            manifest,
            paths,
            temporals,
            sources,
            expected,
            work,
            timings,
        )
        for item in read(work / "stage31_source_freeze.json")["sources"]:
            require(
                file_record(Path(item["path"]))["sha256"] == item["sha256"],
                "Frozen source changed after QC",
            )
        summary.update(
            stage34c2_status="PASS",
            stage34c_status="PASS",
            aggregate_rows=len(expected),
            independent_aggregate_mismatches=0,
            F1="PASS",
            F2="PASS",
            cross_table_validation="PASS",
            release_validation_status="passed",
            release_validation_complete=True,
            publication=inspection,
        )
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        summary.update(stop_gate=phase, reason=str(exc))
    finalize_gate_records(work, summary, timings)
    timings["total_new_downstream_seconds"] = time.perf_counter() - start
    dump(work / "timings.json", timings)
    files = list((work / "publication").rglob("*"))
    summary["publication_artifact_counts"] = dict(
        csv=sum(p.suffix == ".csv" for p in files),
        json=sum(p.suffix == ".json" for p in files),
        total=sum(p.is_file() for p in files),
    )
    dump(work / "stage34c2_summary.json", summary)
    dump(
        work / "article_metric_limitation.json",
        dict(
            emitted_optional_metrics=0,
            article_metric_readiness=False,
            statement=(
                "Publication F2 validates emitted metrics only. An empty "
                "optional metrics table does not establish article-metric "
                "readiness."
            ),
            next_task="Separate article-metric readiness audit",
        ),
    )
    (work / "warnings_limitations.txt").write_text(
        LABEL + "; 0.1-0.5 ns and five samples per replica.\n"
        "Not final Dataset v1.0; no full 100-ns contact analysis or Stage 35.\n"
        "No Stage 29 r2/r3; no cross-replica specialized correspondence.\n"
        "R1 specialized science remains separate; specialized aggregates are absent.\n"
        "External fragment-preserving Variant C remains approved "
        "for these pilots only.\n"
        "Per-trajectory PBC diagnostics are archived; internal MIC=false; "
        "legacy scientific_pbc_status=unresolved.\n"
        "Raw DCD authority retains historical stat/header/config/log bindings, "
        "not full DCD hashes.\n"
        "NAMD 2.14 versus 3.0.3 producer heterogeneity; "
        "different seeds do not prove independence.\n"
        "F2 validates emitted metrics only; empty optional metrics "
        "do not establish article-metric readiness.\n"
        "Requested-time exact Decimal serialization unchanged.\n"
        "Stage 34 remains IN PROGRESS: article metrics, clean-install Stage 34.D, "
        "cluster Stage 34.E, specialized correspondence.\n"
    )
    return summary


def finalize_gate_records(work, summary, timings):
    """Do not allow a stopped pilot to imply a completed release or F1/F2 PASS."""
    for name in (
        "stage33_release_check",
        "stage33_f1_source_authority",
        "stage33_f2_metric_authority",
        "biological_annotation_output_check",
        "cross_table_validation",
        "release_validation",
        "independent_publication_check",
    ):
        if not (work / f"{name}.json").exists():
            dump(
                work / f"{name}.json",
                dict(
                    status="NOT RUN",
                    complete=False,
                    stop_gate=summary.get("stop_gate"),
                    reason=summary.get("reason"),
                ),
            )
    for name in (
        "manual_review_qc_binding_seconds",
        "group_manifest_seconds",
        "stage31_aggregation_seconds",
        "independent_aggregation_seconds",
        "stage33_publication_seconds",
        "f1_f2_validation_seconds",
        "independent_publication_seconds",
    ):
        timings.setdefault(name, None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("local_md"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    work = root / f"stage34c_three_replica_downstream_{stamp}_{uuid4().hex}"
    work.mkdir(parents=True)
    print(work, flush=True)
    summary = run(root, work)
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["stage34c2_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
