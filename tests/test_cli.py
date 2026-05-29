from pathlib import Path

import pytest

import mania.cli as cli


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
