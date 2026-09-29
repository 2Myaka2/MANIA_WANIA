"""Exact source/run approval integrity, without GROMACS or coordinate decoding."""

import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_gromacs_wt_runtime import make_site, runtime

attest = importlib.import_module("gromacs_wt_source_attestation")

HEAD = "a" * 40


@pytest.fixture
def approval(tmp_path):
    site = make_site(tmp_path)
    site.output.mkdir()
    site.path = site.output / "gromacs_source_attestation.json"
    site.kwargs = dict(
        source=site.source,
        rows=site.authority.trajectories,
        authority_inventory=runtime.inventory(site.runtime),
        repository_head=HEAD,
    )
    attest.save(
        site.path, reviewer="Reviewer", review_note="Source mapping only", **site.kwargs
    )
    return site


def test_exact_gromacs_document_and_reuse(approval):
    document = attest.verify(approval.path, **approval.kwargs)
    assert document["schema_version"] == "mania.gromacs_source_attestation.v0.1"
    assert document["scope"] == "source_run_correspondence_only"
    assert document["statement"] == attest.STATEMENT
    assert len(document["trajectories"]) == 6
    assert len(document["trajectories"][0]["logs"]) == 2
    assert set(document["trajectories"][0]) == {
        "trajectory_id",
        "xtc",
        "tpr",
        "mdp",
        "logs",
    }


@pytest.mark.parametrize("role", ["xtc", "tpr", "mdp", "logs"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_changed_or_missing_sources_invalidate(approval, role, damage):
    row = approval.authority.trajectories[0]
    name = (
        row.expected_xtc_path
        if role == "xtc"
        else row.logs[0].path
        if role == "logs"
        else getattr(row, role).path
    )
    path = approval.source / name
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"new bytes")
    with pytest.raises(ValueError, match="Invalid GROMACS"):
        attest.verify(approval.path, **approval.kwargs)


@pytest.mark.parametrize(
    "damage",
    [
        "checksum",
        "payload",
        "duplicate",
        "empty",
        "path",
        "timestamp",
        "scope",
        "unknown_field",
        "json_duplicate",
    ],
)
def test_corrupt_attestation_rejected(approval, damage):
    data = json.loads(approval.path.read_text())
    if damage == "json_duplicate":
        approval.path.write_text('{"scope":"a","scope":"b"}')
    else:
        if damage == "checksum":
            data["payload_sha256"] = "0" * 64
        elif damage == "payload":
            data["review_note"] = "tampered"
        elif damage == "duplicate":
            data["trajectories"].append(data["trajectories"][0])
        elif damage == "empty":
            data["trajectories"] = []
        elif damage == "path":
            data["trajectories"][0]["xtc"]["path"] = "NORM/replica 1/other.xtc"
        elif damage == "timestamp":
            data["approved_utc"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        elif damage == "scope":
            data["scope"] = "PBC_approved"
        else:
            data["coordinate_approval"] = True
        if damage not in {"checksum", "payload"}:
            data.pop("payload_sha256")
            data["payload_sha256"] = attest.digest(data)
        approval.path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        attest.verify(approval.path, **approval.kwargs)


def test_never_overwrite_approval(approval):
    before = approval.path.read_bytes()
    with pytest.raises(ValueError, match="protected"):
        attest.save(
            approval.path, reviewer="Other", review_note="Changed", **approval.kwargs
        )
    assert approval.path.read_bytes() == before


@pytest.mark.parametrize("kind", ["empty", "duplicate"])
def test_save_bad_selections(approval, kind):
    kwargs = dict(approval.kwargs)
    kwargs["rows"] = [] if kind == "empty" else kwargs["rows"] * 2
    with pytest.raises(ValueError, match="selections"):
        attest.save(
            approval.output / "new.json", reviewer="R", review_note="N", **kwargs
        )


@pytest.mark.parametrize("kind", ["head", "authority", "source", "mapping"])
def test_binding_changes_invalidate(approval, kind, tmp_path):
    kwargs = dict(approval.kwargs)
    if kind == "head":
        kwargs["repository_head"] = "b" * 40
    elif kind == "authority":
        kwargs["authority_inventory"] = []
    elif kind == "source":
        kwargs["source"] = tmp_path
    else:
        kwargs["rows"][0].expected_xtc_path = "NORM/replica 1/other.xtc"
    with pytest.raises(ValueError):
        attest.verify(approval.path, **kwargs)


def test_same_size_xtc_change_invalidates_hash(approval):
    path = approval.source / approval.authority.trajectories[0].expected_xtc_path
    path.write_bytes(b"x" * path.stat().st_size)
    with pytest.raises(ValueError, match="identity changed"):
        attest.verify(approval.path, **approval.kwargs)


def test_source_mutation_between_hashes_rejected(tmp_path, monkeypatch):
    site = make_site(tmp_path)
    first = site.authority.trajectories[0].expected_xtc_path
    last = site.authority.trajectories[-1].expected_xtc_path
    original = attest.identity

    def mutate(source, name):
        result = original(source, name)
        if name == last:
            (source / first).write_bytes(b"changed after earlier hash")
        return result

    monkeypatch.setattr(attest, "identity", mutate)
    with pytest.raises(ValueError, match="changed during capture"):
        attest.capture(site.source, site.authority.trajectories)
