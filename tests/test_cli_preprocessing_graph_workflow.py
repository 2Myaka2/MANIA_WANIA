import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import mania.cli as cli
from mania.preprocessing import (
    ContactProgressCallback,
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
    PreprocessingContactProgressEvent,
    PreprocessingFrameSamplingOptions,
)

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
STAGE15_ORDER_WITH_SCIENTIFIC = (
    "build_preprocessing_graph_workflow_plan",
    "load_preprocessing_graph_workflow_condition_runtimes",
    "compute_preprocessing_graph_workflow_rg_contacts",
    "export_preprocessing_graph_workflow_artifacts",
    "export_preprocessing_graph_workflow_scientific_csvs",
    "run_preprocessing_graph_workflow_diagnostics",
    "compare_preprocessing_graph_workflow_reference_artifacts",
)
VERBOSE_STAGE_MESSAGES = (
    "[1/7] Building workflow plan",
    "[2/7] Loading manifest and condition runtimes",
    "[3/7] Computing Rg and contacts",
    "[4/7] Exporting graph artifacts",
    "[5/7] Running graph diagnostics",
    "[6/7] Running/skipping reference comparison",
    "[7/7] Writing final summary",
)
VERBOSE_STAGE_MESSAGES_WITH_SCIENTIFIC = (
    "[1/8] Building workflow plan",
    "[2/8] Loading manifest and condition runtimes",
    "[3/8] Computing Rg and contacts",
    "[4/8] Exporting graph artifacts",
    "[5/8] Exporting optional scientific CSVs",
    "[6/8] Running graph diagnostics",
    "[7/8] Running/skipping reference comparison",
    "[8/8] Writing final summary",
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
    options: object | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "passed": self.passed,
            "output_layout": self.output_layout.to_dict(),
        }
        if self.options is not None:
            to_dict = getattr(self.options, "to_dict", None)
            if callable(to_dict):
                payload["options"] = to_dict()
        return payload


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
    frame_sampling: dict[str, object] | None = None
    contact_detection_options: dict[str, object] | None = None
    contact_computation_limits: dict[str, object] | None = None
    issues: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["include_rg"] = self.include_rg
        payload["include_contacts"] = self.include_contacts
        payload["frame_sampling"] = self.frame_sampling
        payload["contact_detection_options"] = (
            self.contact_detection_options
        )
        payload["contact_computation_limits"] = (
            self.contact_computation_limits
        )
        payload["issues"] = list(self.issues)
        payload["issue_count"] = len(self.issues)
        return payload


@dataclass(frozen=True)
class FakeScientificCsvExportResult:
    export_rg_timeseries: bool
    export_contact_edges: bool
    export_contacts_perframe: bool
    passed: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": "scientific_csv_export",
            "passed": self.passed,
            "skipped": False,
            "requested_exports": {
                "rg_timeseries": self.export_rg_timeseries,
                "contact_edges": self.export_contact_edges,
                "contacts_perframe": self.export_contacts_perframe,
            },
            "rg_timeseries_written": self.export_rg_timeseries and self.passed,
            "contact_edges_written": self.export_contact_edges and self.passed,
            "contacts_perframe_written": (
                self.export_contacts_perframe and self.passed
            ),
            "paths": {
                "rg_timeseries_csv": (
                    "out/rg/rg_timeseries.csv"
                    if self.export_rg_timeseries
                    else None
                ),
                "contact_edges_csv": (
                    "out/contacts/contact_edges.csv"
                    if self.export_contact_edges
                    else None
                ),
                "contacts_perframe_csv": (
                    "out/contacts/contacts_perframe.csv"
                    if self.export_contacts_perframe
                    else None
                ),
            },
            "validation": {
                "rg_timeseries": (
                    {"passed": True} if self.export_rg_timeseries else None
                ),
                "contact_edges": (
                    {"passed": True} if self.export_contact_edges else None
                ),
                "contacts_perframe": (
                    {"passed": True}
                    if self.export_contacts_perframe
                    else None
                ),
            },
            "issues": (
                []
                if self.passed
                else [
                    {
                        "kind": "forced_scientific_csv_export_failure",
                        "message": "Forced scientific CSV export failure.",
                    }
                ]
            ),
        }


@dataclass(frozen=True)
class FakeDiagnosticsWorkflowResult:
    passed: bool
    diagnostics_run: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "diagnostics_ran": True,
            "diagnostics_passed": False,
            "diagnostics_report_built": True,
            "diagnostics_report_json_written": True,
            "diagnostics_run": self.diagnostics_run,
            "issues": [
                {
                    "kind": "diagnostics_checks_failed",
                    "message": "Stage 14 graph_diagnostics step did not pass.",
                }
            ],
        }


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


def assert_no_verbose_stage_messages(text: str) -> None:
    for message in VERBOSE_STAGE_MESSAGES:
        assert message not in text


def install_fake_stage15(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failing_stage: str | None = None,
    diagnostics_result: object | None = None,
    scientific_result: object | None = None,
) -> tuple[list[str], dict[str, Any]]:
    calls: list[str] = []
    received: dict[str, Any] = {}

    def fake_build(options: object) -> FakePlan:
        calls.append("build_preprocessing_graph_workflow_plan")
        received["options"] = options
        return FakePlan(passed=failing_stage != "plan", options=options)

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
        frame_sampling: PreprocessingFrameSamplingOptions,
        contact_options: PreprocessingContactDetectionOptions,
        contact_computation_limits: (
            PreprocessingContactComputationLimits | None
        ) = None,
        progress_callback: ContactProgressCallback | None = None,
    ) -> FakeComputationResult:
        calls.append("compute_preprocessing_graph_workflow_rg_contacts")
        received["runtime_loading"] = runtime_loading
        received["include_rg"] = include_rg
        received["include_contacts"] = include_contacts
        received["frame_sampling"] = frame_sampling
        received["contact_options"] = contact_options
        received["contact_computation_limits"] = contact_computation_limits
        received["progress_callback"] = progress_callback
        if progress_callback is not None:
            progress_callback(
                PreprocessingContactProgressEvent(
                    condition_name="normal",
                    frame_index=None,
                    stage="condition_selection",
                    message=(
                        "contact selection="
                        f"{contact_options.contact_selection}"
                    ),
                )
            )
            progress_callback(
                PreprocessingContactProgressEvent(
                    condition_name="normal",
                    frame_index=0,
                    stage="frame_start",
                    message="selected residues=2",
                )
            )
            progress_callback(
                PreprocessingContactProgressEvent(
                    condition_name="normal",
                    frame_index=0,
                    stage="frame_candidates_built",
                    message="candidate residue pairs=1",
                    residue_count=2,
                    candidate_pair_count=1,
                )
            )
        computation_issues: tuple[dict[str, object], ...] = ()
        if failing_stage == "computation":
            computation_issues = (
                {
                    "kind": "contact_frame_limit_exceeded",
                    "message": (
                        "Contact computation skipped for condition 'normal' "
                        "frame 0 because estimated residue pairs 3 exceed "
                        "max_residue_pairs_per_frame=2."
                    ),
                },
            )
        return FakeComputationResult(
            "computation",
            passed=failing_stage != "computation",
            include_rg=include_rg,
            include_contacts=include_contacts,
            frame_sampling=frame_sampling.to_dict(),
            contact_detection_options=contact_options.to_dict(
                include_contact_selection=True
            ),
            contact_computation_limits=(
                None
                if contact_computation_limits is None
                else contact_computation_limits.to_dict()
            ),
            issues=computation_issues,
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

    def fake_scientific_csv_export(
        computation: object,
        output_layout: object,
        *,
        export_rg_timeseries: bool,
        export_contact_edges: bool,
        export_contacts_perframe: bool,
    ) -> object:
        calls.append("export_preprocessing_graph_workflow_scientific_csvs")
        received["scientific_computation"] = computation
        received["scientific_output_layout"] = output_layout
        received["scientific_export_flags"] = {
            "export_rg_timeseries": export_rg_timeseries,
            "export_contact_edges": export_contact_edges,
            "export_contacts_perframe": export_contacts_perframe,
        }
        if scientific_result is not None:
            return scientific_result
        return FakeScientificCsvExportResult(
            export_rg_timeseries=export_rg_timeseries,
            export_contact_edges=export_contact_edges,
            export_contacts_perframe=export_contacts_perframe,
            passed=failing_stage != "scientific_csv_export",
        )

    def fake_diagnostics(
        graph_export: object,
        *,
        write_report_json: bool,
        create_parent_directories: bool = True,
    ) -> object:
        calls.append("run_preprocessing_graph_workflow_diagnostics")
        received["diagnostics_graph_export"] = graph_export
        received["diagnostics_kwargs"] = {
            "write_report_json": write_report_json,
            "create_parent_directories": create_parent_directories,
        }
        if diagnostics_result is not None:
            return diagnostics_result
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
        "export_preprocessing_graph_workflow_scientific_csvs",
        fake_scientific_csv_export,
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


def test_graph_export_help_mentions_verbose_without_mdanalysis() -> None:
    result = run_python_module("preprocessing", "run-graph-export", "--help")

    assert result.returncode == 0
    assert "--verbose" in result.stdout
    assert "--export-scientific-csvs" in result.stdout
    assert "--export-rg-timeseries" in result.stdout
    assert "--export-contact-edges" in result.stdout
    assert "--export-contacts-perframe" in result.stdout
    assert "--frame-start" in result.stdout
    assert "--frame-stop" in result.stdout
    assert "--frame-stride" in result.stdout
    assert "--max-frames" in result.stdout
    assert "--contact-selection" in result.stdout
    assert "--contact-max-residue-pairs-per-frame" in result.stdout
    assert "--contact-max-distance-evaluations-per-frame" in result.stdout
    assert "MDAnalysis" not in result.stderr


def test_graph_export_accepts_scientific_csv_flags() -> None:
    args = cli.build_parser().parse_args(
        [
            *BASE_COMMAND,
            "--export-scientific-csvs",
            "--export-rg-timeseries",
            "--export-contact-edges",
            "--export-contacts-perframe",
        ]
    )

    assert args.export_scientific_csvs is True
    assert args.export_rg_timeseries is True
    assert args.export_contact_edges is True
    assert args.export_contacts_perframe is True


def test_graph_export_accepts_frame_sampling_flags() -> None:
    args = cli.build_parser().parse_args(
        [
            *BASE_COMMAND,
            "--frame-start",
            "100",
            "--frame-stop",
            "500",
            "--frame-stride",
            "5",
            "--max-frames",
            "100",
        ]
    )

    assert args.frame_start == 100
    assert args.frame_stop == 500
    assert args.frame_stride == 5
    assert args.max_frames == 100


def test_graph_export_accepts_contact_limit_flags() -> None:
    args = cli.build_parser().parse_args(
        [
            *BASE_COMMAND,
            "--contact-max-residue-pairs-per-frame",
            "50000",
            "--contact-max-distance-evaluations-per-frame",
            "1000000",
        ]
    )

    assert args.contact_max_residue_pairs_per_frame == 50000
    assert args.contact_max_distance_evaluations_per_frame == 1000000


@pytest.mark.parametrize("selection", ("all", "protein"))
def test_graph_export_accepts_contact_selection_flag(
    selection: str,
) -> None:
    args = cli.build_parser().parse_args(
        [
            *BASE_COMMAND,
            "--contact-selection",
            selection,
        ]
    )

    assert args.contact_selection == selection


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
    scientific_payload = payload["scientific_csv_export"]
    options = received["options"]

    assert payload["passed"] is True
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["passed"] is True
    assert scientific_payload["skipped"] is True
    assert calls == list(STAGE15_ORDER)
    assert options.manifest_path == Path("manifest.yaml")
    assert options.output_dir == Path("out")
    assert options.reference_semantics == "MANIA_analysis_v1_2"
    assert options.enable_reference_comparison is False
    assert options.reference_nodes_csv_path is None
    assert options.reference_edges_csv_path is None
    assert options.reference_graph_json_path is None
    assert options.frame_sampling == PreprocessingFrameSamplingOptions()
    assert options.contact_detection_options == (
        PreprocessingContactDetectionOptions()
    )
    assert received["frame_sampling"] == PreprocessingFrameSamplingOptions()
    assert received["contact_options"] == PreprocessingContactDetectionOptions()
    assert received["expected_condition_names"] == ("normal", "tumor")


@pytest.mark.parametrize(
    ("extra_args", "expected_sampling"),
    (
        (
            ("--frame-stride", "2"),
            PreprocessingFrameSamplingOptions(frame_stride=2),
        ),
        (
            ("--frame-start", "3"),
            PreprocessingFrameSamplingOptions(frame_start=3),
        ),
        (
            ("--frame-stop", "7"),
            PreprocessingFrameSamplingOptions(frame_stop=7),
        ),
        (
            ("--max-frames", "4"),
            PreprocessingFrameSamplingOptions(max_frames=4),
        ),
        (
            (
                "--frame-start",
                "100",
                "--frame-stop",
                "500",
                "--frame-stride",
                "5",
                "--max-frames",
                "100",
            ),
            PreprocessingFrameSamplingOptions(
                frame_start=100,
                frame_stop=500,
                frame_stride=5,
                max_frames=100,
            ),
        ),
    ),
)
def test_frame_sampling_flags_are_forwarded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra_args: tuple[str, ...],
    expected_sampling: PreprocessingFrameSamplingOptions,
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(monkeypatch, capsys, *BASE_COMMAND, *extra_args)
    payload = stdout_json(stdout)
    computation = payload["computation"]

    assert payload["passed"] is True
    assert received["frame_sampling"] == expected_sampling
    assert isinstance(computation, dict)
    assert computation["frame_sampling"] == expected_sampling.to_dict()


def test_contact_limit_flags_are_forwarded_and_serialized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-max-residue-pairs-per-frame",
        "50000",
        "--contact-max-distance-evaluations-per-frame",
        "1000000",
    )
    payload = stdout_json(stdout)
    limits = PreprocessingContactComputationLimits(
        max_residue_pairs_per_frame=50000,
        max_atom_distance_evaluations_per_frame=1000000,
    )
    plan = payload["plan"]
    computation = payload["computation"]

    assert received["options"].contact_computation_limits == limits
    assert received["contact_computation_limits"] == limits
    assert isinstance(plan, dict)
    assert plan["options"]["contact_computation_limits"] == limits.to_dict()
    assert isinstance(computation, dict)
    assert computation["contact_computation_limits"] == limits.to_dict()


def test_contact_selection_flag_is_forwarded_and_serialized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
    )
    payload = stdout_json(stdout)
    expected_options = PreprocessingContactDetectionOptions(
        contact_selection="protein"
    )
    plan = payload["plan"]
    computation = payload["computation"]

    assert received["options"].contact_detection_options == expected_options
    assert received["contact_options"] == expected_options
    assert isinstance(plan, dict)
    assert plan["options"]["contact_detection_options"] == (
        expected_options.to_dict(include_contact_selection=True)
    )
    assert isinstance(computation, dict)
    assert computation["contact_detection_options"] == (
        expected_options.to_dict(include_contact_selection=True)
    )


@pytest.mark.parametrize(
    ("extra_args", "expected_message"),
    (
        (("--frame-start", "-1"), "frame_start"),
        (("--frame-stride", "0"), "frame_stride"),
        (
            ("--frame-start", "5", "--frame-stop", "5"),
            "frame_stop",
        ),
        (("--max-frames", "0"), "max_frames"),
    ),
)
def test_invalid_frame_sampling_flags_fail_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra_args: tuple[str, ...],
    expected_message: str,
) -> None:
    called = False

    def fake_build(options: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(cli, "build_preprocessing_graph_workflow_plan", fake_build)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        *extra_args,
        expected_exit_code=2,
    )

    assert stdout == ""
    assert "Invalid frame sampling options" in stderr
    assert expected_message in stderr
    assert called is False


@pytest.mark.parametrize(
    ("flag", "value"),
    (
        ("--contact-max-residue-pairs-per-frame", "0"),
        ("--contact-max-residue-pairs-per-frame", "-1"),
        ("--contact-max-distance-evaluations-per-frame", "0"),
        ("--contact-max-distance-evaluations-per-frame", "-1"),
    ),
)
def test_invalid_contact_limit_flags_fail_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag: str,
    value: str,
) -> None:
    called = False

    def fake_build(options: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(cli, "build_preprocessing_graph_workflow_plan", fake_build)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        flag,
        value,
        expected_exit_code=2,
    )

    assert stdout == ""
    assert flag in stderr
    assert "positive integer" in stderr
    assert called is False


@pytest.mark.parametrize("selection", ("water", ""))
def test_invalid_contact_selection_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    selection: str,
) -> None:
    called = False

    def fake_build(options: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(cli, "build_preprocessing_graph_workflow_plan", fake_build)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        selection,
        expected_exit_code=2,
    )

    assert stdout == ""
    assert "--contact-selection" in stderr
    assert "invalid choice" in stderr
    assert called is False


def test_verbose_command_parses_and_calls_stage15_in_order(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--verbose",
    )

    assert stdout_json(stdout)["passed"] is True
    assert calls == list(STAGE15_ORDER)
    assert VERBOSE_STAGE_MESSAGES[0] in stderr
    assert "[1/8]" not in stderr


def test_non_verbose_graph_export_stdout_remains_final_json_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    payload = stdout_json(stdout)

    assert payload["passed"] is True
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    assert stderr == ""
    assert_no_verbose_stage_messages(stdout)
    assert_no_verbose_stage_messages(stderr)


def test_default_command_does_not_write_scientific_csvs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    calls, _ = install_fake_stage15(monkeypatch)
    output_dir = tmp_path / "out"

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        "preprocessing",
        "run-graph-export",
        "--manifest",
        "manifest.yaml",
        "--output",
        str(output_dir),
    )
    payload = stdout_json(stdout)
    scientific_payload = payload["scientific_csv_export"]

    assert "export_preprocessing_graph_workflow_scientific_csvs" not in calls
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["skipped"] is True
    assert not (output_dir / "rg" / "rg_timeseries.csv").exists()
    assert not (output_dir / "contacts" / "contact_edges.csv").exists()
    assert not (output_dir / "contacts" / "contacts_perframe.csv").exists()


def test_scientific_csv_shortcut_exports_safe_subset_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--export-scientific-csvs",
    )
    payload = stdout_json(stdout)
    scientific_payload = payload["scientific_csv_export"]

    assert calls == list(STAGE15_ORDER_WITH_SCIENTIFIC)
    assert received["scientific_export_flags"] == {
        "export_rg_timeseries": True,
        "export_contact_edges": True,
        "export_contacts_perframe": False,
    }
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["rg_timeseries_written"] is True
    assert scientific_payload["contact_edges_written"] is True
    assert scientific_payload["contacts_perframe_written"] is False
    assert scientific_payload["requested_exports"]["contacts_perframe"] is False


def test_scientific_csv_granular_flags_export_expected_outputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--export-rg-timeseries",
        "--export-contact-edges",
        "--export-contacts-perframe",
    )
    payload = stdout_json(stdout)
    scientific_payload = payload["scientific_csv_export"]

    assert received["scientific_export_flags"] == {
        "export_rg_timeseries": True,
        "export_contact_edges": True,
        "export_contacts_perframe": True,
    }
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["rg_timeseries_written"] is True
    assert scientific_payload["contact_edges_written"] is True
    assert scientific_payload["contacts_perframe_written"] is True


def test_requested_scientific_csv_failure_makes_cli_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = install_fake_stage15(
        monkeypatch,
        failing_stage="scientific_csv_export",
    )

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--export-rg-timeseries",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    scientific_payload = payload["scientific_csv_export"]
    graph_payload = payload["graph_export"]

    assert calls == list(STAGE15_ORDER_WITH_SCIENTIFIC[:5])
    assert payload["stage"] == "scientific_csv_export"
    assert payload["passed"] is False
    assert isinstance(graph_payload, dict)
    assert graph_payload["passed"] is True
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["passed"] is False
    assert "forced_scientific_csv_export_failure" in json.dumps(
        scientific_payload
    )


def test_verbose_scientific_csv_export_progress_stays_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--verbose",
        "--export-scientific-csvs",
    )
    payload = stdout_json(stdout)

    assert payload["passed"] is True
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    for message in VERBOSE_STAGE_MESSAGES_WITH_SCIENTIFIC:
        assert message in stderr
        assert message not in stdout
    assert "{" not in stderr


def test_verbose_graph_export_progress_goes_to_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--verbose",
    )
    payload = stdout_json(stdout)
    reference_payload = payload["reference_comparison"]

    assert payload["passed"] is True
    assert isinstance(reference_payload, dict)
    assert reference_payload["skipped"] is True
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    for message in VERBOSE_STAGE_MESSAGES:
        assert message in stderr
        assert message not in stdout
    for forbidden in ("%", "ETA", "remaining"):
        assert forbidden not in stderr


def test_verbose_contacts_progress_goes_to_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--verbose",
    )
    payload = stdout_json(stdout)

    assert payload["passed"] is True
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    assert "[contacts]" in stderr
    assert "condition=normal" in stderr
    assert "contact selection=all" in stderr
    assert "selected residues=2" in stderr
    assert "frame=0" in stderr
    assert "candidate residue pairs=1" in stderr
    assert "[contacts]" not in stdout


def test_cli_computation_failure_json_exposes_contact_limit_issue(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch, failing_stage="computation")

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-max-residue-pairs-per-frame",
        "2",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    computation = payload["computation"]

    assert payload["stage"] == "computation"
    assert payload["passed"] is False
    assert isinstance(computation, dict)
    assert "contact_frame_limit_exceeded" in json.dumps(computation)
    assert "max_residue_pairs_per_frame=2" in json.dumps(computation)


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


@pytest.mark.parametrize(
    ("failing_stage", "expected_stage_number", "expected_calls", "extra_args"),
    (
        ("plan", 1, STAGE15_ORDER[:1], ()),
        ("runtime_loading", 2, STAGE15_ORDER[:2], ()),
        ("computation", 3, STAGE15_ORDER[:3], ()),
        ("graph_export", 4, STAGE15_ORDER[:4], ()),
        ("diagnostics", 5, STAGE15_ORDER[:5], ()),
        (
            "reference_comparison",
            6,
            STAGE15_ORDER,
            (
                "--enable-reference-comparison",
                "--reference-nodes",
                "ref/nodes.csv",
                "--reference-edges",
                "ref/edges.csv",
                "--reference-graph-json",
                "ref/graph.json",
            ),
        ),
    ),
)
def test_verbose_stage_failure_prints_stderr_failure_and_json_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing_stage: str,
    expected_stage_number: int,
    expected_calls: tuple[str, ...],
    extra_args: tuple[str, ...],
) -> None:
    calls, _ = install_fake_stage15(monkeypatch, failing_stage=failing_stage)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        *extra_args,
        "--verbose",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    stage_message = VERBOSE_STAGE_MESSAGES[expected_stage_number - 1]

    assert payload["stage"] == failing_stage
    assert payload["passed"] is False
    assert calls == list(expected_calls)
    assert stage_message in stderr
    assert f"[{expected_stage_number}/7] Failed:" in stderr
    assert VERBOSE_STAGE_MESSAGES[6] in stderr
    assert_no_verbose_stage_messages(stdout)
    assert "object at 0x" not in stderr


def test_cli_diagnostics_failure_summary_includes_run_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics_run = {
        "passed": False,
        "node_count": 123,
        "edge_count": 456,
        "check_count": 3,
        "failed_check_count": 1,
        "checks": [
            {
                "name": "edge_count_nonzero",
                "passed": False,
                "summary": "No graph edges passed diagnostics.",
                "issues": [
                    {
                        "kind": "empty_edges",
                        "message": "No edges found.",
                    }
                ],
            }
        ],
        "issues": [],
    }
    install_fake_stage15(
        monkeypatch,
        diagnostics_result=FakeDiagnosticsWorkflowResult(
            passed=False,
            diagnostics_run=diagnostics_run,
        ),
    )

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    diagnostics = payload["diagnostics"]

    assert payload["stage"] == "diagnostics"
    assert payload["passed"] is False
    assert stderr == ""
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    assert isinstance(diagnostics, dict)
    assert diagnostics["diagnostics_run"] == diagnostics_run
    assert diagnostics_run["node_count"] == 123
    assert diagnostics_run["edge_count"] == 456
    assert diagnostics_run["failed_check_count"] == 1
    assert "object at 0x" not in stdout


def test_verbose_diagnostics_failure_keeps_diagnostics_details_in_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics_run = {
        "passed": False,
        "node_count": 123,
        "edge_count": 456,
        "check_count": 3,
        "failed_check_count": 1,
        "checks": [
            {
                "name": "edge_count_nonzero",
                "passed": False,
                "summary": "No graph edges passed diagnostics.",
                "issues": [],
            }
        ],
        "issues": [],
    }
    install_fake_stage15(
        monkeypatch,
        diagnostics_result=FakeDiagnosticsWorkflowResult(
            passed=False,
            diagnostics_run=diagnostics_run,
        ),
    )

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--verbose",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    diagnostics = payload["diagnostics"]

    assert "[5/7] Failed:" in stderr
    assert isinstance(diagnostics, dict)
    assert diagnostics["diagnostics_run"] == diagnostics_run
    assert_no_verbose_stage_messages(stdout)


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
