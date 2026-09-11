"""Frozen specialized formulas, sparse semantics, exact computation coverage."""

from dataclasses import fields, replace
from decimal import Inexact, Rounded, localcontext
from unittest.mock import Mock

import pytest
from test_preprocessing_protein_edge_window_table import table_input

from mania.preprocessing import specialized_contact_windows as windows
from mania.preprocessing.protein_glycan_contacts import (
    PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON,
    ProteinGlycanContactFrameResult,
    ProteinGlycanContactObservation,
)
from mania.preprocessing.protein_lipid_contacts import (
    ProteinLipidContactFrameResult,
    ProteinLipidContactObservation,
)


def frames(
    binding,
    *,
    kind="lipid",
    positive=(0, 1, 3, 4),
    distances=None,
    partners=("one",),
    excluded=True,
):
    results = []
    for sample in binding.sampling_plan.selected_samples:
        i, t = sample.source_frame_index, sample.actual_time_ps
        observations = []
        if kind == "glycan" and excluded:
            observations = [
                ProteinGlycanContactObservation(
                    i,
                    t,
                    0,
                    10,
                    "ALA",
                    None,
                    partner,
                    "SAME-NAME",
                    (20 + p,),
                    0,
                    20 + p,
                    "external_metadata",
                    None,
                    None,
                    True,
                    PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON,
                    1.0,
                )
                for p, partner in enumerate(partners)
            ]
        if sample.requested_sample_index in positive:
            distance = distances[sample.requested_sample_index] if distances else 3.0
            for p, partner in enumerate(partners):
                common = (i, t, 1, "11A", "GLY", None, partner, "SAME-NAME", (20 + p,))
                observations.append(
                    ProteinLipidContactObservation(*common, distance)
                    if kind == "lipid"
                    else ProteinGlycanContactObservation(
                        *common,
                        0,
                        20 + p,
                        "external_metadata",
                        None,
                        None,
                        False,
                        None,
                        distance,
                    )
                )
        if kind == "lipid":
            results.append(
                ProteinLipidContactFrameResult(
                    i,
                    t,
                    2,
                    len(partners),
                    2 * len(partners),
                    len(observations),
                    tuple(observations),
                )
            )
        else:
            results.append(
                ProteinGlycanContactFrameResult(
                    i,
                    t,
                    2,
                    len(partners),
                    2 * len(partners),
                    len(observations),
                    len(partners) if excluded else 0,
                    tuple(observations),
                )
            )
    return tuple(results)


def aggregate(binding, results, kind="lipid", count=1):
    fn = getattr(windows, f"aggregate_protein_{kind}_contacts_by_window")
    return fn(
        binding.sampling_plan,
        binding.window_plan,
        execution_condition=binding.execution_condition,
        frame_results=results,
        partner_count=count,
    )


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
@pytest.mark.parametrize("missing,occupancy", [((), 0.8), ((2,), 1.0)])
def test_missing_vs_negative_and_episode_delegation(
    kind, missing, occupancy, monkeypatch
):
    binding = table_input(missing=missing).temporal_execution
    spy = Mock(wraps=windows.compute_window_contact_episodes)
    monkeypatch.setattr(windows, "compute_window_contact_episodes", spy)
    result = aggregate(binding, frames(binding, kind=kind), kind)
    row = result.windows[0].metrics[0]
    assert row.n_contact_frames == 4 and row.n_resolved_frames_in_window == 5 - len(
        missing
    )
    assert row.occupancy == occupancy
    assert row.n_contact_episodes == 2
    assert row.mean_episode_length_ns == row.max_episode_length_ns == 0.05
    assert row.distance_mean_A == row.distance_min_A == 3.0
    assert result.status == ("partial" if missing else "complete")
    assert spy.call_count == 2
    assert "edge_weight" not in {f.name for f in fields(row)}


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_positive_only_distances_and_excluded_carrier(kind):
    binding = table_input().temporal_execution
    result = aggregate(
        binding,
        frames(binding, kind=kind, positive=(0, 3), distances={0: 3.0, 3: 4.0}),
        kind,
    )
    assert result.observed_row_count == 1
    row = result.windows[0].metrics[0]
    assert row.protein_residue_index == 1
    assert row.n_contact_frames == 2 and row.occupancy == 0.4
    assert row.distance_mean_A == 3.5 and row.distance_min_A == 3.0
    assert row.n_contact_episodes == 2
    assert row.mean_episode_length_ns == row.max_episode_length_ns == 0.0
    assert result.excluded_raw_observation_count == (5 if kind == "glycan" else 0)


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_sparse_excluded_only_empty_and_same_name_partner_identity(kind):
    binding = table_input().temporal_execution
    empty = aggregate(binding, frames(binding, kind=kind, positive=()), kind)
    assert empty.windows[0].metrics == () and empty.observed_row_count == 0
    separate = aggregate(
        binding, frames(binding, kind=kind, partners=("one", "two")), kind, count=2
    )
    assert separate.observed_row_count == 2
    assert [
        getattr(row, f"{kind}_partner_id") for row in separate.windows[0].metrics
    ] == ["one", "two"]


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
@pytest.mark.parametrize(
    "damage", ["missing", "extra", "duplicate", "absent_kind", "pair_evidence"]
)
def test_exact_coverage_and_consistent_pair_evidence(kind, damage):
    binding = table_input().temporal_execution
    results = frames(binding, kind=kind)
    count = 1
    if damage == "missing":
        results = results[:-1]
    elif damage == "extra":
        f = results[-1]
        extra = replace(
            f,
            frame_index=999,
            contacts=tuple(replace(c, frame_index=999) for c in f.contacts),
        )
        results = (*results, extra)
    elif damage == "duplicate":
        results = (*results, results[-1])
    elif damage == "absent_kind":
        count = 0
    else:
        first = results[0]
        results = (
            replace(
                first,
                contacts=tuple(
                    replace(c, protein_resname="CHANGED") for c in first.contacts
                ),
            ),
            *results[1:],
        )
    with pytest.raises(ValueError):
        aggregate(binding, results, kind, count)


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_overlapping_windows_are_independent_and_decimal_context_isolated(kind):
    binding = table_input(count=7, length=0.2, step=0.1).temporal_execution
    results = frames(binding, kind=kind, positive=tuple(range(7)))
    expected = aggregate(binding, results, kind)
    assert len(expected.windows) == 2
    assert [w.metrics[0].n_contact_frames for w in expected.windows] == [4, 5]
    assert [w.metrics[0].n_contact_episodes for w in expected.windows] == [1, 1]
    assert [w.metrics[0].max_episode_length_ns for w in expected.windows] == [0.15, 0.2]
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert aggregate(binding, results, kind).to_dict() == expected.to_dict()
