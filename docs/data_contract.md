# MANIA Data Contract v0.1

## Purpose

- This document defines MANIA v0.1 output artifacts consumed by WANIA.
- It is a contract, not an implementation document.
- The listed artifacts and columns may not all be implemented yet.

## Output Layout

```text
mania_output/
├── run_meta.json
├── normal/
│   ├── nodes.csv
│   ├── edges.csv
│   ├── graph.json
│   ├── centrality.csv
│   ├── communities.csv
│   ├── temporal_rin.csv
│   ├── rg_timeseries.csv
│   ├── conformational_states.csv
│   └── contacts_perframe.parquet
├── tumor/
│   └── same per-condition artifacts
├── comparison.csv
└── stats.csv
```

- `comparison.csv` and `stats.csv` are cross-condition artifacts.
- `comparison.csv` and `stats.csv` are not inside `normal/` or `tumor/`.
- Single-condition runs may omit `comparison.csv` and `stats.csv` or mark them
  unavailable later.

## Per-Condition Artifacts

### nodes.csv

Per-residue node table for one condition.

Required columns:

```text
resid
resname
region
condition
x_ca
y_ca
z_ca
tm_relative_z
rmsf_A
sasa_A2
ss
degree
strength
betweenness
closeness
eigenvector
pagerank
kcore
community_id
```

### edges.csv

Per-edge contact and edge-dynamics table for one condition.

Required columns:

```text
resid_i
resid_j
edge_type
condition
contact_freq
mean_dist_A
std_dist_A
n_episodes
mean_lifetime_frames
max_lifetime_frames
mean_lifetime_ns
max_lifetime_ns
formation_count
breakage_count
first_seen_frame
last_seen_frame
window_cv
```

### centrality.csv

Per-residue centrality metrics for one condition.

Required columns:

```text
resid
condition
degree
strength
betweenness
closeness
eigenvector
pagerank
kcore
```

### communities.csv

Per-residue community assignments for one condition.

Required columns:

```text
resid
condition
community_id
community_size
algorithm
```

### temporal_rin.csv

Window-level temporal RIN summary for one condition.

Required columns:

```text
window_id
time_start_ps
time_end_ps
condition
n_edges
n_nodes_active
density
window_cv
```

### rg_timeseries.csv

Per-frame radius of gyration time series for one condition.

Required columns:

```text
frame
time_ps
rg_A
condition
```

Notebook v1.1 reference files are named
`rg_timeseries_{condition}.csv`. The backend contract stores the same
information as `{condition}/rg_timeseries.csv`. The backend contract requires
`time_ps` for consistency with other time-series artifacts. Adapter logic will
handle filename/layout conversion later. Deriving or calculating `time_ps` is
outside this task.

### conformational_states.csv

Per-frame conformational state assignments for one condition.

Required columns:

```text
frame
time_ps
condition
state_id
cluster_label
rg_A
rmsd_A
```

### contacts_perframe.parquet

Per-frame contact table for one condition.

Required columns:

```text
frame
time_ps
resid_i
resid_j
edge_type
dist_A
condition
```

## graph.json

`graph.json` is the per-condition graph representation.

Required keys:

```text
condition
n_nodes
n_edges
directed
schema_version
nodes
edges
```

Example shape:

```json
{
  "condition": "normal",
  "n_nodes": 690,
  "n_edges": 1234,
  "directed": false,
  "schema_version": "0.1",
  "nodes": [],
  "edges": []
}
```

## Cross-Condition Artifacts

### comparison.csv

Cross-condition comparison table. This file is not stored inside a condition
directory.

Required columns:

```text
resid_or_edge_id
metric
normal_value
tumor_value
delta
statistic
p_value
q_value
effect_size
condition_specificity
```

### stats.csv

Cross-condition statistics table. This file is not stored inside a condition
directory.

Required columns:

```text
resid_or_edge_id
metric
test
statistic
p_value
q_value
effect_size
significant
```

## MVP Exclusions

- `allosteric_paths.json` is optional and outside MVP v0.1.
- Energy analysis is not implemented.
- ESM-2 is not implemented.
- FastAPI is not implemented.
- No deletion/insertion support in v0.1.
