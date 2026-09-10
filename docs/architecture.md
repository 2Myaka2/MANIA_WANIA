# MANIA Architecture — v0.1 Foundation and Historical Planning

## Current implementation status

MANIA implementation has advanced through accepted Stage 24.G, with an
operational scientific/backend preprocessing and analysis CLI.
[README.md](../README.md) is the current implementation-status overview.

The sections below preserve the original v0.1 architectural foundation and
historical planning context. Older wording such as “future”, “skeleton”, and
“not implemented” may describe that original context rather than the current
repository inventory. These sections are not a current capability checklist.

See [Stage 25 reproducibility hardening](stage25_reproducibility_hardening.md)
for the approved current roadmap. Stage 25.A software identity is complete.
Stage 25.B run provenance and effective sampling is complete. Stage 25.C
input/output artifact inventory and opt-in checksums is complete. Stage 25.D
unified technical artifact validation is complete. Stage 25.E observation-only PBC audit and runtime metadata is complete.
Stage 25.F reproducibility documentation and FAIR² bridge is complete.
Stage 25.G final technical-hardening acceptance is complete.
The scientific PBC protocol remains unresolved; MANIA applies no internal
minimum-image correction. Stage 25 is complete.
FastAPI remains postponed.

Stage 26 is complete: Stage 26.A and 26.B are accepted; Stage 26.C implements
authoritative Dataset execution binding, technical propagation, and validation.
The Dataset v1.0 scientific contract is frozen except for concrete NAMD condition
labels, which remain unresolved. Dataset v1.0 remains unreleased.
Stage 27 physical-time sampling/window engine is complete. Stage 27.A and 27.B
are accepted; Stage 27.C integrates their plans into preprocessing. Stage 27 is complete.
Stage 28 contact episodes/lifetime/publication protein-edge tables are next;
Stage 28 has not started. The 95% exclusion policy remains Stage 32.
WANIA is unchanged. Analysis Dataset-context propagation is outside Stage 26;
analysis temporal propagation is outside Stage 27.

Accepted Stage 27.A implements the standalone
[physical-time sampling resolver](physical_time_sampling_contract.md), consuming
only production bounds and stride. Stage 27.B implements the standalone
[physical-time window planner](physical_time_window_contract.md), interpreting
window length, step, and overlap over the authoritative sampling records.
Stage 27.C [preprocessing execution](physical_time_execution_contract.md) collects
actual source times once per Dataset condition and routes exact resolved source
indexes to existing Rg and contact passes. Window planning adds no trajectory
pass. The separate temporal artifact records effective execution, while requested
Dataset context remains in provenance. Windows do not yet partition contacts.

## Purpose

This document describes the intended architecture of the MANIA Python package.
It is a guide for future implementation and for keeping module responsibilities
separated.

This is not a description of implemented scientific algorithms. MANIA is
currently at the engineering skeleton stage, so many modules exist as
placeholders or narrow scaffolding for later work.

## High-Level Flow

The target architecture is a staged flow from user configuration to stable
artifacts for WANIA:

```text
YAML config
  -> Pydantic validation
  -> pipeline entry point
  -> preprocessing
  -> analysis
  -> export
  -> QC
  -> report
  -> WANIA artifacts
```

This diagram describes the intended architecture. It does not mean every stage
is implemented today. At the skeleton stage, config validation and basic CLI
entry points are the main working pieces.

## Package Layout

The MANIA package lives under `src/mania/`.

### `config.py`

`config.py` owns the Pydantic models for the user-facing YAML configuration. It
loads YAML, validates the top-level shape, and returns a typed MANIA config
object. It should remain focused on schema and value validation, not physical
input checks or scientific processing.

### `cli.py`

`cli.py` owns the command-line interface exposed as `mania`. It currently
supports config validation and a skeleton `run` command. As the project grows,
the CLI should stay thin and delegate real work to `config.py`, `pipeline.py`,
and specialized modules.

### `__main__.py`

`__main__.py` allows `python -m mania` to call the same CLI entry point as the
installed `mania` command.

### `constants.py`

`constants.py` contains lightweight constants for the v0.1 data contract, such
as schema version, artifact names, required columns, and required graph keys.
It should mirror `docs/data_contract.md` and stay free of heavyweight runtime
logic.

### `pipeline.py`

`pipeline.py` is the future orchestration layer. It currently builds and formats
a lightweight `PipelinePlan` placeholder without executing pipeline stages. Its
responsibility is to connect validated configuration to preprocessing, analysis,
export, QC, and report generation without embedding heavy scientific
implementation directly.

### `residues.py`

`residues.py` is the future source of truth for lipid, glycan, and glycolipid
residue names. It is intentionally not filled with final scientific registries
yet. Final residue lists must come from the domain expert.

### `io/`

`io/` is reserved for input and output path helpers and other small file-system
utilities. It should not become a scientific processing layer. Future physical
input checks should coordinate with QC rather than being hidden inside config
validation.

### `preprocessing/`

`preprocessing/` is the future layer for preparing inputs before analysis. It
may eventually handle trajectory preparation, residue tables, per-frame
contacts, and intermediate artifacts. This scientific preprocessing work is not
implemented yet.

### `analysis/`

`analysis/` is intentionally broad in the current skeleton. It may contain
modules such as `graph.py`, `metrics.py`, `temporal.py`, and `comparison.py`.
The layer should hold analysis responsibilities after preprocessing has
prepared suitable inputs.

### `export/`

`export/` is the future layer for writing MANIA outputs in the shape expected by
WANIA. It should follow `docs/data_contract.md` and the constants in
`src/mania/constants.py`. It is not the place for analysis algorithms.

`export/manifest.py` prepares the future `manifest.json` structure as typed
skeleton data and summaries. It does not write files yet.

`export/run_meta.py` prepares the future `run_meta.json` metadata as typed
skeleton data and summaries. It does not write files yet.

### `qc/`

`qc/` is reserved for deterministic quality-control checks. It should validate
facts about configuration, inputs, and outputs without producing biological
interpretation.

`qc/runner.py` defines `QCMessage`, `QCReport`, and skeleton QC summaries. It
does not run real QC checks yet.

### `report/`

`report/` is reserved for deterministic report generation. Future reports
should summarize produced artifacts and QC results. They should not introduce
biological interpretation unless that is explicitly requested and designed
later.

`report/runner.py` defines `ReportSummary` and report summary formatting. It
does not generate HTML yet.

## Config Layer

`configs/mania.example.yaml` is the user-facing example configuration. YAML is
the main user-facing config format for MANIA.

`src/mania/config.py` loads and validates config files with Pydantic v2 models.
The current validation checks the YAML structure and configured values, including
supported run modes and the allowed number of systems.

Config validation does not check whether topology or trajectory files physically
exist. File existence belongs to future QC or input checks, not the current
Pydantic config layer.

## Pipeline Layer

`pipeline.py` is the future orchestration layer. It should decide how to run the
configured workflow and route work to specialized modules. The current code only
builds a placeholder `PipelinePlan` from validated config and formats it for the
skeleton `run` command.

The supported run modes are:

- `full`: a future full run from input trajectories to final artifacts.
- `analysis`: a future analysis-only run using already prepared preprocessing
  artifacts.

`pipeline.py` should not contain heavy scientific implementation directly. It
should call preprocessing, analysis, export, QC, and report modules.

## Preprocessing Layer

The preprocessing layer will eventually be responsible for preparing analysis
inputs. Future responsibilities may include:

- input preparation;
- trajectory preprocessing;
- residue tables;
- contacts per frame;
- intermediate artifacts.

This work is not implemented yet. No scientific MD preprocessing should be
described as working at the skeleton stage.

## Analysis Layer

The current `analysis/` package is intentionally broad. In the skeleton it may
contain, or later contain, these coarse modules:

- `graph.py`
- `metrics.py`
- `temporal.py`
- `comparison.py`

This structure is deliberate for v0.1. Do not split it into a larger module tree
until there is concrete migrated logic that needs the separation.

Later, after notebook logic is migrated and responsibilities are clearer, the
analysis layer may be decomposed into:

- `graph/`
- `metrics/`
- `temporal/`
- `comparison/`
- `edge_dynamics/`

Do not create those folders yet. `edge_dynamics` is not implemented yet, but
edge-dynamics fields are already part of the v0.1 data contract.

## Export Layer

`export/` is intended to prepare final MANIA/WANIA artifacts. It should follow
`docs/data_contract.md` and `src/mania/constants.py`.

The current export skeleton prepares in-memory manifest and run metadata
structures only. It does not write `manifest.json`, `run_meta.json`, or final
WANIA artifact files yet.

Per-condition artifacts are planned under condition directories such as
`normal/` and `tumor/`. These include artifacts such as `nodes.csv`,
`edges.csv`, `graph.json`, `centrality.csv`, `communities.csv`,
`temporal_rin.csv`, `conformational_states.csv`, and
`contacts_perframe.parquet`.

`comparison.csv` and `stats.csv` are planned cross-condition artifacts. They
should not be placed inside condition directories.

## QC Layer

QC should be deterministic checks, not LLM-based interpretation. Future checks
may include:

- config validity;
- input existence;
- residue count matching;
- residue ID set matching;
- output artifact presence;
- data contract columns.

Physical input checks are future work. They are not part of current config
validation.

The current QC skeleton can build typed QC messages and summaries, but it does
not write `qc_report.json` or `qc_report.md` yet.

## Report Layer

`report/` is for deterministic report generation. A future output may include
`analysis_report.html`.

The report should summarize generated artifacts and QC results. It should not
generate biological interpretation unless that capability is explicitly
requested and designed later.

The current report skeleton builds an in-memory `ReportSummary` and formatted
text summary only. It does not write `analysis_report.html` yet.

## Residue Registry

`residues.py` is the future source of truth for lipid, glycan, and glycolipid
residue names. Do not invent final residue lists yet. The final residue registry
is prepared by the domain expert.

Glycolipids should not be duplicated in the residue interaction network as both
protein-lipid and protein-glycan edges. Glycolipid interactions use
`edge_type = "protein_glycolipid"`.

## Current Non-Goals

The v0.1 skeleton does not include:

- FastAPI;
- MDAnalysis;
- GROMACS execution;
- Yandex Disk integration;
- ESM-2 implementation;
- energy rerun implementation;
- allosteric paths in the MVP;
- real scientific trajectory analysis.
