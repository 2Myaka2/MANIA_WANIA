"""Run the nine reviewed Egor trajectories with one explicit batch review."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Match the accepted serial preparation profile before importing numerical code.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

if __package__:
    from . import production_input_preparation as prep
else:
    import production_input_preparation as prep

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "production/egor_runtime"
SELECTIONS = tuple(sorted(prep.SELECTIONS))
MIN_FREE_BYTES = 12_000_000_000


def read(path: Path) -> Any:
    return prep.read_strict_json(path)


def original_path(source: Path, logical: str) -> Path:
    """Bind only the reviewed egor mount; never search by filename."""
    parts = prep.portable_path(logical).parts
    prep.require(parts[0] == "egor" and len(parts) > 1, "Wrong Egor source mount")
    return prep.contained(source, Path(*parts[1:]).as_posix())


def discover(source: Path, runtime: Path, selections: tuple[str, ...]) -> dict:
    prep.package_inventory(runtime)
    inventory = read(runtime / "authority/source_inventory.json")
    prep.require(
        len(inventory) == 9
        and {r["trajectory_id"] for r in inventory} == set(SELECTIONS),
        "Runtime authority must contain exactly the nine Egor selections",
    )
    rows = {r["trajectory_id"]: r for r in inventory}
    paths: dict[str, dict | None] = {}
    by_trajectory = {}
    errors = []
    shared = read(runtime / "authority/shared_toppar.json")["sources"]
    for tid in selections:
        row = rows[tid]
        records = [
            *row["files"].values(),
            *row.get("parameter_references", []),
            *shared,
        ]
        selected_paths = {r["path"] for r in records} | {row["expected_dcd_path"]}
        by_trajectory[tid] = sorted(selected_paths)
        for item in records:
            name = item["path"]
            prep.require(name not in paths or paths[name] == item, "Conflicting source")
            paths[name] = item
        paths[row["expected_dcd_path"]] = None
        for name in sorted(selected_paths):
            path = original_path(source, name)
            if not path.is_file():
                kind = "DCD" if name == row["expected_dcd_path"] else "source"
                errors.append(
                    f"{tid}: missing {kind}"
                    f" {path} (authority: {name}; run: {row['declared_dcd_filename']})"
                )
    prep.require(not errors, "Source discovery failed:\n" + "\n".join(errors))
    return dict(paths=paths, by_trajectory=by_trajectory)


def bind_sources(source: Path, data: Path, runtime: Path, discovery: dict) -> dict:
    """Create contained hard links and retain the immutable authority bytes."""
    prep.no_symlinks(data)
    data.mkdir(parents=True, exist_ok=True)
    package = data / "egor_handoff"
    if not package.exists():
        shutil.copytree(runtime, package)
    prep.require(
        prep.package_inventory(package) == prep.package_inventory(runtime),
        "Runtime authority changed; retain this attempt and choose a fresh OUTPUT_DIR",
    )
    records = {}
    for logical, expected in discovery["paths"].items():
        original = original_path(source, logical)
        actual = prep.record(original, source)
        if expected is not None:
            prep.require(
                (actual["size_bytes"], actual["sha256"])
                == (expected["size_bytes"], expected["sha256"]),
                f"Wrong source/system authority: {logical}",
            )
        target = data / logical
        prep.no_symlinks(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            prep.require(
                target.samefile(original),
                f"Source replaced: {original}; choose a fresh OUTPUT_DIR",
            )
        else:
            try:
                os.link(original, target)
            except OSError as exc:
                raise ValueError(
                    f"Cannot hard-link {original} into {data}; a writable input "
                    "filesystem supporting hard links is required; no raw copy made"
                ) from exc
        records[logical] = actual
    snapshot = dict(source_root=str(source), files=records)
    saved = data / "source_binding.json"
    if saved.exists():
        prep.require(
            read(saved) == snapshot, "Source changed; choose a fresh OUTPUT_DIR"
        )
    else:
        prep.dump(saved, snapshot)
    return snapshot


def verify_sources(source: Path, snapshot: dict, logical_paths: list[str]) -> None:
    for name in logical_paths:
        prep.require(
            prep.record(original_path(source, name), source) == snapshot["files"][name],
            f"Source changed after binding/preparation: {name}",
        )


def environment(repo: Path) -> dict:
    import mania

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True
        ).strip()

    mania_path = Path(mania.__file__).resolve()
    prep.require(
        mania_path == repo / "src/mania/__init__.py",
        "Install this checkout in the active environment: "
        'python -m pip install -e ".[md]"',
    )
    return dict(
        git_sha=git("rev-parse", "HEAD"),
        git_status=git("status", "--porcelain"),
        python=sys.version,
        executable=sys.executable,
        mania=importlib.metadata.version("mania-wania"),
        mania_import_path=str(mania_path),
        mdanalysis=importlib.metadata.version("MDAnalysis"),
        command=[sys.executable, *sys.argv],
        cwd=str(Path.cwd()),
    )


class Commands:
    def __init__(self, directory: Path, data: Path):
        self.directory, self.data = directory, data

    def run(self, label: str, command: list[str]) -> dict:
        started, timer = prep.utc_now(), time.monotonic()
        out = self.directory / f"{label}.stdout"
        err = self.directory / f"{label}.stderr"
        env = dict(os.environ, MANIA_DATA_ROOT=str(self.data))
        env.pop("PYTHONPATH", None)
        invocation = dict(
            command=command,
            cwd=str(Path.cwd()),
            data_root=str(self.data),
            started_utc=started,
            stdout=str(out),
            stderr=str(err),
        )
        # A killed launcher still leaves the exact command and its log locations.
        prep.dump(self.directory / f"{label}.started.json", invocation)
        code = None
        try:
            with out.open("x") as stdout, err.open("x") as stderr:
                code = subprocess.call(command, env=env, stdout=stdout, stderr=stderr)
        finally:
            prep.dump(
                self.directory / f"{label}.command.json",
                dict(
                    **invocation,
                    ended_utc=prep.utc_now(),
                    elapsed_seconds=time.monotonic() - timer,
                    exit_code=code,
                ),
            )
        prep.require(
            code == 0,
            f"{label} failed (exit {code}): {err.read_text()[-3000:]} "
            f"{out.read_text()[-3000:]} Logs: {self.directory}",
        )
        return read(out)


def plan_attempt(output: Path, data: Path, tid: str, technical: bool) -> dict:
    base = output / "trajectories" / tid
    prep.no_symlinks(base)
    attempts = sorted(base.glob("attempt_[0-9][0-9][0-9][0-9]"))
    attempt = attempts[-1] if attempts else base / "attempt_0001"

    def paths(at: Path) -> dict:
        production = at / "production"
        target = production / "technical_validation" if technical else production
        target = target / "trajectories" / tid
        result = data / "prepared" / tid / at.name
        marker = target / (
            "technical_complete.json" if technical else "science_complete.json"
        )
        return dict(
            tid=tid,
            attempt=at,
            result=result,
            production=production,
            target=target,
            marker=marker,
            binding=result / "confirmation/production_input_binding.json",
        )

    plan = paths(attempt)
    for path in (plan["result"], plan["marker"], plan["binding"]):
        prep.no_symlinks(path)
    if attempts and not plan["marker"].is_file():
        # A completed preparation declined before confirmation can be reviewed again.
        pending = (
            (plan["result"] / "complete.json").is_file()
            and not (plan["result"] / "confirmation").exists()
            and not plan["target"].exists()
        )
        if not pending:
            print(
                f"{tid}: preserving incomplete {attempt}; creating a fresh attempt.",
                flush=True,
            )
            number = int(attempt.name.split("_")[1]) + 1
            prep.require(
                number <= 9999, "Attempt limit reached; choose a new OUTPUT_DIR"
            )
            plan = paths(base / f"attempt_{number:04d}")
    plan["reuse"] = plan["marker"].is_file()
    return plan


def report_for(plan: dict, data: Path) -> dict:
    result = plan["result"]
    complete = read(result / "complete.json")
    prep.check_records(complete, data)
    report = read(result / "report.json")
    prep.require(
        report["trajectory_id"] == plan["tid"]
        and report["status"] == "pending_review"
        and report["failures"] == []
        and set(report["checks"]) == prep.AUTOMATIC_CHECKS
        and all(value is True for value in report["checks"].values()),
        f"{plan['tid']}: automatic preparation checks failed",
    )
    prep.check_records(report["inputs"], data)
    prep.check_records(report["outputs"], data)
    return dict(report=report, sha256=complete["report.json"]["sha256"])


def preparation_command(
    plan: dict, data: Path, operation: str, minimum: int
) -> list[str]:
    return [
        sys.executable,
        str(REPO / "tools/prepare_production_inputs.py"),
        operation,
        "--data-root",
        str(data),
        "--result-root",
        str(plan["result"]),
        "--authority-package",
        str(data / "egor_handoff"),
        "--trajectory-id",
        plan["tid"],
        "--min-free-bytes",
        str(minimum),
    ]


def production_command(
    plan: dict, data: Path, operation: str, minimum: int, technical: bool
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "mania",
        "production",
        operation,
        "--catalog",
        str(data / "egor_handoff/catalog/dataset.yaml"),
        "--trajectory-id",
        plan["tid"],
        "--output-root",
        str(plan["production"]),
        "--input-binding",
        str(plan["binding"]),
        "--min-free-bytes",
        str(minimum),
    ]
    if technical:
        command.extend(
            ["--technical-manifest", str(data / "egor_handoff/technical_0ss_r1.json")]
        )
    if plan["reuse"]:
        command.append("--resume")
    return command


def batch(
    source: Path,
    output: Path,
    *,
    technical: bool = False,
    runtime: Path = RUNTIME,
    minimum: int = MIN_FREE_BYTES,
) -> int:
    source = source.resolve()
    prep.require(source.is_dir(), f"Egor input directory does not exist: {source}")
    prep.no_symlinks(output.absolute())
    output = output.resolve()
    prep.require(
        not output.is_relative_to(source) and not source.is_relative_to(output),
        "OUTPUT_DIR and EGOR_DATA_DIR must be disjoint; "
        "output inside input is forbidden",
    )
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / ".launcher.lock"
    prep.no_symlinks(lock_path)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another launcher is using this OUTPUT_DIR") from exc
        return locked_batch(source, output, technical, runtime, minimum)


def locked_batch(
    source: Path, output: Path, technical: bool, runtime: Path, minimum: int
) -> int:
    mode = "test_0ss_r1" if technical else "production"
    selections = (SELECTIONS[0],) if technical else SELECTIONS
    key = hashlib.sha256(str(output).encode()).hexdigest()[:20]
    data = source / ".mania_egor" / key / mode
    output = output / mode
    invocation = output / "launcher" / uuid.uuid4().hex
    prep.no_symlinks(invocation)
    invocation.mkdir(parents=True)
    commands = Commands(invocation, data)
    completed: list[str] = []
    phase, current = "preflight", "batch"
    print(f"Evidence: {invocation}", flush=True)
    try:
        meta = environment(REPO)
        prep.dump(invocation / "environment.json", meta)
        discovery = discover(source, runtime, selections)
        plans = [plan_attempt(output, data, tid, technical) for tid in selections]
        estimate = 0
        for plan in plans:
            template = read(runtime / f"templates/{plan['tid']}/raw_time.template.json")
            if not plan["reuse"] and not (plan["result"] / "complete.json").exists():
                estimate += (
                    template["expected_frame_count"]
                    * (12 * template["expected_atom_count"] + 8192)
                    + 1024 * 1024
                )
        disk = dict(
            input=prep._space(source, minimum, estimate + minimum),
            output=prep._space(output, minimum, 0),
        )
        snapshot = bind_sources(source, data, runtime, discovery)
        # Verify every selected system/run before the first heavy preparation.
        for tid in selections:
            current = tid
            prep.select_authority(data, data / "egor_handoff", tid)
        prep.dump(
            invocation / "preflight.json",
            dict(
                selections=list(selections),
                source_binding=snapshot,
                disk=disk,
                authority_inventory=prep.package_inventory(runtime),
                technical_test=technical,
            ),
        )
        print(
            f"Preflight PASS: {len(selections)} source sets; Git {meta['git_sha']}.",
            flush=True,
        )
        pending = []
        for plan in plans:
            current, phase = plan["tid"], "prepare"
            if plan["reuse"]:
                verify_sources(source, snapshot, discovery["by_trajectory"][current])
                outcome = commands.run(
                    f"{current}.reuse",
                    production_command(plan, data, "run", minimum, technical),
                )
                prep.require(
                    outcome.get("reused") is True, "Completed result was not reused"
                )
                completed.append(current)
                print(f"{current}: completed result validated and reused.", flush=True)
                continue
            if not plan["attempt"].exists():
                plan["attempt"].mkdir(parents=True)
                prep.dump(
                    plan["attempt"] / "attempt.json",
                    dict(
                        **meta,
                        trajectory_id=current,
                        data_root=str(data),
                        preparation=str(plan["result"]),
                        production=str(plan["production"]),
                    ),
                )
            if not (plan["result"] / "complete.json").exists():
                print(
                    f"{current}: preparing full raw trajectory; logs in {invocation}.",
                    flush=True,
                )
                commands.run(
                    f"{current}.prepare",
                    [
                        *preparation_command(plan, data, "prepare", minimum),
                        "--workers",
                        "1",
                        "--threads",
                        "1",
                    ],
                )
            plan.update(report_for(plan, data))
            pending.append(plan)
        if pending:
            phase, current = "human_review", "batch"
            print("\nReview the entire selected set before approving:", flush=True)
            for plan in plans:
                tid = plan["tid"]
                if plan["reuse"]:
                    print(f"{tid}: validated completed result reused.", flush=True)
                    continue
                report = plan["report"]
                e = report["evidence"]
                print(
                    f"{tid}: 12/12 automatic PASS; {e['frame_count']} frames; "
                    f"{e['atom_count']} atoms; {e['scientific_time_bounds_ps']} ps.\n"
                    f"  Summary: {plan['result'] / 'summary.txt'}\n"
                    f"  Report: {plan['result'] / 'report.json'}\n"
                    f"  Raw: {report['inputs']['trajectory_path']['path']}\n"
                    f"  PSF: {report['inputs']['topology_path']['path']}\n"
                    f"  CONF/OUT: {report['inputs']['config_path']['path']} / "
                    f"{report['inputs']['log_path']['path']}",
                    flush=True,
                )
            print(
                "Automatic checks: " + ", ".join(sorted(prep.AUTOMATIC_CHECKS)),
                flush=True,
            )
            print(
                "DCD has no atom labels. Review source/run/PSF correspondence and "
                "each summary/report. Automatic PASS is not human review or final QC.",
                flush=True,
            )
            reviewer = input("Reviewer name (required): ").strip()
            note = input("Review note (required): ").strip()
            answer = input(
                f"Approve this displayed {len(plans)}-trajectory set? [y/N]: "
            ).strip()
            prep.dump(
                invocation / "review.json",
                dict(
                    reviewer=reviewer,
                    note=note,
                    answer=answer,
                    selections=list(selections),
                    reports={p["tid"]: p["sha256"] for p in pending},
                    reused=completed,
                    utc=prep.utc_now(),
                ),
            )
            prep.require(
                answer.lower() == "y", "Approval declined; no new production started"
            )
            prep.require(
                bool(reviewer) and bool(note), "Named reviewer and review note required"
            )
            phase = "confirm"
            verify_sources(source, snapshot, list(discovery["paths"]))
            for plan in pending:
                current = plan["tid"]
                commands.run(
                    f"{current}.confirm",
                    [
                        *preparation_command(plan, data, "confirm", minimum),
                        "--report-sha256",
                        plan["sha256"],
                        "--reviewer",
                        reviewer,
                        "--review-note",
                        note,
                        "--approve",
                        "--production-output-root",
                        str(plan["production"]),
                    ],
                )
            # All confirmations and public preflights must pass before any new run.
            phase = "validate"
            for plan in pending:
                current = plan["tid"]
                outcome = commands.run(
                    f"{current}.validate",
                    production_command(plan, data, "validate", minimum, technical),
                )
                prep.require(
                    outcome.get("status") == "preflight_passed",
                    "Production preflight failed",
                )
            phase = "run"
            for plan in pending:
                current = plan["tid"]
                verify_sources(source, snapshot, discovery["by_trajectory"][current])
                print(
                    f"{current}: production running; "
                    f"{len(completed)}/{len(plans)} completed.",
                    flush=True,
                )
                outcome = commands.run(
                    f"{current}.run",
                    production_command(plan, data, "run", minimum, technical),
                )
                expected = "technical_complete" if technical else "science_complete"
                prep.require(outcome.get("status") == expected, f"Missing {expected}")
                completed.append(current)
        prep.dump(
            invocation / "result.json",
            dict(
                status="completed",
                completed=completed,
                total=len(selections),
                exit_code=0,
            ),
        )
        print(
            f"{len(completed)}/{len(selections)} completed. Evidence: {invocation}",
            flush=True,
        )
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        prep.dump(
            invocation / "result.json",
            dict(
                status="stopped",
                completed=completed,
                total=len(selections),
                exit_code=1,
                trajectory=current,
                phase=phase,
                error=str(exc),
            ),
        )
        print(
            f"STOP {current} / {phase}: {exc}\n"
            f"{len(completed)}/{len(selections)} completed; attempts preserved. "
            f"Evidence: {invocation}",
            file=sys.stderr,
            flush=True,
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("egor_data_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--TEST-0ss-r1-5-8ns",
        dest="technical",
        action="store_true",
        help="advanced acceptance TEST only: raw 0SS/r1, technical 5–8 ns",
    )
    args = parser.parse_args(argv)
    try:
        return batch(args.egor_data_dir, args.output_dir, technical=args.technical)
    except Exception as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
