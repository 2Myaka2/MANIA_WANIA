"""Opt-in Rg export check for local loaded runtimes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from _harness import local_reference_package_path

from mania.preprocessing import (
    compute_manifest_rg,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
    validate_rg_timeseries_csv,
    write_rg_timeseries_csv,
)

pytestmark = [
    pytest.mark.local_scientific,
    pytest.mark.requires_mdanalysis,
    pytest.mark.requires_real_md_data,
]

CSV_HEADER = (
    "condition_name,frame_index,time_ps,rg_value,rg_unit,frame_passed"
)


def test_export_local_manifest_rg(tmp_path: Path) -> None:
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
    assert rg_result.passed is True, rg_result.to_dict()

    csv_path = tmp_path / "rg_timeseries.csv"
    write_result = write_rg_timeseries_csv(rg_result, csv_path)

    assert write_result.passed is True, write_result.to_dict()
    assert write_result.rows_written > 0
    assert csv_path.exists()
    assert csv_path.is_file()
    assert csv_path.parent == tmp_path

    validation_result = validate_rg_timeseries_csv(csv_path)

    assert validation_result.passed is True, validation_result.to_dict()
    assert validation_result.row_count == write_result.rows_written
    assert validation_result.invalid_row_count == 0
    assert validation_result.issues == ()

    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        first_line = csv_file.readline().rstrip("\r\n")
        rows = list(csv.DictReader(csv_file, fieldnames=CSV_HEADER.split(",")))

    assert first_line == CSV_HEADER
    assert rows
    known_condition_names = set(rg_result.condition_names)
    assert {row["condition_name"] for row in rows} <= known_condition_names
    assert {row["frame_passed"] for row in rows} <= {"true", "false"}

    json.dumps(write_result.to_dict())
    json.dumps(validation_result.to_dict())
