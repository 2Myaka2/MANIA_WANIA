import csv
import math
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

import mania.analysis
import mania.analysis.conformation_pca as pca_module
from mania.analysis import (
    CONFORMATION_PCA_COLUMNS,
    CONFORMATION_PCA_STATUS_COMPUTED,
    CONFORMATION_PCA_STATUS_CONSTANT_MATRIX,
    CONFORMATION_PCA_STATUS_EMPTY_INPUT,
    CONFORMATION_PCA_STATUS_FAILED,
    CONFORMATION_PCA_STATUS_NO_FEATURES,
    CONFORMATION_PCA_STATUS_ONE_FRAME,
    CONFORMATION_PCA_STATUS_UNAVAILABLE,
    ConformationPcaError,
    ContactFingerprintFeature,
    ContactFingerprintFrame,
    ContactFingerprintMatrix,
    build_conformation_pca_projection,
    write_conformation_pca_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "mania" / "analysis" / "conformation_pca.py"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _feature(column_index: int) -> ContactFingerprintFeature:
    residue_index_j = column_index + 2
    return ContactFingerprintFeature(
        condition="normal",
        feature_id=f"normal:1--{residue_index_j}:vdw",
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
    values: tuple[tuple[int, ...], ...] = (
        (1, 0, 0),
        (0, 1, 0),
        (1, 1, 0),
        (0, 0, 1),
    ),
    *,
    frame_indexes: tuple[int, ...] = (2, 100, 900, 1200),
    times: tuple[float | None, ...] = (2.5, None, 9.0, 12.0),
) -> ContactFingerprintMatrix:
    n_features = len(values[0]) if values else 0
    return ContactFingerprintMatrix(
        condition="normal",
        frames=tuple(
            ContactFingerprintFrame(
                condition="normal",
                row_index=row_index,
                frame_index=frame_index,
                time_ps=times[row_index],
            )
            for row_index, frame_index in enumerate(frame_indexes)
        ),
        features=tuple(_feature(index) for index in range(n_features)),
        values=values,
        status="computed",
        notes="",
    )


def test_nonconstant_binary_fingerprints_have_default_disabled_projection(
) -> None:
    fingerprints = _matrix()
    projection = build_conformation_pca_projection(fingerprints)

    assert projection.condition == "normal"
    assert projection.status == CONFORMATION_PCA_STATUS_UNAVAILABLE
    assert projection.n_components == 0
    assert projection.n_features == 3
    assert projection.n_frames == 4
    assert [row.row_index for row in projection.rows] == [0, 1, 2, 3]
    assert [row.frame_index for row in projection.rows] == [2, 100, 900, 1200]
    assert [row.time_ps for row in projection.rows] == [2.5, None, 9.0, 12.0]
    assert all(
        (
            row.pc1,
            row.pc2,
            row.pc3,
            row.explained_variance_ratio_pc1,
            row.explained_variance_ratio_pc2,
            row.explained_variance_ratio_pc3,
        )
        == (None, None, None, None, None, None)
        for row in projection.rows
    )
    assert "not requested" in projection.notes


def test_numpy_is_direct_dependency_without_broader_numerical_stack() -> None:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    dependency_names = {
        requirement.split(">=", maxsplit=1)[0].split("<", maxsplit=1)[0].lower()
        for requirement in dependencies
        if isinstance(requirement, str)
    }

    assert "numpy" in dependency_names
    assert dependency_names.isdisjoint({"scikit-learn", "scipy", "pandas"})


def test_disabled_pca_does_not_import_numpy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(name: str) -> object:
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(pca_module.importlib, "import_module", fail_import)

    projection = build_conformation_pca_projection(_matrix())

    assert projection.status == CONFORMATION_PCA_STATUS_UNAVAILABLE
    assert projection.n_components == 0


def test_explicit_pca_computes_centered_rank_one_projection() -> None:
    fingerprints = _matrix(
        values=((1,), (0,), (0,)),
        frame_indexes=(10, 20, 30),
        times=(0.0, 1.0, 2.0),
    )

    projection = build_conformation_pca_projection(fingerprints, enable_pca=True)

    assert projection.status == CONFORMATION_PCA_STATUS_COMPUTED
    assert projection.n_components == 1
    assert projection.n_features == 1
    assert projection.n_frames == 3
    assert "centered NumPy SVD" in projection.notes
    assert "parity not claimed" in projection.notes
    assert [row.pc1 for row in projection.rows] == pytest.approx(
        [2.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0]
    )
    assert all(row.pc2 is None and row.pc3 is None for row in projection.rows)
    assert [
        row.explained_variance_ratio_pc1 for row in projection.rows
    ] == pytest.approx([1.0, 1.0, 1.0])
    assert all(
        row.explained_variance_ratio_pc2 is None
        and row.explained_variance_ratio_pc3 is None
        for row in projection.rows
    )


def test_explicit_pca_limits_components_to_numerical_rank() -> None:
    rank_deficient = _matrix(
        values=((1, 1), (0, 0), (0, 0)),
        frame_indexes=(10, 20, 30),
        times=(None, None, None),
    )
    rank_three = _matrix(
        values=(
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 1),
            (1, 0, 1),
        ),
        frame_indexes=(0, 1, 2, 3, 4),
        times=(None, None, None, None, None),
    )

    rank_deficient_projection = build_conformation_pca_projection(
        rank_deficient,
        enable_pca=True,
    )
    rank_three_projection = build_conformation_pca_projection(
        rank_three,
        enable_pca=True,
    )

    assert rank_deficient_projection.n_components == 1
    assert all(
        row.pc1 is not None and row.pc2 is None and row.pc3 is None
        for row in rank_deficient_projection.rows
    )
    assert rank_three_projection.n_components == 3
    assert all(
        row.pc1 is not None and row.pc2 is not None and row.pc3 is not None
        for row in rank_three_projection.rows
    )


def test_explicit_pca_is_deterministic_and_csv_is_byte_stable(
    tmp_path: Path,
) -> None:
    first_projection = build_conformation_pca_projection(
        _matrix(),
        enable_pca=True,
    )
    second_projection = build_conformation_pca_projection(
        _matrix(),
        enable_pca=True,
    )
    output_dir = tmp_path / "analysis" / "normal"
    output = write_conformation_pca_csv(first_projection, output_dir)
    first_bytes = output.read_bytes()
    write_conformation_pca_csv(second_projection, output_dir)
    text = output.read_text(encoding="utf-8").lower()

    assert first_projection == second_projection
    assert output.read_bytes() == first_bytes
    assert "nan" not in text
    assert "inf" not in text
    assert all(
        value is None or math.isfinite(value)
        for row in first_projection.rows
        for value in (
            row.pc1,
            row.pc2,
            row.pc3,
            row.explained_variance_ratio_pc1,
            row.explained_variance_ratio_pc2,
            row.explained_variance_ratio_pc3,
        )
    )


def test_centered_binary_values_distinguish_constant_and_nonconstant_inputs(
) -> None:
    constant = _matrix(
        values=((1, 0), (1, 0)),
        frame_indexes=(5, 20),
        times=(None, 2.0),
    )
    nonconstant = replace(constant, values=((1, 0), (0, 0)))

    constant_projection = build_conformation_pca_projection(constant)
    nonconstant_projection = build_conformation_pca_projection(nonconstant)
    all_zero_projection = build_conformation_pca_projection(
        replace(constant, values=((0, 0), (0, 0)))
    )

    assert constant_projection.status == CONFORMATION_PCA_STATUS_CONSTANT_MATRIX
    assert all_zero_projection.status == CONFORMATION_PCA_STATUS_CONSTANT_MATRIX
    assert "zero total variance" in constant_projection.notes
    assert nonconstant_projection.status == CONFORMATION_PCA_STATUS_UNAVAILABLE
    assert all(row.pc1 is None for row in constant_projection.rows)


def test_empty_one_frame_and_zero_feature_inputs_are_explicit() -> None:
    empty = _matrix(values=(), frame_indexes=(), times=())
    one_frame = _matrix(values=((1,),), frame_indexes=(42,), times=(None,))
    zero_features = ContactFingerprintMatrix(
        condition="normal",
        frames=(
            ContactFingerprintFrame("normal", 0, 5, None),
            ContactFingerprintFrame("normal", 1, 100, 10.0),
        ),
        features=(),
        values=((), ()),
        status="zero_features",
        notes="sampled frames contain no contact features",
    )

    empty_projection = build_conformation_pca_projection(empty)
    one_projection = build_conformation_pca_projection(one_frame)
    zero_projection = build_conformation_pca_projection(zero_features)

    assert empty_projection.status == CONFORMATION_PCA_STATUS_EMPTY_INPUT
    assert empty_projection.rows == ()
    assert one_projection.status == CONFORMATION_PCA_STATUS_ONE_FRAME
    assert zero_projection.status == CONFORMATION_PCA_STATUS_NO_FEATURES
    assert [row.frame_index for row in zero_projection.rows] == [5, 100]
    assert all(
        row.n_components == 0 and row.pc1 is None
        for row in zero_projection.rows
    )


def test_csv_is_atomic_ordered_byte_stable_and_header_only_when_empty(
    tmp_path: Path,
) -> None:
    projection = build_conformation_pca_projection(_matrix())
    output_dir = tmp_path / "analysis" / "normal"
    output = write_conformation_pca_csv(projection, output_dir)
    first_bytes = output.read_bytes()
    write_conformation_pca_csv(projection, output_dir)

    assert output.name == "conformation_pca_normal.csv"
    assert output.read_bytes() == first_bytes
    assert not tuple(output_dir.glob("*.tmp"))
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert reader.fieldnames == list(CONFORMATION_PCA_COLUMNS)
    assert [row["frame_index"] for row in rows] == ["2", "100", "900", "1200"]
    assert rows[0]["time_ps"] == "2.5"
    assert rows[1]["time_ps"] == ""
    assert rows[0]["pc1"] == rows[0]["explained_variance_ratio_pc1"] == ""
    assert rows[0]["n_components"] == "0"
    assert rows[0]["n_features"] == "3"
    assert rows[0]["status"] == CONFORMATION_PCA_STATUS_UNAVAILABLE

    empty_output = write_conformation_pca_csv(
        build_conformation_pca_projection(
            _matrix(values=(), frame_indexes=(), times=())
        ),
        tmp_path / "empty",
    )
    assert empty_output.read_text(encoding="utf-8") == ",".join(
        CONFORMATION_PCA_COLUMNS
    ) + "\n"


def test_invalid_fingerprint_values_and_shape_are_rejected(tmp_path: Path) -> None:
    fingerprints = _matrix()
    with pytest.raises(ConformationPcaError, match="binary integers"):
        build_conformation_pca_projection(
            replace(fingerprints, values=((2, 0, 0), *fingerprints.values[1:]))
        )
    with pytest.raises(ConformationPcaError, match="column count"):
        build_conformation_pca_projection(
            replace(fingerprints, values=((1, 0), *fingerprints.values[1:]))
        )

    projection = build_conformation_pca_projection(fingerprints)
    invented_row = replace(projection.rows[0], pc1=0.0)
    with pytest.raises(ConformationPcaError, match="must not contain"):
        write_conformation_pca_csv(
            replace(projection, rows=(invented_row, *projection.rows[1:])),
            tmp_path,
        )


def test_enabled_pca_failure_is_explicit_without_fake_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_compute(
        fingerprints: ContactFingerprintMatrix,
    ) -> object:
        raise RuntimeError("synthetic SVD failure")

    monkeypatch.setattr(pca_module, "_compute_pca_values", fail_compute)

    projection = build_conformation_pca_projection(_matrix(), enable_pca=True)

    assert projection.status == CONFORMATION_PCA_STATUS_FAILED
    assert projection.n_components == 0
    assert all(
        (
            row.pc1,
            row.pc2,
            row.pc3,
            row.explained_variance_ratio_pc1,
            row.explained_variance_ratio_pc2,
            row.explained_variance_ratio_pc3,
        )
        == (None, None, None, None, None, None)
        for row in projection.rows
    )


def test_public_api_and_forbidden_dependency_boundaries() -> None:
    assert (
        mania.analysis.build_conformation_pca_projection
        is build_conformation_pca_projection
    )
    assert mania.analysis.write_conformation_pca_csv is write_conformation_pca_csv
    assert (
        mania.analysis.CONFORMATION_PCA_STATUS_COMPUTED
        == CONFORMATION_PCA_STATUS_COMPUTED
    )
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "pandas",
        "pyarrow",
        "sklearn",
        "temporal_rin",
        "window_contact_freq",
        "k-means",
        "silhouette",
        "representative frame",
        "conformation_labels",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source
