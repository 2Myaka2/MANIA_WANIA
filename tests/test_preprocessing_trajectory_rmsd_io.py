"""Strict two-artifact persistence and all requested scientific/lineage identities."""

import csv
import io
import json

import pytest
from test_preprocessing_trajectory_rmsd import XYZ, accumulator, temporal_binding

from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.physical_time_execution_io import (
    write_preprocessing_temporal_execution,
)
from mania.preprocessing.trajectory_rmsd import SelectedFrameObservation
from mania.preprocessing.trajectory_rmsd_io import (
    MEASUREMENT_FILENAME,
    TIMESERIES_FILENAME,
    FileBinding,
    file_sha256,
    read_rmsd_evidence,
    write_rmsd_evidence,
)


def persisted(root, *, missing=False):
    binding = temporal_binding([0, 5200, 5400, 8000]) if missing else temporal_binding()
    value = accumulator(binding)
    assert write_preprocessing_temporal_execution(
        PreprocessingTemporalExecution((binding,)), root
    ).passed
    for sample in binding.sampling_plan.selected_samples:
        value.observe(SelectedFrameObservation("normal", sample, XYZ, value.selection))
    bindings = {
        role: FileBinding(
            artifact_id="source:" + role,
            path=None,
            byte_size=20,
            sha256=str(n) * 64,
            format="json",
        )
        for n, role in enumerate(
            (
                "topology",
                "mapping",
                "prepared_trajectory",
                "raw_trajectory",
                "preparation_report",
            ),
            1,
        )
    }
    metadata = write_rmsd_evidence(value, root, source_bindings=bindings)
    return metadata, value.finalize(), bindings


def test_csv_json_round_trip_and_deterministic_bytes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    metadata, rows, bindings = persisted(first, missing=True)
    persisted(second, missing=True)
    assert read_rmsd_evidence(first, expected_bindings=bindings) == (metadata, rows)
    for name in (MEASUREMENT_FILENAME, TIMESERIES_FILENAME):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (
        rows[0].state == "missing"
        and metadata.reference.sample.requested_sample_index == 1
    )
    with pytest.raises(ValueError, match="immutable"):
        value = accumulator()
        for sample in value.binding.sampling_plan.selected_samples:
            value.observe(
                SelectedFrameObservation("normal", sample, XYZ, value.selection)
            )
        write_rmsd_evidence(value, first, source_bindings=bindings)


@pytest.mark.parametrize(
    "role", ["topology", "mapping", "prepared_trajectory", "raw_trajectory"]
)
def test_expected_lineage_changed_rejected(tmp_path, role):
    _, _, bindings = persisted(tmp_path)
    bindings[role] = bindings[role].model_copy(update={"sha256": "f" * 64})
    with pytest.raises(ValueError, match="lineage"):
        read_rmsd_evidence(tmp_path, expected_bindings=bindings)


@pytest.mark.parametrize(
    "damage",
    [
        "method",
        "unit",
        "selection",
        "reference",
        "software",
        "software_types",
        "completion_bool",
        "schema",
        "completion",
        "extra",
        "duplicate_key",
    ],
)
def test_metadata_contract_and_identity_tampering_rejected(tmp_path, damage):
    persisted(tmp_path)
    path = tmp_path / MEASUREMENT_FILENAME
    data = json.loads(path.read_text())
    if damage == "method":
        data["method"]["rotation"] = "allow_reflection"
    if damage == "unit":
        data["method"]["coordinate_unit"] = "nm"
    if damage == "selection":
        data["atom_selection"]["atoms"].reverse()
    if damage == "reference":
        data["reference"]["sample"]["requested_sample_index"] = 3
    if damage == "software":
        data["implementation"]["algorithm_source_sha256"] = "f" * 64
    if damage == "software_types":
        data["implementation"]["software_identity"]["version"] = 1
    if damage == "completion_bool":
        data["completeness"]["resolved_measurement_count_matches"] = 1
    if damage == "schema":
        data["measurement_contract_id"] = "future"
    if damage == "completion":
        data["completeness"]["measured_count"] -= 1
    if damage == "extra":
        data["threshold"] = 3
    path.write_text(json.dumps(data))
    if damage == "duplicate_key":
        path.write_text(
            path.read_text().replace('"kind":', '"kind":"duplicate","kind":')
        )
    with pytest.raises(ValueError):
        read_rmsd_evidence(tmp_path)


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "reorder",
        "nan",
        "inf",
        "identity",
        "bool_index",
        "missing_state",
    ],
)
def test_csv_rows_strict_even_after_table_hash_rebound(tmp_path, damage):
    persisted(tmp_path)
    csv_path = tmp_path / TIMESERIES_FILENAME
    rows = list(csv.reader(io.StringIO(csv_path.read_text())))
    indexes = {name: i for i, name in enumerate(rows[0])}
    if damage == "missing":
        rows.pop()
    if damage == "duplicate":
        rows.append(rows[-1])
    if damage == "reorder":
        rows[1], rows[2] = rows[2], rows[1]
    if damage in ("nan", "inf"):
        rows[2][indexes["rmsd_A"]] = damage
    if damage == "identity":
        rows[1][indexes["replica_id"]] = "other"
    if damage == "bool_index":
        rows[1][indexes["requested_sample_index"]] = "True"
    if damage == "missing_state":
        rows[1][indexes["state"]] = "missing"
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    csv_path.write_text(stream.getvalue())
    path = tmp_path / MEASUREMENT_FILENAME
    data = json.loads(path.read_text())
    data["table"].update(
        sha256=file_sha256(csv_path), byte_size=csv_path.stat().st_size
    )
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_rmsd_evidence(tmp_path)
