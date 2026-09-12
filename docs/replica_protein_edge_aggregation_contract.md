# Canonical protein-edge replica aggregation — Stage 31.B

## Status

Stage 30 is complete. Stage 31.A is accepted at checkpoint
`b7f112c890503d192ca1356ce775256f575424ff`.
Stage 31.B pure canonical protein-edge replica aggregation is implemented in
[`replica_protein_edge_aggregation.py`](../src/mania/replica_protein_edge_aggregation.py).
Stage 31 remains incomplete. Stage 31.C specialized lipid/glycan replica
aggregation is next. Stage 31.D owns Dataset workflow, aggregate exports,
provenance/validation and final Stage 31 acceptance.

## Canonical-only input and identity

```python
aggregate_canonical_protein_edges_across_replicas(
    group: CompatibleReplicaAggregationGroup,
    table: CanonicalProteinEdgeWindowTable,
) -> CanonicalProteinEdgeReplicaAggregation
```

Only the exact accepted Stage 30.C canonical protein-edge table is accepted.
There is no source-level aggregation. The table and group must both target
`uniprotkb:O95436-1:sequence-v3`, sequence SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
Reference mismatches fail, including for empty tables.

One edge identity is exactly
`(source_canonical_residue_number, target_canonical_residue_number, edge_type)`.
Numbers are exact integers in 1..690 with `source < target`. Canonical names
must match the pinned reference and therefore agree across replicas. Source
residue indexes, IDs, chains and names never determine statistical identity
and need not agree across replicas. Retained source MET may map explicitly to
canonical 330 THR in a T330M group; output identity retains 330 THR only.
The group's `variant_id` remains authoritative and must agree across members.

To keep aggregate model construction and aggregation free of filesystem reads,
the module holds an in-memory copy of the accepted Stage 30.A reference payload.
The existing `CanonicalProteinReference` validates its pinned sequence digest
and metadata; regression tests compare its entire payload to the packaged
reference. It supplies no new sequence or source mapping authority. Present-row
scientific validity delegates to the existing pure source-row validator on a
private copy, and canonical evidence delegates to Stage 30.B mapping validation
with that in-memory reference. Recorded `row.occupancy` is used unchanged;
31.B does not independently redefine its contact/frame formula.

## Group, window and engine/system boundaries

The accepted Stage 31.A group is the only authority for expected replicas,
availability and the compatible requested physical window. Match members only
by exact `(dataset_id, system_id, trajectory_id, replica_id)`. Matching rows must
agree with the member's dataset, system, trajectory, replica, engine, variant,
condition and disulfide state. `condition=None` is valid; condition is never
a join key. Engines and systems never share a statistical vector.

Each call operates on one group/window. A combined table may contain other
systems, replica keys and windows, which do not enter this aggregate. Rows
targeting the group's `window_id` and `window_index` must have exactly equal
requested start/end under `Decimal(str(value))` equality and identical endpoint
inclusion. A same-label/index bounds mismatch fails instead of being silently
ignored. Production interval, length, step and overlap compatibility remain
Stage 31.A's responsibility and are not recomputed from rows.

These binding checks also apply to matching unavailable/excluded rows. Their
mere presence is valid. Exact table/row types, fixed table metadata, unique
canonical row identities and deterministic input ordering protect against
ambiguous or tampered inputs. Public errors are portable, deterministic
`ReplicaProteinEdgeAggregationError(ValueError)` messages.

## Edge universe and sparse absence

For the current group/window, the universe is the union of canonical edge
identities observed in at least one **available** member. It excludes edges
seen only in unavailable/excluded replicas, other groups or other windows.
There is no enumeration of all possible canonical pairs.

| Member status | Present row | Absent row |
| --- | --- | --- |
| `available` | Use recorded occupancy | Use 0 only in the statistical vector |
| `unavailable` | No observation | No observation |
| `excluded` | No observation | No observation |

An available replica with no rows remains available and enters every emitted
edge's denominator. Sparse absence never creates or modifies a per-replica
source/canonical row. Unavailable/excluded replicas contribute neither a zero
nor any denominator count, even when their scientific rows physically exist.

Zero available replicas, or no edges observed in any available replica, returns
a valid empty aggregate: `edge_count = 0`, `edges = ()` (JSON `[]`). No division
by zero or fabricated edge occurs.

## Frozen statistics and deterministic arithmetic

Let `x_1, ..., x_n` contain all available occupancies for one edge, including
materialized zeroes. For every emitted edge, `n > 0`.

| Field | Definition |
| --- | --- |
| `n_replicates_available` | `n = group.available_replica_count` |
| `mean_occupancy` | `sum(x_i) / n` |
| `median_occupancy` | Middle sorted value for odd n; arithmetic mean of the two middle values for even n |
| `std_occupancy` | For n >= 2, `sqrt(sum((x_i - mean)^2) / (n - 1))` |
| `n_replicates_supporting` | Count of `x_i > 0`, strictly, with no epsilon or other threshold |
| `support_fraction` | `n_replicates_supporting / n_replicates_available` |

The sample standard deviation uses **ddof=1**. This decision is frozen in
Stage 31.B and is recorded only in dedicated Stage 31 documentation; the frozen
Dataset scientific contract is unchanged.

For **n=1**, `std_occupancy = None` (JSON `null`). A single observation supplies
no sample-variance estimate, so no artificial zero-variance claim is made.
Its mean and median equal that observation, with support count 1 and fraction 1.

Occupancies are converted with `Decimal(str(value))`. Sorted Decimal values
supply the mean, median, support fraction and sample variance. All arithmetic,
including square root, uses an isolated `Context(prec=50)` with fixed default
rounding and traps; caller precision, rounding, traps and flags remain unchanged.
Each statistic converts once to float at the public model boundary. There is
no binary-float incremental accumulation.

## Frozen models and serialization

`CanonicalProteinEdgeReplicaAggregate` fields, in order:

```text
source_canonical_residue_number, source_canonical_resname,
target_canonical_residue_number, target_canonical_resname, edge_type,
mean_occupancy, std_occupancy, median_occupancy,
n_replicates_available, n_replicates_supporting, support_fraction
```

Mean, median and support fraction are finite in [0,1]. Supporting count is an
exact integer in 1..n. Standard deviation is null exactly for n=1, and otherwise
finite and non-negative. Validation also checks exact support fraction, n=1
mean/median equality, mean no larger than support fraction, and zero median
when absent replicas form a strict majority.

`CanonicalProteinEdgeReplicaAggregation` has fields `group`, `edge_count`,
`edges`, plus non-init fixed reference metadata and these constants:

```text
schema_version = mania.canonical_protein_edge_replica_aggregation.v0.1
kind = mania_canonical_protein_edge_replica_aggregation
```

The root requires an exact compatible group, exact aggregate rows in a tuple,
`edge_count == len(edges)`, unique edge identities and ordering by
`(edge_type, source_canonical_residue_number, target_canonical_residue_number)`.
Every row's available count must equal the group's count. Both models provide
independent deterministic `to_dict()` results. Root serialization contains fixed
metadata, the complete group, edge count and an ordered JSON array of edges.
Input group and canonical table serialize identically before and after a call.

## Scientific smoke

The fixture uses `napi2b-v1-test` / `wt-norm` / `gromacs`, window 20–25 ns,
expected replicas 1,2,3 and canonical `311 GLN — 330 THR`, type `hbond`.

| Available vector | Mean | Median | Sample std | Available | Supporting | Support fraction |
| --- | --- | --- | --- | --- | --- | --- |
| `[0.7, 0.0, 0.2]` | 0.3 | 0.2 | 0.36055512754639896 | 3 | 2 | 0.6666666666666666 |
| `[0.7, 0.0]`, third unavailable or excluded | 0.35 | 0.35 | 0.4949747468305833 | 2 | 1 | 0.5 |
| `[0.6]`, other members unavailable/excluded | 0.6 | 0.6 | null | 1 | 1 | 1.0 |
| `[0.0, 1.0]` | 0.5 | 0.5 | 0.7071067811865476 | 2 | 1 | 0.5 |
| `[0.2, 0.5, 0.8]` | 0.5 | 0.5 | 0.3 | 3 | 3 | 1.0 |

## Scientific and integration boundaries

31.B makes no QC/exclusion decisions: no 95% coverage threshold, occupancy or
support cutoff, RMSD, MAD or variance filtering. Explicit upstream exclusions
are respected; Stage 32 owns QC policy. There is no annotation-based biological
filtering, cross-window aggregation or cross-system/engine aggregation.

No specialized lipid/glycan aggregation, CSV export, workflow/CLI integration,
manifest, provenance/inventory or unified-validation change is implemented.
The pure API uses no filesystem, network, Git, subprocess, clock, trajectory or
MDAnalysis. Stage 27–30 science and canonical per-replica tables, PBC, analysis,
dependencies and WANIA remain unchanged.
