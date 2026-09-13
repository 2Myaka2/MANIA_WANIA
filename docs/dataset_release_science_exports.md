# Dataset v1.0 scientific publication exports — Stage 33.C

## Status

Stage 32 is complete (Stage 32 COMPLETE). Stage 33.A is accepted and remains the
sole frozen schema authority. Stage 33.B is accepted at
`5f093a088df721a9d1bf743bc8259ee566b473da`.
Stage 33.C scientific publication exporters are implemented. Stage 33 remains
incomplete. Stage 33.D release assembly is next. Dataset v1.0 remains unreleased;
package version remains `mania-wania 0.1.0`.

## Production authority

The production DAG remains:

```text
27–30 per-replica scientific outputs
  -> 32 QC and authoritative DatasetQCDecisionSet
  -> QC-derived Stage 31 aggregation manifest
  -> 31 replica aggregation using that exact manifest
  -> 33 publication
```

Development order `27 -> 28 -> 29 -> 30 -> 31 -> 32 -> 33` does not change
production authority. A technically valid pre-QC aggregate cannot be published.

## API and seven publication tables

`build_dataset_release_scientific_tables` in `mania.dataset_release_science`
returns an immutable `DatasetReleaseScientificTables` containing exactly:

| Family | Frozen relative path |
| --- | --- |
| Protein per replica | `science/protein_edges_by_window.csv` |
| Lipid per replica | `science/protein_lipid_contacts_by_window.csv` |
| Glycan per replica | `science/protein_glycan_contacts_by_window.csv` |
| Protein aggregate | `aggregates/protein_edges_by_window_replica_aggregation.csv` |
| Lipid aggregate | `aggregates/protein_lipid_contacts_by_window_replica_aggregation.csv` |
| Glycan aggregate | `aggregates/protein_glycan_contacts_by_window_replica_aggregation.csv` |
| Explicit metrics | `metrics/metrics.csv` |

Individual builders expose the same logical models. Empty accepted input families
produce empty tables with their frozen headers. The bundle always exposes seven
schemas; no missing partner, edge or aggregate is fabricated. Builders read no
files, scan no directories and infer nothing from the current environment.
Writing each explicit CSV path is a separate operation.

## Per-replica inclusion and excluded history

Stage 33.B `simulations.included_in_scientific_release` is the only publication
inclusion authority. There is no second selection list and no recalculation from
QC, aggregate availability, source row presence, condition or filenames.

Every encountered Stage 30 canonical row must match one simulation by the full
`(dataset_id, system_id, trajectory_id, replica_id)` key. Unknown keys fail.
Known rows with inclusion false are omitted normally. Those replicas remain in
simulations, normalized QC and upstream audit/provenance; inputs are never
mutated or deleted. An included replica may have no sparse science rows.

Technical unavailability for Stage 31 remains distinct from scientific-release
inclusion. A QC-available replica with valid per-replica science and aggregation
unavailability may publish per-replica science when the simulation flag is true.
It contributes no aggregation denominator. An available aggregate member can
also have per-replica scientific inclusion false under the supplied 33.B model.

## Canonical protein science

Inputs are exactly the accepted Stage 30 `CanonicalProteinEdgeWindowTable`,
`CanonicalProteinLipidWindowTable` and `CanonicalProteinGlycanWindowTable` models.
Their reference must match `uniprotkb:O95436-1:sequence-v3` and SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
No recanonicalization occurs.

Frozen scientific columns are copied exactly: window evidence, resolved-frame
denominator, contact counts, occupancy and episode/lifetime summaries. Protein
`edge_weight == occupancy` is checked and preserved; inconsistent input fails.
No absent canonical pair becomes a zero row. Retained source-topology identity
is not published. Canonical graph endpoint names remain valid: T330M source
topology `MET 330` publishes canonical `330 THR`.

## Specialized science and glycan carrier boundary

Lipid/glycan partner IDs and names are copied with the full replica key and
canonical protein identity. Partner IDs remain topology-local. They are not
converted into canonical or cross-replica molecule identities.

Distance and episode summaries come directly from the accepted ordinary contact
tables. `distance_mean_A` and `distance_min_A` retain contact-positive-frame-only
semantics. Glycan carrier-residue to first-sugar covalent linkage observations
remain excluded from ordinary occupancy/lifetime/distance summaries. Raw carrier
geometry is not an input to publication and stays upstream audit evidence.
Specialized science has no invented `edge_weight`. No annotation or QC fields
are denormalized into scientific rows.

## Aggregate authority and copied statistics

The frozen `DatasetReleaseAggregationAuthority` requires all three accepted models:

1. Authoritative Stage 32 `DatasetQCDecisionSet`.
2. QC-derived Stage 31 `ReplicaAggregationManifest`.
3. Exact `aggregation_manifest_used` for the supplied Stage 31 aggregate run.

The manifest used must equal the QC-derived manifest by exact model equality,
including paths, groups, members and correspondence. Pending review fails.
Decision-set and manifest candidate populations must agree. Availability must
respect accepted Stage 32 decisions, including technical-unavailable precedence.
This is structural model-level authority supplied by the caller; full file and
provenance proof is Stage 33.D work. No QC decision is created or reevaluated.

Accepted Dataset-level `CanonicalProteinEdgeReplicaAggregationTable`,
`CanonicalProteinLipidReplicaAggregationTable` and
`CanonicalProteinGlycanReplicaAggregationTable` rows are projected losslessly.
Every row must match an exact authoritative group, requested physical window,
window label/index and consistency metadata. Condition never defines a group.
Repeated windows validate independently.

`n_replicates_available` must equal the count of available members of that group.
Every member's `simulations.included_in_replica_aggregation` must agree with its
availability. Excluded and technically unavailable members contribute no denominator.
The six accepted statistics are copied, never recalculated: `mean_occupancy`,
`std_occupancy`, `median_occupancy`, `n_replicates_available`,
`n_replicates_supporting` and `support_fraction`. Sample-SD semantics stay in
Stage 31. Single-replica SD stays `None`, encoded as a blank cell, never zero.

## Correspondence IDs

Specialized aggregate `partner_correspondence_id` must exist in that exact
QC-derived group/family, with matching partner name. Accepted QC projection may
remove excluded bindings; only retained available mappings are required.
Correspondence is never inferred from local IDs, names or row order.
It is an aggregation correspondence identity, not a canonical lipid/glycan,
chemical registry or globally portable molecule identity.

Specialized aggregates contain only the six frozen occupancy/support statistics.
No aggregate distance, lifetime, contact counts or specialized `edge_weight` are
added. Zero-available groups and empty accepted aggregate tables emit no rows.

## Explicit metrics

`AuthoritativePublicationMetric` preserves all frozen Stage 33.A fields, including
explicit `metric_id`, `source_record_key`, metric name/value/unit and source
artifact role/path. There is no closed metric vocabulary or computation.
This publication-selection API requires a finite numeric value without rounding,
normalization or rescaling. The generic frozen CSV schema retains its accepted
nullable metric-value capability; this builder requires an actual measurement.

Every supplied metric must belong to a science-included simulation. An explicit
metric for an excluded, unselected or unknown replica fails rather than vanishing.
QC review evidence is never automatically promoted into primary metrics.
Replica-global metrics have both window fields null. Window-scoped metrics have
both fields populated and must match the exact replica/window relationship.
Source paths must be relative, use forward slashes and contain no parent traversal
or home leakage; unsafe paths are rejected without rewriting or inspecting files.
Stage 33.D validates source-artifact lineage.

## Keys and CSV serialization

All primary keys, field order, nullability and paths come from the unchanged
Stage 33.A contract. Duplicate publication rows fail; they are not deduplicated.
In-scope foreign keys validate science/metrics to simulations, science/window
metrics to time windows, aggregates to systems and canonical endpoints to nodes.
Canonical names, identity labels, requested windows and denominator evidence
are checked against supplied metadata. Global metrics skip only the window FK.

33.C reuses the exact same CSV serialization authority as 33.B:
`DatasetReleaseTable`, `build_publication_table`, `write_publication_csv` and
`read_publication_csv`. The accepted scope amendment generalizes only table-ID
lookup to all 17 frozen tabular publication specs. The original ten Stage 33.B
builders and their serialized bytes retain their behavior. Hierarchical release
JSON, unknown and non-publication IDs remain unsupported by the CSV adapter.
No duplicate publication schemas or second serialization framework exist.

Strict frozen headers, deterministic primary-key sorting, exact numeric values,
blank nulls, lowercase `true`/`false`, atomic writes, path binding and overwrite
protection remain unchanged. All seven tables support exact model/CSV/model
roundtrips and deterministic bytes, including header-only output.

## Stage 33.D

Release assembly, the three release JSON artifacts, inventory/provenance, full
lineage, complete cross-table validation, runtime integration, publication CLI
and final Stage 33 acceptance remain next. This stage adds no Parquet adapter,
dependency, trajectory runtime, scientific recomputation or aggregation engine.
Accepted Stage 27–32 science, PBC, analysis and WANIA remain unchanged.
