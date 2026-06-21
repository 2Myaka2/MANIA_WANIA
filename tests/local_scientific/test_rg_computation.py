"""Opt-in Rg computation check for local loaded runtimes."""

from __future__ import annotations

import json
import math

import pytest
from _harness import local_reference_package_path

from mania.preprocessing import (
    PreprocessingManifestRgResult,
    compute_manifest_rg,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_compute_local_manifest_rg() -> None:
    local_package_path = local_reference_package_path()
    if local_package_path is None:
        pytest.skip("MANIA_LOCAL_REFERENCE_PACKAGE is not configured")

    manifest_path = next(
        (
            local_package_path / name
            for name in ("preprocessing_manifest.yaml", "manifest.yaml")
            if (local_package_path / name).is_file()
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
        base_dir=local_package_path,
    )
    assert load_result.passed is True, load_result.to_dict()

    rg_result = compute_manifest_rg(load_result)

    assert isinstance(rg_result, PreprocessingManifestRgResult)
    assert rg_result.passed is True, rg_result.to_dict()
    assert rg_result.condition_results
    assert rg_result.condition_names == manifest.condition_names()
    assert all(rg_result.condition_names)

    frame_results = [
        frame_result
        for condition_result in rg_result.condition_results
        for frame_result in condition_result.frame_results
    ]
    assert frame_results

    for condition_result in rg_result.condition_results:
        frame_indexes = tuple(
            frame_result.frame_index
            for frame_result in condition_result.frame_results
        )
        assert frame_indexes == tuple(range(len(frame_indexes)))

        for frame_result in condition_result.frame_results:
            if frame_result.passed:
                assert frame_result.rg_value is not None
                assert math.isfinite(frame_result.rg_value)
                assert frame_result.rg_value >= 0

    payload = rg_result.to_dict()
    json.dumps(payload)
    for condition_payload in payload["condition_results"]:
        assert isinstance(condition_payload, dict)
        assert "runtime_object" not in condition_payload
