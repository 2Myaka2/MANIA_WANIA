import csv
import json
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")

REQUIRED_FILES = (
    "residue_table_normal.csv",
    "residue_table_tumor.csv",
    "centrality_normal.csv",
    "centrality_tumor.csv",
    "communities_normal.csv",
    "communities_tumor.csv",
    "protein_contact_edges_undirected_normal.csv",
    "protein_contact_edges_undirected_tumor.csv",
    "rg_timeseries_normal.csv",
    "rg_timeseries_tumor.csv",
    "mania_manifest.json",
)

EXPECTED_HEADERS = {
    "residue_table_normal.csv": [
        "resid",
        "resname",
        "region",
        "condition",
        "x_ca",
        "y_ca",
        "z_ca",
        "tm_relative_z",
        "rmsf_A",
        "sasa_A2",
        "ss",
    ],
    "residue_table_tumor.csv": [
        "resid",
        "resname",
        "region",
        "condition",
        "x_ca",
        "y_ca",
        "z_ca",
        "tm_relative_z",
        "rmsf_A",
        "sasa_A2",
        "ss",
    ],
    "centrality_normal.csv": [
        "resid",
        "condition",
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
    ],
    "centrality_tumor.csv": [
        "resid",
        "condition",
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
    ],
    "communities_normal.csv": [
        "resid",
        "condition",
        "community_id",
        "community_size",
        "algorithm",
    ],
    "communities_tumor.csv": [
        "resid",
        "condition",
        "community_id",
        "community_size",
        "algorithm",
    ],
    "protein_contact_edges_undirected_normal.csv": [
        "resid_i",
        "resid_j",
        "edge_type",
        "condition",
        "contact_freq",
        "mean_dist_A",
        "std_dist_A",
        "n_episodes",
        "mean_lifetime_frames",
        "max_lifetime_frames",
        "mean_lifetime_ns",
        "max_lifetime_ns",
        "formation_count",
        "breakage_count",
        "first_seen_frame",
        "last_seen_frame",
        "window_cv",
    ],
    "protein_contact_edges_undirected_tumor.csv": [
        "resid_i",
        "resid_j",
        "edge_type",
        "condition",
        "contact_freq",
        "mean_dist_A",
        "std_dist_A",
        "n_episodes",
        "mean_lifetime_frames",
        "max_lifetime_frames",
        "mean_lifetime_ns",
        "max_lifetime_ns",
        "formation_count",
        "breakage_count",
        "first_seen_frame",
        "last_seen_frame",
        "window_cv",
    ],
    "rg_timeseries_normal.csv": ["frame", "rg_A", "condition"],
    "rg_timeseries_tumor.csv": ["frame", "rg_A", "condition"],
}

EXPECTED_ROW_COUNTS = {
    "residue_table_normal.csv": 2,
    "residue_table_tumor.csv": 2,
    "centrality_normal.csv": 2,
    "centrality_tumor.csv": 2,
    "communities_normal.csv": 2,
    "communities_tumor.csv": 2,
    "protein_contact_edges_undirected_normal.csv": 1,
    "protein_contact_edges_undirected_tumor.csv": 1,
    "rg_timeseries_normal.csv": 2,
    "rg_timeseries_tumor.csv": 2,
}


def read_rows(filename: str) -> list[dict[str, str]]:
    with (FIXTURE_DIR / filename).open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_header(filename: str) -> list[str]:
    with (FIXTURE_DIR / filename).open(encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        return next(reader)


def condition_from_filename(filename: str) -> str:
    if filename.endswith("_normal.csv"):
        return "normal"
    if filename.endswith("_tumor.csv"):
        return "tumor"
    raise AssertionError(f"Cannot infer condition from {filename}")


def test_notebook_export_fixture_directory_exists() -> None:
    assert FIXTURE_DIR.is_dir()


def test_required_notebook_export_fixture_files_exist() -> None:
    for filename in REQUIRED_FILES:
        assert (FIXTURE_DIR / filename).is_file()


def test_csv_fixture_files_are_readable_and_non_empty() -> None:
    for filename in EXPECTED_HEADERS:
        header = read_header(filename)
        rows = read_rows(filename)

        assert header == EXPECTED_HEADERS[filename]
        assert rows


def test_condition_values_match_filename_condition() -> None:
    for filename in EXPECTED_HEADERS:
        condition = condition_from_filename(filename)

        for row in read_rows(filename):
            if "condition" in row:
                assert row["condition"] == condition


def test_row_counts_are_intentionally_tiny() -> None:
    for filename, expected_count in EXPECTED_ROW_COUNTS.items():
        assert len(read_rows(filename)) == expected_count


def test_rg_timeseries_files_use_notebook_shape_without_time_ps() -> None:
    for filename in ("rg_timeseries_normal.csv", "rg_timeseries_tumor.csv"):
        header = read_header(filename)

        assert header == ["frame", "rg_A", "condition"]
        assert "time_ps" not in header


def test_residue_ids_repeat_across_conditions() -> None:
    normal_resids = {row["resid"] for row in read_rows("residue_table_normal.csv")}
    tumor_resids = {row["resid"] for row in read_rows("residue_table_tumor.csv")}

    assert {"1", "2"}.issubset(normal_resids)
    assert {"1", "2"}.issubset(tumor_resids)


def test_manifest_has_conditions_and_global_features() -> None:
    with (FIXTURE_DIR / "mania_manifest.json").open(encoding="utf-8") as json_file:
        manifest = json.load(json_file)

    assert manifest["conditions"] == ["normal", "tumor"]
    assert "global_features" in manifest

    global_features = manifest["global_features"]
    for condition in ("normal", "tumor"):
        assert condition in global_features
        assert "rg_mean_A" in global_features[condition]
        assert "rg_std_A" in global_features[condition]
        assert global_features[condition]["n_rg_frames"] == 2
