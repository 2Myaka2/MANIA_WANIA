import csv
from dataclasses import replace
from pathlib import Path

from mania.analysis import (
    CONFORMATION_CLUSTERING_ALGORITHM,
    CONFORMATION_CLUSTERING_INPUT_SOURCE,
    CONFORMATION_CLUSTERING_NOTEBOOK_PARITY,
    CONFORMATION_CLUSTERING_PCA_STATUS,
    CONFORMATION_CLUSTERING_STATUS_COMPUTED,
    CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
    CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
    CONFORMATION_CLUSTERING_STATUS_NO_FEATURES,
    CONFORMATION_CLUSTERING_STATUS_NO_VALID_K,
    CONFORMATION_LABELS_COLUMNS,
    CONFORMATION_PCA_COLUMNS,
    CONFORMATION_PCA_STATUS_CONSTANT_MATRIX,
    CONFORMATION_PCA_STATUS_NO_FEATURES,
    CONFORMATION_PCA_STATUS_ONE_FRAME,
    CONFORMATION_PCA_STATUS_UNAVAILABLE,
    STATIC_RIN_COMMUNITY_ALGORITHM,
    TEMP_MIN_FREQ,
    TEMP_STEP,
    TEMP_WINDOW,
    TEMPORAL_RIN_METRICS_COLUMNS,
    TEMPORAL_RIN_STATUS_COMPUTED,
    TEMPORAL_RIN_STATUS_EMPTY_WINDOW,
    ConformationClustering,
    ConformationPcaProjection,
    ContactFingerprintMatrix,
    TemporalContactRow,
    TemporalRinConfig,
    TemporalRinInput,
    TemporalRinMetrics,
    build_conformation_clusters,
    build_conformation_pca_projection,
    build_contact_fingerprint_matrix,
    build_temporal_rin_window_graphs,
    compute_temporal_rin_metrics,
    generate_temporal_windows,
    write_conformation_labels_csv,
    write_conformation_pca_csv,
    write_temporal_rin_csv,
)

CONDITION = "normal"
FRAME_INDEXES = (2, 100, 900, 1200)
TIMES = (2.5, None, 9.0, 12.0)


def _contact(
    frame_index: int,
    time_ps: float | None,
    residue_index_i: int,
    residue_index_j: int,
    edge_type: str,
) -> TemporalContactRow:
    identities = {
        1: ("10", "ALA", "A"),
        2: ("20", "GLY", "A"),
        3: ("30", "LYS", "B"),
    }
    resid_i, resname_i, segment_id_i = identities[residue_index_i]
    resid_j, resname_j, segment_id_j = identities[residue_index_j]
    return TemporalContactRow(
        condition=CONDITION,
        frame_index=frame_index,
        time_ps=time_ps,
        residue_index_i=residue_index_i,
        resid_i=resid_i,
        resname_i=resname_i,
        segment_id_i=segment_id_i,
        residue_index_j=residue_index_j,
        resid_j=resid_j,
        resname_j=resname_j,
        segment_id_j=segment_id_j,
        edge_type=edge_type,
        distance_A=3.5 if edge_type == "hbond" else 4.0,
    )


def _temporal_input() -> TemporalRinInput:
    config = TemporalRinConfig(
        window_size=2,
        step_size=2,
        min_frequency=0.5,
    )
    rows = (
        _contact(2, 2.5, 1, 2, "vdw"),
        _contact(100, None, 1, 2, "vdw"),
        _contact(900, 9.0, 2, 3, "hbond"),
        _contact(1200, 12.0, 2, 3, "hbond"),
    )
    return TemporalRinInput(
        condition=CONDITION,
        config=config,
        rows=rows,
        sampled_frame_indexes=FRAME_INDEXES,
        windows=generate_temporal_windows(CONDITION, FRAME_INDEXES, config=config),
    )


def _stage22_results() -> tuple[
    TemporalRinMetrics,
    ContactFingerprintMatrix,
    ConformationPcaProjection,
    ConformationClustering,
]:
    temporal_input = _temporal_input()
    window_graphs = build_temporal_rin_window_graphs(temporal_input)
    temporal_metrics = compute_temporal_rin_metrics(window_graphs)
    fingerprints = build_contact_fingerprint_matrix(temporal_input)
    projection = build_conformation_pca_projection(fingerprints)
    clustering = build_conformation_clusters(fingerprints)
    return temporal_metrics, fingerprints, projection, clustering


def _write_bundle(root: Path) -> tuple[dict[str, bytes], ContactFingerprintMatrix]:
    temporal_metrics, fingerprints, projection, clustering = _stage22_results()
    condition_root = root / "analysis" / CONDITION
    paths = (
        write_temporal_rin_csv(temporal_metrics, condition_root),
        write_conformation_pca_csv(projection, condition_root),
        write_conformation_labels_csv(clustering, condition_root),
    )
    return ({path.name: path.read_bytes() for path in paths}, fingerprints)


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_stage22_artifacts_are_schema_valid_cross_consistent_and_deterministic(
    tmp_path: Path,
) -> None:
    first_bytes, fingerprints = _write_bundle(tmp_path / "first")
    second_bytes, second_fingerprints = _write_bundle(tmp_path / "second")

    assert first_bytes == second_bytes
    assert fingerprints == second_fingerprints
    assert tuple(first_bytes) == (
        "temporal_rin_normal.csv",
        "conformation_pca_normal.csv",
        "conformation_labels_normal.csv",
    )

    condition_root = tmp_path / "first" / "analysis" / CONDITION
    temporal_header, temporal_rows = _read_csv(
        condition_root / "temporal_rin_normal.csv"
    )
    pca_header, pca_rows = _read_csv(
        condition_root / "conformation_pca_normal.csv"
    )
    labels_header, label_rows = _read_csv(
        condition_root / "conformation_labels_normal.csv"
    )

    assert temporal_header == TEMPORAL_RIN_METRICS_COLUMNS
    assert pca_header == CONFORMATION_PCA_COLUMNS
    assert labels_header == CONFORMATION_LABELS_COLUMNS
    assert {row["condition"] for row in temporal_rows + pca_rows + label_rows} == {
        CONDITION
    }

    assert [row["window_id"] for row in temporal_rows] == ["0", "1"]
    assert [row["frame_start"] for row in temporal_rows] == ["2", "900"]
    assert [row["frame_end"] for row in temporal_rows] == ["100", "1200"]
    assert all(
        int(row["frame_end"]) - int(row["frame_start"]) + 1
        != int(row["sampled_frame_count"])
        for row in temporal_rows
    )
    assert all(row["sampled_frame_count"] == "2" for row in temporal_rows)
    assert all(row["active_frame_count"] == "2" for row in temporal_rows)
    assert all(row["n_nodes"] == "2" for row in temporal_rows)
    assert all(row["n_edges"] == "1" for row in temporal_rows)
    assert all(row["density"] == "1" for row in temporal_rows)
    assert all(row["mean_degree"] == "1" for row in temporal_rows)
    assert all(row["mean_strength"] == "1" for row in temporal_rows)
    assert all(row["betweenness_mean"] == "0" for row in temporal_rows)
    assert all(row["closeness_mean"] == "1" for row in temporal_rows)
    assert all(row["status"] == TEMPORAL_RIN_STATUS_COMPUTED for row in temporal_rows)
    assert {row["community_algorithm"] for row in temporal_rows} == {
        STATIC_RIN_COMMUNITY_ALGORITHM
    }
    assert all("louvain" not in row["community_algorithm"] for row in temporal_rows)

    expected_frame_indexes = [str(frame_index) for frame_index in FRAME_INDEXES]
    expected_times = ["2.5", "", "9", "12"]
    fingerprint_frame_indexes = [
        str(frame.frame_index) for frame in fingerprints.frames
    ]
    fingerprint_times = [
        "" if frame.time_ps is None else format(frame.time_ps, ".15g")
        for frame in fingerprints.frames
    ]
    assert [row["frame_index"] for row in pca_rows] == expected_frame_indexes
    assert [row["frame_index"] for row in label_rows] == expected_frame_indexes
    assert fingerprint_frame_indexes == expected_frame_indexes
    assert [row["time_ps"] for row in pca_rows] == expected_times
    assert [row["time_ps"] for row in label_rows] == expected_times
    assert fingerprint_times == expected_times

    unavailable_fields = (
        "pc1",
        "pc2",
        "pc3",
        "explained_variance_ratio_pc1",
        "explained_variance_ratio_pc2",
        "explained_variance_ratio_pc3",
    )
    assert all(
        row["status"] == CONFORMATION_PCA_STATUS_UNAVAILABLE
        and row["n_components"] == "0"
        and all(row[field] == "" for field in unavailable_fields)
        for row in pca_rows
    )

    assert all(
        row["status"] == CONFORMATION_CLUSTERING_STATUS_COMPUTED
        for row in label_rows
    )
    assert {row["selected_k"] for row in label_rows} == {"2"}
    assert {row["silhouette_score"] for row in label_rows} == {"1"}
    assert {row["algorithm"] for row in label_rows} == {
        CONFORMATION_CLUSTERING_ALGORITHM
    }
    assert {row["input_source"] for row in label_rows} == {
        CONFORMATION_CLUSTERING_INPUT_SOURCE
    }
    assert {row["pca_status"] for row in label_rows} == {
        CONFORMATION_CLUSTERING_PCA_STATUS
    }
    assert {row["notebook_parity"] for row in label_rows} == {
        CONFORMATION_CLUSTERING_NOTEBOOK_PARITY
    }
    assert all("binary contact fingerprints" in row["notes"] for row in label_rows)
    assert all("parity not claimed" in row["notes"] for row in label_rows)
    assert [row["is_representative"] for row in label_rows] == [
        "true",
        "false",
        "true",
        "false",
    ]
    state_ids = {row["state_id"] for row in label_rows}
    assert state_ids == {"1", "2"}
    for state_id in state_ids:
        assert sum(
            row["state_id"] == state_id and row["is_representative"] == "true"
            for row in label_rows
        ) == 1

    wania_only_fields = {"x", "y", "z", "capabilities", "diagnostics"}
    assert not wania_only_fields.intersection(temporal_header)
    assert not wania_only_fields.intersection(pca_header)
    assert not wania_only_fields.intersection(labels_header)


def test_stage22_skipped_and_unavailable_states_do_not_invent_values(
    tmp_path: Path,
) -> None:
    _, fingerprints, _, _ = _stage22_results()
    no_features = replace(
        fingerprints,
        features=(),
        values=((), (), (), ()),
        status="zero_features",
        notes="sampled frames contain no contact features",
    )
    insufficient = replace(
        fingerprints,
        frames=fingerprints.frames[:2],
        values=fingerprints.values[:2],
    )
    constant = replace(
        fingerprints,
        values=((0, 0), (0, 0), (0, 0), (0, 0)),
    )

    no_feature_pca = build_conformation_pca_projection(no_features)
    constant_pca = build_conformation_pca_projection(constant)
    one_frame_pca = build_conformation_pca_projection(
        replace(
            fingerprints,
            frames=fingerprints.frames[:1],
            values=fingerprints.values[:1],
        )
    )
    assert no_feature_pca.status == CONFORMATION_PCA_STATUS_NO_FEATURES
    assert constant_pca.status == CONFORMATION_PCA_STATUS_CONSTANT_MATRIX
    assert one_frame_pca.status == CONFORMATION_PCA_STATUS_ONE_FRAME
    for index, projection in enumerate(
        (no_feature_pca, constant_pca, one_frame_pca)
    ):
        assert projection.notes
        assert all(
            row.n_components == 0
            and row.pc1 is None
            and row.pc2 is None
            and row.pc3 is None
            and row.explained_variance_ratio_pc1 is None
            and row.explained_variance_ratio_pc2 is None
            and row.explained_variance_ratio_pc3 is None
            for row in projection.rows
        )
        output = write_conformation_pca_csv(
            projection,
            tmp_path / f"pca_skipped_{index}",
        )
        _, rows = _read_csv(output)
        assert rows
        assert all(
            row["n_components"] == "0"
            and row["pc1"] == row["pc2"] == row["pc3"] == ""
            and row["explained_variance_ratio_pc1"] == ""
            and row["explained_variance_ratio_pc2"] == ""
            and row["explained_variance_ratio_pc3"] == ""
            for row in rows
        )

    no_feature_labels = build_conformation_clusters(no_features)
    insufficient_labels = build_conformation_clusters(insufficient)
    constant_labels = build_conformation_clusters(constant)
    assert no_feature_labels.status == CONFORMATION_CLUSTERING_STATUS_NO_FEATURES
    assert (
        insufficient_labels.status
        == CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES
    )
    assert constant_labels.status == CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX

    no_valid_k = replace(
        no_feature_labels,
        status=CONFORMATION_CLUSTERING_STATUS_NO_VALID_K,
        notes=(
            "no candidate k produced valid non-empty clusters; clustering input "
            "is binary contact fingerprints; PCA coordinates unavailable; "
            "notebook PCA-to-k-means parity not claimed"
        ),
        rows=tuple(
            replace(
                row,
                status=CONFORMATION_CLUSTERING_STATUS_NO_VALID_K,
                notes=(
                    "no candidate k produced valid non-empty clusters; clustering "
                    "input is binary contact fingerprints; PCA coordinates "
                    "unavailable; notebook PCA-to-k-means parity not claimed"
                ),
            )
            for row in no_feature_labels.rows
        ),
    )
    skipped_results = (
        no_feature_labels,
        insufficient_labels,
        constant_labels,
        no_valid_k,
    )
    skipped_fields = (
        "state_id",
        "cluster_label",
        "selected_k",
        "silhouette_score",
        "is_representative",
        "distance_to_centroid",
    )
    for index, clustering in enumerate(skipped_results):
        output = write_conformation_labels_csv(
            clustering,
            tmp_path / f"skipped_{index}",
        )
        _, rows = _read_csv(output)
        assert rows
        assert all(row["notes"] for row in rows)
        assert all(
            all(row[field] == "" for field in skipped_fields) for row in rows
        )

    empty_window_config = TemporalRinConfig(
        window_size=2,
        step_size=2,
        min_frequency=0.5,
    )
    empty_window_input = TemporalRinInput(
        condition=CONDITION,
        config=empty_window_config,
        rows=(),
        sampled_frame_indexes=(5, 100),
        windows=generate_temporal_windows(
            CONDITION,
            (5, 100),
            config=empty_window_config,
        ),
    )
    temporal_output = write_temporal_rin_csv(
        compute_temporal_rin_metrics(
            build_temporal_rin_window_graphs(empty_window_input)
        ),
        tmp_path / "temporal_skipped",
    )
    _, temporal_rows = _read_csv(temporal_output)
    assert len(temporal_rows) == 1
    assert temporal_rows[0]["status"] == TEMPORAL_RIN_STATUS_EMPTY_WINDOW
    assert temporal_rows[0]["notes"]
    assert (
        temporal_rows[0]["frame_start"],
        temporal_rows[0]["frame_end"],
        temporal_rows[0]["sampled_frame_count"],
        temporal_rows[0]["active_frame_count"],
    ) == ("5", "100", "2", "0")
    for field in (
        "density",
        "mean_degree",
        "mean_strength",
        "betweenness_mean",
        "betweenness_max",
        "closeness_mean",
        "modularity",
        "n_communities",
        "community_algorithm",
    ):
        assert temporal_rows[0][field] == ""


def test_stage22_empty_inputs_write_header_only_artifacts(tmp_path: Path) -> None:
    config = TemporalRinConfig()
    empty_input = TemporalRinInput(
        condition=CONDITION,
        config=config,
        rows=(),
        sampled_frame_indexes=(),
        windows=(),
    )
    empty_fingerprints = build_contact_fingerprint_matrix(empty_input)
    output_dir = tmp_path / "analysis" / CONDITION
    temporal_path = write_temporal_rin_csv(
        compute_temporal_rin_metrics(
            build_temporal_rin_window_graphs(empty_input)
        ),
        output_dir,
    )
    pca_path = write_conformation_pca_csv(
        build_conformation_pca_projection(empty_fingerprints),
        output_dir,
    )
    labels_path = write_conformation_labels_csv(
        build_conformation_clusters(empty_fingerprints),
        output_dir,
    )

    assert temporal_path.read_text(encoding="utf-8") == ",".join(
        TEMPORAL_RIN_METRICS_COLUMNS
    ) + "\n"
    assert pca_path.read_text(encoding="utf-8") == ",".join(
        CONFORMATION_PCA_COLUMNS
    ) + "\n"
    assert labels_path.read_text(encoding="utf-8") == ",".join(
        CONFORMATION_LABELS_COLUMNS
    ) + "\n"
    assert (TEMP_WINDOW, TEMP_STEP, TEMP_MIN_FREQ) == (10, 10, 0.25)
