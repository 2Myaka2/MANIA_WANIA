"""Opt-in contacts export check for local loaded runtimes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _harness import local_reference_package_path

from mania.preprocessing import (
    PreprocessingContactDetectionOptions,
    PreprocessingContactEdgesCsvValidationResult,
    PreprocessingContactEdgesCsvWriteResult,
    PreprocessingContactsPerFrameCsvValidationResult,
    PreprocessingContactsPerFrameCsvWriteResult,
    PreprocessingManifestContactsResult,
    compute_manifest_contacts,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]


def test_export_local_manifest_contacts(tmp_path: Path) -> None:
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

    perframe_path = tmp_path / "contacts_perframe.csv"
    edges_path = tmp_path / "contact_edges.csv"
    perframe_write = write_contacts_perframe_csv(
        contacts_result,
        perframe_path,
    )
    edges_write = write_contact_edges_csv(contacts_result, edges_path)

    assert isinstance(
        perframe_write,
        PreprocessingContactsPerFrameCsvWriteResult,
    )
    assert isinstance(edges_write, PreprocessingContactEdgesCsvWriteResult)
    assert perframe_write.passed is True, perframe_write.to_dict()
    assert edges_write.passed is True, edges_write.to_dict()
    assert perframe_write.output_path == perframe_path
    assert edges_write.output_path == edges_path
    assert perframe_write.rows_written >= 0
    assert edges_write.rows_written >= 0
    assert perframe_path.exists()
    assert edges_path.exists()
    assert perframe_path.is_file()
    assert edges_path.is_file()
    assert perframe_path.parent == tmp_path
    assert edges_path.parent == tmp_path

    perframe_validation = validate_contacts_perframe_csv(perframe_path)
    edges_validation = validate_contact_edges_csv(edges_path)

    assert isinstance(
        perframe_validation,
        PreprocessingContactsPerFrameCsvValidationResult,
    )
    assert isinstance(
        edges_validation,
        PreprocessingContactEdgesCsvValidationResult,
    )
    assert perframe_validation.passed is True, perframe_validation.to_dict()
    assert edges_validation.passed is True, edges_validation.to_dict()
    assert perframe_validation.row_count == perframe_write.rows_written
    assert edges_validation.row_count == edges_write.rows_written
    assert perframe_validation.contact_count == perframe_write.rows_written
    assert edges_validation.aggregate_edge_count == edges_write.rows_written
    assert perframe_validation.invalid_row_count == 0
    assert edges_validation.invalid_row_count == 0

    json.dumps(contacts_result.to_dict())
    json.dumps(perframe_write.to_dict())
    json.dumps(edges_write.to_dict())
    json.dumps(perframe_validation.to_dict())
    json.dumps(edges_validation.to_dict())
