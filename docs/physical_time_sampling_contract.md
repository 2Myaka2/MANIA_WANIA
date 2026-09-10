# Physical-time sampling contract — Stage 27.A

## Status and scope

Stage 26 is complete at checkpoint
`027c1125f34a8cd5809d32779ad51de28b8fcca5`. Stage 27.A implements the pure
physical-time sampling resolver in
[`physical_time_sampling.py`](../src/mania/preprocessing/physical_time_sampling.py).
Stage 27.A is accepted; Stage 27.B pure physical-time window planning is implemented.
**Stage 27 remains incomplete. Stage 27.C workflow integration is next.**
Stage 27.C will own preprocessing workflow integration, provenance, regression,
and final acceptance. This resolver has no workflow or CLI integration.

The accepted [Dataset identity contract](dataset_identity_contract.md) supplies
`DatasetTemporalParameters`. The
[frozen Dataset v1.0 scientific contract](dataset_v1_scientific_contract.md)
remains unchanged, including its historical Stage 26.A implementation status.
Dataset v1.0 remains unreleased. MANIA remains version `0.1.0`.

## Requested versus effective

A requested value is not evidence that a trajectory frame exists. The resolver
never overwrites, clamps, or silently rewrites requested scientific parameters.
It consumes only `production_start_ns`, `production_end_ns`, and
`frame_stride_ps`, retaining their supplied model values in the plan.

The plan separately records the complete supplied source-axis extent, matched
source indexes and actual times, missing requested targets, effective matched
bounds, and actual coverage. Requested bounds are in ns; source, target, actual,
delta, and effective times are in ps.

## Closed production interval and Decimal grid

**The requested physical production interval is CLOSED: `[start, end]`.**
Both endpoints can be requested. A 50–100 ns interval with 500 ps stride has
101 requested targets; all 101 resolve only if unique matching frames exist.

Values enter Decimal arithmetic through `Decimal(str(value))`. The resolver
converts ns to ps by exact multiplication by 1000 and increments by the Decimal
stride while `target <= end`. Arithmetic uses a local precision sufficient for
the input exponent range, independent of the caller's Decimal context. Only
public target values become floats; repeated binary-float addition is not used.
Production times that cannot be represented as finite ps floats raise
`ValueError` instead of emitting non-finite records.

End is included only if it lies on the requested grid. For 0–1 ns with a 300 ps
stride, targets are **0, 300, 600, 900 ps**. There is no artificial 1000 ps target,
and requested end remains 1 ns. A stride longer than the interval produces one
requested target at start.

## Source-axis contract

The API is:

```python
resolve_physical_time_sampling(
    source_frames: tuple[PhysicalTimeSourceFrame, ...],
    *,
    temporal: DatasetTemporalParameters,
) -> ResolvedPhysicalTimeSamplingPlan
```

`source_frames` must be a tuple of `PhysicalTimeSourceFrame` records, and
`temporal` must be the exact `DatasetTemporalParameters` type. Incorrect API
types and invalid dataclass fields raise `ValueError`. No trajectory object is
accepted or iterated. Source order is authoritative: indexes must be unique
and `current_time_ps > previous_time_ps` strictly. Equal or decreasing times
are fatal even when their difference falls within the matching tolerance.
The resolver never sorts or reorders source frames.

Frame indexes must be non-negative integers, with bool rejected. Source times
must be finite non-negative numbers, with bool rejected. Index gaps and indexes
that do not numerically increase are valid. Selected indexes come directly from
source records; no index is derived from `time / dt` or requested grid position.
Time gaps and frames outside production are allowed. `source_frame_count`
describes the entire supplied tuple. Source extent is its minimum and maximum
time (also first and last on a valid axis); both are `None` for an empty axis.
Reporting minimum/maximum on a failed axis does not repair its order.

## Matching and ambiguity

The public technical constants are:

```python
PHYSICAL_TIME_MATCH_ABS_TOLERANCE_PS = 1e-6
PHYSICAL_TIME_MATCH_REL_TOLERANCE = 1e-9
```

Each actual/target comparison uses:

```python
math.isclose(
    actual_time_ps,
    requested_time_ps,
    rel_tol=PHYSICAL_TIME_MATCH_REL_TOLERANCE,
    abs_tol=PHYSICAL_TIME_MATCH_ABS_TOLERANCE_PS,
)
```

**This tolerance handles floating representation noise. It is NOT scientific
nearest-frame snapping.** It never authorizes rounding requested bounds to
frames, rounding stride to the save interval, flooring/ceiling targets, or
substituting adjacent frames. A tiny actual-time offset across a requested
boundary is evaluated using this same tolerance; there is no separate clamp.

Exactly one match resolves a target only if that source frame matches no other
requested target. Zero matches leave the target missing. More than one frame
matching a target is fatal `ambiguous_time_match`. A source frame matching more
than one target is also fatal: all affected targets remain missing, including
an earlier target that would otherwise have received the frame. Grid order is
never a tie-breaker. Independent, unique matches remain in a failed ambiguity
plan; its error prevents treating it as complete or partial.

Monotonic candidate bounds and source-use counts avoid a source-by-target brute
force scan: matching is O(source frame count + requested sample count).

## Missing targets and failed axes

Every requested grid position appears exactly once in selected or missing
records. Each collection is ordered by requested sample index. Missing records
contain only their zero-based requested index and requested time; no source
frame is fabricated. They include targets unresolved because of fatal errors.

An empty source, duplicate frame index, or non-increasing time step prevents
trustworthy resolution of the source axis. All targets remain missing, coverage
is zero, and status is `failed`. For ambiguity, the plan retains independent
matches and reports actual coverage, but status remains `failed`.

A source saved every 100 ps with requested stride 250 ps resolves targets
0, 500, and 1000 ps; 250 and 750 ps stay missing. No 200/300 or 700/800 ps
replacement is selected.

Requests outside source data are never clamped. For requested 50–100 ns and
source 60–90 ns, outside targets remain missing and unique interior matches
are selected. Requested bounds stay 50 and 100 ns; effective bounds describe
the actual selected frames. If the entire grid is outside source data, all
targets remain missing, coverage is zero, and status is `failed`.

## Records and resolved-plan fields

All public records are frozen dataclasses with deterministic `to_dict()`
serialization in field declaration order.

| Record | Fields |
| --- | --- |
| `PhysicalTimeSourceFrame` | `frame_index`, `time_ps` |
| `ResolvedPhysicalTimeSample` | `requested_sample_index`, `requested_time_ps`, `source_frame_index`, `actual_time_ps`, `time_delta_ps` |
| `MissingPhysicalTimeSample` | `requested_sample_index`, `requested_time_ps` |
| `PhysicalTimeSamplingIssue` | `severity`, `code`, `message`, `frame_index`, `requested_sample_index` |

Selected-record numeric values are finite, indexes are non-negative integers,
and requested/actual times are non-negative. Bool is rejected. Actual/requested
times must satisfy the public tolerance. `time_delta_ps` must equal
`actual_time_ps - requested_time_ps`; positive, zero, and negative deltas are
valid. Missing records validate the same requested index and time constraints.

`ResolvedPhysicalTimeSamplingPlan` fields, in serialization order:

| Group | Fields |
| --- | --- |
| Status | `status` |
| Requested | `requested_production_start_ns`, `requested_production_end_ns`, `requested_frame_stride_ps` |
| Technical matching | `match_abs_tolerance_ps`, `match_rel_tolerance` |
| Source | `source_frame_count`, `source_start_time_ps`, `source_end_time_ps` |
| Grid | `requested_sample_count` |
| Resolution | `sampled_frame_count`, `missing_sample_count`, `coverage_fraction` |
| Effective | `effective_start_time_ps`, `effective_end_time_ps`, `effective_stride_ps` |
| Records | `selected_samples`, `missing_samples`, `issues` |

Counts must match tuple lengths, selected plus missing must equal requested,
and requested count must equal the closed Decimal grid size (at least one).
Records must partition the grid without duplicates or incorrect target times.
A source frame may appear in selected records at most once. Coverage must equal
`sampled_frame_count / requested_sample_count`, in `[0, 1]`. Plan validation
also checks tolerances, ordered actual times, extent/effective fields, and
status consistency. Record tuples serialize as independent JSON lists.

## Status and issues

`PhysicalTimeSamplingStatus = Literal["complete", "partial", "failed"]`:

- `complete`: every requested target resolved uniquely; at least one exists.
- `partial`: at least one target resolved and at least one is missing, with
  no fatal error.
- `failed`: no target resolved, or a fatal source-axis/ambiguity error exists.

Issue severity is `error` or `warning`; optional indexes default to `None`.
Resolver issues contain portable counts and indexes, with no local paths,
timestamps, or environment metadata. Text must be non-empty and stripped.
Codes are `empty_source_time_axis`, `duplicate_source_frame_index`,
`non_monotonic_source_time`, `ambiguous_time_match`,
`requested_samples_missing`, and `no_requested_samples_resolved`.
Errors are aggregated by category with the first relevant index where useful.
One aggregate missing warning accompanies explicit missing records; there is
no warning string for every missing target.

## Effective bounds and stride

With selected samples, effective start/end are the first/last selected
**actual** times. Without selected samples, both are `None`.

`effective_stride_ps` is defined only when at least two selected samples exist,
no requested samples are missing, and every consecutive selected pair has
consecutive requested indexes. It is the arithmetic mean of consecutive actual
time differences. Otherwise it is `None`, including a single selected sample.
For selected requested indexes 0, 1, 3, 4 it is `None`; a mean over the missing
index 2 would conceal the gap. Stride is observational, is not forced to equal
the requested stride, and is never used for selection.

## QC and window boundaries

Coverage is computed without applying the future Dataset v1.0 95% exclusion
threshold. Plans at 94% and 96% are both `partial` when there is no fatal error.
Dataset exclusion policy belongs to Stage 32.

`window_length_ns`, `window_step_ns`, and `overlap_percent` remain requested and
operationally inert in 27.A. Changing only these fields produces the identical
sampling plan. Stage 27.B now interprets them; no windows, memberships, overlap
consistency, or window-based calculations are implemented here.

## Stage 27.B handoff

The 27.A output is the authoritative requested-sample resolution consumed by
the [pure physical-time window planner](physical_time_window_contract.md).
27.B combines the selected/missing records by requested sample index and assigns
membership using requested sample time. It does not regenerate the sampling grid
or rerun time matching. Actual selected times only describe effective window
bounds. Accepted 27.A sampling semantics and workflow behavior are unchanged.

## Purity, compatibility, and API boundary

The resolver uses standard library code plus the existing
`DatasetTemporalParameters` import. It performs no filesystem, Git, subprocess,
clock, environment, or trajectory access and imports no MDAnalysis or trajectory
runtime module. The optional scientific dependency boundary is unchanged.

Identical source tuples and temporal requests produce byte-for-byte identical:

```python
json.dumps(plan.to_dict(), allow_nan=False, separators=(",", ":"))
```

The module's `__all__` contains only the two tolerance constants, the four leaf
record classes, `PhysicalTimeSamplingStatus`, `ResolvedPhysicalTimeSamplingPlan`,
and `resolve_physical_time_sampling`. There is no preprocessing `__init__.py`
re-export; Stage 27.C may decide the workflow-facing export boundary.

Existing Dataset models/table/binding, manifests, CLI, trajectory loading/frame
sampling, Rg, contacts, graph, provenance/inventory, runtime metadata/PBC,
validation, analysis, dependencies, and WANIA are unchanged. Existing Stage
20–24 artifact schemas, scientific rows, and calculations remain intact. No
existing run changes merely because this standalone module is present.
