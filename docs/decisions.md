# MANIA/WANIA Accepted Decisions for v0.1

This document records accepted project decisions for MANIA v0.1. These are
scope and contract decisions, not a list of implemented features.

## Historical context and current status

This document originated as a v0.1 planning and decision record. Some older
implementation-status statements, including the skeleton focus and “No
MDAnalysis yet”, are historical and do not describe the current repository.
The original decisions below are preserved as a historical record.

[README.md](../README.md) contains the current implementation status through
accepted Stage 24.G. [Stage 25 reproducibility
hardening](stage25_reproducibility_hardening.md) contains the approved Stage 25
roadmap; Stage 25.A software identity is complete. Stage 25.B run provenance
and effective sampling is complete. Stage 25.C input/output artifact inventory
and opt-in checksums is complete. Stage 25.D unified technical artifact validation is
complete. Stage 25.E observation-only PBC audit and runtime metadata is complete.
Stage 25.F reproducibility documentation and FAIR² bridge is complete.
Stage 25.G final technical-hardening acceptance is complete.
The scientific PBC protocol remains unresolved; MANIA applies no internal
minimum-image correction. Stage 25 is complete. FastAPI remains postponed.

Stage 26 is complete: Stage 26.A and 26.B are accepted; Stage 26.C implements
authoritative Dataset execution binding, technical propagation, and validation.
The Dataset v1.0 scientific contract is frozen except for concrete NAMD condition
labels, which remain unresolved. Dataset v1.0 remains unreleased.
Stage 27 physical-time sampling/window engine is complete. Stage 27.A and 27.B
are accepted; Stage 27.C integrates their plans into preprocessing. Stage 27 is complete.
Stage 28 is complete: accepted 28.A episodes, 28.B aggregation, and 28.C source
CSV contracts are integrated by 28.D with artifact lineage and unified validation.
Stage 29 is complete: accepted 29.A/B/C identity and geometry are integrated by
29.D with explicit metadata, specialized windows, source exports, and validation.
Stage 30 is complete: accepted 30.A/B/C reference, explicit mapping, and canonical
intermediate tables are integrated by 30.D with complete system biological
annotations, preprocessing lineage, and offline reconstruction validation.
Protein-edge and specialized source CSVs remain pre-canonical and unchanged;
canonical and annotated outputs are additive. Explicit mapping to UniProt O95436
and authoritative system annotations remain mandatory before Dataset publication.
Stage 31 is complete: accepted 31.A/B/C are integrated by 31.D through a
separate canonical-only Dataset aggregation workflow, aggregate CSV exports,
portable inventory/provenance, and exact offline reconstruction validation.
Stage 32 is complete: accepted 32.A/B/C are integrated by 32.D through strict
Dataset QC evidence controls, authoritative release decisions, reports,
QC-derived aggregation availability and correspondence projection, portable
inventory/provenance, and exact offline reconstruction validation.
Stage 33 publication export is next and has not started. Stage 34 multi-engine pilot and
Stage 35 full production remain later.
Stage 34 acceptance requires a real three-replica group, real canonical mapping,
a real physical window contract, authoritative real QC-derived availability and
exclusion, and real aggregation; preferably T330M. Specialized layers require
authoritative real partner correspondence. Synthetic QC cannot satisfy this gate.
The 95% exclusion policy is implemented in Stage 32 through accepted 32.B.
WANIA is unchanged. Analysis Dataset-context propagation is outside Stage 26;
analysis temporal propagation is outside Stage 27.

## Project Scope

- MANIA is a Python package for preparing molecular dynamics analysis artifacts.
- WANIA is a web interface that consumes MANIA outputs.
- The current focus is repository skeleton, config, CLI, docs, and tests.
- FastAPI is postponed until the Python package and data contract are stable.

## Repository and Package

- The repository uses `src-layout`.
- Installable project name: `mania-wania`.
- Python import package: `mania`.
- CLI command: `mania`.
- Supported Python version: `>=3.11`.
- Pydantic v2 is used for config models.
- YAML is the main user-facing config format.

## Pipeline Modes

- `full` mode is the future full run from trajectories to final artifacts.
- `analysis` mode is the future analysis-only run using prepared preprocessing
  artifacts.
- Preprocessing and analysis must remain architecturally separated.

## Current Skeleton Architecture

- `analysis/` is temporarily an aggregated skeleton layer.
- Later, it may be decomposed into `graph/`, `metrics/`, `temporal/`,
  `comparison/`, and `edge_dynamics/`.
- `edge_dynamics` is not implemented yet, but its fields are part of the data
  contract.

## Config

- `runtime.run_mode` supports only `full` and `analysis`.
- `runtime.log_level` supports `DEBUG`, `INFO`, `WARNING`, `ERROR`, and
  `CRITICAL`.
- One-condition and two-condition configs are supported.
- Topology and trajectory path existence is not checked in config validation;
  this belongs to future QC/input checks.
- Energy analysis and ESM-2 are config fields only, not implemented features.

## Residue Registry

- `src/mania/residues.py` is the future single source of truth for lipid,
  glycan, and glycolipid residue names.
- Do not invent final residue lists yet.
- The final residue registries will be prepared by the domain expert.
- Glycolipids should not be duplicated in RIN; they will use
  `edge_type = "protein_glycolipid"`.

## Data Contract

- Mandatory per-condition artifacts:
  - `nodes.csv`
  - `edges.csv`
  - `graph.json`
  - `centrality.csv`
  - `communities.csv`
  - `temporal_rin.csv`
  - `conformational_states.csv`
  - `contacts_perframe.parquet`
- Cross-condition artifacts:
  - `comparison.csv`
  - `stats.csv`
- `comparison.csv` and `stats.csv` are not per-condition files.
- `allosteric_paths.json` is optional and outside MVP v0.1.

## Scientific Scope Limits

- No deletions/insertions support in v0.1.
- Normal/tumor currently means WT vs T330M.
- Residue count and residue IDs must match between conditions.
- Resname differences, for example `THR -> MET`, are informational facts for QC.
- Rg is global protein `Rg(t)`, not residue-level Rg in `nodes.csv`.
- `window_stability_score` is renamed to `window_cv`.
- `window_cv = std(contact_freq_per_window) / mean(contact_freq_per_window)`,
  with `mean = 0` handled explicitly later.

## Original v0.1 Non-Goals (Historical)

- No FastAPI yet.
- No MDAnalysis yet.
- No GROMACS execution yet.
- No DSSP/SASA/RMSF implementation yet.
- No energy rerun implementation yet.
- No ESM-2 implementation yet.
- No Yandex Disk integration yet.
- No final biological interpretation in the report module yet.
