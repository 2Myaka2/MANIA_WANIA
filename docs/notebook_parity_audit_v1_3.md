# Notebook parity audit v1.3

## 1. Executive summary

This audit compares the accepted Stage 16 backend with the reference
`MANIA_preprocessing_v1_2` and `MANIA_analysis_v1_3` notebooks. It records
feature-level parity; it does not claim that the backend and notebooks are
fully identical.

The backend implements the Stage 16 frame-sampling, contact-selection,
contact-aggregation, atom-cache, backbone, typed π-interaction, representative
coordinate, graph-analysis, and WANIA sample work described below. Important
gaps remain: representative Cα coordinates are not full Kabsch parity,
notebook parquet output is not required, and formal statistics, temporal RIN,
conformational clustering, figures, and YaDisk behavior are outside the
accepted production backend.

The notebooks are reference/spec artifacts. The notebooks are not executable
CI dependencies, and there is no real MD data in default CI. Default tests use
synthetic or fixture data and do not execute either notebook.

## 2. Scope and sources

Audited sources:

- `data/reference/notebooks_libraries_v1_3/MANIA_preprocessing_v1_2.ipynb`
- `data/reference/notebooks_libraries_v1_3/MANIA_analysis_v1_3.ipynb`
- `docs/notebook_gap_report_v1_3.md`
- `docs/wania_mvp_contract_v0_1.md`
- `tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json`

Backend implementation and contract files were used to verify names,
artifacts, and accepted semantics. This is a documentation audit, not a
notebook execution result or a real-MD output-equality claim.

The status vocabulary in the matrices is limited to:
`implemented`, `partially implemented`, `implemented with backend-specific
semantics`, `deferred`, `not applicable to backend`, and `not executed in CI`.

## 3. Backend stages covered

| Backend stage | Accepted scope relevant to this audit |
|---|---|
| Stage 16.1 | Stable WANIA object JSON adapter and schema contract |
| Stage 16.2 | Source-frame sampling with original frame indexes |
| Stage 16.3 | Contacts progress and optional safety limits |
| Stage 16.4 | `contact_selection=all` and `contact_selection=protein` |
| Stage 16.5 | Representative Cα coordinates in graph and WANIA nodes |
| Stage 16.6 | Structural `backbone` edges and `EDGE_PRIORITY` |
| Stage 16.7 | `InteractionAccumulator`-style typed contact aggregation |
| Stage 16.8 | `build_atom_cache`-style pre-frame contact caching |
| Stage 16.9 | Accepted per-frame contact/backbone CSV export semantics |
| Stage 16.10 | `aromatic_pi` and `cation_pi` chemistry |
| Stage 16.11 | Analysis graph metrics/community MVP and artifact writer |
| Stage 16.12 | Deterministic WANIA frontend sample |

Stages before 16 remain relevant where the Stage 16 work deliberately reuses
the accepted manifest, graph export, scientific CSV, and diagnostics paths.

## 4. Preprocessing notebook parity matrix

| Notebook feature | Notebook location | Backend status | Backend stage | Backend artifact/module | Notes / semantic differences |
|---|---|---|---|---|---|
| Input/config paths | Step 3, Cells 6–7 | implemented with backend-specific semantics | Accepted pre-16 manifest boundary | `src/mania/preprocessing/trajectory_manifest_loader.py`; explicit manifest and output paths | The backend uses validated manifests and caller-supplied paths; it does not use notebook-local, Colab, or YaDisk path defaults. |
| `contact_selection` / protein-only scope | Step 7, Cells 18–19 | implemented with backend-specific semantics | Stage 16.4 | `src/mania/preprocessing/trajectory_contacts.py` | `all` preserves full-system behavior; `protein` uses the runtime protein selection without a protein-specific residue list. |
| Frame sampling | Steps 6–8 | implemented | Stage 16.2 | `src/mania/preprocessing/trajectory_frame_sampling.py` | Start/stop/stride/max-frame sampling preserves original source frame indexes across accepted computations and exports. |
| Contacts progress and safety limits | Step 7, Cell 19 | implemented with backend-specific semantics | Stage 16.3 | `src/mania/preprocessing/trajectory_contacts.py` | Progress callbacks and optional pair/distance-evaluation guards fail clearly rather than treating partial contacts as complete. |
| `InteractionAccumulator` | Step 7, Cell 19 | implemented with backend-specific semantics | Stage 16.7 | `src/mania/preprocessing/trajectory_contact_accumulator.py` | The backend canonicalizes residue pairs and uses sampled-frame count as frequency denominator. Structural per-frame backbone rows remain a separate path. |
| `build_atom_cache` concept | Step 7 v1.2 notes and Cell 19 | implemented with backend-specific semantics | Stage 16.8 | `src/mania/preprocessing/trajectory_contacts.py` | Backend `build_atom_cache` caches stable residue metadata and selected atom references before frame iteration; positions remain frame-specific. No timing guarantee or new neighbor search is claimed. |
| Backbone edge type | Step 7 and Step 7b, Cells 19–21 | implemented | Stage 16.6 and Stage 16.9 | `src/mania/preprocessing/trajectory_graph_export.py`; `contacts/contacts_perframe.csv` | Graph backbone joins sequential same-condition, same-chain protein residues within 4.5 Å; Stage 16.9 adds live per-frame backbone observations for protein selection. |
| `EDGE_PRIORITY` | Step 11 export semantics | implemented with backend-specific semantics | Stage 16.6 | `src/mania/constants.py`; `src/mania/preprocessing/trajectory_graph_export.py` | Notebook `EDGE_PRIORITY` maps to backend `EDGE_TYPE_PRIORITY`. Canonical snake_case names are used, and `backbone` is highest priority while all overlapping types remain available. |
| Per-frame contacts export | Step 7b, Cells 20–21 | implemented with backend-specific semantics | Stage 16.9 | `contacts/contacts_perframe.csv` | Accepted contact types and backbone preserve source frame indexes. The backend uses opt-in CSV rather than required parquet and does not claim a full temporal RIN. |
| `aromatic_pi` detection | Step 7, Cell 19 | implemented with backend-specific semantics | Stage 16.10 | `src/mania/preprocessing/trajectory_interaction_geometry.py`; `src/mania/preprocessing/trajectory_contact_chemistry.py` | Complete supported rings use deterministic best-fit-plane normals, a 7.0 Å centroid cutoff, and accepted parallel/T-shaped angle rules. The implementation is dependency-free rather than an identical SVD stack. |
| `cation_pi` detection | Step 7, Cell 19 | implemented with backend-specific semantics | Stage 16.10 | `src/mania/preprocessing/trajectory_interaction_geometry.py`; `src/mania/preprocessing/trajectory_contact_chemistry.py` | The accepted backend uses LYS NZ or ARG CZ and distance below 6.0 Å to a supported ring centroid. It does not claim the notebook narrative's additional cation-to-ring-normal angle behavior. |
| Cα coordinates | Step 8, Cells 22–23 | implemented with backend-specific semantics | Stage 16.5 | `graph/nodes.csv`; `graph/graph.json`; `src/mania/wania/graph_payload.py` | Backend nodes carry `x/y/z` plus `x_ca/y_ca/z_ca`. These are representative Cα coordinates from the first sampled condition frame, not trajectory averages. |
| Kabsch alignment semantics | Step 8, Cells 22–23 | deferred | Stage 16.5 boundary | No backend alignment artifact | The coordinate implementation is not full Kabsch parity; cross-condition alignment and notebook `CA_COORDS` reconciliation are not claimed. |
| Scientific CSV exports | Step 11, Cells 28–29 | partially implemented | Accepted pre-16 exports plus Stage 16.9–16.10 | `rg/rg_timeseries.csv`; `contacts/contact_edges.csv`; `contacts/contacts_perframe.csv` | Accepted outputs are optional CSVs. Required notebook parquet output and the full notebook residue-feature export set remain outside this stage. |
| Graph export | Steps 10–11, Cells 26–29 | implemented with backend-specific semantics | Accepted Stage 15 plus Stage 16.5–16.6 | `graph/graph.json`; `graph/nodes.csv`; `graph/edges.csv` | The backend preserves its accepted graph schema, adds representative coordinates and backbone semantics, and does not emit notebook framework objects. |
| Diagnostics/reporting | Steps 3b and 11 | implemented with backend-specific semantics | Accepted Stage 15 diagnostics | `src/mania/preprocessing/trajectory_graph_diagnostics.py`; `reports/graph_diagnostics_report.json` | Backend graph diagnostics are deterministic workflow artifacts; they are not the notebook's full interactive print/QC report set. |
| Notebook execution and real-MD equality | Whole notebook | not executed in CI | Stage 16.13 boundary | Optional manual validation only | The notebook is a reference/spec artifact. Real-MD notebook output equality is not a default-CI claim. |

## 5. Analysis notebook parity matrix

| Notebook feature | Notebook location | Backend status | Backend stage | Backend artifact/module | Notes / semantic differences |
|---|---|---|---|---|---|
| Input/output path conventions | Cells 3b–4, Cells 8–11 | implemented with backend-specific semantics | Accepted backend artifact layout | Explicit `graph/graph.json` input and caller-selected `analysis/` output | The backend does not download artifacts, discover notebook folders, or rely on Colab/YaDisk paths. |
| Graph QC | Cell 6, Cells 14–15 | implemented with backend-specific semantics | Accepted pre-16 diagnostics | `src/mania/preprocessing/trajectory_graph_diagnostics.py`; `reports/graph_diagnostics_report.json` | Backend diagnostics validate accepted graph artifacts; they are not a line-for-line execution of notebook `GraphQC`. |
| Centrality metrics | Cell 7, Cells 16–17 | implemented with backend-specific semantics | Stage 16.11 | `src/mania/analysis/graph_metrics.py`; `analysis/metrics_<condition>.csv` | The analysis graph metrics MVP computes degree, strength, betweenness, closeness, eigenvector, pagerank, and kcore per condition. |
| Community detection | Cell 8, Cells 18–19 | implemented with backend-specific semantics | Stage 16.11 | `src/mania/analysis/graph_metrics.py`; `analysis/communities_<condition>.csv` | Louvain with seed 42 is preferred when available; the accepted dependency boundary currently reports and uses deterministic greedy modularity fallback. |
| Node feature enrichment | Cells 7–8 and Cell 12 export | partially implemented | Stage 16.11 | `analysis/metrics_<condition>.csv` | Existing `region`, `ss`, `rmsf_A`, `sasa_A2`, identity, and coordinates are preserved when present; Stage 16.11 does not compute missing structural features or invent labels. |
| Cα coordinates in graph/WANIA nodes | Cell 12, Cells 26–27 | implemented with backend-specific semantics | Stage 16.5 and Stage 16.1 | `graph/graph.json`; `src/mania/wania/graph_payload.py` | The backend uses `x_ca/y_ca/z_ca` and `x/y/z`; coordinates are representative first-sampled-frame values rather than aligned trajectory averages. |
| `EDGE_PRIORITY` | Graph construction/export, Cells 12–13 and 26–27 | implemented with backend-specific semantics | Stage 16.6 | `src/mania/constants.py`; `src/mania/preprocessing/trajectory_graph_export.py` | Notebook `EDGE_PRIORITY` maps to backend `EDGE_TYPE_PRIORITY`; `backbone` has highest accepted priority and overlapping interaction types are preserved. |
| Analysis artifact export | Cell 12, Cells 26–27 | implemented with backend-specific semantics | Stage 16.11 | `src/mania/analysis/graph_metrics_export.py`; `analysis/analysis_metrics_report.json` | The explicit Python writer produces metrics/community CSVs and a report under `analysis/`; it is not yet part of the preprocessing CLI. |
| Formal statistical tests | Cell 9, Cells 20–21 | deferred | Future separately accepted stage | No backend artifact | Mann-Whitney U, FDR-BH, effect-size, and bootstrap-CI computation are not implemented. |
| Temporal RIN | Cell 10, Cells 22–23 | deferred | Future separately accepted stage | No `temporal_rin_<condition>.csv` | Per-frame contacts are not a sliding-window temporal RIN implementation. |
| Conformational clustering | Cell 11, Cells 24–25 | deferred | Future separately accepted stage | No conformation-label artifact | No backend conformational-state clustering is implemented. |
| PCA / k-means / silhouette | Cell 11, Cells 24–25 | deferred | Future separately accepted stage | No conformation-PCA artifact | No PCA, k-means, or silhouette pipeline is implemented. |
| Figures | Visualization Cell 28 | not applicable to backend | Notebook/reference scope | No production PNG artifacts | Figures are notebook/reference only; figure generation is not accepted backend production behavior. |
| YaDisk download/upload | Cell 3b and Cell 12b, Cells 8–9 and 29–30 | not applicable to backend | Notebook/reference scope | No YaDisk module or artifact | YaDisk notebook/reference only behavior is intentionally absent from the production backend. |
| WANIA/frontend sample | Cell 12 export intent | implemented with backend-specific semantics | Stage 16.12 | `tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json` | The WANIA frontend sample is compact, deterministic, synthetic, and safe for default CI; it is not a real-MD benchmark or frontend implementation. |
| Full analysis notebook rewrite | Whole notebook | deferred | Current backend boundary | No notebook runner | The current goal is a dependency-light metrics/community MVP, not production execution or a complete rewrite of every notebook analysis. |
| Notebook execution | Whole notebook | not executed in CI | Stage 16.13 boundary | Reference/spec artifact only | Default CI reads stable docs/fixtures and does not execute the notebook. |

## 6. WANIA/frontend payload parity

| Notebook/WANIA concern | Backend status | Backend stage | Backend artifact/module | Notes / semantic differences |
|---|---|---|---|---|
| Object JSON payload contract | implemented with backend-specific semantics | Stage 16.1 | `src/mania/wania/graph_payload.py` | The backend keeps the WANIA payload object JSON contract stable and separate from backend `graph/graph.json`. |
| WANIA MVP frontend profile | documented contract freeze | Stage 17.1 | `docs/wania_mvp_contract_v0_1.md` | The frontend may rely on the required MVP subset without treating optional scientific/backend fields as required. |
| Node coordinates and identity | implemented | Stage 16.5 | WANIA `graph.nodes` | Accepted graph identity and representative coordinates are preserved; the Stage 17.1 MVP keeps coordinates optional. |
| Backbone and typed edge preservation | implemented | Stage 16.6 and Stage 16.10 | WANIA `graph.edges` | Primary priority and all interaction types remain available without claiming full typed-RIN capability or making those types required by the MVP. |
| Analysis artifact references | implemented with backend-specific semantics | Stage 16.11 and Stage 16.12 | WANIA `artifacts` plus the frontend sample | The payload may reference separate metrics/community/report artifacts; analysis rows are not embedded. |
| Temporal, formal-statistical, and conformational capability flags | implemented | Stage 16.1 and Stage 16.12 | WANIA `capabilities` | Unsupported capabilities remain false instead of being inferred from notebook plans. |
| Upload/job API and frontend application | not applicable to backend | Future product scope | No FastAPI endpoint or frontend module | Stage 16.13 adds no FastAPI, upload/job API, or frontend implementation. |

## 7. Backend module and artifact mapping

| Notebook concept | Backend module or artifact |
|---|---|
| `InteractionAccumulator` | `src/mania/preprocessing/trajectory_contact_accumulator.py` |
| Atom cache / `build_atom_cache` | `src/mania/preprocessing/trajectory_contacts.py` |
| Aromatic/cation-π geometry | `src/mania/preprocessing/trajectory_interaction_geometry.py` |
| Aromatic/cation-π chemistry | `src/mania/preprocessing/trajectory_contact_chemistry.py` |
| Graph export, backbone, and priority | `src/mania/constants.py`; `src/mania/preprocessing/trajectory_graph_export.py` |
| WANIA payload | `src/mania/wania/graph_payload.py` |
| Analysis metrics/community computation | `src/mania/analysis/graph_metrics.py` |
| Analysis export | `src/mania/analysis/graph_metrics_export.py` |
| WANIA frontend sample | `tests/fixtures/wania_graph_payload_frontend_sample_v0_1.json` |
| Backend graph object | `graph/graph.json` |
| Backend graph node table | `graph/nodes.csv` |
| Backend graph edge table | `graph/edges.csv` |
| Aggregate scientific contacts | `contacts/contact_edges.csv` |
| Per-frame scientific contacts | `contacts/contacts_perframe.csv` |
| Graph diagnostics | `reports/graph_diagnostics_report.json` |
| Per-condition analysis metrics | `analysis/metrics_<condition>.csv` |
| Per-condition communities | `analysis/communities_<condition>.csv` |
| Analysis report | `analysis/analysis_metrics_report.json` |

## 8. Known intentional differences

- The backend does not execute notebooks in CI and requires no real MD data in
  default CI.
- Local/generated output artifacts are not committed.
- Backend Cα coordinates are representative first-sampled-frame coordinates,
  not trajectory averages, and the backend does not claim full Kabsch
  coordinate parity.
- Backend scientific exports use accepted opt-in CSV paths; required parquet
  output is deferred.
- The backend keeps the WANIA payload object JSON contract stable.
- `aromatic_pi` uses dependency-free best-fit-plane geometry. The accepted
  `cation_pi` rule is the center-to-centroid distance rule described in the
  preprocessing matrix; no additional cation-normal angle parity is claimed.
- The Stage 16.11 analysis writer is an explicit Python API, not a
  preprocessing CLI step.
- The backend does not implement FastAPI/upload/job API behavior, formal
  statistical tests, temporal RIN, conformational clustering, production
  figures, or YaDisk transfer behavior.
- No heavy dependencies for scipy, statsmodels, sklearn, or parquet support are
  added by this audit.

## 9. Deferred items

- Full Kabsch-aligned coordinate reconciliation and real-MD notebook output
  equality are deferred.
- Required parquet output is deferred; accepted CSV exports remain stable.
- formal statistics deferred: Mann-Whitney U, FDR-BH, effect sizes, and
  bootstrap confidence intervals.
- temporal RIN deferred: no sliding-window topology pipeline is claimed.
- conformational clustering deferred: PCA, k-means, silhouette scoring, and
  state labels are not implemented.
- Figure production is notebook/reference only.
- YaDisk notebook/reference only upload/download behavior is not production
  backend scope.
- A full analysis-notebook rewrite and automatic biological interpretation are
  deferred and are not implied by Stage 16.11.

## 10. Optional manual validation plan

This validation is optional, local-only, and not required in CI. It requires a
prepared local manifest and real MD files that remain outside version control:

```bash
mania preprocessing run-graph-export \
  --manifest local_md_small/manifests/napi2b_10ns.yaml \
  --output mania_output/napi2b_10ns_small_protein_graph_parity_audit \
  --expected-condition normal \
  --expected-condition tumor \
  --max-frames 1 \
  --contact-selection protein \
  --contact-max-residue-pairs-per-frame 500000 \
  --contact-max-distance-evaluations-per-frame 50000000 \
  --export-scientific-csvs \
  --export-contacts-perframe \
  --verbose
```

Then write Stage 16.11 artifacts through the Python API:

```python
from pathlib import Path

from mania.analysis.graph_metrics import (
    compute_analysis_graph_metrics_from_graph_json,
)
from mania.analysis.graph_metrics_export import (
    write_analysis_graph_metrics_artifacts,
)

root = Path("mania_output/napi2b_10ns_small_protein_graph_parity_audit")
result = compute_analysis_graph_metrics_from_graph_json(root / "graph" / "graph.json")
write_analysis_graph_metrics_artifacts(result, root / "analysis")
print(result.passed)
```

Manual checks:

- graph nodes contain `x/y/z` and `x_ca/y_ca/z_ca`;
- `backbone` edges exist for qualifying sequential protein residues;
- `aromatic_pi` and `cation_pi` appear when accepted geometry detects them;
- `contacts/contacts_perframe.csv` preserves source frame indexes;
- analysis metrics/community/report artifacts are written; and
- a WANIA payload can be built from the accepted artifacts and explicit run
  metadata.

Manual validation output must not be committed. A successful local smoke run
would increase confidence for that dataset, but it would not prove full
notebook identity.

## 11. Recommended next stages

Stage 19 freezes scope from this reference evidence; it does not execute the
notebooks or make them production runtime or CI inputs. See
`mania_rin_mvp_gap_matrix.md` and `mania_rin_mvp_scope_v0_1.md`.

The planning-level roadmap is Stage 20 RIN preprocessing parity, Stage 21 RIN
analysis parity, Stage 22 temporal RIN plus conformational artifacts, and Stage
23 WANIA RIN alignment. FastAPI/upload/job API, Docker/demo packaging,
database models, production API serving, and frontend implementation remain
separately scoped later work.
