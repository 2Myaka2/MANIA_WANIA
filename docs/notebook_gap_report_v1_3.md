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
preserves accepted generic `residue_contact` observations; Stage 16.10 adds
the two typed chemistry observations described below.

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

## What Stage 16.9 ports

Per-frame contact export parity is implemented in Stage 16.9 for accepted
backend interaction types. When `contact_selection=protein`,
`contacts/contacts_perframe.csv` includes structural `backbone` observations
for sequential residues in the same condition and chain whose live sampled-
frame Cα distance is at most `BACKBONE_MAX_CA_DIST_A = 4.5` Å. The distance
field contains that Cα distance. Original source frame indexes are preserved;
sampled frames are not renumbered.

Contact-derived `residue_contact` rows remain compatible, and `all` selection
keeps its previous all-residue contact behavior. Safety-limit failures do not
produce fake-complete backbone rows. Aggregate contacts, Stage 16.6 graph
backbone/priority behavior, and the WANIA object JSON contract are unchanged.
This CSV is not a full temporal RIN and does not enable
`typed_rin_interactions` or `temporal_interactions`.

Notebook v1.2 writes parquet. Backend Stage 16.9 ports the semantics into the
accepted CSV export path; parquet format parity remains future export-format
scope. At Stage 16.9, analysis metrics parity remained deferred to Stage 16.11.

## What Stage 16.10 ports

Aromatic π–π / cation-π chemistry parity is implemented in Stage 16.10 under
the canonical backend names `aromatic_pi` and `cation_pi`. Aromatic rings use
deterministic centroids and dependency-free best-fit-plane unit normals. The
normal-axis angle is sign-invariant: parallel interactions require an angle
below 30°, while T-shaped interactions accept 60°–120°. The notebook's exact
aromatic centroid cutoff is 7.0 Å.

Cation-π detection uses the LYS NZ or ARG CZ cation center and requires its
distance to a supported aromatic ring centroid to be below 6.0 Å. Incomplete
or unsupported atom-name patterns are skipped deterministically. The accepted
amino-acid patterns are general residue chemistry rather than protein-specific
residue IDs.

Both interaction types flow through `InteractionAccumulator`, typed aggregate
and per-frame CSV output, graph priority, and WANIA edge-type preservation.
Frame sampling, original source indexes, `contact_selection`, atom-cache scope,
contact limits, and partial/failed finalization behavior remain unchanged. No
new dependency is required. Notebook compact names `aromaticpi` and `cationpi`
remain aliases only. The WANIA object schema is not redesigned, and
`typed_rin_interactions` and `temporal_interactions` remain false.

## What Stage 16.11 ports

Analysis graph metrics/community MVP is implemented in Stage 16.11. The
dependency-light Python API consumes accepted backend `graph/graph.json` data
and computes condition-specific degree, strength, betweenness, closeness,
eigenvector, pagerank, and kcore. Strength sums numeric `contact_freq` values;
missing, null, empty, non-numeric, or non-finite values contribute 0.0. Pure
backbone edges therefore remain valid without invented contact frequencies.

NetworkX Louvain with seed 42 is the preferred community algorithm where the
accepted dependency boundary provides it. The current boundary does not, so
Stage 16.11 records a deterministic fallback issue and uses dependency-free
greedy modularity. No new dependency is required. The report includes
community count and modularity per condition.

Existing node identifiers and available residue fields are preserved,
including `region`, `ss`, `rmsf_A`, `sasa_A2`, `x/y/z`, and
`x_ca/y_ca/z_ca`. Stage 16.11 does not recompute coordinates or invent region
labels. It writes separate `analysis/metrics_<condition>.csv`,
`analysis/communities_<condition>.csv`, and
`analysis/analysis_metrics_report.json` artifacts only when its Python writer
is called. Accepted preprocessing graph schemas and CLI behavior are
unchanged. The WANIA schema is not redesigned and its analysis capability
flags remain unchanged; analysis artifacts are separate backend outputs.

## Deferred Stage 16 parity scope

- `InteractionAccumulator`: implemented in Stage 16.7.
- `build_atom_cache`: implemented in Stage 16.8.
- Per-frame contact export parity: implemented in Stage 16.9.
- Aromatic π–π / cation-π chemistry parity: implemented in Stage 16.10.
- Analysis graph metrics/community MVP: implemented in Stage 16.11.
- Parquet format parity remains future export-format scope.
- Formal statistical tests remain deferred, including Mann-Whitney U, FDR-BH,
  Cohen d, and bootstrap confidence intervals.
- Full temporal RIN remains deferred.
- Conformational clustering remains deferred, including PCA, k-means, and
  silhouette analysis.
- Figures and YaDisk upload remain notebook/reference-only scope.

Full typed or temporal RIN and broader notebook analysis remain future work.

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
- Per-frame contact export parity is implemented in Stage 16.9 without adding
  full temporal RIN or changing the WANIA object JSON contract.
- Aromatic π–π / cation-π chemistry parity is implemented in Stage 16.10
  without declaring full typed or temporal RIN capability.
- Analysis graph metrics/community parity is implemented in Stage 16.11 as
  separate backend artifacts without changing preprocessing graph artifacts
  or the WANIA contract.
- Formal statistical tests, full temporal RIN, conformational clustering,
  figure generation, YaDisk integration, and parquet format parity remain
  deferred or notebook/reference-only scope.
