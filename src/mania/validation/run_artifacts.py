"""Stage 25.D.1 technical integrity and references, without scientific validation."""

import stat
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from mania.artifact_inventory import (
    ArtifactChecksumMode,
    ArtifactDirection,
    ArtifactInventory,
    ArtifactInventoryEntry,
)
from mania.artifact_inventory_io import (
    ArtifactInventoryReadError,
    read_artifact_inventory,
    stream_file_sha256,
)
from mania.run_provenance import PortableArtifactReference, RunProvenance
from mania.run_provenance_io import RunProvenanceReadError, read_run_provenance

PREPROCESSING_VALIDATION_SCOPE = "preprocessing"
ANALYSIS_VALIDATION_SCOPE = "analysis"

ArtifactValidationScope = Literal["preprocessing", "analysis"]
ArtifactSetValidationStatus = Literal["passed", "partial", "failed"]
ArtifactResolutionStatus = Literal["resolved", "not_resolved"]


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty stripped string")


def _scope(value: object) -> None:
    if value not in (PREPROCESSING_VALIDATION_SCOPE, ANALYSIS_VALIDATION_SCOPE):
        raise ValueError("scope must be preprocessing or analysis")


@dataclass(frozen=True)
class ArtifactSetValidationIssue:
    """Portable technical diagnostic; never captures an underlying exception."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    artifact_id: str | None = None
    path: str | None = None
    condition: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning"):
            raise ValueError("severity must be error or warning")
        _text(self.code, "code")
        _text(self.message, "message")
        for name in ("artifact_id", "condition"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if self.path is not None:
            PortableArtifactReference("validation_issue", self.path)

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "artifact_id": self.artifact_id,
            "path": self.path,
            "condition": self.condition,
        }


@dataclass(frozen=True)
class ArtifactSetValidationRecord:
    """Integrity observations for one declared artifact, without its local path."""

    artifact_id: str
    direction: ArtifactDirection
    role: str
    path: str
    condition: str | None
    resolution_status: ArtifactResolutionStatus
    exists: bool | None
    byte_size_expected: int
    byte_size_actual: int | None
    byte_size_matches: bool | None
    sha256_expected: str | None
    sha256_checked: bool
    sha256_matches: bool | None

    def __post_init__(self) -> None:
        # Reuse the accepted identity/size/checksum constraints; format is not reported.
        ArtifactInventoryEntry(
            self.artifact_id,
            self.direction,
            self.role,
            self.path,
            "bin",
            self.byte_size_expected,
            self.sha256_expected,
            self.condition,
        )
        if self.resolution_status not in ("resolved", "not_resolved"):
            raise ValueError("invalid resolution_status")
        for name in ("exists", "byte_size_matches", "sha256_matches"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"{name} must be bool or None")
        if type(self.sha256_checked) is not bool:
            raise ValueError("sha256_checked must be bool")
        if self.byte_size_actual is not None and (
            type(self.byte_size_actual) is not int or self.byte_size_actual < 0
        ):
            raise ValueError("byte_size_actual must be a non-negative integer or None")
        if self.resolution_status == "not_resolved":
            if (
                self.direction != "input"
                or self.sha256_checked
                or any(
                    value is not None
                    for value in (
                        self.exists,
                        self.byte_size_actual,
                        self.byte_size_matches,
                        self.sha256_matches,
                    )
                )
            ):
                raise ValueError("unresolved inputs must have no file observations")
        elif self.exists is None:
            raise ValueError("resolved artifacts require an existence result")
        expected_match = (
            None
            if self.byte_size_actual is None
            else self.byte_size_actual == self.byte_size_expected
        )
        if self.byte_size_matches is not expected_match:
            raise ValueError("byte_size_matches must agree with observed size")
        if self.byte_size_actual is not None and self.exists is not True:
            raise ValueError("observed size requires an existing file")
        if self.sha256_checked:
            if self.sha256_expected is None or self.byte_size_actual is None:
                raise ValueError(
                    "checksum verification requires a declared hash and file"
                )
        elif self.sha256_matches is not None:
            raise ValueError("unchecked checksum must have no match result")

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "direction": self.direction,
            "role": self.role,
            "path": self.path,
            "condition": self.condition,
            "resolution_status": self.resolution_status,
            "exists": self.exists,
            "byte_size_expected": self.byte_size_expected,
            "byte_size_actual": self.byte_size_actual,
            "byte_size_matches": self.byte_size_matches,
            "sha256_expected": self.sha256_expected,
            "sha256_checked": self.sha256_checked,
            "sha256_matches": self.sha256_matches,
        }


@dataclass(frozen=True)
class ArtifactSetValidationReport:
    """Technical checks only: passing never certifies scientific acceptance."""

    scope: ArtifactValidationScope
    run_id: str | None
    workflow: str | None
    provenance_path: str
    inventory_path: str
    checksum_mode: ArtifactChecksumMode | None
    artifact_records: tuple[ArtifactSetValidationRecord, ...]
    issues: tuple[ArtifactSetValidationIssue, ...]
    status: ArtifactSetValidationStatus = field(init=False)

    def __post_init__(self) -> None:
        _scope(self.scope)
        for name in ("run_id", "workflow"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        for path in (self.provenance_path, self.inventory_path):
            PortableArtifactReference("validation_metadata", path)
        if self.checksum_mode not in (None, "none", "sha256"):
            raise ValueError("invalid checksum_mode")
        for name, model in (
            ("artifact_records", ArtifactSetValidationRecord),
            ("issues", ArtifactSetValidationIssue),
        ):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                type(v) is model for v in values
            ):
                raise ValueError(f"{name} must be a tuple of {model.__name__}")
        ids = [record.artifact_id for record in self.artifact_records]
        paths = [record.path for record in self.artifact_records]
        if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
            raise ValueError("artifact record IDs and paths must be unique")
        if not self.error_count and None in (
            self.run_id,
            self.workflow,
            self.checksum_mode,
        ):
            raise ValueError("unavailable metadata requires an error issue")
        status: ArtifactSetValidationStatus = (
            "failed"
            if self.error_count
            else "partial"
            if self.unresolved_input_count
            else "passed"
        )
        object.__setattr__(self, "status", status)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    @property
    def complete(self) -> bool:
        return self.checksum_mode is not None and self.unresolved_input_count == 0

    @property
    def artifact_count(self) -> int:
        return len(self.artifact_records)

    @property
    def resolved_artifact_count(self) -> int:
        return sum(r.resolution_status == "resolved" for r in self.artifact_records)

    @property
    def unresolved_input_count(self) -> int:
        return sum(r.resolution_status == "not_resolved" for r in self.artifact_records)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "run_id": self.run_id,
            "workflow": self.workflow,
            "status": self.status,
            "provenance_path": self.provenance_path,
            "inventory_path": self.inventory_path,
            "checksum_mode": self.checksum_mode,
            "artifact_records": [record.to_dict() for record in self.artifact_records],
            "issues": [issue.to_dict() for issue in self.issues],
            "passed": self.passed,
            "complete": self.complete,
            "artifact_count": self.artifact_count,
            "resolved_artifact_count": self.resolved_artifact_count,
            "unresolved_input_count": self.unresolved_input_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


def _entry_issue(
    entry: ArtifactInventoryEntry,
    code: str,
    message: str,
) -> ArtifactSetValidationIssue:
    return ArtifactSetValidationIssue(
        "error",
        code,
        message,
        entry.artifact_id,
        entry.path,
        entry.condition,
    )


def _check_references(
    provenance: RunProvenance,
    inventory: ArtifactInventory,
    provenance_path: str,
    inventory_path: str,
) -> list[ArtifactSetValidationIssue]:
    issues: list[ArtifactSetValidationIssue] = []
    if inventory.run_id != provenance.run_id:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "run_id_mismatch",
                "Inventory and provenance run IDs differ.",
            )
        )
    if inventory.workflow != provenance.workflow:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "workflow_mismatch",
                "Inventory and provenance workflows differ.",
            )
        )
    if inventory.inventory_path != inventory_path:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "inventory_path_mismatch",
                "Inventory declares a different location from the selected scope.",
                path=inventory_path,
            )
        )
    references = [
        r for r in provenance.artifact_references if r.role == "artifact_inventory"
    ]
    if not references:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "missing_inventory_reference",
                "Provenance has no inventory reference.",
                path=inventory_path,
            )
        )
    elif len(references) > 1:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "duplicate_inventory_reference",
                "Provenance has more than one inventory reference.",
                path=inventory_path,
            )
        )
    if any(reference.path != inventory_path for reference in references):
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "invalid_inventory_reference",
                "Provenance inventory reference does not match the selected scope.",
                path=inventory_path,
            )
        )
    output_paths = {e.path for e in inventory.artifacts if e.direction == "output"}
    for reference in provenance.artifact_references:
        if (
            reference.role != "artifact_inventory"
            and reference.path not in output_paths
        ):
            issues.append(
                ArtifactSetValidationIssue(
                    "error",
                    "provenance_reference_not_in_inventory",
                    "Provenance artifact reference has no matching inventory output.",
                    path=reference.path,
                )
            )
    for entry in inventory.artifacts:
        # Also protect the actual inventory location if its declared root path is wrong.
        if entry.path == inventory_path:
            issues.append(
                _entry_issue(
                    entry,
                    "inventory_self_reference",
                    "Inventory must not contain itself.",
                )
            )
        if entry.path == provenance_path:
            issues.append(
                _entry_issue(
                    entry,
                    "provenance_inventory_cycle",
                    "Inventory must not contain its corresponding provenance.",
                )
            )
        if entry.condition is not None and entry.condition not in provenance.conditions:
            issues.append(
                _entry_issue(
                    entry,
                    "artifact_condition_not_in_run",
                    "Artifact condition is absent from provenance conditions.",
                )
            )
    return issues


def _check_artifact(
    entry: ArtifactInventoryEntry,
    local_path: Path | None,
) -> tuple[ArtifactSetValidationRecord, list[ArtifactSetValidationIssue]]:
    record = ArtifactSetValidationRecord(
        artifact_id=entry.artifact_id,
        direction=entry.direction,
        role=entry.role,
        path=entry.path,
        condition=entry.condition,
        resolution_status="not_resolved" if local_path is None else "resolved",
        exists=None if local_path is None else False,
        byte_size_expected=entry.byte_size,
        byte_size_actual=None,
        byte_size_matches=None,
        sha256_expected=entry.sha256,
        sha256_checked=False,
        sha256_matches=None,
    )
    if local_path is None:
        return record, []
    try:
        observed = local_path.stat()
    except (FileNotFoundError, NotADirectoryError):
        return record, [
            _entry_issue(entry, "artifact_missing", "Artifact file is missing.")
        ]
    except OSError:
        return record, [
            _entry_issue(
                entry,
                "artifact_stat_error",
                "Artifact file metadata could not be inspected.",
            )
        ]
    record = replace(record, exists=True)
    if not stat.S_ISREG(observed.st_mode):
        return record, [
            _entry_issue(entry, "artifact_not_file", "Artifact is not a regular file.")
        ]
    record = replace(
        record,
        byte_size_actual=observed.st_size,
        byte_size_matches=observed.st_size == entry.byte_size,
    )
    issues: list[ArtifactSetValidationIssue] = []
    if not record.byte_size_matches:
        issues.append(
            _entry_issue(
                entry,
                "artifact_size_mismatch",
                "Artifact byte size does not match inventory.",
            )
        )
    if entry.sha256 is not None:
        record = replace(record, sha256_checked=True)
        try:
            digest = stream_file_sha256(local_path)
        except (OSError, ValueError):
            issues.append(
                _entry_issue(
                    entry,
                    "artifact_checksum_error",
                    "Artifact SHA256 could not be verified.",
                )
            )
        else:
            record = replace(record, sha256_matches=digest == entry.sha256)
            if not record.sha256_matches:
                issues.append(
                    _entry_issue(
                        entry,
                        "artifact_checksum_mismatch",
                        "Artifact SHA256 does not match inventory.",
                    )
                )
    return record, issues


def validate_run_artifact_integrity(
    run_root: Path,
    *,
    scope: ArtifactValidationScope,
    input_artifact_paths: Mapping[str, Path] | None = None,
) -> ArtifactSetValidationReport:
    """Check only declared files; unmapped external inputs remain unresolved."""
    if type(run_root) is not type(Path()):
        raise ValueError("run_root must be an exact Path")
    _scope(scope)
    if input_artifact_paths is not None and not isinstance(
        input_artifact_paths, Mapping
    ):
        raise ValueError("input_artifact_paths must be a mapping or None")
    mappings = {} if input_artifact_paths is None else dict(input_artifact_paths)
    if any(not isinstance(key, str) for key in mappings):
        raise ValueError("input_artifact_paths keys must be strings")
    if any(type(value) is not type(Path()) for value in mappings.values()):
        raise ValueError("input_artifact_paths values must be exact Path")
    prefix = "analysis/" if scope == ANALYSIS_VALIDATION_SCOPE else ""
    provenance_path = prefix + "run_provenance.json"
    inventory_path = prefix + "artifact_inventory.json"
    issues: list[ArtifactSetValidationIssue] = []
    provenance = None
    inventory = None
    try:
        provenance = read_run_provenance(run_root / provenance_path)
    except RunProvenanceReadError:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "provenance_read_error",
                "Run provenance could not be read as the supported contract.",
                path=provenance_path,
            )
        )
    try:
        inventory = read_artifact_inventory(run_root / inventory_path)
    except ArtifactInventoryReadError:
        issues.append(
            ArtifactSetValidationIssue(
                "error",
                "inventory_read_error",
                "Artifact inventory could not be read as the supported contract.",
                path=inventory_path,
            )
        )
    records: list[ArtifactSetValidationRecord] = []
    if inventory is not None:
        input_ids = {
            e.artifact_id for e in inventory.artifacts if e.direction == "input"
        }
        unknown_count = len(mappings.keys() - input_ids)
        if unknown_count:
            issues.append(
                ArtifactSetValidationIssue(
                    "error",
                    "unknown_input_artifact_mapping",
                    f"Mapping keys absent from inventory input IDs: {unknown_count}.",
                )
            )
        if provenance is not None:
            issues.extend(
                _check_references(
                    provenance,
                    inventory,
                    provenance_path,
                    inventory_path,
                )
            )
        for entry in inventory.artifacts:
            # Invalid technical entries are diagnosed, never inventoried or hashed here.
            if entry.path in (provenance_path, inventory_path):
                if provenance is None:
                    issues.append(
                        _entry_issue(
                            entry,
                            "provenance_inventory_cycle"
                            if entry.path == provenance_path
                            else "inventory_self_reference",
                            "Inventory must exclude its technical metadata files.",
                        )
                    )
                continue
            local_path = (
                run_root / entry.path
                if entry.direction == "output"
                else mappings.get(entry.artifact_id)
            )
            record, artifact_issues = _check_artifact(entry, local_path)
            records.append(record)
            issues.extend(artifact_issues)
    unresolved_count = sum(r.resolution_status == "not_resolved" for r in records)
    if unresolved_count:
        issues.append(
            ArtifactSetValidationIssue(
                "warning",
                "external_inputs_not_resolved",
                f"External inputs not resolved: {unresolved_count}.",
            )
        )
    identity = provenance if provenance is not None else inventory
    return ArtifactSetValidationReport(
        scope=scope,
        run_id=None if identity is None else identity.run_id,
        workflow=None if identity is None else identity.workflow,
        provenance_path=provenance_path,
        inventory_path=inventory_path,
        checksum_mode=None if inventory is None else inventory.checksum_mode,
        artifact_records=tuple(records),
        issues=tuple(issues),
    )


__all__ = [
    "PREPROCESSING_VALIDATION_SCOPE",
    "ANALYSIS_VALIDATION_SCOPE",
    "ArtifactValidationScope",
    "ArtifactSetValidationStatus",
    "ArtifactResolutionStatus",
    "ArtifactSetValidationIssue",
    "ArtifactSetValidationRecord",
    "ArtifactSetValidationReport",
    "validate_run_artifact_integrity",
]
