# Contacts performance boundary

## Purpose

This document fixes the contacts MVP performance expectations and boundaries
before Stage 13.5b adds lightweight performance sanity checks.

This document is not a benchmark report.
This document does not introduce timing requirements.
This document does not change implementation behavior.

Stage 13.5a is documentation and docs-test work only. It records what the
contacts MVP currently does, where default CI and local scientific tests stop,
and what Stage 13.5b may check without turning contacts into a hard
performance-gated feature.

## Current MVP scope

The contacts MVP currently supports:

- residue-level per-frame contact detection;
- manifest-level aggregation;
- `contacts_perframe.csv` export;
- `contact_edges.csv` aggregate export;
- contacts validation for both CSV outputs;
- contacts comparison against generated/reference CSV outputs.

Contacts computation consumes already loaded runtimes. It does not load
topologies or trajectories and does not acquire MDAnalysis itself.

Contacts export consumes existing contacts results. Contacts validation
consumes existing CSV files. Contacts comparison consumes existing generated
and reference CSV files.

## Computational shape

Contacts detection is per-frame. For each visited frame, the MVP considers
residue pairs and the atoms selected by the configured contact options.

Runtime cost grows qualitatively with:

- number of frames;
- number of residues;
- selected atom counts;
- number of conditions.

Memory use and output size grow with detected contact observations.
`contacts_perframe.csv` may grow with per-frame contact observations.
`contact_edges.csv` is aggregated and is normally smaller than
`contacts_perframe.csv`.

Stage 13.5a does not claim optimized spatial indexing, NumPy/vectorized
acceleration, graph algorithms, or graph export exists.

## Default CI boundary

Default CI remains dependency-free for contacts boundary coverage. It does not
require MDAnalysis, real MD data, local reference packages, or large trajectory
workloads.

Default CI does not use hard wall-clock timing thresholds for contacts. It may
use small synthetic checks that verify deterministic behavior and bounded
result shape without measuring machine-specific performance.

The boundary is no hard timing thresholds for contacts in default CI.

Real MD data is not required by default. MDAnalysis remains optional and is
required only by the existing opt-in scientific loading path.

## Local scientific boundary

Local scientific tests are opt-in. They may load real local reference package
data through the existing local scientific harness when explicitly enabled.

Local scientific tests are integration smoke tests. They are not benchmark
gates and should not pass or fail based on strict timing thresholds.
Local scientific tests are not benchmark gates.

## Export, validation, and comparison boundary

Contacts writers are dependency-free and consume existing contacts results.
Contacts validators are read-only and dependency-free. Contacts comparison is
CSV-level and dependency-free.

Export, validation, and comparison do not load trajectories, do not acquire
MDAnalysis, and do not create graph outputs.

`contact_edges.csv` is an aggregate contacts table.
`contact_edges.csv` is not backend graph edges.csv.
contact_edges.csv is not backend graph edges.csv.

Graph export remains future work.

## Future Stage 13.5b sanity checks

Stage 13.5b should add lightweight performance sanity checks, not true
benchmarks. Stage 13.5b must preserve the no-hard-benchmark boundary.
Stage 13.5b must use no hard timing benchmarks.
Stage 13.5b lightweight sanity checks must remain stable in default CI.

Stage 13.5b checks should:

- use small synthetic data;
- avoid real MD data;
- avoid MDAnalysis;
- avoid hard timing thresholds;
- avoid measuring machine-specific wall-clock performance;
- check deterministic bounded behavior where possible;
- guard against accidentally obvious explosive behavior;
- remain stable in default CI.

Acceptable Stage 13.5b examples include:

- verifying synthetic contacts computation completes on a small fixture
  without excessive result size;
- verifying writers, validators, and comparison handle small synthetic CSVs
  deterministically;
- verifying no local scientific test is required;
- verifying docs preserve the no-hard-benchmark boundary.

Unacceptable Stage 13.5b examples include:

- failing if computation takes more than a fixed number of seconds;
- requiring real trajectories;
- requiring MDAnalysis in default CI;
- benchmarking against a specific machine;
- comparing performance numbers across runs;
- adding large generated test data.

## Explicit non-goals

Stage 13.5a does not add:

- source behavior changes;
- new public APIs;
- performance optimizations;
- benchmark tests;
- timing thresholds;
- local scientific performance gates;
- contacts report bundle;
- graph performance tests;
- graph export;
- graph diagnostics;
- CLI/workflow integration;
- real-data CI;
- biological interpretation.

## Future optimization directions

Future stages may consider spatial neighbor search, residue pair pruning,
chunked processing, optional vectorized or scientific backends,
memory-aware streaming exports, and graph-stage performance work.

These directions are not implemented in Stage 13.5a.
