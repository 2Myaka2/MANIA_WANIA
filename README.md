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
WANIA/frontend API payloads
```

Rg and contacts are computed in memory for graph export. Optional Rg/contact
CSVs are side-effect scientific exports, not WANIA/frontend API payloads.

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

Future Stage 16+ scope includes the FastAPI upload/job API, WANIA frontend
adapter/API payloads, and any temporal RIN workflow. This future scope should
be specified separately before implementation.

## Documentation

- `docs/preprocessing_graph_workflow_boundary_before_frontend_api.md`: accepted
  Stage 15 backend workflow boundary.
- `docs/preprocessing_graph_workflow_contract.md`: workflow APIs, options, and
  output layout.
- `docs/local_scientific_integration_tests.md`: local-only real MD smoke test
  boundary.
- `docs/architecture.md`: intended package architecture.
- `AGENTS.md`: working rules for Codex, coding agents, and assistants.
