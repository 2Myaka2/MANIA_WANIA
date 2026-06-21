# Preprocessing graph export boundary before workflow

## Purpose

Stage 14.4b freezes the completed Stage 14 graph export boundary before any
workflow or CLI integration. It summarizes the accepted Python API sequence,
backend graph artifacts, validation, diagnostics, reference comparison, and
known mismatch guidance that future orchestration may consume.

This document is a boundary document. It does not add source behavior, new
public APIs, workflow/CLI integration, real-data CI, temporal RIN export or
comparison, biological interpretation, dependency changes, or reference-data
changes.

Stage 15.1 adds the next dependency-free workflow contract layer in
`docs/preprocessing_graph_workflow_contract.md`. That contract defines run
options, deterministic output layout, planned step names, and planning issues
only. It still does not execute the workflow or add CLI integration.

Stage 15.7 now adds an optional workflow orchestration wrapper around the
accepted Stage 14.3a/14.3b reference comparison APIs. It remains disabled by
default, requires explicit reference artifact paths when enabled, does not
search for reference artifacts, does not execute notebooks, and does not
compare temporal RIN. Stage 15.7 does not change the Stage 14 comparison
algorithm or accepted artifact contracts described here.

Stage 15.10 now documents the final backend workflow boundary before future
frontend/API work in
`docs/preprocessing_graph_workflow_boundary_before_frontend_api.md`.

## Completed Stage 14 capabilities

Stage 14 now provides these accepted slices:

- Stage 14.1a: real preprocessing graph export mapping from accepted contacts
  result objects;
- Stage 14.1b: backend graph `nodes.csv` writer;
- Stage 14.1c: backend graph `edges.csv` writer;
- Stage 14.1c-fix: corrected multi-type edge schema;
- Stage 14.1d: graph CSV validation;
- Stage 14.1e: `graph.json` writer;
- Stage 14.1f: graph export bundle boundary;
- Stage 14.2a: graph diagnostics runner bridge;
- Stage 14.2b: diagnostics report shape;
- Stage 14.3a: reference comparison input contract;
- Stage 14.3b: generated-vs-reference graph artifact comparison;
- Stage 14.4a: expected mismatch and known semantic difference guidance;
- Stage 14.4b: final graph export boundary docs before workflow.

These slices are dependency-free at the export, validation, diagnostics,
report, and comparison boundary. They operate on accepted in-memory contacts
results or existing graph artifacts; they do not inspect or process real MD
data by themselves.

## Public API Surface

The accepted Stage 14 public APIs are grouped by purpose below.

Mapping:

```python
PreprocessingGraphNodeMappingRecord
PreprocessingGraphEdgeMappingRecord
PreprocessingGraphExportMappingIssue
PreprocessingGraphExportMappingResult
build_preprocessing_graph_export_mapping(...)
```

CSV writers:

```python
PreprocessingGraphNodesCsvWriteIssue
PreprocessingGraphNodesCsvWriteResult
write_preprocessing_graph_nodes_csv(...)

PreprocessingGraphEdgesCsvWriteIssue
PreprocessingGraphEdgesCsvWriteResult
write_preprocessing_graph_edges_csv(...)
```

CSV validation:

```python
PreprocessingGraphCsvValidationIssue
PreprocessingGraphCsvValidationResult
validate_preprocessing_graph_csvs(...)
```

graph.json writer:

```python
PreprocessingGraphJsonWriteIssue
PreprocessingGraphJsonWriteResult
write_preprocessing_graph_json(...)
```

Bundle:

```python
PreprocessingGraphExportBundleArtifact
PreprocessingGraphExportBundleIssue
PreprocessingGraphExportBundleResult
build_preprocessing_graph_export_bundle(...)
```

Diagnostics:

```python
PreprocessingGraphDiagnosticsRunIssue
PreprocessingGraphDiagnosticsCheckResult
PreprocessingGraphDiagnosticsRunResult
run_preprocessing_graph_diagnostics(...)
```

Diagnostics report:

```python
PreprocessingGraphDiagnosticsReportSection
PreprocessingGraphDiagnosticsReport
build_preprocessing_graph_diagnostics_report(...)
```

Reference comparison input:

```python
PreprocessingGraphReferenceComparisonOptions
PreprocessingGraphReferenceComparisonInput
PreprocessingGraphReferenceComparisonIssue
PreprocessingGraphReferenceComparisonInputValidationResult
validate_preprocessing_graph_reference_comparison_input(...)
```

Reference comparison:

```python
PreprocessingGraphReferenceComparisonMismatch
PreprocessingGraphReferenceComparisonTargetResult
PreprocessingGraphReferenceComparisonResult
compare_preprocessing_graph_reference_artifacts(...)
```

## Artifact Boundary

Stage 14 backend graph artifacts are:

```text
nodes.csv
edges.csv
graph.json
```

Stage 14 `edges.csv` is backend graph `edges.csv`. Stage 13
`contact_edges.csv` is not backend graph `edges.csv`.

Stage 14 `graph.json` is structural and row-preserving. It is derived from
accepted and validated backend graph CSV artifacts, and current CSV-derived
node and edge row values are preserved as strings.
CSV-derived node and edge row values are preserved as strings.

The Stage 14 graph export bundle consumes existing graph artifacts and reports
metadata and consistency issues. It does not generate, copy, rewrite, or
mutate `nodes.csv`, corrected `edges.csv`, or `graph.json`.
The graph export bundle consumes existing graph artifacts.

## Accepted Schemas

The accepted `nodes.csv` schema is:

```text
resid,resname,region,condition,x_ca,y_ca,z_ca,tm_relative_z,rmsf_A,sasa_A2,ss,degree,strength,betweenness,closeness,eigenvector,pagerank,kcore,community_id
```

The accepted corrected `edges.csv` schema is:

```text
resid_i,resid_j,edge_type,all_edge_types,n_edge_types,condition,contact_freq,mean_dist_A,std_dist_A,n_episodes,mean_lifetime_frames,max_lifetime_frames,mean_lifetime_ns,max_lifetime_ns,formation_count,breakage_count,first_seen_frame,last_seen_frame,window_cv
```

The accepted `graph.json` top-level structure is:

```text
condition
n_nodes
n_edges
directed
schema_version
nodes
edges
```

`graph.json` preserves node rows from `nodes.csv` and edge rows from corrected
`edges.csv`. It is structural JSON, not a byte-for-byte notebook export.

## Corrected Multi-Type Edge Schema

Corrected backend graph edges preserve:

```text
edge_type
all_edge_types
n_edge_types
```

The accepted priority is:

```python
EDGE_TYPE_PRIORITY = (
    "hbond",
    "disulfide",
    "salt_bridge",
    "ionic",
    "cation_pi",
    "aromatic_pi",
    "hydrophobic",
    "vdw",
)
```

`edge_type` is the primary prioritized edge type. `all_edge_types` is
pipe-separated in current row-preserving artifacts. `n_edge_types` is the
row-preserving string count in current artifacts.

The generic `residue_contact` edge type remains valid for MVP generated graph edges.
It represents Stage 13 generic contact semantics, not biochemical interaction
classification.

## Expected Artifact Sequence Before Workflow

The accepted conceptual Python API sequence before workflow integration is:

```text
Stage 13 contacts result / aggregate contacts
        |
build_preprocessing_graph_export_mapping(...)
        |
write_preprocessing_graph_nodes_csv(...)
write_preprocessing_graph_edges_csv(...)
        |
validate_preprocessing_graph_csvs(...)
        |
write_preprocessing_graph_json(...)
        |
build_preprocessing_graph_export_bundle(...)
        |
run_preprocessing_graph_diagnostics(...)
        |
build_preprocessing_graph_diagnostics_report(...)
        |
validate_preprocessing_graph_reference_comparison_input(...)
        |
compare_preprocessing_graph_reference_artifacts(...)
        |
consult docs/preprocessing_graph_reference_mismatches.md
```

This is a programmatic sequence of accepted APIs. No workflow or CLI
orchestration exists yet. A future workflow may orchestrate this sequence, but
it must preserve the artifact and validation boundaries described here.
No workflow or CLI orchestration exists yet.

## Validation Boundary

`validate_preprocessing_graph_csvs(...)` validates `nodes.csv` plus corrected
backend graph `edges.csv`. It checks exact headers, required identity fields,
duplicate node and edge keys, edge endpoint consistency, self-edges, optional
numeric fields, condition values, and corrected multi-type edge fields.

`build_preprocessing_graph_export_bundle(...)` validates existing graph
artifacts as a coherent artifact set. It starts from existing paths, reuses
CSV validation, checks lightweight `graph.json` structure and count
consistency, and returns metadata and issues.

`validate_preprocessing_graph_reference_comparison_input(...)` validates
generated/reference readiness only. It verifies generated and reference graph
artifact bundles, comparison options, condition expectations, schema-version
expectations, and target enablement.

These validations do not perform biological interpretation and do not classify
expected mismatches.

## Diagnostics And Report Boundary

`run_preprocessing_graph_diagnostics(...)` is a read-only bridge over existing
graph artifacts. It starts with the Stage 14 graph export bundle boundary and
only runs downstream graph JSON validation, contract graph loading, and graph
structure diagnostics after the bundle passes.

`build_preprocessing_graph_diagnostics_report(...)` consumes an existing
`PreprocessingGraphDiagnosticsRunResult`. It builds an in-memory JSON-safe
report shape with overview, artifact, check, issue, schema/reference, and
boundary sections.

The diagnostics report builder does not run diagnostics, read files, write
files, discover reference data, or compare artifacts.

## Reference Comparison Boundary

Graph reference comparison targets `MANIA_analysis_v1_2` semantics. v1.1
reference artifacts remain historical.

Stage 14.3b compares these generated/reference graph artifacts:

```text
nodes.csv
corrected edges.csv
graph.json
```

CSV comparison is exact row-preserving string comparison. It reports row-count
differences, missing generated rows, extra generated rows, and field value
mismatches using deterministic row keys.

`graph.json` comparison is structural, not byte-level. JSON indentation and
object key order do not matter, but top-level metadata, node items, edge
items, and item values still compare after parsing.
graph.json comparison is structural, not byte-level.

Comparison reports mismatches. It does not classify whether a mismatch is
expected, acceptable, scientifically meaningful, or a bug. Expected mismatch
interpretation lives in `docs/preprocessing_graph_reference_mismatches.md`.

## Expected Mismatch Guidance

Stage 14.4a guidance remains the place to interpret comparison differences.
Known guidance includes:

- generic `residue_contact` versus reference biochemical interaction labels;
- empty optional graph metric or geometry fields in generated MVP artifacts;
- exact string comparison causing formatting-sensitive CSV mismatches;
- structural JSON comparison ignoring formatting but not value differences;
- temporal RIN being documented in v1.2 but not compared by Stage 14 graph
  comparison.

Identity, schema, endpoint, condition, count, and unexpected loss of
`edge_type`, `all_edge_types`, or `n_edge_types` still require investigation.

## Reference Semantics

The current graph reference semantics are:

```text
MANIA_analysis_v1_2
```

The expected reference notebook context is:

```text
data/reference/notebooks_libraries_v1_2/MANIA_analysis_v1_2.ipynb
```

`MANIA_analysis_v1_2` documents two relevant changes:

- v1.2 Cell 5 adds interaction priority for graph edge display;
- v1.2 Cell 12 fixes temporal RIN export handling.

The v1.2 Cell 12 temporal RIN fix is documented reference context only for
this graph export boundary. Temporal RIN export and temporal RIN comparison
remain future scope. v1.1 remains historical and is not the default graph
comparison semantics.

## Relationship To Stage 13 Contacts

Stage 13 Contacts MVP computes residue contacts and exports contacts
artifacts. Its accepted contacts outputs are `contacts_perframe.csv` and
`contact_edges.csv`.

Stage 13 `contact_edges.csv` is an aggregate contacts table. It is not backend
graph `edges.csv`.

Stage 14 graph export maps Stage 13 contact-derived residues and contacts into
backend graph artifacts through accepted contacts result objects and graph
mapping records. Stage 14 backend graph `edges.csv` is a separate graph
artifact with the corrected backend graph edge schema.

The boundary is:

```text
Stage 13 contact_edges.csv: aggregate contacts table
Stage 14 edges.csv: backend graph artifact
```

## What Future Workflow/CLI May Consume

Future workflow or CLI integration may consume:

- accepted Stage 13 contacts result objects as graph mapping input;
- `build_preprocessing_graph_export_mapping(...)`;
- backend graph `nodes.csv` and corrected `edges.csv` writers;
- graph CSV validation before JSON writing;
- `write_preprocessing_graph_json(...)`;
- the graph export bundle boundary;
- diagnostics runner and in-memory diagnostics report builder;
- generated/reference comparison input validation and comparison;
- `MANIA_analysis_v1_2` as current graph reference semantics;
- `docs/preprocessing_graph_reference_mismatches.md` for mismatch
  interpretation guidance.

Future workflow/CLI may orchestrate these pieces. It should not duplicate
their validation or comparison logic in a separate workflow-only path.

## What Remains Out Of Scope

Stage 14.4b does not add:

- workflow/CLI integration;
- automatic end-to-end graph export command;
- real-data CI;
- temporal RIN export;
- temporal RIN comparison;
- notebook cell-level comparison;
- biological interpretation;
- biochemical interaction classification beyond generic MVP contact semantics;
- new diagnostics algorithms;
- new public APIs;
- source behavior changes;
- dependency changes;
- reference data modifications.

## Guardrails For Future Workflow Integration

Future workflow/CLI integration should preserve these boundaries:

- reuse accepted Stage 14 public APIs rather than duplicating logic;
- call validation before graph JSON, bundle, diagnostics, and comparison steps;
- preserve the Stage 13 contacts versus Stage 14 graph artifact boundary;
- preserve `MANIA_analysis_v1_2` as default graph reference semantics unless a
  later explicit stage changes it;
- keep v1.1 historical unless explicitly scoped;
- keep temporal RIN export and comparison separate unless future temporal
  scope is accepted;
- do not require MDAnalysis in default graph export docs or default tests;
- do not add real-data CI accidentally;
- keep local scientific tests opt-in;
- do not reinterpret generic `residue_contact` as biochemical classification;
- do not modify `data/reference/**` as part of workflow orchestration.

Future workflow/CLI must not accidentally change the accepted Stage 14
schemas, edge priority semantics, row-preserving string comparison behavior,
diagnostics report shape, or the distinction between mismatch reporting and
mismatch interpretation.

## Suggested Next Stage

The next scoped stage may be:

```text
Stage 15 - Workflow/CLI integration for preprocessing graph export
```

Stage 15.1 begins that work with an in-memory workflow contract only. Later
Stage 15 slices should orchestrate the accepted Stage 14 APIs and artifacts
while preserving the boundaries frozen here.
