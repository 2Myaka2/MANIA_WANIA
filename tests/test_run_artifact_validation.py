"""Small deterministic artifact sets exercise technical integrity, never MD science."""

import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import mania.validation as validation
import mania.validation.run_artifacts as integrity
from mania.artifact_inventory import ArtifactInventory, ArtifactInventoryEntry
from mania.artifact_inventory_io import stream_file_sha256
from mania.run_provenance import PortableArtifactReference, RunProvenance
from mania.software_identity import SoftwareIdentity
from mania.validation import (
    ANALYSIS_VALIDATION_SCOPE,
    PREPROCESSING_VALIDATION_SCOPE,
    ArtifactSetValidationIssue,
    ArtifactSetValidationRecord,
    ArtifactSetValidationReport,
    validate_run_artifact_integrity,
)


def forbidden(*args, **kwargs):
    raise AssertionError("Undeclared observation or scientific validation")


def write_metadata(bundle):
    (bundle.root / bundle.provenance_path).write_text(
        json.dumps(bundle.provenance.to_dict()),
        encoding="utf-8",
    )
    (bundle.root / bundle.inventory_path).write_text(
        json.dumps(bundle.inventory.to_dict()),
        encoding="utf-8",
    )


@pytest.fixture
def artifact_set(tmp_path):
    def create(*, scope="preprocessing", mode="none", inputs=0, status="completed"):
        root = tmp_path / "run"
        prefix = "analysis/" if scope == "analysis" else ""
        output_path = prefix + "normal/output.csv"
        output = root / output_path
        output.parent.mkdir(parents=True, exist_ok=True)
        # Intentionally invalid scientific CSV: semantics belong to other validators.
        output.write_bytes(b"abc")
        local_input = tmp_path / "private-source.xtc"
        local_input.write_bytes(b"abc")
        sha = hashlib.sha256(b"abc").hexdigest() if mode == "sha256" else None
        entries = tuple(
            ArtifactInventoryEntry(
                f"input:{index}",
                "input",
                "trajectory",
                f"inputs/conditions/0001/trajectories/{index:04d}/trajectory.xtc",
                "xtc",
                3,
                sha,
                "normal",
            )
            for index in range(1, inputs + 1)
        ) + (
            ArtifactInventoryEntry(
                "output:1",
                "output",
                "table",
                output_path,
                "csv",
                3,
                sha,
                "normal",
            ),
        )
        workflow = "analysis" if scope == "analysis" else "preprocessing_graph_export"
        provenance = RunProvenance(
            "run-001",
            workflow,
            status,
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
            SoftwareIdentity(
                "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
            ),
            ("mania", "synthetic"),
            {},
            ("normal",),
            artifact_references=(
                PortableArtifactReference("table", output_path),
                PortableArtifactReference(
                    "artifact_inventory", prefix + "artifact_inventory.json"
                ),
            ),
        )
        inventory = ArtifactInventory(
            provenance.run_id,
            workflow,
            prefix + "artifact_inventory.json",
            mode,
            entries,
        )
        bundle = SimpleNamespace(
            root=root,
            output=output,
            local_input=local_input,
            scope=scope,
            provenance=provenance,
            inventory=inventory,
            provenance_path=prefix + "run_provenance.json",
            inventory_path=prefix + "artifact_inventory.json",
        )
        write_metadata(bundle)
        return bundle

    return create


def validate(bundle, **kwargs):
    return validate_run_artifact_integrity(bundle.root, scope=bundle.scope, **kwargs)


def codes(report):
    return [issue.code for issue in report.issues]


@pytest.mark.parametrize(
    "scope", [PREPROCESSING_VALIDATION_SCOPE, ANALYSIS_VALIDATION_SCOPE]
)
@pytest.mark.parametrize("status", ["completed", "failed"])
def test_exact_scope_layout_and_technical_only_result(artifact_set, scope, status):
    bundle = artifact_set(scope=scope, status=status)
    other = "analysis/" if scope == "preprocessing" else ""
    sentinels = [
        bundle.root / (other + name)
        for name in (
            "run_provenance.json",
            "artifact_inventory.json",
            "unrelated.csv",
        )
    ]
    for path in sentinels:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unrelated malformed data")
    before = {p: p.read_bytes() for p in sentinels + [bundle.output]}
    report = validate(bundle)
    assert report.status == "passed" and report.passed and report.complete
    assert report.provenance_path == bundle.provenance_path
    assert report.inventory_path == bundle.inventory_path
    assert report.run_id == bundle.provenance.run_id
    assert report.workflow == bundle.provenance.workflow
    assert report.artifact_count == report.resolved_artifact_count == 1
    assert report.issues == ()
    assert {p: p.read_bytes() for p in before} == before
    # Even a failed scientific run can pass these technical checks.
    assert "scientific" not in report.to_dict()


def test_scope_is_required_and_never_auto_detected(artifact_set):
    bundle = artifact_set(scope="analysis")
    with pytest.raises(TypeError):
        validate_run_artifact_integrity(bundle.root)
    report = validate_run_artifact_integrity(bundle.root, scope="preprocessing")
    assert report.status == "failed"
    assert codes(report) == ["provenance_read_error", "inventory_read_error"]


@pytest.mark.parametrize("scope", [None, "auto", "Analysis", "", 1])
def test_invalid_scope_rejected(tmp_path, scope):
    with pytest.raises(ValueError, match="scope"):
        validate_run_artifact_integrity(tmp_path, scope=scope)


def test_exact_path_arguments(tmp_path):
    class Derived(type(Path())):
        pass

    for path in (str(tmp_path), None, Derived(tmp_path)):
        with pytest.raises(ValueError, match="exact Path"):
            validate_run_artifact_integrity(path, scope="preprocessing")
    for mapping in (
        [],
        {1: tmp_path},
        {"input:1": str(tmp_path)},
        {"input:1": Derived(tmp_path)},
    ):
        with pytest.raises(ValueError, match="input_artifact_paths"):
            validate_run_artifact_integrity(
                tmp_path, scope="preprocessing", input_artifact_paths=mapping
            )


@pytest.mark.parametrize("metadata", ["provenance", "inventory"])
@pytest.mark.parametrize("damage", ["missing", "malformed", "directory"])
def test_metadata_failure_is_failed_portable_report(artifact_set, metadata, damage):
    bundle = artifact_set()
    path = bundle.root / getattr(bundle, metadata + "_path")
    if damage == "malformed":
        path.write_bytes(b"{")
    else:
        path.unlink()
        if damage == "directory":
            path.mkdir()
    report = validate(bundle)
    assert report.status == "failed" and not report.passed
    assert metadata + "_read_error" in codes(report)
    assert str(bundle.root) not in json.dumps(report.to_dict())
    assert "Traceback" not in json.dumps(report.to_dict())
    if metadata == "inventory":
        assert report.checksum_mode is None and not report.complete
        assert report.artifact_records == ()


@pytest.mark.parametrize(
    "case,expected",
    [
        ("run_id", "run_id_mismatch"),
        ("workflow", "workflow_mismatch"),
        ("inventory_path", "inventory_path_mismatch"),
        ("missing_reference", "missing_inventory_reference"),
        ("duplicate_reference", "duplicate_inventory_reference"),
        ("wrong_reference", "invalid_inventory_reference"),
        ("missing_output_reference", "provenance_reference_not_in_inventory"),
        ("input_reference", "provenance_reference_not_in_inventory"),
        ("condition", "artifact_condition_not_in_run"),
    ],
)
def test_cross_record_errors(artifact_set, case, expected):
    bundle = artifact_set(inputs=1)
    if case in ("run_id", "workflow", "inventory_path"):
        value = "other/artifact_inventory.json" if case == "inventory_path" else "other"
        bundle.inventory = replace(bundle.inventory, **{case: value})
    elif case == "condition":
        bundle.inventory = replace(
            bundle.inventory,
            artifacts=(
                replace(bundle.inventory.artifacts[0], condition="unknown"),
                bundle.inventory.artifacts[1],
            ),
        )
    else:
        references = bundle.provenance.artifact_references
        if case == "missing_reference":
            references = references[:1]
        elif case == "duplicate_reference":
            references += (
                PortableArtifactReference(
                    "artifact_inventory", "other/artifact_inventory.json"
                ),
            )
        elif case == "wrong_reference":
            references = (
                references[0],
                PortableArtifactReference(
                    "artifact_inventory", "other/artifact_inventory.json"
                ),
            )
        elif case == "input_reference":
            references += (
                PortableArtifactReference(
                    "trajectory", bundle.inventory.artifacts[0].path
                ),
            )
        else:
            references += (PortableArtifactReference("other", "absent.csv"),)
        bundle.provenance = replace(bundle.provenance, artifact_references=references)
    write_metadata(bundle)
    report = validate(bundle)
    assert report.status == "failed"
    assert expected in codes(report)
    assert report.unresolved_input_count == 1


def test_inventory_output_need_not_be_provenance_reference(artifact_set):
    bundle = artifact_set()
    bundle.provenance = replace(
        bundle.provenance, artifact_references=bundle.provenance.artifact_references[1:]
    )
    write_metadata(bundle)
    assert validate(bundle).status == "passed"


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
@pytest.mark.parametrize("metadata", ["provenance", "inventory"])
def test_no_technical_metadata_entry_or_hash(
    artifact_set, monkeypatch, scope, metadata
):
    bundle = artifact_set(scope=scope, mode="sha256")
    entry = replace(
        bundle.inventory.artifacts[0], path=getattr(bundle, metadata + "_path")
    )
    if metadata == "inventory":
        # The generic model rejects self-reference at its declared root, so exercise
        # a dishonest alternate root too: D.1 must protect the actual known location.
        bundle.inventory = replace(
            bundle.inventory, inventory_path="other/artifact_inventory.json"
        )
    bundle.inventory = replace(bundle.inventory, artifacts=(entry,))
    write_metadata(bundle)
    monkeypatch.setattr(integrity, "stream_file_sha256", forbidden)
    report = validate(bundle)
    expected = (
        "provenance_inventory_cycle"
        if metadata == "provenance"
        else "inventory_self_reference"
    )
    assert expected in codes(report) and report.status == "failed"
    assert report.artifact_records == ()


def test_reader_rejects_inventory_self_entry_before_checks(artifact_set):
    bundle = artifact_set()
    target = bundle.root / bundle.inventory_path
    data = bundle.inventory.to_dict()
    data["artifacts"][0]["path"] = bundle.inventory_path
    target.write_text(json.dumps(data))
    report = validate(bundle)
    assert codes(report) == ["inventory_read_error"]
    assert report.artifact_records == ()


@pytest.mark.parametrize(
    "damage,expected",
    [
        ("missing", "artifact_missing"),
        ("directory", "artifact_not_file"),
        ("size", "artifact_size_mismatch"),
        ("checksum", "artifact_checksum_mismatch"),
    ],
)
def test_output_integrity_errors(artifact_set, damage, expected):
    bundle = artifact_set(mode="sha256" if damage == "checksum" else "none")
    if damage in ("missing", "directory"):
        bundle.output.unlink()
        if damage == "directory":
            bundle.output.mkdir()
    else:
        bundle.output.write_bytes(b"xyz" if damage == "checksum" else b"larger")
    report = validate(bundle)
    assert codes(report) == [expected]
    assert report.status == "failed" and report.complete
    record = report.artifact_records[0]
    assert record.resolution_status == "resolved"
    assert record.exists is (damage != "missing")
    assert record.sha256_checked is (damage == "checksum")


@pytest.mark.parametrize("mapped", [False, True])
def test_none_mode_only_opens_technical_metadata(artifact_set, monkeypatch, mapped):
    bundle = artifact_set(inputs=2)
    actual_open, actual_stat = Path.open, Path.stat
    allowed = {
        bundle.root / bundle.provenance_path,
        bundle.root / bundle.inventory_path,
    }
    inspected = []

    def guarded_open(path, *args, **kwargs):
        assert path in allowed
        return actual_open(path, *args, **kwargs)

    def guarded_stat(path, *args, **kwargs):
        inspected.append(path)
        assert path in allowed | {bundle.output} | (
            {bundle.local_input} if mapped else set()
        )
        return actual_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", guarded_open)
        patch.setattr(Path, "stat", guarded_stat)
        patch.setattr(integrity, "stream_file_sha256", forbidden)
        patch.setattr(hashlib, "sha256", forbidden)
        mappings = (
            {f"input:{i}": bundle.local_input for i in (1, 2)} if mapped else None
        )
        report = validate(bundle, input_artifact_paths=mappings)
    assert report.status == ("passed" if mapped else "partial")
    assert report.passed and report.complete is mapped
    assert report.unresolved_input_count == (0 if mapped else 2)
    assert all(
        not r.sha256_checked and r.sha256_matches is None
        for r in report.artifact_records
    )
    if not mapped:
        assert bundle.local_input not in inspected
        assert codes(report) == ["external_inputs_not_resolved"]
        assert report.issues[0].message == "External inputs not resolved: 2."
        for record in report.artifact_records[:2]:
            assert record.resolution_status == "not_resolved"
            assert (
                record.exists
                is record.byte_size_actual
                is record.byte_size_matches
                is None
            )


def test_declared_sha256_reuses_streaming_helper_for_mapped_inputs_and_outputs(
    artifact_set, monkeypatch
):
    bundle = artifact_set(mode="sha256", inputs=1)
    spy = Mock(wraps=stream_file_sha256)
    monkeypatch.setattr(integrity, "stream_file_sha256", spy)
    report = validate(bundle, input_artifact_paths={"input:1": bundle.local_input})
    assert report.status == "passed"
    assert [call.args[0] for call in spy.call_args_list] == [
        bundle.local_input,
        bundle.output,
    ]
    assert all(r.sha256_checked and r.sha256_matches for r in report.artifact_records)


def test_unmapped_sha256_input_is_not_hashed(artifact_set, monkeypatch):
    bundle = artifact_set(mode="sha256", inputs=1)
    spy = Mock(wraps=stream_file_sha256)
    monkeypatch.setattr(integrity, "stream_file_sha256", spy)
    report = validate(bundle)
    spy.assert_called_once_with(bundle.output)
    assert report.status == "partial" and report.passed
    assert not report.artifact_records[0].sha256_checked


@pytest.mark.parametrize(
    "error", [PermissionError("/private/secret"), ValueError("private exception repr")]
)
def test_checksum_failure_is_deterministic(artifact_set, monkeypatch, error):
    bundle = artifact_set(mode="sha256")
    monkeypatch.setattr(integrity, "stream_file_sha256", Mock(side_effect=error))
    report = validate(bundle)
    assert codes(report) == ["artifact_checksum_error"]
    assert report.issues[0].message == "Artifact SHA256 could not be verified."
    assert report.artifact_records[0].sha256_checked
    assert report.artifact_records[0].sha256_matches is None
    assert "private" not in json.dumps(report.to_dict())


@pytest.mark.parametrize(
    "damage,expected",
    [
        ("size", "artifact_size_mismatch"),
        ("checksum", "artifact_checksum_mismatch"),
        ("missing", "artifact_missing"),
        ("directory", "artifact_not_file"),
    ],
)
def test_explicit_input_mapping_integrity_errors(artifact_set, damage, expected):
    bundle = artifact_set(inputs=1, mode="sha256" if damage == "checksum" else "none")
    if damage in ("missing", "directory"):
        bundle.local_input.unlink()
        if damage == "directory":
            bundle.local_input.mkdir()
    else:
        bundle.local_input.write_bytes(b"xyz" if damage == "checksum" else b"longer")
    report = validate(bundle, input_artifact_paths={"input:1": bundle.local_input})
    assert codes(report) == [expected] and report.status == "failed"
    assert report.unresolved_input_count == 0
    assert str(bundle.local_input) not in json.dumps(report.to_dict())


@pytest.mark.parametrize("key", ["unknown", "output:1", "", "/private/unknown"])
def test_unknown_mapping_keys_fail_without_inspection_or_leaking_values(
    artifact_set, key
):
    bundle = artifact_set()
    report = validate(
        bundle, input_artifact_paths={key: bundle.root / "private-never-read"}
    )
    assert codes(report) == ["unknown_input_artifact_mapping"]
    assert report.status == "failed"
    assert "private" not in json.dumps(report.to_dict())


def test_partial_mapping_keeps_other_inputs_unresolved(artifact_set):
    bundle = artifact_set(inputs=3)
    report = validate(bundle, input_artifact_paths={"input:2": bundle.local_input})
    assert report.status == "partial" and report.passed and not report.complete
    assert report.artifact_count == 4 and report.resolved_artifact_count == 2
    assert report.unresolved_input_count == 2 and report.warning_count == 1
    assert report.artifact_records[1].byte_size_matches


def test_stat_failure_is_deterministic(artifact_set, monkeypatch):
    bundle = artifact_set()
    actual_stat = Path.stat

    def guarded_stat(path, *args, **kwargs):
        if path == bundle.output:
            raise PermissionError("/private/filesystem")
        return actual_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded_stat)
    report = validate(bundle)
    assert codes(report) == ["artifact_stat_error"] and report.status == "failed"
    assert "private" not in json.dumps(report.to_dict())


def test_no_discovery_or_specialized_validator_calls(artifact_set, monkeypatch):
    bundle = artifact_set(inputs=1)
    with monkeypatch.context() as patch:
        for module, names in (
            (Path, ("glob", "rglob", "iterdir", "resolve", "cwd", "home")),
            (os, ("walk", "scandir", "listdir", "getenv")),
            (subprocess, ("run", "Popen")),
            (
                validation,
                (
                    "validate_csv_artifact_schema",
                    "validate_condition_column",
                    "validate_graph_json",
                    "validate_global_features",
                ),
            ),
        ):
            for name in names:
                patch.setattr(module, name, forbidden)
        assert validate(bundle).status == "partial"
    tree = ast.parse(inspect.getsource(integrity))
    permitted = {
        "mania.artifact_inventory",
        "mania.artifact_inventory_io",
        "mania.run_provenance",
        "mania.run_provenance_io",
    }
    for node in ast.walk(tree):
        imports = []
        if isinstance(node, ast.Import):
            imports = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports = [node.module]
        for name in imports:
            assert name in permitted or name.split(".")[0] in sys.stdlib_module_names
        if isinstance(node, (ast.FunctionDef, ast.Name, ast.Attribute)):
            name = (
                node.name
                if isinstance(node, ast.FunctionDef)
                else node.id
                if isinstance(node, ast.Name)
                else node.attr
            )
            assert name not in {
                "validate_csv_artifact_schema",
                "validate_condition_column",
                "validate_graph_json",
                "validate_global_features",
                "validate_rg_timeseries",
            }


def test_report_serialization_order_counts_and_publication_boundary(artifact_set):
    bundle = artifact_set(inputs=1)
    report = validate(bundle)
    payload = report.to_dict()
    assert list(payload) == [
        "scope",
        "run_id",
        "workflow",
        "status",
        "provenance_path",
        "inventory_path",
        "checksum_mode",
        "artifact_records",
        "issues",
        "passed",
        "complete",
        "artifact_count",
        "resolved_artifact_count",
        "unresolved_input_count",
        "error_count",
        "warning_count",
    ]
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert json.dumps(validate(bundle).to_dict()) == json.dumps(payload)
    assert [r["artifact_id"] for r in payload["artifact_records"]] == [
        "input:1",
        "output:1",
    ]
    assert report.error_count == 0 and report.warning_count == 1
    assert [e.format for e in bundle.inventory.artifacts] == ["xtc", "csv"]
    forbidden_fields = {
        "published",
        "release_member",
        "dataset_member",
        "distribute",
        "package_include",
        "scientifically_accepted",
        "scientifically_valid",
        "publication_ready",
        "dataset_approved",
    }
    for model in (
        ArtifactSetValidationReport,
        ArtifactSetValidationRecord,
        ArtifactSetValidationIssue,
    ):
        assert forbidden_fields.isdisjoint(f.name for f in fields(model))
    for word in forbidden_fields:
        assert word not in json.dumps(payload)
    for instance in (report, report.artifact_records[0], report.issues[0]):
        with pytest.raises(FrozenInstanceError):
            instance.new_field = "changed"
    payload["artifact_records"].clear()
    assert report.artifact_count == 2
    assert set(integrity.__all__).issubset(validation.__all__)


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "info"},
        {"code": ""},
        {"message": " "},
        {"path": "/private/file"},
        {"path": "../file"},
        {"path": "C:\\private"},
        {"condition": 1},
        {"artifact_id": ""},
    ],
)
def test_issue_rejects_invalid_values(changes):
    with pytest.raises(ValueError):
        ArtifactSetValidationIssue(
            **dict(severity="error", code="code", message="Message.") | changes
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"resolution_status": "guessed"},
        {"exists": 1},
        {"path": "/private"},
        {"byte_size_expected": True},
        {"byte_size_actual": -1},
        {"byte_size_matches": False},
        {"sha256_checked": 1},
        {"sha256_checked": True},
        {"sha256_matches": True},
        {"resolution_status": "not_resolved"},
    ],
)
def test_record_rejects_inconsistent_values(artifact_set, changes):
    record = validate(artifact_set()).artifact_records[0]
    with pytest.raises(ValueError):
        replace(record, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "auto"},
        {"inventory_path": "/private"},
        {"checksum_mode": "other"},
        {"issues": []},
        {"artifact_records": []},
        {"run_id": None},
    ],
)
def test_report_rejects_invalid_values(artifact_set, changes):
    report = validate(artifact_set())
    with pytest.raises(ValueError):
        replace(report, **changes)
