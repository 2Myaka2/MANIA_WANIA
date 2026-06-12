"""Skip controls for local-only scientific tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from _harness import (
    local_reference_package_available,
    local_scientific_enabled,
    mdanalysis_available,
)

LOCAL_SCIENTIFIC_DIR = Path(__file__).resolve().parent
LOCAL_DISABLED_REASON = (
    "local scientific tests are disabled; set MANIA_RUN_LOCAL_SCIENTIFIC=1"
)
MDANALYSIS_UNAVAILABLE_REASON = (
    "MDAnalysis is unavailable; install the optional md or science extra"
)
REAL_DATA_UNAVAILABLE_REASON = (
    "local real MD data is unavailable; set MANIA_LOCAL_REFERENCE_PACKAGE "
    "to an existing directory"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply deterministic skips only within the local scientific directory."""
    local_items = [
        item
        for item in items
        if Path(str(item.path)).resolve().is_relative_to(LOCAL_SCIENTIFIC_DIR)
    ]
    if not local_scientific_enabled():
        skip = pytest.mark.skip(reason=LOCAL_DISABLED_REASON)
        for item in local_items:
            item.add_marker(skip)
        return

    for item in local_items:
        if (
            item.get_closest_marker("requires_mdanalysis") is not None
            and not mdanalysis_available()
        ):
            item.add_marker(
                pytest.mark.skip(reason=MDANALYSIS_UNAVAILABLE_REASON)
            )
        if (
            item.get_closest_marker("requires_real_md_data") is not None
            and not local_reference_package_available()
        ):
            item.add_marker(
                pytest.mark.skip(reason=REAL_DATA_UNAVAILABLE_REASON)
            )
