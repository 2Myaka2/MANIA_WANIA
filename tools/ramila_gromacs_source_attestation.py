"""Immutable GROMACS source/run correspondence; approval covers no PBC/science/QC."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__:
    from . import ramila_gromacs_runtime as rt
else:
    import ramila_gromacs_runtime as rt

STATEMENT = (
    "I confirm that these raw XTC files belong to the listed "
    "GROMACS TPR/run source sets."
)
SCOPE = "source_run_correspondence_only"


def repository_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=rt.REPO, text=True
    ).strip()


def capture(source: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rt.discover(source, rows)
    paths = [r["xtc_path"] for r in rows] + [
        f["path"] for r in rows for f in rt.lightweight(r)
    ]

    def snapshot():
        return [
            (
                rt.checked_file(source, p).stat().st_size,
                rt.checked_file(source, p).stat().st_mtime_ns,
                rt.checked_file(source, p).stat().st_ctime_ns,
            )
            for p in paths
        ]

    before = snapshot()
    result = []
    for row in rows:
        result.append(
            dict(
                trajectory_id=row["trajectory_id"],
                xtc=rt.identity(source, row["xtc_path"]).model_dump(),
                tpr=rt.identity(source, row["tpr"]["path"]).model_dump(),
                mdp=rt.identity(source, row["mdp"]["path"]).model_dump(),
                logs=[rt.identity(source, f["path"]).model_dump() for f in row["logs"]],
                additional_tprs=[
                    rt.identity(source, f["path"]).model_dump()
                    for f in row["additional_tprs"]
                ],
            )
        )
    rt.require(before == snapshot(), "Source changed during complete hashing")
    return result


def save(
    path: Path,
    source: Path,
    rows: list[dict[str, Any]],
    *,
    reviewer: str,
    review_note: str,
    approve: str,
    runtime: Path = rt.RUNTIME,
) -> dict[str, Any]:
    rt.require(approve.lower() == "y", "Source approval declined; no approval saved")
    rt.require(
        tuple(r["trajectory_id"] for r in rows) == rt.SELECTIONS,
        "Normal init requires all 12 final XTCs",
    )
    rt.require(reviewer.strip() == reviewer and bool(reviewer), "Reviewer required")
    rt.require(
        review_note.strip() == review_note and bool(review_note), "Review note required"
    )
    rt.require(
        not path.exists() and not path.is_symlink(),
        "Existing approval protected; use a fresh OUTPUT_ROOT",
    )
    payload = dict(
        schema_version="mania.ramila_gromacs_source_attestation.v1",
        scope=SCOPE,
        statement=STATEMENT,
        source_root=str(source.resolve()),
        reviewer=reviewer,
        review_note=review_note,
        approved_utc=datetime.now(UTC).isoformat(),
        repository_head=repository_head(),
        runtime_inventory=rt.runtime_inventory(runtime),
        trajectories=capture(source, rows),
    )
    document = dict(**payload, payload_sha256=rt.digest(payload))
    rt.dump(path, document)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    return document


def verify(
    path: Path,
    source: Path,
    rows: list[dict[str, Any]],
    *,
    runtime: Path = rt.RUNTIME,
) -> dict[str, Any]:
    rt.require(path.resolve() == path, "Redirected source approval")
    document = rt.read_json(path)
    fields = {
        "schema_version",
        "scope",
        "statement",
        "source_root",
        "reviewer",
        "review_note",
        "approved_utc",
        "repository_head",
        "runtime_inventory",
        "trajectories",
        "payload_sha256",
    }
    rt.require(set(document) == fields, "Invalid source approval fields")
    checksum = document["payload_sha256"]
    payload = {k: v for k, v in document.items() if k != "payload_sha256"}
    rt.require(checksum == rt.digest(payload), "Corrupted source approval")
    rt.require(
        document["schema_version"] == "mania.ramila_gromacs_source_attestation.v1"
        and document["scope"] == SCOPE
        and document["statement"] == STATEMENT,
        "Wrong approval scope",
    )
    for field in ("reviewer", "review_note"):
        value = document[field]
        rt.require(
            isinstance(value, str) and bool(value) and value.strip() == value,
            f"Invalid approval {field}",
        )
    try:
        approved = datetime.fromisoformat(document["approved_utc"])
        rt.require(
            approved.utcoffset() is not None
            and approved.utcoffset().total_seconds() == 0
            and approved <= datetime.now(UTC),
            "Invalid approval timestamp",
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid approval timestamp") from exc
    rt.require(document["source_root"] == str(source.resolve()), "Source root changed")
    rt.require(
        document["runtime_inventory"] == rt.runtime_inventory(runtime),
        "Runtime authority changed",
    )
    rt.require(
        document["repository_head"] == repository_head(),
        "Accepted repository version changed",
    )
    rt.require(
        tuple(r["trajectory_id"] for r in rows) == rt.SELECTIONS,
        "Approval must retain all 12 source mappings",
    )
    # Validate exact paths before opening any changed XTC target.
    expected = [
        (
            r["trajectory_id"],
            r["xtc_path"],
            r["tpr"]["path"],
            r["mdp"]["path"],
            [f["path"] for f in r["logs"]],
            [f["path"] for f in r["additional_tprs"]],
        )
        for r in rows
    ]
    actual = [
        (
            r["trajectory_id"],
            r["xtc"]["path"],
            r["tpr"]["path"],
            r["mdp"]["path"],
            [f["path"] for f in r["logs"]],
            [f["path"] for f in r["additional_tprs"]],
        )
        for r in document["trajectories"]
    ]
    rt.require(expected == actual, "Changed source mapping invalidates approval")
    rt.require(
        document["trajectories"] == capture(source, rows),
        "Changed XTC/TPR/MDP/LOG invalidates continuation",
    )
    return document
