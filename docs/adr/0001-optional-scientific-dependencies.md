# ADR: Optional scientific dependencies

## Status

Accepted

## Context

MANIA/WANIA currently has a lightweight backend that can be installed and
tested without scientific trajectory-processing packages. Its default runtime
dependencies are limited to configuration and YAML support, while the existing
development extra contains test, lint, and type-checking tools.

Stage 8 added preprocessing input and reference contracts, opt-in local path
validation, residue-library bridge planning, and local reference package sanity
checks. These features validate models and filesystem metadata without loading
or interpreting scientific data.

Future preprocessing will likely need external packages for topology and
trajectory access, numerical work, tabular data, or scientific graph analysis.
Adding those packages directly to the core runtime would make installation,
tests, CI, and maintenance heavier before the scientific boundary is designed.

Real molecular dynamics (MD) trajectories, topologies, structures, and residue
libraries remain local/reference inputs. They must not become normal committed
fixtures or a default CI requirement.

## Decision

- The core MANIA/WANIA runtime must remain lightweight.
- Scientific dependencies must be optional.
- Future scientific code must live behind explicit optional dependency
  boundaries.
- Missing optional dependencies must produce clear, deterministic errors.
- Core tests must not require scientific dependencies.
- The default CI and test suite must not require real MD trajectory or topology
  data.
- Stage 9.1 does not add dependencies.
- Stage 9.1 does not add optional dependency groups or extras.
- Stage 9.2 will decide the exact dependency extras or groups.

## Consequences

- The current lightweight workflow remains installable and testable without
  scientific packages.
- Stage 8 preprocessing manifest and reference checks remain based on the
  standard library and the existing lightweight runtime.
- Future scientific features require explicit optional dependency handling and
  deterministic missing-dependency behavior.
- Tests involving real MD data should be local-only or explicitly marked in a
  later stage.
- Documentation must continue to distinguish committed placeholder examples
  from local real reference packages.

## Core runtime boundary

The core/default runtime includes:

- config and manifest models;
- JSON and YAML config loaders;
- backend contract validators;
- the comparison layer;
- the graph diagnostics layer that does not require `networkx`;
- the notebook export adapter;
- the existing lightweight CLI workflow;
- preprocessing manifest models and loader;
- local path validation based on filesystem metadata;
- local reference package sanity checks based on standard-library filesystem
  checks.

## Optional scientific runtime boundary

The following future capabilities belong behind optional scientific
dependencies:

- topology loading;
- trajectory loading;
- frame iteration;
- atom and residue selection;
- residue extraction from topology or trajectory data;
- real Rg computation;
- real contact extraction;
- scientific graph construction from trajectory-derived contacts when it
  requires optional dependencies;
- local-only scientific integration tests.

## Candidate dependency families

Stage 9.1 identified these candidate families for future optional dependencies:

- MD trajectory and topology runtime: `MDAnalysis`;
- numerical arrays and mathematics: `numpy`;
- tabular or local data handling, if needed: `pandas` and `pyarrow`;
- graph or scientific graph analysis, if needed: `networkx`.

Stage 9.1 did not choose final extra names or modify dependency configuration.

## Stage 9.2 extras decision

Stage 9.2 defines two PEP 621 optional dependency extras:

- `md` is the minimal future molecular-dynamics runtime extra. It directly
  installs `MDAnalysis` for future topology loading, trajectory loading, frame
  iteration, and atom or residue selection.
- `science` is the aggregate convenience extra for future scientific
  preprocessing. It currently repeats the same direct dependency set as `md`,
  so it also directly installs `MDAnalysis`.

Install either extra from a local checkout with:

```bash
pip install ".[md]"
pip install ".[science]"
```

The dependencies remain optional so the core runtime, preprocessing manifest
loading, filesystem checks, current CLI workflow, and default tests remain
lightweight. Stage 9.2 does not add `numpy`, `pandas`, `networkx`, or `pyarrow`
explicitly. `numpy` may be installed transitively by a scientific package, but
immediate trajectory/topology boundary work does not require a separate direct
declaration. `pandas` and `pyarrow` are not needed for that immediate boundary
work. `networkx` is excluded because the current graph diagnostics layer
remains lightweight and does not require it.

Stage 9.2 does not implement scientific runtime code, topology or trajectory
loading, or scientific calculations. It also does not make real MD data part
of default CI or the default test suite.

## Stage 9.3 local test strategy

Future local scientific integration tests are explicit opt-in tests that must
not run in default CI. They may require the optional extras and local,
uncommitted MD data. Stage 9.3 adds strategy only; see
`docs/local_scientific_integration_tests.md`.

## Stage 9.4 default CI boundary

Default CI must not require optional scientific extras or real MD data, and
local scientific tests remain opt-in. Stage 9.4 adds boundary documentation
and tests only; see `docs/default_ci_scientific_boundary.md`.

## Stage 10.4 preprocessing boundary

Stage 10 completed residue-library bridge, validation, and explicit
residue-name QC work without scientific dependencies. Topology and trajectory
loading remain future optional scientific runtime work. See
`docs/preprocessing_before_trajectory_parsing.md`.

## Stage 11.1 optional runtime boundary

Stage 11.1 implements safe MDAnalysis availability, status, and lazy import
helpers while keeping MDAnalysis optional. Default CI and default tests must
continue to work without it. Actual topology and trajectory loading remains
future Stage 11.4 work.

## Stage 11.2 runtime result models

Stage 11.2 implements runtime input and result dataclasses without scientific
dependencies. MDAnalysis remains optional, and actual topology or trajectory
loading remains future work.

## Stage 11.3 local scientific test harness

Stage 11.3 implements an opt-in `local_scientific` harness with
`requires_mdanalysis` and `requires_real_md_data` markers.
`MANIA_RUN_LOCAL_SCIENTIFIC` enables local execution, while
`MANIA_LOCAL_REFERENCE_PACKAGE` identifies optional local data. MDAnalysis
remains optional, and default CI remains independent from scientific extras
and real data.

## Stage 11.4 single-condition loader

Stage 11.4 adds the first single-condition MDAnalysis loader. MDAnalysis
remains optional and is required lazily only after declared paths are
validated. Default CI remains independent from real MD data. Residue
extraction, Rg, contacts, and graph export remain future work.

## Stage 11.5 manifest condition loader

Stage 11.5 adds manifest-wide condition loading by reusing the single-condition
loader. MDAnalysis remains optional and is lazily required only by
single-condition loading, while default CI remains independent from real MD
data. Residue extraction, Rg, contacts, and graph export remain future work.

## Stage 11.6 runtime metadata reports

Stage 11.6 adds lightweight metadata and provenance reports that consume
already loaded runtime results. The metadata layer does not acquire MDAnalysis
directly, so MDAnalysis remains optional and default CI remains independent
from real MD data. Rg, contacts, and graph export remain future work.

## Stage 11.7 residue-name extraction

Stage 11.7 adds residue-name extraction from already loaded runtime results.
MDAnalysis remains optional and default CI remains independent from real MD
data. Residue QC, Rg, contacts, and graph export remain future work.

## Stage 11.8 runtime boundary before Rg

Stage 11.8 documents the completed Stage 11 runtime boundary before Rg.
MDAnalysis remains optional, default CI remains independent from real MD data,
and Stage 12 Rg work remains future work. See
`docs/preprocessing_runtime_boundary_before_rg.md`.

## Stage 15.3 manifest-driven workflow runtime loading

Stage 15.3 adds a workflow-level manifest-driven runtime loading wrapper for
two conditions after Stage 15.2 readiness. Stage 15.3 readiness is called
before runtime loading, and readiness failure prevents runtime loading. The
wrapper reuses the existing Stage 11 runtime/manifest loading APIs and adds no
new runtime loader.

The Stage 15.3 import/default CI does not require MDAnalysis. The real runtime loading remains optional/local/scientific through the accepted Stage 11 boundary and may
require optional scientific dependencies only when executed locally with
extras. No MDAnalysis dependency is added to default CI.

`local_md` remains local-only, not committed, and not required by default CI.
The wrapper adds no Rg/contacts/graph/diagnostics/reference/CLI behavior.
Stage 15.4 will orchestrate manifest-level Rg + contacts, and Stage 15.3 does
not compute them.

`MANIA_analysis_v1_2` remains the current reference semantics. The reference
notebook not executed boundary remains in force; the reference comparison remains Stage 15.7 optional mode. Temporal RIN remains future scope. WANIA frontend
adapter/API payload remains future scope.

## Stage 15.4 manifest-level Rg + contacts orchestration

Stage 15.4 adds manifest-level Rg + contacts orchestration after Stage 15.3
runtime loading. The Stage 15.3 runtime loading result feeds Stage 15.4, and
Stage 15.4 does not load runtimes itself. It consumes the raw Stage 11
manifest runtime load result already retained by Stage 15.3.

The wrapper reuses accepted Stage 12 Rg APIs and accepted Stage 13 contacts
APIs. It adds no new scientific algorithms, does not manually compute Rg, and
does not manually compute contacts.

The Stage 15.4 boundary is in-memory orchestration only: no CSV export, no
graph export, no diagnostics, no reference comparison, no CLI, no notebook
execution, no file creation, and no local real MD smoke test. Stage 15.5 will
orchestrate graph export, and Stage 15.4 does not build graph artifacts.

Import/default CI does not require MDAnalysis. Real computation remains
optional/local/scientific through the accepted Stage 11, Stage 12, and Stage
13 boundaries. `local_md` remains local-only, not committed, and not required
by default CI.

`MANIA_analysis_v1_2` remains the current reference semantics. The reference
notebook is not executed; notebook not executed remains part of the workflow
boundary. The reference comparison remains Stage 15.7 optional mode, disabled
by default. Temporal RIN remains future scope. WANIA frontend adapter/API
payload remains future scope.

## Stage 15.5 graph export orchestration

Stage 15.5 adds graph export orchestration after Stage 15.4. The Stage 15.4
computation result feeds Stage 15.5, and Stage 15.5 does not compute
Rg/contacts. The wrapper consumes already computed in-memory results and
reuses accepted Stage 14 graph export APIs for mapping, backend graph
nodes.csv, corrected edges.csv, CSV validation, graph.json, and bundle
creation. It adds no new graph semantics.

Stage 13 `contact_edges.csv` is an aggregate contacts table. backend graph
edges.csv is a separate backend graph artifact. Stage 15.5 writes backend graph
edges.csv through the accepted Stage 14 graph edge writer.

Import/default CI remains dependency-free. Stage 15.5 does not require
MDAnalysis, default CI does not require real MD data, and default CI does not
require `local_md`. `local_md` remains local-only and not committed.

Stage 15.5 has no diagnostics, no reference comparison, no CLI, and no
notebook execution. Stage 15.6 will orchestrate diagnostics + diagnostics
report. Reference comparison remains Stage 15.7 optional mode. Temporal RIN
remains future scope. WANIA frontend adapter/API payload remains future scope.

## Stage 12.1a Rg result contracts

Stage 12.1a adds dependency-free Rg result and report dataclasses. They use
only the standard library, do not access runtime objects, and keep MDAnalysis
optional. Actual Rg computation remains future Stage 12.1b work.

## Stage 12.1b single-condition Rg computation

Stage 12.1b computes Rg from one already loaded condition result.
`compute_condition_rg(...)` does not acquire dependencies or load files; it
uses the runtime object produced through the existing Stage 11 loading
boundary. MDAnalysis remains optional and local-scientific, while default CI
remains independent from real MD data.

## Stage 12.1c manifest Rg computation

Stage 12.1c composes the accepted single-condition Rg function across an
existing manifest load result. The manifest layer does not acquire
dependencies, load files, or directly inspect runtime objects. MDAnalysis
remains optional behind the Stage 11 loading boundary, and default CI remains
independent from real MD data.

## Stage 12.1d local scientific Rg smoke test

Stage 12.1d validates the existing loading and manifest Rg computation path
with optional MDAnalysis and explicitly configured local real data. The smoke
test remains opt-in, adds no new CI job, and keeps default CI independent from
MDAnalysis and local reference data.

## Stage 12.2a Rg CSV writer

Stage 12.2a adds a dependency-free CSV writer that consumes existing Rg result
objects. It uses only the standard library and does not load files or acquire
MDAnalysis. MDAnalysis remains optional and is required only by the existing
loading and computation paths. Default CI remains independent from local real
data.

## Stage 12.2b Rg CSV validation

Stage 12.2b adds dependency-free validation for exported Rg CSV files. It uses
standard-library CSV parsing and consumes exported files only. MDAnalysis
remains optional and is required only by loading and computation paths.
Default CI remains independent from local real data.

## Stage 12.2c Rg export docs and examples

Stage 12.2c adds documentation and synthetic examples for the accepted Rg
export chain. The synthetic example uses existing result, writer, and
validator APIs and requires neither MDAnalysis nor real data. MDAnalysis
remains optional for loading and computation, default CI remains independent
from local real data, and no scientific data is committed.

## Stage 12.2d local scientific Rg export smoke test

Stage 12.2d exercises the accepted Rg export chain with optional MDAnalysis
and explicitly configured local real data. The writer and validator remain
dependency-free, generated CSV is written only to pytest's temporary path,
and no scientific data is committed. The smoke test remains opt-in, so default
CI stays independent from local real data.

## Stage 12.3a Rg reference comparison input contract

Stage 12.3a adds dependency-free dataclasses and readiness validation for
future Rg reference comparison. The validator uses only filesystem metadata
unless CSV contract validation is requested, in which case it reuses the
dependency-free `validate_rg_timeseries_csv(...)` API. It does not compare
numeric values or acquire MDAnalysis.

MDAnalysis remains optional and unrelated to comparison input validation.
Default CI remains independent from local real data, and no local scientific
comparison smoke test is added in this stage.

## Stage 12.3b numeric-tolerant Rg CSV comparison

Stage 12.3b adds dependency-free comparison of exported actual and reference
Rg CSV files. It uses standard-library CSV parsing and mathematics, reuses the
Stage 12.3a input validation boundary, and does not load trajectories or
recompute Rg.

MDAnalysis remains optional and unrelated to exported CSV comparison. Default
CI remains independent from local real data, no scientific data is committed,
and no local scientific comparison smoke test is added in this stage.

## Stage 12.4a lightweight in-memory Rg report bundle

Stage 12.4a adds a dependency-free in-memory bundle that consumes existing Rg
computation, CSV write, CSV validation, and reference comparison result
objects only. Bundle construction performs no scientific or file operation.

MDAnalysis remains optional and unrelated to report bundle construction.
Default CI remains independent from local real data, and no local scientific
report smoke test or report-file writer is added in this stage.

## Stage 12.4b final Rg MVP boundary

Stage 12 closes with computation, CSV writing and validation, numeric-tolerant
CSV comparison, and an in-memory report bundle. The conceptual Python API flow
does not create a CLI command, workflow wrapper, persistent output directory
manager, or report-file writer.

Only local Rg computation and export smoke tests use optional MDAnalysis and
explicitly configured real data. MDAnalysis remains optional. Default CI does
not require real MD data, local scientific tests are skipped by default, and
the default suite uses fake, synthetic, or unit-level coverage for the Stage
12 contracts, writer, validator, comparison, and report bundle.

Contacts extraction belongs to Stage 13 in separate contacts-specific modules.
Graph integration follows only after contacts are stable; neither is part of
the Stage 12 Rg modules.

## Stage 13.1a contacts definition and options contract

Stage 13.1a adds only dependency-free contact definition and options
dataclasses. The contracts use the standard library, serialize without runtime
objects, and do not acquire MDAnalysis or load scientific files.

MDAnalysis remains optional. Actual contact computation will later consume
already loaded runtimes through the established preprocessing boundary.
Default CI remains independent from real MD data, and Stage 13.1a adds no
local scientific contacts test, contact export, or graph export.

## Stage 13.1b contacts result contracts

Stage 13.1b adds dependency-free contacts issue, pair, frame, condition, and
manifest result contracts. They use only standard-library dataclasses and
mathematics, validate value and nested-result shapes, and serialize without
runtime objects.

MDAnalysis remains optional. Actual contact computation will later use already
loaded runtimes through the existing preprocessing boundary. Default CI
remains independent from real MD data, and this stage adds no local scientific
contacts test, CSV export, or graph export.

## Stage 13.2a single-condition contacts computation

Stage 13.2a adds dependency-free contact computation that consumes one already
loaded condition runtime object. `compute_condition_contacts(...)` does not
load files, call runtime loaders, or acquire MDAnalysis.

MDAnalysis remains optional behind the existing Stage 11 loading boundary.
Default CI uses fake runtime objects and does not need MDAnalysis or real MD
data. Local scientific contacts smoke coverage, CSV export, and graph export
remain future explicit stages.

## Stage 13.2b manifest contacts aggregation

Stage 13.2b composes the accepted single-condition contacts function across an
existing manifest load result. The manifest layer does not acquire
dependencies, load files, directly inspect runtime objects, add distance
logic, export CSV, compare references, or add graph semantics.

MDAnalysis remains optional behind the existing Stage 11 loading boundary.
Default CI uses fake load results and does not need MDAnalysis or real MD data.
Contact CSV export and graph output remain future explicit stages.

## Stage 13.2c local contacts computation smoke test

Stage 13.2c adds an opt-in local scientific smoke test for the accepted
contacts computation chain. The test loads a local manifest, loads local
condition runtimes, computes manifest-level contacts, inspects result shape,
and serializes the result.

MDAnalysis remains optional behind the existing Stage 11 loading boundary, and
the local smoke test runs only when the existing local scientific environment
is explicitly enabled. Default CI remains independent from MDAnalysis, real MD
data, and local reference packages. This stage does not change dependency
requirements, add contact export, or add graph output.

## Stage 13.3a contacts per-frame CSV writer

Stage 13.3a adds a dependency-free `contacts_perframe.csv` writer for existing
condition-level and manifest-level contacts results. The writer uses the
standard library, consumes already computed contacts objects only, and does
not load files, acquire MDAnalysis, recompute contacts, validate CSV, compare
references, write aggregate contact edges, or produce graph outputs.

MDAnalysis remains optional behind the existing Stage 11 loading boundary.
Default CI remains independent from MDAnalysis, real MD data, and local
reference packages.

## Stage 13.3b contact edges CSV writer

Stage 13.3b adds a dependency-free `contact_edges.csv` writer for existing
condition-level and manifest-level contacts results. The writer uses the
standard library, consumes already computed contacts objects only, and does
not load files, acquire MDAnalysis, recompute contacts, validate CSV, compare
references, or produce graph outputs.

`contact_edges.csv` is an aggregate contacts table, not backend graph
`edges.csv`. Graph dependencies and graph export remain out of scope. Default
CI remains independent from MDAnalysis, real MD data, and local reference
packages.

## Stage 13.3c contacts CSV validation

Stage 13.3c adds dependency-free validation for `contacts_perframe.csv` and
`contact_edges.csv`. The validators read CSV files only, use only the standard
library, do not need MDAnalysis, and do not load or recompute contacts from
runtime objects.

Default CI remains independent from MDAnalysis and real MD data. Graph
dependencies remain out of scope.

## Stage 13.3d contacts export docs and examples

Stage 13.3d adds documentation and synthetic examples for the accepted contacts
export chain. The synthetic example uses existing result, writer, and validator
APIs and requires neither MDAnalysis nor real data. It writes generated output
only into a temporary directory when run directly.

MDAnalysis remains optional for loading and computation, default CI remains
independent from local real data, and no scientific data is committed. This
stage does not add source behavior changes, local scientific export smoke
coverage, reference comparison, report bundles, graph export, CLI integration,
workflow integration, or graph dependencies.

## Stage 13.3e local contacts export smoke test

Stage 13.3e adds an opt-in local scientific smoke test for the accepted
contacts computation/export/validation chain. It uses the existing local
scientific harness and writes generated `contacts_perframe.csv` and
`contact_edges.csv` files only as temporary pytest outputs.

MDAnalysis remains optional behind the existing loading boundary, and default
CI remains independent from real MD data, local reference packages, and local
scientific environment variables. The local contacts export smoke test does
not change dependency requirements, commit generated CSV artifacts, compare
references, build report bundles, produce graph outputs, or add graph
dependencies.

## Stage 13.4a contacts reference comparison input contract

Stage 13.4a adds dependency-free contacts reference comparison input and
option contracts for generated/reference `contacts_perframe.csv` and
`contact_edges.csv` pairs. The validator uses only filesystem metadata and the
existing contacts CSV validators. It does not load MDAnalysis, recompute
contacts, compare rows, compute numeric differences, build report bundles, or
produce graph outputs.

Default CI remains independent from MDAnalysis, real MD data, local reference
packages, and graph dependencies.

## Stage 13.4b contacts output comparison

Stage 13.4b adds dependency-free comparison for generated/reference
`contacts_perframe.csv` and `contact_edges.csv` outputs. It uses
standard-library CSV parsing and mathematics, reuses the Stage 13.4a input
validation boundary and existing contacts CSV validators, and does not load
trajectories or recompute contacts.

The comparison supports exact contacts row-key matching, optional exact row
order enforcement, tolerant distance and frequency comparisons, exact
non-tolerant status, time, and count comparisons, and JSON-safe result
objects. It does not build report bundles, add local scientific comparison
smoke tests, add CLI/workflow integration, produce graph outputs, or add graph
dependencies.

MDAnalysis remains optional and unrelated to contacts CSV comparison. Default
CI remains independent from real MD data, local reference packages, and graph
dependencies.

## Stage 13.5a contacts performance boundary docs

Stage 13.5a adds contacts performance boundary documentation only. It does not
change dependency requirements, source behavior, or implementation
performance.

MDAnalysis remains optional. Default CI remains independent from real MD data,
local reference packages, and local scientific environment variables. No hard
timing benchmark requirement is introduced. Graph export remains future work.

## Stage 13.5b contacts performance sanity checks

Stage 13.5b adds lightweight contacts performance sanity checks that are
dependency-free and default-CI-safe. They use small synthetic contacts data and
exercise bounded deterministic result, export, validation, and comparison
behavior.

The checks add no MDAnalysis requirement, no real MD data requirement, no
benchmark dependency, and no hard timing gate. MDAnalysis remains optional,
local scientific tests remain opt-in, and default CI remains stable. This
stage does not change source behavior, add performance optimization, or add
graph export.

## Stage 13.6 final contacts MVP boundary

Stage 13.6 adds final contacts MVP boundary documentation and a docs test only.
It records that the completed contacts MVP covers:

```text
loaded manifest runtimes
-> contacts computation
-> contacts export
-> CSV validation
-> reference comparison
-> performance boundary/sanity checks
```

MDAnalysis remains optional behind the existing loading boundary. Default CI
remains independent from MDAnalysis, real MD data, local reference packages,
and local scientific environment variables.

Stage 13.6 does not change dependency requirements, source behavior, public
APIs, or implementation performance. It does not add a contacts report bundle,
graph export, backend graph `nodes.csv`, backend graph `edges.csv`,
`graph.json`, graph diagnostics from real preprocessing, CLI/workflow
scientific MVP, biological interpretation, or real-data CI.

## Stage 14.1a preprocessing graph export mapping

Stage 14.1a starts graph export work with dependency-free in-memory graph
export mapping only. It consumes accepted preprocessing contacts result
objects and maps contact-observed residue identities to condition-scoped node
records and aggregate contacts to condition-scoped graph edge records.

The graph export mapping is dependency-free. It adds no MDAnalysis
requirement, no real MD data requirement, and no dependency configuration
change, so default CI remains stable. Graph diagnostics/validators are not run
yet.

contact_edges.csv is aggregate contacts table output from Stage 13. backend
graph edges.csv remains separate/future at the Stage 14.1a mapping boundary.
Stage 14.1a maps contacts into graph edge records but writes no backend graph
`nodes.csv`, no backend graph `edges.csv`, and no `graph.json`.

Graph artifact writers remain future stages: the nodes.csv writer is Stage
14.1b, the backend graph edges.csv writer is Stage 14.1c, and the graph.json writer is Stage 14.1e.
Rg-to-graph mapping remains future until explicitly scoped.

## Stage 14.1b preprocessing graph nodes CSV writer

Stage 14.1b adds the backend graph nodes CSV writer from accepted
preprocessing graph mapping. The graph nodes CSV writer is dependency-free,
requires no MDAnalysis, requires no real MD data, and does not change
dependency configuration, so default CI remains stable.

The writer consumes `PreprocessingGraphExportMappingResult` and writes only
backend graph nodes.csv. It does not write backend graph edges.csv, does not
write `graph.json`, and graph diagnostics/validators are not run yet.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv is separate/future, backend graph edges.csv writer remains Stage
14.1c, graph CSV validation remains Stage 14.1d, and graph.json remains Stage
14.1e.

## Stage 14.1c preprocessing graph edges CSV writer

Stage 14.1c adds the backend graph edges.csv writer from accepted
preprocessing graph mapping. The graph edges CSV writer is dependency-free,
requires no MDAnalysis, requires no real MD data, and does not change
dependency configuration, so default CI remains stable.

The writer consumes `PreprocessingGraphExportMappingResult` and writes only
backend graph edges.csv through `write_preprocessing_graph_edges_csv(...)`.
It uses the accepted backend graph `EDGE_COLUMNS` schema and adapts mapping
fields narrowly: source and target node IDs become `resid_i` and `resid_j`,
priority-selected `edge_kind` becomes `edge_type`, all unique edge types
become pipe-separated `all_edge_types`, the unique type count becomes
`n_edge_types`, `condition_name` becomes `condition`, `contact_frequency`
becomes `contact_freq`, and angstrom-labelled `mean_minimum_distance` becomes
`mean_dist_A`. Unsupported optional edge metadata is serialized as empty
strings.

Stage 14.1c-fix records
`data/reference/notebooks_libraries_v1_2/MANIA_analysis_v1_2.ipynb` as the
current graph reference semantics while v1.1 remains historical. v1.2 Cell 5
adds graph edge display priority for multi-type residue pairs. v1.2 Cell 12
fixes temporal RIN export handling, but temporal RIN export is documented-only
in this correction and remains future temporal/workflow artifact scope. This
does not add hydrogen-bond, salt-bridge, hydrophobic, or other biochemical
interaction detection to Stage 13; current preprocessing contacts still map to
the generic `residue_contact` type.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv is separate and is written only by this graph-stage writer from
accepted graph mapping records. Stage 14.1c does not write backend graph
nodes.csv, does not write `graph.json`, and graph diagnostics/validators are
not run yet.

graph CSV validation remains Stage 14.1d and graph.json remains Stage 14.1e.

## Stage 14.1d preprocessing graph CSV validation boundary

Stage 14.1d adds the graph CSV validation boundary for generated backend graph
nodes.csv and corrected edges.csv. The validator is dependency-free, requires
no MDAnalysis, requires no real MD data, and does not change dependency
configuration, so default CI remains stable.

The validator consumes existing CSV files only. corrected edges.csv includes
all_edge_types and n_edge_types, and validation uses the accepted
`EDGE_TYPE_PRIORITY` for multi-type edge ordering. Stage 13 contact_edges.csv
is aggregate contacts table output, while backend graph edges.csv is separate
graph artifact.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority defines the accepted graph edge display priority,
v1.2 Cell 12 temporal RIN export fix remains documented-only here, and
temporal RIN export remains future scope.

Stage 14.1d does not write `graph.json`, does not build graph export bundles,
does not run graph diagnostics, and adds no local scientific graph smoke test.
graph.json remains Stage 14.1e and diagnostics remain Stage 14.2a.

## Stage 14.1e preprocessing graph JSON writer

Stage 14.1e adds a dependency-free graph.json writer for generated backend
graph artifacts. The writer consumes accepted/validated nodes.csv + corrected
edges.csv, calls `validate_preprocessing_graph_csvs(...)` before writing, and
preserves row fields in the accepted backend graph JSON structure.

The writer uses only the standard library. It has no MDAnalysis requirement,
no real MD data requirement, and no dependency configuration change, so
default CI remains stable. graph JSON preserves `edge_type`, `all_edge_types`,
and `n_edge_types` as corrected multi-type edge fields, including current
generic residue_contact semantics.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv and graph.json are Stage 14 graph artifacts.
MANIA_analysis_v1_2 remains the current graph reference semantics. v1.2 Cell
5 interaction priority defines the accepted graph edge display priority,
v1.2 Cell 12 temporal RIN export fix remains documented-only here, and
temporal RIN export remains future scope.

Stage 14.1e does not build graph export bundles, does not run graph
diagnostics, does not perform graph comparison, and adds no local scientific
graph smoke test. graph export bundle remains Stage 14.1f and diagnostics
remain Stage 14.2a.

## Stage 14.1f preprocessing graph export bundle boundary

Stage 14.1f adds a dependency-free graph export bundle boundary for existing
Stage 14 graph artifacts. The bundle consumes existing nodes.csv, corrected
edges.csv, and graph.json artifacts, uses
`validate_preprocessing_graph_csvs(...)` for CSV consistency, and checks
lightweight graph JSON structure/count consistency.

The bundle uses only the standard library. It has no MDAnalysis requirement,
no real MD data requirement, and no dependency configuration change, so
default CI remains stable. graph diagnostics are not run yet.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv and graph.json are Stage 14 graph artifacts, and the Stage 14.1f
bundle does not treat contact_edges.csv as backend graph edges.csv.

The bundle preserves corrected multi-type edge fields through the boundary:
`edge_type`, `all_edge_types`, and `n_edge_types`. MANIA_analysis_v1_2 remains
the current graph reference semantics. v1.2 Cell 5 interaction priority
defines the accepted graph edge display priority, v1.2 Cell 12 temporal RIN
export fix remains documented-only here, and temporal RIN export remains
future scope.

Stage 14.1f does not run graph diagnostics, does not perform graph comparison,
does not add a report bundle beyond lightweight artifact metadata, and adds no
local scientific graph smoke test, temporal RIN export, or CLI/workflow
integration. The bundle does not run diagnostics; diagnostics remain
Stage 14.2a.

## Stage 14.2a preprocessing graph diagnostics runner bridge

Stage 14.2a adds a dependency-free graph diagnostics bridge that runs existing
graph validators/diagnostics on generated graph artifacts. The runner consumes
existing nodes.csv, corrected edges.csv, and graph.json artifacts and uses
Stage 14.1f bundle boundary before running downstream checks.

The graph diagnostics bridge must not require MDAnalysis, has no real MD data
requirement, and makes no dependency configuration change. Default CI remains
stable. It reuses existing read-only core graph validation/diagnostic code and
does not add a new scientific dependency boundary.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv, graph.json, and diagnostics are Stage 14 graph artifacts, and
Stage 14.2a does not treat contact_edges.csv as backend graph edges.csv.

The bridge preserves corrected graph edge fields `edge_type`,
`all_edge_types`, and `n_edge_types`. MANIA_analysis_v1_2 remains the current
graph reference semantics. v1.2 Cell 5 interaction priority defines the
accepted graph edge display priority, v1.2 Cell 12 temporal RIN export fix
remains documented-only here, and temporal RIN export remains future scope.

Stage 14.2a adds no diagnostics report shape, graph reference comparison,
temporal RIN export, local scientific graph smoke test, real-data CI, or
CLI/workflow integration. diagnostics report shape remains Stage 14.2b and
reference comparison remains Stage 14.3.

## Stage 14.2b preprocessing graph diagnostics report shape

Stage 14.2b adds a dependency-free in-memory diagnostics report shape for an
already computed Stage 14.2a diagnostics result. It uses only standard-library
dataclasses and scalar JSON-safe summaries.

The report shape has no MDAnalysis requirement, no real MD data requirement,
and no dependency configuration change, so default CI remains stable. It does
not run diagnostics again, read or write files, create a report bundle,
perform graph reference comparison, add a local scientific graph smoke test,
export temporal RIN artifacts, or add CLI/workflow integration.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv, graph.json, diagnostics, and diagnostics report are Stage 14 graph
artifacts. MANIA_analysis_v1_2 remains the current graph reference semantics.
v1.2 Cell 5 interaction priority defines the accepted graph edge display
priority, v1.2 Cell 12 temporal RIN export fix remains documented-only here,
and temporal RIN export remains future scope.

## Stage 14.3a graph reference comparison input contract

Stage 14.3a adds only a dependency-free reference graph comparison input
contract. It validates generated/reference artifact readiness for explicit
generated and reference `nodes.csv`, corrected backend graph `edges.csv`, and
`graph.json` paths. It uses the existing graph export bundle boundary and
standard-library dataclasses only.

Stage 14.3a has no MDAnalysis requirement, no real MD data requirement, and
no dependency configuration change. It does not perform comparison; actual
comparison remains Stage 14.3b. It does not compare node rows, edge rows, or
full graph JSON contents, and it does not add diagnostics execution, notebook
artifact comparison, temporal RIN export, CLI/workflow integration, or
biological interpretation.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.1
historical reference artifacts remain historical. v1.2 Cell 5 interaction
priority defines the accepted graph edge display priority, v1.2 Cell 12
temporal RIN export fix remains documented-only here, and temporal RIN export
remains future scope.

Corrected graph edges preserve `edge_type`, `all_edge_types`, and
`n_edge_types` according to `EDGE_TYPE_PRIORITY`. Stage 13 contact_edges.csv
is aggregate contacts table output. backend graph edges.csv, graph.json,
diagnostics, and comparison inputs are Stage 14 graph artifacts.

## Stage 14.3b graph reference artifact comparison

Stage 14.3b compares generated graph artifacts with notebook reference artifacts v1.2 and uses Stage 14.3a input contract. It adds dependency-free generated/reference comparison for enabled `nodes.csv`, corrected backend graph `edges.csv`, and `graph.json` targets after Stage 14.3a validation passes.

The comparison is read-only and returns deterministic JSON-safe result objects. CSV field values compare exactly as strings, and `graph.json` comparison is structural rather than byte-level. Stage 14.3b identifies exact differences only; expected mismatch documentation remains Stage 14.4a.

MANIA_analysis_v1_2 remains the current graph reference semantics. v1.1 historical reference artifacts remain historical. v1.2 Cell 5 interaction priority defines graph edge display priority, and v1.2 Cell 12 temporal RIN export fix remains documented-only here; temporal RIN export remains future scope.

Corrected graph comparison includes `edge_type`, `all_edge_types`, and `n_edge_types` according to `EDGE_TYPE_PRIORITY`. Stage 13 contact_edges.csv is aggregate contacts table output. backend graph edges.csv, graph.json, diagnostics, and comparison are Stage 14 graph artifacts.

## Stage 14.4a graph mismatch interpretation docs

Stage 14.4a documents expected mismatches and known semantic differences for
Stage 14.3b graph comparison in
`docs/preprocessing_graph_reference_mismatches.md`. It does not add optional
scientific dependencies, comparison logic changes, expected mismatch
classification code, semantic-difference classification code,
CLI/workflow integration, real-data CI, temporal RIN export/comparison, or
biological interpretation.

contact_edges.csv is an aggregate contacts table from Stage 13. backend graph
edges.csv is a Stage 14 graph artifact. Stage 14 graph comparison compares
backend graph edges.csv, not Stage 13 contact_edges.csv. Stage 14.4b remains
final graph export boundary docs before workflow.

## Stage 15.1 workflow contract

Stage 15.1 adds only the dependency-free preprocessing graph workflow
contract. It defines run options, deterministic output layout, planned step
names, and planning issues in memory; see
`docs/preprocessing_graph_workflow_contract.md`.

The contract uses only the standard library. It does not load manifests,
validate local MD paths, load runtimes, compute Rg, compute contacts, export
graph artifacts, run diagnostics, build diagnostics reports, perform
reference comparison, execute notebooks, add CLI integration, or create
workflow files.

MDAnalysis remains optional and is not required by the Stage 15.1 contract.
`local_md` remains local-only, local real MD data is not required by default
CI, and no dependency or CI configuration changes are made by this stage.

## Stage 15.2 local manifest readiness

Stage 15.2 adds local manifest readiness using the existing manifest contract,
existing manifest loader, and existing manifest path validation. It does not
define a new Stage 15 manifest format. In short: no new Stage 15 manifest
format.

The local manifest example is:

```text
local_md/manifests/napi2b_10ns.yaml
```

Its semantic relative paths are:

```text
../normal/topology.tpr
../normal/trajectory.xtc
../tumor/topology.tpr
../tumor/trajectory.xtc
```

The readiness check does not require MDAnalysis and does not require real MD
data in default CI. It checks filesystem metadata only and does not load
trajectories, create runtime objects, compute Rg, compute contacts, export
graph artifacts, run diagnostics, execute notebooks, or perform reference
comparison. The notebook is not executed, reference comparison remains
optional, and temporal RIN remains future scope.

`local_md` remains local-only and not committed. Local MD smoke coverage
remains Stage 15.9 and skipped by default. Runtime loading remains Stage 15.3.

## Non-goals for Stage 9.1

Stage 9.1 does not:

- add optional dependency groups or extras;
- modify `pyproject.toml`;
- import MDAnalysis;
- import numpy;
- import pandas;
- import networkx;
- import pyarrow;
- implement trajectory loading;
- implement topology loading;
- implement residue extraction from topology or trajectory data;
- implement Rg computation;
- implement contacts computation;
- add local real data;
- add committed reference packages;
- add a CI dependency on real MD data;
- add CLI integration;
- add workflow integration.

## Future stages

```text
Stage 9.1:
  ADR only; define the dependency boundary.

Stage 9.2:
  define the [md] and [science] optional extras without implementing
  scientific preprocessing.

Stage 9.3:
  define the local-only scientific integration test strategy.

Stage 9.4:
  document and test the default CI scientific boundary.

Stage 10:
  residue-library bridge work.

Stage 11:
  minimal trajectory/topology loading prototype, after dependency-boundary
  decisions.
```

Stages 9.1 through 9.4 record dependency, test, and CI boundary decisions only.
The later-stage entries are planning notes and do not describe implemented
capabilities.

## Open questions

- Should MDAnalysis be the first supported trajectory backend?
- Should a later stage add more granular extras?
- Should `numpy` remain transitive or become an explicit dependency when
  scientific runtime code is designed?
- Should local-only scientific tests use pytest markers?
- How should missing optional dependencies be reported?
- How should documentation distinguish placeholder examples from local real
  reference packages?
- Should scientific integration tests live outside the default test suite?
