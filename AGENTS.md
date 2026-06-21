# AGENTS.md

## Purpose

This file defines mandatory working rules for Codex, coding agents, and
assistants that modify the `MANIA_WANIA` repository.

Keep this file short and strict. Detailed project decisions live in `docs/`.

Main rule:

> Work in small, reviewable, testable steps. Do not expand architecture,
> dependencies, or scientific logic unless the task explicitly asks for it.

## Project Stage

`MANIA_WANIA` is currently at the engineering skeleton stage.

Current focus:

- package structure;
- config validation;
- CLI skeleton;
- documentation;
- tests;
- data contract;
- CI;
- small typed helpers.

Do not treat planned scientific modules as implemented features.

## Mandatory Rules

1. Modify only the files listed in the task.
2. Keep every change small and focused.
3. Do not add unrelated refactoring.
4. Do not create large future module trees unless explicitly requested.
5. Do not implement scientific MD logic unless explicitly requested.
6. Do not add dependencies unless explicitly requested.
7. Do not add large data files, outputs, caches, virtual environments, or secrets.
8. Do not hardcode local user paths.
9. Do not invent final lipid, glycan, or glycolipid residue lists.
10. Every functional change must include tests or a clear verification path.
11. Documentation-only tasks must not modify Python code.
12. Code tasks must preserve existing CLI behavior unless the task explicitly changes it.

## Required Checks

For normal development tasks, run:

    pytest
    ruff check .
    mypy src

If bare commands are unavailable on `PATH`, use the virtual environment:

    .venv/bin/pytest
    .venv/bin/ruff check .
    .venv/bin/mypy src

For CLI-related tasks, also check relevant commands, for example:

    mania --version
    mania validate-config configs/mania.example.yaml
    mania run --config configs/mania.example.yaml
    python -m mania --version

## Required Task Report

Every Codex task must return:

- changed files;
- short summary;
- exact commands run;
- outputs of `pytest`, `ruff check .`, and `mypy src`;
- relevant CLI command outputs, if applicable;
- `git status --short`;
- `git diff --name-only`;
- confirmation that only allowed files changed;
- TODOs, if any.

Do not claim checks passed without showing command output.

## Forbidden Unless Explicitly Requested

Do not add or implement:

- MDAnalysis;
- GROMACS execution or wrappers;
- FastAPI;
- pandas;
- pyarrow;
- networkx;
- ESM or ESM-2 implementation;
- Yandex Disk integration;
- trajectory/topology reading;
- DSSP/SASA/RMSF implementation;
- energy rerun implementation;
- allosteric paths implementation;
- final biological interpretation in reports.

## Repository Commands

Install locally:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -U pip setuptools wheel
    python -m pip install -e ".[dev]"

Common checks:

    pytest
    ruff check .
    mypy src

Useful CLI checks:

    mania --version
    mania validate-config configs/mania.example.yaml
    mania run --config configs/mania.example.yaml
    python -m mania --version

## Project References

Before changing project architecture, data contract, workflow, or review rules,
read the relevant document:

- `README.md` — project entry point.
- `docs/decisions.md` — accepted MANIA/WANIA v0.1 decisions.
- `docs/data_contract.md` — output artifact contract for WANIA.
- `docs/architecture.md` — intended package architecture.
- `docs/git_workflow.md` — branch and Git workflow.
- `docs/code_review.md` — review checklist.
- `docs/task_templates.md` — reusable Codex task templates.

When a task touches one of these areas, follow the corresponding document.

## Current Stable Names

Do not rename these unless explicitly requested:

- installable project name: `mania-wania`;
- Python import package: `mania`;
- CLI command: `mania`;
- example config: `configs/mania.example.yaml`.

## Git Workflow

Use small topic branches based on `develop`.

Typical flow:

    git checkout develop
    git pull
    git checkout -b feature/example-task

After the task:

    pytest
    ruff check .
    mypy src
    git status
    git diff
    git add ...
    git commit -m "..."

Merge accepted task branches back into `develop`.

Do not merge `develop` into a topic branch after every commit unless needed.
Update from `develop` before final merge if `develop` changed or conflicts are
likely.
