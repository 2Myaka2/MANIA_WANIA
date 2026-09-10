# MANIA/WANIA

MANIA currently provides a backend preprocessing graph workflow for molecular
dynamics (MD) data. WANIA is the future web/API layer that will consume MANIA
outputs after a separate Stage 16+ contract is accepted.

The current practical workflow starts from a preprocessing manifest and local
raw MD files, loads runtimes, computes Rg and contacts in memory, exports
backend graph artifacts, writes diagnostics when report writing succeeds, and
can optionally write the root-level Stage 20 artifacts consumed by
`mania analyze`. Reference comparison is separate and requires explicit
reference artifact paths.

## Stage 25 Reproducibility Hardening Status

Stage 25 is reproducibility and publication hardening. Stage 25.A software
identity is complete. Stage 25.B run provenance and effective sampling is
complete. Stage 25.C input/output artifact inventory and opt-in checksums is
complete. Stage 25.D unified technical artifact validation is complete. Stage 25.E observation-only PBC audit and runtime metadata is complete.
Stage 25.F reproducibility documentation and FAIR² bridge is complete.
Stage 25.G final technical-hardening acceptance is complete.
The scientific PBC protocol remains unresolved; MANIA applies no internal
minimum-image correction. Stage 25 is complete. FastAPI remains postponed.

**Stage 26 — COMPLETE.** Stage 26 is complete: Stage 26.A and 26.B are accepted; Stage 26.C implements
authoritative Dataset execution binding, technical propagation, and validation.
The Dataset v1.0 scientific contract is frozen except for concrete NAMD condition
labels, which remain unresolved. Dataset v1.0 remains unreleased.
Stage 27 physical-time sampling/window engine is complete. Stage 27.A and 27.B
are accepted; Stage 27.C integrates their plans into preprocessing. Stage 27 is complete.
Stage 28 contact episodes/lifetime/publication protein-edge tables are next;
Stage 28 has not started. The 95% exclusion policy remains Stage 32.
WANIA is unchanged. Analysis Dataset-context propagation is outside Stage 26;
analysis temporal propagation is outside Stage 27.

See the [Dataset identity contract](docs/dataset_identity_contract.md) and
[parameter-table contract](docs/dataset_parameter_table_contract.md). A manifest
can supply inline `dataset_spec`, or top-level `dataset_parameter_table_path`
with per-condition `dataset_ref`. Table binding uses only the exact
`(dataset_id, system_id, trajectory_id, replica_id)` key. Inline plus table must
agree in every spec field. Scientific condition `None` stays `None`.
Resolved context enters preprocessing provenance; a used table enters inventory
and unified technical validation. Dataset-aware runs now execute the requested
physical production interval and stride through Stage 27 and require all legacy
frame options at their defaults. Legacy-only manifests retain the existing frame
sampler. See the [physical-time execution contract](docs/physical_time_execution_contract.md).
`temporal_execution.json` separately records actual selected source frames,
coverage, and full-window membership; it enters inventory and provenance without
changing scientific artifact schemas. Partial coverage may proceed. Windows are
metadata only: contacts still aggregate all selected frames, with no occupancy,
episodes, or lifetime calculations.

**Stage 25 — COMPLETE.** See the
[final acceptance record](docs/stage25_final_acceptance.md),
the [Stage 25 roadmap](docs/stage25_reproducibility_hardening.md),
[reproducibility guide](docs/reproducibility.md), and
[software release reference](docs/software_release_reference.md).

Completed `mania preprocessing run-graph-export` runs automatically emit
`<output>/runtime_metadata.json` and `<output>/pbc_audit.json`; completed
`mania analyze` runs emit `<output>/analysis/runtime_metadata.json`. These
technical artifacts enter inventory and provenance without changing scientific
stdout counts. There is no new PBC CLI option: external preprocessing is
`undeclared` automatically and scientific PBC status remains `unresolved`.
Failed scientific runs retain the existing Stage 25.B/C metadata boundary.
See [PBC and runtime metadata](docs/pbc_runtime_metadata.md).

Stage 25.D.1 integrity/reference checks and D.2 existing-validator coordination
are implemented through `validate_run_artifacts` and the technical validation CLI:

```bash
mania artifacts validate out --scope preprocessing
```

Scope is explicit (`preprocessing` or `analysis`). Optional repeated
`--input-artifact-path ARTIFACT_ID=PATH` mappings resolve external inputs; their
paths are never guessed. `passed` and `partial` return exit 0; `failed` returns
exit 1. A partial report has no technical errors but incomplete validation.
Technical success does not certify scientific correctness or publication readiness.
See [unified artifact validation](docs/unified_artifact_validation.md).

MANIA has one package-version source, `src/mania/_version.py`, shared by
`mania.__version__` and dynamic package metadata. `mania --version` remains the
standard human-readable version command, printing `mania-wania 0.1.0`.
The Python API `get_software_identity()` returns immutable structured runtime
software identity: software and distribution names, the MANIA version, the
exact source-checkout commit when available, commit source, and working-tree
status (`clean`, `dirty`, or `unavailable`). Git inspection is lazy and occurs
only when this function is called, using the module location rather than the
process working directory. Wheel installations without checkout metadata
report Git fields as unavailable (`commit_sha` is `None`).

```bash
.venv/bin/python -c "import json; from mania.software_identity import get_software_identity; print(json.dumps(get_software_identity().to_dict(), indent=2, sort_keys=True))"
```

This Python API invocation prints the software identity as JSON to stdout; it
is software identity only, creates no run provenance, and adds no CLI subcommand.

Successful and covered failed preprocessing runs write
`<output>/run_provenance.json`; successful and covered failed analysis runs write
`<output>/analysis/run_provenance.json`. The separate locations protect preprocessing
provenance even when analysis uses the same input and output root. These records
are additive: `RunMeta`, `mania_manifest.json`, and `analysis/extended_metrics.json`
retain their existing roles and schemas. The existing command needs no new flag:

```bash
mania analyze \
  --input preprocessing_output \
  --output run_output \
  --condition normal \
  --condition tumor \
  --enable-pca
```

The analysis passport records execution identity, UTC timing, portable command
and configuration, conditions, and references to completed analysis outputs;
failed runs claim no partial outputs. Sampling remains in preprocessing
provenance. See the [run-provenance contract](docs/run_provenance_contract.md)
for covered failures and metadata error behavior.

Preprocessing automatically writes `<output>/artifact_inventory.json`; analysis
writes `<output>/analysis/artifact_inventory.json`. The default size-only mode
`--artifact-checksum-mode none` records exact byte sizes without reading contents
for integrity metadata. SHA256 is explicit opt-in and streams every inventoried
input and output in bounded chunks:

```bash
mania analyze --input preprocessing_output --output run_output \
  --condition normal --condition tumor --artifact-checksum-mode sha256
```

The shared analysis resolver supplies the exact Stage 20 input paths used by
execution; completed output paths come from its result. No directory scanning
occurs. After authoritative inputs resolve, failed analysis gets an input-only
inventory; earlier failures produce no inventory. Each workflow's provenance
references its own inventory only after successful writing. Inventories exclude
themselves and run provenance. Analysis preserves both root preprocessing
technical files even with the same input and output root. See the
[artifact inventory contract](docs/artifact_inventory_contract.md).

## Stage 20 Preprocessing Status

Stage 20 preprocessing parity is consolidated through Stage 20.F:

- Stage 20.A implements `residue_table_{cond}.csv` baseline export.
- Stage 20.B implements `protein_contact_edges_undirected_{cond}.csv` and
  `contacts_perframe_{cond}.csv` with the accepted aggregation semantics.
- Stage 20.C implements the accepted protein-only RIN edge semantics.
- Stage 20.D implements `edge_semantics.json`, `mania_manifest.json`, and
  `mania_residue_library.json`.
- Stage 20.E explicitly defers optional non-protein node/contact inventory.
- Stage 20.F validates these accepted artifacts and aligns their docs/tests.

This Stage 20 status does not itself implement Stage 21 analysis parity,
temporal RIN, non-protein inventory, a full heterograph, or a WANIA typed-RIN
schema. Accepted Stage 21 outcomes are described below. The accepted WANIA
JSON contract and required rendering fields remain unchanged.

## Stage 21.A Static RIN Graph Status

Stage 21.A adds a dependency-free MANIA static analysis RIN graph builder over
the accepted per-condition Stage 20 residue table and protein contact edge
artifacts. It preserves Stage 20 residue and residue-pair identity, collapses
overlapping typed observations onto one undirected residue-pair edge, selects
the primary type with the central `EDGE_TYPE_PRIORITY`, and retains every
typed aggregate in priority order. The recommended output is a per-condition
`analysis/{condition}/graph.json`; missing `contact_freq` produces explicit
null `contact_freq` and `weight` values.

This analysis artifact is not `wania_graph_payload.json` and does not change
WANIA required fields or render-coordinate semantics. Stage 21.A itself does
not compute metrics or later-stage analysis outputs.

## Stage 21.B Static RIN Metrics Status

Stage 21.B computes deterministic per-node `degree`, `strength`,
`betweenness`, `closeness`, `eigenvector`, `pagerank`, and `kcore` values from
the accepted Stage 21.A in-memory graph or exported `graph.json`. It writes
`centrality_{condition}.csv` with stable node, column, and float formatting.
`kcore` remains the existing MANIA contract spelling.

Only `strength` uses the accepted scientific `weight = contact_freq` value.
It sums available numeric incident weights; a node with incident edges but no
numeric incident weight receives a missing strength, while an isolated node
receives degree and strength zero. Betweenness and closeness are unweighted so
contact strength is never misinterpreted as path distance. Iterative metric
non-convergence produces deterministic missing values.

This remains a MANIA backend/scientific artifact. Stage 21.B itself does not
add metrics to the WANIA payload or implement communities, enrichment,
comparison, statistics, temporal RIN, or conformation artifacts.

## Stage 21.C Static RIN Communities Status

Stage 21.C computes deterministic community assignments from the accepted
Stage 21.A in-memory graph or exported `graph.json`. No Louvain implementation
is available within the accepted dependency boundary, so the implementation
truthfully reports `greedy_modularity_unweighted` as its deterministic
fallback. Community detection and modularity use topology only; available and
missing `weight = contact_freq` values are preserved but not reinterpreted or
filled.

The writer emits `communities_{condition}.csv` with Stage 21.A node identity,
stable one-based community IDs, community size, algorithm, modularity, and
community count. Communities are ordered by their minimum residue identity;
disconnected components and isolates therefore remain deterministic. This is
a MANIA backend/scientific artifact and does not change the WANIA payload.
Region enrichment and later comparison/statistics remain outside Stage 21.C.

## Stage 21.D Static RIN Region Enrichment Status

Stage 21.D consumes the accepted per-condition Stage 21.A `graph.json` and
Stage 21.C `communities_{condition}.csv`. It uses only non-empty `region`
labels already present on Stage 21.A nodes; unlabeled nodes are excluded from
contingency tables and no region is inferred from residue numbers. For each
community and observed region, a dependency-free two-sided Fisher exact test
is computed only when community, outside-community, region, and non-region
margins are available.

The deterministic writer emits `region_enrichment_{condition}.csv` with the
2x2 counts, raw p-value, method, status, accepted community metadata, and
labeled/total node counts. Empty graphs, missing labels, one-community graphs,
and insufficient region margins produce explicit skipped statuses with no
invented p-values. This is a MANIA backend/scientific artifact; it does not
change WANIA, implement cross-condition statistics, or start temporal or
conformation analysis. Stages 21.E and 21.F are described separately below;
Stage 22 requires separate approval.

## Stage 21.E Cross-Condition Comparison Status

Stage 21.E consumes accepted `centrality_{condition}.csv` artifacts and
compares every deterministic lexical condition pair. Nodes match only when
`residue_index`, `resid`, `resname`, and `segment_id` all agree; row order and
condition-local node IDs are never used as cross-condition identity. Exact
matches receive per-metric `value_b - value_a` rows in root-level
`comparison.csv`. Missing metrics remain empty, unmatched entities are counted,
and identity conflicts produce explicit skipped statuses.

Root-level `stats.csv` reports a paired mean-delta summary and Cohen's dz when
the complete matched pairs are sufficient and paired-difference sample
variance is defined. No p-value method is implemented, so p-value and adjusted
p-value fields remain empty and correction is explicitly `none`. Edge,
condition-local community, and region-enrichment comparison scopes are
explicitly skipped. This dependency-free backend/scientific analysis does not
change the WANIA payload. Stage 21.F validation is described separately below;
temporal RIN and conformation analysis remain unimplemented.

## Stage 21.F Analysis Validation And Alignment Status

Stage 21.F consolidates the accepted Stage 21.A–21.E outputs with focused
synthetic contract tests. The tests validate fixed graph/CSV schemas,
deterministic bytes and row ordering, graph-to-centrality and
graph-to-community node identity, graph/community-to-enrichment labels and
IDs, centrality-to-comparison stable residue identity, and
comparison-to-statistics IDs and statuses. They also verify that Louvain is
not claimed, region labels are not invented, unsupported scopes remain
`skipped_unsupported_scope`, and `stats.csv` retains empty `p_value` and
`p_adjusted` fields with `correction = none`.

This is validation, documentation, and test alignment only; no accepted Stage
21 schema or algorithm changes. Stage 22 temporal RIN is not implemented.
Conformation/PCA/k-means/silhouette artifacts are not implemented. WANIA
typed-RIN schema is not implemented. Full heterograph/non-protein inventory is
not implemented. Frontend/API/Docker/database/production API work is not
implemented. The accepted WANIA JSON contract remains unchanged.

## Stage 22.A Temporal RIN Input And Window Contract Status

Stage 22.A defines a dependency-free temporal input contract over the accepted
Stage 20 `contacts_perframe_{condition}.csv` artifact. `TemporalRinConfig`
exposes the accepted defaults `TEMP_WINDOW = 10`, `TEMP_STEP = 10`, and
`TEMP_MIN_FREQ = 0.25`, with positive window/step validation and frequency
validation in `[0, 1]`. The loader validates condition, non-negative integer
frame indexes, stable residue identity, normalized undirected residue pairs,
and `edge_type` against `EDGE_TYPE_PRIORITY`. Because Stage 20 already emits
one minimum-distance observation per frame/pair/type, duplicate normalized
keys are rejected as invalid artifacts.

Windows use the sorted unique frame indexes that actually occur in the
per-frame contact artifact. Window membership is ordinal: numeric gaps do not
imply unsampled frames. `window_id` is zero-based; `frame_start` and
`frame_end` are the first and last assigned source frame indexes and are both
inclusive. A reached trailing window is emitted when it contains at least one
sampled frame. The denominator reserved for later window-level
`contact_freq` is `sampled_frame_count`, never the numeric frame span.
Header-only input has no sampled frames or windows; one-frame and
fewer-than-window inputs produce one partial window.

Stage 22.A does not build window-level RIN graphs, compute or filter
window-level contact frequencies, calculate temporal metrics, export
`temporal_rin_{condition}.csv`, or implement fingerprints, PCA, k-means,
silhouette, representative frames, or conformation artifacts. It changes no
Stage 20/21 artifact schema and no WANIA payload behavior.

## Stage 22.B Window-level Contact Frequency And RIN Status

Stage 22.B consumes the validated Stage 22.A rows and sampled-frame windows to
build one deterministic in-memory RIN graph per window. Typed contacts are
grouped by normalized residue pair and `edge_type`; their
`window_contact_freq` is the number of observed sampled frames divided by the
window's `sampled_frame_count`. Numeric frame spans and inferred unsampled
frames are never used. `TEMP_MIN_FREQ` is applied only to typed-contact
inclusion and is inclusive: `window_contact_freq >= min_frequency`.

Passing interaction types are retained in `EDGE_TYPE_PRIORITY` order. The
first passing type is the primary edge type, and its window contact frequency
is the edge weight. Mean, population-standard-deviation, minimum, and maximum
distance summaries use available observed distances only; missing distances
are not treated as zero. Header-only input produces no window graphs, while a
window with no rows or no passing typed contacts remains an explicit empty
graph with a deterministic status.

Stage 22.B is an internal backend/scientific graph construction layer. It does
not compute temporal graph metrics or export `temporal_rin_{condition}.csv`;
those operations are provided separately by Stage 22.C. Stage 22.B does not
construct contact fingerprints, or implement PCA, k-means, silhouette,
representative frames, or conformation artifacts. Stage 20 and Stage 21
artifacts and the accepted WANIA payload contract remain unchanged.

## Stage 22.C Temporal Graph Metrics And Export Status

Stage 22.C consumes the accepted Stage 22.B window graphs and emits one stable
summary row per window in
`analysis/{condition}/temporal_rin_{condition}.csv`. Window and condition
identity remain unchanged. `active_frame_count` is the number of sampled
frames containing at least one accepted contact row before `TEMP_MIN_FREQ`
filtering. Empty and no-passing-contact windows retain explicit statuses and
have empty derived-metric fields.

Node and edge counts use the active Stage 22.B topology. Density and mean
degree are unweighted; mean strength uses the primary edge's
`window_contact_freq`. Betweenness and closeness remain unweighted, so contact
frequency is never interpreted as distance or cost. Community count and
modularity reuse the truthful deterministic Stage 21.C
`greedy_modularity_unweighted` fallback and do not claim Louvain.

Stage 22.C does not construct contact fingerprints or implement PCA, k-means,
silhouette, representative frames, or conformation artifacts. It changes no
Stage 20 or Stage 21 artifact schema, no Stage 22.A/B frequency or window
semantics, and no accepted WANIA payload contract.

## Stage 22.D Contact Fingerprint Matrix Status

Stage 22.D consumes accepted Stage 22.A validated
`contacts_perframe_{condition}.csv` observations and builds an internal,
condition-local binary contact fingerprint matrix. Rows are sampled frames in
numeric `frame_index` order. Columns are normalized residue-pair/`edge_type`
features ordered by residue indexes and `EDGE_TYPE_PRIORITY`; distinct types
for the same pair remain distinct columns. Values are exactly `1` when the
feature is observed in the frame and `0` otherwise.

Frame timing and feature residue identity remain metadata outside the matrix.
Numeric frame gaps do not create inferred frames, and distances, counts,
contact frequencies, window frequencies, and temporal metrics are not matrix
values. Header-only, one-frame, one-feature, and representable zero-feature
inputs have deterministic in-memory results. Stage 22.D adds no public CSV.

Stage 22.D does not implement PCA, SVD, explained variance, k-means,
silhouette, representative frames, or conformation artifacts. It does not
change `temporal_rin_{condition}.csv`, any Stage 20/21/22.A–C behavior, or the
accepted WANIA payload contract.

## Stage 22.E Contact Fingerprint PCA Export Status

Stage 22.E consumes the accepted Stage 22.D binary contact fingerprint matrix
and writes the deterministic backend/scientific artifact
`analysis/{condition}/conformation_pca_{condition}.csv`. The artifact preserves
condition, sampled-frame order, `frame_index`, optional `time_ps`, and feature
count. It reserves stable `pc1`/`pc2`/`pc3` and explained-variance-ratio
columns and is written atomically with stable float and line formatting.

The accepted dependency boundary does not directly provide NumPy or another
numerical linear-algebra backend. Stage 22.E therefore does not fake PCA.
Nonconstant matrices receive `pca_unavailable`; zero-frame, zero-feature,
one-frame, and constant centered matrices receive explicit statuses. All such
rows have `n_components = 0` and empty component and explained-variance
fields. Header-only fingerprint input produces a header-only artifact. A later
explicit dependency decision is required before centered SVD, public PC1-PC3
coordinates, explained variance, and deterministic loading-sign stabilization
can emit computed coordinates.

Stage 24.A provides that explicit dependency decision for MANIA only. NumPy is
now an accepted direct dependency, and computed PCA is available only when the
analysis API is called with `enable_pca=True`. The default
`enable_pca=False` path preserves the Stage 22.E fallback: no PCA computation,
no fake coordinates, blank explained-variance fields, and the existing
`pca_unavailable` status for nonconstant inputs.

Stage 22.E does not implement k-means, silhouette selection, cluster labels,
representative frames, or `conformation_labels_{condition}.csv`. It does not
use temporal RINs, distances, frequencies, or trajectories as PCA input and
does not change Stage 20/21/22.A–D artifacts or the accepted WANIA payload
contract.

## Stage 22.F Contact Fingerprint Clustering Status

Stage 22.F consumes `ContactFingerprintMatrix.values` from Stage 22.D and
writes the deterministic backend/scientific artifact
`analysis/{condition}/conformation_labels_{condition}.csv`. It uses
deterministic dependency-free k-means directly on binary contact fingerprint
vectors: farthest-first initialization, lowest-cluster assignment tie breaks,
arithmetic-mean centroids, and assignment-stability or bounded-iteration
stopping. It does not read `conformation_pca_{condition}.csv`, temporal RIN
metrics, contact distances, or contact frequencies.

Candidate `k` values run from 2 through the lower of 10 and one less than the
frame count. Only candidates with mathematically valid silhouette labels are
scored with Euclidean fingerprint distance. The highest silhouette score wins,
with the lowest `k` winning exact score ties. States are relabeled by their
minimum `frame_index`. Each computed state has exactly one representative:
the frame nearest its final centroid by squared Euclidean distance, with the
lowest `frame_index` breaking distance ties. Empty, featureless, insufficient,
constant, and no-valid-candidate inputs receive explicit statuses and no
invented labels, scores, representatives, or centroid distances.

Stage 22.F does not use PCA coordinates and does not claim notebook PCA to
k-means parity. The default artifact records `algorithm =
deterministic_kmeans_fingerprint`, `input_source =
contact_fingerprint_matrix`, `pca_status = pca_unavailable`, and
`notebook_parity = not_pca_kmeans_parity`. Stage 24.B adds an optional
explicit PCA clustering basis without changing this default: callers must pass
`clustering_basis="pca"` and a computed in-memory `ConformationPcaProjection`.
Supplying a projection alone does not switch modes, PCA is not silently
enabled, and no silent fallback to fingerprints occurs. PCA-mode metadata
records `algorithm = deterministic_kmeans_pca`, `input_source =
conformation_pca_coordinates`, `pca_status = computed`, and a truthful
notebook-parity-not-claimed value. Stage 22.F does not change
`conformation_pca_{condition}.csv` or `temporal_rin_{condition}.csv`, alter
prior Stage 20–22 artifacts, or change the accepted WANIA payload contract.

## Stage 22.G Temporal/Conformation Validation And Alignment Status

Stage 22.G consolidates the accepted Stage 22.A–22.F outcomes with focused
synthetic schema, deterministic-output, skipped-state, and cross-artifact
tests. The tests validate `temporal_rin_{condition}.csv`,
`conformation_pca_{condition}.csv`, and
`conformation_labels_{condition}.csv` field order and stable bytes. They also
check temporal window identity, fingerprint/PCA/label frame coverage and
ordering, optional `time_ps`, explicit status/notes behavior, and header-only
empty artifacts. No accepted Stage 22 schema or scientific algorithm changes
in this consolidation pass.

Default PCA output remains disabled: `pca_unavailable` rows keep
`n_components = 0`, blank component coordinates, and blank explained-variance
ratios unless PCA is explicitly enabled. Conformation labels remain derived
from binary contact fingerprints by default; Stage 22.F does not use PCA
coordinates and does not claim notebook PCA-to-k-means parity. Stage 24.A adds
opt-in computed PCA, and Stage 24.B adds opt-in PCA clustering. Full notebook
parity is not claimed.

The accepted WANIA payload contract remains unchanged. WANIA temporal
animation, WANIA conformation UI, and a WANIA typed-RIN schema remain deferred.
API, Docker, database, frontend, and production workers also remain deferred,
as do cross-protein comparison and non-protein heterograph support.

## Stage 23.A WANIA RIN Profile And Scientific Boundary Status

Stage 23.A defines the WANIA RIN profile as the unchanged, stable
frontend-facing graph render contract after accepted Stages 20–22. MANIA owns
backend/scientific preprocessing, static-analysis, temporal-analysis, and
conformation artifacts; WANIA owns the render payload with `graph.nodes`,
`graph.edges`, node `x/y/z`, edge `interaction.primary_type`, capabilities,
diagnostics, and the artifact-reference object.

`wania_graph_payload.json` is not
`analysis/{condition}/graph.json`,
`analysis/{condition}/temporal_rin_{condition}.csv`,
`analysis/{condition}/conformation_pca_{condition}.csv`, or
`analysis/{condition}/conformation_labels_{condition}.csv`. Scientific
artifacts may be referenced but are not inlined and are not required for base
graph rendering. This docs/profile block changes no required fields, runtime
payload behavior, capabilities, artifact-reference mapping, demo payload, or
Stage 20–22 artifact schema. See
`docs/wania_science_ui_boundary_v0_1.md`.

## Stage 23.B WANIA Capabilities Alignment Status

Stage 23.B documents the existing boolean-only, payload-specific capability
model without changing runtime flags or schema. A capability may advertise
base render support, an optional artifact path already supported by the
adapter, or related MANIA backend/scientific support. It never means that
scientific CSV/JSON contents are inlined into the base WANIA graph payload or
required for base rendering.

Static rendering and existing path-backed Rg/contact capabilities are
available. MANIA typed protein-RIN semantics, centrality, deterministic
`greedy_modularity_unweighted` communities, temporal RIN artifacts, and
fingerprint-based conformation labels exist with the limitations documented in
`docs/wania_science_ui_boundary_v0_1.md`. Cross-condition statistics remain
limited to the accepted node-metric comparison. Computed PCA, PCA-based
clustering, notebook PCA-to-k-means parity, Louvain, MWU, bootstrap CI,
p-values, FDR-BH, full statistical parity, non-protein heterograph support,
inter-component interactions, and cross-protein comparison are not claimed.

No required field, runtime payload behavior, adapter/writer behavior, artifact
reference, demo payload, or Stage 20–22 artifact schema changes in Stage 23.B.
Artifact-reference alignment and demo-payload policy remain Stage 23.C work.

## Stage 23.C WANIA Artifact References And Demo Policy Status

Stage 23.C defines artifact-reference semantics without changing the runtime
mapping. Individual MANIA scientific references remain optional metadata in
the required `artifacts` object. Condition-level Stage 20–22 outputs and
run/root-level manifests, semantics, comparison, and statistics files may be
referenced only through an explicitly accepted mapping. References are
portable file paths, not artifact contents; scientific CSV/JSON rows are not
inlined into `graph.nodes`, `graph.edges`, or the base payload. Missing
optional science does not invalidate base graph rendering, and unavailable
artifacts must not receive fake paths.

The existing adapter keeps its narrower legacy reference shape and
boolean/path-backed capability behavior. Stage 23.C adds no Stage 20–22 key,
schema field, API URL, or adapter/writer behavior. The Stage 17.2 minimal
fixture remains authoritative for required shape, while the Stage 16.12 rich
frontend fixture remains the authoritative illustrative sample. Fixtures are
regenerated only for an explicitly accepted contract/runtime/scenario change
and must remain synthetic, small, deterministic, and safe for default CI.
This policy-only stage does not regenerate any demo payload or add synthetic
Stage 20–22 references. See `docs/wania_science_ui_boundary_v0_1.md`.

## Stage 23 Completion Status

Stage 23.D adds focused WANIA contract tests for the unchanged required fields,
frontend render `x/y/z`, boolean `diagnostics.passed`, optional file
references, non-inlined scientific contents, conservative capabilities, and
deterministic demo export. Stage 23.E closes the documentation alignment and
records the acceptance checklist in
`docs/wania_science_ui_boundary_v0_1.md`.

Stage 23 is complete as a contract, policy, tests, and documentation alignment
stage. It does not change the WANIA base runtime schema, required fields,
adapter/writer behavior, capability derivation, artifact-reference mapping, or
demo payload. MANIA static, temporal, PCA, and conformation-label artifacts
remain separate optional scientific files. Their contents are not copied into
`graph.nodes` or `graph.edges`, and missing optional science is not a
base-render diagnostics failure.

At Stage 23 close, computed PCA remained unavailable and conformation labels
remained fingerprint-based rather than PCA-based. Stage 24.A now adds optional
computed PCA for MANIA only; fingerprint clustering remains the default and
does not use PCA coordinates. Notebook PCA-to-k-means parity, Louvain, MWU,
bootstrap confidence intervals, p-values, FDR-BH, and full statistical parity
are not claimed. API, Docker, database, frontend implementation, and production
workers remain future scope; FastAPI remains postponed.

The former roadmap statement "Stage 25 Minimal API is postponed" is historical;
Stage 25 now covers reproducibility and publication hardening.

## Stage 24.A Optional Computed PCA Status

Stage 24.A approves NumPy as a direct project dependency for optional MANIA
computed PCA. PCA is not part of the default analysis path: callers must pass
`enable_pca=True` to `build_conformation_pca_projection(...)` to compute
coordinates. With the default `enable_pca=False`, MANIA does not import or run
NumPy PCA code and continues to emit blank coordinates and blank explained
variance values for nonconstant inputs.

The PCA input contract is unchanged:
`ContactFingerprintMatrix.values` is the only accepted matrix. Rows are
sampled frames, columns are deterministic normalized residue-pair/type
features, and values are binary 0/1 contact fingerprints. PCA does not use
temporal metrics, contact frequencies, distance summaries, WANIA render
coordinates, graph coordinates, C-alpha coordinates, or Stage 21 metrics.

When explicitly enabled, MANIA computes PCA with centered NumPy SVD. It
subtracts each feature mean, retains up to the internal default maximum of 10
rank-supported components, stabilizes each component sign by the largest
absolute loading with the lowest feature-index tie break, and writes finite
deterministic coordinates and explained-variance ratios to the existing
`analysis/{condition}/conformation_pca_{condition}.csv` schema. The public CSV
schema remains limited to PC1-PC3, and unavailable exported components remain
blank. Empty, one-frame, zero-feature, and constant/all-zero inputs are
skipped honestly with explicit statuses and no fake coordinates or
explained-variance ratios. A requested numerical PCA failure records
`pca_failed`; `mania analyze` treats that status as fatal before writing
current-run Stage 24 artifacts.

The original v1.2 notebook was inspected. Its conformation cell builds dense
binary fingerprints, centers them with `StandardScaler(with_std=False)`, does
not standardize them, uses scikit-learn `PCA`, and performs k-means on PCA
coordinates. The notebook code does not show deterministic component-sign
stabilization. Stage 24.A therefore implements centered NumPy SVD and does not
claim exact notebook parity.

Stage 24.A does not implement PCA-based clustering, `mania analyze`,
`extended_metrics.json`, WANIA schema or payload changes, API/frontend work,
Docker, database models, or production workers. FastAPI remains postponed.

## Stage 24.B Optional PCA-Based Clustering Status

Stage 24.B adds a second conformation clustering basis to
`build_conformation_clusters(...)`: `fingerprint` remains the default, and
`pca` is explicit opt-in only through `clustering_basis="pca"`. Fingerprint
clustering continues to use direct binary residue-contact-pattern similarity
from `ContactFingerprintMatrix.values`. PCA clustering uses proximity in the
reduced PCA feature space from a successfully computed in-memory
`ConformationPcaProjection`.

PCA mode requires a supplied projection with `status = computed`, at least one
retained component, finite coordinates, matching condition, matching frame
count, matching frame order and `frame_index`, and non-conflicting `time_ps`
where both sides provide time. Invalid PCA configuration fails explicitly; it
does not fall back to fingerprint clustering. Supplying a computed projection
while leaving the basis at the default does not switch modes, and PCA is not
silently enabled.

By default, PCA clustering uses all successfully computed components retained
internally by the accepted projection artifact, up to the internal default
maximum of 10.
Callers may pass `pca_components_for_clustering=N` to use the first `N`
computed components. `N` must be an integer from 1 through
`projection.n_components`; unavailable component columns are not filled or
silently ignored.

Both bases reuse the same deterministic dependency-free k-means framework,
candidate-k range, Euclidean silhouette calculation, selected-k tie behavior,
state relabeling, CSV serialization, and no-fake-value skipped behavior. The
active feature vectors are the only difference. Representative frames and
`distance_to_centroid` are computed in the active clustering space. PCA-mode
CSV metadata uses `deterministic_kmeans_pca`,
`conformation_pca_coordinates`, `computed`, and a notebook parity value that
states parity is not claimed.

The v1.2 notebook clusters over all PCA score columns from
`n_comp = min(10, n_frames - 1, len(all_pairs) - 1)` after centering with
`StandardScaler(with_std=False)`, while it exports only PC1/PC2/PC3 for
visualization. MANIA therefore retains more than three internal PCA components
for clustering while keeping the public PCA CSV limited to PC1-PC3, but does
not claim exact notebook parity. Stage 24.C handles analysis
orchestration separately; `extended_metrics.json`, WANIA changes,
API/frontend work, Docker, database models, and production workers remain
unimplemented. FastAPI remains postponed.

## Stage 24.C Analysis Orchestration CLI Status

Stage 24.C adds a separate top-level analysis command:

```bash
mania analyze \
  --input ./mania_output \
  --output ./mania_output \
  --condition normal \
  --condition tumor
```

`--input` is an existing Stage 20 preprocessing output root containing
`residue_table_{condition}.csv`,
`protein_contact_edges_undirected_{condition}.csv`, and
`contacts_perframe_{condition}.csv` for every requested condition. Optional
root metadata files such as `edge_semantics.json`, `mania_manifest.json`, and
`mania_residue_library.json` are validated when present. The command does not
read raw trajectories, does not rerun preprocessing or contact generation, and
does not invoke WANIA payload assembly.

`--output` is the run root. Scientific artifacts are written below
`<output>/analysis/` without recursively cleaning that directory. The
canonical Stage 24 analysis layout is:

```text
<output>/
`-- analysis/
    |-- extended_metrics.json
    |-- comparison.csv
    |-- stats.csv
    `-- {condition}/
        |-- graph.json
        |-- centrality_{condition}.csv
        |-- communities_{condition}.csv
        |-- region_enrichment_{condition}.csv
        |-- temporal_rin_{condition}.csv
        |-- conformation_pca_{condition}.csv
        `-- conformation_labels_{condition}.csv
```

The default run keeps PCA disabled and clusters directly from contact
fingerprints:

```bash
mania analyze \
  --input ./mania_output \
  --output ./mania_output \
  --condition normal \
  --condition tumor
```

With `--enable-pca`, the accepted centered NumPy SVD PCA projection is
computed and written when the fingerprint matrix is valid, but clustering
still remains fingerprint-based unless PCA basis is requested explicitly:

```bash
mania analyze \
  --input ./mania_output \
  --output ./mania_output \
  --condition normal \
  --condition tumor \
  --enable-pca
```

In this mode, PCA status is `computed`, clustering basis remains
`fingerprint`, and PCA is not used for clustering. Fingerprint and PCA
clustering answer different scientific questions: fingerprint clustering uses
direct binary residue-contact-pattern similarity, while PCA clustering uses
proximity in internally retained PCA feature space.

PCA clustering is explicit opt-in and requires an enabled, computed in-memory
projection:

```bash
mania analyze \
  --input ./mania_output \
  --output ./mania_output \
  --condition normal \
  --condition tumor \
  --enable-pca \
  --clustering-basis pca
```

`--pca-components-for-clustering N` is valid only with
`--clustering-basis pca`, and `N` selects from the internally computed
components. Valid values may exceed three when enough internal components
exist. PCA basis without `--enable-pca`, PCA component selection with the
fingerprint basis, a requested PCA component count above the actual computed
count, unsafe/duplicate condition names, missing required Stage 20 artifacts,
and invalid artifact schemas fail clearly without a success JSON summary.
Explicit requested PCA numerical failure is fatal: stdout contains no success
JSON, `passed=true` is not emitted, and current-run Stage 24 analysis
artifacts, including `analysis/extended_metrics.json`, are not written.
Accepted degenerate PCA inputs remain nonfatal skipped outcomes for
fingerprint clustering.

For one condition, per-condition artifacts are written and root-level
`comparison.csv` / `stats.csv` are header-only; no self-comparison is
fabricated. For two or more conditions, the accepted conservative Stage 21.E
node-metric comparison and stats writer is used. On success, stdout contains
one deterministic JSON object with the requested conditions, PCA/clustering
configuration, portable relative artifact paths, skipped steps, and
diagnostic issues. It is a CLI summary only and is separate from the persisted
Stage 24.D manifest.

Each successful `mania analyze` run also writes the MANIA-only analysis
manifest:

```text
analysis/extended_metrics.json
```

The manifest schema version is `mania.extended_metrics.v0.1`. It is a compact
index over the current run's scientific outputs, not a data table dump and not
WANIA JSON. Artifact references are portable paths relative to the run output
root, always under `analysis/`, and are derived from `AnalyzeRunResult`
current-run artifact ownership rather than from scanning the output tree.

The manifest records requested conditions in request order, the PCA and
clustering configuration, per-condition analysis statuses and artifact
references, run-level cross-condition status, diagnostics, and a stable
limitations list. PCA intent is separate from compatibility CSV status: with
default `--enable-pca` omitted, the PCA analysis status is `not_requested`
even though `conformation_pca_{condition}.csv` is still written with blank
compatibility rows. When PCA computes, the manifest reports backend
`numpy_svd`, the maximum internal component setting, the actual internally
computed component count, and the CSV-exported component count. Clustering
metadata separately records basis, PCA status, whether PCA was used for
clustering, and requested/used PCA component counts. Computed PCA may coexist
with fingerprint clustering; in that case `pca_status = computed` and
`pca_used_for_clustering = false`.

For one condition, `comparison.csv` and `stats.csv` may be referenced as
header-only current-run artifacts while cross-condition status is
`not_applicable` with reason `single_condition`. Optional scientific outcomes
such as missing region labels, degenerate PCA, or unavailable clustering are
represented with skipped/unavailable statuses and compact reasons. The
manifest is deterministic UTF-8 JSON with sorted keys, two-space indentation,
one trailing newline, no timestamps, and no embedded centrality/community/
temporal/PCA/label/comparison/stat rows or graph node/edge arrays.

`extended_metrics.json` is not consumed by WANIA in Stage 24. WANIA required
fields, runtime schema, capabilities, artifact mapping, adapters, fixtures,
and `wania_graph_payload.json` remain unchanged. API/frontend integration is
future scope.

This orchestration layer calls the accepted Stage 21 and Stage 22 Python APIs
directly. It adds no dependency, no WANIA schema/runtime/capability/artifact
mapping change, no API/frontend/Docker/database/worker code, and no final
biological interpretation. Repeated runs over identical inputs and options are
intended to produce byte-identical analysis artifacts and stdout JSON.

Stage 24.E validates this integrated workflow with small synthetic Stage
20-style inputs and closes Stage 24 as a MANIA-only backend/scientific stage.
The closure keeps PCA optional and disabled by default, keeps fingerprint
clustering as the default, keeps PCA clustering explicit opt-in with no silent
fallback, and preserves the distinction between the stdout summary and
`analysis/extended_metrics.json`. WANIA JSON, runtime schema, adapter/writer
behavior, capabilities, artifact mapping, fixtures, and
`wania_graph_payload.json` remain unchanged.

Stage 24.F corrects PCA provenance, requested PCA failure semantics, and
internal PCA component capacity without changing public CLI options or CSV
field order. It preserves truthful computed-but-unused PCA metadata for
fingerprint clustering, makes explicit requested numerical PCA failure fatal
in `mania analyze`, keeps accepted degenerate PCA inputs nonfatal, allows PCA
clustering to use internally retained components beyond PC3, and keeps WANIA
unchanged. No YAML or JSON analysis configuration exists.

## Current Backend Workflow

Accepted Stage 15 workflow:

```text
raw MD files + preprocessing manifest
-> runtime loading
-> in-memory Rg + contacts
-> graph/nodes.csv
-> graph/edges.csv
-> graph/graph.json
-> optional root-level Stage 20 analysis inputs when explicitly requested
-> optional scientific CSV exports when explicitly requested
-> diagnostics report when diagnostics report writing succeeds
```

Reference comparison is optional and disabled by default. When enabled, it
requires explicit reference artifact paths; the CLI does not auto-search
`data/reference/**`.

The main command is:

```bash
mania preprocessing run-graph-export \
  --manifest PATH \
  --output PATH
```

Preprocessing does not invoke `mania analyze`. `mania analyze` does not read
raw `.tpr`/`.xtc` files and does not repeat contact computation. Neither
command invokes WANIA automatically.

## Protein-Agnostic Boundary

The current backend workflow is protein-agnostic and is not NaPi2b-specific.
NaPi2b is only the current local sample dataset used in examples and tests.
Future Stage 16 API work must not hardcode NaPi2b.

One uploaded package/job should represent one protein run. Future API/job
metadata should carry `protein_id`, `protein_name`, `run_name`, and
`condition_names`. Conditions are states/groups within a protein run, not the
protein identity.

Full multi-protein dashboard/catalog/comparison is future product scope.
Cross-protein comparison is future scope and may require residue, sequence,
or structure mapping or alignment. The current Stage 15 backend graph workflow
must not imply cross-protein comparability by default.

See `docs/wania_api_protein_agnostic_boundary.md`.

## Install For Local Development

For local development and scientific workflow use, install the development and
optional MD extras:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,md]"
```

The `md` extra is for local scientific/runtime work. It is not a new core
dependency boundary, and default CI does not require real MD data.

## Local MD Data Layout

Keep local raw MD data outside version control. A typical local layout is:

```text
local_md/
|-- manifests/
|   `-- napi2b_10ns.yaml
|-- normal/
|   |-- topology.tpr
|   `-- trajectory.xtc
`-- tumor/
    |-- topology.tpr
    `-- trajectory.xtc
```

`local_md/` is local-only. Raw MD files must not be committed. Use `.tpr`
topology by default. A `.gro` topology may be used only when supported by the
current MDAnalysis/runtime loading path.

## Manifest Example

Example `local_md/manifests/napi2b_full.yaml`:

```yaml
output_root: ../outputs

conditions:
  - condition: normal
    topology_path: ../normal/topology.tpr
    trajectory_paths:
      - ../normal/trajectory.xtc

  - condition: tumor
    topology_path: ../tumor/topology.tpr
    trajectory_paths:
      - ../tumor/trajectory.xtc
```

## Manifest Readiness Check

Before running the workflow, check that the manifest can be loaded and that its
declared local input paths are ready:

```bash
python - <<'PY'
import json
from mania.preprocessing import check_preprocessing_graph_workflow_manifest_readiness

result = check_preprocessing_graph_workflow_manifest_readiness(
    "local_md/manifests/napi2b_10ns.yaml"
)
print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
PY
```

## Run Graph Export Workflow

Run the accepted Stage 15 backend graph export workflow with explicit manifest
and output paths:

```bash
mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_10ns.yaml \
  --output mania_output/napi2b_10ns \
  --verbose
```

`--verbose` sends progress messages to stderr. Stdout remains the final
machine-readable JSON result. The command exits non-zero when a workflow stage
fails. The CLI does not execute notebooks, auto-discover `local_md`, or produce
WANIA frontend/API payloads.

## Export Analysis-Ready Inputs

To make preprocessing output directly reusable by `mania analyze`, pass the
explicit `--export-analysis-inputs` flag with protein-only contacts. This
writes the accepted Stage 20 CSV/JSON files directly under `--output`:

```text
residue_table_{condition}.csv
protein_contact_edges_undirected_{condition}.csv
contacts_perframe_{condition}.csv
edge_semantics.json
mania_manifest.json
mania_residue_library.json
```

Smoke preprocessing:

```bash
mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_full.yaml \
  --output mania_output/napi2b_smoke \
  --expected-condition normal \
  --expected-condition tumor \
  --contact-selection protein \
  --export-analysis-inputs \
  --max-frames 10 \
  --verbose
```

Full preprocessing:

```bash
mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_full.yaml \
  --output mania_output/napi2b_full \
  --expected-condition normal \
  --expected-condition tumor \
  --contact-selection protein \
  --export-analysis-inputs \
  --verbose
```

Analysis with PCA from the same root:

```bash
mania analyze \
  --input mania_output/napi2b_full \
  --output mania_output/napi2b_full \
  --condition normal \
  --condition tumor \
  --enable-pca
```

PCA-basis clustering is a separate explicit analysis choice:

```bash
mania analyze \
  --input mania_output/napi2b_full \
  --output mania_output/napi2b_full \
  --condition normal \
  --condition tumor \
  --enable-pca \
  --clustering-basis pca
```

This workflow uses CSV/JSON Stage 20 artifacts; `.npz` files are not required.
The preprocessing step reads `.tpr`/`.xtc`, computes contacts once, and
persists analysis-ready inputs so PCA, clustering, and later analysis options
can be rerun without recalculating raw trajectory contacts.

### Frame Sampling

By default, preprocessing computes every trajectory frame. Stage 16.2 adds
optional source-frame sampling for larger trajectories:

```text
--frame-start
--frame-stop
--frame-stride
--max-frames
```

`frame_stop` is exclusive, `max_frames` caps sampled frames after
start/stop/stride filtering, and sampled frame indexes preserve original source
frame indexes. `frame_time_ps` remains timing metadata/fallback between source
frames; it is not stride. Sampling affects Rg, contacts, graph outputs, and
optional scientific CSV exports. It does not change the WANIA object JSON
contract.

Frame sampling reduces the number of frames, not the cost of contacts inside
one sampled frame. With `--verbose`, contacts progress is also printed to
stderr. Optional local smoke/debug guards are available and are disabled by
default:

```text
--contact-max-residue-pairs-per-frame
--contact-max-distance-evaluations-per-frame
```

If a configured contact guard is exceeded, the workflow reports the issue in
the final JSON and exits non-zero rather than silently producing complete graph
artifacts from incomplete contacts.

### Contact Selection

Contacts use `contact_selection="all"` by default, preserving the existing
full-system residue behavior. Use `--contact-selection protein` to build a
protein residue-contact graph from `runtime_object.select_atoms("protein")`;
no NaPi2b-specific residue filtering or residue-name blacklist is used.

Frame sampling reduces the number of frames. `contact_selection` reduces the
per-frame candidate residue set. Contact limits remain optional smoke/debug
guards.

### Representative Cα Coordinates

Stage 16.5 adds condition-specific representative Cα coordinates to graph and
WANIA nodes as `x/y/z` and `x_ca/y_ca/z_ca`. The aliases `x/y/z` are for
frontend layout; `x_ca/y_ca/z_ca` retain the Cα meaning. Values come from the
first sampled frame, not a trajectory average, and do not claim full Kabsch
notebook parity.

Stage 16.6 adds structural `backbone` edges for sequential protein Cα nodes in
one condition and chain within 4.5 Å. `backbone` is the highest-priority edge
type, while overlapping contact types and metrics are preserved. Pure
backbone edges do not invent contact frequency. Broader notebook chemistry
parity remains deferred, and `typed_rin_interactions` remains false.

Stage 16.7 ports the notebook `InteractionAccumulator` idea into internal
backend contact aggregation. Sampled-frame frequency, distance aggregates,
and original first/last source frame indexes are finalized deterministically;
default scientific behavior and scientific CSV, graph, and WANIA schemas are
unchanged.

Stage 16.8 ports the notebook `build_atom_cache` idea as an internal contact
performance/refactor layer. After contact selection, stable residue metadata
and existing `heavy`/`all` filtered atom references are cached before frame
iteration; coordinates remain frame-specific. This adds no neighbor-search
backend and makes no benchmark or timing guarantee. Default scientific
behavior and output schemas, including the WANIA object JSON contract, remain
unchanged.

Stage 16.9 adds sampled-frame `backbone` observations to the optional
`contacts/contacts_perframe.csv` export for `contact_selection=protein` while
preserving original source frame indexes. Contact aggregates, graph backbone
priority, and the WANIA contract are unchanged. This is CSV semantic parity,
not parquet dependency or full temporal RIN parity.

Stage 16.10 adds canonical `aromatic_pi` and `cation_pi` chemistry without new
dependencies. Aromatic π–π uses ring centroids within the notebook's 7.0 Å
cutoff and sign-invariant best-fit-plane normal angles (parallel below 30°;
T-shaped 60°–120°). Cation-π uses LYS NZ or ARG CZ to ring-centroid distance
below 6.0 Å. Typed observations use the existing accumulator, sampled source
indexes, contact selection/limits, optional CSV exports, graph priority, and
WANIA edge-type preservation. Full typed/temporal RIN remains deferred; the
WANIA object JSON contract is unchanged.

Stage 16.11 adds a dependency-light Python API for condition-specific degree,
strength, betweenness, closeness, eigenvector, pagerank, kcore, and community
metrics over accepted `graph/graph.json` data. Numeric `contact_freq` drives
strength; absent or invalid weights contribute 0.0. NetworkX Louvain is
preferred where the accepted dependency boundary provides it; the current
boundary uses and reports deterministic greedy modularity as the fallback.
The explicit writer creates `analysis/metrics_<condition>.csv`,
`analysis/communities_<condition>.csv`, and
`analysis/analysis_metrics_report.json` without changing preprocessing graph
artifacts or CLI behavior. Existing node attributes and Cα coordinates are
preserved. Formal statistics, temporal RIN, conformational clustering,
figures, and YaDisk remain deferred, and the WANIA schema is unchanged.

Stage 16.12 provides the compact frontend-ready WANIA sample payload at
`tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json`. The fixture is
synthetic, deterministic, and safe for default CI. It demonstrates residue
identity, condition-specific `x/y/z` and `x_ca/y_ca/z_ca`, `backbone`,
`residue_contact`, `aromatic_pi`, `cation_pi`, primary/all interaction type
behavior, diagnostics, and relative analysis artifact references. It is not a
real-MD benchmark and is not an API response guarantee beyond the documented
payload contract. FastAPI/upload/job API remains future scope. Temporal RIN
remains future scope. Formal statistics remain future scope. Conformational
clustering remains future scope.

Stage 17.1 freezes the documented WANIA MVP frontend profile. The profile is
the stable frontend-facing subset of the WANIA object JSON payload, not the
full backend/scientific export and not a FastAPI/upload/job API contract. See
`docs/wania_mvp_contract_v0_1.md`. The Stage 16.12 sample remains a rich
illustrative payload rather than the minimal required MVP payload.

Stage 17.2 freezes the exact required fields and coordinate-based render
profile in `docs/wania_required_fields_contract_v0_1.md`. It adds only a
minimal fixture and contract tests; it does not add runtime validation or
change scientific, API, frontend, or CLI behavior.

Stage 17.3 defines the science-vs-UI layer boundary in
`docs/wania_science_ui_boundary_v0_1.md`. It separates stable display fields,
optional scientific annotations, backend-only implementation details, and
future capabilities without changing payload or runtime behavior.

Stage 18.1 defines the WANIA JSON assembly profile, Stage 18.2 validates its
artifact-to-payload mapping, and Stage 18.3 exposes that accepted mapping as a
one-command demo export. See `docs/wania_json_assembly_profile_v0_1.md`.

Stage 19 freezes the MANIA scientific MVP RIN scope before later
implementation and alignment work. WANIA MVP remains the accepted, stable
frontend-facing JSON contract for graph rendering; it is not the complete
MANIA scientific output format. Stage 19 is documentation-only. See
`docs/mania_rin_mvp_gap_matrix.md` and
`docs/mania_rin_mvp_scope_v0_1.md`.

## Build A Demo-Ready WANIA Payload

Build the frontend-facing WANIA MVP payload from the accepted synthetic graph
fixture and explicit run metadata:

```bash
mania wania build-payload \
  --graph-json tests/fixtures/wania_assembly_artifacts_v0_1/graph/graph.json \
  --output /tmp/wania_demo/wania_graph_payload.json \
  --run-name demo_wania_assembly \
  --protein-id demo_protein \
  --protein-name "Demo Protein" \
  --condition-name normal \
  --condition-name tumor
```

This creates `/tmp/wania_demo/wania_graph_payload.json`; alternatively,
`--output-dir /tmp/wania_demo` selects the directory and uses that fixed file
name. Required inputs are `graph/graph.json`, an output location, `run_name`,
`protein_id`, `protein_name`, and every graph condition name. A successful run
prints the output path, and the resulting valid JSON contains the Stage 17
run, capability, graph, artifact, and diagnostics fields. On a call it can
show condition-specific residue nodes and coordinates, graph edges and
interaction types, available capabilities, and diagnostics status.

The command is a thin wrapper over the accepted WANIA adapter/writer. It does
not require optional scientific artifacts and preserves optional fields that
the adapter supports when they are present in `graph/graph.json`. It does not
run FastAPI, a frontend, notebooks, MD processing, or new scientific
computation.

## Optional Scientific CSV Exports

By default, the Stage 15 CLI does not export Rg/contacts CSVs. They can be
exported with explicit optional flags after graph export succeeds.

These legacy flags are distinct from `--export-analysis-inputs`.
`--export-analysis-inputs` writes the root-level per-condition Stage 20 bundle
consumed directly by `mania analyze`. `--export-scientific-csvs` writes the
older optional side CSV subset under `rg/` and `contacts/`, and it does not
write the full analysis-ready bundle or run analysis.

Recommended safe shortcut:

```bash
mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_10ns.yaml \
  --output mania_output/napi2b_10ns \
  --verbose \
  --export-scientific-csvs
```

`--export-scientific-csvs` exports:

```text
rg/rg_timeseries.csv
contacts/contact_edges.csv
```

The shortcut does not export per-frame contacts.
contacts/contacts_perframe.csv is exported only when explicitly requested.
contacts_perframe.csv requires --export-contacts-perframe because it can be
large:

```bash
mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_10ns.yaml \
  --output mania_output/napi2b_10ns \
  --verbose \
  --export-scientific-csvs \
  --export-contacts-perframe
```

For protein selection, rows can include `backbone` alongside
`residue_contact`. Stage 16.10 also emits `aromatic_pi` and `cation_pi` rows
when detected. Frame indexes remain original trajectory source indexes;
`contact_selection` limits the exported residue scope.

Granular flags are also available:

```text
--export-rg-timeseries
--export-contact-edges
--export-contacts-perframe
```

Stage 13 `contact_edges.csv` is an aggregate contacts table. It is not the
backend graph edge table at `graph/edges.csv`.

## Outputs

Default output tree:

```text
mania_output/napi2b_10ns/
|-- graph/
|   |-- nodes.csv
|   |-- edges.csv
|   `-- graph.json
`-- reports/
    `-- graph_diagnostics_report.json
```

Expected Stage 15 graph output paths:

```text
graph/nodes.csv
graph/edges.csv
graph/graph.json
reports/graph_diagnostics_report.json
```

`reports/graph_reference_comparison.json` is produced only when reference
comparison is explicitly enabled and successful. Graph artifacts may exist even
if diagnostics fail. Inspect diagnostics failure details in the final JSON and,
when written, `reports/graph_diagnostics_report.json`.

Optional scientific CSV output tree when requested:

```text
mania_output/napi2b_10ns/
|-- graph/
|   |-- nodes.csv
|   |-- edges.csv
|   `-- graph.json
|-- rg/
|   `-- rg_timeseries.csv
|-- contacts/
|   |-- contact_edges.csv
|   `-- contacts_perframe.csv
`-- reports/
    `-- graph_diagnostics_report.json
```

`rg/` and `contacts/` appear only when the corresponding optional CSV export
flags are requested.

## What Is Not Produced Yet

The Stage 15 workflow CLI still does not produce:

```text
temporal RIN artifacts
WANIA/frontend API payloads through the workflow CLI
```

Rg and contacts are computed in memory for graph export. Optional Rg/contact
CSVs are side-effect scientific exports, not WANIA/frontend API payloads.

Stage 16.1 adds a Python adapter that can build a WANIA object JSON payload
from existing Stage 15 artifacts and explicit protein/run metadata. The
adapter writes `wania_graph_payload.json`; Stage 18.3 makes that accepted
adapter/writer available through `mania wania build-payload`. Neither stage
adds FastAPI, an upload/job API, frontend implementation, or new scientific
computation.

## Data And Git Boundaries

Local raw data and generated outputs must remain local and must not be
committed:

```text
local_md/
local_md_protein/
mania_output/
*.tpr
*.xtc
*.gro
*.cpt
*.edr
*.log
*.dcd
*.psf
```

Generated local outputs should not be committed. This README documents the
boundary only; it does not change `.gitignore`.

## Future Scope

Stage 15 `graph/graph.json` remains backend graph workflow output and should
not be assumed to be frontend-ready. The separate WANIA MVP JSON contract is
accepted and stable for frontend graph rendering.

Stage 16.0 documents the future WANIA object JSON payload contract. The
contract is object JSON, protein-agnostic, and separate from backend
`graph/graph.json`.

Stage 16.1 adds a Python adapter for that WANIA object JSON payload. The
adapter consumes accepted Stage 15 artifacts and does not change backend
`graph/graph.json`.

Stage 16.12 adds a stable synthetic payload sample for frontend fixture and
contract review. It does not add frontend implementation or an API endpoint.

The planning-level scientific roadmap is:

- **Stage 19 — MANIA RIN MVP scope freeze:** documentation only.
- **Stage 20 — RIN preprocessing parity.**
- **Stage 21 — RIN analysis parity.**
- **Stage 22 — Temporal RIN + conformational artifacts.**
- **Stage 23 — WANIA RIN alignment.**
- **Stage 24.A — Optional computed PCA with direct NumPy dependency.**
- **Stage 24.B — Optional explicit PCA-based clustering mode.**
- **Stage 24.C — Analysis orchestration CLI.**
- **Stage 24.D — MANIA-only `analysis/extended_metrics.json` manifest.**
- **Stage 24.E — Validation, documentation, and Stage 24 acceptance.**
- **Stage 24.F — PCA provenance, failure semantics, and internal component
  capacity correction.**
- **Stage 25 — Reproducibility and publication hardening:** Stage 25.A software
  identity, Stage 25.B run provenance, and Stage 25.C artifact inventory are
  complete. Stage 25.D unified technical artifact validation is complete.
  Stage 25.E observation-only PBC audit and runtime metadata is complete.
  Stage 25.F reproducibility documentation and FAIR² bridge is complete.
  Stage 25.G final technical-hardening acceptance is complete;
  Stage 25 is complete.
- **Stage 26 — Dataset identity and authoritative execution binding:** complete;
  technical context, input lineage, validation, and scientific byte regression.
- **Stage 27 — Physical-time sampling/window engine:** complete; accepted sampling
  and window plans drive exact preprocessing frame execution and temporal evidence.
- **Stage 28 — Contact episodes/lifetime/publication protein-edge tables:** next;
  not started.

The Stage 19 scope freeze originally recorded Stages 20–23 as future work.
Stages 20–23 are now complete within their accepted boundaries. Stage 24.A
adds opt-in computed PCA, Stage 24.B adds opt-in PCA clustering without
changing WANIA or fingerprint clustering defaults, Stage 24.C wires the
accepted preprocessing-input-to-analysis-artifact workflow through
`mania analyze`, Stage 24.D writes the MANIA-only manifest, Stage 24.E
validates the integrated Stage 24 workflow, and Stage 24.F closes the PCA
provenance/failure/component-capacity corrections.
FastAPI/upload and job APIs, Docker/demo packaging, database models,
production API serving, and frontend implementation remain postponed and
require separate scope approval.

## Documentation

- `docs/notebook_parity_audit_v1_3.md`: Stage 16 notebook-to-backend parity
  matrices, intentional differences, deferred scope, and optional validation.
- `docs/preprocessing_graph_workflow_boundary_before_frontend_api.md`: accepted
  Stage 15 backend workflow boundary.
- `docs/wania_api_protein_agnostic_boundary.md`: protein-agnostic Stage 16+
  API/run boundary.
- `docs/wania_object_json_payload_contract.md`: future WANIA object JSON
  payload contract, separate from backend `graph/graph.json`.
- `docs/wania_mvp_contract_v0_1.md`: stable frontend-facing WANIA MVP profile,
  including required, optional, backend-only, and future classifications.
- `docs/wania_required_fields_contract_v0_1.md`: exact required WANIA MVP
  fields and minimal valid payload rules.
- `docs/wania_science_ui_boundary_v0_1.md`: science-vs-UI layer ownership for
  display fields, optional science, backend internals, future capability, and
  the complete Stage 23 WANIA RIN alignment and acceptance checklist.
- `docs/wania_json_assembly_profile_v0_1.md`: Stage 18.1 inputs, demo-ready
  output expectations, portable references, and Stage 17 alignment.
- `docs/mania_rin_mvp_gap_matrix.md`: Stage 19.1 inventory of RIN requirements,
  repository evidence, coverage, and unresolved naming/contract gaps.
- `docs/mania_rin_mvp_scope_v0_1.md`: Stage 19.2 MANIA scientific MVP scope
  freeze, WANIA boundary, planning-level ownership, and the completed Stage 24
  acceptance checklist.
- `docs/preprocessing_graph_workflow_contract.md`: workflow APIs, options, and
  output layout.
- `docs/local_scientific_integration_tests.md`: local-only real MD smoke test
  boundary.
- `docs/architecture.md`: intended package architecture.
- `AGENTS.md`: working rules for Codex, coding agents, and assistants.
