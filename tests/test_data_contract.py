from mania.constants import (
    ARTIFACT_COLUMNS,
    CENTRALITY_COLUMNS,
    COMMUNITIES_COLUMNS,
    COMPARISON_COLUMNS,
    CONFORMATIONAL_STATES_COLUMNS,
    CONTACTS_PERFRAME_COLUMNS,
    CROSS_CONDITION_ARTIFACTS,
    EDGE_COLUMNS,
    GRAPH_REQUIRED_KEYS,
    NODE_COLUMNS,
    PER_CONDITION_ARTIFACTS,
    RG_TIMESERIES_COLUMNS,
    SCHEMA_VERSION,
    STATS_COLUMNS,
    TEMPORAL_RIN_COLUMNS,
)

EXPECTED_PER_CONDITION_ARTIFACTS = (
    "nodes.csv",
    "edges.csv",
    "graph.json",
    "centrality.csv",
    "communities.csv",
    "temporal_rin.csv",
    "rg_timeseries.csv",
    "conformational_states.csv",
    "contacts_perframe.parquet",
)

EXPECTED_CROSS_CONDITION_ARTIFACTS = (
    "comparison.csv",
    "stats.csv",
)

EXPECTED_COLUMN_SCHEMAS = {
    "NODE_COLUMNS": (
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
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
        "community_id",
    ),
    "EDGE_COLUMNS": (
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
    ),
    "CENTRALITY_COLUMNS": (
        "resid",
        "condition",
        "degree",
        "strength",
        "betweenness",
        "closeness",
        "eigenvector",
        "pagerank",
        "kcore",
    ),
    "COMMUNITIES_COLUMNS": (
        "resid",
        "condition",
        "community_id",
        "community_size",
        "algorithm",
    ),
    "TEMPORAL_RIN_COLUMNS": (
        "window_id",
        "time_start_ps",
        "time_end_ps",
        "condition",
        "n_edges",
        "n_nodes_active",
        "density",
        "window_cv",
    ),
    "RG_TIMESERIES_COLUMNS": (
        "frame",
        "time_ps",
        "rg_A",
        "condition",
    ),
    "CONFORMATIONAL_STATES_COLUMNS": (
        "frame",
        "time_ps",
        "condition",
        "state_id",
        "cluster_label",
        "rg_A",
        "rmsd_A",
    ),
    "CONTACTS_PERFRAME_COLUMNS": (
        "frame",
        "time_ps",
        "resid_i",
        "resid_j",
        "edge_type",
        "dist_A",
        "condition",
    ),
    "COMPARISON_COLUMNS": (
        "resid_or_edge_id",
        "metric",
        "normal_value",
        "tumor_value",
        "delta",
        "statistic",
        "p_value",
        "q_value",
        "effect_size",
        "condition_specificity",
    ),
    "STATS_COLUMNS": (
        "resid_or_edge_id",
        "metric",
        "test",
        "statistic",
        "p_value",
        "q_value",
        "effect_size",
        "significant",
    ),
}

COLUMN_SCHEMAS = {
    "NODE_COLUMNS": NODE_COLUMNS,
    "EDGE_COLUMNS": EDGE_COLUMNS,
    "CENTRALITY_COLUMNS": CENTRALITY_COLUMNS,
    "COMMUNITIES_COLUMNS": COMMUNITIES_COLUMNS,
    "TEMPORAL_RIN_COLUMNS": TEMPORAL_RIN_COLUMNS,
    "RG_TIMESERIES_COLUMNS": RG_TIMESERIES_COLUMNS,
    "CONFORMATIONAL_STATES_COLUMNS": CONFORMATIONAL_STATES_COLUMNS,
    "CONTACTS_PERFRAME_COLUMNS": CONTACTS_PERFRAME_COLUMNS,
    "COMPARISON_COLUMNS": COMPARISON_COLUMNS,
    "STATS_COLUMNS": STATS_COLUMNS,
}


def test_schema_version() -> None:
    assert SCHEMA_VERSION == "0.1"


def test_artifact_constants_are_tuples() -> None:
    assert isinstance(PER_CONDITION_ARTIFACTS, tuple)
    assert isinstance(CROSS_CONDITION_ARTIFACTS, tuple)


def test_artifact_order() -> None:
    assert PER_CONDITION_ARTIFACTS == EXPECTED_PER_CONDITION_ARTIFACTS
    assert CROSS_CONDITION_ARTIFACTS == EXPECTED_CROSS_CONDITION_ARTIFACTS


def test_cross_condition_artifacts_are_not_per_condition() -> None:
    assert "comparison.csv" not in PER_CONDITION_ARTIFACTS
    assert "stats.csv" not in PER_CONDITION_ARTIFACTS


def test_column_constants_are_tuples() -> None:
    for schema in COLUMN_SCHEMAS.values():
        assert isinstance(schema, tuple)


def test_column_constants_match_expected_order() -> None:
    assert COLUMN_SCHEMAS == EXPECTED_COLUMN_SCHEMAS


def test_no_schema_contains_duplicate_column_names() -> None:
    for schema in COLUMN_SCHEMAS.values():
        assert len(schema) == len(set(schema))


def test_artifact_columns_covers_tabular_artifacts_only() -> None:
    expected_tabular_artifacts = (
        set(PER_CONDITION_ARTIFACTS) - {"graph.json"}
    ) | set(CROSS_CONDITION_ARTIFACTS)

    assert set(ARTIFACT_COLUMNS) == expected_tabular_artifacts
    assert "graph.json" not in ARTIFACT_COLUMNS
    assert "run_meta.json" not in ARTIFACT_COLUMNS


def test_artifact_columns_values_are_tuples() -> None:
    for columns in ARTIFACT_COLUMNS.values():
        assert isinstance(columns, tuple)


def test_graph_required_keys() -> None:
    assert GRAPH_REQUIRED_KEYS == (
        "condition",
        "n_nodes",
        "n_edges",
        "directed",
        "schema_version",
        "nodes",
        "edges",
    )
