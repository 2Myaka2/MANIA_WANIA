# Local scientific integration tests

## Purpose

The local scientific harness supports explicit, developer-run scientific tests
without making optional dependencies or real molecular dynamics (MD) data part
of the default test suite or default CI.

## Implemented harness

Stage 11.3 registers these pytest markers:

- `local_scientific`: local-only tests skipped unless explicitly enabled;
- `requires_mdanalysis`: tests requiring the optional MDAnalysis runtime;
- `requires_real_md_data`: tests requiring a local real MD reference package.

Tests under `tests/local_scientific` are collected by plain `pytest` but skipped
by default. The harness does not alter tests outside that directory.

## Default behavior

The default command remains:

```bash
pytest
```

With `MANIA_RUN_LOCAL_SCIENTIFIC` unset, empty, or set to any value other than
`1`, `true`, `yes`, or `on` (case-insensitive), all tests under
`tests/local_scientific` are skipped.

Default/core tests do not require optional extras, MDAnalysis, local real data,
or a local reference package.

Default/core tests must not require these extras.

## Enabling local tests

Enable the local scientific directory explicitly:

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 pytest tests/local_scientific
```

Tests marked `requires_mdanalysis` run only when the Stage 11.1 availability
helper reports MDAnalysis is installed. Otherwise they skip with a clear
reason. Install an optional extra locally when needed:

```bash
pip install ".[md]"
pip install ".[science]"
```

## Local reference package

`MANIA_LOCAL_REFERENCE_PACKAGE` may point to a local-only reference package:

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 \
MANIA_LOCAL_REFERENCE_PACKAGE=/path/to/local/package \
pytest tests/local_scientific
```

Tests marked `requires_real_md_data` run only when that path exists and is a
directory. The harness does not create the path or scan it for scientific
files.

Real topology files must not be committed.
Real trajectory files must not be committed.
Real structures and full reference-package data must also remain local.
`data/reference` remains local and uncommitted unless a future explicit
decision changes that policy.

## Test categories

### Default unit/contract tests

Default tests remain lightweight and require neither optional scientific
dependencies nor real MD data.

### Documentation/config tests

Documentation and configuration tests verify markers, environment behavior,
dependency boundaries, and the absence of committed real data.

### Local scientific integration tests

The local directory is opt-in harness space. It contains the Stage 11.3 marker
smoke tests, a Stage 11.4 single-condition loading test, and a Stage 11.5
manifest-wide condition loading test. Stage 11.6 adds a metadata report test
for already loaded local runtimes.

The loading and metadata tests require:

- `MANIA_RUN_LOCAL_SCIENTIFIC=1`;
- MDAnalysis installed through the `md` or `science` optional extra;
- `MANIA_LOCAL_REFERENCE_PACKAGE` pointing to local data.

The loading and metadata tests look for `preprocessing_manifest.yaml` and then
`manifest.yaml` under the local package directory. The Stage 11.4 test loads
only the first condition in manifest order; the Stage 11.5 test loads all
declared conditions; the Stage 11.6 test collects metadata from that manifest
load result. If no supported manifest exists, the tests skip with a clear
message. Default CI does not run these opt-in tests.

## Stage 9.3 history

Stage 9.3 documented the original strategy only.
Stage 9.3 does not register pytest markers.
It does not create `tests/local_scientific`, import MDAnalysis, implement
trajectory loading, compute Rg or contacts, or modify CI. Stage 11.3 implements
the harness while preserving those scientific and CI boundaries.

See `docs/default_ci_scientific_boundary.md` for default CI requirements.
