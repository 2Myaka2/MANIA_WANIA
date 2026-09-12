"""Deterministic human/audit CSV derived solely from authoritative decisions."""

import csv
import io
import re
from dataclasses import dataclass, fields, replace
from pathlib import Path

from mania._dataset_qc_json import decode, payload
from mania.dataset_hard_qc import HardQCStatus
from mania.dataset_qc_contract import (
    DatasetQCDecisionSet,
    QCDecisionMode,
    QCReasonCode,
    QCReleaseDecision,
    QCStatus,
    expected_qc_status,
)
from mania.dataset_review_qc import ReviewQCStatus
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    write_atomic_text,
)

DATASET_QC_SUMMARY_CSV_FILENAME = "dataset_qc_summary.csv"


@dataclass(frozen=True)
class DatasetQCSummaryRow:
    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    hard_qc_status: HardQCStatus
    review_qc_status: ReviewQCStatus | None
    qc_status: QCStatus
    release_decision: QCReleaseDecision
    decision_mode: QCDecisionMode
    decision_reason_code: QCReasonCode | None
    human_readable_reason: str | None
    reviewer: str | None
    decision_note: str | None
    hard_fail_count: int
    review_finding_count: int
    total_check_count: int

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name.endswith("_count"):
                if type(value) is not int or value < 0:
                    raise ValueError("Summary counts must be non-negative integers")
            elif value is not None and (type(value) is not str or not value.strip()):
                raise ValueError("Summary text must be non-empty")
        if any(
            getattr(self, n) is None
            for n in (
                "dataset_id",
                "system_id",
                "trajectory_id",
                "replica_id",
            )
        ):
            raise ValueError("Summary identity must be present")
        if self.qc_status not in ("pass", "review", "fail") or (
            self.hard_qc_status != ("fail" if self.qc_status == "fail" else "pass")
            or self.review_qc_status
            != (None if self.qc_status == "fail" else self.qc_status)
            or (self.hard_fail_count > 0) != (self.qc_status == "fail")
            or (self.review_finding_count > 0) != (self.qc_status == "review")
            or self.total_check_count
            < max(
                1,
                self.hard_fail_count + self.review_finding_count,
            )
        ):
            raise ValueError("Summary statuses/counts disagree")
        allowed = {
            ("pass", "available", "automatic"),
            ("fail", "excluded", "automatic"),
            ("review", "pending_review", "automatic"),
            ("review", "available", "manual"),
            ("review", "excluded", "manual"),
        }
        if (self.qc_status, self.release_decision, self.decision_mode) not in allowed:
            raise ValueError("Invalid summary decision combination")
        if self.qc_status == "pass":
            if self.decision_reason_code is not None or self.human_readable_reason:
                raise ValueError("PASS summary forbids reason")
        elif self.decision_reason_code is None or (
            expected_qc_status(self.decision_reason_code) != self.qc_status
            or self.human_readable_reason is None
        ):
            raise ValueError("Summary reason must match status")
        if self.decision_mode == "manual":
            if self.reviewer is None or self.decision_note is None:
                raise ValueError("Manual summary requires reviewer and note")
        elif self.reviewer is not None or self.decision_note is not None:
            raise ValueError("Automatic summary forbids manual provenance")

    @property
    def replica_key(self) -> tuple[str, str, str, str]:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id


DATASET_QC_SUMMARY_CSV_COLUMNS = tuple(f.name for f in fields(DatasetQCSummaryRow))
_NULLABLE = {
    "review_qc_status",
    "decision_reason_code",
    "human_readable_reason",
    "reviewer",
    "decision_note",
}


@dataclass(frozen=True)
class DatasetQCSummary:
    rows: tuple[DatasetQCSummaryRow, ...]

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or any(
            type(r) is not DatasetQCSummaryRow for r in self.rows
        ):
            raise ValueError("Expected tuple of exact summary rows")
        for row in self.rows:
            replace(row)
        if len({r.replica_key for r in self.rows}) != len(self.rows):
            raise ValueError("Duplicate summary replica key")
        object.__setattr__(
            self,
            "rows",
            tuple(
                sorted(
                    self.rows,
                    key=lambda r: r.replica_key,
                )
            ),
        )


def build_dataset_qc_summary(decisions: DatasetQCDecisionSet) -> DatasetQCSummary:
    return DatasetQCSummary(
        tuple(
            DatasetQCSummaryRow(
                *r.replica_key,
                "fail" if r.qc_status == "fail" else "pass",
                None if r.qc_status == "fail" else r.qc_status,
                r.qc_status,
                r.release_decision,
                r.decision_mode,
                r.decision_reason_code,
                r.human_readable_reason,
                r.reviewer,
                r.decision_note,
                sum(c.status == "fail" for c in r.findings),
                sum(c.status == "review" for c in r.findings),
                len(r.findings),
            )
            for r in decisions.records
        )
    )


def dataset_qc_summary_csv_bytes(summary: DatasetQCSummary) -> bytes:
    if type(summary) is not DatasetQCSummary:
        raise ValueError("Expected exact DatasetQCSummary")
    decode(payload(summary), DatasetQCSummary)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(DATASET_QC_SUMMARY_CSV_COLUMNS)
    for row in summary.rows:
        writer.writerow(
            "" if (v := getattr(row, n)) is None else v
            for n in DATASET_QC_SUMMARY_CSV_COLUMNS
        )
    return stream.getvalue().encode("utf-8")


def read_dataset_qc_summary_csv(path: str | Path) -> DatasetQCSummary:
    try:
        with Path(path).open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != DATASET_QC_SUMMARY_CSV_COLUMNS:
                raise ValueError("Invalid exact summary header")
            rows = []
            for cells in reader:
                data: dict[str, object] = {}
                for name, value in zip(
                    DATASET_QC_SUMMARY_CSV_COLUMNS, cells, strict=True
                ):
                    if name.endswith("_count"):
                        if re.fullmatch(r"0|[1-9][0-9]*", value) is None:
                            raise ValueError("Invalid strict integer")
                        data[name] = int(value)
                    else:
                        data[name] = (
                            None if name in _NULLABLE and value == "" else value
                        )
                rows.append(decode(data, DatasetQCSummaryRow))
        return DatasetQCSummary(tuple(rows))
    except (OSError, ValueError, TypeError, csv.Error, OverflowError):
        raise ValueError("Invalid or unreadable Dataset QC summary CSV.") from None


def write_dataset_qc_summary_csv(
    summary: DatasetQCSummary,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_atomic_text(
        dataset_qc_summary_csv_bytes(summary).decode("utf-8"),
        Path(path),
        overwrite=overwrite,
    )
