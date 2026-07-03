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
| Protein-protein contact edge export | MANIA scientific MVP | **Partially covered.** Production writes `graph/edges.csv` and `contacts/contact_edges.csv`; the notebook-style `protein_contact_edges_undirected_{cond}.csv` name/layout is not the production contract. | Stage 20 must decide mapping rather than silently replace an accepted artifact. |
| Edge frequency and distance aggregation | MANIA scientific MVP | **Already covered** for accepted contact observations by `trajectory_contact_accumulator.py` and its tests. | Stage 20 parity work may extend semantics but must preserve sampled-frame frequency meaning. |
| Per-frame contacts artifact | MANIA scientific MVP | **Partially covered.** `contacts/contacts_perframe.csv` is an accepted opt-in CSV with source-frame indexes; required parquet and exact notebook naming are not covered. | The CSV is the MVP baseline. Parquet is not required by this freeze; any later format addition needs a separate dependency/contract decision. |
| Static RIN graph export | MANIA scientific MVP | **Already covered** as backend `graph/graph.json`; it is distinct from the WANIA payload. | Preserve the backend/frontend separation. |
| Rg time series | MANIA scientific MVP supporting artifact | **Partially covered** relative to notebook naming, but the scientific CSV is implemented at `rg/rg_timeseries.csv`. | Preserve the accepted backend artifact; naming parity remains a Stage 20 decision. |
| Edge semantics manifest | MANIA scientific MVP | **Partially covered.** A historical `edge_semantics.json` and current priority vocabulary exist, but there is no production writer for the full criteria. | Stage 20 target. The manifest must report accepted semantics rather than imply unsupported chemistry. |
| MANIA run manifest export | Backend-only/internal | **Partially covered and unclear.** `mania_manifest.json` is consumed by an adapter, while current workflow provenance has a different role/layout. | Stage 20 may define reproducibility metadata, but this is not a WANIA render field. |
| Residue library / QC artifact | Backend-only/internal | **Partially covered.** Residue-library validation and bridging exist; a per-run emitted `mania_residue_library.json` is not established. | Preserve validation/QC ownership. Do not invent final biological residue lists. |
| Non-protein node inventory | Optional scientific artifact | **Not implemented in production.** Notebook/reference naming is `nonprotein_nodes_{condition}.csv`. | Optional Stage 20 extension after identity and naming are accepted. |
| Protein–non-protein edge inventory | Optional scientific artifact | **Not implemented in production.** Only notebook/reference evidence exists for `np_contact_edges_{cond}.csv`. | Optional Stage 20 extension; never required for the WANIA base graph. |

The immediate protein RIN scientific baseline therefore consists of residue
identity/structural tables, protein contact edges, contact aggregation,
per-frame observations, the static graph, and explicit semantics/provenance.
Optional heterograph inventories do not block that baseline.

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

### 4.2 RIN edge semantics

| Edge semantic | Frozen scope | Coverage at Stage 19.2 |
| --- | --- | --- |
| `backbone` | MANIA scientific MVP | **Already covered** with backend-specific representative-Cα semantics. |
| `aromatic_pi` | MANIA scientific MVP | **Already covered** with accepted backend-specific geometry. |
| `cation_pi` | MANIA scientific MVP | **Already covered** with accepted backend-specific geometry. |
| `hbond` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. |
| `disulfide` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. |
| `vdw` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. |
| `hydrophobic` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. |
| `ionic` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. |
| `salt_bridge` | MANIA scientific MVP | **MVP target for future implementation.** Recognized vocabulary and notebook reference logic exist; production detection is missing. Its distinction from `ionic` must be explicit before implementation. |
| `protein_lipid` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |
| `protein_glycan` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |
| `glycan_anchor` | Optional scientific artifact | **Not implemented.** Reference-only evidence; anchor semantics require confirmation. |
| `protein_ligand` | Optional scientific artifact | **Not implemented.** Reference-only evidence; identity and chemistry contracts are required before promotion. |

Stage 20 owns later protein-edge parity. This freeze does not choose atom
selection rules, cutoffs, overlap behavior, or a graph library, and does not
claim full typed-RIN support. Specific interaction values remain optional
scientific annotations in WANIA even when MANIA can compute them.

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
| Static RIN graph input/export | MANIA scientific MVP | **Already covered** by backend `graph/graph.json`. |
| `degree`, `strength`, `betweenness`, `closeness`, `eigenvector`, `pagerank` | MANIA scientific MVP | **Already covered** by `src/mania/analysis/graph_metrics.py` and tests. |
| Weighted graph baseline | MANIA scientific MVP | **Already covered** for `strength` using numeric `contact_freq`; broader unspecified weighted metrics are not added by this freeze. |
| `k_core` | MANIA scientific MVP | **Partially covered** under the production name `kcore`; canonical naming remains undecided. |
| `community` | MANIA scientific MVP | **Already covered** with separate community artifacts. Algorithm/fallback choice is backend-only. |
| `modularity` | MANIA scientific MVP | **Already covered** as a report-level community quality value. |
| `centrality_{cond}.csv` | MANIA scientific MVP artifact concept | **Partially covered** by current `analysis/metrics_<condition>.csv`; filename and content mapping remain undecided. |
| `communities_{cond}.csv` | MANIA scientific MVP artifact | **Already covered** in the current analysis output layout. |
| Cross-condition comparison, `stats.csv`, `comparison.csv` | MANIA scientific MVP | **MVP target for future implementation.** Historical examples/planned schemas do not prove a production computation or accepted artifact. |
| `MWU`, `FDR-BH`, `Cohen's d`, Bootstrap CI | MANIA scientific MVP | **MVP targets for future implementation** in Stage 21. Algorithms, dependencies, schemas, and test fixtures remain to be accepted. |
| `NMI`, `ARI` | Optional scientific artifact | **Not implemented.** Requires an explicit within-run cross-condition node/partition mapping contract. |
| Region/community enrichment and Fisher enrichment | Optional scientific artifact | **Not implemented.** Requires accepted labels, hypotheses, and output schema. |

Metrics, communities, comparison tables, statistics, and enrichment outputs
are separate MANIA scientific artifacts. They do not become required node,
edge, or top-level fields in `wania_graph_payload.json`. Cross-protein
comparison is not the cross-condition comparison targeted here and remains
v2/future scope.

### 4.6 Temporal RIN and conformation artifacts

| Capability or artifact | Frozen scope | Coverage at Stage 19.2 |
| --- | --- | --- |
| Temporal RIN input contract | MANIA scientific MVP | **Partially covered.** Per-frame contacts are a possible input, but there is no accepted temporal input contract. |
| Sliding-window configuration (`TEMP_WINDOW`, `TEMP_STEP`, `TEMP_MIN_FREQ`) | MANIA scientific MVP | **MVP target for future implementation.** Reference parameters exist; backend config/validation does not. |
| Window-level contact frequency | MANIA scientific MVP | **MVP target for future implementation.** Aggregate whole-run contact frequency is not window-level frequency. |
| Window-level RIN construction / `temporal_rin_{cond}.csv` | MANIA scientific MVP | **MVP target for future implementation.** Per-frame contacts do not establish temporal RIN coverage. |
| Temporal graph metrics | MANIA scientific MVP | **MVP target for future implementation.** The exact metric set and artifact shape remain open for Stage 22. |
| Contact fingerprint matrix | MANIA scientific MVP | **Partially covered.** Per-frame observations exist as possible input; matrix construction/export is missing. |
| PCA, k-means, silhouette selection | MANIA scientific MVP | **MVP targets for future implementation** as the accepted conformation-label pipeline, subject to a separate dependency and determinism decision. |
| Conformation labels | MANIA scientific MVP | **MVP target for future implementation.** Historical `conformation_labels_{cond}.csv` does not match the planned backend name/schema. |
| Representative frames | Optional scientific artifact | **Not implemented.** Must not be confused with first-sampled-frame Cα coordinate provenance. |
| Conformation PCA export | Optional scientific artifact | **Not implemented.** No production artifact/schema is accepted. |

These Stage 22 roadmap items are part of the complete MANIA scientific MVP,
but none is required for WANIA base graph rendering. Interactive temporal
playback and a required inline WANIA temporal model remain v2/future product
scope.

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
| Stage 21 — RIN analysis parity | Static/weighted metrics and community artifact parity, comparison/statistics targets, and optional enrichment/partition comparisons. |
| Stage 22 — Temporal RIN + conformational artifacts | Temporal input/window contract, window-level graphs/metrics, contact fingerprints, conformation labels, and optional representative/PCA exports. |
| Stage 23 — WANIA RIN alignment | Map only accepted and available MANIA outputs into optional WANIA annotations, capabilities, and portable artifact references without expanding the base render contract by implication. |

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
| `contacts_per_frame` / `contacts_perframe`; parquet / backend CSV | **MVP naming decision needed.** Current CSV is accepted production evidence; parquet is not an MVP requirement. |
| `non_protein_nodes` / `nonprotein_nodes` | **Optional artifact naming issue.** No production contract is implied. |
| `res_i` / backend `resid_i` and `res_j` / backend `resid_j` | **MVP naming decision needed.** Existing backend names remain current evidence. |
| `centrality_*` / production `metrics_*` | **MVP naming decision needed** for Stage 21 artifact parity. |
| `dssp` / backend `ss` | **MVP naming decision needed** with the computation/provenance contract. |
| `k_core` / backend `kcore` | **MVP naming decision needed.** Current production output remains `kcore`. |
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
3. What exact distinction and overlap rules separate `ionic` from
   `salt_bridge`?
4. What schemas and dependency boundary apply to MWU, FDR-BH, Cohen's d, and
   bootstrap confidence intervals?
5. What within-run node mapping is required for condition comparison, NMI,
   and ARI?
6. Which temporal graph metrics and window boundary/time fields are included
   in the Stage 22 artifact contract?
7. Should any optional non-protein or enrichment artifact be promoted in a
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
