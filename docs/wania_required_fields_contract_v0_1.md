# Required WANIA fields contract v0.1

## 1. Purpose and status terms

This document freezes the small required-fields profile that a WANIA MVP
frontend can trust. It is a docs, fixture, and tests contract. It is not schema
redesign, not a runtime validator, not FastAPI, and not an upload/job API or
frontend implementation. In short, it is not upload/job API work.

Stage 17.3 classifies the layer responsibility of these fields and separates
them from optional science and backend internals in the
[`Science vs UI boundary`](wania_science_ui_boundary_v0_1.md). That boundary
does not change this required set.

The terms in this contract mean:

- **required:** the field is present in every valid WANIA MVP payload and does
  not disappear without a contract version change. The frontend may use it
  without optional-science fallback checks.
- **optional:** the field may be present as progressive enhancement. Its
  absence does not invalidate the payload or break basic graph rendering.
- **backend-only:** the field or concept may exist in backend artifacts or
  implementation, but it is not part of the frontend MVP contract. The
  frontend must not depend on it.
- **future:** the capability or field is intentionally deferred. The frontend
  must not expect it unless a future contract version enables it.

Required means only what is needed to load the payload, understand run and
condition context, read capabilities, render the coordinate-based graph
skeleton, and show basic diagnostics and artifact references without crashing.

## 2. Required structure

### Top level

Every valid payload has these required top-level fields:

| Field | Required shape |
|---|---|
| `schema_version` | The accepted value `wania_graph.v0.1`. |
| `run` | An object with the required run fields below. |
| `capabilities` | An object with the availability semantics below. |
| `graph` | An object containing `graph.nodes` and `graph.edges`. |
| `artifacts` | An object; `{}` is valid when no optional references are available. |
| `diagnostics` | An object with the stable status/issues shape below. |

Optional science sections such as temporal, statistics, analysis, and
conformation data are not required top-level fields.

### Run metadata

The accepted `run` object requires:

| Field | Purpose |
|---|---|
| `run_name` | Stable run identifier within the protein context. |
| `protein_id` | Stable protein identifier. |
| `protein_name` | Frontend display name for the protein. |
| `condition_names` | Non-empty array of condition identifiers used by nodes and edges. |

These are the current Stage 16.1 adapter names. `job_id` is optional because
the accepted adapter permits it to be null. Local paths, manifest paths, raw
MD paths, notebook paths, and generated output paths are not run metadata.

### Capabilities

The `capabilities` object and its current `static_contact_graph` signal are
required. In this contract, capabilities are availability signals:

- `false` means the frontend must not expect the feature;
- `true` means the frontend may use the feature if its data is present;
- capability true does not make optional blocks required for basic MVP graph
  rendering;
- required fields exist independently of optional capabilities.

Other accepted capability flags are optional signals. If present, they must
be honest. In particular, `typed_rin_interactions`, `temporal_interactions`,
`temporal_rin`, `analysis_statistics`, `conformational_states`, and
`cross_protein_comparison` remain false unless a future contract explicitly
accepts their feature and data.

### Graph

`graph.nodes` and `graph.edges` are required arrays. `graph.edges` may be empty
for a nodes-only graph. Both arrays may be empty for an explicit empty state,
but diagnostics must then explain the empty state through a non-empty optional
`diagnostics.issues` array.

Advanced graph metrics, analysis blocks, communities, counts, condition
records, component records, and directedness metadata are optional.

### Node

Every renderable node requires:

| Field | Purpose |
|---|---|
| node `id` | Stable node identity within the payload. |
| node `condition` | A value listed in `run.condition_names`. |
| node `residue.index` | Accepted residue index identity. |
| node `residue.name` | Accepted residue display identity. |
| node `x/y/z` | Finite frontend-facing render coordinates. |

This freezes WANIA MVP v0.1 as the coordinate-based render profile. `x/y/z`
are required for renderable nodes and are frontend-facing render coordinates.
`x_ca/y_ca/z_ca` remain optional explicit scientific Cα coordinates. The
contract does not require coordinate provenance or recomputation and does not
change Stage 16.5 coordinate behavior.

Node `label`, `residue.id`, `residue.chain_id`/`chain_id`, `component_id`, and
node metrics are optional progressive enhancements.

### Edge

Every edge requires:

| Field | Purpose |
|---|---|
| edge `id` | Stable edge identity within the payload. |
| edge `source` | Existing source node id. |
| edge `target` | Existing target node id. |
| edge `condition` | A value listed in `run.condition_names`. |
| edge `interaction` | Interaction object. |
| `interaction.primary_type` | Canonical required primary edge type field. |

The prose term edge type refers to `interaction.primary_type`; this contract
does not add a parallel top-level `edge_type` field. It does not require any
specific scientific interaction type.

### Artifacts

`artifacts` is a required stable object, but every artifact reference inside it
is optional. If present, a reference path must be relative, must not traverse
through `..`, and must not point to `local_md`, `local_md_protein`,
`mania_output`, raw trajectory files, or other machine-local inputs or
generated outputs. Large CSV content is not inlined.

Graph, Rg/contact CSV, `contacts_perframe`, analysis metrics, community, and
diagnostics report references are optional. No analysis artifact is needed for
basic graph rendering.

### Diagnostics

`diagnostics` and `diagnostics.passed` are required. The accepted
`diagnostics.passed` status summary is a boolean: `true` or `false`; it must not
be `null`. This wording reflects the accepted Stage 18.3 demo export guardrail
without changing the required field set. `diagnostics.issues` is optional
because the current WANIA adapter does not emit it; if present, it must be an
array, and an empty issues array is valid. An empty graph must use a non-empty
issues array to explain its empty state. `report_path` and diagnostics details
beyond this status/issues shape are optional.

## 3. Optional progressive enhancements

The following remain optional for MVP validity:

- `x_ca/y_ca/z_ca` and `chain_id`;
- `interaction.all_types`, backend `all_edge_types`, and backend
  `n_edge_types`;
- `contact_frequency`, distance summaries, distance statistics, and other
  interaction details;
- `backbone` as a specific interaction type;
- `aromatic_pi` as a specific interaction type;
- `cation_pi` as a specific interaction type;
- analysis metrics and communities;
- Rg, contact, per-frame contact, analysis, and diagnostics artifact
  references;
- diagnostics details beyond the required `passed` status summary and the
  conditional issues rule.

The absence of these fields does not invalidate an otherwise valid payload.
Put plainly: backbone is optional, `aromatic_pi` is optional, `cation_pi` is
optional, analysis metrics are optional, and communities are optional.

## 4. Backend-only boundary

The following are backend-only and are never frontend dependencies:

- `InteractionAccumulator` internals;
- atom cache and `build_atom_cache` internals;
- contact engine internals and chemistry helper internals;
- raw per-frame computation details;
- raw trajectory paths and `local_md` paths;
- `local_md_protein` paths and `mania_output` paths;
- notebook execution details and full notebook parity internals.

`InteractionAccumulator` is backend-only, and the atom cache is backend-only.

## 5. Future and deferred

The following remain future work: temporal RIN; typed RIN full schema; formal
statistics; conformational clustering; PCA/k-means/silhouette; cross-protein
comparison; frontend implementation; and FastAPI/upload/job API work. Their
names in documentation or false capability signals do not make their payload
data available.

Temporal RIN is future, formal statistics are future, and conformational
clustering is future.

## 6. Fixtures and relationship to Stage 16.12

The minimal MVP fixture is
`tests/fixtures/wania_mvp_minimal_payload_v0_1.json`. It contains only the
required graph contract and deliberately omits optional science.

The Stage 16.12 rich frontend sample at
`tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json` passes this
same required-fields contract as a superset. Its scientific interaction
examples, Cα coordinates, metrics, and artifact references remain
illustrative; the Stage 16.12 rich frontend sample is not the minimal MVP
fixture.

Stage 17.2 adds no runtime payload validator, source behavior, scientific
computation, API, frontend, dependency, or schema redesign.

Stage 18.1 uses this required skeleton to define when an assembled
`wania_graph_payload.json` is demo-ready. See the
[`WANIA JSON assembly profile`](wania_json_assembly_profile_v0_1.md). Mapping
validation remains separate Stage 18.2 work.
