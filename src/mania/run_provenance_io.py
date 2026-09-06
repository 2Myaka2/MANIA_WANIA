"""Atomic, standard-library-only persistence of an immutable run passport."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mania.run_provenance import RUN_PROVENANCE_FILENAME, RunProvenance


@dataclass(frozen=True)
class RunProvenanceWriteResult:
    """Internal write outcome; local paths are not part of the passport."""

    output_path: Path
    written: bool
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise ValueError("output_path must be a Path")
        if type(self.written) is not bool:
            raise ValueError("written must be a bool")
        if self.error is not None and (
            not isinstance(self.error, str)
            or not self.error
            or self.error != self.error.strip()
        ):
            raise ValueError("error must be a non-empty stripped string")
        if self.written != (self.error is None):
            raise ValueError("written must be true exactly when error is absent")

    @property
    def passed(self) -> bool:
        return self.written and self.error is None

    def to_dict(self) -> dict[str, object]:
        return {
            "output_path": str(self.output_path),
            "written": self.written,
            "error": self.error,
            "passed": self.passed,
        }


def write_run_provenance(
    provenance: RunProvenance,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> RunProvenanceWriteResult:
    """Publish complete UTF-8 JSON atomically, without inspecting artifacts."""
    if type(provenance) is not RunProvenance:
        raise ValueError("provenance must be RunProvenance")
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be a bool")
    if not isinstance(output_dir, (str, Path)) or output_dir == "":
        raise ValueError("output_dir must be a Path or non-empty string")
    directory = Path(output_dir)
    target = directory / RUN_PROVENANCE_FILENAME
    temporary: Path | None = None
    error: str | None = None
    try:
        if not overwrite and os.path.lexists(target):
            return RunProvenanceWriteResult(target, False, "Target already exists.")
        payload = (
            json.dumps(
                provenance.to_dict(),
                indent=2,
                sort_keys=False,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=directory,
            prefix=f".{RUN_PROVENANCE_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        if overwrite:
            os.replace(temporary, target)
        else:
            # Atomic publication without clobbering a concurrently created target.
            os.link(temporary, target)
    except FileExistsError:
        error = "Target already exists."
    except OSError:
        error = "Filesystem write failed."
    except (TypeError, ValueError, OverflowError, RecursionError):
        error = "JSON serialization failed."
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                error = "Temporary file cleanup failed."
    return RunProvenanceWriteResult(target, error is None, error)


__all__ = ["RunProvenanceWriteResult", "write_run_provenance"]
