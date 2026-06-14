# Preprocessing Rg export

## What this guide covers

This guide documents the accepted Stage 12 Python API chain for computing,
writing, validating, and comparing radius-of-gyration (Rg) time-series output.
Stage 12.2c added documentation and synthetic examples only. Stage 12.3b adds
dependency-free numeric-tolerant comparison for two exported CSV files. Stage
12.4a adds a lightweight in-memory report bundle for existing results.

## Current Stage 12 export chain

The manifest-level export chain is:

1. Load a preprocessing manifest.
2. Load the manifest condition runtimes.
3. Compute manifest-level Rg results.
4. Write `rg_timeseries.csv`.
5. Validate the exported `rg_timeseries.csv`.

Loading and computation may require MDAnalysis and caller-provided trajectory
files. Writing and validation consume existing results or CSV files and do not
acquire MDAnalysis themselves.

## Public APIs

The accepted imports are:

```python
from mania.preprocessing import (
    compute_manifest_rg,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
    validate_rg_timeseries_csv,
    write_rg_timeseries_csv,
)
```

These are Python APIs. Stage 12.2c does not add a workflow wrapper or a CLI
command.

`write_rg_timeseries_csv(...)` accepts a condition-level or manifest-level Rg
result, an output path, and the keyword arguments
`include_failed_frames=False` and `overwrite=True`. Its report contains
`output_path`, `passed`, `rows_written`, `condition_count`, `frame_count`,
`skipped_frame_count`, and `issues`.

`validate_rg_timeseries_csv(...)` accepts a CSV path. Its report contains
`csv_path`, `passed`, `row_count`, `valid_row_count`, `invalid_row_count`, and
`issues`. Both reports provide JSON-serializable `to_dict()` output.

Stage 12.3a also exports
`PreprocessingRgReferenceComparisonOptions`,
`PreprocessingRgReferenceComparisonInput`,
`PreprocessingRgReferenceComparisonIssue`,
`PreprocessingRgReferenceComparisonInputValidationResult`, and
`validate_rg_reference_comparison_input(...)`.

Stage 12.3b adds
`PreprocessingRgReferenceComparisonRowResult`,
`PreprocessingRgReferenceComparisonResult`, and
`compare_rg_timeseries_csv(...)`.

Stage 12.4a adds `PreprocessingRgReportBundleIssue`,
`PreprocessingRgReportBundleSummary`, `PreprocessingRgReportBundle`, and
`build_rg_report_bundle(...)`.

## Minimal manifest-level usage

```python
from mania.preprocessing import (
    compute_manifest_rg,
    load_manifest_condition_runtimes,
    load_preprocessing_input_manifest,
    validate_rg_timeseries_csv,
    write_rg_timeseries_csv,
)

manifest = load_preprocessing_input_manifest("preprocessing_manifest.yaml")
load_result = load_manifest_condition_runtimes(manifest, base_dir=".")
rg_result = compute_manifest_rg(load_result)

write_result = write_rg_timeseries_csv(
    rg_result,
    "rg_timeseries.csv",
)

validation_result = validate_rg_timeseries_csv("rg_timeseries.csv")
```

Callers should inspect `load_result.passed`, `rg_result.passed`,
`write_result.passed`, and `validation_result.passed` and review their
structured issues.

The caller must provide the manifest, topology, and trajectory files. This
repository does not contain real MD reference data, and default CI does not
run real-data Rg export.

For a dependency-free demonstration of only the result, writer, and validator
layers, see `examples/preprocessing/rg_export_usage.py`.

## CSV schema

The exact Stage 12.2a header is:

```text
condition_name,frame_index,time_ps,rg_value,rg_unit,frame_passed
```

The fields are:

- `condition_name`: condition name from the manifest and Rg result.
- `frame_index`: zero-based frame index.
- `time_ps`: frame time in picoseconds; empty when time is missing.
- `rg_value`: radius-of-gyration value; empty for a failed frame when that
  frame is included.
- `rg_unit`: unit label, currently `angstrom` by default; empty when missing.
- `frame_passed`: lowercase `true` or `false`.

The CSV contains frame rows only. It does not contain issue JSON,
condition-level issues, or manifest-level issues.

## Failed-frame policy

Passed frames are written by default. With
`include_failed_frames=True`, failed frame rows are included too. Failed rows
may have an empty `rg_value`, and `frame_passed` records whether each included
frame passed.

Condition-level-only and manifest-level-only failures are not converted into
CSV rows. If no frame is writable under the selected policy, writing fails
with a `no_writable_frames` issue instead of creating a successful-looking
CSV.

## CSV validation

`validate_rg_timeseries_csv(...)`:

- validates the exact header;
- validates that every row has six columns;
- validates `condition_name`;
- validates non-negative integer `frame_index` values;
- validates empty or finite non-negative `time_ps` and `rg_value` values;
- validates empty or non-whitespace `rg_unit` values;
- accepts only lowercase `true` and `false` for `frame_passed`;
- validates passed-frame consistency for `rg_value` and `rg_unit`;
- reports non-monotonic frame indexes within each condition;
- allows repeated frame indexes in Stage 12.2b.

The validator reads only and does not mutate CSV files. It does not compute
Rg, load runtime files, or compare reference values.

## Reference comparison

Stage 12.3a defines the paths, options, issue types, and readiness-report shape
for future Rg reference comparison.
`validate_rg_reference_comparison_input(...)` checks that the actual and
reference paths identify distinct existing files. By default it also calls
`validate_rg_timeseries_csv(...)` for each file; callers may set
`validate_csv_contract=False` to perform path and option checks without
reading CSV contents.

Stage 12.3b uses that input contract and its comparison options with
`compare_rg_timeseries_csv(...)`. It matches rows by `condition_name` and
`frame_index` by default, compares `rg_value` with absolute or relative
tolerance, compares present `time_ps` values with absolute tolerance, and
checks exact `rg_unit` consistency when requested. It reports missing or extra
rows, failed-frame rows, numeric and time mismatches, and duplicate row keys
in deterministic JSON-serializable results.

The comparison reads exported CSV files only. It does not recompute Rg,
convert units, load runtime data, discover reference files, or create a report
bundle.

## In-memory report bundle

Stage 12.4a adds `build_rg_report_bundle(...)` for combining existing
computation, CSV write, CSV validation, and optional reference comparison
results. The bundle preserves each nested result through its own `to_dict()`
method and provides a flattened summary for quick display.

The report bundle is dependency-free and JSON-serializable. It does not
compute Rg, write or validate CSV, compare reference files, read runtime data,
or acquire MDAnalysis. It is not a CLI command, workflow runner, or JSON,
Markdown, or HTML report-file writer. Final Rg MVP boundary documentation
before contacts remains Stage 12.4b.

## Local scientific boundary

Stage 12.1d provides an opt-in local scientific Rg computation smoke test.
Stage 12.2d adds an opt-in local scientific export smoke test that verifies
local manifest loading, runtime loading, manifest Rg computation, CSV writing,
and CSV validation through the accepted APIs.

The test writes only under pytest's temporary path and does not commit
generated CSV from local data. It checks export and validation consistency,
not exact numeric Rg values. No local scientific comparison smoke test is part
of Stage 12.3a or Stage 12.3b.

Real MD data must remain outside the repository. Default CI remains
independent from local real data and optional scientific dependencies.

## Not implemented yet

Stage 12.4a does not add:

- new computation logic;
- new writer or validator behavior;
- a report-file writer;
- contacts or graph computation;
- CLI or workflow integration;
- a CI job using real MD data;
- committed real MD data.

Reference comparison remains Stage 12.3 overall: Stage 12.3a defines input
readiness and Stage 12.3b performs numeric-tolerant exported CSV comparison.
Stage 12.4a provides the lightweight in-memory report bundle, while final Rg
MVP boundary documentation remains Stage 12.4b. Contacts and graph work remain
later stages.

## Troubleshooting

- **Missing output directory:** the writer does not create parent
  directories. Create the parent before calling it.
- **Existing output with `overwrite=False`:** writing returns an
  `output_exists` issue and leaves the file unchanged.
- **No writable frames:** passed frames are required by default. Inspect the
  Rg result or explicitly choose `include_failed_frames=True`.
- **Invalid header:** validate a file with the exact six-column header shown
  above.
- **Missing or invalid `rg_value` on a passed frame:** passed rows require a
  present, finite, non-negative value.
- **Missing `rg_unit` on a passed frame:** passed rows require a non-empty unit
  label.
- **MDAnalysis is not installed:** install the optional `md` or `science`
  extra for local loading and computation. Writing and validation alone do not
  require it.
- **Local reference package is unavailable:** provide caller-owned manifest
  and trajectory paths. The repository does not supply real MD data.
