"""Source-only launcher behavior; all inputs are tiny synthetic files."""

import ast
import importlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_gromacs_wt_runtime import make_site

launcher = importlib.import_module("run_gromacs_wt_all")


@pytest.fixture
def site(tmp_path):
    return make_site(tmp_path)


def no_prompt(_):
    pytest.fail("Unexpected prompt")


def approve(site, answer="y"):
    prompts = []
    answers = iter(["Reviewer", "These source sets correspond", answer])

    def prompt(text):
        prompts.append(text)
        return next(answers)

    code = launcher.batch(site.source, site.output, runtime=site.runtime, prompt=prompt)
    return code, prompts


def test_approval_and_identical_rerun_without_prompt(site, capsys):
    code, prompts = approve(site)
    assert code == 3
    assert len(prompts) == 3
    assert not any("hash" in p.lower() or "sha" in p.lower() for p in prompts)
    path = site.output / "gromacs_source_attestation.json"
    before = path.read_bytes()
    assert json.loads(before)["reviewer"] == "Reviewer"
    assert (
        launcher.batch(site.source, site.output, runtime=site.runtime, prompt=no_prompt)
        == 3
    )
    assert path.read_bytes() == before
    output = capsys.readouterr().out
    assert '"coordinate_backend_status": "pending_real_xtc_validation"' in output
    assert '"production_launched": false' in output
    assert "Existing source approval verified; no prompt" in output


@pytest.mark.parametrize("answer", ["N", "", "no"])
def test_decline_has_no_attestation(site, answer):
    assert approve(site, answer)[0] == 1
    assert not site.output.exists()


@pytest.mark.parametrize("role", ["xtc", "tpr", "mdp", "log"])
def test_changed_source_cannot_reprompt_or_continue(site, role):
    assert approve(site)[0] == 3
    row = site.authority.trajectories[0]
    path = (
        row.expected_xtc_path
        if role == "xtc"
        else row.logs[0].path
        if role == "log"
        else getattr(row, role).path
    )
    (site.source / path).write_bytes(b"changed source")
    assert (
        launcher.batch(site.source, site.output, runtime=site.runtime, prompt=no_prompt)
        == 1
    )


def test_missing_xtc_fails_before_approval(site, capsys):
    row = site.authority.trajectories[0]
    (site.source / row.expected_xtc_path).unlink()
    assert (
        launcher.batch(site.source, site.output, runtime=site.runtime, prompt=no_prompt)
        == 1
    )
    output = capsys.readouterr().err
    assert row.trajectory_id in output and row.expected_xtc_path in output
    assert not site.output.exists()


@pytest.mark.parametrize("representative", [False, True])
def test_preflight_never_reads_xtc_or_launches_commands(
    site, monkeypatch, representative
):
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix != ".xtc", "Preflight must never read XTC bytes"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(
        launcher.subprocess,
        "check_output",
        lambda *a, **k: pytest.fail("Unexpected command"),
    )
    assert (
        launcher.batch(
            site.source,
            site.output,
            runtime=site.runtime,
            representative=representative,
            preflight_only=True,
            prompt=no_prompt,
        )
        == 3
    )
    assert not site.output.exists()


def test_representative_does_not_require_other_xtcs(site, capsys):
    for row in site.authority.trajectories:
        if row.trajectory_id != launcher.REPRESENTATIVE:
            (site.source / row.expected_xtc_path).unlink()
    assert (
        launcher.batch(
            site.source,
            site.output,
            runtime=site.runtime,
            representative=True,
            prompt=no_prompt,
        )
        == 3
    )
    out = capsys.readouterr().out
    assert launcher.REPRESENTATIVE in out
    assert "gromacs_wt_norm_r1" not in out


@pytest.mark.parametrize(
    "kind",
    [
        "output_inside",
        "source_inside",
        "runtime",
        "repository",
        "symlink",
        "nonempty",
        "low_space",
        "readonly_source",
    ],
)
def test_root_and_storage_protection(site, tmp_path, monkeypatch, kind):
    output = site.output
    if kind == "output_inside":
        output = site.source / "results"
    elif kind == "source_inside":
        output = site.source.parent
    elif kind == "runtime":
        output = site.runtime / "results"
    elif kind == "repository":
        output = launcher.REPO / "tools/results"
    elif kind == "symlink":
        output.mkdir()
        link = tmp_path / "link"
        link.symlink_to(output, target_is_directory=True)
        output = link
    elif kind == "nonempty":
        output.mkdir()
        (output / "precious.txt").write_text("preserve")
    elif kind == "low_space":
        monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    else:
        monkeypatch.setattr(launcher.os, "access", lambda *a: False)
    assert (
        launcher.batch(site.source, output, runtime=site.runtime, prompt=no_prompt) == 1
    )
    assert not (output / "gromacs_source_attestation.json").exists()


def test_changed_runtime_invalidates_approval(site):
    assert approve(site)[0] == 3
    (site.runtime / "new-review.txt").write_text("authority amended")
    assert (
        launcher.batch(site.source, site.output, runtime=site.runtime, prompt=no_prompt)
        == 1
    )


def test_python_and_storage_scope(site, monkeypatch):
    env = launcher.environment(site.source, site.output, launcher.CHECKPOINT_BYTES)
    assert env["production_storage_sufficiency"] == "NOT_MEASURED"
    assert env["prepared_storage_format"] == "OPEN"
    assert "Google Drive" in env["warnings"][0]
    monkeypatch.setattr(launcher.sys, "version_info", (3, 10))
    with pytest.raises(ValueError, match="3.11"):
        launcher.environment(site.source, site.output, launcher.CHECKPOINT_BYTES)


def test_checkpoint_only_subprocess_is_git(site, monkeypatch):
    commands = []
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda *a, **k: pytest.fail("Production command forbidden"),
    )
    # Supply a synthetic HEAD without starting a process.
    monkeypatch.setattr(
        launcher.subprocess,
        "check_output",
        lambda args, **kw: commands.append(args) or "a" * 40,
    )
    assert approve(site)[0] == 3
    assert commands == [["git", "rev-parse", "HEAD"]]
    assert [p.name for p in site.output.iterdir()] == [
        "gromacs_source_attestation.json"
    ]
    tree = ast.parse(Path(launcher.__file__).read_text())
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(name.startswith("mania") for name in imports)
