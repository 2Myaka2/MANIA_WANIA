"""Opt-in real-data check for loading every manifest condition."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mania.preprocessing import (
    PreprocessingManifestLoadResult,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_load_local_manifest_conditions() -> None:
    package_value = os.environ.get("MANIA_LOCAL_REFERENCE_PACKAGE", "").strip()
    if not package_value:
        pytest.skip("MANIA_LOCAL_REFERENCE_PACKAGE is not configured")

    package_dir = Path(package_value)
    manifest_path = next(
        (
            package_dir / name
            for name in ("preprocessing_manifest.yaml", "manifest.yaml")
            if (package_dir / name).is_file()
        ),
        None,
    )
    if manifest_path is None:
        pytest.skip(
            "Local reference package has no preprocessing_manifest.yaml "
            "or manifest.yaml"
        )

    manifest = load_preprocessing_input_manifest(manifest_path)
    result = load_manifest_condition_runtimes(
        manifest,
        base_dir=package_dir,
    )

    assert isinstance(result, PreprocessingManifestLoadResult)
    assert result.condition_results
    assert result.passed is True, result.to_dict()
