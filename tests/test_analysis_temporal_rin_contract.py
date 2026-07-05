import csv
import json
from pathlib import Path

import pytest

import mania.analysis
from mania.analysis import (
    TEMP_MIN_FREQ,
    TEMP_STEP,
    TEMP_WINDOW,
    TemporalRinConfig,
    TemporalRinInputError,
    generate_temporal_windows,
    load_temporal_rin_input,
)
from mania.preprocessing.trajectory_protein_contact_export import (
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
)


def _contact_row(
    *,
    frame_index: object = 0,
    condition: object = "normal",
    edge_type: object = "vdw",
    reverse: bool = False,
    **overrides: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "condition": condition,
        "frame_index": frame_index,
        "time_ps": "",
        "residue_index_i": 1,
        "resid_i": 10,
        "resname_i": "ALA",
        "segment_id_i": "A",
        "residue_index_j": 2,
        "resid_j": 20,
        "resname_j": "GLY",
        "segment_id_j": "A",
        "edge_type": edge_type,
        "distance_A": 4.0,
    }
    if reverse:
        for field in ("residue_index", "resid", "resname", "segment_id"):
            row[f"{field}_i"], row[f"{field}_j"] = (
                row[f"{field}_j"],
                row[f"{field}_i"],
            )
    row.update(overrides)
    return row


def _write_contacts(
    path: Path,
    rows: list[dict[str, object]],
    *,
    columns: tuple[str, ...] = PROTEIN_CONTACT_PERFRAME_COLUMNS,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_temporal_config_defaults_are_explicit_valid_and_public() -> None:
    config = TemporalRinConfig()

    assert TEMP_WINDOW == config.window_size == 10
    assert TEMP_STEP == config.step_size == 10
    assert TEMP_MIN_FREQ == config.min_frequency == 0.25
    assert json.loads(json.dumps(config.to_dict())) == config.to_dict()
    assert mania.analysis.TemporalRinConfig is TemporalRinConfig


@pytest.mark.parametrize("field", ["window_size", "step_size"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_temporal_config_requires_positive_integer_sizes(
    field: str, value: object
) -> None:
    kwargs = {field: value}
    with pytest.raises(ValueError, match=field):
        TemporalRinConfig(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-0.1, 1.1, True, float("inf")])
def test_temporal_config_requires_bounded_finite_frequency(value: object) -> None:
    with pytest.raises(ValueError, match="min_frequency"):
        TemporalRinConfig(min_frequency=value)  # type: ignore[arg-type]


def test_load_is_deterministic_normalizes_pairs_and_uses_edge_priority(
    tmp_path: Path,
) -> None:
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [
            _contact_row(frame_index=20, edge_type="vdw", reverse=True),
            _contact_row(frame_index=2, edge_type="vdw"),
            _contact_row(frame_index=2, edge_type="hbond"),
            _contact_row(frame_index=7, edge_type="salt_bridge"),
        ],
    )
    config = TemporalRinConfig(window_size=2, step_size=1)

    result = load_temporal_rin_input(path, condition="normal", config=config)

    assert result.condition == "normal"
    assert result.sampled_frame_indexes == (2, 7, 20)
    assert [(row.frame_index, row.edge_type) for row in result.rows] == [
        (2, "hbond"),
        (2, "vdw"),
        (7, "salt_bridge"),
        (20, "vdw"),
    ]
    assert all(row.residue_index_i == 1 for row in result.rows)
    assert all(row.resid_i == "10" for row in result.rows)
    assert all(row.residue_index_j == 2 for row in result.rows)
    assert all(row.resid_j == "20" for row in result.rows)
    assert [window.frame_indexes for window in result.windows] == [
        (2, 7),
        (7, 20),
        (20,),
    ]


def test_windows_use_ordinal_sampled_frames_and_inclusive_boundaries() -> None:
    frames = range(0, 110, 10)

    windows = generate_temporal_windows("normal", frames)

    assert [window.window_id for window in windows] == [0, 1]
    assert windows[0].frame_indexes == tuple(range(0, 100, 10))
    assert windows[0].frame_start == 0
    assert windows[0].frame_end == 90
    assert windows[0].frame_start_ordinal == 0
    assert windows[0].frame_end_ordinal == 9
    assert windows[0].sampled_frame_count == 10
    assert windows[0].contact_frequency_denominator == 10
    assert windows[1].frame_indexes == (100,)
    assert windows[1].frame_start == windows[1].frame_end == 100
    assert windows[1].frame_start_ordinal == windows[1].frame_end_ordinal == 10
    assert windows[1].sampled_frame_count == 1
    assert windows[1].contact_frequency_denominator == 1


def test_non_contiguous_frames_are_not_inferred_and_duplicates_are_unique() -> None:
    windows = generate_temporal_windows(
        "normal",
        [100, 2, 100, 7],
        config=TemporalRinConfig(window_size=10, step_size=10),
    )

    assert len(windows) == 1
    assert windows[0].frame_indexes == (2, 7, 100)
    assert windows[0].frame_start == 2
    assert windows[0].frame_end == 100
    assert windows[0].sampled_frame_count == 3
    assert windows[0].contact_frequency_denominator != 100 - 2 + 1


def test_empty_header_only_input_has_no_sampled_frames_or_windows(
    tmp_path: Path,
) -> None:
    path = _write_contacts(tmp_path / "contacts_perframe_normal.csv", [])

    result = load_temporal_rin_input(path, condition="normal")

    assert result.condition == "normal"
    assert result.rows == ()
    assert result.sampled_frame_indexes == ()
    assert result.windows == ()


def test_one_frame_and_fewer_than_window_emit_partial_window(
    tmp_path: Path,
) -> None:
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [_contact_row(frame_index=42)],
    )

    result = load_temporal_rin_input(path, condition="normal")

    assert result.sampled_frame_indexes == (42,)
    assert len(result.windows) == 1
    assert result.windows[0].window_id == 0
    assert result.windows[0].frame_start == result.windows[0].frame_end == 42
    assert result.windows[0].sampled_frame_count == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"condition": "tumor"}, "condition mismatch"),
        ({"frame_index": "not-an-int"}, "invalid integer frame_index"),
        ({"frame_index": -1}, "frame_index must be non-negative"),
        ({"resid_i": ""}, "empty resid_i"),
        ({"edge_type": "unknown"}, "unsupported Stage 20 edge_type"),
        ({"time_ps": "nan"}, "non-finite time_ps"),
        ({"distance_A": -0.1}, "distance_A must be non-negative"),
    ],
)
def test_invalid_contact_rows_fail_deterministically(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [_contact_row(**overrides)],
    )

    with pytest.raises(TemporalRinInputError, match=message):
        load_temporal_rin_input(path, condition="normal")


def test_self_edges_and_inconsistent_residue_identity_are_rejected(
    tmp_path: Path,
) -> None:
    self_edge_path = _write_contacts(
        tmp_path / "self.csv",
        [_contact_row(residue_index_j=1)],
    )
    inconsistent_path = _write_contacts(
        tmp_path / "inconsistent.csv",
        [
            _contact_row(frame_index=0),
            _contact_row(frame_index=1, resname_i="VAL"),
        ],
    )

    with pytest.raises(TemporalRinInputError, match="self edge"):
        load_temporal_rin_input(self_edge_path, condition="normal")
    with pytest.raises(TemporalRinInputError, match="inconsistent"):
        load_temporal_rin_input(inconsistent_path, condition="normal")


def test_duplicate_normalized_frame_pair_type_is_rejected(tmp_path: Path) -> None:
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [
            _contact_row(frame_index=5),
            _contact_row(frame_index=5, reverse=True, distance_A=3.0),
        ],
    )

    with pytest.raises(TemporalRinInputError, match="duplicate frame"):
        load_temporal_rin_input(path, condition="normal")


def test_missing_accepted_stage20_column_is_rejected(tmp_path: Path) -> None:
    columns = tuple(
        column
        for column in PROTEIN_CONTACT_PERFRAME_COLUMNS
        if column != "edge_type"
    )
    row = _contact_row()
    row.pop("edge_type")
    path = _write_contacts(
        tmp_path / "contacts_perframe_normal.csv",
        [row],
        columns=columns,
    )

    with pytest.raises(TemporalRinInputError, match="missing required columns"):
        load_temporal_rin_input(path, condition="normal")


@pytest.mark.parametrize("frames", [[-1], [1.5], [True]])
def test_window_generator_rejects_invalid_sampled_frame_indexes(
    frames: list[object],
) -> None:
    with pytest.raises(ValueError, match="sampled_frame_indexes"):
        generate_temporal_windows("normal", frames)  # type: ignore[arg-type]
