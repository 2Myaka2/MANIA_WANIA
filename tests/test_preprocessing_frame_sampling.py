import json

import pytest

from mania.preprocessing import (
    PreprocessingFrameSamplingOptions,
    iter_sampled_trajectory_frames,
)


def sampled_indexes(
    options: PreprocessingFrameSamplingOptions,
    *,
    frame_count: int = 10,
) -> list[int]:
    return [
        source_frame_index
        for source_frame_index, _ in iter_sampled_trajectory_frames(
            list(range(frame_count)),
            options,
        )
    ]


def test_default_options_are_valid_and_json_safe() -> None:
    options = PreprocessingFrameSamplingOptions()

    assert options.frame_start == 0
    assert options.frame_stop is None
    assert options.frame_stride == 1
    assert options.max_frames is None
    assert json.loads(json.dumps(options.to_dict())) == options.to_dict()


@pytest.mark.parametrize("frame_start", [-1, True, False])
def test_frame_start_invalid(frame_start: object) -> None:
    with pytest.raises(ValueError, match="frame_start"):
        PreprocessingFrameSamplingOptions(
            frame_start=frame_start,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("frame_stride", [0, -1, True, False])
def test_frame_stride_invalid(frame_stride: object) -> None:
    with pytest.raises(ValueError, match="frame_stride"):
        PreprocessingFrameSamplingOptions(
            frame_stride=frame_stride,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("frame_stop", [0, 2, True, False])
def test_frame_stop_invalid(frame_stop: object) -> None:
    with pytest.raises(ValueError, match="frame_stop"):
        PreprocessingFrameSamplingOptions(
            frame_start=2,
            frame_stop=frame_stop,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("max_frames", [0, -1, True, False])
def test_max_frames_invalid(max_frames: object) -> None:
    with pytest.raises(ValueError, match="max_frames"):
        PreprocessingFrameSamplingOptions(
            max_frames=max_frames,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("options", "expected_indexes"),
    (
        (PreprocessingFrameSamplingOptions(), list(range(10))),
        (PreprocessingFrameSamplingOptions(frame_stride=2), [0, 2, 4, 6, 8]),
        (PreprocessingFrameSamplingOptions(frame_start=3), list(range(3, 10))),
        (
            PreprocessingFrameSamplingOptions(frame_start=3, frame_stride=2),
            [3, 5, 7, 9],
        ),
        (PreprocessingFrameSamplingOptions(frame_stop=7), list(range(7))),
        (
            PreprocessingFrameSamplingOptions(
                frame_start=2,
                frame_stop=8,
                frame_stride=3,
            ),
            [2, 5],
        ),
        (PreprocessingFrameSamplingOptions(max_frames=3), [0, 1, 2]),
        (
            PreprocessingFrameSamplingOptions(
                frame_start=2,
                frame_stride=2,
                max_frames=3,
            ),
            [2, 4, 6],
        ),
    ),
)
def test_iter_sampled_trajectory_frames_yields_source_indexes(
    options: PreprocessingFrameSamplingOptions,
    expected_indexes: list[int],
) -> None:
    assert sampled_indexes(options) == expected_indexes
