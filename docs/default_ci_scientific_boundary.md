# Default CI scientific boundary

## Purpose

This document defines the default continuous integration (CI) boundary for
scientific runtime and scientific data concerns. Default CI protects the
lightweight MANIA/WANIA backend and must remain separate from future local-only
scientific runtime work.

## Current CI status

At Stage 11.3, `.github/workflows/ci.yml`:

- installs the project and development tooling with `.[dev]`;
- runs the default test suite with plain `pytest`;
- does not install `.[md]`;
- does not install `.[science]`;
- does not set `MANIA_RUN_LOCAL_SCIENTIFIC`;
- does not provide `MANIA_LOCAL_REFERENCE_PACKAGE`;
- does not reference `data/reference`;
- does not select local scientific tests by marker or path.

Stage 11.3 adds the test harness without modifying that workflow.

## Default CI guarantees

Default CI should keep the lightweight backend healthy, including:

- manifest and config models;
- JSON and YAML loaders;
- backend contract validators;
- the comparison layer;
- graph diagnostics that do not require `networkx`;
- the notebook export adapter;
- the current lightweight CLI workflow;
- preprocessing path and reference package metadata checks that do not parse
  scientific files;
- documentation and configuration tests.

## What default CI must not require

Default CI must not require:

- `MDAnalysis`;
- GROMACS;
- `numpy` as an explicit project dependency;
- `pandas`;
- `networkx`;
- `pyarrow`;
- real topology files;
- real trajectory files;
- real reference-structure files;
- full real residue libraries;
- a local reference package;
- `data/reference`;
- notebooks, parquet files, figures, or full reference exports;
- internet access or downloads.

## Relationship to optional extras

The `md` and `science` optional extras exist for future opt-in scientific
runtime work. Default CI should not install these extras. Defining an optional
extra does not make it a default or core requirement.

If a dedicated scientific CI workflow or job is accepted later, it must be
explicit and separate from default CI.

## Relationship to local scientific integration tests

The local scientific harness exists under `tests/local_scientific`. Its
registered markers are `local_scientific`, `requires_mdanalysis`, and
`requires_real_md_data`. These tests remain opt-in and are skipped unless
`MANIA_RUN_LOCAL_SCIENTIFIC` is enabled.

Default CI must not enable `MANIA_RUN_LOCAL_SCIENTIFIC`, set
`MANIA_LOCAL_REFERENCE_PACKAGE`, select `tests/local_scientific` explicitly,
or install `.[md]` or `.[science]`.

See `docs/local_scientific_integration_tests.md` for the local test strategy.

## Relationship to local reference packages

Local reference packages are user-local inputs. They are not committed and are
not required in default CI. Default CI should not rely on
`MANIA_LOCAL_REFERENCE_PACKAGE`, a similar environment variable, or
`data/reference`.

## Future change process

Any future scientific CI behavior must be proposed explicitly. An accepted
scientific CI strategy should require:

- a separate workflow or job;
- explicit optional extras installation;
- explicit pytest marker selection;
- an explicit local or synthetic dataset policy;
- no committed real MD data unless a future ADR explicitly permits a tiny,
  deterministic synthetic fixture.

## Non-goals for Stage 9.4

Stage 9.4 does not modify CI workflows.
Stage 9.4 does not add scientific CI jobs.
Stage 9.4 does not install scientific extras in CI.
Stage 9.4 does not register pytest markers.
Stage 9.4 does not create `tests/local_scientific`.
Stage 9.4 does not add real MD data.
Stage 9.4 does not add topology or trajectory fixtures.
Stage 9.4 does not import MDAnalysis, numpy, pandas, networkx, or pyarrow.
Stage 9.4 does not implement trajectory loading or topology loading.
Stage 9.4 does not compute Rg.
Stage 9.4 does not compute contacts.
Stage 9.4 does not add CLI or workflow integration.
Stage 9.4 does not modify runtime source.

## Future stages

```text
Stage 9.4:
  default CI scientific boundary documentation/tests.

Stage 10:
  residue-library bridge work, still without default CI real-data dependency.

Stage 11:
  minimal trajectory loading prototype after optional runtime decisions.
  Any local scientific tests must remain opt-in and skipped outside local setup.

Stage 12+:
  Rg/contact/graph scientific tests, still local-only unless a future explicit
  CI strategy is accepted.
```

These later stages are planning notes and are not implemented by Stage 9.4.

Stage 11.3 implements only the local scientific test harness. It does not add
scientific CI behavior, real MD data, or topology/trajectory loading tests.
