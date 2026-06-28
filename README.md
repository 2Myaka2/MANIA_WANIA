# MANIA/WANIA

MANIA currently provides a backend preprocessing graph workflow for molecular
dynamics (MD) data. WANIA is the future web/API layer that will consume MANIA
outputs after a separate Stage 16+ contract is accepted.

The current practical workflow starts from a preprocessing manifest and local
raw MD files, loads runtimes, computes Rg and contacts in memory, exports
backend graph artifacts, writes diagnostics when report writing succeeds, and
can optionally compare generated graph artifacts against explicit reference
artifacts.

## Current Backend Workflow

Accepted Stage 15 workflow:

```text
raw MD files + preprocessing manifest
-> runtime loading
-> in-memory Rg + contacts
-> graph/nodes.csv
-> graph/edges.csv
-> graph/graph.json
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

Example `local_md/manifests/napi2b_10ns.yaml`:

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
unchanged. Per-frame parity, richer chemistry, and analysis metrics parity
remain deferred to Stages 16.9–16.11.

## Optional Scientific CSV Exports

By default, the Stage 15 CLI does not export Rg/contacts CSVs. They can be
exported with explicit optional flags after graph export succeeds.

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
adapter can write `wania_graph_payload.json` when called directly from Python.
It does not add FastAPI, an upload/job API, frontend implementation, or CLI
integration.

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

Stage 15 output is backend graph workflow output. It is not yet the final WANIA
API/frontend contract, and `graph.json` should not be assumed to be
frontend-ready.

Stage 16.0 documents the future WANIA object JSON payload contract. The
contract is object JSON, protein-agnostic, and separate from backend
`graph/graph.json`.

Stage 16.1 adds a Python adapter for that WANIA object JSON payload. The
adapter consumes accepted Stage 15 artifacts and does not change backend
`graph/graph.json`.

Future Stage 16+ implementation scope includes the FastAPI upload/job API,
WANIA API serving, frontend integration, and any temporal RIN workflow. This
future scope should be specified separately before implementation.

## Documentation

- `docs/preprocessing_graph_workflow_boundary_before_frontend_api.md`: accepted
  Stage 15 backend workflow boundary.
- `docs/wania_api_protein_agnostic_boundary.md`: protein-agnostic Stage 16+
  API/run boundary.
- `docs/wania_object_json_payload_contract.md`: future WANIA object JSON
  payload contract, separate from backend `graph/graph.json`.
- `docs/preprocessing_graph_workflow_contract.md`: workflow APIs, options, and
  output layout.
- `docs/local_scientific_integration_tests.md`: local-only real MD smoke test
  boundary.
- `docs/architecture.md`: intended package architecture.
- `AGENTS.md`: working rules for Codex, coding agents, and assistants.
