# MANIA/WANIA Codex Task Templates

This document contains reusable task templates for Codex.

Use these templates to keep tasks small, explicit, and easy to review.

## Template 1: Documentation-Only Task

    Task: <short task title>.

    Context:
    - Documentation-only task.
    - MANIA_WANIA is at skeleton stage.
    - Do not modify Python code.
    - Do not add dependencies.
    - Do not implement scientific MD logic.
    - Follow AGENTS.md and relevant docs.

    Files to modify:
    - <exact file path>

    Do not modify any other files.

    Requirements:
    1. <requirement>
    2. <requirement>
    3. <requirement>

    Acceptance criteria:
    - The document is filled and readable.
    - No Python files are modified.
    - No dependencies are added.
    - pytest passes.
    - ruff check . passes.
    - mypy src passes.
    - Changed files are limited to the listed files.

    Commands to run:
    - pytest
    - ruff check .
    - mypy src
    - git status --short
    - git diff -- <files>
    - git diff --name-only

    If bare commands are not available on PATH, also try:
    - .venv/bin/pytest
    - .venv/bin/ruff check .
    - .venv/bin/mypy src

    Return:
    - changed files
    - short summary
    - exact commands run
    - outputs of pytest, ruff check ., mypy src
    - git status --short output
    - git diff --name-only output
    - TODOs if any

## Template 2: Small Implementation Task

    Task: <short task title>.

    Context:
    - MANIA_WANIA is at skeleton stage.
    - This is a small implementation + tests task.
    - Do not implement scientific MD logic.
    - Do not read trajectory/topology files.
    - Do not create output files or directories unless explicitly requested.
    - Do not add dependencies.
    - Follow AGENTS.md and relevant docs.

    Files to modify:
    - <source file>
    - <test file>

    Do not modify any other files.

    Requirements:
    1. <implementation requirement>
    2. <implementation requirement>
    3. <test requirement>

    Acceptance criteria:
    - pytest passes.
    - ruff check . passes.
    - mypy src passes.
    - No new dependencies.
    - No scientific MD logic.
    - No real MD files are read.
    - Changed files are limited to the listed files.

    Commands to run:
    - pytest
    - ruff check .
    - mypy src
    - git status --short
    - git diff -- <files>
    - git diff --name-only

    If bare commands are not available on PATH, also try:
    - .venv/bin/pytest
    - .venv/bin/ruff check .
    - .venv/bin/mypy src

    Return:
    - changed files
    - short summary
    - exact commands run
    - outputs of pytest, ruff check ., mypy src
    - git status --short output
    - git diff --name-only output
    - confirmation that only allowed files changed
    - TODOs if any

## Template 3: CLI Task

    Task: <short CLI task title>.

    Context:
    - MANIA_WANIA already has a working CLI command: mania.
    - Do not implement scientific MD logic.
    - Do not add dependencies.
    - Keep existing CLI behavior unchanged unless the task explicitly asks otherwise.
    - Follow AGENTS.md and relevant docs.

    Files to modify:
    - src/mania/cli.py
    - <test file>

    Requirements:
    1. <CLI behavior>
    2. <error behavior>
    3. <tests>

    Keep these working:
    - mania --version
    - mania validate-config configs/mania.example.yaml
    - mania run --config configs/mania.example.yaml
    - python -m mania --version

    Acceptance criteria:
    - pytest passes.
    - ruff check . passes.
    - mypy src passes.
    - No new dependencies.
    - No scientific MD logic.
    - Changed files are limited to the listed files.

    Commands to run:
    - mania --version
    - mania validate-config configs/mania.example.yaml
    - mania run --config configs/mania.example.yaml
    - python -m mania --version
    - pytest
    - ruff check .
    - mypy src
    - git status --short
    - git diff -- <files>
    - git diff --name-only

    If bare commands are not available on PATH, also try:
    - .venv/bin/mania --version
    - .venv/bin/mania validate-config configs/mania.example.yaml
    - .venv/bin/mania run --config configs/mania.example.yaml
    - .venv/bin/python -m mania --version
    - .venv/bin/pytest
    - .venv/bin/ruff check .
    - .venv/bin/mypy src

    Return:
    - changed files
    - short summary
    - exact commands run
    - command outputs
    - TODOs if any

## Template 4: Test-Only Task

    Task: <short test task title>.

    Context:
    - Test-only task.
    - Do not modify implementation code unless a test exposes a real bug and the fix is explicitly requested.
    - Do not add dependencies.
    - Do not implement scientific MD logic.
    - Follow AGENTS.md and relevant docs.

    Files to modify:
    - <test file>

    Requirements:
    1. <test requirement>
    2. <test requirement>

    Acceptance criteria:
    - pytest passes.
    - ruff check . passes.
    - mypy src passes.
    - No implementation files are modified.
    - No dependencies are added.
    - Changed files are limited to the listed test files.

    Commands to run:
    - pytest
    - ruff check .
    - mypy src
    - git status --short
    - git diff -- <files>
    - git diff --name-only

    Return:
    - changed files
    - short summary
    - exact commands run
    - outputs
    - TODOs if any

## Template 5: Review Current Diff

    Task: review the current diff.

    Context:
    - Review-only task.
    - Do not modify files.
    - Follow AGENTS.md and docs/code_review.md.

    Review:
    - git status --short
    - git diff --name-only
    - git diff

    Check:
    - whether changed files match the intended task;
    - whether forbidden dependencies or scientific logic were added;
    - whether tests are present for functional changes;
    - whether data contract and constants remain consistent;
    - whether README/docs need updates.

    Run:
    - pytest
    - ruff check .
    - mypy src

    Return:
    - summary of changed files
    - risks
    - whether the diff is acceptable
    - required fixes, if any
    - command outputs
