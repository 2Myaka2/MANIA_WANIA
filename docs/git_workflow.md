# MANIA/WANIA Git Workflow

## Purpose

This guide describes how to work with Git in the `MANIA_WANIA` repository. It
is a practical beginner-friendly workflow guide, not a Git internals tutorial.

The goal is to keep Codex-assisted changes small, reviewable, and safe. The
scientific/backend CLI is operational through accepted Stage 24.G. The current
focus is the approved Stage 25 reproducibility and publication-hardening
roadmap. Stage 25.A software identity is complete. Stage 25.B run provenance
and effective sampling is complete. Stage 25.C input/output artifact inventory
and opt-in checksums is complete. Stage 25.D unified technical artifact validation is
complete. Stage 25.E observation-only PBC audit and runtime metadata is complete.
Stage 25.F reproducibility documentation and FAIR² bridge is next.
The scientific PBC protocol remains unresolved; MANIA applies no internal
minimum-image correction. Stage 25 as a whole
remains incomplete. FastAPI remains postponed.

## Branch Model

This repository uses a small branch model:

- `main`: stable branch for accepted milestones.
- `develop`: integration branch for current development.
- `feature/*`: small focused feature branches for code or package changes.
- `docs/*`: documentation-only branches.
- `fix/*`: bugfix branches.

Work should usually start from `develop`. Each task should get its own small
topic branch. After review and checks, task branches are merged into `develop`.
`develop` is merged into `main` only at stable milestones.

Example topic branches include:

- `docs/architecture`
- `docs/data-contract-v01`
- `docs/project-decisions`
- `docs/git_workflow`
- `feature/config-validation`

A topic branch does not need to merge `develop` after every commit. Update a
topic branch from `develop` before final merge only if `develop` has changed in
the meantime or if there may be conflicts.

This section documents the workflow only. Do not create, delete, rename, merge,
rebase, or switch branches unless that is the actual task.

## Basic Daily Workflow

Start a new code or package task from `develop`:

```bash
git status
git checkout develop
git pull
git checkout -b feature/example-task
```

For documentation-only tasks, use a `docs/*` branch:

```bash
git checkout -b docs/example-doc-task
```

After making changes, run checks and inspect what changed:

```bash
pytest
ruff check .
mypy src
git status
git diff
```

Stage only the files that belong to the task:

```bash
git add docs/git_workflow.md
git commit -m "docs: add git workflow guide"
```

Push the branch with its actual branch name:

```bash
git push -u origin feature/example-task
```

For a documentation branch, use the documentation branch name:

```bash
git push -u origin docs/git_workflow
```

## Updating A Topic Branch From `develop`

It is not necessary to merge `develop` into a topic branch after every commit.
Update the topic branch from `develop` when:

- `develop` changed while the branch was open;
- the branch touches files that may conflict with new changes;
- the branch is ready for final review or merge;
- tests behave differently from expected.

Safe beginner-friendly update commands:

```bash
git checkout docs/git_workflow
git merge develop
pytest
ruff check .
mypy src
```

This keeps the branch compatible with the latest accepted project state. Do not
use destructive commands such as `git reset --hard` for normal workflow.

## Commit Style

Use small, clear commits. A good commit changes one thing and has a message that
explains the purpose of the change.

Examples:

- `chore: initialize repository skeleton`
- `build: add package metadata and dev dependencies`
- `feat: add config validation`
- `docs: add project decisions`
- `docs: add data contract v0.1`
- `docs: add architecture guide`
- `docs: add git workflow guide`
- `test: add config tests`
- `fix: correct README formatting`

Common prefixes:

- `docs`: documentation-only changes.
- `feat`: user-visible functionality.
- `test`: tests.
- `fix`: corrections.
- `build`: packaging, dependency, or build metadata.
- `chore`: repository maintenance.

## Before Committing

Before each commit, check:

- `pytest` passes;
- `ruff check .` passes;
- `mypy src` passes;
- `git diff` contains only intended changes;
- `git status` shows no surprise files;
- no large data files are included;
- no unrelated files are changed;
- `.venv/` and caches are not staged;
- no secrets or credentials are staged.

## Working With Codex

Give Codex small tasks. List the exact files allowed to change and state clear
non-goals.

Ask Codex to report:

- changed files;
- commands run;
- check outputs;
- TODOs or limitations.

Review `git diff` before accepting Codex changes. Reject unapproved dependency
or scientific-semantic changes. Keep Stage 25 hardening tasks focused and
preserve accepted Stage 20–24 behavior and artifact contracts.

If Codex cannot run `pytest`, `ruff`, or `mypy` because the tools are not on
`PATH`, rerun them locally in `.venv` before accepting the task:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src
```

## Pull Request And Merge Workflow

A simple review flow:

- finish the topic branch;
- run `pytest`, `ruff check .`, and `mypy src`;
- push the topic branch;
- open a pull request into `develop`, or manually merge into `develop` if
  working locally;
- review the diff;
- check tests;
- merge when accepted;
- delete the topic branch after merge if it is no longer needed;
- later merge `develop` into `main` at stable milestones.

Example local merge into `develop`:

```bash
git checkout develop
git pull
git merge docs/example-doc-task
pytest
ruff check .
mypy src
git push
```

PR-based review is preferred when using GitHub. For a solo learning project, a
local merge is also acceptable if the diff is reviewed and checks pass.

## How To Recover From Mistakes

Start with safe inspection commands:

```bash
git status
git diff
git log --oneline
```

What they do:

- `git status`: shows changed, staged, and untracked files.
- `git diff`: shows unstaged file changes.
- `git log --oneline`: shows recent commits in a compact list.

Safe restore commands:

```bash
git restore <file>
git restore --staged <file>
```

What they do:

- `git restore <file>`: discards unstaged changes in one file.
- `git restore --staged <file>`: removes one file from the staging area without
  deleting the file or its edits.

Avoid advanced destructive commands during normal work:

```bash
git reset --hard
git clean -fd
git push --force
```

These commands can delete local changes or rewrite shared history. Use them only
with a clear reason and after making sure the work is backed up.

## Files That Should Not Be Committed

Do not commit local environments, caches, large data, outputs, or credentials:

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`
- `data/`
- `outputs/`
- `mania_output/`
- large trajectory files;
- `.xtc`
- `.trr`
- `.tpr`
- `.dcd`
- `.edr`
- `.gro`
- `.pdb`
- local secrets or credentials;
- `.env`

Scientific data files should stay outside normal Git commits unless there is an
explicit decision to add a small test fixture later.

## Recommended Workflow For This Project Stage

For the approved [Stage 25 hardening roadmap](stage25_reproducibility_hardening.md):

- keep tasks small;
- proceed in separate accepted hardening steps;
- use separate topic branches for each Codex task;
- start topic branches from the latest `develop`;
- merge accepted task branches back into `develop`;
- do not merge `develop` into a topic branch after every commit unless needed;
- keep FastAPI and unrelated product work postponed;
- do not make unreviewed scientific-semantic changes; changes to accepted
  Stage 20–24 scientific behavior require a separate approved scope;
- new dependencies require separate approval;
- preserve existing artifact contracts and CLI behavior unless explicitly
  changed by a focused task;
- always verify with `pytest`, `ruff check .`, and `mypy src` before committing
  or merging.
