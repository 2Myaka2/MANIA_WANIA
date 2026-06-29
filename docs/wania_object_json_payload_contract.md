# WANIA object JSON payload contract

## Purpose

Stage 16.0 documents the future WANIA object JSON payload contract before any
API, adapter, writer, or frontend integration is implemented.

This is a docs/tests/sample contract only. Stage 16.0 adds no runtime behavior.

The top-level payload object includes `schema_version`, `run`, `capabilities`,
`graph`, `temporal`, `artifacts`, and `diagnostics`.

## Why object JSON

The WANIA payload uses object JSON.

Preferred object JSON:

```json
{
  "nodes": [
    {
      "id": "n1",
      "label": "LYS123",
      "condition": "normal"
    }
  ]
}
```

Compact table JSON is not the Stage 16.0 contract:

```json
{
  "node_fields": ["id", "label", "condition"],
  "nodes": [["n1", "LYS123", "normal"]]
}
```

Object JSON is easier for frontend code to read, debug, and extend. Compact
payloads, pagination, gzip, or table-oriented serialization can be considered
later after the initial contract and adapter behavior are accepted.

## Backend graph artifact vs WANIA payload

`graph/graph.json` is a backend graph artifact.

The current backend `graph/graph.json` is not the frontend/API payload and is
not frontend/API payload shape. A future `wania_graph_payload.json` or
equivalent output is the future frontend/API payload.

Stage 16.0 does not change current `graph/graph.json`, does not change graph
export, and does not implement adapter or runtime writer code.

## Stage 16.1 Python adapter

Stage 16.1 introduces a WANIA object JSON adapter as Python runtime code. The
adapter consumes accepted Stage 15 artifacts, uses backend `graph/graph.json`
as the primary graph input, builds the object JSON payload described here, and
can write `wania_graph_payload.json` when explicitly called.

Public adapter API:

```python
build_wania_graph_payload_from_artifacts(...)
write_wania_graph_payload_json(...)
```

The adapter requires explicit protein/run metadata: `protein_id`,
`protein_name`, `run_name`, and `condition_names`. It does not infer protein
identity from output paths, file names, or condition names.

Stage 16.1 is not FastAPI and is not upload/job API. It does not implement an
API server, upload flow, database model, background worker, or frontend. It
does not change backend graph/graph.json, does not change graph export, and
does not change Stage 15 workflow semantics.

Stage 16.1 does not compute typed RIN, temporal RIN, centrality/community
metrics, node structural metrics, conformational states, cross-condition
statistics, inter-component interaction analysis, or cross-protein comparison.

Large Stage 15 CSV artifacts remain referenced by path in the `artifacts`
block. The adapter does not inline large CSVs such as `rg_timeseries.csv`,
`contact_edges.csv`, or `contacts_perframe.csv`.

## Stage 16.2 frame sampling

Stage 16.2 adds controlled preprocessing frame sampling before FastAPI/upload
or job API work. It affects Rg computation, contacts computation, graph outputs
derived from sampled contacts, optional scientific CSV exports, and JSON-safe
workflow provenance metadata.

The WANIA object JSON contract is not changed by Stage 16.2. A WANIA payload
can be regenerated from sampled Stage 15 artifacts without changing the
payload schema or the Stage 16.1 adapter payload schema.

## Stage 16.5 representative Cα coordinates

Stage 16.5 extends WANIA node objects non-breakingly with representative Cα
coordinates preserved from backend `graph/graph.json`:

```json
{
  "x": 121.22,
  "y": 83.81,
  "z": 98.52,
  "x_ca": 121.22,
  "y_ca": 83.81,
  "z_ca": 98.52
}
```

`x/y/z` are frontend-facing aliases. `x_ca/y_ca/z_ca` preserve Cα semantics.
Values are JSON-safe floats or null. These are representative,
condition-specific Cα coordinates from the first sampled frame, not a
trajectory average. Stage 16.5 does not claim full Kabsch parity;
Kabsch-aligned notebook parity remains future scope.

This is only a non-breaking node extension. Artifact references and the Stage
16.1 adapter input/output contract are unchanged.

## Stage 16.6 backbone edge semantics

Stage 16.6 ports `backbone` and the notebook `EDGE_PRIORITY` as a non-breaking
interaction type value extension. A backend structural edge between
sequential Cα residues can map to:

```json
{
  "interaction": {
    "primary_type": "backbone",
    "all_types": ["backbone", "vdw"]
  }
}
```

The adapter preserves `backbone` in `primary_type` and `all_types`. It does
not interpret structural backbone support as richer typed RIN chemistry, so
`typed_rin_interactions` remains false. Artifact references and payload shape
remain unchanged.

Overlapping backbone and contact-derived edges preserve contact-derived
metrics. Pure backbone structural edges do not invent contact_frequency or
other contact metrics when none exist. `InteractionAccumulator`,
`build_atom_cache`, and per-frame CSV parity are backend preprocessing details;
per-frame parquet parity remains deferred.

## Stage 16.10 aromatic and cation-π preservation

Stage 16.10 ports the canonical backend interaction values `aromatic_pi` and
`cation_pi`. The adapter preserves either value in
`interaction.primary_type` and preserves both in `interaction.all_types` when
they are present in accepted graph JSON. Ring centroids, normals, angle modes,
and cation centers are not added to the WANIA payload.

This is edge-type preservation, not a WANIA object JSON redesign and not a
declaration of full typed RIN support. typed_rin_interactions remains false,
the temporal RIN capability remains false, and no per-frame rows are inlined.
Analysis metrics parity remains deferred to Stage 16.11 in the Stage 16.10
boundary; full temporal RIN remains deferred.

## Stage 16.11 separate analysis artifacts

Stage 16.11 implements a backend-safe graph metrics/community MVP over
accepted `graph/graph.json` artifacts. The Python API can write separate
`analysis/metrics_<condition>.csv`,
`analysis/communities_<condition>.csv`, and
`analysis/analysis_metrics_report.json` artifacts. Centrality metrics are
degree, strength, betweenness, closeness, eigenvector, pagerank, and kcore;
existing residue attributes and representative Cα coordinates are preserved
where available.

At Stage 16.11 these CSVs are separate backend analysis outputs; they are not
inlined in WANIA nodes and were not added to the Stage 16.1 artifact block.
The Stage 16.11 computation does not itself change the WANIA adapter or object
JSON schema, and `node_structural_metrics` remains false.
`typed_rin_interactions`, temporal capabilities, statistics, and
conformational-state capabilities also remain false.

## Stage 16.12 frontend sample

Stage 16.12 provides a compact frontend-ready WANIA sample payload at
`tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json`. It is a
deterministic synthetic reference fixture, not a real-MD benchmark. The sample
demonstrates protein/run metadata, conditions, residue identity,
condition-specific `x/y/z` and `x_ca/y_ca/z_ca`, `backbone`,
`residue_contact`, `aromatic_pi`, `cation_pi`, primary/all interaction type
behavior, diagnostics, and analysis artifact references.

The adapter accepts optional condition-keyed Stage 16.11 metrics and community
CSV paths plus the analysis report path. When supplied, they appear under
`artifacts.analysis`; `centrality_metrics` and `community_detection` are true.
When absent, the pre-16.12 artifact object and false capability values remain
unchanged. CSV contents are not inlined, and node `metrics` remain empty unless
a separately accepted mapping supplies confirmed node values.

This sample is not an API response guarantee beyond the documented payload
contract and adds no frontend implementation. `typed_rin_interactions` remains
false, temporal interaction/RIN capability remains false, statistical analysis
remains unavailable, and conformational-state capability remains false.
FastAPI/upload/job API remains future scope. Temporal RIN remains future scope.
Formal statistics remain future scope. Conformational clustering remains future
scope.

## Stage 17.1 WANIA MVP frontend profile

Stage 17.1 freezes the stable frontend-facing subset of this object JSON
payload in `docs/wania_mvp_contract_v0_1.md`. The WANIA MVP profile is not the
full backend graph export or scientific analysis layer, and it is not a
FastAPI/upload/job API contract.

The Stage 16.12 sample is a rich illustrative payload, not the minimal required
MVP payload. Optional coordinates, scientific interaction types, measurements,
and analysis artifact references in that sample do not become universal MVP
requirements. Strict required-field validation and a minimal valid payload
fixture remain Stage 17.2 scope.

## Protein-agnostic run metadata

The payload is protein-agnostic. The `run` block identifies which protein run
the payload describes:

```json
{
  "run": {
    "job_id": "job_001",
    "run_name": "egfr_mutant_test",
    "protein_id": "egfr",
    "protein_name": "EGFR",
    "condition_names": ["wild_type", "mutant"]
  }
}
```

`protein_id`, `protein_name`, and `run_name` identify which protein and which
run. `condition_names` identifies states or groups inside one protein run.
Conditions are not protein identities.

Incorrect:

```json
{
  "condition_names": ["egfr", "napi2b"]
}
```

Example condition names include `normal`, `tumor`, `wild_type`, `mutant`,
`apo`, and `ligand_bound`.

## Conditions

The `graph.conditions` list gives object JSON condition records used by nodes
and edges:

```json
{
  "conditions": [
    {
      "id": "normal",
      "label": "normal"
    }
  ]
}
```

Each node and edge carries a `condition` value that should match a declared
condition id.

## Capabilities

The payload includes a `capabilities` object so frontend code can enable or
disable UI blocks without inferring maturity from placeholder columns.

`true` means MANIA can currently provide data for that block. `false` means
the block is reserved or future scope, but the calculation or adapter is not
implemented yet.

Required Stage 16.0 capability flags:

```json
{
  "capabilities": {
    "static_contact_graph": true,
    "rg_timeseries": true,
    "aggregate_contacts": true,
    "contacts_perframe": true,
    "typed_rin_interactions": false,
    "centrality_metrics": false,
    "community_detection": false,
    "node_structural_metrics": false,
    "conformational_states": false,
    "cross_condition_statistics": false,
    "temporal_rin": false,
    "inter_component_interactions": false,
    "cross_protein_comparison": false
  }
}
```

Available now:

- `static_contact_graph`;
- `rg_timeseries`;
- `aggregate_contacts`;
- `contacts_perframe`;
- `centrality_metrics` and `community_detection` when optional Stage 16.11
  analysis artifact references are supplied;
- diagnostics, represented by the `diagnostics` block.

Planned or near future:

- WANIA object JSON adapter;
- `typed_rin_interactions`;
- `node_structural_metrics`, such as RMSF, SASA, and secondary structure;
- `inter_component_interactions`.

Later or separate scientific scope:

- `temporal_rin`;
- `conformational_states`;
- `cross_condition_statistics`;
- `cross_protein_comparison`.

Frontend behavior should follow `capabilities`: unavailable blocks should be
hidden, disabled, or shown with an unavailable state rather than populated from
planned or empty backend columns.

## Graph block

The top-level `graph` block contains object JSON graph data:

```json
{
  "graph": {
    "directed": false,
    "node_count": 2,
    "edge_count": 1,
    "conditions": [],
    "components": [],
    "nodes": [],
    "edges": []
  }
}
```

The `graph` block is the future WANIA payload representation, separate from
the backend graph artifact at `graph/graph.json`.

## Nodes

Nodes are object JSON records. Each node represents a residue in a condition:

```json
{
  "id": "normal|A|123|123|LYS",
  "label": "LYS123",
  "condition": "normal",
  "component_id": null,
  "x": 121.22,
  "y": 83.81,
  "z": 98.52,
  "x_ca": 121.22,
  "y_ca": 83.81,
  "z_ca": 98.52,
  "residue": {
    "index": 123,
    "id": "123",
    "name": "LYS",
    "chain_id": "A"
  },
  "metrics": {}
}
```

`metrics` is reserved for confirmed node metrics. Current planned or empty
backend columns must not be treated as available UI data until a future adapter
and capability confirm them.

## Edges

Edges are object JSON records. Each edge links source and target node ids in a
condition:

```json
{
  "source": "normal|A|123|123|LYS",
  "target": "normal|A|150|150|ASP",
  "condition": "normal",
  "source_component_id": null,
  "target_component_id": null,
  "is_inter_component": false,
  "interaction": {
    "primary_type": "residue_contact",
    "all_types": ["residue_contact"]
  },
  "metrics": {
    "contact_frequency": 0.74,
    "mean_distance_A": 3.8
  }
}
```

The current static graph can provide residue-contact and structural backbone
edge data. Richer typed RIN interactions remain future scope.

## Interaction object

The edge `interaction` object reserves the future typed RIN shape without
implementing typed RIN computation:

```json
{
  "interaction": {
    "primary_type": "residue_contact",
    "all_types": ["residue_contact"]
  }
}
```

Future typed RIN examples may use:

```json
{
  "interaction": {
    "primary_type": "hbond",
    "all_types": ["hbond", "salt_bridge"]
  }
}
```

Expected future typed interaction examples include `hbond`, `salt_bridge`,
`hydrophobic`, `vdw`, `cation_pi`, `aromatic_pi`, and `disulfide`.

Stage 16.0 does not compute typed RIN and does not implement typed RIN
calculations.

## Components and inter-component extension point

The payload reserves component metadata for future interactions inside one
protein run, such as chain-to-chain, domain-to-domain, subunit-to-subunit, or
protein-component-to-protein-component interactions inside one complex.

Component object:

```json
{
  "components": [
    {
      "id": "chain_A",
      "label": "Chain A",
      "type": "protein_chain"
    }
  ]
}
```

Node extension:

```json
{
  "component_id": "chain_A",
  "residue": {
    "chain_id": "A"
  }
}
```

Edge extension:

```json
{
  "source_component_id": "chain_A",
  "target_component_id": "chain_B",
  "is_inter_component": true
}
```

Inter-component interactions inside one run are planned feasible extension
scope. Cross-protein comparison between different proteins or jobs is separate
future research/product scope.

Stage 16.0 does not implement inter-component interaction computation.

## Temporal RIN extension point

The payload reserves a temporal RIN extension point:

```json
{
  "temporal": {
    "available": false,
    "windows": []
  }
}
```

Temporal RIN is not required for the static graph MVP. Temporal RIN remains
future scope, likely after Stage 17 or in a separately scoped scientific task,
and should remain generic per protein run.

Stage 16.0 does not compute temporal RIN.

## Artifacts block

The `artifacts` block records backend artifact paths related to the run:

```json
{
  "artifacts": {
    "backend_graph_json": "graph/graph.json",
    "nodes_csv": "graph/nodes.csv",
    "edges_csv": "graph/edges.csv",
    "rg_timeseries_csv": "rg/rg_timeseries.csv",
    "contact_edges_csv": "contacts/contact_edges.csv",
    "contacts_perframe_csv": "contacts/contacts_perframe.csv",
    "diagnostics_report_json": "reports/graph_diagnostics_report.json",
    "analysis": {
      "metrics_csv": {
        "normal": "analysis/metrics_normal.csv",
        "tumor": "analysis/metrics_tumor.csv"
      },
      "communities_csv": {
        "normal": "analysis/communities_normal.csv",
        "tumor": "analysis/communities_tumor.csv"
      },
      "metrics_report_json": "analysis/analysis_metrics_report.json"
    }
  }
}
```

These paths reference backend artifacts. They do not make `graph/graph.json`
the WANIA frontend/API payload. The `analysis` entry is optional and only
references separate Stage 16.11 artifacts; no CSV rows are embedded.

## Diagnostics block

The `diagnostics` block represents graph diagnostics status for frontend/API
display:

```json
{
  "diagnostics": {
    "passed": true,
    "report_path": "reports/graph_diagnostics_report.json"
  }
}
```

The diagnostics report remains a backend report artifact.

## Current MANIA state

MANIA currently computes Rg and contacts. MANIA currently builds a static
residue-contact graph.

MANIA can optionally write scientific CSVs with explicit flags:

- `rg/rg_timeseries.csv`;
- `contacts/contact_edges.csv`;
- `contacts/contacts_perframe.csv`.

MANIA does not yet compute full typed RIN or temporal RIN. Stage 16.11 computes
centrality and community metrics as separate backend analysis artifacts, and
Stage 16.12 can reference those artifacts without inlining them. Node
structural attributes are preserved only when already present; Stage 16.11
does not compute them.

Current backend schema may contain planned or empty columns for future metrics.
Planned or empty backend columns must not be treated as available UI data until
adapter and capability metadata confirm them.

Current backend `graph/graph.json` is not the final frontend/API payload.

## Future scope

Future work may implement API output, frontend integration, typed RIN,
temporal RIN, node structural metric computation, inter-component
interactions, and broader product features.

Cross-protein comparison remains future scope and may require sequence
alignment, structure alignment, residue mapping, or domain mapping. The
current backend graph workflow does not provide cross-protein comparability.
The `cross_protein_comparison` capability remains `false`.

## Out of scope for Stage 16.0

Stage 16.0 does not implement FastAPI.
Stage 16.0 does not implement adapter or runtime writer code.
Stage 16.0 does not change graph export.
Stage 16.0 does not change current `graph/graph.json`.
Stage 16.0 does not compute typed RIN.
Stage 16.0 does not compute temporal RIN.
Stage 16.0 does not compute centrality, community, or node structural metrics.
Stage 16.0 does not implement inter-component interaction computation.
Stage 16.0 does not implement cross-protein comparison.
Stage 16.0 adds docs/tests/sample contract only.

## Sample payload

The Stage 16.0 sample contract fixture is:

```text
tests/fixtures/wania_graph_payload_v0_1.json
```

The sample is valid object JSON and is a contract sample, not runtime output.

The Stage 16.12 final frontend reference sample is:

```text
tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json
```

It is compact synthetic fixture data for default CI and frontend contract
review. It is not generated real-MD output and does not imply API availability.
