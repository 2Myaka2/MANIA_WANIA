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
