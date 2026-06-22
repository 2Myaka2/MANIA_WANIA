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
- diagnostics, represented by the `diagnostics` block.

Planned or near future:

- WANIA object JSON adapter;
- `centrality_metrics`;
- `community_detection`;
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

The current static contact graph can provide residue-contact edge data. Typed
RIN interactions remain future scope.

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
    "diagnostics_report_json": "reports/graph_diagnostics_report.json"
  }
}
```

These paths reference backend artifacts. They do not make `graph/graph.json`
the WANIA frontend/API payload.

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

MANIA does not yet compute full typed RIN. MANIA does not yet compute temporal
RIN. MANIA does not yet compute centrality, community, or node structural
metrics as confirmed frontend fields.

Current backend schema may contain planned or empty columns for future metrics.
Planned or empty backend columns must not be treated as available UI data until
adapter and capability metadata confirm them.

Current backend `graph/graph.json` is not the final frontend/API payload.

## Future scope

Future work may implement a WANIA object JSON adapter, API output, frontend
integration, typed RIN, temporal RIN, centrality metrics, community detection,
node structural metrics, inter-component interactions, and broader product
features.

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
