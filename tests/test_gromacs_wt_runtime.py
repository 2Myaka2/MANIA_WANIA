"""Small synthetic sources only; never access the local Ramila delivery."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import gromacs_wt_runtime as runtime


def make_site(tmp_path):
    source = tmp_path / "WT"
    package = tmp_path / "runtime"
    package.mkdir()
    authority = runtime.load_authority().model_dump()
    for row in authority["trajectories"]:
        prefix = f"{row['condition']}/replica {row['replica']}"
        # Same exact basename in all six folders deliberately tests collisions.
        for role, name in (("tpr", "run.tpr"), ("mdp", "production_segment.mdp")):
            path = source / prefix / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{row['trajectory_id']} {role}")
            row[role] = runtime.identity(source, f"{prefix}/{name}").model_dump()
        row["logs"] = []
        for name in ("run.log", "run.part0002.log"):
            (source / prefix / name).write_text(f"{row['trajectory_id']} {name}")
            row["logs"].append(
                runtime.identity(source, f"{prefix}/{name}").model_dump()
            )
        row["expected_xtc_path"] = f"{prefix}/delivery.xtc"
        (source / row["expected_xtc_path"]).write_bytes(b"synthetic XTC identity only")
    (package / "authority.json").write_text(json.dumps(authority))
    return SimpleNamespace(
        source=source,
        runtime=package,
        output=tmp_path / "results",
        authority=runtime.load_authority(package),
    )


@pytest.fixture
def site(tmp_path):
    return make_site(tmp_path)


def test_exact_six_separated_scoped_paths(site):
    rows = runtime.discover(site.source, site.authority)
    assert tuple(r.trajectory_id for r in rows) == runtime.SELECTIONS
    assert [r.condition for r in rows] == ["NORM"] * 3 + ["TUMOR"] * 3
    assert [r.replica for r in rows] == [1, 2, 3] * 2
    assert len({r.tpr.sha256 for r in rows}) == 6
    assert len({r.tpr.path for r in rows}) == 6
    assert all(
        [Path(i.path).name for i in r.logs] == ["run.log", "run.part0002.log"]
        for r in rows
    )


@pytest.mark.parametrize("role", ["tpr", "mdp", "logs", "xtc"])
@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_missing_or_wrong_sources(site, role, damage):
    row = site.authority.trajectories[0]
    name = (
        row.expected_xtc_path
        if role == "xtc"
        else row.logs[0].path
        if role == "logs"
        else getattr(row, role).path
    )
    path = site.source / name
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed")
    if role == "xtc" and damage == "changed":
        # Discovery never opens/validates XTC bytes; approval identity does.
        runtime.discover(site.source, site.authority)
    else:
        with pytest.raises(ValueError, match=row.trajectory_id):
            runtime.discover(site.source, site.authority)


def test_all_missing_xtcs_reported_before_any_xtc_read(site, monkeypatch):
    for r in site.authority.trajectories:
        (site.source / r.expected_xtc_path).unlink()
    original = Path.open

    def guard(path, *args, **kwargs):
        assert path.suffix != ".xtc"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    with pytest.raises(ValueError) as error:
        runtime.discover(site.source, site.authority)
    for row in site.authority.trajectories:
        assert row.trajectory_id in str(error.value)
        assert row.expected_xtc_path in str(error.value)


@pytest.mark.parametrize("selections", [(), (runtime.SELECTIONS[0],) * 2, ("t330m",)])
def test_bad_selections_rejected(site, selections):
    with pytest.raises(ValueError):
        runtime.discover(site.source, site.authority, selections)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "x/../y", "x//y", "x\\y"])
def test_unsafe_paths(name):
    with pytest.raises(ValueError):
        runtime.relative_path(name)


def test_symlink_source_rejected(site, tmp_path):
    path = site.source / site.authority.trajectories[0].tpr.path
    outside = tmp_path / "external.tpr"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="redirected"):
        runtime.discover(site.source, site.authority)


def test_authority_requires_exact_six_and_correct_replica(site):
    raw = site.authority.model_dump()
    raw["trajectories"].pop()
    with pytest.raises(ValueError, match="exactly six"):
        runtime.Authority.model_validate(raw)
    raw = site.authority.model_dump()
    raw["trajectories"][0]["tpr"]["path"] = "TUMOR/replica 1/run.tpr"
    with pytest.raises(ValueError, match="directory"):
        runtime.Authority.model_validate(raw)


def test_unknown_xtc_is_fail_closed(site):
    site.authority.trajectories[0].expected_xtc_path = None
    with pytest.raises(ValueError, match="UNRESOLVED"):
        runtime.discover(site.source, site.authority)
    assert len(runtime.discover(site.source, site.authority, require_xtc=False)) == 6


def test_tracked_authority_retains_five_discrepancies():
    authority = runtime.load_authority()
    assert sum(bool(r.unresolved_discrepancies) for r in authority.trajectories) == 5
    assert len(authority.trajectories[4].logs) == 11
    assert (
        authority.trajectories[4].expected_xtc_path
        == "TUMOR/replica 2/md_rep2_full.xtc"
    )
    assert authority.prepared_storage_format == "OPEN"
