# MANIA RIN MVP scientific scope v0.1

## 1. Purpose

This document freezes the scientific scope of the MANIA residue interaction
network (RIN) MVP before implementation work begins. It is the Stage 19.2
scope decision, not an implementation specification. It separates the MANIA
scientific artifacts from the accepted WANIA frontend payload and records
which capabilities are already covered, later MVP targets, optional science,
backend-only details, or v2/future work.

Stage 19 remains documentation-only. A capability classified as an MVP target
is authorized for planning in the mapped later stage; it is not claimed as
implemented by this document.

## 2. Source inputs

The main input is `docs/mania_rin_mvp_gap_matrix.md`. Its evidence and status
rules control every coverage claim in this scope freeze.

The following accepted documents were inspected only to preserve existing
boundaries and terminology:

- `docs/wania_mvp_contract_v0_1.md`;
- `docs/wania_object_json_payload_contract.md`;
- `docs/wania_required_fields_contract_v0_1.md`;
- `docs/wania_science_ui_boundary_v0_1.md`;
- `docs/wania_json_assembly_profile_v0_1.md`;
- `docs/notebook_parity_audit_v1_3.md`;
- `README.md`.

Repository notebooks and historical exports are reference/specification
evidence only. Their presence does not prove production coverage. Production
coverage requires the source, tests, or accepted current contract evidence
identified by the Stage 19.1 gap matrix.

## 3. Definitions

This document uses two independent dimensions: implementation status and
scope category.

| Implementation status | Meaning |
| --- | --- |
| **Already covered** | Stage 19.1 identifies concrete production or accepted-contract evidence for the requirement. |
| **Partially covered** | Related production behavior exists, but computation, integration, semantics, naming, or layout remains incomplete. |
| **MVP target for future implementation** | The capability belongs to the scientific MVP, but a later mapped stage must specify and implement the missing behavior. |
| **Unclear / needs confirmation** | The intended shape, ownership, naming, or semantics cannot yet be frozen safely. |
| **Not implemented** | Only reference intent, historical output, or a planned schema exists. |

| Scope category | Meaning |
| --- | --- |
| **MANIA scientific MVP** | Backend scientific data or analysis required for the complete RIN MVP roadmap. It is not automatically a WANIA requirement. |
| **Optional scientific artifact** | Useful scientific enrichment whose absence does not make the MANIA or WANIA MVP invalid. |
| **WANIA frontend payload MVP** | The already accepted minimum frontend-facing render and status contract. |
| **Backend-only/internal** | Scientific implementation, provenance, validation, or artifact detail that the frontend must not depend on. |
| **v2 / future scope** | Outside the RIN MVP roadmap and subject to a separate scope decision. |
| **Out of Stage 19** | Implementation, schema changes, and product work forbidden during this documentation stage. |

“MVP target” never means “already covered.” Optional MANIA artifacts may be
referenced by WANIA, but their rows and fields do not thereby become frontend
state.

## 4. MANIA scientific MVP scope

### 4.1 RIN preprocessing artifacts

| Capability or artifact | Frozen scope | Coverage at Stage 19.2 | Later-stage intent |
| --- | --- | --- | --- |
| Residue table export and residue identity | MANIA scientific MVP | **Covered at the Stage 20.A baseline.** The public preprocessing writer emits per-condition `residue_table_{cond}.csv` files from the accepted graph mapping while preserving `graph/nodes.csv` as a separate artifact. | Later Stage 20 work may add computed attributes, but must preserve this identity and naming baseline. |
| Residue structural attributes | MANIA scientific MVP | **Partially covered.** Accepted columns can be preserved, but the missing attributes are not generally computed. | Stage 20 target, feature by feature, with provenance and units specified. |
| Protein-protein contact edge export | MANIA scientific MVP | **Covered at the Stage 20.B baseline and extended at Stage 20.C.** The public preprocessing writer emits per-condition `protein_contact_edges_undirected_{cond}.csv` files for results computed with `contact_selection="protein"`, including available typed protein interactions. Existing `graph/edges.csv` and `contacts/contact_edges.csv` remain separate artifacts. | Preserve the Stage 20.B schema and aggregation semantics. |
| Edge frequency and distance aggregation | MANIA scientific MVP | **Covered at the Stage 20.B baseline** by the accepted interaction accumulator: contact frequency uses sampled frames, and distance summaries use population standard deviation over one normalized observation per contacting frame and edge type. | Preserve these semantics in later parity work. |
| Per-frame contacts artifact | MANIA scientific MVP | **Covered at the Stage 20.B CSV baseline.** The per-condition artifact is `contacts_perframe_{cond}.csv` and preserves source frame indexes, residue identity, edge type, and distance in Å. | `contacts_perframe` is the accepted spelling; `contacts_per_frame` and parquet remain explicit non-baseline alternatives. |
| Static RIN graph export | MANIA scientific MVP | **Already covered** as backend `graph/graph.json`; it is distinct from the WANIA payload. | Preserve the backend/frontend separation. |
| Rg time series | MANIA scientific MVP supporting artifact | **Partially covered** relative to notebook naming, but the scientific CSV is implemented at `rg/rg_timeseries.csv`. | Preserve the accepted backend artifact; naming parity remains a Stage 20 decision. |
| Edge semantics manifest | MANIA scientific MVP | **Covered at Stage 20.D.** The deterministic `edge_semantics.json` writer reports the implemented Stage 20.C protein-only vocabulary, criteria, limitations, overlap, and central priority order. | Preserve it as descriptive metadata; do not promote deferred non-protein chemistry. |
| MANIA run manifest export | Backend-only/internal | **Covered at Stage 20.D.** `mania_manifest.json` records available Stage 20.A/B/D artifacts using portable filenames and leaves unavailable run provenance explicitly null. | This remains optional backend provenance, not a WANIA render field. |
| Residue library / QC artifact | Backend-only/internal | **Covered at Stage 20.D.** `mania_residue_library.json` records the Stage 20.A identity inventory, missing values, and deterministic identity-conflict QC. | It is per-run QC, not a biological residue database or non-protein inventory. |
| Non-protein node inventory | Optional scientific artifact | **Explicitly deferred at Stage 20.E.** `non_protein_nodes_{cond}.csv` is not emitted. Notebook/reference naming is `nonprotein_nodes_{condition}.csv`, but production has no accepted non-protein identity or classification contract. | A later explicit scope must accept identity, inclusion, and naming before implementation. |
| Protein–non-protein edge inventory | Optional scientific artifact | **Explicitly deferred at Stage 20.E.** `np_contact_edges_{cond}.csv` is not emitted. Current contact results do not preserve protein/non-protein membership or a mapping from mixed-selection indexes to Stage 20.A protein identity. | Never required for the WANIA base graph; a later explicit scope must accept mixed-contact identity and semantics. |

The immediate protein RIN scientific baseline therefore consists of residue
identity/structural tables, protein contact edges, contact aggregation,
per-frame observations, the static graph, and explicit semantics/provenance.
Optional heterograph inventories do not block that baseline.

#### Stage 20.F validation and alignment

Stage 20.F consolidates, rather than expands, the accepted preprocessing
baseline. Synthetic contract tests write the Stage 20.A/B/D artifacts together
and validate their schemas, cross-artifact residue identity, sampled-frame
aggregation, deterministic ordering and bytes, portable manifest references,
protein-only semantics vocabulary, residue-library missing/conflict behavior,
and Stage 20.E deferral. No accepted artifact schema or scientific computation
is changed. Stage 21 analysis parity, temporal RIN, non-protein inventory, full
heterograph support, and WANIA typed-RIN schema work remain unimplemented.

#### Stage 20.E optional non-protein inventory deferral

Stage 20.E chooses explicit deferral rather than a false implementation. The
current runtime can select either all residues or protein residues, but the
resulting contact records do not retain endpoint membership as protein or
non-protein. Residue indexes are local to the selected residue collection, so
an all-residue result does not provide a reliable mapping back to the accepted
Stage 20.A protein residue identity. The repository also has no deterministic
production contract for excluding solvent/ions or classifying a non-protein
residue as lipid, glycan, ligand, or another biological entity.

Consequently, production emits neither `non_protein_nodes_{cond}.csv` nor
`np_contact_edges_{cond}.csv`. `mania_manifest.json` lists produced artifacts
only and does not advertise either artifact as implemented. The deferred
`protein_lipid`, `protein_glycan`, `glycan_anchor`, and `protein_ligand` names
remain unimplemented; no generic contact is silently promoted to one of those
semantics. This decision does not change the protein RIN baseline or any WANIA
field, capability, coordinate, or rendering requirement.

#### Stage 20.A residue table baseline

`write_preprocessing_residue_tables_csv(mapping_result, output_dir)` writes one
root-level `residue_table_{cond}.csv` for every condition represented by the
accepted preprocessing graph mapping. The original condition value remains in
the `condition` column; only unsafe filename characters are normalized, and
colliding normalized names fail deterministically. This is a new explicit
artifact, not a silent alias for `graph/nodes.csv`.

The fixed Stage 20.A columns are:

```text
condition,residue_index,resid,resname,segment_id,region,x_ca,y_ca,z_ca,tm_relative_z,rmsf_A,sasa_A2,ss
```

`residue_index` is the zero-based runtime residue index, `resid` is the source
residue identifier, and `segment_id` preserves the available segment/chain
identity. This resolves the current composite graph-node `resid` mismatch
without changing `graph/nodes.csv`. `ss` retains the existing backend name for
the potential DSSP-derived value; it does not claim DSSP computation.

`x_ca/y_ca/z_ca` preserve the optional scientific Cα values already carried by
the graph mapping. In the current production mapping they are representative
coordinates from the first sampled frame. They are not WANIA render `x/y/z`,
and the writer does not create render coordinates. Unavailable segment,
coordinate, and structural values are emitted as empty CSV fields. `region`,
`tm_relative_z`, `rmsf_A`, `sasa_A2`, and `ss` are fixed baseline columns but
remain empty because the current mapping does not compute or carry those
attributes. Phi/psi and graph-level Rg summaries are not added at this stage;
their computation and ownership remain later explicit decisions.

#### Stage 20.B protein contact artifact baseline

`write_preprocessing_protein_contact_artifacts_csv(contacts_result,
output_dir)` consumes accepted condition or manifest contact results whose
selection is explicitly `protein`. It writes one root-level artifact pair per
condition:

```text
protein_contact_edges_undirected_{cond}.csv
contacts_perframe_{cond}.csv
```

The edge columns are:

```text
condition,residue_index_i,resid_i,resname_i,segment_id_i,residue_index_j,resid_j,resname_j,segment_id_j,edge_type,contact_frame_count,sampled_frame_count,contact_freq,mean_dist_A,std_dist_A,weight
```

The per-frame columns are:

```text
condition,frame_index,time_ps,residue_index_i,resid_i,resname_i,segment_id_i,residue_index_j,resid_j,resname_j,segment_id_j,edge_type,distance_A
```

Endpoint ordering is undirected and deterministic by `residue_index`.
`condition` plus `residue_index_i/j` identifies the same zero-based runtime
residues as Stage 20.A; source `resid`, `resname`, and `segment_id` are retained
to make that mapping explicit. A reused residue index with conflicting source
identity fails export.

For each condition and edge type, `contact_freq` is the number of sampled
frames containing the normalized pair divided by all sampled frames in that
condition. Duplicate observations of the same pair/type in one frame retain
the minimum distance. `mean_dist_A` and `std_dist_A` use those per-contacting-
frame distances; `std_dist_A` is the population standard deviation (`ddof=0`).
The persisted `weight` equals `contact_freq`.

This per-condition CSV pair is an explicit Stage 20.B artifact, not an alias
for the older combined `contacts/contact_edges.csv` and
`contacts/contacts_perframe.csv`, whose schemas and layout remain unchanged.
The accepted Stage 20.B spelling is `contacts_perframe` (without the second
underscore); no parquet dependency or `contacts_per_frame` artifact is added.
Stage 20.B itself introduced no new contact chemistry. Stage 20.C now feeds
typed protein observations through this unchanged schema and aggregation path.

#### Stage 20.C protein RIN edge semantics

The sampled-frame protein contact pipeline now detects `hbond`, `disulfide`,
`vdw`, `hydrophobic`, `ionic`, and `salt_bridge` alongside the existing
`residue_contact`, `aromatic_pi`, and `cation_pi` observations. Overlapping
types remain separate per-frame and aggregate observations. Graph export uses
the single `EDGE_TYPE_PRIORITY` order and preserves all types; `backbone` is
highest and `residue_contact` is the final generic fallback.

The accepted backend criteria are:

- `hbond`: N/O donor-to-N/O acceptor distance at most 3.5 Å and explicit
  D–H···A angle at least 120°. The runtime topology must expose the donor's
  bonded hydrogen through `atom.bonds`; missing hydrogen or bond data is
  skipped, and no position or distance-only fallback is invented.
- `disulfide`: CYS SG–SG distance at most 2.2 Å.
- `vdw`: the residue-pair minimum heavy-atom distance is from 3.0 through
  4.5 Å, inclusive.
- `hydrophobic`: CB–CB distance at most 5.0 Å for ALA, VAL, ILE, LEU, MET,
  PHE, TRP, PRO, or TYR pairs. Missing CB atoms are skipped.
- `ionic`: minimum supported charged-atom distance at most 6.0 Å. Positive
  atoms are LYS NZ, ARG NH1/NH2, and HIS/HID/HIE/HIP ND1/NE2; negative atoms
  are ASP OD1/OD2 and GLU OE1/OE2.
- `salt_bridge`: minimum charged donor/acceptor atom distance at most 4.0 Å,
  restricted to LYS NZ or ARG NH1/NH2 against ASP OD1/OD2 or GLU OE1/OE2.
  It is a distinct, potentially overlapping annotation rather than an alias
  for `ionic`; histidine variants are not salt-bridge donors in this backend
  criterion.

These are backend/scientific annotations. They do not change the WANIA JSON
contract, required payload fields, render coordinates, or capability flags.

### 4.2 RIN edge semantics

| Edge semantic | Frozen scope | Coverage at Stage 19.2 |
| --- | --- | --- |
| `backbone` | MANIA scientific MVP | **Already covered** with backend-specific representative-Cα semantics. |
| `aromatic_pi` | MANIA scientific MVP | **Already covered** with accepted backend-specific geometry. |
| `cation_pi` | MANIA scientific MVP | **Already covered** with accepted backend-specific geometry. |
| `hbond` | MANIA scientific MVP | **Covered at Stage 20.C with an explicit-hydrogen limitation.** Production detection requires topology-provided donor–hydrogen bonding and applies the accepted distance and angle cutoffs; it does not use the notebook's distance-only fallback. |
| `disulfide` | MANIA scientific MVP | **Covered at Stage 20.C** by CYS SG–SG distance detection. |
| `vdw` | MANIA scientific MVP | **Covered at Stage 20.C** by the protein residue-pair minimum heavy-atom distance window. |
| `hydrophobic` | MANIA scientific MVP | **Covered at Stage 20.C** for the accepted residue set when both CB atoms are present. |
| `ionic` | MANIA scientific MVP | **Covered at Stage 20.C** with explicit positive and negative residue atom groups. |
| `salt_bridge` | MANIA scientific MVP | **Covered at Stage 20.C** as a narrower charged donor/acceptor group criterion distinct from, and allowed to overlap with, `ionic`. |
| `protein_lipid` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |
| `protein_glycan` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |
| `glycan_anchor` | Optional scientific artifact | **Not implemented.** Reference-only evidence; anchor semantics require confirmation. |
| `protein_ligand` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |

Stage 20.C freezes the protein atom selections, cutoffs, and overlap behavior
above. It does not claim full notebook or frontend typed-RIN support. Specific
interaction values remain optional scientific annotations in WANIA even when
MANIA can compute them.

### 4.3 Node attributes and coordinate roles

| Attribute | Frozen scope and coverage |
| --- | --- |
| `resid`, `resname` | MANIA scientific MVP; **already covered** in production node export and adapted into WANIA residue identity. |
| `region` | MANIA scientific MVP; **partially covered** because it is preserved when present but not populated by a production classifier. Stage 20 target. |
| `rmsf`, `sasa` | MANIA scientific MVP; **partially covered** as preserved unit-bearing backend fields (`rmsf_A`, `sasa_A2`), but production computation is missing. Stage 20 target. |
| `dssp` | MANIA scientific MVP; **partially covered** as backend `ss`; production computation and canonical naming are missing. Stage 20 target. |
| `tm_relative_z` | MANIA scientific MVP; **partially covered** because an export slot exists but production calculation is missing. Stage 20 target. |
| `phi/psi` | Optional scientific artifact; **not implemented** and representation is undecided. |
| `rg_mean`, `rg_std` | Optional scientific artifact; **unclear / needs confirmation** because notebook evidence treats these as graph-level values while backend prose uses unit-bearing `rg_mean_A` and `rg_std_A`. They must not be treated as node fields without a later decision. |
| `x/y/z` | WANIA frontend payload MVP; **already covered** as required frontend-facing render coordinates. They do not assert alignment, averaging, or scientific-coordinate provenance. |
| `x_ca/y_ca/z_ca` | MANIA scientific MVP provenance and optional WANIA enrichment; **already covered** as representative, condition-specific Cα coordinates from the first sampled frame. Full Kabsch or trajectory-average parity is not claimed. |

Scientific coordinate provenance belongs to MANIA artifacts and metadata.
Frontend layout/render use belongs to WANIA. Kabsch-aligned or cross-condition
coordinate reconciliation is v2/future scope unless separately accepted.

### 4.4 Edge attributes

| Attribute | Frozen scope and coverage |
| --- | --- |
| `res_i`, `res_j` | MANIA scientific MVP identity concept; **partially covered** under backend `resid_i`/`resid_j`. The requested names are not silently accepted as aliases. |
| `edge_type` | MANIA scientific MVP; **already covered** as the backend primary type. WANIA maps the concept to `interaction.primary_type` and must not gain a parallel required field. |
| `contact_freq` | MANIA scientific MVP; **already covered** for contact-derived edges. Pure structural backbone edges may legitimately lack it. |
| `mean_dist_A`, `std_dist_A` | MANIA scientific MVP; **already covered** for aggregated contact observations. |
| `condition` | MANIA scientific MVP and WANIA frontend payload MVP; **already covered** in both layers. |
| `weight = contact_freq` | MANIA scientific analysis rule; **partially covered** as the default analysis interpretation, not as a separate persisted `weight` field. No duplicate edge column is required by this freeze. |

For WANIA base rendering, edge identity/endpoints, `condition`, and
`interaction.primary_type` remain the accepted fields. MANIA names such as
`res_i`, `res_j`, `contact_freq`, `mean_dist_A`, `std_dist_A`, and a derived
weight are not required WANIA render fields. Contact frequency and distance
summaries may remain optional WANIA enrichment.

### 4.5 RIN analysis artifacts and metrics

| Capability or metric | Frozen scope | Coverage at Stage 19.2 |
| --- | --- | --- |
| Static RIN graph input/export | MANIA scientific MVP | **Covered at the Stage 21.A analysis baseline.** `src/mania/analysis/static_rin_graph.py` builds a per-condition analysis graph directly from accepted Stage 20 residue/contact artifacts. The older backend `graph/graph.json` remains a separate accepted workflow artifact. |
| `degree`, `strength`, `betweenness`, `closeness`, `eigenvector`, `pagerank` | MANIA scientific MVP | **Covered for the Stage 21.A graph by Stage 21.B.** `src/mania/analysis/static_rin_metrics.py` consumes the accepted static graph directly. |
| Weighted graph baseline | MANIA scientific MVP | **Covered for Stage 21.B strength.** Available numeric `weight = contact_freq` values are summed; path metrics remain unweighted. |
| `k_core` | MANIA scientific MVP | **Covered under the accepted production spelling `kcore`.** |
| `community` | MANIA scientific MVP | **Covered for the Stage 21.A graph by Stage 21.C.** The dependency-free implementation reports deterministic unweighted greedy modularity as a fallback, not Louvain. |
| `modularity` | MANIA scientific MVP | **Covered for the Stage 21.A graph by Stage 21.C.** The deterministic unweighted value is repeated in the community artifact rows. |
| `centrality_{cond}.csv` | MANIA scientific MVP artifact concept | **Covered for the Stage 21.B static graph** as deterministic `centrality_{condition}.csv`; the older `analysis/metrics_<condition>.csv` remains a separate legacy analysis path. |
| `communities_{cond}.csv` | MANIA scientific MVP artifact | **Covered for the Stage 21.A graph by Stage 21.C** as deterministic `communities_{condition}.csv`; the older analysis output remains a separate legacy path. |
| Cross-condition comparison, `stats.csv`, `comparison.csv` | MANIA scientific MVP | **Covered for accepted Stage 21.B node metrics by Stage 21.E.** Stable residue identity is matched across lexical condition pairs; unsafe rows and scopes are explicitly skipped. |
| `MWU`, `FDR-BH`, `Cohen's d`, Bootstrap CI | MANIA scientific MVP | **Partially covered by Stage 21.E.** Cohen's dz is computed from complete paired differences when sample variance is defined. MWU, bootstrap CI, p-values, and FDR-BH remain unimplemented; correction is explicitly `none`. |
| `NMI`, `ARI` | Optional scientific artifact | **Not implemented.** Requires an explicit within-run cross-condition node/partition mapping contract. |
| Region/community enrichment and Fisher enrichment | Optional scientific artifact | **Covered for existing Stage 21.A region labels by Stage 21.D.** Missing labels and insufficient margins produce explicit skipped rows; no biological region mapping is inferred. |

Metrics, communities, comparison tables, statistics, and enrichment outputs
are separate MANIA scientific artifacts. They do not become required node,
edge, or top-level fields in `wania_graph_payload.json`. Cross-protein
comparison is not the cross-condition comparison targeted here and remains
v2/future scope.

#### Stage 21.A static analysis graph baseline

`build_static_rin_graph(...)` consumes one condition's accepted
`residue_table_{cond}.csv` and
`protein_contact_edges_undirected_{cond}.csv`. Optional references to
`edge_semantics.json`, `mania_manifest.json`, and
`mania_residue_library.json` are validated and retained as portable filenames.
It emits deterministic Stage 20.A residue nodes and one normalized undirected
edge per Stage 20.B residue pair. Analysis node IDs use
`{condition}:{residue_index}` and retain source `resid`, `resname`, and
`segment_id` as separate identity fields.

When a pair has multiple Stage 20.C interaction rows, the central
`EDGE_TYPE_PRIORITY` selects the primary type while `all_edge_types` and the
complete per-type aggregate records remain available. The primary aggregate's
`contact_freq` is also the stored `weight`; when frequency is unavailable both
fields are null. No metric is computed from that weight in Stage 21.A. The
portable JSON target is a per-condition analysis `graph.json`, for example
`analysis/normal/graph.json`.

This is a MANIA backend/scientific artifact, not the WANIA frontend payload.
It changes neither Stage 20 artifact schemas nor WANIA required fields,
coordinates, or rendering semantics. Centrality, weighted metrics,
communities, enrichment, cross-condition comparison, statistics, temporal RIN,
and conformation artifacts remain outside Stage 21.A.

#### Stage 21.B static centrality and weighted metrics

Stage 21.B consumes the accepted Stage 21.A `StaticRinGraph` or its exported
`graph.json`, preserving condition, node IDs, and residue identity. It exports
stable `centrality_{condition}.csv` rows ordered by `residue_index`, using the
existing `kcore` spelling. Degree, betweenness, closeness, eigenvector,
PageRank, and core number use graph topology. Betweenness and closeness are
unweighted; `contact_freq` is a strength rather than a distance.

Strength sums only valid numeric incident `weight = contact_freq` values. An
isolated node has degree and strength zero. A non-isolated node with no numeric
incident weights has missing strength; with mixed weighted and missing edges,
its strength is the sum of the available numeric weights. Iterative metric
non-convergence is represented by a missing value. Stage 21.B does not change
the Stage 21.A graph or WANIA contracts and does not implement communities,
enrichment, comparison, statistics, temporal RIN, or conformation artifacts.

#### Stage 21.C static communities and community quality

Stage 21.C consumes the same accepted Stage 21.A `StaticRinGraph` or exported
`graph.json`, preserving condition, node ID, residue identity, and the graph's
edge topology. Louvain is unavailable inside the accepted dependency
boundary, so Stage 21.C uses and reports
`greedy_modularity_unweighted`. It does not label the fallback as Louvain and
does not add a dependency.

Community detection and modularity are unweighted. Thus `contact_freq`
remains scientific contact strength and is never interpreted as distance or
filled when missing. Stable tie-breaking uses Stage 21.A residue identity;
community IDs are one-based and ordered by minimum residue identity. Isolates
form deterministic singleton communities.

The deterministic `communities_{condition}.csv` contains condition, Stage
21.A node identity, community ID and size, the actual algorithm name,
modularity, and community count. It is a MANIA backend/scientific artifact,
not a WANIA contract change. Stage 21.C does not implement region enrichment,
cross-condition comparison or statistics, NMI/ARI, temporal RIN, or
conformation analysis.

#### Stage 21.D static region enrichment

Stage 21.D joins accepted Stage 21.A node identity and existing `region`
labels to accepted Stage 21.C community assignments. It emits deterministic
`region_enrichment_{condition}.csv` rows ordered by community and region. The
2x2 table is defined over labeled nodes only; missing labels are excluded and
are never converted into a biological category or inferred from residue
numbers.

When both community groups and both region margins are available, Stage 21.D
reports a dependency-free two-sided Fisher exact raw p-value with method and
status metadata. Empty graphs, absent labels, one-community graphs, and
insufficient margins instead receive explicit skipped statuses and no invented
p-value. This optional MANIA scientific artifact does not change the WANIA
payload and does not implement Stage 21.E cross-condition comparison,
multiple-testing correction, temporal RIN, or conformation analysis.

#### Stage 21.E cross-condition comparison and statistical outputs

Stage 21.E consumes accepted Stage 21.B `centrality_{condition}.csv` artifacts
without rebuilding graph or metric semantics. Conditions are ordered
lexically and every deterministic pair is compared. A node matches only by the
complete accepted residue identity `(residue_index, resid, resname,
segment_id)`; row order and condition-specific `node_id` values are not
cross-condition keys. Conflicting identity at a shared residue index blocks
statistics for that pair.

Root-level `comparison.csv` records each accepted Stage 21.B metric for exact,
missing, unmatched, and conflicting identities. Missing values are never
replaced by zero. Root-level `stats.csv` reports matched, unmatched, and
missing-metric counts; the supported methods are paired mean delta and Cohen's
dz over complete paired differences. Insufficient observations and zero
paired-difference sample variance produce explicit skipped statuses.

No p-value method is introduced, so raw and adjusted p-values remain missing
and correction is recorded as `none`; MWU, bootstrap CI, and FDR-BH remain
deferred. Edge comparison does not treat absent edges as zero, condition-local
community IDs are not matched, and region enrichment is not compared through
those IDs. These scopes receive deterministic unsupported-scope rows. This is
a dependency-free MANIA backend/scientific artifact and does not alter the
WANIA contract. Stage 21.F validation is described separately below; temporal
RIN and conformation work remain unimplemented.

#### Stage 21.F analysis validation and docs/tests alignment

Stage 21.F is a consolidation pass over the accepted Stage 21.A–21.E
artifacts. Focused synthetic contract tests validate fixed schemas,
deterministic bytes and ordering, graph/centrality/community node identity,
region/community references, comparison identity provenance, and statistical
method/status rows. The tests also preserve truthful skipped behavior: the
Stage 21.C fallback remains `greedy_modularity_unweighted`, Stage 21.D uses
only existing non-empty graph region labels and raw Fisher p-values, and Stage
21.E retains empty p-value fields, `correction = none`, and explicit
`skipped_unsupported_scope` rows.

No production analysis algorithm or accepted artifact schema changes in Stage
21.F. The accepted WANIA JSON contract remains unchanged. Stage 22 temporal
RIN is not implemented. Conformation/PCA/k-means/silhouette artifacts are not
implemented. WANIA typed-RIN schema is not implemented. Full
heterograph/non-protein inventory is not implemented.

### 4.6 Temporal RIN and conformation artifacts

| Capability or artifact | Frozen scope | Coverage at Stage 19.2 |
| --- | --- | --- |
| Temporal RIN input contract | MANIA scientific MVP | **Stage 22.A covered.** The dependency-free loader consumes accepted `contacts_perframe_{condition}.csv`, validates condition/frame/residue-pair/edge-type identity, normalizes undirected pairs, rejects duplicate frame/pair/type keys, and treats only observed sorted frame indexes as sampled frames. |
| Sliding-window configuration (`TEMP_WINDOW`, `TEMP_STEP`, `TEMP_MIN_FREQ`) | MANIA scientific MVP | **Stage 22.A covered.** Accepted defaults are `10`, `10`, and `0.25`; windows use zero-based IDs, ordinal sampled-frame membership, inclusive first/last source-frame boundaries, and non-empty partial trailing windows. Later window contact frequency uses `sampled_frame_count` as its denominator. |
| Window-level contact frequency | MANIA scientific MVP | **Stage 22.B covered.** Validated observations are grouped per accepted sampled-frame window, normalized pair, and type. Frequency uses `observed sampled frames / sampled_frame_count`; inclusive `TEMP_MIN_FREQ` filtering applies only to typed-contact inclusion. |
| Window-level RIN construction / `temporal_rin_{cond}.csv` | MANIA scientific MVP | **Stage 22.B covers internal graph construction and Stage 22.C covers the public summary export.** Passing types are priority ordered, the primary type supplies edge weight, available distances receive deterministic summaries, and empty windows remain explicit. Stage 22.C writes one deterministic row per accepted window to `analysis/{condition}/temporal_rin_{condition}.csv`. |
| Temporal graph metrics | MANIA scientific MVP | **Stage 22.C covered.** Counts, density, mean degree, mean strength, unweighted betweenness/closeness summaries, and deterministic unweighted community/modularity summaries are computed from accepted Stage 22.B graphs. Empty/no-passing windows remain explicit with missing derived metrics. |
| Contact fingerprint matrix | MANIA scientific MVP | **Stage 22.D covered as an internal representation.** Accepted Stage 22.A per-frame observations become sampled-frame rows and normalized pair/type columns in deterministic order. Values are binary observed/not-observed membership; no public artifact is added. |
| PCA projection | MANIA scientific MVP | **Stage 24.A optional computed PCA covered.** Stage 22.E established the no-fake-coordinate artifact contract. Stage 24.A approves NumPy as a direct dependency and computes centered SVD PCA only when explicitly enabled with `enable_pca=True`; the default remains disabled and preserves blank unavailable fields. |
| k-means and silhouette selection | MANIA scientific MVP | **Stage 22.F covered from fingerprints.** Deterministic dependency-free k-means consumes binary contact fingerprint values directly. Candidate `k` values are bounded by frame count and the default maximum of 10; only valid label sets receive Euclidean silhouette scores, and the lowest `k` wins score ties. PCA coordinates are not used by the default clustering path. |
| Conformation labels | MANIA scientific MVP | **Stage 22.F covered.** `analysis/{condition}/conformation_labels_{condition}.csv` preserves condition, frame order, `frame_index`, and optional `time_ps`, and explicitly records fingerprint input, unavailable PCA, and lack of notebook PCA-to-k-means parity. Skipped rows contain no invented clustering values. |
| Representative frames | Optional scientific artifact | **Stage 22.F covered for computed clusters.** The frame nearest each final fingerprint centroid is selected, with `frame_index` breaking ties. This is not first-sampled-frame Cα coordinate provenance. |
| Conformation PCA export | Optional scientific artifact | **Stage 24.A optional computed PCA covered.** `analysis/{condition}/conformation_pca_{condition}.csv` preserves frame metadata, feature count, and stable component/variance columns. Default rows keep the Stage 22.E disabled fallback with `n_components = 0` and blank numerical fields; explicit `enable_pca=True` rows contain finite centered NumPy SVD coordinates only for available rank-supported components. |

These Stage 22 roadmap items are part of the complete MANIA scientific MVP.
Stage 22.A covers only the input/configuration/window contract. Stage 22.B
constructs deterministic in-memory window RINs. Stage 22.C consumes those
graphs, uses primary `window_contact_freq` only for strength, keeps shortest
paths and the `greedy_modularity_unweighted` fallback unweighted, and writes
the public temporal summary artifact. Stage 22.D builds condition-local binary
contact fingerprints directly from validated per-frame contacts without
inferring frames or using distances/frequencies as values. Stage 22.E adds the
deterministic PCA artifact contract but emits no fake coordinates while the
accepted dependency boundary lacks a numerical backend. K-means, silhouette,
conformation labels, and representative frames are covered separately by Stage
22.F using deterministic dependency-free k-means directly on the binary contact
fingerprint matrix. PCA coordinates are not used by the default clustering
path, and Stage 22.F does not claim notebook PCA-to-k-means parity. It exports
`conformation_labels_{condition}.csv`, selects `k` by valid silhouette scores,
and selects centroid-nearest representatives only for computed clusters. Full
notebook parity requires a future explicit approval stage.
None of these items is required for WANIA base graph rendering. Interactive
temporal playback and a required inline WANIA temporal model remain v2/future
product scope.

#### Stage 22.G temporal/conformation validation and docs/tests alignment

Stage 22.G adds focused synthetic contract coverage without changing accepted
Stage 22 schemas or algorithms. It validates deterministic field and row
ordering for `temporal_rin_{condition}.csv`,
`conformation_pca_{condition}.csv`, and
`conformation_labels_{condition}.csv`; cross-artifact condition, frame, and
optional `time_ps` consistency; fingerprint/PCA/label frame coverage; explicit
skipped and unavailable values; and header-only empty outputs.

The validation preserves the default `pca_unavailable` fallback with zero
components and blank PCA and explained-variance fields. Labels remain
fingerprint-based: Stage 22.F does not use PCA coordinates and does not claim
notebook PCA-to-k-means parity. Stage 24.A later adds optional computed PCA
with explicit `enable_pca=True`; full notebook parity is not claimed. The
accepted WANIA payload contract remains unchanged. WANIA temporal animation,
WANIA conformation UI, a WANIA typed-RIN schema, API, Docker, database,
frontend, and production workers remain deferred. Cross-protein comparison and
non-protein heterograph support also remain outside this stage.

#### Stage 24.A optional computed PCA

Stage 24.A approves NumPy as an accepted direct dependency for MANIA optional
computed PCA. The activation mechanism is explicit:
`build_conformation_pca_projection(fingerprints, enable_pca=True)`. The
default `enable_pca=False` path does not compute PCA and preserves the
Stage 22.E blank `pca_unavailable` fallback for nonconstant inputs.

The PCA input remains exactly `ContactFingerprintMatrix.values`: sampled-frame
rows, deterministic residue-pair/type feature columns, and binary 0/1 contact
fingerprint values. PCA must not use temporal metrics, contact frequencies,
distance summaries, WANIA coordinates, graph coordinates, C-alpha coordinates,
or Stage 21 centrality values.

The enabled implementation centers each feature column, runs NumPy SVD,
computes up to three components bounded by frame count, feature count, and
numerical rank, computes explained-variance ratios from centered variance, and
stabilizes component signs by the largest absolute loading with lowest
feature-index tie break. Empty, one-frame, zero-feature, constant/all-zero, and
failed numerical inputs remain explicit and emit no fake coordinates or fake
explained-variance ratios.

The v1.2 notebook was inspected. It uses dense binary fingerprints,
`StandardScaler(with_std=False)` for centering without standardization,
scikit-learn `PCA`, and k-means on PCA coordinates. Component-sign
stabilization is not visible in the notebook code, so exact notebook parity is
not claimed. PCA-based clustering remains Stage 24.B scope only after explicit
approval. `mania analyze`, `extended_metrics.json`, WANIA changes, and the
postponed Stage 25 Minimal API are not implemented in Stage 24.A.

## 5. Out of MANIA scientific MVP / v2 scope

The following are not required to complete the RIN MVP defined here:

- cross-protein comparison, residue alignment, and multi-protein mapping;
- inter-protein graph comparison without an explicit identity/mapping
  contract;
- Kabsch-aligned trajectory-average or cross-condition coordinate parity;
- a full WANIA typed-RIN schema or a requirement that every chemistry type be
  present in every payload;
- required parquet export or a new parquet dependency;
- production scientific figures and final biological interpretation;
- interactive temporal playback and frontend conformation tooling;
- automatic notebook execution, a complete notebook rewrite, or real-MD
  output equality in default CI;
- API serving, upload/job orchestration, Docker, databases, workers, or a
  frontend application.

Optional non-protein science may be promoted only by a later explicit scope
decision. It is not implicitly v1-required because notebook reference code or
historical files exist.

## 6. WANIA frontend MVP boundary

The accepted `wania_graph_payload.json` remains frontend-facing. This scope
document does not change its structure or required fields.

- `graph.nodes` and `graph.edges` remain the base render model.
- Node `x/y/z` remain required frontend-facing render coordinates.
- Node `x_ca/y_ca/z_ca` remain optional scientific Cα provenance.
- Edge `interaction.primary_type` remains the canonical required frontend
  edge-type field.
- `interaction.all_types` remains optional scientific detail.
- `capabilities` remain availability signals. A true capability does not make
  optional scientific data required for basic rendering.
- `artifacts` remains a stable reference object; individual references are
  optional, and large scientific tables remain outside the payload.
- `diagnostics` remains frontend-facing status metadata.
- Centrality, communities, structural metrics, typed chemistry details,
  formal statistics, temporal RIN, and conformational outputs are not required
  WANIA payload fields.

The accepted demo export command remains `mania wania build-payload`. For its
generated Stage 18.3 demo output, `diagnostics.passed` remains boolean and must
not be `null`. Stage 19.3 reconciles the older nullable prose with this
accepted command guardrail without changing runtime behavior.

## 7. Optional scientific artifact boundary

The optional scientific set is:

- non-protein node and protein–non-protein edge inventories;
- `protein_lipid`, `protein_glycan`, `glycan_anchor`, and `protein_ligand`
  semantics;
- phi/psi annotation;
- graph-level Rg summary enrichment pending shape/name confirmation;
- NMI/ARI partition comparison;
- region/community Fisher enrichment;
- representative-frame export;
- conformation PCA detail export.

An optional artifact may be absent, advertised through an honest capability,
or referenced through a portable relative `artifacts` entry. It must not be
inlined merely to make WANIA renderable, and its absence must not fail the base
WANIA profile.

## 8. Backend-only/internal boundary

The following stay backend-only/internal even when they support an accepted
scientific artifact:

- contact accumulation, atom caching, atom selection, frame iteration,
  distance limits, and chemistry geometry implementation;
- graph-library choice, community fallback, numerical fallback, and
  statistical implementation detail;
- raw per-frame calculation state and contact fingerprint construction
  internals;
- run-manifest normalization, residue-library validation/QC, and adapter
  mapping internals;
- scientific coordinate provenance beyond optional frontend annotations;
- local/raw paths, trajectory objects, notebook paths/cells, and generated
  output directories;
- backend artifact filenames/layout except where a separately accepted
  artifact contract exposes a portable reference.

Per-frame contacts and scientific CSV rows are backend scientific data from
WANIA's perspective. WANIA may reference them, but the frontend must not need
to load them to render the base graph.

## 9. Stage mapping

This is planning-level ownership only; it does not create implementation tasks.

| Future stage | Accepted high-level scope |
| --- | --- |
| Stage 20 — RIN preprocessing parity | Protein residue/edge artifacts, missing protein edge semantics, structural attributes, per-frame/static artifact parity, semantics/provenance manifests, and explicit handling of optional non-protein artifacts. |
| Stage 21 — RIN analysis parity | **Completed through Stage 21.F:** accepted static graph, metrics, communities, enrichment, conservative node comparison/statistics, and validation/docs/tests alignment. |
| Stage 22 — Temporal RIN + conformational artifacts | **Completed through Stage 22.G:** accepted temporal input/windows, window graphs/metrics, contact fingerprints, PCA-unavailable and fingerprint-clustering artifacts, representatives, and validation/docs/tests alignment. |
| Stage 23 — WANIA RIN alignment | **Completed through Stage 23.E:** accepted MANIA/WANIA boundary, conservative capabilities, optional file-reference policy, deterministic contract protection, and documentation acceptance checklist without expanding the base render contract. |

## 10. Non-goals

Stage 19.2 does not add or change runtime logic, RIN algorithms, contact
chemistry, edge-semantic computation, graph metrics, temporal RIN,
PCA/k-means/silhouette behavior, WANIA schema/required fields, CLI behavior,
FastAPI, upload/job APIs, Docker, databases, workers, frontend code,
dependencies, real-MD CI data, or generated outputs. It does not begin Stages
20–23 and does not perform the broad Stage 19.3 documentation consistency
pass.

## 11. Risks and guardrails

### 11.1 Naming and contract gaps

| Mismatch | Decision state |
| --- | --- |
| `contacts_per_frame` / `contacts_perframe`; parquet / backend CSV | **Resolved for the Stage 20.B baseline.** Use per-condition `contacts_perframe_{cond}.csv`; the older combined backend CSV remains separate, and neither parquet nor `contacts_per_frame` is added. |
| `non_protein_nodes` / `nonprotein_nodes` | **Optional artifact naming issue.** No production contract is implied. |
| `res_i` / backend `resid_i` and `res_j` / backend `resid_j` | **MVP naming decision needed.** Existing backend names remain current evidence. |
| `centrality_*` / production `metrics_*` | **Resolved for Stage 21.B.** The accepted Stage 21.A graph path exports `centrality_{condition}.csv`; legacy `metrics_*` output remains separate. |
| `dssp` / backend `ss` | **MVP naming decision needed** with the computation/provenance contract. |
| `k_core` / backend `kcore` | **Resolved for Stage 21.B.** Keep the existing production and MANIA contract spelling `kcore`. |
| notebook `xca/yca/zca` / backend `x_ca/y_ca/z_ca` | **MVP naming decision needed only for parity mapping.** Backend underscore names remain accepted scientific provenance fields. |
| `rg_mean/rg_std` / `rg_mean_A/rg_std_A` and node/graph shape | **Unclear / needs confirmation; optional artifact naming issue.** |
| `conformation_labels_{cond}.csv` / planned `conformational_states.csv` | **MVP naming decision needed** in Stage 22; neither name proves implementation. |
| historical temporal `cond`/frame bounds / planned `condition`/window/time fields | **MVP naming/schema decision needed** in Stage 22. |
| older nullable `diagnostics.passed` prose / Stage 18.3 boolean demo output | **Reconciled in Stage 19.3.** The boolean/not-null demo requirement remains authoritative; runtime behavior is unchanged. |

### 11.2 Scientific and layer guardrails

- A recognized vocabulary value or planned column is not proof that its
  computation exists.
- Notebook/reference evidence must not be reported as backend production
  parity.
- New chemistry and statistics require explicit semantics, provenance,
  deterministic tests, and a dependency decision in their implementation
  stage.
- Existing backend-specific semantics must not be relabeled as line-for-line
  notebook parity.
- Backend scientific fields must not become required WANIA render fields by
  convenience or by appearing in a rich sample.
- Capability flags must remain false until the corresponding accepted data is
  genuinely available.
- Final lipid, glycan, glycolipid, ligand, region, or residue lists must not be
  invented during implementation.

## 12. Open questions

These questions do not reopen the scope categories above; they must be settled
inside the relevant later-stage contract before implementation:

1. Which current backend names stay canonical, and which notebook names are
   supported through explicit adapter mappings?
2. What algorithms, units, missing-value rules, and provenance are accepted
   for region, RMSF, SASA, DSSP/`ss`, and `tm_relative_z`?
3. What schemas and dependency boundary apply to MWU, FDR-BH, Cohen's d, and
   bootstrap confidence intervals?
4. What within-run node mapping is required for condition comparison, NMI,
   and ARI?
5. Which temporal graph metrics and window boundary/time fields are included
   in the Stage 22 artifact contract?
6. Should any optional non-protein or enrichment artifact be promoted in a
   later version after its identity and biological semantics are accepted?
## 13. Acceptance checklist for future stages

Before a later stage claims a scoped capability as covered, it must confirm:

- [ ] The artifact or computation is in the stage mapped by this document.
- [ ] Current production evidence, tests, and limitations are cited.
- [ ] Naming, schema, units, provenance, and missing-value behavior are explicit.
- [ ] Reference/notebook parity and backend-specific semantics are distinguished.
- [ ] Optional artifacts remain optional and v2 scope has not been imported.
- [ ] No scientific artifact field is made a required WANIA field without a separately accepted WANIA contract change.
- [ ] `x/y/z` and `x_ca/y_ca/z_ca` retain their distinct render/provenance meanings.
- [ ] `interaction.primary_type`, capabilities, artifacts, and diagnostics retain their accepted WANIA roles.
- [ ] Unsupported capability flags remain false.
- [ ] `mania wania build-payload` and the boolean Stage 18.3 demo `diagnostics.passed` guardrail remain unchanged unless a separately scoped task explicitly changes them.
- [ ] Tests use small synthetic fixtures; raw/local/generated MD outputs are not committed.
- [ ] Dependencies, if any, are separately and explicitly authorized.
