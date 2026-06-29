# WANIA Science vs UI boundary v0.1

## 1. Purpose

The purpose of this document is to prevent backend scientific implementation
details from becoming accidental frontend contract. The WANIA payload can
contain both display fields and scientific annotations, but the frontend must
rely on the stable display model rather than computational internals.

The frontend display model contains simple identities, coordinates,
relationships, status, and portable references. The backend/science
computational model contains the algorithms, runtime objects, intermediate
state, and local workflow details used to produce those values. The WANIA
payload is the bridge between the two models; it does not require the frontend
to understand molecular-dynamics implementation details.

Scientific annotations enhance UI, but do not define the minimal UI. Backend
internals must not leak into frontend contract. Future capabilities must
remain behind capabilities and documentation until explicitly accepted.

## 2. Layer model

Stage 17.3 classifies contract concepts into four layers:

1. **UI-facing fields.** Stable display-model fields used directly by the
   frontend for basic graph rendering, context, links, and status display.
2. **Optional scientific annotations.** Scientific values that can improve
   the UI when present, but are not required for MVP validity or a basic graph
   render.
3. **Backend-only implementation details.** Computation, runtime, debug,
   notebook, reproducibility, and local-path details that are not frontend
   contract.
4. **Future capabilities.** Capabilities or schema areas that are deliberately
   deferred and must not yet be expected by the frontend.

These UI-facing fields, optional scientific annotations, backend-only details,
and future capabilities describe layer responsibility. They do not redefine
which fields are required. Stage 17.2 remains the authority for the required
WANIA MVP fields.

## 3. UI-facing fields

UI-facing fields are stable and understandable without knowledge of how
molecular contacts or graph analyses were computed.

The UI-facing top-level blocks are:

- `schema_version`;
- `run`, including `run.run_name`, `run.protein_id`, `run.protein_name`, and
  `run.condition_names`;
- `capabilities`;
- `graph`, including `graph.nodes` and `graph.edges`;
- `artifacts`;
- `diagnostics`.

The UI-facing node fields are:

- `node.id`;
- `node.condition`;
- `node.residue.index`;
- `node.residue.name`;
- `node.x`, `node.y`, and `node.z`.

`node.label` and `node.residue.chain_id` are optional but UI-usable when
present. They remain progressive enhancements rather than additions to the
Stage 17.2 required set.

The UI-facing edge fields are:

- `edge.id`;
- `edge.source`;
- `edge.target`;
- `edge.condition`;
- `edge.interaction.primary_type`.

The UI-facing diagnostics status is `diagnostics.passed`.
`diagnostics.issues` is UI-usable if present. The stable `artifacts` object is
UI-facing, and its accepted keys/categories and relative artifact references
may be used for links. Individual references remain optional.

UI-facing does not mean every field is always required. Required fields are
defined by Stage 17.2; Stage 17.3 classifies fields by layer responsibility.

## 4. Optional scientific annotations

Optional scientific annotations support progressive enhancement. Examples
include:

- `x_ca/y_ca/z_ca`, labels, and `node.residue.chain_id` when available;
- `interaction.all_types`, backend `all_edge_types`, and backend
  `n_edge_types`;
- `contact_frequency`, distance summaries, and distance statistics;
- `backbone`, `aromatic_pi`, and `cation_pi` as accepted interaction type
  values;
- `node.metrics`, including centrality metrics such as `degree`, `strength`,
  `betweenness`, `closeness`, `pagerank`, and `kcore`;
- `node.community` or equivalent accepted community annotations;
- Rg artifact references, contact artifact references,
  `contacts_perframe` artifact references, analysis artifact references, and
  extended diagnostics.

Optional scientific annotations must not be required for MVP validity. They
must not be required for basic graph rendering. A frontend may show them only
when they are present and supported by the accepted capabilities and
documentation.

The stable payload may therefore be useful at two levels: its required display
model always supports the MVP, while optional scientific annotations can add
tooltips, filters, overlays, or analysis panels without changing the minimum
rendering contract.

## 5. Backend-only implementation details

The following are backend-only and must never become frontend dependencies:

- `InteractionAccumulator` internals and atom cache internals;
- contact engine internals and chemistry helper internals;
- the `aromatic_pi geometry algorithm` and `cation_pi geometry algorithm`,
  including SVD/best-fit-plane ring normal implementation, centroid cutoff
  implementation details, and angle threshold implementation details;
- raw `AtomGroup` selection details and `MDAnalysis` runtime objects;
- frame iteration internals, distance evaluation counters, contact safety
  limit internals, and raw per-frame computation details;
- `NetworkX` or greedy-modularity implementation details, community fallback
  internals, and strength fallback internals;
- notebook cell or step mechanics and notebook parity implementation details;
- `local_md`, `local_md_protein`, and `mania_output` paths;
- raw trajectory paths, temporary output directories, absolute paths, and
  other local or generated paths.

These concepts may appear in implementation docs, audit docs, debug logs, or
scientific reports. They must not become required frontend fields and must not
be used by the frontend to decide basic rendering behavior. Raw, local, and
generated paths are backend-only and forbidden in the frontend contract;
portable artifact references follow the rules in Section 9.

## 6. Future capabilities

The following remain future or deferred:

- temporal RIN and interactive temporal playback;
- full typed RIN schema (also described as the typed RIN full schema);
- formal statistics;
- conformational clustering, including PCA/k-means/silhouette;
- cross-protein comparison and multi-protein alignment/comparison;
- production FastAPI/upload/job API;
- a database-backed job model and background workers;
- frontend implementation.

Future capabilities may be represented as false or may be absent in
`capabilities`. The frontend must not expect their data blocks until a future
contract version explicitly accepts them.

## 7. Interaction type vs chemistry implementation

The frontend may consume values such as:

```text
edge.interaction.primary_type = backbone
edge.interaction.primary_type = aromatic_pi
edge.interaction.primary_type = cation_pi
```

It must not depend on the aromatic π ring-normal algorithm, SVD or
best-fit-plane implementation, parallel or T-shaped angle thresholds, centroid
cutoffs, cation-center definitions, cation-to-ring centroid cutoffs, or atom
selection logic.

`primary_type` is a UI-facing/optional scientific annotation: the
`edge.interaction.primary_type` field is required and UI-facing, while
particular scientific chemistry values are optional annotations. The chemistry
detection algorithm is backend-only.

Changing backend chemistry implementation should not require frontend changes
as long as accepted interaction type names and the payload contract remain
stable.

## 8. Graph metrics vs analysis algorithm

The frontend may consume optional annotations such as
`node.metrics.degree`, `node.metrics.pagerank`, `node.metrics.kcore`, and
`node.community`. It may also offer portable artifact links such as:

```text
analysis/metrics_<condition>.csv
analysis/communities_<condition>.csv
analysis/analysis_metrics_report.json
```

The frontend must not depend on which algorithm computed a community, which
fallback was used, how null or non-finite values were handled internally, or
which graph library or dependency performed the computation.

Metrics/community values are optional scientific annotations.
Metric/community computation methods are backend-only analysis details.

## 9. Artifacts vs frontend state

The WANIA payload must be sufficient for basic graph rendering. Artifact
references extend it for download, audit, debug, reproducibility, or future
analysis panels. The frontend MVP must not read every artifact file to render
the graph, and large CSV contents must be referenced rather than inlined.

Artifact paths must be relative and portable. They must not point to
`local_md`, `local_md_protein`, `mania_output`, raw trajectories, or absolute
paths.

An artifact reference is a UI-facing or optional product-facing link. Artifact
file internals are backend/scientific unless an explicit future contract
promotes them to UI-facing data. Local artifact layout is backend-only.
Frontend state, such as selections, open panels, filters, and layout choices,
is not inferred from backend artifact layout.

## 10. Capabilities as product-level availability signals

Capabilities describe product-level feature availability, not backend
mechanisms. Current accepted names include `static_contact_graph`,
`rg_timeseries`, `aggregate_contacts`, `contacts_perframe`,
`centrality_metrics`, and `community_detection`. Future or unsupported accepted
signals include `typed_rin_interactions`, `node_structural_metrics`,
`conformational_states`, `cross_condition_statistics`, `temporal_rin`,
`inter_component_interactions`, and `cross_protein_comparison`.

The current contract uses the `diagnostics` and `artifacts` blocks directly;
it does not invent separate capability names for them or for coordinates.

Capability semantics are:

- `capability=false`: the frontend must not expect the feature;
- `capability=true`: the frontend may show an optional panel or visualization
  if the corresponding data is present;
- required MVP fields are defined separately by Stage 17.2.

Backend internals must not become capabilities. Names such as `atom_cache`,
`interaction_accumulator`, `svd_ring_normals`,
`networkx_greedy_modularity`, `distance_eval_limit`, and
`mda_atomgroup_selection` would expose implementation mechanisms and are not
product-level availability signals.

## 11. Stage 16.12 rich sample interpretation

The Stage 16.12 frontend sample is a rich illustrative payload. It demonstrates
optional scientific annotations and artifact references. It is not the minimal
MVP contract; the minimal MVP fixture is defined by Stage 17.2.

Rich sample examples that remain optional include `x_ca/y_ca/z_ca`,
`backbone`, `aromatic_pi`, `cation_pi`, generic contact examples, diagnostics
references, analysis references, node metrics, community, all interaction
types, and artifact references beyond the stable `artifacts` object itself.
The sample must not be rewritten or interpreted as exposing backend internals,
raw paths, or local paths.

## 12. Non-goals

Stage 17.3 is docs/tests-only boundary hardening. It is not schema redesign,
not frontend implementation, and not runtime validator implementation. It does
not implement or change:

- contact types, chemistry detection, graph metrics, analysis algorithms, or
  backbone behavior;
- `EDGE_PRIORITY`, `InteractionAccumulator`, atom cache, `aromatic_pi`, or
  `cation_pi` behavior;
- temporal RIN, typed RIN full schema, formal statistics, conformational
  clustering, PCA/k-means/silhouette, or cross-protein comparison;
- FastAPI/upload/job API, database models, background workers, or frontend
  code;
- CLI behavior, runtime payload validation, schema fields, payload fields, or
  runtime outputs;
- dependencies, real-data CI, hard timing benchmarks, or local MD workflow.

No new payload fields are defined by this document.

## 13. Relationship to Stage 17.1 and Stage 17.2

Stage 17.1 defines what WANIA MVP is. Stage 17.2 defines required fields.
Stage 17.3 defines layer responsibility and prevents backend scientific
internals from becoming frontend contract.

Together, the three documents keep the MVP identity, its required display
model, and the science-versus-UI ownership boundary separate and reviewable.
