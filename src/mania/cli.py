"""Command-line interface for MANIA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NoReturn

from mania import __version__
from mania.config import load_config
from mania.pipeline import build_pipeline_plan, format_pipeline_plan
from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsPipelineResult,
    run_notebook_export_graph_diagnostics_pipeline_from_config_file,
)


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
        return

    parser.print_help()
