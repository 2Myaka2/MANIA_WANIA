import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from test_cli_analyze import (
    PROJECT_ROOT,
    _aggregate_edge_rows,
    _analysis_bytes,
    _perframe_row,
    _read_csv,
    _request,
    _residue_rows,
    _write_csv,
    _write_stage20_root,
    invoke_cli,
)

import mania.cli as cli
from mania.analysis import (
    EXTENDED_METRICS_SCHEMA_VERSION,
    ExtendedMetricsError,
    build_extended_metrics_manifest,
    run_analysis,
)
from mania.preprocessing import (
    PROTEIN_CONTACT_EDGE_COLUMNS,
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
    RESIDUE_TABLE_COLUMNS,
)


def _manifest_path(output_root: Path) -> Path:
    return output_root / "analysis" / "extended_metrics.json"


def _read_manifest(output_root: Path) -> dict[str, Any]:
    payload = json.loads(_manifest_path(output_root).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _condition_manifest(
    manifest: Mapping[str, Any],
    condition: str,
) -> Mapping[str, Any]:
    for item in manifest["condition_results"]:
        if item["condition"] == condition:
            return item
    raise AssertionError(f"missing condition result: {condition}")


def _artifact_references(value: object) -> tuple[str, ...]:
    references: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "artifacts":
                assert isinstance(child, Mapping)
                references.extend(str(path) for path in child.values())
            else:
                references.extend(_artifact_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_artifact_references(child))
    return tuple(references)


def _write_constant_condition(root: Path, condition: str) -> None:
    _write_csv(
        root / f"residue_table_{condition}.csv",
        RESIDUE_TABLE_COLUMNS,
        _residue_rows(condition),
    )
    _write_csv(
        root / f"protein_contact_edges_undirected_{condition}.csv",
        PROTEIN_CONTACT_EDGE_COLUMNS,
        _aggregate_edge_rows(condition),
    )
    _write_csv(
        root / f"contacts_perframe_{condition}.csv",
        PROTEIN_CONTACT_PERFRAME_COLUMNS,
        (
            _perframe_row(condition, 0, 0.0, 1, 2, "vdw", 3.3),
            _perframe_row(condition, 1, 1.0, 1, 2, "vdw", 3.4),
            _perframe_row(condition, 2, 2.0, 1, 2, "vdw", 3.5),
            _perframe_row(condition, 3, 3.0, 1, 2, "vdw", 3.6),
        ),
    )


def _walk_scientific_table_keys(value: object) -> tuple[str, ...]:
    forbidden = {
        "centrality_rows",
        "community_rows",
        "comparison_rows",
        "contacts_perframe",
        "edges",
        "frame_coordinates",
        "graph_edges",
        "graph_nodes",
        "label_rows",
        "nodes",
        "pca_rows",
        "protein_contact_edges",
        "residue_rows",
        "rows",
        "stats_rows",
        "temporal_windows",
    }
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in forbidden:
                matches.append(key)
            matches.extend(_walk_scientific_table_keys(child))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_walk_scientific_table_keys(child))
    return tuple(matches)


def test_default_extended_metrics_manifest_is_compact_and_relative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal", "tumor"))

    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        "analyze",
        "--input",
        str(input_root),
        "--output",
        str(output_root),
        "--condition",
        "normal",
        "--condition",
        "tumor",
    )

    assert stderr == ""
    summary = json.loads(stdout)
    assert "analysis/extended_metrics.json" in summary["artifacts"]["written"]
    manifest = _read_manifest(output_root)
    assert manifest["schema_version"] == EXTENDED_METRICS_SCHEMA_VERSION
    assert manifest["kind"] == "mania_analysis_manifest"
    assert manifest["stage"] == "24.D"
    assert manifest["conditions"] == ["normal", "tumor"]
    assert manifest["configuration"] == {
        "clustering_basis": "fingerprint",
        "pca_components_for_clustering": None,
        "pca_enabled": False,
    }
    normal = _condition_manifest(manifest, "normal")
    analyses = normal["analyses"]
    assert analyses["conformation_pca"]["enabled"] is False
    assert analyses["conformation_pca"]["status"] == "not_requested"
    assert analyses["conformation_pca"]["reason"] == "pca_not_requested"
    assert analyses["conformation_clustering"]["basis"] == "fingerprint"
    assert analyses["conformation_clustering"]["algorithm"] == (
        "deterministic_kmeans_fingerprint"
    )
    assert analyses["conformation_clustering"]["input_source"] == (
        "contact_fingerprint_matrix"
    )
    assert manifest["run_results"]["cross_condition"]["status"] == "computed"
    assert manifest["diagnostics"] == {"issues": [], "passed": True}
    assert manifest["limitations"] == sorted(manifest["limitations"])
    assert not _walk_scientific_table_keys(manifest)
    for reference in _artifact_references(manifest):
        assert reference.startswith("analysis/")
        assert not reference.startswith("/")
        assert ".." not in Path(reference).parts
        assert "://" not in reference
        assert "\\" not in reference


def test_pca_enabled_manifest_reports_computed_projection(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal", "tumor"))

    run_analysis(
        _request(input_root, output_root, "normal", "tumor", enable_pca=True)
    )

    normal = _condition_manifest(_read_manifest(output_root), "normal")
    pca = normal["analyses"]["conformation_pca"]
    clustering = normal["analyses"]["conformation_clustering"]
    assert pca["enabled"] is True
    assert pca["status"] == "computed"
    assert pca["backend"] == "numpy_svd"
    assert pca["n_components"] == 1
    assert clustering["basis"] == "fingerprint"
    assert clustering["pca_components_requested"] is None
    assert clustering["pca_status"] == "pca_unavailable"


def test_pca_clustering_manifest_reports_requested_and_used_components(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal", "tumor"))

    run_analysis(
        _request(
            input_root,
            output_root,
            "normal",
            "tumor",
            enable_pca=True,
            clustering_basis="pca",
            pca_components_for_clustering=1,
        )
    )

    normal = _condition_manifest(_read_manifest(output_root), "normal")
    clustering = normal["analyses"]["conformation_clustering"]
    assert clustering["basis"] == "pca"
    assert clustering["algorithm"] == "deterministic_kmeans_pca"
    assert clustering["input_source"] == "conformation_pca_coordinates"
    assert clustering["pca_status"] == "computed"
    assert clustering["pca_components_requested"] == 1
    assert clustering["pca_components_used"] == 1


def test_degenerate_pca_manifest_reports_skipped_without_fake_values(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_constant_condition(input_root, "normal")

    run_analysis(_request(input_root, output_root, "normal", enable_pca=True))

    manifest = _read_manifest(output_root)
    pca = _condition_manifest(manifest, "normal")["analyses"]["conformation_pca"]
    assert pca["enabled"] is True
    assert pca["status"] == "skipped"
    assert pca["reason"] == "constant_matrix"
    assert "n_components" not in pca
    _, pca_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_pca_normal.csv"
    )
    assert {row["status"] for row in pca_rows} == {"constant_matrix"}
    assert all(row["pc1"] == "" for row in pca_rows)


def test_single_condition_manifest_does_not_claim_self_comparison(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    run_analysis(_request(input_root, output_root, "normal"))

    cross_condition = _read_manifest(output_root)["run_results"]["cross_condition"]
    assert cross_condition["status"] == "not_applicable"
    assert cross_condition["reason"] == "single_condition"
    assert cross_condition["artifacts"] == {
        "comparison": "analysis/comparison.csv",
        "stats": "analysis/stats.csv",
    }


def test_manifest_excludes_stale_files_from_previous_or_unrelated_runs(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))
    stale_paths = (
        output_root / "analysis" / "stale" / "centrality_stale.csv",
        output_root / "analysis" / "normal" / "stale_extra.csv",
        output_root / "analysis" / "tumor" / "graph.json",
    )
    for path in stale_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale\n", encoding="utf-8")

    run_analysis(_request(input_root, output_root, "normal"))

    encoded = json.dumps(_read_manifest(output_root), sort_keys=True)
    assert "stale" not in encoded
    assert "analysis/tumor/graph.json" not in encoded


def test_manifest_bytes_and_stdout_are_deterministic(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    _write_stage20_root(input_root, ("normal", "tumor"))
    command = (
        sys.executable,
        "-m",
        "mania",
        "analyze",
        "--input",
        str(input_root),
        "--condition",
        "normal",
        "--condition",
        "tumor",
    )

    first = subprocess.run(
        (*command, "--output", str(first_output)),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    second = subprocess.run(
        (*command, "--output", str(second_output)),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout
    assert _manifest_path(first_output).read_bytes() == _manifest_path(
        second_output
    ).read_bytes()
    assert _analysis_bytes(first_output) == _analysis_bytes(second_output)
    manifest_bytes = _manifest_path(first_output).read_bytes()
    assert manifest_bytes.endswith(b"\n")
    assert not manifest_bytes.endswith(b"\n\n")
    decoded = manifest_bytes.decode("utf-8")
    assert "NaN" not in decoded
    assert "Infinity" not in decoded
    assert str(tmp_path) not in decoded


def test_manifest_writer_rejects_outside_root_artifacts(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    outside = tmp_path / "outside.csv"
    _write_stage20_root(input_root, ("normal",))
    result = run_analysis(_request(input_root, output_root, "normal"))
    unsafe = result.__class__(
        request=result.request,
        analysis_root=result.analysis_root,
        condition_results=result.condition_results,
        comparison_csv=outside,
        stats_csv=result.stats_csv,
        skipped=result.skipped,
        diagnostics_issues=result.diagnostics_issues,
    )

    with pytest.raises(ExtendedMetricsError, match="outside output root"):
        build_extended_metrics_manifest(unsafe)


def test_manifest_is_not_added_to_wania_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("WANIA builder must not be invoked")

    monkeypatch.setattr(
        cli,
        "build_wania_graph_payload_from_artifacts",
        fail_if_called,
    )
    invoke_cli(
        monkeypatch,
        capsys,
        "analyze",
        "--input",
        str(input_root),
        "--output",
        str(output_root),
        "--condition",
        "normal",
    )

    manifest = _read_manifest(output_root)
    assert "wania" not in json.dumps(manifest["run_results"], sort_keys=True)
    assert not (output_root / "wania_graph_payload.json").exists()
