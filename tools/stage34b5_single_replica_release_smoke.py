#!/usr/bin/env python3
"""Real single-replica QC evidence, stopping at unavailable review authority.

This continuation implements only the reached B.5 gates. It does not substitute
an RMSD assessment, create pre-QC availability, or execute downstream workflows.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
import time
import zipfile
from dataclasses import fields
from decimal import Decimal
from pathlib import Path

from mania import canonical_window_tables_io as canonical_io
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.canonical_window_tables import DatasetCanonicalResidueMappingBinding
from mania.dataset_hard_qc import (
    ReplicaProteinPBCEvidence,
    ReplicaRawIntegrityEvidence,
    RequiredArtifactEvidence,
    RequiredMetadataEvidence,
    evaluate_replica_hard_qc,
)
from mania.dataset_qc_contract import QCEvidenceRecord
from mania.dataset_qc_evidence_io import (
    ReplicaHardQCEvidence,
    read_replica_hard_qc_evidence,
    write_replica_hard_qc_evidence,
)
from mania.dataset_review_qc import (
    ProteinEdgeEmptyWindowEvidence,
    ReplicaMADMetricObservation,
    _mad_checks,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)

_spec = importlib.util.spec_from_file_location(
    "stage34b5_b4", Path(__file__).with_name("stage34b4_namd_specialized_pilot.py")
)
b4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b4)
require, dump, file_record = b4.require, b4.dump, b4.file_record
BLOCKER = (
    "No authoritative RMSD/drift assessment is supplied for this exact replica "
    "and five-frame contract. Stage 32.C requires an explicit bool assessment; "
    "missing evidence cannot become drift_detected=False or True. Complete "
    "review QC and an authoritative release decision cannot be constructed."
)


def require_b4_pass(summary):
    require(summary["stage34b4_status"] == "PASS", "B.4 must completely PASS")
    require(summary["independent"]["status"] == "PASS", "B.4 independent failure")
    require(
        summary["technical"]["status"] == "passed" and summary["technical"]["complete"],
        "B.4 technical validation incomplete",
    )


def freeze_file(source, target, expected_sha256=None):
    before = file_record(source)
    if expected_sha256 is not None:
        require(before["sha256"] == expected_sha256, "Frozen input binding changed")
    shutil.copyfile(source, target)
    require(file_record(target)["sha256"] == before["sha256"], "Freeze copy changed")
    return {**before, "frozen_path": f"frozen/{target.name}"}


def freeze_inputs(b4_work, work):
    summary = json.loads((b4_work / "stage34b4_summary.json").read_text())
    require_b4_pass(summary)
    bindings = json.loads((b4_work / "accepted_b3_bindings.json").read_text())
    require(bindings["status"] == "PASS", "Accepted binding absent")
    b3_work = Path(bindings["prepared"]["path"]).parent
    frozen = work / "frozen"
    frozen.mkdir()
    inputs = {
        "b4_summary": b4_work / "stage34b4_summary.json",
        "b4_bindings": b4_work / "accepted_b3_bindings.json",
        "b4_validation": b4_work / "technical_validation.json",
        "b4_source_observations": b4_work / "source_input_observations.json",
        "b3_summary": b3_work / "stage34b_real_pilot_summary.json",
        "b3_identity": b3_work / "prepared_trajectory_identity.json",
        "b3_pbc": b3_work / "persisted_pbc_validation.json",
        "b3_validation": b3_work / "technical_validation.json",
        "temporal": b3_work / "output/temporal_execution.json",
        "protein_edge": b3_work / "output/protein_edges_by_window_canonical.csv",
        "protein_source": b3_work / "output/protein_edges_by_window_source.csv",
        "protein_lipid": b4_work
        / "output/protein_lipid_contacts_by_window_canonical.csv",
        "protein_glycan": b4_work
        / "output/protein_glycan_contacts_by_window_canonical.csv",
        "lipid_source": b4_work / "output/protein_lipid_contacts_by_window_source.csv",
        "glycan_source": b4_work
        / "output/protein_glycan_contacts_by_window_source.csv",
        "partner_catalog": b4_work / "molecular_partner_catalog.json",
        "partner_metadata": b4_work / "molecular_partner_metadata.json",
    }
    for name in ("elements", "time", "mapping"):
        inputs[name] = Path(bindings["authorities"][name]["path"])
    # The accepted B.3 archive supplies the historical bytes, not a new result.
    with zipfile.ZipFile(b3_work.with_suffix(".zip")) as archive:
        for role in ("protein_edge", "protein_source", "temporal"):
            source = inputs[role]
            require(
                source.read_bytes() == archive.read(f"output/{source.name}"),
                "Accepted B.3 scientific artifact differs from its archive",
            )
    inputs["required_source_keys"] = (
        inputs["mapping"].parent / "source_protein_residues.csv"
    )
    expected = {
        n: bindings["authorities"][n]["sha256"] for n in ("elements", "time", "mapping")
    }
    for name in ("lipid", "glycan"):
        check = next(
            c
            for c in summary["technical"]["checks"]
            if c["validator"] == f"{name}_canonical"
        )
        expected[f"protein_{name}"] = check["artifact"]["sha256"]
    records = {}
    for role, path in inputs.items():
        target = frozen / f"{role}{path.suffix}"
        records[role] = freeze_file(path, target, expected.get(role))
        records[role]["origin"] = (
            "new_B4"
            if path.is_relative_to(b4_work)
            else "accepted_historical_B3_or_authority"
        )
    dump(
        work / "frozen_scientific_inputs.json",
        {
            "status": "PASS",
            "freeze_before_qc": True,
            "regeneration_after_qc": False,
            "inputs": records,
            "large_inputs_by_binding_only": {
                n: bindings["authorities"][n] for n in ("psf",)
            },
            "prepared_by_binding_only": bindings["prepared"],
        },
    )
    return records


def evidence(role, records, *, kind="artifact", detail=None):
    return QCEvidenceRecord(
        f"real:{role}",
        kind,
        role,
        records[role]["frozen_path"],
        None,
        None,
        None,
        None,
        detail or f"Frozen real artifact SHA256 {records[role]['sha256']}.",
    )


def build_hard_evidence(work, records):
    def path(role):
        return work / records[role]["frozen_path"]

    bindings = json.loads(path("b4_bindings").read_text())
    observation = json.loads(path("b4_source_observations").read_text())
    persisted = json.loads(path("b3_identity").read_text())
    b4.validate_frame_records(persisted["frames"])
    require(
        all(r["checks"]["pointwise_atom_order"] for r in persisted["frames"]),
        "Accepted writer atom-order evidence absent",
    )
    require(
        bindings["prepared"]["sha256"] == persisted["sha256"] == b4.PREPARED_SHA256,
        "Prepared atom-order evidence refers to a different derivative",
    )
    pbc = json.loads(path("b3_pbc").read_text())
    b4.b3.require_representation(pbc["frames"])
    temporal = read_preprocessing_temporal_execution(path("temporal"))
    binding = temporal.bindings[0]
    identity = binding.dataset_spec.identity
    mapping = read_canonical_residue_mapping(path("mapping"))
    with path("required_source_keys").open() as stream:
        source_rows = list(csv.DictReader(stream))
    required_keys = tuple(
        (identity.engine, r["source_segment"], r["source_resid"], r["source_resname"])
        for r in source_rows
    )
    require(
        len(required_keys) == observation["protein_residues"]
        and set(required_keys) == {r.source_key for r in mapping.mappings},
        "Required source inventory differs from the accepted complete mapping",
    )
    tables, artifacts = {}, []
    for family, reader in (
        ("protein_edge", canonical_io.read_canonical_protein_edge_window_csv),
        ("protein_lipid", canonical_io.read_canonical_protein_lipid_window_csv),
        ("protein_glycan", canonical_io.read_canonical_protein_glycan_window_csv),
    ):
        tables[family] = reader(path(family))
        artifacts.append(
            RequiredArtifactEvidence(
                family, True, True, evidence(family, records), family, tables[family]
            )
        )
    # Other required artifacts retain their completed strict validation evidence.
    for role in (
        "temporal",
        "protein_source",
        "lipid_source",
        "glycan_source",
        "partner_catalog",
        "partner_metadata",
        "b3_validation",
        "b4_validation",
    ):
        artifacts.append(
            RequiredArtifactEvidence(role, True, True, evidence(role, records))
        )
    require(
        json.loads(path("b3_validation").read_text())["complete"] is True,
        "B.3 technical validation incomplete",
    )
    require(
        json.loads(path("b4_validation").read_text())["complete"] is True,
        "B.4 technical validation incomplete",
    )
    raw = ReplicaRawIntegrityEvidence(
        True,
        True,
        observation["atoms"],
        bindings["authorities"]["atoms_covered"],
        True,
        "accepted_psf_all_atoms_prepared_five_frame_derivative",
        evidence("b4_source_observations", records),
        evidence("b4_bindings", records),
        evidence(
            "b3_identity",
            records,
            detail="Accepted B.3 pointwise writer/reader "
            "coordinate order plus unchanged PSF and prepared-XTC SHA256; "
            "XTC does not independently contain atom labels.",
        ),
    )
    value = ReplicaHardQCEvidence(
        identity,
        raw,
        DatasetCanonicalResidueMappingBinding(*identity.replica_key, mapping),
        required_keys,
        ReplicaProteinPBCEvidence(
            False,
            evidence(
                "b3_pbc",
                records,
                kind="pbc",
                detail="Accepted persisted direct/periodic diagnostic: zero "
                "substantive bond/protein disagreements in all five frames. "
                "Not inferred from boxes or contacts; scientific PBC unresolved.",
            ),
        ),
        binding.sampling_plan,
        tuple(
            RequiredMetadataEvidence(role, True, evidence(role, records))
            for role in ("elements", "time", "mapping", "required_source_keys")
        ),
        tuple(artifacts),
    )
    return value, tables, temporal


def hard_findings(value, path):
    require(
        write_replica_hard_qc_evidence(value, path).passed, "QC evidence write failed"
    )
    restored = read_replica_hard_qc_evidence(path)
    require(restored == value, "Strict hard-QC evidence roundtrip differs")
    return evaluate_replica_hard_qc(
        **{f.name: getattr(restored, f.name) for f in fields(restored)}
    )


def partial_review_observations(identity, protein, temporal, records):
    binding = temporal.bindings[0]
    expected = {w.window_id for w in binding.window_plan.windows}
    populated = {r.window_id for r in protein.rows}
    require(populated <= expected, "Canonical window not in the frozen pilot plan")
    empty = len(expected - populated)
    ev = evidence(
        "protein_edge",
        records,
        detail="Strict canonical table plus explicit "
        "valid Stage 27 requested windows; missing artifacts are not empty windows.",
    )
    windows = ProteinEdgeEmptyWindowEvidence(len(expected), empty, (ev,))
    fraction = Decimal(empty) / Decimal(len(expected))
    metric = ReplicaMADMetricObservation(
        *identity.replica_key,
        identity.engine,
        "edge_count",
        "canonical_protein_edge_window_rows",
        len(protein.rows),
        "rows",
        (ev,),
    )
    # Only the accepted scalar MAD routine is applicable without inventing RMSD.
    # Its partial finding is never wrapped as a completed review evaluation.
    mad = _mad_checks((metric,))[identity.replica_key]
    return {
        "status": "INCOMPLETE_REVIEW_AUTHORITY",
        "rmsd_drift": None,
        "reason": BLOCKER,
        "empty_windows": windows.to_dict(),
        "empty_window_fraction": str(fraction),
        "accepted_threshold": "> 0.01",
        "empty_window_rule_triggered": fraction > Decimal("0.01"),
        "mad_observation": metric.to_dict(),
        "accepted_partial_mad_finding": mad.to_dict(),
        "complete_stage32c_evaluation": "NOT RUN",
        "partial_findings_authorize_release": False,
    }


def pending_decision(hard):
    require(
        hard.hard_qc_status == "pass",
        "Cannot replace a hard exclusion with pending review",
    )
    return {
        "record_kind": "pending_authority_record_not_a_Stage32_decision_set",
        "replica_key": list(hard.replica_key),
        "status": "pending_review",
        "authoritative_release_decision": None,
        "production_ready": False,
        "reviewer": None,
        "reason": BLOCKER,
        "policy": "Hard PASS requires matching complete review evaluation; "
        "a valid review evaluation requires explicit RMSD authority.",
    }


def run(b4_work):
    work = b4_work / "b5"
    work.mkdir(exist_ok=False)
    started = time.perf_counter()
    records = freeze_inputs(b4_work, work)
    value, tables, temporal = build_hard_evidence(work, records)
    hard = hard_findings(value, work / "stage32_qc_evidence.json")
    dump(work / "stage32_qc_findings.json", hard.to_dict())
    require(
        hard.hard_qc_status == "pass",
        "Hard QC failed; preserve exclusion before any downstream",
    )
    partial = partial_review_observations(
        value.identity, tables["protein_edge"], temporal, records
    )
    dump(work / "stage32_review_observations.json", partial)
    dump(work / "stage32_qc_pending_decision.json", pending_decision(hard))
    for name in (
        "qc_decision_to_stage31_manifest",
        "stage31_manifest",
        "stage31_aggregation_check",
        "stage33_release_check",
        "stage33_f1_source_authority",
        "stage33_f2_metric_authority",
        "release_validation",
        "stage34c_prep",
    ):
        dump(work / f"{name}_NOT_RUN.json", {"status": "NOT RUN", "reason": BLOCKER})
    for record in records.values():
        require(
            file_record(Path(record["path"]))["sha256"] == record["sha256"],
            "Scientific input changed after QC freeze",
        )
    summary = {
        "stage34b5_status": "AUTHORITY STOP",
        "label": "single-replica downstream smoke",
        "reason": BLOCKER,
        "hard_qc_status": hard.hard_qc_status,
        "hard_check_count": len(hard.checks),
        "hard_fail_count": 0,
        "complete_review_qc": "NOT RUN",
        "qc_decision_status": "pending_review",
        "authoritative_release_decision": None,
        "production_ready": False,
        "expected_samples": value.sampling_plan.requested_sample_count,
        "resolved_samples": value.sampling_plan.sampled_frame_count,
        "coverage": value.sampling_plan.coverage_fraction,
        "valid_requested_windows": partial["empty_windows"]["expected_window_count"],
        "empty_windows": partial["empty_windows"]["empty_window_count"],
        "scientific_pbc_status": "unresolved",
        "condition": value.identity.condition,
        "qc_derived_stage31_manifest": "NOT RUN",
        "stage31_aggregation": "NOT RUN",
        "stage33_publication": "NOT RUN",
        "F1": "NOT RUN",
        "F2": "NOT RUN",
        "release_validation": "NOT RUN",
        "stage34c_prep": "NOT RUN",
        "wall_seconds": time.perf_counter() - started,
    }
    dump(work / "stage34b5_summary.json", summary)
    (work / "warnings_limitations.txt").write_text(BLOCKER + "\n" + b4.LIMITATIONS)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b4-evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.b4_evidence.resolve()), indent=2))
    return 2  # An authority STOP is never reported as a complete smoke PASS.


if __name__ == "__main__":
    sys.exit(main())
