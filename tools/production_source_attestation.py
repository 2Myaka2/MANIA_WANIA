"""Exact source/run correspondence approval, separate from preparation and QC."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from mania.preprocessing.molecular_partner_metadata_io import (
    read_strict_json,
    write_atomic_text,
)
from mania.preprocessing.namd_authority import source_identity
from mania.production_catalog import portable_path
from mania.production_run import BoundFile

ROLES = ("trajectory_path", "topology_path", "config_path", "log_path", "box_path")
STATEMENT = (
    "I confirm that these raw DCD files belong to the listed PSF/run source sets."
)


def require(ok: object, message: str) -> None:
    if not ok:
        raise ValueError(message)


class Source(BoundFile):
    binding_path: str

    @field_validator("binding_path")
    @classmethod
    def relative_binding(cls, value: str) -> str:
        portable_path(value)
        return value


class Trajectory(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    trajectory_id: str
    sources: dict[str, Source]


class Attestation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["mania.production_source_attestation.v0.1"]
    scope: Literal["source_run_correspondence_only"]
    statement: Literal[
        "I confirm that these raw DCD files belong to the listed PSF/run source sets."
    ]
    source_root: str
    trajectories: list[Trajectory]
    reviewer: str
    review_note: str
    approved_utc: str
    repository_head: str
    authority_inventory: dict[str, str]
    payload_sha256: str

    @field_validator("reviewer", "review_note")
    @classmethod
    def named(cls, value: str) -> str:
        require(bool(value) and value.strip() == value, "Named reviewer/note required")
        return value


def digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def capture(source: Path, mapping: dict) -> list[dict]:
    """Hash literal source paths; never infer a run from filenames or headers."""
    rows = []
    for tid, roles in sorted(mapping.items()):
        require(set(roles) == set(ROLES), f"{tid}: incomplete source mapping")
        records = {}
        for role, paths in roles.items():
            name = paths["path"]
            path = source / portable_path(name)
            require(
                path.is_file() and path.resolve() == path,
                f"{tid}: missing or redirected {role}: {name}; "
                "new source approval required",
            )
            identity = source_identity(path)
            records[role] = dict(
                **paths, size_bytes=identity.size_bytes, sha256=identity.sha256
            )
        rows.append(dict(trajectory_id=tid, sources=records))
    return rows


def save(
    path: Path,
    *,
    source: Path,
    trajectories: list[dict],
    reviewer: str,
    review_note: str,
    repository_head: str,
    authority_inventory: dict,
) -> None:
    payload = dict(
        schema_version="mania.production_source_attestation.v0.1",
        scope="source_run_correspondence_only",
        statement=STATEMENT,
        source_root=str(source),
        trajectories=trajectories,
        reviewer=reviewer,
        review_note=review_note,
        approved_utc=datetime.now(UTC).isoformat(),
        repository_head=repository_head,
        authority_inventory=authority_inventory,
    )
    document = Attestation.model_validate(
        dict(**payload, payload_sha256=digest(payload))
    )
    result = write_atomic_text(
        document.model_dump_json(indent=2) + "\n", path, overwrite=False
    )
    require(result.passed, f"Source attestation protected: {path}: {result.error}")


def verify(
    path: Path,
    *,
    authority_inventory: dict,
    source: Path | None = None,
    mapping: dict | None = None,
) -> dict:
    """Recheck all bytes, including other replicas, before allowing continuation."""
    try:
        document = Attestation.model_validate(read_strict_json(path)).model_dump()
        checksum = document.pop("payload_sha256")
        require(digest(document) == checksum, "Corrupted source attestation digest")
        require(
            re.fullmatch(r"[0-9a-f]{40,64}", document["repository_head"]),
            "Invalid repository HEAD",
        )
        approved = datetime.fromisoformat(document["approved_utc"])
        require(
            approved.utcoffset() == UTC.utcoffset(approved)
            and approved <= datetime.now(UTC),
            "Invalid approval timestamp",
        )
        root = Path(document["source_root"])
        require(root.is_absolute() and root.resolve() == root, "Invalid source root")
        require(source is None or root == source, "Wrong attested source root")
        require(
            document["authority_inventory"] == authority_inventory,
            "Source attestation authority changed",
        )
        rows = document["trajectories"]
        actual_mapping = {
            row["trajectory_id"]: {
                role: {key: item[key] for key in ("path", "binding_path")}
                for role, item in row["sources"].items()
            }
            for row in rows
        }
        require(
            bool(rows) and len(actual_mapping) == len(rows),
            "Duplicate/empty selections",
        )
        require(
            mapping is None or mapping == actual_mapping,
            "Wrong attested trajectory/source mapping",
        )
        current = capture(root, actual_mapping)
        for expected, observed in zip(rows, current, strict=True):
            require(
                expected["trajectory_id"] == observed["trajectory_id"],
                "Wrong trajectory ordering",
            )
            for role in ROLES:
                require(
                    expected["sources"][role] == observed["sources"][role],
                    f"{expected['trajectory_id']}: {role} source identity/path changed",
                )
        return dict(**document, payload_sha256=checksum)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise ValueError(
            f"Invalid source attestation: {exc}. "
            "New explicit source approval required; "
            "preserve this evidence and choose a fresh OUTPUT_DIR."
        ) from exc


def match_report(document: dict, report: dict, root: Path) -> None:
    tid = report["trajectory_id"]
    selected = [r for r in document["trajectories"] if r["trajectory_id"] == tid]
    require(len(selected) == 1, f"{tid}: missing attested trajectory")
    for role, item in selected[0]["sources"].items():
        expected = dict(
            path=item["binding_path"],
            size_bytes=item["size_bytes"],
            sha256=item["sha256"],
        )
        require(
            report["inputs"][role] == expected
            and (Path(document["source_root"]) / item["path"]).samefile(
                root / item["binding_path"]
            ),
            f"{tid}: attested source/report mapping differs: {role}",
        )
