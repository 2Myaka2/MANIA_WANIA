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

These packages are candidates for future optional dependencies only. They are
not declared here as installed or required:

- MD trajectory and topology runtime: `MDAnalysis`;
- numerical arrays and mathematics: `numpy`;
- tabular or local data handling, if needed: `pandas` and `pyarrow`;
- graph or scientific graph analysis, if needed: `networkx`.

Stage 9.2 will decide whether extras such as `[science]`, `[md]`, or more
granular groups should exist. Stage 9.1 does not choose final extra names and
does not modify dependency configuration.

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
  decide exact dependency extras/groups, for example [science] / [md],
  without necessarily implementing scientific preprocessing.

Stage 9.3:
  define a local-only scientific integration test strategy.

Stage 9.4:
  document and enforce that CI/default tests do not require real MD data.

Stage 10:
  residue-library bridge work.

Stage 11:
  minimal trajectory/topology loading prototype, after dependency-boundary
  decisions.
```

These are planning notes only and do not describe implemented capabilities.

## Open questions

- Should optional dependencies be grouped as `[science]`, `[md]`, or more
  granular extras?
- Should MDAnalysis be the first supported trajectory backend?
- Should `numpy` be explicit or only transitive through MD-related packages?
- Should local-only scientific tests use pytest markers?
- How should missing optional dependencies be reported?
- How should documentation distinguish placeholder examples from local real
  reference packages?
- Should scientific integration tests live outside the default test suite?
