"""One backend, twelve selections, immutable init and safe numbered attempts."""

import importlib
import shutil
import subprocess
from pathlib import Path

import pytest
from test_ramila_gromacs_runtime import make_site, rt

run = importlib.import_module("run_ramila_gromacs")


@pytest.mark.parametrize(
    "selector,count",
    [
        ("wt", 6),
        ("t330m", 6),
        ("all", 12),
        ("gromacs_wt_norm_r1", 1),
        ("gromacs_t330m_tumor_r3", 1),
    ],
)
def test_exact_one_or_variant_selection(selector, count):
    selected = run.select_ids(selector)
    assert len(selected) == count
    assert set(selected) <= set(rt.SELECTIONS)


def test_init_human_n_declines_and_y_reuses_without_reprompt(tmp_path, monkeypatch):
    site = make_site(tmp_path)
    monkeypatch.setattr(run.attestation, "repository_head", lambda: "a" * 40)
    answers = iter(["Owner", "Confirmed twelve source sets", "N"])
    with pytest.raises(ValueError, match="declined"):
        run.init(
            site.source,
            site.output,
            runtime=site.runtime,
            input_fn=lambda _: next(answers),
        )
    assert not (site.output / "source_attestation.json").exists()
    answers = iter(["Owner", "Confirmed twelve source sets", "y"])
    assert (
        run.init(
            site.source,
            site.output,
            runtime=site.runtime,
            input_fn=lambda _: next(answers),
        )["status"]
        == "source_approved"
    )

    def forbidden(_):
        pytest.fail("Unchanged immutable approval must not reprompt")

    assert (
        run.init(site.source, site.output, runtime=site.runtime, input_fn=forbidden)[
            "status"
        ]
        == "source_approval_reused"
    )


def test_normal_init_requires_all_twelve_before_prompt(tmp_path):
    site = make_site(tmp_path)
    (site.source / site.rows[-1]["xtc_path"]).unlink()
    with pytest.raises(ValueError):
        run.init(
            site.source,
            site.output,
            runtime=site.runtime,
            input_fn=lambda _: pytest.fail("No prompt before all twelve files"),
        )


def lifecycle(tmp_path, monkeypatch):
    site = make_site(tmp_path)
    calls = []
    monkeypatch.setattr(run.attestation, "repository_head", lambda: "a" * 40)
    monkeypatch.setattr(run.prep, "prepare", lambda *a, **kw: calls.append("prepare"))
    monkeypatch.setattr(
        run, "verify_preparation", lambda *a, **kw: calls.append("verify")
    )
    monkeypatch.setattr(run, "validate_and_replay", lambda *a: dict(replay="PASS"))
    monkeypatch.setattr(
        run, "retain_ramila_handoff_inputs", lambda *a, **kw: "retained_inputs_spy"
    )
    import mania.production_handoff

    def prerequisites(root, retained, **kwargs):
        assert retained == "retained_inputs_spy"
        assert not (root / "science_complete.json").exists()

    monkeypatch.setattr(
        mania.production_handoff, "validate_handoff_prerequisites", prerequisites
    )

    def publish(root, retained, **kwargs):
        assert retained == "retained_inputs_spy"
        assert (root / "science_complete.json").is_file()
        calls.append("handoff")
        (root / "handoff_complete.json").write_text('{"synthetic_seal_spy":true}')

    monkeypatch.setattr(mania.production_handoff, "publish_handoff", publish)
    monkeypatch.setattr(
        mania.production_handoff,
        "load_completed_handoff",
        lambda *a: calls.append("load_handoff"),
    )
    import mania.cli

    def engine(manifest, output, condition, **kw):
        assert kw["handoff_inputs"] == "retained_inputs_spy"
        calls.append("science")
        output.mkdir()
        (output / "ledger.json").write_text('{"completed":true}')

    monkeypatch.setattr(mania.cli, "run_production_preprocessing", engine)
    return site, calls


def test_one_trajectory_completed_reuse_rechecks_artifacts(tmp_path, monkeypatch):
    site, calls = lifecycle(tmp_path, monkeypatch)
    kwargs = dict(
        runtime=site.runtime, technical=True, developer=True, technical_subset=True
    )
    first = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    second = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    assert first["reused"] is False and second["reused"] is True
    assert first["production_eligible"] is False
    assert calls.count("prepare") == calls.count("science") == 1
    (Path(first["output"]) / "preprocessing/ledger.json").write_text("changed")
    with pytest.raises(ValueError, match="Completed artifacts changed"):
        run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)


def test_incomplete_attempt_preserved_and_next_attempt_is_distinct(
    tmp_path, monkeypatch
):
    site, calls = lifecycle(tmp_path, monkeypatch)
    import mania.cli

    original = mania.cli.run_production_preprocessing

    def interrupted(*a, **kw):
        raise RuntimeError("Simulated interruption")

    monkeypatch.setattr(mania.cli, "run_production_preprocessing", interrupted)
    kwargs = dict(runtime=site.runtime, technical=True, developer=True)
    with pytest.raises(RuntimeError, match="interruption"):
        run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    first = (
        site.output / "technical_validation" / rt.REPRESENTATIVES[0] / "attempt_0001"
    )
    before = (first / "request.json").read_bytes()
    monkeypatch.setattr(mania.cli, "run_production_preprocessing", original)
    result = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    assert Path(result["output"]).name == "attempt_0002"
    assert (first / "request.json").read_bytes() == before
    assert not (first.parent / ".active").exists()


@pytest.mark.parametrize(
    "wrapper,operation,selector",
    [
        ("init_ramila_gromacs.sh", "init", None),
        ("run_ramila_gromacs_one.sh", "run", "gromacs_wt_norm_r1"),
        ("run_ramila_wt_all.sh", "run", "wt"),
        ("run_ramila_t330m_all.sh", "run", "t330m"),
        ("run_ramila_gromacs_all.sh", "run", "all"),
    ],
)
def test_thin_shell_wrappers_share_backend_and_preserve_spaced_roots(
    tmp_path, wrapper, operation, selector
):
    import os

    target = tmp_path / wrapper
    shutil.copy(rt.REPO / wrapper, target)
    spy = tmp_path / "python_spy"
    spy.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    spy.chmod(0o755)
    args = [str(target), "source with spaces", "output with spaces"]
    if wrapper == "run_ramila_gromacs_one.sh":
        args.append(selector)
    result = subprocess.run(
        args,
        env={**os.environ, "MANIA_PYTHON": str(spy)},
        check=True,
        capture_output=True,
        text=True,
    )
    expected = [
        str(tmp_path / "tools/run_ramila_gromacs.py"),
        operation,
        "source with spaces",
        "output with spaces",
    ]
    if selector is not None:
        expected.append(selector)
    assert result.stdout.splitlines() == expected


def test_normal_run_cannot_prepare_without_source_approval(tmp_path, monkeypatch):
    site, calls = lifecycle(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        run.run_one(
            site.source, site.output, rt.REPRESENTATIVES[0], runtime=site.runtime
        )
    assert calls == []


def test_developer_mode_cannot_select_a_nonrepresentative(tmp_path):
    site = make_site(tmp_path)
    with pytest.raises(ValueError, match="restricted to representative"):
        run.run_one(
            site.source,
            site.output,
            rt.SELECTIONS[1],
            runtime=site.runtime,
            technical=True,
            developer=True,
        )


def test_live_ownership_preserved_without_new_attempt(tmp_path, monkeypatch):
    site, calls = lifecycle(tmp_path, monkeypatch)
    parent = site.output / "technical_validation" / rt.REPRESENTATIVES[0]
    lock = parent / ".active"
    lock.mkdir(parents=True)
    with pytest.raises(ValueError, match="ownership preserved"):
        run.run_one(
            site.source,
            site.output,
            rt.REPRESENTATIVES[0],
            runtime=site.runtime,
            technical=True,
            developer=True,
        )
    assert lock.is_dir() and not list(parent.glob("attempt_*"))
    assert calls == []


def test_subset_preparation_never_becomes_production_ready(tmp_path):
    site = make_site(tmp_path)
    directory = tmp_path / "prepared"
    row = site.rows[0]
    rt.dump(
        directory / "preparation_complete.json",
        dict(
            status="passed",
            trajectory_id=row["trajectory_id"],
            protocol=rt.PROTOCOL,
            format="XTC:4",
            internal_MIC=False,
            full_axis_preserved=False,
        ),
    )
    with pytest.raises(ValueError, match="not production preparation"):
        run.verify_preparation(directory, site.source, row, technical=False)


def test_missing_biological_authority_does_not_invent_annotation_object(tmp_path):
    site = make_site(tmp_path)
    manifest = run.manifest_for(
        site.source,
        tmp_path / "prepared",
        tmp_path / "attempt",
        site.rows[0],
        technical=True,
        runtime=site.runtime,
    )
    condition = manifest.conditions[0]
    assert condition.biological_annotation_metadata_path is None
    assert condition.metadata == {"ramila_biological_annotation_authority": "PENDING"}
    assert condition.dataset_spec.temporal.production_end_ns == 8


def test_explicit_preparation_change_cannot_be_ignored_during_reuse(
    tmp_path, monkeypatch
):
    site, calls = lifecycle(tmp_path, monkeypatch)
    kwargs = dict(runtime=site.runtime, technical=True, developer=True)
    run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    with pytest.raises(ValueError, match="Explicit preparation differs"):
        run.run_one(
            site.source,
            site.output,
            rt.REPRESENTATIVES[0],
            prepared_directory=tmp_path / "different_preparation",
            **kwargs,
        )
    assert calls.count("science") == 1


def test_invalid_developer_group_rejected_before_any_trajectory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run,
        "run_one",
        lambda *a, **kw: pytest.fail(
            "Unsupported developer group must fail before execution"
        ),
    )
    assert (
        run.main(
            [
                "run",
                str(tmp_path / "source"),
                str(tmp_path / "output"),
                "wt",
                "--technical",
                "--developer-representative",
            ]
        )
        == 1
    )


def test_legacy_v1_attempt_is_preserved_and_fresh_namespace_used(tmp_path, monkeypatch):
    site, calls = lifecycle(tmp_path, monkeypatch)
    kwargs = dict(runtime=site.runtime, technical=True, developer=True)
    first = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    legacy = Path(first["output"])
    (legacy / "handoff_complete.json").unlink()
    request = rt.read_json(legacy / "request.json")
    request.pop("handoff_contract_id")
    (legacy / "request.json").write_text(__import__("json").dumps(request))
    before = run.tree_digests(legacy)
    second = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    assert Path(second["output"]).name == "attempt_0002"
    assert second["legacy_attempts"] == [str(legacy)]
    assert run.tree_digests(legacy) == before
    assert calls.count("science") == calls.count("handoff") == 2


def test_new_contract_science_without_handoff_seal_cannot_be_reused(
    tmp_path, monkeypatch
):
    site, calls = lifecycle(tmp_path, monkeypatch)
    kwargs = dict(runtime=site.runtime, technical=True, developer=True)
    first = run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    (Path(first["output"]) / "handoff_complete.json").unlink()
    with pytest.raises(ValueError, match="lacks completed handoff"):
        run.run_one(site.source, site.output, rt.REPRESENTATIVES[0], **kwargs)
    assert calls.count("science") == 1


def test_ramila_prerequisite_failure_prevents_both_completion_markers(
    tmp_path, monkeypatch
):
    import mania.production_handoff

    site, calls = lifecycle(tmp_path, monkeypatch)

    def reject(root, retained, **kwargs):
        assert not (root / "science_complete.json").exists()
        raise ValueError("Missing compact prerequisite")

    monkeypatch.setattr(
        mania.production_handoff, "validate_handoff_prerequisites", reject
    )
    with pytest.raises(ValueError, match="compact prerequisite"):
        run.run_one(
            site.source,
            site.output,
            rt.REPRESENTATIVES[0],
            runtime=site.runtime,
            technical=True,
            developer=True,
        )
    assert "science" in calls and "handoff" not in calls
    assert not list(site.output.rglob("science_complete.json"))
    assert not list(site.output.rglob("handoff_complete.json"))


def test_external_prepared_directory_real_common_rmsd_and_handoff(
    tmp_path, monkeypatch
):
    import copy

    from test_production_handoff import handoff_case

    from mania.dataset_identity import DatasetTrajectorySpec
    from mania.preprocessing.trajectory_rmsd_io import read_rmsd_evidence
    from mania.production_handoff import HandoffCompletion, load_completed_handoff

    (tmp_path / "ramila").mkdir()
    site = make_site(tmp_path / "ramila")
    row = site.rows[0]
    spec = copy.deepcopy(row["dataset_spec"])
    spec["temporal"]["production_end_ns"] = 8.0
    (tmp_path / "setup").mkdir()
    setup = handoff_case(
        tmp_path / "setup",
        monkeypatch,
        produce=False,
        spec=DatasetTrajectorySpec.model_validate(
            {k: spec[k] for k in ("identity", "temporal")}
        ),
        source_paths={
            "raw_trajectory": site.source / row["xtc_path"],
            "topology": site.source / row["tpr"]["path"],
        },
    )
    (site.runtime / row["canonical_mapping_path"]).parent.mkdir(
        parents=True, exist_ok=True
    )
    (site.runtime / row["partner_metadata_path"]).parent.mkdir(
        parents=True, exist_ok=True
    )
    shutil.copyfile(
        setup.retained.source.compact_files["canonical_residue_mapping"],
        site.runtime / row["canonical_mapping_path"],
    )
    shutil.copyfile(
        setup.retained.source.compact_files["molecular_partner_metadata"],
        site.runtime / row["partner_metadata_path"],
    )
    shutil.copyfile(
        setup.retained.source.compact_files["source_time_authority"],
        setup.preparation / "source_axis.json",
    )
    monkeypatch.setattr(run, "verify_preparation", lambda *a, **kw: None)
    monkeypatch.setattr(
        run.prep,
        "prepare",
        lambda *a, **kw: pytest.fail("External preparation authority must be used"),
    )
    monkeypatch.setattr(run.attestation, "repository_head", lambda: "a" * 40)
    result = run.run_one(
        site.source,
        site.output,
        row["trajectory_id"],
        technical=True,
        developer=True,
        runtime=site.runtime,
        prepared_directory=setup.preparation,
    )
    root = Path(result["output"])
    manifest = load_completed_handoff(root)
    metadata, rows = read_rmsd_evidence(root / "preprocessing")
    assert manifest.replica_identity.trajectory_id == row["trajectory_id"]
    assert len(rows) == 16 and metadata.atom_selection.atom_count == 4
    assert rt.read_json(root / "science_complete.json")["preparation_root"] == str(
        setup.preparation
    )
    assert (
        HandoffCompletion.model_validate(
            rt.read_json(root / "handoff_complete.json")
        ).production_eligible
        is False
    )
    report = setup.report.read_bytes()
    shutil.rmtree(setup.preparation)
    assert load_completed_handoff(root) == manifest
    assert (
        root / "evidence/producer/preparation_report/preparation_complete.json"
    ).read_bytes() == report
