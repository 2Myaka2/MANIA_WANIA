"""Synthetic technical contracts exercise delegation, gates, and portable reports."""

import builtins
import hashlib
import io
import json
import os
import subprocess
import time
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import mania.validation as validation
import mania.validation.unified as unified
from mania.artifact_inventory import ArtifactInventory, ArtifactInventoryEntry
from mania.artifact_inventory_io import ArtifactInventoryReadError
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS
from mania.preprocessing import trajectory_contacts_export_validation as contacts
from mania.preprocessing import trajectory_graph_export as graph_export
from mania.preprocessing import trajectory_rg_export_validation as rg
from mania.run_provenance import PortableArtifactReference, RunProvenance
from mania.software_identity import SoftwareIdentity
from mania.validation import artifacts, graph, run_artifacts


def csv_bytes(columns, condition=None):
    header = ",".join(columns) + "\n"
    if condition is not None:
        header += (
            ",".join(condition if c == "condition" else "" for c in columns) + "\n"
        )
    return header.encode()


def graph_bytes(condition="normal"):
    return json.dumps(
        dict(
            condition=condition,
            n_nodes=0,
            n_edges=0,
            directed=False,
            schema_version="0.1",
            nodes=[],
            edges=[],
        )
    ).encode()


def write_metadata(bundle):
    for path, model in (
        (bundle.inventory_path, bundle.inventory),
        (bundle.provenance_path, bundle.provenance),
    ):
        (bundle.root / path).write_text(json.dumps(model.to_dict()), encoding="utf-8")


def make_bundle(root, *, scope="preprocessing", mode="none", outputs=None, inputs=()):
    """Explicit small file set shared with CLI and isolated package smoke checks."""
    root.mkdir(parents=True, exist_ok=True)
    prefix = "analysis/" if scope == "analysis" else ""
    if outputs is None:
        outputs = (
            (
                "residue_table",
                csv_bytes(unified._csv_contracts()["residue_table"], "normal"),
                "normal",
            ),
        )
    entries = []
    paths = {}
    mappings = {}
    for direction, supplied in (("input", inputs), ("output", outputs)):
        for index, (role, content, condition) in enumerate(supplied):
            identity = f"{direction}:{index}"
            suffix = (
                "xtc"
                if role == "condition_trajectory"
                else (
                    "json"
                    if "graph" in role
                    and role
                    not in (
                        "graph_nodes",
                        "graph_edges",
                        "reference_nodes",
                        "reference_edges",
                    )
                    else "csv"
                )
            )
            portable = "inputs/" if direction == "input" else prefix + "artifacts/"
            portable += f"{index}_{role}.{suffix}"
            path = (
                root / portable
                if direction == "output"
                else (root.parent / "private-source" / f"{index}_{role}.{suffix}")
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            paths[identity] = path
            if direction == "input":
                mappings[identity] = path
            entries.append(
                ArtifactInventoryEntry(
                    identity,
                    direction,
                    role,
                    portable,
                    suffix,
                    len(content),
                    hashlib.sha256(content).hexdigest() if mode == "sha256" else None,
                    condition,
                )
            )
    workflow = "analysis" if scope == "analysis" else "preprocessing_graph_export"
    inventory_path = prefix + "artifact_inventory.json"
    provenance = RunProvenance(
        "synthetic-run",
        workflow,
        "completed",
        datetime(2026, 1, 2, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
        SoftwareIdentity(
            "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
        ),
        ("mania", "synthetic"),
        {},
        ("normal", "tumor"),
        artifact_references=(
            PortableArtifactReference("artifact_inventory", inventory_path),
        )
        + tuple(
            PortableArtifactReference(e.role, e.path)
            for e in entries
            if e.direction == "output"
        ),
    )
    bundle = SimpleNamespace(
        root=root,
        scope=scope,
        paths=paths,
        mappings=mappings,
        inventory_path=inventory_path,
        provenance_path=prefix + "run_provenance.json",
        inventory=ArtifactInventory(
            "synthetic-run", workflow, inventory_path, mode, tuple(entries)
        ),
        provenance=provenance,
    )
    (root / prefix).mkdir(parents=True, exist_ok=True)
    write_metadata(bundle)
    return bundle


def validate(bundle, *, mapped=False):
    return validation.validate_run_artifacts(
        bundle.root,
        scope=bundle.scope,
        input_artifact_paths=bundle.mappings if mapped else None,
    )


def forbid(*args, **kwargs):
    raise AssertionError("Unexpected filesystem discovery, mutation, clock, or process")


def guard_validation(patch):
    for name in (
        "glob",
        "rglob",
        "iterdir",
        "resolve",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "rename",
        "replace",
    ):
        patch.setattr(Path, name, forbid)
    patch.setattr(os, "walk", forbid)
    for name in ("run", "Popen"):
        patch.setattr(subprocess, name, forbid)
    for name in ("time", "time_ns"):
        patch.setattr(time, name, forbid)
    patch.setattr(
        run_artifacts,
        "read_run_provenance",
        Mock(wraps=run_artifacts.read_run_provenance),
    )
    for owner in (builtins, io):
        original = owner.open

        def read_only(file, mode="r", *args, _open=original, **kwargs):
            assert not any(flag in mode for flag in "wax+")
            return _open(file, mode, *args, **kwargs)

        patch.setattr(owner, "open", read_only)


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
def test_foundation_single_integrity_call_mapping_identity_and_isolation(
    tmp_path, monkeypatch, scope
):
    bundle = make_bundle(tmp_path / "run", scope=scope)
    other = "" if scope == "analysis" else "analysis/"
    sentinels = [
        bundle.root / (other + p)
        for p in (
            "run_provenance.json",
            "artifact_inventory.json",
            "unrelated.csv",
        )
    ]
    for path in sentinels:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unrelated malformed content")
    paths = (
        list(bundle.paths.values())
        + sentinels
        + [
            bundle.root / bundle.inventory_path,
            bundle.root / bundle.provenance_path,
        ]
    )
    before = {p: p.read_bytes() for p in paths}
    original = run_artifacts.validate_run_artifact_integrity
    spy = Mock(wraps=original)
    with monkeypatch.context() as patch:
        guard_validation(patch)
        patch.setattr(run_artifacts, "validate_run_artifact_integrity", spy)
        report = validate(bundle, mapped=True)
    spy.assert_called_once_with(
        bundle.root, scope=scope, input_artifact_paths=bundle.mappings
    )
    assert spy.call_args.kwargs["input_artifact_paths"] is bundle.mappings
    assert report.scope == scope and report.status == "passed"
    assert before == {p: p.read_bytes() for p in paths}
    assert report.to_dict() == validate(bundle).to_dict()


@pytest.mark.parametrize("mode", ["none", "sha256"])
@pytest.mark.parametrize(
    "damage", [None, "missing", "directory", "size", "checksum", "read_error"]
)
def test_integrity_gate_precedes_specialized_validation(
    tmp_path, monkeypatch, mode, damage
):
    if mode == "none" and damage in ("checksum", "read_error"):
        pytest.skip("No checksum read in none mode")
    bundle = make_bundle(tmp_path / "run", mode=mode)
    output = bundle.paths["output:0"]
    if damage in ("missing", "directory"):
        output.unlink()
        if damage == "directory":
            output.mkdir()
    elif damage == "size":
        output.write_bytes(b"bad")
    elif damage == "checksum":
        content = output.read_bytes()
        output.write_bytes(b"!" + content[1:])
    elif damage == "read_error":
        monkeypatch.setattr(
            run_artifacts, "stream_file_sha256", Mock(side_effect=OSError("private"))
        )
    schema = Mock(wraps=artifacts.validate_csv_artifact_schema)
    monkeypatch.setattr(artifacts, "validate_csv_artifact_schema", schema)
    report = validate(bundle)
    if damage:
        schema.assert_not_called()
        assert report.status == "failed"
        assert report.specialized_records[0].status == "skipped_integrity_failure"
        assert report.issues == ()
    else:
        schema.assert_called_once()
        assert report.status == "passed"
        record = report.integrity_report.artifact_records[0]
        assert record.sha256_checked == (mode == "sha256")


def test_every_current_emitted_role_is_explicitly_classified(tmp_path):
    from test_analysis_artifact_inventory import declared_inputs
    from test_analysis_run_provenance import analysis_result
    from test_preprocessing_artifact_inventory import make_runtime, make_stages

    from mania.analysis import artifact_inventory as analysis_adapter
    from mania.analysis.orchestration import AnalyzeRequest
    from mania.preprocessing import artifact_inventory as preprocessing_adapter

    runtime = make_runtime(tmp_path)
    root = tmp_path / "out"
    stages = make_stages(root, runtime)
    options = stages["reference_comparison"].options
    prep = preprocessing_adapter.collect_preprocessing_input_file_specs(
        runtime,
        include_reference_inputs=True,
        reference_nodes_path=options.reference_nodes_csv_path,
        reference_edges_path=options.reference_edges_csv_path,
        reference_graph_path=options.reference_graph_json_path,
    ) + preprocessing_adapter.collect_preprocessing_output_file_specs(
        output_root=root, **stages
    )
    request = AnalyzeRequest(tmp_path / "in", root, ("normal", "tumor"))
    analysis = analysis_adapter.collect_analysis_input_file_specs(
        request=request,
        resolved_input_paths=declared_inputs(request),
    ) + analysis_adapter.collect_analysis_output_file_specs(analysis_result(request))
    assert {e.role for e in prep} == unified._PREPROCESSING_POLICY.keys()
    assert {e.role for e in analysis} == unified._ANALYSIS_POLICY.keys()
    assert len({e.role for e in prep}) == 21
    assert len({e.role for e in analysis}) == 16


@pytest.mark.parametrize(
    "scope,role,owner,name",
    [
        ("preprocessing", "graph_json", graph, "validate_graph_json"),
        ("analysis", "analysis_graph", graph, "validate_graph_json"),
        ("preprocessing", "reference_graph", graph, "validate_graph_json"),
        ("preprocessing", "rg_timeseries", rg, "validate_rg_timeseries_csv"),
        ("preprocessing", "contact_edges", contacts, "validate_contact_edges_csv"),
        (
            "preprocessing",
            "contacts_perframe",
            contacts,
            "validate_contacts_perframe_csv",
        ),
    ],
)
def test_delegates_existing_specialized_validator(
    tmp_path, monkeypatch, scope, role, owner, name
):
    bundle = make_bundle(
        tmp_path / "run", scope=scope, outputs=((role, b"abc", "normal"),)
    )
    spy = Mock(return_value=SimpleNamespace(passed=True))
    monkeypatch.setattr(owner, name, spy)
    report = validate(bundle)
    kwargs = {"expected_condition": "normal"} if owner is graph else {}
    spy.assert_called_once_with(bundle.paths["output:0"], **kwargs)
    assert report.specialized_records[0].validator == name
    assert report.status == "passed"


@pytest.mark.parametrize(
    "scope,role,contract",
    [
        ("preprocessing", "residue_table", "residue_table"),
        ("preprocessing", "protein_contact_edges", "protein_contact_edges"),
        ("preprocessing", "protein_contacts_perframe", "protein_contacts_perframe"),
        ("analysis", "contacts_perframe", "protein_contacts_perframe"),
        *[
            ("analysis", "analysis_" + c, c)
            for c in (
                "centrality",
                "communities",
                "region_enrichment",
                "temporal_rin",
                "conformation_pca",
                "conformation_labels",
                "comparison",
                "stats",
            )
        ],
    ],
)
def test_delegates_exact_accepted_csv_and_condition_contract(
    tmp_path, monkeypatch, scope, role, contract
):
    bundle = make_bundle(
        tmp_path / "run", scope=scope, outputs=((role, b"abc", "normal"),)
    )
    schema = Mock(return_value=SimpleNamespace(is_valid=True))
    condition = Mock(return_value=None)
    monkeypatch.setattr(artifacts, "validate_csv_artifact_schema", schema)
    monkeypatch.setattr(artifacts, "validate_condition_column", condition)
    monkeypatch.setattr(contacts, "validate_contacts_perframe_csv", forbid)
    report = validate(bundle)
    columns = unified._csv_contracts()[contract]
    schema.assert_called_once_with(
        bundle.paths["output:0"], contract, expected_columns=columns
    )
    if "condition" in columns:
        condition.assert_called_once_with(bundle.paths["output:0"], "normal")
    else:
        condition.assert_not_called()
    assert report.status == "passed"


@pytest.mark.parametrize(
    "roles", [("graph_nodes", "graph_edges"), ("reference_nodes", "reference_edges")]
)
@pytest.mark.parametrize(
    "outcome", ["passed", "failed", "missing", "unresolved", "absent", "duplicate"]
)
def test_pair_called_once_and_gated_as_a_group(tmp_path, monkeypatch, roles, outcome):
    supplied = tuple((role, b"abc", None) for role in roles)
    if outcome == "absent":
        supplied = supplied[:1]
    if outcome == "duplicate":
        supplied += supplied[:1]
    inputs = supplied if outcome == "unresolved" else ()
    bundle = make_bundle(
        tmp_path / "run", outputs=() if inputs else supplied, inputs=inputs
    )
    if outcome == "missing":
        bundle.paths["output:1"].unlink()
    spy = Mock(
        return_value=SimpleNamespace(passed=outcome != "failed", issues=("private",))
    )
    monkeypatch.setattr(graph_export, "validate_preprocessing_graph_csvs", spy)
    report = validate(bundle)
    if outcome in ("passed", "failed"):
        spy.assert_called_once_with(bundle.paths["output:0"], bundle.paths["output:1"])
        assert report.specialized_validation_count == 2
        assert report.error_count == (outcome == "failed")
        assert all(r.status == outcome for r in report.specialized_records)
    else:
        spy.assert_not_called()
        expected = {
            "missing": "skipped_integrity_failure",
            "unresolved": "not_resolved",
            "absent": "failed",
            "duplicate": "failed",
        }[outcome]
        assert all(r.status == expected for r in report.specialized_records)
        assert report.status == ("partial" if outcome == "unresolved" else "failed")


@pytest.mark.parametrize(
    "role,content",
    [
        ("graph_json", graph_bytes()),
        (
            "rg_timeseries",
            b"condition_name,frame_index,time_ps,rg_value,rg_unit,frame_passed\nnormal,0,0,1,angstrom,true\n",
        ),
        ("contact_edges", csv_bytes(contacts._CONTACT_EDGES_HEADER)),
        ("contacts_perframe", csv_bytes(contacts._CONTACTS_PERFRAME_HEADER)),
        (
            "residue_table",
            csv_bytes(unified._csv_contracts()["residue_table"], "normal"),
        ),
    ],
)
@pytest.mark.parametrize("invalid", [False, True])
def test_real_validator_integration(tmp_path, role, content, invalid):
    bundle = make_bundle(
        tmp_path / "run", outputs=((role, b"bad" if invalid else content, "normal"),)
    )
    report = validate(bundle)
    assert report.integrity_report.status == "passed"
    assert report.status == ("failed" if invalid else "passed")
    assert len(report.issues) == int(invalid)
    assert str(tmp_path) not in json.dumps(report.to_dict())


@pytest.mark.parametrize("invalid", [False, True])
def test_real_graph_pair_validation(tmp_path, invalid):
    bundle = make_bundle(
        tmp_path / "run",
        outputs=(
            ("graph_nodes", csv_bytes(NODE_COLUMNS), None),
            ("graph_edges", b"bad" if invalid else csv_bytes(EDGE_COLUMNS), None),
        ),
    )
    report = validate(bundle)
    assert report.status == ("failed" if invalid else "passed")
    assert report.specialized_failed_count == (2 if invalid else 0)
    assert report.error_count == int(invalid)


@pytest.mark.parametrize("incomplete", [False, True])
def test_pair_preserves_each_members_integrity_gate(tmp_path, monkeypatch, incomplete):
    supplied = (("graph_nodes", b"abc", None), ("graph_edges", b"abc", None))
    bundle = make_bundle(
        tmp_path / "run",
        outputs=(),
        inputs=supplied[:1] if incomplete else supplied,
    )
    bundle.paths["input:0"].unlink()
    monkeypatch.setattr(graph_export, "validate_preprocessing_graph_csvs", forbid)
    report = validation.validate_run_artifacts(
        bundle.root,
        scope=bundle.scope,
        input_artifact_paths={"input:0": bundle.paths["input:0"]},
    )
    assert report.status == "failed"
    assert report.specialized_records[0].status == "skipped_integrity_failure"
    if incomplete:
        assert report.issues[0].code == "invalid_graph_pair"
    else:
        assert report.specialized_records[1].status == "not_resolved"
        assert report.issues == ()


@pytest.mark.parametrize("role", ["graph_json", "residue_table"])
@pytest.mark.parametrize("condition", ["normal", "tumor"])
def test_existing_condition_validation(tmp_path, role, condition):
    content = (
        graph_bytes(condition)
        if role == "graph_json"
        else csv_bytes(
            unified._csv_contracts()["residue_table"],
            condition,
        )
    )
    bundle = make_bundle(tmp_path / "run", outputs=((role, content, "normal"),))
    report = validate(bundle)
    assert report.status == ("passed" if condition == "normal" else "failed")


@pytest.mark.parametrize("mapped", [False, True])
@pytest.mark.parametrize("raw", [False, True])
def test_external_input_resolution_and_lineage_only(tmp_path, monkeypatch, mapped, raw):
    role = "condition_trajectory" if raw else "residue_table"
    content = b"synthetic-xtc" if raw else csv_bytes(unified._csv_contracts()[role])
    bundle = make_bundle(
        tmp_path / "run",
        scope="preprocessing" if raw else "analysis",
        outputs=(),
        inputs=((role, content, "normal"),),
    )
    # A plausible local copy is deliberately invalid and never used.
    guessed = bundle.root / bundle.inventory.artifacts[0].path
    guessed.parent.mkdir(parents=True, exist_ok=True)
    guessed.write_bytes(b"wrong")
    spy = Mock(wraps=artifacts.validate_csv_artifact_schema)
    monkeypatch.setattr(artifacts, "validate_csv_artifact_schema", spy)
    report = validate(bundle, mapped=mapped)
    assert report.status == ("passed" if mapped else "partial")
    assert report.passed and report.complete == mapped
    expected = "not_applicable" if raw else ("passed" if mapped else "not_resolved")
    assert report.specialized_records[0].status == expected
    assert spy.call_count == int(mapped and not raw)
    payload = json.dumps(report.to_dict())
    assert str(tmp_path) not in payload
    for field in (
        "scientifically_valid",
        "scientifically_accepted",
        "publication_ready",
        "dataset_approved",
        "published",
        "dataset_member",
        "release_member",
    ):
        assert field not in payload
    if raw:
        assert ".xtc" in payload


@pytest.mark.parametrize(
    "outcome", ["exception", "passed_false", "valid_false", "success", "programming"]
)
def test_result_normalization_and_path_safety(tmp_path, monkeypatch, outcome):
    bundle = make_bundle(tmp_path / "run", outputs=(("rg_timeseries", b"abc", None),))
    leaked = str(tmp_path / "private" / "secret.csv")
    result = SimpleNamespace(
        passed=outcome != "passed_false",
        is_valid=outcome != "valid_false",
        issues=(leaked, leaked),
        path=Path(leaked),
    )
    spy = Mock(return_value=result)
    if outcome == "exception":
        spy.side_effect = artifacts.ArtifactValidationError(leaked)
    if outcome == "programming":
        spy.side_effect = RuntimeError(leaked)
    monkeypatch.setattr(rg, "validate_rg_timeseries_csv", spy)
    if outcome == "programming":
        with pytest.raises(RuntimeError):
            validate(bundle)
        return
    report = validate(bundle)
    assert str(tmp_path) not in json.dumps(report.to_dict())
    assert report.error_count == int(outcome != "success")
    assert (
        report.specialized_records[0].issue_count
        == {
            "exception": 1,
            "passed_false": 2,
            "valid_false": 2,
            "success": 0,
        }[outcome]
    )


def test_unknown_future_role_cannot_silently_pass(tmp_path):
    bundle = make_bundle(tmp_path / "run", outputs=(("future_role", b"abc", None),))
    report = validate(bundle)
    assert report.status == "partial" and report.passed and not report.complete
    assert report.unsupported_count == report.warning_count == 1
    assert report.specialized_records[0].validator is None
    assert report.issues[0].code == "unsupported_artifact_role"


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
def test_known_integrity_only_roles_do_not_call_legacy_manifest_validator(
    tmp_path, monkeypatch, scope
):
    import mania.validation.manifest as manifest

    policy = (
        unified._PREPROCESSING_POLICY
        if scope == "preprocessing"
        else unified._ANALYSIS_POLICY
    )
    bundle = make_bundle(
        tmp_path / "run",
        scope=scope,
        outputs=tuple(
            (role, b"opaque", None) for role, c in policy.items() if c is None
        ),
    )
    monkeypatch.setattr(manifest, "validate_global_features", forbid)
    monkeypatch.setattr(unified, "_invoke", forbid)
    report = validate(bundle)
    assert report.status == "passed"
    assert all(r.status == "not_applicable" for r in report.specialized_records)


def test_metadata_failure_and_inventory_reread_are_reports(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path / "run")
    (bundle.root / bundle.provenance_path).write_bytes(b"invalid")
    assert validate(bundle).status == "failed"
    write_metadata(bundle)
    monkeypatch.setattr(
        unified,
        "read_artifact_inventory",
        Mock(side_effect=ArtifactInventoryReadError("private")),
    )
    report = validate(bundle)
    assert report.status == "failed" and report.issues[0].code == "inventory_read_error"
    assert report.specialized_records == ()
    (bundle.root / bundle.inventory_path).write_bytes(b"invalid")
    report = validate(bundle)
    assert report.status == "failed" and report.error_count == 1
    assert report.issues == ()


def test_changed_inventory_cannot_use_previous_integrity_observations(
    tmp_path, monkeypatch
):
    bundle = make_bundle(tmp_path / "run")
    changed = replace(
        bundle.inventory,
        artifacts=(replace(bundle.inventory.artifacts[0], byte_size=1),),
    )
    monkeypatch.setattr(unified, "read_artifact_inventory", Mock(return_value=changed))
    monkeypatch.setattr(unified, "_invoke", forbid)
    report = validate(bundle)
    assert report.status == "failed" and report.issues[0].code == "inventory_changed"


def test_report_models_public_frozen_json_safe_and_validated(tmp_path):
    bundle = make_bundle(tmp_path / "run")
    report = validate(bundle)
    assert isinstance(report, validation.UnifiedArtifactValidationReport)
    assert (
        report.schema_version == validation.UNIFIED_ARTIFACT_VALIDATION_SCHEMA_VERSION
    )
    assert report.kind == validation.UNIFIED_ARTIFACT_VALIDATION_KIND
    assert report.specialized_validation_count == report.specialized_passed_count == 2
    with pytest.raises(FrozenInstanceError):
        report.scope = "analysis"
    serialized = report.to_dict()
    serialized["specialized_records"].clear()
    assert len(report.specialized_records) == 2
    for changes in (
        dict(issue_count=-1),
        dict(issue_count=True),
        dict(status="unknown"),
        dict(path="/private.csv"),
        dict(status="unsupported"),
    ):
        with pytest.raises(ValueError):
            replace(report.specialized_records[0], **changes)
    with pytest.raises(ValueError):
        replace(report, scope="analysis")
    with pytest.raises(ValueError):
        validation.UnifiedArtifactValidationIssue(
            "error", "code", "message", path="/private"
        )


@pytest.mark.parametrize(
    "args,kwargs",
    [
        (("out",), {"scope": "preprocessing"}),
        ((Path("out"),), {"scope": "auto"}),
        ((Path("out"),), {"scope": "analysis", "input_artifact_paths": {"a": "file"}}),
    ],
)
def test_api_programming_misuse_raises(args, kwargs):
    with pytest.raises(ValueError):
        validation.validate_run_artifacts(*args, **kwargs)
