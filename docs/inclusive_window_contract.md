# Versioned temporal boundaries — Stage 34.D.4c

Dataset v1 production explicitly requests `mania.window_boundaries.inclusive.v1`.
This approved scientific amendment changes full-window membership only. The
package remains `mania-wania` 0.1.0; package and scientific contract versions
are independent. Dataset v1 remains unreleased. Stage 35 is not authorized.

| Profile | Ordinary full window | Full window ending at production end |
| --- | --- | --- |
| `mania.window_boundaries.legacy.v1` | `[start,end)` | `[start,end]` |
| `mania.window_boundaries.inclusive.v1` | `[start,end]` | `[start,end]` |

The absent-policy default is legacy. Historical Stage 34 outputs retain their
original meaning and bytes. Neither bounds, window labels nor an individual
right-inclusive flag identify the profile: terminal windows can have identical
local evidence under both profiles.

## Request and planning

Set one top-level preprocessing manifest policy, separate from the frozen six
numeric `DatasetTemporalParameters` and `DatasetTrajectorySpec` v0.1:

```yaml
temporal_policy:
  schema_version: mania.preprocessing_temporal_policy.v0.1
  boundary_profile: mania.window_boundaries.inclusive.v1
```

Both listed profiles are accepted; unknown versions, unknown profiles and extra
policy fields fail. Policy requires Dataset context and applies to its bound
conditions. Inline/table equality still compares the original Dataset spec.
The existing unversioned preprocessing input manifest adds this optional,
separately versioned carrier, following its existing optional-control convention.
No per-window boundary configuration is accepted.

`plan_physical_time_windows(..., boundary_profile=...)` dispatches membership in
the existing Decimal planner. Inclusive windows use the existing right-inclusive
bisect branch. Full-window positions/counts, sampling-grid generation, matching
tolerances and source timestamps are unchanged. Off-grid endpoints are never
appended; no shortened trailing window is created. The independent execution
verifier derives inclusion from the recorded profile using rational arithmetic
and rejects inconsistent flags or memberships without raw trajectory access.

| Analysis interval | Selected targets | Full windows | Final window | Inclusive targets/window |
| --- | ---: | ---: | --- | ---: |
| 5–100 ns | 476 | 94 | [98,100] ns | 11 |
| 5–30 ns | 126 | 24 | [28,30] ns | 11 |

Both schedules request 200 ps stride, 2 ns length and 1 ns step. `[5,7]` contains
5.0 through 7.0 ns in 0.2 ns increments; `[6,8]` contains 6.0 through 8.0 ns.
They share six targets. Overlap is **1 ns / 50% of window duration**, not 50%
of discrete samples. Counts derive from actual requested-grid membership.
The same legacy schedules select 476/126 targets and 94/24 windows, with ten
targets in ordinary windows and eleven in the production-ending window.
The first 5 ns remain stabilization/QC source data.

## Persistence and compatibility

| Authority | Legacy shape | Explicit inclusive shape |
| --- | --- | --- |
| Requested Dataset context | `mania.preprocessing_dataset_context.v0.1`, no policy | `mania.preprocessing_dataset_context.v0.2`, nested `temporal_policy` |
| Temporal execution | `mania.preprocessing_temporal_execution.v0.1` | `mania.preprocessing_temporal_execution.v0.2` |
| Nested window plan | `mania.physical_time_windows.v0.1`, implicit legacy | `mania.physical_time_windows.v0.2`, explicit `boundary_profile` |
| Aggregation manifest | `mania.replica_aggregation_manifest.v0.1` | `mania.replica_aggregation_manifest.v0.2`, profile in every spec/member window |
| Publication manifest | `mania.dataset_release_manifest.v0.1`, implicit legacy | `mania.dataset_release_manifest.v0.2`, release-wide `boundary_profile` |

An explicitly requested legacy policy uses context v0.2 to retain the request;
its execution still writes the exact legacy temporal v0.1 shape. Temporal JSON
strictly dispatches the listed version/profile pairs, rejects hybrids and never
guesses from individual windows. Reading and writing old models retains their
old serialization. Sampling JSON and the six-number Dataset spec stay v0.1.

Canonical and annotated window CSVs retain their exact legacy headers. Their
profile-aware layout appends one `boundary_profile` column; corresponding model
schema identities are v0.2 when inclusive rows are present. Aggregate CSVs use
the same exact appended-column dispatch. Unknown columns/profiles and missing
cells fail. Header-only tables assert no window identity; their bound temporal
execution and manifest remain authoritative, including zero emitted metrics.
Pre-canonical protein/lipid/glycan source CSVs remain unchanged. CLI export and
offline canonical reconstruction supply profiles from the retained temporal
execution, then preserve them through annotation.

Stage 31 adds profile identity to the physical window key and compares every
matching canonical row against its group. A mixed-profile replica group fails
even at identical terminal windows. Aggregation manifests use one profile.
Stage 32 reads and projects that versioned manifest through its existing QC
bridge; QC evidence, the 95% production-sample rule, availability and statistics
are unchanged.

Stage 33 uses one profile across temporal evidence and aggregation authority.
`release/dataset_manifest.json` supplies the versioned boundary authority for all
rows of `metadata/time_windows.csv` and the linked science/aggregate tables.
Their existing CSV schemas and Decimal serialization stay unchanged. The
export-control manifest retains exact temporal-evidence paths for offline
reconstruction. The release manifest, requested windows and source identities
are all checked on reconstruction. F1 compares complete canonical models,
including profiles. F2 rejects metric sources whose profile differs from the
release, including terminal sources with otherwise identical physical evidence.

## Unchanged scientific semantics and remaining work

Missing expected targets remain absent from occupancy denominators and break
episode continuity. Occupancy remains contacts / resolved frames. Requested
stride is intentional; adjacent requested positions remain continuous. Lifetime
uses actual first/last positive times; a singleton is zero ns. Episodes are
window-local, and shared positive observations legitimately contribute to both
windows. No cross-window deduplication is performed.

Contact geometry, 6.0 Å lipid and 4.5 Å glycan cutoffs, heavy atoms, glycan anchor
exclusion, distance summaries, protein edge weight, PBC, canonical mapping,
QC, replica statistics and Decimal conversion remain unchanged.

The operational catalog v1.1 requests this policy once for all 33 trajectories.
Its D.4b timing values and readiness statuses are unchanged. Remaining work is
specialized per-frame persistence and offline replay, including explicit
zero-contact frame retention and all-layer multi-window reconstruction. Protein
per-frame export is already available. This task adds no such persistence,
launcher, source controls, PBC execution or production MD run.

## Legacy regression fixture

`tests/fixtures/temporal_execution_legacy_v01.json` is the unchanged 4,573-byte
temporal JSON from accepted Stage 34.A specialized NORMAL evidence, run
`stage34a_specialized_normal_20260915T131821Z_02b6678fd1cf41498b41a0085d2f4d7a`,
`output/temporal_execution.json`. It contains no coordinates or local paths.
SHA256: `32da4e2fb3bd8dfe7ed2e98fd3a6a4f3b8c5627c27fbbf84cf3042b1ab02312c`.
Repository tests use only the committed fixture and verify exact legacy
planner reconstruction and byte-preserving serialization.
