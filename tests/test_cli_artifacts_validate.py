"""Minimal CLI surface, deterministic JSON, and real technical validation."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_unified_artifact_validation import (
    csv_bytes,
    forbid,
    graph_bytes,
    guard_validation,
    make_bundle,
)

import mania.cli as cli
from mania.validation import artifacts, unified


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["mania", *map(str, args)])
    try:
        cli.main()
    except SystemExit as exc:
        code = exc.code
    else:
        code = 0
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize("args", [(), ("artifacts",), ("artifacts", "validate")])
def test_help_documents_command_and_boundary(monkeypatch, capsys, args):
    code, out, err = run_cli(monkeypatch, capsys, *args, "--help")
    assert code == 0 and err == ""
    if not args:
        assert "mania artifacts validate" in " ".join(out.split())
    elif len(args) == 1:
        assert "validate" in out
    else:
        text = " ".join(out.split())
        for phrase in (
            "Technical artifact/integrity validation",
            "explicit --scope",
            "mappings are optional",
            "partial (exit 0)",
            "does not certify scientific correctness or publication readiness",
        ):
            assert phrase in text
        for flag in (
            "checksum",
            "--auto",
            "--strict",
            "--require-complete",
            "--publication",
            "--scientific",
            "--skip-",
        ):
            assert flag not in text


@pytest.mark.parametrize(
    "tail",
    [
        (),
        ("run",),
        ("--scope", "preprocessing"),
        ("run", "--scope", "auto"),
        ("run", "--scope", "other"),
        *[
            ("run", "--scope", "analysis", "--input-artifact-path", mapping)
            for mapping in ("id", "=path", "id=", "=")
        ],
        (
            "run",
            "--scope",
            "analysis",
            "--input-artifact-path",
            "id=one",
            "--input-artifact-path",
            "id=two",
        ),
        *[
            ("run", "--scope", "analysis", flag)
            for flag in (
                "--checksum",
                "--artifact-checksum-mode",
                "--auto-scope",
                "--strict",
            )
        ],
    ],
)
def test_parser_errors_exit_two_without_report(monkeypatch, capsys, tail):
    monkeypatch.setattr(cli, "validate_run_artifacts", forbid)
    code, out, err = run_cli(monkeypatch, capsys, "artifacts", "validate", *tail)
    assert code == 2 and out == "" and "error:" in err


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
def test_mapping_parsed_at_first_equals_without_filesystem_access(monkeypatch, scope):
    parser = cli.build_parser()
    with monkeypatch.context() as patch:
        for name in ("stat", "exists", "open", "glob", "rglob", "iterdir", "resolve"):
            patch.setattr(Path, name, forbid)
        args = parser.parse_args(
            [
                "artifacts",
                "validate",
                "run",
                "--scope",
                scope,
                "--input-artifact-path",
                "unknown:1=one=two.csv",
                "--input-artifact-path",
                "unknown:2=other path.csv",
            ]
        )
    assert args.run_root == Path("run") and args.scope == scope
    assert args.input_artifact_paths == {
        "unknown:1": Path("one=two.csv"),
        "unknown:2": Path("other path.csv"),
    }
    assert (
        parser.parse_args(
            [
                "artifacts",
                "validate",
                "run",
                "--scope",
                scope,
            ]
        ).input_artifact_paths
        is None
    )


@pytest.mark.parametrize(
    "status,expected", [("passed", 0), ("partial", 0), ("failed", 1)]
)
def test_one_sorted_json_line_exit_status_and_mapping_forwarding(
    monkeypatch, capsys, status, expected
):
    payload = {"status": status, "passed": status == "failed", "scope": "analysis"}
    report = SimpleNamespace(
        status=status, passed=status == "failed", to_dict=lambda: payload
    )
    spy = Mock(return_value=report)
    monkeypatch.setattr(cli, "validate_run_artifacts", spy)
    code, out, err = run_cli(
        monkeypatch,
        capsys,
        "artifacts",
        "validate",
        "run",
        "--scope",
        "analysis",
        "--input-artifact-path",
        "id=one=two.csv",
        "--input-artifact-path",
        "id2=two.csv",
    )
    assert code == expected and err == ""
    assert out == json.dumps(payload, sort_keys=True) + "\n"
    assert len(out.splitlines()) == 1
    spy.assert_called_once_with(
        Path("run"),
        scope="analysis",
        input_artifact_paths={"id": Path("one=two.csv"), "id2": Path("two.csv")},
    )


def test_unexpected_internal_failure_is_deterministic(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "validate_run_artifacts", Mock(side_effect=RuntimeError("/private/path"))
    )
    code, out, err = run_cli(
        monkeypatch, capsys, "artifacts", "validate", "run", "--scope", "analysis"
    )
    assert code == 1 and out == ""
    assert err == "Artifact validation failed: unexpected internal error.\n"
    assert "Traceback" not in err and "/private" not in err


@pytest.mark.parametrize("scope", ["preprocessing", "analysis"])
def test_real_cli_partial_passed_and_corruption_read_only(
    tmp_path, monkeypatch, capsys, scope
):
    content = csv_bytes(unified._csv_contracts()["residue_table"], "normal")
    inputs = (
        (("condition_trajectory", b"synthetic-xtc", "normal"),)
        if scope == "preprocessing"
        else (("residue_table", content, "normal"),)
    )
    outputs = (
        None
        if scope == "preprocessing"
        else (
            ("analysis_graph", graph_bytes(), "normal"),
            (
                "analysis_centrality",
                csv_bytes(unified._csv_contracts()["centrality"], "normal"),
                "normal",
            ),
        )
    )
    bundle = make_bundle(tmp_path / "run", scope=scope, inputs=inputs, outputs=outputs)
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
        path.write_bytes(b"malformed and ignored")
    paths = (
        list(bundle.paths.values())
        + sentinels
        + [
            bundle.root / bundle.inventory_path,
            bundle.root / bundle.provenance_path,
        ]
    )
    before = {p: p.read_bytes() for p in paths}
    base = ("artifacts", "validate", bundle.root, "--scope", scope)
    mapping_args = tuple(
        value
        for identity, path in bundle.mappings.items()
        for value in ("--input-artifact-path", f"{identity}={path}")
    )
    for expected, args in (("partial", base), ("passed", base + mapping_args)):
        with monkeypatch.context() as patch:
            guard_validation(patch)
            code, out, err = run_cli(patch, capsys, *args)
        assert code == 0 and err == ""
        payload = json.loads(out)
        assert payload["status"] == expected and payload["scope"] == scope
        assert payload["passed"] and payload["complete"] == (expected == "passed")
        assert str(tmp_path) not in out
    assert before == {p: p.read_bytes() for p in paths}
    bundle.paths["output:0"].write_bytes(b"broken")
    code, out, err = run_cli(monkeypatch, capsys, *base, *mapping_args)
    assert code == 1 and err == "" and json.loads(out)["status"] == "failed"
    output_record = next(
        r for r in json.loads(out)["specialized_records"]
        if r["artifact_id"] == "output:0"
    )
    assert output_record["status"] == "skipped_integrity_failure"


def test_specialized_failure_with_intact_declared_sha256(tmp_path, monkeypatch, capsys):
    bundle = make_bundle(
        tmp_path / "run",
        mode="sha256",
        outputs=(("residue_table", b"wrong header\n", "normal"),),
    )
    spy = Mock(wraps=artifacts.validate_csv_artifact_schema)
    monkeypatch.setattr(artifacts, "validate_csv_artifact_schema", spy)
    code, out, err = run_cli(
        monkeypatch,
        capsys,
        "artifacts",
        "validate",
        bundle.root,
        "--scope",
        "preprocessing",
    )
    payload = json.loads(out)
    assert code == 1 and err == "" and payload["status"] == "failed"
    assert payload["integrity_report"]["status"] == "passed"
    spy.assert_called_once()
    assert payload["specialized_failed_count"] == 1
    assert str(tmp_path) not in out
    spy.reset_mock()
    bundle.paths["output:0"].write_bytes(b"other header\n")
    code, out, err = run_cli(
        monkeypatch,
        capsys,
        "artifacts",
        "validate",
        bundle.root,
        "--scope",
        "preprocessing",
    )
    assert code == 1 and err == "" and json.loads(out)["status"] == "failed"
    assert (
        json.loads(out)["specialized_records"][0]["status"]
        == "skipped_integrity_failure"
    )
    spy.assert_not_called()


def test_unknown_mapping_id_is_validation_error_not_parser_error(
    tmp_path, monkeypatch, capsys
):
    bundle = make_bundle(tmp_path / "run")
    code, out, err = run_cli(
        monkeypatch,
        capsys,
        "artifacts",
        "validate",
        bundle.root,
        "--scope",
        "preprocessing",
        "--input-artifact-path",
        "unknown=file",
    )
    assert code == 1 and err == ""
    assert (
        json.loads(out)["integrity_report"]["issues"][0]["code"]
        == "unknown_input_artifact_mapping"
    )
