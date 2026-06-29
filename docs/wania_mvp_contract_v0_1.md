# WANIA MVP contract v0.1

## 1. Purpose

The WANIA MVP profile is the stable frontend-facing subset of the WANIA object
JSON payload. It is not the full backend graph export, the full scientific
analysis layer, or notebook parity output. It is not a FastAPI/upload/job API
contract.

The profile gives an initial frontend a stable basis to load a payload, read
run and context information, read capabilities, render graph nodes and edges,
display basic diagnostics, show artifact links, and ignore missing optional
science fields.

Stage 17.1 freezes this documented profile. It is not schema redesign and does
not add runtime validation. Stage 17.2 freezes the exact required subset in
[`wania_required_fields_contract_v0_1.md`](wania_required_fields_contract_v0_1.md),
with contract tests and a minimal valid payload fixture.
Stage 17.3 defines the science-vs-UI ownership boundary in
[`wania_science_ui_boundary_v0_1.md`](wania_science_ui_boundary_v0_1.md).

## 2. Layer separation

WANIA data has three distinct layers:

1. **Backend scientific artifacts.** `graph/graph.json`, scientific CSVs,
   analysis outputs, and diagnostic reports may contain the full accepted
   graph, contact, or analysis detail.
2. **WANIA object JSON payload.** The adapter maps accepted backend artifacts
   into object JSON and may preserve or reference more scientific information
   than an initial frontend needs.
3. **WANIA frontend MVP profile.** This contract defines only what frontend
   code can safely rely on for initial graph rendering and basic context.

Backend artifacts may therefore contain more data than the MVP requires, and
the WANIA object JSON payload may carry optional scientific fields. The
frontend MVP must not depend on backend internals.

## 3. MVP required top-level blocks

The documented MVP profile has these required top-level blocks:

- `schema_version`;
- `run`;
- `capabilities`;
- `graph`;
- `artifacts`;
- `diagnostics`.

The existing payload can also contain `temporal`, but it is not required by
the frontend MVP profile. Stage 17.1 documents the profile; it does not
redesign the runtime schema or introduce strict validation code. The Stage
17.2 required-fields contract provides the exact field-level rules without a
runtime validator.

## 4. MVP graph requirements

The `graph` block contains `graph.nodes` and `graph.edges` arrays. Nodes are
residues or entities that the frontend can render. Edges are relationships or
interactions that the frontend can render.

Stage 17.1 adds no edge types, changes no graph export behavior, and changes no
WANIA adapter behavior.

## 5. MVP node expectations

An MVP node has:

- `id`, a stable node identifier within the payload;
- `condition`, identifying the run condition;
- a residue/display identity, expressed by `label` and/or the accepted
  `residue.index`, `residue.id`, and `residue.name` fields.

The accepted payload also supports coordinates:

- `x/y/z` are frontend-facing render coordinates for coordinate-based graph
  rendering;
- `x_ca/y_ca/z_ca` are optional explicit Cα scientific coordinate fields.

Stage 17.2 selects the coordinate-based WANIA MVP v0.1 render profile:
renderable nodes require `x/y/z`. This selection does not change the runtime
schema, and it does not remove `x_ca/y_ca/z_ca` from the Stage 16.12 sample.

## 6. MVP edge expectations

An MVP edge has:

- `id`;
- `source` and `target` node identifiers;
- `condition`;
- `interaction.primary_type`, the canonical primary edge type in the accepted
  WANIA schema.

The term `edge_type` is useful as a concept and remains a backend artifact
field, but this profile does not introduce a parallel `edge_type` field in the
WANIA object JSON payload. Optional edge enrichment includes
`interaction.all_types` (the WANIA form of backend `all_edge_types`), backend
`n_edge_types`, `metrics.contact_frequency`, distance summaries, and other
interaction details.

Basic MVP rendering does not require `all_types`, `all_edge_types`,
`n_edge_types`, contact frequency, distance statistics, `backbone`,
`aromatic_pi`, `cation_pi`, analysis metrics, communities, or per-frame
contacts.

## 7. Capabilities semantics

Capabilities are availability signals, not universal required-field
declarations:

- `false` means the frontend must not expect or require that feature;
- `true` means the frontend may use the feature when the corresponding data is
  present;
- a true capability does not make its corresponding optional block required
  for basic MVP graph rendering unless the required table below explicitly
  says so.

The current `static_contact_graph` flag advertises the MVP-facing static graph.
Current optional availability flags are `rg_timeseries`, `aggregate_contacts`,
`contacts_perframe`, `centrality_metrics`, and `community_detection`.
`artifacts` and `diagnostics` are required MVP blocks rather than separate
capability names, and the current schema has no dedicated coordinate
capability; coordinate availability is determined from node `x/y/z` values.

The flags `typed_rin_interactions`, `node_structural_metrics`,
`conformational_states`, `cross_condition_statistics`, `temporal_rin`,
`inter_component_interactions`, and `cross_protein_comparison` must remain
honest. Unsupported or future features remain false. Full typed RIN,
temporal interactions/temporal RIN, formal analysis statistics,
conformational clustering, and cross-protein comparison are not MVP
requirements.

## 8. Required / optional / backend-only / future classification

| Block / field | MVP status | Meaning | Notes |
|---|---|---|---|
| `schema_version` | required | Payload contract version | Does not version backend files. |
| `run` metadata | required | Protein, run, and condition context | Frontend-facing context. |
| `capabilities` | required | Optional-feature availability signals | A true value does not expand the required MVP by itself. |
| `graph.nodes` | required | Renderable residues/entities | May be empty for an empty graph. |
| `graph.edges` | required | Renderable relationships/interactions | May be empty for an edgeless graph. |
| node `id` | required | Node identity | Edge endpoints refer to node ids. |
| node `condition` | required | Condition identity | Belongs to the run context. |
| node `residue.index` and `residue.name` | required | Residue/display identity | Exact Stage 17.2 minimal identity fields. |
| node `x/y/z` | required | Frontend-facing coordinates | Required by the Stage 17.2 coordinate-based render profile. |
| node `x_ca/y_ca/z_ca` | optional | Explicit scientific Cα coordinates | Not required for MVP rendering. |
| edge `id` | required | Edge identity | Stable within the payload. |
| edge `source` / `target` | required | Node references | Refer to node ids. |
| edge `condition` | required | Condition identity | Belongs to the run context. |
| edge `interaction.primary_type` | required | Canonical primary display interaction | This is the WANIA field for the conceptual primary `edge_type`. |
| `artifacts` | required | Artifact-reference section | Individual Rg, contact, diagnostic, and analysis references are optional. |
| `diagnostics` | required | Basic status/summary section | Current payloads use `passed` and may provide `report_path`. |
| `interaction.all_types` / backend `all_edge_types` | optional | All types associated with an edge | Progressive scientific enrichment. |
| backend `n_edge_types` | optional | Number of edge types | Not needed for basic rendering. |
| `contact_frequency` and distance summaries | optional | Aggregate interaction measurements | Not needed for basic rendering. |
| `backbone` | optional | Accepted interaction type value | Its absence does not block rendering. |
| `aromatic_pi` / `cation_pi` | optional | Accepted scientific interaction type values | Their absence does not block rendering. |
| analysis metrics and communities | optional | Separate scientific/analysis layer | Analysis artifacts are not required for graph render. |
| Rg/contact CSV references | optional | References to scientific/backend artifacts | Large rows are not inlined. |
| analysis artifact references | optional | References to metrics/community outputs | The `artifacts.analysis` entry is enrichment. |
| per-frame contacts | backend-only | Scientific temporal observations | An optional artifact reference may advertise them; rows are not MVP graph data. |
| `InteractionAccumulator` internals | backend-only | Contact aggregation implementation | Never a frontend dependency. |
| atom cache / `build_atom_cache` internals | backend-only | Contact performance implementation | Never a frontend dependency. |
| raw trajectory paths | backend-only | Local scientific inputs | Forbidden in frontend samples. |
| absolute or local generated-output paths | backend-only | Machine-local implementation details | Forbidden in frontend samples; safe artifact references are relative. |
| full typed RIN schema | future | Rich typed-interaction model | Not frozen by this profile. |
| temporal RIN | future | Windowed/temporal graph analysis | Per-frame contacts do not imply it. |
| formal statistics | future | Cross-condition statistical analysis | Not an MVP panel requirement. |
| conformational clustering | future | Conformational-state analysis | Not implemented by this profile. |
| cross-protein comparison | future | Comparison requiring explicit mapping | Not implied by conditions in one run. |

## 9. Frontend MVP behavior

The frontend MVP should:

- render a graph from `graph.nodes` and `graph.edges`;
- use `x/y/z` for coordinate-based rendering when the values are available or
  required by a later chosen frontend profile;
- display `interaction.primary_type` as the primary edge type;
- tolerate missing optional scientific fields;
- use capabilities to decide whether optional panels should be shown;
- treat advanced science fields as progressive enhancement;
- display basic diagnostics and safe artifact references;
- require neither raw local paths nor generated local outputs;
- require neither analysis artifacts nor `backbone`, `aromatic_pi`, or
  `cation_pi` for a basic graph render.

## 10. Relationship to Stage 16.12 frontend sample

The Stage 16.12 fixture at
`tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json` is a rich,
compact frontend-ready example. It demonstrates accepted backend capabilities,
including coordinates, `backbone`, `aromatic_pi`, `cation_pi`, diagnostics
references, and analysis artifact references.

It is a rich illustrative payload, not the minimal required MVP payload. Not
every optional scientific field present in the sample is required for MVP
rendering, and the sample is not a strict minimal payload fixture. The exact
minimal fixture and superset rule are defined by the
[`Stage 17.2 required-fields contract`](wania_required_fields_contract_v0_1.md).

## 11. Non-goals

Stage 17.1 is not schema redesign, strict validator implementation, a minimal
payload fixture stage, a FastAPI contract, an upload/job API, a database model,
a background worker, or frontend implementation. It adds no graph algorithm,
scientific metric, chemistry detection, temporal RIN, full typed RIN schema,
formal statistics, conformational clustering, notebook execution, or real-MD
CI behavior. In short, Stage 17.1 is not FastAPI and is not an upload/job API.
It is not upload/job API work.

## 12. Stage 17 roadmap

- **Stage 17.1:** freeze and document the WANIA MVP frontend profile.
- **Stage 17.2:** freeze the required-fields contract and add its minimal valid
  payload fixture and tests.
- **Stage 17.3:** harden the science vs UI boundary and backend-only leakage
  rules, as defined by the
  [`Science vs UI boundary`](wania_science_ui_boundary_v0_1.md).
