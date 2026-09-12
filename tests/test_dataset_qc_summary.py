"""Strict human/audit CSV, nullable cells, counts, and header-only schema."""

import csv
import io
from dataclasses import replace

import pytest
from test_dataset_qc_manifest import make_qc_case

from mania.dataset_qc_summary import (
    DatasetQCSummary,
    dataset_qc_summary_csv_bytes,
    read_dataset_qc_summary_csv,
    write_dataset_qc_summary_csv,
)
from mania.dataset_qc_workflow import execute_dataset_qc_manifest


def test_summary_exact_roundtrip_counts_and_nulls(tmp_path):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    outputs = execute_dataset_qc_manifest(manifest, path)
    summary = outputs.summary
    target = tmp_path / "summary.csv"
    assert write_dataset_qc_summary_csv(summary, target).written
    assert read_dataset_qc_summary_csv(target) == summary
    assert target.read_bytes() == dataset_qc_summary_csv_bytes(summary)
    assert not write_dataset_qc_summary_csv(summary, target).written
    assert b"None" not in target.read_bytes() and b"null" not in target.read_bytes()
    rows = list(csv.DictReader(io.StringIO(target.read_text())))
    assert rows[0]["review_qc_status"] == ""
    assert rows[1]["decision_reason_code"] == rows[1]["human_readable_reason"] == ""
    assert rows[1]["reviewer"] == rows[1]["decision_note"] == ""
    for row, decision in zip(summary.rows, outputs.decisions.records, strict=True):
        assert row.total_check_count == len(decision.findings)
        assert row.hard_fail_count == sum(f.status == "fail" for f in decision.findings)
        assert row.review_finding_count == sum(
            f.status == "review" for f in decision.findings
        )
    empty = DatasetQCSummary(())
    assert write_dataset_qc_summary_csv(empty, target, overwrite=True).written
    assert read_dataset_qc_summary_csv(target) == empty
    assert len(target.read_text().splitlines()) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("hard_fail_count", "1.0"),
        ("hard_fail_count", "True"),
        ("hard_fail_count", "-1"),
        ("hard_fail_count", "01"),
        ("review_qc_status", "pass"),
        ("qc_status", "PASS"),
        ("reviewer", "None"),
        ("total_check_count", "0"),
        ("dataset_id", ""),
    ],
)
def test_summary_strict_csv_mutations(tmp_path, field, value):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    summary = execute_dataset_qc_manifest(manifest, path).summary
    target = tmp_path / "summary.csv"
    cells = list(
        csv.reader(io.StringIO(dataset_qc_summary_csv_bytes(summary).decode()))
    )
    cells[1][cells[0].index(field)] = value
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(cells)
    target.write_text(stream.getvalue())
    with pytest.raises(ValueError):
        read_dataset_qc_summary_csv(target)


def test_summary_header_and_duplicate_identity_rejected(tmp_path):
    manifest, path, _, _, _ = make_qc_case(tmp_path)
    summary = execute_dataset_qc_manifest(manifest, path).summary
    with pytest.raises(ValueError):
        replace(summary, rows=summary.rows * 2)
    path.write_text("replica_id,dataset_id\n")
    with pytest.raises(ValueError):
        read_dataset_qc_summary_csv(path)
