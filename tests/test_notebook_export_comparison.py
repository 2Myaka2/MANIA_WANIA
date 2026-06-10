import json
from pathlib import Path

from mania.adapters import export_notebook_contract_subset
from mania.comparison import (
    ReferenceComparisonReport,
    build_comparison_report,
    compare_csv_exact,
    compare_json_exact,
    write_comparison_report,
)
from mania.validation.artifacts import (
    validate_condition_column,
    validate_csv_artifact_schema,
)
from mania.validation.graph import validate_graph_json
from mania.validation.manifest import validate_global_features

SOURCE_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
EXPECTED_FIXTURE_DIR = Path("tests/fixtures/expected_contract_subset_tiny")
CONDITIONS = ("normal", "tumor")
CONDITION_CSV_ARTIFACTS = (
    "rg_timeseries.csv",
    "centrality.csv",
    "communities.csv",
    "nodes.csv",
    "edges.csv",
)
CONDITION_JSON_ARTIFACTS = ("graph.json",)
ROOT_JSON_ARTIFACTS = ("run_meta.json",)
SUPPORTED_RELATIVE_PATHS = (
    *(Path(name) for name in ROOT_JSON_ARTIFACTS),
    *(
        Path(condition) / artifact
        for condition in CONDITIONS
        for artifact in (*CONDITION_CSV_ARTIFACTS, *CONDITION_JSON_ARTIFACTS)
    ),
)
UNSUPPORTED_ROOT_ARTIFACTS = ("comparison.csv", "stats.csv")
UNSUPPORTED_CONDITION_ARTIFACTS = (
    "temporal_rin.csv",
    "conformational_states.csv",
    "contacts_perframe.parquet",
)


def export_subset(output_dir: Path) -> Path:
    export_notebook_contract_subset(
        SOURCE_FIXTURE_DIR,
        output_dir,
        CONDITIONS,
        frame_time_ps=100.0,
    )
    return output_dir


def build_subset_comparison_report(output_dir: Path) -> ReferenceComparisonReport:
    results = []
    for relative_path in SUPPORTED_RELATIVE_PATHS:
        expected_path = EXPECTED_FIXTURE_DIR / relative_path
        actual_path = output_dir / relative_path
        artifact = relative_path.as_posix()
        if relative_path.suffix == ".json":
            results.append(compare_json_exact(expected_path, actual_path, artifact))
        else:
            results.append(compare_csv_exact(expected_path, actual_path, artifact))
    return build_comparison_report(results)


def validate_generated_output_subset(output_dir: Path) -> None:
    validate_global_features(
        output_dir / "run_meta.json",
        expected_conditions=CONDITIONS,
    )
    for condition in CONDITIONS:
        for artifact in CONDITION_CSV_ARTIFACTS:
            path = output_dir / condition / artifact
            validate_csv_artifact_schema(path, artifact)
            validate_condition_column(path, condition)
        validate_graph_json(
            output_dir / condition / "graph.json",
            expected_condition=condition,
        )


def test_expected_fixture_exists_and_has_supported_files() -> None:
    expected_files = tuple(
        sorted(
            path.relative_to(EXPECTED_FIXTURE_DIR)
            for path in EXPECTED_FIXTURE_DIR.rglob("*")
            if path.is_file()
        )
    )

    assert expected_files == tuple(sorted(SUPPORTED_RELATIVE_PATHS))
    for artifact in UNSUPPORTED_ROOT_ARTIFACTS:
        assert not (EXPECTED_FIXTURE_DIR / artifact).exists()
    for condition in CONDITIONS:
        for artifact in UNSUPPORTED_CONDITION_ARTIFACTS:
            assert not (EXPECTED_FIXTURE_DIR / condition / artifact).exists()


def test_adapter_output_matches_expected_fixture_exactly(tmp_path: Path) -> None:
    output_dir = export_subset(tmp_path / "generated")

    report = build_subset_comparison_report(output_dir)

    assert report.passed is True
    assert all(result.passed for result in report.results)


def test_comparison_report_can_be_written(tmp_path: Path) -> None:
    output_dir = export_subset(tmp_path / "generated")
    report = build_subset_comparison_report(output_dir)

    report_path = write_comparison_report(report, tmp_path / "comparison_report.json")
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.is_file()
    assert payload["passed"] is True


def test_comparison_catches_adapter_output_difference(tmp_path: Path) -> None:
    output_dir = export_subset(tmp_path / "generated")
    changed_path = output_dir / "normal" / "rg_timeseries.csv"
    changed_path.write_text(
        changed_path.read_text(encoding="utf-8").replace("37.0", "37.5"),
        encoding="utf-8",
    )

    report = build_subset_comparison_report(output_dir)

    assert report.passed is False
    assert report.failed_results()
    assert any(
        result.artifact == "normal/rg_timeseries.csv"
        for result in report.failed_results()
    )


def test_generated_outputs_still_pass_validators(tmp_path: Path) -> None:
    output_dir = export_subset(tmp_path / "generated")

    validate_generated_output_subset(output_dir)
