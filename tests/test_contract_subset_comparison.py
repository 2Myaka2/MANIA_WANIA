import json
from pathlib import Path
from shutil import copytree

import pytest

from mania.adapters import export_notebook_contract_subset
from mania.comparison import (
    COMPARISON_MODE_CSV_EXACT,
    COMPARISON_MODE_JSON_EXACT,
    CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS,
    CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS,
    CONTRACT_SUBSET_ROOT_ARTIFACTS,
    ArtifactComparisonSpec,
    ContractSubsetComparisonError,
    ReferenceComparisonReport,
    build_contract_subset_comparison_specs,
    compare_contract_subset,
)

NOTEBOOK_FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
EXPECTED_FIXTURE_DIR = Path("tests/fixtures/expected_contract_subset_tiny")
CONDITIONS = ("normal", "tumor")
UNSUPPORTED_ROOT_ARTIFACTS = ("comparison.csv", "stats.csv")
UNSUPPORTED_CONDITION_ARTIFACTS = (
    "temporal_rin.csv",
    "conformational_states.csv",
    "contacts_perframe.parquet",
)


def test_contract_subset_constants_include_only_supported_artifacts() -> None:
    assert CONTRACT_SUBSET_ROOT_ARTIFACTS == ("run_meta.json",)
    assert CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS == (
        "rg_timeseries.csv",
        "centrality.csv",
        "communities.csv",
        "nodes.csv",
        "edges.csv",
    )
    assert CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS == ("graph.json",)

    supported_artifacts = {
        *CONTRACT_SUBSET_ROOT_ARTIFACTS,
        *CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS,
        *CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS,
    }
    unsupported_artifacts = {
        *UNSUPPORTED_ROOT_ARTIFACTS,
        *UNSUPPORTED_CONDITION_ARTIFACTS,
    }
    assert supported_artifacts.isdisjoint(unsupported_artifacts)


def test_build_contract_subset_comparison_specs_preserves_order_and_modes() -> None:
    specs = build_contract_subset_comparison_specs(CONDITIONS)

    assert specs == (
        ArtifactComparisonSpec("run_meta.json", COMPARISON_MODE_JSON_EXACT),
        ArtifactComparisonSpec("normal/rg_timeseries.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("normal/centrality.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("normal/communities.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("normal/nodes.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("normal/edges.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("normal/graph.json", COMPARISON_MODE_JSON_EXACT),
        ArtifactComparisonSpec("tumor/rg_timeseries.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("tumor/centrality.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("tumor/communities.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("tumor/nodes.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("tumor/edges.csv", COMPARISON_MODE_CSV_EXACT),
        ArtifactComparisonSpec("tumor/graph.json", COMPARISON_MODE_JSON_EXACT),
    )


def test_build_contract_subset_comparison_specs_strips_condition_whitespace() -> None:
    specs = build_contract_subset_comparison_specs((" normal ", "tumor"))

    assert specs[1].relative_path == "normal/rg_timeseries.csv"
    assert specs[7].relative_path == "tumor/rg_timeseries.csv"


def test_build_contract_subset_comparison_specs_preserves_condition_case() -> None:
    specs = build_contract_subset_comparison_specs(("Normal",))

    assert specs[1].relative_path == "Normal/rg_timeseries.csv"


@pytest.mark.parametrize(
    "conditions",
    (
        ("normal", " normal "),
        ("normal", ""),
        ("normal", " "),
        "normal",
    ),
)
def test_build_contract_subset_comparison_specs_rejects_invalid_conditions(
    conditions: tuple[str, ...] | str,
) -> None:
    with pytest.raises(ContractSubsetComparisonError):
        build_contract_subset_comparison_specs(conditions)


def test_compare_contract_subset_passes_for_expected_fixture_copy(
    tmp_path: Path,
) -> None:
    actual_root = copytree(EXPECTED_FIXTURE_DIR, tmp_path / "actual")

    report = compare_contract_subset(EXPECTED_FIXTURE_DIR, actual_root, CONDITIONS)

    assert report.passed is True
    assert len(report.results) == 13


def test_compare_contract_subset_passes_for_adapter_output(
    tmp_path: Path,
) -> None:
    actual_root = tmp_path / "actual"
    export_notebook_contract_subset(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=actual_root,
        conditions=CONDITIONS,
        frame_time_ps=100.0,
    )

    report = compare_contract_subset(
        expected_root=EXPECTED_FIXTURE_DIR,
        actual_root=actual_root,
        conditions=CONDITIONS,
    )

    assert isinstance(report, ReferenceComparisonReport)
    assert report.passed is True
    assert all(result.passed for result in report.results)


def test_compare_contract_subset_reports_normal_differences(
    tmp_path: Path,
) -> None:
    actual_root = copytree(EXPECTED_FIXTURE_DIR, tmp_path / "actual")
    changed_path = actual_root / "normal" / "rg_timeseries.csv"
    changed_path.write_text(
        changed_path.read_text(encoding="utf-8").replace("37.0", "37.5"),
        encoding="utf-8",
    )

    report = compare_contract_subset(EXPECTED_FIXTURE_DIR, actual_root, CONDITIONS)

    assert report.passed is False
    assert report.failed_results()[0].artifact == "normal/rg_timeseries.csv"


def test_compare_contract_subset_reports_missing_actual_artifact(
    tmp_path: Path,
) -> None:
    actual_root = copytree(EXPECTED_FIXTURE_DIR, tmp_path / "actual")
    (actual_root / "tumor" / "graph.json").unlink()

    report = compare_contract_subset(EXPECTED_FIXTURE_DIR, actual_root, CONDITIONS)

    assert report.passed is False
    failed = report.failed_results()
    assert any(result.artifact == "tumor/graph.json" for result in failed)
    assert any(
        difference.check == "actual_file_exists"
        for result in failed
        if result.artifact == "tumor/graph.json"
        for difference in result.differences
    )


def test_compare_contract_subset_can_filter_to_single_condition(
    tmp_path: Path,
) -> None:
    expected_root = copytree(EXPECTED_FIXTURE_DIR, tmp_path / "expected")
    expected_run_meta_path = expected_root / "run_meta.json"
    expected_run_meta = json.loads(expected_run_meta_path.read_text(encoding="utf-8"))
    expected_run_meta["conditions"] = ["normal"]
    expected_run_meta["global_features"] = {
        "normal": expected_run_meta["global_features"]["normal"]
    }
    expected_run_meta_path.write_text(
        json.dumps(expected_run_meta, indent=2) + "\n",
        encoding="utf-8",
    )

    actual_root = tmp_path / "actual"
    export_notebook_contract_subset(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=actual_root,
        conditions=("normal",),
        frame_time_ps=100.0,
    )

    report = compare_contract_subset(
        expected_root=expected_root,
        actual_root=actual_root,
        conditions=("normal",),
    )

    assert report.passed is True
    assert len(report.results) == 7
    assert all(not result.artifact.startswith("tumor/") for result in report.results)
