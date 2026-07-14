import csv
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

import mania.analysis.conformation_pca as pca_module
import mania.analysis.orchestration as orchestration
import mania.cli as cli
from mania.analysis import (
    AnalyzeError,
    AnalyzeRequest,
    run_analysis,
)
from mania.preprocessing import (
    PROTEIN_CONTACT_EDGE_COLUMNS,
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
    RESIDUE_TABLE_COLUMNS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_python_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mania", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def invoke_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
    expected_exit_code: int = 0,
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["mania", *args])
    if expected_exit_code == 0:
        cli.main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err

    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    captured = capsys.readouterr()
    assert exc_info.value.code == expected_exit_code
    return int(exc_info.value.code), captured.out, captured.err


def _write_csv(
    path: Path,
    columns: Iterable[str],
    rows: Iterable[Mapping[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=tuple(columns),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _residue_rows(condition: str) -> tuple[dict[str, object], ...]:
    return (
        {
            "condition": condition,
            "residue_index": 1,
            "resid": "10",
            "resname": "ALA",
            "segment_id": "A",
            "region": "ECD",
        },
        {
            "condition": condition,
            "residue_index": 2,
            "resid": "20",
            "resname": "GLY",
            "segment_id": "A",
            "region": "TM",
        },
        {
            "condition": condition,
            "residue_index": 3,
            "resid": "30",
            "resname": "LYS",
            "segment_id": "A",
            "region": "ECD",
        },
    )


def _aggregate_edge_rows(condition: str) -> tuple[dict[str, object], ...]:
    return (
        {
            "condition": condition,
            "residue_index_i": 1,
            "resid_i": "10",
            "resname_i": "ALA",
            "segment_id_i": "A",
            "residue_index_j": 2,
            "resid_j": "20",
            "resname_j": "GLY",
            "segment_id_j": "A",
            "edge_type": "vdw",
            "contact_frame_count": 2,
            "sampled_frame_count": 4,
            "contact_freq": 0.5,
            "mean_dist_A": 3.4,
            "std_dist_A": 0.1,
            "weight": 0.5,
        },
        {
            "condition": condition,
            "residue_index_i": 2,
            "resid_i": "20",
            "resname_i": "GLY",
            "segment_id_i": "A",
            "residue_index_j": 3,
            "resid_j": "30",
            "resname_j": "LYS",
            "segment_id_j": "A",
            "edge_type": "hbond",
            "contact_frame_count": 2,
            "sampled_frame_count": 4,
            "contact_freq": 0.5,
            "mean_dist_A": 2.8,
            "std_dist_A": 0.1,
            "weight": 0.5,
        },
    )


def _perframe_rows(condition: str) -> tuple[dict[str, object], ...]:
    return (
        _perframe_row(condition, 0, 0.0, 1, 2, "vdw", 3.3),
        _perframe_row(condition, 1, 1.0, 1, 2, "vdw", 3.5),
        _perframe_row(condition, 2, 2.0, 2, 3, "hbond", 2.7),
        _perframe_row(condition, 3, 3.0, 2, 3, "hbond", 2.9),
    )


def _perframe_row(
    condition: str,
    frame_index: int,
    time_ps: float,
    residue_index_i: int,
    residue_index_j: int,
    edge_type: str,
    distance_a: float,
) -> dict[str, object]:
    identity = {
        1: ("10", "ALA", "A"),
        2: ("20", "GLY", "A"),
        3: ("30", "LYS", "A"),
    }
    resid_i, resname_i, segment_i = identity[residue_index_i]
    resid_j, resname_j, segment_j = identity[residue_index_j]
    return {
        "condition": condition,
        "frame_index": frame_index,
        "time_ps": time_ps,
        "residue_index_i": residue_index_i,
        "resid_i": resid_i,
        "resname_i": resname_i,
        "segment_id_i": segment_i,
        "residue_index_j": residue_index_j,
        "resid_j": resid_j,
        "resname_j": resname_j,
        "segment_id_j": segment_j,
        "edge_type": edge_type,
        "distance_A": distance_a,
    }


def _write_stage20_condition(
    root: Path,
    condition: str,
    *,
    row_condition: str | None = None,
) -> None:
    artifact_condition = row_condition or condition
    _write_csv(
        root / f"residue_table_{condition}.csv",
        RESIDUE_TABLE_COLUMNS,
        _residue_rows(artifact_condition),
    )
    _write_csv(
        root / f"protein_contact_edges_undirected_{condition}.csv",
        PROTEIN_CONTACT_EDGE_COLUMNS,
        _aggregate_edge_rows(artifact_condition),
    )
    _write_csv(
        root / f"contacts_perframe_{condition}.csv",
        PROTEIN_CONTACT_PERFRAME_COLUMNS,
        _perframe_rows(artifact_condition),
    )


def _write_stage20_root(root: Path, conditions: Iterable[str]) -> None:
    for condition in conditions:
        _write_stage20_condition(root, condition)


def _write_high_rank_stage20_condition(root: Path, condition: str) -> None:
    _write_stage20_condition(root, condition)
    features = (
        (1, 2, "vdw", 3.3),
        (1, 2, "hbond", 2.8),
        (1, 3, "vdw", 3.4),
        (2, 3, "hbond", 2.9),
        (2, 3, "ionic", 3.1),
    )
    patterns = (
        (1, 0, 0, 0, 0),
        (0, 1, 0, 0, 0),
        (0, 0, 1, 0, 0),
        (0, 0, 0, 1, 0),
        (0, 0, 0, 0, 1),
        (1, 1, 1, 1, 1),
    )
    rows = []
    for frame_index, pattern in enumerate(patterns):
        for present, (residue_i, residue_j, edge_type, distance) in zip(
            pattern,
            features,
            strict=True,
        ):
            if present:
                rows.append(
                    _perframe_row(
                        condition,
                        frame_index,
                        float(frame_index),
                        residue_i,
                        residue_j,
                        edge_type,
                        distance,
                    )
                )
    _write_csv(
        root / f"contacts_perframe_{condition}.csv",
        PROTEIN_CONTACT_PERFRAME_COLUMNS,
        rows,
    )


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def _analysis_bytes(root: Path) -> dict[str, bytes]:
    analysis_root = root / "analysis"
    return {
        path.relative_to(analysis_root).as_posix(): path.read_bytes()
        for path in sorted(analysis_root.rglob("*"))
        if path.is_file()
    }


def _request(
    input_root: Path,
    output_root: Path,
    *conditions: str,
    enable_pca: bool = False,
    clustering_basis: str = "fingerprint",
    pca_components_for_clustering: int | None = None,
) -> AnalyzeRequest:
    return AnalyzeRequest(
        input_root=input_root,
        output_root=output_root,
        conditions=conditions,
        enable_pca=enable_pca,
        clustering_basis=clustering_basis,  # type: ignore[arg-type]
        pca_components_for_clustering=pca_components_for_clustering,
    )


def test_analyze_help_documents_command_surface() -> None:
    top = run_python_module("--help")
    help_result = run_python_module("analyze", "--help")

    assert top.returncode == 0
    assert "analyze" in top.stdout
    assert "preprocessing" in top.stdout
    assert "wania" in top.stdout
    assert help_result.returncode == 0
    for phrase in (
        "--input",
        "--output",
        "--condition",
        "--enable-pca",
        "--clustering-basis",
        "{fingerprint,pca}",
        "--pca-components-for-clustering",
    ):
        assert phrase in help_result.stdout


def test_default_analyze_run_writes_accepted_layout_without_wania_or_raw_md(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal", "tumor"))

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("forbidden analyze dependency was invoked")

    monkeypatch.setattr(
        cli,
        "build_wania_graph_payload_from_artifacts",
        fail_if_called,
    )
    monkeypatch.setattr(
        cli,
        "compute_preprocessing_graph_workflow_rg_contacts",
        fail_if_called,
    )
    import mania.preprocessing.trajectory_contacts as trajectory_contacts
    import mania.preprocessing.trajectory_loader as trajectory_loader

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fail_if_called,
    )
    monkeypatch.setattr(
        trajectory_loader,
        "load_single_condition_runtime",
        fail_if_called,
    )

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
    assert stdout.count("\n") == 1
    summary = json.loads(stdout)
    assert summary["passed"] is True
    assert summary["stage"] == "24.C"
    assert summary["command"] == "analyze"
    assert summary["conditions"] == ["normal", "tumor"]
    assert summary["pca"] == {"enabled": False}
    assert summary["clustering"] == {
        "basis": "fingerprint",
        "pca_components_for_clustering": None,
    }
    expected = {
        "analysis/normal/graph.json",
        "analysis/normal/centrality_normal.csv",
        "analysis/normal/communities_normal.csv",
        "analysis/normal/region_enrichment_normal.csv",
        "analysis/normal/temporal_rin_normal.csv",
        "analysis/normal/conformation_pca_normal.csv",
        "analysis/normal/conformation_labels_normal.csv",
        "analysis/tumor/graph.json",
        "analysis/tumor/centrality_tumor.csv",
        "analysis/tumor/communities_tumor.csv",
        "analysis/tumor/region_enrichment_tumor.csv",
        "analysis/tumor/temporal_rin_tumor.csv",
        "analysis/tumor/conformation_pca_tumor.csv",
        "analysis/tumor/conformation_labels_tumor.csv",
        "analysis/comparison.csv",
        "analysis/stats.csv",
        "analysis/extended_metrics.json",
    }
    assert set(summary["artifacts"]["written"]) == expected
    assert summary["artifacts"]["count"] == len(expected)
    assert set(_analysis_bytes(output_root)) == {
        path.removeprefix("analysis/") for path in expected
    }
    assert not (output_root / "wania_graph_payload.json").exists()
    assert (output_root / "analysis" / "extended_metrics.json").is_file()

    _, pca_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_pca_normal.csv"
    )
    _, label_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_labels_normal.csv"
    )
    assert {row["status"] for row in pca_rows} == {"pca_unavailable"}
    assert all(row["pc1"] == "" for row in pca_rows)
    assert {row["input_source"] for row in label_rows} == {
        "contact_fingerprint_matrix"
    }
    assert {row["pca_status"] for row in label_rows} == {"pca_unavailable"}


def test_enable_pca_computes_projection_without_switching_clustering_basis(
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
        "--enable-pca",
    )

    assert stderr == ""
    summary = json.loads(stdout)
    assert summary["pca"] == {"enabled": True}
    assert summary["clustering"]["basis"] == "fingerprint"
    _, pca_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_pca_normal.csv"
    )
    _, label_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_labels_normal.csv"
    )
    assert {row["status"] for row in pca_rows} == {"computed"}
    assert any(row["pc1"] != "" for row in pca_rows)
    assert {row["input_source"] for row in label_rows} == {
        "contact_fingerprint_matrix"
    }


def test_pca_clustering_uses_computed_projection_and_component_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal", "tumor"))
    calls: list[dict[str, object]] = []
    original = orchestration.build_conformation_clusters

    def spy_build_conformation_clusters(*args: Any, **kwargs: Any) -> object:
        calls.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        orchestration,
        "build_conformation_clusters",
        spy_build_conformation_clusters,
    )

    result = run_analysis(
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

    summary = result.to_summary()
    assert summary["pca"] == {"enabled": True}
    assert summary["clustering"] == {
        "basis": "pca",
        "pca_components_for_clustering": 1,
    }
    assert len(calls) == 2
    assert all(call["clustering_basis"] == "pca" for call in calls)
    assert all(call["pca_projection"] is not None for call in calls)
    assert all(call["pca_components_for_clustering"] == 1 for call in calls)

    _, label_rows = _read_csv(
        output_root / "analysis" / "normal" / "conformation_labels_normal.csv"
    )
    assert {row["algorithm"] for row in label_rows} == {
        "deterministic_kmeans_pca"
    }
    assert {row["input_source"] for row in label_rows} == {
        "conformation_pca_coordinates"
    }
    assert {row["pca_status"] for row in label_rows} == {"computed"}


def test_pca_clustering_accepts_component_selection_above_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_high_rank_stage20_condition(input_root, "normal")

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
        "--enable-pca",
        "--clustering-basis",
        "pca",
        "--pca-components-for-clustering",
        "4",
    )

    assert stderr == ""
    assert json.loads(stdout)["passed"] is True
    manifest = json.loads(
        (output_root / "analysis" / "extended_metrics.json").read_text(
            encoding="utf-8"
        )
    )
    analyses = manifest["condition_results"][0]["analyses"]
    assert analyses["conformation_pca"]["computed_component_count"] >= 4
    assert analyses["conformation_pca"]["exported_component_count"] == 3
    assert analyses["conformation_clustering"]["pca_used_for_clustering"] is True
    assert analyses["conformation_clustering"]["pca_components_used"] == 4


@pytest.mark.parametrize(
    ("args", "expected_message", "expected_code"),
    (
        (
            ("--clustering-basis", "pca"),
            "clustering_basis='pca' requires enable_pca=True",
            1,
        ),
        (
            ("--pca-components-for-clustering", "1"),
            "pca_components_for_clustering requires clustering_basis='pca'",
            1,
        ),
        (
            ("--pca-components-for-clustering", "0"),
            "must be a positive integer",
            2,
        ),
        (
            ("--pca-components-for-clustering", "true"),
            "must be a positive integer",
            2,
        ),
        (
            ("--clustering-basis", "invalid"),
            "invalid choice",
            2,
        ),
    ),
)
def test_invalid_pca_cli_combinations_fail_without_success_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, ...],
    expected_message: str,
    expected_code: int,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

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
        *args,
        expected_exit_code=expected_code,
    )

    assert stdout == ""
    assert expected_message in stderr
    assert "passed" not in stdout


def test_pca_component_count_larger_than_projection_fails_before_writes(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    with pytest.raises(AnalyzeError, match="projection.n_components"):
        run_analysis(
            _request(
                input_root,
                output_root,
                "normal",
                enable_pca=True,
                clustering_basis="pca",
                pca_components_for_clustering=2,
            )
        )

    assert not (output_root / "analysis").exists()


def test_requested_numerical_pca_failure_is_fatal_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    def fail_compute(
        fingerprints: object,
        *,
        max_components: int,
    ) -> object:
        raise pca_module._PcaComputationFailed("synthetic SVD failure")

    monkeypatch.setattr(pca_module, "_compute_pca_values", fail_compute)

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
        "--enable-pca",
        expected_exit_code=1,
    )

    assert stdout == ""
    assert "Analyze failed:" in stderr
    assert "pca_failed" in stderr
    assert "passed" not in stdout
    assert not (output_root / "analysis").exists()
    assert not (output_root / "analysis" / "extended_metrics.json").exists()


@pytest.mark.parametrize(
    "condition",
    ("", ".", "..", "normal/tumor", "/normal", "normal tumor"),
)
def test_invalid_condition_names_are_rejected(
    tmp_path: Path,
    condition: str,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    with pytest.raises(AnalyzeError, match="condition"):
        run_analysis(_request(input_root, output_root, condition))


def test_input_validation_rejects_missing_roots_files_and_mismatches(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"

    with pytest.raises(AnalyzeError, match="input root does not exist"):
        run_analysis(_request(input_root, output_root, "normal"))

    input_file = tmp_path / "input-file"
    input_file.write_text("", encoding="utf-8")
    with pytest.raises(AnalyzeError, match="input root is not a directory"):
        run_analysis(_request(input_file, output_root, "normal"))

    _write_stage20_root(input_root, ("normal",))
    (input_root / "contacts_perframe_normal.csv").unlink()
    with pytest.raises(AnalyzeError, match="missing required contacts_perframe"):
        run_analysis(_request(input_root, output_root, "normal"))

    _write_stage20_condition(input_root, "normal", row_condition="tumor")
    with pytest.raises(AnalyzeError, match="condition/artifact mismatch"):
        run_analysis(_request(input_root, output_root, "normal"))

    output_file = tmp_path / "output-file"
    output_file.write_text("", encoding="utf-8")
    _write_stage20_condition(input_root, "normal")
    with pytest.raises(AnalyzeError, match="output root is not a directory"):
        run_analysis(_request(input_root, output_file, "normal"))


def test_duplicate_condition_is_rejected(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    with pytest.raises(AnalyzeError, match="duplicate condition"):
        run_analysis(_request(input_root, output_root, "normal", "normal"))


def test_single_condition_writes_header_only_comparison_and_reports_skip(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("normal",))

    result = run_analysis(_request(input_root, output_root, "normal"))

    comparison_header, comparison_rows = _read_csv(
        output_root / "analysis" / "comparison.csv"
    )
    stats_header, stats_rows = _read_csv(output_root / "analysis" / "stats.csv")
    assert comparison_header
    assert stats_header
    assert comparison_rows == []
    assert stats_rows == []
    assert result.to_summary()["skipped"] == [
        {
            "condition": None,
            "reason": "requires at least two conditions",
            "stage": "cross_condition_comparison",
        }
    ]


def test_multi_condition_comparison_and_order_are_stable(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    output_root = tmp_path / "out"
    _write_stage20_root(input_root, ("tumor", "normal"))

    result = run_analysis(_request(input_root, output_root, "tumor", "normal"))

    summary = result.to_summary()
    assert summary["conditions"] == ["tumor", "normal"]
    _, comparison_rows = _read_csv(output_root / "analysis" / "comparison.csv")
    _, stats_rows = _read_csv(output_root / "analysis" / "stats.csv")
    assert comparison_rows
    assert stats_rows
    assert {
        (row["condition_a"], row["condition_b"]) for row in comparison_rows
    } == {("normal", "tumor")}


def test_analyze_outputs_and_stdout_are_deterministic(tmp_path: Path) -> None:
    input_root = tmp_path / "preprocessing"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    _write_stage20_root(input_root, ("normal", "tumor"))
    command = (
        "analyze",
        "--input",
        str(input_root),
        "--condition",
        "normal",
        "--condition",
        "tumor",
    )

    first = run_python_module(*command, "--output", str(first_output))
    second = run_python_module(*command, "--output", str(second_output))

    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout
    assert first.stdout.count("\n") == 1
    assert json.loads(first.stdout)["passed"] is True
    assert _analysis_bytes(first_output) == _analysis_bytes(second_output)
