import csv
import json
from pathlib import Path

from mania.analysis import (
    AnalysisGraphMetricsArtifacts,
    compute_analysis_graph_metrics_from_graph_json,
    write_analysis_graph_metrics_artifacts,
)
from mania.analysis.graph_metrics_export import (
    COMMUNITIES_COLUMNS,
    METRICS_COLUMNS,
)


def multi_condition_graph() -> dict[str, object]:
    return {
        "condition": "normal",
        "nodes": [
            {
                "id": "normal-A",
                "resid": "10",
                "resname": "ALA",
                "condition": "normal",
                "region": "R1",
                "x_ca": 1.0,
            },
            {"id": "normal-B", "resid": "11", "condition": "normal"},
            {
                "id": "tumor-A",
                "resid": "10",
                "resname": "ALA",
                "condition": "tumor",
                "region": "R2",
                "x_ca": 2.0,
            },
            {"id": "tumor-B", "resid": "11", "condition": "tumor"},
        ],
        "edges": [
            {
                "source": "normal-A",
                "target": "normal-B",
                "condition": "normal",
                "contact_freq": 0.25,
            },
            {
                "source": "tumor-A",
                "target": "tumor-B",
                "condition": "tumor",
                "contact_freq": 0.75,
            },
        ],
    }


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader.fieldnames or []), list(reader)


def test_writer_creates_expected_multi_condition_analysis_artifacts(
    tmp_path: Path,
) -> None:
    result = compute_analysis_graph_metrics_from_graph_json(
        multi_condition_graph()
    )
    output_dir = tmp_path / "analysis"

    artifacts = write_analysis_graph_metrics_artifacts(result, output_dir)

    assert isinstance(artifacts, AnalysisGraphMetricsArtifacts)
    assert artifacts.output_dir == output_dir
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "analysis_metrics_report.json",
        "communities_normal.csv",
        "communities_tumor.csv",
        "metrics_normal.csv",
        "metrics_tumor.csv",
    ]
    assert artifacts.to_dict()["report_path"] == str(
        output_dir / "analysis_metrics_report.json"
    )


def test_metrics_csv_preserves_features_and_contains_all_metrics(
    tmp_path: Path,
) -> None:
    result = compute_analysis_graph_metrics_from_graph_json(
        multi_condition_graph()
    )
    artifacts = write_analysis_graph_metrics_artifacts(
        result,
        tmp_path / "analysis",
    )

    header, rows = read_csv(artifacts.metrics_paths["normal"])

    assert header == list(METRICS_COLUMNS)
    assert len(rows) == 2
    assert rows[0]["condition"] == "normal"
    assert rows[0]["node_id"] == "normal-A"
    assert rows[0]["resid"] == "10"
    assert rows[0]["resname"] == "ALA"
    assert rows[0]["region"] == "R1"
    assert rows[0]["x_ca"] == "1.0"
    for metric in (
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
        "community",
    ):
        assert rows[0][metric] != ""


def test_communities_csv_and_report_are_complete_and_json_safe(
    tmp_path: Path,
) -> None:
    result = compute_analysis_graph_metrics_from_graph_json(
        multi_condition_graph()
    )
    artifacts = write_analysis_graph_metrics_artifacts(
        result,
        tmp_path / "analysis",
    )

    header, rows = read_csv(artifacts.communities_paths["tumor"])
    report = json.loads(artifacts.report_path.read_text(encoding="utf-8"))

    assert header == list(COMMUNITIES_COLUMNS)
    assert len(rows) == 2
    assert all(row["condition"] == "tumor" for row in rows)
    assert all(row["community"] for row in rows)
    assert all(row["node_id"] for row in rows)
    assert all(row["resid"] for row in rows)
    assert report == result.report
    assert report["conditions"] == ["normal", "tumor"]
    json.dumps(report, allow_nan=False)
    assert artifacts.report_path.read_text(encoding="utf-8").endswith("\n")
