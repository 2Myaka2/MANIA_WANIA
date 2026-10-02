"""Developer profiler must preserve calls and reject completed-result reuse."""

import importlib.util
import json
import sys
from contextlib import ExitStack
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "profile_production_performance",
    Path(__file__).parents[1] / "tools/profile_production_performance.py",
)
assert SPEC and SPEC.loader
profiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profiler)


def test_nested_timer_preserves_result_and_accounts_once():
    clock = iter([0.0, 1.0, 4.0, 6.0])
    timer = profiler.CoarseTimer(lambda: next(clock))
    sentinel = object()

    def child():
        return sentinel

    measured_child = timer.wrap(child, "child")

    def parent():
        return measured_child()

    assert timer.wrap(parent, "parent")() is sentinel
    rows = {row["stage"]: row for row in timer.report(8.0)}
    assert rows["child"]["wall_seconds"] == 3.0
    assert rows["parent"]["wall_seconds"] == 3.0
    assert rows["wrapper/uninstrumented"]["wall_seconds"] == 2.0
    assert sum(row["percent_wall"] for row in rows.values()) == 100.0


def test_exception_is_preserved_and_stack_unwound():
    timer = profiler.CoarseTimer()
    error = RuntimeError("unchanged")

    def fail():
        raise error

    with pytest.raises(RuntimeError) as caught:
        timer.wrap(fail, "failing")()
    assert caught.value is error
    assert not timer.stack
    assert next(iter(timer.rows.values()))["calls"] == 1


def test_fresh_run_guard(tmp_path):
    command = [
        "production",
        "run",
        "--output-root",
        str(tmp_path / "fresh"),
        "--technical-manifest",
        "technical.json",
    ]
    assert profiler.validate_command(command) == tmp_path / "fresh"
    with pytest.raises(ValueError, match="fresh"):
        profiler.validate_command([*command, "--resume"])
    (tmp_path / "fresh").mkdir()
    with pytest.raises(ValueError, match="must not exist"):
        profiler.validate_command(command)


@pytest.mark.parametrize("command", [["production", "validate"], ["production", "run"]])
def test_non_benchmark_commands_rejected(command):
    with pytest.raises(ValueError):
        profiler.validate_command(command)


def test_real_boundaries_install_and_restore():
    pytest.importorskip("MDAnalysis")
    from mania import production_run

    original = production_run.file_digest
    with ExitStack() as contexts:
        profiler.CoarseTimer().install(contexts)
        assert production_run.file_digest is not original
        assert sys.modules["mania.production_run"].file_digest.__wrapped__ is original
    assert production_run.file_digest is original


def test_cli_usage_failure_is_recorded_without_masking_exit(tmp_path, monkeypatch):
    from mania import cli

    def usage_failure():
        raise SystemExit(2)

    monkeypatch.setattr(cli, "main", usage_failure)
    monkeypatch.delitem(sys.modules, "mania.production_run", raising=False)
    evidence = tmp_path / "evidence"
    assert (
        profiler.main(
            [
                "--mode",
                "plain",
                "--evidence",
                str(evidence),
                "--",
                "production",
                "run",
                "--output-root",
                str(tmp_path / "fresh"),
                "--technical-manifest",
                "missing.json",
            ]
        )
        == 2
    )
    recorded = json.loads((evidence / "timings.json").read_text())
    assert recorded["exit_code"] == 2
    assert recorded["production_module"] is None
    assert recorded["output_bytes"] == 0
