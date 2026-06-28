import pytest

from mania.preprocessing.trajectory_contacts import InteractionAccumulator


def add_observation(
    accumulator: InteractionAccumulator,
    *,
    frame_index: int,
    resid_i: int | str = "123",
    resid_j: int | str = "150",
    edge_type: str = "residue_contact",
    distance_A: float,
) -> None:
    accumulator.add(
        condition_name="normal",
        frame_index=frame_index,
        resid_i=resid_i,
        resid_j=resid_j,
        edge_type=edge_type,
        distance_A=distance_A,
    )


def test_add_and_finalize_uses_sampled_denominator_and_source_frames() -> None:
    accumulator = InteractionAccumulator()
    add_observation(accumulator, frame_index=0, distance_A=3.0)
    add_observation(accumulator, frame_index=2, distance_A=5.0)

    rows = accumulator.finalize(frame_count=4)

    assert len(rows) == 1
    row = rows[0]
    assert (row.resid_i, row.resid_j) == ("123", "150")
    assert row.edge_type == "residue_contact"
    assert row.observed_frame_count == 2
    assert row.occurrence_count == 2
    assert row.sampled_frame_count == 4
    assert row.contact_freq == 0.5
    assert row.mean_dist_A == 4.0
    assert row.std_dist_A == 1.0
    assert row.first_seen_frame == 0
    assert row.last_seen_frame == 2


def test_finalize_filters_after_frequency_aggregation() -> None:
    accumulator = InteractionAccumulator()
    add_observation(accumulator, frame_index=0, distance_A=3.0)

    assert accumulator.finalize(frame_count=4, min_frequency=0.5) == ()
    assert len(
        accumulator.finalize(frame_count=4, min_frequency=0.25)
    ) == 1


def test_multiple_edge_types_are_independent_and_deterministic() -> None:
    accumulator = InteractionAccumulator()
    add_observation(
        accumulator,
        frame_index=2,
        resid_i=150,
        resid_j=123,
        edge_type="vdw",
        distance_A=4.0,
    )
    add_observation(
        accumulator,
        frame_index=0,
        resid_i=123,
        resid_j=150,
        edge_type="hbond",
        distance_A=3.0,
    )

    rows = accumulator.finalize(frame_count=4)

    assert [row.edge_type for row in rows] == ["hbond", "vdw"]
    assert [(row.resid_i, row.resid_j) for row in rows] == [
        (123, 150),
        (123, 150),
    ]
    assert accumulator.finalize(frame_count=4, edge_type="vdw") == (
        rows[1],
    )


def test_duplicate_occurrences_in_one_frame_count_as_one_observed_frame() -> None:
    accumulator = InteractionAccumulator()
    add_observation(accumulator, frame_index=2, distance_A=3.0)
    add_observation(accumulator, frame_index=2, distance_A=5.0)

    row = accumulator.finalize(frame_count=2)[0]

    assert row.observed_frame_count == 1
    assert row.occurrence_count == 2
    assert row.contact_freq == 0.5
    assert row.mean_dist_A == 4.0


@pytest.mark.parametrize("min_frequency", (-0.1, 1.1))
def test_finalize_rejects_invalid_frequency(min_frequency: float) -> None:
    with pytest.raises(ValueError, match="min_frequency"):
        InteractionAccumulator().finalize(
            frame_count=1,
            min_frequency=min_frequency,
        )
