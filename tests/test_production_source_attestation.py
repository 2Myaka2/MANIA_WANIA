"""Synthetic exact-source approvals and unattended batch continuation."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from test_production_input_preparation import build_bundle, prep, write
from test_run_egor_all import answer, launcher, run_site
from test_run_egor_all import inline as inline  # noqa: F401

attestation = launcher.attestation


@pytest.fixture
def site(tmp_path):
    bundle = build_bundle(tmp_path, source_prefix="egor/raw")
    return SimpleNamespace(
        bundle=bundle,
        source=bundle.root / "egor",
        runtime=bundle.package,
        output=tmp_path / "results",
    )


def approve_sources(site):
    discovery = launcher.discover(site.source, site.runtime, launcher.SELECTIONS)
    path = site.output / "production/source_attestation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    attestation.save(
        path,
        source=site.source,
        trajectories=attestation.capture(site.source, discovery["mapping"]),
        reviewer="Synthetic reviewer",
        review_note="Synthetic source correspondence only",
        repository_head="a" * 40,
        authority_inventory=prep.package_inventory(site.runtime),
    )
    return path, discovery


def test_exact_nine_identities_protected_save_and_scope(site):
    path, discovery = approve_sources(site)
    value = attestation.verify(
        path,
        authority_inventory=prep.package_inventory(site.runtime),
        source=site.source,
        mapping=discovery["mapping"],
    )
    assert value["scope"] == "source_run_correspondence_only"
    assert value["statement"] == attestation.STATEMENT
    assert {r["trajectory_id"] for r in value["trajectories"]} == set(
        launcher.SELECTIONS
    )
    assert len(value["trajectories"]) == 9
    for row in value["trajectories"]:
        assert set(row["sources"]) == set(attestation.ROLES)
        for item in row["sources"].values():
            assert {
                k: item[k] for k in ("path", "size_bytes", "sha256")
            } == prep.record(
                site.source / item["path"],
                site.source,
            )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="protected"):
        approve_sources(site)
    assert path.read_bytes() == before


@pytest.mark.parametrize("role", attestation.ROLES)
@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_every_source_change_stops_without_prompt_or_preparation(
    site,
    monkeypatch,
    capsys,
    role,
    damage,
):
    path, discovery = approve_sources(site)
    saved = path.read_bytes()
    tid = launcher.SELECTIONS[4]
    raw = site.source / discovery["mapping"][tid][role]["path"]
    if damage == "missing":
        raw.unlink()
    else:
        raw.write_bytes(raw.read_bytes() + b"changed")
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("silent reapproval"))
    monkeypatch.setattr(launcher.Commands, "run", lambda *a: pytest.fail("heavy work"))
    assert run_site(site) == 1
    error = capsys.readouterr().err
    assert tid in error
    assert "source approval required" in error
    assert path.read_bytes() == saved
    assert not list(site.source.rglob("prepared.dcd"))


@pytest.mark.parametrize(
    "damage",
    [
        "json",
        "reviewer",
        "schema",
        "mapping",
        "missing_role",
        "duplicate",
        "authority",
    ],
)
def test_corrupted_or_wrong_attestation_stops(site, monkeypatch, damage):
    path, _ = approve_sources(site)
    value = launcher.read(path)
    if damage == "json":
        path.write_text("{broken")
    else:
        if damage == "reviewer":
            value["reviewer"] = "Different reviewer"
        elif damage == "schema":
            value["schema_version"] = "unknown"
        elif damage == "mapping":
            value["trajectories"][0]["sources"]["trajectory_path"]["binding_path"] = (
                value["trajectories"][1]["sources"]["trajectory_path"]["binding_path"]
            )
        elif damage == "missing_role":
            del value["trajectories"][0]["sources"]["box_path"]
        elif damage == "duplicate":
            value["trajectories"][1] = value["trajectories"][0]
        else:
            value["authority_inventory"] = {}
        # A fresh checksum cannot make a wrong mapping or schema authoritative.
        if damage != "reviewer":
            value.pop("payload_sha256")
            value["payload_sha256"] = attestation.digest(value)
        write(path, value)
    saved = path.read_bytes()
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("prompt"))
    monkeypatch.setattr(launcher.Commands, "run", lambda *a: pytest.fail("heavy work"))
    assert run_site(site) == 1
    assert path.read_bytes() == saved


def test_auto_binding_scope_and_identical_second_run(site, inline, monkeypatch):
    answer(monkeypatch, ["Synthetic reviewer", "Sources only", "y"])
    assert run_site(site) == 0
    path = site.output / "production/source_attestation.json"
    before = path.read_bytes()
    confirmations = list(site.source.rglob("confirmation.json"))
    assert len(confirmations) == 9
    for file in confirmations:
        confirmation = launcher.read(file)
        assert confirmation["human_approval_scope"] == "source_run_correspondence_only"
        assert confirmation["final_qc_decision"] is None
        assert confirmation["source_attestation"] == launcher.read(path)
        report = launcher.read(file.parent.parent / "report.json")
        assert report["human_review"] is None
        binding = launcher.read(file.parent / "production_input_binding.json")
        note = binding["prepared_lineage"]["note"]
        assert "No human review of PBC checks, prepared frames, contacts or QC" in note
        assert "Explicit external preparation/atom-order review" not in note
        assert binding["prepared_lineage"]["reviewer"] == "Synthetic reviewer"
    inline.clear()
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("second prompt"))
    assert run_site(site) == 0
    assert path.read_bytes() == before
    assert len(inline) == 9 and all(label.endswith(".reuse") for label, _ in inline)


def test_completed_preparation_continues_unattended_after_interruption(
    site,
    inline,
    monkeypatch,
):
    original = launcher.Commands.run

    def interrupt(self, label, command):
        if label == f"{launcher.SELECTIONS[1]}.prepare":
            raise ValueError("Synthetic interruption before second preparation")
        return original(self, label, command)

    answer(monkeypatch, ["Synthetic reviewer", "Sources only", "y"])
    monkeypatch.setattr(launcher.Commands, "run", interrupt)
    assert run_site(site) == 1
    completed = next(site.source.rglob("complete.json"))
    before = completed.read_bytes()
    inline.clear()
    monkeypatch.setattr(launcher.Commands, "run", original)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("second prompt"))
    assert run_site(site) == 0
    assert completed.read_bytes() == before
    assert sum(label.endswith(".prepare") for label, _ in inline) == 8
    assert sum(label.endswith(".confirm") for label, _ in inline) == 9


def test_source_changed_after_preparation_stops_before_binding(
    site,
    inline,
    monkeypatch,
):
    original = launcher.Commands.run

    def change(self, label, command):
        result = original(self, label, command)
        if label == f"{launcher.SELECTIONS[-1]}.prepare":
            path = site.source / "raw/namd_egor_wt_0ss/1/explicit_delivery.dcd"
            path.write_bytes(path.read_bytes() + b"changed after preparation")
        return result

    answer(monkeypatch, ["Synthetic reviewer", "Sources only", "y"])
    monkeypatch.setattr(launcher.Commands, "run", change)
    assert run_site(site) == 1
    assert len(inline) == 9
    assert not list(site.source.rglob("production_input_binding.json"))
    assert (site.output / "production/source_attestation.json").is_file()


def test_report_mapping_must_match_attested_source(site):
    path, discovery = approve_sources(site)
    document = launcher.read(path)
    tid = launcher.SELECTIONS[0]
    report = dict(
        trajectory_id=tid,
        inputs={
            role: dict(
                path=item["binding_path"],
                size_bytes=item["size_bytes"],
                sha256=item["sha256"],
            )
            for role, item in document["trajectories"][0]["sources"].items()
        },
    )
    # Even a correct source digest cannot stand in for the exact approved path.
    report["inputs"]["trajectory_path"]["path"] = discovery["mapping"][
        launcher.SELECTIONS[1]
    ]["trajectory_path"]["binding_path"]
    with pytest.raises(ValueError, match="attested source/report mapping differs"):
        attestation.match_report(document, report, site.bundle.root)


@pytest.mark.parametrize("damage", ["failed_check", "failures", "control", "mapping"])
def test_automatic_confirmation_rejects_bad_evidence(site, monkeypatch, inline, damage):
    original = launcher.Commands.run

    def intercept(self, label, command):
        if label.endswith(".confirm"):
            result = Path(command[command.index("--result-root") + 1])
            data = Path(command[command.index("--data-root") + 1])
            report_path = result / "report.json"
            report = launcher.read(report_path)
            if damage in {"failed_check", "failures", "mapping"}:
                if damage == "failed_check":
                    report["checks"]["bond_representation"] = False
                elif damage == "failures":
                    report["failures"] = ["Synthetic automatic failure"]
                else:
                    report["inputs"]["trajectory_path"] = report["inputs"][
                        "topology_path"
                    ]
                write(report_path, report)
                complete = launcher.read(result / "complete.json")
                complete["report.json"] = prep.record(report_path, data)
                write(result / "complete.json", complete)
                command[command.index("--report-sha256") + 1] = complete["report.json"][
                    "sha256"
                ]
            else:
                (result / "prepared_time.json").write_text("{}")
        return original(self, label, command)

    answer(monkeypatch, ["Synthetic reviewer", "Sources only", "y"])
    monkeypatch.setattr(launcher.Commands, "run", intercept)
    assert run_site(site) == 1
    assert not list(site.source.rglob("production_input_binding.json"))
    assert not any(label.endswith(".run") for label, _ in inline)
    assert (site.output / "production/source_attestation.json").is_file()
