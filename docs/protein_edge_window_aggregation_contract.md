# Protein-edge window aggregation contract — Stage 28.B

## Status and scope

Stage 27 is complete. Stage 28.A is accepted at checkpoint
`a8083e82993ea3b858251aaa6d3861308a186bf5`. Stage 28.B pure aggregation is
accepted at `869afbf9ea7bd31591026295861db0d0f1dc05d7` and implemented in
[protein_edge_windows.py](../src/mania/preprocessing/protein_edge_windows.py).
Stage 28.C [source-indexed table/export](protein_edge_window_table_contract.md) is
implemented and exports accepted 28.B metrics without recalculation. This export
remains pre-canonical; Stage 30 provides canonical mapping before publication.
Stage 28.C is accepted. Stage 28.D now consumes the accepted pure APIs in
Dataset-aware protein-contact preprocessing, with inventory/provenance lineage,
unified validation, and real-data acceptance. Stage 28 is complete; Stage 29
protein-lipid / protein-glycan dynamic layers are next and have not started.
Dataset v1.0 remains unreleased. MANIA remains `mania-wania 0.1.0`.

## Input and public API

```python
aggregate_protein_edges_by_window(
    sampling_plan: ResolvedPhysicalTimeSamplingPlan,
    window_plan: ResolvedPhysicalTimeWindowPlan,
    *,
    contacts_result: PreprocessingConditionContactsResult,
) -> ProteinEdgeWindowAggregation
```

Inputs require the exact accepted Stage 27 sampling/window models and existing
contact-result models. Physical plans may be complete or partial, with resolved
samples present; failed plans are rejected. Contacts must have
`options.contact_selection == "protein"` and `contacts_result.passed is True`.
The accepted `passed` property means status `computed`, no condition issues,
and no frame issues. The contact frame-index set must exactly equal the selected
source-frame-index set, including selected frames outside emitted windows.
Missing or extra results are errors even when total frame counts agree.
Contact-result detection order does not define temporal order.

Production bounds must agree between plans. Every supplied window is validated
through the accepted 28.A engine with empty presence before aggregation,
including windows with no observed edges. Windows and time matches are never
regenerated. Only each window's resolved source frames provide observations.
Contact frame indexes bridge presence to Stage 27 selected samples;
`PreprocessingContactFrameResult.time_ps` is not lifetime authority.

## Edge identity and metadata

Each dynamic identity is `(source_residue_index, target_residue_index, edge_type)`.
Protein contacts are undirected: lower internal residue index is source, higher
is target. Reversed observations swap residue IDs, residue names, and segment
IDs together with indexes. Source residue IDs may repeat across segments and
are never identity keys. Integer IDs (including negative values), stripped
non-empty string IDs, and `None` retain their original types. Optional segment
IDs are stripped non-empty strings or `None`.

Metadata for one canonical pair/type must be identical across all its positive
observations within a window. Conflicting duplicates within one frame and
conflicts across frames both raise `ProteinEdgeWindowAggregationError`.
Neither detection order nor minimum distance selects a preferred metadata
variant. Canonical UniProt mapping is deferred to Stage 30; no canonical
residue numbers are assigned. `execution_condition` is only the existing legacy
execution/routing name from the contacts result, not Dataset identity.

## Sparse edge universe

A window emits a row only for an exact pair/type observed on at least one of
its resolved frames. No artificial zero rows are generated for other residue
pairs, edges in other windows, or edges elsewhere in a trajectory or replica.
An edge absent from a second window has no row there.

Repeated same-edge/type records within a frame count once for presence, after
metadata consistency checks. Every emitted row has positive contact count,
occupancy, and episode count. A valid window with no contacts has
`edge_count = 0` and `edges = ()`.

## Occupancy and missing versus resolved absence

```text
n_resolved_frames_in_window = ResolvedPhysicalTimeWindow.sampled_frame_count
occupancy = n_contact_frames / n_resolved_frames_in_window
edge_weight = occupancy
```

Occupancy uses `Decimal(n_contact_frames) / Decimal(n_resolved_frames_in_window)`
in an independent local Decimal context, converting once to the public float.
Model validation requires exactly that float, with no scientific tolerance or
configurable formula. Weight uses the identical float. There is no distance,
lifetime, interaction-type, or graph weighting.

Missing requested samples are unobserved, so they cannot be counted as
contact-negative frames. Resolved frames with successful contact computation
and no matching contact are observed negatives and enter the denominator.

| Requested indexes 0, 1, 2, 3, 4 | Resolved frames | Positive indexes | Occupancy | Episodes |
| --- | --- | --- | --- | --- |
| Index 2 missing | 4 | 0, 1, 3, 4 | 4/4 = 1.0 | 0..1 and 3..4 |
| Index 2 resolved, contact absent | 5 | 0, 1, 3, 4 | 4/5 = 0.8 | 0..1 and 3..4 |

Both cases break continuity. Only resolved contact absence enters occupancy's
denominator. Requested sample count, source trajectory length, and global
production sample count are not per-window occupancy denominators.

## Episode metrics and window independence

28.B delegates each observed edge's unique positive source-frame tuple, in
requested-sample order, to the accepted [28.A episode engine](contact_episode_lifetime_contract.md).
It copies contact count, episode count, mean lifetime, and maximum lifetime
from that summary. Requested-index continuity, zero gap tolerance, and actual
resolved-time lifetime remain unchanged; 28.B has no second lifetime formula.
The accepted increasing source-index episode input contract is preserved;
incompatible source labels are errors rather than silently reordered.

At actual times 5000, 5050, 5100, 5150, 5200 ps, positives at indexes
0, 1, 2, 4 yield occupancy/weight 0.8, two episodes, mean 0.05 ns, and maximum
0.10 ns. With index 2 missing and all four resolved samples positive, the
occupancy/weight is 1.0, with two episodes and mean/maximum 0.05 ns.
A single positive observation has one episode with mean/maximum 0.0 ns.
An absent edge produces no metric row; the episode engine's no-contact `None`
lifetimes are not converted into fabricated zero-lifetime rows.

Overlapping windows calculate metrics independently, so the same frame may
contribute to multiple windows. Each denominator belongs to its own window.
Episode state never crosses window or trajectory/replica boundaries.

## Interaction types and backbone

Each existing contact `edge_type` is independent, including different types
for the same pair. Only `PreprocessingContactFrameResult.contacts` supplies
dynamic observations. `backbone_observations` are structural graph information
and never enter these contact occupancy/episode rows. Existing interaction
definitions, backbone behavior, and graph-display type priorities are unchanged.

## Models, ordering, and serialization

All three public models are frozen dataclasses. `ProteinEdgeWindowMetric`
retains window identity, canonical source identity/metadata, the resolved-frame
denominator, and the six required scientific metrics in declaration order.
It rejects bool indexes/counts, self-loops or reversed indexes, empty or
unstripped text, zero-contact rows, non-finite/negative numbers, inconsistent
counts/occupancy/weight, and a mean greater than the maximum lifetime.
Scientific numeric fields serialize as floats.

`WindowProteinEdgeStatistics` fields are `window_id`, `window_index`,
`requested_sample_count`, `resolved_frame_count`, `missing_sample_count`,
`coverage_fraction`, `edge_count`, and `edges`. Requested count equals resolved
plus missing. Coverage preserves Stage 27 semantics: resolved/requested when
requested count is positive, otherwise exactly `0.0`. A zero-resolved window
has no edges and performs no occupancy division. Edge identities are unique,
belong to the exact window, and share its denominator.

Root `to_dict()` order is:

```text
schema_version, kind, status, execution_condition,
window_count, observed_edge_row_count, windows
```

The fixed non-init constants are:

```python
PROTEIN_EDGE_WINDOW_SCHEMA_VERSION = "mania.protein_edge_window_aggregation.v0.1"
PROTEIN_EDGE_WINDOW_KIND = "mania_protein_edge_window_aggregation"
```

Windows retain accepted Stage 27 plan order, consecutive zero-based indexes,
and `window_0001` naming. Edges sort by `edge_type`, then source internal index,
then target internal index. Root counts equal window count and the sum of
window edge counts. `to_dict()` uses independent dictionaries and JSON arrays;
identical inputs are byte-identical under
`json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))`.

## Integrity and physical coverage status

`ProteinEdgeWindowAggregationStatus` is `Literal["complete", "partial"]`.
Complete means both physical plans are complete. Partial means either plan is
partial while accepted resolved samples exist. This is physical coverage only:
94% and 96% accepted partial plans both remain partial, with no 95% rule.

A missing/failed contact frame, condition issue, computation exception recorded
as an issue, or computation-limit failure is not scientific absence and cannot
be represented as partial aggregation. These inputs raise
`ProteinEdgeWindowAggregationError(ValueError)` with deterministic, portable
messages; upstream issue details and local paths are not included.

## Boundaries and verification

This API has no filesystem, trajectory access, optional MDAnalysis requirement,
Git/subprocess, clock, PBC operations, or distance calculations. It is not
re-exported through `preprocessing/__init__.py`. Stage 28.D is its separate
workflow consumer. The 28.B API itself has no CSV export; the separate 28.C layer owns
explicit source CSV persistence. There is no canonical mapping, replica aggregation,
specialized lipid/glycan layer, or QC exclusion. Existing scientific artifacts,
Stage 20–24 schemas, Stage 27 code, 28.A semantics, provenance/inventory,
validation, analysis, dependencies, and WANIA remain unchanged. The frozen
[Dataset scientific contract](dataset_v1_scientific_contract.md) is unchanged.

[Synthetic tests](../tests/test_preprocessing_protein_edge_windows.py) cover the
denominator distinction, sparse presence, orientation and metadata integrity,
window boundaries/overlap, input completeness, engine reuse, deterministic
serialization, public validation, and purity without trajectory files.
