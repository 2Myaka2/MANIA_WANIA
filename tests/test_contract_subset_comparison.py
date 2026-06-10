import csv
import json
from pathlib import Path
from shutil import copytree

import pytest

from mania.adapters import export_notebook_contract_subset
from mania.comparison import (
    COMPARISON_MODE_CSV_EXACT,
    COMPARISON_MODE_CSV_NUMERIC_TOLERANCE,
    COMPARISON_MODE_JSON_EXACT,
    CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS,
    CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS,
    CONTRACT_SUBSET_ROOT_ARTIFACTS,
    DEFAULT_CONTRACT_SUBSET_ABS_TOL,
    EDGES_KEY_COLUMNS,
    EDGES_NUMERIC_COLUMNS,
    EDGES_TEXT_COLUMNS,
    NODES_KEY_COLUMNS,
    NODES_NUMERIC_COLUMNS,
    NODES_TEXT_COLUMNS,
    RG_TIMESERIES_KEY_COLUMNS,
    RG_TIMESERIES_NUMERIC_COLUMNS,
    RG_TIMESERIES_TEXT_COLUMNS,
    ArtifactComparisonSpec,
    ContractSubsetComparisonError,
    ReferenceComparisonReport,
    build_contract_subset_comparison_specs,
    build_contract_subset_numeric_tolerance_specs,
    compare_contract_subset,
    compare_contract_subset_numeric_tolerance,
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


def export_subset(output_dir: Path, conditions: tuple[str, ...] = CONDITIONS) -> Path:
    export_notebook_contract_subset(
        source_dir=NOTEBOOK_FIXTURE_DIR,
        output_dir=output_dir,
        conditions=conditions,
        frame_time_ps=100.0,
    )
    return output_dir


def find_spec(
    specs: tuple[ArtifactComparisonSpec, ...],
    relative_path: str,
) -> ArtifactComparisonSpec:
    for spec in specs:
        if spec.relative_path == relative_path:
            return spec
    raise AssertionError(f"Missing spec: {relative_path}")


def write_csv_rows(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_first_csv_value(path: Path, column: str, value: str) -> None:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = list(reader.fieldnames or ())
        rows = list(reader)
    rows[0][column] = value
    write_csv_rows(path, rows, fieldnames)


def adjusted_expected_root_for_conditions(
    tmp_path: Path,
    conditions: tuple[str, ...],
) -> Path:
    expected_root = copytree(EXPECTED_FIXTURE_DIR, tmp_path / "expected")
    run_meta_path = expected_root / "run_meta.json"
    run_meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
    run_meta["conditions"] = list(conditions)
    run_meta["global_features"] = {
        condition: run_meta["global_features"][condition] for condition in conditions
    }
    run_meta_path.write_text(
        json.dumps(run_meta, indent=2) + "\n",
        encoding="utf-8",
    )
    return expected_root


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


def test_numeric_tolerance_specs_preserve_order_and_modes() -> None:
    specs = build_contract_subset_numeric_tolerance_specs(CONDITIONS)

    assert len(specs) == 13
    assert specs[0].relative_path == "run_meta.json"
    assert specs[0].mode == COMPARISON_MODE_JSON_EXACT
    assert specs[0].numeric_tolerance is None

    csv_specs = tuple(
        spec for spec in specs if spec.relative_path.endswith(".csv")
    )
    assert csv_specs
    assert all(
        spec.mode == COMPARISON_MODE_CSV_NUMERIC_TOLERANCE
        for spec in csv_specs
    )
    assert all(spec.numeric_tolerance is not None for spec in csv_specs)

    graph_specs = tuple(
        spec for spec in specs if spec.relative_path.endswith("graph.json")
    )
    assert graph_specs
    assert all(spec.mode == COMPARISON_MODE_JSON_EXACT for spec in graph_specs)
    assert all(spec.numeric_tolerance is None for spec in graph_specs)


def test_numeric_tolerance_spec_order_matches_exact_spec_order() -> None:
    exact_specs = build_contract_subset_comparison_specs(CONDITIONS)
    tolerant_specs = build_contract_subset_numeric_tolerance_specs(CONDITIONS)

    assert tuple(spec.relative_path for spec in tolerant_specs) == tuple(
        spec.relative_path for spec in exact_specs
    )


def test_numeric_tolerance_rg_timeseries_profile() -> None:
    spec = find_spec(
        build_contract_subset_numeric_tolerance_specs(CONDITIONS),
        "normal/rg_timeseries.csv",
    )

    assert spec.numeric_tolerance is not None
    assert spec.numeric_tolerance.key_columns == RG_TIMESERIES_KEY_COLUMNS
    assert spec.numeric_tolerance.numeric_columns == RG_TIMESERIES_NUMERIC_COLUMNS
    assert spec.numeric_tolerance.text_columns == RG_TIMESERIES_TEXT_COLUMNS


def test_numeric_tolerance_nodes_profile() -> None:
    spec = find_spec(
        build_contract_subset_numeric_tolerance_specs(CONDITIONS),
        "normal/nodes.csv",
    )

    assert spec.numeric_tolerance is not None
    assert spec.numeric_tolerance.key_columns == NODES_KEY_COLUMNS
    assert "x_ca" in spec.numeric_tolerance.numeric_columns
    assert "degree" in spec.numeric_tolerance.numeric_columns
    assert "community_id" in spec.numeric_tolerance.numeric_columns
    assert spec.numeric_tolerance.numeric_columns == NODES_NUMERIC_COLUMNS
    assert "resname" in spec.numeric_tolerance.text_columns
    assert "region" in spec.numeric_tolerance.text_columns
    assert "ss" in spec.numeric_tolerance.text_columns
    assert spec.numeric_tolerance.text_columns == NODES_TEXT_COLUMNS


def test_numeric_tolerance_edges_profile() -> None:
    spec = find_spec(
        build_contract_subset_numeric_tolerance_specs(CONDITIONS),
        "normal/edges.csv",
    )

    assert spec.numeric_tolerance is not None
    assert spec.numeric_tolerance.key_columns == EDGES_KEY_COLUMNS
    assert "contact_freq" in spec.numeric_tolerance.numeric_columns
    assert "mean_dist_A" in spec.numeric_tolerance.numeric_columns
    assert "window_cv" in spec.numeric_tolerance.numeric_columns
    assert spec.numeric_tolerance.numeric_columns == EDGES_NUMERIC_COLUMNS
    assert spec.numeric_tolerance.text_columns == EDGES_TEXT_COLUMNS


def test_build_contract_subset_comparison_specs_strips_condition_whitespace() -> None:
    specs = build_contract_subset_comparison_specs((" normal ", "tumor"))

    assert specs[1].relative_path == "normal/rg_timeseries.csv"
    assert specs[7].relative_path == "tumor/rg_timeseries.csv"


def test_numeric_tolerance_specs_strip_condition_whitespace() -> None:
    specs = build_contract_subset_numeric_tolerance_specs((" normal ", " tumor "))

    assert specs[1].relative_path == "normal/rg_timeseries.csv"
    assert specs[7].relative_path == "tumor/rg_timeseries.csv"
    assert all(
        part == part.strip()
        for spec in specs
        for part in Path(spec.relative_path).parts
    )


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


@pytest.mark.parametrize(
    "conditions",
    (
        ("normal", ""),
        ("normal", " normal "),
    ),
)
def test_build_contract_subset_numeric_tolerance_specs_rejects_invalid_conditions(
    conditions: tuple[str, ...],
) -> None:
    with pytest.raises(ContractSubsetComparisonError):
        build_contract_subset_numeric_tolerance_specs(conditions)


@pytest.mark.parametrize("abs_tol", (-1e-6, float("nan"), float("inf")))
def test_build_contract_subset_numeric_tolerance_specs_rejects_invalid_abs_tol(
    abs_tol: float,
) -> None:
    with pytest.raises(ContractSubsetComparisonError):
        build_contract_subset_numeric_tolerance_specs(CONDITIONS, abs_tol=abs_tol)


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


def test_compare_contract_subset_numeric_tolerance_passes_for_adapter_output(
    tmp_path: Path,
) -> None:
    actual_root = export_subset(tmp_path / "actual")

    report = compare_contract_subset_numeric_tolerance(
        expected_root=EXPECTED_FIXTURE_DIR,
        actual_root=actual_root,
        conditions=CONDITIONS,
    )

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


def test_compare_contract_subset_numeric_tolerance_passes_for_small_numeric_drift(
    tmp_path: Path,
) -> None:
    actual_root = export_subset(tmp_path / "actual")
    changed_path = actual_root / "normal" / "rg_timeseries.csv"
    update_first_csv_value(
        changed_path,
        "rg_A",
        f"{35.0 + (DEFAULT_CONTRACT_SUBSET_ABS_TOL / 2):.10f}",
    )

    report_tolerant = compare_contract_subset_numeric_tolerance(
        EXPECTED_FIXTURE_DIR,
        actual_root,
        CONDITIONS,
    )
    report_exact = compare_contract_subset(
        EXPECTED_FIXTURE_DIR,
        actual_root,
        CONDITIONS,
    )

    assert report_tolerant.passed is True
    assert report_exact.passed is False


def test_compare_contract_subset_numeric_tolerance_fails_outside_tolerance(
    tmp_path: Path,
) -> None:
    actual_root = export_subset(tmp_path / "actual")
    changed_path = actual_root / "normal" / "rg_timeseries.csv"
    update_first_csv_value(changed_path, "rg_A", "35.1")

    report = compare_contract_subset_numeric_tolerance(
        EXPECTED_FIXTURE_DIR,
        actual_root,
        CONDITIONS,
    )

    assert report.passed is False
    failed = report.failed_results()
    assert any(result.artifact == "normal/rg_timeseries.csv" for result in failed)
    assert any(
        difference.check == "csv_numeric_tolerance"
        for result in failed
        if result.artifact == "normal/rg_timeseries.csv"
        for difference in result.differences
    )


def test_compare_contract_subset_numeric_tolerance_fails_for_text_mismatch(
    tmp_path: Path,
) -> None:
    actual_root = export_subset(tmp_path / "actual")
    changed_path = actual_root / "normal" / "nodes.csv"
    update_first_csv_value(changed_path, "resname", "GLY")

    report = compare_contract_subset_numeric_tolerance(
        EXPECTED_FIXTURE_DIR,
        actual_root,
        CONDITIONS,
    )

    assert report.passed is False
    failed = report.failed_results()
    assert any(result.artifact == "normal/nodes.csv" for result in failed)
    assert any(
        difference.check == "csv_text_exact"
        for result in failed
        if result.artifact == "normal/nodes.csv"
        for difference in result.differences
    )


def test_compare_contract_subset_numeric_tolerance_keeps_json_exact(
    tmp_path: Path,
) -> None:
    actual_root = export_subset(tmp_path / "actual")
    graph_path = actual_root / "normal" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["n_nodes"] = 999
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

    report = compare_contract_subset_numeric_tolerance(
        EXPECTED_FIXTURE_DIR,
        actual_root,
        CONDITIONS,
    )

    assert report.passed is False
    failed = report.failed_results()
    assert any(result.artifact == "normal/graph.json" for result in failed)
    assert any(
        difference.check == "json_exact"
        for result in failed
        if result.artifact == "normal/graph.json"
        for difference in result.differences
    )


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


def test_compare_contract_subset_numeric_tolerance_can_filter_to_single_condition(
    tmp_path: Path,
) -> None:
    expected_root = adjusted_expected_root_for_conditions(tmp_path, ("normal",))
    actual_root = export_subset(tmp_path / "actual", conditions=("normal",))

    report = compare_contract_subset_numeric_tolerance(
        expected_root=expected_root,
        actual_root=actual_root,
        conditions=("normal",),
    )

    assert report.passed is True
    assert len(report.results) == 7
    assert all(not result.artifact.startswith("tumor/") for result in report.results)
