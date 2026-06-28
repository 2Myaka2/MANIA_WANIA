# Preprocessing graph workflow boundary before frontend/API

## Purpose

Stage 15 completed the backend preprocessing graph export workflow boundary:

```text
manifest -> runtime loading -> in-memory Rg/contacts -> backend graph export
-> diagnostics/report -> optional reference comparison -> opt-in CLI
-> local-only smoke test
```

Stage 15.10 froze that backend workflow boundary before future frontend/API
work. Pre-16.4 adds optional scientific CSV side exports from already computed
Rg/contact results. It adds no new scientific computation behavior,
frontend/API schema, WANIA payload mapping, temporal RIN export, real-data CI,
or dependency change.

## Accepted Stage 15 sequence

- 15.1 plan/options/layout: defines in-memory workflow options, output layout,
  issues, and plan names; it must not be confused with workflow execution.
- 15.2 manifest readiness: checks an explicit manifest path and declared
  local input paths before runtime; it must not be confused with a new
  manifest format or runtime loading.
- 15.3 runtime loading: reuses accepted Stage 11 manifest runtime loading for
  explicit conditions; it must not be confused with a new runtime loader or
  scientific computation.
- 15.4 Rg + contacts in-memory orchestration: computes Rg and contacts in
  memory through accepted APIs; it must not be confused with CSV export.
- 15.5 graph export: writes backend graph artifacts through accepted Stage 14
  graph export APIs; it must not be confused with diagnostics, reference
  comparison, temporal RIN, or frontend/API payload generation.
- 15.6 diagnostics + diagnostics report: runs accepted graph diagnostics and
  may write the diagnostics report; it must not be confused with graph export
  or reference comparison.
- 15.7 optional reference comparison: compares explicit generated/reference
  graph artifact paths when enabled; it must not be confused with automatic
  reference artifact search, notebook execution, temporal RIN comparison, or
  expected mismatch classification.
- 15.8 opt-in CLI command: exposes a narrow command over accepted Stage 15
  APIs; it must not be confused with a broad CLI framework or automatic local
  data discovery.
- 15.9 local-only smoke test: verifies the accepted CLI workflow only when
  local real MD opt-in variables, local raw files, and optional scientific
  dependencies are present; it must not be confused with default CI.
- 15.10 final boundary docs: records final docs/tests-only workflow
  limitations before frontend/API; it must not be confused with runtime,
  source, CLI, or scientific behavior.
- Pre-16.4 optional scientific CSV exports: may write Rg/contact CSV side
  artifacts only when explicit flags are provided; it must not be confused
  with backend graph export artifacts, WANIA/API payloads, or temporal RIN.
- Pre-16.5 condition-aware diagnostics: Stage 15 graph artifacts may contain
  multiple conditions, and diagnostics handles combined artifacts
  condition-by-condition without changing graph export schema, `graph.json`,
  WANIA API payloads, or frontend/API scope.
- Stage 16.0 WANIA payload contract: documents the future WANIA object JSON
  payload contract. Backend `graph/graph.json` remains a backend artifact, the
  WANIA payload is future adapter/API output, and no runtime adapter is
  implemented in Stage 16.0.
  In short, no runtime adapter is implemented in Stage 16.0.
- Stage 16.1 WANIA adapter: can build the future WANIA object JSON payload
  from accepted Stage 15 artifacts and explicit protein/run metadata. Backend
  graph artifacts remain unchanged, and FastAPI/API remains future scope.
- Stage 16.2 frame sampling: adds controlled preprocessing source-frame
  sampling for Rg, contacts, graph outputs derived from contacts, optional
  scientific CSVs, and JSON-safe workflow provenance. It must not be confused
  with FastAPI/upload/job API work or a WANIA payload schema change.
- Stage 16.5 representative Cα coordinates: captures condition-specific Cα
  positions from the first sampled frame, writes `x_ca/y_ca/z_ca`, adds
  frontend-facing `x/y/z` aliases in graph JSON, and preserves them in WANIA
  node objects. They are not trajectory averages and do not claim full Kabsch
  parity.
- Stage 16.6 backbone graph semantics: adds structural `backbone` edges for
  sequential protein Cα nodes in one condition and chain within
  `BACKBONE_MAX_CA_DIST_A = 4.5` Å, and places `backbone` first in
  `EDGE_PRIORITY`.
- Stage 16.7 contact aggregation parity: ports the notebook
  `InteractionAccumulator` idea into the backend contact result layer. It
  preserves default contact behavior and accepted scientific CSV, graph, and
  WANIA schemas. `build_atom_cache`, per-frame parquet parity, and richer
  typed chemistry remain deferred.

## Accepted public workflow APIs

These accepted workflow APIs are available from `mania.preprocessing`.

Stage 15.1:

```python
PreprocessingGraphWorkflowOptions
PreprocessingGraphWorkflowOutputLayout
PreprocessingGraphWorkflowIssue
PreprocessingGraphWorkflowPlan
build_preprocessing_graph_workflow_plan(...)
```

Stage 15.2:

```python
PreprocessingGraphWorkflowManifestReadinessIssue
PreprocessingGraphWorkflowManifestReadinessResult
check_preprocessing_graph_workflow_manifest_readiness(...)
```

Stage 15.3:

```python
PreprocessingGraphWorkflowRuntimeLoadingIssue
PreprocessingGraphWorkflowRuntimeLoadingResult
load_preprocessing_graph_workflow_condition_runtimes(...)
```

Stage 15.4:

```python
PreprocessingGraphWorkflowComputationIssue
PreprocessingGraphWorkflowComputationResult
compute_preprocessing_graph_workflow_rg_contacts(...)
```

Stage 15.5:

```python
PreprocessingGraphWorkflowGraphExportIssue
PreprocessingGraphWorkflowGraphExportResult
export_preprocessing_graph_workflow_artifacts(...)
```

Stage 15.6:

```python
PreprocessingGraphWorkflowDiagnosticsIssue
PreprocessingGraphWorkflowDiagnosticsResult
run_preprocessing_graph_workflow_diagnostics(...)
```

Stage 15.7:

```python
PreprocessingGraphWorkflowReferenceComparisonIssue
PreprocessingGraphWorkflowReferenceComparisonResult
compare_preprocessing_graph_workflow_reference_artifacts(...)
```

Pre-16.4:

```python
PreprocessingGraphWorkflowScientificCsvExportIssue
PreprocessingGraphWorkflowScientificCsvExportResult
export_preprocessing_graph_workflow_scientific_csvs(...)
```

## Accepted CLI boundary

The accepted Stage 15.8 CLI command is:

```bash
mania preprocessing run-graph-export --manifest PATH --output PATH
```

The command is opt-in, requires explicit `--manifest`, requires explicit
`--output`, and orchestrates accepted Stage 15 APIs. It is no broad CLI
framework; in short, no broad CLI framework. It does not auto-discover
`local_md`, does not auto-search reference artifacts, does not execute
notebooks, and does not generate frontend/API payloads.

Reference comparison is disabled by default. Enabled reference comparison
requires explicit reference artifact paths for reference `nodes.csv`,
corrected `edges.csv`, and `graph.json`.

Optional scientific CSV export is disabled by default. The CLI accepts:

```text
--export-rg-timeseries
--export-contact-edges
--export-contacts-perframe
--export-scientific-csvs
```

`--export-scientific-csvs` exports only the safe subset:
`rg/rg_timeseries.csv` and `contacts/contact_edges.csv`.
`contacts/contacts_perframe.csv` requires `--export-contacts-perframe`.
When requested, optional scientific CSV export runs after graph export and
before diagnostics.

Frame sampling is optional and disabled by default. The CLI accepts:

```text
--frame-start
--frame-stop
--frame-stride
--max-frames
```

Default behavior computes every frame. `frame_stop` is exclusive, `max_frames`
caps sampled frames after start/stop/stride filtering, and sampled frame
indexes preserve original source frame indexes. `frame_time_ps` remains timing
metadata/fallback between source frames; it is not stride.

Contact safety guards are optional and disabled by default:

```text
--contact-max-residue-pairs-per-frame
--contact-max-distance-evaluations-per-frame
```

Frame sampling reduces the number of frames; it does not reduce contacts work
inside one sampled frame. With `--verbose`, contacts progress is printed to
stderr. If a configured contact guard is exceeded, the final JSON exposes the
issue and the workflow exits non-zero rather than silently producing complete
graph artifacts from incomplete contacts.

Contact selection controls which part of the MD system is used for contact
graph construction:

```text
--contact-selection all
--contact-selection protein
```

`all` is the default and preserves existing full-system contact behavior.
`protein` uses `runtime_object.select_atoms("protein").residues` and is
recommended for the protein residue-contact graph / RIN MVP. It reduces the
per-frame candidate residue set, while frame sampling reduces the number of
frames. No NaPi2b-specific filtering or residue-name blacklist is used, contact
limits remain optional smoke/debug guards, and the WANIA object JSON contract
is unchanged.

## Accepted output artifacts

Stage 15 may produce these artifacts under the selected output directory:

```text
graph/nodes.csv
graph/edges.csv
graph/graph.json
reports/graph_diagnostics_report.json
reports/graph_reference_comparison.json
```

`reports/graph_reference_comparison.json` is produced only when reference
comparison is explicitly enabled, the comparison succeeds, and report JSON
writing is enabled.

`graph/edges.csv` is backend graph edges.csv. Stage 13 `contact_edges.csv` is
an aggregate contacts table. Stage 13 `contact_edges.csv` is not backend graph
edges.csv.

Pre-16.4 may also produce these optional opt-in outputs:

```text
rg/rg_timeseries.csv
contacts/contact_edges.csv
contacts/contacts_perframe.csv
```

`contacts/contact_edges.csv` is the Stage 13 aggregate contacts table.
`graph/edges.csv` remains the backend graph edge table. These optional
scientific CSVs are not WANIA/frontend API payloads.

When Stage 16.2 frame sampling is used, Rg, contacts, contact aggregate
frequencies, graph edges, and optional scientific CSVs reflect sampled frames.
Backend graph schemas and WANIA object JSON payload schemas remain unchanged.

Stage 16.5 populates the existing Cα coordinate columns in `nodes.csv` and
extends graph/WANIA node objects non-breakingly with `x/y/z` and
`x_ca/y_ca/z_ca`. Coordinates are representative values from the first
sampled frame per condition, not a trajectory average and not full Kabsch
parity. Protein-only graph export reports `node_coordinates_missing` when an
expected Cα coordinate is unavailable.

Stage 16.6 keeps the accepted backend `graph/edges.csv` columns. `backbone`
has priority over contact-derived types, while `all_edge_types` and
`n_edge_types` preserve every unique type. An overlapping backbone/contact
edge retains its contact metrics. A pure structural backbone edge leaves
contact metrics empty; it does not invent `contact_frequency`. Notebook
compact type names are aliases only and normalize to backend snake_case.

Stage 16.7 centralizes sampled-frame count and distance aggregation in an
`InteractionAccumulator`-style helper. The helper keeps original source frame
indexes, supports deterministic minimum-frequency filtering, and treats edge
types independently. It does not change contact selection, contact safety
limits, progress, scientific CSV schemas, graph schemas, or the WANIA object
JSON contract. Backbone continues to be generated in graph mapping/export,
not by the contact accumulator.

Stage 16.3 contact guard metadata is workflow/CLI metadata only. It is not a
WANIA payload schema change and does not change graph artifact schemas.

The corrected backend graph edge schema includes:

```text
edge_type
all_edge_types
n_edge_types
```

## Outputs deliberately not produced by Stage 15

The accepted Stage 15 workflow CLI still does not produce these outputs; they
are not produced by Stage 15 workflow CLI:

```text
temporal RIN artifacts
WANIA/frontend API payloads
notebook-derived runtime artifacts
```

Stage 15.4 computes Rg and contacts in memory for graph export. Optional
Rg/contact CSVs can now be exported only with explicit Pre-16.4 flags.
Temporal RIN remains future scope. WANIA frontend/API payload remains future
scope.

## Reference comparison boundary

Stage 15.7 reference comparison is disabled by default. When disabled, it
returns deterministic skipped success, does not require reference paths, runs
no comparison, and writes no files.

When enabled, Stage 15.7 requires explicit reference artifact paths. It does
not search `data/reference/**`; in short, no automatic reference artifact search.
It does not execute `MANIA_analysis_v1_2.ipynb`; in short, no notebook execution.
It does not compare temporal RIN, does not classify
expected mismatches programmatically, and adds no programmatic expected
mismatch classification.
There is no programmatic expected mismatch classification.

`docs/preprocessing_graph_reference_mismatches.md` is interpretation guidance
only. Current reference semantics are `MANIA_analysis_v1_2`. v1.1 historical
reference artifacts remain historical.

## Local real MD smoke boundary

Stage 15.9 is local-only, skipped by default, not default CI, and not required
by default CI. It requires both variables:

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1
MANIA_RUN_LOCAL_MD_SMOKE=1
```

The smoke uses `local_md/manifests/napi2b_10ns.yaml` only when present. It
checks local raw MD files before running, checks optional scientific
dependency availability before running, writes only to pytest `tmp_path`, and
must not commit `local_md` or raw MD files. Raw MD files must not be
committed. Raw MD files must not be committed.

## Optional dependency and default CI boundary

Importing `mania.preprocessing` does not require MDAnalysis. CLI help/import
does not require MDAnalysis. Importing or CLI help does not require
MDAnalysis. Importing or CLI help does not require MDAnalysis.

Default tests do not require real MD data. Default CI does not require real MD data.
Default CI does not require `local_md`, and does not install MDAnalysis
or science extras unless explicitly scoped elsewhere. Local real execution may
require optional scientific dependencies through accepted runtime/scientific
APIs.

## Frontend/API future boundary

Stage 15 output is not yet a frontend/API contract. It is backend graph/export
workflow output, not a WANIA frontend/API payload.

Stage 16+ API should be designed around generic protein runs, not
NaPi2b-specific assumptions. This is the protein-agnostic future API boundary:
one job = one protein run, and one uploaded package = one protein run.
Future Stage 16 API/job metadata should include `protein_id`, `protein_name`,
`run_name`, and `condition_names`.

Conditions are not protein identity. Conditions are states/groups within a
protein run, such as `normal` and `tumor`, not different proteins such as
NaPi2b and EGFR. There must be no NaPi2b hardcoding in future API routes, job
metadata, output storage, or frontend payload assumptions. NaPi2b examples are
examples only.

Output artifacts remain backend artifacts for a run. Future graph/scientific
artifacts should be stored under job/run paths, not protein-specific
hardcoded paths. Temporal RIN, if later added, should also be generic per
protein run. WANIA frontend/API payload design remains future scope.

Stage 16.0 documents the future WANIA object JSON payload contract in
`docs/wania_object_json_payload_contract.md`. It does not implement a runtime
adapter, does not change backend `graph/graph.json`, and does not make backend
`graph/graph.json` a frontend/API payload.

Stage 16.1 adds a separate `mania.wania` Python adapter that can build the
future WANIA payload from Stage 15 artifacts. Backend graph artifacts remain
unchanged. FastAPI/API remains future scope.

See `docs/wania_api_protein_agnostic_boundary.md`.

Future frontend/API work must decide separately:

- whether to expose `nodes.csv`, `edges.csv`, `graph.json`, report JSONs, or
  derived payloads;
- whether WANIA frontend needs an adapter;
- whether graph data should be normalized, compressed, paginated, filtered, or
  served through an API;
- how frontend/API handles large graph artifacts;
- how frontend/API handles diagnostics/reference comparison status;
- whether temporal RIN is part of the API;
- whether Rg/contacts CSV exports should be exposed separately.

Do not add any frontend/API schema in Stage 15.10. Do not add any WANIA
payload mapping in Stage 15.10.

Future frontend/API integration must not assume `graph.json` is already
frontend-ready, must not assume Stage 15 artifacts are a WANIA payload, must
not assume Rg/contacts CSVs are emitted by default, and must not assume
reference comparison is required for normal workflow success.

## Future scope checklist

- frontend/API adapter and payload contract;
- WANIA frontend integration;
- temporal RIN export/comparison;
- production workflow runner, if later accepted;
- default CI with synthetic-only workflow checks, if later accepted;
- real-data CI, if ever accepted separately;
- performance benchmarking, if later accepted separately;
- biological interpretation/report expansion, if later accepted separately.

## Guardrails for next frontend/API stage

- do not execute notebooks;
- do not search local raw MD data automatically;
- do not add real-data CI by accident;
- do not assume `graph.json` is already frontend-ready;
- do not treat Stage 13 `contact_edges.csv` as backend graph edges.csv;
- do not make reference comparison required for normal workflow success;
- do not derive protein identity from condition names or path names;
- do not hardcode NaPi2b in future Stage 16 API/storage/frontend design;
- do not add temporal RIN unless explicitly scoped.
