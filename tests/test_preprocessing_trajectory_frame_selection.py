"""Exact enumeration executes a decision without reading time or random access."""

import pytest

from mania.preprocessing.trajectory_frame_selection import (
    ExplicitFrameSelectionError,
    iter_selected_trajectory_frames,
)


@pytest.mark.parametrize("indexes", [(0,), (4,), (0, 2, 5), (1, 4, 9)])
def test_exact_indexes_and_immediate_stop(indexes):
    visited = []
    frames = [object() for _ in range(10)]

    def trajectory():
        for index, frame in enumerate(frames):
            visited.append(index)
            yield frame
        raise AssertionError("Iterator must stop at the last requested frame")

    assert list(iter_selected_trajectory_frames(trajectory(), indexes)) == [
        (i, frames[i]) for i in indexes
    ]
    assert visited == list(range(indexes[-1] + 1))


@pytest.mark.parametrize(
    "indexes", [[], [0], (), (1, 1), (2, 1), (-1,), (True,), (1.0,), ("1",)]
)
def test_invalid_selection(indexes):
    def forbidden():
        raise AssertionError("Invalid selection must not start iteration")
        yield

    with pytest.raises(ExplicitFrameSelectionError):
        list(iter_selected_trajectory_frames(forbidden(), indexes))


def test_exhausted_source_reports_incomplete_selection():
    iterator = iter_selected_trajectory_frames(iter([object()] * 3), (1, 5))
    assert next(iterator)[0] == 1
    with pytest.raises(ExplicitFrameSelectionError, match="Trajectory ended"):
        next(iterator)
