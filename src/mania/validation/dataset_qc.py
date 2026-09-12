"""Strict Stage 32 validation by shared accepted-evaluator reconstruction."""

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from mania.artifact_inventory_io import read_artifact_inventory
from mania.dataset_qc_decision_io import (
    dataset_qc_decision_set_bytes,
    read_dataset_qc_decision_set,
)
from mania.dataset_qc_evidence_io import (
    read_replica_hard_qc_evidence,
    read_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest_io import read_dataset_qc_manifest
from mania.dataset_qc_run import (
    DATASET_QC_WORKFLOW,
    DECISION_ROLE,
    DERIVED_ROLE,
    HARD_EVIDENCE_ROLE,
    MANIFEST_ARTIFACT_ID,
    MANIFEST_ROLE,
    OUTPUT_FILES,
    REVIEW_EVIDENCE_ROLE,
    SUMMARY_ROLE,
    TEMPLATE_ROLE,
    collect_dataset_qc_input_specs,
    dataset_qc_configuration,
)
from mania.dataset_qc_summary import (
    dataset_qc_summary_csv_bytes,
    read_dataset_qc_summary_csv,
)
from mania.dataset_qc_workflow import execute_dataset_qc_manifest
from mania.replica_aggregation_manifest_io import (
    read_replica_aggregation_manifest,
    replica_aggregation_manifest_payload,
)
from mania.run_provenance_io import read_run_provenance
from mania.validation.run_artifacts import ArtifactSetValidationReport
from mania.validation.unified import (
    SpecializedArtifactValidationRecord,
    SpecializedValidationStatus,
    UnifiedArtifactValidationIssue,
    UnifiedArtifactValidationReport,
)


def validate_dataset_qc_run(
    run_root: Path,
    integrity: ArtifactSetValidationReport,
    input_artifact_paths: Mapping[str, Path] | None,
) -> UnifiedArtifactValidationReport:
    records: list[SpecializedArtifactValidationRecord] = []
    issues: list[UnifiedArtifactValidationIssue] = []
    mappings = {} if input_artifact_paths is None else input_artifact_paths

    def report() -> UnifiedArtifactValidationReport:
        return UnifiedArtifactValidationReport(
            integrity.scope,
            integrity.run_id,
            integrity.workflow,
            integrity,
            tuple(records),
            tuple(issues),
        )

    def fail(code: str, message: str) -> None:
        issues.append(UnifiedArtifactValidationIssue("error", code, message))

    try:
        inventory = read_artifact_inventory(run_root / integrity.inventory_path)
        provenance = read_run_provenance(run_root / integrity.provenance_path)
    except ValueError:
        return report()
    if inventory.workflow != DATASET_QC_WORKFLOW or (
        provenance.workflow != DATASET_QC_WORKFLOW
    ):
        fail("dataset_qc_workflow_mismatch", "Selected scope requires Dataset QC run.")
    entries = inventory.artifacts
    observations = {r.artifact_id: r for r in integrity.artifact_records}
    if tuple(
        (e.artifact_id, e.direction, e.role, e.path, e.condition, e.byte_size, e.sha256)
        for e in entries
    ) != tuple(
        (
            r.artifact_id,
            r.direction,
            r.role,
            r.path,
            r.condition,
            r.byte_size_expected,
            r.sha256_expected,
        )
        for r in integrity.artifact_records
    ):
        fail("inventory_changed", "Inventory differs from integrity observations.")
        return report()
    readers: dict[str, Callable[[str | Path], Any]] = {
        MANIFEST_ROLE: read_dataset_qc_manifest,
        TEMPLATE_ROLE: read_replica_aggregation_manifest,
        HARD_EVIDENCE_ROLE: read_replica_hard_qc_evidence,
        REVIEW_EVIDENCE_ROLE: read_replica_review_qc_evidence,
        DECISION_ROLE: read_dataset_qc_decision_set,
        SUMMARY_ROLE: read_dataset_qc_summary_csv,
        DERIVED_ROLE: read_replica_aggregation_manifest,
    }
    models: dict[str, Any] = {}
    for entry in entries:
        observation = observations[entry.artifact_id]
        reader = readers.get(entry.role)
        validator = f"read_{entry.role}" if reader is not None else None
        status: SpecializedValidationStatus
        if observation.resolution_status == "not_resolved":
            status = "not_resolved" if reader is not None else "unsupported"
        elif observation.byte_size_matches is not True or (
            observation.sha256_expected is not None
            and observation.sha256_matches is not True
        ):
            status = "skipped_integrity_failure"
        elif reader is None:
            status = "unsupported"
        else:
            try:
                path = (
                    run_root / entry.path
                    if entry.direction == "output"
                    else mappings[entry.artifact_id]
                )
                models[entry.artifact_id] = reader(path)
                status = "passed"
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                status = "failed"
                fail("dataset_qc_artifact_invalid", "Strict QC artifact reader failed.")
        if status == "unsupported":
            issues.append(
                UnifiedArtifactValidationIssue(
                    "warning",
                    "unsupported_artifact_role",
                    "Artifact role has no supported Dataset QC validation policy.",
                    artifact_id=entry.artifact_id,
                    path=entry.path,
                )
            )
        records.append(
            SpecializedArtifactValidationRecord(
                entry.artifact_id,
                entry.role,
                entry.path,
                entry.condition,
                validator,
                status,
                int(status == "failed"),
            )
        )
    manifest_entries = tuple(e for e in entries if e.role == MANIFEST_ROLE)
    if len(manifest_entries) != 1 or any(
        e.direction != "input" or e.artifact_id != MANIFEST_ARTIFACT_ID
        for e in manifest_entries
    ):
        fail(
            "dataset_qc_manifest_missing",
            "Exactly one QC control manifest is required.",
        )
        return report()
    # Failed provenance may legitimately lack successful outputs. It cannot
    # receive the completed-run acceptance signal, regardless of input validity.
    if provenance.status == "failed":
        fail(
            "dataset_qc_run_failed", "Failed QC run has no complete acceptance result."
        )
    manifest = models.get(MANIFEST_ARTIFACT_ID)
    if manifest is None:
        return report()
    try:
        manifest_path = mappings[MANIFEST_ARTIFACT_ID]
        specs = collect_dataset_qc_input_specs(manifest, manifest_path)
        expected_inputs = tuple(
            (s.artifact_id, s.direction, s.role, s.path, s.format, s.condition)
            for s in specs
        )
        actual_inputs = tuple(
            (e.artifact_id, e.direction, e.role, e.path, e.format, e.condition)
            for e in entries
            if e.direction == "input"
        )
        if actual_inputs != expected_inputs:
            raise ValueError("Input inventory differs from QC controls")
        if provenance.conditions or provenance.sampling_by_condition:
            raise ValueError("QC provenance must not bind conditions or sampling")
        declared_outputs = tuple(e for e in entries if e.direction == "output")
        if {(e.role, e.path) for e in declared_outputs} != {
            (r.role, r.path)
            for r in provenance.artifact_references
            if r.role != "artifact_inventory"
        }:
            raise ValueError("Output inventory and provenance references disagree")
        for entry in declared_outputs:
            if entry.role not in OUTPUT_FILES:
                continue
            if entry.artifact_id != f"output:{entry.role}" or (
                entry.path != OUTPUT_FILES[entry.role]
                or entry.condition is not None
                or entry.format != ("csv" if entry.role == SUMMARY_ROLE else "json")
            ):
                raise ValueError("Invalid QC output lineage")
        if provenance.status == "completed":
            for role in (DECISION_ROLE, SUMMARY_ROLE):
                if sum(e.role == role for e in declared_outputs) != 1:
                    raise ValueError("Missing mandatory QC output")
    except (ValueError, TypeError, KeyError):
        fail(
            "dataset_qc_lineage_mismatch", "QC controls and artifact lineage disagree."
        )
        return report()
    if provenance.status == "failed" or any(r.status != "passed" for r in records):
        return report()
    try:
        mapped = {
            s.local_path.relative_to(manifest_path.parent): mappings[s.artifact_id]
            for s in specs
            if s.role != MANIFEST_ROLE
        }
        expected = execute_dataset_qc_manifest(
            manifest, manifest_path, mapped_paths=mapped
        )
        if provenance.to_dict()["resolved_configuration"] != dataset_qc_configuration(
            manifest,
            inventory.checksum_mode,
            expected,
        ):
            raise ValueError("QC provenance configuration differs from reconstruction")
        expected_models = {
            DECISION_ROLE: expected.decisions,
            SUMMARY_ROLE: expected.summary,
        }
        expected_bytes = {
            DECISION_ROLE: dataset_qc_decision_set_bytes(expected.decisions),
            SUMMARY_ROLE: dataset_qc_summary_csv_bytes(expected.summary),
        }
        if expected.derived_manifest is not None:
            expected_models[DERIVED_ROLE] = expected.derived_manifest
            expected_bytes[DERIVED_ROLE] = (
                json.dumps(
                    replica_aggregation_manifest_payload(
                        expected.derived_manifest,
                        run_root / OUTPUT_FILES[DERIVED_ROLE],
                    ),
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
        elif os.path.lexists(run_root / OUTPUT_FILES[DERIVED_ROLE]):
            raise ValueError("Pending review forbids any derived manifest file")
        if {e.role for e in declared_outputs} != set(expected_models) or (
            len(declared_outputs) != len(expected_models)
        ):
            raise ValueError(
                "Conditional QC outputs disagree with production readiness"
            )
        for role, model in expected_models.items():
            if models[f"output:{role}"] != model or (
                (run_root / OUTPUT_FILES[role]).read_bytes() != expected_bytes[role]
            ):
                raise ValueError("QC output differs from accepted API reconstruction")
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        fail(
            "dataset_qc_reconstruction_mismatch",
            "QC models and bytes must equal accepted evaluator/bridge reconstruction.",
        )
    return report()
