# WANIA JSON assembly profile v0.1

## 1. Purpose

Stage 18 packages accepted MANIA/WANIA backend outputs into a demo-ready WANIA
JSON payload. The purpose of this assembly profile is to define how existing
MANIA artifacts are interpreted as inputs for building
`wania_graph_payload.json` without adding new science or changing the payload
schema.

Stage 18.1 defines the profile. Stage 18.2 validates artifact-to-payload
mapping. Stage 18.3 provides the reproducible demo export flow.

## 2. Assembly scenario

The intended conceptual chain is:

```text
MANIA preprocessing output directory
-> graph artifacts
-> optional scientific artifacts
-> optional analysis artifacts
-> WANIA adapter/writer
-> wania_graph_payload.json
-> Stage 17 contract checks
```

The demo scenario is deliberately small: open `wania_graph_payload.json` and
show its frontend-facing payload shape. Understanding the graph must not
require FastAPI, frontend implementation, notebook execution, or reading all
CSV files. The JSON graph is assembled from the accepted backend graph
artifact; CSVs remain separately referenced enrichment.

## 3. Required assembly inputs

The minimal required artifact is:

```text
graph/graph.json
```

This reflects the current accepted adapter behavior: `graph_json_path` is the
only required artifact path. The graph JSON supplies the source node and edge
records mapped to `graph.nodes` and `graph.edges`. `graph/nodes.csv`,
`graph/edges.csv`, and `reports/graph_diagnostics_report.json` are not required
to build the basic payload.

Assembly also requires explicit run context rather than deriving identity from
local paths:

- `run_name`;
- `protein_id`;
- `protein_name`;
- `condition_names`;
- an output root used to express artifact references relative to the exported
  bundle.

These are assembly context, not additional scientific artifact files. The
Stage 17.2 required fields still govern the assembled values. In particular,
source graph records must map to the required residue identity, condition,
coordinates, endpoints, and interaction type. Stage 18.2 will validate that
mapping; Stage 18.1 does not add a validator.

## 4. Optional assembly inputs

The accepted optional artifact inputs are:

```text
graph/nodes.csv
graph/edges.csv
rg/rg_timeseries.csv
contacts/contact_edges.csv
contacts/contacts_perframe.csv
analysis/metrics_<condition>.csv
analysis/communities_<condition>.csv
analysis/analysis_metrics_report.json
reports/graph_diagnostics_report.json
```

When present, these files may enrich capabilities, diagnostics, optional
annotations, or artifact references. Their absence must not invalidate a
basic demo-ready MVP payload. Large CSV contents are referenced, not inlined.
Analysis metrics and communities remain optional scientific inputs rather
than prerequisites for understanding or rendering the graph.

## 5. Demo-ready output

The expected output file is:

```text
wania_graph_payload.json
```

It must be valid JSON, JSON-safe, portable, frontend-facing, Stage 17
MVP-compatible, and safe to open on a demo call. Its expected content is:

- `schema_version`;
- `run` metadata, including `condition_names`;
- `capabilities`;
- `graph.nodes` and `graph.edges`;
- node `x/y/z` coordinates;
- edge `interaction.primary_type`;
- an `artifacts` object;
- a `diagnostics` object.

Optional content may include `x_ca/y_ca/z_ca`,
`interaction.all_types`, contact frequency, distance summaries, `backbone`,
`aromatic_pi`, `cation_pi`, analysis metrics, communities, scientific artifact
references, analysis artifact references, and extended diagnostics.

## 6. Relationship to Stage 17 contracts

Every demo-ready assembled payload follows all three accepted Stage 17
contracts:

- [Stage 17.1](wania_mvp_contract_v0_1.md) defines the WANIA MVP profile;
- [Stage 17.2](wania_required_fields_contract_v0_1.md) defines its required
  fields;
- [Stage 17.3](wania_science_ui_boundary_v0_1.md) separates stable UI fields,
  optional science, backend-only details, and future capabilities.

Demo-ready does not mean every optional scientific feature is present.
Demo-ready means the payload satisfies the MVP required fields and does not
leak backend-only details.

The Stage 16.12 rich sample demonstrates a rich payload. The Stage 17.2
minimal fixture defines the required skeleton. A Stage 18 demo payload is an
assembled payload that must satisfy the Stage 17 contract; it is neither the
rich sample nor the minimal fixture by definition.

## 7. Required MVP payload expectations

The assembled demo payload must include the Stage 17.2 required fields.

| Area | Required fields |
|---|---|
| Top level | `schema_version`, `run`, `capabilities`, `graph`, `artifacts`, `diagnostics` |
| Run | `run_name`, `protein_id`, `protein_name`, `condition_names` |
| Graph | `graph.nodes`, `graph.edges` |
| Node | `id`, `condition`, `residue.index`, `residue.name`, `x`, `y`, `z` |
| Edge | `id`, `source`, `target`, `condition`, `interaction.primary_type` |
| Diagnostics | `passed` |

`artifacts` is a stable object and may be empty. Nodes and edges follow the
empty-state rules in the Stage 17.2 contract. Capabilities are availability
signals and do not make optional blocks required.

## 8. Optional scientific payload expectations

Optional scientific fields are progressive enhancements. Their absence must
not invalidate the demo-ready MVP payload.

Examples include:

- `x_ca/y_ca/z_ca`;
- `backbone`, `aromatic_pi`, and `cation_pi` interaction type values;
- `interaction.all_types`, backend `all_edge_types`, and backend
  `n_edge_types`;
- contact frequency and distance summaries;
- analysis metrics and communities;
- Rg artifact references, contact artifact references, per-frame artifact
  references, and analysis artifact references;
- extended diagnostics.

Presence of one optional artifact or annotation must not silently promote
other optional science into a required frontend field. Unsupported features
remain future capabilities and must be represented honestly.

## 9. Backend-only leakage rules

The assembled payload must not expose computational implementation details as
frontend contract. Backend-only examples include:

- `InteractionAccumulator` internals;
- atom cache internals;
- contact engine internals and chemistry helper internals;
- MDAnalysis runtime objects, including `AtomGroup` and `ResidueGroup`;
- frame iteration internals and distance evaluation counters;
- graph library internals;
- notebook cell mechanics and notebook execution paths;
- `local_md`, `local_md_protein`, and `mania_output` paths;
- raw trajectory paths, temporary output directories, and absolute local
  paths.

Backend-only details may exist in backend code, diagnostics internals, debug
logs, or audit docs, but they must not be required frontend payload fields.

## 10. Artifact reference rules

Artifact references in a demo-ready payload must use relative paths. They must
be portable, safe to display, and safe to resolve within the exported artifact
bundle. They must not be absolute paths, traverse with `..`, or point to
`local_md`, `local_md_protein`, `mania_output`, raw trajectory paths, or
temporary local directories.

Committed demo payload references must not use raw MD extensions:

```text
.tpr
.xtc
.gro
.cpt
.edr
.dcd
.psf
```

Large CSVs are referenced, not inlined. The assembly output may name accepted
scientific and analysis artifacts inside its bundle, but a reference is not a
promise that its rows are required frontend state.

## 11. Diagnostics expectations

A demo-ready payload includes `diagnostics.passed` for frontend/status
display. Under the Stage 17.2 contract its value may be `true`, `false`, or
`null` when no backend report status is available.

`diagnostics.issues` is stable when present and remains optional under the
accepted payload behavior, except for the Stage 17.2 empty-graph explanation
rule. Extended diagnostic details are optional. They must not expose
backend-only internals as required frontend fields.

## 12. Demo-readiness checklist

A demo-ready `wania_graph_payload.json` satisfies all of the following:

- [ ] It is valid, JSON-safe JSON.
- [ ] It includes every Stage 17.2 required field.
- [ ] It has `graph.nodes` and `graph.edges` arrays.
- [ ] Renderable nodes have `x/y/z`.
- [ ] Edges have `interaction.primary_type`.
- [ ] Artifact references use relative paths and are portable.
- [ ] Diagnostics provide pass/fail status through `diagnostics.passed`.
- [ ] Optional science is allowed but not required.
- [ ] Backend-only internals are absent from the frontend contract.
- [ ] No absolute paths, raw trajectory paths, or local/generated paths are
  present.
- [ ] No notebook execution is required.
- [ ] No FastAPI or frontend implementation is required.

## 13. Relationship to Stage 18.2 and Stage 18.3

Stage 18.1 defines the WANIA JSON assembly profile. Stage 18.2 validates
graph/artifact-to-WANIA MVP mapping using synthetic fixtures and the existing
WANIA adapter/writer. Stage 18.3 will provide the reproducible demo export
command or short command sequence.

The Stage 18.1 profile itself does not implement Stage 18.2 mapping validation
or the Stage 18.3 export flow.

## 14. Non-goals

Stage 18.1 is documentation/tests only. It does not implement new contact
chemistry, new interaction types, new graph metrics, new analysis algorithms,
backbone or `EDGE_PRIORITY` changes, `InteractionAccumulator` changes, atom
cache changes, temporal RIN, a full typed RIN, formal statistics,
conformational clustering, FastAPI, an upload/job API, database models,
background workers, frontend implementation, a notebook execution pipeline,
a runtime validator, a CLI command, new dependencies, real-data CI, or
committed local/generated outputs.

It adds no runtime assembly workflow, payload fields, fixtures, scientific
behavior, adapter behavior, or generated demo JSON. Stage 18.1 is not FastAPI,
not frontend implementation, and not notebook execution.
