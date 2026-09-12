"""Strict UTF-8 JSON controls; paths are relative to the manifest location."""

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from mania.canonical_residue_mapping_io import _constant, _object
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    write_atomic_text,
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
from mania.replica_specialized_aggregation import (
    ReplicaSpecializedPartnerCorrespondenceMember,
    SpecializedPartnerCorrespondence,
    SpecializedPartnerCorrespondences,
)


class ReplicaAggregationManifestReadError(ValueError):
    """Invalid or unreadable explicit aggregation controls."""


def _keys(value: Any, model: type[Any]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {f.name for f in fields(model)}:
        raise ValueError("Invalid exact JSON object fields")
    for item in fields(model):
        if not item.init and (
            type(value[item.name]) is not type(item.default)
            or value[item.name] != item.default
        ):
            raise ValueError("Invalid fixed canonical metadata")
    return {f.name: value[f.name] for f in fields(model) if f.init}


def _array(value: Any) -> list[Any]:
    if type(value) is not list:
        raise ValueError("Expected JSON array")
    return value


def _correspondences(value: Any) -> SpecializedPartnerCorrespondences:
    data = _keys(value, SpecializedPartnerCorrespondences)
    items = []
    for item in _array(data["correspondences"]):
        item = _keys(item, SpecializedPartnerCorrespondence)
        item["members"] = tuple(
            ReplicaSpecializedPartnerCorrespondenceMember(
                **_keys(member, ReplicaSpecializedPartnerCorrespondenceMember)
            )
            for member in _array(item["members"])
        )
        items.append(SpecializedPartnerCorrespondence(**item))
    return SpecializedPartnerCorrespondences(tuple(items))


def read_replica_aggregation_manifest(path: str | Path) -> ReplicaAggregationManifest:
    try:
        target = Path(path)
        data = _keys(
            json.loads(
                target.read_text(encoding="utf-8"),
                object_pairs_hook=_object,
                parse_constant=_constant,
            ),
            ReplicaAggregationManifest,
        )
        groups = []
        for group in _array(data["groups"]):
            group = _keys(group, ReplicaAggregationWorkflowGroup)
            spec = _keys(group["spec"], ReplicaAggregationGroupSpec)
            spec["window"] = ReplicaAggregationWindowDefinition(
                **_keys(spec["window"], ReplicaAggregationWindowDefinition)
            )
            spec["expected_replica_ids"] = tuple(_array(spec["expected_replica_ids"]))
            members = []
            for member in _array(group["members"]):
                member = _keys(member, ReplicaAggregationMember)
                member["window"] = ReplicaAggregationWindowDefinition(
                    **_keys(member["window"], ReplicaAggregationWindowDefinition)
                )
                members.append(ReplicaAggregationMember(**member))
            groups.append(
                ReplicaAggregationWorkflowGroup(
                    ReplicaAggregationGroupSpec(**spec),
                    tuple(members),
                    _correspondences(group["lipid_correspondences"]),
                    _correspondences(group["glycan_correspondences"]),
                )
            )
        data["groups"] = tuple(groups)
        for family in ("protein", "lipid", "glycan"):
            key = f"{family}_canonical_table_paths"
            paths = _array(data[key])
            if any(type(p) is not str or not p or p != p.strip() for p in paths):
                raise ValueError("Expected non-empty path strings")
            data[key] = tuple(target.parent / p for p in paths)
        return ReplicaAggregationManifest(**data)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ReplicaAggregationManifestReadError(
            "Invalid or unreadable replica aggregation manifest."
        ) from None


def replica_aggregation_manifest_payload(
    manifest: ReplicaAggregationManifest,
    path: Path,
) -> dict[str, object]:
    if type(manifest) is not ReplicaAggregationManifest:
        raise ValueError("Expected exact ReplicaAggregationManifest")
    manifest.__post_init__()
    payload: dict[str, object] = {
        f.name: getattr(manifest, f.name) for f in fields(manifest) if not f.init
    }
    for family in ("protein", "lipid", "glycan"):
        name = f"{family}_canonical_table_paths"
        payload[name] = [
            Path(os.path.relpath(p, path.resolve().parent)).as_posix()
            for p in getattr(manifest, name)
        ]
    payload["groups"] = [g.to_dict() for g in manifest.groups]
    return payload


def write_replica_aggregation_manifest(
    manifest: ReplicaAggregationManifest,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    target = Path(path)
    payload = replica_aggregation_manifest_payload(manifest, target)
    return write_atomic_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        target,
        overwrite=overwrite,
    )


@dataclass(frozen=True)
class ReplicaAggregationManifestValidationReport:
    manifest_path: Path
    group_count: int | None
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_replica_aggregation_manifest(
    path: str | Path,
) -> ReplicaAggregationManifestValidationReport:
    try:
        manifest = read_replica_aggregation_manifest(path)
    except ReplicaAggregationManifestReadError as exc:
        return ReplicaAggregationManifestValidationReport(Path(path), None, (str(exc),))
    return ReplicaAggregationManifestValidationReport(
        Path(path), len(manifest.groups), ()
    )
