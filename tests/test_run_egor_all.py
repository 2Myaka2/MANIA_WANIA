"""Batch UX guards with real tiny preparation inputs and isolated contact dispatch."""

import contextlib
import importlib.util
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_production_input_preparation import REPO, build_bundle, prep, seal, write

SPEC = importlib.util.spec_from_file_location(
    "run_egor_all", REPO / "tools/run_egor_all.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.fixture
def site(tmp_path):
    bundle = build_bundle(tmp_path, source_prefix="egor/raw")
    return SimpleNamespace(
        bundle=bundle,
        source=bundle.root / "egor",
        runtime=bundle.package,
        output=tmp_path / "results",
        data=bundle.root / "egor/.bound",
    )


def bind(site, selections=launcher.SELECTIONS):
    discovery = launcher.discover(site.source, site.runtime, selections)
    snapshot = launcher.bind_sources(site.source, site.data, site.runtime, discovery)
    return discovery, snapshot


@pytest.mark.parametrize("tid", launcher.SELECTIONS)
def test_all_nine_exact_source_selections_and_own_authority(site, tid):
    discovery, snapshot = bind(site, (tid,))
    selected = prep.select_authority(site.data, site.data / "egor_handoff", tid)
    system_number = int(tid.split("_")[3][0])
    assert selected["selected"].trajectory_id == tid
    assert selected["template"]["expected_atom_count"] == 4 + system_number
    assert selected["draft"]["catalog_row"]["system_id"] == tid.rsplit("_", 1)[0]
    for name in discovery["paths"]:
        assert (site.data / name).samefile(launcher.original_path(site.source, name))
    assert len(snapshot["files"]) >= 6
    assert prep.package_inventory(site.runtime) == prep.package_inventory(
        site.data / "egor_handoff"
    )


def test_missing_dcd_reports_trajectory_and_exact_identity(site):
    tid = launcher.SELECTIONS[4]
    row = next(
        r
        for r in launcher.read(site.runtime / "authority/source_inventory.json")
        if r["trajectory_id"] == tid
    )
    raw = launcher.original_path(site.source, row["expected_dcd_path"])
    raw.unlink()
    with pytest.raises(ValueError) as error:
        launcher.discover(site.source, site.runtime, launcher.SELECTIONS)
    assert all(
        s in str(error.value)
        for s in (tid, "missing DCD", str(raw), row["declared_dcd_filename"])
    )
    assert not site.data.exists()


@pytest.mark.parametrize("damage", ["psf", "system"])
def test_wrong_psf_or_system_stops_before_preparation(
    site, monkeypatch, damage, capsys
):
    if damage == "psf":
        next(site.source.rglob("own.psf")).write_text("wrong system PSF")
    else:
        path = (
            site.runtime
            / f"templates/{launcher.SELECTIONS[0]}/input_binding.template.json"
        )
        obj = launcher.read(path)
        foreign = launcher.read(
            site.runtime / "templates/namd_egor_wt_2ss_r1/input_binding.template.json"
        )
        obj["payload"]["files"]["partner_metadata"] = foreign["payload"]["files"][
            "partner_metadata"
        ]
        write(path, obj)
        seal(site.runtime)
    monkeypatch.setattr(
        launcher.Commands, "run", lambda *args: pytest.fail("heavy work")
    )
    assert (
        launcher.batch(site.source, site.output, runtime=site.runtime, minimum=1) == 1
    )
    assert "authority" in capsys.readouterr().err.lower() or damage == "system"
    assert not list(site.source.rglob("prepared.dcd"))


@pytest.mark.parametrize("kind", ["output_inside", "input_inside", "escape", "space"])
def test_containment_separation_and_disk_before_heavy_work(site, monkeypatch, kind):
    if kind in {"output_inside", "input_inside"}:
        out = site.source / "results" if kind == "output_inside" else site.source.parent
        with pytest.raises(ValueError, match="disjoint"):
            launcher.batch(site.source, out, runtime=site.runtime, minimum=1)
    elif kind == "escape":
        path = next(site.source.rglob("explicit_delivery.dcd"))
        outside = site.output / "outside.dcd"
        outside.parent.mkdir()
        path.rename(outside)
        path.symlink_to(outside)
        assert (
            launcher.batch(site.source, site.output, runtime=site.runtime, minimum=1)
            == 1
        )
    else:
        monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
        assert (
            launcher.batch(site.source, site.output, runtime=site.runtime, minimum=1)
            == 1
        )
    assert not list(site.source.rglob("prepared.dcd"))


@pytest.fixture
def inline(monkeypatch):
    """Real prepare/confirm/public preflight, contact dispatch stubbed explicitly."""
    import mania.production_run as production

    calls = []

    def run(self, label, command):
        calls.append((label, command))
        options = {
            command[i][2:].replace("-", "_"): command[i + 1]
            for i in range(len(command) - 1)
            if command[i].startswith("--") and not command[i + 1].startswith("--")
        }
        if command[1].endswith("prepare_production_inputs.py"):
            common = dict(
                data_root=Path(options["data_root"]),
                result_root=Path(options["result_root"]),
                authority_package=Path(options["authority_package"]),
                trajectory_id=options["trajectory_id"],
                min_free_bytes=1,
            )
            if command[2] == "prepare":
                return prep.prepare(**common)
            return prep.confirm(
                **common,
                report_sha256=options["report_sha256"],
                source_attestation=Path(options["source_attestation"]),
                production_output_root=Path(options["production_output_root"]),
            )
        monkeypatch.setenv("MANIA_DATA_ROOT", str(self.data))
        kwargs = dict(
            catalog_path=Path(options["catalog"]),
            trajectory_id=options["trajectory_id"],
            output_root=Path(options["output_root"]),
            input_binding=Path(options["input_binding"]),
            min_free_bytes=1,
            resume="--resume" in command,
        )
        if command[4] == "validate":
            return production.preflight_trajectory(**kwargs).to_dict()
        # No synthetic result from this stub is used as real scientific evidence.
        target = kwargs["output_root"] / "trajectories" / kwargs["trajectory_id"]
        target.mkdir(parents=True, exist_ok=True)
        marker = target / "science_complete.json"
        if not marker.exists():
            marker.write_text('{"synthetic_dispatch_test_only": true}\n')
        return dict(status="science_complete", reused=kwargs["resume"])

    monkeypatch.setattr(launcher.Commands, "run", run)
    return calls


def answer(monkeypatch, values):
    replies = iter(values)
    monkeypatch.setattr("builtins.input", lambda _: next(replies))


def run_site(site):
    return launcher.batch(site.source, site.output, runtime=site.runtime, minimum=1)


@pytest.mark.parametrize("reply", ["N", "", "y"])
def test_one_source_review_before_nine_preparations(
    site, inline, monkeypatch, reply, capsys
):
    prompts = []
    replies = iter(
        ["Synthetic named reviewer", "Reviewed synthetic sources only", reply]
    )

    def respond(prompt):
        assert inline == []  # No preparation/production before explicit approval.
        prompts.append(prompt)
        return next(replies)

    monkeypatch.setattr("builtins.input", respond)
    assert run_site(site) == (0 if reply == "y" else 1)
    labels = [label.split(".")[-1] for label, _ in inline]
    if reply == "y":
        assert (
            labels == ["prepare"] * 9 + ["confirm"] * 9 + ["validate"] * 9 + ["run"] * 9
        )
    else:
        assert labels == []
        assert not list(site.source.rglob("prepared.dcd"))
    assert prompts == [
        "Reviewer name (required): ",
        "Review note (required): ",
        "Approve these 9 source/run mappings? [y/N]: ",
    ]
    captured = capsys.readouterr()
    assert all(tid in captured.out for tid in launcher.SELECTIONS)
    assert len([line for line in captured.out.splitlines() if " → " in line]) == 9
    assert launcher.attestation.STATEMENT in captured.out
    assert "SHA256" not in "".join(prompts)


def test_preparation_failure_preserves_evidence_and_stops_batch(
    site, inline, monkeypatch, capsys
):
    answer(monkeypatch, ["Synthetic reviewer", "Sources only", "y"])
    tid = launcher.SELECTIONS[1]
    path = site.source / "raw/namd_egor_wt_0ss/2/explicit_delivery.dcd"
    # Wrong replica header has a valid DCD with the same atom population.
    shutil.copyfile(site.source / "raw/namd_egor_wt_0ss/1/explicit_delivery.dcd", path)
    assert run_site(site) == 1
    assert [label for label, _ in inline] == [
        f"{launcher.SELECTIONS[0]}.prepare",
        f"{tid}.prepare",
    ]
    assert "header/config/log linkage" in capsys.readouterr().err
    operations = [launcher.read(p) for p in site.source.rglob("operation.json")]
    assert {o["status"] for o in operations} == {"completed", "failed"}
    assert not list(site.source.rglob("production_input_binding.json"))
    assert (site.output / "production/source_attestation.json").is_file()


@pytest.mark.parametrize("replacement", [False, True])
def test_input_changed_during_source_review_cannot_be_approved(
    site, inline, monkeypatch, replacement
):
    calls = 0

    def reply(prompt):
        nonlocal calls
        calls += 1
        if calls == 3:
            raw = site.source / "raw/namd_egor_wt_0ss/1/explicit_delivery.dcd"
            if replacement:
                raw.unlink()
            raw.write_bytes(b"changed since the displayed preparation")
            return "y"
        return "Synthetic review only"

    monkeypatch.setattr("builtins.input", reply)
    assert run_site(site) == 1
    assert len(inline) == 0
    assert not list(site.source.rglob("production_input_binding.json"))


def test_completed_reused_and_later_incomplete_attempt_preserved(
    site, inline, monkeypatch, capsys
):
    original_run = launcher.Commands.run
    failed_tid = launcher.SELECTIONS[2]

    def fail_once(self, label, command):
        if label == f"{failed_tid}.run":
            target = Path(command[command.index("--output-root") + 1])
            target.mkdir(parents=True)
            (target / "partial-contact.txt").write_text("preserve these bytes")
            raise ValueError("Interrupted synthetic contact run")
        return original_run(self, label, command)

    monkeypatch.setattr(launcher.Commands, "run", fail_once)
    answer(monkeypatch, ["Synthetic reviewer", "Synthetic note", "y"])
    assert run_site(site) == 1
    assert "2/9 completed" in capsys.readouterr().err
    partial = next(site.output.rglob("partial-contact.txt"))
    before = {p: p.read_bytes() for p in site.output.rglob("science_complete.json")}
    monkeypatch.setattr(launcher.Commands, "run", original_run)
    inline.clear()
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("second prompt"))
    assert run_site(site) == 0
    assert partial.read_text() == "preserve these bytes"
    assert all(p.read_bytes() == value for p, value in before.items())
    reuse = [(label, cmd) for label, cmd in inline if label.endswith(".reuse")]
    assert len(reuse) == 2 and all("--resume" in cmd for _, cmd in reuse)
    new_run = next(cmd for label, cmd in inline if label == f"{failed_tid}.run")
    assert "--resume" not in new_run
    assert "attempt_0002" in new_run[new_run.index("--output-root") + 1]


def test_declined_source_review_requires_new_explicit_approval(
    site, inline, monkeypatch
):
    answer(monkeypatch, ["Synthetic reviewer", "Not approved", "N"])
    assert run_site(site) == 1
    inline.clear()
    answer(monkeypatch, ["Synthetic reviewer", "Reviewed all unchanged reports", "y"])
    assert run_site(site) == 0
    assert sum(label.endswith(".prepare") for label, _ in inline) == 9
    assert sum(label.endswith(".confirm") for label, _ in inline) == 9


def test_no_default_reviewer(site, inline, monkeypatch):
    answer(monkeypatch, ["", "Synthetic note", "y"])
    assert run_site(site) == 1
    assert len(inline) == 0


def test_completed_reuse_dispatches_actual_strict_validator(tmp_path, monkeypatch):
    from test_production_run import install_runtime, make_case, run_case

    import mania.cli as cli

    case = make_case(tmp_path, monkeypatch)
    install_runtime(monkeypatch)
    result = run_case(case)
    before = {
        p: p.read_bytes() for p in Path(result["output"]).rglob("*") if p.is_file()
    }
    catalog = case.data_root / "egor_handoff/catalog"
    catalog.mkdir(parents=True)
    for name in ("dataset.yaml", "trajectories.csv"):
        shutil.copyfile(case.catalog.parent / name, catalog / name)
    log = tmp_path / "commands"
    log.mkdir()
    runner = launcher.Commands(log, case.data_root)
    plan = dict(
        tid=case.selected.trajectory_id,
        production=case.output,
        binding=case.binding,
        reuse=True,
    )
    command = launcher.production_command(plan, case.data_root, "run", 1, False)

    def call(command, *, env, stdout, stderr):
        monkeypatch.setattr(sys, "argv", command[2:])
        monkeypatch.setenv("MANIA_DATA_ROOT", env["MANIA_DATA_ROOT"])
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                cli.main()
            except SystemExit as exc:
                return exc.code
        return 0

    monkeypatch.setattr(launcher.subprocess, "call", call)
    monkeypatch.setattr(
        cli,
        "run_production_preprocessing",
        lambda *args, **kwargs: pytest.fail("geometry on reuse"),
    )
    assert runner.run("reuse", command)["reused"] is True
    assert all(p.read_bytes() == content for p, content in before.items())
    next(p for p in before if p.name == "run_provenance.json").write_text("{}")
    with pytest.raises(ValueError, match="failed"):
        runner.run("corrupt", command)
    assert launcher.read(log / "corrupt.command.json")["exit_code"] != 0


def test_runtime_is_self_contained_and_catalog_unchanged():
    inventory = prep.package_inventory(launcher.RUNTIME)
    assert len(inventory) == 57
    assert max((launcher.RUNTIME / p).stat().st_size for p in inventory) < 400_000
    assert not any(
        Path(p).suffix in {".dcd", ".psf", ".out", ".conf", ".xsc", ".zip"}
        for p in inventory
    )
    for name in ("dataset.yaml", "trajectories.csv"):
        assert (launcher.RUNTIME / "catalog" / name).read_bytes() == (
            REPO / "production/dataset_v1" / name
        ).read_bytes()
    # Historical provenance remains intact, but is not opened as a runtime input.
    text = (
        launcher.RUNTIME / "controls/namd/egor_wt_1ss/topology_authority.json"
    ).read_text()
    assert "local_md/" in text
    assert "/home/" not in "".join(
        (launcher.RUNTIME / p).read_text() for p in inventory
    )
    source = (REPO / "tools/run_egor_all.py").read_text()
    assert "local_md/" not in source and "zipfile" not in source


def test_normal_cli_has_only_two_required_arguments(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(
        launcher, "batch", lambda *a, **kw: captured.append((a, kw)) or 0
    )
    assert launcher.main([str(tmp_path / "Egor"), str(tmp_path / "results")]) == 0
    assert captured[0][1] == {"technical": False}
    assert (
        launcher.main(
            [str(tmp_path / "Egor"), str(tmp_path / "test"), "--TEST-0ss-r1-5-8ns"]
        )
        == 0
    )
    assert captured[1][1] == {"technical": True}


def test_wrong_installed_checkout_is_rejected(monkeypatch, tmp_path):
    import mania

    monkeypatch.setattr(mania, "__file__", str(tmp_path / "foreign/mania/__init__.py"))
    with pytest.raises(ValueError, match="Install this checkout"):
        launcher.environment(REPO)
