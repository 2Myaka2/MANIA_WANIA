# MANIA/WANIA Code Review Checklist

This checklist is used before accepting Codex changes, merging a topic branch
into `develop`, or opening a pull request.

The goal is to keep MANIA/WANIA changes small, reviewable, and safe.

## 1. Scope

Check that the change matches the task.

- Only the files listed in the task were modified.
- No unrelated refactoring was added.
- No speculative architecture was added.
- No large placeholder module trees were created.
- The change is small enough to review in one pass.

If the change touches files outside the task, reject it unless there is a clear
reason and the reason is documented.

## 2. Project Stage

MANIA/WANIA is currently at the engineering skeleton stage.

Prefer changes in:

- documentation;
- config validation;
- CLI skeleton;
- tests;
- constants;
- small typed helpers;
- pipeline placeholders.

Do not accept real scientific MD implementation unless the task explicitly asks
for it.

## 3. Forbidden Or Postponed Work

Reject accidental additions of:

- MDAnalysis;
- GROMACS execution or wrappers;
- FastAPI;
- pandas;
- pyarrow;
- networkx;
- ESM or ESM-2 implementation;
- Yandex Disk integration;
- real trajectory/topology reading;
- DSSP/SASA/RMSF implementation;
- energy rerun implementation;
- final biological interpretation in reports.

These may be added later only through explicit, focused tasks.

## 4. Dependencies

Check:

- no new dependency was added unless explicitly requested;
- `pyproject.toml` was not modified in docs-only tasks;
- heavy scientific dependencies were not added during skeleton tasks;
- runtime and dev dependencies remain minimal.

## 5. Data Contract

If the change touches artifacts, schemas, exports, or constants, check:

- `docs/data_contract.md` and `src/mania/constants.py` remain consistent;
- `SCHEMA_VERSION` remains correct;
- `comparison.csv` and `stats.csv` remain cross-condition artifacts;
- `graph.json` is not treated as a tabular artifact;
- `ARTIFACT_COLUMNS` does not include `graph.json`;
- column order is stable and covered by tests.

## 6. Config And CLI

If the change touches config or CLI, check:

- `mania --version` still works;
- `mania validate-config configs/mania.example.yaml` still works;
- `mania run --config configs/mania.example.yaml` still prints only a placeholder plan;
- config validation does not check physical topology/trajectory file existence yet;
- validation errors are readable and do not print tracebacks for normal user errors.

## 7. Residue Registry

If the change touches `src/mania/residues.py`, check:

- final lipid/glycan/glycolipid residue lists were not invented;
- placeholder registries remain explicit if final lists are unavailable;
- glycolipids are not duplicated as both lipid and glycan RIN edges;
- `edge_type = "protein_glycolipid"` remains the intended glycolipid edge type;
- tests use fake names, not real residue lists.

## 8. Files And Data

Make sure the change does not add:

- `.venv/`;
- `__pycache__/`;
- `.pytest_cache/`;
- `.ruff_cache/`;
- `.mypy_cache/`;
- `data/`;
- `outputs/`;
- `mania_output/`;
- large trajectory files;
- `.xtc`;
- `.trr`;
- `.tpr`;
- `.dcd`;
- `.edr`;
- `.gro`;
- `.pdb`;
- `.env`;
- secrets or credentials.

Scientific data files should stay outside normal Git commits unless there is a
separate small test-fixture decision.

## 9. Tests And Checks

Before accepting a task, run:

    pytest
    ruff check .
    mypy src

If bare commands are unavailable, use the virtual environment:

    .venv/bin/pytest
    .venv/bin/ruff check .
    .venv/bin/mypy src

After push, GitHub Actions CI should pass.

## 10. Review Outputs

For every Codex task, require:

- changed files;
- short summary;
- exact commands run;
- outputs of `pytest`, `ruff check .`, and `mypy src`;
- `git status --short`;
- `git diff --name-only`;
- TODOs, if any.

Do not accept “tests passed” without command output.
