"""Command-line interface for MANIA."""

from __future__ import annotations

import argparse

from mania import __version__


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

    subparsers.add_parser(
        "validate-config",
        help="Validate a MANIA YAML configuration file. Placeholder for v0.1 skeleton.",
    )

    subparsers.add_parser(
        "run",
        help="Run MANIA pipeline. Placeholder for v0.1 skeleton.",
    )

    return parser


def main() -> None:
    """Run the MANIA command-line interface."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        print("Config validation is not implemented yet. Next step: add Pydantic config models.")
        return

    if args.command == "run":
        print("Pipeline execution is not implemented yet. This is a skeleton CLI.")
        return

    parser.print_help()
