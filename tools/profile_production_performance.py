"""Developer-only fresh production timing; no production schema changes.

Use --mode plain for before/after measurements, coarse for exclusive perf_counter
stages, and cprofile for a separate function profile. Arguments after -- are the
ordinary ``mania production run`` arguments. Preparation is never invoked.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import importlib
import json
import platform
import pstats
import resource
import sys
import time
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

# Only real callable boundaries. Nested timings are exclusive and additive.
TARGETS = {
    "mania.production_run": {
        "preflight_trajectory": "input/control validation",
        "_science": "completion verification",
        "file_digest": "SHA256/hashing",
        "_tree_digests": "completion inventory",
    },
    "mania.preprocessing.namd_authority": {
        "source_identity": "SHA256/hashing",
    },
    "mania.preprocessing.trajectory_contacts_export": {
        "write_contacts_perframe_csv": "protein per-frame CSV writing",
    },
    "mania.preprocessing.protein_edge_window_table_io": {
        "write_dataset_protein_edge_window_csv": "protein source CSV writing",
        "read_dataset_protein_edge_window_csv": "protein source CSV reading",
    },
    "mania.preprocessing.trajectory_graph_workflow": {
        "load_preprocessing_graph_workflow_condition_runtimes": "trajectory loading",
        "export_preprocessing_graph_workflow_artifacts": "graph construction/export",
        "run_preprocessing_graph_workflow_diagnostics": "graph diagnostics",
        "export_preprocessing_graph_workflow_scientific_csvs": "scientific CSV export",
        "export_preprocessing_graph_workflow_analysis_inputs": "analysis input export",
    },
    "mania.preprocessing.physical_time_execution": {
        "build_preprocessing_temporal_execution": "temporal sample resolution",
    },
    "mania.preprocessing.trajectory_contacts": {
        "compute_condition_contacts": "protein contact orchestration",
        "_compute_contact_frame": "protein contact geometry",
    },
    "mania.preprocessing.protein_lipid_contacts": {
        "compute_protein_lipid_contacts": "lipid contact geometry",
    },
    "mania.preprocessing.protein_glycan_contacts": {
        "compute_protein_glycan_contacts": "glycan contact geometry",
    },
    "mania.preprocessing.specialized_contact_execution": {
        "execute_specialized_contact_condition": "specialized contact orchestration",
    },
    "mania.preprocessing.specialized_contact_window_tables": {
        "build_protein_lipid_window_table": "lipid window reduction",
        "build_protein_glycan_window_table": "glycan window reduction",
    },
    "mania.preprocessing.protein_edge_window_execution": {
        "build_preprocessing_protein_edge_window_source_table": (
            "protein window reduction"
        ),
    },
    "mania.preprocessing.perframe_observations": {
        "write_perframe_observations": "combined per-frame persistence",
        "read_perframe_observations": "retained-observation verification",
        "_documents": "per-frame object construction/verification",
    },
    "mania.preprocessing.window_replay": {
        "replay_window_tables": "offline replay",
    },
    "mania.artifact_inventory_io": {
        "build_artifact_inventory": "artifact inventory",
        "stream_file_sha256": "SHA256/hashing",
    },
    "mania.validation": {"validate_run_artifacts": "strict validation"},
    "mania.cli": {
        "_export_stage30_tables": "canonical/annotated export",
    },
    "json": {
        "dumps": "JSON serialization",
        "loads": "JSON parsing",
        "dump": "JSON serialization",
        "load": "JSON parsing",
    },
}

for _family in ("edge", "lipid", "glycan"):
    for _module, _prefix, _stage in [
        ("canonical_window_tables", "build_canonical", "canonical transformation"),
        (
            "annotated_window_tables",
            "build_annotated_canonical",
            "annotation transformation",
        ),
        ("canonical_window_tables_io", "write_canonical", "canonical CSV writing"),
        (
            "annotated_window_tables_io",
            "write_annotated_canonical",
            "annotated CSV writing",
        ),
    ]:
        _suffix = "table" if _prefix.startswith("build") else "csv"
        TARGETS.setdefault("mania." + _module, {})[
            f"{_prefix}_protein_{_family}_window_{_suffix}"
        ] = _stage


class CoarseTimer:
    """Single-threaded nested wall timer; children are subtracted from parents."""

    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.stack = []
        self.rows = defaultdict(
            lambda: {"calls": 0, "inclusive_seconds": 0.0, "wall_seconds": 0.0}
        )
        self.file_scans = defaultdict(lambda: {"calls": 0, "bytes": 0, "seconds": 0.0})
        self.dcd_reads = defaultdict(lambda: {"calls": 0, "coordinate_bytes": 0})

    def wrap(self, function, stage):
        key = f"{function.__module__}.{function.__qualname__}"

        @functools.wraps(function)
        def measured(*args, **kwargs):
            entry = [self.clock(), 0.0, stage]
            self.stack.append(entry)
            succeeded = False
            try:
                result = function(*args, **kwargs)
                succeeded = True
                return result
            finally:
                elapsed = self.clock() - entry[0]
                self.stack.pop()
                if self.stack:
                    self.stack[-1][1] += elapsed
                row = self.rows[key]
                row["stage"] = stage
                row["calls"] += 1
                row["inclusive_seconds"] += elapsed
                row["wall_seconds"] += elapsed - entry[1]
                if stage == "SHA256/hashing" and args and isinstance(args[0], Path):
                    path = args[0]
                    if path.is_file():
                        scan = self.file_scans[str(path)]
                        scan["calls"] += 1
                        scan["bytes"] += path.stat().st_size
                        scan["seconds"] += elapsed
                if succeeded and function.__name__ == "_read_next_timestep" and args:
                    runtime = args[0]
                    parent = next(
                        (
                            s[2]
                            for s in reversed(self.stack)
                            if s[2] != "DCD opening/coordinate reads"
                        ),
                        "wrapper",
                    )
                    read = self.dcd_reads[f"{runtime.filename} | {parent}"]
                    read["calls"] += 1
                    read["coordinate_bytes"] += runtime.n_atoms * 3 * 4

        return measured

    def install(self, contexts):
        for module_name, functions in TARGETS.items():
            module = importlib.import_module(module_name)
            for name, stage in functions.items():
                if not hasattr(module, name):
                    raise ValueError(
                        f"Unknown profiling boundary: {module_name}.{name}"
                    )
                original = getattr(module, name)
                replacement = self.wrap(original, stage)
                contexts.enter_context(patch.object(module, name, replacement))
                # Patch already-imported aliases too; future imports see replacement.
                for imported in tuple(sys.modules.values()):
                    if (
                        imported
                        and imported is not module
                        and getattr(imported, "__name__", "").startswith("mania")
                    ):
                        for attr, value in tuple(vars(imported).items()):
                            if value is original:
                                contexts.enter_context(
                                    patch.object(imported, attr, replacement)
                                )
        from MDAnalysis.coordinates.DCD import DCDReader

        for name in ("__init__", "_read_frame", "_read_next_timestep"):
            contexts.enter_context(
                patch.object(
                    DCDReader,
                    name,
                    self.wrap(getattr(DCDReader, name), "DCD opening/coordinate reads"),
                )
            )

    def report(self, wall):
        rows = [dict(function=name, **row) for name, row in self.rows.items()]
        accounted = sum(row["wall_seconds"] for row in rows)
        rows.append(
            {
                "stage": "wrapper/uninstrumented",
                "function": None,
                "calls": 1,
                "wall_seconds": wall - accounted,
            }
        )
        for row in rows:
            row["percent_wall"] = 100 * row["wall_seconds"] / wall if wall else 0.0
        return sorted(rows, key=lambda row: -row["wall_seconds"])


def validate_command(command):
    if command[:2] != ["production", "run"] or "--resume" in command:
        raise ValueError("Only a fresh production run is permitted")
    for flag in ("--output-root", "--technical-manifest"):
        if flag not in command or command.index(flag) + 1 >= len(command):
            raise ValueError(f"Explicit {flag} is required")
    root = Path(command[command.index("--output-root") + 1])
    if root.exists():
        raise ValueError("Benchmark output root must not exist")
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("plain", "coarse", "cprofile"), required=True
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    output = validate_command(command)
    args.evidence.mkdir(parents=True, exist_ok=False)
    timer = CoarseTimer()
    # Geometry performs many builtin calls. Keep all Python call counts/times,
    # with builtin work charged to its Python caller, avoiding builtin event cost.
    profiler = (
        cProfile.Profile(subcalls=False, builtins=False)
        if args.mode == "cprofile"
        else None
    )
    from mania.cli import main as mania_main

    contexts = ExitStack()
    if args.mode == "coarse":
        timer.install(contexts)
        timer.rows.clear()
        timer.file_scans.clear()
        timer.dcd_reads.clear()
    started = time.perf_counter()
    cpu_started = time.process_time()
    result = 1
    try:
        if profiler:
            profiler.enable()
        with patch.object(sys, "argv", ["mania", *command]):
            try:
                mania_main()
                result = 0
            except SystemExit as exc:
                result = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
        return result
    finally:
        if profiler:
            profiler.disable()
        wall = time.perf_counter() - started
        cpu = time.process_time() - cpu_started
        contexts.close()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        production_module = sys.modules.get("mania.production_run")
        measured = {
            "mode": args.mode,
            "cprofile_options": (
                {"subcalls": False, "builtins": False} if profiler else None
            ),
            "command": command,
            "exit_code": result,
            "wall_seconds": wall,
            "cpu_seconds": cpu,
            "peak_rss_kib": usage.ru_maxrss,
            "output_bytes": sum(
                p.stat().st_size for p in output.rglob("*") if p.is_file()
            ),
            "python": sys.version,
            "platform": platform.platform(),
            "production_module": str(Path(production_module.__file__))
            if production_module is not None
            else None,
            "timing_scope": (
                "CLI dispatch through completion; excludes interpreter/import startup"
            ),
        }
        (args.evidence / "timings.json").write_text(
            json.dumps(measured, indent=2) + "\n"
        )
        if args.mode == "coarse":
            (args.evidence / "coarse_stage_timings.json").write_text(
                json.dumps(timer.report(wall), indent=2) + "\n"
            )
            (args.evidence / "file_scans.json").write_text(
                json.dumps(dict(timer.file_scans), indent=2) + "\n"
            )
            (args.evidence / "dcd_reads.json").write_text(
                json.dumps(dict(timer.dcd_reads), indent=2) + "\n"
            )
        if profiler:
            profiler.dump_stats(str(args.evidence / "cprofile.pstats"))
            with (args.evidence / "cprofile_top.txt").open("w") as stream:
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats("cumulative").print_stats(80)
                stats.sort_stats("tottime").print_stats(80)


if __name__ == "__main__":
    raise SystemExit(main())
