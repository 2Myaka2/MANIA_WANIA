"""Offline full release reconstruction through the same Stage 33.B/C builders."""

from collections.abc import Mapping
from pathlib import Path

from mania.artifact_inventory_io import (
    build_artifact_inventory,
    read_artifact_inventory,
)
from mania.dataset_release_csv import publication_csv_bytes, read_publication_csv
from mania.dataset_release_manifest import RELEASE_MANIFEST_PATH
from mania.dataset_release_manifest_io import (
    read_dataset_release_manifest,
    release_json_text,
)
from mania.dataset_release_run import (
    DATASET_RELEASE_WORKFLOW,
    EXPORT_CONTROL_ARTIFACT_ID,
    EXPORT_CONTROL_PORTABLE_PATH,
    release_configuration,
    release_output_specs,
    release_references,
    release_run_id,
    require_release_tree,
)
from mania.dataset_release_validation import validate_dataset_release_tables
from mania.dataset_release_workflow import build_dataset_release
from mania.run_provenance_io import read_run_provenance
from mania.validation.run_artifacts import validate_run_artifact_integrity
from mania.validation.unified import (
    SpecializedArtifactValidationRecord,
    UnifiedArtifactValidationIssue,
    UnifiedArtifactValidationReport,
)


def validate_dataset_release_run(
    root: Path,
    input_artifact_paths: Mapping[str, Path] | None = None,
) -> UnifiedArtifactValidationReport:
    integrity = validate_run_artifact_integrity(root, scope="dataset_release")
    records: list[SpecializedArtifactValidationRecord] = []
    issues: list[UnifiedArtifactValidationIssue] = []
    try:
        mappings = {} if input_artifact_paths is None else dict(input_artifact_paths)
        if set(mappings) != {EXPORT_CONTROL_ARTIFACT_ID}:
            raise ValueError("An explicit export-control manifest mapping is required")
        require_release_tree(root, complete=True)
        bundle = build_dataset_release(mappings[EXPORT_CONTROL_ARTIFACT_ID])
        observed = {}
        for table in bundle.tables:
            model = read_publication_csv(table.table_id, root / table.relative_path)
            if model != table or (
                root / table.relative_path
            ).read_bytes() != publication_csv_bytes(table):
                raise ValueError("Publication CSV differs from accepted reconstruction")
            observed[table.table_id] = model
            records.append(
                SpecializedArtifactValidationRecord(
                    f"output:{table.table_id}",
                    table.table_id,
                    table.relative_path,
                    None,
                    "read_publication_csv",
                    "passed",
                    0,
                )
            )
        validate_dataset_release_tables(
            type(bundle.metadata)(
                **{t.table_id: observed[t.table_id] for t in bundle.metadata.tables}
            ),
            type(bundle.science)(
                **{t.table_id: observed[t.table_id] for t in bundle.science.tables}
            ),
            bundle.aggregation_authority,
            bundle.control,
        )
        if read_dataset_release_manifest(
            root / RELEASE_MANIFEST_PATH
        ) != bundle.manifest or (
            (root / RELEASE_MANIFEST_PATH).read_bytes()
            != release_json_text(bundle.manifest.to_dict()).encode("utf-8")
        ):
            raise ValueError("Release manifest differs from exact reconstruction")
        inventory = read_artifact_inventory(root / integrity.inventory_path)
        expected_inventory = build_artifact_inventory(
            run_id=release_run_id(bundle),
            workflow=DATASET_RELEASE_WORKFLOW,
            inventory_path=integrity.inventory_path,
            file_specs=release_output_specs(bundle, root),
            checksum_mode=inventory.checksum_mode,
        )
        if inventory != expected_inventory:
            raise ValueError(
                "Release inventory differs from exact successful output graph"
            )
        provenance = read_run_provenance(root / integrity.provenance_path)
        expected_command = (
            "mania",
            "dataset",
            "publish",
            "--manifest",
            EXPORT_CONTROL_PORTABLE_PATH,
            "--output",
            ".",
            "--artifact-checksum-mode",
            inventory.checksum_mode,
        )
        conditions = tuple(
            dict.fromkeys(
                str(r["condition"])
                for r in bundle.metadata.systems.records()
                if r["condition"] is not None
            )
        )
        if release_json_text(
            provenance.to_dict()["resolved_configuration"]
        ) != release_json_text(
            release_configuration(
                bundle,
                inventory.checksum_mode,
            )
        ) or (
            provenance.workflow != DATASET_RELEASE_WORKFLOW
            or provenance.run_id != release_run_id(bundle)
            or provenance.status != "completed"
            or provenance.issues
            or provenance.sampling_by_condition
            or provenance.command != expected_command
            or provenance.conditions != conditions
            or provenance.artifact_references != release_references(bundle)
        ):
            raise ValueError("Release provenance differs from authority and outputs")
        if not integrity.passed or not integrity.complete:
            raise ValueError("Release integrity failed")
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        issues.append(
            UnifiedArtifactValidationIssue(
                "error",
                "dataset_release_reconstruction_failed",
                "Release authority, tables or technical metadata differ.",
            )
        )
    return UnifiedArtifactValidationReport(
        "dataset_release",
        integrity.run_id,
        integrity.workflow,
        integrity,
        tuple(records),
        tuple(issues),
    )
