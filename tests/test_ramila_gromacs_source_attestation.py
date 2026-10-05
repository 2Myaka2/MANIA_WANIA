"""All twelve reviewed source bindings are immutable and automatically hashed."""

import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_ramila_gromacs_runtime import make_site, rt

attest = importlib.import_module("ramila_gromacs_source_attestation")


@pytest.fixture
def approved(tmp_path, monkeypatch):
    monkeypatch.setattr(attest, "repository_head", lambda: "a" * 40)
    site = make_site(tmp_path)
    site.path = site.output / "source_attestation.json"
    attest.save(
        site.path,
        site.source,
        site.rows,
        reviewer="Owner",
        review_note="Reviewed source/run correspondence",
        approve="y",
        runtime=site.runtime,
    )
    return site


def test_all_twelve_exact_bindings_and_unchanged_reuse(approved):
    doc = attest.verify(
        approved.path, approved.source, approved.rows, runtime=approved.runtime
    )
    assert doc["scope"] == "source_run_correspondence_only"
    assert tuple(r["trajectory_id"] for r in doc["trajectories"]) == rt.SELECTIONS
    assert len(doc["trajectories"][4]["additional_tprs"]) == 1
    assert doc["reviewer"] == "Owner"


@pytest.mark.parametrize("role", ["xtc", "tpr", "mdp", "logs", "additional_tprs"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_every_changed_or_missing_source_invalidates(approved, role, damage):
    row = approved.rows[4]
    name = (
        row["xtc_path"]
        if role == "xtc"
        else row[role][0]["path"]
        if role in ("logs", "additional_tprs")
        else row[role]["path"]
    )
    path = approved.source / name
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"x" * path.stat().st_size)  # Same-size changes need SHA256.
    with pytest.raises((ValueError, OSError)):
        attest.verify(
            approved.path, approved.source, approved.rows, runtime=approved.runtime
        )


@pytest.mark.parametrize("approve", ["", "N", "yes"])
def test_declining_never_creates_approval(tmp_path, approve):
    site = make_site(tmp_path)
    path = site.output / "source_attestation.json"
    with pytest.raises(ValueError, match="declined"):
        attest.save(
            path,
            site.source,
            site.rows,
            reviewer="R",
            review_note="N",
            approve=approve,
            runtime=site.runtime,
        )
    assert not path.exists()


def test_existing_approval_never_replaced(approved):
    before = approved.path.read_bytes()
    with pytest.raises(ValueError, match="protected"):
        attest.save(
            approved.path,
            approved.source,
            approved.rows,
            reviewer="Other",
            review_note="New",
            approve="y",
            runtime=approved.runtime,
        )
    assert approved.path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer", ""),
        ("review_note", " "),
        ("scope", "PBC"),
        ("approved_utc", "invalid"),
        ("approved_utc", (datetime.now(UTC) + timedelta(days=1)).isoformat()),
    ],
)
def test_invalid_review_metadata_rejected_even_with_recomputed_digest(
    approved, field, value
):
    doc = json.loads(approved.path.read_text())
    doc[field] = value
    doc.pop("payload_sha256")
    doc["payload_sha256"] = rt.digest(doc)
    approved.path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        attest.verify(
            approved.path, approved.source, approved.rows, runtime=approved.runtime
        )


def test_source_changes_during_complete_hash_capture_block(tmp_path, monkeypatch):
    site = make_site(tmp_path)
    original = rt.identity
    first = site.rows[0]["xtc_path"]
    last = site.rows[-1]["xtc_path"]

    def mutate(source, name):
        result = original(source, name)
        if name == last:
            (source / first).write_bytes(b"changed after previous hash")
        return result

    monkeypatch.setattr(rt, "identity", mutate)
    with pytest.raises(ValueError, match="changed during"):
        attest.capture(site.source, site.rows)


def test_new_matching_continuation_log_invalidates_existing_approval(approved):
    row = approved.rows[0]
    from pathlib import Path

    primary = approved.source / row["tpr"]["path"]
    (primary.parent / (Path(primary).stem + ".part9999.log")).write_text(
        "New continuation not reviewed"
    )
    with pytest.raises(ValueError, match="LOG set changed"):
        attest.verify(
            approved.path, approved.source, approved.rows, runtime=approved.runtime
        )
