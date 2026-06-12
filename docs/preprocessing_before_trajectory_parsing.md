# Preprocessing before trajectory parsing

## Purpose

This document summarizes the implemented preprocessing boundary before
topology and trajectory parsing begins.

Stages 8 through 10 provide lightweight contracts, local path checks,
residue-library loading and validation, and residue QC for explicit residue
names. They do not add scientific file parsing or a trajectory runtime.

## Current implemented capabilities

The current preprocessing layer supports:

- a typed preprocessing manifest contract;
- committed placeholder manifest examples;
- explicit local manifest path validation;
- a local reference package sanity checker;
- a bridge from manifest residue-library options to the existing loader and
  custom-residue extension behavior;
- report-based local residue-library format validation;
- residue QC for residue names provided explicitly by the caller.

The main public APIs currently exported from `mania.preprocessing` are:

```python
load_preprocessing_input_manifest(...)
validate_preprocessing_manifest_paths(...)
check_preprocessing_reference_package(...)
load_residue_library_from_manifest_options(...)
resolve_residue_library_manifest_paths(...)
validate_residue_library_from_manifest_options(...)
run_residue_qc_from_manifest_options(...)
```

These APIs cover contracts, local filesystem checks, residue-library files,
and explicit residue-name QC. They do not create a scientific trajectory
session.

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

- topology loading;
- trajectory loading;
- an MDAnalysis Universe, session, or other scientific runtime object;
- GROMACS runtime integration;
- residue extraction from topology/trajectory;
- frame iteration;
- atom or residue selection;
- coordinate or position access from trajectory files;
- real Rg computation;
- real contact extraction;
- contacts-per-frame outputs;
- graph export from real preprocessing;
- local scientific integration tests requiring real MD data;
- CLI or workflow integration for real preprocessing.

## Why trajectory parsing comes next

Stage 11 should begin with minimal topology and trajectory loading because the
later scientific preprocessing stages depend on information that Stage 10
cannot provide:

- residue names from real topology or trajectory inputs;
- frame count and frame times;
- atom selections;
- positions and coordinates;
- inputs for Rg computation;
- inputs for contacts extraction;
- inputs for graph export from real preprocessing.

Starting with contacts or Rg before establishing this loading boundary would
leave the scientific calculations without a defined runtime input. Stage 11 is
future work and is not implemented by Stage 10.4.

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

Stage 10 default tests run without optional scientific dependencies. Stage 11
and later may use the optional extras for actual topology and trajectory
loading, but default and core tests must continue to avoid requiring them.

The dependency decision is documented in
`docs/adr/0001-optional-scientific-dependencies.md`. The local test policy is
documented in `docs/local_scientific_integration_tests.md`, and the default CI
boundary is documented in `docs/default_ci_scientific_boundary.md`.

## Relationship to future Stage 11

Likely Stage 11 ownership is:

```text
Stage 11.1:
  Load topology/trajectory paths from preprocessing manifest options.

Stage 11.2:
  Expose a condition-level Universe/session object or lightweight runtime object.

Stage 11.3:
  Collect basic metadata/provenance such as frame count and time range.

Stage 11.4:
  Extract minimal residue-name information if feasible.

Stage 11.5:
  Keep contacts/Rg out of the first loading step.
```

These entries describe future work, not implemented behavior.

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

This roadmap is planning only. None of the Stage 11 through Stage 15
capabilities is implemented by Stage 10.4.
