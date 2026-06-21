"""Environment helpers for opt-in local scientific tests."""

from __future__ import annotations

import os
from pathlib import Path

import mania.preprocessing

LOCAL_SCIENTIFIC_ENV = "MANIA_RUN_LOCAL_SCIENTIFIC"
LOCAL_REFERENCE_PACKAGE_ENV = "MANIA_LOCAL_REFERENCE_PACKAGE"
ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def local_scientific_enabled() -> bool:
    """Return whether local scientific tests were explicitly enabled."""
    value = os.environ.get(LOCAL_SCIENTIFIC_ENV, "")
    return value.strip().lower() in ENABLED_VALUES


def local_reference_package_path() -> Path | None:
    """Return the configured local reference package path, if any."""
    value = os.environ.get(LOCAL_REFERENCE_PACKAGE_ENV, "").strip()
    return Path(value) if value else None


def local_reference_package_available() -> bool:
    """Return whether the configured local reference package is a directory."""
    path = local_reference_package_path()
    return path is not None and path.exists() and path.is_dir()


def mdanalysis_available() -> bool:
    """Delegate optional runtime discovery to the preprocessing boundary."""
    return mania.preprocessing.is_mdanalysis_available()


__all__ = [
    "local_reference_package_available",
    "local_reference_package_path",
    "local_scientific_enabled",
    "mdanalysis_available",
]
