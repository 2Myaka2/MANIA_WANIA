"""Strict CSV scalars, source identity, deterministic bytes, and atomic failure."""

import csv
import inspect
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest
from test_preprocessing_protein_edge_window_table import ROW_FIELDS, pair, table

from mania.preprocessing import protein_edge_window_table_io as table_io
from mania.preprocessing import protein_edge_windows as aggregation
from mania.preprocessing.protein_edge_window_table import DatasetProteinEdgeWindowTable
from mania.preprocessing.protein_edge_window_table_io import (
    DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
    DatasetProteinEdgeWindowCsvReadError,
    DatasetProteinEdgeWindowCsvValidationIssue,
    DatasetProteinEdgeWindowCsvValidationReport,
    DatasetProteinEdgeWindowCsvWriteResult,
    read_dataset_protein_edge_window_csv,
    validate_dataset_protein_edge_window_csv,
    write_dataset_protein_edge_window_csv,
)


def write(result, directory, **kwargs):
    outcome = write_dataset_protein_edge_window_csv(result, directory, **kwargs)
    assert outcome.passed, outcome.error
    return outcome.output_path


def records(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def save_records(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)


def test_public_api_exact_columns_and_no_canonical_fields():
    assert DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS == ROW_FIELDS
    assert type(DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS) is tuple
    assert not any(
        "canonical" in name or "mapping_status" in name or "distance" in name
        for name in DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS
    )
    assert table_io.__all__ == [
        "DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS",
        "DatasetProteinEdgeWindowCsvReadError",
        "DatasetProteinEdgeWindowCsvValidationIssue",
        "DatasetProteinEdgeWindowCsvValidationReport",
        "DatasetProteinEdgeWindowCsvWriteResult",
        "read_dataset_protein_edge_window_csv",
        "validate_dataset_protein_edge_window_csv",
        "write_dataset_protein_edge_window_csv",
    ]
    assert issubclass(DatasetProteinEdgeWindowCsvReadError, ValueError)
    signature = inspect.signature(write_dataset_protein_edge_window_csv)
    assert tuple(signature.parameters) == ("table", "output_dir", "overwrite")
    assert signature.parameters["overwrite"].kind == inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["overwrite"].default is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"missing": (2,), "positive": (0, 1, 3, 4)},
        {"engine": "namd", "condition": None},
        {"disulfide_state": "intact"},
        {
            "count": 9,
            "length": 0.2,
            "step": 0.1,
            "observations": {3: (pair(edge_type="hbond"), pair(edge_type="ionic"))},
        },
        {
            "observations": {
                0: (
                    pair(
                        source_segid=None,
                        target_segid=None,
                        source_residue_id=None,
                        target_residue_id=None,
                    ),
                )
            }
        },
    ],
)
def test_round_trip_exact_header_bytes_and_validation(tmp_path, kwargs):
    original = table(**kwargs)
    before = original.to_dict()
    path = write(original, tmp_path)
    assert path == tmp_path / "protein_edges_by_window_source.csv"
    raw = path.read_bytes()
    assert raw.startswith((",".join(ROW_FIELDS) + "\n").encode("utf-8"))
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert b"\r\n" not in raw
    reread = read_dataset_protein_edge_window_csv(str(path))
    assert reread.to_dict() == before == original.to_dict()
    report = validate_dataset_protein_edge_window_csv(path)
    assert report.passed and report.issues == ()
    assert report.row_count == original.row_count
    assert records(path)[0] == list(ROW_FIELDS)
    assert write(original, tmp_path / "again").read_bytes() == raw


def test_optional_cells_are_blank_and_numeric_looking_source_resids_stay_strings(
    tmp_path,
):
    result = table(
        engine="namd",
        condition=None,
        observations={
            0: (
                pair(
                    source_segid=None,
                    target_segid=None,
                    source_residue_id=330,
                    target_residue_id="00330",
                ),
            )
        },
    )
    path = write(result, tmp_path)
    cells = dict(zip(ROW_FIELDS, records(path)[1], strict=True))
    for name in ("condition", "disulfide_state", "source_chain_id", "target_chain_id"):
        assert cells[name] == ""
    assert cells["source_resid"] == "330"
    assert cells["target_resid"] == "00330"
    row = read_dataset_protein_edge_window_csv(path).rows[0]
    assert row.condition is row.disulfide_state is None
    assert row.source_chain_id is row.target_chain_id is None
    assert row.source_resid == "330" and type(row.source_resid) is str
    assert row.target_resid == "00330" and type(row.target_resid) is str


@pytest.mark.parametrize(
    ("resid", "expected"), [(330, "330"), ("330A", "330A"), (None, "")]
)
def test_source_resid_export_mapping(tmp_path, resid, expected):
    path = write(
        table(
            observations={0: (pair(source_residue_id=resid, target_residue_id=resid),)}
        ),
        tmp_path,
    )
    cells = dict(zip(ROW_FIELDS, records(path)[1], strict=True))
    assert cells["source_resid"] == cells["target_resid"] == expected
    row = read_dataset_protein_edge_window_csv(path).rows[0]
    assert row.source_resid == row.target_resid == (expected or None)


def test_lowercase_bools_and_repr_floats_without_rounding(tmp_path):
    original = table(count=9, length=0.2, positive=(0, 8))
    path = write(original, tmp_path)
    data = records(path)[1:]
    assert [cells[ROW_FIELDS.index("right_endpoint_inclusive")] for cells in data] == [
        "false",
        "true",
    ]
    for row, cells in zip(original.rows, data, strict=True):
        for name, value in row.to_dict().items():
            if isinstance(value, float):
                assert cells[ROW_FIELDS.index(name)] == repr(value)


@pytest.mark.parametrize(
    ("missing", "positive", "resolved", "occupancy", "maximum"),
    [((), (0, 1, 2, 4), 5, 0.8, 0.1), ((2,), (0, 1, 3, 4), 4, 1.0, 0.05)],
)
def test_scientific_08_and_10_cases_survive_csv(
    tmp_path,
    missing,
    positive,
    resolved,
    occupancy,
    maximum,
):
    result = table(missing=missing, positive=positive)
    row = read_dataset_protein_edge_window_csv(write(result, tmp_path)).rows[0]
    assert row.n_contact_frames == 4
    assert row.resolved_frame_count == resolved
    assert row.occupancy == row.edge_weight == occupancy
    assert row.n_contact_episodes == 2
    assert row.mean_episode_length_ns == 0.05
    assert row.max_episode_length_ns == maximum


def test_header_only_empty_table_is_successful(tmp_path):
    empty = DatasetProteinEdgeWindowTable(())
    path = write(empty, tmp_path)
    assert path.read_bytes() == (",".join(ROW_FIELDS) + "\n").encode("utf-8")
    assert read_dataset_protein_edge_window_csv(path) == empty
    report = validate_dataset_protein_edge_window_csv(path)
    assert report.row_count == 0 and report.passed


def test_utf8_quoting_preserves_source_identifiers(tmp_path):
    row = replace(
        table().rows[0],
        source_chain_id='segment,"alpha"',
        source_resid="330A\ninsert",
        target_chain_id="segment-α",
    )
    result = DatasetProteinEdgeWindowTable((row,))
    path = write(result, tmp_path)
    assert b'"segment,""alpha"""' in path.read_bytes()
    assert read_dataset_protein_edge_window_csv(path) == result


def test_overwrite_false_and_true_atomic_replacement(tmp_path, monkeypatch):
    original = table()
    path = write(original, tmp_path)
    old_bytes = path.read_bytes()
    empty = DatasetProteinEdgeWindowTable(())
    blocked = write_dataset_protein_edge_window_csv(empty, tmp_path)
    assert not blocked.written and not blocked.passed
    assert blocked.error == "Target already exists."
    assert path.read_bytes() == old_bytes
    actual_replace = os.replace
    replacements = []

    def observe_replace(source, target):
        assert Path(source).parent == tmp_path
        assert Path(source).read_bytes() == (",".join(ROW_FIELDS) + "\n").encode()
        assert Path(target).read_bytes() == old_bytes
        replacements.append((source, target))
        actual_replace(source, target)

    monkeypatch.setattr(table_io.os, "replace", observe_replace)
    write(empty, str(tmp_path), overwrite=True)
    assert len(replacements) == 1
    assert read_dataset_protein_edge_window_csv(path) == empty
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("failure", ["publish", "serialize"])
def test_writer_failure_removes_only_owned_temporary_file(
    tmp_path, monkeypatch, overwrite, failure
):
    original = table()
    target = tmp_path / "protein_edges_by_window_source.csv"
    if overwrite:
        target.write_bytes(b"old target\n")
    unrelated = tmp_path / ".unrelated.tmp"
    unrelated.write_bytes(b"keep")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def fail(*args, **kwargs):
        if failure == "serialize":
            raise csv.Error("private input contents")
        raise OSError(f"private path: {tmp_path}")

    if failure == "serialize":
        monkeypatch.setattr(table_io, "_serialize", fail)
    else:
        monkeypatch.setattr(table_io.os, "replace" if overwrite else "link", fail)
    result = write_dataset_protein_edge_window_csv(
        original, tmp_path, overwrite=overwrite
    )
    assert not result.passed and not result.written
    assert result.error == (
        "CSV serialization failed."
        if failure == "serialize"
        else "Filesystem write failed."
    )
    assert str(tmp_path) not in result.error
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_atomic_no_overwrite_rejects_concurrent_target(tmp_path, monkeypatch):
    actual_link = os.link

    def race(source, target):
        assert Path(source).parent == tmp_path
        Path(target).write_bytes(b"concurrent writer\n")
        actual_link(source, target)

    monkeypatch.setattr(table_io.os, "link", race)
    result = write_dataset_protein_edge_window_csv(table(), tmp_path)
    assert result.error == "Target already exists."
    assert not result.passed
    assert result.output_path.read_bytes() == b"concurrent writer\n"
    assert tuple(tmp_path.iterdir()) == (result.output_path,)


def test_dangling_target_symlink_is_not_overwritten(tmp_path):
    target = tmp_path / "protein_edges_by_window_source.csv"
    target.symlink_to(tmp_path / "absent.csv")
    result = write_dataset_protein_edge_window_csv(table(), tmp_path)
    assert result.error == "Target already exists."
    assert target.is_symlink()


@pytest.mark.parametrize("change", ["reordered", "missing", "extra", "duplicate"])
def test_exact_header_required(tmp_path, change):
    path = write(table(), tmp_path)
    data = records(path)
    if change == "reordered":
        data[0][0], data[0][1] = data[0][1], data[0][0]
    elif change == "missing":
        data[0].pop()
    elif change == "extra":
        data[0].append("extra")
    else:
        data[0][1] = data[0][0]
    save_records(path, data)
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)


@pytest.mark.parametrize(
    "payload",
    [b"", b"\xff\n", b'"unterminated', b"\xef\xbb\xbf" + ",".join(ROW_FIELDS).encode()],
)
def test_missing_header_invalid_utf8_bom_and_malformed_csv(tmp_path, payload):
    path = tmp_path / "bad.csv"
    path.write_bytes(payload)
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)


@pytest.mark.parametrize("change", ["short", "long", "blank", "quote"])
def test_every_record_has_exact_cell_count_and_valid_csv(tmp_path, change):
    path = write(table(), tmp_path)
    data = records(path)
    if change == "short":
        data[1].pop()
    elif change == "long":
        data[1].append("extra")
    elif change == "blank":
        data.append([])
    else:
        path.write_text(path.read_text() + '"unterminated\n', encoding="utf-8")
    if change != "quote":
        save_records(path, data)
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)


@pytest.mark.parametrize(
    ("name", "cell"),
    [
        *[
            ("right_endpoint_inclusive", value)
            for value in (
                "True",
                "False",
                "TRUE",
                "FALSE",
                "1",
                "0",
                "yes",
                "",
                " true",
            )
        ],
        *[
            ("window_index", value)
            for value in (
                "0.0",
                "True",
                "false",
                "-1",
                "+0",
                "-0",
                "00",
                " 0",
                "0 ",
                "０",
                "0_0",
                "",
            )
        ],
        *[
            ("occupancy", value)
            for value in (
                "NaN",
                "nan",
                "Infinity",
                "-Infinity",
                "inf",
                "1e999",
                "0_8",
                " 0.8",
                "",
                "0.7",
            )
        ],
        ("edge_weight", "0.7"),
        ("source_residue_index", "7"),
        ("target_residue_index", "0"),
        ("source_resid", " 330"),
        ("source_chain_id", " A"),
        ("engine", "NAMD"),
        ("coverage_fraction", "0.8"),
        ("resolved_frame_count", "4"),
        ("n_contact_episodes", "0"),
        ("mean_episode_length_ns", "0.2"),
    ],
)
def test_strict_scalar_and_row_invariants(tmp_path, name, cell):
    path = write(table(), tmp_path)
    data = records(path)
    data[1][ROW_FIELDS.index(name)] = cell
    save_records(path, data)
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)


@pytest.mark.parametrize("different_condition", [False, True])
def test_duplicate_identity_rejected_without_condition_identity(
    tmp_path, different_condition
):
    path = write(table(), tmp_path)
    data = records(path)
    duplicate = data[1].copy()
    if different_condition:
        duplicate[ROW_FIELDS.index("condition")] = ""
    data.append(duplicate)
    save_records(path, data)
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)


def test_external_csv_is_not_silently_sorted(tmp_path):
    path = write(table(count=9, length=0.2, positive=(0, 8)), tmp_path)
    data = records(path)
    save_records(path, [data[0], *reversed(data[1:])])
    before = path.read_bytes()
    with pytest.raises(DatasetProteinEdgeWindowCsvReadError):
        read_dataset_protein_edge_window_csv(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "directory", "bad"])
def test_validation_wrapper_failure_is_portable_and_deterministic(tmp_path, kind):
    path = tmp_path / "private.csv"
    if kind == "directory":
        path.mkdir()
    elif kind == "bad":
        path.write_bytes(b"bad\n")
    report = validate_dataset_protein_edge_window_csv(path)
    assert not report.passed and report.row_count is None
    assert report.issues == (
        DatasetProteinEdgeWindowCsvValidationIssue(
            "csv",
            "Invalid or unreadable Dataset protein-edge window CSV.",
        ),
    )
    assert str(tmp_path) not in report.issues[0].message
    assert report.to_dict() == validate_dataset_protein_edge_window_csv(path).to_dict()


def test_validator_delegates_to_reader(tmp_path, monkeypatch):
    calls = []

    def fake_reader(path):
        calls.append(path)
        return DatasetProteinEdgeWindowTable(())

    monkeypatch.setattr(table_io, "read_dataset_protein_edge_window_csv", fake_reader)
    report = validate_dataset_protein_edge_window_csv(tmp_path / "not-on-disk.csv")
    assert report.passed and report.row_count == 0
    assert calls == [report.csv_path]


def test_frozen_outcomes_and_deterministic_dict_order(tmp_path):
    path = tmp_path / "source.csv"
    issue = DatasetProteinEdgeWindowCsvValidationIssue("csv", "Invalid CSV.")
    for record, expected_fields, expected_keys in (
        (
            DatasetProteinEdgeWindowCsvWriteResult(path, True),
            ("output_path", "written", "error"),
            ("output_path", "written", "error", "passed"),
        ),
        (issue, ("field", "message"), ("field", "message")),
        (
            DatasetProteinEdgeWindowCsvValidationReport(path, None, (issue,)),
            ("csv_path", "row_count", "issues"),
            ("csv_path", "row_count", "issues", "passed"),
        ),
    ):
        assert tuple(f.name for f in fields(record)) == expected_fields
        assert tuple(record.to_dict()) == expected_keys
        assert record.to_dict() == record.to_dict()
        with pytest.raises(FrozenInstanceError):
            setattr(record, expected_fields[0], None)


def test_io_has_no_discovery_trajectory_git_clock_or_environment_access(
    tmp_path, monkeypatch
):
    original = table()

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected discovery or external-state access")

    for owner, names in (
        (os, ("scandir", "listdir", "walk", "getenv")),
        (Path, ("iterdir", "glob", "rglob")),
        (subprocess, ("run", "Popen")),
        (time, ("time", "monotonic", "perf_counter")),
        (
            aggregation,
            ("aggregate_protein_edges_by_window", "compute_window_contact_episodes"),
        ),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    path = write(original, tmp_path)
    assert read_dataset_protein_edge_window_csv(path) == original
    assert validate_dataset_protein_edge_window_csv(path).passed
