"""Opt-in metadata report check for local loaded runtimes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mania.preprocessing import (
    PreprocessingManifestRuntimeMetadata,
    collect_manifest_runtime_metadata,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_collect_local_trajectory_metadata() -> None:
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
    load_result = load_manifest_condition_runtimes(
        manifest,
        base_dir=package_dir,
    )
    assert load_result.passed is True, load_result.to_dict()

    metadata = collect_manifest_runtime_metadata(load_result)

    assert isinstance(metadata, PreprocessingManifestRuntimeMetadata)
    assert metadata.condition_metadata
    json.dumps(metadata.to_dict())
