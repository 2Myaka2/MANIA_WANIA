import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import mania.cli as cli

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_SOURCE_PATH = PROJECT_ROOT / "src" / "mania" / "cli.py"
BASE_COMMAND = (
    "preprocessing",
    "run-graph-export",
    "--manifest",
    "manifest.yaml",
    "--output",
    "out",
)
STAGE15_ORDER = (
    "build_preprocessing_graph_workflow_plan",
    "load_preprocessing_graph_workflow_condition_runtimes",
    "compute_preprocessing_graph_workflow_rg_contacts",
    "export_preprocessing_graph_workflow_artifacts",
    "run_preprocessing_graph_workflow_diagnostics",
    "compare_preprocessing_graph_workflow_reference_artifacts",
)


@dataclass(frozen=True)
class FakeLayout:
    output_dir: str = "out"

    def to_dict(self) -> dict[str, object]:
        return {"output_dir": self.output_dir}


@dataclass(frozen=True)
class FakePlan:
    passed: bool = True
    output_layout: FakeLayout = field(default_factory=FakeLayout)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "output_layout": self.output_layout.to_dict(),
        }


@dataclass(frozen=True)
class FakeResult:
    stage: str
    passed: bool = True
    skipped: bool = False
    raw: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class FakeComputationResult(FakeResult):
    include_rg: bool = True
    include_contacts: bool = True

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["include_rg"] = self.include_rg
        payload["include_contacts"] = self.include_contacts
        return payload


def run_python_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mania", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def invoke_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
    expected_exit_code: int = 0,
) -> tuple[object, str, str]:
    monkeypatch.setattr(sys, "argv", ["mania", *args])
    if expected_exit_code == 0:
        cli.main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == expected_exit_code
    return exc_info.value.code, captured.out, captured.err


def stdout_json(stdout: str) -> dict[str, object]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def install_fake_stage15(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failing_stage: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    calls: list[str] = []
    received: dict[str, Any] = {}

    def fake_build(options: object) -> FakePlan:
        calls.append("build_preprocessing_graph_workflow_plan")
        received["options"] = options
        return FakePlan(passed=failing_stage != "plan")

    def fake_load(
        manifest_path: str | Path,
        *,
        expected_condition_names: tuple[str, ...],
    ) -> FakeResult:
        calls.append("load_preprocessing_graph_workflow_condition_runtimes")
        received["manifest_path"] = Path(manifest_path)
        received["expected_condition_names"] = expected_condition_names
        return FakeResult(
            "runtime_loading",
            passed=failing_stage != "runtime_loading",
            raw=object(),
        )

    def fake_compute(
        runtime_loading: object,
        *,
        include_rg: bool,
        include_contacts: bool,
    ) -> FakeComputationResult:
        calls.append("compute_preprocessing_graph_workflow_rg_contacts")
        received["runtime_loading"] = runtime_loading
        received["include_rg"] = include_rg
        received["include_contacts"] = include_contacts
        return FakeComputationResult(
            "computation",
            passed=failing_stage != "computation",
            include_rg=include_rg,
            include_contacts=include_contacts,
            raw=object(),
        )

    def fake_export(
        computation: FakeComputationResult,
        output_layout: object,
    ) -> FakeResult:
        calls.append("export_preprocessing_graph_workflow_artifacts")
        received["computation"] = computation
        received["output_layout"] = output_layout
        passed = failing_stage != "graph_export" and computation.include_contacts
        return FakeResult("graph_export", passed=passed, raw=object())

    def fake_diagnostics(
        graph_export: object,
        *,
        write_report_json: bool,
        create_parent_directories: bool = True,
    ) -> FakeResult:
        calls.append("run_preprocessing_graph_workflow_diagnostics")
        received["diagnostics_graph_export"] = graph_export
        received["diagnostics_kwargs"] = {
            "write_report_json": write_report_json,
            "create_parent_directories": create_parent_directories,
        }
        return FakeResult(
            "diagnostics",
            passed=failing_stage != "diagnostics",
            raw=object(),
        )

    def fake_reference(
        graph_export: object,
        options: Any,
        output_layout: object,
        *,
        write_report_json: bool,
        create_parent_directories: bool = True,
    ) -> FakeResult:
        calls.append("compare_preprocessing_graph_workflow_reference_artifacts")
        received["reference_graph_export"] = graph_export
        received["reference_options"] = options
        received["reference_output_layout"] = output_layout
        received["reference_kwargs"] = {
            "write_report_json": write_report_json,
            "create_parent_directories": create_parent_directories,
        }
        enabled = bool(options.enable_reference_comparison)
        return FakeResult(
            "reference_comparison",
            passed=failing_stage != "reference_comparison",
            skipped=not enabled,
            raw=object(),
        )

    monkeypatch.setattr(cli, "build_preprocessing_graph_workflow_plan", fake_build)
    monkeypatch.setattr(
        cli,
        "load_preprocessing_graph_workflow_condition_runtimes",
        fake_load,
    )
    monkeypatch.setattr(
        cli,
        "compute_preprocessing_graph_workflow_rg_contacts",
        fake_compute,
    )
    monkeypatch.setattr(
        cli,
        "export_preprocessing_graph_workflow_artifacts",
        fake_export,
    )
    monkeypatch.setattr(
        cli,
        "run_preprocessing_graph_workflow_diagnostics",
        fake_diagnostics,
    )
    monkeypatch.setattr(
        cli,
        "compare_preprocessing_graph_workflow_reference_artifacts",
        fake_reference,
    )
    return calls, received


def test_cli_help_works_without_mdanalysis() -> None:
    result = run_python_module("preprocessing", "--help")

    assert result.returncode == 0
    assert "run-graph-export" in result.stdout
    assert "MDAnalysis" not in result.stderr


@pytest.mark.parametrize(
    "args",
    (
        ("preprocessing", "run-graph-export", "--output", "out"),
        ("preprocessing", "run-graph-export", "--manifest", "manifest.yaml"),
    ),
)
def test_graph_export_requires_manifest_and_output_args(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, ...],
) -> None:
    called = False

    def fake_build(options: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(cli, "build_preprocessing_graph_workflow_plan", fake_build)

    _, _, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *args,
        expected_exit_code=2,
    )

    assert "the following arguments are required" in stderr
    assert called is False


def test_default_command_builds_options_and_calls_stage15_in_order(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    payload = stdout_json(stdout)
    options = received["options"]

    assert payload["passed"] is True
    assert calls == list(STAGE15_ORDER)
    assert options.manifest_path == Path("manifest.yaml")
    assert options.output_dir == Path("out")
    assert options.reference_semantics == "MANIA_analysis_v1_2"
    assert options.enable_reference_comparison is False
    assert options.reference_nodes_csv_path is None
    assert options.reference_edges_csv_path is None
    assert options.reference_graph_json_path is None
    assert received["expected_condition_names"] == ("normal", "tumor")


@pytest.mark.parametrize(
    ("failing_stage", "expected_calls"),
    (
        ("plan", STAGE15_ORDER[:1]),
        ("runtime_loading", STAGE15_ORDER[:2]),
        ("computation", STAGE15_ORDER[:3]),
        ("graph_export", STAGE15_ORDER[:4]),
        ("diagnostics", STAGE15_ORDER[:5]),
        ("reference_comparison", STAGE15_ORDER),
    ),
)
def test_stage15_failure_stops_at_failed_stage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing_stage: str,
    expected_calls: tuple[str, ...],
) -> None:
    calls, _ = install_fake_stage15(monkeypatch, failing_stage=failing_stage)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)

    assert payload["stage"] == failing_stage
    assert payload["passed"] is False
    assert calls == list(expected_calls)


def test_reference_comparison_disabled_by_default_is_called_as_skipped_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    payload = stdout_json(stdout)
    reference_payload = payload["reference_comparison"]

    assert calls[-1] == "compare_preprocessing_graph_workflow_reference_artifacts"
    assert received["reference_options"].enable_reference_comparison is False
    assert isinstance(reference_payload, dict)
    assert reference_payload["passed"] is True
    assert reference_payload["skipped"] is True


def test_reference_comparison_enabled_requires_explicit_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_unexpected_call(*args: object, **kwargs: object) -> object:
        pytest.fail("runtime workflow APIs must not be called after plan failure")

    monkeypatch.setattr(
        cli,
        "load_preprocessing_graph_workflow_condition_runtimes",
        fail_unexpected_call,
    )

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--enable-reference-comparison",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    plan_payload = payload["plan"]

    assert payload["stage"] == "plan"
    assert isinstance(plan_payload, dict)
    assert "reference_paths_required" in json.dumps(plan_payload)


def test_reference_comparison_enabled_passes_explicit_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--enable-reference-comparison",
        "--reference-nodes",
        "ref/nodes.csv",
        "--reference-edges",
        "ref/edges.csv",
        "--reference-graph-json",
        "ref/graph.json",
    )
    options = received["options"]

    assert options.enable_reference_comparison is True
    assert options.reference_nodes_csv_path == Path("ref/nodes.csv")
    assert options.reference_edges_csv_path == Path("ref/edges.csv")
    assert options.reference_graph_json_path == Path("ref/graph.json")


def test_skip_diagnostics_still_allows_enabled_reference_comparison(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--skip-diagnostics",
        "--enable-reference-comparison",
        "--reference-nodes",
        "ref/nodes.csv",
        "--reference-edges",
        "ref/edges.csv",
        "--reference-graph-json",
        "ref/graph.json",
    )
    payload = stdout_json(stdout)

    assert "run_preprocessing_graph_workflow_diagnostics" not in calls
    assert calls[-1] == "compare_preprocessing_graph_workflow_reference_artifacts"
    assert payload["diagnostics"] == {"passed": True, "skipped": True}


def test_skip_rg_passes_include_rg_false_to_computation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    invoke_cli(monkeypatch, capsys, *BASE_COMMAND, "--skip-rg")

    assert received["include_rg"] is False
    assert received["include_contacts"] is True


def test_skip_contacts_passes_include_contacts_false_and_export_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--skip-contacts",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)

    assert received["include_contacts"] is False
    assert calls == list(STAGE15_ORDER[:4])
    assert payload["stage"] == "graph_export"
    assert payload["passed"] is False


def test_expected_condition_args_are_forwarded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--expected-condition",
        "normal",
        "--expected-condition",
        "tumor",
    )

    assert received["expected_condition_names"] == ("normal", "tumor")


def test_no_write_diagnostics_report_flag_is_forwarded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--no-write-diagnostics-report",
    )

    assert received["diagnostics_kwargs"]["write_report_json"] is False


def test_no_write_reference_comparison_flag_is_forwarded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--enable-reference-comparison",
        "--reference-nodes",
        "ref/nodes.csv",
        "--reference-edges",
        "ref/edges.csv",
        "--reference-graph-json",
        "ref/graph.json",
        "--no-write-reference-comparison",
    )

    assert received["reference_kwargs"]["write_report_json"] is False


def test_graph_export_output_is_deterministic_json_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    payload = stdout_json(stdout)

    json.dumps(payload, allow_nan=False, sort_keys=True)
    assert "raw" not in stdout


def test_cli_does_not_auto_discover_local_md_or_reference_artifacts() -> None:
    source = CLI_SOURCE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "glob(",
        "rglob(",
        "local_md",
        "napi2b_10ns.yaml",
        "data/reference",
        "notebooks_libraries_v1_2",
        "MANIA_analysis_v1_2.ipynb",
    ):
        assert forbidden not in source


def test_cli_does_not_add_notebook_temporal_or_frontend_execution_paths() -> None:
    source = CLI_SOURCE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "nbconvert",
        "jupyter",
        "papermill",
        "execute_notebook",
        "temporal_rin",
        "temporal RIN",
        "frontend",
        "frontend_payload",
        "export_frontend",
    ):
        assert forbidden not in source


def test_cli_does_not_import_default_scientific_stack() -> None:
    source = CLI_SOURCE_PATH.read_text(encoding="utf-8")

    for forbidden in ("MDAnalysis", "numpy", "pandas", "networkx", "pyarrow"):
        assert forbidden not in source
