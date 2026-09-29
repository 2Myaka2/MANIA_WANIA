"""Literal WT source authority and metadata-only preflight; no coordinate reader."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SELECTIONS = tuple(
    f"gromacs_wt_{condition}_r{replica}"
    for condition in ("norm", "tumor")
    for replica in (1, 2, 3)
)
REPRESENTATIVE = "gromacs_wt_tumor_r2"
RUNTIME = Path(__file__).resolve().parents[1] / "production/gromacs_wt_runtime"
PENDING = "pending_real_xtc_validation"


def require(ok: object, message: str) -> None:
    if not ok:
        raise ValueError(message)


def relative_path(value: str) -> str:
    p = PurePosixPath(value)
    require(
        bool(value)
        and not p.is_absolute()
        and str(p) == value
        and ".." not in p.parts
        and "\\" not in value
        and not any(ord(c) < 32 for c in value)
        and ":" not in value,
        f"Unsafe relative path: {value!r}",
    )
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Identity(StrictModel):
    path: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    _path = field_validator("path")(relative_path)


class SourceSet(StrictModel):
    trajectory_id: str
    condition: Literal["NORM", "TUMOR"]
    replica: int = Field(ge=1, le=3)
    tpr: Identity
    mdp: Identity
    logs: list[Identity] = Field(min_length=1)
    expected_xtc_path: str | None
    provenance_basis: dict[str, Any]
    unresolved_discrepancies: list[dict[str, Any]]
    coordinate_checks_pending: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def check_paths(self) -> SourceSet:
        require(
            self.trajectory_id
            == f"gromacs_wt_{self.condition.lower()}_r{self.replica}",
            "Condition/replica selection mismatch",
        )
        prefix = PurePosixPath(f"{self.condition}/replica {self.replica}")
        paths = [self.tpr.path, self.mdp.path, *(f.path for f in self.logs)]
        require(self.tpr.path.endswith(".tpr"), "Expected TPR")
        require(self.mdp.path.endswith(".mdp"), "Expected MDP")
        require(all(f.path.endswith(".log") for f in self.logs), "Expected LOG")
        require(
            [f.path for f in self.logs] == sorted(f.path for f in self.logs),
            "LOG order must be deterministic",
        )
        if self.expected_xtc_path is not None:
            relative_path(self.expected_xtc_path)
            require(self.expected_xtc_path.endswith(".xtc"), "Expected XTC")
            paths.append(self.expected_xtc_path)
        require(len(paths) == len(set(paths)), "Duplicate source paths")
        require(
            all(PurePosixPath(p).parent == prefix for p in paths),
            "Source paths must stay in their condition/replica directory",
        )
        return self


class Authority(StrictModel):
    schema_version: Literal["mania.gromacs_wt_runtime.v0.1"]
    intake_status: Literal["PARTIAL", "PASS"]
    analysis_request: dict[str, Any]
    evidence_basis: dict[str, Any]
    trajectories: list[SourceSet]
    coordinate_backend_status: Literal["pending_real_xtc_validation"]
    prepared_storage_format: Literal["OPEN"]

    @model_validator(mode="after")
    def six_only(self) -> Authority:
        require(
            tuple(s.trajectory_id for s in self.trajectories) == SELECTIONS,
            "Authority must contain exactly six ordered WT selections",
        )
        return self


def read_json(path: Path) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def checked_file(root: Path, name: str) -> Path:
    path = root / relative_path(name)
    require(
        path.resolve() == path and path.is_file(),
        f"Missing or redirected source file: {path}",
    )
    require(path.stat().st_size > 0, f"Empty source file: {path}")
    return path


def identity(root: Path, name: str) -> Identity:
    path = checked_file(root, name)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
        after = os.fstat(stream.fileno())
    observed = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    require(
        all(
            getattr(before, f) == getattr(after, f) == getattr(observed, f)
            for f in fields
        )
        and path.resolve() == path,
        f"Source changed during hashing: {path}",
    )
    return Identity(path=name, size_bytes=before.st_size, sha256=sha.hexdigest())


def load_authority(runtime: Path = RUNTIME) -> Authority:
    return Authority.model_validate(read_json(checked_file(runtime, "authority.json")))


def inventory(runtime: Path) -> list[dict[str, Any]]:
    require(
        runtime.is_dir() and runtime.resolve() == runtime,
        "Missing or redirected runtime authority",
    )
    files = sorted(p for p in runtime.rglob("*") if not p.is_dir())
    require(bool(files), "Empty runtime authority")
    return [
        identity(runtime, p.relative_to(runtime).as_posix()).model_dump() for p in files
    ]


def select(authority: Authority, selections: tuple[str, ...]) -> list[SourceSet]:
    require(
        bool(selections) and len(set(selections)) == len(selections),
        "Duplicate/empty selections",
    )
    require(set(selections) <= set(SELECTIONS), "Unknown WT selection")
    return [row for row in authority.trajectories if row.trajectory_id in selections]


def discover(
    source: Path,
    authority: Authority,
    selections: tuple[str, ...] = SELECTIONS,
    *,
    require_xtc: bool = True,
) -> list[SourceSet]:
    """Hash only small files. XTC existence checks never open trajectory bytes."""
    rows = select(authority, selections)
    errors = []
    for row in rows:
        for expected in [row.tpr, row.mdp, *row.logs]:
            try:
                require(
                    identity(source, expected.path) == expected,
                    f"Small-file authority mismatch: {expected.path}",
                )
            except (ValueError, OSError) as exc:
                errors.append(f"{row.trajectory_id}: {exc}")
        if require_xtc:
            if row.expected_xtc_path is None:
                errors.append(f"{row.trajectory_id}: expected XTC path UNRESOLVED")
            else:
                try:
                    checked_file(source, row.expected_xtc_path)
                except (ValueError, OSError) as exc:
                    errors.append(f"{row.trajectory_id}: expected XTC: {exc}")
    require(not errors, "\n".join(errors))
    return rows


def valid_head(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{40,64}", value) is not None
