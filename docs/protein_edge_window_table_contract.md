# Dataset protein-edge-by-window source table — Stage 28.C

## Status and release boundary

Stage 27 is complete. Stage 28.A is accepted. Stage 28.B is accepted at checkpoint
`869afbf9ea7bd31591026295861db0d0f1dc05d7`. Stage 28.C source-indexed table/export
is implemented. Stage 28 remains incomplete; Stage 28.D integration and real-data
acceptance is next. MANIA remains `mania-wania 0.1.0`.

**This file is not yet Dataset v1.0 release-ready.**
The artifact is a **source-indexed, canonical-ready Dataset export candidate**:

```text
protein_edges_by_window_source.csv
```

The `_source` suffix distinguishes this interim artifact from final canonical
publication tables. Stage 30 canonical mapping is required before release
publication. It must replace/enrich source residue references with validated
UniProt O95436 canonical numbering before final publication. Final export belongs
to Stage 30/33; the [frozen Dataset scientific contract](dataset_v1_scientific_contract.md)
is unchanged. Technical CSV validation is not a release decision.

There are no canonical residue numbers, canonical residue names, mapping status,
blank canonical columns, or invented canonical placeholders in Stage 28.C.
Preserving source evidence is a scientific integrity requirement, not permission
to publish source numbers as canonical UniProt numbers.

## Models and explicit input binding

[protein_edge_window_table.py](../src/mania/preprocessing/protein_edge_window_table.py)
provides frozen `DatasetProteinEdgeWindowTableInput`,
`DatasetProteinEdgeWindowRow`, and `DatasetProteinEdgeWindowTable` dataclasses.
The root exposes fixed non-init constants:

```text
schema_version = mania.dataset_protein_edges_by_window_source.v0.1
kind = mania_dataset_protein_edges_by_window_source
```

```python
build_dataset_protein_edge_window_table(
    inputs: tuple[DatasetProteinEdgeWindowTableInput, ...],
) -> DatasetProteinEdgeWindowTable
```

Each input explicitly pairs exact `PreprocessingConditionTemporalExecution` and
`ProteinEdgeWindowAggregation` records. Their execution conditions must agree;
that label is only an in-memory routing bridge. Failed scientific state is not
accepted. Dataset identity comes only from `temporal_execution.dataset_spec.identity`.
Aggregation window count/order and each window's ID, index, requested/resolved/
missing counts, and coverage must exactly match the retained temporal window plan.
Each edge must belong to its parent window and use its resolved denominator.
Inconsistent inputs raise portable `DatasetProteinEdgeWindowTableError` messages;
the builder never repairs or regenerates plans.

## Dataset and dynamic row identity

Dataset trajectory identity is the replica key:

```text
(dataset_id, system_id, trajectory_id, replica_id)
```

Input replica keys must be unique, including inputs with no observed edges.
`condition` is nullable scientific metadata, never a trajectory/row lookup key.
Two trajectories/replicas both labelled `NORM` remain separate. A NAMD identity
with `condition=None` retains that absence; no routing name or engine label is
substituted. All eight Dataset identity fields are copied exactly, including
optional `disulfide_state`. Engines must already be normalized Dataset engines
(`gromacs` or `namd`); strings must already be non-empty and stripped.

The unique dynamic edge row identity is:

```text
(dataset_id, system_id, trajectory_id, replica_id, window_id,
 source_residue_index, target_residue_index, edge_type)
```

Rows sort exactly by `dataset_id`, `system_id`, `trajectory_id`, `replica_id`,
`window_index`, `edge_type`, `source_residue_index`, `target_residue_index`.
Neither identity nor sorting includes condition. The table rejects duplicates
and incorrect order; only the builder sorts its copied rows.

## Window identity and retained temporal evidence

`window_id` and zero-based `window_index` identify the accepted Stage 27 window.
`requested_window_start_ns`, `requested_window_end_ns`, and
`right_endpoint_inclusive` copy its requested bounds and endpoint rule unchanged.
`effective_window_start_ns` and `effective_window_end_ns` use the first/last actual
selected times, converted from ps with
`float(Decimal(str(value)) / Decimal("1000"))` in an independent Decimal context.
Accepted floating representation noise is preserved. Bounds are never clamped,
rounded for presentation, inferred from stride, or replaced with requested times.

An observed edge requires positive requested and resolved counts, present finite
non-negative effective bounds, and effective end at least start. Requested end
must exceed start. Counts reject booleans. Sampling evidence remains:

```text
requested_sample_count = resolved_frame_count + missing_sample_count
coverage_fraction = resolved_frame_count / requested_sample_count
```

Coverage is checked by exact equality to Stage 27's float ratio, without a
tolerance or a 95% threshold. Physical partial coverage remains exportable.

## Source edge identity and Stage 30 join evidence

Internal indexes are authoritative inside a trajectory. Undirected orientation
is inherited from 28.B: `source_residue_index < target_residue_index`.
This ordering is unrelated to biological canonical numbering.

Both sides retain chain/segment reference, resid, and resname. Existing 28.B
`source_segid`/`target_segid` copy into `source_chain_id`/`target_chain_id` as
interim source-side mapping references. SEGID is not universally equivalent to a
canonical biological chain identifier. Stage 30 will validate source mapping
semantics per engine/system, including any chain correspondence.

`source_resid` and `target_resid` are `str | None`: integer `330` becomes `"330"`,
string `"330A"` stays unchanged, and `None` stays absent. Numeric-looking strings
remain strings on CSV read. Equal source resids in different chains remain
distinct when internal indexes differ. Resids are never assumed globally unique.
Together with engine and trajectory identity, these fields provide explicit
evidence for the later strict mapping join. No NAMD/GROMACS equivalence is inferred.

## Accepted metrics, copied without recalculation

Stage 28.C copies all six [Stage 28.B metrics](protein_edge_window_aggregation_contract.md)
exactly: `n_contact_frames`, `occupancy`, `n_contact_episodes`,
`mean_episode_length_ns`, `max_episode_length_ns`, and `edge_weight`.
Row validation delegates their accepted invariants to `ProteinEdgeWindowMetric`.
No episode segmentation or contact calculation is called.

```text
n_contact_frames = number of positive resolved frames in the window
occupancy = n_contact_frames / resolved_frame_count
edge_weight = occupancy
episode_length_ns = last_contact_actual_time_ns - first_contact_actual_time_ns
```

The occupancy comparison uses 28.B's independent Decimal ratio converted once
to float. Missing samples break continuity and do not enter the denominator.
Resolved negatives break continuity and do enter the denominator. Gap tolerance
remains zero; a single-frame episode lasts `0.0` ns. Positive counts, bounded
occupancy, finite non-negative lifetimes, `max >= mean`, and identical
weight/occupancy remain required. No distance publication metrics are added.

| Requested / resolved / missing | Positive frames | Occupancy and weight | Episodes | Mean / max lifetime |
| --- | --- | --- | --- | --- |
| 5 / 5 / 0 | 4 (indexes 0, 1, 2, 4) | 0.8 | 2 | 0.05 / 0.10 ns |
| 5 / 4 / 1 | all 4 resolved (indexes 0, 1, 3, 4) | 1.0 | 2 | 0.05 / 0.05 ns |

These examples use actual times 5000, 5050, 5100, 5150, 5200 ps; the second lacks
the 5100 ps sample. Stage 28.C preserves their distinct accepted outputs.

## Sparse semantics

Only observed edge/type/window combinations have rows. Zero-contact edges and
zero-edge windows create no artificial rows. Overlapping windows retain independent
rows even when source frames overlap. `hbond` and `ionic` for the same pair/window
are separate rows because `edge_type` is part of identity.

`rows == ()` is valid, including zero builder inputs or Dataset-aware inputs
without observed edges. Window completeness remains in `temporal_execution.json`
until a later complete Dataset publication bundle supplies dedicated window
metadata. This CSV alone cannot enumerate zero-edge trajectories/windows.

## Exact CSV contract and persistence

[protein_edge_window_table_io.py](../src/mania/preprocessing/protein_edge_window_table_io.py)
exports `DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS` as this exact 34-column tuple,
matching row declaration and `to_dict()` order:

```text
dataset_id,system_id,trajectory_id,variant_id,engine,condition,replica_id,disulfide_state,window_id,window_index,requested_window_start_ns,requested_window_end_ns,right_endpoint_inclusive,effective_window_start_ns,effective_window_end_ns,requested_sample_count,resolved_frame_count,missing_sample_count,coverage_fraction,source_residue_index,target_residue_index,source_chain_id,target_chain_id,source_resid,target_resid,source_resname,target_resname,edge_type,n_contact_frames,occupancy,n_contact_episodes,mean_episode_length_ns,max_episode_length_ns,edge_weight
```

`write_dataset_protein_edge_window_csv(table, output_dir, *, overwrite=False)`
writes only `<output_dir>/protein_edges_by_window_source.csv` using standard
`csv`, UTF-8, LF record endings, and exactly one final newline. Optional condition,
disulfide, chain, and resid values use empty cells for `None`; absence is never
encoded as the literals `None`, `null`, or `NA`. Booleans use lowercase
`true`/`false`; integers use unsigned base-10 decimal; finite floats use `repr`
without scientific rounding. Standard CSV quoting preserves delimiters in strings.

The header is always written: an empty table produces exactly one header row.
Identical inputs yield identical bytes across output directories. A task-owned
temporary file is created in the target directory and published atomically:
replacement with overwrite enabled, or a no-clobber link otherwise. Existing
targets, including concurrent creations, are protected when overwrite is false.
Failure cleans only the owned temporary file and preserves any prior target.
The frozen write result exposes `output_path`, `written`, `error`, and `passed`.

`read_dataset_protein_edge_window_csv(path)` requires UTF-8, exact header/order,
exact cell counts, strict scalar parsing, full row validation, and table uniqueness/
ordering. It rejects duplicate/reordered/missing/extra columns, malformed CSV,
non-lowercase booleans, signed/zero-padded/non-integer count cells, non-finite
floats, scientific invariant violations, and incorrectly ordered external rows.
It never silently sorts. Empty optional cells return `None`. A header-only file
returns zero rows. Read errors are portable `DatasetProteinEdgeWindowCsvReadError`.

`validate_dataset_protein_edge_window_csv(path)` delegates to the strict reader.
Its frozen report contains `csv_path`, `row_count` (or `None` on failure), frozen
`field`/`message` issues, and a `passed` property. Outcome dictionaries retain
their explicit local path field; error/issue text never exposes paths or contents.
The table's root dictionary order is `schema_version`, `kind`, `row_count`, `rows`.
It is deterministic under `json.dumps(..., allow_nan=False, separators=(",", ":"))`.

## Stage 28.D boundary and verification

This pure transformation and explicit file API has no workflow/CLI integration,
automatic preprocessing emission, inventory/provenance role, or unified-validation
role. Stage 28.D owns those integrations and real PoC acceptance. No canonical
mapping, replica aggregation, QC release decision, exclusion policy, or biological
interpretation is implemented. There is no trajectory read, directory scan, Git,
clock, environment metadata, PBC operation, or new dependency. These APIs are not
re-exported through `preprocessing/__init__.py`.

28.A, 28.B, Stage 27, existing contacts/graph/residue/temporal schemas,
provenance/inventory, unified validation, CLI, analysis, dependencies, and WANIA
remain unchanged. [Table tests](../tests/test_preprocessing_protein_edge_window_table.py)
and [CSV tests](../tests/test_preprocessing_protein_edge_window_table_io.py) cover
the scientific examples, mapping evidence, nullable identity, deterministic sparse
rows, strict failures, atomic cleanup, and pure operation without MDAnalysis.
