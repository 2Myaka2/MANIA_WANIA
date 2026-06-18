# Contacts export

## Purpose

Contacts export turns existing contacts result objects into two dependency-free
CSV outputs:

```text
contacts_perframe.csv
contact_edges.csv
```

It does not compute contacts.
It does not load trajectories.
It does not acquire MDAnalysis.
It does not run graph export.

The accepted conceptual flow is:

```text
contacts result object
-> write contacts_perframe.csv
-> write contact_edges.csv
-> validate both CSV outputs
-> optionally compare generated CSV outputs with references
```

## Inputs

The accepted writer inputs are:

```python
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
```

Those result objects are normally produced by:

```python
compute_condition_contacts(...)
compute_manifest_contacts(...)
```

Stage 13.3d examples use synthetic constructed result objects instead of real
MD data. They do not require MDAnalysis, load trajectories, or compute contacts
from runtime objects.

## Per-frame contacts CSV

The canonical filename is `contacts_perframe.csv`.

The writer is:

```python
write_contacts_perframe_csv(...)
```

The validator is:

```python
validate_contacts_perframe_csv(...)
```

The file contains one row per contact pair per frame. Zero-contact results and
empty manifest results write a header-only file and pass when the input object
and output path are valid.

Failed frames are skipped by default and counted in the writer result. With
`include_failed_frames=True`, contacts already present on failed frames are
written with `frame_passed` set to `false`.

The exact header is:

```text
condition_name,frame_index,time_ps,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,minimum_distance,distance_unit,atom_filter,frame_passed
```

## Aggregate contact edges CSV

The canonical filename is `contact_edges.csv`.

The writer is:

```python
write_contact_edges_csv(...)
```

The validator is:

```python
validate_contact_edges_csv(...)
```

The file contains one row per aggregate residue pair per condition.
Zero-contact results and empty manifest results write a header-only file and
pass when the input object and output path are valid.

Failed frames are skipped by default and do not contribute to
`total_frame_count`. Failed frames do not contribute to `total_frame_count`.
With `include_failed_frames=True`, failed frames contribute to totals and any
contacts already present on those frames are aggregated.

The aggregate fields are:

- `contact_frame_count`
- `total_frame_count`
- `contact_frequency`
- `minimum_distance`
- `mean_minimum_distance`

The exact header is:

```text
condition_name,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,contact_frame_count,total_frame_count,contact_frequency,minimum_distance,mean_minimum_distance,distance_unit,atom_filter
```

contact_edges.csv is an aggregate contacts table.
It is not backend graph edges.csv.

contact_edges.csv is not nodes.csv.
contact_edges.csv is not backend graph edges.csv.
contact_edges.csv is not graph.json.
Graph export belongs to a later stage.

Stage 14.1a adds in-memory graph export mapping from accepted contacts result
objects. contacts export outputs can now feed graph export mapping through
the same accepted contacts result semantics, but this does not make
contact_edges.csv backend graph edges.csv.

contact_edges.csv is aggregate contacts table output from Stage 13.
backend graph edges.csv remains separate/future at the Stage 14.1a mapping
boundary. Stage 14.1a maps contacts into graph edge records and contact
endpoint residue identities into graph node records.

Graph writers remain future stages at the Stage 14.1a boundary: the nodes.csv
writer is Stage 14.1b, the backend graph edges.csv writer is Stage 14.1c, and
the graph.json writer is Stage 14.1e.

Stage 14.1b adds a nodes.csv writer for contacts-derived graph mapping. This
writer consumes `PreprocessingGraphExportMappingResult` and writes backend
graph nodes.csv only. It does not write graph edges and does not turn Stage
13 contact_edges.csv into backend graph edges.csv.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv is separate/future, and backend graph edges.csv writer remains
Stage 14.1c at the Stage 14.1b boundary. graph CSV validation remains Stage
14.1d and graph.json remains Stage 14.1e.

Stage 14.1c adds `write_preprocessing_graph_edges_csv(...)` for backend graph
edges.csv from accepted graph mapping records. The writer uses the accepted
backend graph `EDGE_COLUMNS` schema, preserves source and target node IDs as
`resid_i` and `resid_j`, preserves condition scope in `condition`, maps the
priority-selected `edge_kind` to `edge_type`, writes all unique edge types to
`all_edge_types`, writes their count to `n_edge_types`, maps
`contact_frequency` to `contact_freq`, and maps angstrom-labelled
`mean_minimum_distance` to `mean_dist_A`. Unsupported optional edge metadata
is serialized as empty strings.

Stage 14.1c-fix uses
`data/reference/notebooks_libraries_v1_2/MANIA_analysis_v1_2.ipynb` as the
current graph reference semantics while keeping v1.1 artifacts historical.
v1.2 Cell 5 adds interaction priority for graph edge display. v1.2 Cell 12
fixes temporal RIN export handling, but temporal RIN export is not implemented
by this correction and remains future temporal/workflow artifact scope.
Current Stage 13 generic contacts still write graph edges as
`residue_contact|1` semantics: `edge_type = residue_contact`,
`all_edge_types = residue_contact`, and `n_edge_types = 1`.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv is separate and is now produced only by the Stage 14.1c graph edge
writer. Stage 14.1c does not validate graph CSV outputs, does not write
`graph.json`, and does not run graph validators or diagnostics. graph CSV
validation remains Stage 14.1d and graph.json remains Stage 14.1e.

Stage 13 contacts outputs can feed graph mapping and graph CSV writers through
accepted contacts result objects. Stage 14.1d validates generated backend
graph nodes.csv + corrected edges.csv. This validation is not Stage 13
contacts CSV validation and does not call `validate_contact_edges_csv(...)`.

The graph CSV validation boundary validates generated nodes.csv and corrected
edges.csv only. corrected edges.csv includes all_edge_types and n_edge_types,
and corrected graph edges.csv has multi-type edge fields: `edge_type`,
`all_edge_types`, and `n_edge_types`. Stage 13 contact_edges.csv is aggregate
contacts table output, while backend graph edges.csv is separate graph
artifact.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority defines edge type display priority, v1.2 Cell 12
temporal RIN export fix remains documented-only here, and temporal RIN export
remains future scope.

Stage 14.1d does not write `graph.json`, build a graph export bundle, run
graph diagnostics, add CLI/workflow integration, or change contacts export.
graph.json remains Stage 14.1e and diagnostics remain Stage 14.2a.

Stage 14.1e adds the dependency-free graph.json writer from Stage 14 backend
graph artifacts. Stage 13 contacts outputs can feed graph mapping and graph
CSV writers through accepted contacts result objects, and Stage 14.1e writes
graph.json from accepted/validated nodes.csv + corrected edges.csv. This does
not make Stage 13 contact_edges.csv the backend graph edges.csv. Stage 13
contact_edges.csv is aggregate contacts table output; backend graph edges.csv
and graph.json are Stage 14 graph artifacts.

The Stage 14.1e graph JSON writer uses Stage 14.1d validation before writing.
graph JSON preserves corrected graph edge fields including `edge_type`,
`all_edge_types`, and `n_edge_types`, and it preserves current generic
residue_contact semantics as row fields. It does not build a graph export
bundle, run graph diagnostics, perform graph comparison, or add CLI/workflow
integration. graph export bundle remains Stage 14.1f and diagnostics remain
Stage 14.2a.

Stage 14.1f builds the graph export bundle boundary from existing Stage 14
artifacts. Stage 13 contacts outputs can feed graph mapping and graph CSV
writers through accepted contacts result objects, but the Stage 14.1f bundle
consumes existing nodes.csv, corrected edges.csv, and graph.json artifacts.
This bundle does not make Stage 13 contact_edges.csv the backend graph
edges.csv.

The bundle uses Stage 14.1d CSV validation, checks lightweight graph JSON
structure/count consistency, and preserves corrected graph edge fields through
the bundle boundary: `edge_type`, `all_edge_types`, and `n_edge_types`.
Stage 13 contact_edges.csv is aggregate contacts table output; backend graph
edges.csv and graph.json are Stage 14 graph artifacts.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority is the accepted graph edge display priority, v1.2 Cell
12 temporal RIN export fix remains documented-only here, and temporal RIN
export remains future scope.

Stage 14.1f is dependency-free and read-only. The bundle does not run
diagnostics, graph comparison, local scientific graph smoke tests, temporal
RIN export, or CLI/workflow integration. diagnostics remain Stage 14.2a.

## Validation

Use the read-only validators after writing:

```python
validate_contacts_perframe_csv(...)
validate_contact_edges_csv(...)
```

The validators are:

- read-only
- dependency-free
- exact-header validators
- type/range validators
- not reference comparison
- not graph validation

They read existing CSV files only. They do not compute contacts, load runtime
objects, write CSV, compare references, or produce graph outputs.

## Synthetic example

See `examples/preprocessing/contacts_export_usage.py` for a dependency-free
example that constructs synthetic contacts results, writes both accepted CSVs
inside a `TemporaryDirectory`, and validates both files.

Small static examples are also committed:

- `examples/preprocessing/contacts_perframe.example.csv`
- `examples/preprocessing/contact_edges.example.csv`

These examples are deterministic synthetic rows, not real scientific data.

## Boundaries

Stage 13.3d does not add:

- new computation
- source behavior changes
- local scientific export smoke
- reference comparison
- report bundle
- graph export
- CLI/workflow integration
- real-data CI
- biological interpretation

The examples do not create backend graph `nodes.csv`, backend graph
`edges.csv`, or `graph.json`.

## Local scientific smoke

Stage 13.3e adds an opt-in local scientific contacts export smoke test. It
verifies the accepted local compute/write/validate chain:

```text
load manifest -> load runtimes -> compute manifest contacts
-> write contacts_perframe.csv -> write contact_edges.csv
-> validate both CSV outputs
```

The test uses the existing local scientific harness, requires
`MANIA_RUN_LOCAL_SCIENTIFIC=1`, and uses
`MANIA_LOCAL_REFERENCE_PACKAGE=<path>` for local real data. Generated CSV
files are written only to pytest's temporary directory.

The smoke test does not add new export APIs, compare references, build a
report bundle, or produce graph outputs. contact_edges.csv remains aggregate
contacts output, not backend graph edges.csv.

## Reference comparison input contract

Stage 13.4a adds a dependency-free input contract for future contacts
reference comparison:

```python
PreprocessingContactsReferenceComparisonOptions
PreprocessingContactsReferenceComparisonInput
PreprocessingContactsReferenceComparisonIssue
PreprocessingContactsReferenceComparisonInputValidationResult
validate_contacts_reference_comparison_input(...)
```

The contract describes generated/reference path pairs for both accepted
contacts CSV targets:

```text
generated contacts_perframe.csv vs reference contacts_perframe.csv
generated contact_edges.csv vs reference contact_edges.csv
```

Validation checks option values, requested path pairs, file existence,
directory paths, same generated/reference paths, and the existing
`validate_contacts_perframe_csv(...)` and `validate_contact_edges_csv(...)`
contracts. It does not compare generated and reference rows, compute numeric
differences, match rows, produce mismatch reports, build report bundles, or
produce graph outputs.

## Contacts output comparison

Stage 13.4b adds dependency-free generated/reference comparison for the two
accepted contacts CSV outputs:

```python
compare_contacts_outputs(...)
```

The comparison consumes a validated
`PreprocessingContactsReferenceComparisonInput` and returns JSON-safe result
objects:

```python
PreprocessingContactsReferenceComparisonRowResult
PreprocessingContactsReferenceComparisonTargetResult
PreprocessingContactsReferenceComparisonResult
```

The function compares `contacts_perframe.csv`, `contact_edges.csv`, or both
according to `PreprocessingContactsReferenceComparisonOptions`. Rows are
matched by the exact contacts CSV key used by the validators. Distance fields
use the configured distance absolute/relative tolerances, `contact_frequency`
uses the configured frequency absolute/relative tolerances, and non-tolerant
status, time, and count fields are compared exactly. Row order is ignored by
default and can be enforced with `require_exact_row_order=True`.

The comparison is read-only and uses only the standard library. It does not
compute contacts, change writers or validators, build report bundles, add a
local scientific comparison smoke test, create CLI/workflow integration, or
produce graph outputs. `contact_edges.csv` remains an aggregate contacts
table, not backend graph `edges.csv`.

## Performance boundary

Stage 13.5a documents the contacts MVP performance boundary in
`docs/preprocessing_contacts_performance_boundary.md`.

Stage 13.5b adds lightweight performance sanity checks with small synthetic
data only. These checks cover bounded deterministic contacts result, export,
validation, and comparison behavior without hard timing thresholds.

## Final contacts MVP boundary

Stage 13 Contacts MVP now covers:

```text
loaded manifest runtimes
-> contacts computation
-> contacts export
-> CSV validation
-> reference comparison
-> performance boundary/sanity checks
```

The only accepted contacts CSV outputs are:

```text
contacts_perframe.csv
contact_edges.csv
```

`contact_edges.csv` is an aggregate contacts table. It is not backend graph
`edges.csv`, does not imply backend graph `nodes.csv`, and is not
`graph.json`.

Still not implemented by the contacts export layer:

- contacts report bundle
- `graph.json`
- graph diagnostics from real preprocessing
- CLI/workflow scientific MVP
- biological interpretation
- real-data CI

Stage 13.6 adds final boundary documentation and a docs test only. It does
not add source behavior, public APIs, report bundle output, graph export,
CLI/workflow integration, local scientific comparison or performance gates,
real-data CI, or biological interpretation.

Export, validation, and comparison are dependency-free CSV-level operations.
They consume existing contacts results or existing CSV files, do not load
trajectories, and do not acquire MDAnalysis. Stage 13.5a adds no performance
tests, benchmark tests, hard timing thresholds, source behavior changes, or
performance optimizations.

Graph export is handled by explicit graph-stage APIs, not by contacts export.
`contact_edges.csv` remains an aggregate contacts table, not backend graph
`edges.csv`.

Stage 14.1a graph mapping is in-memory only. It writes no backend graph
`nodes.csv`, no backend graph `edges.csv`, and no `graph.json`, and it does
not run graph validators or diagnostics.

Stage 14.1b writes backend graph `nodes.csv` from accepted graph mapping.
Stage 14.1c writes backend graph `edges.csv` from accepted graph mapping.
The contacts export layer still does not produce backend graph artifacts.

Stage 14.2a runs existing graph validators/diagnostics on generated graph
artifacts after the Stage 14.1f bundle boundary passes. Stage 13 contacts
outputs can feed graph mapping and graph writers through accepted contacts
result objects, but diagnostics do not reinterpret Stage 13 contact_edges.csv
as backend graph edges.csv.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv, graph.json, and diagnostics are Stage 14 graph artifacts. The
diagnostics operate on corrected graph artifacts and preserve graph edge
fields:

```text
edge_type
all_edge_types
n_edge_types
```

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority is the accepted display priority, v1.2 Cell 12
temporal RIN export fix is documented, and temporal RIN export remains future
scope.

Stage 14.2a adds no diagnostics report shape, graph reference comparison,
temporal RIN export, CLI/workflow integration, real-data CI, or biological
interpretation. diagnostics report shape remains Stage 14.2b and reference
comparison remains Stage 14.3.

Stage 14.2b adds the dependency-free diagnostics report shape that summarizes
diagnostics over generated Stage 14 graph artifacts. The report builder
consumes an already computed Stage 14.2a diagnostics result; it does not run
diagnostics again, write report files, create a report bundle, compare
references, add CLI/workflow integration, export temporal RIN artifacts, or
add biological interpretation.

The Stage 14.2b diagnostics report does not reinterpret Stage 13
contact_edges.csv as backend graph edges.csv. Stage 13 contact_edges.csv is
aggregate contacts table output. backend graph edges.csv, graph.json,
diagnostics, and diagnostics report are Stage 14 graph artifacts.

The report preserves corrected graph edge fields as schema/reference context:

```text
edge_type
all_edge_types
n_edge_types
```

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority is the accepted display priority, v1.2 Cell 12
temporal RIN export fix is documented, and temporal RIN export remains future
scope. Reference comparison remains Stage 14.3.

Stage 14.3a adds only the dependency-free reference graph comparison input
contract. It validates generated/reference artifact readiness for explicit
generated and reference `nodes.csv`, corrected backend graph `edges.csv`, and
`graph.json` paths. Stage 14.3a does not perform comparison; actual
comparison remains Stage 14.3b.

The graph comparison input contract records counts and top-level metadata
through the existing graph export bundle boundary. It does not compare node
rows, edge rows, full graph JSON contents, numeric tolerances, diagnostics,
notebook artifacts, temporal RIN export, CLI/workflow outputs, or biological
interpretation.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.1
historical reference artifacts remain historical. v1.2 Cell 5 interaction
priority and v1.2 Cell 12 temporal RIN export fix remain documented context;
temporal RIN export remains future scope.

Corrected graph edges preserve `edge_type`, `all_edge_types`, and
`n_edge_types` according to `EDGE_TYPE_PRIORITY`. Stage 13 contact_edges.csv
is aggregate contacts table output.
backend graph edges.csv, graph.json, diagnostics, and comparison inputs are Stage 14 graph artifacts.

## Future stages

Graph export remains future after contacts MVP.
