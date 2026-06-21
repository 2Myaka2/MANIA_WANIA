"""Opt-in local real-MD smoke test for the Stage 15 graph workflow CLI."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from _harness import ENABLED_VALUES, mdanalysis_available

import mania.cli as cli
from mania.preprocessing import (
    load_preprocessing_input_manifest,
    validate_preprocessing_manifest_paths,
)

pytestmark = pytest.mark.local_scientific

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_SOURCE_PATH = Path(__file__).resolve()
LOCAL_SCIENTIFIC_DOC_PATH = REPO_ROOT / "docs" / (
    "local_scientific_integration_tests.md"
)
LOCAL_MD_SMOKE_ENV = "MANIA_RUN_LOCAL_MD_SMOKE"
LOCAL_MANIFEST_RELATIVE_PATH = (
    Path("local_md") / "manifests" / "napi2b_10ns.yaml"
)
LOCAL_MANIFEST_PATH = REPO_ROOT / LOCAL_MANIFEST_RELATIVE_PATH
EXPECTED_MANIFEST_PATHS = {
    "normal": {
        "topology_path": Path("../normal/topology.tpr"),
        "trajectory_paths": (Path("../normal/trajectory.xtc"),),
    },
    "tumor": {
        "topology_path": Path("../tumor/topology.tpr"),
        "trajectory_paths": (Path("../tumor/trajectory.xtc"),),
    },
}


def test_local_md_smoke_skip_reason_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(LOCAL_MD_SMOKE_ENV, raising=False)

    reason = _local_md_smoke_skip_reason(
        manifest_path=tmp_path / "missing.yaml",
    )

    assert reason == (
        "local MD smoke test is disabled; set MANIA_RUN_LOCAL_MD_SMOKE=1"
    )


def test_local_md_smoke_skip_reason_reports_missing_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LOCAL_MD_SMOKE_ENV, "1")
    manifest_path = tmp_path / "missing.yaml"

    reason = _local_md_smoke_skip_reason(manifest_path=manifest_path)

    assert reason == f"local MD smoke manifest is missing: {manifest_path}"


def test_local_md_smoke_skip_reason_reports_missing_raw_md_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LOCAL_MD_SMOKE_ENV, "1")
    manifest_path = _write_smoke_manifest(tmp_path)

    reason = _local_md_smoke_skip_reason(manifest_path=manifest_path)

    assert reason is not None
    assert reason.startswith("local MD smoke raw MD files are unavailable:")
    assert "conditions[normal].topology_path" in reason


def test_local_md_smoke_skip_reason_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LOCAL_MD_SMOKE_ENV, "1")
    manifest_path = _write_smoke_manifest(tmp_path)
    _write_required_raw_md_placeholders(tmp_path)

    reason = _local_md_smoke_skip_reason(
        manifest_path=manifest_path,
        mdanalysis_is_available=False,
    )

    assert reason == (
        "MDAnalysis is unavailable; install the optional md or science extra"
    )


def test_local_md_smoke_implementation_uses_explicit_manifest_only() -> None:
    source = TEST_SOURCE_PATH.read_text(encoding="utf-8")

    assert "LOCAL_MANIFEST_RELATIVE_PATH" in source
    assert "local_md" in source
    assert "napi2b_10ns.yaml" in source
    for forbidden in (
        "gl" + "ob(",
        "rg" + "lob(",
        "os." + "walk",
        "MANIA_LOCAL_" + "REFERENCE_PACKAGE",
        "data/" + "local_md",
        "data/" + "reference",
    ):
        assert forbidden not in source


def test_local_md_smoke_implementation_does_not_run_notebook_tools() -> None:
    source = TEST_SOURCE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "nb" + "convert",
        "ju" + "pyter",
        "paper" + "mill",
        "execute_" + "notebook",
    ):
        assert forbidden not in source


def test_local_md_smoke_implementation_keeps_future_scopes_disabled() -> None:
    source = TEST_SOURCE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "--enable-" + "reference-comparison",
        "temporal_" + "rin",
        "temporal " + "RIN",
        "frontend_" + "payload",
        "export_" + "frontend",
        "WANIA " + "frontend",
    ):
        assert forbidden not in source


def test_local_scientific_docs_describe_stage_15_9_smoke() -> None:
    strategy_text = LOCAL_SCIENTIFIC_DOC_PATH.read_text(encoding="utf-8")

    for term in (
        "local_md/manifests/napi2b_10ns.yaml",
        "MANIA_RUN_LOCAL_MD_SMOKE",
        "skipped by default",
        "Default CI does not run this test",
        "raw MD files",
        "must not be committed",
    ):
        assert term in strategy_text


def test_run_graph_export_cli_against_local_real_md(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    skip_reason = _local_md_smoke_skip_reason()
    if skip_reason is not None:
        pytest.skip(skip_reason)

    output_dir = tmp_path / "napi2b_10ns_graph_workflow"

    exit_code, stdout, stderr = _run_graph_export_cli(
        monkeypatch,
        capsys,
        manifest_path=LOCAL_MANIFEST_RELATIVE_PATH,
        output_dir=output_dir,
    )

    assert exit_code == 0, stderr
    payload = _json_object(stdout)
    assert payload["passed"] is True
    for key in (
        "plan",
        "runtime_loading",
        "computation",
        "graph_export",
        "diagnostics",
        "reference_comparison",
    ):
        assert key in payload
        assert isinstance(payload[key], dict)

    assert (output_dir / "graph" / "nodes.csv").is_file()
    assert (output_dir / "graph" / "edges.csv").is_file()
    assert (output_dir / "graph" / "graph.json").is_file()
    assert (output_dir / "reports" / "graph_diagnostics_report.json").is_file()

    assert not (
        output_dir / "reports" / "graph_reference_comparison.json"
    ).exists()
    assert not (output_dir / "rg" / "rg_timeseries.csv").exists()
    assert not (output_dir / "contacts" / "contacts_perframe.csv").exists()
    assert not (output_dir / "contacts" / "contact_edges.csv").exists()

    _assert_csv_header_contains(
        output_dir / "graph" / "nodes.csv",
        {"resid", "resname", "condition"},
    )
    _assert_csv_header_contains(
        output_dir / "graph" / "edges.csv",
        {
            "resid_i",
            "resid_j",
            "edge_type",
            "all_edge_types",
            "n_edge_types",
            "condition",
            "contact_freq",
            "mean_dist_A",
        },
    )
    graph_payload = _json_file(output_dir / "graph" / "graph.json")
    for key in (
        "condition",
        "nodes",
        "edges",
        "n_nodes",
        "n_edges",
        "schema_version",
    ):
        assert key in graph_payload

    diagnostics_payload = _json_file(
        output_dir / "reports" / "graph_diagnostics_report.json"
    )
    for key in (
        "passed",
        "status",
        "sections",
        "schema_version",
        "reference_semantics",
        "edge_schema",
    ):
        assert key in diagnostics_payload


def _local_md_smoke_enabled() -> bool:
    value = os.environ.get(LOCAL_MD_SMOKE_ENV, "")
    return value.strip().lower() in ENABLED_VALUES


def _local_md_smoke_skip_reason(
    *,
    manifest_path: Path = LOCAL_MANIFEST_PATH,
    mdanalysis_is_available: bool | None = None,
) -> str | None:
    if not _local_md_smoke_enabled():
        return "local MD smoke test is disabled; set MANIA_RUN_LOCAL_MD_SMOKE=1"
    if not manifest_path.is_file():
        return f"local MD smoke manifest is missing: {manifest_path}"

    manifest = load_preprocessing_input_manifest(manifest_path)
    _assert_manifest_declares_expected_local_paths(manifest.to_dict())
    path_report = validate_preprocessing_manifest_paths(
        manifest,
        base_dir=manifest_path.parent,
    )
    if not path_report.passed:
        issue = path_report.issues[0]
        return (
            "local MD smoke raw MD files are unavailable: "
            f"{issue.field} -> {issue.resolved_path}"
        )

    if mdanalysis_is_available is None:
        mdanalysis_is_available = mdanalysis_available()
    if not mdanalysis_is_available:
        return "MDAnalysis is unavailable; install the optional md or science extra"
    return None


def _assert_manifest_declares_expected_local_paths(
    manifest_payload: dict[str, Any],
) -> None:
    conditions = manifest_payload["conditions"]
    assert isinstance(conditions, list)
    observed = {
        condition["condition"]: {
            "topology_path": Path(condition["topology_path"]),
            "trajectory_paths": tuple(
                Path(path) for path in condition["trajectory_paths"]
            ),
        }
        for condition in conditions
    }

    assert observed == EXPECTED_MANIFEST_PATHS


def _run_graph_export_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    manifest_path: Path,
    output_dir: Path,
) -> tuple[int, str, str]:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "preprocessing",
            "run-graph-export",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_dir),
        ],
    )
    try:
        cli.main()
        exit_code = 0
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _assert_csv_header_contains(path: Path, expected_columns: set[str]) -> None:
    with path.open(encoding="utf-8", newline="") as csv_file:
        header = next(csv.reader(csv_file))
    assert header
    assert expected_columns <= set(header)


def _json_object(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def _json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_smoke_manifest(root: Path) -> Path:
    manifest_dir = root / "local_md" / "manifests"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "napi2b_10ns.yaml"
    manifest_path.write_text(
        "\n".join(
            (
                "output_root: ../outputs",
                "conditions:",
                "  - condition: normal",
                "    topology_path: ../normal/topology.tpr",
                "    trajectory_paths:",
                "      - ../normal/trajectory.xtc",
                "  - condition: tumor",
                "    topology_path: ../tumor/topology.tpr",
                "    trajectory_paths:",
                "      - ../tumor/trajectory.xtc",
                "",
            )
        ),
        encoding="utf-8",
    )
    return manifest_path


def _write_required_raw_md_placeholders(root: Path) -> None:
    for relative_path in (
        Path("local_md") / "normal" / "topology.tpr",
        Path("local_md") / "normal" / "trajectory.xtc",
        Path("local_md") / "tumor" / "topology.tpr",
        Path("local_md") / "tumor" / "trajectory.xtc",
    ):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")
