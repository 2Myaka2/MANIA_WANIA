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

## What Stage 16.6 ports

The backbone edge type and the notebook v1.3 `EDGE_PRIORITY` update are
implemented in Stage 16.6. A backbone edge is a structural graph edge between
sequential protein residues in one condition and chain, derived from their
representative Cα coordinates. `BACKBONE_MAX_CA_DIST_A = 4.5` Å. Missing Cα
coordinates, non-sequential indexes, different conditions, and different
known chain ids do not produce backbone edges.

`backbone` is first in the accepted backend priority, ahead of `hbond`,
`disulfide`, `salt_bridge`, `ionic`, `cation_pi`, `aromatic_pi`,
`hydrophobic`, and `vdw`. Notebook compact aliases `saltbridge`, `cationpi`,
and `aromaticpi` normalize to the accepted backend snake_case names.

For 690 continuous protein residues in one chain, local manual validation
should find approximately 689 backbone edges per condition. Default CI uses
small synthetic inputs instead of real MD data.

## What Stage 16.7 ports

InteractionAccumulator is implemented in Stage 16.7 as an internal contact
aggregation layer. It records observations by condition, canonical residue
pair, and edge type; uses sampled frame count as the contact-frequency
denominator; retains original source frame indexes; and deterministically
finalizes frequency and distance aggregates. The current contact engine still
produces only accepted generic `residue_contact` observations.

This is an internal refactor/parity step. Default scientific behavior,
accepted scientific CSV and graph schemas, backbone mapping, and the WANIA
object JSON contract remain unchanged. Failed or partial contact computation
does not expose finalized aggregates as a complete result.

## What Stage 16.8 ports

build_atom_cache is implemented in Stage 16.8 as an internal contact
performance/refactor layer. After `contact_selection` resolves the runtime
residues and before frame iteration, the backend caches stable residue
identity metadata and the atom references selected by the existing `heavy` or
`all` filter. Coordinates are still read from those cached atom references in
each sampled frame, so trajectory positions and accepted contact semantics do
not change. Empty filtered atom groups retain the existing successful
zero-contact behavior.

This stage makes no benchmark or timing guarantee and introduces no new
neighbor-search backend. Default scientific behavior, accepted output
schemas, and the WANIA object JSON contract remain unchanged.

## Deferred Stage 16 parity scope

- `build_atom_cache`: implemented in Stage 16.8.
- Per-frame contact parity remains deferred to Stage 16.9, including parquet
  parity.
- Richer aromatic/cation-pi chemistry remains deferred to Stage 16.10.
- Analysis metrics parity remains deferred to Stage 16.11.

Typed or temporal RIN, centrality/community metrics, and other full notebook
chemistry parity also remain future work.

## Known semantic gaps

- Representative coordinates come from the first sampled condition frame;
  they are not trajectory-average coordinates.
- No alignment pipeline was added, so full Kabsch parity is future scope.
- Protein identity uses the accepted runtime protein selection; no residue
  blacklist or protein-specific hardcoding is introduced.
- The backend uses `x_ca/y_ca/z_ca`; notebook-only `xca/yca/zca` names are not
  competing backend fields.
- Backbone edge type and `EDGE_PRIORITY` are implemented in Stage 16.6.
- `InteractionAccumulator` is implemented in Stage 16.7 without changing
  accepted output schemas.
- `build_atom_cache` is implemented in Stage 16.8 without changing accepted
  output schemas or contact scientific semantics.
- Per-frame parquet parity, richer typed chemistry, and analysis metrics
  remain deferred to Stages 16.9–16.11.
