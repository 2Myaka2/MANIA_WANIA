# Preprocessing before trajectory parsing

## Purpose

This document summarizes the implemented preprocessing boundary before
topology and trajectory parsing begins.

Stages 8 through 10 provide lightweight contracts, local path checks,
residue-library loading and validation, and residue QC for explicit residue
names. Stages 11.1 through 11.3 add the optional runtime boundary, runtime
value models, and local-only test harness. Stage 11.4 adds the first loader for
one already-prepared condition, Stage 11.5 composes it across a manifest, and
Stage 11.6 reports lightweight metadata from loaded results. Stage 11.7 adds
minimal residue-name extraction from those loaded results. Stage 11.8 closes
the runtime boundary before Rg; see
`docs/preprocessing_runtime_boundary_before_rg.md`. Stage 12.1a adds only the
dependency-free Rg result/report contract. Stage 12.1b adds Rg computation for
one already loaded condition, and Stage 12.1c composes condition Rg results
across a manifest load result. Stage 12.1d adds an opt-in local scientific
smoke test for the loading and manifest Rg computation chain. Stage 12.2a adds
a dependency-free `rg_timeseries.csv` writer for existing condition-level and
manifest-level Rg results. Stage 12.2b adds dependency-free validation for
already exported Rg CSV files. Stage 12.2c adds Rg export documentation and
synthetic examples without changing runtime behavior. Stage 12.2d adds
opt-in local scientific smoke coverage for Rg CSV export and validation. Stage
12.3a adds the dependency-free Rg reference comparison input contract and
readiness validation. Stage 12.3b adds dependency-free numeric-tolerant
comparison of exported actual and reference Rg CSV files. Stage 12.4a adds a
dependency-free in-memory bundle for existing Stage 12 result objects. Final
Rg MVP boundary documentation is completed by Stage 12.4b. Stage 12 Rg MVP is
complete. Stage 13 contacts begins with a dependency-free MVP definition and
options contract in separate contacts-specific modules. Stage 13.1b adds the
dependency-free contact result dataclasses and report shape. Stage 13.2a adds
single-condition residue contacts extraction from already loaded runtimes.
Stage 13.2b composes contact computation across manifest load results. Stage
13.2c adds opt-in local scientific smoke coverage for contacts computation.
Stage 13.3a adds dependency-free `contacts_perframe.csv` writing for existing
contacts results.

## Current implemented capabilities

The current preprocessing layer supports:

- a typed preprocessing manifest contract;
- committed placeholder manifest examples;
- explicit local manifest path validation;
- a local reference package sanity checker;
- a bridge from manifest residue-library options to the existing loader and
  custom-residue extension behavior;
- report-based local residue-library format validation;
- residue QC for residue names provided explicitly by the caller;
- safe MDAnalysis availability, status, and lazy-require helpers;
- file-agnostic runtime input, runtime wrapper, load issue, and load result
  dataclasses;
- single-condition topology and trajectory loading through
  `load_single_condition_runtime(...)`;
- manifest-wide condition loading through
  `load_manifest_condition_runtimes(...)`;
- lightweight runtime metadata reports through
  `collect_condition_runtime_metadata(...)` and
  `collect_manifest_runtime_metadata(...)`;
- ordered residue-name extraction through
  `extract_condition_residue_names(...)` and
  `extract_manifest_residue_names(...)`;
- frozen frame, condition, manifest, and issue contracts for future Rg
  computation;
- single-condition Rg computation through `compute_condition_rg(...)`;
- manifest-level Rg computation through `compute_manifest_rg(...)`;
- opt-in local scientific smoke coverage for manifest-level Rg computation;
- deterministic Rg CSV writing through `write_rg_timeseries_csv(...)`;
- read-only Rg CSV validation through `validate_rg_timeseries_csv(...)`;
- Rg export documentation and dependency-free synthetic examples;
- opt-in local scientific Rg export smoke coverage;
- Rg reference comparison input and option contracts through
  `PreprocessingRgReferenceComparisonInput` and
  `PreprocessingRgReferenceComparisonOptions`;
- comparison readiness validation through
  `validate_rg_reference_comparison_input(...)`;
- numeric-tolerant exported Rg CSV comparison through
  `compare_rg_timeseries_csv(...)`;
- lightweight in-memory Rg result bundling through
  `build_rg_report_bundle(...)`;
- dependency-free Stage 13 contact definition and detection option contracts
  through `PreprocessingContactDefinition` and
  `PreprocessingContactDetectionOptions`;
- dependency-free Stage 13 contact issue, pair, frame, condition, and manifest
  result contracts;
- single-condition residue contacts extraction through
  `compute_condition_contacts(...)`;
- manifest-level contacts aggregation through
  `compute_manifest_contacts(...)`;
- opt-in local scientific contacts computation smoke coverage;
- dependency-free contacts per-frame CSV writing through
  `write_contacts_perframe_csv(...)`.

The main public APIs currently exported from `mania.preprocessing` are:

```python
load_preprocessing_input_manifest(...)
validate_preprocessing_manifest_paths(...)
check_preprocessing_reference_package(...)
load_residue_library_from_manifest_options(...)
resolve_residue_library_manifest_paths(...)
validate_residue_library_from_manifest_options(...)
run_residue_qc_from_manifest_options(...)
get_mdanalysis_status(...)
is_mdanalysis_available(...)
require_mdanalysis(...)
load_single_condition_runtime(...)
load_manifest_condition_runtimes(...)
collect_condition_runtime_metadata(...)
collect_manifest_runtime_metadata(...)
extract_condition_residue_names(...)
extract_manifest_residue_names(...)
compute_condition_contacts(...)
compute_manifest_contacts(...)
write_contacts_perframe_csv(...)
```

These APIs cover contracts, local filesystem checks, residue-library files,
explicit residue-name QC, and condition runtime loading.

## Stage 11.1 optional runtime boundary

Stage 11.1 provides a small optional dependency boundary for `MDAnalysis`:

- `get_mdanalysis_status(...)` reports deterministic availability and version
  information when safely available;
- `is_mdanalysis_available(...)` checks availability without importing
  `MDAnalysis` at module import time;
- `require_mdanalysis(...)` lazily imports `MDAnalysis` or raises a clear
  project-specific optional dependency error.

The default/core install and imports such as `import mania.preprocessing`
remain valid without `MDAnalysis`. Future Stage 11 loading code should call
`require_mdanalysis(...)` when it actually needs the optional runtime.

The helper itself does not load topology or trajectory files or create an
MDAnalysis Universe/session object. Stage 11.4 uses it only after declared
paths pass lightweight filesystem validation.

## Stage 11.2 runtime result models

Stage 11.2 defines safe value and report models for future condition loading:

- `PreprocessingConditionRuntimeInput` stores condition paths and can resolve
  relative manifest paths against an explicitly supplied `base_dir`;
- `PreprocessingConditionRuntime` can wrap a future scientific runtime object;
- `PreprocessingTrajectoryLoadIssue` defines deterministic future issue kinds;
- `PreprocessingConditionLoadResult` summarizes future load status, issues,
  inputs, and runtime metadata.

These dataclasses do not check or read files, call
`require_mdanalysis(...)`, load topology or trajectory data, or create an
MDAnalysis Universe/session object. Runtime objects are retained only on the
runtime wrapper and are excluded from `to_dict()` output.

Runtime objects remain opaque to serialization. Stage 11.6 can inspect only
safe count-style runtime interfaces after loading.

## Stage 11.3 local scientific test harness

Stage 11.3 provides opt-in test infrastructure under `tests/local_scientific`.
The registered markers are `local_scientific`, `requires_mdanalysis`, and
`requires_real_md_data`.

Local tests are skipped by default. Set `MANIA_RUN_LOCAL_SCIENTIFIC=1` to
enable them. Tests requiring local real data also use
`MANIA_LOCAL_REFERENCE_PACKAGE`; tests requiring MDAnalysis skip when the
optional runtime is unavailable.

The harness includes marker smoke tests and opt-in Stage 11.4 through 11.7
checks for single-condition loading, manifest loading, metadata, and residue
names. Default test runs still skip all tests in this directory.

## Stage 11.4 single-condition loading

`load_single_condition_runtime(...)` accepts one
`PreprocessingConditionRuntimeInput` and returns a
`PreprocessingConditionLoadResult`.

The loader validates the declared topology and trajectory paths before calling
`require_mdanalysis(...)`. Missing paths, non-file paths, a missing optional
runtime, and expected Universe constructor failures are returned as
deterministic load issues instead of escaping as expected local errors.

On success, exactly one Universe/session object is wrapped in
`PreprocessingConditionRuntime`. The runtime object remains excluded from
`to_dict()` output. The loader does not inspect runtime internals, collect
metadata or provenance, extract residue names, iterate frames, select atoms,
or compute Rg or contacts.

## Stage 11.5 manifest condition loading

`load_manifest_condition_runtimes(...)` accepts a
`PreprocessingInputManifest` and returns a
`PreprocessingManifestLoadResult`. It iterates in manifest order, converts each
condition through
`PreprocessingConditionRuntimeInput.from_manifest_condition(...)`, and calls
`load_single_condition_runtime(...)` for each condition.

All returned `PreprocessingConditionLoadResult` values are preserved.
A normal failure for one condition does not stop later conditions and is not
duplicated as a manifest-level issue. Manifest-level issues are reserved for
unexpected conversion or wrapper-call failures.

The aggregate result serializes through the existing per-condition
`to_dict()` boundary, so runtime objects remain opaque and are not serialized.

## Stage 11.6 runtime metadata

`collect_condition_runtime_metadata(...)` and
`collect_manifest_runtime_metadata(...)` consume already loaded condition and
manifest results. Reports preserve condition names, load status, declared
paths, runtime type, and lightweight atom, residue, segment, and frame counts
when those count-style interfaces are safely available.

The metadata layer does not load files, acquire MDAnalysis, or call either
loader. Runtime objects are never serialized. Collection does not extract
residue names, iterate frames, access coordinates or positions, or perform
atom selections.

## Stage 11.7 residue-name extraction

`extract_condition_residue_names(...)` and
`extract_manifest_residue_names(...)` consume already loaded results and read
only `runtime_object.residues.resnames`. Accepted values are converted with
`str(value).strip()`, preserve case and source order, and produce deterministic
first-seen unique names. `None` and empty stripped values are excluded and
reported as invalid.

The extraction layer does not serialize runtime objects, load files, acquire
MDAnalysis, call loaders or metadata collectors, or run residue QC. It does
not access atoms, iterate frames, or access coordinates or positions. Rg,
contacts, and graph export remain future work.

## Stage 12.1a Rg result contract

Stage 12.1a defines `PreprocessingRgComputationIssue`,
`PreprocessingRgFrameResult`, `PreprocessingConditionRgResult`, and
`PreprocessingManifestRgResult`. These dependency-free dataclasses provide
validated numeric fields, property-based pass/fail semantics, deterministic
aggregates, path serialization, and JSON-serializable reports without runtime
objects.

Stage 12.1a does not compute Rg, iterate frames, access MDAnalysis runtime
objects, export CSV, compare reference results, build report bundles, compute
contacts, or generate graphs. Actual Rg computation begins in Stage 12.1b.

## Stage 12.1b single-condition Rg computation

`compute_condition_rg(...)` consumes one existing
`PreprocessingConditionLoadResult` and returns a
`PreprocessingConditionRgResult`. It uses the loaded runtime's primary atom
group and iterates that condition's trajectory to compute one Rg value per
visited frame. It does not load files or acquire MDAnalysis itself.

Manifest-level Rg remains Stage 12.1c. Local scientific Rg coverage remains
Stage 12.1d, CSV export remains Stage 12.2, and reference comparison remains
Stage 12.3. Configurable atom selections, contacts, graph generation,
workflow integration, and CLI integration remain future work.

## Stage 12.1c manifest Rg computation

`compute_manifest_rg(...)` consumes one `PreprocessingManifestLoadResult`,
calls `compute_condition_rg(...)` for every condition result in order, and
returns a `PreprocessingManifestRgResult`. Failed and partial condition
results are retained, and manifest-level load issues are mapped into the Rg
report. The manifest function does not directly inspect runtime objects.

CSV export remains Stage 12.2, and reference comparison remains Stage 12.3.
Report bundles, contacts, graph generation, workflow integration, and CLI
integration remain future work.

## Stage 12.1d local scientific Rg smoke test

The opt-in local scientific suite now loads a configured local manifest, loads
its condition runtimes, and computes manifest-level Rg. The smoke test checks
the report shape, JSON serialization, deterministic frame indexes, and finite
non-negative Rg values without asserting exact numeric references.

The test requires the existing optional MDAnalysis runtime and local real data.
It remains skipped by default and outside default CI. Local scientific export
smoke coverage, reference comparison, contacts, and graph generation remain
future work.

## Stage 12.2a Rg CSV writer

`write_rg_timeseries_csv(...)` consumes already computed
`PreprocessingConditionRgResult` or `PreprocessingManifestRgResult` objects.
It writes deterministic frame rows without loading files, recomputing Rg, or
acquiring MDAnalysis.

The accepted export chain is documented in
`docs/preprocessing_rg_export.md`, with synthetic examples under
`examples/preprocessing` and opt-in local scientific export smoke coverage
under `tests/local_scientific`. Reference comparison remains Stage 12.3.
Contacts, graph generation, workflow integration, and CLI integration remain
future work.

## Stage 12.2b Rg CSV validation

`validate_rg_timeseries_csv(...)` reads existing Rg CSV files and validates
their exact header, row shapes, fields, passed-frame consistency, and
per-condition frame ordering. It uses only standard-library CSV parsing and
does not write files, compute Rg, or load scientific runtimes.

Stage 12.2c documents validation as the final step in the accepted export
chain. Stage 12.2d exercises that chain on explicitly configured local data.
Stage 12.3a now defines reference comparison inputs and validates their paths
and optional CSV contracts. It does not compare values, times, or row counts.
Numeric comparison remains Stage 12.3b, and report bundle work remains Stage
12.4.

## Stage 12.2c Rg export docs and examples

The Rg export guide shows the Python API flow from manifest loading through
CSV validation. The examples are synthetic, do not load trajectories, and do
not require MDAnalysis or local reference data. Stage 12.2c adds no source
runtime behavior or public API.

## Stage 12.2d local scientific Rg export smoke test

The opt-in local scientific suite now covers manifest loading, runtime
loading, Rg computation, temporary CSV writing, and CSV validation. It checks
the accepted export chain without exact numeric reference comparison and does
not commit generated local-data output. Comparison, reporting, contacts, and
graph work remain future stages.

## Stage 12.3a Rg reference comparison input contract

The dependency-free input contract stores actual and reference CSV paths,
future comparison options, and structured validation issues. Its validator
checks path readiness and may call the existing Rg CSV validator for each
file. It does not compare Rg values, time values, or row counts. Numeric
comparison remains Stage 12.3b, and report bundle work remains Stage 12.4.

## Stage 12.3b numeric-tolerant Rg CSV comparison

`compare_rg_timeseries_csv(...)` consumes the Stage 12.3a input contract and
compares exported actual and reference CSV rows without loading trajectories
or recomputing Rg. It applies absolute and relative Rg tolerances, absolute
time tolerance, optional exact unit matching, deterministic key matching, and
missing, extra, duplicate, or failed-row reporting.

The comparison uses only the standard library and returns deterministic
JSON-serializable row and whole-file results. Contacts and graph generation
remain future stages.

## Stage 12.4a lightweight in-memory Rg report bundle

`build_rg_report_bundle(...)` accepts existing computation, CSV write, CSV
validation, and optional comparison results. It preserves nested
JSON-serializable reports and provides a flattened summary without reading or
writing files, recomputing Rg, validating CSV, or comparing references.

The bundle does not add a report-file writer, CLI command, workflow runner,
contacts, or graph generation. Stage 12.4b completes the final Rg MVP
boundary documentation.

## Stage 12.4b final Rg MVP boundary

Stage 12 now supports Rg result contracts, condition and manifest computation,
`rg_timeseries.csv` writing and validation, export documentation and examples,
numeric-tolerant reference comparison, and an in-memory report bundle. Its
local scientific coverage includes opt-in Rg computation and export smoke
tests; default CI remains independent from MDAnalysis and real MD data.

The conceptual Python API flow is:

```text
manifest -> load runtimes -> compute Rg -> write rg_timeseries.csv
         -> validate CSV -> compare with reference CSV -> build report bundle
```

This is not a CLI command, workflow wrapper, or persistent output directory
manager. Supported outputs are in-memory Rg dataclass results,
`rg_timeseries.csv`, a CSV validation report, a reference comparison report,
and an in-memory report bundle. No JSON, Markdown, or HTML report file writer
is part of Stage 12.

## Stage 13.1a contacts definition and options contract

Stage 12 Rg MVP is complete. Stage 13 contacts begins with the dependency-free
MVP definition and options contract documented in
`docs/preprocessing_contacts_mvp.md`.

`PreprocessingContactDefinition` records the residue-level, per-frame,
distinct-residue-pair definition. `PreprocessingContactDetectionOptions`
records validated detection settings. No contacts computation was implemented
by Stage 13.1; Stage 13.2a now provides the first single-condition computation.
No contacts export existed in Stage 13.1, and no graph export exists yet.

Contacts use contacts-specific modules rather than the Stage 12 Rg
computation, export, validation, comparison, or report modules. Contact result
dataclasses were deferred to Stage 13.1b, followed by computation in Stage
13.2a.

## Stage 13.1b contacts result contracts

The contact result dataclasses and report shape now exist for issues,
residue-residue pairs, frames, conditions, and manifests. They provide strict
constructor validation, deterministic summary counts, and JSON-safe nested
serialization.

Stage 13.1b itself performs no distance calculation. Stage 13.2a now consumes
these contracts for single-condition extraction. CSV export remains future
Stage 13.3 work, and graph export remains after the contacts MVP is stable.

## Stage 13.2a single-condition contacts extraction

`compute_condition_contacts(...)` accepts one
`PreprocessingConditionLoadResult` and
`PreprocessingContactDetectionOptions`, then returns a
`PreprocessingConditionContactsResult`. It uses the existing runtime object,
iterates frames in order, and computes residue-level contacts from the minimum
selected atom distance. The default filter excludes hydrogens; the `all`
filter includes all atoms with usable positions, and `skip_resnames` is
respected.

The function does not load files, call manifest loaders, or acquire
MDAnalysis. Coordinates are assumed to match the configured unit label and no
unit conversion is performed. Default CI covers the duck-typed runtime
boundary with fake objects and no real MD data.

Opt-in local scientific contacts smoke coverage exists in Stage 13.2c. The
per-frame contacts CSV writer begins in Stage 13.3a. Contacts aggregate export,
validation, comparison, and reporting remain later stages. No graph export is
part of Stage 13.2a.

## Stage 13.2b manifest contacts aggregation

`compute_manifest_contacts(...)` consumes one
`PreprocessingManifestLoadResult`, calls `compute_condition_contacts(...)` for
every condition result in order, and returns a
`PreprocessingManifestContactsResult`. Failed and partial condition results are
retained, manifest-level load issues are mapped into the contact report, and
unexpected condition-computation exceptions become deterministic failed
condition results.

The manifest function does not inspect runtime objects, load files, call
runtime loaders, acquire MDAnalysis, add contact distance logic, export CSV,
compare references, run local scientific smoke tests, or add graph semantics.

## Stage 13.2c local contacts computation smoke test

The opt-in local scientific suite now loads a configured local manifest, loads
its condition runtimes, and computes manifest-level contacts. The smoke test
checks result shape, nested JSON serialization, and basic nonnegative count
sanity without asserting exact contact counts.

The test requires the existing optional MDAnalysis runtime and local real data.
It remains skipped by default and outside default CI. Contacts export begins
with the Stage 13.3a per-frame writer, while graph export remains future work.

## Stage 13.3a contacts per-frame CSV writer

`write_contacts_perframe_csv(...)` consumes existing condition-level or
manifest-level contacts results and writes deterministic `contacts_perframe.csv`
rows. It writes one row per detected contact pair per frame and does not
recompute contacts, load runtimes, acquire MDAnalysis, validate CSV, compare
references, or create graph outputs.

The aggregate `contact_edges.csv` writer remains future Stage 13.3b work.
Contacts CSV validation and comparison remain future stages, and graph export
remains future work.

## Stage 11.8 runtime boundary before Rg

Stage 11.8 documents the completed Stage 11 public API, opaque runtime-object
boundary, local scientific test controls, explicit pre-Rg non-goals, and Stage
12 composition rules. The canonical handoff is
`docs/preprocessing_runtime_boundary_before_rg.md`.

Stage 11.8 adds documentation and boundary tests only. Rg, contacts, graph
export, CLI integration, and workflow integration remain future work.

## Explicit residue-name boundary

Stage 10.3 can run residue QC only for explicit residue names supplied directly
by the caller.

Stage 10 does not know how to obtain topology/trajectory-derived residue names.
It does not inspect `.tpr`, `.xtc`, `.pdb`, `.gro`, or other scientific
structure or trajectory files.

`skip_resnames` can be applied to explicit residue names before the existing
residue QC runs. It is not yet applied to topology/trajectory-derived residue
lists because residue extraction from topology/trajectory is not implemented
before Stage 11.

## What is not implemented yet

The following capabilities are not implemented:

- topology loading beyond declared manifest condition inputs;
- trajectory loading beyond declared manifest condition inputs;
- GROMACS runtime integration;
- residue QC from loaded topology;
- frame iteration beyond single-condition Rg and contacts computation;
- configurable atom or residue selection beyond the contacts heavy/all MVP;
- coordinate or position access outside existing loaded runtime objects;
- report file writing or persistent output directory management;
- automatic reference package discovery;
- unit conversion between `nm` and `angstrom`;
- notebook parity guarantees beyond CSV comparison support;
- performance optimization for large trajectories;
- a broad trajectory preprocessing pipeline;
- aggregate contact-edge export;
- contacts CSV validation and comparison;
- graph export from real preprocessing;
- graph diagnostics from real preprocessing outputs;
- CLI or workflow integration for real preprocessing.

## Why trajectory parsing comes next

Stage 11.4 begins minimal topology and trajectory loading because later
scientific preprocessing stages depend on information that Stage 10 cannot
provide:

- residue names from real topology or trajectory inputs;
- frame count and frame times;
- atom selections;
- positions and coordinates;
- inputs for Rg computation;
- inputs for contacts extraction;
- inputs for graph export from real preprocessing.

Starting with contacts or Rg before establishing this loading boundary would
leave the scientific calculations without a defined runtime input.

## Safe API usage today

Load a preprocessing manifest and check its declared local paths:

```python
from mania.preprocessing import (
    load_preprocessing_input_manifest,
    validate_preprocessing_manifest_paths,
)

manifest = load_preprocessing_input_manifest("preprocessing_manifest.yaml")
path_report = validate_preprocessing_manifest_paths(manifest, base_dir=".")
```

Validate residue-library options using existing loader and extension behavior:

```python
from mania.preprocessing import validate_residue_library_from_manifest_options

report = validate_residue_library_from_manifest_options(
    manifest.residue_library,
    base_dir=".",
)
```

Run residue QC with residue names supplied explicitly by the caller:

```python
from mania.preprocessing import run_residue_qc_from_manifest_options

qc_report = run_residue_qc_from_manifest_options(
    manifest.residue_library,
    ["ALA", "GLY", "SOD"],
    base_dir=".",
)
```

These examples do not parse topology or trajectory files and do not require
`MDAnalysis`.

## Local/reference data policy

- Real topology, trajectory, and reference-structure files remain local-only.
- Full real residue libraries remain local/reference inputs.
- Real MD data must not be committed to the repository.
- `data/reference/...` remains local and uncommitted unless a future explicit
  task changes that policy.
- Default CI must not require real MD data or a local reference package.

## Relationship to optional scientific dependencies

The `md` and `science` extras exist for future opt-in scientific runtime work.
Stage 10 APIs do not require those extras and do not import `MDAnalysis`.
Stage 11.1 can report availability and lazily require `MDAnalysis`, while
keeping it outside the default/core dependency set.

Default tests run without requiring optional scientific dependencies. Stages
11.4 and 11.5 use the optional extras only for actual local topology and
trajectory loading. Stage 11.6 consumes their existing results without
acquiring MDAnalysis, while default and core tests continue to avoid requiring
scientific extras.

The dependency decision is documented in
`docs/adr/0001-optional-scientific-dependencies.md`. The local test policy is
documented in `docs/local_scientific_integration_tests.md`, and the default CI
boundary is documented in `docs/default_ci_scientific_boundary.md`.

## Relationship to future Stage 11

Stage 11 ownership is:

```text
Stage 11.1:
  Optional MDAnalysis scientific runtime boundary.

Stage 11.2:
  Runtime result dataclasses.

Stage 11.3:
  Local-only scientific test harness.

Stage 11.4:
  Load a single condition.

Stage 11.5:
  Load manifest conditions.

Stage 11.6:
  Collect metadata/provenance.

Stage 11.7:
  Extract residue names.

Stage 11.8:
  Document the boundary before Rg.
```

Stages 11.1 through 11.7 provide the runtime capabilities listed above. Stage
11.8 documents and tests their boundary before Stage 12 begins.

## Non-goals for Stage 10.4

Stage 10.4 does not:

- add runtime source code;
- add new APIs;
- modify dependency configuration;
- import `MDAnalysis`;
- import numpy, pandas, networkx, or pyarrow;
- add GROMACS integration;
- parse topology files;
- parse trajectory files;
- extract residue names from scientific files;
- compute Rg;
- compute contacts;
- generate graph outputs;
- add local scientific integration tests;
- add real data;
- change CLI or workflow behavior.

## Future stages

```text
Stage 11:
  minimal topology/trajectory loading prototype.

Stage 12:
  real Rg preprocessing MVP.

Stage 13:
  contacts extraction MVP.

Stage 14:
  graph export from real preprocessing.

Stage 15:
  scientific MVP workflow.
```

Stage 12 is complete at the documented Rg MVP boundary. Stage 13 should begin
contacts extraction in separate contacts-specific modules and should not add
contacts to the Rg-specific computation, export, validation, comparison, or
report modules. Recommended order:

1. Contact definition and options contract.
2. Minimal per-frame contacts extraction.
3. Contacts export, validation, and comparison.
4. Graph integration after contacts are stable.

Stages 13 through 15 remain planning only.
