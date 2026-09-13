"""Cycle-free release persistence and narrow adapters to unchanged generic models."""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mania._version import __version__
from mania.artifact_inventory import ArtifactChecksumMode
from mania.artifact_inventory_io import (
    ArtifactInventoryFileSpec,
    build_artifact_inventory,
    write_artifact_inventory,
)
from mania.dataset_release_contract import PUBLICATION_ARTIFACT_REGISTRY
from mania.dataset_release_csv import write_publication_csv
from mania.dataset_release_manifest import (
    EXPORT_MANIFEST_FILENAME,
    RELEASE_INVENTORY_PATH,
    RELEASE_MANIFEST_PATH,
    RELEASE_PROVENANCE_PATH,
)
from mania.dataset_release_manifest_io import (
    release_json_text,
    write_dataset_release_manifest,
)
from mania.dataset_release_workflow import (
    DatasetReleaseBundle,
    DatasetReleaseError,
    build_dataset_release,
)
from mania.preprocessing.molecular_partner_metadata_io import write_atomic_text
from mania.run_provenance import PortableArtifactReference, RunProvenance
from mania.software_identity import DISTRIBUTION_NAME, SOFTWARE_NAME, SoftwareIdentity

DATASET_RELEASE_WORKFLOW = "dataset_release"
EXPORT_CONTROL_ARTIFACT_ID = "input:dataset_release_export_manifest"
EXPORT_CONTROL_PORTABLE_PATH = f"inputs/{EXPORT_MANIFEST_FILENAME}"


def release_run_id(bundle: DatasetReleaseBundle) -> str:
    # Stable release identity keeps inventories deterministic without hashing.
    return (
        f"dataset-release:{bundle.manifest.dataset_id}:"
        f"{bundle.manifest.release_version}"
    )


def release_configuration(
    bundle: DatasetReleaseBundle, mode: ArtifactChecksumMode
) -> dict[str, object]:
    control = bundle.control
    payload = {
        "workflow": DATASET_RELEASE_WORKFLOW,
        **{
            k: v
            for k, v in bundle.manifest.to_dict().items()
            if k
            not in (
                "schema_version",
                "kind",
                "publication_artifacts",
            )
        },
        "export_control_manifest_path": EXPORT_CONTROL_PORTABLE_PATH,
        "upstream_reference_base": "export_control_manifest_parent",
        "stage32_run": control.to_dict()["stage32_run"],
        "stage31_run": control.to_dict()["stage31_run"],
        "aggregation_manifest_used_path": control.aggregation_manifest_used_path,
        **bundle.counts,
        "production_aggregate_lineage_verified": True,
        "trajectory_passes": 0,
        "artifact_checksum_mode": mode,
    }
    return dict(json.loads(release_json_text(payload)))


def release_output_specs(
    bundle: DatasetReleaseBundle, root: Path
) -> tuple[ArtifactInventoryFileSpec, ...]:
    return tuple(
        ArtifactInventoryFileSpec(
            f"output:{a.artifact_id}",
            "output",
            a.artifact_id,
            root / a.relative_path,
            a.relative_path,
            a.mandatory_encoding,
        )
        for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts
        if a.relative_path not in (RELEASE_INVENTORY_PATH, RELEASE_PROVENANCE_PATH)
    )


def release_references(
    bundle: DatasetReleaseBundle,
) -> tuple[PortableArtifactReference, ...]:
    return (
        *(
            PortableArtifactReference(s.role, s.path)
            for s in release_output_specs(bundle, Path("."))
        ),
        PortableArtifactReference("artifact_inventory", RELEASE_INVENTORY_PATH),
    )


def require_release_tree(root: Path, *, complete: bool) -> None:
    """Inspect only the output tree for extras; never discover authority from files."""
    expected = {a.relative_path for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts}
    allowed_dirs = {str(Path(p).parent) for p in expected}
    present = set()
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("Release output path must not traverse symlinks")
    if root.exists():
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ValueError("Release tree must not contain symlinks")
            if path.is_dir() and relative in allowed_dirs:
                continue
            if not path.is_file() or relative not in expected:
                raise ValueError("Unregistered release output artifact")
            present.add(relative)
    if complete and present != expected:
        raise ValueError("Completed release requires exactly 17 CSV and 3 JSON files")


@dataclass(frozen=True)
class DatasetReleaseRunResult:
    bundle: DatasetReleaseBundle
    output_dir: Path
    checksum_mode: ArtifactChecksumMode

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.bundle.manifest.dataset_id,
            "release_version": self.bundle.manifest.release_version,
            "status": "completed",
            **self.bundle.counts,
            "production_aggregate_lineage_verified": True,
            "artifact_checksum_mode": self.checksum_mode,
            "output_root": str(self.output_dir),
            "trajectory_passes": 0,
        }


def run_dataset_release(
    manifest_path: Path,
    output_dir: Path,
    *,
    checksum_mode: ArtifactChecksumMode = "none",
    overwrite: bool = False,
) -> DatasetReleaseRunResult:
    if checksum_mode not in ("none", "sha256") or type(overwrite) is not bool:
        raise DatasetReleaseError(
            "Dataset release manifest failed: invalid run options."
        )
    bundle = build_dataset_release(manifest_path)
    started = datetime.now(UTC)
    writes_started = False
    try:
        require_release_tree(output_dir, complete=False)
        if not overwrite and any(
            os.path.lexists(output_dir / a.relative_path)
            for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts
        ):
            raise ValueError("Target already exists; use --overwrite")

        # All authority files must remain outside the dedicated release root.
        def paths(value: object) -> Iterator[Path]:
            if isinstance(value, dict):
                for name, item in value.items():
                    if (name.endswith("_path") or name == "path") and isinstance(
                        item, str
                    ):
                        yield manifest_path.parent / item
                    else:
                        yield from paths(item)
            elif isinstance(value, (tuple, list)):
                for item in value:
                    yield from paths(item)

        inputs = (
            manifest_path,
            *paths(bundle.control.to_dict()),
            *(manifest_path.parent / p for p in bundle.control.temporal_evidence_paths),
        )
        targets = [
            output_dir / a.relative_path
            for a in PUBLICATION_ARTIFACT_REGISTRY.artifacts
        ]
        if any(p.resolve().is_relative_to(output_dir.resolve()) for p in inputs) or any(
            p.exists() and target.exists() and p.samefile(target)
            for p in inputs
            for target in targets
        ):
            raise ValueError("Release output must not replace authority inputs")
        # The manifest is the completion declaration. Invalidate it before an
        # explicitly requested overwrite and never retain it on a later failure.
        if overwrite:
            for name in (
                RELEASE_MANIFEST_PATH,
                RELEASE_INVENTORY_PATH,
                RELEASE_PROVENANCE_PATH,
            ):
                (output_dir / name).unlink(missing_ok=True)
        writes_started = True
        for table in bundle.tables:
            write_publication_csv(
                table, output_dir / table.relative_path, overwrite=overwrite
            )
        if not write_dataset_release_manifest(
            bundle.manifest,
            output_dir / RELEASE_MANIFEST_PATH,
            overwrite=overwrite,
        ).written:
            raise ValueError("Dataset manifest write failed")
        inventory = build_artifact_inventory(
            run_id=release_run_id(bundle),
            workflow=DATASET_RELEASE_WORKFLOW,
            inventory_path=RELEASE_INVENTORY_PATH,
            file_specs=release_output_specs(bundle, output_dir),
            checksum_mode=checksum_mode,
        )
        if not write_artifact_inventory(
            inventory, output_dir, overwrite=overwrite
        ).written:
            raise ValueError("Release inventory write failed")
        provenance = RunProvenance(
            run_id=release_run_id(bundle),
            workflow=DATASET_RELEASE_WORKFLOW,
            status="completed",
            started_at_utc=started,
            ended_at_utc=datetime.now(UTC),
            software_identity=SoftwareIdentity(
                SOFTWARE_NAME,
                DISTRIBUTION_NAME,
                __version__,
                None,
                "unavailable",
                "unavailable",
            ),
            command=(
                "mania",
                "dataset",
                "publish",
                "--manifest",
                EXPORT_CONTROL_PORTABLE_PATH,
                "--output",
                ".",
                "--artifact-checksum-mode",
                checksum_mode,
            ),
            resolved_configuration=release_configuration(bundle, checksum_mode),
            conditions=tuple(
                dict.fromkeys(
                    str(r["condition"])
                    for r in bundle.metadata.systems.records()
                    if r["condition"] is not None
                )
            ),
            artifact_references=release_references(bundle),
        )
        if not write_atomic_text(
            release_json_text(provenance.to_dict()),
            output_dir / RELEASE_PROVENANCE_PATH,
            overwrite=overwrite,
        ).written:
            raise ValueError("Release provenance write failed")
        require_release_tree(output_dir, complete=True)
    except Exception:
        if writes_started:
            for name in (
                RELEASE_MANIFEST_PATH,
                RELEASE_INVENTORY_PATH,
                RELEASE_PROVENANCE_PATH,
            ):
                try:
                    (output_dir / name).unlink(missing_ok=True)
                except OSError:
                    pass
        raise DatasetReleaseError(
            "Dataset release write failed: release is incomplete."
        ) from None
    return DatasetReleaseRunResult(bundle, output_dir, checksum_mode)
