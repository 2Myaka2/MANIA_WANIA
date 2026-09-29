"""GROMACS XTC/TPR/MDP/multiple-LOG correspondence, independent of Egor."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gromacs_wt_runtime import (
    Identity,
    SourceSet,
    StrictModel,
    checked_file,
    identity,
    read_json,
    require,
    valid_head,
)
from pydantic import Field, field_validator, model_validator

STATEMENT = (
    "I confirm that these raw XTC files belong to the listed "
    "GROMACS TPR/run source sets."
)


class Trajectory(StrictModel):
    trajectory_id: str
    xtc: Identity
    tpr: Identity
    mdp: Identity
    logs: list[Identity] = Field(min_length=1)


class Attestation(StrictModel):
    schema_version: Literal["mania.gromacs_source_attestation.v0.1"]
    scope: Literal["source_run_correspondence_only"]
    statement: str
    source_root: str
    trajectories: list[Trajectory] = Field(min_length=1)
    reviewer: str
    review_note: str
    approved_utc: str
    repository_head: str
    authority_inventory: list[Identity] = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reviewer", "review_note")
    @classmethod
    def named(cls, value: str) -> str:
        require(bool(value) and value.strip() == value, "Named reviewer/note required")
        return value

    @model_validator(mode="after")
    def validate_approval(self) -> Attestation:
        require(self.statement == STATEMENT, "Wrong approval statement")
        require(valid_head(self.repository_head), "Invalid repository HEAD")
        approved = datetime.fromisoformat(self.approved_utc)
        require(
            approved.utcoffset() == UTC.utcoffset(approved)
            and approved <= datetime.now(UTC),
            "Invalid approval UTC",
        )
        root = Path(self.source_root)
        require(root.is_absolute() and root.resolve() == root, "Invalid source root")
        names = [r.trajectory_id for r in self.trajectories]
        require(names == sorted(set(names)), "Duplicate/unsorted selections")
        names = [i.path for i in self.authority_inventory]
        require(names == sorted(set(names)), "Duplicate/unsorted authority inventory")
        return self


def digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def capture(source: Path, rows: list[SourceSet]) -> list[dict[str, Any]]:
    """Explicit approval path only: stream complete XTC hashes without decoding."""
    names = [r.trajectory_id for r in rows]
    require(bool(names) and names == sorted(set(names)), "Duplicate/empty selections")
    paths = [
        name
        for row in rows
        for name in [
            row.expected_xtc_path,
            row.tpr.path,
            row.mdp.path,
            *(item.path for item in row.logs),
        ]
    ]
    require(None not in paths, "Unresolved XTC path")

    def snapshot() -> list[tuple[int, ...]]:
        result: list[tuple[int, ...]] = []
        for name in paths:
            assert name is not None
            stat = checked_file(source, name).stat()
            result.append(
                (
                    stat.st_dev,
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                )
            )
        return result

    before = snapshot()
    result = []
    for row in rows:
        require(
            row.expected_xtc_path is not None, f"{row.trajectory_id}: unresolved XTC"
        )
        assert row.expected_xtc_path is not None
        tpr, mdp, *logs = [
            identity(source, i.path) for i in [row.tpr, row.mdp, *row.logs]
        ]
        require(
            [tpr, mdp, *logs] == [row.tpr, row.mdp, *row.logs],
            f"{row.trajectory_id}: small-file authority changed",
        )
        result.append(
            Trajectory(
                trajectory_id=row.trajectory_id,
                xtc=identity(source, row.expected_xtc_path),
                tpr=tpr,
                mdp=mdp,
                logs=logs,
            ).model_dump()
        )
    require(snapshot() == before, "Source set changed during capture")
    return result


def save(
    path: Path,
    *,
    source: Path,
    rows: list[SourceSet],
    reviewer: str,
    review_note: str,
    repository_head: str,
    authority_inventory: list[dict[str, Any]],
) -> None:
    require(
        not path.exists() and not path.is_symlink(),
        f"Existing approval protected: {path}; choose a fresh output directory",
    )
    require(
        bool(reviewer.strip()) and bool(review_note.strip()),
        "Named reviewer/note required",
    )
    payload = dict(
        schema_version="mania.gromacs_source_attestation.v0.1",
        scope="source_run_correspondence_only",
        statement=STATEMENT,
        source_root=str(source),
        trajectories=capture(source, rows),
        reviewer=reviewer,
        review_note=review_note,
        approved_utc=datetime.now(UTC).isoformat(),
        repository_head=repository_head,
        authority_inventory=authority_inventory,
    )
    document = Attestation.model_validate(
        dict(**payload, payload_sha256=digest(payload))
    )
    # Exclusive creation: an interrupted partial write remains fail-closed evidence.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(document.model_dump_json(indent=2) + "\n")


def verify(
    path: Path,
    *,
    source: Path,
    rows: list[SourceSet],
    authority_inventory: list[dict[str, Any]],
    repository_head: str,
) -> dict[str, Any]:
    try:
        require(path.resolve() == path, "Redirected attestation")
        document = Attestation.model_validate(read_json(path)).model_dump()
        checksum = document.pop("payload_sha256")
        require(digest(document) == checksum, "Corrupted attestation checksum")
        require(document["source_root"] == str(source), "Source root changed")
        require(
            document["authority_inventory"] == authority_inventory,
            "Runtime authority changed",
        )
        require(
            document["repository_head"] == repository_head, "Repository HEAD changed"
        )
        # Check mappings before opening any trajectory at a changed path.
        expected = [
            (
                r.trajectory_id,
                r.expected_xtc_path,
                r.tpr.path,
                r.mdp.path,
                [i.path for i in r.logs],
            )
            for r in rows
        ]
        actual = [
            (
                r["trajectory_id"],
                r["xtc"]["path"],
                r["tpr"]["path"],
                r["mdp"]["path"],
                [i["path"] for i in r["logs"]],
            )
            for r in document["trajectories"]
        ]
        require(expected == actual, "Selection/source paths changed")
        require(
            document["trajectories"] == capture(source, rows), "Source identity changed"
        )
        return dict(**document, payload_sha256=checksum)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise ValueError(
            f"Invalid GROMACS source attestation: {exc}. Preserve the existing "
            "approval; new explicit approval requires a fresh output directory."
        ) from exc
