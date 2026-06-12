# Local scientific integration tests

## Purpose

This document defines how future scientific integration tests should be
organized. These tests will be local, explicit opt-in checks rather than part
of the default test suite or default CI.

## Current status

Stage 9.3 is documentation and test-strategy work only. Stage 9.2 defined the
optional `md` and `science` extras, but Stage 9.3 does not add scientific
integration tests or real molecular dynamics (MD) data.

Default tests still do not require optional scientific dependencies. Stage 9.3
does not modify CI or runtime source.

## Test categories

### Default unit/contract tests

Default unit/contract tests:

- run in the default test suite;
- do not require optional scientific dependencies;
- do not require real MD data;
- may use tiny committed synthetic or text fixtures;
- may validate contracts, manifests, reports, config parsing, documentation,
  and lightweight behavior.

### Documentation/config tests

Documentation/config tests validate documentation, examples, ADRs, and
`pyproject.toml` optional extras. They do not import scientific dependencies
and run by default.

### Local scientific integration tests

Local scientific integration tests are future opt-in tests only. They may:

- require optional extras such as `.[md]` or `.[science]`;
- require local uncommitted MD data;
- use a local reference package;
- run outside default CI;
- be skipped unless explicitly enabled.

They must not become part of default CI, require real data in the repository,
or make optional scientific dependencies necessary for the default test suite.

## Proposed future markers

The project currently has no registered custom pytest markers. A future
implementation may propose:

- `local_scientific`: requires local user/reference setup and is not part of
  default CI;
- `requires_mdanalysis`: requires the optional `MDAnalysis` dependency;
- `requires_real_md_data`: requires local uncommitted trajectory or topology
  data.

Stage 9.3 does not register pytest markers, add marked scientific tests, or
create `tests/local_scientific`.

## Local data policy

- Real topology files must not be committed.
- Real trajectory files must not be committed.
- Real reference-structure files must not be committed.
- Full real residue libraries must remain local/reference inputs.
- Notebooks, parquet files, figures, and full exports must not be committed.
- `data/reference/...` must remain local and uncommitted unless a later
  explicit task changes that policy.
- Future local scientific tests should use user-provided local paths or a local
  reference package.

## Optional dependency policy

Future local scientific integration tests may require one of the optional
extras:

```bash
pip install ".[md]"
pip install ".[science]"
```

Default/core tests must not require these extras. Documentation/config tests
must not import optional scientific dependencies.

Future tests should skip with a clear message when an optional dependency is
missing. Missing local data may cause a clear skip or a local preflight failure,
depending on the later test design. Stage 9.3 does not implement skip helpers.

## Suggested local package layout

The Stage 8.5 local reference package convention can support future local
scientific tests:

```text
local_reference_package/
  preprocessing_manifest.yaml
  data/
    normal/
      topology.tpr
      trajectory.xtc
    tumor/
      topology.tpr
      trajectory.xtc
  residue_library/
    mania_residue_library.json
```

This layout is local-only. The directory and its files are not committed and
are not part of default tests.

## How future local tests should run

The following is a future example only:

```bash
pip install ".[md]"

MANIA_LOCAL_REFERENCE_PACKAGE=/path/to/local_reference_package \
  pytest tests/local_scientific -m local_scientific
```

This command is not enabled by Stage 9.3. The `tests/local_scientific`
directory is not created, and the marker is not registered in Stage 9.3. The
exact command may be refined in Stage 9.4 or Stage 11.

## What default tests must not require

Default tests must not require:

- `MDAnalysis`;
- an explicit `numpy` dependency;
- `pandas`;
- `networkx`;
- `pyarrow`;
- GROMACS;
- real topology files;
- real trajectory files;
- local reference packages;
- internet access or downloads;
- notebook, parquet, or figure artifacts.

## Non-goals for Stage 9.3

Stage 9.3 does not:

- add local scientific integration tests;
- add real MD data;
- add topology fixtures;
- add trajectory fixtures;
- modify CI;
- register pytest markers;
- create `tests/local_scientific`;
- import MDAnalysis;
- import numpy, pandas, networkx, or pyarrow;
- implement trajectory loading;
- implement topology loading;
- compute Rg;
- compute contacts;
- run residue QC from topology or trajectory data;
- add CLI integration;
- add workflow integration;
- modify runtime source.

## Future stages

```text
Stage 9.3:
  local-only scientific integration test strategy.

Stage 9.4:
  document/enforce that default CI does not depend on real MD data.

Stage 10:
  residue-library bridge work.

Stage 11:
  minimal trajectory loading prototype and first local-only scientific
  integration tests, after dependency/runtime decisions.

Stage 12+:
  Rg/contact/graph scientific integration tests.
```

These later stages are planning notes and are not implemented by Stage 9.3.
