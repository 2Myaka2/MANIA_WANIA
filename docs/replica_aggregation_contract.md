# Replica aggregation group and physical-window contract — Stage 31.A

## Status

Stage 30 is complete at accepted Stage 30.D checkpoint
`ea7ca9ddb0f3b19cce883b955521ddbbd1153353`.
Stage 31.A group/window contract is implemented in
[`replica_aggregation_contract.py`](../src/mania/replica_aggregation_contract.py).
Stage 31.A is accepted. Stage 31.B pure canonical protein-edge replica
aggregation is implemented in the
[protein-edge aggregation contract](replica_protein_edge_aggregation_contract.md).
Stage 31.B is accepted. Stage 31.C specialized lipid/glycan replica aggregation
is implemented with mandatory explicit specialized-partner correspondence in the
[specialized aggregation contract](replica_specialized_aggregation_contract.md).
Availability semantics remain unchanged. Stage 31 remains incomplete.
Stage 31.D is next and owns Dataset workflow, aggregate
exports, provenance/validation, and final Stage 31 acceptance.

## Canonical-only boundary

```text
replica source tables
  → explicit Stage 30 canonical mapping
  → canonical per-replica tables
  → Stage 31 replica aggregation
```

Stage 31 statistical aggregation is defined only over canonicalized tables.
Source-indexed tables remain audit inputs and are never statistical join keys
across replicas. Source resid equality is never a replica aggregation key:
GROMACS source resid 311 and NAMD source resid 311 must not be joined by numeric
equality. Stage 31.A accepts no tables; Stage 31.B accepts only canonical
Stage 30 protein-edge tables, never Stage 28/29 `_source` inputs. Stage 31.C
applies the canonical-only protein boundary to specialized tables and requires
explicit correspondence for topology-local partners.

The public constants derive from accepted Stage 30 mapping constants:

| Constant | Pinned value |
| --- | --- |
| `REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID` | `uniprotkb:O95436-1:sequence-v3` |
| `REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256` | `33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9` |

No sequence is duplicated or read. The group specification exposes non-init
`canonical_reference_id` and `canonical_reference_sequence_sha256`; each member
must explicitly supply that exact reference and sequence digest. A mismatch
fails. This pins the canonical target; it does not independently prove mapping
of any source table, which remains Stage 30's responsibility.

Biological annotated canonical tables exist after Stage 30.D, but grouping does
not require annotation fields. `is_ecd`, `is_mx35`, glycosylation flags and other
annotations do not determine group identity, compatibility or availability.
Publication layers may carry them later.

## Group identity and engine isolation

`ReplicaAggregationGroupSpec` is frozen, with fields in order:

```text
dataset_id, system_id, engine, variant_id, condition, disulfide_state,
expected_replica_ids, window,
canonical_reference_id (non-init), canonical_reference_sequence_sha256 (non-init)
```

Its authoritative `group_key` is exactly:

```python
(dataset_id, system_id, engine, window.physical_window_key)
```

Identifiers follow accepted Dataset semantics: actual non-empty strings,
surrounding whitespace stripped, case and internal text retained, no imposed
naming convention. `condition` and `disulfide_state` accept `None`; supplied
labels use the same text normalization. No label is inferred.

`variant_id`, `condition` and `disulfide_state` must agree across all members and
the specification, but condition is consistency metadata, not lookup identity.
Two systems sharing `NORM` remain separate groups. A NAMD group with
`condition=None` is valid when every member agrees.

Engine must be exactly `gromacs` or `namd`; Stage 31.A does not normalize engine
spelling or infer equivalence. GROMACS and NAMD never share one statistical
group, even if dataset/system, labels, canonical target and physical window
otherwise match. A mixed-engine group fails.

## Compatible requested physical windows

The frozen `ReplicaAggregationWindowDefinition` has these fields in exact order:

```text
window_id: str
window_index: int
requested_production_start_ns: float
requested_production_end_ns: float
requested_window_start_ns: float
requested_window_end_ns: float
right_endpoint_inclusive: bool
window_length_ns: float
window_step_ns: float
overlap_percent: float
```

Window labels are non-empty stripped strings; the index is a non-negative exact
integer, excluding bool. Endpoint inclusion is an exact bool. Physical numeric
fields accept finite non-negative int/float values, excluding bool. Production
and window intervals must be positive, and the window must lie within requested
production. Length/step satisfy `0 < step <= length`; overlap is in `[0, 100)`.
The window duration equals length exactly under `Decimal(str(value))` arithmetic
with a private context spanning the supplied exponents. Caller Decimal precision,
rounding or traps do not alter the result.

Overlap consistency follows the accepted
[Stage 27 contract](physical_time_window_contract.md):
`implied_overlap = (1 - step / length) * 100`, compared with `math.isclose` and
the reused absolute `1e-6` and relative `1e-9` overlap tolerance constants.
This validates schedule consistency only and never rewrites supplied values.
Stage 31.A does not generate schedules, infer labels from indexes or recompute
endpoint inclusion; it compares the supplied requested contract.

The exact `physical_window_key` is the following tuple, with all numeric
components Decimal-normalized in an isolated context (including canonical zero):

```text
(requested_production_start_ns, requested_production_end_ns,
 requested_window_start_ns, requested_window_end_ns, right_endpoint_inclusive,
 window_length_ns, window_step_ns, overlap_percent)
```

There is no approximate float grouping. Even distinct overlap values that both
pass Stage 27's consistency tolerance have distinct compatibility keys.
`window_id` equality is insufficient: `window_0001` at 20–25 ns cannot aggregate
with `window_0001` at 22.5–27.5 ns. Production context, step, overlap and endpoint
semantics must also agree. A different length for identical bounds already
fails window construction because duration must equal length.

Stage 31 v1.0 additionally requires identical `window_id` and `window_index`.
Labels/indexes are retained evidence, not the physical scientific identity.
Equal physical keys with different labels or indexes fail conservatively;
there is no silent renaming.

## Requested versus effective observations

Requested scientific schedule defines compatibility. Effective bounds,
`resolved_frame_count`, `missing_sample_count`, and `coverage_fraction` do not
occur in the Stage 31.A window/member contract or compatibility key. They may
legitimately differ between replicas because source samples are missing.
Per-replica technical coverage remains separate evidence for later layers.
No effective sample count, coverage threshold or observed endpoint can silently
change requested-window identity or availability.

## Expected replicas and member records

Every `expected_replica_ids` value is an explicit, non-empty tuple of unique,
normalized non-empty strings. The caller's tuple is the authoritative order,
including intentional non-lexical orders such as `("3", "1", "2")`.
Duplicates after whitespace normalization fail.

Every expected replica must have exactly one explicit member-state record.
For `("1", "2", "3")`, supplying only replicas 1 and 2 fails. The caller must
represent replica 3 as unavailable or excluded when appropriate. Extra replica
IDs, duplicate IDs (even under different trajectories), and duplicate replica
keys fail before any ordering is performed.

The frozen `ReplicaAggregationMember` has fields in order:

```text
dataset_id, system_id, trajectory_id, replica_id, variant_id, engine,
condition, disulfide_state, canonical_reference_id,
canonical_reference_sequence_sha256, window, availability_status,
availability_reason
```

Its `replica_key` is the accepted Dataset identity:
`(dataset_id, system_id, trajectory_id, replica_id)`, with no condition.
All group metadata and canonical reference fields must match the specification,
along with both physical-window identity and label/index evidence.

## Availability and the critical absent-row rule

`ReplicaWindowAvailabilityStatus` is exactly
`Literal["available", "unavailable", "excluded"]`.

| Explicit member state | Meaning | Stage 31.B / Stage 31.C absent corresponding entity row |
| --- | --- | --- |
| `available` | Replica/window scientifically available for aggregation | Observed occupancy 0 for this available replica |
| `unavailable` | Known replica/window explicitly unavailable | Not occupancy 0; omitted from statistics and available-replica denominator |
| `excluded` | Explicit upstream exclusion state | Not occupancy 0; omitted from statistics and available-replica denominator |

**An available replica plus an absent sparse corresponding entity/edge row contributes
occupancy 0 in aggregation. An unavailable or excluded replica never
contributes occupancy 0 and never participates in occupancy statistics.**

For Stage 31.C, this rule requires explicit partner correspondence covering
every available replica. Missing correspondence is invalid input, never sparse
absence or occupancy zero. Equal topology-local partner IDs or names do not
establish correspondence. This adds partner evidence without changing member
availability semantics.

Stage 28/29 source tables and Stage 30 canonical tables are sparse. Absence of
one edge/partner row must never be interpreted as replica unavailability.
Availability comes only from the explicit member state. Stage 31.A does not
materialize edge-specific zeroes; it establishes the evidence required to do
that correctly in 31.B/31.C. Stage 31.B now materializes sparse protein-edge
absence as zero only in available members' statistical vectors, leaving the
underlying canonical tables unchanged.

For `available`, `availability_reason` must be `None`. For `unavailable` and
`excluded`, a non-empty portable reason is required. Only surrounding whitespace
is stripped; all remaining text is preserved verbatim. Reasons must be printable
prose without path separators (`/`, `\`), home-path marker `~`, or internal control
characters. Use a portable explanation such as `Requested replica data unavailable`.
Local paths are rejected, and error messages never interpolate supplied values.

## Public group API and determinism

```python
build_compatible_replica_aggregation_group(
    spec: ReplicaAggregationGroupSpec,
    members: tuple[ReplicaAggregationMember, ...],
) -> CompatibleReplicaAggregationGroup
```

Exact model types and exact tuples are required. The frozen result fields are
`spec` and `members`. Both direct construction and the builder validate all
members, then order them by `spec.expected_replica_ids`. Members must be non-empty;
an entirely unavailable/excluded group remains valid with zero available members.

Derived properties are `member_count`, `available_replica_count`,
`unavailable_replica_count`, `excluded_replica_count`, `available_members`,
`unavailable_members`, and `excluded_members`. Partitions retain expected order.
These count explicit availability states without calculating entity statistics.

Every public model provides independent deterministic `to_dict()` data in field
order, with tuples serialized as JSON arrays. Group serialization contains its
specification and members; derived keys/counts/partitions are properties rather
than duplicated fields. Identical inputs produce byte-identical
`json.dumps(group.to_dict(), allow_nan=False, separators=(",", ":"))`.
Errors use `ReplicaAggregationContractError(ValueError)` and deterministic,
portable messages. No timestamp, UUID, environment, filesystem, CSV, network,
Git or process access occurs in contract operations.

## Scientific smoke and boundaries

The acceptance fixture is `napi2b-v1-test` / `wt-norm` / `gromacs`, expected
replicas `("1", "2", "3")`, production 20–30 ns, `window_0001` index 0 at
20–25 ns, right endpoint exclusive, length 5 ns, step 2.5 ns, overlap 50%.
Replicas 1 and 2 are available; replica 3 is unavailable with a portable reason.
The compatible group has 3 members, 2 available, and 1 unavailable. Changing
replica 2 to 22.5–27.5 ns while retaining `window_0001` fails.

Stage 31.A never performs QC exclusion: no coverage, RMSD, MAD, PBC, missing-frame
or edge-count decision and no 95% threshold. Stage 32 remains responsible for
Dataset release QC/exclusion policy; Stage 31.A preserves explicitly supplied
state only.

No statistics are implemented in Stage 31.A. Stage 31.B implements mean, median,
standard deviation, supporting replica count and support fraction for canonical
protein edges. Sample standard deviation with ddof=1 is frozen in Stage 31.B;
one available replica has `std_occupancy = None`. Stage 31.A itself chooses no
estimator and its compatibility semantics remain unchanged. Stage 31.C applies
the same statistics only to explicitly corresponding specialized partners.
Stage 31.D is next.
There is no workflow integration, CLI change, export, provenance/inventory
change or unified-validation integration. Accepted Stage 27–30 science, source
and canonical tables, annotations, PBC, analysis, dependencies, frozen Dataset
scientific contract and WANIA remain unchanged.
