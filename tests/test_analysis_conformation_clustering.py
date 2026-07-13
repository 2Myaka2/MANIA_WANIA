import csv
import math
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    CONFORMATION_CLUSTERING_ALGORITHM,
    CONFORMATION_CLUSTERING_ALGORITHM_PCA,
    CONFORMATION_CLUSTERING_BASIS_FINGERPRINT,
    CONFORMATION_CLUSTERING_BASIS_PCA,
    CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER,
    CONFORMATION_CLUSTERING_CANDIDATE_VALID,
    CONFORMATION_CLUSTERING_INPUT_SOURCE,
    CONFORMATION_CLUSTERING_INPUT_SOURCE_PCA,
    CONFORMATION_CLUSTERING_K_MAX,
    CONFORMATION_CLUSTERING_NOTEBOOK_PARITY,
    CONFORMATION_CLUSTERING_NOTEBOOK_PARITY_PCA,
    CONFORMATION_CLUSTERING_PCA_STATUS,
    CONFORMATION_CLUSTERING_STATUS_COMPUTED,
    CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
    CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT,
    CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
    CONFORMATION_CLUSTERING_STATUS_NO_FEATURES,
    CONFORMATION_LABELS_COLUMNS,
    CONFORMATION_PCA_STATUS_COMPUTED,
    ConformationClusteringConfig,
    ConformationClusteringError,
    ConformationPcaProjection,
    ConformationPcaRow,
    ContactFingerprintFeature,
    ContactFingerprintFrame,
    ContactFingerprintMatrix,
    build_conformation_clusters,
    build_conformation_pca_projection,
    write_conformation_labels_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "analysis" / "conformation_clustering.py"
DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_gap_matrix.md",
    REPO_ROOT / "docs" / "mania_rin_mvp_scope_v0_1.md",
)


def _feature(
    column_index: int, *, condition: str = "normal"
) -> ContactFingerprintFeature:
    residue_index_j = column_index + 2
    return ContactFingerprintFeature(
        condition=condition,
        feature_id=f"{condition}:1--{residue_index_j}:vdw",
        column_index=column_index,
        residue_index_i=1,
        resid_i="10",
        resname_i="ALA",
        segment_id_i="A",
        residue_index_j=residue_index_j,
        resid_j=str(residue_index_j * 10),
        resname_j="GLY",
        segment_id_j="A",
        edge_type="vdw",
        edge_priority_rank=8,
    )


def _matrix(
    values: tuple[tuple[int, ...], ...] = ((0,), (0,), (1,), (1,)),
    *,
    frame_indexes: tuple[int, ...] = (2, 100, 900, 1200),
    times: tuple[float | None, ...] = (2.5, None, 9.0, 12.0),
    condition: str = "normal",
) -> ContactFingerprintMatrix:
    n_features = len(values[0]) if values else 0
    return ContactFingerprintMatrix(
        condition=condition,
        frames=tuple(
            ContactFingerprintFrame(
                condition=condition,
                row_index=row_index,
                frame_index=frame_index,
                time_ps=times[row_index],
            )
            for row_index, frame_index in enumerate(frame_indexes)
        ),
        features=tuple(
            _feature(column_index, condition=condition)
            for column_index in range(n_features)
        ),
        values=values,
        status="computed",
        notes="",
    )


def _pca_projection(
    fingerprints: ContactFingerprintMatrix,
    coordinates: tuple[tuple[float, ...], ...],
) -> ConformationPcaProjection:
    n_components = len(coordinates[0]) if coordinates else 0
    ratios = (1.0, 0.0, 0.0)
    rows = []
    for frame, row_coordinates in zip(
        fingerprints.frames,
        coordinates,
        strict=True,
    ):
        padded = row_coordinates + (None,) * (3 - len(row_coordinates))
        rows.append(
            ConformationPcaRow(
                condition=fingerprints.condition,
                row_index=frame.row_index,
                frame_index=frame.frame_index,
                time_ps=frame.time_ps,
                pc1=padded[0],
                pc2=padded[1],
                pc3=padded[2],
                explained_variance_ratio_pc1=ratios[0],
                explained_variance_ratio_pc2=(
                    ratios[1] if n_components >= 2 else None
                ),
                explained_variance_ratio_pc3=(
                    ratios[2] if n_components >= 3 else None
                ),
                n_components=n_components,
                n_features=fingerprints.shape[1],
                n_frames=fingerprints.shape[0],
                status=CONFORMATION_PCA_STATUS_COMPUTED,
                notes="computed with centered NumPy SVD; notebook parity not claimed",
            )
        )
    return ConformationPcaProjection(
        condition=fingerprints.condition,
        rows=tuple(rows),
        n_components=n_components,
        n_features=fingerprints.shape[1],
        n_frames=fingerprints.shape[0],
        status=CONFORMATION_PCA_STATUS_COMPUTED,
        notes="computed with centered NumPy SVD; notebook parity not claimed",
    )


def test_binary_fingerprints_are_clustered_deterministically_without_pca() -> None:
    fingerprints = _matrix()
    first = build_conformation_clusters(fingerprints)
    second = build_conformation_clusters(fingerprints)
    enabled_projection = build_conformation_pca_projection(
        fingerprints,
        enable_pca=True,
    )
    explicit_fingerprint = build_conformation_clusters(
        fingerprints,
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_FINGERPRINT,
        pca_projection=enabled_projection,
    )

    assert first == second
    assert explicit_fingerprint == first
    assert first.condition == "normal"
    assert first.status == CONFORMATION_CLUSTERING_STATUS_COMPUTED
    assert first.selected_k == 2
    assert first.silhouette_score == 1.0
    assert [(candidate.k, candidate.status) for candidate in first.candidates] == [
        (2, CONFORMATION_CLUSTERING_CANDIDATE_VALID),
        (3, CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER),
    ]
    assert first.candidates[0].n_iterations == 2
    assert first.candidates[0].converged is True
    assert [row.frame_index for row in first.rows] == [2, 100, 900, 1200]
    assert [row.time_ps for row in first.rows] == [2.5, None, 9.0, 12.0]
    assert [row.state_id for row in first.rows] == [1, 1, 2, 2]
    assert [row.cluster_label for row in first.rows] == [
        "state_1",
        "state_1",
        "state_2",
        "state_2",
    ]
    assert [row.is_representative for row in first.rows] == [True, False, True, False]
    assert all(row.distance_to_centroid == 0.0 for row in first.rows)
    assert all(row.algorithm == CONFORMATION_CLUSTERING_ALGORITHM for row in first.rows)
    assert all(
        row.input_source == CONFORMATION_CLUSTERING_INPUT_SOURCE
        for row in first.rows
    )
    assert all(
        row.pca_status == CONFORMATION_CLUSTERING_PCA_STATUS for row in first.rows
    )
    assert all(
        row.notebook_parity == CONFORMATION_CLUSTERING_NOTEBOOK_PARITY
        for row in first.rows
    )
    assert "binary contact fingerprints" in first.notes
    assert "PCA coordinates unavailable" in first.notes
    assert "parity not claimed" in first.notes


def test_farthest_first_assignment_and_representative_ties_are_stable() -> None:
    fingerprints = _matrix(values=((0, 0), (0, 1), (1, 0), (1, 1)))
    two_clusters = build_conformation_clusters(
        fingerprints,
        config=ConformationClusteringConfig(max_k=2),
    )
    selected = build_conformation_clusters(fingerprints)

    # The first centroid is 00 and the next is farthest-first 11. Both middle
    # rows initially tie and deterministically enter the lower cluster index.
    assert [row.state_id for row in two_clusters.rows] == [1, 1, 1, 2]
    assert two_clusters.candidates[0].converged is True

    # With selected k=3, frames 2 and 900 tie around their final centroid.
    assert selected.selected_k == 3
    assert [row.state_id for row in selected.rows] == [1, 2, 1, 3]
    assert selected.rows[0].distance_to_centroid == 0.25
    assert selected.rows[2].distance_to_centroid == 0.25
    assert selected.rows[0].is_representative is True
    assert selected.rows[2].is_representative is False


def test_candidate_range_best_silhouette_and_lowest_k_tie_break() -> None:
    tie_matrix = _matrix(
        values=((0, 0), (0, 1), (0, 1), (1, 0), (1, 1)),
        frame_indexes=(2, 20, 200, 2000, 20000),
        times=(None, None, None, None, None),
    )
    tied = build_conformation_clusters(tie_matrix)

    scores = {candidate.k: candidate.silhouette_score for candidate in tied.candidates}
    assert scores[3] == scores[4] == 0.4
    assert tied.selected_k == 3

    many_unique_values = tuple(product((0, 1), repeat=4))[:12]
    many = build_conformation_clusters(
        _matrix(
            values=many_unique_values,
            frame_indexes=tuple(range(0, 120, 10)),
            times=(None,) * 12,
        )
    )
    assert CONFORMATION_CLUSTERING_K_MAX == 10
    assert [candidate.k for candidate in many.candidates] == list(range(2, 11))


def test_pca_clustering_requires_explicit_computed_projection() -> None:
    fingerprints = _matrix(values=((0, 0), (0, 1), (1, 0), (1, 1)))
    projection = _pca_projection(
        fingerprints,
        ((0.0,), (0.0,), (10.0,), (10.0,)),
    )
    default = build_conformation_clusters(fingerprints)

    assert build_conformation_clusters(fingerprints, pca_projection=projection) == (
        default
    )
    with pytest.raises(ConformationClusteringError, match="clustering_basis"):
        build_conformation_clusters(fingerprints, clustering_basis="invalid")
    with pytest.raises(ConformationClusteringError, match="requires pca_projection"):
        build_conformation_clusters(
            fingerprints,
            clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        )
    with pytest.raises(ConformationClusteringError, match="computed PCA"):
        build_conformation_clusters(
            fingerprints,
            clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
            pca_projection=build_conformation_pca_projection(fingerprints),
        )


def test_pca_clustering_uses_pca_space_metadata_components_and_csv_bytes(
    tmp_path: Path,
) -> None:
    fingerprints = _matrix(
        values=((0, 0), (0, 0), (0, 0), (1, 1)),
    )
    projection = _pca_projection(
        fingerprints,
        ((0.0, 0.0), (2.0, 1.0), (4.0, 2.0), (100.0, 3.0)),
    )

    all_components = build_conformation_clusters(
        fingerprints,
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        pca_projection=projection,
        config=ConformationClusteringConfig(max_k=2),
    )
    pc1_only = build_conformation_clusters(
        fingerprints,
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        pca_projection=projection,
        pca_components_for_clustering=1,
        config=ConformationClusteringConfig(max_k=2),
    )
    output = write_conformation_labels_csv(all_components, tmp_path)
    first_bytes = output.read_bytes()
    write_conformation_labels_csv(all_components, tmp_path)

    assert all_components.status == CONFORMATION_CLUSTERING_STATUS_COMPUTED
    assert all_components.selected_k == 2
    assert [row.state_id for row in all_components.rows] == [1, 1, 1, 2]
    assert [row.is_representative for row in all_components.rows] == [
        False,
        True,
        False,
        True,
    ]
    assert [row.distance_to_centroid for row in all_components.rows] == [
        5.0,
        0.0,
        5.0,
        0.0,
    ]
    assert [row.distance_to_centroid for row in pc1_only.rows] == [
        4.0,
        0.0,
        4.0,
        0.0,
    ]
    assert all(
        row.algorithm == CONFORMATION_CLUSTERING_ALGORITHM_PCA
        and row.input_source == CONFORMATION_CLUSTERING_INPUT_SOURCE_PCA
        and row.pca_status == CONFORMATION_PCA_STATUS_COMPUTED
        and row.notebook_parity == CONFORMATION_CLUSTERING_NOTEBOOK_PARITY_PCA
        for row in all_components.rows
    )
    assert "PCA frame-score coordinates" in all_components.notes
    assert "exact notebook parity not claimed" in all_components.notes
    assert output.read_bytes() == first_bytes
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(CONFORMATION_LABELS_COLUMNS)
    assert {row["algorithm"] for row in rows} == {
        CONFORMATION_CLUSTERING_ALGORITHM_PCA
    }
    assert {row["input_source"] for row in rows} == {
        CONFORMATION_CLUSTERING_INPUT_SOURCE_PCA
    }
    assert {row["pca_status"] for row in rows} == {
        CONFORMATION_PCA_STATUS_COMPUTED
    }
    assert {row["distance_to_centroid"] for row in rows} == {"0", "5"}


def test_pca_component_selection_is_explicit_and_rejects_unavailable_values(
) -> None:
    fingerprints = _matrix()
    projection = _pca_projection(
        fingerprints,
        ((0.0,), (0.0,), (10.0,), (10.0,)),
    )

    clustering = build_conformation_clusters(
        fingerprints,
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        pca_projection=projection,
    )
    assert clustering.selected_k == 2

    for requested in (0, -1, 2, True, 1.5):
        with pytest.raises(ConformationClusteringError):
            build_conformation_clusters(
                fingerprints,
                clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
                pca_projection=projection,
                pca_components_for_clustering=requested,
            )

    blank_pc2_projection = replace(
        projection,
        n_components=2,
        rows=tuple(
            replace(row, n_components=2, pc2=None) for row in projection.rows
        ),
    )
    with pytest.raises(ConformationClusteringError, match="finite"):
        build_conformation_clusters(
            fingerprints,
            clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
            pca_projection=blank_pc2_projection,
        )


def test_pca_frame_identity_validation_rejects_mismatches() -> None:
    fingerprints = _matrix()
    projection = _pca_projection(
        fingerprints,
        ((0.0,), (0.0,), (10.0,), (10.0,)),
    )

    mismatches = (
        (
            replace(projection, condition="tumor"),
            "condition",
        ),
        (
            replace(projection, n_frames=3, rows=projection.rows[:-1]),
            "frame count",
        ),
        (
            replace(
                projection,
                rows=(
                    projection.rows[0],
                    replace(
                        projection.rows[1],
                        frame_index=projection.rows[0].frame_index,
                    ),
                    *projection.rows[2:],
                ),
            ),
            "duplicate",
        ),
        (
            replace(
                projection,
                rows=(
                    projection.rows[0],
                    replace(projection.rows[1], frame_index=777),
                    *projection.rows[2:],
                ),
            ),
            "frame_index",
        ),
        (
            replace(
                projection,
                rows=(replace(projection.rows[0], time_ps=99.0), *projection.rows[1:]),
            ),
            "time_ps",
        ),
        (
            replace(
                projection,
                rows=(replace(projection.rows[0], pc1=math.inf), *projection.rows[1:]),
            ),
            "finite",
        ),
    )

    for invalid_projection, message in mismatches:
        with pytest.raises(ConformationClusteringError, match=message):
            build_conformation_clusters(
                fingerprints,
                clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
                pca_projection=invalid_projection,
            )


def test_pca_degenerate_inputs_skip_without_invented_labels() -> None:
    constant = build_conformation_clusters(
        _matrix(),
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        pca_projection=_pca_projection(
            _matrix(),
            ((1.0,), (1.0,), (1.0,), (1.0,)),
        ),
    )
    two_frame_fingerprints = _matrix(
        values=((0,), (1,)),
        frame_indexes=(5, 100),
        times=(None, 10.0),
    )
    insufficient = build_conformation_clusters(
        two_frame_fingerprints,
        clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
        pca_projection=_pca_projection(
            two_frame_fingerprints,
            ((0.0,), (1.0,)),
        ),
    )
    zero_component_projection = _pca_projection(
        _matrix(),
        ((0.0,), (0.0,), (10.0,), (10.0,)),
    )
    zero_component_projection = replace(
        zero_component_projection,
        n_components=0,
        rows=tuple(
            replace(row, n_components=0, pc1=None)
            for row in zero_component_projection.rows
        ),
    )

    assert constant.status == CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX
    assert insufficient.status == CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES
    for clustering in (constant, insufficient):
        assert clustering.selected_k is None
        assert clustering.silhouette_score is None
        assert all(
            row.pca_status == CONFORMATION_PCA_STATUS_COMPUTED
            for row in clustering.rows
        )
        assert all(
            (
                row.state_id,
                row.cluster_label,
                row.selected_k,
                row.silhouette_score,
                row.is_representative,
                row.distance_to_centroid,
            )
            == (None, None, None, None, None, None)
            for row in clustering.rows
        )
    with pytest.raises(ConformationClusteringError, match="1-3"):
        build_conformation_clusters(
            _matrix(),
            clustering_basis=CONFORMATION_CLUSTERING_BASIS_PCA,
            pca_projection=zero_component_projection,
        )


@pytest.mark.parametrize(
    ("fingerprints", "expected_status"),
    [
        (
            _matrix(values=(), frame_indexes=(), times=()),
            CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT,
        ),
        (
            _matrix(values=((1,),), frame_indexes=(42,), times=(None,)),
            CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
        ),
        (
            _matrix(
                values=((0,), (1,)),
                frame_indexes=(5, 100),
                times=(None, 10.0),
            ),
            CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
        ),
        (
            ContactFingerprintMatrix(
                condition="normal",
                frames=(
                    ContactFingerprintFrame("normal", 0, 5, None),
                    ContactFingerprintFrame("normal", 1, 100, 10.0),
                    ContactFingerprintFrame("normal", 2, 900, None),
                ),
                features=(),
                values=((), (), ()),
                status="zero_features",
                notes="sampled frames contain no contact features",
            ),
            CONFORMATION_CLUSTERING_STATUS_NO_FEATURES,
        ),
        (
            _matrix(values=((0, 0), (0, 0), (0, 0), (0, 0))),
            CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
        ),
        (
            _matrix(values=((1, 0), (1, 0), (1, 0), (1, 0))),
            CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
        ),
    ],
)
def test_degenerate_inputs_have_explicit_status_without_invented_labels(
    fingerprints: ContactFingerprintMatrix,
    expected_status: str,
) -> None:
    clustering = build_conformation_clusters(fingerprints)

    assert clustering.status == expected_status
    assert clustering.selected_k is None
    assert clustering.silhouette_score is None
    for row in clustering.rows:
        assert (
            row.state_id,
            row.cluster_label,
            row.selected_k,
            row.silhouette_score,
            row.is_representative,
            row.distance_to_centroid,
        ) == (None, None, None, None, None, None)
        assert row.input_source == "contact_fingerprint_matrix"
        assert row.pca_status == "pca_unavailable"


def test_csv_is_atomic_ordered_byte_stable_and_blank_when_skipped(
    tmp_path: Path,
) -> None:
    clustering = build_conformation_clusters(_matrix())
    output_dir = tmp_path / "analysis" / "normal"
    output = write_conformation_labels_csv(clustering, output_dir)
    first_bytes = output.read_bytes()
    write_conformation_labels_csv(clustering, output_dir)

    assert output.name == "conformation_labels_normal.csv"
    assert output.read_bytes() == first_bytes
    assert not tuple(output_dir.glob("*.tmp"))
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(CONFORMATION_LABELS_COLUMNS)
    assert [row["frame_index"] for row in rows] == ["2", "100", "900", "1200"]
    assert rows[0]["time_ps"] == "2.5"
    assert rows[1]["time_ps"] == ""
    assert rows[0]["silhouette_score"] == "1"
    assert rows[0]["distance_to_centroid"] == "0"
    assert [row["is_representative"] for row in rows] == [
        "true",
        "false",
        "true",
        "false",
    ]

    skipped_output = write_conformation_labels_csv(
        build_conformation_clusters(
            _matrix(values=((0,), (1,)), frame_indexes=(5, 100), times=(None, None))
        ),
        tmp_path / "skipped",
    )
    with skipped_output.open(encoding="utf-8", newline="") as csv_file:
        skipped_rows = list(csv.DictReader(csv_file))
    for field in (
        "state_id",
        "cluster_label",
        "selected_k",
        "silhouette_score",
        "is_representative",
        "distance_to_centroid",
    ):
        assert all(row[field] == "" for row in skipped_rows)

    empty_output = write_conformation_labels_csv(
        build_conformation_clusters(_matrix(values=(), frame_indexes=(), times=())),
        tmp_path / "empty",
    )
    assert empty_output.read_text(encoding="utf-8") == ",".join(
        CONFORMATION_LABELS_COLUMNS
    ) + "\n"


def test_invalid_fingerprint_and_clustering_contracts_are_rejected(
    tmp_path: Path,
) -> None:
    fingerprints = _matrix()
    with pytest.raises(ConformationClusteringError, match="binary integers"):
        build_conformation_clusters(
            replace(fingerprints, values=((2,), *fingerprints.values[1:]))
        )
    with pytest.raises(ConformationClusteringError, match="column count"):
        build_conformation_clusters(
            replace(fingerprints, values=((1, 0), *fingerprints.values[1:]))
        )
    with pytest.raises(ConformationClusteringError, match="max_k"):
        ConformationClusteringConfig(max_k=1)

    skipped = build_conformation_clusters(
        _matrix(values=((0,), (1,)), frame_indexes=(5, 100), times=(None, None))
    )
    invented = replace(skipped.rows[0], state_id=1)
    with pytest.raises(ConformationClusteringError, match="invented"):
        write_conformation_labels_csv(
            replace(skipped, rows=(invented, *skipped.rows[1:])),
            tmp_path,
        )


def test_public_api_dependency_boundary_and_docs_record_stage22f_decision() -> None:
    assert mania.analysis.build_conformation_clusters is build_conformation_clusters
    assert mania.analysis.write_conformation_labels_csv is write_conformation_labels_csv
    assert mania.analysis.CONFORMATION_CLUSTERING_BASIS_FINGERPRINT == "fingerprint"
    assert mania.analysis.CONFORMATION_CLUSTERING_BASIS_PCA == "pca"
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "import numpy",
        "from numpy",
        "pandas",
        "pyarrow",
        "scipy",
        "sklearn",
        "build_conformation_pca_projection",
        "temporal_rin",
        "window_contact_freq",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source

    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "conformation_labels_{condition}.csv" in text
        assert "deterministic dependency-free k-means" in text
        assert "binary contact fingerprint" in text
        assert "PCA coordinates" in text
        assert "not claim notebook PCA" in text
