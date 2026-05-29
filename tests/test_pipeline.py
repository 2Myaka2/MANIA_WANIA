from pathlib import Path

from mania.config import load_config
from mania.pipeline import build_pipeline_plan, format_pipeline_plan

EXAMPLE_CONFIG = Path("configs/mania.example.yaml")


def test_build_pipeline_plan_reads_project_name() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert plan.project_name == "NaPi2b_NORM_TUMOR"


def test_build_pipeline_plan_reads_run_id() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert plan.run_id == "run_001"


def test_build_pipeline_plan_reads_run_mode() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert plan.run_mode == "full"


def test_build_pipeline_plan_reads_conditions_in_config_order() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert plan.conditions == ("normal", "tumor")


def test_build_pipeline_plan_reads_output_dir() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert plan.output_dir == "mania_output"


def test_format_pipeline_plan_contains_expected_project_name() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert "Project: NaPi2b_NORM_TUMOR" in format_pipeline_plan(plan)


def test_format_pipeline_plan_contains_expected_run_id() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert "Run ID: run_001" in format_pipeline_plan(plan)


def test_format_pipeline_plan_contains_expected_run_mode() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert "Run mode: full" in format_pipeline_plan(plan)


def test_format_pipeline_plan_contains_expected_conditions() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert "Conditions: normal, tumor" in format_pipeline_plan(plan)


def test_format_pipeline_plan_contains_expected_output_directory() -> None:
    plan = build_pipeline_plan(load_config(EXAMPLE_CONFIG))

    assert "Output directory: mania_output" in format_pipeline_plan(plan)
