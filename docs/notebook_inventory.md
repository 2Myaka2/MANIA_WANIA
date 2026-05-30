# MANIA/WANIA Notebook Inventory Template

## Purpose

This document is a template for future review of existing research notebooks
before moving logic into MANIA modules.

It will be used to inventory notebook sections, inputs, outputs, assumptions,
dependencies, generated artifacts, and possible target modules.

This is a planning document only. It does not mean that notebook logic has
already been migrated into MANIA.

## Rules

When reviewing notebooks:

- do not copy large notebook code blocks into this document;
- do not migrate scientific logic without a separate task;
- do not add notebook outputs, images, trajectories, or generated files;
- do not add real notebooks or data files;
- record inputs, outputs, assumptions, dependencies, and the target MANIA module;
- keep notes concise and focused on migration planning.

Notebook migration must happen later through explicit, focused tasks.

## Suggested Review Process

Use the following process for each notebook:

1. Identify the notebook.
2. Split the notebook into logical sections or cell ranges.
3. Describe the purpose of each section.
4. Record required inputs.
5. Record produced outputs.
6. Record important variables and assumptions.
7. Identify dependencies.
8. Record generated artifacts.
9. Decide whether the section belongs in preprocessing, analysis, export, QC, report, docs, or tests.
10. Assign migration priority.
11. List open questions and risks.

## Inventory Table Template

| Notebook | Section / cells | Purpose | Inputs | Outputs | Key variables | Dependencies | Generated artifacts | Target MANIA module | Migration priority | Open questions / notes |
|---|---|---|---|---|---|---|---|---|---|---|
| example_notebook.ipynb | cells 1-5 | Load trajectory metadata | topology path, trajectory path | metadata summary | topology_file, trajectory_file | MDAnalysis later | none | preprocessing | P1 | Example only; do not treat as implemented |

The example row is fake and exists only to show how the table should be filled.
It does not mean that trajectory loading, MDAnalysis integration, or metadata
extraction is implemented.

## Target Module Guide

Use this guide when deciding where a notebook section may belong later.

### src/mania/preprocessing/

Use for future input preparation and preprocessing logic, such as:

- trajectory preparation;
- topology/trajectory input handling;
- residue tables;
- contact extraction;
- intermediate preprocessing artifacts.

This is not implemented yet.

### src/mania/analysis/

Use for future analysis logic, such as:

- graph construction;
- graph metrics;
- temporal analysis;
- comparison logic;
- conformational state summaries.

At the current skeleton stage, this layer is intentionally broad.

### src/mania/export/

Use for future logic that prepares final MANIA/WANIA artifacts according to
`docs/data_contract.md` and `src/mania/constants.py`.

Examples:

- final CSV/JSON/Parquet artifact preparation;
- export manifest preparation;
- WANIA-facing output layout.

### src/mania/qc/

Use for future deterministic checks, such as:

- input existence checks;
- residue count matching;
- residue ID set matching;
- output artifact presence;
- data contract column checks.

QC should be deterministic and should not be LLM-based interpretation.

### src/mania/report/

Use for future deterministic report generation.

Possible future output:

- `analysis_report.html`

The report should summarize artifacts and QC results. It should not generate
biological interpretation unless that is explicitly designed later.

### docs/

Use for explanatory material, project decisions, assumptions, diagrams, and
migration notes that should not become Python code.

### tests/

Use when notebook behavior can be turned into a small, deterministic unit test
or fixture-based test.

Large scientific data must not be added to tests.

## Migration Priority Levels

Use the following priority labels:

- P0: required for MVP pipeline.
- P1: useful for v0.1 but not blocking.
- P2: future improvement.
- Out of scope: not planned for MANIA v0.1.

Priority should describe project importance, not how interesting the notebook
section is scientifically.

## Current Non-Goals

The current engineering skeleton does not include:

- notebook migration;
- MDAnalysis integration;
- real trajectory loading;
- output artifact generation;
- preprocessing implementation;
- generated notebook outputs;
- committed notebook data files.

Notebook review is allowed as planning. Notebook logic migration requires a
separate implementation task.
