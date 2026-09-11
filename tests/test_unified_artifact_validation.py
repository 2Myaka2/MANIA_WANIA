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
        parameter_table_local_path=tmp_path / "parameters.csv",
        molecular_partner_metadata_paths=(("normal", tmp_path / "partners.json"),),
        include_reference_inputs=True,
        reference_nodes_path=options.reference_nodes_csv_path,
        reference_edges_path=options.reference_edges_csv_path,
        reference_graph_path=options.reference_graph_json_path,
    ) + preprocessing_adapter.collect_preprocessing_output_file_specs(
        output_root=root,
        runtime_metadata_path=root / "runtime_metadata.json",
        temporal_execution_path=root / "temporal_execution.json",
        molecular_partner_catalog_path=root / "molecular_partner_catalog.json",
        protein_lipid_contacts_by_window_source_path=root
        / "protein_lipid_contacts_by_window_source.csv",
        protein_glycan_contacts_by_window_source_path=root
        / "protein_glycan_contacts_by_window_source.csv",
        protein_edges_by_window_source_path=root / "protein_edges_by_window_source.csv",
        pbc_audit_path=root / "pbc_audit.json",
        **stages,
    )
    request = AnalyzeRequest(tmp_path / "in", root, ("normal", "tumor"))
    analysis = analysis_adapter.collect_analysis_input_file_specs(
        request=request,
        resolved_input_paths=declared_inputs(request),
    ) + analysis_adapter.collect_analysis_output_file_specs(
        analysis_result(request),
        runtime_metadata_path=root / "analysis/runtime_metadata.json",
    )
    assert {e.role for e in prep} == unified._PREPROCESSING_POLICY.keys()
    assert {e.role for e in analysis} == unified._ANALYSIS_POLICY.keys()
    assert len({e.role for e in prep}) == 30
    assert len({e.role for e in analysis}) == 17


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


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
@pytest.mark.parametrize("damage", [None, "schema", "scope", "path", "environment"])
def test_runtime_metadata_strict_dispatch_and_scope_path(
    tmp_path, monkeypatch, scope, damage,
):
    from test_runtime_metadata import metadata_model

    portable = ("analysis/" if scope == "analysis" else "") + "runtime_metadata.json"
    payload = metadata_model(scope=scope, metadata_path=portable).to_dict()
    if damage == "schema":
        payload["schema_version"] = "future"
    elif damage == "scope":
        payload["scope"] = "analysis" if scope == "preprocessing" else "preprocessing"
    elif damage == "path":
        payload["metadata_path"] = "nested/runtime_metadata.json"
    elif damage == "environment":
        payload["environment"]["python_version"] = 3
    bundle = make_bundle(tmp_path, scope=scope, outputs=(
        ("runtime_metadata", json.dumps(payload).encode(), None),
    ))
    reader = Mock(wraps=unified.read_runtime_metadata)
    monkeypatch.setattr(unified, "read_runtime_metadata", reader)
    with monkeypatch.context() as patch:
        guard_validation(patch)
        report = validate(bundle)
    reader.assert_called_once_with(bundle.paths["output:0"])
    assert report.unsupported_count == 0
    assert report.status == ("failed" if damage else "passed")
    assert report.specialized_records[0].validator == "read_runtime_metadata"
    assert report.specialized_records[0].status == report.status


@pytest.mark.parametrize("boxes", [(), (None,), ((0, 20, 30, 90, 90, 90),),
                                   ((10, 20, 30, 90, 90, 90), None)])
def test_pbc_metadata_status_never_fails_technical_validation(tmp_path, boxes):
    from test_preprocessing_pbc_audit import audit, observe

    payload = audit(observations=tuple(observe(box, index=i)
                                       for i, box in enumerate(boxes))).to_dict()
    bundle = make_bundle(
        tmp_path, outputs=(("pbc_audit", json.dumps(payload).encode(), None),),
    )
    report = validate(bundle)
    assert report.status == "passed" and report.complete
    assert report.issues == () and report.unsupported_count == 0
    assert report.specialized_records[0].validator == "read_pbc_audit"
    assert report.specialized_records[0].status == "passed"


@pytest.mark.parametrize("field,value", [
    ("scientific_pbc_status", "approved"),
    ("mania_internal_minimum_image_correction_applied", True),
    ("audit_path", "nested/pbc_audit.json"),
])
def test_invalid_pbc_claims_and_path_are_technical_failures(tmp_path, field, value):
    from test_preprocessing_pbc_audit import audit

    payload = audit().to_dict()
    payload[field] = value
    bundle = make_bundle(
        tmp_path, outputs=(("pbc_audit", json.dumps(payload).encode(), None),),
    )
    report = validate(bundle)
    assert report.status == "failed" and report.specialized_failed_count == 1
    assert report.issues[0].code == "specialized_validation_failed"


def test_analysis_does_not_support_pbc_audit_role(tmp_path):
    from test_preprocessing_pbc_audit import audit

    bundle = make_bundle(tmp_path, scope="analysis", outputs=(
        ("pbc_audit", json.dumps(audit().to_dict()).encode(), None),
    ))
    report = validate(bundle)
    assert report.status == "partial" and report.unsupported_count == 1


def dataset_bundle(root, *, source="parameter_table", table=True, context=True):
    from test_preprocessing_dataset_binding import spec, table_bytes

    from mania.preprocessing.dataset_binding import (
        PreprocessingDatasetBinding,
        PreprocessingDatasetContext,
    )

    value = spec(condition="normal")
    value = value.model_copy(
        update={
            "temporal": value.temporal.model_copy(
                update={
                    "window_length_ns": 7.4,
                    "overlap_percent": 50.0,
                }
            )
        }
    )
    bundle = make_bundle(
        root,
        inputs=(
            (
                (
                    "dataset_parameter_table",
                    table_bytes(
                        spec(condition="normal", replica_id="unused"),
                        value,
                    ),
                    None,
                ),
            )
            if table
            else ()
        ),
    )
    if context:
        dataset_context = PreprocessingDatasetContext(
            bindings=(
                PreprocessingDatasetBinding(
                    execution_condition="normal",
                    source=source,
                    dataset_spec=value,
                ),
            )
        )
        bundle.provenance = replace(
            bundle.provenance,
            resolved_configuration={
                "dataset_context": dataset_context.to_dict(),
            },
        )
        from test_preprocessing_physical_time_execution import loading

        from mania.preprocessing.physical_time_execution import (
            build_preprocessing_temporal_execution,
        )
        from mania.preprocessing.physical_time_execution_io import (
            write_preprocessing_temporal_execution,
        )

        runtime, _ = loading((125,))
        execution = build_preprocessing_temporal_execution(runtime, dataset_context)
        written = write_preprocessing_temporal_execution(execution, root)
        content = written.output_path.read_bytes()
        entry = ArtifactInventoryEntry(
            "output:temporal_execution",
            "output",
            "temporal_execution",
            "temporal_execution.json",
            "json",
            len(content),
            None,
            None,
        )
        bundle.inventory = replace(
            bundle.inventory,
            artifacts=(*bundle.inventory.artifacts, entry),
        )
        bundle.paths[entry.artifact_id] = written.output_path
        bundle.provenance = replace(
            bundle.provenance,
            artifact_references=(
                *bundle.provenance.artifact_references,
                PortableArtifactReference(
                    "temporal_execution", "temporal_execution.json"
                ),
            ),
        )
        write_metadata(bundle)
    return bundle


def test_inline_dataset_context_technical_validation(tmp_path):
    bundle = dataset_bundle(tmp_path / "run", source="inline_manifest", table=False)
    report = validate(bundle)
    assert report.status == "passed" and report.complete
    assert report.unsupported_count == 0


@pytest.mark.parametrize("value", [None, {}, {"bindings": []}])
def test_malformed_dataset_context_fails(tmp_path, value):
    bundle = dataset_bundle(tmp_path / "run", table=False)
    bundle.provenance = replace(
        bundle.provenance, resolved_configuration={"dataset_context": value}
    )
    write_metadata(bundle)
    report = validate(bundle)
    assert report.status == "failed"
    assert "dataset_context_invalid" in [issue.code for issue in report.issues]


@pytest.mark.parametrize(
    "table,context,source",
    [
        (False, True, "parameter_table"),
        (True, False, "parameter_table"),
        (True, True, "inline_manifest"),
    ],
)
def test_dataset_lineage_consistency_both_directions(tmp_path, table, context, source):
    bundle = dataset_bundle(
        tmp_path / "run", table=table, context=context, source=source
    )
    report = validate(bundle, mapped=True)
    assert report.status == "failed"
    assert "dataset_parameter_table_lineage_mismatch" in [i.code for i in report.issues]


@pytest.mark.parametrize("source", ["parameter_table", "inline_and_parameter_table"])
def test_dataset_table_specialized_and_exact_semantic_validation(
    tmp_path, monkeypatch, source
):
    bundle = dataset_bundle(tmp_path / "run", source=source)
    reader = Mock(wraps=unified.read_dataset_parameter_table_csv)
    monkeypatch.setattr(unified, "read_dataset_parameter_table_csv", reader)
    report = validate(bundle)
    assert report.status == "partial" and not report.complete
    assert (
        next(
            r for r in report.specialized_records if r.role == "dataset_parameter_table"
        ).status
        == "not_resolved"
    )
    reader.assert_not_called()
    report = validate(bundle, mapped=True)
    assert report.status == "passed" and report.complete
    assert report.unsupported_count == 0
    reader.assert_called_once_with(bundle.mappings["input:0"])
    table_record = next(
        r for r in report.specialized_records if r.role == "dataset_parameter_table"
    )
    assert table_record.status == "passed"
    assert table_record.validator == "read_dataset_parameter_table_csv"


@pytest.mark.parametrize(
    "change", ["temporal", "missing", "invalid", "engine", "condition", "disulfide"]
)
def test_mapped_table_tampering_fails_without_checksums(tmp_path, change):
    bundle = dataset_bundle(tmp_path / "run")
    path = bundle.mappings["input:0"]
    original = path.read_bytes()
    replacements = {
        "temporal": (b"17.3", b"19.3"),
        "missing": (b",A,", b",B,"),
        "invalid": (b"dataset_id", b"dataset_zz"),
        "engine": (b"gromacs", b"namd   "),
        "condition": (b",normal,", b",tumor ,"),
        "disulfide": (b",A,,", b",A,X,"),
    }
    changed = original.replace(*replacements[change])
    assert original != changed
    if change == "disulfide":
        # Preserve size to isolate semantic checking from the integrity gate.
        changed = changed.replace(b"unused", b"unuse", 1)
    assert len(changed) == len(original)
    path.write_bytes(changed)
    report = validate(bundle, mapped=True)
    assert report.integrity_report.status == "passed"
    assert report.status == "failed" and not report.complete
    assert report.unsupported_count == 0
    assert any(
        r.role == "dataset_parameter_table" and r.status == "failed"
        for r in report.specialized_records
    )
    assert str(path) not in str(report.to_dict())


@pytest.mark.parametrize(
    "damage", ["no_context", "no_reference", "no_entry", "no_file"]
)
def test_temporal_execution_bidirectional_lineage(tmp_path, damage):
    bundle = dataset_bundle(tmp_path / "run", source="inline_manifest", table=False)
    if damage == "no_context":
        bundle.provenance = replace(bundle.provenance, resolved_configuration={})
    elif damage == "no_reference":
        bundle.provenance = replace(
            bundle.provenance,
            artifact_references=tuple(
                r
                for r in bundle.provenance.artifact_references
                if r.role != "temporal_execution"
            ),
        )
    elif damage == "no_entry":
        bundle.inventory = replace(
            bundle.inventory,
            artifacts=tuple(
                e for e in bundle.inventory.artifacts if e.role != "temporal_execution"
            ),
        )
    else:
        (bundle.root / "temporal_execution.json").unlink()
    write_metadata(bundle)
    report = validate(bundle)
    assert report.status == "failed"
    assert report.unsupported_count == 0


@pytest.mark.parametrize("damage", ["spec", "sampling", "windows", "nested"])
def test_temporal_execution_strict_semantic_validation_without_checksums(
    tmp_path, damage
):
    bundle = dataset_bundle(tmp_path / "run", source="inline_manifest", table=False)
    path = bundle.root / "temporal_execution.json"
    payload = json.loads(path.read_text())
    binding = payload["bindings"][0]
    if damage == "spec":
        binding["dataset_spec"]["identity"]["variant_id"] = "tampered"
    elif damage == "sampling":
        binding["sampling_plan"]["requested_frame_stride_ps"] = 19.3
    elif damage == "windows":
        binding["window_plan"]["requested_window_step_ns"] = 3.8
    else:
        binding["sampling_plan"]["selected_samples"][0]["time_delta_ps"] = 1.0
    content = json.dumps(payload).encode()
    path.write_bytes(content)
    bundle.inventory = replace(
        bundle.inventory,
        artifacts=tuple(
            replace(e, byte_size=len(content)) if e.role == "temporal_execution" else e
            for e in bundle.inventory.artifacts
        ),
    )
    write_metadata(bundle)
    report = validate(bundle)
    assert report.integrity_report.status == "passed"
    assert report.status == "failed" and report.unsupported_count == 0
    assert any(
        r.role == "temporal_execution" and r.status == "failed"
        for r in report.specialized_records
    )


@pytest.mark.parametrize("count", [1, 2])
def test_temporal_pbc_count_cross_check_preserves_unresolved_status(tmp_path, count):
    from test_preprocessing_pbc_audit import audit, observe

    bundle = dataset_bundle(tmp_path / "run", source="inline_manifest", table=False)
    payload = audit(
        observations=tuple(observe(None, index=i) for i in range(count))
    ).to_dict()
    assert payload["scientific_pbc_status"] == "unresolved"
    content = json.dumps(payload).encode()
    path = bundle.root / "pbc_audit.json"
    path.write_bytes(content)
    bundle.inventory = replace(
        bundle.inventory,
        artifacts=(
            *bundle.inventory.artifacts,
            ArtifactInventoryEntry(
                "output:pbc_audit",
                "output",
                "pbc_audit",
                "pbc_audit.json",
                "json",
                len(content),
                None,
                None,
            ),
        ),
    )
    bundle.provenance = replace(
        bundle.provenance,
        artifact_references=(
            *bundle.provenance.artifact_references,
            PortableArtifactReference("pbc_audit", "pbc_audit.json"),
        ),
    )
    write_metadata(bundle)
    report = validate(bundle)
    assert report.status == ("passed" if count == 1 else "failed"), report.to_dict()
    assert (
        "temporal_execution_pbc_count_mismatch" in [i.code for i in report.issues]
    ) == (count != 1)


def protein_window_bundle(root, *, empty=False, condition=None):
    from test_preprocessing_protein_edge_window_execution import (
        build,
        manifest,
        retained,
    )

    from mania.preprocessing.dataset_binding import (
        PreprocessingDatasetBinding,
        PreprocessingDatasetContext,
    )
    from mania.preprocessing.physical_time_execution import (
        PreprocessingTemporalExecution,
    )
    from mania.preprocessing.physical_time_execution_io import (
        write_preprocessing_temporal_execution,
    )
    from mania.preprocessing.protein_edge_window_table_io import (
        write_dataset_protein_edge_window_csv,
    )

    binding, contacts = retained(
        condition=condition,
        engine="namd",
        route="normal",
        positive=() if empty else (0, 1, 3, 4),
    )
    temporal = PreprocessingTemporalExecution((binding,))
    bundle = make_bundle(
        root, outputs=(), inputs=(("condition_topology", b"small", "normal"),)
    )
    context = PreprocessingDatasetContext(
        bindings=(
            PreprocessingDatasetBinding(
                execution_condition="normal",
                source="inline_manifest",
                dataset_spec=binding.dataset_spec,
            ),
        )
    )
    bundle.provenance = replace(
        bundle.provenance,
        resolved_configuration={
            "dataset_context": context.to_dict(),
            "include_contacts": True,
            "contact_detection_options": {"contact_selection": "protein"},
        },
    )
    source = write_dataset_protein_edge_window_csv(
        build(temporal, manifest(contacts)), root
    )
    resolved = write_preprocessing_temporal_execution(temporal, root)
    for role, result, fmt in (
        ("protein_edges_by_window_source", source, "csv"),
        ("temporal_execution", resolved, "json"),
    ):
        assert result.passed
        path = result.output_path
        entry = ArtifactInventoryEntry(
            f"output:{role}",
            "output",
            role,
            path.name,
            fmt,
            path.stat().st_size,
            None,
            None,
        )
        bundle.inventory = replace(
            bundle.inventory, artifacts=(*bundle.inventory.artifacts, entry)
        )
        bundle.provenance = replace(
            bundle.provenance,
            artifact_references=(
                *bundle.provenance.artifact_references,
                PortableArtifactReference(role, path.name),
            ),
        )
    write_metadata(bundle)
    return bundle


def remove_window_role(bundle, role, *, inventory=True, provenance=True, file=True):
    if inventory:
        bundle.inventory = replace(
            bundle.inventory,
            artifacts=tuple(e for e in bundle.inventory.artifacts if e.role != role),
        )
    if provenance:
        bundle.provenance = replace(
            bundle.provenance,
            artifact_references=tuple(
                r for r in bundle.provenance.artifact_references if r.role != role
            ),
        )
    if file:
        suffix = "csv" if role == "protein_edges_by_window_source" else "json"
        (bundle.root / f"{role}.{suffix}").unlink()
    write_metadata(bundle)


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("condition", [None, "normal"])
def test_source_table_complete_sparse_and_nullable_context(tmp_path, empty, condition):
    bundle = protein_window_bundle(tmp_path, empty=empty, condition=condition)
    report = validate(bundle, mapped=True)
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    record = next(
        r
        for r in report.specialized_records
        if r.role == "protein_edges_by_window_source"
    )
    assert record.validator == "read_dataset_protein_edge_window_csv"
    assert record.status == "passed"


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "reference",
        "inventory",
        "file",
        "context",
        "temporal",
        "duplicate_reference",
        "duplicate_inventory",
        "legacy_unlisted",
    ],
)
def test_source_table_lineage_both_directions(tmp_path, damage):
    role = "protein_edges_by_window_source"
    bundle = protein_window_bundle(tmp_path)
    if damage in ("missing", "reference", "inventory", "file", "legacy_unlisted"):
        remove_window_role(
            bundle,
            role,
            inventory=damage in ("missing", "inventory", "legacy_unlisted"),
            provenance=damage in ("missing", "reference", "legacy_unlisted"),
            file=damage in ("missing", "file"),
        )
    if damage in ("context", "legacy_unlisted"):
        config = bundle.provenance.to_dict()["resolved_configuration"]
        config.pop("dataset_context")
        bundle.provenance = replace(bundle.provenance, resolved_configuration=config)
    if damage == "temporal":
        remove_window_role(bundle, "temporal_execution")
    if damage == "duplicate_reference":
        # Generic schema already rejects exact duplicates; a second portable path
        # still represents an ambiguous specialized reference.
        bundle.provenance = replace(
            bundle.provenance,
            artifact_references=(
                *bundle.provenance.artifact_references,
                PortableArtifactReference(role, "other.csv"),
            ),
        )
    if damage == "duplicate_inventory":
        entry = next(e for e in bundle.inventory.artifacts if e.role == role)
        bundle.inventory = replace(
            bundle.inventory,
            artifacts=(
                *bundle.inventory.artifacts,
                replace(entry, artifact_id="output:other", path="other.csv"),
            ),
        )
    write_metadata(bundle)
    report = validate(bundle, mapped=True)
    assert report.status == "failed" and not report.complete


@pytest.mark.parametrize(
    "status,contacts,selection",
    [
        ("completed", False, "protein"),
        ("completed", True, "all"),
        ("failed", True, "protein"),
    ],
)
def test_source_table_conditional_absence_and_failed_run_exception(
    tmp_path, status, contacts, selection
):
    bundle = protein_window_bundle(tmp_path)
    remove_window_role(bundle, "protein_edges_by_window_source")
    config = bundle.provenance.to_dict()["resolved_configuration"]
    config["include_contacts"] = contacts
    config["contact_detection_options"]["contact_selection"] = selection
    bundle.provenance = replace(
        bundle.provenance, status=status, resolved_configuration=config
    )
    write_metadata(bundle)
    report = validate(bundle, mapped=True)
    assert report.status == "passed" and report.complete, report.to_dict()


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset_id": "other"},
        {"system_id": "other"},
        {"trajectory_id": "other"},
        {"replica_id": "other"},
        {"variant_id": "other"},
        {"engine": "gromacs"},
        {"condition": "normal"},
        {"disulfide_state": "other"},
        {"window_id": "window_9999"},
        {"window_index": "9"},
        {"requested_window_start_ns": "4.0"},
        {"requested_window_end_ns": "6.0"},
        {"right_endpoint_inclusive": "true"},
        {"effective_window_start_ns": "4.9"},
        {"effective_window_end_ns": "5.21"},
        {
            "requested_sample_count": "6",
            "missing_sample_count": "1",
            "coverage_fraction": str(5 / 6),
        },
        {
            "resolved_frame_count": "4",
            "missing_sample_count": "1",
            "coverage_fraction": "0.8",
            "occupancy": "1.0",
            "edge_weight": "1.0",
        },
        {"coverage_fraction": "0.9"},
        {"occupancy": "0.7"},
        {"edge_weight": "0.7"},
        {"n_contact_frames": "0"},
        {"n_contact_episodes": "0"},
    ],
)
def test_source_table_strict_rows_and_temporal_cross_checks(tmp_path, changes):
    import csv

    bundle = protein_window_bundle(tmp_path)
    path = tmp_path / "protein_edges_by_window_source.csv"
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = list(reader)
    rows[0].update(changes)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    bundle.inventory = replace(
        bundle.inventory,
        artifacts=tuple(
            replace(e, byte_size=path.stat().st_size)
            if e.role == "protein_edges_by_window_source"
            else e
            for e in bundle.inventory.artifacts
        ),
    )
    write_metadata(bundle)
    report = validate(bundle, mapped=True)
    assert report.status == "failed", report.to_dict()
    assert (
        next(
            r
            for r in report.specialized_records
            if r.role == "protein_edges_by_window_source"
        ).status
        == "failed"
    )


def test_malformed_source_header_is_strict_failure(tmp_path):
    bundle = protein_window_bundle(tmp_path)
    path = tmp_path / "protein_edges_by_window_source.csv"
    content = path.read_bytes().replace(b"dataset_id", b"unknown_id", 1)
    path.write_bytes(content)
    report = validate(bundle, mapped=True)
    assert report.status == "failed"
    assert (
        next(
            r
            for r in report.specialized_records
            if r.role == "protein_edges_by_window_source"
        ).status
        == "failed"
    )
