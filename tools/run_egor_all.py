"""Initialize Egor sources once, then run independent trajectory jobs safely."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
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
    from . import production_source_attestation as attestation
else:
    import production_input_preparation as prep
    import production_source_attestation as attestation

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


def discover(
    source: Path,
    runtime: Path,
    selections: tuple[str, ...],
    *,
    check_sources: bool = True,
) -> dict:
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
    mapping = {}
    errors = []
    shared = read(runtime / "authority/shared_toppar.json")["sources"]
    for tid in selections:
        row = rows[tid]
        selected = dict(row["files"])
        selected["trajectory_path"] = dict(path=row["expected_dcd_path"])
        mapping[tid] = {
            role: dict(
                path=Path(
                    *prep.portable_path(selected[role]["path"]).parts[1:]
                ).as_posix(),
                binding_path=selected[role]["path"],
            )
            for role in attestation.ROLES
        }
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
        for name in sorted(selected_paths) if check_sources else ():
            path = original_path(source, name)
            if not path.is_file():
                kind = "DCD" if name == row["expected_dcd_path"] else "source"
                errors.append(
                    f"{tid}: missing {kind}"
                    f" {path} (authority: {name}; run: {row['declared_dcd_filename']})"
                )
    prep.require(not errors, "Source discovery failed:\n" + "\n".join(errors))
    return dict(paths=paths, by_trajectory=by_trajectory, mapping=mapping)


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


def verify_sources(
    source: Path, snapshot: dict, logical_paths: list[str], data: Path
) -> None:
    for name in logical_paths:
        original = original_path(source, name)
        prep.no_symlinks(source / Path(*prep.portable_path(name).parts[1:]))
        prep.no_symlinks(data / name)
        prep.require(original.is_file(), f"Missing selected source: {name}")
        prep.require(
            (data / name).is_file() and (data / name).samefile(original),
            f"Source replaced or shared source view changed: {name}; "
            "preserve evidence and choose a fresh OUTPUT_DIR",
        )
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
        self.lock_fd: int | None = None

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
                code = subprocess.call(
                    command,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    # Keep the trajectory locked if the launcher is killed while
                    # its scientific child is still running.
                    pass_fds=() if self.lock_fd is None else (self.lock_fd,),
                )
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
        # A completed preparation can continue through automatic confirmation.
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
    failed_checks = sorted(
        name for name in prep.AUTOMATIC_CHECKS if report["checks"].get(name) is not True
    )
    prep.require(
        report["trajectory_id"] == plan["tid"]
        and report["status"] == "pending_review"
        and report["failures"] == []
        and set(report["checks"]) == prep.AUTOMATIC_CHECKS
        and all(value is True for value in report["checks"].values()),
        f"{plan['tid']}: automatic preparation checks failed: {failed_checks}; "
        f"failures: {report['failures']}; status: {report['status']}",
    )
    prep.check_records(report["inputs"], data)
    prep.check_records(report["outputs"], data)
    return dict(report=report, sha256=complete["report.json"]["sha256"])


def preparation_command(
    plan: dict, data: Path, operation: str, minimum: int
) -> list[str]:
    return [
        sys.executable,
        str(REPO / "tools/run_egor_all.py")
        if operation == "confirm"
        else str(REPO / "tools/prepare_production_inputs.py"),
        "--confirm-selected" if operation == "confirm" else operation,
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


def select_trajectories(
    trajectory_id: str | None = None,
    replica: str | None = None,
    *,
    technical: bool = False,
) -> tuple[str, ...]:
    prep.require(not (trajectory_id and replica), "Choose one selection mode")
    prep.require(
        trajectory_id is None or trajectory_id in SELECTIONS, "Unknown trajectory ID"
    )
    prep.require(replica is None or replica in ("r1", "r2", "r3"), "Invalid replica")
    selected = (
        (trajectory_id,)
        if trajectory_id
        else tuple(
            tid for tid in SELECTIONS if replica is None or tid.endswith("_" + replica)
        )
    )
    if technical:
        prep.require(
            replica is None and trajectory_id in (None, SELECTIONS[0]),
            "Technical acceptance supports only namd_egor_wt_0ss_r1",
        )
        return (SELECTIONS[0],)
    return selected


def locations(source: Path, output: Path, technical: bool) -> tuple[Path, Path, Path]:
    source = source.resolve()
    prep.require(source.is_dir(), f"Egor input directory does not exist: {source}")
    prep.no_symlinks(output.absolute())
    output = output.resolve()
    prep.require(
        not output.is_relative_to(source) and not source.is_relative_to(output),
        "OUTPUT_DIR and EGOR_DATA_DIR must be disjoint; "
        "output inside input is forbidden",
    )
    mode = "test_0ss_r1" if technical else "production"
    key = hashlib.sha256(str(output).encode()).hexdigest()[:20]
    data = source / ".mania_egor" / key / mode
    prep.no_symlinks(data)
    return source, output / mode, data


@contextmanager
def exclusive_lock(path: Path, message: str):
    """Never unlink lock files: all contenders must flock the same stable inode."""
    prep.no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(message) from exc
        # Closing the descriptor releases the lock after any inherited scientific
        # child also closes it. Explicit LOCK_UN would unlock a surviving child.
        yield lock.fileno()


def shared_document(
    source: Path, output: Path, data: Path, discovery: dict, runtime: Path
):
    """Small immutable completion manifest; published only after successful init."""
    return dict(
        schema_version="egor.initialization.v1",
        mode=output.name,
        source_root=str(source),
        data_root=str(data),
        selections=list(discovery["mapping"]),
        authority_inventory=prep.package_inventory(runtime),
        source_binding=prep.record(data / "source_binding.json", data),
        source_attestation=prep.record(output / "source_attestation.json", output),
    )


def check_shared(
    source: Path, output: Path, data: Path, discovery: dict, runtime: Path
) -> dict:
    marker = output / "initialization.json"
    prep.require(
        marker.is_file(),
        "Initialization absent or incomplete. Run ./init_egor_production.sh "
        "EGOR_DATA_DIR OUTPUT_DIR first"
        + (
            " --TEST-0ss-r1-5-8ns (technical namespace only)"
            if output.name != "production"
            else ""
        ),
    )
    for path in (
        marker,
        output / "source_attestation.json",
        data / "source_binding.json",
    ):
        prep.no_symlinks(path)
    expected = shared_document(source, output, data, discovery, runtime)
    prep.require(
        read(marker) == dict(**expected, payload_sha256=attestation.digest(expected)),
        "Shared initialization changed/corrupted; preserve evidence "
        "and choose a fresh OUTPUT_DIR",
    )
    prep.require(
        prep.package_inventory(data / "egor_handoff")
        == expected["authority_inventory"],
        "Shared runtime authority changed",
    )
    snapshot = read(data / "source_binding.json")
    prep.require(
        snapshot["source_root"] == str(source)
        and set(snapshot["files"]) == set(discovery["paths"]),
        "Wrong shared source binding",
    )
    # Global schema/digest/mapping checks, without reading unrelated large DCDs.
    attestation.verify(
        output / "source_attestation.json",
        authority_inventory=expected["authority_inventory"],
        source=source,
        mapping=discovery["mapping"],
        trajectory_ids=(),
    )
    return snapshot


def initialize(
    source: Path,
    output: Path,
    *,
    technical: bool = False,
    runtime: Path = RUNTIME,
    minimum: int = MIN_FREE_BYTES,
) -> int:
    source, output, data = locations(source, output, technical)
    selections = select_trajectories(technical=technical)
    try:
        with exclusive_lock(
            output / ".init.lock",
            "Another initialization is active; retry after it finishes",
        ):
            meta = environment(REPO)
            discovery = discover(source, runtime, selections)
            inventory = prep.package_inventory(runtime)
            path = output / "source_attestation.json"
            prep.no_symlinks(path)
            if (output / "initialization.json").exists():
                snapshot = check_shared(source, output, data, discovery, runtime)
                attestation.verify(
                    path,
                    authority_inventory=inventory,
                    source=source,
                    mapping=discovery["mapping"],
                )
                verify_sources(source, snapshot, list(discovery["paths"]), data)
                print(
                    "Initialization verified and reused; no human prompt.", flush=True
                )
                return 0
            # Existing accepted attestations are never replaced, including after
            # an interrupted initialization. Verify before any shared-state writes.
            if path.exists():
                attestation.verify(
                    path,
                    authority_inventory=inventory,
                    source=source,
                    mapping=discovery["mapping"],
                )
            prep._space(source, minimum, 0)
            prep._space(output, minimum, 0)
            snapshot = bind_sources(source, data, runtime, discovery)
            for tid in selections:
                prep.select_authority(data, data / "egor_handoff", tid)
            if not path.exists():
                print(
                    "\nSource/run correspondence (DCD / PSF / CONF / OUT / XSC):",
                    flush=True,
                )
                for tid, roles in discovery["mapping"].items():
                    system, replica = tid.split("_")[-2:]
                    print(
                        f"{system.upper()} {replica} ({tid}) → "
                        + " / ".join(roles[role]["path"] for role in attestation.ROLES),
                        flush=True,
                    )
                identities = attestation.capture(source, discovery["mapping"])
                print(attestation.STATEMENT, flush=True)
                print(
                    "This approves source/run correspondence only. It does not certify "
                    "PBC checks, prepared frames, contacts or QC.",
                    flush=True,
                )
                reviewer = input("Reviewer name (required): ").strip()
                note = input("Review note (required): ").strip()
                answer = input(
                    f"Approve these {len(selections)} source/run mappings? [y/N]: "
                ).strip()
                prep.require(
                    answer.lower() == "y", "Approval declined; no preparation started"
                )
                prep.require(
                    bool(reviewer) and bool(note),
                    "Named reviewer and review note required",
                )
                prep.require(
                    attestation.capture(source, discovery["mapping"]) == identities,
                    "Sources changed during review; "
                    "new explicit source approval required",
                )
                verify_sources(source, snapshot, list(discovery["paths"]), data)
                attestation.save(
                    path,
                    source=source,
                    trajectories=identities,
                    reviewer=reviewer,
                    review_note=note,
                    repository_head=meta["git_sha"],
                    authority_inventory=inventory,
                )
            verify_sources(source, snapshot, list(discovery["paths"]), data)
            document = shared_document(source, output, data, discovery, runtime)
            prep.dump(
                output / "initialization.json",
                dict(**document, payload_sha256=attestation.digest(document)),
            )
            print(
                f"Initialization PASS: {len(selections)} source sets; "
                "no preparation run. "
                f"Namespace: {output}. Git {meta['git_sha']}.",
                flush=True,
            )
            return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"STOP initialization: {exc}", file=sys.stderr, flush=True)
        return 1


def run_trajectory(
    source: Path,
    output: Path,
    data: Path,
    tid: str,
    technical: bool,
    runtime: Path,
    minimum: int,
    discovery: dict,
    commands: Commands,
    meta: dict,
) -> None:
    with exclusive_lock(
        output / "trajectories" / tid / ".trajectory.lock",
        f"{tid}: another trajectory job is active; duplicate execution rejected",
    ) as fd:
        commands.lock_fd = fd
        snapshot = check_shared(source, output, data, discovery, runtime)
        path = output / "source_attestation.json"

        def verify_selected() -> None:
            check_shared(source, output, data, discovery, runtime)
            attestation.verify(
                path,
                authority_inventory=prep.package_inventory(runtime),
                source=source,
                mapping=discovery["mapping"],
                trajectory_ids=(tid,),
            )
            verify_sources(source, snapshot, discovery["by_trajectory"][tid], data)

        verify_selected()
        plan = plan_attempt(output, data, tid, technical)
        if plan["reuse"]:
            outcome = commands.run(
                f"{tid}.reuse",
                production_command(plan, data, "run", minimum, technical),
            )
            prep.require(
                outcome.get("reused") is True, "Completed result was not reused"
            )
            print(f"{tid}: completed result validated; reused=true.", flush=True)
            return
        template = read(runtime / f"templates/{tid}/raw_time.template.json")
        estimate = (
            0
            if (plan["result"] / "complete.json").is_file()
            else (
                template["expected_frame_count"]
                * (12 * template["expected_atom_count"] + 8192)
                + 1024 * 1024
            )
        )
        prep._space(source, minimum, estimate + minimum)
        prep._space(output, minimum, 0)
        prep.select_authority(data, data / "egor_handoff", tid)
        if not plan["attempt"].exists():
            plan["attempt"].mkdir(parents=True)
            prep.dump(
                plan["attempt"] / "attempt.json",
                dict(
                    **meta,
                    trajectory_id=tid,
                    data_root=str(data),
                    preparation=str(plan["result"]),
                    production=str(plan["production"]),
                ),
            )
        if not (plan["result"] / "complete.json").exists():
            print(
                f"{tid}: preparing full raw trajectory; logs in {commands.directory}.",
                flush=True,
            )
            commands.run(
                f"{tid}.prepare",
                [
                    *preparation_command(plan, data, "prepare", minimum),
                    "--workers",
                    "1",
                    "--threads",
                    "1",
                ],
            )
        plan.update(report_for(plan, data))
        verify_selected()
        commands.run(
            f"{tid}.confirm",
            [
                *preparation_command(plan, data, "confirm", minimum),
                "--report-sha256",
                plan["sha256"],
                "--source-attestation",
                str(path),
                "--production-output-root",
                str(plan["production"]),
            ],
        )
        outcome = commands.run(
            f"{tid}.validate",
            production_command(plan, data, "validate", minimum, technical),
        )
        prep.require(
            outcome.get("status") == "preflight_passed", "Production preflight failed"
        )
        verify_selected()
        print(f"{tid}: production running.", flush=True)
        outcome = commands.run(
            f"{tid}.run", production_command(plan, data, "run", minimum, technical)
        )
        expected = "technical_complete" if technical else "science_complete"
        prep.require(outcome.get("status") == expected, f"Missing {expected}")


def batch(
    source: Path,
    output: Path,
    *,
    technical: bool = False,
    runtime: Path = RUNTIME,
    minimum: int = MIN_FREE_BYTES,
    trajectory_id: str | None = None,
    replica: str | None = None,
) -> int:
    selections = select_trajectories(trajectory_id, replica, technical=technical)
    source, output, data = locations(source, output, technical)
    invocation = output / "launcher" / uuid.uuid4().hex
    prep.no_symlinks(invocation)
    invocation.mkdir(parents=True)
    commands = Commands(invocation, data)
    completed: list[str] = []
    current = "preflight"
    print(f"Evidence: {invocation}", flush=True)
    try:
        meta = environment(REPO)
        prep.dump(invocation / "environment.json", meta)
        discovery = discover(
            source,
            runtime,
            select_trajectories(technical=technical),
            check_sources=False,
        )
        check_shared(source, output, data, discovery, runtime)
        prep.dump(
            invocation / "selection.json",
            dict(selections=selections, technical=technical),
        )
        for current in selections:
            run_trajectory(
                source,
                output,
                data,
                current,
                technical,
                runtime,
                minimum,
                discovery,
                commands,
                meta,
            )
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
                error=str(exc),
            ),
        )
        print(
            f"STOP {current}: {exc}\n{len(completed)}/{len(selections)} completed; "
            f"attempts preserved. Evidence: {invocation}",
            file=sys.stderr,
            flush=True,
        )
        return 1


def confirmation_main(argv: list[str]) -> int:
    """Internal subprocess dispatch; preserve the existing automatic confirmation."""
    parser = argparse.ArgumentParser(
        description="Selected-source automatic confirmation"
    )
    for name in (
        "data-root",
        "result-root",
        "authority-package",
        "source-attestation",
        "production-output-root",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--trajectory-id", required=True, choices=SELECTIONS)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--min-free-bytes", required=True, type=int)
    args = vars(parser.parse_args(argv))
    try:
        result = attestation.confirm_selected(
            **args,
            command=[
                sys.executable,
                str(Path(__file__).resolve()),
                "--confirm-selected",
                *argv,
            ],
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status="failed", error=str(exc))), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--confirm-selected":
        return confirmation_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("egor_data_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--init", action="store_true")
    modes.add_argument("--trajectory-id", choices=SELECTIONS)
    modes.add_argument("--replica", choices=("r1", "r2", "r3"))
    modes.add_argument("--all", action="store_true")
    parser.add_argument(
        "--TEST-0ss-r1-5-8ns",
        dest="technical",
        action="store_true",
        help="developer acceptance only: isolated 0SS/r1 initialization and 5–8 ns run",
    )
    args = parser.parse_args(argv)
    try:
        if args.init:
            return initialize(
                args.egor_data_dir, args.output_dir, technical=args.technical
            )
        return batch(
            args.egor_data_dir,
            args.output_dir,
            technical=args.technical,
            trajectory_id=args.trajectory_id,
            replica=args.replica,
        )
    except Exception as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
