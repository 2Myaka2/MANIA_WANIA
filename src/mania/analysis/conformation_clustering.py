"""Deterministic Stage 22.F clustering of binary contact fingerprints."""

from __future__ import annotations

import csv
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mania.analysis.contact_fingerprints import ContactFingerprintMatrix

CONFORMATION_CLUSTERING_K_MAX = 10
CONFORMATION_CLUSTERING_ALGORITHM = "deterministic_kmeans_fingerprint"
CONFORMATION_CLUSTERING_INPUT_SOURCE = "contact_fingerprint_matrix"
CONFORMATION_CLUSTERING_PCA_STATUS = "pca_unavailable"
CONFORMATION_CLUSTERING_NOTEBOOK_PARITY = "not_pca_kmeans_parity"

CONFORMATION_CLUSTERING_STATUS_COMPUTED = "computed"
CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT = "empty_input"
CONFORMATION_CLUSTERING_STATUS_NO_FEATURES = "no_features"
CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES = "insufficient_frames"
CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX = "constant_matrix"
CONFORMATION_CLUSTERING_STATUS_NO_VALID_K = "no_valid_k"

CONFORMATION_CLUSTERING_CANDIDATE_VALID = "valid"
CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER = "empty_cluster"

CONFORMATION_LABELS_COLUMNS = (
    "condition",
    "row_index",
    "frame_index",
    "time_ps",
    "state_id",
    "cluster_label",
    "selected_k",
    "silhouette_score",
    "is_representative",
    "distance_to_centroid",
    "algorithm",
    "input_source",
    "pca_status",
    "notebook_parity",
    "status",
    "notes",
)

_FINGERPRINT_NOTE = (
    "clustered directly from binary contact fingerprints; "
    "PCA coordinates unavailable; notebook PCA-to-k-means parity not claimed"
)
_SKIPPED_FINGERPRINT_NOTE = (
    "clustering input is binary contact fingerprints; "
    "PCA coordinates unavailable; notebook PCA-to-k-means parity not claimed"
)
_STATUSES = {
    CONFORMATION_CLUSTERING_STATUS_COMPUTED,
    CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT,
    CONFORMATION_CLUSTERING_STATUS_NO_FEATURES,
    CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
    CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
    CONFORMATION_CLUSTERING_STATUS_NO_VALID_K,
}

_Vector = tuple[int, ...]
_Centroid = tuple[float, ...]


class ConformationClusteringError(ValueError):
    """Raised when fingerprints cannot form a clustering artifact."""


@dataclass(frozen=True)
class ConformationClusteringConfig:
    """Dependency-free k-means limits."""

    max_k: int = CONFORMATION_CLUSTERING_K_MAX
    max_iterations: int = 100

    def __post_init__(self) -> None:
        if type(self.max_k) is not int or self.max_k < 2:
            raise ConformationClusteringError("max_k must be an integer >= 2")
        if type(self.max_iterations) is not int or self.max_iterations < 1:
            raise ConformationClusteringError(
                "max_iterations must be a positive integer"
            )


@dataclass(frozen=True)
class ConformationClusteringCandidate:
    """Auditable result for one candidate k."""

    k: int
    silhouette_score: float | None
    status: str
    n_iterations: int
    converged: bool


@dataclass(frozen=True)
class ConformationLabelRow:
    """One fingerprint frame and its optional selected conformation state."""

    condition: str
    row_index: int
    frame_index: int
    time_ps: float | None
    state_id: int | None
    cluster_label: str | None
    selected_k: int | None
    silhouette_score: float | None
    is_representative: bool | None
    distance_to_centroid: float | None
    algorithm: str
    input_source: str
    pca_status: str
    notebook_parity: str
    status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        """Return one row in stable artifact column order."""
        return {
            column: getattr(self, column) for column in CONFORMATION_LABELS_COLUMNS
        }


@dataclass(frozen=True)
class ConformationClustering:
    """Selected clustering and artifact rows for one condition."""

    condition: str
    rows: tuple[ConformationLabelRow, ...]
    candidates: tuple[ConformationClusteringCandidate, ...]
    selected_k: int | None
    silhouette_score: float | None
    status: str
    notes: str


@dataclass(frozen=True)
class _KmeansResult:
    assignments: tuple[int, ...]
    centroids: tuple[_Centroid, ...]
    status: str
    n_iterations: int
    converged: bool


def build_conformation_clusters(
    fingerprints: ContactFingerprintMatrix,
    *,
    config: ConformationClusteringConfig | None = None,
) -> ConformationClustering:
    """Cluster accepted binary fingerprints without PCA or dependencies."""
    if not isinstance(fingerprints, ContactFingerprintMatrix):
        raise TypeError("fingerprints must be a ContactFingerprintMatrix")
    clustering_config = config or ConformationClusteringConfig()
    if not isinstance(clustering_config, ConformationClusteringConfig):
        raise TypeError("config must be a ConformationClusteringConfig")
    _validate_fingerprints(fingerprints)

    n_frames, n_features = fingerprints.shape
    if not n_frames:
        return _skipped_clustering(
            fingerprints,
            CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT,
            "fingerprint matrix contains no frames",
        )
    if not n_features:
        return _skipped_clustering(
            fingerprints,
            CONFORMATION_CLUSTERING_STATUS_NO_FEATURES,
            "fingerprint matrix contains no features",
        )
    if n_frames < 3:
        return _skipped_clustering(
            fingerprints,
            CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES,
            "at least three frames are required for silhouette selection",
        )
    if len(set(fingerprints.values)) == 1:
        return _skipped_clustering(
            fingerprints,
            CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX,
            "all fingerprint rows are identical",
        )

    candidate_results: dict[int, _KmeansResult] = {}
    candidates: list[ConformationClusteringCandidate] = []
    maximum_k = min(clustering_config.max_k, n_frames - 1)
    for k in range(2, maximum_k + 1):
        result = _run_kmeans(
            fingerprints.values,
            tuple(frame.frame_index for frame in fingerprints.frames),
            k=k,
            max_iterations=clustering_config.max_iterations,
        )
        if result.status == CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER:
            candidates.append(
                ConformationClusteringCandidate(
                    k=k,
                    silhouette_score=None,
                    status=result.status,
                    n_iterations=result.n_iterations,
                    converged=result.converged,
                )
            )
            continue
        score = _silhouette_score(fingerprints.values, result.assignments)
        candidate_results[k] = result
        candidates.append(
            ConformationClusteringCandidate(
                k=k,
                silhouette_score=score,
                status=CONFORMATION_CLUSTERING_CANDIDATE_VALID,
                n_iterations=result.n_iterations,
                converged=result.converged,
            )
        )

    valid_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.status == CONFORMATION_CLUSTERING_CANDIDATE_VALID
        and candidate.silhouette_score is not None
    )
    if not valid_candidates:
        return _skipped_clustering(
            fingerprints,
            CONFORMATION_CLUSTERING_STATUS_NO_VALID_K,
            "no candidate k produced valid non-empty clusters",
            candidates=tuple(candidates),
        )

    selected = valid_candidates[0]
    assert selected.silhouette_score is not None
    for candidate in valid_candidates[1:]:
        assert candidate.silhouette_score is not None
        if candidate.silhouette_score > selected.silhouette_score:
            selected = candidate
    selected_score = selected.silhouette_score
    assert selected_score is not None
    result = candidate_results[selected.k]
    rows = _computed_rows(
        fingerprints,
        result,
        selected_k=selected.k,
        silhouette_score=selected_score,
    )
    clustering = ConformationClustering(
        condition=fingerprints.condition,
        rows=rows,
        candidates=tuple(candidates),
        selected_k=selected.k,
        silhouette_score=selected_score,
        status=CONFORMATION_CLUSTERING_STATUS_COMPUTED,
        notes=_FINGERPRINT_NOTE,
    )
    _validate_clustering(clustering)
    return clustering


def write_conformation_labels_csv(
    clustering: ConformationClustering,
    output_dir: str | Path,
) -> Path:
    """Write ``conformation_labels_{condition}.csv`` atomically and stably."""
    if not isinstance(clustering, ConformationClustering):
        raise TypeError("clustering must be a ConformationClustering")
    _validate_clustering(clustering)
    component = re.sub(r"[^A-Za-z0-9_.-]+", "_", clustering.condition).strip(
        "._"
    )
    if not component:
        raise ConformationClusteringError(
            "condition must contain a filename-safe character"
        )
    directory = Path(output_dir)
    if directory.exists() and not directory.is_dir():
        raise ConformationClusteringError(
            "conformation labels output is not a directory"
        )
    output_path = directory / f"conformation_labels_{component}.csv"
    temporary_path: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=directory,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(
                csv_file,
                fieldnames=CONFORMATION_LABELS_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            for row in clustering.rows:
                writer.writerow(
                    {key: _csv_value(value) for key, value in row.to_dict().items()}
                )
        temporary_path.replace(output_path)
    except (OSError, csv.Error) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ConformationClusteringError(
            f"conformation labels could not be written: {output_path}"
        ) from error
    return output_path


def _run_kmeans(
    values: tuple[_Vector, ...],
    frame_indexes: tuple[int, ...],
    *,
    k: int,
    max_iterations: int,
) -> _KmeansResult:
    centroids = _initialize_centroids(values, frame_indexes, k)
    previous_assignments: tuple[int, ...] | None = None
    for iteration in range(1, max_iterations + 1):
        assignments = tuple(
            min(
                range(k),
                key=lambda cluster: _squared_distance(row, centroids[cluster]),
            )
            for row in values
        )
        if len(set(assignments)) != k:
            return _KmeansResult(
                assignments=(),
                centroids=(),
                status=CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER,
                n_iterations=iteration,
                converged=False,
            )
        centroids = _updated_centroids(values, assignments, k)
        if assignments == previous_assignments:
            return _KmeansResult(
                assignments=assignments,
                centroids=centroids,
                status=CONFORMATION_CLUSTERING_CANDIDATE_VALID,
                n_iterations=iteration,
                converged=True,
            )
        previous_assignments = assignments
    assert previous_assignments is not None
    return _KmeansResult(
        assignments=previous_assignments,
        centroids=centroids,
        status=CONFORMATION_CLUSTERING_CANDIDATE_VALID,
        n_iterations=max_iterations,
        converged=False,
    )


def _initialize_centroids(
    values: tuple[_Vector, ...],
    frame_indexes: tuple[int, ...],
    k: int,
) -> tuple[_Centroid, ...]:
    first = min(
        range(len(values)),
        key=lambda index: (values[index], frame_indexes[index]),
    )
    chosen = [first]
    while len(chosen) < k:
        remaining = (index for index in range(len(values)) if index not in chosen)
        next_index = min(
            remaining,
            key=lambda index: (
                -min(
                    _squared_distance(values[index], values[chosen_index])
                    for chosen_index in chosen
                ),
                frame_indexes[index],
            ),
        )
        chosen.append(next_index)
    return tuple(tuple(float(value) for value in values[index]) for index in chosen)


def _updated_centroids(
    values: tuple[_Vector, ...],
    assignments: tuple[int, ...],
    k: int,
) -> tuple[_Centroid, ...]:
    n_features = len(values[0])
    members = tuple(
        tuple(index for index, label in enumerate(assignments) if label == cluster)
        for cluster in range(k)
    )
    return tuple(
        tuple(
            math.fsum(values[index][column] for index in cluster_members)
            / len(cluster_members)
            for column in range(n_features)
        )
        for cluster_members in members
    )


def _silhouette_score(
    values: tuple[_Vector, ...], assignments: tuple[int, ...]
) -> float:
    clusters = tuple(sorted(set(assignments)))
    n_frames = len(values)
    if not (2 <= len(clusters) <= n_frames - 1):
        raise ConformationClusteringError("silhouette labels are not valid")
    members = {
        cluster: tuple(
            index for index, assigned in enumerate(assignments) if assigned == cluster
        )
        for cluster in clusters
    }
    samples: list[float] = []
    for index, own_cluster in enumerate(assignments):
        own_members = tuple(
            member for member in members[own_cluster] if member != index
        )
        if not own_members:
            samples.append(0.0)
            continue
        a = math.fsum(
            _euclidean_distance(values[index], values[member])
            for member in own_members
        ) / len(own_members)
        b = min(
            math.fsum(
                _euclidean_distance(values[index], values[member])
                for member in members[cluster]
            )
            / len(members[cluster])
            for cluster in clusters
            if cluster != own_cluster
        )
        denominator = max(a, b)
        samples.append(0.0 if denominator == 0.0 else (b - a) / denominator)
    return math.fsum(samples) / n_frames


def _computed_rows(
    fingerprints: ContactFingerprintMatrix,
    result: _KmeansResult,
    *,
    selected_k: int,
    silhouette_score: float,
) -> tuple[ConformationLabelRow, ...]:
    members = {
        cluster: tuple(
            index
            for index, assigned in enumerate(result.assignments)
            if assigned == cluster
        )
        for cluster in range(selected_k)
    }
    ordered_clusters = tuple(
        sorted(
            members,
            key=lambda cluster: min(
                fingerprints.frames[index].frame_index for index in members[cluster]
            ),
        )
    )
    state_by_cluster = {
        cluster: state_id
        for state_id, cluster in enumerate(ordered_clusters, start=1)
    }
    representatives = {
        cluster: min(
            members[cluster],
            key=lambda index: (
                _squared_distance(
                    fingerprints.values[index], result.centroids[cluster]
                ),
                fingerprints.frames[index].frame_index,
            ),
        )
        for cluster in ordered_clusters
    }
    rows = []
    for index, frame in enumerate(fingerprints.frames):
        cluster = result.assignments[index]
        state_id = state_by_cluster[cluster]
        rows.append(
            ConformationLabelRow(
                condition=fingerprints.condition,
                row_index=frame.row_index,
                frame_index=frame.frame_index,
                time_ps=frame.time_ps,
                state_id=state_id,
                cluster_label=f"state_{state_id}",
                selected_k=selected_k,
                silhouette_score=silhouette_score,
                is_representative=index == representatives[cluster],
                distance_to_centroid=_squared_distance(
                    fingerprints.values[index], result.centroids[cluster]
                ),
                algorithm=CONFORMATION_CLUSTERING_ALGORITHM,
                input_source=CONFORMATION_CLUSTERING_INPUT_SOURCE,
                pca_status=CONFORMATION_CLUSTERING_PCA_STATUS,
                notebook_parity=CONFORMATION_CLUSTERING_NOTEBOOK_PARITY,
                status=CONFORMATION_CLUSTERING_STATUS_COMPUTED,
                notes=_FINGERPRINT_NOTE,
            )
        )
    return tuple(rows)


def _skipped_clustering(
    fingerprints: ContactFingerprintMatrix,
    status: str,
    reason: str,
    *,
    candidates: tuple[ConformationClusteringCandidate, ...] = (),
) -> ConformationClustering:
    notes = f"{reason}; {_SKIPPED_FINGERPRINT_NOTE}"
    rows = tuple(
        ConformationLabelRow(
            condition=fingerprints.condition,
            row_index=frame.row_index,
            frame_index=frame.frame_index,
            time_ps=frame.time_ps,
            state_id=None,
            cluster_label=None,
            selected_k=None,
            silhouette_score=None,
            is_representative=None,
            distance_to_centroid=None,
            algorithm=CONFORMATION_CLUSTERING_ALGORITHM,
            input_source=CONFORMATION_CLUSTERING_INPUT_SOURCE,
            pca_status=CONFORMATION_CLUSTERING_PCA_STATUS,
            notebook_parity=CONFORMATION_CLUSTERING_NOTEBOOK_PARITY,
            status=status,
            notes=notes,
        )
        for frame in fingerprints.frames
    )
    clustering = ConformationClustering(
        condition=fingerprints.condition,
        rows=rows,
        candidates=candidates,
        selected_k=None,
        silhouette_score=None,
        status=status,
        notes=notes,
    )
    _validate_clustering(clustering)
    return clustering


def _validate_fingerprints(fingerprints: ContactFingerprintMatrix) -> None:
    n_frames, n_features = fingerprints.shape
    if len(fingerprints.values) != n_frames:
        raise ConformationClusteringError(
            "fingerprint row count does not match frames"
        )
    frame_indexes: set[int] = set()
    for row_index, (frame, values) in enumerate(
        zip(fingerprints.frames, fingerprints.values, strict=True)
    ):
        if frame.condition != fingerprints.condition:
            raise ConformationClusteringError(
                "fingerprint frame condition does not match matrix"
            )
        if frame.row_index != row_index:
            raise ConformationClusteringError(
                "fingerprint frame row_index must match deterministic row order"
            )
        if frame.frame_index in frame_indexes:
            raise ConformationClusteringError(
                "fingerprint frame_index values must be unique"
            )
        frame_indexes.add(frame.frame_index)
        if len(values) != n_features:
            raise ConformationClusteringError(
                "fingerprint column count does not match features"
            )
        if any(type(value) is not int or value not in (0, 1) for value in values):
            raise ConformationClusteringError(
                "fingerprint values must be binary integers"
            )
    for column_index, feature in enumerate(fingerprints.features):
        if feature.condition != fingerprints.condition:
            raise ConformationClusteringError(
                "fingerprint feature condition does not match matrix"
            )
        if feature.column_index != column_index:
            raise ConformationClusteringError(
                "fingerprint feature column_index must match deterministic order"
            )


def _validate_clustering(clustering: ConformationClustering) -> None:
    if clustering.status not in _STATUSES:
        raise ConformationClusteringError("unsupported conformation status")
    if clustering.status == CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT:
        if clustering.rows:
            raise ConformationClusteringError("empty input must not contain rows")
    for expected_row_index, row in enumerate(clustering.rows):
        if row.condition != clustering.condition:
            raise ConformationClusteringError(
                "conformation row condition does not match"
            )
        if row.row_index != expected_row_index:
            raise ConformationClusteringError(
                "conformation row_index must match deterministic row order"
            )
        if (
            row.algorithm != CONFORMATION_CLUSTERING_ALGORITHM
            or row.input_source != CONFORMATION_CLUSTERING_INPUT_SOURCE
            or row.pca_status != CONFORMATION_CLUSTERING_PCA_STATUS
            or row.notebook_parity != CONFORMATION_CLUSTERING_NOTEBOOK_PARITY
            or row.status != clustering.status
            or row.notes != clustering.notes
        ):
            raise ConformationClusteringError(
                "conformation row metadata does not match clustering"
            )
    if clustering.status == CONFORMATION_CLUSTERING_STATUS_COMPUTED:
        if clustering.selected_k is None or clustering.silhouette_score is None:
            raise ConformationClusteringError(
                "computed clustering must contain k and silhouette"
            )
        for row in clustering.rows:
            if (
                row.state_id is None
                or row.cluster_label is None
                or row.selected_k != clustering.selected_k
                or row.silhouette_score != clustering.silhouette_score
                or row.is_representative is None
                or row.distance_to_centroid is None
            ):
                raise ConformationClusteringError(
                    "computed row is missing clustering values"
                )
        state_ids = {row.state_id for row in clustering.rows}
        if state_ids != set(range(1, clustering.selected_k + 1)):
            raise ConformationClusteringError("computed state IDs are not consecutive")
        for state_id in state_ids:
            if sum(
                row.state_id == state_id and row.is_representative is True
                for row in clustering.rows
            ) != 1:
                raise ConformationClusteringError(
                    "each state must have exactly one representative"
                )
    else:
        if clustering.selected_k is not None or clustering.silhouette_score is not None:
            raise ConformationClusteringError(
                "skipped clustering must not contain selected values"
            )
        for row in clustering.rows:
            optional_values = (
                row.state_id,
                row.cluster_label,
                row.selected_k,
                row.silhouette_score,
                row.is_representative,
                row.distance_to_centroid,
            )
            if any(value is not None for value in optional_values):
                raise ConformationClusteringError(
                    "skipped row must not contain invented clustering values"
                )


def _squared_distance(
    left: tuple[int | float, ...], right: tuple[int | float, ...]
) -> float:
    return math.fsum((left[index] - right[index]) ** 2 for index in range(len(left)))


def _euclidean_distance(left: _Vector, right: _Vector) -> float:
    return math.sqrt(_squared_distance(left, right))


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return format(value, ".15g")
    return value


__all__ = [
    "CONFORMATION_CLUSTERING_ALGORITHM",
    "CONFORMATION_CLUSTERING_CANDIDATE_EMPTY_CLUSTER",
    "CONFORMATION_CLUSTERING_CANDIDATE_VALID",
    "CONFORMATION_CLUSTERING_INPUT_SOURCE",
    "CONFORMATION_CLUSTERING_K_MAX",
    "CONFORMATION_CLUSTERING_NOTEBOOK_PARITY",
    "CONFORMATION_CLUSTERING_PCA_STATUS",
    "CONFORMATION_CLUSTERING_STATUS_COMPUTED",
    "CONFORMATION_CLUSTERING_STATUS_CONSTANT_MATRIX",
    "CONFORMATION_CLUSTERING_STATUS_EMPTY_INPUT",
    "CONFORMATION_CLUSTERING_STATUS_INSUFFICIENT_FRAMES",
    "CONFORMATION_CLUSTERING_STATUS_NO_FEATURES",
    "CONFORMATION_CLUSTERING_STATUS_NO_VALID_K",
    "CONFORMATION_LABELS_COLUMNS",
    "ConformationClustering",
    "ConformationClusteringCandidate",
    "ConformationClusteringConfig",
    "ConformationClusteringError",
    "ConformationLabelRow",
    "build_conformation_clusters",
    "write_conformation_labels_csv",
]
