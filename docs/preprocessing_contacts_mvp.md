# Preprocessing contacts MVP

## Stage 13 goal

Stage 13 introduces residue contacts in small, contacts-specific steps. Stage
13.1a was contract-only: it defined the MVP contact meaning and validated
detection options before any contact computation. Stage 13.1b added only the
dependency-free result dataclasses and report shape. Stage 13.2a adds
single-condition residue contact extraction from an already loaded runtime.
Stage 13.2b composes those condition results across an existing manifest load
result. Stage 13.2c adds opt-in local scientific smoke coverage for the
manifest contacts computation path. Stage 13.3a adds dependency-free
`contacts_perframe.csv` writing for existing contacts results. Stage 13.3b
adds dependency-free `contact_edges.csv` aggregate contacts writing. Stage
13.3c adds read-only validation for both contacts CSV outputs. Stage 13.3d
adds dependency-free contacts export documentation and synthetic examples.
Stage 13.3e adds opt-in local scientific smoke coverage for the accepted
contacts compute/export/validation chain. Stage 13.4a adds the
dependency-free contacts reference comparison input contract and readiness
validation only. Stage 13.4b adds dependency-free output comparison for the
two accepted contacts CSV outputs. Stage 13.5a adds contacts performance
boundary documentation only; see
`docs/preprocessing_contacts_performance_boundary.md`. Stage 13.5b adds
lightweight contacts performance sanity checks using small synthetic data only.

## MVP contact definition

A residue-residue contact is detected per frame when the minimum distance
between selected atoms of two distinct residues is less than or equal to the
configured cutoff distance.

The MVP contact level is residue-level, detection occurs per trajectory frame,
and each pair represents two distinct residues. The distance is the minimum
atom-atom distance between the selected atoms of those residues. The default
atom filter is `heavy`, the default cutoff is `4.5`, and the default distance
unit label is `angstrom`.

Stage 13 performs no unit conversion and no biological interpretation.

## Contact detection options

`PreprocessingContactDefinition` records the fixed MVP definition.
`PreprocessingContactDetectionOptions` records the extraction options:

- `cutoff_distance` and `distance_unit`;
- `atom_filter`, currently `heavy` or `all`;
- residue-level `contact_level`;
- same-residue and duplicate-pair exclusion;
- `skip_resnames`, which controls solvent and ion exclusion;
- frame-index and time inclusion flags reserved by the result contract.

Same-residue exclusion and duplicate-pair exclusion are enabled by default.
The options validate their values, normalize `skip_resnames` deterministically,
and serialize without runtime objects.

## Result contracts

Stage 13.1b added these shape contracts:

```python
PreprocessingContactComputationIssue
PreprocessingContactPairResult
PreprocessingContactFrameResult
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
```

The pair contract represents one observed residue-residue contact in one
frame. It validates distinct source and target residue indexes but does not
create graph direction or graph semantics. Stage 13.2a emits each pair once in
canonical lower-index-first order.

Frame, condition, and manifest contracts provide deterministic contact, frame,
and condition counts plus nested JSON-safe `to_dict()` output. Stage 13.2a
consumes the frame and condition contracts without changing their behavior,
and Stage 13.2b consumes the manifest contract without changing its summary
semantics.

Stage 13.1a added no contact computation and no contact result dataclasses.
Stage 13.1b added those dataclasses before Stage 13.2a implemented
single-condition computation.

## Stage 13.2a single-condition extraction

`compute_condition_contacts(...)` accepts one existing
`PreprocessingConditionLoadResult`, uses its already loaded runtime object, and
returns `PreprocessingConditionContactsResult`. It does not load files or
acquire MDAnalysis.

For every trajectory frame, the function:

- preserves zero-based trajectory iteration order;
- reads a usable frame time, then falls back to
  `frame_index * frame_time_ps`, or uses `None`;
- preserves original residue iteration indexes;
- respects `skip_resnames`;
- selects heavy atoms by default or all atoms when requested;
- computes the minimum selected atom distance for each canonical distinct
  residue pair;
- records a contact when that distance is less than or equal to the cutoff;
- returns deterministic pair ordering and JSON-safe result objects.

Coordinates are assumed compatible with the configured option unit label. No
unit conversion is performed. Pure-Python nested distance loops are the
accepted MVP; performance optimization is future Stage 13.5 work. Biological
interpretation is out of scope.

Missing load/runtime inputs are returned as failed condition results. Atom
position problems are frame issues, so available frame results are preserved
and the condition can return `partial`. Residues with no selected atoms,
including hydrogen-only residues under the heavy filter, produce no contacts
without failing.

## Stage 13.2b manifest aggregation

`compute_manifest_contacts(...)` accepts one existing
`PreprocessingManifestLoadResult`, calls `compute_condition_contacts(...)` for
each contained condition load result in deterministic manifest order, and
returns `PreprocessingManifestContactsResult`.

The manifest function defaults options to
`PreprocessingContactDetectionOptions()` and passes the selected options to
each condition computation. Failed and partial condition contact results are
preserved. Manifest-level load issues are mapped into contact computation
issues on the manifest result. Unexpected per-condition computation exceptions
are captured as deterministic failed condition contact results so later
conditions can still be processed.

Stage 13.2b is orchestration only. It does not inspect runtime objects, load
files, acquire MDAnalysis, add distance logic, export CSV, compare references,
run local scientific smoke tests, or add graph semantics.

## Stage 13.2c local scientific smoke

The local scientific contacts computation smoke test validates the accepted
runtime computation path when explicitly enabled with the existing local
scientific harness. It uses the public load-manifest, load-runtimes, and
compute-manifest-contacts APIs, then checks result shape and JSON
serialization.

The smoke test is opt-in and local only. It does not add export, validation,
reference comparison, report bundles, graph output, benchmark thresholds, or
biological interpretation. At Stage 13.2c, contacts CSV export remained future
Stage 13.3 work, and graph export remained future work.

## Stage 13.3a contacts_perframe.csv writer

`write_contacts_perframe_csv(...)` accepts either a
`PreprocessingConditionContactsResult` or a
`PreprocessingManifestContactsResult` and writes the canonical
`contacts_perframe.csv` table. It writes one row per detected contact pair per
frame, preserving condition result order, frame result order, and contact pair
order from the existing result object.

The fixed header is:

```text
condition_name,frame_index,time_ps,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,minimum_distance,distance_unit,atom_filter,frame_passed
```

Zero-contact results and empty manifest results write the header only and pass
when the input object and output path are otherwise valid. Failed condition
results are reported through deterministic write issues but do not fail the
write solely because the condition failed. Failed frames are skipped by
default, counted in `skipped_frame_count`, and reported through
`frame_result_failed`; with `include_failed_frames=True`, any contacts already
present on failed frames are written with `frame_passed` set to `false`.

The writer returns a JSON-safe
`PreprocessingContactsPerFrameCsvWriteResult`. It does not recompute contacts,
load runtimes, acquire MDAnalysis, create parent directories, validate the
written CSV, compare references, write `contact_edges.csv`, or produce graph
outputs.

## Stage 13.3b contact_edges.csv aggregate writer

`write_contact_edges_csv(...)` accepts either a
`PreprocessingConditionContactsResult` or a
`PreprocessingManifestContactsResult` and writes the canonical
`contact_edges.csv` aggregate contacts table. It writes one row per
residue-pair aggregate per condition.

The fixed header is:

```text
condition_name,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,contact_frame_count,total_frame_count,contact_frequency,minimum_distance,mean_minimum_distance,distance_unit,atom_filter
```

For each aggregate contact pair, the writer reports `contact_frame_count`,
`total_frame_count`, `contact_frequency`, `minimum_distance`, and
`mean_minimum_distance`. Pairs are aggregated by condition, residue-pair
identity, residue labels, segment labels, distance unit, and atom filter, so
pairs from different conditions, units, or atom filters are not merged.

Zero-contact results and empty manifest results write the header only and pass
when the input object and output path are otherwise valid. Failed condition
results are reported through deterministic write issues but do not fail the
write solely because the condition failed. Failed frames are skipped by
default and do not contribute to `total_frame_count`; with
`include_failed_frames=True`, failed frames contribute to totals and any
contacts already present on those frames are aggregated. Duplicate same-pair
contacts in one frame are reported as `duplicate_pair_in_frame`, count as one
contacted frame, use the minimum duplicate distance for that frame, and make
the write result fail as a data-quality issue.

The writer returns a JSON-safe `PreprocessingContactEdgesCsvWriteResult`. It
does not recompute contacts, load runtimes, acquire MDAnalysis, create parent
directories, validate the written CSV, compare references, or produce graph
outputs.

## Stage 13.3c contacts CSV validation

`validate_contacts_perframe_csv(...)` validates an existing
`contacts_perframe.csv` file. `validate_contact_edges_csv(...)` validates an
existing `contact_edges.csv` aggregate contacts file.

The validators check the exact fixed headers, row column counts, required
fields, integer fields, finite non-negative numeric fields, lowercase
`frame_passed` values for the per-frame table, `heavy` or `all` atom filters,
same-residue pairs, and duplicate row keys. Header-only outputs pass with zero
rows.

For `contact_edges.csv`, validation also checks aggregate consistency:
`contact_frame_count` and `total_frame_count` are positive integers,
`contact_frame_count` does not exceed `total_frame_count`,
`contact_frequency` is between 0 and 1 and matches the count ratio within
`1e-12`, and `mean_minimum_distance` is not below `minimum_distance`.

The validators are read-only. They read CSV files only, do not recompute
contacts, do not write CSV, do not call contacts writers, do not compare
references, and do not produce graph outputs.

## What contact_edges.csv means

contact_edges.csv is an aggregate contacts table of observed residue pairs.
It is not backend graph edges.csv and does not establish the backend graph
data contract.

`contacts_perframe.csv` is the Stage 13.3a per-frame contacts export.
`contact_edges.csv` is the Stage 13.3b aggregate contacts export. Backend
graph `nodes.csv`, backend graph `edges.csv`, and `graph.json` remain future
graph-stage artifacts.

## Stage 13.3d contacts export docs and examples

The contacts export guide documents the accepted flow from existing contacts
result objects through `contacts_perframe.csv`, `contact_edges.csv`, and both
CSV validators. The examples are synthetic, dependency-free, and write
temporary output only when run directly.

Stage 13.3d adds no source behavior changes, contact computation, local
scientific export smoke test, reference comparison, report bundle, graph
export, CLI integration, workflow integration, real-data CI, or biological
interpretation.

## Stage 13.3e local scientific contacts export smoke

The local scientific contacts export smoke test validates the accepted chain
when explicitly enabled with the existing local scientific harness:

```text
load manifest -> load runtimes -> compute manifest contacts
-> write contacts_perframe.csv -> write contact_edges.csv
-> validate both CSV outputs
```

The Stage 13.3 export block now covers the per-frame writer,
`contact_edges.csv` aggregate writer, validators, docs/examples, and opt-in
local export smoke. Generated CSV files are written only under pytest's
temporary path during the test.

The smoke test does not add source behavior changes, new APIs, reference
comparison, report bundles, graph export, CLI integration, workflow
integration, real-data CI, benchmark thresholds, or biological interpretation.
Reference comparison is covered by Stage 13.4, and graph export remains
future.

## Stage 13.4a contacts reference comparison input contract

`PreprocessingContactsReferenceComparisonInput` stores generated/reference CSV
path pairs for `contacts_perframe.csv` and `contact_edges.csv`.
`PreprocessingContactsReferenceComparisonOptions` stores distance,
frequency, row-order, and target-selection options.

`validate_contacts_reference_comparison_input(...)` checks that requested
targets have both generated and reference paths, that paths exist and are not
directories, that generated/reference paths are distinct, and that each
requested file passes the accepted contacts CSV validator. It is
dependency-free and read-only.

Stage 13.4a does not compare CSV rows, compute numeric differences, match
rows, produce mismatch reports, build report bundles, add local scientific
comparison smoke coverage, or produce graph outputs. Numeric contacts output
comparison remains Stage 13.4b.

## Stage 13.4b contacts output comparison

`compare_contacts_outputs(...)` compares generated contacts CSV outputs with
reference contacts CSV outputs using the accepted Stage 13.4a input contract.
It can compare only `contacts_perframe.csv`, only `contact_edges.csv`, or both
targets according to `PreprocessingContactsReferenceComparisonOptions`.

The comparison returns JSON-safe
`PreprocessingContactsReferenceComparisonRowResult`,
`PreprocessingContactsReferenceComparisonTargetResult`, and
`PreprocessingContactsReferenceComparisonResult` objects. It first uses
`validate_contacts_reference_comparison_input(...)`; invalid inputs return an
empty failed comparison report with deterministic issues.

Rows are matched by exact contacts CSV keys. For `contacts_perframe.csv`, the
key is condition, frame index, residue pair identity, residue labels, segment
labels, distance unit, and atom filter. For `contact_edges.csv`, the key is
condition, residue pair identity, residue labels, segment labels, distance
unit, and atom filter. Distance fields are compared with distance tolerances,
`contact_frequency` is compared with frequency tolerances, and time, status,
and count fields are exact comparisons. Row order is ignored unless
`require_exact_row_order=True`.

Stage 13.4b does not compute contacts, change contacts writers or validators,
add report bundles, add local scientific comparison smoke coverage, add
CLI/workflow integration, or produce graph outputs. `contact_edges.csv`
remains an aggregate contacts table and is not backend graph `edges.csv`.

## Stage 13.5a contacts performance boundary docs

Stage 13.5a documents the contacts MVP performance boundary in
`docs/preprocessing_contacts_performance_boundary.md`.

The boundary records that contacts computation is MVP-level, default CI
remains stable and independent from real MD data, local scientific tests remain
opt-in integration smoke tests, and `contact_edges.csv` remains aggregate
contacts output rather than backend graph `edges.csv`.

Stage 13.5a adds no performance tests, benchmark tests, hard timing
benchmarks, source behavior changes, performance optimizations, CLI/workflow
integration, report bundles, or graph export. Stage 13.5b adds lightweight
performance sanity checks without hard timing thresholds. Graph remains
future work.

## Stage 13.5b contacts performance sanity checks

Stage 13.5b adds dependency-free lightweight performance sanity checks for the
contacts MVP. The checks use small synthetic data only and cover bounded,
deterministic result, export, validation, and comparison behavior. Stage 13.6
closes the contacts MVP documentation boundary before graph-specific work.

Stage 13.5b adds no benchmark tests, hard timing thresholds, source behavior
changes, implementation optimizations, local scientific performance gates,
CLI/workflow integration, report bundles, or graph export. Graph remains
future work.

## Stage 13.6 final contacts MVP boundary

Stage 13 Contacts MVP now covers the accepted Python API flow:

```text
loaded manifest runtimes
-> contacts computation
-> contacts export
-> CSV validation
-> reference comparison
-> performance boundary/sanity checks
```

The implemented contacts blocks are:

- loaded-runtime contact computation through `compute_condition_contacts(...)`
  and `compute_manifest_contacts(...)`;
- dependency-free `contacts_perframe.csv` and aggregate `contact_edges.csv`
  export;
- read-only CSV validation for both accepted contacts outputs;
- dependency-free generated/reference CSV comparison for both contacts
  outputs;
- documented performance boundary plus small synthetic sanity checks.

The final contacts MVP public surface includes:

```python
PreprocessingContactDefinition
PreprocessingContactDetectionOptions
PreprocessingContactComputationIssue
PreprocessingContactPairResult
PreprocessingContactFrameResult
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
compute_condition_contacts(...)
compute_manifest_contacts(...)
PreprocessingContactsPerFrameCsvWriteIssue
PreprocessingContactsPerFrameCsvWriteResult
write_contacts_perframe_csv(...)
PreprocessingContactEdgesCsvWriteIssue
PreprocessingContactEdgesCsvWriteResult
write_contact_edges_csv(...)
PreprocessingContactsPerFrameCsvValidationIssue
PreprocessingContactsPerFrameCsvValidationResult
validate_contacts_perframe_csv(...)
PreprocessingContactEdgesCsvValidationIssue
PreprocessingContactEdgesCsvValidationResult
validate_contact_edges_csv(...)
PreprocessingContactsReferenceComparisonOptions
PreprocessingContactsReferenceComparisonInput
PreprocessingContactsReferenceComparisonIssue
PreprocessingContactsReferenceComparisonInputValidationResult
validate_contacts_reference_comparison_input(...)
PreprocessingContactsReferenceComparisonRowResult
PreprocessingContactsReferenceComparisonResult
compare_contacts_outputs(...)
```

This is a Python API and documentation/test boundary, not a workflow product.
`contact_edges.csv` remains an aggregate contacts table. It is not backend
graph `edges.csv`.

Stage 13.6 adds no source behavior, public APIs, report bundle, graph export,
CLI/workflow integration, real-data CI, or biological interpretation.

## What is not implemented yet

Before Stage 13.3a there was no `contacts_perframe.csv` writer.
Before Stage 13.3b there was no `contact_edges.csv` writer. Before Stage
13.3c there were no contacts CSV validators. Before Stage 13.3d there were no
contacts export docs/examples. Before Stage 13.3e there was no local
scientific contacts export smoke. Before Stage 13.4b there was no contacts
output comparison. Before Stage 13.5a there was no contacts performance
boundary doc. Before Stage 13.5b there were no contacts performance sanity
checks. Stage 13.5b adds no contacts benchmark tests. Stage 13.6 adds final
boundary docs and tests only.

At the Stage 13.6 boundary, still not implemented:

- contacts report bundle;
- graph export;
- backend graph `nodes.csv`;
- backend graph `edges.csv`;
- `graph.json`;
- graph diagnostics from real preprocessing;
- CLI/workflow scientific MVP;
- biological interpretation;
- real-data CI.

## Boundary before graph

No graph export exists yet.
No backend graph `nodes.csv` is produced.
No backend graph `edges.csv` is produced.
No `graph.json` is produced.
Graph export belongs to a later stage after contacts are stable.

The next stage may begin graph-specific work only after this contacts MVP
boundary. Any backend graph `nodes.csv`, backend graph `edges.csv`,
`graph.json`, or graph diagnostics from real preprocessing must be introduced
by an explicit graph-stage task, not by the contacts MVP.

## Stage 14.1a transition

Stage 13 Contacts MVP remains complete. Stage 14.1a starts graph mapping by
turning accepted preprocessing contacts results into in-memory graph-ready
records only.

contact_edges.csv remains aggregate contacts output. contact_edges.csv is
aggregate contacts table output from Stage 13; it is not backend graph
edges.csv. backend graph edges.csv remains separate/future; the backend graph
edges.csv writer is Stage 14.1c.

Stage 14.1a maps contacts into graph edge records and maps contact-observed
residue identities into condition-scoped node records. Stage 14.1a maps
contact-observed residues only; isolated residues and Rg-to-graph mapping
remain future unless explicitly scoped.

Graph artifact writers remain future from the Stage 14.1a boundary: the
nodes.csv writer is Stage 14.1b, the backend graph edges.csv writer is Stage
14.1c, and the graph.json writer is Stage 14.1e.
Stage 14.1a does not run graph validators or diagnostics and does not add
CLI/workflow integration.

## Stage 14.1b transition

Stage 13 Contacts MVP remains complete. Stage 14.1a graph mapping can feed
Stage 14.1b nodes.csv writer, which writes backend graph nodes.csv only from
accepted graph node mapping records.

Stage 13 contact_edges.csv is aggregate contacts table output and remains
aggregate contacts output. It is not backend graph edges.csv. backend graph
edges.csv is separate/future, and backend graph edges.csv writer remains
Stage 14.1c at this boundary.

Stage 14.1b does not write graph edges, does not validate graph CSV outputs,
does not write `graph.json`, and does not run graph validators or diagnostics.
graph CSV validation remains Stage 14.1d and graph.json remains Stage 14.1e.

## Stage 14.1c transition

Stage 13 Contacts MVP remains complete. Stage 14.1c adds the backend graph
edges.csv writer from accepted Stage 14.1a graph mapping records:

```python
write_preprocessing_graph_edges_csv(...)
```

The writer consumes `PreprocessingGraphExportMappingResult` and writes
backend graph edges.csv only. It uses the accepted backend graph `EDGE_COLUMNS`
schema, preserving mapping source and target node IDs in `resid_i` and
`resid_j`, preserving condition scope in `condition`, mapping `edge_kind` to
`edge_type`, mapping `contact_frequency` to `contact_freq`, and mapping
angstrom-labelled `mean_minimum_distance` to `mean_dist_A`.

Unsupported optional edge metadata is serialized as empty strings because
the backend graph edge schema has no columns for Stage 13 frame counts,
minimum distance, atom filter, distance unit, or dynamic lifetime metrics.

Stage 13 contact_edges.csv is aggregate contacts table output and remains
aggregate contacts output. It is not backend graph edges.csv. backend graph
edges.csv is separate and is now written only by the Stage 14.1c graph edge
writer from accepted graph mapping records.

Stage 14.1c does not validate graph CSV outputs, does not write `graph.json`,
does not run graph validators or diagnostics, and does not add workflow/CLI
integration. graph CSV validation remains Stage 14.1d and graph.json remains
Stage 14.1e.
