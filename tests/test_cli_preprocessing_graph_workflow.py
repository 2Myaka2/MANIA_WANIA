import json
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

import mania.cli as cli
import mania.software_identity as identity_module
from mania.artifact_inventory import ArtifactInventory
from mania.artifact_inventory_io import ArtifactInventoryWriteResult
from mania.preprocessing import (
    ContactProgressCallback,
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
    PreprocessingContactProgressEvent,
    PreprocessingFrameSamplingOptions,
)
from mania.preprocessing.run_provenance import PreprocessingRunProvenanceBuildError
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowOutputLayout,
    build_preprocessing_graph_workflow_plan,
)
from mania.run_provenance import RunProvenance
from mania.run_provenance_io import RunProvenanceWriteResult, write_run_provenance
from mania.software_identity import SoftwareIdentity

FIXED_IDENTITY = SoftwareIdentity(
    "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
)
START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
END = datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)
FIXED_PROVENANCE = RunProvenance(
    "fixed", "preprocessing_graph_export", "completed", START, END,
    FIXED_IDENTITY, ("mania",), {}, (),
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
STAGE15_ORDER_WITH_ANALYSIS_INPUTS = (
    "build_preprocessing_graph_workflow_plan",
    "load_preprocessing_graph_workflow_condition_runtimes",
    "compute_preprocessing_graph_workflow_rg_contacts",
    "export_preprocessing_graph_workflow_artifacts",
    "export_preprocessing_graph_workflow_analysis_inputs",
    "run_preprocessing_graph_workflow_diagnostics",
    "compare_preprocessing_graph_workflow_reference_artifacts",
)
STAGE15_ORDER_WITH_ANALYSIS_AND_SCIENTIFIC = (
    "build_preprocessing_graph_workflow_plan",
    "load_preprocessing_graph_workflow_condition_runtimes",
    "compute_preprocessing_graph_workflow_rg_contacts",
    "export_preprocessing_graph_workflow_artifacts",
    "export_preprocessing_graph_workflow_analysis_inputs",
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
VERBOSE_STAGE_MESSAGES_WITH_ANALYSIS_INPUTS = (
    "[1/8] Building workflow plan",
    "[2/8] Loading manifest and condition runtimes",
    "[3/8] Computing Rg and contacts",
    "[4/8] Exporting graph artifacts",
    "[5/8] Exporting analysis-ready artifacts",
    "[6/8] Running graph diagnostics",
    "[7/8] Running/skipping reference comparison",
    "[8/8] Writing final summary",
)
VERBOSE_STAGE_MESSAGES_WITH_ANALYSIS_AND_SCIENTIFIC = (
    "[1/9] Building workflow plan",
    "[2/9] Loading manifest and condition runtimes",
    "[3/9] Computing Rg and contacts",
    "[4/9] Exporting graph artifacts",
    "[5/9] Exporting analysis-ready artifacts",
    "[6/9] Exporting optional scientific CSVs",
    "[7/9] Running graph diagnostics",
    "[8/9] Running/skipping reference comparison",
    "[9/9] Writing final summary",
)


@dataclass(frozen=True)
class FakeLayout(PreprocessingGraphWorkflowOutputLayout):
    def to_dict(self) -> dict[str, object]:
        return {"output_dir": str(self.output_dir)}


def fake_layout(output_dir: Path = Path("out")) -> FakeLayout:
    return FakeLayout(
        output_dir, "fake",
        output_dir / "rg/rg_timeseries.csv",
        output_dir / "contacts/contacts_perframe.csv",
        output_dir / "contacts/contact_edges.csv",
        output_dir / "graph/nodes.csv",
        output_dir / "graph/edges.csv",
        output_dir / "graph/graph.json",
        output_dir / "reports/graph_diagnostics_report.json",
        output_dir / "reports/graph_reference_comparison.json",
    )


@dataclass(frozen=True)
class FakePlan:
    passed: bool = True
    output_layout: FakeLayout = field(default_factory=fake_layout)
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
class FakeAnalysisInputExportResult:
    passed: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": "analysis_input_export",
            "requested": True,
            "skipped": False,
            "passed": self.passed,
            "residue_tables": {"passed": True, "artifacts": []},
            "protein_contacts": {"passed": self.passed, "artifacts": []},
            "manifests": {"passed": self.passed, "paths": []},
            "issues": (
                []
                if self.passed
                else [
                    {
                        "kind": "forced_analysis_input_export_failure",
                        "message": "Forced analysis input export failure.",
                        "stage": "protein_contacts",
                    }
                ]
            ),
            "issue_count": 0 if self.passed else 1,
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
    analysis_input_result: object | None = None,
    software_identity: SoftwareIdentity = FIXED_IDENTITY,
    timestamps: tuple[datetime, datetime] = (START, END),
    completed_provenance: RunProvenance = FIXED_PROVENANCE,
    provenance_write_result: RunProvenanceWriteResult | None = None,
) -> tuple[list[str], dict[str, Any]]:
    calls: list[str] = []
    received: dict[str, Any] = {}

    def fake_build(options: Any) -> FakePlan:
        calls.append("build_preprocessing_graph_workflow_plan")
        received["options"] = options
        return FakePlan(
            passed=failing_stage != "plan", options=options,
            output_layout=fake_layout(options.output_dir),
        )

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

    def fake_analysis_input_export(
        graph_export: object,
        output_dir: str | Path | None = None,
    ) -> object:
        calls.append("export_preprocessing_graph_workflow_analysis_inputs")
        received["analysis_input_graph_export"] = graph_export
        received["analysis_input_output_dir"] = output_dir
        if analysis_input_result is not None:
            return analysis_input_result
        return FakeAnalysisInputExportResult(
            passed=failing_stage != "analysis_input_export"
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
        "export_preprocessing_graph_workflow_analysis_inputs",
        fake_analysis_input_export,
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
    received["clock"] = Mock(side_effect=timestamps)
    received["inventory_builder"] = Mock(return_value=ArtifactInventory(
        "fixed", "preprocessing_graph_export", "artifact_inventory.json", "none", ()
    ))
    received["inventory_writer"] = Mock(side_effect=lambda inventory, root, **kw: (
        ArtifactInventoryWriteResult(Path(root) / "artifact_inventory.json", True)
    ))
    received["identity"] = Mock(return_value=software_identity)
    received["provenance_builder"] = Mock(return_value=completed_provenance)
    received["failed_provenance_builder"] = Mock(
        return_value=replace(completed_provenance, status="failed")
    )
    received["provenance_writer"] = Mock(
        side_effect=lambda provenance, output_dir, **kwargs: (
            provenance_write_result
            if provenance_write_result is not None
            else RunProvenanceWriteResult(
                Path(output_dir) / "run_provenance.json", True
            )
        )
    )
    for name, key in (
        ("build_preprocessing_artifact_inventory", "inventory_builder"),
        ("write_artifact_inventory", "inventory_writer"),
        ("_utc_now", "clock"),
        ("get_software_identity", "identity"),
        ("build_completed_preprocessing_run_provenance", "provenance_builder"),
        ("build_failed_preprocessing_run_provenance", "failed_provenance_builder"),
        ("write_run_provenance", "provenance_writer"),
    ):
        monkeypatch.setattr(cli, name, received[key])
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
    assert "--export-analysis-inputs" in result.stdout
    assert "--contact-selection protein" in result.stdout
    assert "--skip-contacts" in result.stdout
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


def test_graph_export_accepts_analysis_input_export_flag() -> None:
    args = cli.build_parser().parse_args(
        [
            *BASE_COMMAND,
            "--contact-selection",
            "protein",
            "--export-analysis-inputs",
        ]
    )

    assert args.export_analysis_inputs is True
    assert args.contact_selection == "protein"


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
    analysis_input_payload = payload["analysis_input_export"]
    options = received["options"]

    assert payload["passed"] is True
    assert isinstance(scientific_payload, dict)
    assert scientific_payload["passed"] is True
    assert scientific_payload["skipped"] is True
    assert isinstance(analysis_input_payload, dict)
    assert analysis_input_payload == {
        "passed": True,
        "requested": False,
        "skipped": True,
        "stage": "analysis_input_export",
    }
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


@pytest.mark.parametrize(
    ("extra_args", "expected_message"),
    (
        (
            ("--export-analysis-inputs", "--contact-selection", "all"),
            "--export-analysis-inputs requires --contact-selection protein",
        ),
        (
            (
                "--export-analysis-inputs",
                "--contact-selection",
                "protein",
                "--skip-contacts",
            ),
            "--export-analysis-inputs cannot be used with --skip-contacts",
        ),
    ),
)
def test_analysis_input_export_invalid_combinations_fail_before_workflow(
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
    assert expected_message in stderr
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
    assert "export_preprocessing_graph_workflow_analysis_inputs" not in calls
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


def test_analysis_input_export_runs_after_graph_export_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
    )
    payload = stdout_json(stdout)
    analysis_payload = payload["analysis_input_export"]

    assert calls == list(STAGE15_ORDER_WITH_ANALYSIS_INPUTS)
    assert received["analysis_input_output_dir"] == Path("out")
    assert isinstance(analysis_payload, dict)
    assert analysis_payload["requested"] is True
    assert analysis_payload["skipped"] is False
    assert analysis_payload["passed"] is True


def test_analysis_input_export_coexists_with_legacy_scientific_csvs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, received = install_fake_stage15(monkeypatch)

    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-contacts-perframe",
    )
    payload = stdout_json(stdout)

    assert calls == list(STAGE15_ORDER_WITH_ANALYSIS_AND_SCIENTIFIC)
    assert received["scientific_export_flags"] == {
        "export_rg_timeseries": False,
        "export_contact_edges": False,
        "export_contacts_perframe": True,
    }
    assert payload["analysis_input_export"]["passed"] is True
    assert payload["scientific_csv_export"]["paths"]["contacts_perframe_csv"] == (
        "out/contacts/contacts_perframe.csv"
    )


def test_requested_analysis_input_export_failure_makes_cli_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = install_fake_stage15(
        monkeypatch,
        failing_stage="analysis_input_export",
    )

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        expected_exit_code=1,
    )
    payload = stdout_json(stdout)
    analysis_payload = payload["analysis_input_export"]

    assert calls == list(STAGE15_ORDER_WITH_ANALYSIS_INPUTS[:5])
    assert payload["stage"] == "analysis_input_export"
    assert payload["passed"] is False
    assert isinstance(analysis_payload, dict)
    assert analysis_payload["passed"] is False
    assert "forced_analysis_input_export_failure" in json.dumps(
        analysis_payload
    )
    assert "Analysis input export failed during protein_contacts" in stderr


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


def test_verbose_analysis_input_export_progress_stays_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--verbose",
    )
    payload = stdout_json(stdout)

    assert payload["passed"] is True
    assert stdout.strip() == json.dumps(payload, sort_keys=True)
    for message in VERBOSE_STAGE_MESSAGES_WITH_ANALYSIS_INPUTS:
        assert message in stderr
        assert message not in stdout
    assert "{" not in stderr


def test_verbose_analysis_and_scientific_progress_totals_are_correct(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_stage15(monkeypatch)

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--verbose",
    )
    payload = stdout_json(stdout)

    assert payload["passed"] is True
    for message in VERBOSE_STAGE_MESSAGES_WITH_ANALYSIS_AND_SCIENTIFIC:
        assert message in stderr
        assert message not in stdout
    assert "[1/8]" not in stderr
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
    install_fake_stage15(monkeypatch)
    monkeypatch.setattr(
        cli, "build_preprocessing_graph_workflow_plan",
        build_preprocessing_graph_workflow_plan,
    )

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


def test_completed_provenance_integration_preserves_output(monkeypatch, capsys):
    calls, received = install_fake_stage15(monkeypatch)
    observations = []

    def clock():
        observations.append(tuple(calls))
        return START if len(observations) == 1 else END

    received["clock"].side_effect = clock
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *BASE_COMMAND, "--run-name", "experiment", "--verbose"
    )
    assert observations == [(), STAGE15_ORDER]
    received["identity"].assert_called_once_with()
    assert received["clock"].call_count == 2
    builder = received["provenance_builder"]
    builder.assert_called_once()
    assert builder.call_args.args == (received["computation"],)
    supplied = builder.call_args.kwargs
    assert supplied["run_id"] == received["options"].run_name == "experiment"
    assert supplied["started_at_utc"] == START <= supplied["ended_at_utc"] == END
    assert supplied["software_identity"] is FIXED_IDENTITY
    received["provenance_writer"].assert_called_once_with(
        FIXED_PROVENANCE, received["output_layout"].output_dir, overwrite=False
    )
    assert supplied["command"] == (
        "mania",
        *BASE_COMMAND[:5],
        ".",
        "--run-name",
        "experiment",
        "--verbose",
    )
    expected = cli._build_preprocessing_graph_export_summary(
        "preprocessing_graph_export",
        passed=True,
        plan=FakePlan(options=received["options"]),
        runtime_loading=received["runtime_loading"],
        computation=received["computation"],
        graph_export=received["diagnostics_graph_export"],
        analysis_input_export=cli._skipped_analysis_input_export_summary(),
        scientific_csv_export=cli._skipped_scientific_csv_export_summary(),
        diagnostics=FakeResult("diagnostics"),
        reference_comparison=FakeResult("reference_comparison", skipped=True),
    )
    assert stdout == json.dumps(expected, sort_keys=True) + "\n"
    assert set(stdout_json(stdout)) == {
        "stage",
        "passed",
        "plan",
        "runtime_loading",
        "computation",
        "graph_export",
        "analysis_input_export",
        "scientific_csv_export",
        "diagnostics",
        "reference_comparison",
    }
    assert tuple(
        line for line in stderr.splitlines() if not line.startswith("[contacts]")
    ) == (tuple(message + "..." for message in VERBOSE_STAGE_MESSAGES))


@pytest.mark.parametrize("equals", [False, True])
def test_portable_command_and_resolved_configuration_preserve_execution_paths(
    monkeypatch, capsys, tmp_path, equals
):
    _, received = install_fake_stage15(monkeypatch)
    paths = {
        "--manifest": tmp_path / "inputs/manifest.yaml",
        "--output": tmp_path / "selected-output",
        "--reference-nodes": tmp_path / "reference/nodes.csv",
        "--reference-edges": tmp_path / "reference/edges.csv",
        "--reference-graph-json": tmp_path / "reference/graph.json",
    }
    tokens = ["preprocessing", "run-graph-export"]
    portable = ["mania", *tokens]
    for option, path in paths.items():
        name = "." if option == "--output" else path.name
        tokens.extend([f"{option}={path}"] if equals else [option, str(path)])
        portable.extend([f"{option}={name}"] if equals else [option, name])
    extra = [
        "--contact-selection",
        "protein",
        "--frame-start",
        "2",
        "--frame-stop",
        "20",
        "--frame-stride",
        "3",
        "--max-frames",
        "4",
        "--contact-max-residue-pairs-per-frame",
        "20",
        "--contact-max-distance-evaluations-per-frame",
        "100",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--enable-reference-comparison",
        "--expected-condition",
        "alpha",
        "--expected-condition",
        "beta",
    ]
    argv = [str(tmp_path / "bin/mania"), *tokens, *extra]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    capsys.readouterr()
    supplied = received["provenance_builder"].call_args.kwargs
    assert supplied["command"] == tuple([*portable, *extra])
    assert isinstance(supplied["command"], tuple)
    assert sys.argv is argv and sys.argv[0] == str(tmp_path / "bin/mania")
    options = received["options"]
    assert options.manifest_path == paths["--manifest"] == received["manifest_path"]
    assert options.output_dir == paths["--output"]
    assert options.reference_nodes_csv_path == paths["--reference-nodes"]
    assert options.reference_edges_csv_path == paths["--reference-edges"]
    assert options.reference_graph_json_path == paths["--reference-graph-json"]
    received["provenance_writer"].assert_called_once_with(
        FIXED_PROVENANCE, paths["--output"], overwrite=False
    )
    config = supplied["resolved_configuration"]
    assert config["manifest_name"] == "manifest.yaml" and config["output_root"] == "."
    assert config["reference_input_names"] == {
        "nodes": "nodes.csv",
        "edges": "edges.csv",
        "graph_json": "graph.json",
    }
    assert config["expected_condition_names"] == ["alpha", "beta"]
    assert config["frame_sampling"] == {
        "frame_start": 2,
        "frame_stop": 20,
        "frame_stride": 3,
        "max_frames": 4,
    }
    assert config["contact_detection_options"]["contact_selection"] == "protein"
    assert config["contact_computation_limits"] == {
        "max_residue_pairs_per_frame": 20,
        "max_atom_distance_evaluations_per_frame": 100,
    }
    assert config["export_analysis_inputs"] is True
    assert config["scientific_csv_exports"] == {
        "export_rg_timeseries": True,
        "export_contact_edges": True,
        "export_contacts_perframe": False,
    }
    serialized = json.dumps(config, allow_nan=False)
    assert str(tmp_path) not in serialized and str(Path.cwd()) not in serialized
    assert "/" not in serialized


def test_default_resolved_configuration(monkeypatch, capsys):
    _, received = install_fake_stage15(monkeypatch)
    invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    config = received["provenance_builder"].call_args.kwargs["resolved_configuration"]
    options = received["options"]
    assert config == {
        "manifest_name": "manifest.yaml",
        "output_root": ".",
        "run_name": options.run_name,
        "expected_condition_names": ["normal", "tumor"],
        "include_rg": True,
        "include_contacts": True,
        "include_graph_export": True,
        "include_diagnostics": True,
        "enable_reference_comparison": False,
        "reference_semantics": "MANIA_analysis_v1_2",
        "reference_input_names": {"nodes": None, "edges": None, "graph_json": None},
        "frame_sampling": PreprocessingFrameSamplingOptions().to_dict(),
        "contact_detection_options": PreprocessingContactDetectionOptions().to_dict(
            include_contact_selection=True
        ),
        "contact_computation_limits": PreprocessingContactComputationLimits().to_dict(),
        "export_analysis_inputs": False,
        "scientific_csv_exports": {
            "export_rg_timeseries": False,
            "export_contact_edges": False,
            "export_contacts_perframe": False,
        },
        "write_diagnostics_report": True,
        "write_reference_comparison_report": True,
    }
    json.dumps(config, allow_nan=False)


@pytest.mark.parametrize(
    "extra,roles",
    [
        ((), ("graph_diagnostics_report",)),
        (("--skip-diagnostics",), ()),
        (("--no-write-diagnostics-report",), ()),
        (
            ("--export-analysis-inputs", "--contact-selection", "protein"),
            ("preprocessing_manifest", "graph_diagnostics_report"),
        ),
        (
            ("--export-scientific-csvs",),
            ("rg_timeseries", "contact_edges", "graph_diagnostics_report"),
        ),
        (
            ("--export-contacts-perframe",),
            ("contacts_perframe", "graph_diagnostics_report"),
        ),
        (("--export-rg-timeseries",), ("rg_timeseries", "graph_diagnostics_report")),
        (("--export-contact-edges",), ("contact_edges", "graph_diagnostics_report")),
        (
            ("--enable-reference-comparison",),
            ("graph_diagnostics_report", "reference_comparison_report"),
        ),
        (
            ("--enable-reference-comparison", "--no-write-reference-comparison"),
            ("graph_diagnostics_report",),
        ),
        (
            ("--skip-diagnostics", "--enable-reference-comparison"),
            ("reference_comparison_report",),
        ),
        (
            (
                "--export-analysis-inputs",
                "--contact-selection",
                "protein",
                "--export-scientific-csvs",
                "--export-contacts-perframe",
                "--enable-reference-comparison",
            ),
            (
                "preprocessing_manifest",
                "rg_timeseries",
                "contact_edges",
                "contacts_perframe",
                "graph_diagnostics_report",
                "reference_comparison_report",
            ),
        ),
    ],
)
def test_completed_artifact_references_follow_successful_exports(
    monkeypatch, capsys, extra, roles
):
    _, received = install_fake_stage15(monkeypatch)
    invoke_cli(monkeypatch, capsys, *BASE_COMMAND, *extra)
    references = received["provenance_builder"].call_args.kwargs["artifact_references"]
    assert tuple(item.role for item in references) == (
        "graph_nodes",
        "graph_edges",
        "graph_json",
        *roles,
        "artifact_inventory",
    )
    expected = {
        "graph_nodes": "graph/nodes.csv",
        "graph_edges": "graph/edges.csv",
        "graph_json": "graph/graph.json",
        "preprocessing_manifest": "mania_manifest.json",
        "rg_timeseries": "rg/rg_timeseries.csv",
        "contact_edges": "contacts/contact_edges.csv",
        "contacts_perframe": "contacts/contacts_perframe.csv",
        "graph_diagnostics_report": "reports/graph_diagnostics_report.json",
        "reference_comparison_report": "reports/graph_reference_comparison.json",
        "artifact_inventory": "artifact_inventory.json",
    }
    assert [item.to_dict() for item in references] == [
        {"role": item.role, "path": expected[item.role]} for item in references
    ]


def test_artifact_references_are_lexical_without_filesystem_observation(monkeypatch):
    args = cli.build_parser().parse_args(BASE_COMMAND)
    options = cli._build_preprocessing_graph_workflow_options(args)
    layout = build_preprocessing_graph_workflow_plan(options).output_layout

    def forbidden(*args, **kwargs):
        raise AssertionError("File observation is forbidden")

    with monkeypatch.context() as patch:
        for name in ("exists", "stat", "resolve", "read_bytes", "open", "iterdir"):
            patch.setattr(Path, name, forbidden)
        references = cli._completed_preprocessing_artifact_references(
            args, options, layout
        )
        for outside in (
            Path("elsewhere/nodes.csv"),
            Path("out/../nodes.csv"),
            Path("/nodes"),
        ):
            with pytest.raises(PreprocessingRunProvenanceBuildError, match="inside"):
                cli._completed_preprocessing_artifact_references(
                    args, options, replace(layout, graph_nodes_csv_path=outside)
                )
    assert references[0].path == "graph/nodes.csv"


@pytest.mark.parametrize("name", ["", "/", ".", ".."])
def test_command_rejects_empty_or_nonportable_input_names(name):
    with pytest.raises(PreprocessingRunProvenanceBuildError, match="portable filename"):
        cli._portable_preprocessing_command(("local-mania", "--manifest", name))


def test_command_does_not_guess_paths_in_other_arguments():
    original = (
        "local-mania",
        "--reference-semantics",
        "arbitrary/text",
        "--run-name=a/b",
    )
    assert cli._portable_preprocessing_command(original) == ("mania", *original[1:])


@pytest.mark.parametrize("overwrite", [False, True])
def test_writer_receives_resolved_overwrite(monkeypatch, capsys, overwrite):
    _, received = install_fake_stage15(monkeypatch)
    build_options = cli._build_preprocessing_graph_workflow_options
    monkeypatch.setattr(
        cli,
        "_build_preprocessing_graph_workflow_options",
        lambda args: replace(build_options(args), overwrite=overwrite),
    )
    invoke_cli(monkeypatch, capsys, *BASE_COMMAND)
    assert received["provenance_writer"].call_args.kwargs == {"overwrite": overwrite}


@pytest.mark.parametrize("failure", ["build", "write"])
def test_provenance_failure_keeps_scientific_files_and_omits_summary(
    monkeypatch, capsys, tmp_path, failure
):
    _, received = install_fake_stage15(monkeypatch)
    scientific = tmp_path / "graph/nodes.csv"
    scientific.parent.mkdir()
    scientific.write_text("retained scientific result\n")
    target = tmp_path / "run_provenance.json"
    if failure == "build":
        received[
            "provenance_builder"
        ].side_effect = PreprocessingRunProvenanceBuildError(
            "Sampling collection contains errors."
        )
        message = "Run provenance build failed: Sampling collection contains errors.\n"
    else:
        target.write_bytes(b"existing provenance")
        monkeypatch.setattr(cli, "write_run_provenance", write_run_provenance)
        message = "Run provenance write failed: Target already exists.\n"
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--output",
        str(tmp_path),
        expected_exit_code=1,
    )
    assert stdout == "" and stderr == message
    assert scientific.read_text() == "retained scientific result\n"
    if failure == "build":
        received["provenance_writer"].assert_not_called()
        assert not target.exists()
    else:
        assert target.read_bytes() == b"existing provenance"
    assert sorted(
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")
    ) == (
        ["graph", "graph/nodes.csv"]
        + (["run_provenance.json"] if failure == "write" else [])
    )


@pytest.mark.parametrize(
    "stage",
    [
        "plan",
        "runtime_loading",
        "computation",
        "graph_export",
        "analysis_input_export",
        "scientific_csv_export",
        "diagnostics",
        "reference_comparison",
    ],
)
def test_earlier_failures_do_not_build_or_write_completed_provenance(
    monkeypatch, capsys, stage
):
    _, received = install_fake_stage15(monkeypatch, failing_stage=stage)
    _, stdout, _ = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--contact-selection",
        "protein",
        "--export-analysis-inputs",
        "--export-scientific-csvs",
        "--enable-reference-comparison",
        expected_exit_code=1,
    )
    assert stdout_json(stdout)["stage"] == stage
    received["provenance_builder"].assert_not_called()
    received["failed_provenance_builder"].assert_called_once()
    received["provenance_writer"].assert_called_once()
    assert received["clock"].call_count == 2


def test_invalid_options_do_not_capture_start_or_emit_provenance(monkeypatch, capsys):
    _, received = install_fake_stage15(monkeypatch)
    invoke_cli(
        monkeypatch, capsys, *BASE_COMMAND, "--frame-stride", "0", expected_exit_code=2
    )
    for key in ("clock", "identity", "provenance_builder", "provenance_writer"):
        received[key].assert_not_called()


@pytest.mark.parametrize(
    "args",
    [("--help",), ("preprocessing", "run-graph-export", "--help"), ("--version",)],
)
def test_parser_help_and_version_do_not_capture_time_or_git(monkeypatch, capsys, args):
    def forbidden(*args, **kwargs):
        raise AssertionError("Parser/help/version must not observe time or Git")

    monkeypatch.setattr(cli, "_utc_now", forbidden)
    monkeypatch.setattr(cli, "get_software_identity", forbidden)
    monkeypatch.setattr(identity_module, "_run_git", forbidden)
    cli.build_parser()
    monkeypatch.setattr(sys, "argv", ["mania", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == "" and "--provenance" not in captured.out
    if args == ("--version",):
        assert captured.out == "mania-wania 0.1.0\n"


def test_successful_mocked_workflow_reaches_real_writer(monkeypatch, capsys, tmp_path):
    _, received = install_fake_stage15(monkeypatch)
    writer = Mock(wraps=write_run_provenance)
    monkeypatch.setattr(cli, "write_run_provenance", writer)
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *BASE_COMMAND, "--output", str(tmp_path), "--verbose"
    )
    received["provenance_builder"].assert_called_once()
    writer.assert_called_once_with(FIXED_PROVENANCE, tmp_path, overwrite=False)
    target = tmp_path / "run_provenance.json"
    assert json.loads(target.read_text()) == FIXED_PROVENANCE.to_dict()
    assert list(tmp_path.iterdir()) == [target]
    assert stdout_json(stdout)["passed"] is True
    assert tuple(
        line for line in stderr.splitlines() if not line.startswith("[contacts]")
    ) == (tuple(message + "..." for message in VERBOSE_STAGE_MESSAGES))


def test_cli_import_does_not_read_clock_or_inspect_git(monkeypatch):
    import datetime as datetime_module
    import importlib

    def forbidden(*args, **kwargs):
        raise AssertionError("Import must not capture time or inspect Git")

    class NoClock(datetime):
        now = utcnow = today = forbidden

    with monkeypatch.context() as patch:
        patch.setattr(datetime_module, "datetime", NoClock)
        patch.setattr(identity_module, "get_software_identity", forbidden)
        patch.setattr(identity_module, "_run_git", forbidden)
        patch.setattr(subprocess, "run", forbidden)
        importlib.reload(cli)
    importlib.reload(cli)


def test_cli_completed_passport_with_real_builder_and_writer(
    monkeypatch, capsys, tmp_path
):
    from mania.preprocessing.run_provenance import (
        build_completed_preprocessing_run_provenance,
    )
    from mania.preprocessing.trajectory_contacts import (
        PreprocessingConditionContactsResult,
        PreprocessingContactFrameResult,
        PreprocessingManifestContactsResult,
    )
    from mania.preprocessing.trajectory_graph_workflow import (
        PreprocessingGraphWorkflowComputationResult,
        PreprocessingGraphWorkflowManifestReadinessResult,
        PreprocessingGraphWorkflowRuntimeLoadingResult,
    )

    _, received = install_fake_stage15(monkeypatch)
    conditions = ("normal", "tumor")
    readiness = PreprocessingGraphWorkflowManifestReadinessResult(
        Path("manifest.yaml"), True, True, conditions, 2
    )
    loading = PreprocessingGraphWorkflowRuntimeLoadingResult(
        readiness.manifest_path,
        readiness,
        conditions,
        conditions,
        runtime_load_result=object(),
    )
    contacts = PreprocessingManifestContactsResult(
        tuple(
            PreprocessingConditionContactsResult(
                condition_name=name,
                status="computed",
                options=PreprocessingContactDetectionOptions(),
                frame_results=(PreprocessingContactFrameResult(name, 2, 4.0),),
            )
            for name in conditions
        )
    )
    computation = PreprocessingGraphWorkflowComputationResult(
        loading,
        conditions,
        False,
        True,
        frame_sampling=PreprocessingFrameSamplingOptions(frame_start=2, frame_stride=3),
        contacts_result=contacts,
    )
    monkeypatch.setattr(
        cli,
        "compute_preprocessing_graph_workflow_rg_contacts",
        lambda *args, **kwargs: computation,
    )
    builder = Mock(wraps=build_completed_preprocessing_run_provenance)
    monkeypatch.setattr(cli, "build_completed_preprocessing_run_provenance", builder)
    monkeypatch.setattr(cli, "write_run_provenance", write_run_provenance)
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *BASE_COMMAND,
        "--output",
        str(tmp_path),
        "--run-name",
        "real-passport",
        "--skip-rg",
        "--frame-start",
        "2",
        "--frame-stride",
        "3",
    )
    assert stdout_json(stdout)["passed"] is True and stderr == ""
    received["identity"].assert_called_once_with()
    builder.assert_called_once()
    payload = json.loads((tmp_path / "run_provenance.json").read_text())
    assert payload["run_id"] == "real-passport" and payload["status"] == "completed"
    assert payload["software_identity"] == FIXED_IDENTITY.to_dict()
    assert payload["started_at_utc"] == "2026-01-02T03:04:05.000000Z"
    assert payload["ended_at_utc"] == "2026-01-02T03:04:06.000000Z"
    assert payload["conditions"] == list(conditions)
    for item in payload["sampling_by_condition"]:
        assert item["requested"]["frame_stride"] == 3
        assert item["effective"]["sampled_frame_count"] == 1
        assert item["effective"]["first_source_frame_index"] == 2
        assert item["effective"]["first_time_ps"] == 4.0
    assert payload["resolved_configuration"]["output_root"] == "."
    assert payload["artifact_references"][0] == {
        "role": "graph_nodes",
        "path": "graph/nodes.csv",
    }
    assert list(tmp_path.iterdir()) == [tmp_path / "run_provenance.json"]
