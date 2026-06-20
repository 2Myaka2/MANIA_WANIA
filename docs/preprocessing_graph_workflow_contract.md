# Preprocessing graph workflow contract

## Purpose

Stage 15.1 adds the workflow contract foundation for future preprocessing
graph export orchestration. It defines dependency-free in-memory run options,
output layout metadata, planning issues, and planned step names.

This is a workflow contract only. It has no execution behavior. The plan does
not load a manifest, validate local MD paths, load trajectories, compute Rg,
compute contacts, export graph artifacts, run diagnostics, build reports,
perform reference comparison, execute a notebook, or write workflow files.

## Public API

The Stage 15.1 public API is exported from `mania.preprocessing`:

```python
PreprocessingGraphWorkflowOptions
PreprocessingGraphWorkflowOutputLayout
PreprocessingGraphWorkflowIssue
PreprocessingGraphWorkflowPlan
build_preprocessing_graph_workflow_plan(...)
```

The dataclasses are frozen and provide JSON-safe `to_dict()` output. Paths are
serialized as strings. The builder creates only in-memory objects and does not
create directories or files.

Stage 15.2 adds the local manifest readiness API, also exported from
`mania.preprocessing`:

```python
PreprocessingGraphWorkflowManifestReadinessIssue
PreprocessingGraphWorkflowManifestReadinessResult
check_preprocessing_graph_workflow_manifest_readiness(...)
```

This readiness check is still pre-runtime. It checks whether a manifest path
exists, is a file, can be loaded with the existing preprocessing manifest
loader, conforms to the existing manifest contract, and has local input paths
that pass the existing manifest path validator. Stage 15.2 uses the existing
preprocessing manifest contract and does not define a new Stage 15 manifest
format. In short: no new Stage 15 manifest format.

## Run options

`PreprocessingGraphWorkflowOptions` records:

- `manifest_path`;
- `output_dir`;
- `run_name`;
- `overwrite`;
- toggles for Rg, contacts, graph export, diagnostics, and reference
  comparison;
- optional explicit reference artifact paths;
- `reference_semantics`.

`reference_semantics` defaults to `MANIA_analysis_v1_2`. v1.1 remains
historical and is not the default. Reference comparison is disabled by
default.

The options validate types only. They do not check whether `manifest_path` or
`output_dir` exists, do not load YAML, do not inspect `local_md`, and do not
validate topology or trajectory paths.

## Output layout

The deterministic output layout is:

```text
<output_dir>/
  rg/
    rg_timeseries.csv
  contacts/
    contacts_perframe.csv
    contact_edges.csv
  graph/
    nodes.csv
    edges.csv
    graph.json
  reports/
    graph_diagnostics_report.json
    graph_reference_comparison.json
```

The report JSON paths are planned paths for later orchestration. Stage 15.1
does not write `graph_diagnostics_report.json` or
`graph_reference_comparison.json`.

## Planned steps

Every plan includes the foundational step names:

```text
load_manifest
validate_manifest_paths
load_condition_runtimes
```

The remaining steps are included by option:

- `compute_rg` when Rg is enabled;
- `compute_contacts` when contacts are enabled;
- graph export steps when graph export is enabled;
- diagnostics steps when diagnostics and graph export are enabled;
- reference comparison steps when reference comparison and graph export are
  enabled.

Graph export steps are:

```text
build_graph_mapping
write_graph_nodes_csv
write_graph_edges_csv
validate_graph_csvs
write_graph_json
build_graph_export_bundle
```

Diagnostics steps are:

```text
run_graph_diagnostics
build_graph_diagnostics_report
```

Reference comparison steps are:

```text
validate_reference_comparison_input
compare_reference_graph_artifacts
```

These are planned step names only. Stage 15.1 does not call the Stage 11-14
runtime, computation, export, diagnostics, or comparison APIs.

## Dependency rules

Graph export depends on contacts. If graph export is enabled while contacts
are disabled, the plan fails with a deterministic `stage_disabled` issue.

Diagnostics depend on graph export. If diagnostics are enabled while graph
export is disabled, the plan fails with a deterministic `stage_disabled`
issue.

Reference comparison depends on graph export. If reference comparison is
enabled while graph export is disabled, the plan fails with a deterministic
`stage_disabled` issue.

If Rg, contacts, graph export, diagnostics, and reference comparison are all
disabled, the plan fails with `no_workflow_targets_enabled`.

## Reference comparison

The reference comparison disabled by default behavior means normal workflow
planning does not depend on reference artifacts. A default plan can pass
without reference artifact paths.

When reference comparison is enabled, callers must provide explicit reference
artifact paths for:

```text
reference_nodes_csv_path
reference_edges_csv_path
reference_graph_json_path
```

Missing explicit reference artifact paths produce
`reference_paths_required`. Stage 15.1 does not search for reference
artifacts automatically and does not modify `data/reference/**`. The notebook
is not executed. The reference notebook is not executed.

`MANIA_analysis_v1_2` is the current graph reference semantics. v1.1 remains
historical. The v1.2 temporal RIN remains future scope and is not a Stage 15.1
artifact.

## Local data and CI

`local_md` remains local-only. Real topology and trajectory files are not
required by default CI, and `local_md` is not required by default CI. Real MD
files must not be committed. Stage 15.1 does not inspect `local_md`, validate
local MD paths, require MDAnalysis, or add real-data CI.

The workflow contract uses only the standard library. It does not add
dependencies and does not require MDAnalysis, numpy, pandas, pyarrow,
networkx, or local scientific extras.

## Stage 15.2 local manifest readiness

Stage 15.2 adds local manifest readiness only. The check is intended for local
manifests such as:

```text
local_md/manifests/napi2b_10ns.yaml
```

The example local manifest uses the existing preprocessing manifest contract.
Its semantic relative paths are expected to point from the manifest directory
to local inputs, for example:

```text
../normal/topology.tpr
../normal/trajectory.xtc
../tumor/topology.tpr
../tumor/trajectory.xtc
```

These paths are examples only and are not a new schema. Stage 15.2 uses the
existing manifest contract, reports condition names in manifest order, reports
the local input paths declared by the manifest, and returns deterministic
JSON-safe readiness metadata.

Stage 15.2 does not load trajectories, does not create runtime objects, does
not require MDAnalysis, does not compute Rg, does not compute contacts, does
not export graph artifacts, does not run diagnostics, does not execute
reference comparison, does not execute notebooks, does not call CLI or
workflow execution, and does not create files or directories. Stage 15.3 will
add runtime loading.

## Stage 15.3 manifest-driven runtime loading

Stage 15.3 adds a narrow manifest-driven runtime loading layer for the local
two conditions workflow handoff. It exposes runtime loading metadata and the
raw accepted Stage 11 manifest runtime load result for future orchestration,
while `to_dict()` exposes only deterministic JSON-safe metadata and never
serializes raw runtime objects.

Stage 15.3 readiness is called before runtime loading, using the Stage 15.2
local manifest readiness check. A readiness failure prevents runtime loading.
Only after readiness passes does Stage 15.3 reuse the existing Stage 11
runtime/manifest loading APIs, specifically the accepted manifest condition
runtime loading boundary. It adds no new runtime loader and no new manifest
format.

The expected local NAPI2B condition names are `normal` and `tumor` by default.
The expected condition list is configurable, and callers may disable the
normal/tumor expectation for future workflows. The wrapper reports the
condition runtime names loaded through the Stage 11 result.

Stage 15.3 is manifest-driven runtime loading only: no
Rg/contacts/graph/diagnostics/reference/CLI behavior is added. It does not
compute Rg, compute contacts, export graph artifacts, run diagnostics, build a
diagnostics report, perform reference comparison, execute notebooks, or add a
CLI/workflow execution entrypoint.

The Stage 15.3 import/default CI does not require MDAnalysis. The real runtime loading remains optional/local/scientific and may require optional scientific dependencies
only when executed locally with the accepted Stage 11 boundary. `local_md`
remains local-only, not committed, and not required by default CI.

`MANIA_analysis_v1_2` remains the current reference semantics. The reference
notebook is not executed; notebook not executed is part of the workflow
boundary. The reference comparison remains Stage 15.7 optional mode, disabled by
default. Temporal RIN remains future scope. WANIA frontend adapter/API payload
remains future scope.

Stage 15.4 will orchestrate manifest-level Rg + contacts. Stage 15.3 does not
compute them.

## Stage 15.4 manifest-level Rg + contacts orchestration

Stage 15.4 adds manifest-level Rg + contacts orchestration as an in-memory
handoff from Stage 15.3 to later graph export. The Stage 15.3 runtime loading
result feeds Stage 15.4, and Stage 15.4 does not load runtimes itself. It
does not call manifest loading, manifest path validation, local readiness, or
runtime loading APIs.

Stage 15.4 reuses accepted Stage 12 Rg APIs and accepted Stage 13 contacts
APIs. It calls the accepted manifest-level computation boundaries for Rg and
contacts when requested, preserves the raw accepted result objects in memory
for future stages, and exposes only deterministic JSON-safe metadata through
`to_dict()`. It adds no new scientific algorithms, does not manually compute
Rg, and does not manually compute contacts.

The Stage 15.4 boundary is computation orchestration only: no CSV export, no
graph export, no diagnostics, no diagnostics report, no reference comparison,
no CLI, no notebook execution, no file or directory creation, and no local
real MD smoke test. Import/default CI does not require MDAnalysis. Real
computation remains optional/local/scientific through the accepted Stage 11,
Stage 12, and Stage 13 boundaries.

Stage 15.5 will orchestrate graph export: mapping, nodes.csv, corrected
edges.csv, CSV validation, graph.json, and bundle creation. Stage 15.4 does
not build graph artifacts.

`local_md` remains local-only, not committed, and not required by default CI.
`MANIA_analysis_v1_2` remains the current reference semantics. The reference
notebook is not executed; notebook not executed remains part of the workflow
boundary. The reference comparison remains Stage 15.7 optional mode, disabled
by default. Temporal RIN remains future scope. WANIA frontend adapter/API
payload remains future scope.

## Stage 15.5 graph export orchestration

Stage 15.5 adds graph export orchestration only. The Stage 15.4 computation
result feeds Stage 15.5, and Stage 15.5 does not compute Rg/contacts. The
wrapper consumes `PreprocessingGraphWorkflowComputationResult` and
`PreprocessingGraphWorkflowOutputLayout`, requires a passed Stage 15.4
computation with a retained contacts result, and preserves raw accepted Stage
14 graph export results in memory for Stage 15.6 while exposing only JSON-safe
metadata through `to_dict()`.

Stage 15.5 reuses accepted Stage 14 graph export APIs and adds no new graph
semantics. The orchestration order is mapping, backend graph `nodes.csv`,
corrected edges.csv, CSV validation, `graph.json`, and graph export bundle.
The corrected backend graph edge schema remains the accepted Stage 14 schema
with `edge_type`, `all_edge_types`, and `n_edge_types`.

Stage 13 `contact_edges.csv` is an aggregate contacts table. It is not the
backend graph edges.csv artifact. Stage 15.5 writes backend graph edges.csv
through the accepted Stage 14 graph edge writer, not through the Stage 13
contacts CSV writers.

Stage 15.5 may create only the graph parent directory and may write only:

```text
<output_dir>/graph/nodes.csv
<output_dir>/graph/edges.csv
<output_dir>/graph/graph.json
```

It does not write Rg CSV files, contacts CSV files, diagnostics report JSON,
or reference comparison JSON. It performs CSV validation before writing
`graph.json` and building the bundle; failed CSV validation stops both later
steps.

Stage 15.5 does not load manifests, validate manifest paths, load runtimes,
compute Rg, compute contacts, run diagnostics, build diagnostics reports,
perform reference comparison, execute notebooks, call CLI/workflow execution,
add a local real MD smoke test, or add real-data CI. In short: no diagnostics,
no reference comparison, no CLI, and no notebook execution in Stage 15.5.

Stage 15.6 will orchestrate diagnostics + diagnostics report. Stage 15.5 does not run diagnostics. Reference comparison remains Stage 15.7 optional mode,
disabled by default. Temporal RIN remains future scope. WANIA frontend
adapter/API payload remains future scope.

Import/default CI remains dependency-free for Stage 15.5. The wrapper consumes
already computed in-memory results and accepted dependency-free graph export
APIs. It does not require MDAnalysis, real `local_md` data, or real `.tpr` /
`.xtc` files in default CI. `local_md` remains local-only and not committed.

## CLI and frontend boundary

There is no CLI in Stage 15.1. Stage 15.8 will add the narrow opt-in CLI
boundary later. The CLI boundary later belongs to Stage 15.8, not Stage 15.1.

WANIA frontend adapter/API payload remains future scope. Stage 15.1 does not
adapt graph export to the WANIA prototype and does not define frontend payload
contracts.
