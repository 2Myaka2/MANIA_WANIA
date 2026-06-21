"""Opt-in contacts computation check for local loaded runtimes."""

from __future__ import annotations

import json

import pytest
from _harness import local_reference_package_path

from mania.preprocessing import (
    PreprocessingContactDetectionOptions,
    PreprocessingManifestContactsResult,
    compute_manifest_contacts,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_compute_local_manifest_contacts() -> None:
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

    options = PreprocessingContactDetectionOptions()
    contacts_result = compute_manifest_contacts(load_result, options=options)

    assert isinstance(contacts_result, PreprocessingManifestContactsResult)
    assert contacts_result.condition_count >= 0
    assert contacts_result.frame_count >= 0
    assert contacts_result.contact_count >= 0
    assert isinstance(contacts_result.passed, bool)
    json.dumps(contacts_result.to_dict())

    if load_result.condition_results:
        assert contacts_result.condition_count == len(
            load_result.condition_results
        )
        assert contacts_result.condition_results

    for condition_result in contacts_result.condition_results:
        assert condition_result.condition_name
        assert condition_result.frame_count >= 0
        assert condition_result.contact_count >= 0
        json.dumps(condition_result.to_dict())

        for frame_result in condition_result.frame_results:
            assert frame_result.frame_index >= 0
            assert frame_result.contact_count >= 0
            json.dumps(frame_result.to_dict())

            for contact in frame_result.contacts:
                assert (
                    contact.source_residue_index
                    != contact.target_residue_index
                )
                assert contact.source_resname
                assert contact.target_resname
                assert contact.minimum_distance >= 0
                assert contact.distance_unit == options.distance_unit
                assert contact.atom_filter == options.atom_filter
