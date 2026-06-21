"""Path helpers for MANIA output artifacts."""

from pathlib import Path

__all__ = [
    "as_path",
    "get_condition_artifact_path",
    "get_condition_output_dir",
    "get_cross_condition_artifact_path",
]


def as_path(path: str | Path) -> Path:
    """Return a string or Path input as a Path."""
    if isinstance(path, Path):
        return path
    return Path(path)


def get_condition_output_dir(output_dir: str | Path, condition: str) -> Path:
    """Return the output directory for one condition."""
    return as_path(output_dir) / condition


def get_condition_artifact_path(
    output_dir: str | Path,
    condition: str,
    artifact_name: str,
) -> Path:
    """Return the path for a per-condition artifact."""
    return get_condition_output_dir(output_dir, condition) / artifact_name


def get_cross_condition_artifact_path(
    output_dir: str | Path,
    artifact_name: str,
) -> Path:
    """Return the path for a cross-condition artifact."""
    return as_path(output_dir) / artifact_name
