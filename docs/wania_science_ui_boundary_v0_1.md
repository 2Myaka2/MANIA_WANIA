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

The following remain future or deferred WANIA capabilities, even where MANIA
now emits a related backend/scientific artifact:

- temporal RIN UI and interactive temporal playback;
- full typed RIN schema (also described as the typed RIN full schema);
- formal statistics UI;
- conformation UI, including PCA/k-means/silhouette presentation;
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

Stage 18.1 carries this ownership boundary into artifact assembly: a
demo-ready payload may preserve optional science but must not expose
backend-only details as frontend requirements. See the
[`WANIA JSON assembly profile`](wania_json_assembly_profile_v0_1.md).

## 14. Stage 23.A WANIA RIN profile

### Profile definition and ownership boundary

After accepted Stages 20–22, the **WANIA RIN profile** means the existing,
stable frontend-facing graph render contract. It is the small payload shape a
frontend can use to identify a run, render nodes and edges, inspect capability
signals and diagnostics, and offer portable artifact links. It is not a dump
of MANIA preprocessing, static-analysis, temporal-analysis, or conformation
outputs.

The ownership boundary is:

```text
MANIA = backend/scientific RIN preprocessing and analysis artifacts
WANIA = stable frontend-facing JSON contract for graph rendering
```

MANIA scientific artifacts may contain richer tables, metrics, method status,
and provenance than the frontend needs. WANIA may reference such artifacts,
but scientific CSV/JSON contents must not be inlined into the base WANIA graph
payload and must not become prerequisites for base graph rendering. Stage
23.A freezes that policy only; it does not add or change an artifact-reference
key or mapping.

### Unchanged base render contract

The WANIA base render contract is unchanged, and the WANIA required fields are
unchanged. The authoritative field-level rules remain in the
[`Required WANIA fields contract`](wania_required_fields_contract_v0_1.md).
The required render profile remains:

| Area | Required fields |
|---|---|
| Top level | `schema_version`, `run`, `capabilities`, `graph`, `artifacts`, `diagnostics` |
| Run | `run_name`, `protein_id`, `protein_name`, `condition_names` |
| Graph | `graph.nodes`, `graph.edges` |
| Node | `id`, `condition`, `residue.index`, `residue.name`, `x`, `y`, `z` render coordinates |
| Edge | `id`, `source`, `target`, `condition`, `interaction.primary_type` |
| Diagnostics | `diagnostics.passed` |

The `artifacts` object is required, while every individual artifact reference
inside it remains optional. The presence or absence of an optional MANIA
artifact does not expand or reduce the required WANIA render field set.

In particular, none of the following become required WANIA node, edge, or
top-level render fields: centrality values, community IDs, region-enrichment
values, temporal window rows, temporal RIN metrics, PCA coordinates,
conformation labels, `selected_k`, `silhouette_score`, representative-frame
flags, MANIA statistics tables, or raw per-frame contact rows.

### Static RIN distinction

The frontend payload and MANIA static analysis graph have different purposes:

```text
wania_graph_payload.json
!= analysis/{condition}/graph.json
```

`wania_graph_payload.json` is the stable frontend-facing render contract. It
contains the accepted WANIA graph fields, render coordinates, capabilities,
diagnostics, and artifact-reference object.

`analysis/{condition}/graph.json` is the MANIA backend/scientific static RIN
artifact built from accepted Stage 20 residue and protein-contact artifacts.
Its scientific topology, aggregate typed-contact data, and provenance do not
replace the WANIA payload and do not become required WANIA fields.

Stage 21 scientific outputs are optional artifacts at this boundary:

- `analysis/{condition}/graph.json`;
- `analysis/{condition}/centrality_{condition}.csv`;
- `analysis/{condition}/communities_{condition}.csv`;
- `analysis/{condition}/region_enrichment_{condition}.csv`;
- `analysis/comparison.csv`;
- `analysis/stats.csv`.

Centrality, community, enrichment, comparison, and statistics rows may be
offered through later accepted artifact references, but they are not inlined
base graph state. Louvain is not implemented; community output uses the
truthful deterministic `greedy_modularity_unweighted` fallback. NMI and ARI
are not implemented. For cross-condition statistics, MWU, bootstrap CI,
p-values, and FDR-BH are not implemented; full statistical parity is not
claimed.

### Temporal RIN distinction

The temporal artifact is also separate from the WANIA graph payload:

```text
wania_graph_payload.json
!= analysis/{condition}/temporal_rin_{condition}.csv
```

`analysis/{condition}/temporal_rin_{condition}.csv` is a MANIA
backend/scientific per-window metrics artifact. Its rows describe sampled-frame
windows and derived graph summaries. Temporal window rows and temporal RIN
metrics are not required WANIA node or edge fields, are not required for base
rendering, and must not be embedded as base graph arrays. WANIA temporal
animation remains unimplemented.

The temporal source of truth remains the accepted Stage 20
`contacts_perframe_{condition}.csv`; the Stage 22 ordinal sampled-frame,
inclusive `frame_start`/`frame_end`, and `sampled_frame_count` denominator
semantics are unchanged by this profile.

### Conformation artifact distinction

The conformation artifacts remain separate backend/scientific outputs:

```text
wania_graph_payload.json
!= analysis/{condition}/conformation_pca_{condition}.csv
!= analysis/{condition}/conformation_labels_{condition}.csv
```

`analysis/{condition}/conformation_pca_{condition}.csv` exists, but computed
PCA is not implemented under the accepted dependency boundary. PCA coordinates
and explained-variance ratios remain unavailable and blank, `n_components =
0`, and applicable rows report `pca_unavailable` or an explicit skipped
status. No fake PCA coordinates are emitted.

`analysis/{condition}/conformation_labels_{condition}.csv` contains MANIA
backend/scientific fingerprint-based clustering labels. Its deterministic
k-means input is the binary `ContactFingerprintMatrix.values`, not PCA
coordinates and not rows from the PCA artifact. PCA-based clustering is not
claimed, and notebook PCA-to-k-means parity is not claimed. WANIA conformation
UI remains unimplemented.

### Optional scientific artifact boundary

The optional scientific-artifact boundary includes accepted Stage 20
preprocessing CSV/JSON artifacts, Stage 21 static-analysis artifacts, and Stage
22 temporal/conformation artifacts. These outputs are optional from the WANIA
base-render perspective even when MANIA requires or produces them for a
scientific workflow.

Stage 20 optional scientific artifacts at this WANIA boundary include
`residue_table_{condition}.csv`,
`protein_contact_edges_undirected_{condition}.csv`,
`contacts_perframe_{condition}.csv`, `edge_semantics.json`,
`mania_manifest.json`, and `mania_residue_library.json`. Stage 22 optional
scientific artifacts include `temporal_rin_{condition}.csv`,
`conformation_pca_{condition}.csv`, and
`conformation_labels_{condition}.csv` under `analysis/{condition}/`. The Stage
21 optional artifact list is defined in the static RIN distinction above.

Scientific artifacts may be referenced. Scientific artifacts must not be
inlined into the base WANIA graph payload. Scientific artifacts must not become
required for base graph rendering. Any future reference must remain portable
and relative under the existing artifact safety rules.

Stage 23.A defines no reference mapping. Capabilities alignment belongs to
Stage 23.B, artifact-reference alignment and demo payload policy belong to
Stage 23.C, WANIA contract-test updates belong to Stage 23.D, and the full
documentation acceptance checklist belongs to Stage 23.E. Capabilities are
not changed, artifact references are not changed, and the demo payload is not
regenerated here.

Stages 20, 21, and 22 artifact schemas and scientific behavior remain
unchanged. Computed PCA is not added. No numerical backend dependency is added.
Stage 24 has not started. API, Docker, database, frontend implementation, and
production workers remain unimplemented.

## 15. Stage 23.B capability alignment

### Boolean capability model

The current WANIA capability model is boolean-only and payload-specific. A
capability may indicate that the base render function exists, that the current
payload was assembled with an optional artifact path already supported by the
adapter, or that related backend/scientific support exists. These meanings must
be read with the capability-specific limitations below.

In the current payload:

- `true` means that the payload advertises the named capability under the
  existing adapter rules;
- `false` means that the payload does not advertise that capability; it does
  not by itself prove that related MANIA backend/scientific work is absent;
- an absent key is not an availability claim.

The boolean model cannot encode `partial` by itself. Partial and limited
behavior is therefore defined by this document rather than by changing a
boolean into a new object. A capability may indicate backend/scientific
artifact availability. A capability does not mean scientific contents are
embedded in the base WANIA graph payload. It also does not make a scientific
artifact required for base graph rendering.

Stage 23.B does not change the existing boolean keys, their runtime derivation,
the payload schema, or adapter/writer behavior. In particular, a MANIA artifact
that has no accepted WANIA reference input yet does not cause its current
payload flag to become `true`. Artifact-reference mapping and demo-payload
policy remain Stage 23.C work.

### Capability status and meaning

| Exact WANIA key | Accepted MANIA/WANIA status | Current payload interpretation and limits |
|---|---|---|
| `static_contact_graph` | available | WANIA can render its static graph payload. The MANIA `analysis/{condition}/graph.json` scientific artifact is a different graph contract. |
| `rg_timeseries` | available when its existing optional path is supplied | Advertises the existing optional Rg reference only; it does not inline Rg rows. |
| `aggregate_contacts` | available when its existing optional path is supplied | Advertises the existing aggregate-contact reference only; it does not inline contact rows. |
| `contacts_perframe` | available when its existing optional path is supplied | MANIA per-frame preprocessing is available. Raw per-frame rows are not embedded in `graph.nodes` or `graph.edges`. |
| `typed_rin_interactions` | backend semantics available; current WANIA capability unavailable | Stage 20/21 support the accepted protein interaction vocabulary and priority, while the current payload flag remains `false`. `interaction.primary_type` remains the only required edge interaction field; this flag does not promise a WANIA typed-RIN schema. |
| `centrality_metrics` | available as optional MANIA science; current adapter support is limited to its existing analysis-metrics paths | `centrality_{condition}.csv` is an optional Stage 21 artifact. Centrality values do not become required `graph.nodes` fields. Stage 23.B adds no mapping for the Stage 21 filename. |
| `community_detection` | available with a limited deterministic fallback; current adapter support is limited to its existing community paths | `communities_{condition}.csv` uses `greedy_modularity_unweighted`. Louvain is not implemented, and community IDs are not required node fields. |
| `node_structural_metrics` | limited backend availability; current WANIA capability unavailable | Stage 20 `residue_table_{condition}.csv` can carry `x_ca/y_ca/z_ca`, `tm_relative_z`, `rmsf_A`, `sasa_A2`, and `ss` to the extent values exist. This does not make them required node fields and does not redefine WANIA render `x/y/z`. |
| `conformational_states` | partial/limited backend availability; current WANIA capability unavailable | Fingerprint-based `conformation_labels_{condition}.csv` is available, but computed PCA and PCA coordinates are unavailable. Clustering does not use PCA coordinates, and notebook PCA-to-k-means parity is not claimed. |
| `cross_condition_statistics` | partial/limited backend availability; current WANIA capability unavailable | Stage 21.E supports conservative node-metric comparison in `comparison.csv` and `stats.csv`. It does not support MWU, bootstrap CI, p-values, FDR-BH, NMI/ARI, or edge/community/region-enrichment comparison, and it does not claim full statistical notebook parity. |
| `temporal_rin` | available as optional MANIA science; current WANIA capability unavailable | `temporal_rin_{condition}.csv` provides per-window scientific metrics. Its rows are not inlined in nodes or edges, and WANIA temporal animation is not implemented. |
| `inter_component_interactions` | unavailable/deferred | Stage 20 deferred non-protein inventory and heterograph support. No inter-component or full heterograph support is claimed. |
| `cross_protein_comparison` | unavailable/future scope | Cross-protein identity, alignment, and comparison support are not implemented. |

The exact current adapter keys are the names in this table. In particular,
`cross_condition_statistics` is the current key rather than
`analysis_statistics`; `temporal_rin` is the current key rather than
`temporal_interactions`; and `conformational_states` is the current key even
though the accepted backend artifact is named
`conformation_labels_{condition}.csv`. Stage 23.B introduces no aliases or new
capability keys.

### Preserved limitations and boundaries

`conformational_states` must not be read as a computed-PCA claim. The accepted
PCA artifact keeps `n_components = 0`, blank PCA coordinates, blank
explained-variance ratios, and `pca_unavailable` or an explicit skipped status.
The labels are deterministic k-means results over binary contact fingerprints,
not PCA-based clustering, and notebook PCA-to-k-means parity is not claimed.

`community_detection` must not be read as a Louvain claim.
`cross_condition_statistics` must not be read as an MWU, bootstrap CI,
p-value, FDR-BH, NMI/ARI, edge/community/region-enrichment comparison, or full
statistical parity claim. `node_structural_metrics` must not be read as a
change to WANIA `x/y/z` render-coordinate semantics.

Non-protein heterograph support, inter-component interactions, and
cross-protein comparison remain deferred. WANIA temporal animation, WANIA
conformation UI, and a WANIA typed-RIN schema remain unimplemented. API,
Docker, database, frontend implementation, and production workers are not
implemented. Stage 24 has not started.

The required WANIA fields remain unchanged. Scientific contents are not
inlined into the base payload, scientific artifacts are not required for base
rendering, and Stage 23.B changes no artifact reference, demo payload, or Stage
20–22 artifact/schema behavior.

## 16. Stage 23.C artifact references and demo payload policy

### Reference boundary and current runtime model

An **artifact reference** is portable metadata that identifies a separate
artifact file. It is not artifact content:

```text
artifact reference != artifact content
WANIA payload artifact reference != MANIA artifact file contents
WANIA base graph render validity != full scientific artifact availability
```

The top-level `artifacts` object remains required by the WANIA required-fields
contract, but every MANIA scientific artifact reference inside it is optional.
A payload with the required render fields and no optional scientific
references can still be valid and renderable. Scientific CSV rows, JSON
tables, and other artifact contents must not be copied into `artifacts`,
`graph.nodes`, or `graph.edges`.

The existing adapter has a narrower legacy mapping than the accepted Stage
20–22 artifact inventory. Its fixed reference slots are relative path strings
or `null`; its existing analysis metrics and communities references are
condition-keyed maps and are omitted with the `analysis` group when none are
supplied. This is the current artifact reference model, not a new generic
reference schema. Stage 23.C documents which accepted MANIA outputs are
eligible for later references but adds no adapter input, payload key, alias,
or runtime mapping for them.

The graph JSON consumed to construct the WANIA render graph is still a
required assembler input. That requirement is distinct from optional links to
additional MANIA scientific outputs after the base graph has been assembled.

### Condition-level reference policy

The following accepted MANIA artifacts are condition-specific and may receive
condition-keyed WANIA references when a mapping is explicitly accepted:

- `residue_table_{condition}.csv`;
- `protein_contact_edges_undirected_{condition}.csv`;
- `contacts_perframe_{condition}.csv`;
- `analysis/{condition}/graph.json`;
- `analysis/{condition}/centrality_{condition}.csv`;
- `analysis/{condition}/communities_{condition}.csv`;
- `analysis/{condition}/region_enrichment_{condition}.csv`;
- `analysis/{condition}/temporal_rin_{condition}.csv`;
- `analysis/{condition}/conformation_pca_{condition}.csv`;
- `analysis/{condition}/conformation_labels_{condition}.csv`.

No condition is required to provide every artifact. A condition-level
reference identifies the separate file for that condition; it does not turn
the file's rows into node or edge attributes and does not affect base-render
validity. Stage 23.C does not silently map Stage 21
`centrality_{condition}.csv` to the legacy adapter's `metrics_csv` name or add
references for Stage 22 outputs.

### Run/root-level reference policy

The following accepted MANIA artifacts are run/root-level and may receive
scalar WANIA references when a mapping is explicitly accepted:

- `edge_semantics.json`;
- `mania_manifest.json`;
- `mania_residue_library.json`;
- `analysis/comparison.csv`;
- `analysis/stats.csv`.

These references are run metadata links, not node or edge fields. They remain
optional, their contents remain out of the base payload, and Stage 23.C adds
no runtime mapping for them.

### Missing and unavailable artifacts

An optional reference is emitted only through an already-supported input when
the caller supplies an available artifact path. Under the existing shape, an
unsupplied fixed slot remains `null`, while an unsupplied condition-keyed
analysis group is omitted. Either representation means that WANIA must not
expect that optional artifact. Implementations must not invent a path, use a
placeholder path, or set a path-backed capability to `true` for an unavailable
artifact.

The current adapter derives path-backed booleans from supplied paths; most
optional scientific paths are not existence-validated by the assembler.
Callers must therefore supply only paths to artifacts that are actually
available. Missing optional science is not a diagnostics failure and does not
invalidate the base render graph. A future availability/status model would
need separate explicit approval; it must not be simulated with fake paths.

Artifact references remain relative to the declared output root and must obey
the existing portability rules: no absolute paths, parent traversal, raw
trajectory paths, machine-local paths, API endpoint URLs, or local/generated
output roots. References point to files; they do not embed file contents.

### Interaction with boolean capabilities

Stage 23.B remains authoritative for capability meaning. A current
path-backed capability can be `true` when its corresponding supported path is
supplied. It says only that the payload advertises that optional feature; it
does not say that the artifact contents are inline, make the reference or file
required for base rendering, or claim an unimplemented algorithm.

In particular, `centrality_metrics` does not make centrality values required
node fields; `temporal_rin` does not inline temporal rows; and
`conformational_states` does not claim computed PCA. Missing optional
references leave the relevant path-backed capability false under current
assembly rules and never make the required base graph invalid. The current
boolean model still cannot represent `partial` directly.

### Demo payload regeneration policy

The authoritative required fixture shape is the Stage 17.2 minimal fixture,
`tests/fixtures/wania_mvp_minimal_payload_v0_1.json`, together with the
required-fields contract. The Stage 16.12
`tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json` fixture is the
authoritative rich illustrative sample, not the minimal contract and not a
real-MD result. Runtime assembly behavior remains authoritative in the
adapter/writer and its focused tests. A generated `wania_graph_payload.json`
is an export product, not a third authoritative fixture.

Regenerate a committed fixture only when an explicitly accepted contract,
adapter/writer behavior, or deliberate fixture scenario changes its expected
bytes. Regeneration must use the accepted deterministic writer or demo export
flow, and the resulting diff must be reviewed by contract tests. A
documentation-only policy change is not a reason to regenerate a fixture.

Every committed demo payload must remain synthetic, small, deterministic, and
safe for default CI. It must not contain real MD output, raw/local/generated
MD paths, heavy generated scientific artifacts, inlined CSV rows or
scientific tables, secrets, or API endpoint URLs. Synthetic Stage 20–22
artifact references are deferred until their exact runtime mapping is
explicitly accepted and tested; unsupported or unavailable paths must not be
added merely to illustrate future support.

Therefore Stage 23.C is policy-only. The existing minimal fixture, rich
frontend sample, assembly fixtures, and any generated
`wania_graph_payload.json` remain unchanged. Their current synthetic artifact
references remain illustrative under the legacy mapping; no new Stage 20–22
reference is fabricated.

### Preserved scientific and stage limits

Computed PCA and PCA coordinates remain unavailable. Conformation labels are
fingerprint-based; PCA-based clustering and notebook PCA-to-k-means parity are
not claimed. Louvain is not implemented. MWU, bootstrap CI, p-values, and
FDR-BH are not implemented, and cross-condition statistics remain limited to
the accepted node-metric comparison rather than full statistical parity.
Non-protein heterograph support remains deferred.

WANIA temporal animation, WANIA conformation UI, and a WANIA typed-RIN schema
remain unimplemented. API, Docker, database, frontend implementation, and
production workers are not implemented. No dependency is added. Stage 20,
Stage 21, and Stage 22 artifacts and scientific behavior are unchanged. Stage
23.D and Stage 23.E have not started. Stage 24 has not started.
