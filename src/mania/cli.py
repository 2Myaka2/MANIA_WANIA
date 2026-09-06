"""Command-line interface for MANIA."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, cast

from mania import __version__
from mania.analysis import (
    CONFORMATION_CLUSTERING_BASES,
    CONFORMATION_CLUSTERING_BASIS_FINGERPRINT,
    AnalyzeError,
    AnalyzeRequest,
    run_analysis,
)
from mania.config import load_config
from mania.pipeline import build_pipeline_plan, format_pipeline_plan
from mania.pipeline_steps import (
    NotebookExportGraphDiagnosticsPipelineResult,
    run_notebook_export_graph_diagnostics_pipeline_from_config_file,
)
from mania.preprocessing.run_provenance import (
    PreprocessingRunProvenanceBuildError,
    build_completed_preprocessing_run_provenance,
)
from mania.preprocessing.trajectory_contacts import (
    ContactProgressCallback,
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
    PreprocessingContactProgressEvent,
)
from mania.preprocessing.trajectory_frame_sampling import (
    PreprocessingFrameSamplingOptions,
)
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowOptions,
    PreprocessingGraphWorkflowOutputLayout,
    build_preprocessing_graph_workflow_plan,
    compare_preprocessing_graph_workflow_reference_artifacts,
    compute_preprocessing_graph_workflow_rg_contacts,
    export_preprocessing_graph_workflow_analysis_inputs,
    export_preprocessing_graph_workflow_artifacts,
    export_preprocessing_graph_workflow_scientific_csvs,
    load_preprocessing_graph_workflow_condition_runtimes,
    run_preprocessing_graph_workflow_diagnostics,
)
from mania.run_provenance import PortableArtifactReference
from mania.run_provenance_io import write_run_provenance
from mania.software_identity import get_software_identity
from mania.wania import (
    WaniaGraphPayloadArtifactPaths,
    WaniaGraphPayloadRunMetadata,
    build_wania_graph_payload_from_artifacts,
    write_wania_graph_payload_json,
)

_DEFAULT_EXPECTED_CONDITION_NAMES = ("normal", "tumor")
_DEFAULT_REFERENCE_SEMANTICS = "MANIA_analysis_v1_2"
_CONTACT_SELECTION_CHOICES = ("all", "protein")
_PREPROCESSING_STAGE_BUILD_PLAN = "Building workflow plan"
_PREPROCESSING_STAGE_LOAD_RUNTIMES = "Loading manifest and condition runtimes"
_PREPROCESSING_STAGE_COMPUTE = "Computing Rg and contacts"
_PREPROCESSING_STAGE_GRAPH_EXPORT = "Exporting graph artifacts"
_PREPROCESSING_STAGE_ANALYSIS_INPUTS = "Exporting analysis-ready artifacts"
_PREPROCESSING_STAGE_SCIENTIFIC_CSVS = "Exporting optional scientific CSVs"
_PREPROCESSING_STAGE_DIAGNOSTICS = "Running graph diagnostics"
_PREPROCESSING_STAGE_REFERENCE_COMPARISON = (
    "Running/skipping reference comparison"
)
_PREPROCESSING_STAGE_SUMMARY = "Writing final summary"


def _positive_contact_limit_value(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be a positive integer"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_pca_component_value(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be a positive integer"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


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

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run accepted MANIA analysis over existing preprocessing artifacts.",
    )
    analyze_parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Preprocessing output root containing accepted Stage 20 artifacts.",
    )
    analyze_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Run output root; analysis artifacts are written under analysis/.",
    )
    analyze_parser.add_argument(
        "--condition",
        action="append",
        dest="conditions",
        required=True,
        help="Condition to analyze. Repeat for each condition.",
    )
    analyze_parser.add_argument(
        "--enable-pca",
        action="store_true",
        help="Compute the accepted optional PCA projection.",
    )
    analyze_parser.add_argument(
        "--clustering-basis",
        choices=CONFORMATION_CLUSTERING_BASES,
        default=CONFORMATION_CLUSTERING_BASIS_FINGERPRINT,
        help=(
            "Conformation clustering basis. Defaults to fingerprint; pca "
            "requires --enable-pca."
        ),
    )
    analyze_parser.add_argument(
        "--pca-components-for-clustering",
        type=_positive_pca_component_value,
        default=None,
        help=(
            "Positive PCA component count for pca clustering. Requires "
            "--clustering-basis pca."
        ),
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
    graph_export_parser.add_argument(
        "--export-rg-timeseries",
        action="store_true",
        help="Export optional rg/rg_timeseries.csv after graph export.",
    )
    graph_export_parser.add_argument(
        "--export-contact-edges",
        action="store_true",
        help="Export optional contacts/contact_edges.csv after graph export.",
    )
    graph_export_parser.add_argument(
        "--export-contacts-perframe",
        action="store_true",
        help=(
            "Export optional contacts/contacts_perframe.csv after graph "
            "export. This can be large and is never included in the shortcut."
        ),
    )
    graph_export_parser.add_argument(
        "--export-scientific-csvs",
        action="store_true",
        help=(
            "Export the safe optional scientific CSV subset: "
            "rg/rg_timeseries.csv and contacts/contact_edges.csv."
        ),
    )
    graph_export_parser.add_argument(
        "--export-analysis-inputs",
        action="store_true",
        help=(
            "Explicitly write root-level preprocessing artifacts required by "
            "mania analyze. Disabled by default; requires "
            "--contact-selection protein and is incompatible with "
            "--skip-contacts."
        ),
    )
    graph_export_parser.add_argument(
        "--frame-start",
        type=int,
        default=0,
        help="First source trajectory frame index to include. Defaults to 0.",
    )
    graph_export_parser.add_argument(
        "--frame-stop",
        type=int,
        default=None,
        help="Exclusive source trajectory frame stop index.",
    )
    graph_export_parser.add_argument(
        "--frame-stride",
        type=int,
        default=1,
        help="Source trajectory frame sampling stride. Defaults to 1.",
    )
    graph_export_parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum sampled frame count after filtering.",
    )
    graph_export_parser.add_argument(
        "--contact-max-residue-pairs-per-frame",
        type=_positive_contact_limit_value,
        default=None,
        help=(
            "Optional smoke/debug guard for maximum candidate residue pairs "
            "inside one contacts frame."
        ),
    )
    graph_export_parser.add_argument(
        "--contact-max-distance-evaluations-per-frame",
        type=_positive_contact_limit_value,
        default=None,
        help=(
            "Optional smoke/debug guard for maximum atom distance "
            "evaluations inside one contacts frame."
        ),
    )
    graph_export_parser.add_argument(
        "--contact-selection",
        choices=_CONTACT_SELECTION_CHOICES,
        default="all",
        help=(
            "Contact residue selection scope. Use 'all' for the full "
            "system or 'protein' for runtime protein residues."
        ),
    )
    graph_export_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print stage-by-stage progress messages to stderr.",
    )

    wania_parser = subparsers.add_parser(
        "wania",
        help="Build WANIA payload artifacts.",
    )
    wania_subparsers = wania_parser.add_subparsers(dest="wania_command")
    payload_parser = wania_subparsers.add_parser(
        "build-payload",
        help="Build wania_graph_payload.json from an accepted graph artifact.",
    )
    payload_parser.add_argument(
        "--graph-json",
        type=Path,
        required=True,
        help="Path to the accepted graph/graph.json artifact.",
    )
    payload_output_group = payload_parser.add_mutually_exclusive_group(
        required=True
    )
    payload_output_group.add_argument(
        "--output",
        type=Path,
        help="Exact output JSON path.",
    )
    payload_output_group.add_argument(
        "--output-dir",
        type=Path,
        help="Directory in which to write wania_graph_payload.json.",
    )
    payload_parser.add_argument(
        "--run-name",
        required=True,
        help="Explicit WANIA run name.",
    )
    payload_parser.add_argument(
        "--protein-id",
        required=True,
        help="Explicit protein identifier.",
    )
    payload_parser.add_argument(
        "--protein-name",
        required=True,
        help="Explicit protein display name.",
    )
    payload_parser.add_argument(
        "--condition-name",
        action="append",
        dest="condition_names",
        required=True,
        help="Graph condition name. Repeat for each condition.",
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
        "frame_sampling": PreprocessingFrameSamplingOptions(
            frame_start=args.frame_start,
            frame_stop=args.frame_stop,
            frame_stride=args.frame_stride,
            max_frames=args.max_frames,
        ),
        "contact_detection_options": PreprocessingContactDetectionOptions(
            contact_selection=args.contact_selection,
        ),
        "contact_computation_limits": PreprocessingContactComputationLimits(
            max_residue_pairs_per_frame=(
                args.contact_max_residue_pairs_per_frame
            ),
            max_atom_distance_evaluations_per_frame=(
                args.contact_max_distance_evaluations_per_frame
            ),
        ),
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
    analysis_input_export: object | None = None,
    scientific_csv_export: object | None = None,
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
        "analysis_input_export": _json_safe_result(analysis_input_export),
        "scientific_csv_export": _json_safe_result(scientific_csv_export),
        "diagnostics": _json_safe_result(diagnostics),
        "reference_comparison": _json_safe_result(reference_comparison),
    }


def _print_preprocessing_graph_export_summary(
    payload: dict[str, object],
) -> None:
    print(json.dumps(payload, sort_keys=True))


def _verbose_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "verbose", False))


def _scientific_csv_export_requested(args: argparse.Namespace) -> bool:
    return any(
        (
            bool(getattr(args, "export_scientific_csvs", False)),
            bool(getattr(args, "export_rg_timeseries", False)),
            bool(getattr(args, "export_contact_edges", False)),
            bool(getattr(args, "export_contacts_perframe", False)),
        )
    )


def _analysis_input_export_requested(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "export_analysis_inputs", False))


def _scientific_export_flags(args: argparse.Namespace) -> dict[str, bool]:
    shortcut = bool(getattr(args, "export_scientific_csvs", False))
    return {
        "export_rg_timeseries": (
            shortcut or bool(getattr(args, "export_rg_timeseries", False))
        ),
        "export_contact_edges": (
            shortcut or bool(getattr(args, "export_contact_edges", False))
        ),
        "export_contacts_perframe": bool(
            getattr(args, "export_contacts_perframe", False)
        ),
    }


def _preprocessing_graph_export_verbose_stages(
    args: argparse.Namespace,
) -> dict[int, str]:
    stages = [
        _PREPROCESSING_STAGE_BUILD_PLAN,
        _PREPROCESSING_STAGE_LOAD_RUNTIMES,
        _PREPROCESSING_STAGE_COMPUTE,
        _PREPROCESSING_STAGE_GRAPH_EXPORT,
    ]
    if _analysis_input_export_requested(args):
        stages.append(_PREPROCESSING_STAGE_ANALYSIS_INPUTS)
    if _scientific_csv_export_requested(args):
        stages.append(_PREPROCESSING_STAGE_SCIENTIFIC_CSVS)
    stages.extend(
        (
            _PREPROCESSING_STAGE_DIAGNOSTICS,
            _PREPROCESSING_STAGE_REFERENCE_COMPARISON,
            _PREPROCESSING_STAGE_SUMMARY,
        )
    )
    return dict(enumerate(stages, start=1))


def _preprocessing_graph_export_stage_count(args: argparse.Namespace) -> int:
    return len(_preprocessing_graph_export_verbose_stages(args))


def _diagnostics_stage_number(args: argparse.Namespace) -> int:
    return _preprocessing_graph_export_stage_number(
        args,
        _PREPROCESSING_STAGE_DIAGNOSTICS,
    )


def _reference_comparison_stage_number(args: argparse.Namespace) -> int:
    return _preprocessing_graph_export_stage_number(
        args,
        _PREPROCESSING_STAGE_REFERENCE_COMPARISON,
    )


def _summary_stage_number(args: argparse.Namespace) -> int:
    return _preprocessing_graph_export_stage_count(args)


def _analysis_input_export_stage_number(args: argparse.Namespace) -> int:
    return _preprocessing_graph_export_stage_number(
        args,
        _PREPROCESSING_STAGE_ANALYSIS_INPUTS,
    )


def _scientific_csv_export_stage_number(args: argparse.Namespace) -> int:
    return _preprocessing_graph_export_stage_number(
        args,
        _PREPROCESSING_STAGE_SCIENTIFIC_CSVS,
    )


def _preprocessing_graph_export_stage_number(
    args: argparse.Namespace,
    message: str,
) -> int:
    stages = _preprocessing_graph_export_verbose_stages(args)
    for stage_number, stage_message in stages.items():
        if stage_message == message:
            return stage_number
    raise ValueError(f"progress stage is not active: {message}")


def _print_preprocessing_graph_export_progress(
    args: argparse.Namespace,
    stage_number: int,
) -> None:
    if not _verbose_enabled(args):
        return
    stages = _preprocessing_graph_export_verbose_stages(args)
    message = stages[stage_number]
    stage_count = _preprocessing_graph_export_stage_count(args)
    print(f"[{stage_number}/{stage_count}] {message}...", file=sys.stderr)


def _print_preprocessing_graph_export_failure(
    args: argparse.Namespace,
    stage_number: int,
) -> None:
    if not _verbose_enabled(args):
        return
    stages = _preprocessing_graph_export_verbose_stages(args)
    message = stages[stage_number]
    stage_count = _preprocessing_graph_export_stage_count(args)
    print(
        f"[{stage_number}/{stage_count}] Failed: {message}.",
        file=sys.stderr,
    )


def _contact_limit_flags_enabled(args: argparse.Namespace) -> bool:
    return (
        args.contact_max_residue_pairs_per_frame is not None
        or args.contact_max_distance_evaluations_per_frame is not None
    )


def _format_contacts_progress_event(
    event: PreprocessingContactProgressEvent,
) -> str:
    prefix = f"[contacts] condition={event.condition_name}"
    if event.frame_index is not None:
        prefix = f"{prefix} frame={event.frame_index}"
    message = event.message
    if event.stage == "frame_start":
        message = f"{message}..."
    return f"{prefix}: {message}"


def _contacts_progress_callback(
    args: argparse.Namespace,
) -> ContactProgressCallback | None:
    if not _verbose_enabled(args):
        return None

    def callback(event: PreprocessingContactProgressEvent) -> None:
        print(_format_contacts_progress_event(event), file=sys.stderr)

    return callback


def _skipped_scientific_csv_export_summary() -> dict[str, object]:
    return {
        "stage": "scientific_csv_export",
        "passed": True,
        "skipped": True,
        "requested_exports": {
            "rg_timeseries": False,
            "contact_edges": False,
            "contacts_perframe": False,
        },
        "rg_timeseries_written": False,
        "contact_edges_written": False,
        "contacts_perframe_written": False,
        "paths": {},
        "validation": {
            "rg_timeseries": None,
            "contact_edges": None,
            "contacts_perframe": None,
        },
        "issues": [],
        "issue_count": 0,
    }


def _skipped_analysis_input_export_summary() -> dict[str, object]:
    return {
        "stage": "analysis_input_export",
        "requested": False,
        "skipped": True,
        "passed": True,
    }


def _print_analysis_input_export_error(result: object) -> None:
    payload = _json_safe_result(result)
    if payload is None:
        print("Analysis input export failed.", file=sys.stderr)
        return
    issues = payload.get("issues")
    if isinstance(issues, list) and issues:
        first = issues[0]
        if isinstance(first, dict):
            message = first.get("message")
            stage = first.get("stage")
            if isinstance(message, str):
                prefix = (
                    "Analysis input export failed"
                    if not isinstance(stage, str)
                    else f"Analysis input export failed during {stage}"
                )
                print(f"{prefix}: {message}", file=sys.stderr)
                return
    print("Analysis input export failed.", file=sys.stderr)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _portable_input_name(value: str | Path) -> str:
    name = Path(value).name
    # Reuse the portable path contract, including rejection of empty names.
    try:
        return PortableArtifactReference("input", name).path
    except ValueError:
        raise PreprocessingRunProvenanceBuildError(
            "Input path must have a portable filename."
        ) from None


def _portable_preprocessing_command(argv: tuple[str, ...]) -> tuple[str, ...]:
    path_options = {
        "--manifest", "--output", "--reference-nodes", "--reference-edges",
        "--reference-graph-json",
    }
    tokens = ["mania"]
    index = 1
    while index < len(argv):
        token = argv[index]
        option, separator, value = token.partition("=")
        if option in path_options:
            if not separator:
                index += 1
                if index == len(argv):
                    raise PreprocessingRunProvenanceBuildError(
                        "Path option requires a value."
                    )
                value = argv[index]
            portable = "." if option == "--output" else _portable_input_name(value)
            if separator:
                tokens.append(f"{option}={portable}")
            else:
                tokens.extend((option, portable))
        else:
            tokens.append(token)
        index += 1
    return tuple(tokens)


def _preprocessing_resolved_configuration(
    args: argparse.Namespace,
    options: PreprocessingGraphWorkflowOptions,
) -> dict[str, object]:
    return {
        "manifest_name": _portable_input_name(options.manifest_path),
        "output_root": ".",
        "run_name": options.run_name,
        "expected_condition_names": list(_expected_condition_names(args)),
        "include_rg": options.include_rg,
        "include_contacts": options.include_contacts,
        "include_graph_export": options.include_graph_export,
        "include_diagnostics": options.include_diagnostics,
        "enable_reference_comparison": options.enable_reference_comparison,
        "reference_semantics": options.reference_semantics,
        "reference_input_names": {
            name: None if path is None else _portable_input_name(path)
            for name, path in (
                ("nodes", options.reference_nodes_csv_path),
                ("edges", options.reference_edges_csv_path),
                ("graph_json", options.reference_graph_json_path),
            )
        },
        "frame_sampling": options.frame_sampling.to_dict(),
        "contact_detection_options": options.contact_detection_options.to_dict(
            include_contact_selection=True
        ),
        "contact_computation_limits": options.contact_computation_limits.to_dict(),
        "export_analysis_inputs": _analysis_input_export_requested(args),
        "scientific_csv_exports": _scientific_export_flags(args),
        "write_diagnostics_report": not args.no_write_diagnostics_report,
        "write_reference_comparison_report": not args.no_write_reference_comparison,
    }


def _completed_preprocessing_artifact_references(
    args: argparse.Namespace,
    options: PreprocessingGraphWorkflowOptions,
    layout: PreprocessingGraphWorkflowOutputLayout,
) -> tuple[PortableArtifactReference, ...]:
    """Link known outputs; called only after every requested stage has passed."""
    paths = [
        ("graph_nodes", layout.graph_nodes_csv_path),
        ("graph_edges", layout.graph_edges_csv_path),
        ("graph_json", layout.graph_json_path),
    ]
    if _analysis_input_export_requested(args):
        paths.append(
            ("preprocessing_manifest", layout.output_dir / "mania_manifest.json")
        )
    flags = _scientific_export_flags(args)
    for role, path in (
        ("rg_timeseries", layout.rg_timeseries_csv_path),
        ("contact_edges", layout.contact_edges_csv_path),
        ("contacts_perframe", layout.contacts_perframe_csv_path),
    ):
        if flags[f"export_{role}"]:
            paths.append((role, path))
    if options.include_diagnostics and not args.no_write_diagnostics_report:
        paths.append(("graph_diagnostics_report", layout.diagnostics_report_json_path))
    if options.enable_reference_comparison and not args.no_write_reference_comparison:
        paths.append(
            ("reference_comparison_report", layout.reference_comparison_json_path)
        )
    try:
        return tuple(
            PortableArtifactReference(
                role, path.relative_to(layout.output_dir).as_posix()
            )
            for role, path in paths
        )
    except ValueError:
        raise PreprocessingRunProvenanceBuildError(
            "Artifact path must be portable and inside the output root."
        ) from None


def _run_preprocessing_graph_export_command(args: argparse.Namespace) -> int:
    if _analysis_input_export_requested(args):
        if args.skip_contacts:
            print(
                "--export-analysis-inputs cannot be used with --skip-contacts",
                file=sys.stderr,
            )
            return 2
        if args.contact_selection != "protein":
            print(
                "--export-analysis-inputs requires --contact-selection protein",
                file=sys.stderr,
            )
            return 2
    try:
        options = _build_preprocessing_graph_workflow_options(args)
    except ValueError as exc:
        print(f"Invalid frame sampling options: {exc}", file=sys.stderr)
        return 2
    started_at_utc = _utc_now()
    software_identity = get_software_identity()
    command = tuple(sys.argv)
    analysis_input_export: object | None = (
        None
        if _analysis_input_export_requested(args)
        else _skipped_analysis_input_export_summary()
    )
    scientific_csv_export: object | None = (
        None
        if _scientific_csv_export_requested(args)
        else _skipped_scientific_csv_export_summary()
    )
    _print_preprocessing_graph_export_progress(args, 1)
    plan = build_preprocessing_graph_workflow_plan(options)
    if not plan.passed:
        _print_preprocessing_graph_export_failure(args, 1)
        _print_preprocessing_graph_export_progress(
            args,
            _summary_stage_number(args),
        )
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "plan",
                passed=False,
                plan=plan,
                analysis_input_export=analysis_input_export,
                scientific_csv_export=scientific_csv_export,
            )
        )
        return 1

    _print_preprocessing_graph_export_progress(args, 2)
    runtime_loading = load_preprocessing_graph_workflow_condition_runtimes(
        options.manifest_path,
        expected_condition_names=_expected_condition_names(args),
    )
    if not runtime_loading.passed:
        _print_preprocessing_graph_export_failure(args, 2)
        _print_preprocessing_graph_export_progress(
            args,
            _summary_stage_number(args),
        )
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "runtime_loading",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                analysis_input_export=analysis_input_export,
                scientific_csv_export=scientific_csv_export,
            )
        )
        return 1

    _print_preprocessing_graph_export_progress(args, 3)
    computation_kwargs: dict[str, Any] = {
        "include_rg": options.include_rg,
        "include_contacts": options.include_contacts,
        "frame_sampling": options.frame_sampling,
        "contact_options": options.contact_detection_options,
    }
    if _contact_limit_flags_enabled(args):
        computation_kwargs["contact_computation_limits"] = (
            options.contact_computation_limits
        )
    progress_callback = _contacts_progress_callback(args)
    if progress_callback is not None:
        computation_kwargs["progress_callback"] = progress_callback
    computation = compute_preprocessing_graph_workflow_rg_contacts(
        runtime_loading,
        **computation_kwargs,
    )
    if not computation.passed:
        _print_preprocessing_graph_export_failure(args, 3)
        _print_preprocessing_graph_export_progress(
            args,
            _summary_stage_number(args),
        )
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "computation",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
                analysis_input_export=analysis_input_export,
                scientific_csv_export=scientific_csv_export,
            )
        )
        return 1

    _print_preprocessing_graph_export_progress(args, 4)
    graph_export = export_preprocessing_graph_workflow_artifacts(
        computation,
        plan.output_layout,
    )
    if not graph_export.passed:
        _print_preprocessing_graph_export_failure(args, 4)
        _print_preprocessing_graph_export_progress(
            args,
            _summary_stage_number(args),
        )
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "graph_export",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
                graph_export=graph_export,
                analysis_input_export=analysis_input_export,
                scientific_csv_export=scientific_csv_export,
            )
        )
        return 1

    if _analysis_input_export_requested(args):
        analysis_stage = _analysis_input_export_stage_number(args)
        _print_preprocessing_graph_export_progress(args, analysis_stage)
        analysis_input_export = (
            export_preprocessing_graph_workflow_analysis_inputs(
                graph_export,
                plan.output_layout.output_dir,
            )
        )
        if not _workflow_result_passed(analysis_input_export):
            _print_preprocessing_graph_export_failure(args, analysis_stage)
            _print_analysis_input_export_error(analysis_input_export)
            _print_preprocessing_graph_export_progress(
                args,
                _summary_stage_number(args),
            )
            _print_preprocessing_graph_export_summary(
                _build_preprocessing_graph_export_summary(
                    "analysis_input_export",
                    passed=False,
                    plan=plan,
                    runtime_loading=runtime_loading,
                    computation=computation,
                    graph_export=graph_export,
                    analysis_input_export=analysis_input_export,
                    scientific_csv_export=scientific_csv_export,
                )
            )
            return 1

    if _scientific_csv_export_requested(args):
        scientific_stage = _scientific_csv_export_stage_number(args)
        _print_preprocessing_graph_export_progress(args, scientific_stage)
        scientific_export_flags = _scientific_export_flags(args)
        scientific_csv_export = (
            export_preprocessing_graph_workflow_scientific_csvs(
                computation,
                plan.output_layout,
                export_rg_timeseries=scientific_export_flags[
                    "export_rg_timeseries"
                ],
                export_contact_edges=scientific_export_flags[
                    "export_contact_edges"
                ],
                export_contacts_perframe=scientific_export_flags[
                    "export_contacts_perframe"
                ],
            )
        )
        if not _workflow_result_passed(scientific_csv_export):
            _print_preprocessing_graph_export_failure(args, scientific_stage)
            _print_preprocessing_graph_export_progress(
                args,
                _summary_stage_number(args),
            )
            _print_preprocessing_graph_export_summary(
                _build_preprocessing_graph_export_summary(
                    "scientific_csv_export",
                    passed=False,
                    plan=plan,
                    runtime_loading=runtime_loading,
                    computation=computation,
                    graph_export=graph_export,
                    analysis_input_export=analysis_input_export,
                    scientific_csv_export=scientific_csv_export,
                )
            )
            return 1

    diagnostics: object | None
    diagnostics_stage = _diagnostics_stage_number(args)
    _print_preprocessing_graph_export_progress(args, diagnostics_stage)
    if args.skip_diagnostics:
        diagnostics = {"passed": True, "skipped": True}
    else:
        diagnostics = run_preprocessing_graph_workflow_diagnostics(
            graph_export,
            write_report_json=not args.no_write_diagnostics_report,
        )
        if not _workflow_result_passed(diagnostics):
            _print_preprocessing_graph_export_failure(
                args,
                diagnostics_stage,
            )
            _print_preprocessing_graph_export_progress(
                args,
                _summary_stage_number(args),
            )
            _print_preprocessing_graph_export_summary(
                _build_preprocessing_graph_export_summary(
                    "diagnostics",
                    passed=False,
                    plan=plan,
                    runtime_loading=runtime_loading,
                    computation=computation,
                    graph_export=graph_export,
                    analysis_input_export=analysis_input_export,
                    scientific_csv_export=scientific_csv_export,
                    diagnostics=diagnostics,
                )
            )
            return 1

    reference_comparison_stage = _reference_comparison_stage_number(args)
    _print_preprocessing_graph_export_progress(
        args,
        reference_comparison_stage,
    )
    reference_comparison = (
        compare_preprocessing_graph_workflow_reference_artifacts(
            graph_export,
            options,
            plan.output_layout,
            write_report_json=not args.no_write_reference_comparison,
        )
    )
    if not reference_comparison.passed:
        _print_preprocessing_graph_export_failure(
            args,
            reference_comparison_stage,
        )
        _print_preprocessing_graph_export_progress(
            args,
            _summary_stage_number(args),
        )
        _print_preprocessing_graph_export_summary(
            _build_preprocessing_graph_export_summary(
                "reference_comparison",
                passed=False,
                plan=plan,
                runtime_loading=runtime_loading,
                computation=computation,
                graph_export=graph_export,
                analysis_input_export=analysis_input_export,
                scientific_csv_export=scientific_csv_export,
                diagnostics=diagnostics,
                reference_comparison=reference_comparison,
            )
        )
        return 1

    ended_at_utc = _utc_now()
    try:
        provenance = build_completed_preprocessing_run_provenance(
            computation,
            run_id=options.run_name,
            started_at_utc=started_at_utc,
            ended_at_utc=ended_at_utc,
            software_identity=software_identity,
            command=_portable_preprocessing_command(command),
            resolved_configuration=_preprocessing_resolved_configuration(args, options),
            artifact_references=_completed_preprocessing_artifact_references(
                args, options, plan.output_layout
            ),
        )
    except PreprocessingRunProvenanceBuildError as exc:
        print(f"Run provenance build failed: {exc}", file=sys.stderr)
        return 1
    write_result = write_run_provenance(
        provenance, plan.output_layout.output_dir, overwrite=options.overwrite
    )
    if not write_result.passed:
        print(f"Run provenance write failed: {write_result.error}", file=sys.stderr)
        return 1

    _print_preprocessing_graph_export_progress(
        args,
        _summary_stage_number(args),
    )
    _print_preprocessing_graph_export_summary(
        _build_preprocessing_graph_export_summary(
            "preprocessing_graph_export",
            passed=True,
            plan=plan,
            runtime_loading=runtime_loading,
            computation=computation,
            graph_export=graph_export,
            analysis_input_export=analysis_input_export,
            scientific_csv_export=scientific_csv_export,
            diagnostics=diagnostics,
            reference_comparison=reference_comparison,
        )
    )
    return 0


def _run_wania_build_payload_command(args: argparse.Namespace) -> int:
    output_path = (
        args.output
        if args.output is not None
        else args.output_dir / "wania_graph_payload.json"
    )
    artifact_root = args.graph_json.parent.parent
    try:
        run_metadata = WaniaGraphPayloadRunMetadata(
            run_name=args.run_name,
            protein_id=args.protein_id,
            protein_name=args.protein_name,
            condition_names=args.condition_names,
        )
        condition_names = tuple(run_metadata.condition_names or ())
        if len(condition_names) != len(set(condition_names)):
            print(
                "WANIA payload build failed: condition names must be unique.",
                file=sys.stderr,
            )
            return 1
        build_result = build_wania_graph_payload_from_artifacts(
            run_metadata=run_metadata,
            artifact_paths=WaniaGraphPayloadArtifactPaths(
                graph_json_path=args.graph_json,
            ),
            output_root=artifact_root,
        )
    except Exception as exc:
        print(f"WANIA payload build failed: {exc}", file=sys.stderr)
        return 1

    if not build_result.passed:
        messages = "; ".join(
            issue.message for issue in build_result.issues if issue.fatal
        )
        print(f"WANIA payload build failed: {messages}", file=sys.stderr)
        return 1

    diagnostics = cast(dict[str, Any], build_result.payload["diagnostics"])
    if diagnostics.get("passed") is None:
        diagnostics["passed"] = build_result.passed

    try:
        write_result = write_wania_graph_payload_json(
            build_result.payload,
            output_path,
        )
    except Exception as exc:
        print(f"WANIA payload write failed: {exc}", file=sys.stderr)
        return 1
    if not write_result.passed:
        messages = "; ".join(issue.message for issue in write_result.issues)
        print(f"WANIA payload write failed: {messages}", file=sys.stderr)
        return 1

    print(f"WANIA payload written: {write_result.output_path}")
    return 0


def _run_analyze_command(args: argparse.Namespace) -> int:
    try:
        request = AnalyzeRequest(
            input_root=args.input,
            output_root=args.output,
            conditions=tuple(args.conditions or ()),
            enable_pca=args.enable_pca,
            clustering_basis=args.clustering_basis,
            pca_components_for_clustering=args.pca_components_for_clustering,
        )
        result = run_analysis(request)
    except AnalyzeError as exc:
        print(f"Analyze failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Analyze failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_summary(), sort_keys=True))
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

    if args.command == "analyze":
        exit_code = _run_analyze_command(args)
        if exit_code != 0:
            raise SystemExit(exit_code)
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

    if args.command == "wania" and args.wania_command == "build-payload":
        exit_code = _run_wania_build_payload_command(args)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    parser.print_help()
