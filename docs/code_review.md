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

The MANIA scientific/backend CLI is operational through accepted Stage 24.G.
[Stage 25](stage25_reproducibility_hardening.md) is approved as reproducibility
and publication hardening. Stage 25.A software identity is complete. Stage
25.B run provenance and effective sampling is complete. Stage 25.C
input/output artifact inventory and opt-in checksums is complete. Stage 25.D
unified technical artifact validation is complete. Stage 25.E observation-only PBC audit and runtime metadata is complete.
Stage 25.F reproducibility documentation and FAIR² bridge is complete.
Stage 25.G final technical-hardening acceptance is next.
The scientific PBC protocol remains unresolved; MANIA applies no internal
minimum-image correction. Stage 25 as a whole remains incomplete.
FastAPI remains postponed.

Review small, focused hardening steps against their approved scope. Preserve
accepted scientific semantics, existing CLI behavior, and Stage 20–24 artifact
compatibility unless a focused task explicitly authorizes changes.

## 3. Forbidden Or Postponed Work

MDAnalysis and trajectory/topology reading already exist within the optional
scientific dependency boundary. Reject unapproved changes to:

- scientific runtime behavior;
- trajectory loading;
- frame sampling;
- contact computation;
- typed-interaction semantics;
- RIN algorithms;
- PCA;
- clustering;
- scientific schemas and scientific rows;
- dependencies, including the optional scientific dependency boundary.

Keep unrelated scientific scope postponed. Reject accidental additions of:

- GROMACS execution or wrappers;
- FastAPI;
- database infrastructure or background workers;
- WANIA redesign;
- pandas;
- pyarrow;
- networkx;
- ESM or ESM-2 implementation;
- Yandex Disk integration;
- DSSP/SASA/RMSF implementation;
- energy rerun implementation;
- final biological interpretation in reports.

These may be added later only through explicit, focused tasks.

## 4. Dependencies

Check:

- no new dependency was added unless explicitly requested;
- `pyproject.toml` was not modified in docs-only tasks;
- the existing optional scientific dependency boundary was preserved unless
  explicitly authorized;
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
