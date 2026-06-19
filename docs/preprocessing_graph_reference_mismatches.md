# Expected mismatches and known semantic differences for preprocessing graph comparison

## Purpose

Stage 14.4a documents how to interpret mismatches reported by Stage 14.3b
when comparing generated Stage 14 graph artifacts with notebook reference
graph artifacts under `MANIA_analysis_v1_2`.

Stage 14.4a is documentation-only and does not change comparison logic. It
does not add expected mismatch classification code, semantic-difference
classification code, source behavior changes, workflow integration, real-data
CI, or biological interpretation.

## Accepted comparison behavior

Stage 14.3b consumes an explicit
`PreprocessingGraphReferenceComparisonInput` and validates inputs through the
Stage 14.3a readiness validator before comparing row or item content. If
validation fails, row/content comparison is refused and the result reports an
input-validation mismatch.

When enabled, Stage 14.3b compares these targets:

- generated/reference `nodes.csv`;
- generated/reference corrected `edges.csv`;
- generated/reference row-preserving `graph.json`.

CSV values compare exactly as strings. No numeric tolerance, type conversion,
format normalization, or expected-mismatch classification is applied. The
comparison detects missing rows, extra rows, row-count differences, and field
value mismatches using deterministic row keys.

graph.json comparison is structural, not byte-level. JSON indentation,
object key order, and equivalent formatting do not matter, but top-level
metadata values, node items, edge items, and item field values still compare
by parsed value.

Stage 14.3b returns deterministic JSON-safe mismatch, target, and result
objects. It reports what differs; it does not decide whether a mismatch is
expected, acceptable, scientifically meaningful, or a bug.

## Current reference semantics

The current graph reference semantics are:

```text
MANIA_analysis_v1_2
```

The expected reference notebook location is:

```text
data/reference/notebooks_libraries_v1_2/MANIA_analysis_v1_2.ipynb
```

v1.1 reference artifacts are historical. They must not be deleted or modified
as part of Stage 14.4a.

The v1.2 notebook documents two relevant changes:

- Cell 5 adds interaction priority for graph edge display.
- Cell 12 fixes temporal RIN export handling.

Stage 14.3b graph comparison targets graph artifacts only. The v1.2 Cell 12
temporal RIN fix is reference context, not a Stage 14 graph comparison target.

## Artifact boundary

contact_edges.csv is an aggregate contacts table from Stage 13.
backend graph edges.csv is a Stage 14 graph artifact.
Stage 14 graph comparison compares backend graph edges.csv, not Stage 13
contact_edges.csv.

Stage 13 contact extraction and aggregate contacts export can feed Stage 14
graph mapping through accepted result objects, but the CSV artifacts have
different contracts. Do not compare Stage 13 `contact_edges.csv` directly
against notebook/reference backend graph `edges.csv` and treat that as a
Stage 14 graph comparison.

## Expected mismatch categories

The categories below are expected or plausible during Stage 14 comparison.
They are interpretation guidance only. They are not programmatic mismatch
classes, and they do not make every mismatch acceptable.

### nodes.csv

Expected or plausible node mismatches include:

- missing or extra node rows;
- different `resid` identity representation;
- different `resname` formatting;
- different `condition` naming;
- empty optional metric fields in generated artifacts where references contain
  notebook-derived metrics.

Reference-only graph metric fields can include:

- `degree`;
- `strength`;
- `betweenness`;
- `closeness`;
- `eigenvector`;
- `pagerank`;
- `kcore`;
- `community_id`.

Coordinate, geometry, and annotation fields can be empty in generated MVP
artifacts unless an explicit stage scopes them:

- `x_ca`;
- `y_ca`;
- `z_ca`;
- `tm_relative_z`;
- `rmsf_A`;
- `sasa_A2`;
- `ss`.

Empty optional metric or geometry fields can be expected when Stage 14 graph
export does not compute those values yet. Identity/key differences are more
serious: mismatched `resid`, `resname`, or `condition` values may indicate
different residue identity construction, condition scoping, or reference
adaptation and require investigation.

### corrected edges.csv

Expected or plausible corrected edge mismatches include:

- missing or extra edge rows;
- different edge endpoint identity in `resid_i` or `resid_j`;
- different primary `edge_type`;
- different `all_edge_types`;
- different `n_edge_types`;
- generic generated `residue_contact` edge versus a biochemical interaction
  edge in the reference;
- different `contact_freq`;
- different `mean_dist_A`;
- empty optional temporal or lifetime fields in generated artifacts where the
  reference may include notebook-derived temporal metrics;
- differences caused by interaction priority ordering.

Optional temporal and lifetime edge fields include:

- `std_dist_A`;
- `n_episodes`;
- `mean_lifetime_frames`;
- `max_lifetime_frames`;
- `mean_lifetime_ns`;
- `max_lifetime_ns`;
- `formation_count`;
- `breakage_count`;
- `first_seen_frame`;
- `last_seen_frame`;
- `window_cv`.

Generic `residue_contact` versus biochemical interaction labels can be a known
semantic difference. Endpoint identity, condition, and loss of corrected edge
schema fields usually require closer investigation.

### graph.json

Expected or plausible graph JSON mismatches include:

- top-level count mismatch;
- schema version mismatch;
- condition mismatch;
- missing or extra node items;
- missing or extra edge items;
- node or edge field mismatches inherited from the row-preserving CSV-backed
  JSON structure.

JSON formatting differences should not matter because comparison is
structural, not byte-level. Value differences still matter after parsing.

## Corrected multi-type edge schema

Corrected Stage 14 graph edges preserve these fields:

```text
edge_type
all_edge_types
n_edge_types
```

The accepted edge type priority is:

```python
EDGE_TYPE_PRIORITY = (
    "hbond",
    "disulfide",
    "salt_bridge",
    "ionic",
    "cation_pi",
    "aromatic_pi",
    "hydrophobic",
    "vdw",
)
```

`edge_type` is the primary prioritized display or comparison type.
`all_edge_types` preserves all observed edge types as a pipe-separated string
in current row-preserving graph artifacts. `n_edge_types` preserves the number
of edge types as a string in current row-preserving artifacts.

The current generic `residue_contact` edge type remains valid for MVP
generated graph artifacts.

## Generic residue_contact boundary

Stage 13 Contacts MVP detects residue contacts using the MVP contact
definition and options. It does not infer biochemical interaction classes such
as `hbond`, `salt_bridge`, `hydrophobic`, `vdw`, or related notebook/reference
interaction labels.

Therefore, generated Stage 14 graph edges can legitimately use:

```text
edge_type=residue_contact
all_edge_types=residue_contact
n_edge_types=1
```

A mismatch between `residue_contact` and a reference biochemical type is not
automatically a bug. It may reflect a known semantic difference between MVP
contact extraction and notebook/reference interaction classification. It
still requires interpretation in Stage 14.4 and future scientific validation.

Do not overread this boundary: `residue_contact` explains an interaction-class
semantic gap, not arbitrary endpoint, condition, schema, or count mismatches.

## Known semantic differences

Known semantic differences likely to matter include:

- MVP residue contacts versus notebook biochemical interaction classes;
- exact string comparison versus numeric formatting differences;
- row-preserving generated artifacts versus notebook-derived enriched graph
  metrics;
- missing optional metrics because Stage 14 graph export does not compute
  graph centralities or biological annotations;
- condition-scoped graph identity;
- graph JSON structural comparison ignores formatting but not value
  differences;
- temporal RIN is documented in v1.2 but not compared here.

These differences explain why an exact mismatch can appear without immediately
proving a source-code defect. They also do not prove the mismatch is safe.

## Temporal RIN boundary

Temporal RIN export and temporal RIN comparison remain future scope.

Stage 14.3b does not compare `temporal_rin.csv`, notebook temporal RIN cells,
window-level temporal graph outputs, diagnostics, workflow outputs, or real
data runs. v1.2 Cell 12 is documented reference context only for this graph
artifact comparison stage.

## What is not a bug by itself

The following are not bugs by themselves:

- JSON indentation or key-order differences;
- empty optional graph metric fields when Stage 14 does not generate them;
- generic `residue_contact` when biochemical interaction inference is out of
  scope;
- absence of temporal RIN artifacts from Stage 14 graph comparison;
- v1.1 not being used by default;
- reference artifacts not being modified.

Each item can still be part of a larger investigation when paired with
identity, schema, count, or value mismatches that should not differ.

## What requires investigation

The following should be investigated rather than waved through as expected:

- mismatched required identity fields such as `resid`, `resid_i`, `resid_j`,
  and `condition`;
- schema version mismatch when matching schema is required;
- endpoint inconsistency between nodes and edges;
- unexpectedly missing generated graph rows when corresponding contacts should
  have been present;
- unexpected loss of `edge_type`, `all_edge_types`, or `n_edge_types`;
- mismatch in `contact_freq` or `mean_dist_A` after inputs and definitions are
  known to match.

## Future stages

Stage 14.4a documents expected mismatches and known semantic differences.

Stage 14.4b remains final graph export boundary docs before workflow.

Future workflow/CLI scope may integrate graph export into the broader
workflow. This stage adds no CLI/workflow integration.

Future temporal/workflow scope may add temporal RIN export/comparison. This
stage adds no temporal RIN export or comparison.

Future scientific scope may add biochemical interaction classification if it
is explicitly scoped. This stage adds no biological interpretation and no
real-data CI.
