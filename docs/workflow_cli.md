# Workflow CLI and config usage

## Purpose

This workflow runs a controlled lightweight path:

```text
notebook export artifacts
        ↓
backend MANIA/WANIA contract subset
        ↓
graph diagnostics report bundle
```

It is intended for Stage 7 backend workflow integration. It does not run
MDAnalysis or GROMACS, and it does not replace the full future MANIA
production pipeline.

## What the workflow currently does

The workflow can:

- export supported notebook-derived artifacts into the backend contract layout;
- write root-level `run_meta.json`;
- write per-condition contract files;
- run graph diagnostics on the exported contract graph artifacts;
- write detailed graph diagnostics reports;
- write a compact diagnostics summary.

## What the workflow does not do yet

The workflow does not:

- run molecular dynamics preprocessing;
- call GROMACS;
- run MDAnalysis;
- compute new scientific centrality metrics;
- compute Louvain or other community detection;
- compute temporal RIN;
- perform biological interpretation;
- replace the full future production pipeline.

## Config file formats

Workflow config files can be written as:

- JSON;
- YAML.

The file maps directly to the workflow config model.

## Minimal JSON config example

```json
{
  "source_dir": "tests/fixtures/notebook_export_v1_1_tiny",
  "output_dir": "tmp/mania_output",
  "diagnostics_output_dir": "tmp/mania_diagnostics",
  "frame_time_ps": 100.0
}
```

When `conditions` is omitted, the adapter and workflow can infer conditions
from available metadata and generated output.

## Full YAML config example

```yaml
source_dir: tests/fixtures/notebook_export_v1_1_tiny
output_dir: tmp/mania_output
diagnostics_output_dir: tmp/mania_diagnostics
conditions:
  - normal
  - tumor
frame_time_ps: 100.0
abs_tol: 1.0e-6
weight_column: contact_freq
degree_column: degree
strength_column: strength
```

## Config fields

- `source_dir`: directory containing notebook-like export files.
- `output_dir`: directory where backend contract files are written.
- `diagnostics_output_dir`: directory where graph diagnostics reports are
  written.
- `conditions`: optional condition names to export and diagnose. If omitted or
  `null`, conditions are inferred.
- `frame_time_ps`: frame spacing used when exporting Rg time series.
- `abs_tol`: absolute tolerance for graph topology consistency checks.
- `weight_column`: edge column used as graph edge weight.
- `degree_column`: node column containing exported degree values.
- `strength_column`: node column containing exported strength values.

Defaults:

- `conditions`: `null`
- `abs_tol`: `1e-6`
- `weight_column`: `contact_freq`
- `degree_column`: `degree`
- `strength_column`: `strength`

Validation:

- `frame_time_ps` must be positive and finite.
- `abs_tol` must be finite and non-negative.
- condition names are stripped and deduplicated.
- column names must be non-empty strings.

## Running from CLI

```bash
mania workflow run --config workflow.yaml
```

The Python module form is also supported:

```bash
python -m mania workflow run --config workflow.yaml
```

## CLI JSON output

On success, the CLI prints a compact JSON summary:

```json
{
  "workflow": "notebook_export_graph_diagnostics",
  "conditions": ["normal", "tumor"],
  "passed": false,
  "export_output_dir": "tmp/mania_output",
  "diagnostics_output_dir": "tmp/mania_diagnostics",
  "diagnostics_summary_path": "tmp/mania_diagnostics/multi_condition_graph_diagnostics_summary.json",
  "export_written_paths_count": 13,
  "diagnostics_written_paths_count": 10
}
```

Counts may differ when fewer or more conditions are selected.

## Exit code behavior

Default behavior:

```bash
mania workflow run --config workflow.yaml
```

- exits `0` when workflow execution succeeds;
- this includes cases where diagnostics have `"passed": false`.

CI-like strict behavior:

```bash
mania workflow run --config workflow.yaml --fail-on-diagnostics-failure
```

- exits `0` if workflow execution succeeds and diagnostics pass;
- exits `2` if workflow execution succeeds but diagnostics have
  `"passed": false`;
- still exits non-zero for fatal errors such as invalid config, export failure,
  or fatal diagnostics errors.

## Understanding passed=false

`"passed": false` does not necessarily mean export crashed. It means the
workflow ran and graph diagnostics found report-level issues.

Examples include:

- strength mismatch;
- degree mismatch;
- isolated nodes;
- self-loops;
- duplicate undirected edge keys.

The current tiny fixture intentionally produces `"passed": false` because
exported node strength differs from edge-derived `contact_freq`. This behavior
is documented and tested.

## Output files

Backend output files:

```text
{output_dir}/run_meta.json
{output_dir}/{condition}/rg_timeseries.csv
{output_dir}/{condition}/centrality.csv
{output_dir}/{condition}/communities.csv
{output_dir}/{condition}/nodes.csv
{output_dir}/{condition}/edges.csv
{output_dir}/{condition}/graph.json
```

Diagnostics output files:

```text
{diagnostics_output_dir}/multi_condition_graph_diagnostics.json
{diagnostics_output_dir}/multi_condition_graph_diagnostics_summary.json
{diagnostics_output_dir}/{condition}/graph_diagnostics.json
{diagnostics_output_dir}/{condition}/graph_qc.json
{diagnostics_output_dir}/{condition}/graph_topology_metrics.json
{diagnostics_output_dir}/{condition}/graph_topology_consistency.json
```

## Python API equivalent

```python
from mania.pipeline_steps import (
    load_notebook_export_graph_diagnostics_workflow_config,
    run_notebook_export_graph_diagnostics_pipeline_from_config,
)

config = load_notebook_export_graph_diagnostics_workflow_config("workflow.yaml")
result = run_notebook_export_graph_diagnostics_pipeline_from_config(config)

print(result.conditions)
print(result.passed)
```

Config-file runner:

```python
from mania.pipeline_steps import (
    run_notebook_export_graph_diagnostics_pipeline_from_config_file,
)

result = run_notebook_export_graph_diagnostics_pipeline_from_config_file(
    "workflow.yaml"
)
```

## Future work

Later stages may add:

- broader pipeline runner;
- more CLI commands;
- real scientific preprocessing integration;
- heavier scientific dependencies only when intentionally introduced.

These future items are not implemented by the current workflow.
