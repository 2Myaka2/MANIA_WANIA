#!/usr/bin/env python3
"""Publish the frozen five-frame B.5 chain with explicit annotation authority.

No upstream execution, trajectory reading, scientific inference or schema changes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mania.biological_annotations_io import (
    read_dataset_system_biological_annotations,
)
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.dataset_qc_manifest_io import read_dataset_qc_manifest
from mania.dataset_qc_run import collect_dataset_qc_input_specs
from mania.dataset_release_contact_definition_authority import (
    build_dataset_release_contact_definitions,
    materialize_contact_definition_authority,
)
from mania.dataset_release_csv import publication_number, read_publication_csv
from mania.dataset_release_inputs_io import (
    PUBLICATION_INPUT_KIND,
    PUBLICATION_INPUT_SCHEMA_VERSION,
    read_dataset_release_publication_inputs,
)
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
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
    write_preprocessing_temporal_execution,
)
from mania.replica_aggregation_manifest_io import read_replica_aggregation_manifest
from mania.replica_aggregation_run import collect_replica_aggregation_input_specs
from mania.replica_aggregation_workflow import FAMILIES
from mania.validation.unified import validate_run_artifacts

_spec = importlib.util.spec_from_file_location(
    "accepted_b5_resume",
    Path(__file__).with_name("stage34b5_resume_downstream_smoke.py"),
)
prior = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prior)
require, dump, file_record = prior.require, prior.dump, prior.file_record
KEY = prior.REPLICA_KEY
IDENTITY = prior.accepted.IDENTITY | {"condition": "PMm"}
LABEL = "Stage 34.B.5 single-replica short publication smoke"
SITES = {
    "glycosylation_sites": [295, 308],
    "disulfide_variant_sites": [303, 322, 328, 350],
    "cysteine_variant_sites": [],
}
FROZEN_HASHES = {
    "qc/replica_aggregation_manifest_qc_derived.json": (
        "711cd4e66b7b69bf4382abcb98fd272a553ce31e3f9f01db164bf17b6b4a2aa5"
    ),
    "frozen/protein_edge.csv": (
        "335a3577618ad21e56a9c064c70d4d3cb6c6c4e6054c85f1858676a09bb7aabc"
    ),
    "bound/protein_edges_by_window_canonical.csv": (
        "52065cb5134ff5b095ea5ea6c056c4e90e42a3126c2730c3cc007de212dd58d5"
    ),
    "qc/dataset_qc_decision_set.json": (
        "3340cb3a6f33dcd3287bd2a1182fe2df360f164659c213fffd62561f737e5b73"
    ),
    "aggregation/protein_edges_by_window_canonical_replica_aggregation.csv": (
        "73744ee48cc83c3280ed7adba6746c463e99af19e0656242123094180c5ab058"
    ),
}
ALLOWED_FILES = (
    "tools/stage34b5_publication_resume.py",
    "tests/test_stage34b5_publication_resume.py",
    "docs/stage34b5_resume_downstream_smoke.md",
)


def read(path):
    return json.loads(path.read_text())


def checkpoint(repo, work):
    def command(argv):
        return prior.command(repo, work, argv)

    require(command(["git", "branch", "--show-current"]) == "FAIR", "Required FAIR")
    head = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--short"])
    require(
        all(s[3:] in ALLOWED_FILES for s in status.splitlines()),
        "Unexpected working-tree changes",
    )
    command(["git", "rev-parse", "develop"])
    command(["git", "merge-base", "--is-ancestor", "develop", "HEAD"])
    command(["git", "log", "--oneline", "--decorate", "-32"])
    for name in prior.ALLOWED_FILES:
        command(["git", "ls-files", "--error-unmatch", name])
        command(["git", "cat-file", "-e", f"HEAD:{name}"])
        # The documentation may be extended by this task; code/tests remain frozen.
        if not name.startswith("docs/"):
            require(
                not command(["git", "status", "--porcelain", "--", name]),
                "Previous resume helper/tests must be committed",
            )
    require(not command(["git", "diff", "--cached", "--name-only"]), "Nothing staged")
    dump(work / "git_state.txt", dict(starting_head=head, branch="FAIR", status=status))
    return head


def check_frozen_hashes(base):
    records = {}
    for name, expected in FROZEN_HASHES.items():
        record = file_record(base / name)
        require(record["sha256"] == expected, f"Frozen identity differs: {name}")
        records[name] = record
    return records


def bind_history(base, work):
    """Compare prior archive bytes; link history without editing or reexecuting it."""
    records = check_frozen_hashes(base)
    inventory = read(base / "evidence_inventory.json")
    with zipfile.ZipFile(base.with_suffix(".zip")) as archive:
        for item in inventory["files"]:
            name = item["path"]
            require(
                prior.accepted.digest(base / name) == item["sha256"],
                f"Accepted evidence changed: {name}",
            )
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == item["sha256"],
                f"Accepted archive differs: {name}",
            )
    links = {"prior": base}
    bindings = read(base / "accepted_evidence_bindings.json")
    links.update({n: Path(bindings[n]) for n in ("b3", "b4", "rmsd")})
    references = {}
    for name, path in links.items():
        (work / name).symlink_to(path, target_is_directory=True)
        references[name] = dict(
            directory=str(path), archive=file_record(path.with_suffix(".zip"))
        )
    dump(work / "accepted_evidence_links.json", references)
    return records


def validate_annotation_authority(artifact, provenance):
    annotations = read_dataset_system_biological_annotations(artifact)
    require(
        (annotations.dataset_id, annotations.system_id) == KEY[:2],
        "Annotation system differs",
    )
    require(annotations.annotation_scope == "complete_for_system", "Incomplete scope")
    reference = load_default_napi2b_canonical_reference()
    require(provenance["system_identity"] == IDENTITY, "Authority identity differs")
    require(
        provenance["canonical_reference_id"] == reference.reference_id
        and provenance["canonical_reference_sequence_sha256"]
        == reference.sequence_sha256,
        "Authority reference differs",
    )
    require(
        provenance["authority_kind"]
        == "externally_supplied_complete_system_annotations",
        "PSF connectivity alone cannot supply biological authority",
    )
    identities = {}
    for category, expected in SITES.items():
        sites = getattr(annotations, category)
        require(
            [s.canonical_residue_number for s in sites] == expected,
            f"Exact externally accepted list required: {category}",
        )
        evidence = provenance["categories"][category]
        require(
            evidence["accepted_positions"] == expected
            and evidence["scientific_authority"]
            and evidence["independent_evidence"],
            f"Missing category provenance: {category}",
        )
        for site in sites:
            resname = "ASN" if category == "glycosylation_sites" else "CYS"
            require(
                reference.residue_at(site.canonical_residue_number).canonical_resname
                == site.canonical_resname
                == resname,
                "Wrong canonical residue identity",
            )
            require(
                site.source == evidence["scientific_authority"]
                and site.verifier == evidence["independent_evidence"],
                "Annotation provenance was not preserved",
            )
            if category == "glycosylation_sites":
                require(
                    site.glycan_name == "FA2G2S2" and site.present_in_topology is True,
                    "Supplied glycan authority differs",
                )
            identities[str(site.canonical_residue_number)] = resname
    return annotations, dict(
        status="PASS",
        annotation_scope=annotations.annotation_scope,
        **SITES,
        canonical_residues=identities,
        canonical_reference_id=reference.reference_id,
        strict_read=True,
        topology_inference=False,
    )


def bind_temporal(base, work):
    """Apply the already accepted condition label; prove all temporal science equal."""
    original = read_preprocessing_temporal_execution(base / "frozen/temporal.json")
    require(len(original.bindings) == 1, "Single replica temporal evidence required")
    binding = original.bindings[0]
    require(
        binding.dataset_spec.identity.to_dict() == prior.accepted.IDENTITY,
        "Unexpected historical temporal identity",
    )
    spec = binding.dataset_spec.model_copy(
        update={
            "identity": binding.dataset_spec.identity.model_copy(
                update={"condition": "PMm"}
            )
        }
    )
    bound = replace(
        original,
        bindings=(replace(binding, dataset_spec=spec, execution_condition="PMm"),),
    )
    require(
        replace(
            bound.bindings[0],
            dataset_spec=binding.dataset_spec,
            execution_condition=binding.execution_condition,
        )
        == binding,
        "Temporal science changed",
    )
    temporal = spec.temporal
    require(
        (temporal.production_start_ns, temporal.production_end_ns) == (0.1, 0.5)
        and binding.sampling_plan.requested_sample_count == 5
        and binding.sampling_plan.sampled_frame_count == 5,
        "Smoke scope changed",
    )
    require(
        write_preprocessing_temporal_execution(
            bound, work / "publication_temporal"
        ).written,
        "Temporal binding write failed",
    )
    dump(
        work / "temporal_condition_binding.json",
        dict(
            status="PASS",
            source=file_record(base / "frozen/temporal.json"),
            condition_authority="prior/condition_authority.json",
            changed_fields=[
                "bindings[0].dataset_spec.identity.condition",
                "bindings[0].execution_condition",
            ],
            prior_value=None,
            bound_value="PMm",
            temporal_science_equal=True,
            interval_ns=[0.1, 0.5],
            requested_samples=5,
            resolved_samples=5,
        ),
    )


def release_control(base):
    qc_path = base / "dataset_qc_manifest.json"
    used_path = base / "qc/replica_aggregation_manifest_qc_derived.json"
    used = read_replica_aggregation_manifest(used_path)

    def binding(directory, specs):
        return ReleaseUpstreamRun(
            f"prior/{directory}/run_provenance.json",
            f"prior/{directory}/artifact_inventory.json",
            tuple(
                ReleaseInputBinding(
                    s.artifact_id,
                    "prior/" + s.local_path.resolve().relative_to(base).as_posix(),
                )
                for s in specs
            ),
        )

    qc = read_dataset_qc_manifest(qc_path)
    return DatasetReleaseExportManifest(
        KEY[0],
        binding("qc", collect_dataset_qc_input_specs(qc, qc_path)),
        binding(
            "aggregation", collect_replica_aggregation_input_specs(used, used_path)
        ),
        "prior/qc/dataset_qc_decision_set.json",
        "prior/qc/dataset_qc_summary.csv",
        "prior/qc/replica_aggregation_manifest_qc_derived.json",
        "prior/qc/replica_aggregation_manifest_qc_derived.json",
        "prior/aggregation/" + FAMILIES[0].filename,
        None,
        None,
        tuple(
            ReleaseCanonicalBinding(
                f.name,
                "prior/bound/" + f.filename.replace("_replica_aggregation", ""),
                (KEY,),
            )
            for f in FAMILIES
        ),
        ("publication_temporal/temporal_execution.json",),
        (ReleaseAnnotationBinding(*KEY[:2], "biological_annotations_authority.json"),),
        "publication_inputs.json",
        (KEY,),
        (KEY[:2],),
    )


def annotation_output_check(table):
    rows = table.records()
    require(
        len(rows) == 690
        and {r["canonical_residue_number"] for r in rows} == set(range(1, 691)),
        "Expected all canonical annotations",
    )
    flags = {
        "is_glycosylation_site": set(SITES["glycosylation_sites"]),
        "is_disulfide_variant_site": set(SITES["disulfide_variant_sites"]),
        "is_cysteine_variant_site": set(),
        "is_ecd": set(range(234, 362)),
        "is_mx35_region": set(range(311, 342)),
    }
    for row in rows:
        for flag, sites in flags.items():
            require(
                row[flag] is (row["canonical_residue_number"] in sites),
                f"Complete positive/negative annotation differs: {flag}",
            )
    return dict(
        status="PASS",
        checked_residues=690,
        negative_semantics="false",
        true_counts={k: len(v) for k, v in flags.items()},
    )


def compare_published_rows(source, published):
    """Compare every identity/scientific field retained by publication, exactly."""
    require(len(source) == len(published), "Publication row population differs")
    if not source:
        return
    names = set(source[0].to_dict()) & set(published[0])
    require(bool(names), "No comparable scientific fields")

    def normalized(row):
        return tuple(
            publication_number(row[n]) if type(row[n]) in (int, float) else row[n]
            for n in sorted(names)
        )

    require(
        sorted(normalized(r.to_dict()) for r in source)
        == sorted(normalized(r) for r in published),
        "Publication scientific values differ",
    )


def independent_publication_check(bundle, canonical, aggregate, root):
    """Compare persisted science directly against frozen source/aggregate models."""
    counts = {}
    for family, table_id in (
        ("protein", "protein_edges_by_window"),
        ("lipid", "protein_lipid_contacts_by_window"),
        ("glycan", "protein_glycan_contacts_by_window"),
    ):
        table = getattr(bundle.science, table_id)
        published = read_publication_csv(table_id, root / table.relative_path).records()
        compare_published_rows(canonical[family].rows, published)
        counts[family] = len(published)
    table = bundle.science.protein_edges_by_window_replica_aggregation
    compare_published_rows(
        aggregate.rows,
        read_publication_csv(table.table_id, root / table.relative_path).records(),
    )
    result = prior.independent_protein_check(
        canonical["protein"],
        aggregate,
        bundle.aggregation_authority.aggregation_manifest_used,
    )
    prior.require_stage31(result)
    systems = bundle.metadata.systems.records()
    simulations = bundle.metadata.simulations.records()
    require(
        len(systems) == len(simulations) == 1 and systems[0]["condition"] == "PMm",
        "Publication system population/condition differs",
    )
    require(
        tuple(
            simulations[0][n]
            for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
        )
        == KEY
        and simulations[0]["qc_status"] == "pass"
        and simulations[0]["release_decision"] == "available"
        and simulations[0]["decision_mode"] == "automatic",
        "Publication QC differs",
    )
    window = bundle.metadata.time_windows.records()
    require(
        len(window) == 1
        and float(window[0]["requested_window_start_ns"]) == 0.1
        and float(window[0]["requested_window_end_ns"]) == 0.5
        and window[0]["expected_sample_count"]
        == window[0]["resolved_sample_count"]
        == 5,
        "Publication interval differs",
    )
    require(bundle.science.metrics.row_count == 0, "No additional metrics authorized")
    require(
        bundle.science.protein_lipid_contacts_by_window_replica_aggregation.row_count
        == 0
        and (
            bundle.science.protein_glycan_contacts_by_window_replica_aggregation.row_count
        )
        == 0,
        "Specialized correspondence must not be invented",
    )
    return dict(
        status="PASS",
        source_rows=counts,
        aggregate=result,
        condition="PMm",
        replica_id="1",
        interval_ns=[0.1, 0.5],
        metric_count=0,
        final_dataset_release=False,
    )


def construct_contact_definitions(
    work, replica_key, edge_directory, protocol_path, diagnostic_path, catalog_path=None
):
    """Bind explicit current artifacts to the committed constructor; no seed input."""
    approval = read(work / protocol_path)
    require(
        approval["protocol_scientifically_approved"] is True
        and approval["internal_mic"] is False,
        "Explicit external PBC approval with internal MIC=false required",
    )
    authority = None
    if catalog_path is not None:
        authority = "contact_authority/contact_definition_authority_v1.json"
        materialize_contact_definition_authority(work, authority)
    return [
        model.to_dict()
        for model in build_dataset_release_contact_definitions(
            workspace=work,
            replica_key=replica_key,
            edge_semantics_path=f"{edge_directory}/edge_semantics.json",
            run_provenance_path=f"{edge_directory}/run_provenance.json",
            pbc_correction_status=dict(
                internal_mic=False,
                external_protocol_approved=True,
                historical_scientific_pbc_status="unresolved",
                protocol_authority=protocol_path,
                trajectory_preparation_and_diagnostics=diagnostic_path,
            ),
            specialized_authority_path=authority,
            partner_catalog_path=catalog_path,
        )
    ]


def software_records(work, dataset_id, directories):
    records = []
    for directory in directories:
        provenance = read(work / directory / "run_provenance.json")
        records.append(
            dict(
                dataset_id=dataset_id,
                run_id=provenance["run_id"],
                component_name="mania-wania",
                component_role="package",
                version=provenance["software_identity"]["version"],
                source_artifact_role="run_provenance",
                source_artifact_path=f"{directory}/run_provenance.json",
            )
        )
    return records


def prepare_publication_inputs(work):
    contacts = construct_contact_definitions(
        work,
        KEY,
        "b3/output",
        "prior/pbc_protocol_approval.json",
        "prior/frozen/b3_pbc.json",
        "prior/frozen/partner_catalog.json",
    )
    software = software_records(
        work, KEY[0], ("b3/output", "prior/qc", "prior/aggregation")
    )
    software.append(
        dict(
            dataset_id=KEY[0],
            run_id=None,
            component_name="NAMD",
            component_role="engine",
            version=None,
            source_artifact_role="accepted_namd_source_evidence",
            source_artifact_path="prior/frozen/b4_source_observations.json",
        )
    )
    dump(
        work / "publication_inputs.json",
        dict(
            kind=PUBLICATION_INPUT_KIND,
            schema_version=PUBLICATION_INPUT_SCHEMA_VERSION,
            contact_definitions=contacts,
            software_versions=software,
            metrics=[],
        ),
    )
    return read_dataset_release_publication_inputs(work / "publication_inputs.json")


def run(base, work, annotation_path, provenance_path, publication_inputs_path=None):
    started = time.perf_counter()
    summary = dict(
        label=LABEL,
        stage34b5_status="STOP",
        stage34b_status="INCOMPLETE",
        stage34_status="IN PROGRESS",
        stage34c_status="WAITING FOR replicas 2 and 3",
        final_dataset_release=False,
        interval_ns=[0.1, 0.5],
        stage32_recomputed=False,
        stage31_recomputed=False,
        rmsd_recalculated=False,
        internal_mic=False,
        replicas_2_3_run=False,
        full_100ns_analysis=False,
        all_33_run=False,
        stage35_run=False,
    )
    timings = {}
    phase = "repository checkpoint"
    try:
        summary["starting_head"] = checkpoint(Path(__file__).resolve().parents[1], work)
        phase = "frozen bindings"
        frozen = bind_history(base, work)
        phase = "biological annotation authority"
        annotations, check = validate_annotation_authority(
            annotation_path, read(provenance_path)
        )
        for source, name in (
            (annotation_path, "biological_annotations_authority.json"),
            (provenance_path, "biological_annotations_provenance.json"),
        ):
            (work / name).write_bytes(source.read_bytes())
        dump(work / "biological_annotations_validation.json", check)
        prior.publication_readiness(
            dict(status="PASS", aggregate_mismatches=0), (annotations,)
        )
        bind_temporal(base, work)
        if publication_inputs_path is None:
            prepare_publication_inputs(work)
        else:
            (work / "publication_inputs.json").write_bytes(
                publication_inputs_path.read_bytes()
            )
        control = release_control(base)
        path = work / "dataset_release_export_manifest.json"
        require(
            write_dataset_release_export_manifest(control, path).written,
            "Control write failed",
        )
        phase = "frozen Stage 32/31 lineage"
        authority, _, aggregates = load_release_authority(control, work)
        canonical = {
            f.name: f.canonical_reader(
                work
                / next(b.path for b in control.canonical_bindings if b.family == f.name)
            )
            for f in FAMILIES
        }
        check = prior.independent_protein_check(
            canonical["protein"],
            aggregates["protein"],
            authority.aggregation_manifest_used,
        )
        prior.require_stage31(check)
        require(
            check["source_rows"] == check["aggregate_rows"] == 6514,
            "Frozen row counts differ",
        )
        decision = authority.decisions.records[0]
        require(
            len(authority.decisions.records) == 1
            and decision.replica_key == KEY
            and decision.qc_status == "pass"
            and decision.release_decision == "available"
            and decision.decision_mode == "automatic",
            "Accepted QC differs",
        )
        require(
            read(base / "qc/run_provenance.json")["resolved_configuration"][
                "production_ready"
            ]
            is True,
            "Accepted QC is not production ready",
        )
        dump(
            work / "frozen_stage32_stage31_binding_check.json",
            dict(
                status="PASS",
                frozen=frozen,
                independent_aggregate_check=check,
                stage32_recomputed=False,
                stage31_recomputed=False,
                production_ready=True,
            ),
        )
        timings["binding_seconds"] = time.perf_counter() - started
        inputs = read_dataset_release_publication_inputs(
            work / "publication_inputs.json"
        )
        require(
            not inputs.metrics,
            "No additional metric selection authorized for this smoke",
        )
        phase = "Stage 33 publication"
        tick = time.perf_counter()
        result = run_dataset_release(path, work / "publication", checksum_mode="sha256")
        timings["stage33_seconds"] = time.perf_counter() - tick
        bundle = result.bundle
        dump(work / "stage33_release_check.json", result.to_dict())
        phase = "F1"
        validate_release_canonical_source_authority(
            control, authority.aggregation_manifest_used, canonical
        )
        dump(
            work / "stage33_f1_source_authority.json",
            dict(
                status="PASS",
                comparison="complete canonical-model equality",
                source=frozen["bound/protein_edges_by_window_canonical.csv"],
                source_rows=6514,
            ),
        )
        phase = "F2"
        validate_publication_metric_sources(inputs, control, work, bundle.metadata)
        dump(
            work / "stage33_f2_metric_authority.json",
            dict(
                status="PASS",
                emitted_metrics=0,
                reason=(
                    "No separately selected authoritative publication metrics; "
                    "canonical science retained"
                ),
            ),
        )
        phase = "annotation output"
        dump(
            work / "biological_annotation_output_check.json",
            annotation_output_check(
                read_publication_csv(
                    "residue_annotations",
                    work
                    / "publication"
                    / bundle.metadata.residue_annotations.relative_path,
                )
            ),
        )
        phase = "cross-table validation"
        validate_dataset_release_tables(
            bundle.metadata, bundle.science, authority, control
        )
        dump(
            work / "cross_table_validation.json",
            dict(status="PASS", tables=[t.table_id for t in bundle.tables]),
        )
        phase = "release validation"
        tick = time.perf_counter()
        report = validate_run_artifacts(
            work / "publication",
            scope="dataset_release",
            input_artifact_paths={"input:dataset_release_export_manifest": path},
        )
        dump(work / "release_validation.json", report.to_dict())
        require(
            report.status == "passed" and report.complete,
            "Incomplete release validation",
        )
        timings["release_validation_seconds"] = time.perf_counter() - tick
        phase = "independent publication checks"
        dump(
            work / "independent_publication_check.json",
            independent_publication_check(
                bundle, canonical, aggregates["protein"], work / "publication"
            ),
        )
        check_frozen_hashes(base)
        summary.update(
            stage34b5_status="PASS",
            stage34b_status="PASS",
            F1="PASS",
            F2="PASS",
            cross_table_validation="PASS",
            release_validation_status=report.status,
            release_validation_complete=report.complete,
        )
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        summary.update(stop_gate=phase, reason=str(exc))
    files = list((work / "publication").rglob("*"))
    summary["publication_artifact_counts"] = dict(
        csv=sum(p.suffix == ".csv" for p in files),
        json=sum(p.suffix == ".json" for p in files),
        total=sum(p.is_file() for p in files),
    )
    for name in (
        "frozen_stage32_stage31_binding_check",
        "biological_annotations_validation",
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
    timings["total_seconds"] = time.perf_counter() - started
    dump(work / "timings.json", timings)
    dump(work / "stage34b5_publication_resume_summary.json", summary)
    (work / "warnings_limitations.txt").write_text(
        f"{LABEL}; 0.1-0.5 ns, five requested/resolved samples, replica 1 only.\n"
        "The frozen release_version identifies the schema, not a final Dataset claim.\n"
        "Specialized aggregation absent: authoritative partner correspondence absent.\n"
        "Optional metrics absent: no additional authoritative metric selection.\n"
        "External PBC protocol approval: prior/pbc_protocol_approval.json.\n"
        "Trajectory evidence: prior/frozen/b3_pbc.json; internal MIC=false.\n"
        "Historical scientific_pbc_status=unresolved remains unchanged.\n"
        + (
            f"STOP: {summary.get('stop_gate')}: {summary.get('reason')}\n"
            if summary["stage34b5_status"] != "PASS"
            else ""
        )
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "prior-evidence",
        "annotation-input",
        "annotation-provenance",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--publication-inputs", type=Path)
    args = parser.parse_args(argv)
    base = args.prior_evidence.resolve()
    work = base.parent / (
        "stage34b5_publication_resume_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_")
        + uuid4().hex
    )
    work.mkdir()
    summary = run(
        base,
        work,
        args.annotation_input,
        args.annotation_provenance,
        args.publication_inputs,
    )
    print(json.dumps(dict(evidence=str(work), summary=summary), indent=2))
    return 0 if summary["stage34b5_status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
