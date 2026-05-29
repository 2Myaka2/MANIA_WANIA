"""Command-line interface for MANIA."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NoReturn

from mania import __version__
from mania.config import load_config
from mania.pipeline import build_pipeline_plan, format_pipeline_plan


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

    return parser


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

    parser.print_help()
