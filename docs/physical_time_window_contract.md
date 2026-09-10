# Physical-time window contract — Stage 27.B

## Status and scope

Stage 26 is complete. Stage 27.A is accepted at checkpoint
`0ccb5f67430b26d4145caee5073bac72299bda6a`. Stage 27.B implements the pure
planner in
[`physical_time_windows.py`](../src/mania/preprocessing/physical_time_windows.py).
**Stage 27 remains incomplete; Stage 27.C workflow integration is next.**
There is no preprocessing workflow or CLI integration. Dataset v1.0 remains
unreleased, and its frozen scientific contract is unchanged.

## Input and authoritative sampling handoff

```python
plan_physical_time_windows(
    sampling_plan: ResolvedPhysicalTimeSamplingPlan,
    *,
    temporal: DatasetTemporalParameters,
) -> ResolvedPhysicalTimeWindowPlan
```

The exact accepted types are required; incorrect types raise `ValueError`.
The [Stage 27.A sampling plan](physical_time_sampling_contract.md) is authoritative.
Stage 27.A answers which requested sampling points resolved to source frames;
Stage 27.B assigns those selected/missing records to requested windows.

Temporal production start, production end, and frame stride must equal the
sampling plan's requested values using normalized Decimal numeric equality,
without tolerance. An ordinary mismatch returns a serializable failed plan
with `sampling_contract_mismatch`. Selected and missing records are combined
by `requested_sample_index`; indexes must uniquely cover
`0 .. requested_sample_count - 1`. A broken partition also returns that error.
The planner never regenerates the sampling grid from stride, reruns source-time
matching, chooses replacement frames, or mutates the input plan or request.

## Three-parameter consistency

Window length, step, and overlap describe the same schedule:

```text
0 < window_step_ns <= window_length_ns
implied_overlap_percent = (1 - window_step_ns / window_length_ns) * 100
```

The supplied overlap must agree using:

```python
WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE = 1e-6
WINDOW_OVERLAP_PERCENT_REL_TOLERANCE = 1e-9

math.isclose(
    supplied_overlap_percent,
    implied_overlap_percent,
    rel_tol=WINDOW_OVERLAP_PERCENT_REL_TOLERANCE,
    abs_tol=WINDOW_OVERLAP_PERCENT_ABS_TOLERANCE,
)
```

This is a technical numeric-representation tolerance only. It never changes
length, step, supplied overlap, or scientific boundaries. Contradictions produce
`inconsistent_window_overlap`; invalid step produces `invalid_window_step`.
Neither chooses one control as authoritative or silently rewrites another.
Failed schedules contain no windows and retain all supplied requested values.
`implied_overlap_percent` is `None` for an invalid step, otherwise it reports
the formula even when supplied overlap is inconsistent.

`DatasetTemporalParameters` itself is unchanged: its existing validation already
rejects zero step. The planner also rejects zero step deterministically if a
caller bypasses that model's validation.

## Full requested windows and interval semantics

Production start/end, length, and step enter through `Decimal(str(value))`.
For consecutive zero-based indexes `k`, compute exactly:

```text
start = production_start_ns + k * window_step_ns
end = start + window_length_ns
```

Generate a window only while `end <= production_end_ns`; stop at the first
overrun. There is no truncated, shortened, clamped, or partial requested window.
The exact full-window count, when length fits, is:

```text
floor((production_end_ns - production_start_ns - window_length_ns)
      / window_step_ns) + 1
```

Arithmetic has its own local Decimal context with sufficient precision for
the input exponent span, including ps-to-ns conversion, independently of caller
precision and traps. There is no cumulative binary-float addition. Public
requested boundaries serialize as finite floats after planning; a boundary pair
that cannot retain a positive interval in that representation raises `ValueError`.

Ordinary windows are **`[start, end)`**. Only when the Decimal requested end is
**exactly equal** to requested production end is the right endpoint inclusive:
**`[start, end]`**. No tolerance broadens either boundary. The inclusive endpoint
adds no sampling target; it retains the endpoint only if 27.A requested it.

| Production / length / step / overlap | Full requested windows |
| --- | --- |
| 0–10 ns / 5 ns / 5 ns / 0% | `[0,5)`, `[5,10]` |
| 0–10 ns / 5 ns / 2.5 ns / 50% | `[0,5)`, `[2.5,7.5)`, `[5,10]` |
| 0–10 ns / 4 ns / 3 ns / 25% | `[0,4)`, `[3,7)`, `[6,10]` |
| 0–10 ns / 4 ns / 4 ns / 0% | `[0,4)`, `[4,8)`; trailing interval is uncovered |

The third example does not generate `[9,10]` or `[9,13)`. Generally a trailing
interval may remain uncovered, including production end if no full window ends
there. This does not by itself make generated complete windows partial.

## Membership and requested/effective distinction

Membership uses each accepted record's **requested** time:
`Decimal(str(requested_time_ps)) / 1000`, compared to Decimal window boundaries.
It never uses `actual_time_ps` for inclusion. With 1 ns targets, `[0,5)` contains
0, 1, 2, 3, 4 ns and `[5,10]` contains 5, 6, 7, 8, 9, 10 ns. The shared 5 ns
boundary appears only in the second window, even if its actual source time has
a tiny accepted offset below 5 ns.

Requested boundaries are the scientific request. Effective start/end are the
actual times of the first/last selected members in requested-grid order, in ps.
They are both `None` without selected samples, and equal for one selected sample.
They are observational: missing endpoints may move effective bounds inward,
and accepted source-time representation noise may put them slightly outside
requested boundaries. Requested bounds are never substituted as observed bounds.

Source frame indexes are copied from selected records in requested-grid order,
preserving gaps and non-increasing numeric index values. No frame index is
inferred from time or grid position.

## Missing samples, empty windows, and overlap

Missing records remain in requested membership and in
`missing_requested_sample_indexes`, contributing to missing counts and reducing
coverage. They never fabricate source membership. A missing requested target
can affect multiple overlapping windows.

Windows with zero requested sampling targets remain in the physical schedule;
they are empty and unsuitable for later contact metrics. Their requested,
selected, and missing counts are all zero, and coverage is defined as `0.0`.
The schedule depends on window parameters, not frame or sampling availability.

| Window status | Rule |
| --- | --- |
| `complete` | At least one selected sample and no missing assigned targets |
| `partial` | At least one selected sample and at least one missing assigned target |
| `empty` | No selected samples; zero or more requested targets |

Otherwise coverage is `sampled_frame_count / requested_sample_count`.
It is a descriptive fraction, without an arbitrary classification threshold.

Overlapping windows intentionally share requested samples and source frames.
Membership is never de-duplicated across windows. Aggregate requested, sampled,
and missing counts sum window memberships, so `total_window_sampled_frame_count`
may exceed the sampling plan's unique `sampled_frame_count`.

## Records, serialization, and planning status

The public identity constants are:

```python
PHYSICAL_TIME_WINDOW_SCHEMA_VERSION = "mania.physical_time_windows.v0.1"
PHYSICAL_TIME_WINDOW_KIND = "mania_physical_time_windows"
```

All three public models are frozen dataclasses. `to_dict()` returns independent
JSON-safe dictionaries in declaration order, retaining optional `None` values
and converting record and membership tuples to lists. Serialization supports
`json.dumps(..., allow_nan=False)` deterministically. No local path is added.

`ResolvedPhysicalTimeWindow` fields in order:

| Group | Fields |
| --- | --- |
| Identity | `window_index`, `window_id` |
| Requested | `requested_start_ns`, `requested_end_ns`, `right_endpoint_inclusive` |
| Counts | `requested_sample_count`, `sampled_frame_count`, `missing_sample_count`, `coverage_fraction` |
| Effective | `effective_start_time_ps`, `effective_end_time_ps` |
| Membership | `requested_sample_indexes`, `selected_requested_sample_indexes`, `missing_requested_sample_indexes`, `source_frame_indexes` |
| Status | `status` |

Indexes/counts are non-negative integers with bool rejected; times and coverage
are finite non-negative numbers. Window IDs are non-empty stripped strings.
Requested end must exceed start and inclusion is an exact bool. Counts match
membership lengths, selected and missing indexes partition requested membership
in grid order, and coverage, effective-bound presence/order, and status agree
with counts. Source indexes are unique within each window.

Planner IDs use `f"window_{window_index + 1:04d}"`, starting at `window_0001`.
They contain no condition, replica, or Dataset ID. Higher publication identity
composition belongs later.

`PhysicalTimeWindowPlanningIssue` fields are `severity` (`error` or `warning`),
`code`, `message`, and optional `window_index` (default `None`). Text is non-empty
and stripped; an optional index must be a non-negative integer.

`ResolvedPhysicalTimeWindowPlan` fields in order:

| Group | Fields |
| --- | --- |
| Identity/status | `schema_version`, `kind`, `status` |
| Requested | `requested_production_start_ns`, `requested_production_end_ns`, `requested_window_length_ns`, `requested_window_step_ns`, `requested_overlap_percent`, `implied_overlap_percent` |
| Schedule | `window_count`, `complete_window_count`, `partial_window_count`, `empty_window_count` |
| Coverage | `windows_with_samples_count`, `total_window_requested_sample_count`, `total_window_sampled_frame_count`, `total_window_missing_sample_count` |
| Records | `windows`, `issues` |

Schema version/kind are non-init constants. Plan validation checks record types,
consecutive window indexes/IDs, aggregate counts, implied overlap, schedule
errors, issue indexes, and status consistency.

| Plan status | Rule |
| --- | --- |
| `complete` | Valid schedule, at least one full window, every window complete |
| `partial` | Valid schedule, at least one window with samples, at least one partial or empty window |
| `failed` | Parameter/contract error, no full windows, or no selected samples in any generated window |

Issue codes are `inconsistent_window_overlap`, `invalid_window_step`,
`no_full_windows`, `empty_windows_present`, `partial_windows_present`,
`no_resolved_window_samples`, and `sampling_contract_mismatch`. Empty/partial
warnings aggregate counts by category. Window status describes assigned records;
the upstream sampling plan and its diagnostics remain separate and unchanged.

## Synthetic NaPi2b-style verification

For 50–100 ns, 500 ps sampling, 5 ns length, 2.5 ns step, and 50% overlap:
101 complete sampling targets produce exactly
`floor((50 - 5) / 2.5) + 1 = 19` full windows. Starts are 50, 52.5, …, 95 ns;
the final window is `[95,100]`. There are 191 selected window memberships,
intentionally exceeding 101 unique selected samples.

If the 57.5 ns target becomes missing, only zero-based windows 2 and 3 become
partial. The other 17 stay complete, requested boundaries remain identical,
and total selected memberships become 189. The window starting at 57.5 ns
observes its first selected actual time at 58 ns, without replacement.

## QC and scientific boundary

The future Dataset 95% exclusion rule is not applied. Coverage at 94% and 96%
with missing targets produces partial windows in both cases. Future exclusion
and aggregation policies do not enter this planner.

There is no contact calculation, occupancy, lifetime, contact episode semantics,
edge-weight calculation, Rg, replica aggregation, or publication export. These
remain future stages. The module uses standard library code plus the accepted
Dataset temporal model and sampling records only; it accesses no filesystem,
trajectory runtime, scientific stack, Git, clock, or environment.

The 27.A resolver, Dataset models, Stage 26 binding, CLI, frame selection,
scientific outputs, Stage 20–24 schemas/rows/calculations, provenance/inventory,
PBC semantics, analysis, dependencies, and WANIA remain unchanged.
