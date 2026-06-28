# Notebook gap report v1.3

## Reference scope

This report compares the backend with the reference semantics described by
`MANIA_preprocessing_v1_2` and `MANIA_analysis_v1_3`. The notebooks are
reference/specification artifacts only: default tests and CI do not execute
them.

## What preprocessing v1.2 adds

`MANIA_preprocessing_v1_2` adds an `InteractionAccumulator` refactor,
`build_atom_cache`, backbone interactions, richer per-frame interaction
exports, and Cα coordinates around a Kabsch-alignment workflow. It also
contains richer chemistry details such as π–π SVD ring normals and cation-π
centroid logic.

## What analysis v1.3 adds

`MANIA_analysis_v1_3` puts backbone first in `EDGE_PRIORITY` and exposes node
coordinates in graph JSON using notebook names `xca/yca/zca` plus `x/y/z`
aliases. The stable backend names are instead `x_ca/y_ca/z_ca` and `x/y/z`.

## What the backend already supports

Before Stage 16.5, the backend supports sampled per-condition Rg and generic
residue contacts, contact computation limits and progress, `contact_selection`
values `all` and `protein`, graph CSV/JSON export and diagnostics, and the
Stage 16.1 WANIA object JSON adapter. Workflow metadata retains
`frame_sampling`, `contact_computation_limits`, and `contact_selection`.

## What Stage 16.5 ports

Stage 16.5 ports representative Cα coordinates from the first sampled frame
for selected residues. Coordinates are condition-specific and protein-residue
bound. Backend `graph/graph.json` and WANIA nodes expose JSON-safe
`x/y/z` frontend aliases and explicit `x_ca/y_ca/z_ca` scientific fields.

These are representative coordinates, not a trajectory average. Stage 16.5
does not claim full Kabsch parity. Kabsch-aligned Cα coordinate parity with
`MANIA_preprocessing_v1_2`, including careful reconciliation of notebook
`CA_COORDS` semantics, remains a future notebook-parity gap.

For `contact_selection=protein`, a graph node without representative Cα
coordinates produces the deterministic `node_coordinates_missing` issue and
graph export stops clearly. The default `all` selection keeps legacy
full-system behavior: residues without an identifiable Cα may carry null
coordinates.

## Stage 16.6 deferred scope

Backbone edge type support is deferred. The notebook v1.3 `EDGE_PRIORITY`
update is also deferred. Stage 16.5 does not change the edge schema or edge
priority.

## Stage 16.7+ deferred scope

`InteractionAccumulator`, `build_atom_cache`, richer typed chemistry,
π–π SVD normals, cation-π centroid logic, and per-frame parquet parity are
deferred. Typed or temporal RIN, centrality/community metrics, and other full
notebook chemistry parity also remain future work.

## Known semantic gaps

- Representative coordinates come from the first sampled condition frame;
  they are not trajectory-average coordinates.
- No alignment pipeline was added, so full Kabsch parity is future scope.
- Protein identity uses the accepted runtime protein selection; no residue
  blacklist or protein-specific hardcoding is introduced.
- The backend uses `x_ca/y_ca/z_ca`; notebook-only `xca/yca/zca` names are not
  competing backend fields.
- Backbone and `EDGE_PRIORITY` parity remain deferred to Stage 16.6.
- The accumulator, atom cache, richer chemistry, and parquet parity remain
  deferred to Stage 16.7+.
