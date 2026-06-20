"""Command-line interface for MANIA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, NoReturn, cast

from mania import __version__
from mania.config import load_config
from mania.pipeline import build_pipeline_plan, format_pipeline_plan
from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsPipelineResult,
    run_notebook_export_graph_diagnostics_pipeline_from_config_file,
)
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowOptions,
    build_preprocessing_graph_workflow_plan,
    compare_preprocessing_graph_workflow_reference_artifacts,
    compute_preprocessing_graph_workflow_rg_contacts,
    export_preprocessing_graph_workflow_artifacts,
    load_preprocessing_graph_workflow_condition_runtimes,
    run_preprocessing_graph_workflow_diagnostics,
)

_DEFAULT_EXPECTED_CONDITION_NAMES = ("normal", "tumor")
_DEFAULT_REFERENCE_SEMANTICS = "MANIA_analysis_v1_2"


def _exit_with_error(message: str) -> NoReturn:
    """Print a readable CLI error and exit with status 1."""
    raise SystemExit(message)


def build_parser() -> argparse.ArgumentParser:
    """Build the MANIA command-line parser."""
    parser = argparse.ArgumentParser(
        prog="mania",
        description="MANIA toolkit for MD trajectory analysis artifacts.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mania-wania {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate a MANIA YAML configuration file.",
    )
    validate_parser.add_argument(
        "config",
        type=Path,
        help="Path to a MANIA YAML configuration file.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run MANIA pipeline. Placeholder for v0.1 skeleton.",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a MANIA YAML configuration file.",
    )

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Run internal workflow integrations.",
    )
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_command")
    workflow_run_parser = workflow_subparsers.add_parser(
        "run",
        help="Run notebook export plus graph diagnostics from config.",
    )
    workflow_run_parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a workflow JSON or YAML configuration file.",
    )
    workflow_run_parser.add_argument(
        "--fail-on-diagnostics-failure",
        action="store_true",
        help="Exit non-zero when graph diagnostics complete but report passed=false.",
    )

    preprocessing_parser = subparsers.add_parser(
        "preprocessing",
        help="Run preprocessing commands.",
    )
    preprocessing_subparsers = preprocessing_parser.add_subparsers(
        dest="preprocessing_command"
    )
    graph_export_parser = preprocessing_subparsers.add_parser(
        "run-graph-export",
        help="Run the preprocessing graph export workflow.",
    )
    graph_export_parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to a preprocessing manifest.",
    )
    graph_export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for preprocessing graph export artifacts.",
    )
    graph_export_parser.add_argument(
        "--run-name",
        help="Workflow run name. Defaults to the Stage 15 workflow default.",
    )
    graph_export_parser.add_argument(
        "--expected-condition",
        action="append",
        dest="expected_conditions",
        help=(
            "Expected condition name for runtime loading. Can be repeated; "
            "defaults to normal and tumor."
        ),
    )
    graph_export_parser.add_argument(
        "--skip-rg",
        action="store_true",
        help="Skip Rg computation.",
    )
    graph_export_parser.add_argument(
        "--skip-contacts",
        action="store_true",
        help="Skip contacts computation.",
    )
    graph_export_parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="Skip graph diagnostics after graph export.",
    )
    graph_export_parser.add_argument(
        "--enable-reference-comparison",
        action="store_true",
        help="Enable explicit generated/reference graph artifact comparison.",
    )
    graph_export_parser.add_argument(
        "--reference-nodes",
        type=Path,
        help="Explicit reference nodes.csv path for reference comparison.",
    )
    graph_export_parser.add_argument(
        "--reference-edges",
        type=Path,
        help="Explicit reference edges.csv path for reference comparison.",
    )
    graph_export_parser.add_argument(
        "--reference-graph-json",
        type=Path,
        help="Explicit reference graph.json path for reference comparison.",
    )
    graph_export_parser.add_argument(
        "--reference-semantics",
        default=_DEFAULT_REFERENCE_SEMANTICS,
        help="Reference semantics label for graph comparison.",
    )
    graph_export_parser.add_argument(
        "--no-write-diagnostics-report",
        action="store_true",
        help="Do not write the diagnostics report JSON.",
    )
    graph_export_parser.add_argument(
        "--no-write-reference-comparison",
        action="store_true",
        help="Do not write the reference comparison JSON.",
    )

    return parser


def _build_workflow_summary(
    result: NotebookExportGraphDiagnosticsPipelineResult,
) -> dict[str, object]:
    """Build a compact JSON-serializable workflow CLI summary."""
    return {
        "workflow": "notebook_export_graph_diagnostics",
        "conditions": list(result.conditions),
        "passed": result.passed,
        "export_output_dir": str(result.export_result.output_dir),
        "diagnostics_output_dir": str(
            result.diagnostics_result.diagnostics_output_dir
        ),
        "diagnostics_summary_path": (
            None
            if result.diagnostics_result.summary_path is None
            else str(result.diagnostics_result.summary_path)
        ),
        "export_written_paths_count": len(result.export_result.written_paths),
        "diagnostics_written_paths_count": len(
            result.diagnostics_result.written_paths
        ),
    }


def _build_preprocessing_graph_workflow_options(
    args: argparse.Namespace,
) -> PreprocessingGraphWorkflowOptions:
    option_kwargs: dict[str, Any] = {
        "manifest_path": args.manifest,
        "output_dir": args.output,
        "include_rg": not args.skip_rg,
        "include_contacts": not args.skip_contacts,
        "include_graph_export": True,
        "include_diagnostics": not args.skip_diagnostics,
        "enable_reference_comparison": args.enable_reference_comparison,
        "reference_nodes_csv_path": args.reference_nodes,
        "reference_edges_csv_path": args.reference_edges,
        "reference_graph_json_path": args.reference_graph_json,
        "reference_semantics": args.reference_semantics,
    }
    if args.run_name is not None:
        option_kwargs["run_name"] = args.run_name
    return PreprocessingGraphWorkflowOptions(**option_kwargs)


def _expected_condition_names(args: argparse.Namespace) -> tuple[str, ...]:
    if args.expected_conditions is None:
        return _DEFAULT_EXPECTED_CONDITION_NAMES
    return tuple(args.expected_conditions)


def _json_safe_result(result: object | None) -> dict[str, object] | None:
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    to_dict = getattr(result, "to_dict", None)
    if not callable(to_dict):
        return {"passed": bool(getattr(result, "passed", False))}
    payload = to_dict()
    if not isinstance(payload, dict):
        raise ValueError("workflow result to_dict() must return a dictionary")
    return cast(dict[str, object], payload)


def _workflow_result_passed(result: object) -> bool:
    return bool(getattr(result, "passed", False))


def _build_preprocessing_graph_export_summary(
    stage: str,
    *,
    passed: bool,
    plan: object | None = None,
    runtime_loading: object | None = None,
    computation: object | None = None,
    graph_export: object | None = None,
    diagnostics: object | None = None,
    reference_comparison: object | None = None,
) -> dict[str, object]:
    return {
        "stage": stage,
        "passed": passed,
        "plan": _json_safe_result(plan),
        "runtime_loading": _json_safe_result(runtime_loading),
        "computation": _json_safe_result(computation),
        "graph_export": _json_safe_result(graph_export),
        "diagnostics": _json_safe_result(diagnostics),
        "reference_comparison": _json_safe_result(reference_comparison),
    }


def _print_preprocessing_graph_export_summary(
    payload: dict[str, object],
) -> None:
    print(json.dumps(payload, sort_keys=True))


def _run_preprocessing_graph_export_command(args: argparse.Namespace) -> int:
    options = _build_preprocessing_graph_workflow_options(args)
    plan = build_preprocessing_graph_workflow_plan(options)
    if not plan.passed:
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "plan",
                passed=False,
                plan=plan,
            )
        )
        return 1

    runtime_loading = load_preprocessing_graph_workflow_condition_runtimes(
        options.manifest_path,
        expected_condition_names=_expected_condition_names(args),
    )
    if not runtime_loading.passed:
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "runtime_loading",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
            )
        )
        return 1

    computation = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading,
        include_rg=options.include_rg,
        include_contacts=options.include_contacts,
    )
    if not computation.passed:
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "computation",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
            )
        )
        return 1

    graph_export = export_preprocessing_graph_workflow_artifacts(
        computation,
        plan.output_layout,
    )
    if not graph_export.passed:
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "graph_export",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
                graph_export=graph_export,
            )
        )
        return 1

    diagnostics: object | None
    if args.skip_diagnostics:
        diagnostics = {"passed": True, "skipped": True}
    else:
        diagnostics = run_preprocessing_graph_workflow_diagnostics(
            graph_export,
            write_report_json=not args.no_write_diagnostics_report,
        )
        if not _workflow_result_passed(diagnostics):
            _print_preprocessing_graph_export_summary(
                _build_preprocessing_graph_export_summary(
                    "diagnostics",
                    passed=False,
                    plan=plan,
                    runtime_loading=runtime_loading,
                    computation=computation,
                    graph_export=graph_export,
                    diagnostics=diagnostics,
                )
            )
            return 1

    reference_comparison = (
        compare_preprocessing_graph_workflow_reference_artifacts(
            graph_export,
            options,
            plan.output_layout,
            write_report_json=not args.no_write_reference_comparison,
        )
    )
    if not reference_comparison.passed:
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "reference_comparison",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
                graph_export=graph_export,
                diagnostics=diagnostics,
                reference_comparison=reference_comparison,
            )
        )
        return 1

    _print_preprocessing_graph_export_summary(
        _build_preprocessing_graph_export_summary(
            "preprocessing_graph_export",
            passed=True,
            plan=plan,
            runtime_loading=runtime_loading,
            computation=computation,
            graph_export=graph_export,
            diagnostics=diagnostics,
            reference_comparison=reference_comparison,
        )
    )
    return 0


def main() -> None:
    """Run the MANIA command-line interface."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        try:
            load_config(args.config)
        except Exception as exc:
            _exit_with_error(f"Config is invalid: {args.config}\n{exc}")
        print(f"Config is valid: {args.config}")
        return

    if args.command == "run":
        try:
            config = load_config(args.config)
        except Exception as exc:
            _exit_with_error(f"Config is invalid: {args.config}\n{exc}")
        plan = build_pipeline_plan(config)
        print(format_pipeline_plan(plan))
        return

    if args.command == "workflow" and args.workflow_command == "run":
        try:
            result = run_notebook_export_graph_diagnostics_pipeline_from_config_file(
                args.config
            )
        except Exception as exc:
            _exit_with_error(f"Workflow failed: {args.config}\n{exc}")
        print(json.dumps(_build_workflow_summary(result), sort_keys=True))
        if args.fail_on_diagnostics_failure and not result.passed:
            raise SystemExit(2)
        return

    if (
        args.command == "preprocessing"
        and args.preprocessing_command == "run-graph-export"
    ):
        exit_code = _run_preprocessing_graph_export_command(args)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    parser.print_help()
