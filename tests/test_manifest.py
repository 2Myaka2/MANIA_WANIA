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
from mania.export.manifest import (
    Manifest,
    build_manifest,
    format_manifest_summary,
    manifest_to_dict,
)
from mania.pipeline import PipelinePlan

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "mania_version",
    "project_name",
    "run_id",
    "run_mode",
    "conditions",
    "per_condition_artifacts",
    "cross_condition_artifacts",
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
    raise AssertionError("manifest helpers must not inspect or write files")


def test_build_manifest_reads_project_name_from_pipeline_plan() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.project_name == "NaPi2b_NORM_TUMOR"


def test_build_manifest_reads_run_id_from_pipeline_plan() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.run_id == "run_001"


def test_build_manifest_reads_run_mode_from_pipeline_plan() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.run_mode == "full"


def test_build_manifest_reads_conditions_from_pipeline_plan() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.conditions == ("normal", "tumor")


def test_build_manifest_uses_schema_version() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.schema_version == SCHEMA_VERSION


def test_build_manifest_uses_mania_version() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.mania_version == mania.__version__


def test_build_manifest_includes_per_condition_artifacts() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.per_condition_artifacts == PER_CONDITION_ARTIFACTS


def test_build_manifest_includes_cross_condition_artifacts() -> None:
    manifest = build_manifest(sample_plan())

    assert manifest.cross_condition_artifacts == CROSS_CONDITION_ARTIFACTS


def test_manifest_to_dict_returns_basic_json_types() -> None:
    manifest_dict = manifest_to_dict(build_manifest(sample_plan()))

    assert set(manifest_dict) == EXPECTED_MANIFEST_KEYS
    assert isinstance(manifest_dict["schema_version"], str)
    assert isinstance(manifest_dict["mania_version"], str)
    assert isinstance(manifest_dict["project_name"], str)
    assert isinstance(manifest_dict["run_id"], str)
    assert isinstance(manifest_dict["run_mode"], str)
    assert isinstance(manifest_dict["conditions"], list)
    assert isinstance(manifest_dict["per_condition_artifacts"], list)
    assert isinstance(manifest_dict["cross_condition_artifacts"], list)


def test_manifest_to_dict_can_be_json_dumped() -> None:
    manifest_dict = manifest_to_dict(build_manifest(sample_plan()))

    assert json.dumps(manifest_dict)


def test_manifest_to_dict_converts_tuple_fields_to_lists() -> None:
    manifest_dict = manifest_to_dict(build_manifest(sample_plan()))

    assert manifest_dict["conditions"] == ["normal", "tumor"]
    assert manifest_dict["per_condition_artifacts"] == list(PER_CONDITION_ARTIFACTS)
    assert manifest_dict["cross_condition_artifacts"] == list(CROSS_CONDITION_ARTIFACTS)


def test_comparison_and_stats_remain_cross_condition_artifacts() -> None:
    manifest = build_manifest(sample_plan())

    assert "comparison.csv" in manifest.cross_condition_artifacts
    assert "stats.csv" in manifest.cross_condition_artifacts
    assert "comparison.csv" not in manifest.per_condition_artifacts
    assert "stats.csv" not in manifest.per_condition_artifacts


def test_graph_json_remains_per_condition_artifact() -> None:
    manifest = build_manifest(sample_plan())

    assert "graph.json" in manifest.per_condition_artifacts
    assert "graph.json" not in manifest.cross_condition_artifacts


def test_format_manifest_summary_contains_expected_fields() -> None:
    summary = format_manifest_summary(build_manifest(sample_plan()))

    assert "Project: NaPi2b_NORM_TUMOR" in summary
    assert "Run ID: run_001" in summary
    assert "Run mode: full" in summary
    assert "Conditions: normal, tumor" in summary
    assert f"Schema version: {SCHEMA_VERSION}" in summary


def test_format_manifest_summary_uses_stable_line_order() -> None:
    summary = format_manifest_summary(build_manifest(sample_plan()))

    assert summary.splitlines() == [
        "MANIA manifest skeleton",
        "Project: NaPi2b_NORM_TUMOR",
        "Run ID: run_001",
        "Run mode: full",
        "Conditions: normal, tumor",
        f"Schema version: {SCHEMA_VERSION}",
    ]


def test_format_manifest_summary_does_not_write_files(monkeypatch) -> None:
    monkeypatch.setattr(builtins, "open", fail_filesystem_access)
    monkeypatch.setattr(Path, "write_text", fail_filesystem_access)

    summary = format_manifest_summary(build_manifest(sample_plan()))

    assert summary.startswith("MANIA manifest skeleton")


def test_build_manifest_does_not_inspect_or_require_artifact_existence(
    monkeypatch,
) -> None:
    monkeypatch.setattr(os.path, "exists", fail_filesystem_access)
    monkeypatch.setattr(Path, "exists", fail_filesystem_access)
    monkeypatch.setattr(Path, "is_file", fail_filesystem_access)
    monkeypatch.setattr(Path, "is_dir", fail_filesystem_access)
    plan = PipelinePlan(
        project_name="NaPi2b_NORM_TUMOR",
        run_id="run_001",
        run_mode="full",
        conditions=("normal", "tumor"),
        output_dir="missing_output_dir",
    )

    manifest = build_manifest(plan)

    assert isinstance(manifest, Manifest)
    assert manifest.project_name == "NaPi2b_NORM_TUMOR"
