# Contact episode and lifetime contract — Stage 28.A

## Status and scope

Stage 27 is complete, with accepted Stage 27.C checkpoint
`9fb784bdceb242d7ba503d682b804cf430c5425b`. Stage 28.A is accepted and provides the
pure
[episode engine](../src/mania/preprocessing/contact_episodes.py).
Stage 28.B [pure per-window protein-edge aggregation](protein_edge_window_aggregation_contract.md)
is implemented and consumes this engine, including occupancy and
`edge_weight = occupancy`. Episode semantics are unchanged.
Stage 28.C source-indexed table/export is accepted. Stage 28.D integrates the
accepted APIs into Dataset-aware protein-contact preprocessing with lineage,
unified validation, and real-data regression. Stage 28 is complete; Stage 29
protein-lipid / protein-glycan dynamic layers are next and have not started.
The source table remains pre-canonical and requires Stage 30 mapping before
publication. Dataset v1.0 remains unreleased. Episode science is unchanged.

The engine consumes already detected presence for one generic contact in exactly
one resolved window from exactly one trajectory/replica. Existing MANIA protein
contact detection remains authoritative. No edge/residue identity is assigned
here; 28.B associates summaries with protein edges.

## Public API and authoritative inputs

```python
compute_window_contact_episodes(
    sampling_plan: ResolvedPhysicalTimeSamplingPlan,
    window: ResolvedPhysicalTimeWindow,
    *,
    contact_source_frame_indexes: tuple[int, ...],
) -> WindowContactEpisodeSummary
```

The exact accepted [27.A sampling](physical_time_sampling_contract.md) and
[27.B window](physical_time_window_contract.md) model types are required. Window
membership is authoritative: every requested index must exist among the plan's
selected/missing records, selected indexes must map to the same source frames
in the same order, missing indexes must identify missing records, and effective
time bounds must agree with the first/last selected records. The engine does
not regenerate windows or rerun physical-time matching.

Contact indexes must be a tuple of unique, strictly increasing non-negative
integers, with bool rejected. Each must identify a selected resolved source
frame inside this window. Globally selected frames outside the window and
unresolved/unselected frames are errors. Empty input is valid. The positive
source indexes must also preserve requested-sample order; a Stage 27 plan with
nonmonotonic source labels is not silently sorted or repaired to fit the episode
model's strictly increasing source-index contract.

Invalid inputs raise `ContactEpisodeComputationError(ValueError)` with portable,
deterministic messages. No local paths or environment metadata enter results.

## Continuity and duration

**Requested sample index determines continuity. Actual resolved time determines
lifetime duration.** Two successive positive observations belong to one episode
only when `next_requested_sample_index == previous_requested_sample_index + 1`.
Intentional frame stride is not a gap: source indexes `500, 505, 510` can form
one episode when requested indexes are `0, 1, 2`.

```text
gap_tolerance = 0
episode_length_ns = (end_actual_time_ps - start_actual_time_ps) / 1000
```

Duration uses `Decimal(str(actual_time_ps))` for the actual first and last
positive observations. Arithmetic uses a local Decimal context independent of
caller precision/traps, then converts to float. Actual times are never snapped
back to requested targets. No duration is inferred from frame count or requested
stride. MANIA does not assign unobserved time before the first or after the last
positive observation; there is no half-frame correction.

| Case | Observations in ns | Episodes and durations |
| --- | --- | --- |
| Continuous | 5.00 contact, 5.05 contact, 5.10 contact | One episode, 0.10 ns |
| One frame | 5.00 contact | One episode, 0.0 ns |
| Missing break | 5.00 contact, 5.05 contact, 5.10 missing, 5.15 contact | Two episodes, 0.05 ns and 0.0 ns |
| Resolved absence break | 5.00 contact, 5.05 contact, 5.10 resolved but no contact, 5.15 contact | Two episodes, 0.05 ns and 0.0 ns |

Gap tolerance is fixed, with no configurable parameter. A window boundary always
breaks continuation. A replica/trajectory boundary always breaks continuation.
Calls have no cross-window episode state and accept only one sampling plan.
Overlapping windows may legitimately contain the same source observations;
each call calculates its own episodes independently.

## Models and summary semantics

Both public models are frozen dataclasses. `ContactEpisode` fields in order:

```text
episode_index, start_requested_sample_index, end_requested_sample_index,
start_source_frame_index, end_source_frame_index, contact_frame_count,
start_actual_time_ps, end_actual_time_ps, episode_length_ns, source_frame_indexes
```

Indexes are non-negative integers with bool rejected. Source membership is
non-empty, strictly increasing, matches its endpoints and contact count, and the
requested-index span equals that count. Actual endpoints and duration are finite
and non-negative; end is at least start. One frame has equal actual endpoints.
Stored duration must equal the float converted from the Decimal formula.

`WindowContactEpisodeSummary` fields in order:

```text
schema_version, kind, window_id, window_index, gap_tolerance,
n_contact_frames, n_contact_episodes, mean_episode_length_ns,
max_episode_length_ns, contact_source_frame_indexes, episodes
```

Schema, kind, and gap tolerance are fixed non-init fields:

```python
CONTACT_EPISODE_SCHEMA_VERSION = "mania.contact_episode_summary.v0.1"
CONTACT_EPISODE_KIND = "mania_contact_episode_summary"
CONTACT_EPISODE_GAP_TOLERANCE = 0
```

For non-empty episodes, `n_contact_frames` is the sum of episode contact counts,
`n_contact_episodes` is the episode count, mean is the arithmetic mean of
`episode_length_ns` using Decimal-based averaging before float conversion, and
max is the maximum episode duration. Episode indexes start at zero per call.
Summary validation requires ordered membership, consistent counts/aggregates,
and a requested-position break between consecutive episodes.

### No-contact state

No positive frames means zero contact frames, zero episodes, empty membership
and episode tuples, and `None` mean/max lifetime (JSON `null`). No episode exists.
This differs from one real positive frame, which creates one observed episode
with duration, mean, and max all `0.0 ns`.

### Missingness

Missing requested samples break continuity but are not observed negative-contact
frames. They contribute no positive frames and create no synthetic observations.
Resolved observations absent from the positive tuple are observed contact
absences; no separate negative-contact input is needed.

Occupancy is calculated by the separate 28.B aggregation API, with denominator
`n_resolved_frames_in_window`: `occupancy = n_contact_frames /
n_resolved_frames_in_window`. Missing requests do not enter that denominator.
Stage 32 separately evaluates sampling coverage; 28.A applies no 95% threshold
and accepts partial windows and empty windows with empty positive input.

## Determinism and scientific boundaries

`to_dict()` preserves declaration order, returns independent dictionaries,
converts tuples to JSON arrays, and retains `None`. Identical inputs serialize
byte-identically using
`json.dumps(summary.to_dict(), allow_nan=False, separators=(",", ":"))`.
No timestamps, random IDs, filesystem access, trajectory iteration, scientific
optional-stack import, Git, subprocess, or clock is involved.

Contact detection, distance calculations, cutoffs, interaction definitions, and
PBC remain unchanged. This episode engine has no minimum-image correction,
occupancy or edge weight calculation, per-edge aggregation, workflow/export integration, or
publication table. Existing scientific artifacts, Stage 20–24 contracts,
Dataset identity/binding, provenance/inventory, validation, analysis,
dependencies, and WANIA are unchanged. MANIA remains version `0.1.0`.

See the narrowly amended [frozen scientific contract](dataset_v1_scientific_contract.md)
for accepted lifetime/missingness rules and the future Stage 29 distance and
specialized-layer edge-weight clarifications. Stage 29 is not implemented here.
