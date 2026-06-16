# Contacts performance boundary

## Purpose

This document fixes the contacts MVP performance expectations and boundaries
before and after Stage 13.5b lightweight performance sanity checks.

This document is not a benchmark report.
This document does not introduce timing requirements.
This document does not change implementation behavior.

Stage 13.5a is documentation and docs-test work only. It records what the
contacts MVP currently does, where default CI and local scientific tests stop,
and what Stage 13.5b may check without turning contacts into a hard
performance-gated feature. Stage 13.6 keeps this as the final contacts MVP
boundary before graph-specific work.

## Current MVP scope

The contacts MVP currently supports:

- residue-level per-frame contact detection;
- manifest-level aggregation;
- `contacts_perframe.csv` export;
- `contact_edges.csv` aggregate export;
- contacts validation for both CSV outputs;
- contacts comparison against generated/reference CSV outputs;
- lightweight performance sanity checks over small synthetic contacts data.

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

## Stage 13.5b lightweight sanity checks

Stage 13.5b adds lightweight contacts performance sanity checks, not true
benchmarks. The checks use small synthetic data only, do not measure
wall-clock time, do not enforce hard timing thresholds, and do not require
MDAnalysis or real MD data.
Stage 13.5b uses no hard timing benchmarks.

The checks are default-CI-safe and dependency-free. They verify bounded,
deterministic behavior of contacts result, export, validation, and comparison
flows without adding a machine-specific performance gate.

Stage 13.5b checks:

- use small synthetic data;
- avoid real MD data;
- avoid MDAnalysis;
- avoid hard timing thresholds;
- avoid measuring machine-specific wall-clock performance;
- check deterministic bounded behavior;
- guard against accidentally obvious explosive behavior;
- remain stable in default CI.

The accepted Stage 13.5b checks include:

- verifying synthetic contacts result size remains bounded;
- verifying writers, validators, and comparison handle small synthetic outputs
  deterministically and with bounded row counts;
- verifying no local scientific test is required;
- verifying docs preserve the no-hard-benchmark boundary.

Stage 13.5b still does not add:

- failing if computation takes more than a fixed number of seconds;
- requiring real trajectories;
- requiring MDAnalysis in default CI;
- benchmarking against a specific machine;
- comparing performance numbers across runs;
- adding large generated test data.

## Explicit non-goals

Stage 13.5a and Stage 13.5b do not add:

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

These directions are not implemented in Stage 13.5a or Stage 13.5b.

## Final contacts MVP performance boundary

The completed Stage 13 Contacts MVP flow is:

```text
loaded manifest runtimes
-> contacts computation
-> contacts export
-> CSV validation
-> reference comparison
-> performance boundary/sanity checks
```

The final performance layer is limited to documentation and small synthetic
sanity checks. It does not introduce benchmark reports, wall-clock thresholds,
local scientific performance gates, real-data CI, graph performance tests, or
optimization work.

The following remain outside the contacts MVP:

- contacts report bundle;
- graph export;
- backend graph `nodes.csv`;
- backend graph `edges.csv`;
- `graph.json`;
- graph diagnostics from real preprocessing;
- CLI/workflow scientific MVP;
- biological interpretation;
- real-data CI.
