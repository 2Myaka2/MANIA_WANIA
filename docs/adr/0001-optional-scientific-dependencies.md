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
`edge_kind` becomes `edge_type`, `condition_name` becomes `condition`,
`contact_frequency` becomes `contact_freq`, and angstrom-labelled
`mean_minimum_distance` becomes `mean_dist_A`. Unsupported optional edge
metadata is serialized as empty strings.

Stage 13 contact_edges.csv is aggregate contacts table output. backend graph
edges.csv is separate and is written only by this graph-stage writer from
accepted graph mapping records. Stage 14.1c does not write backend graph
nodes.csv, does not write `graph.json`, and graph diagnostics/validators are
not run yet.

graph CSV validation remains Stage 14.1d and graph.json remains Stage 14.1e.

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
