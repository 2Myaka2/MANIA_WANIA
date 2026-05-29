import subprocess
import sys
from pathlib import Path

import pytest

import mania.cli as cli
from mania import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_python_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mania", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_python_module_version_prints_package_version() -> None:
    result = run_python_module("--version")

    assert result.returncode == 0
    assert __version__ in result.stdout


def test_python_module_validate_config_accepts_example_config() -> None:
    result = run_python_module(
        "validate-config",
        "configs/mania.example.yaml",
    )

    assert result.returncode == 0
    assert "Config is valid" in result.stdout


def test_python_module_run_prints_pipeline_plan() -> None:
    result = run_python_module(
        "run",
        "--config",
        "configs/mania.example.yaml",
    )

    assert result.returncode == 0
    assert "MANIA pipeline execution is not implemented yet." in result.stdout
    assert "Project: NaPi2b_NORM_TUMOR" in result.stdout
    assert "Run mode: full" in result.stdout
    assert "Conditions: normal, tumor" in result.stdout


def test_run_command_prints_pipeline_plan(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["mania", "run", "--config", "configs/mania.example.yaml"],
    )

    cli.main()

    captured = capsys.readouterr()
    assert "MANIA pipeline execution is not implemented yet." in captured.out
    assert "Project: NaPi2b_NORM_TUMOR" in captured.out
    assert "Run ID: run_001" in captured.out
    assert "Run mode: full" in captured.out
    assert "Conditions: normal, tumor" in captured.out
    assert "Output directory: mania_output" in captured.out


def test_run_command_requires_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["mania", "run"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "the following arguments are required: --config" in captured.err


def test_run_command_invalid_config_exits_nonzero(monkeypatch) -> None:
    def raise_invalid_config(path: Path) -> object:
        raise ValueError(f"bad config: {path}")

    monkeypatch.setattr("sys.argv", ["mania", "run", "--config", "bad.yaml"])
    monkeypatch.setattr(cli, "load_config", raise_invalid_config)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code != 0
