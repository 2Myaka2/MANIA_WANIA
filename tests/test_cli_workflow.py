import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_FIXTURE_DIR = PROJECT_ROOT / "tests/fixtures/notebook_export_v1_1_tiny"
CONDITIONS = ("normal", "tumor")


def run_python_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mania", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def workflow_payload(
    tmp_path: Path,
    *,
    conditions: list[str] | None = None,
    include_conditions: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_dir": str(NOTEBOOK_FIXTURE_DIR),
        "output_dir": str(tmp_path / "mania_output"),
        "diagnostics_output_dir": str(tmp_path / "diagnostics"),
        "frame_time_ps": 100.0,
    }
    if include_conditions:
        payload["conditions"] = list(CONDITIONS) if conditions is None else conditions
    return payload


def write_json_config(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_yaml_config(path: Path, payload: dict[str, object]) -> Path:
    lines = [
        f"source_dir: {payload['source_dir']}",
        f"output_dir: {payload['output_dir']}",
        f"diagnostics_output_dir: {payload['diagnostics_output_dir']}",
        f"frame_time_ps: {payload['frame_time_ps']}",
    ]
    conditions = payload.get("conditions")
    if isinstance(conditions, list):
        lines.append("conditions:")
        lines.extend(f"  - {condition}" for condition in conditions)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_workflow_config(
    path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return run_python_module("workflow", "run", "--config", str(path), *extra_args)


def load_stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def make_passing_notebook_source(tmp_path: Path) -> Path:
    source_dir = tmp_path / "passing_notebook_export"
    shutil.copytree(NOTEBOOK_FIXTURE_DIR, source_dir)
    (source_dir / "centrality_normal.csv").write_text(
        (source_dir / "centrality_normal.csv")
        .read_text(encoding="utf-8")
        .replace(",0.70,", ",0.75,"),
        encoding="utf-8",
    )
    (source_dir / "centrality_tumor.csv").write_text(
        (source_dir / "centrality_tumor.csv")
        .read_text(encoding="utf-8")
        .replace(",0.80,", ",0.60,"),
        encoding="utf-8",
    )
    return source_dir


def test_cli_workflow_runs_from_json_config(tmp_path: Path) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["workflow"] == "notebook_export_graph_diagnostics"
    assert payload["conditions"] == ["normal", "tumor"]
    assert payload["passed"] is False
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert (tmp_path / "mania_output" / "normal" / "nodes.csv").exists()
    assert (tmp_path / "mania_output" / "tumor" / "nodes.csv").exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics.json"
    ).exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics_summary.json"
    ).exists()


def test_cli_workflow_runs_from_yaml_config(tmp_path: Path) -> None:
    config_path = write_yaml_config(
        tmp_path / "workflow.yaml",
        workflow_payload(tmp_path),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["conditions"] == ["normal", "tumor"]
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics_summary.json"
    ).exists()


def test_cli_workflow_supports_inferred_conditions(tmp_path: Path) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path, include_conditions=False),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["conditions"] == ["normal", "tumor"]


def test_cli_workflow_supports_single_condition(tmp_path: Path) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path, conditions=["normal"]),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["conditions"] == ["normal"]
    assert (tmp_path / "mania_output" / "normal").is_dir()
    assert not (tmp_path / "mania_output" / "tumor").exists()
    assert (tmp_path / "diagnostics" / "normal" / "graph_diagnostics.json").exists()
    assert not (tmp_path / "diagnostics" / "tumor").exists()


def test_cli_workflow_missing_config_exits_nonzero(tmp_path: Path) -> None:
    result = run_workflow_config(tmp_path / "missing.json")

    assert result.returncode != 0
    assert "Workflow failed" in result.stderr


def test_cli_workflow_invalid_config_exits_nonzero(tmp_path: Path) -> None:
    payload = workflow_payload(tmp_path)
    payload["frame_time_ps"] = 0
    config_path = write_json_config(tmp_path / "workflow.json", payload)

    result = run_workflow_config(config_path)

    assert result.returncode != 0
    assert "Workflow failed" in result.stderr


def test_cli_workflow_diagnostics_passed_false_still_exits_zero(
    tmp_path: Path,
) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["passed"] is False


def test_cli_workflow_fail_on_diagnostics_failure_exits_two(
    tmp_path: Path,
) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path),
    )

    result = run_workflow_config(
        config_path,
        "--fail-on-diagnostics-failure",
    )
    payload = load_stdout_json(result)

    assert result.returncode == 2
    assert payload["passed"] is False
    assert (tmp_path / "mania_output" / "run_meta.json").exists()
    assert (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics_summary.json"
    ).exists()


def test_cli_workflow_fail_on_diagnostics_failure_passed_true_exits_zero(
    tmp_path: Path,
) -> None:
    source_dir = make_passing_notebook_source(tmp_path)
    payload = workflow_payload(tmp_path)
    payload["source_dir"] = str(source_dir)
    config_path = write_json_config(tmp_path / "workflow.json", payload)

    result = run_workflow_config(
        config_path,
        "--fail-on-diagnostics-failure",
    )
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert payload["passed"] is True


def test_cli_workflow_invalid_config_with_fail_flag_exits_nonzero(
    tmp_path: Path,
) -> None:
    payload = workflow_payload(tmp_path)
    payload["frame_time_ps"] = 0
    config_path = write_json_config(tmp_path / "workflow.json", payload)

    result = run_workflow_config(
        config_path,
        "--fail-on-diagnostics-failure",
    )

    assert result.returncode != 0
    assert "Workflow failed" in result.stderr


def test_cli_workflow_help_mentions_fail_on_diagnostics_failure() -> None:
    result = run_python_module("workflow", "run", "--help")

    assert result.returncode == 0
    assert "--fail-on-diagnostics-failure" in result.stdout


def test_cli_workflow_output_contains_written_path_counts(tmp_path: Path) -> None:
    config_path = write_json_config(
        tmp_path / "workflow.json",
        workflow_payload(tmp_path),
    )

    result = run_workflow_config(config_path)
    payload = load_stdout_json(result)

    assert result.returncode == 0
    assert isinstance(payload["export_written_paths_count"], int)
    assert isinstance(payload["diagnostics_written_paths_count"], int)
    assert payload["export_written_paths_count"] > 0
    assert payload["diagnostics_written_paths_count"] > 0
