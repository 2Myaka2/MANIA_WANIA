#!/usr/bin/env python3
"""Publish the frozen real C.1/C.2/C.3 pilot; never execute upstream science."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import time
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from mania import canonical_window_tables_io as canonical_io
from mania.dataset_release_csv import publication_number, read_publication_csv
from mania.dataset_release_inputs_io import read_dataset_release_publication_inputs
from mania.dataset_release_manifest import ReleaseCanonicalBinding
from mania.dataset_release_manifest_io import (
    read_dataset_release_export_manifest,
    write_dataset_release_export_manifest,
)
from mania.dataset_release_run import run_dataset_release
from mania.dataset_release_source_authority import (
    validate_publication_metric_sources,
    validate_release_canonical_source_authority,
)
from mania.dataset_release_validation import validate_dataset_release_tables
from mania.dataset_release_workflow import load_release_authority
from mania.replica_aggregation_workflow import FAMILIES
from mania.validation.unified import validate_run_artifacts


def helper(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c2 = helper("stage34c_three_replica_downstream")
c3 = helper("stage34c_r2r3_specialized")
publication = c2.publication
require, dump, read, file_record = c2.require, c2.dump, c2.read, c2.file_record
REPLICAS = c2.REPLICAS
C3 = "stage34c_r2r3_specialized_20260923T172052Z_707e6e5f6d6b4426922145487a665bcd"
C3_SHA = "0e4e45808010cc45172a29b57578abed51a24878b1ec7303e78b57d20fb29f5a"
MANIFEST_SHA = "a61d84021593a94973539bb1f318ee09bff0595fef0f4052b7fe73063176e452"
QC_SHA = "ccd98a52349875664a0878f4a245a39ee3412e74077171a6c2483fb8fa313688"
AGGREGATE_SHA = "823f43543e0a8459c1353d5ff0f4244ec2ebef9c1ce707a1dbe8a92bf1b57bff"
SOURCE_HASHES = {
    "protein": {
        "1": "52065cb5134ff5b095ea5ea6c056c4e90e42a3126c2730c3cc007de212dd58d5",
        "2": "828d2f6a795f37e1fada8f6e0986231f03faee5415c2e1e54f7f5083ce047f82",
        "3": "db2fdd9f55f9d9d84e93e6cdffa4b68260be718d4328a91a1e2fef8d495149dc",
    },
    "lipid": {
        "1": "ea7887ed8dc9de6a029fa791c4c713acb7a0bd83acc7889038b4ce6236c4507c",
        "2": "0ba3d178422b57e339d09eef54c821caaf7e1c08c62d42889e37c4beb9ce161f",
        "3": "086e8c4bbf3061581584ecb80a08561e4597251ba54df3d9e2f8435679c77c92",
    },
    "glycan": {
        "1": "7cde63b71bcce0b13df716de4488d4075e7575b5d7eba421cdab6f89a9dfe497",
        "2": "f37832a098afeeb2cc491e2bb3a8f8a93490daf527301dad7ca23589189da4d0",
        "3": "568867b41761d82bb2510ccb38b0da7779c7764d073be653cbfa917b0a6e8ded",
    },
}
ROWS = {
    "protein": c2.ROWS,
    "lipid": dict(zip(REPLICAS, (897, 916, 913), strict=True)),
    "glycan": dict(zip(REPLICAS, (6, 7, 6), strict=True)),
}
TABLES = {
    "protein": "protein_edges_by_window",
    "lipid": "protein_lipid_contacts_by_window",
    "glycan": "protein_glycan_contacts_by_window",
}
ALLOWED_FILES = (
    "tools/stage34c_publication_resume.py",
    "tests/test_stage34c_publication_resume.py",
    "docs/stage34c_namd_three_replica.md",
)
GATES = (
    "frozen_qc_stage31_binding",
    "frozen_specialized_sources",
    "specialized_condition_binding_check",
    "stage33_canonical_coverage_check",
    "stage33_release_check",
    "stage33_f1_source_authority",
    "stage33_f2_metric_authority",
    "protein_aggregate_publication_check",
    "per_replica_science_publication_check",
    "biological_annotation_output_check",
    "qc_publication_check",
    "cross_table_validation",
    "release_validation",
    "independent_publication_check",
)


def checkpoint(repo, work):
    def command(argv):
        return c2.prior.command(repo, work, argv)

    require(command(["git", "branch", "--show-current"]) == "FAIR", "Required FAIR")
    head = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--short"])
    require(
        all(s.split(maxsplit=1)[-1] in ALLOWED_FILES for s in status.splitlines()),
        "Unexpected working-tree change",
    )
    command(["git", "rev-parse", "develop"])
    for revision in ("develop", "b52bad0", "0d2a172", "6a72a90"):
        command(["git", "merge-base", "--is-ancestor", revision, "HEAD"])
    command(["git", "log", "--oneline", "--decorate", "-32"])
    for name in (
        *c2.ALLOWED_FILES[:2],
        *c3.ALLOWED_FILES[:2],
        "tools/stage34c_namd_r2r3_pilots.py",
        "tests/test_stage34c_namd_r2r3_pilots.py",
    ):
        command(["git", "cat-file", "-e", f"HEAD:{name}"])
        require(
            not command(["git", "status", "--porcelain", "--", name]),
            "Accepted tooling changed",
        )
    require(not command(["git", "diff", "--cached", "--name-only"]), "Nothing staged")
    dump(work / "git_state.txt", dict(starting_head=head, branch="FAIR", status=status))
    return head


def pinned(path, expected):
    record = file_record(path)
    require(record["sha256"] == expected, f"Frozen hash differs: {path}")
    return record


def bind_history(root, work):
    """Verify accepted ZIP/live bytes and copy compact authority, never raw MD."""
    records = {}
    records["c2"] = c2.verified_copy(
        root / c3.C2,
        c3.C2_SHA,
        work / "history/c2",
        lambda n: (
            n.startswith(
                ("history/", "qc/", "aggregation/", "qc_inputs/", "bound/", "temporal/")
            )
            or n
            in {
                "dataset_release_export_manifest.json",
                "dataset_qc_manifest.json",
                "aggregation_template.json",
                "publication_inputs.json",
                "biological_annotations_authority.json",
                "biological_annotations_provenance.json",
                "stage31_aggregate_check.json",
                "stage34c2_summary.json",
            }
        ),
    )
    records["c3"] = c2.verified_copy(
        root / C3,
        C3_SHA,
        work / "history/c3",
        lambda n: (
            n
            in {
                "stage34c3_summary.json",
                "frozen_protein_chain.json",
                "stage33_canonical_coverage_readiness.json",
                "r2_canonical_source_freeze.json",
                "r3_canonical_source_freeze.json",
            }
            or (
                n.startswith(("replica2/", "replica3/"))
                and (
                    "/output/" in n
                    or Path(n).name
                    in {
                        "summary.json",
                        "technical_validation.json",
                        "prepared_binding.json",
                        "canonical_specialised_check.json",
                        "molecular_partner_catalog.json",
                        "temporal_execution.json",
                        "glycan_anchor_metadata.json",
                    }
                )
            )
        ),
    )
    summary = read(work / "history/c3/stage34c3_summary.json")
    require(summary["status"] == "PASS", "C.3 not accepted")
    require(
        {r["replica_id"] for r in summary["replicas"]} == {"2", "3"},
        "C.3 replica population differs",
    )
    for replica in summary["replicas"]:
        require(
            replica["independent"]["status"] == "PASS"
            and replica["technical"]["status"] == "passed"
            and replica["technical"]["complete"] is True
            and replica["technical"]["unsupported_count"] == 0
            and all(
                v["scientific_value_mismatches"] == 0
                for v in replica["canonical"].values()
            ),
            "C.3 independent/technical/scientific gates differ",
        )
    dump(work / "accepted_archive_bindings.json", records)
    return summary


def no_specialized_aggregation(control, used):
    require(
        control.lipid_aggregate_path is None
        and control.glycan_aggregate_path is None
        and not used.lipid_canonical_table_paths
        and not used.glycan_canonical_table_paths
        and all(
            not getattr(g, f"{f}_correspondences").correspondences
            for g in used.groups
            for f in ("lipid", "glycan")
        ),
        "Specialized aggregation/correspondence is unauthorized",
    )


def bind_frozen_chain(work):
    base = work / "history/c2"
    control = read_dataset_release_export_manifest(
        base / "dataset_release_export_manifest.json"
    )
    frozen = {
        "manifest": pinned(base / control.qc_derived_manifest_path, MANIFEST_SHA),
        "decisions": pinned(base / control.decision_set_path, QC_SHA),
        "aggregate": pinned(base / control.protein_aggregate_path, AGGREGATE_SHA),
    }
    authority, _, aggregates = load_release_authority(control, base)
    c2.require_three_decisions(authority.decisions)
    used = authority.aggregation_manifest_used
    no_specialized_aggregation(control, used)
    require(
        len(used.groups) == 1 and used.groups[0].spec.expected_replica_ids == REPLICAS,
        "Expected exactly the three accepted replicas",
    )
    group = used.groups[0]
    require(
        all(
            getattr(group.spec, n) == c2.identity("1")[n]
            for n in (
                "dataset_id",
                "system_id",
                "engine",
                "variant_id",
                "condition",
                "disulfide_state",
            )
        ),
        "Group identity differs",
    )
    require(len(aggregates["protein"].rows) == 7168, "Aggregate row count differs")
    require(
        read(base / "qc/run_provenance.json")["resolved_configuration"][
            "production_ready"
        ]
        is True,
        "Frozen QC is not production ready",
    )
    sources = {}
    paths = {}
    for binding in control.canonical_bindings:
        if binding.family != "protein":
            continue
        replica = binding.replica_keys[0][-1]
        path = base / binding.path
        pinned(path, SOURCE_HASHES["protein"][replica])
        table = FAMILIES[0].canonical_reader(path)
        check_source(table, "protein", replica)
        paths[replica], sources[replica] = path, table
    require(
        {p.resolve() for p in used.protein_canonical_table_paths}
        == {p.resolve() for p in paths.values()},
        "Protein Stage 31 source substitution",
    )
    frozen["protein_sources"] = {r: file_record(p) for r, p in paths.items()}
    dump(
        work / "frozen_qc_stage31_binding.json",
        dict(
            status="PASS",
            **frozen,
            replicas=list(REPLICAS),
            qc_status="pass",
            release_decision="available",
            production_ready=True,
            stage32_recomputed=False,
            stage31_recomputed=False,
            aggregate_rows=7168,
        ),
    )
    return control, sources, paths, aggregates["protein"]


def check_source(table, family, replica):
    require(
        len(table.rows) == ROWS[family][replica] and len(table.rows) > 0,
        "Frozen row population differs or fake empty source",
    )
    wanted = c2.identity(replica)
    require(
        all(
            all(getattr(r, n) == v for n, v in wanted.items() if n != "condition")
            and r.condition in (None, "PMm")
            for r in table.rows
        ),
        "Frozen source identity differs",
    )
    require(
        all(
            r.requested_sample_count == r.resolved_frame_count == 5
            and r.missing_sample_count == 0
            and r.coverage_fraction == 1
            and r.requested_window_start_ns == 0.1
            and r.requested_window_end_ns == 0.5
            for r in table.rows
        ),
        "Only the five-sample pilot is authorized",
    )


def compare_condition_models(original, bound):
    expected = type(original)(tuple(replace(r, condition="PMm") for r in original.rows))
    require(bound == expected, "Metadata binding changed non-condition model fields")
    return dict(
        status="PASS",
        rows=len(original.rows),
        changed_fields=["condition"]
        if any(r.condition != "PMm" for r in original.rows)
        else [],
        row_population_equal=True,
        partner_identity_equal=True,
        window_identity_equal=True,
        all_scientific_fields_equal=True,
        complete_model_mismatches=0,
    )


def bind_specialized(work, old_control, c3_summary):
    sources, paths, records, checks = {}, {}, {}, {}
    history = read(work / "history/c3/frozen_protein_chain.json")
    for family in FAMILIES[1:]:
        sources[family.name], paths[family.name] = {}, {}
        for replica in REPLICAS:
            if replica == "1":
                binding = next(
                    b for b in old_control.canonical_bindings if b.family == family.name
                )
                path = work / "history/c2" / binding.path
                # C.3 explicitly froze this accepted history path and digest.
                record = next(
                    r for r in history if r["path"].endswith("/" + binding.path)
                )
            else:
                result = next(
                    r for r in c3_summary["replicas"] if r["replica_id"] == replica
                )
                record = result["freeze"][family.name]
                path = (
                    work
                    / f"history/c3/replica{replica}/output"
                    / Path(record["path"]).name
                )
            require(
                record["sha256"] == SOURCE_HASHES[family.name][replica],
                "Accepted C.3 freeze differs",
            )
            original_record = pinned(path, record["sha256"])
            original = family.canonical_reader(path)
            check_source(original, family.name, replica)
            candidate = type(original)(
                tuple(replace(r, condition="PMm") for r in original.rows)
            )
            check = compare_condition_models(original, candidate)
            writer = getattr(
                canonical_io, f"write_canonical_protein_{family.name}_window_csv"
            )
            written = writer(candidate, work / f"publication_bound/r{replica}")
            require(written.written, "Specialized publication copy write failed")
            bound = family.canonical_reader(written.output_path)
            compare_condition_models(original, bound)
            sources[family.name][replica] = original
            paths[family.name][replica] = written.output_path
            name = f"{family.name}_r{replica}"
            records[name] = dict(
                source=original_record,
                rows=len(original.rows),
                bound=file_record(written.output_path),
                accepted_c3_freeze=record,
            )
            checks[name] = check
    dump(work / "frozen_specialized_sources.json", dict(status="PASS", sources=records))
    dump(
        work / "specialized_condition_binding_check.json",
        dict(status="PASS", sources=checks),
    )
    return sources, paths


def relocate_control(control, paths, work):
    prefix = "history/c2/"

    def upstream(binding):
        return replace(
            binding,
            provenance_path=prefix + binding.provenance_path,
            inventory_path=prefix + binding.inventory_path,
            input_bindings=tuple(
                replace(b, path=prefix + b.path) for b in binding.input_bindings
            ),
        )

    bindings = [
        replace(b, path=prefix + b.path)
        for b in control.canonical_bindings
        if b.family == "protein"
    ]
    bindings.extend(
        ReleaseCanonicalBinding(f, p.relative_to(work).as_posix(), (c2.key(r),))
        for f, replicas in paths.items()
        for r, p in replicas.items()
    )
    return replace(
        control,
        stage32_run=upstream(control.stage32_run),
        stage31_run=upstream(control.stage31_run),
        canonical_bindings=tuple(bindings),
        annotation_bindings=tuple(
            replace(b, path=prefix + b.path) for b in control.annotation_bindings
        ),
        temporal_evidence_paths=tuple(
            prefix + p for p in control.temporal_evidence_paths
        ),
        **{
            name: prefix + getattr(control, name)
            for name in (
                "decision_set_path",
                "qc_summary_path",
                "qc_derived_manifest_path",
                "aggregation_manifest_used_path",
                "protein_aggregate_path",
            )
        },
    )


def prepare_publication_inputs(work):
    data = read(work / "history/c2/publication_inputs.json")
    require(not data["metrics"], "No optional metrics authorized")
    original = copy.deepcopy(data["contact_definitions"])
    for replica in ("2", "3"):
        data["contact_definitions"].extend(
            copy.deepcopy(d) | {"replica_key": list(c2.key(replica))}
            for d in original
            if d["contact_layer"] != "protein-protein"
        )
    for definition in data["contact_definitions"]:
        definition["source_artifact_path"] = (
            "history/c2/" + definition["source_artifact_path"]
        )
        replica = definition["replica_key"][-1]
        pbc = definition["parameters"]["pbc_correction_status"]
        # Metadata references identify each trajectory's already frozen evidence.
        pbc.update(
            protocol_authority="history/c2/history/r1/pbc_protocol_approval.json",
            trajectory_preparation_and_diagnostics=(
                "history/c2/history/r1/frozen/b3_pbc.json"
                if replica == "1"
                else (
                    f"history/c2/history/c1/replica{replica}/persisted_pbc_validation.json"
                )
            ),
        )
        specific = definition["parameters"].get("type_specific_parameters", {})
        if "partner_catalog" in specific:
            specific["partner_catalog"] = (
                "history/c2/history/r1/frozen/partner_catalog.json"
                if replica == "1"
                else f"history/c3/replica{replica}/molecular_partner_catalog.json"
            )
        require(pbc["internal_mic"] is False, "Internal MIC changed")
        for name in ("protocol_authority", "trajectory_preparation_and_diagnostics"):
            require((work / pbc[name]).is_file(), "Missing trajectory PBC evidence")
    for software in data["software_versions"]:
        software["source_artifact_path"] = (
            "history/c2/" + software["source_artifact_path"]
        )
    dump(work / "publication_inputs.json", data)
    return read_dataset_release_publication_inputs(work / "publication_inputs.json")


def validate_f1(control, authority, canonical, specialized_sources, work):
    validate_release_canonical_source_authority(
        control, authority.aggregation_manifest_used, canonical
    )
    for family in FAMILIES[1:]:
        expected_rows = []
        for replica in REPLICAS:
            binding = next(
                b
                for b in control.canonical_bindings
                if b.family == family.name and b.replica_keys == (c2.key(replica),)
            )
            table = family.canonical_reader(work / binding.path)
            compare_condition_models(specialized_sources[family.name][replica], table)
            expected_rows.extend(table.rows)
        expected = family.canonical_table(
            tuple(sorted(expected_rows, key=lambda r: r.row_order))
        )
        require(
            canonical[family.name] == expected, "F1 specialized source substitution"
        )
    return dict(
        status="PASS",
        families=list(TABLES),
        comparison="complete strict model equality",
        protein_authority="exact three inputs used by accepted Stage 31",
        specialized_authority="frozen C.3 models with condition-only PMm binding",
        model_mismatches=0,
        row_counts=ROWS,
    )


def compare_emitted_fields(source, table):
    """Independent keyed equality of EVERY emitted column, no scientific calculation."""

    def number(value):
        return publication_number(value) if type(value) in (int, float) else value

    names = tuple(c.name for c in table.spec.columns)
    expected = []
    for row in source.rows:
        expected.append(
            {
                n: number(
                    source.canonical_reference_id
                    if n == "canonical_reference_id"
                    else getattr(row, n)
                )
                for n in names
            }
        )

    def index(rows):
        result = {}
        duplicates = 0
        for row in rows:
            key = tuple(row[n] for n in table.spec.primary_key)
            duplicates += key in result
            result[key] = row
        return result, duplicates

    wanted, duplicate_source = index(expected)
    actual, duplicates = index(table.records())
    require(not duplicate_source, "Duplicate authoritative identity")
    totals = dict(
        missing_rows=len(wanted.keys() - actual.keys()),
        extra_rows=len(actual.keys() - wanted.keys()) + duplicates,
        identity_mismatches=0,
        numeric_mismatches=0,
        denominator_availability_mismatches=0,
        null_semantics_mismatches=0,
    )
    differences = []
    for key in wanted.keys() & actual.keys():
        for name in names:
            a, b = wanted[key][name], actual[key][name]
            if a == b:
                continue
            category = (
                "null_semantics_mismatches"
                if a is None or b is None
                else "denominator_availability_mismatches"
                if name
                in {
                    "n_replicates_available",
                    "n_replicates_supporting",
                    "support_fraction",
                    "requested_sample_count",
                    "resolved_frame_count",
                    "missing_sample_count",
                    "coverage_fraction",
                }
                else "numeric_mismatches"
                if isinstance(a, (int, float, Decimal)) and not isinstance(a, bool)
                else "identity_mismatches"
            )
            totals[category] += 1
            if len(differences) < 20:
                differences.append(dict(field=name, expected=str(a), actual=str(b)))
    total = sum(totals.values())
    return dict(
        status="PASS" if total == 0 else "FAIL",
        **totals,
        total_mismatches=total,
        source_rows=len(expected),
        published_rows=table.row_count,
        checked_fields=list(names),
        differences=differences,
        comparison="exact accepted Decimal serialization of every emitted source field",
    )


def inspect_identity(records):
    simulations = records["simulations"]
    require(
        len(simulations) == 3
        and {
            tuple(
                r[n] for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
            )
            for r in simulations
        }
        == {c2.key(r) for r in REPLICAS},
        "Publication must have exactly three accepted simulations",
    )
    systems = records["systems"]
    require(
        len(systems) == 1
        and all(
            systems[0][n] == c2.identity("1")[n]
            for n in (
                "dataset_id",
                "system_id",
                "engine",
                "condition",
                "variant_id",
                "disulfide_state",
            )
        ),
        "Published system differs",
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
        "Only the exact five-sample 0.1-0.5 ns pilot is authorized",
    )
    require(not records["metrics"], "No additional metrics authorized")
    for family in ("lipid", "glycan"):
        require(
            not records[TABLES[family] + "_replica_aggregation"],
            "Specialized aggregate must be truthful header-only",
        )


def inspect_qc(records, authority, work):
    checks = {}
    for decision in authority.decisions.records:
        replica = decision.replica_id
        qc = next(r for r in records["quality_control"] if r["replica_id"] == replica)
        simulation = next(
            r for r in records["simulations"] if r["replica_id"] == replica
        )
        for name in ("qc_status", "release_decision", "decision_mode"):
            require(
                qc[name] == simulation[name] == getattr(decision, name),
                "Published QC decision changed",
            )
        require(
            qc["reviewer"] == decision.reviewer
            and qc["decision_note"] == decision.decision_note,
            "QC decision provenance changed",
        )
        expected = []
        for finding in decision.findings:
            for evidence in finding.evidence:
                expected.append(
                    evidence.to_dict()
                    | dict(
                        dataset_id=decision.dataset_id,
                        system_id=decision.system_id,
                        trajectory_id=decision.trajectory_id,
                        replica_id=replica,
                        check_id=finding.check_id,
                        used_for_decision=evidence.evidence_id
                        in decision.decision_evidence_ids,
                    )
                )
        published = [
            r for r in records["quality_control_evidence"] if r["replica_id"] == replica
        ]
        require(
            sorted(expected, key=lambda r: (r["check_id"], r["evidence_id"]))
            == sorted(published, key=lambda r: (r["check_id"], r["evidence_id"])),
            "Replica-specific QC evidence changed",
        )
        review = read(work / f"history/c2/qc_inputs/r{replica}_review.json")[
            "rmsd_drift"
        ]
        human = next(
            e
            for e in review["evidence"]
            if e["evidence_id"] == f"human:rmsd:pilot-r{replica}"
        )
        retained = retained_manual_evidence(human, published)
        detail = json.loads(human["details"])
        checks[replica] = dict(
            qc_status=qc["qc_status"],
            release_decision=qc["release_decision"],
            production_ready=True,
            reviewer=detail["reviewer"],
            published_evidence_rows=len(published),
            evidence_mismatches=0,
            manual_assessment_preserved=True,
            review_input_evidence_id=human["evidence_id"],
            accepted_decision_evidence_id=retained["evidence_id"],
        )
    return dict(
        status="PASS",
        replicas=checks,
        group_reviewer_created=False,
        note="Automatic policy decisions retain separate manual RMSD evidence",
    )


def retained_manual_evidence(human, published):
    """Stage 32 assigns finding-local IDs; every supplied evidence field survives.

    The caller separately compares all publication evidence, including IDs,
    exactly against the frozen authoritative decision set.
    """
    matches = [
        row
        for row in published
        if row["check_id"] == "rmsd_drift"
        and all(
            row[name] == value for name, value in human.items() if name != "evidence_id"
        )
    ]
    require(len(matches) == 1, "Manual reviewer evidence was not preserved")
    return matches[0]


def require_complete(report):
    require(
        report.status == "passed"
        and report.complete is True
        and report.unsupported_count == 0,
        "Complete release validation required",
    )


def independent_inspection(bundle, source_paths, aggregate, authority, work):
    tables = {
        t.table_id: read_publication_csv(
            t.table_id, work / "publication" / t.relative_path
        )
        for t in bundle.tables
    }
    records = {n: t.records() for n, t in tables.items()}
    inspect_identity(records)
    checks = {}
    for family in FAMILIES:
        table_id = TABLES[family.name]
        combined = []
        for replica in REPLICAS:
            source = family.canonical_reader(source_paths[family.name][replica])
            check_source(source, family.name, replica)
            combined.extend(source.rows)
        source = family.canonical_table(
            tuple(sorted(combined, key=lambda r: r.row_order))
        )
        checks[family.name] = compare_emitted_fields(source, tables[table_id])
        checks[family.name]["per_replica_rows"] = {
            r: sum(row["replica_id"] == r for row in records[table_id])
            for r in REPLICAS
        }
    dump(
        work / "per_replica_science_publication_check.json",
        dict(
            status="PASS"
            if all(c["status"] == "PASS" for c in checks.values())
            else "FAIL",
            families=checks,
            total_mismatches=sum(c["total_mismatches"] for c in checks.values()),
        ),
    )
    require(
        all(c["status"] == "PASS" for c in checks.values()),
        "Per-replica science differs",
    )
    check = compare_emitted_fields(
        aggregate, tables[TABLES["protein"] + "_replica_aggregation"]
    )
    dump(work / "protein_aggregate_publication_check.json", check)
    require(
        check["status"] == "PASS" and check["published_rows"] == 7168,
        "Published protein aggregate differs",
    )
    annotations = publication.annotation_output_check(tables["residue_annotations"])
    reference = {
        r["canonical_residue_number"]: r["canonical_resname"] for r in records["nodes"]
    }
    require(
        all(reference[n] == "ASN" for n in (295, 308))
        and all(reference[n] == "CYS" for n in (303, 322, 328, 350)),
        "Biological site residue identity differs",
    )
    dump(work / "biological_annotation_output_check.json", annotations)
    dump(work / "qc_publication_check.json", inspect_qc(records, authority, work))
    return dict(
        status="PASS",
        simulations=3,
        replica_ids=list(REPLICAS),
        source_rows=ROWS,
        aggregate_rows=7168,
        metrics=0,
        table_counts={n: t.row_count for n, t in tables.items()},
        header_only=[n for n, t in tables.items() if t.row_count == 0],
        final_dataset_release=False,
        full_100ns_analysis=False,
        interval_ns=[0.1, 0.5],
        samples_per_replica=5,
        decimal_contract="unchanged exact-value Decimal; no rounding",
    )


def run(root, work):
    started = time.perf_counter()
    timings = {}
    summary = dict(
        stage34c4_status="STOP",
        stage34c_status="INCOMPLETE",
        stage34_status="IN PROGRESS",
        label=c2.LABEL,
        final_dataset_release=False,
        full_100ns_analysis=False,
        interval_ns=[0.1, 0.5],
        replicas=list(REPLICAS),
        samples_per_replica=5,
        per_replica_science_rerun=False,
        stage32_recomputed=False,
        stage31_recomputed=False,
        rmsd_recalculated=False,
        specialized_aggregation_run=False,
        internal_mic=False,
        stage35_run=False,
    )
    phase = "repository checkpoint"
    try:
        summary["starting_head"] = checkpoint(Path(__file__).resolve().parents[1], work)
        phase = "frozen archive/source bindings"
        historical = bind_history(root, work)
        old, protein, protein_paths, aggregate = bind_frozen_chain(work)
        specialized, specialized_paths = bind_specialized(work, old, historical)
        control = relocate_control(old, specialized_paths, work)
        authority, _, _ = load_release_authority(control, work)
        no_specialized_aggregation(control, authority.aggregation_manifest_used)
        publication.validate_annotation_authority(
            work / "history/c2/biological_annotations_authority.json",
            read(work / "history/c2/biological_annotations_provenance.json"),
        )
        inputs = prepare_publication_inputs(work)
        path = work / "dataset_release_export_manifest.json"
        require(
            write_dataset_release_export_manifest(control, path).written,
            "Release control write failed",
        )
        all_paths = specialized_paths | {"protein": protein_paths}
        freezes = {
            b.path: dict(
                file_record(work / b.path), rows=ROWS[b.family][b.replica_keys[0][-1]]
            )
            for b in control.canonical_bindings
        }
        phase = "frozen Stage 33 canonical coverage"
        candidates = {d.replica_key for d in authority.decisions.records}
        coverage = c3.coverage_readiness(control, work, candidates, freezes)
        dump(work / "stage33_canonical_coverage_check.json", coverage)
        require(coverage["status"] == "PASS", "Required canonical coverage failed")
        canonical = c3.frozen_coverage_gate(control, work, candidates)
        validate_f1(control, authority, canonical, specialized, work)
        timings["binding_seconds"] = time.perf_counter() - started
        phase = "Stage 33 publication"
        print(
            "Frozen QC, sources, aggregate, annotations and nine-family coverage PASS",
            flush=True,
        )
        tick = time.perf_counter()
        result = run_dataset_release(path, work / "publication", checksum_mode="sha256")
        timings["stage33_publication_seconds"] = time.perf_counter() - tick
        dump(work / "stage33_release_check.json", result.to_dict())
        phase = "F1/F2 and full cross-table validation"
        dump(
            work / "stage33_f1_source_authority.json",
            validate_f1(control, authority, canonical, specialized, work),
        )
        validate_publication_metric_sources(
            inputs, control, work, result.bundle.metadata
        )
        dump(
            work / "stage33_f2_metric_authority.json",
            dict(
                status="PASS",
                emitted_metrics=0,
                article_metric_readiness=False,
                scope="PASS for emitted metrics; no centrality publication claim",
            ),
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
        phase = "complete release validation"
        tick = time.perf_counter()
        report = validate_run_artifacts(
            work / "publication",
            scope="dataset_release",
            input_artifact_paths={"input:dataset_release_export_manifest": path},
        )
        dump(work / "release_validation.json", report.to_dict())
        require_complete(report)
        timings["release_validation_seconds"] = time.perf_counter() - tick
        phase = "independent persisted-publication inspection"
        tick = time.perf_counter()
        inspection = independent_inspection(
            result.bundle, all_paths, aggregate, authority, work
        )
        dump(work / "independent_publication_check.json", inspection)
        timings["independent_inspection_seconds"] = time.perf_counter() - tick
        # Check the authoritative live originals again after downstream execution.
        for family, sources in all_paths.items():
            for replica, source in sources.items():
                if family == "protein":
                    pinned(
                        root / c3.C2 / source.relative_to(work / "history/c2"),
                        SOURCE_HASHES[family][replica],
                    )
        for record in read(work / "frozen_specialized_sources.json")[
            "sources"
        ].values():
            original = Path(record["source"]["path"])
            relative = original.relative_to(work / "history")
            original_root = root / (c3.C2 if relative.parts[0] == "c2" else C3)
            pinned(
                original_root.joinpath(*relative.parts[1:]), record["source"]["sha256"]
            )
        pinned(root / c3.C2 / old.qc_derived_manifest_path, MANIFEST_SHA)
        pinned(root / c3.C2 / old.decision_set_path, QC_SHA)
        pinned(root / c3.C2 / old.protein_aggregate_path, AGGREGATE_SHA)
        summary.update(
            stage34c1_status="PASS",
            stage34c2_protein_qc_aggregation="PASS",
            stage34c3_status="PASS",
            stage34c4_status="PASS",
            stage34c_status="PASS",
            F1="PASS",
            F2="PASS",
            cross_table_validation="PASS",
            release_validation_status=report.status,
            release_validation_complete=report.complete,
            independent_publication_check="PASS",
            row_counts=inspection["table_counts"],
            header_only=inspection["header_only"],
        )
    except Exception as exc:
        summary.update(stop_gate=phase, reason=str(exc))
        (work / "failure_traceback.txt").write_text(traceback.format_exc())
        print(f"STOP at {phase}: {exc}", flush=True)
    files = [p for p in (work / "publication").rglob("*") if p.is_file()]
    summary["publication_artifact_counts"] = dict(
        csv=sum(p.suffix == ".csv" for p in files),
        json=sum(p.suffix == ".json" for p in files),
        total=len(files),
    )
    for name in GATES:
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
    dump(
        work / "article_metric_limitation.json",
        dict(
            emitted_metric_count=0,
            article_metric_readiness=False,
            reason="No separately authorized metrics; centrality remains unresolved",
        ),
    )
    timings["total_seconds"] = time.perf_counter() - started
    dump(work / "timings.json", timings)
    dump(work / "stage34c4_summary.json", summary)
    (work / "warnings_limitations.txt").write_text(
        "Real NAMD WT / 2SS / PMm replicas 1,2,3; 0.1-0.5 ns, five samples each.\n"
        "Short publication smoke, not final Dataset v1.0 or full 100-ns science.\n"
        "release_version denotes the unchanged schema, not Dataset completion.\n"
        "No specialized aggregation: authoritative partner correspondence absent.\n"
        "No optional metrics: article-metric readiness remains unresolved.\n"
        "Approved external fragment-preserving PBC; trajectory diagnostics preserved.\n"
        "Internal MIC=false; legacy scientific_pbc_status=unresolved unchanged.\n"
        "Exact requested-time Decimal serialization unchanged.\n"
        "Stage 34 remains IN PROGRESS; Stage 35 not started.\n"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("local_md"))
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    work = (
        args.workspace
        or root
        / (
            "stage34c_publication_resume_"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_")
            + uuid4().hex
        )
    ).resolve()
    require(
        work.is_relative_to(root)
        and subprocess.run(["git", "check-ignore", "-q", str(work)]).returncode == 0,
        "Workspace must be ignored",
    )
    work.mkdir(exist_ok=False)
    print(f"Evidence workspace: {work}", flush=True)
    summary = run(root, work)
    print(f"Stage 34.C.4: {summary['stage34c4_status']}", flush=True)
    return 0 if summary["stage34c4_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
