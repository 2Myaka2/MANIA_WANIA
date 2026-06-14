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
