"""Marker-only smoke tests for the local scientific harness."""

import pytest
from _harness import (
    local_reference_package_available,
    local_scientific_enabled,
    mdanalysis_available,
)


@pytest.mark.local_scientific
def test_local_scientific_harness_is_enabled() -> None:
    assert local_scientific_enabled() is True


@pytest.mark.local_scientific
@pytest.mark.requires_mdanalysis
def test_optional_runtime_marker_path() -> None:
    assert mdanalysis_available() is True


@pytest.mark.local_scientific
@pytest.mark.requires_real_md_data
def test_local_real_data_marker_path() -> None:
    assert local_reference_package_available() is True
