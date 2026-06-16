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
for already loaded local runtimes, and Stage 11.7 adds a residue-name
extraction test. Stage 12.1d adds an Rg computation smoke test over the loaded
manifest result. Stage 12.2d adds an Rg CSV export and validation smoke test.
Stage 13.2c adds a contacts computation smoke test over the loaded manifest
result. Stage 13.3e adds a contacts CSV export and validation smoke test.

These local scientific integration tests require:

- `MANIA_RUN_LOCAL_SCIENTIFIC=1`;
- MDAnalysis installed through the `md` or `science` optional extra;
- `MANIA_LOCAL_REFERENCE_PACKAGE` pointing to local data.

These tests look for `preprocessing_manifest.yaml` and then `manifest.yaml`
under the local package directory. The Stage 11.4 test loads only the first
condition, Stage 11.5 loads all conditions, Stage 11.6 collects metadata, and
Stage 11.7 extracts residue names from the loaded result. Stage 12.1d loads all
conditions and computes manifest-level Rg. Stage 12.2d repeats that accepted
loading and computation chain, writes `rg_timeseries.csv` only under pytest's
temporary path, and validates the exported file. Stage 13.2c loads all
conditions and computes manifest-level contacts. Stage 13.3e repeats the
accepted contacts computation chain, writes `contacts_perframe.csv` and
`contact_edges.csv` only under pytest's temporary path, and validates both
exported files. If no supported manifest exists, the tests skip with a clear
message. Default CI does not run these opt-in tests.

Stage 11.8 records this completed local coverage as single-condition loading,
manifest loading, metadata, and residue names. The suite remains opt-in:
`MANIA_RUN_LOCAL_SCIENTIFIC` enables it, and
`MANIA_LOCAL_REFERENCE_PACKAGE` identifies local data. The runtime boundary
before Rg is documented in
`docs/preprocessing_runtime_boundary_before_rg.md`.

The Stage 12.1d smoke test checks the Rg result/report shape, JSON
serialization, deterministic frame indexes, and finite non-negative Rg
values. It does not write CSV, compare numeric references, compute contacts,
or generate graphs.

## Stage 13.2c local contacts computation smoke test

The Stage 13.2c smoke test is opt-in through the existing harness. It requires:

- `MANIA_RUN_LOCAL_SCIENTIFIC=1`;
- MDAnalysis through the optional `md` or `science` setup;
- `MANIA_LOCAL_REFERENCE_PACKAGE` pointing to a local package containing
  `preprocessing_manifest.yaml` or `manifest.yaml`.

The test loads the local manifest, loads condition runtimes, computes
manifest-level contacts with `compute_manifest_contacts(...)`, inspects the
result shape, and serializes the result with `json.dumps(...)`.

The test does not write contacts CSV, validate contacts CSV, compare
references, run graph diagnostics, or run in default CI. It does not assert
exact contact counts or benchmark timing thresholds.

## Stage 13.3e local contacts export smoke test

The Stage 13.3e smoke test is opt-in through the existing harness. It requires:

- `MANIA_RUN_LOCAL_SCIENTIFIC=1`;
- MDAnalysis through the optional `md` or `science` setup;
- `MANIA_LOCAL_REFERENCE_PACKAGE` pointing to a local package containing
  `preprocessing_manifest.yaml` or `manifest.yaml`.

The test runs the accepted chain:

```text
load manifest -> load runtimes -> compute manifest contacts
-> write contacts_perframe.csv -> write contact_edges.csv
-> validate both CSVs
```

The generated CSV outputs are written only to pytest's temporary directory
during the test. The test checks write and validation report shape,
row-count consistency, and JSON serialization without asserting exact contact
counts or requiring contacts to be non-zero.

The test does not compare references, build a report bundle, run graph
diagnostics, produce graph outputs, write persistent repository artifacts, or
run in default CI.

## Stage 12.2d local Rg export smoke test

The Stage 12.2d smoke test is opt-in through the existing harness. It requires:

- `MANIA_RUN_LOCAL_SCIENTIFIC=1`;
- MDAnalysis through the optional `md` or `science` setup;
- `MANIA_LOCAL_REFERENCE_PACKAGE` pointing to a local package containing
  `preprocessing_manifest.yaml` or `manifest.yaml`.

The test loads the local manifest and condition runtimes, computes
manifest-level Rg, writes `rg_timeseries.csv` under pytest's `tmp_path`, and
validates the exported CSV. It checks the exact header, report serialization,
row-count consistency, known condition names, and lowercase `frame_passed`
values.

The test does not compare exact Rg values or use numeric tolerances. It does
not write persistent repository artifacts or run in default CI. Generated
files stay in a pytest temp directory. There is no committed generated CSV
from local data.

## Final Stage 12 local scientific boundary

Stage 12 includes exactly two Rg-focused local scientific smoke tests:

- the Stage 12.1d local scientific Rg computation smoke;
- the Stage 12.2d local scientific Rg export smoke.

They are opt-in through `MANIA_RUN_LOCAL_SCIENTIFIC=1`, require optional
MDAnalysis setup, and require `MANIA_LOCAL_REFERENCE_PACKAGE`. Local
scientific tests are skipped by default, and default CI does not run them as
real-data tests.

The computation smoke checks manifest-level Rg report shape and basic numeric
sanity. The export smoke writes `rg_timeseries.csv` only into a pytest temp
directory and validates it. No real MD data or generated local-data CSV is
committed. Stage 12 adds no local scientific comparison, report-bundle,
contacts, or graph smoke test.

## Stage 9.3 history

Stage 9.3 documented the original strategy only.
Stage 9.3 does not register pytest markers.
It does not create `tests/local_scientific`, import MDAnalysis, implement
trajectory loading, compute Rg or contacts, or modify CI. Stage 11.3 implements
the harness while preserving those scientific and CI boundaries.

See `docs/default_ci_scientific_boundary.md` for default CI requirements.
