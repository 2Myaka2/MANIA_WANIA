"""Process-level init/trajectory locking; synthetic inputs and contact dispatch."""

import contextlib
import io
import json
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_run_egor_all import answer, init_site, launcher, run_site
from test_run_egor_all import inline as inline  # noqa: F401
from test_run_egor_all import site as site  # noqa: F401

CTX = multiprocessing.get_context("fork")


def launch(function):
    queue = CTX.Queue()

    def execute():
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = function()
        queue.put((code, out.getvalue(), err.getvalue()))

    process = CTX.Process(target=execute)
    process.start()
    return process, queue


def finish(job):
    process, queue = job
    try:
        result = queue.get(timeout=60)
        process.join(timeout=10)
        assert process.exitcode == 0
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        queue.close()


def initialized(site, monkeypatch, **kwargs):
    answer(monkeypatch, ["Synthetic reviewer", "Synthetic sources only", "y"])
    assert init_site(site, **kwargs) == 0
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Worker prompted"))


def shared_state(site):
    _, out, data = launcher.locations(site.source, site.output, False)
    paths = [
        out / "source_attestation.json",
        out / "initialization.json",
        data / "source_binding.json",
    ]
    paths += [p for p in (data / "egor_handoff").rglob("*") if p.is_file()]
    paths += [p for p in (data / "egor").rglob("*") if p.is_file()]
    return {
        str(p): (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in paths
    }


@pytest.mark.parametrize("tid", launcher.SELECTIONS)
def test_every_exact_trajectory_selection(tid, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(launcher, "batch", lambda *a, **kw: calls.append(kw) or 0)
    assert (
        launcher.main([str(tmp_path), str(tmp_path / "out"), "--trajectory-id", tid])
        == 0
    )
    assert launcher.select_trajectories(
        **{k: calls[0][k] for k in ("trajectory_id", "replica")}
    ) == (tid,)


@pytest.mark.parametrize("replica", ("r1", "r2", "r3"))
def test_replica_selection(replica):
    assert launcher.select_trajectories(replica=replica) == tuple(
        f"namd_egor_wt_{ss}ss_{replica}" for ss in range(3)
    )


def test_all_selection(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(launcher, "batch", lambda *a, **kw: calls.append(kw) or 0)
    assert launcher.main([str(tmp_path), str(tmp_path / "out"), "--all"]) == 0
    assert launcher.select_trajectories() == launcher.SELECTIONS
    assert len(launcher.SELECTIONS) == 9


@pytest.mark.parametrize("args", [("--trajectory-id", "unknown"), ("--replica", "r4")])
def test_invalid_selection_rejected_before_work(tmp_path, monkeypatch, args):
    monkeypatch.setattr(launcher, "environment", lambda *a: pytest.fail("preflight"))
    with pytest.raises(SystemExit) as exc:
        launcher.main([str(tmp_path), str(tmp_path / "out"), *args])
    assert exc.value.code == 2
    assert not (tmp_path / "out").exists()


def test_initialization_does_not_prepare(site, inline, monkeypatch):
    initialized(site, monkeypatch)
    assert not inline
    assert not list(site.source.rglob("prepared.dcd"))
    assert not list(site.output.rglob("attempt_*"))
    state = shared_state(site)
    assert init_site(site) == 0
    assert shared_state(site) == state


def test_worker_requires_complete_initialization(site, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("prompt"))
    assert run_site(site, init=False, trajectory_id=launcher.SELECTIONS[0]) == 1
    assert "./init_egor_production.sh" in capsys.readouterr().err
    assert not list(site.source.rglob("prepared.dcd"))


def test_interrupted_init_not_accepted_by_workers(site, monkeypatch, inline):
    original = launcher.prep.dump

    def interrupt(path, value):
        if path.name == "initialization.json":
            raise OSError("Synthetic interruption before completion publication")
        original(path, value)

    answer(monkeypatch, ["Synthetic reviewer", "Source scope", "y"])
    monkeypatch.setattr(launcher.prep, "dump", interrupt)
    assert init_site(site) == 1
    saved = (site.output / "production/source_attestation.json").read_bytes()
    assert run_site(site, init=False) == 1
    assert inline == []
    monkeypatch.setattr(launcher.prep, "dump", original)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("reapproval"))
    assert init_site(site) == 0
    assert (site.output / "production/source_attestation.json").read_bytes() == saved


def test_two_first_initializations_are_race_safe(site, monkeypatch, record_property):
    entered, release = CTX.Event(), CTX.Event()
    replies = iter(["Synthetic reviewer", "Synthetic source review", "y"])

    def respond(prompt):
        entered.set()
        assert release.wait(30)
        return next(replies)

    monkeypatch.setattr("builtins.input", respond)
    first = launch(lambda: init_site(site))
    try:
        assert entered.wait(30)
        second = finish(launch(lambda: init_site(site)))
        assert second[0] == 1 and "Another initialization is active" in second[2]
        assert not (site.output / "production/source_attestation.json").exists()
    finally:
        release.set()
        result = finish(first)
    assert result[0] == 0
    record_property("init_race", json.dumps(dict(first=result, second=second)))
    assert sum(" → " in line for line in result[1].splitlines()) == 9
    assert len(list(site.source.rglob("egor_handoff"))) == 1
    before = shared_state(site)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("second prompt"))
    assert init_site(site) == 0
    assert shared_state(site) == before


@pytest.mark.parametrize("reuse_first", [False, True])
def test_different_trajectory_processes_overlap_and_shared_state_is_immutable(
    site, monkeypatch, inline, reuse_first, record_property
):
    initialized(site, monkeypatch)
    first_tid, second_tid = launcher.SELECTIONS[0], launcher.SELECTIONS[3]
    if reuse_first:
        assert run_site(site, init=False, trajectory_id=first_tid) == 0
    before = shared_state(site)
    barrier = CTX.Barrier(2)
    original = launcher.Commands.run

    def overlap(self, label, command):
        if label.endswith((".prepare", ".reuse")):
            barrier.wait(timeout=30)
        return original(self, label, command)

    monkeypatch.setattr(launcher.Commands, "run", overlap)
    first = launch(lambda: run_site(site, init=False, trajectory_id=first_tid))
    second = launch(lambda: run_site(site, init=False, trajectory_id=second_tid))
    results = [finish(first), finish(second)]
    assert [r[0] for r in results] == [0, 0], results
    if reuse_first:
        assert "reused=true" in results[0][1]
    assert shared_state(site) == before
    record_property(
        "different_trajectories",
        json.dumps(
            dict(
                results=results,
                barrier_participants=2,
                reused_first=reuse_first,
                shared_files_unchanged=len(before),
                source_root=str(site.source),
                output_root=str(site.output),
            )
        ),
    )
    markers = list(site.output.rglob("science_complete.json"))
    assert len(markers) == 2 and markers[0].parent != markers[1].parent


def test_same_trajectory_second_process_is_rejected(
    site, monkeypatch, inline, record_property
):
    initialized(site, monkeypatch)
    entered, release = CTX.Event(), CTX.Event()
    original = launcher.Commands.run

    def wait(self, label, command):
        if label.endswith(".prepare"):
            entered.set()
            assert release.wait(30)
        return original(self, label, command)

    monkeypatch.setattr(launcher.Commands, "run", wait)
    tid = launcher.SELECTIONS[0]
    first = launch(lambda: run_site(site, init=False, trajectory_id=tid))
    try:
        assert entered.wait(30)
        rejected = finish(launch(lambda: run_site(site, init=False, trajectory_id=tid)))
        assert rejected[0] == 1 and "duplicate execution rejected" in rejected[2]
        assert tid in rejected[2]
    finally:
        release.set()
        result = finish(first)
    assert result[0] == 0
    record_property("same_trajectory", json.dumps(dict(first=result, second=rejected)))
    assert len(list(site.output.rglob("attempt_0001"))) == 1
    assert not list(site.output.rglob("attempt_0002"))


def test_failed_a_preserves_completed_b_and_allocates_fresh_attempt(
    site, monkeypatch, inline
):
    initialized(site, monkeypatch)
    a, b = launcher.SELECTIONS[0], launcher.SELECTIONS[3]
    assert run_site(site, init=False, trajectory_id=b) == 0
    root_b = site.output / "production/trajectories" / b
    before = {p: p.read_bytes() for p in root_b.rglob("*") if p.is_file()}
    original = launcher.Commands.run

    def fail(self, label, command):
        if label == f"{a}.run":
            target = Path(command[command.index("--output-root") + 1])
            target.mkdir(parents=True)
            (target / "partial.txt").write_text("preserve incomplete contacts")
            raise ValueError("Synthetic interrupted contacts")
        return original(self, label, command)

    monkeypatch.setattr(launcher.Commands, "run", fail)
    assert run_site(site, init=False, trajectory_id=a) == 1
    partial = next(site.output.rglob("partial.txt"))
    monkeypatch.setattr(launcher.Commands, "run", original)
    assert run_site(site, init=False, trajectory_id=a) == 0
    assert partial.read_text() == "preserve incomplete contacts"
    assert (site.output / "production/trajectories" / a / "attempt_0002").is_dir()
    assert all(p.read_bytes() == data for p, data in before.items())
    assert run_site(site, init=False, trajectory_id=b) == 0
    assert inline[-1][0] == f"{b}.reuse"


@pytest.mark.parametrize("role", launcher.attestation.ROLES)
@pytest.mark.parametrize("damage", ["changed", "missing", "replaced"])
def test_selected_source_guard_precedes_heavy_work(
    site, monkeypatch, role, damage, capsys
):
    initialized(site, monkeypatch)
    tid = launcher.SELECTIONS[0]
    discovery = launcher.discover(site.source, site.runtime, (tid,))
    raw = site.source / discovery["mapping"][tid][role]["path"]
    previous = raw.read_bytes()
    if damage in ("missing", "replaced"):
        raw.unlink()
    if damage != "missing":
        raw.write_bytes(previous if damage == "replaced" else previous + b"changed")
    monkeypatch.setattr(launcher.Commands, "run", lambda *a: pytest.fail("heavy work"))
    assert run_site(site, init=False, trajectory_id=tid) == 1
    assert "source" in capsys.readouterr().err.lower()
    assert not list(site.source.rglob("prepared.dcd"))


def test_selected_worker_does_not_hash_unrelated_dcd_even_during_confirmation(
    site, monkeypatch, inline
):
    initialized(site, monkeypatch)
    selected, unrelated = launcher.SELECTIONS[0], launcher.SELECTIONS[3]
    discovery = launcher.discover(site.source, site.runtime, (unrelated,))
    raw = site.source / discovery["mapping"][unrelated]["trajectory_path"]["path"]
    raw.write_bytes(b"unrelated damaged DCD")
    original = launcher.attestation.capture
    hashed = []

    def capture(source, mapping):
        hashed.extend(mapping)
        assert unrelated not in mapping
        return original(source, mapping)

    monkeypatch.setattr(launcher.attestation, "capture", capture)
    assert run_site(site, init=False, trajectory_id=selected) == 0
    assert hashed and set(hashed) == {selected}
    monkeypatch.setattr(launcher.attestation, "capture", original)
    with pytest.raises(ValueError, match="identity/path changed"):
        launcher.attestation.verify(
            site.output / "production/source_attestation.json",
            authority_inventory=launcher.prep.package_inventory(site.runtime),
        )


@pytest.mark.parametrize("damage", ["manifest", "runtime", "binding", "attestation"])
def test_shared_state_corruption_stops_workers(site, monkeypatch, damage):
    initialized(site, monkeypatch)
    _, out, data = launcher.locations(site.source, site.output, False)
    paths = dict(
        manifest=out / "initialization.json",
        runtime=data / "egor_handoff/handoff_manifest.json",
        binding=data / "source_binding.json",
        attestation=out / "source_attestation.json",
    )
    paths[damage].write_text("{}")
    monkeypatch.setattr(launcher.Commands, "run", lambda *a: pytest.fail("heavy work"))
    assert run_site(site, init=False, trajectory_id=launcher.SELECTIONS[0]) == 1


def test_technical_initialization_is_not_production_authority(site, monkeypatch):
    initialized(site, monkeypatch, technical=True)
    path = site.output / "test_0ss_r1/source_attestation.json"
    assert len(launcher.read(path)["trajectories"]) == 1
    assert run_site(site, init=False, trajectory_id=launcher.SELECTIONS[0]) == 1
    # Even copying the technical shared documents cannot satisfy normal init.
    out = site.output / "production"
    out.mkdir(exist_ok=True)
    (out / "source_attestation.json").write_bytes(path.read_bytes())
    (out / "initialization.json").write_bytes(
        (path.parent / "initialization.json").read_bytes()
    )
    assert run_site(site, init=False, trajectory_id=launcher.SELECTIONS[0]) == 1


@pytest.mark.parametrize("replica", ("r1", "r2", "r3"))
def test_replica_dispatch_uses_trajectory_locks(site, monkeypatch, replica):
    initialized(site, monkeypatch)
    tid = f"namd_egor_wt_0ss_{replica}"
    lock = site.output / "production/trajectories" / tid / ".trajectory.lock"
    with launcher.exclusive_lock(lock, "test"):
        assert run_site(site, init=False, replica=replica) == 1


def test_child_keeps_lock_after_launcher_process_exits(tmp_path):
    lock_path = tmp_path / "trajectory.lock"
    child_ready, release = tmp_path / "child.ready", tmp_path / "release"
    child = (
        "from pathlib import Path\nimport time\n"
        f"Path({str(child_ready)!r}).touch()\n"
        f"while not Path({str(release)!r}).exists():\n    time.sleep(0.02)\n"
        "print('{}')\n"
    )

    def parent():
        with launcher.exclusive_lock(lock_path, "test") as fd:
            commands = launcher.Commands(tmp_path, tmp_path)
            commands.lock_fd = fd
            commands.run("orphan", [sys.executable, "-c", child])

    process = CTX.Process(target=parent)
    process.start()
    try:
        deadline = time.monotonic() + 10
        while not child_ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert child_ready.exists()
        process.terminate()
        process.join(timeout=10)
        assert process.exitcode != 0
        with pytest.raises(ValueError, match="still active"):
            with launcher.exclusive_lock(lock_path, "still active"):
                pytest.fail("inherited lock lost")
    finally:
        release.touch()
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
    deadline = time.monotonic() + 10
    while True:
        try:
            with launcher.exclusive_lock(lock_path, "still active"):
                break
        except ValueError:
            assert time.monotonic() < deadline
            time.sleep(0.02)


def test_wrapper_arguments_are_thin_and_preserve_spaces(tmp_path):
    fake = tmp_path / "python"
    fake.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ["PATH"])
    cases = (
        ("init_egor_production.sh", [], ["--init", "data path", "out path"]),
        ("run_egor_all.sh", [], ["--all", "data path", "out path"]),
        (
            "run_egor_one.sh",
            [launcher.SELECTIONS[0]],
            ["data path", "out path", "--trajectory-id", launcher.SELECTIONS[0]],
        ),
        ("run_egor_replica.sh", ["r2"], ["data path", "out path", "--replica", "r2"]),
    )
    for script, extra, expected in cases:
        result = subprocess.run(
            [str(launcher.REPO / script), "data path", "out path", *extra],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stdout.splitlines() == [
            str(launcher.REPO / "tools/run_egor_all.py"),
            *expected,
        ]


def test_selected_confirmation_subcommand_dispatch(site, monkeypatch, inline):
    initialized(site, monkeypatch)
    original = launcher.Commands.run
    confirmation = []

    def run(self, label, command):
        if label.endswith(".confirm"):
            assert command[2] == "--confirm-selected"
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                assert launcher.main(command[2:]) == 0
            result = json.loads(stream.getvalue())
            confirmation.append(result)
            return result
        return original(self, label, command)

    monkeypatch.setattr(launcher.Commands, "run", run)
    assert run_site(site, init=False, trajectory_id=launcher.SELECTIONS[0]) == 0
    assert len(confirmation) == 1
    assert confirmation[0]["status"] == "binding_materialized"
    assert [label.rsplit(".", 1)[1] for label, _ in inline] == [
        "prepare",
        "validate",
        "run",
    ]
