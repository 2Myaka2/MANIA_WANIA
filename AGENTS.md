# AGENTS.md

## Purpose

This file defines the working rules for Codex, coding agents, and assistants that modify the `MANIA_WANIA` repository.

The main rule: work in small, reviewable, testable steps. Do not expand the architecture or implement heavy scientific logic unless the task explicitly asks for it.

---

## Project overview

`MANIA_WANIA` is a research software project for molecular dynamics trajectory analysis and preparation of artifacts for a future web interface.

`MANIA` is the Python package. It will eventually:

- read and validate analysis configuration;
- support one-condition and two-condition runs;
- run preprocessing;
- build residue interaction network artifacts;
- calculate structural and graph metrics;
- produce temporal and conformational outputs;
- export stable artifacts for `WANIA`;
- run QC checks;
- generate an HTML analysis report.

`WANIA` is the future web interface. This repository currently focuses on `MANIA` and the data contract for `WANIA`.

---

## Current development stage

The project is currently at the engineering skeleton stage.

At this stage, the repository must:

- keep a clean Python package structure;
- use `src-layout`;
- install with `pip install -e ".[dev]"`;
- import as `mania`;
- expose the CLI command `mania`;
- validate a YAML config through Pydantic;
- contain an example YAML config;
- document the data contract v0.1;
- contain minimal tests;
- avoid heavy scientific implementation.

---

## Core rules

1. Do not make broad architectural changes without an explicit task.
2. Do not create large empty module trees “for the future”.
3. Do not implement scientific algorithms if the task only concerns skeleton, config, docs, or tests.
4. Do not commit large data files.
5. Do not hardcode local user paths.
6. Do not invent final lipid, glycan, or glycolipid residue lists.
7. Keep every change small, reviewable, and explainable.
8. Every functional change must include tests or a minimal verification path.
9. Stabilize the Python package and data contract before adding FastAPI.

---

## Expected repository structure

Current expected skeleton:

```text
MANIA_WANIA/
├── .gitignore
├── .python-version
├── AGENTS.md
├── README.md
├── pyproject.toml
├── configs/
│   └── mania.example.yaml
├── docs/
│   ├── architecture.md
│   ├── data_contract.md
│   ├── decisions.md
│   └── git_workflow.md
├── src/
│   └── mania/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── constants.py
│       ├── exceptions.py
│       ├── pipeline.py
│       ├── residues.py
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── comparison.py
│       │   ├── graph.py
│       │   ├── metrics.py
│       │   └── temporal.py
│       ├── export/
│       │   ├── __init__.py
│       │   ├── manifest.py
│       │   └── wania.py
│       ├── io/
│       │   ├── __init__.py
│       │   └── paths.py
│       ├── preprocessing/
│       │   ├── __init__.py
│       │   └── runner.py
│       ├── qc/
│       │   ├── __init__.py
│       │   └── runner.py
│       └── report/
│           ├── __init__.py
│           └── runner.py
└── tests/
    ├── test_config.py
    ├── test_data_contract.py
    ├── test_imports.py
    └── test_residues.py
```

---

## Important note about `analysis/`

At the skeleton stage, `src/mania/analysis/` is intentionally broad:

```text
analysis/
├── graph.py
├── metrics.py
├── temporal.py
└── comparison.py
```

This is intentional. Do not split it into a large final module tree too early.

Later, after notebook logic is migrated, this layer may be decomposed into:

```text
graph/
metrics/
temporal/
comparison/
edge_dynamics/
```

Do not create these larger modules unless a task explicitly asks for it.

---

## Naming conventions

Installable distribution name:

```text
mania-wania
```

Importable Python package:

```python
import mania
```

CLI command:

```bash
mania
```

Do not rename these unless explicitly requested.

---

## Python version

Supported Python version:

```text
>=3.11
```

Using Python 3.12 locally is acceptable. Keep `requires-python = ">=3.11"` unless the team makes a different decision.

---

## Dependencies

Current minimal runtime dependencies:

```text
pydantic
PyYAML
```

Current minimal development dependencies:

```text
pytest
ruff
mypy
types-PyYAML
```

Do not add heavy scientific dependencies unless the task explicitly requires them.

Do not add these dependencies during skeleton/config/docs-only tasks:

- MDAnalysis;
- GROMACS wrappers;
- DSSP tools;
- FreeSASA;
- ESM models;
- FastAPI;
- pandas;
- pyarrow;
- networkx.

Add them later only when a concrete implementation needs them.

---

## Configuration

The main user-facing config format is YAML.

The Python config implementation must use Pydantic.

Main file:

```text
src/mania/config.py
```

Example config:

```text
configs/mania.example.yaml
```

Minimal Pydantic models:

```text
ProjectConfig
SystemConfig
RuntimeConfig
FeatureConfig
MANIAConfig
```

Minimal loader function:

```python
load_config(path: str | Path) -> MANIAConfig
```

---

## Example YAML config

`configs/mania.example.yaml` should be a valid example:

```yaml
project:
  name: "NaPi2b_NORM_TUMOR"
  run_id: "run_001"

systems:
  normal:
    topology: "data/normal/system.tpr"
    trajectory: "data/normal/traj.xtc"
    condition: "normal"
    label: 0
  tumor:
    topology: "data/tumor/system.tpr"
    trajectory: "data/tumor/traj.xtc"
    condition: "tumor"
    label: 1

runtime:
  output_dir: "mania_output"
  cache_dir: "mania_output/cache"
  temp_dir: "mania_output/tmp"
  log_level: "INFO"
  run_mode: "full"
  resume: true
  overwrite: false
  strict_validation: true
  n_jobs: 1

features:
  rg: true
  energy_rerun: false
  energy_groups: ["Protein", "MEMB"]
  esm2: false
```

---

## Run modes

MANIA must support two run modes:

```text
full
analysis
```

`full` means a full run from input trajectories to final artifacts.

`analysis` means running only the analysis stage using already prepared preprocessing artifacts.

At the skeleton stage, the actual pipeline logic may be a placeholder, but the config must already validate these values.

---

## One-condition and two-condition runs

MANIA must support both:

- one-condition runs;
- two-condition runs, for example `normal` and `tumor`.

If only one condition is provided:

- preprocessing should work;
- graph, metrics, temporal, and conformational analysis should work;
- cross-condition analysis should not run;
- `comparison.csv` and `stats.csv` should not be produced, or should be marked as unavailable in later pipeline stages.

If two conditions are provided:

- each condition is analyzed separately;
- the comparison layer runs afterward.

---

## Residue registry

File:

```text
src/mania/residues.py
```

Purpose: central CHARMM36 / CHARMM-GUI residue name registry.

Future structures:

```python
LIPID_RESIDUES
GLYCAN_RESIDUES
GLYCOLIPID_RESIDUES

ALL_LIPIDS
ALL_GLYCANS
ALL_GLYCOLIPIDS
```

Important rules:

- final residue lists are provided by the scientific lead;
- do not invent the final scientific lists;
- placeholder values and TODO comments are acceptable at the skeleton stage;
- glycolipids such as GM1/GM3 must be handled as a separate edge type: `protein_glycolipid`;
- glycolipids must not be duplicated as both `protein_lipid` and `protein_glycan` edges.

---

## Data contract v0.1

Minimal approved artifacts.

Per-condition / per-trajectory artifacts:

```text
nodes.csv
edges.csv
graph.json
centrality.csv
communities.csv
temporal_rin.csv
conformational_states.csv
contacts_perframe.parquet
```

Cross-condition artifacts only:

```text
comparison.csv
stats.csv
```

Optional / outside MVP v0.1:

```text
allosteric_paths.json
```

Energy analysis and ESM-2 are config fields only at this stage. Their implementation is postponed.

---

## `nodes.csv`

Required columns:

```text
resid
resname
region
condition
x_ca
y_ca
z_ca
tm_relative_z
rmsf_A
sasa_A2
ss
degree
strength
betweenness
closeness
eigenvector
pagerank
kcore
community_id
```

---

## `edges.csv`

Required columns:

```text
resid_i
resid_j
edge_type
condition
contact_freq
mean_dist_A
std_dist_A
n_episodes
mean_lifetime_frames
max_lifetime_frames
mean_lifetime_ns
max_lifetime_ns
formation_count
breakage_count
first_seen_frame
last_seen_frame
window_cv
```

`window_cv` replaces the earlier name `window_stability_score`.

Formula:

```text
window_cv = std(contact_freq_per_window) / mean(contact_freq_per_window)
```

Division by zero must be handled explicitly when `mean = 0`.

---

## `graph.json`

Minimal structure:

```json
{
  "condition": "normal",
  "n_nodes": 690,
  "n_edges": 1234,
  "directed": false,
  "schema_version": "0.1",
  "nodes": [],
  "edges": []
}
```

---

## `centrality.csv`

Required columns:

```text
resid
condition
degree
strength
betweenness
closeness
eigenvector
pagerank
kcore
```

---

## `communities.csv`

Required columns:

```text
resid
condition
community_id
community_size
algorithm
```

---

## `temporal_rin.csv`

Required columns:

```text
window_id
time_start_ps
time_end_ps
condition
n_edges
n_nodes_active
density
window_cv
```

---

## `conformational_states.csv`

Required columns:

```text
frame
time_ps
condition
state_id
cluster_label
rg_A
rmsd_A
```

In v0.1, Rg is only global protein `Rg(t)`:

- per-frame;
- mean/std;
- used for cluster description and condition comparison.

Do not add residue-level Rg unless explicitly requested.

---

## `contacts_perframe.parquet`

Required columns:

```text
frame
time_ps
resid_i
resid_j
edge_type
dist_A
condition
```

---

## `comparison.csv`

Cross-condition artifact.

Do not place it inside `normal/` or `tumor/`.

Required columns:

```text
resid_or_edge_id
metric
normal_value
tumor_value
delta
statistic
p_value
q_value
effect_size
condition_specificity
```

---

## `stats.csv`

Cross-condition artifact.

Do not place it inside `normal/` or `tumor/`.

Required columns:

```text
resid_or_edge_id
metric
test
statistic
p_value
q_value
effect_size
significant
```

---

## QC module

QC is a deterministic module, not an LLM agent.

Directory:

```text
src/mania/qc/
```

Future outputs:

```text
qc_report.json
qc_report.md
```

Future checks:

- config validity;
- input path existence;
- supported `run_mode`;
- number of systems;
- condition names;
- residue count agreement between conditions;
- residue ID set agreement between conditions;
- residue name differences between conditions, for example `330: THR -> MET`;
- required output artifacts;
- required data contract columns.

Deletions and insertions are out of scope for v0.1.

---

## Report module

Report is a deterministic module, not an LLM agent.

Directory:

```text
src/mania/report/
```

Future output:

```text
analysis_report.html
```

The report should summarize computed data and generated artifacts.

Do not add biological interpretation unless explicitly requested.

---

## CLI

File:

```text
src/mania/cli.py
```

The CLI should support:

```bash
mania --version
mania validate-config configs/mania.example.yaml
mania run --config configs/mania.example.yaml
```

Current priority:

```bash
mania validate-config configs/mania.example.yaml
```

Expected `validate-config` behavior:

- load YAML;
- validate through Pydantic;
- print a clear success message;
- return exit code `0`;
- print a readable error on failure;
- return exit code `1` on failure.

---

## Tests

Every task should add or update tests.

Minimal tests:

```text
tests/test_imports.py
tests/test_config.py
tests/test_data_contract.py
tests/test_residues.py
```

Skeleton tests must not require real MD trajectories.

Expected commands:

```bash
pip install -e ".[dev]"
pytest
```

Also useful:

```bash
ruff check .
mypy src
```

If `mypy` is too strict at this stage, do not over-optimize. Leave a clear TODO and keep progress practical.

---

## Data files

Large scientific data must not be committed.

Do not commit:

```text
data/
outputs/
mania_output/
*.xtc
*.tpr
*.trr
*.dcd
*.psf
*.edr
*.gro
*.pdb
```

`*.parquet` should also generally not be committed, except for future small fixtures.

If small test fixtures are needed later, place them under:

```text
tests/fixtures/
```

---

## Yandex Disk

Do not connect Yandex Disk data in code at the skeleton stage.

At this stage, data sources may only be documented, for example in:

```text
docs/data_sources.md
```

Do not implement Yandex Disk download logic unless explicitly requested.

---

## FastAPI

Do not implement FastAPI yet.

First stabilize:

1. Python package structure;
2. Pydantic config;
3. CLI;
4. data contract;
5. tests;
6. basic documentation.

FastAPI will be added later as a separate stage.

---

## Do not implement now

Do not implement without a specific task:

- MDAnalysis;
- GROMACS/NAMD parsing;
- RMSF;
- SASA;
- DSSP;
- φ/ψ;
- TM-Z;
- contact maps;
- edge dynamics;
- energy rerun;
- ESM-2;
- allosteric paths;
- FastAPI;
- Yandex Disk integration;
- biological interpretation;
- final residue registries.

---

## Git workflow

Use small branches and small commits.

Example branches:

```text
feature/config-validation
feature/data-contract-docs
feature/qc-skeleton
feature/report-skeleton
```

Example commits:

```text
chore: initialize repository skeleton
build: add package metadata and dev dependencies
feat: add pydantic config models
feat: add validate-config command
docs: add data contract v0.1
test: add config validation tests
```

Do not mix unrelated changes in one commit.

---

## How to work on a task

For each task:

1. Read `AGENTS.md`.
2. Check `docs/decisions.md`.
3. Check `docs/data_contract.md`.
4. Make minimal changes.
5. Add or update tests.
6. Run checks.
7. Report:
   - changed files;
   - what was implemented;
   - which commands were run;
   - results of checks;
   - remaining TODOs.

---

## Current next task

The next expected task after the skeleton is:

Implement minimal Pydantic config validation.

Target files:

```text
src/mania/config.py
src/mania/cli.py
configs/mania.example.yaml
tests/test_config.py
tests/test_imports.py
```

Acceptance criteria:

```bash
pip install -e ".[dev]"
mania validate-config configs/mania.example.yaml
pytest
```

All commands must pass.