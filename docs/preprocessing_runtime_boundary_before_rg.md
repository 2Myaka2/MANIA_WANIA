# Preprocessing runtime boundary before Rg

## Purpose

Stage 11 closes the minimal preprocessing runtime boundary needed before real
radius-of-gyration (Rg) work begins. Stage 12.1a adds dependency-free Rg result
and report contracts, Stage 12.1b computes Rg for one already loaded
condition, and Stage 12.1c composes those results across a manifest load
result. This document records the capabilities that later Stage 12 work may
compose, the limits that remain in force, and the local-only testing policy
for scientific runtime behavior.

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
metadata, and residue names. Real MD data must remain uncommitted.

## What is explicitly not implemented before Rg computation

Stage 12.1c does not implement:

- local scientific Rg smoke coverage;
- `rg_timeseries.csv` export;
- contacts computation or contacts-per-frame output;
- aggregate contact edge output;
- graph export from real preprocessing;
- graph JSON, node, or edge output from real runtime results;
- a real preprocessing workflow runner;
- CLI integration or workflow integration for real scientific preprocessing;
- automatic residue QC from loaded topology;
- atom selections;
- frame iteration outside one-condition Rg computation;
- coordinate or position extraction;
- notebook parity checks for real Rg, contacts, or graph outputs;
- reference notebook comparison for real Rg, contacts, or graph outputs;
- scientific workload performance optimization;
- a CI job with real MD data.

Contacts and graph export remain future work after the Rg stage. These items
are non-goals for the Stage 12.1c computation.

## Stage 12.1c computation boundary

Manifest-level Rg computation now composes the accepted single-condition
function over ordered load results. It preserves failed and partial condition
reports and maps manifest load issues without directly inspecting runtime
objects. It does not load files or acquire MDAnalysis dependencies.

The local scientific Rg smoke test remains Stage 12.1d. CSV export remains
Stage 12.2, reference comparison remains Stage 12.3, and the lightweight
report bundle remains Stage 12.4. Contacts and graph generation remain future
stages after Rg.

## Stage 12 handoff

Stage 12 may build on:

```python
PreprocessingManifestLoadResult
PreprocessingConditionLoadResult
PreprocessingManifestRuntimeMetadata
PreprocessingManifestResidueNames
```

It may also compose the optional MDAnalysis boundary, loaded runtime objects
from Stage 11.4 and Stage 11.5, local manifest package behavior, and the local
scientific harness.

Stage 12 should begin with a real Rg preprocessing MVP. Its recommended scope
is:

- compute Rg per frame;
- export `rg_timeseries.csv` in the backend contract format;
- compare with notebook or reference outputs where possible;
- validate and compare Rg outputs, with lightweight reporting if needed.

Unless separately scoped, Stage 12 should still avoid contacts, graph export,
the full workflow MVP, broad CLI integration, and any CI job with real MD
data.

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
