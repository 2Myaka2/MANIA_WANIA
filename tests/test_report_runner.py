import builtins
import json
import os
from pathlib import Path
from typing import NoReturn

import mania
from mania.constants import (
    CROSS_CONDITION_ARTIFACTS,
    PER_CONDITION_ARTIFACTS,
    SCHEMA_VERSION,
)
from mania.export.manifest import Manifest
from mania.pipeline import PipelinePlan
from mania.qc.runner import QCReport
from mania.report.runner import (
    ReportSummary,
    build_report_summary,
    format_report_summary,
    report_summary_to_dict,
)

EXPECTED_REPORT_SUMMARY_KEYS = {
    "title",
    "project_name",
    "run_id",
    "run_mode",
    "conditions",
    "qc_passed",
    "artifact_count",
}


def sample_plan() -> PipelinePlan:
    return PipelinePlan(
        project_name="NaPi2b_NORM_TUMOR",
        run_id="run_001",
        run_mode="full",
        conditions=("normal", "tumor"),
        output_dir="mania_output",
    )


def sample_manifest() -> Manifest:
    return Manifest(
        schema_version=SCHEMA_VERSION,
        mania_version=mania.__version__,
        project_name="NaPi2b_NORM_TUMOR",
        run_id="run_001",
        run_mode="full",
        conditions=("normal", "tumor"),
        per_condition_artifacts=PER_CONDITION_ARTIFACTS,
        cross_condition_artifacts=CROSS_CONDITION_ARTIFACTS,
    )


def sample_qc_report() -> QCReport:
    return QCReport(passed=True, messages=())


def fail_filesystem_access(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("report helpers must not inspect or write files")


def test_build_report_summary_reads_project_name_from_pipeline_plan() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())

    assert summary.project_name == "NaPi2b_NORM_TUMOR"


def test_build_report_summary_reads_run_id_from_pipeline_plan() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())

    assert summary.run_id == "run_001"


def test_build_report_summary_reads_run_mode_from_pipeline_plan() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())

    assert summary.run_mode == "full"


def test_build_report_summary_reads_conditions_from_pipeline_plan() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())

    assert summary.conditions == ("normal", "tumor")


def test_build_report_summary_reads_qc_passed_from_qc_report() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())

    assert summary.qc_passed is True


def test_build_report_summary_calculates_artifact_count() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    expected_count = (
        len(PER_CONDITION_ARTIFACTS) * len(sample_plan().conditions)
        + len(CROSS_CONDITION_ARTIFACTS)
    )

    assert summary.artifact_count == expected_count


def test_report_summary_to_dict_returns_basic_json_types() -> None:
    summary_dict = report_summary_to_dict(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert set(summary_dict) == EXPECTED_REPORT_SUMMARY_KEYS
    assert isinstance(summary_dict["title"], str)
    assert isinstance(summary_dict["project_name"], str)
    assert isinstance(summary_dict["run_id"], str)
    assert isinstance(summary_dict["run_mode"], str)
    assert isinstance(summary_dict["conditions"], list)
    assert isinstance(summary_dict["qc_passed"], bool)
    assert isinstance(summary_dict["artifact_count"], int)


def test_report_summary_to_dict_can_be_json_dumped() -> None:
    summary_dict = report_summary_to_dict(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert json.dumps(summary_dict)


def test_report_summary_to_dict_converts_conditions_tuple_to_list() -> None:
    summary_dict = report_summary_to_dict(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert summary_dict["conditions"] == ["normal", "tumor"]


def test_format_report_summary_contains_expected_fields() -> None:
    summary = format_report_summary(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert "MANIA analysis report skeleton" in summary
    assert "Project: NaPi2b_NORM_TUMOR" in summary
    assert "Run ID: run_001" in summary
    assert "Run mode: full" in summary
    assert "Conditions: normal, tumor" in summary
    assert "QC passed: true" in summary
    assert "Expected artifacts: 18" in summary


def test_format_report_summary_uses_stable_line_order() -> None:
    summary = format_report_summary(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert summary.splitlines() == [
        "MANIA analysis report skeleton",
        "Project: NaPi2b_NORM_TUMOR",
        "Run ID: run_001",
        "Run mode: full",
        "Conditions: normal, tumor",
        "QC passed: true",
        "Expected artifacts: 18",
    ]


def test_module_does_not_inspect_or_write_to_filesystem(monkeypatch) -> None:
    monkeypatch.setattr(builtins, "open", fail_filesystem_access)
    monkeypatch.setattr(os.path, "exists", fail_filesystem_access)
    monkeypatch.setattr(os, "makedirs", fail_filesystem_access)
    monkeypatch.setattr(Path, "exists", fail_filesystem_access)
    monkeypatch.setattr(Path, "mkdir", fail_filesystem_access)
    monkeypatch.setattr(Path, "read_text", fail_filesystem_access)
    monkeypatch.setattr(Path, "write_text", fail_filesystem_access)

    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    summary_dict = report_summary_to_dict(summary)
    formatted = format_report_summary(summary)

    assert isinstance(summary, ReportSummary)
    assert summary_dict["artifact_count"] == 18
    assert formatted.startswith("MANIA analysis report skeleton")


def test_module_does_not_generate_html() -> None:
    summary = build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    summary_dict = report_summary_to_dict(summary)
    formatted = format_report_summary(summary)

    assert "<html" not in formatted.lower()
    assert "analysis_report.html" not in formatted
    assert "analysis_report.html" not in json.dumps(summary_dict)


def test_module_does_not_add_biological_interpretation() -> None:
    summary = format_report_summary(
        build_report_summary(sample_plan(), sample_manifest(), sample_qc_report())
    )

    assert "biological" not in summary.lower()
    assert "interpretation" not in summary.lower()
