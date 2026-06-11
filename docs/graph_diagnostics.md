# Graph diagnostics layer

## Purpose

The graph diagnostics layer validates backend contract graph artifacts after
export. It is designed to work on generated MANIA/WANIA contract output,
especially per-condition folders containing:

- `nodes.csv`
- `edges.csv`

The layer is currently lightweight and pure Python. It reads existing contract
artifacts and produces deterministic diagnostic reports.

## Scope

The layer checks:

- graph structure loaded from contract CSV files;
- graph QC, including connected components, isolated nodes, self-loops, and
  duplicate undirected edge keys;
- topology-derived degree and strength;
- consistency between exported node metrics and edge-derived topology;
- condition-level and multi-condition diagnostics;
- compact cross-condition summary reports.

## Non-goals

This layer does not:

- run MDAnalysis;
- call GROMACS;
- compute scientific centralities such as betweenness, closeness, eigenvector,
  or PageRank;
- compute Louvain or other community detection;
- compute temporal RIN;
- interpret biological meaning;
- mutate source output;
- run automatically in the pipeline or CLI yet.

## Input contract

For each condition, diagnostics expect:

```text
{output_root}/{condition}/nodes.csv
{output_root}/{condition}/edges.csv
```

When conditions are inferred rather than passed explicitly, diagnostics also
expect root-level run metadata:

```text
{output_root}/run_meta.json
```

`run_meta.json` must contain a top-level `conditions` list. A minimal example
is:

```json
{
  "conditions": ["normal", "tumor"]
}
```

## Main public entrypoints

- `load_contract_graph_from_condition_dir(...)`: load one condition graph from
  `{condition}/nodes.csv` and `{condition}/edges.csv`.
- `compute_graph_qc(...)`: compute basic structural QC for a loaded contract
  graph.
- `compute_graph_topology_metrics(...)`: compute degree and strength from graph
  edges.
- `check_graph_topology_consistency(...)`: compare exported node degree and
  strength columns with computed topology metrics.
- `run_condition_graph_diagnostics(...)`: run loading, QC, topology metrics,
  and topology consistency for one condition.
- `run_multi_condition_graph_diagnostics(...)`: run condition diagnostics for a
  provided ordered condition list.
- `run_output_graph_diagnostics(...)`: run multi-condition diagnostics using
  explicit conditions or conditions inferred from `run_meta.json`.
- `run_and_write_output_graph_diagnostics(...)`: run diagnostics and write the
  detailed diagnostics bundle only.
- `run_and_write_output_graph_diagnostics_report_bundle(...)`: run diagnostics,
  write the detailed bundle, build a summary, and write the summary JSON.
- `summarize_multi_condition_graph_diagnostics(...)`: build a compact
  cross-condition summary from existing diagnostics.

## Diagnostics outputs

The full report bundle writes:

```text
multi_condition_graph_diagnostics.json
multi_condition_graph_diagnostics_summary.json
{condition}/graph_diagnostics.json
{condition}/graph_qc.json
{condition}/graph_topology_metrics.json
{condition}/graph_topology_consistency.json
```

The detailed diagnostics bundle contains full machine-readable reports for the
multi-condition run and each condition. The summary is a compact
cross-condition overview with counts and pass/fail status.

## Pass/fail meaning

- `passed_basic_qc`: true when basic graph QC found no isolated nodes,
  self-loops, or duplicate undirected edge keys.
- `passed_topology_consistency`: true when exported node degree and strength
  match edge-derived topology within tolerance.
- `passed`: true only when both basic QC and topology consistency pass.
- `passed_conditions`: condition names with passing diagnostics, preserving
  condition order.
- `failed_conditions`: condition names with failing diagnostics, preserving
  condition order.

Normal diagnostic failures are report values, not exceptions. Examples include:

- isolated nodes;
- self-loops;
- duplicate undirected edge keys;
- degree or strength mismatch.

Fatal malformed input is an exception. Examples include:

- missing `nodes.csv`;
- missing `edges.csv`;
- invalid `run_meta.json`;
- invalid numeric edge weight;
- missing requested metric column.

## Degree and strength consistency

Computed degree comes from unique graph neighbors. Computed strength comes from
summing edge weights, using `contact_freq` by default.

Duplicate edge rows contribute to strength because they are edge rows with
weights, but they do not increase degree beyond the unique neighbor. A self-loop
contributes its weight to strength once.

Topology consistency compares these computed values with exported node columns.
The default exported columns are `degree` and `strength`.

## Current tiny fixture note

The tiny expected fixtures currently have strength consistency mismatches. This
is intentional and covered by tests.

For those fixtures, graph QC still passes, but full diagnostics fail because
topology consistency fails. Fixture files should not be silently modified only
to make diagnostics pass.

## Example usage

```python
from mania.analysis.graph_diagnostics import (
    run_and_write_output_graph_diagnostics_report_bundle,
)

result = run_and_write_output_graph_diagnostics_report_bundle(
    output_root="path/to/output",
    diagnostics_output_dir="path/to/diagnostics",
)

print(result.passed)
print(result.summary.failed_conditions)
```

With explicit conditions:

```python
result = run_and_write_output_graph_diagnostics_report_bundle(
    output_root="path/to/output",
    diagnostics_output_dir="path/to/diagnostics",
    conditions=("normal", "tumor"),
)
```

## Future integration

Stage 7 will connect these functions to the controlled backend workflow through
configuration, pipeline wrappers, and possibly CLI commands. At present, this
layer is only callable from Python and does not run automatically.
