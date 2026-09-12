"""Separate Dataset QC run using the unchanged Stage 25 technical schemas."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mania.artifact_inventory import ArtifactChecksumMode
from mania.artifact_inventory_io import (
    ArtifactInventoryFileSpec,
    build_artifact_inventory,
    write_artifact_inventory,
)
from mania.dataset_qc_decision_io import (
    DATASET_QC_DECISION_SET_FILENAME,
    dataset_qc_decision_set_bytes,
    write_dataset_qc_decision_set,
)
from mania.dataset_qc_manifest import DatasetQCManifest
from mania.dataset_qc_summary import (
    DATASET_QC_SUMMARY_CSV_FILENAME,
    dataset_qc_summary_csv_bytes,
    write_dataset_qc_summary_csv,
)
from mania.dataset_qc_workflow import (
    QC_DERIVED_REPLICA_AGGREGATION_MANIFEST_FILENAME,
    DatasetQCOutputs,
    DatasetQCWorkflowError,
    execute_dataset_qc_manifest,
    load_dataset_qc_manifest,
)
from mania.replica_aggregation_manifest_io import (
    replica_aggregation_manifest_payload,
    write_replica_aggregation_manifest,
)
from mania.run_provenance import (
    PortableArtifactReference,
    RunProvenance,
    RunProvenanceIssue,
)
from mania.run_provenance_io import read_run_provenance, write_run_provenance
from mania.software_identity import get_software_identity

DATASET_QC_WORKFLOW = "dataset_qc"
MANIFEST_ROLE = "dataset_qc_manifest"
MANIFEST_ARTIFACT_ID = "input:dataset_qc_manifest"
MANIFEST_PORTABLE_PATH = "inputs/dataset_qc_manifest.json"
TEMPLATE_ROLE = "replica_aggregation_manifest_template"
HARD_EVIDENCE_ROLE = "dataset_hard_qc_evidence"
REVIEW_EVIDENCE_ROLE = "dataset_review_qc_evidence"
DECISION_ROLE = "dataset_qc_decision_set"
SUMMARY_ROLE = "dataset_qc_summary"
DERIVED_ROLE = "qc_derived_replica_aggregation_manifest"
OUTPUT_FILES = {
    DECISION_ROLE: DATASET_QC_DECISION_SET_FILENAME,
    SUMMARY_ROLE: DATASET_QC_SUMMARY_CSV_FILENAME,
    DERIVED_ROLE: QC_DERIVED_REPLICA_AGGREGATION_MANIFEST_FILENAME,
}


def collect_dataset_qc_input_specs(
    manifest: DatasetQCManifest,
    manifest_path: Path,
) -> tuple[ArtifactInventoryFileSpec, ...]:
    specs = [
        ArtifactInventoryFileSpec(
            MANIFEST_ARTIFACT_ID,
            "input",
            MANIFEST_ROLE,
            manifest_path,
            MANIFEST_PORTABLE_PATH,
            "json",
        )
    ]
    paths = [(TEMPLATE_ROLE, manifest.aggregation_manifest_template_path)]
    for replica in manifest.replicas:
        paths.append((HARD_EVIDENCE_ROLE, replica.hard_qc_evidence_path))
        if replica.review_qc_evidence_path is not None:
            paths.append((REVIEW_EVIDENCE_ROLE, replica.review_qc_evidence_path))
    seen: set[Path] = set()
    for role, path in paths:
        if path in seen:
            continue
        seen.add(path)
        index = sum(s.role == role for s in specs) + 1
        specs.append(
            ArtifactInventoryFileSpec(
                f"input:{role}:{index:04d}",
                "input",
                role,
                manifest_path.parent / path,
                f"inputs/qc/{path.as_posix()}",
                "json",
            )
        )
    return tuple(specs)


def dataset_qc_configuration(
    manifest: DatasetQCManifest,
    checksum_mode: ArtifactChecksumMode,
    outputs: DatasetQCOutputs | None,
) -> dict[str, object]:
    config: dict[str, object] = {
        "workflow": DATASET_QC_WORKFLOW,
        "manifest_path": MANIFEST_PORTABLE_PATH,
        "canonical_reference": {
            "reference_id": manifest.canonical_reference_id,
            "sequence_sha256": manifest.canonical_reference_sequence_sha256,
        },
        "replica_count": len(manifest.replicas),
        "artifact_checksum_mode": checksum_mode,
    }
    if outputs is not None:
        rows = outputs.summary.rows
        config.update(
            {
                "hard_pass_count": sum(r.hard_qc_status == "pass" for r in rows),
                "hard_fail_count": sum(r.hard_qc_status == "fail" for r in rows),
                "review_pass_count": sum(r.review_qc_status == "pass" for r in rows),
                "review_count": sum(r.review_qc_status == "review" for r in rows),
                "pass_count": sum(r.qc_status == "pass" for r in rows),
                "fail_count": sum(r.qc_status == "fail" for r in rows),
                "available_count": sum(r.release_decision == "available" for r in rows),
                "pending_review_count": sum(
                    r.release_decision == "pending_review" for r in rows
                ),
                "excluded_count": sum(r.release_decision == "excluded" for r in rows),
                "production_ready": outputs.production_ready,
            }
        )
    return config


@dataclass(frozen=True)
class DatasetQCRunResult:
    output_dir: Path
    outputs: DatasetQCOutputs
    checksum_mode: ArtifactChecksumMode

    def to_dict(self) -> dict[str, object]:
        return {
            **dataset_qc_configuration(
                self.outputs.manifest, self.checksum_mode, self.outputs
            ),
            "status": "completed",
            "outputs": {
                role: str(self.output_dir / filename)
                for role, filename in OUTPUT_FILES.items()
                if role != DERIVED_ROLE or self.outputs.production_ready
            },
            "trajectory_passes": 0,
        }


def _preflight(
    output_dir: Path,
    inputs: tuple[ArtifactInventoryFileSpec, ...],
    overwrite: bool,
) -> None:
    paths = [
        output_dir / n
        for n in (
            *OUTPUT_FILES.values(),
            "artifact_inventory.json",
            "run_provenance.json",
        )
    ]
    if any(
        p.resolve() == s.local_path.resolve()
        or (p.exists() and s.local_path.exists() and p.samefile(s.local_path))
        for p in paths
        for s in inputs
    ):
        raise ValueError("Output must not replace QC inputs")
    if any(p.is_symlink() or (p.exists() and not p.is_file()) for p in paths):
        raise ValueError("Output targets must be regular files without symlinks")
    if not overwrite and any(os.path.lexists(p) for p in paths):
        raise ValueError("Target already exists; use --overwrite")
    provenance_path = output_dir / "run_provenance.json"
    if provenance_path.exists() and (
        read_run_provenance(provenance_path).workflow != DATASET_QC_WORKFLOW
    ):
        raise ValueError("A dedicated Dataset QC output root is required")


def run_dataset_qc(
    manifest_path: Path,
    output_dir: Path,
    *,
    checksum_mode: ArtifactChecksumMode = "none",
    overwrite: bool = False,
) -> DatasetQCRunResult:
    if checksum_mode not in ("none", "sha256") or type(overwrite) is not bool:
        raise DatasetQCWorkflowError("Dataset QC manifest failed: invalid run options")
    manifest = load_dataset_qc_manifest(manifest_path)
    input_specs = collect_dataset_qc_input_specs(manifest, manifest_path)
    try:
        _preflight(output_dir, input_specs, overwrite)
    except (OSError, ValueError):
        raise DatasetQCWorkflowError(
            "Dataset QC export write failed: output preflight failed."
        ) from None
    started = datetime.now(UTC)
    run_id = "dataset-qc-" + started.strftime("%Y%m%dT%H%M%S%fZ")
    software = get_software_identity()
    outputs: DatasetQCOutputs | None = None
    written: list[ArtifactInventoryFileSpec] = []
    failure: str | None = None
    try:
        outputs = execute_dataset_qc_manifest(manifest, manifest_path)
        # Validate serialization of every model before the first scientific write.
        dataset_qc_decision_set_bytes(outputs.decisions)
        dataset_qc_summary_csv_bytes(outputs.summary)
        if outputs.derived_manifest is not None:
            replica_aggregation_manifest_payload(
                outputs.derived_manifest,
                output_dir / OUTPUT_FILES[DERIVED_ROLE],
            )
        elif (output_dir / OUTPUT_FILES[DERIVED_ROLE]).exists():
            raise DatasetQCWorkflowError(
                "Dataset QC export write failed: pending review requires an output "
                "root without a previous derived aggregation manifest."
            )
        for role, filename in OUTPUT_FILES.items():
            target = output_dir / filename
            if role == DECISION_ROLE:
                result = write_dataset_qc_decision_set(
                    outputs.decisions,
                    target,
                    overwrite=overwrite,
                )
            elif role == SUMMARY_ROLE:
                result = write_dataset_qc_summary_csv(
                    outputs.summary,
                    target,
                    overwrite=overwrite,
                )
            elif outputs.derived_manifest is not None:
                result = write_replica_aggregation_manifest(
                    outputs.derived_manifest,
                    target,
                    overwrite=overwrite,
                )
            else:
                continue
            if not result.written:
                raise ValueError("QC artifact write failed")
            written.append(
                ArtifactInventoryFileSpec(
                    f"output:{role}",
                    "output",
                    role,
                    target,
                    filename,
                    "csv" if role == SUMMARY_ROLE else "json",
                )
            )
    except DatasetQCWorkflowError as exc:
        failure = str(exc)
    except Exception:
        failure = "Dataset QC export write failed: output construction/write failed."
    references = [PortableArtifactReference(s.role, s.path) for s in written]
    try:
        inventory = build_artifact_inventory(
            run_id=run_id,
            workflow=DATASET_QC_WORKFLOW,
            inventory_path="artifact_inventory.json",
            file_specs=input_specs + tuple(written),
            checksum_mode=checksum_mode,
        )
        if not write_artifact_inventory(
            inventory, output_dir, overwrite=overwrite
        ).written:
            raise ValueError("Inventory write failed")
        references.append(
            PortableArtifactReference(
                "artifact_inventory",
                "artifact_inventory.json",
            )
        )
    except Exception:
        failure = failure or "Dataset QC export write failed: inventory failed."
    try:
        provenance = RunProvenance(
            run_id=run_id,
            workflow=DATASET_QC_WORKFLOW,
            status="failed" if failure else "completed",
            started_at_utc=started,
            ended_at_utc=datetime.now(UTC),
            software_identity=software,
            command=(
                "mania",
                "dataset",
                "qc",
                "--manifest",
                MANIFEST_PORTABLE_PATH,
                "--output",
                ".",
                "--artifact-checksum-mode",
                checksum_mode,
            )
            + (("--overwrite",) if overwrite else ()),
            resolved_configuration=dataset_qc_configuration(
                manifest,
                checksum_mode,
                outputs,
            ),
            conditions=(),
            artifact_references=tuple(references),
            issues=(
                RunProvenanceIssue(
                    "error",
                    "dataset_qc_failed",
                    "Dataset QC run failed.",
                    "dataset_qc",
                    None,
                ),
            )
            if failure
            else (),
        )
        if not write_run_provenance(
            provenance, output_dir, overwrite=overwrite
        ).written:
            raise ValueError("Provenance write failed")
    except Exception:
        failure = failure or "Dataset QC export write failed: provenance failed."
    if failure:
        raise DatasetQCWorkflowError(failure)
    assert outputs is not None
    return DatasetQCRunResult(output_dir, outputs, checksum_mode)
