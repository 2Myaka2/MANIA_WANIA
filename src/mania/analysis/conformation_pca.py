"""Deterministic Stage 22.E contact-fingerprint PCA artifact contract."""

from __future__ import annotations

import csv
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mania.analysis.contact_fingerprints import ContactFingerprintMatrix

CONFORMATION_PCA_STATUS_EMPTY_INPUT = "empty_input"
CONFORMATION_PCA_STATUS_ONE_FRAME = "one_frame"
CONFORMATION_PCA_STATUS_NO_FEATURES = "no_features"
CONFORMATION_PCA_STATUS_CONSTANT_MATRIX = "constant_matrix"
CONFORMATION_PCA_STATUS_UNAVAILABLE = "pca_unavailable"

_SKIPPED_STATUSES = {
    CONFORMATION_PCA_STATUS_EMPTY_INPUT,
    CONFORMATION_PCA_STATUS_ONE_FRAME,
    CONFORMATION_PCA_STATUS_NO_FEATURES,
    CONFORMATION_PCA_STATUS_CONSTANT_MATRIX,
    CONFORMATION_PCA_STATUS_UNAVAILABLE,
}

CONFORMATION_PCA_COLUMNS = (
    "condition",
    "row_index",
    "frame_index",
    "time_ps",
    "pc1",
    "pc2",
    "pc3",
    "explained_variance_ratio_pc1",
    "explained_variance_ratio_pc2",
    "explained_variance_ratio_pc3",
    "n_components",
    "n_features",
    "n_frames",
    "status",
    "notes",
)


class ConformationPcaError(ValueError):
    """Raised when a fingerprint matrix cannot form the PCA artifact contract."""


@dataclass(frozen=True)
class ConformationPcaRow:
    """Projection metadata and optional coordinates for one fingerprint frame."""

    condition: str
    row_index: int
    frame_index: int
    time_ps: float | None
    pc1: float | None
    pc2: float | None
    pc3: float | None
    explained_variance_ratio_pc1: float | None
    explained_variance_ratio_pc2: float | None
    explained_variance_ratio_pc3: float | None
    n_components: int
    n_features: int
    n_frames: int
    status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        """Return one row in stable artifact column order."""
        return {
            column: getattr(self, column) for column in CONFORMATION_PCA_COLUMNS
        }


@dataclass(frozen=True)
class ConformationPcaProjection:
    """Stage 22.E projection result for one condition."""

    condition: str
    rows: tuple[ConformationPcaRow, ...]
    n_components: int
    n_features: int
    n_frames: int
    status: str
    notes: str


def build_conformation_pca_projection(
    fingerprints: ContactFingerprintMatrix,
) -> ConformationPcaProjection:
    """Build a truthful PCA artifact result from accepted Stage 22.D values.

    The current accepted dependency boundary has no numerical linear-algebra
    backend. Non-degenerate inputs therefore receive ``pca_unavailable`` and
    no invented coordinates. Deterministic centering is still used to
    distinguish constant binary matrices from non-degenerate inputs.
    """
    if not isinstance(fingerprints, ContactFingerprintMatrix):
        raise TypeError("fingerprints must be a ContactFingerprintMatrix")
    _validate_fingerprints(fingerprints)

    n_frames, n_features = fingerprints.shape
    if not n_frames:
        status = CONFORMATION_PCA_STATUS_EMPTY_INPUT
        notes = "fingerprint matrix contains no frames"
    elif not n_features:
        status = CONFORMATION_PCA_STATUS_NO_FEATURES
        notes = "fingerprint matrix contains no features"
    elif n_frames == 1:
        status = CONFORMATION_PCA_STATUS_ONE_FRAME
        notes = "PCA requires at least two frames"
    elif _total_centered_sum_of_squares(fingerprints.values) == 0.0:
        status = CONFORMATION_PCA_STATUS_CONSTANT_MATRIX
        notes = "centered fingerprint matrix has zero total variance"
    else:
        status = CONFORMATION_PCA_STATUS_UNAVAILABLE
        notes = "no accepted numerical PCA backend is available"

    rows = tuple(
        ConformationPcaRow(
            condition=fingerprints.condition,
            row_index=frame.row_index,
            frame_index=frame.frame_index,
            time_ps=frame.time_ps,
            pc1=None,
            pc2=None,
            pc3=None,
            explained_variance_ratio_pc1=None,
            explained_variance_ratio_pc2=None,
            explained_variance_ratio_pc3=None,
            n_components=0,
            n_features=n_features,
            n_frames=n_frames,
            status=status,
            notes=notes,
        )
        for frame in fingerprints.frames
    )
    return ConformationPcaProjection(
        condition=fingerprints.condition,
        rows=rows,
        n_components=0,
        n_features=n_features,
        n_frames=n_frames,
        status=status,
        notes=notes,
    )


def write_conformation_pca_csv(
    projection: ConformationPcaProjection,
    output_dir: str | Path,
) -> Path:
    """Write ``conformation_pca_{condition}.csv`` atomically and stably."""
    if not isinstance(projection, ConformationPcaProjection):
        raise TypeError("projection must be a ConformationPcaProjection")
    _validate_projection(projection)
    component = re.sub(r"[^A-Za-z0-9_.-]+", "_", projection.condition).strip(
        "._"
    )
    if not component:
        raise ConformationPcaError(
            "condition must contain a filename-safe character"
        )
    directory = Path(output_dir)
    if directory.exists() and not directory.is_dir():
        raise ConformationPcaError("conformation PCA output is not a directory")
    output_path = directory / f"conformation_pca_{component}.csv"
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
                fieldnames=CONFORMATION_PCA_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            for row in projection.rows:
                writer.writerow(
                    {key: _csv_value(value) for key, value in row.to_dict().items()}
                )
        temporary_path.replace(output_path)
    except (OSError, csv.Error) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ConformationPcaError(
            f"conformation PCA could not be written: {output_path}"
        ) from error
    return output_path


def _validate_fingerprints(fingerprints: ContactFingerprintMatrix) -> None:
    n_frames, n_features = fingerprints.shape
    if len(fingerprints.values) != n_frames:
        raise ConformationPcaError("fingerprint row count does not match frames")
    for row_index, (frame, values) in enumerate(
        zip(fingerprints.frames, fingerprints.values, strict=True)
    ):
        if frame.condition != fingerprints.condition:
            raise ConformationPcaError(
                "fingerprint frame condition does not match matrix"
            )
        if frame.row_index != row_index:
            raise ConformationPcaError(
                "fingerprint frame row_index must match deterministic row order"
            )
        if len(values) != n_features:
            raise ConformationPcaError(
                "fingerprint column count does not match features"
            )
        if any(type(value) is not int or value not in (0, 1) for value in values):
            raise ConformationPcaError("fingerprint values must be binary integers")
    for column_index, feature in enumerate(fingerprints.features):
        if feature.condition != fingerprints.condition:
            raise ConformationPcaError(
                "fingerprint feature condition does not match matrix"
            )
        if feature.column_index != column_index:
            raise ConformationPcaError(
                "fingerprint feature column_index must match deterministic order"
            )


def _total_centered_sum_of_squares(
    values: tuple[tuple[int, ...], ...],
) -> float:
    n_frames = len(values)
    n_features = len(values[0])
    means = tuple(
        math.fsum(row[column] for row in values) / n_frames
        for column in range(n_features)
    )
    return math.fsum(
        (value - means[column]) ** 2
        for row in values
        for column, value in enumerate(row)
    )


def _validate_projection(projection: ConformationPcaProjection) -> None:
    if projection.n_frames != len(projection.rows):
        raise ConformationPcaError("projection n_frames does not match rows")
    if projection.status not in _SKIPPED_STATUSES:
        raise ConformationPcaError("unsupported conformation PCA status")
    if projection.n_components != 0:
        raise ConformationPcaError(
            "unavailable PCA projection must have zero components"
        )
    for expected_row_index, row in enumerate(projection.rows):
        if row.condition != projection.condition:
            raise ConformationPcaError("projection row condition does not match")
        if row.row_index != expected_row_index:
            raise ConformationPcaError(
                "projection row_index must match deterministic row order"
            )
        if (
            row.n_components != projection.n_components
            or row.n_features != projection.n_features
            or row.n_frames != projection.n_frames
            or row.status != projection.status
            or row.notes != projection.notes
        ):
            raise ConformationPcaError(
                "projection row metadata does not match projection"
            )
        numerical_fields = (
            row.pc1,
            row.pc2,
            row.pc3,
            row.explained_variance_ratio_pc1,
            row.explained_variance_ratio_pc2,
            row.explained_variance_ratio_pc3,
        )
        if any(value is not None for value in numerical_fields):
            raise ConformationPcaError(
                "unavailable PCA projection must not contain numerical values"
            )


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".15g")
    return value


__all__ = [
    "CONFORMATION_PCA_COLUMNS",
    "CONFORMATION_PCA_STATUS_CONSTANT_MATRIX",
    "CONFORMATION_PCA_STATUS_EMPTY_INPUT",
    "CONFORMATION_PCA_STATUS_NO_FEATURES",
    "CONFORMATION_PCA_STATUS_ONE_FRAME",
    "CONFORMATION_PCA_STATUS_UNAVAILABLE",
    "ConformationPcaError",
    "ConformationPcaProjection",
    "ConformationPcaRow",
    "build_conformation_pca_projection",
    "write_conformation_pca_csv",
]
