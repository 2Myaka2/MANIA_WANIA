# MANIA/WANIA

MANIA is a Python package for preparing molecular dynamics analysis artifacts.
WANIA is a future web interface that consumes MANIA outputs.

This repository is currently at the engineering skeleton stage: package layout,
config validation, CLI, documentation, and tests. It is not yet performing real
scientific trajectory analysis.

## Current Status

The current skeleton supports:

- Editable install with `pip install -e ".[dev]"`.
- Importing the package as `mania`.
- Checking the package version with `mania --version`.
- Validating the example YAML config with
  `mania validate-config configs/mania.example.yaml`.
- Running the test suite with `pytest`.
- Running lint checks with `ruff check .`.
- Running type checks with `mypy src`.

## Current Non-Goals

The current stage does not include:

- MDAnalysis integration.
- GROMACS execution.
- FastAPI.
- Yandex Disk integration.
- Final residue registries.
- Real scientific trajectory analysis.

## Repository Structure

```text
configs/     Example MANIA YAML configuration files.
docs/        Project decisions, data contract, and supporting documentation.
src/mania/   Python package source code.
tests/       Minimal tests for the skeleton package and data contract.
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"

mania --version
mania validate-config configs/mania.example.yaml
pytest
ruff check .
mypy src
```

## Config Validation

The example configuration lives at `configs/mania.example.yaml`. It defines the
project metadata, one or two systems, runtime options, and feature flags for the
current skeleton.

Validate it with:

```bash
mania validate-config configs/mania.example.yaml
```

Config validation checks the YAML structure and Pydantic model constraints. It
does not check whether trajectory or topology files exist yet.

## Documentation

- `docs/decisions.md`: accepted MANIA/WANIA v0.1 project decisions.
- `docs/data_contract.md`: MANIA v0.1 output artifact contract for WANIA.
- `docs/architecture.md`: planned architecture notes placeholder.
- `docs/git_workflow.md`: planned git workflow notes placeholder.
- `AGENTS.md`: working rules for Codex, coding agents, and assistants.

## Development Workflow

1. Create a feature branch.
2. Make a small focused change.
3. Run checks:

   ```bash
   pytest
   ruff check .
   mypy src
   ```

4. Commit with a clear message.
