# Physical-time preprocessing execution — Stage 27.C

## Status

Stage 25 and Stage 26 are complete. Stage 27.A and Stage 27.B are accepted;
their sampling/window implementations and numerical semantics are unchanged.
Stage 27.C integrates those plans into preprocessing and passes all 40 acceptance
criteria with the authorized local-PoC correction. Stage 27 is complete.
Stage 28 contact episodes, lifetime, and publication protein-edge tables are
next and have not started. Dataset v1.0 remains unreleased; its frozen scientific
contract is unchanged. Concrete NAMD condition labels remain unresolved.
The 95% exclusion policy remains Stage 32. WANIA is unchanged and FastAPI remains
postponed.

## Legacy and Dataset execution

`mania preprocessing run-graph-export` retains its existing flags. For a legacy
manifest, `frame_start`, exclusive `frame_stop`, `frame_stride`, and `max_frames`
behave as before. There is no additional time-axis pass or temporal artifact.

If any condition has Dataset context, all global legacy controls must be at
their exact defaults: `0`, `None`, `1`, `None`, respectively. A conflict exits 1
before planning/science with `Physical-time sampling configuration failed:`.
This also applies to mixed manifests: Dataset entries use physical selection,
and legacy-only entries use their default all-frame behavior. Dataset parameters
are never copied to legacy conditions.

```text
requested Dataset context (Stage 26 binding by exact replica_key)
  -> actual source time axis, collected once per Dataset condition
  -> accepted 27.A sampling plan
  -> accepted 27.B window plan
  -> exact enumerated source indexes used by existing Rg and contacts
```

The runtime lookup and source-index map use the legacy execution condition only
after authoritative Dataset binding. They do not look up Dataset table rows by
condition and do not infer scientific condition labels.

## Actual source times and exact execution

The dedicated planning pass enumerates the loaded trajectory and reads only
actual `timestep.time` in ps. Enumeration supplies zero-based source indexes;
the timestep's internal frame number is not consulted. Missing, raising,
non-numeric, non-finite, or negative time metadata fails planning. There is no
fallback to manifest `frame_time_ps`, index times dt, requested stride, topology,
or filenames. Non-increasing times fail through the accepted 27.A resolver.

`iter_selected_trajectory_frames` requires a non-empty tuple of strictly
increasing non-negative integer indexes, rejecting booleans and duplicates.
It enumerates once, preserves source indexes, stops immediately after the final
selected frame, and raises if the source ends early. It does no time matching,
random access, sorting, or file access. Condition APIs reject explicit indexes
together with an explicitly supplied legacy sampler. Manifest APIs reject
unknown routing keys and retain manifest result order.

For each Dataset condition with both scientific targets enabled, execution has
three conceptual passes: time-axis planning, existing Rg, existing contacts.
Window planning consumes the sampling plan only and adds no trajectory pass.
Legacy conditions retain two scientific passes with no additional planning pass.

## Requested and effective evidence

Successful Dataset execution writes `<output>/temporal_execution.json`:

| Field | Contract |
| --- | --- |
| `schema_version` | `mania.preprocessing_temporal_execution.v0.1` |
| `kind` | `mania_preprocessing_temporal_execution` |
| `status` | `complete` or `partial`, derived from nested plans |
| `bindings` | Non-empty ordered list of unique execution conditions and replica keys |

Each frozen binding contains `execution_condition`, the full `dataset_spec`,
`sampling_plan`, and `window_plan`. All requested plan fields must equal the
Dataset temporal request. Failed plans cannot appear in a successful record.
Window source membership and effective bounds must correspond to the sampling
plan. Source paths and duplicate routing maps are not serialized.

`resolved_configuration.dataset_context` in provenance remains the requested
identity/temporal contract, including its Stage 26 binding source. It is never
replaced by effective values. The dedicated temporal artifact records selected
source indexes, actual observed bounds, missing requested targets, coverage,
and full requested windows with their selected/missing membership.

Partial sampling/window coverage may proceed using resolved frames. Exact
missing points and partial status remain recorded. There is no automatic
trajectory exclusion or 95% threshold in Stage 27.

## Stage 28 boundary and PBC

Windows are execution metadata in Stage 27. They do not partition scientific
contact aggregation. Existing contacts aggregate all physically selected frames
with unchanged cutoffs, distances, contact types, and edge weights. Changing
only window length/step/overlap must leave current scientific artifacts identical.
There are no per-window contact tables, occupancy, episodes, or lifetime metrics.

PBC observations attach to the selected Rg pass when enabled, otherwise contacts,
and never both. Planning reads no box dimensions and emits no PBC observations.
PBC sampled counts equal physical selected sample counts for Dataset conditions.
The runtime metadata adapter uses these same counters unchanged.
`mania_internal_minimum_image_correction_applied` remains `false`, and
`scientific_pbc_status` remains `unresolved`. Technical acceptance does not
establish scientific PBC correctness or Dataset publication readiness.

## Persistence, integrity, and validation

After successful scientific workflow execution, the CLI atomically writes the
temporal artifact before runtime metadata, PBC audit, inventory, and provenance.
JSON is UTF-8, indent 2, declaration order, non-ASCII preserving, rejects NaN,
and has one trailing newline. Atomic publication respects overwrite protection.

Inventory adds exactly `output:temporal_execution`, role `temporal_execution`,
path `temporal_execution.json`, format `json`, condition `null`, before runtime
and PBC outputs. It inspects only the supplied successful path. Mode `none`
records exact size without hashing; `sha256` uses the existing bounded streaming
helper. Provenance references the same portable role/path. Generic inventory
and provenance schemas remain unchanged and have no checksum cycles.

Unified preprocessing validation strictly reconstructs every nested model
without trajectory access or rerunning either planner. Completed Dataset
provenance requires exactly one temporal output and reference. Legacy provenance
requires neither. Ordered execution bindings and full Dataset specs must agree
with requested context. Temporal/PBC sample-count mismatches are technical errors.
The existing integrity gate still precedes specialized validation. Analysis has
no temporal role or temporal propagation in this stage.

## Failure behavior

Source collection failures, failed plans, and inconsistent temporal contracts
exit 1 before science with `Physical-time execution planning failed:`. Resolved
Dataset context and a used parameter table remain in best-effort failed
provenance/inventory when authoritative inputs are available. No successful
temporal/scientific output is invented.

A temporal write failure after science uses `Temporal execution write failed:`,
retains scientific outputs, attempts existing runtime/PBC/inventory/provenance
handling, exits 1, and suppresses the successful summary. Inventory and provenance
claim the temporal artifact only after successful publication. A completed
scientific passport missing required temporal evidence fails the full technical
gate, even if the science itself finished. Ordinary failed-science exceptions
retain the established successful-output boundary.


## Stage 27.C acceptance evidence

Acceptance was run from the Stage 27.B checkpoint
`43e2d8f6297e9f5df7e6fba958c099ac0066707d`, preserving the accepted 27.A/27.B
implementations and the frozen Dataset scientific contract.

The real local NaPi2b PoC uses actual source times 0–10000 ps across 1001 frames.
Its accepted frame-based selection `500,505,...,1000` corresponds to **5–10 ns
with a 50 ps stride**. The earlier 50–100 ns / 500 ps request was based on an
incorrect local time-axis assumption and correctly failed before science. The
corrected values are local acceptance controls only; they do not redefine future
100 ns Dataset production intervals or tracked production parameter tables.

Strict temporal reading verified both `normal` and `tumor`: 101 requested and
selected samples, zero missing, coverage 1.0, complete status, exact source
indexes `500,505,...,1000`, and actual effective bounds 5000–10000 ps. A 5 ns
window with 2.5 ns step and 50% overlap yields exactly **one full `[5,10]` window**
with the right production endpoint included. It has no partial or empty windows.
The synthetic 50–100 ns / 5 ns / 2.5 ns **19-window regression remains unchanged**.

All 12 deterministic preprocessing and all 17 downstream PCA-enabled analysis
artifacts are byte-identical to the accepted Stage 25.G frame-based outputs and
the original NaPi2b baseline. Both mapped unified gates pass with `complete: true`
(six preprocessing inputs including the Dataset table; nine analysis inputs).
PBC observes 101 frames per condition, internal minimum-image correction remains
false, scientific status remains unresolved, and external preprocessing remains
undeclared. Runtime metadata records 202 sampled/contact frames.

Real inventories use checksum mode `none`; no raw trajectory is SHA256 reread.
Controlled SHA256 tests verify temporal digests and same-size mutation rejection
before specialized validation. Instrumented synthetic execution confirms one
planning pass plus one Rg and one contacts pass; PBC attaches to one scientific
pass and windows add no trajectory pass. Changing only windows leaves all 15
synthetic scientific files byte-identical. The legacy checkpoint comparison
preserves all 20 controlled outputs and stdout/stderr exactly.

The focused suite passes with 1061 passed and 2 skipped. Full pytest passes with
5260 passed and 22 skipped; Ruff and mypy pass, and both version commands report
`mania-wania 0.1.0`. The prior wheel build/install/outside-checkout smoke is reused
after verifying all production files unchanged during the acceptance correction.
No occupancy, contact episodes, lifetime, per-window contacts, scientific schema,
analysis science, dependency, or WANIA change is included. Stage 28 is next and
has not started.
