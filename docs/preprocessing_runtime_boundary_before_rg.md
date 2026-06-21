# Preprocessing runtime boundary before Rg

## Purpose

Stage 11 closes the minimal preprocessing runtime boundary needed before real
radius-of-gyration (Rg) work begins. Stage 12.1a adds dependency-free Rg result
and report contracts, Stage 12.1b computes Rg for one already loaded
condition, and Stage 12.1c composes those results across a manifest load
result. Stage 12.1d adds an opt-in local scientific smoke test for that loading
and computation path. Stage 12.2a adds a dependency-free CSV writer for
already computed Rg results, and Stage 12.2b adds dependency-free validation
for those exported CSV files. Stage 12.2c documents and demonstrates that
accepted export chain without adding runtime behavior. Stage 12.2d adds
opt-in local scientific smoke coverage for the full export chain. This
document also records the Stage 12.3a dependency-free reference comparison
input contract and Stage 12.3b numeric-tolerant comparison of exported Rg CSV
files. Stage 12.4a adds a dependency-free in-memory bundle that summarizes
existing Stage 12 results. The remaining limits and local-only testing policy
for scientific runtime behavior stay in force.

## Final Stage 12 Rg MVP boundary

Stage 12.4b closes the Rg MVP documentation boundary before contacts. The
completed Stage 12 scope includes:

- dependency-free frame, condition, manifest, and issue result contracts;
- single-condition Rg computation;
- manifest-level Rg computation;
- an opt-in local scientific Rg computation smoke test;
- the deterministic `rg_timeseries.csv` writer;
- read-only validation for exported Rg CSV files;
- Rg export documentation and synthetic examples;
- an opt-in local scientific Rg export smoke test;
- the reference comparison input and readiness contract;
- numeric-tolerant actual/reference CSV comparison;
- a lightweight in-memory Rg report bundle.

The accepted Stage 12 public API exported by `mania.preprocessing` is:

```python
# Computation
PreprocessingRgComputationIssue
PreprocessingRgFrameResult
PreprocessingConditionRgResult
PreprocessingManifestRgResult
compute_condition_rg(...)
compute_manifest_rg(...)

# Export
PreprocessingRgCsvWriteIssue
PreprocessingRgCsvWriteResult
write_rg_timeseries_csv(...)

# Validation
PreprocessingRgCsvValidationIssue
PreprocessingRgCsvValidationResult
validate_rg_timeseries_csv(...)

# Reference comparison
PreprocessingRgReferenceComparisonOptions
PreprocessingRgReferenceComparisonInput
PreprocessingRgReferenceComparisonIssue
PreprocessingRgReferenceComparisonInputValidationResult
validate_rg_reference_comparison_input(...)
PreprocessingRgReferenceComparisonRowResult
PreprocessingRgReferenceComparisonResult
compare_rg_timeseries_csv(...)

# In-memory report bundle
PreprocessingRgReportBundleIssue
PreprocessingRgReportBundleSummary
PreprocessingRgReportBundle
build_rg_report_bundle(...)
```

The accepted conceptual Python API flow is:

```text
manifest -> load runtimes -> compute Rg -> write rg_timeseries.csv
         -> validate CSV -> compare with reference CSV -> build report bundle
```

This is a conceptual Python API flow, not a CLI command or workflow wrapper.
It does not imply a persistent output directory manager. Callers compose the
existing functions and own their input and output paths.

Stage 12 currently produces in-memory Rg dataclass results,
`rg_timeseries.csv`, a CSV validation report, a reference comparison report,
and an in-memory report bundle. It does not provide a report JSON file writer,
report Markdown writer, report HTML writer, workflow output directory manager,
or Stage 12 CLI command.

## Stage 11 completed capabilities

Stage 11 now provides:

- an optional MDAnalysis dependency boundary;
- runtime input, wrapper, issue, and load-result dataclasses;
- an opt-in local scientific test harness;
- single-condition runtime loading;
- manifest-level condition runtime loading;
- lightweight metadata and provenance reports;
- residue-name extraction from already loaded runtime results.

Default tests still do not require MDAnalysis or real MD data. Real topology,
trajectory, structure, and reference-package data remains local-only and
uncommitted.

## Public API surface

The following names are the Stage 11 public surface exported from
`mania.preprocessing`.

### Optional dependency boundary

```python
get_mdanalysis_status(...)
is_mdanalysis_available(...)
require_mdanalysis(...)
OptionalScientificDependencyStatus
PreprocessingOptionalDependencyError
```

### Runtime and load models

```python
PreprocessingTrajectoryLoadIssue
PreprocessingConditionRuntimeInput
PreprocessingConditionRuntime
PreprocessingConditionLoadResult
```

### Single-condition loading

```python
load_single_condition_runtime(...)
```

### Manifest loading

```python
load_manifest_condition_runtimes(...)
PreprocessingManifestLoadIssue
PreprocessingManifestLoadResult
```

### Metadata and provenance

```python
collect_condition_runtime_metadata(...)
collect_manifest_runtime_metadata(...)
PreprocessingRuntimeMetadataIssue
PreprocessingConditionRuntimeMetadata
PreprocessingManifestRuntimeMetadata
```

### Residue-name extraction

```python
extract_condition_residue_names(...)
extract_manifest_residue_names(...)
PreprocessingResidueNameExtractionIssue
PreprocessingConditionResidueNames
PreprocessingManifestResidueNames
```

### Stage 12.1a Rg result contracts

```python
PreprocessingRgComputationIssue
PreprocessingRgFrameResult
PreprocessingConditionRgResult
PreprocessingManifestRgResult
```

These frozen dataclasses define frame, condition, and manifest report shapes,
deterministic pass/fail summaries, aggregate counts, and JSON-serializable
`to_dict()` output. They do not retain or serialize runtime objects.

### Stage 12.1b single-condition Rg computation

```python
compute_condition_rg(...)
```

`compute_condition_rg(...)` consumes one already loaded
`PreprocessingConditionLoadResult`, iterates its runtime trajectory only for
Rg, uses the loaded runtime's primary atom group, and returns a
`PreprocessingConditionRgResult`. The unit field labels the coordinate unit
used by the loaded runtime; no unit conversion is performed.

### Stage 12.1c manifest Rg computation

```python
compute_manifest_rg(...)
```

`compute_manifest_rg(...)` consumes a `PreprocessingManifestLoadResult`,
calls `compute_condition_rg(...)` once for each condition in source order,
preserves partial failures and manifest load issues, and returns a
`PreprocessingManifestRgResult`. The manifest layer does not directly inspect
runtime objects.

### Stage 12.2a Rg CSV writer

```python
write_rg_timeseries_csv(...)
PreprocessingRgCsvWriteIssue
PreprocessingRgCsvWriteResult
```

The `rg_timeseries.csv` writer consumes existing condition-level or
manifest-level Rg results and writes deterministic frame rows in their
existing condition and frame order. It does not compute Rg, load files, or
acquire MDAnalysis dependencies.

Failed frame rows are skipped by default and may be included explicitly.
Expanded docs and examples remain Stage 12.2c, and the local scientific export
smoke test remains Stage 12.2d. Reference comparison remains Stage 12.3.
Contacts and graph generation remain future stages.

### Stage 12.2b Rg CSV validation

```python
validate_rg_timeseries_csv(...)
PreprocessingRgCsvValidationIssue
PreprocessingRgCsvValidationResult
```

The validator reads an already exported `rg_timeseries.csv` without modifying
it. It checks the exact Stage 12.2a header, row shape, numeric fields,
`frame_passed` values, passed-frame value and unit consistency, and
non-monotonic frame indexes within each condition.

Validation does not compute Rg, write files, load runtime files, acquire
MDAnalysis, or compare reference values. Local scientific export smoke
coverage remains Stage 12.2d, and reference comparison remains Stage 12.3.
Contacts and graph generation remain future stages.

### Stage 12.2c Rg export docs and examples

`docs/preprocessing_rg_export.md` documents the accepted manifest loading,
manifest Rg computation, CSV writing, and CSV validation chain.
`examples/preprocessing/rg_export_usage.py` demonstrates the writer and
validator with synthetic result objects, and
`examples/preprocessing/rg_timeseries.example.csv` shows the exact schema.

The synthetic examples require neither MDAnalysis nor real data. Stage 12.2c
adds no runtime behavior. Reference comparison remains Stage 12.3, and the
report bundle remains Stage 12.4. Contacts and graph generation remain future
stages.

### Stage 12.2d local scientific Rg export smoke test

The opt-in local scientific export smoke test uses an explicitly configured
local reference package to load a manifest and condition runtimes, compute
manifest-level Rg, write `rg_timeseries.csv` under pytest's temporary path,
and validate the exported file.

It checks report serialization, the exact CSV header, row-count consistency,
known condition names, and valid lowercase `frame_passed` values without exact
numeric Rg comparison. Default CI remains independent from MDAnalysis and
local real data. Reference comparison remains Stage 12.3, the report bundle
remains Stage 12.4, and contacts and graph generation remain future stages.

### Stage 12.3a Rg reference comparison input contract

```python
PreprocessingRgReferenceComparisonOptions
PreprocessingRgReferenceComparisonInput
PreprocessingRgReferenceComparisonIssue
PreprocessingRgReferenceComparisonInputValidationResult
validate_rg_reference_comparison_input(...)
```

The dependency-free contract records actual and reference CSV paths and future
comparison options. Input validation checks path readiness and can reuse
`validate_rg_timeseries_csv(...)` for each file. It does not compute
differences or compare Rg values, time values, or row counts. Numeric
comparison remains Stage 12.3b, and report bundle work remains Stage 12.4.
Contacts and graph generation remain future stages.

### Stage 12.3b numeric-tolerant Rg CSV comparison

```python
PreprocessingRgReferenceComparisonRowResult
PreprocessingRgReferenceComparisonResult
compare_rg_timeseries_csv(...)
```

The dependency-free comparison consumes the Stage 12.3a input contract, reads
the two exported CSV files, matches deterministic frame keys, and compares Rg
and time values with configured tolerances. It checks units according to the
options and reports missing, extra, duplicate, failed, or differing rows.

This layer compares exported CSVs only. It does not recompute Rg, load runtime
data, or acquire MDAnalysis. The report bundle remains Stage 12.4, and
contacts and graph generation remain future stages.

### Stage 12.4a lightweight in-memory Rg report bundle

```python
PreprocessingRgReportBundleIssue
PreprocessingRgReportBundleSummary
PreprocessingRgReportBundle
build_rg_report_bundle(...)
```

The dependency-free bundle summarizes existing computation, write,
validation, and optional comparison result objects. It preserves their nested
dictionary reports and adds a flattened status and count summary without
performing any scientific or file operation.

Stage 12.4a does not add contacts, graph generation, report-file output, CLI
commands, or workflow integration. Stage 12.4b closes the final Rg MVP
boundary documentation before contacts.

## Runtime object boundary

Runtime objects are intentionally opaque. Loaders may create and retain a
runtime object inside `PreprocessingConditionRuntime`, but `to_dict()` reports
do not expose it. Runtime objects are not serialized.

Stage 11 reports expose structured paths, statuses, issues, metadata, and
residue-name results rather than raw runtime objects in JSON. Downstream
reports must preserve this non-serialization boundary.

The metadata and residue-name layers are separate:

- `collect_manifest_runtime_metadata(...)` may collect only lightweight
  count-style metadata from already loaded results;
- `extract_manifest_residue_names(...)` may read residue names only through
  `runtime_object.residues.resnames`.

Stage 11 does not expose trajectory frames or frame coordinates and does not
provide atom selections.

## Local scientific testing boundary

The opt-in tests live under `tests/local_scientific` and use these markers:

- `local_scientific`;
- `requires_mdanalysis`;
- `requires_real_md_data`.

The local controls are:

- `MANIA_RUN_LOCAL_SCIENTIFIC`, which explicitly enables local scientific
  tests;
- `MANIA_LOCAL_REFERENCE_PACKAGE`, which points to an optional local reference
  package.

Expected commands are:

```bash
pytest
```

```bash
pytest tests/local_scientific
```

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 pytest tests/local_scientific
```

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 \
MANIA_LOCAL_REFERENCE_PACKAGE=/path/to/local/package \
pytest tests/local_scientific
```

Plain `pytest` does not require local scientific data. Default CI must not
enable the local scientific tests. Local runs may pass or skip depending on
MDAnalysis and local-data availability.

The local scientific suite covers single-condition loading, manifest loading,
metadata, residue names, manifest-level Rg computation, and Rg CSV export and
validation. The local scientific Rg computation smoke test checks report shape
and basic finite, non-negative scientific sanity. The local scientific Rg
export smoke test writes generated output only into a pytest temporary
directory and validates it without exact numeric reference comparison.

Both Rg smoke tests require `MANIA_RUN_LOCAL_SCIENTIFIC=1`, optional
MDAnalysis setup, and `MANIA_LOCAL_REFERENCE_PACKAGE`. Local scientific tests
are skipped by default. No real MD data or generated local-data CSV is
committed.

Default CI does not require MDAnalysis. Default CI does not require real MD data
and does not run the local scientific tests as real-data tests. The default
suite uses fake, synthetic, and unit-level coverage for Rg contracts,
computation boundaries, the writer, validator, comparison, and report bundle.
MDAnalysis remains optional.

## What is explicitly not implemented before Rg computation

Stage 12.4a does not implement:

- an Rg report-file writer;
- contacts computation or contacts-per-frame output;
- contacts export or validation;
- aggregate contact edge output;
- graph export from real preprocessing;
- graph diagnostics from real preprocessing outputs;
- graph JSON, node, or edge output from real runtime results;
- a real preprocessing workflow runner;
- CLI integration or workflow integration for real scientific preprocessing;
- a persistent workflow output directory manager;
- automatic reference package discovery;
- automatic residue QC from loaded topology;
- configurable atom selections;
- unit conversion between nanometers and angstroms;
- frame iteration outside one-condition Rg computation;
- coordinate or position extraction;
- notebook parity guarantees beyond exported CSV comparison support;
- reference notebook comparison for real Rg, contacts, or graph outputs;
- scientific workload performance optimization;
- a broad trajectory preprocessing pipeline;
- a CI job with real MD data.

Contacts and graph export remain future work after the Rg stage. These items
are non-goals for the Stage 12.4a in-memory report bundle.

## Stage 12.1d local scientific boundary

Manifest-level Rg computation now composes the accepted single-condition
function over ordered load results. It preserves failed and partial condition
reports and maps manifest load issues without directly inspecting runtime
objects.

The Stage 12.1d smoke test validates the accepted manifest loading and Rg
computation chain against explicitly configured local data. It remains opt-in,
uses the existing optional MDAnalysis boundary, and does not make real data a
default CI requirement.

The dependency-free CSV writer is now available for existing Rg result
objects, and dependency-free validation is available for its exported files.
The Rg export guide and synthetic examples now document that chain without
changing runtime behavior. The opt-in local scientific export smoke test now
checks the complete accepted chain on explicitly configured local data. The
Stage 12.3a reference comparison input contract validates comparison
readiness, and Stage 12.3b now performs dependency-free numeric-tolerant
comparison of exported CSV files without runtime loading or Rg recomputation.
Stage 12.4a now summarizes existing Stage 12 results in a lightweight
in-memory bundle. Stage 12.4b closes the final boundary documentation, and
contacts and graph generation remain future stages after Rg.

## Stage 12 handoff

The completed Stage 12 Rg MVP builds on:

```python
PreprocessingManifestLoadResult
PreprocessingConditionLoadResult
PreprocessingManifestRuntimeMetadata
PreprocessingManifestResidueNames
```

It may also compose the optional MDAnalysis boundary, loaded runtime objects
from Stage 11.4 and Stage 11.5, local manifest package behavior, and the local
scientific harness.

Rg computation lives in Rg-specific preprocessing modules. Rg export,
validation, comparison, and report construction also remain in Rg-specific
modules. Contacts must not be mixed into those Stage 12 modules.

Stage 13 should start a contacts extraction MVP in separate contacts-specific
modules. The recommended ordering is:

1. Define contact options and output contracts.
2. Add a minimal per-frame contacts extraction boundary.
3. Add contacts export, validation, and comparison.
4. Integrate graph work only after contacts are stable.

Graph export remains a later stage after contacts. Stage 13 should begin with
contract-only or minimal extraction boundaries rather than a broad workflow.

## Safe composition rules for Stage 12

Stage 12 should:

1. Accept existing Stage 11 load results instead of duplicating loaders.
2. Keep MDAnalysis optional and acquire it only through the existing boundary.
3. Preserve runtime-object opacity in serialized reports.
4. Keep real-data tests under the opt-in local scientific harness.
5. Preserve manifest condition order and partial-failure reporting.
6. Reuse metadata and residue-name reports as separate inputs when needed.
7. Keep Rg output focused on the accepted backend contract.
8. Leave contacts, graph export, workflow integration, and broad CLI
   integration for explicit later stages.
