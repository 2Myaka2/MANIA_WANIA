import json

import pytest

from mania.preprocessing import (
    PreprocessingContactComputationLimits,
    PreprocessingContactProgressEvent,
)


def test_default_contact_computation_limits_are_unlimited_and_json_safe(
) -> None:
    limits = PreprocessingContactComputationLimits()

    assert limits.max_residue_pairs_per_frame is None
    assert limits.max_atom_distance_evaluations_per_frame is None
    assert json.loads(json.dumps(limits.to_dict())) == limits.to_dict()


def test_contact_computation_limits_accept_positive_ints_and_none() -> None:
    limits = PreprocessingContactComputationLimits(
        max_residue_pairs_per_frame=1,
        max_atom_distance_evaluations_per_frame=None,
    )

    assert limits.max_residue_pairs_per_frame == 1
    assert limits.max_atom_distance_evaluations_per_frame is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("max_residue_pairs_per_frame", 0),
        ("max_residue_pairs_per_frame", -1),
        ("max_residue_pairs_per_frame", True),
        ("max_residue_pairs_per_frame", False),
        ("max_atom_distance_evaluations_per_frame", 0),
        ("max_atom_distance_evaluations_per_frame", -1),
        ("max_atom_distance_evaluations_per_frame", True),
        ("max_atom_distance_evaluations_per_frame", False),
    ),
)
def test_contact_computation_limits_reject_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactComputationLimits(**{field_name: value})


def test_contact_progress_event_validates_and_serializes() -> None:
    event = PreprocessingContactProgressEvent(
        condition_name="normal",
        frame_index=0,
        stage="frame_candidates_built",
        message="candidate residue pairs=1",
        residue_count=2,
        candidate_pair_count=1,
    )

    assert event.condition_name == "normal"
    assert event.frame_index == 0
