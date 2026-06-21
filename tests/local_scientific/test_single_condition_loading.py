"""Opt-in real-data check for loading exactly one manifest condition."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntimeInput,
    load_preprocessing_input_manifest,
    load_single_condition_runtime,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_load_first_local_manifest_condition() -> None:
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
    condition = manifest.conditions[0]
    runtime_input = PreprocessingConditionRuntimeInput.from_manifest_condition(
        condition.condition,
        condition,
        base_dir=package_dir,
    )

    result = load_single_condition_runtime(runtime_input)

    assert isinstance(result, PreprocessingConditionLoadResult)
    assert result.passed is True, result.to_dict()
