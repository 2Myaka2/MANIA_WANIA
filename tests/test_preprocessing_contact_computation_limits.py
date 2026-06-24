import json

import pytest

from mania.preprocessing import (
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
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


def test_default_contact_selection_is_all_and_json_safe() -> None:
    options = PreprocessingContactDetectionOptions()

    assert options.contact_selection == "all"
    payload = options.to_dict(include_contact_selection=True)
    assert payload["contact_selection"] == "all"
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize("selection", ("all", "protein"))
def test_contact_selection_accepts_supported_values(selection: str) -> None:
    options = PreprocessingContactDetectionOptions(
        contact_selection=selection
    )

    assert options.contact_selection == selection


@pytest.mark.parametrize(
    "selection",
    ("", " ", "water", True, False, None, 1),
)
def test_contact_selection_rejects_invalid_values(
    selection: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(
            contact_selection=selection
        )
