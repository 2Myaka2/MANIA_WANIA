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

## CLI and frontend boundary

There is no CLI in Stage 15.1. Stage 15.8 will add the narrow opt-in CLI
boundary later. The CLI boundary later belongs to Stage 15.8, not Stage 15.1.

WANIA frontend adapter/API payload remains future scope. Stage 15.1 does not
adapt graph export to the WANIA prototype and does not define frontend payload
contracts.
