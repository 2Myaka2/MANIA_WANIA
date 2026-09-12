# Canonical specialized replica aggregation — Stage 31.C

## Status

Stage 30 is complete. Stage 31.A is accepted. Stage 31.B is accepted at checkpoint
`aae168ab2fc253382c78c9f4248927a9dd4de33c`.
Stage 31.C specialized lipid/glycan replica aggregation is implemented in
[`replica_specialized_aggregation.py`](../src/mania/replica_specialized_aggregation.py).
Stage 31.C is accepted at checkpoint
`dfe614cada83b91cf8015df89c1ea551960b1113`. Stage 31 is complete.
Stage 31.D integrates accepted A/B/C without changing science through the
[Dataset aggregation workflow](replica_aggregation_workflow.md), aggregate exports,
portable inventory/provenance and unified reconstruction validation.
Stage 32 Dataset QC / exclusion is next and has not started.

## Canonical protein boundary

Only exact accepted Stage 30.C `CanonicalProteinLipidWindowTable` and
`CanonicalProteinGlycanWindowTable` inputs are accepted. Protein identity is
canonical O95436-1 residue number and reference resname, pinned to
`uniprotkb:O95436-1:sequence-v3`, sequence SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
Reference mismatches fail even with empty science. Every retained protein name
must match the pinned residue in 1..690. Source residue IDs, indexes, chains and
names never define cross-replica statistical identity. Explicit source MET to
canonical 330 THR mapping retains THR in the aggregate.

As in 31.B, an in-memory copy of the accepted Stage 30.A reference payload keeps
model construction and aggregation free of reference-file reads. The accepted
reference model verifies its pinned digest and metadata; regression compares the
entire payload to the packaged reference. Present-row source/metric validity is
checked through the accepted pure validator on a private copy; canonical mapping
validity uses Stage 30.B with the in-memory reference. Occupancy is consumed
unchanged. Source tables are never statistical inputs.

## Partner identity warning

Stage 29 partner IDs such as `lipid_0001` and `glycan_0001` are topology-local.
Equal IDs or partner names across replicas do not prove molecular correspondence.
No component-count, residue-ID, list-order or nearest-spatial matching is allowed.

`partner_correspondence_id` means only that the supplied topology-local partner
instances are explicitly permitted to be compared in this replica group. It is
aggregation evidence only, **not a canonical molecule ID**, chemical registry ID,
UniProt ID or Dataset publication partner identity. It need only be unique in
the supplied collection; another system/group may reuse the ID independently.

## Explicit partner correspondence

All models are frozen and expose independent deterministic `to_dict()` results.

`ReplicaSpecializedPartnerCorrespondenceMember` fields, in order:

```text
dataset_id, system_id, trajectory_id, replica_id, local_partner_id, partner_name
```

Dataset identifiers follow accepted non-empty string/strip semantics. Partner
IDs and names must be non-empty stripped strings. The derived `replica_key` is
exactly `(dataset_id, system_id, trajectory_id, replica_id)`; it has no condition.

`SpecializedPartnerCorrespondence` fields are `partner_correspondence_id`,
`partner_kind`, `partner_name`, `members`. Kind is exactly `lipid` or `glycan`,
using the accepted `MolecularPartnerKind`. Members are a tuple, unique and sorted
by replica key. Every member name must exactly equal the supplied correspondence
name; names are neither normalized nor used to match partners.

`SpecializedPartnerCorrespondences` contains a tuple named `correspondences`.
IDs are unique and sorted. Within a replica and kind, a local partner can belong
to only one correspondence. `lookup(partner_correspondence_id)` requires an exact
ID; there is no name lookup. Unsorted or ambiguous input fails deterministically.

Each layer call requires only correspondences of that layer's kind. Every
correspondence's member-key set must equal **exactly all available replica keys**
in the accepted `CompatibleReplicaAggregationGroup`. Missing available bindings,
extra/foreign bindings and bindings to unavailable/excluded members fail.
The correspondence itself makes no availability or window decisions.

An available replica must have exactly one local partner binding for each
correspondence. Local IDs and component residue indexes may differ across
replicas. A relevant row's local partner ID must match that replica's binding,
and its name must agree with the correspondence. Same-name unbound partners are
ignored. If no meaningful corresponding partner exists across all available
replicas, omit that correspondence; no aggregate is fabricated.

## Missing correspondence vs sparse absence

| Evidence | Aggregation behavior |
| --- | --- |
| Available replica + complete valid correspondence + matching row | Use recorded occupancy |
| Available replica + complete valid correspondence + absent sparse row | Materialize 0 only in the statistical vector |
| Defined correspondence missing an available replica binding | Fail before occupancy materialization; never zero |
| No correspondence defined for a partner | Ignore its rows; no inferred aggregate |
| Unavailable or excluded replica | No occupancy value, support contribution or denominator count |

For each correspondence, the universe is the union of canonical protein residue
numbers observed with its explicitly bound partners in at least one available
replica for the current window. Rows only in unavailable/excluded replicas never
create this universe. There is no enumeration of all 690 residues.

Zero available replicas require `correspondences.correspondences == ()` and
return valid empty roots with `row_count=0`, `rows=()`. One available replica with
an explicit binding is valid; if it has no rows, the residue universe is empty.

## Group and physical-window binding

Match by the exact four-field replica key, then the current `window_id` and
`window_index`, then the explicitly bound local partner ID. Other replicas,
systems and windows are ignored. Unbound partners and unavailable/excluded rows
may exist but supply no statistical evidence. Neither condition nor partner name
selects rows.

Relevant rows must agree with all member Dataset metadata: dataset, system,
trajectory, replica, engine, variant, condition and disulfide state.
`condition=None` is valid. A contradictory engine for the same bound replica
fails; rows belonging to another engine/system are unrelated and ignored.
Matching label/index rows must agree with requested start/end under
`Decimal(str(value))` equality and with right-endpoint inclusion. Different
bounds under the same label/index fail. Complete requested schedule compatibility
belongs to 31.A and is not recomputed. Duplicate relevant replica/window/canonical
protein/local-partner rows fail even if their source protein evidence differs.
As in 31.B, Dataset/window binding checks also apply to rows for the current
replica key and label/index that are unbound or unavailable/excluded; their mere
presence is valid, but contradictory identity or window metadata fails.

## Statistics

Both layers emit only:

```text
canonical_residue_number, canonical_resname,
partner_correspondence_id, partner_name,
mean_occupancy, std_occupancy, median_occupancy,
n_replicates_available, n_replicates_supporting, support_fraction
```

For the available vector including permitted sparse zeroes, mean is `sum(x)/n`,
median uses sorted values (averaging the two middle values for even n), supporting
count is strictly `occupancy > 0` with no epsilon, and support fraction is
`supporting/n`. Sample SD uses **ddof=1**:
`sqrt(sum((x - mean)**2)/(n - 1))`. For n=1, `std_occupancy=None` (JSON `null`).

The exact accepted 31.B arithmetic is used: `Decimal(str(value))`, sorted
summation and an isolated `Context(prec=50)` for mean, median, sample variance,
square root and support fraction. Convert once to public floats. Caller Decimal
precision, rounding, traps and flags are unchanged. No suitable public 31.B
statistical helper exists; the narrow formula is repeated without modifying
31.B and exact cross-layer equality is tested.

Row validation checks canonical identity, non-empty partner fields, finite
bounded mean/median/support fraction, positive available count, support in 1..n,
exact support fraction, n=1 SD/mean/median rules, non-negative SD otherwise,
mean no greater than support fraction and zero median for a strict zero majority.

## Aggregate roots and pure APIs

```python
aggregate_canonical_protein_lipid_across_replicas(group, table, *, correspondences)
aggregate_canonical_protein_glycan_across_replicas(group, table, *, correspondences)
```

They return `CanonicalProteinLipidReplicaAggregation` and
`CanonicalProteinGlycanReplicaAggregation`, containing respective
`CanonicalProteinLipidReplicaAggregate` / `CanonicalProteinGlycanReplicaAggregate`
rows. Root init fields are `group`, `correspondences`, `row_count`, `rows`.
Non-init public fields are schema, kind and exact canonical reference identity.

| Layer | Schema version | Kind |
| --- | --- | --- |
| Lipid | `mania.canonical_protein_lipid_replica_aggregation.v0.1` | `mania_canonical_protein_lipid_replica_aggregation` |
| Glycan | `mania.canonical_protein_glycan_replica_aggregation.v0.1` | `mania_canonical_protein_glycan_replica_aggregation` |

Roots validate exact group and row types, correspondence kind/coverage,
`row_count == len(rows)`, unique identities, row-to-correspondence ID/name binding,
and each row's available count against the group. Rows are sorted by
`(partner_correspondence_id, canonical_residue_number)`. Empty roots are valid.
Errors are portable deterministic `ReplicaSpecializedAggregationError(ValueError)`.
Group, table and correspondence serialization remain identical before/after calls.

## Scientific smokes

The controlled lipid correspondence binds r1 `lipid_0003`, r2 `lipid_0007`, and
r3 `lipid_0002` for canonical 311 GLN. Glycan fixtures use explicit equivalent
bindings and synthetic partner names, without introducing biological registries.

| Available vector | Mean | Median | Sample SD | Available | Supporting | Support fraction |
| --- | --- | --- | --- | --- | --- | --- |
| Lipid `[0.7, 0, 0.2]` | 0.3 | 0.2 | 0.36055512754639896 | 3 | 2 | 0.6666666666666666 |
| Glycan `[0.5, 0.5, 0]` | 0.3333333333333333 | 0.5 | 0.28867513459481287 | 3 | 2 | 0.6666666666666666 |
| `[0.7, 0]`, third unavailable/excluded | 0.35 | 0.35 | 0.4949747468305833 | 2 | 1 | 0.5 |
| `[0.6]` | 0.6 | 0.6 | null | 1 | 1 | 1.0 |

**Three available replicas with correspondence only for r1/r2 fail before any
occupancy zero is materialized**, even for an empty canonical table.

## No distance/lifetime aggregation

Distance mean/minimum, contact-frame counts, episode counts, episode lengths and
glycan linkage evidence remain per-replica. No inter-replica formula is frozen
for those fields. No distance averaging/minimum, lifetime aggregation, summed
contact frames, specialized `edge_weight`, local partner IDs or component
indexes are added to aggregate rows.

## QC and integration boundaries

No Stage 32 QC, 95% policy, exclusions, outlier thresholds, RMSD, MAD or annotation
filtering is performed. Explicit upstream member availability is respected.
No automatic partner matching is included. The pure Stage 31.C module has no
workflow/CLI, CSV/export, manifest or provenance/validation responsibilities;
these are provided separately by Stage 31.D. The API uses no
filesystem, network, Git, subprocess, clock, trajectory or MDAnalysis operations.
Stage 27–30 science, 31.A/B source, canonical per-replica tables, frozen Dataset
scientific contract, dependencies, PBC, analysis and WANIA remain unchanged.
