# MANIA RIN MVP requirements inventory and gap matrix

## 1. Purpose and scope

This document originated as the Stage 19.1 inventory for the MANIA RIN MVP and
is maintained through the Stage 20.F preprocessing consolidation. It maps the
requirements supplied for Stage 19 to concrete repository evidence, current
coverage, layer ownership, and unresolved gaps. Historical Stage 19 candidate
wording remains inventory context; accepted Stage 20 rows record the actual
implemented or explicitly deferred outcome.

The accepted WANIA MVP remains the frontend-facing JSON contract for graph
rendering. MANIA scientific requirements, optional scientific artifacts, and
future work are kept separate from that contract. In particular, this document
does not change `mania wania build-payload`, the generated payload schema, or
the Stage 18.3 requirement that a demo payload has a boolean
`diagnostics.passed` value.

## 2. Evidence sources inspected

### Repository evidence

- `README.md` and `docs/**`, especially `docs/data_contract.md`,
  `docs/notebook_gap_report_v1_3.md`,
  `docs/notebook_parity_audit_v1_3.md`,
  `docs/preprocessing_graph_workflow_contract.md`, and the WANIA v0.1 contract
  documents.
- `src/mania/**`, including preprocessing graph/contact/Rg exports, graph
  metrics and exports, notebook adapters, constants, and the WANIA payload
  adapter.
- `tests/**` and `tests/fixtures/**`, including notebook-export fixtures,
  WANIA fixtures, Stage 18.3 command tests, and graph/analysis tests.
- `data/reference/**`, including historical v1.1 exports and the repository
  notebooks listed below.

### Notebook locations checked

| Requested name | Result |
| --- | --- |
| `MANIA_preprocessing_v1.2.ipynb` | Absent at repository root and under the exact dot-version name. |
| `MANIA_preprocessing_v1_2.ipynb` | Present at `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb`; absent at repository root. |
| `MANIA_analysis_v1.3.ipynb` | Absent at repository root and under the exact dot-version name. |
| `MANIA_analysis_v1_3.ipynb` | Present at `data/reference/notebooks_libraries_v1_3/MANIA_analysis_v1_3.ipynb`; absent at repository root. |
| Other `data/reference/**` notebook/reference locations | Present: v1.1 notebooks and exports, `data/reference/notebooks_libraries_v1_2/MANIA_analysis_v1_2.ipynb`, and v1.3 notebooks. |

The v1.2 preprocessing and v1.3 analysis notebooks are concrete repository
reference/specification evidence. They are not production-backend evidence:
`docs/notebook_parity_audit_v1_3.md` explicitly says that default CI does not
execute them and that reference output presence does not establish backend
parity.

### External/project-context evidence

The Stage 19.1 task brief supplies the requirement inventory and the proposed
MANIA/WANIA layer framing. A requirement is not considered implemented merely
because it appears in that brief. Where a repository notebook specifies a
requirement but production source/tests do not implement it, the matrix says
so explicitly.

## 3. Evidence rules and status definitions

`Repo evidence` always names a path and says what that path proves for every
`covered` or `partially covered` row. Repository notebooks and historical
exports prove reference intent or example shape only; source plus tests or an
accepted current contract are required to claim production coverage.

| Status | Meaning |
| --- | --- |
| `covered` | Concrete current repository evidence implements, tests, or freezes the exact requirement. |
| `partially covered` | Related behavior exists, but naming, layout, semantics, computation, or integration is incomplete. |
| `missing` | No current production implementation or accepted exact artifact was found. Reference-only evidence may still exist. |
| `unclear / needs confirmation` | Evidence is indirect or the intended meaning/layer is ambiguous. |
| `v2 / out of MVP` | Explicitly deferred beyond the immediate MVP. |

The `Classification` column uses `accepted required`, `MVP candidate`,
`optional candidate`, `backend/internal`, and `future/deferred`. “MVP
candidate” means Stage 19.2 must decide the frozen scientific scope; it does
not make the item a WANIA render requirement.

### Stage 20 consolidation status

Stage 20.A implements the residue table baseline; Stage 20.B implements the
protein contact edge and per-frame CSVs with accepted frequency and distance
aggregation; Stage 20.C implements protein-only RIN edge semantics; Stage 20.D
implements the three semantics/provenance manifests; and Stage 20.E explicitly
defers optional non-protein inventories. Stage 20.F adds deterministic
cross-artifact contract coverage and aligns documentation with those outcomes.
It does not implement Stage 21, temporal RIN, non-protein inventory, full
heterograph support, or a WANIA typed-RIN schema.

## 4. Gap matrices

### 4.1 RIN preprocessing artifacts

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `residue_table_{cond}.csv` | Preprocessing artifact | Stage 19 context; preprocessing v1.2 reference | `src/mania/preprocessing/trajectory_residue_table_export.py` — production per-condition writer from the accepted graph mapping; focused synthetic tests cover identity, Cα provenance, missing values, naming, and CSV safety. | covered at Stage 20.A baseline | accepted required | MANIA scientific MVP | Explicit root-level artifact; it does not replace or silently alias `graph/nodes.csv`. `residue_index`, source `resid`, `resname`, and `segment_id` are separate columns. Uncomputed structural columns are empty. | Stage 20.A complete; computed attributes remain later scoped work |
| `protein_contact_edges_undirected_{cond}.csv` | Preprocessing artifact | Stage 19 context; preprocessing v1.2 reference | `src/mania/preprocessing/trajectory_protein_contact_export.py` — writes one undirected protein-contact edge CSV per condition; focused Stage 20.B/20.C tests cover identity, normalization, typed observations, sampled-frame frequency, distance aggregation, weight, and filenames. | covered at Stage 20.B baseline and Stage 20.C typed extension | accepted required | MANIA scientific MVP | This explicit artifact does not replace or alias `graph/edges.csv` or `contacts/contact_edges.csv`. Stage 20.C feeds typed protein observations through the unchanged Stage 20.B schema and aggregation semantics. | Stage 20.C complete |
| `contacts_per_frame_{cond}.parquet` | Preprocessing artifact | Stage 19 context | `src/mania/preprocessing/trajectory_protein_contact_export.py` — writes the accepted per-condition CSV mapping `contacts_perframe_{cond}.csv`; focused tests preserve source frame and residue-pair identity. | covered by explicit Stage 20.B CSV mapping | accepted required | MANIA scientific MVP | The accepted baseline spelling is `contacts_perframe`; `contacts_per_frame` and parquet are not silently treated as implemented. The older `contacts/contacts_perframe.csv` remains a distinct combined artifact. | Stage 20.B complete; format changes require separate approval |
| `non_protein_nodes_{cond}.csv` | Preprocessing artifact | Stage 19 context; Stage 20.E decision | `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb` writes `nonprotein_nodes_{condition}.csv`, but production contact results retain no protein/non-protein membership and no accepted inclusion/classification contract exists. | explicitly deferred at Stage 20.E; not emitted | optional candidate | optional scientific artifact | Reference-only evidence cannot establish production identity, solvent/ion inclusion, biological classification, or canonical naming. It is not a WANIA render requirement and is not reported as produced. | Later explicit scope only |
| `np_contact_edges_{cond}.csv` | Preprocessing artifact | Stage 19 context; Stage 20.E decision | Reference artifacts exist, but current mixed-selection contact results do not retain endpoint membership or reliably map their selection-local indexes to Stage 20.A protein residue identity. | explicitly deferred at Stage 20.E; not emitted | optional candidate | optional scientific artifact | No production writer or accepted generic mixed-contact contract. `protein_lipid`, `protein_glycan`, `glycan_anchor`, and `protein_ligand` remain unimplemented. | Later explicit scope only |
| `rg_timeseries_{cond}.csv` | Preprocessing artifact | Stage 19 context; preprocessing v1.2 reference | `src/mania/preprocessing/trajectory_rg_export.py` — implements the Rg CSV writer; `src/mania/preprocessing/trajectory_graph_workflow.py` — integrates it at `rg/rg_timeseries.csv`. | partially covered | MVP candidate | MANIA scientific MVP | Scientific content is implemented, but notebook and backend filenames/layout differ. | Stage 19.2 |
| `edge_semantics.json` | Preprocessing artifact | Stage 19 context; Stage 20.C implementation | `src/mania/preprocessing/trajectory_preprocessing_manifests.py` — deterministic writer reuses the central edge priority and accepted chemistry thresholds; focused synthetic tests cover vocabulary, order, and deferred non-protein types. | covered at Stage 20.D | accepted required | MANIA scientific MVP | Describes implemented protein-only Stage 20.C semantics and limitations without adding chemistry. | Stage 20.D complete |
| `mania_manifest.json` | Preprocessing artifact | Stage 19 context; Stage 20.A/B artifacts | `src/mania/preprocessing/trajectory_preprocessing_manifests.py` — records available Stage 20.A/B/D artifacts as portable filenames and represents unavailable provenance as null. | covered at Stage 20.D | backend/internal | backend-only/internal | Optional preprocessing provenance; it is not a required WANIA payload field. | Stage 20.D complete |
| `mania_residue_library.json` | Preprocessing artifact | Stage 19 context; Stage 20.A identity | `src/mania/preprocessing/trajectory_preprocessing_manifests.py` — emits the per-run Stage 20.A identity inventory with deterministic missing-value and conflict QC. | covered at Stage 20.D | backend/internal | backend-only/internal | Not a biological residue database and does not include non-protein inventory. | Stage 20.D complete |

### 4.2 RIN edge semantics

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `backbone` | Edge semantics | Preprocessing v1.2 and analysis v1.3 references | `src/mania/preprocessing/trajectory_graph_export.py` — creates structural backbone graph edges; `tests/test_preprocessing_graph_backbone_edges.py` — regression-tests them. | covered | MVP candidate | MANIA scientific MVP | Implemented with backend-specific representative-Cα semantics. It remains optional in WANIA rendering. | Stage 19.2 |
| `aromatic_pi`, `cation_pi` | Edge semantics | Preprocessing v1.2 reference | `src/mania/preprocessing/trajectory_contact_chemistry.py` — detects both interaction types; `tests/test_preprocessing_aromatic_cation_pi_contacts.py` — tests accepted chemistry behavior. | covered | MVP candidate | MANIA scientific MVP | Backend geometry intentionally does not claim line-for-line notebook parity. | Stage 19.2 |
| `hbond`, `disulfide`, `vdw`, `hydrophobic`, `ionic`, `salt_bridge` | Edge semantics | Stage 20.C criteria; preprocessing v1.2 reference | `src/mania/preprocessing/trajectory_contact_chemistry.py` — dependency-free production detection; `src/mania/preprocessing/trajectory_contacts.py` — sampled-frame integration; `tests/test_preprocessing_protein_rin_edge_semantics.py` — focused synthetic criteria, overlap, priority, aggregation, and incomplete-data coverage. | covered at Stage 20.C with explicit hbond limitation | MVP candidate | MANIA scientific MVP | H-bonds require an explicit topology-provided bonded hydrogen and angle; no distance-only fallback is used. `salt_bridge` uses the narrower LYS/ARG-to-ASP/GLU charged atom groups at 4.0 Å and may overlap with the broader 6.0 Å `ionic` annotation. | Stage 20.C complete |
| `protein_lipid`, `protein_glycan`, `glycan_anchor`, `protein_ligand` | Edge semantics | Preprocessing v1.2 reference | `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb` — defines these reference semantics. | missing | optional candidate | optional scientific artifact | No production implementation or accepted backend edge vocabulary was found. These cannot be required WANIA base-graph fields. | Stage 19.2 |

### 4.3 Node attributes

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `resid`, `resname` | Node attributes | Stage 19 context; backend contract | `src/mania/constants.py` — includes both in `NODE_COLUMNS`; `tests/test_preprocessing_trajectory_graph_nodes_csv_writer.py` — tests production node export. | covered | MVP candidate | MANIA scientific MVP | Backend graph identities are also adapted into WANIA residue identity. | Stage 19.2 |
| `region` | Node attributes | Stage 19 context; backend contract | `src/mania/constants.py` — includes `region`; `src/mania/analysis/graph_metrics.py` — preserves it when present. | partially covered | MVP candidate | MANIA scientific MVP | Preserved/exported but not computed or populated by a production region-classification step. | Stage 19.2 |
| `rmsf`, `sasa` | Node attributes | Preprocessing v1.2 reference | `src/mania/analysis/graph_metrics.py` — preserves `rmsf_A` and `sasa_A2`; `docs/notebook_parity_audit_v1_3.md` — states that missing structural features are not computed. | partially covered | MVP candidate | MANIA scientific MVP | Naming includes units in backend; production computation is missing. | Stage 19.2 |
| `dssp` | Node attributes | Preprocessing v1.2 reference | `src/mania/constants.py` — provides the backend `ss` column; `src/mania/analysis/graph_metrics.py` — preserves `ss` when present. | partially covered | MVP candidate | MANIA scientific MVP | Contract naming mismatch (`dssp` versus `ss`) and no production DSSP computation. | Stage 19.2 |
| `phi/psi` | Node attributes | Preprocessing v1.2 reference | `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb` — computes a four-value `phi_psi` encoding in reference code. | missing | optional candidate | optional scientific artifact | No backend field, representation decision, or production computation was found. | Stage 19.2 |
| `tm_relative_z` | Node attributes | Preprocessing v1.2 reference; backend contract | `src/mania/constants.py` — includes `tm_relative_z` in `NODE_COLUMNS`; `src/mania/preprocessing/trajectory_graph_export.py` — carries the field through node CSV export. | partially covered | MVP candidate | MANIA scientific MVP | Contract/export slot exists, but no production calculation was found. | Stage 19.2 |
| `rg_mean`, `rg_std` | Node attributes | Stage 19 list; graph-level in preprocessing v1.2 reference | `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb` — explicitly defines them as global graph features; `docs/data_contract.md` — names backend summaries `rg_mean_A` and `rg_std_A`. | unclear / needs confirmation | optional candidate | optional scientific artifact | Layer/shape mismatch: these appear graph-level, not per-node; names also differ. | Stage 19.2 |
| `x/y/z` | Node attributes | Backend/WANIA contracts | `src/mania/preprocessing/trajectory_graph_export.py` — writes render-coordinate aliases from representative Cα data; `tests/test_wania_graph_artifact_mapping_v0_1.py` — requires finite WANIA render coordinates. | covered | accepted required | WANIA frontend payload MVP | Required for renderable WANIA v0.1 nodes, not a demand for aligned/averaged scientific coordinates. | None; contract frozen |
| `x_ca/y_ca/z_ca` | Node attributes | Preprocessing v1.2 reference; backend contract | `src/mania/preprocessing/trajectory_contacts.py` — captures representative Cα coordinates; `tests/test_preprocessing_trajectory_graph_nodes_csv_writer.py` — tests graph-node export. | covered | MVP candidate | MANIA scientific MVP | Optional in WANIA; backend uses first sampled-frame coordinates and does not claim Kabsch parity. | Stage 19.2 |

### 4.4 Edge attributes

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `res_i`, `res_j` | Edge attributes | Stage 19 context | `src/mania/constants.py` — backend contract uses `resid_i` and `resid_j`; the historical reference CSV also carries `i/j` and `resid_i/resid_j`. | partially covered | MVP candidate | MANIA scientific MVP | Contract naming mismatch; `res_i/res_j` is not an accepted current backend pair. | Stage 19.2 |
| `edge_type` | Edge attributes | Backend contract | `src/mania/constants.py` — requires `edge_type`; `tests/test_preprocessing_trajectory_graph_edges_csv_writer.py` — tests its export. | covered | MVP candidate | MANIA scientific MVP | WANIA maps this concept to `interaction.primary_type`; it does not add a parallel frontend field. | Stage 19.2 |
| `contact_freq` | Edge attributes | Backend contract | `src/mania/preprocessing/trajectory_contact_accumulator.py` — finalizes sampled-frame contact frequencies; `tests/test_preprocessing_interaction_accumulator.py` — tests aggregation. | covered | MVP candidate | MANIA scientific MVP | Backbone-only edges may legitimately lack a contact frequency. | Stage 19.2 |
| `mean_dist_A`, `std_dist_A` | Edge attributes | Backend contract | `src/mania/preprocessing/trajectory_contact_accumulator.py` — computes distance aggregates; `tests/test_preprocessing_interaction_accumulator.py` — tests finalized values. | covered | MVP candidate | MANIA scientific MVP | Optional frontend enrichment, not WANIA base-render data. | Stage 19.2 |
| `condition` | Edge attributes | Backend and WANIA contracts | `src/mania/constants.py` — requires the backend edge condition; `tests/test_wania_graph_artifact_mapping_v0_1.py` — validates condition-scoped WANIA edges. | covered | accepted required | WANIA frontend payload MVP | Required in the WANIA edge profile and present in MANIA artifacts. | None; contract frozen |
| `weight = contact_freq` | Edge attributes | Analysis v1.3 reference | `src/mania/analysis/graph_metrics.py` — defaults `weight_field` to `contact_freq` and uses it for strength/weighted analysis. | partially covered | MVP candidate | MANIA scientific MVP | Implemented as analysis interpretation, not as a separate persisted `weight` edge field. | Stage 19.2 |

### 4.5 RIN analysis artifacts

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `graph.json` | Analysis artifact | Backend contract; Stage 21.A/21.F | `src/mania/analysis/static_rin_graph.py` — deterministically builds and writes a per-condition static analysis graph; `tests/test_analysis_stage21_artifact_validation.py` — validates its schema, identity, weights, provenance, ordering, and cross-artifact node sets. | covered and validated | accepted required | MANIA scientific MVP | Recommended analysis layout is `analysis/{condition}/graph.json`. It reuses central `EDGE_TYPE_PRIORITY`, retains all typed aggregates, and is neither the older workflow `graph/graph.json` nor the WANIA frontend payload. | Stage 21.F complete |
| `centrality_{cond}.csv` | Analysis artifact | Stage 21.B/21.F | `src/mania/analysis/static_rin_metrics.py` — writes deterministic `centrality_{condition}.csv`; `tests/test_analysis_stage21_artifact_validation.py` — validates schema, graph identity, condition, ordering, and comparison provenance. | covered and validated | MVP candidate | MANIA scientific MVP | The accepted Stage 21.B artifact is separate from the legacy `metrics_<condition>.csv` path. | Stage 21.F complete |
| `communities_{cond}.csv` | Analysis artifact | Analysis v1.3 reference; Stage 21.C/21.F | `src/mania/analysis/static_rin_communities.py` — writes deterministic assignments; Stage 21.F contract tests validate graph identity, sizes, count, ordering, and truthful `greedy_modularity_unweighted` metadata. | covered and validated | accepted required | MANIA scientific MVP | Includes Stage 21.A node identity, community size, actual algorithm, modularity, and community count; not required in WANIA payload rows. | Stage 21.F complete |
| `region_enrichment_{cond}.csv` | Analysis artifact | Stage 21.D/21.F | `src/mania/analysis/static_rin_region_enrichment.py` — joins accepted graph labels to communities; Stage 21.F validates schema, references, labels, raw p-values, statuses, and ordering. | covered when existing region labels provide valid margins; otherwise explicitly skipped | optional candidate | Optional scientific artifact | Uses labeled nodes only, reports raw two-sided Fisher p-values, and never infers regions from residue numbers or adds FDR. | Stage 21.F complete |
| `stats.csv`, `comparison.csv` | Analysis artifact | Analysis v1.3 reference; Stage 21.E/21.F | `src/mania/analysis/static_rin_comparison.py` — writes deterministic root-level comparison and method/status rows; Stage 21.F validates schemas, stable identity provenance, counts, skipped scopes, and empty p-value fields. | covered and validated for conservative node-metric comparisons | MVP candidate | MANIA scientific MVP | Missing values remain missing; identity conflicts and deferred edge/community/region scopes are explicit. The scientific schema does not modify the WANIA-facing skeleton. | Stage 21.F complete |
| `temporal_rin_{cond}.csv` | Analysis artifact | Analysis v1.3 reference; Stage 22.C/22.G | `src/mania/analysis/temporal_rin_metrics.py` — computes deterministic metrics from accepted Stage 22.B window graphs and atomically writes one row per window; Stage 22.G validates schema, bytes, window identity, and truthful skipped metrics. | covered and validated | MVP candidate | MANIA scientific MVP | Stable identity/status fields accompany counts, density, degree/strength, unweighted path summaries, and truthful `greedy_modularity_unweighted` community summaries. The artifact remains separate from WANIA base rendering. | Stage 22.G complete |
| `conformation_labels_{cond}.csv` | Analysis artifact | Analysis v1.3 reference; Stage 22.F/22.G | `src/mania/analysis/conformation_clustering.py` — writes deterministic fingerprint-based labels and representatives; Stage 22.G validates schema, bytes, frame identity, PCA-unavailable metadata, and skipped fields. | covered and validated as `conformation_labels_{condition}.csv` | MVP candidate | MANIA scientific MVP | The accepted artifact deliberately does not claim notebook PCA-to-k-means parity and remains separate from planned legacy `conformational_states.csv` naming. | Stage 22.G complete |
| `conformation_pca_{cond}.csv` | Analysis artifact | Analysis v1.3 reference; Stage 22.E/22.G; Stage 24.A | `src/mania/analysis/conformation_pca.py` — consumes accepted Stage 22.D fingerprints and atomically writes a deterministic per-frame artifact; Stage 22.G validates schema, bytes, frame identity, and blank unavailable fields; Stage 24.A adds optional centered NumPy SVD computation when `enable_pca=True`. | covered and validated with explicit disabled/skipped/computed statuses | optional candidate | optional scientific artifact | Default PCA remains disabled and preserves blank `pca_unavailable` rows with `n_components = 0`. Explicit PCA uses only `ContactFingerprintMatrix.values`, emits finite rank-supported coordinates and explained-variance ratios, and leaves unavailable components blank. PCA-based clustering is handled separately by explicit Stage 24.B opt-in mode. | Stage 24.A complete; Stage 24.B complete for optional PCA clustering |
| `mania analyze` | Analysis orchestration CLI | Stage 24.C roadmap | `src/mania/analysis/orchestration.py` — validates requested Stage 20 artifact roots and conditions, orchestrates accepted Stage 21/22 APIs, writes the accepted `analysis/` layout, preserves disabled-PCA and fingerprint-clustering defaults, and returns deterministic stdout JSON; `tests/test_cli_analyze.py` covers help, default/PCA/PCA-clustering runs, invalid combinations, input validation, single/multi-condition comparison, determinism, no raw-MD calls, and WANIA non-invocation. | covered and validated through Stage 24.E | MVP candidate | MANIA scientific MVP | This is a backend orchestration command only. It does not read raw trajectories, rerun preprocessing, invoke WANIA, change WANIA required fields/runtime schema/adapter/capabilities/artifact mapping, or add API/frontend/Docker/database/worker code. The stdout JSON remains a compact command summary, not the persisted manifest. | Stage 24.E complete; Stage 24 closed |
| `extended_metrics.json` | Analysis manifest | Stage 24.D roadmap | `src/mania/analysis/extended_metrics.py` — writes `analysis/extended_metrics.json` with schema version `mania.extended_metrics.v0.1` from current-run `AnalyzeRunResult` artifact ownership; `tests/test_analysis_extended_metrics.py` covers default, PCA, PCA-clustering, degenerate PCA, single-condition comparison, relative-path containment, stale-file exclusion, deterministic bytes, no embedded scientific tables, and WANIA non-integration. | covered and validated through Stage 24.E | backend/internal | MANIA scientific MVP | MANIA-only compact index/status manifest. It records condition-level and run-level statuses, PCA intent versus computation status, clustering provenance, requested/used PCA components, diagnostics, limitations, and portable `analysis/` artifact references. It does not duplicate scientific rows, parse stdout, scan stale output files, alter WANIA payloads, or implement API/frontend integration. | Stage 24.E complete; Stage 24 closed |

### 4.6 Analysis metrics

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `degree`, `strength`, `betweenness`, `closeness`, `eigenvector`, `pagerank` | Analysis metrics | Analysis v1.3 reference | `src/mania/analysis/graph_metrics.py` — computes all six metrics; `tests/test_analysis_graph_metrics.py` — regression-tests the analysis API. | covered | MVP candidate | MANIA scientific MVP | Separate scientific metrics; not required WANIA node fields. | Stage 19.2 |
| `k_core` | Analysis metrics | Stage 19 context; analysis v1.3 reference | `src/mania/analysis/graph_metrics.py` — computes core numbers under the name `kcore`; tests cover the output. | partially covered | MVP candidate | MANIA scientific MVP | Naming gap: `k_core` versus accepted backend/notebook export `kcore`. | Stage 19.2 |
| `community` | Analysis metrics | Analysis v1.3 reference; Stage 21.C/21.F | `src/mania/analysis/static_rin_communities.py` — assigns stable one-based communities and explicitly reports `greedy_modularity_unweighted`; Stage 21.F validates identity, sizes, counts, and algorithm metadata. | covered and validated for the Stage 21.A graph | accepted required | MANIA scientific MVP | Louvain is unavailable within the accepted dependency boundary; the deterministic fallback is not mislabeled. | Stage 21.F complete |
| `modularity` | Analysis metrics | Analysis v1.3 reference; Stage 21.C/21.F | `src/mania/analysis/static_rin_communities.py` — computes deterministic unweighted modularity; Stage 21.F validates its stable artifact representation. | covered and validated for the Stage 21.A graph | accepted required | MANIA scientific MVP | Community quality is backend scientific output, not a required WANIA field. | Stage 21.F complete |
| `NMI`, `ARI` | Analysis metrics | Analysis v1.3 reference | `data/reference/notebooks_libraries_v1_3/MANIA_analysis_v1_3.ipynb` — specifies cross-condition partition comparison; `docs/notebook_parity_audit_v1_3.md` — does not list a backend implementation. | missing | optional candidate | optional scientific artifact | Requires an explicit cross-condition node mapping/partition contract. | Stage 19.2 |
| `Fisher enrichment` | Analysis metrics | Analysis v1.3 reference; Stage 21.D/21.F | `src/mania/analysis/static_rin_region_enrichment.py` — computes dependency-free two-sided Fisher exact tests; Stage 21.F validates auditable tables, graph labels, raw p-values, and statuses. | covered and validated for existing Stage 21.A region labels | optional candidate | optional scientific artifact | Missing labels are excluded, not classified; no region-number mapping, correction, or cross-condition claim is introduced. | Stage 21.F complete |
| `MWU`, `FDR-BH`, `Cohen's d`, `Bootstrap CI` | Analysis metrics | Analysis v1.3 reference; Stage 21.E | `src/mania/analysis/static_rin_comparison.py` — computes Cohen's dz only for sufficient complete pairs with defined sample variance and reports paired mean delta. | partially covered | MVP candidate | MANIA scientific MVP | MWU, bootstrap CI, p-values, and FDR-BH remain unimplemented. `stats.csv` records empty p-value fields and `correction=none`; no significance claim is emitted. | Stage 21.E complete; remaining methods require separate approval |

### 4.7 Temporal RIN and conformation

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `TEMP_WINDOW`, `TEMP_STEP`, `TEMP_MIN_FREQ` | Temporal RIN | Analysis v1.3 reference; Stage 22.A | `src/mania/analysis/temporal.py` — exposes validated defaults `10`, `10`, and `0.25`, validates accepted Stage 20 per-frame input, and generates deterministic sampled-frame windows; focused synthetic tests cover validation and boundary behavior. | covered for input/config/window contract | MVP candidate | MANIA scientific MVP | Windows use sorted observed frame indexes, zero-based IDs, inclusive source-frame boundaries, partial trailing windows, and `sampled_frame_count` as the later contact-frequency denominator. | Stage 22.A complete |
| Window-level RIN | Temporal RIN | Analysis v1.3 reference; Stage 22.B | `src/mania/analysis/temporal_rin_windows.py` — groups validated rows by accepted window/pair/type, computes frequency with `sampled_frame_count`, applies inclusive `TEMP_MIN_FREQ`, retains passing types in `EDGE_TYPE_PRIORITY` order, and builds deterministic in-memory graphs. | covered for internal graph construction | MVP candidate | MANIA scientific MVP | Empty/no-passing windows remain explicit. Available distances receive deterministic mean, population-standard-deviation, minimum, and maximum summaries without replacing missing values with zero. No temporal metrics, public CSV export, or WANIA change is included. | Stage 22.B complete; Stage 22.C remains separate |
| Temporal graph metrics | Temporal RIN | Stage 22.C | `src/mania/analysis/temporal_rin_metrics.py` — reuses Stage 21.B metric behavior and the Stage 21.C deterministic community fallback over accepted Stage 22.B graphs. | covered at Stage 22.C | MVP candidate | MANIA scientific MVP | Strength uses primary window contact frequency; betweenness, closeness, modularity, and communities are unweighted. Empty/no-passing windows have explicit statuses and no invented derived metrics. | Stage 22.C complete |
| Contact fingerprint matrix | Conformation | Analysis v1.3 reference; Stage 22.D | `src/mania/analysis/contact_fingerprints.py` — consumes accepted Stage 22.A validated rows and builds a deterministic dependency-light frame-by-normalized-pair/type binary matrix with separate frame and feature metadata. | covered internally at Stage 22.D | MVP candidate | MANIA scientific MVP | Rows use sampled `frame_index` identity without inferring gaps; columns retain separate edge types in `EDGE_TYPE_PRIORITY` order; values are only 0/1 membership. No public fingerprint or conformation artifact is added. | Stage 22.D complete |
| `PCA` | Conformation | Analysis v1.3 reference; Stage 22.E; Stage 24.A | `src/mania/analysis/conformation_pca.py` — validates binary Stage 22.D values, preserves frame metadata, exports the stable artifact contract, and computes optional centered NumPy SVD PCA only when `enable_pca=True`. | optional computed PCA covered | MVP candidate | MANIA scientific MVP | Default nonconstant inputs still use `pca_unavailable` with blank coordinates. Explicit PCA computes up to three numerical-rank-supported components with deterministic sign stabilization and finite explained-variance ratios. Degenerate and failed inputs emit no fake values. | Stage 24.A complete |
| `k-means`, `silhouette`, `conformation_labels_{condition}.csv` | Conformation | Analysis v1.3 reference; Stage 22.F/22.G; Stage 24.B | `src/mania/analysis/conformation_clustering.py` — consumes the Stage 22.D binary contact fingerprint matrix by default, or a computed in-memory PCA projection when `clustering_basis="pca"` is explicit. Both bases reuse deterministic dependency-free k-means, valid silhouette scoring, state-ID stabilization, representative selection, and atomic per-frame label export; Stage 22.G and Stage 24.B tests validate schema, bytes, frame coverage, metadata, skipped values, PCA component selection, and identity checks. | covered from contact fingerprints and optional PCA coordinates | MVP candidate | MANIA scientific MVP | The default artifact records fingerprint input and unavailable/not-used PCA. Optional PCA mode records `deterministic_kmeans_pca`, `conformation_pca_coordinates`, and `pca_status = computed`. PCA is not silently enabled, supplying a projection alone does not switch modes, invalid PCA configuration does not fall back to fingerprints, and notebook PCA-to-k-means parity is not claimed. | Stage 24.B complete |
| Representative frames | Conformation | Analysis v1.3 reference; Stage 22.F/22.G; Stage 24.B | `src/mania/analysis/conformation_clustering.py` — selects the frame nearest each computed centroid in the active clustering space and breaks ties by `frame_index`; tests require exactly one representative per computed state and none for skipped rows. | covered and validated for computed clusters | optional candidate | optional scientific artifact | Fingerprint representatives use fingerprint space; PCA representatives use PCA coordinate space. Do not confuse conformation representatives with representative first-frame Cα coordinates. | Stage 24.B complete |
| Stage 22 temporal/conformation validation | Validation | Stage 22.G | `tests/test_analysis_stage22_artifact_validation.py` validates all three public schemas, deterministic bytes, window/frame identity, PCA/label/fingerprint coverage, truthful unavailable/skipped fields, and WANIA-field separation; `tests/test_analysis_stage22_docs.py` freezes accepted and deferred claims. | covered at Stage 22.G | accepted required | MANIA scientific MVP | Validation only: no schema, scientific algorithm, dependency, computed PCA, WANIA contract, or Stage 23 implementation change. | Stage 22.G complete |

### 4.8 WANIA alignment

| Requirement | Requirement group | Source / context | Repo evidence | Current repo status | Classification | Layer | Gap / notes | Suggested follow-up stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Accepted `wania_graph_payload.json` | WANIA alignment | Accepted Stage 18.3 state | `tests/test_wania_demo_export_command_v0_1.py` — runs `mania wania build-payload`, writes the named payload, and validates the required profile. | covered | accepted required | WANIA frontend payload MVP | The generated demo output is intentionally not committed at repository root. | None; contract frozen |
| `graph.nodes`, `graph.edges` | WANIA alignment | WANIA v0.1 contract | `tests/test_wania_graph_artifact_mapping_v0_1.py` — validates both arrays in assembled payloads; `src/mania/wania/graph_payload.py` — constructs them. | covered | accepted required | WANIA frontend payload MVP | Base rendering does not require optional scientific artifacts. | None; contract frozen |
| `x/y/z` render coordinates | WANIA alignment | WANIA required-fields profile | `tests/test_wania_graph_artifact_mapping_v0_1.py` — requires finite render coordinates for mapped nodes. | covered | accepted required | WANIA frontend payload MVP | `x_ca/y_ca/z_ca` remain optional scientific coordinates. | None; contract frozen |
| `interaction.primary_type` | WANIA alignment | WANIA required-fields profile | `src/mania/wania/graph_payload.py` — maps the backend primary edge type; `tests/test_wania_demo_export_command_v0_1.py` — validates every demo edge. | covered | accepted required | WANIA frontend payload MVP | No parallel WANIA `edge_type` field should be introduced. | None; contract frozen |
| `interaction.all_types` | WANIA alignment | WANIA optional enrichment | `src/mania/wania/graph_payload.py` — preserves all backend edge types; `tests/test_wania_graph_artifact_mapping_v0_1.py` — tests rich versus minimal payload behavior. | covered | optional candidate | WANIA frontend payload MVP | Optional progressive enrichment, not required for basic rendering. | None; contract frozen |
| `capabilities` | WANIA alignment | WANIA v0.1 contract | `src/mania/wania/graph_payload.py` — emits availability flags; `tests/test_wania_graph_artifact_mapping_v0_1.py` — checks that values are boolean and future capabilities stay false. | covered | accepted required | WANIA frontend payload MVP | Capability true does not make optional science required. | None; contract frozen |
| `artifacts` | WANIA alignment | WANIA v0.1 contract | `src/mania/wania/graph_payload.py` — emits portable relative references; `tests/test_wania_graph_artifact_mapping_v0_1.py` — checks the required object and safe paths. | covered | accepted required | WANIA frontend payload MVP | Individual scientific references remain optional. | None; contract frozen |
| `diagnostics` | WANIA alignment | Accepted Stage 18.3 state | `tests/test_wania_demo_export_command_v0_1.py` — requires `diagnostics.passed` to be boolean and rejects `null` for demo output. | covered | accepted required | WANIA frontend payload MVP | At Stage 19.1, older Stage 17 prose still permitted null; Stage 19.3 reconciles the prose without changing the Stage 18.3 demo guardrail. | Contract frozen; documentation reconciled in Stage 19.3 |

## 5. Naming and contract mismatch notes

The following differences must not be silently normalized:

- `contacts_per_frame_{cond}.parquet` (Stage 19 list) versus
  `contacts_perframe_{cond}.parquet` (repository notebooks/reference exports)
  versus `contacts/contacts_perframe.csv` (older combined backend artifact):
  Stage 20.B explicitly accepts per-condition
  `contacts_perframe_{cond}.csv`; parquet and the second underscore remain
  unimplemented rather than silent aliases.
- `non_protein_nodes_{cond}.csv` versus notebook/reference
  `nonprotein_nodes_{cond}.csv`: naming gap.
- `res_i/res_j` versus backend `resid_i/resid_j` and historical intermediate
  `i/j`: contract naming mismatch.
- `centrality_{cond}.csv` versus current analysis
  `metrics_<condition>.csv`: artifact naming/contents gap.
- `dssp` versus backend `ss`, and `k_core` versus backend `kcore`: field naming
  gaps that need confirmation.
- Notebook coordinate names `xca/yca/zca` versus backend
  `x_ca/y_ca/z_ca`; the backend also supplies WANIA render aliases `x/y/z`.
- `rg_mean/rg_std` are graph-level notebook features, while backend contract
  prose uses `rg_mean_A/rg_std_A`; treating them as node attributes would be a
  shape and naming mismatch.
- Historical `conformation_labels_{cond}.csv` versus planned backend
  `conformational_states.csv`: artifact naming/schema gap.
- Historical temporal exports use fields such as `cond`, `frame_start`, and
  `frame_end`, while `src/mania/constants.py` plans `condition`, `window_id`,
  and time boundaries: schema mismatch.
- `docs/wania_required_fields_contract_v0_1.md` and
  `docs/wania_json_assembly_profile_v0_1.md` retain older nullable
  `diagnostics.passed` prose, while the accepted Stage 18.3 command test
  requires a boolean demo payload value. Stage 19.1 records this inconsistency
  but does not change either contract or runtime behavior. Stage 19.3 later
  reconciles that prose with the already accepted boolean requirement.

## 6. MVP, optional, and future separation

- **WANIA frontend payload MVP:** the frozen render contract consists of the
  accepted required payload structure, renderable `graph.nodes` and
  `graph.edges`, node `x/y/z`, edge `interaction.primary_type`, capability
  signals, artifact-reference object, and diagnostics. Centrality,
  communities, temporal RIN, conformation, and full typed chemistry are not
  required for base rendering.
- **MANIA scientific MVP candidates:** preprocessing graph/contact/Rg
  artifacts; accepted graph attributes; graph metrics/community output;
  statistical/comparison artifacts; and the temporal/conformation candidates
  listed above. Stage 19.2 must freeze which candidates are immediate MVP
  requirements and which remain roadmap items.
- **Optional scientific artifacts:** non-protein node/contact exports,
  phi/psi, graph-level Rg enrichment, NMI/ARI, Fisher enrichment,
  conformation PCA detail, and representative-frame output are useful science
  candidates but must not become WANIA render requirements by implication.
- **v2/future scope:** inter-protein/cross-protein interactions and comparison
  remain v2 unless a separate explicit decision supplies identity/mapping
  semantics. FastAPI, Docker, databases, background workers, a production API,
  and frontend implementation are out of Stage 19.

Temporal RIN may be frozen into the MANIA scientific MVP roadmap, but it is
not required for WANIA base graph rendering. Communities and centrality remain
separate MANIA scientific artifacts and do not automatically become required
fields in `wania_graph_payload.json`.

## 7. Open questions

1. Which naming/layout is canonical for Stage 19.2: notebook-style flat
   artifacts, the current backend workflow layout, or an explicit adapter
   mapping for each item?
2. Are all recognized protein edge types required for the first scientific
   MVP, or should only currently implemented backbone and π interactions be
   frozen initially?
3. Are non-protein nodes/edges part of the scientific MVP or optional
   heterograph artifacts?
4. Should structural features be computed in the scientific MVP, merely
   preserved when supplied, or split by feature (`RMSF`, `SASA`, DSSP,
   phi/psi, TM-relative Z)?
5. Are `rg_mean/rg_std` definitively graph-level values, and what unit-bearing
   canonical names should be used?
6. Should the production centrality artifact retain `metrics_<condition>.csv`
   or adopt/map `centrality_{cond}.csv`?
7. Which formal statistics and temporal/conformation artifacts are immediate
   scientific MVP requirements rather than post-MVP roadmap items?
## 8. Suggested next step

Stage 19.2 — MANIA RIN MVP scope document
