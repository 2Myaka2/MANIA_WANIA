import builtins
import json
import os
from pathlib import Path
from typing import NoReturn

import mania
from mania.constants import SCHEMA_VERSION
from mania.export.run_meta import (
    RunMeta,
    build_run_meta,
    format_run_meta_summary,
    run_meta_to_dict,
)
from mania.pipeline import PipelinePlan

EXPECTED_RUN_META_KEYS = {
    "schema_version",
    "mania_version",
    "project_name",
    "run_id",
    "run_mode",
    "conditions",
    "output_dir",
}


def sample_plan() -> PipelinePlan:
    return PipelinePlan(
        project_name="NaPi2b_NORM_TUMOR",
        run_id="run_001",
        run_mode="full",
        conditions=("normal", "tumor"),
        output_dir="mania_output",
    )


def fail_filesystem_access(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("run metadata helpers must not inspect or write files")


def test_build_run_meta_reads_project_name_from_pipeline_plan() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.project_name == "NaPi2b_NORM_TUMOR"


def test_build_run_meta_reads_run_id_from_pipeline_plan() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.run_id == "run_001"


def test_build_run_meta_reads_run_mode_from_pipeline_plan() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.run_mode == "full"


def test_build_run_meta_reads_conditions_from_pipeline_plan() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.conditions == ("normal", "tumor")


def test_build_run_meta_reads_output_dir_from_pipeline_plan() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.output_dir == "mania_output"


def test_build_run_meta_uses_schema_version() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.schema_version == SCHEMA_VERSION


def test_build_run_meta_uses_mania_version() -> None:
    run_meta = build_run_meta(sample_plan())

    assert run_meta.mania_version == mania.__version__


def test_run_meta_to_dict_returns_basic_json_types() -> None:
    run_meta_dict = run_meta_to_dict(build_run_meta(sample_plan()))

    assert set(run_meta_dict) == EXPECTED_RUN_META_KEYS
    assert isinstance(run_meta_dict["schema_version"], str)
    assert isinstance(run_meta_dict["mania_version"], str)
    assert isinstance(run_meta_dict["project_name"], str)
    assert isinstance(run_meta_dict["run_id"], str)
    assert isinstance(run_meta_dict["run_mode"], str)
    assert isinstance(run_meta_dict["conditions"], list)
    assert isinstance(run_meta_dict["output_dir"], str)


def test_run_meta_to_dict_can_be_json_dumped() -> None:
    run_meta_dict = run_meta_to_dict(build_run_meta(sample_plan()))

    assert json.dumps(run_meta_dict)


def test_run_meta_to_dict_converts_tuple_fields_to_lists() -> None:
    run_meta_dict = run_meta_to_dict(build_run_meta(sample_plan()))

    assert run_meta_dict["conditions"] == ["normal", "tumor"]


def test_format_run_meta_summary_contains_expected_fields() -> None:
    summary = format_run_meta_summary(build_run_meta(sample_plan()))

    assert "Project: NaPi2b_NORM_TUMOR" in summary
    assert "Run ID: run_001" in summary
    assert "Run mode: full" in summary
    assert "Conditions: normal, tumor" in summary
    assert "Output directory: mania_output" in summary
    assert f"Schema version: {SCHEMA_VERSION}" in summary


def test_format_run_meta_summary_uses_stable_line_order() -> None:
    summary = format_run_meta_summary(build_run_meta(sample_plan()))

    assert summary.splitlines() == [
        "MANIA run metadata skeleton",
        "Project: NaPi2b_NORM_TUMOR",
        "Run ID: run_001",
        "Run mode: full",
        "Conditions: normal, tumor",
        "Output directory: mania_output",
        f"Schema version: {SCHEMA_VERSION}",
    ]


def test_module_does_not_inspect_or_write_to_filesystem(monkeypatch) -> None:
    monkeypatch.setattr(builtins, "open", fail_filesystem_access)
    monkeypatch.setattr(os.path, "exists", fail_filesystem_access)
    monkeypatch.setattr(os, "makedirs", fail_filesystem_access)
    monkeypatch.setattr(Path, "exists", fail_filesystem_access)
    monkeypatch.setattr(Path, "is_file", fail_filesystem_access)
    monkeypatch.setattr(Path, "is_dir", fail_filesystem_access)
    monkeypatch.setattr(Path, "mkdir", fail_filesystem_access)
    monkeypatch.setattr(Path, "read_text", fail_filesystem_access)
    monkeypatch.setattr(Path, "write_text", fail_filesystem_access)

    run_meta = build_run_meta(sample_plan())
    run_meta_dict = run_meta_to_dict(run_meta)
    summary = format_run_meta_summary(run_meta)

    assert isinstance(run_meta, RunMeta)
    assert run_meta_dict["output_dir"] == "mania_output"
    assert summary.startswith("MANIA run metadata skeleton")


def test_run_meta_to_dict_does_not_include_created_at() -> None:
    run_meta_dict = run_meta_to_dict(build_run_meta(sample_plan()))

    assert "created_at" not in run_meta_dict
