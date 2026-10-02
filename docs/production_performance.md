# Production performance measurements

The performance checkpoint starts at `egor-production-v2`, commit
`3f001f5e3dae61df2a2177ab97cd3481f8d8decb`. It is separate from scientific
stage development. Neither production tag is moved, and the full 5–100 ns
trajectory is not rerun.

Use the accepted real `namd_egor_wt_0ss_r1` prepared input with its explicit
5–8 ns technical manifest. The required temporal result is 16 selected samples,
two inclusive windows [5,7] and [6,8] ns, 11 samples per window, and six shared
samples. Preparation is excluded from the benchmark. All existing input
authority, completion, inventory, replay and strict validation checks remain
enabled.

## Developer helpers

Run each measurement in a separate process and a new output directory:

```bash
PYTHONPATH=src python tools/profile_production_performance.py \
  --mode plain --evidence "$EVIDENCE/baseline_1" -- \
  production run --catalog "$CATALOG" \
  --trajectory-id namd_egor_wt_0ss_r1 \
  --output-root "$OUTPUT_ROOT" --input-binding "$INPUT_BINDING" \
  --technical-manifest "$TECHNICAL_MANIFEST" --min-free-bytes 21474836480
```

`MANIA_DATA_ROOT` must point to the verified input root. Use an existing
environment containing the project dependencies; `PYTHONPATH=src` selects
the isolated checkout's source. Keep the machine and environment constant.
Run at least two fresh `plain` measurements before optimization, followed
by separate `coarse` and `cprofile` runs. A warm-up is optional when technical
execution is costly. Do not run the full test suite during measurements.

The helper rejects `--resume` and an existing output root. `plain` adds no
function hooks. Its `perf_counter` and process CPU measurements cover CLI
dispatch through final completion; interpreter/import startup is excluded.
Wrap the command with `/usr/bin/time -v` to also measure whole-process wall
time, CPU and peak RSS. `resource.ru_maxrss` is recorded in KiB on Linux.
Output size includes every regular file in the new output tree.

`coarse` installs temporary wrappers around existing functions, preserving
their arguments, return objects and exceptions. Nested timings are exclusive
for additive wall accounting; inclusive times are also retained. The residual
is explicitly labeled uninstrumented. Canonical and annotated transformations,
source writing, persistence, rereading, replay, validation and hashing remain
separate where real function boundaries exist. Shared per-frame construction
and persistence are reported together instead of assigning fictitious per-layer
boundaries. Hash scan bytes count repeated logical full-file reads, not physical
disk traffic. DCD coordinate bytes count requested coordinate payloads, excluding
headers and cell records; filesystem cache effects are not inferred.

`cprofile` uses standard-library `cProfile` and `pstats`, retaining the binary
profile and cumulative/self-time rankings with source locations and call counts.
Python call events are retained; builtin events and caller/callee edge recording
are disabled to limit profiler overhead. Builtin work is charged to its Python
caller, so self-time is interpreted with that explicit limitation.
It is diagnostic evidence and is never used as the primary before timing against
an unprofiled optimized run.

Compare complete technical trajectory roots with:

```bash
python tools/compare_production_performance_outputs.py \
  "$BASELINE_TRAJECTORY_ROOT" "$OPTIMIZED_TRAJECTORY_ROOT" \
  --report "$EVIDENCE/scientific_parity.json"
```

This comparison requires the protein, lipid, glycan, temporal, completion,
canonical, annotated and graph artifacts. Scientific CSV text and deterministic
JSON bytes must match. Every nonidentical JSON/CSV is compared field by field.
Only enumerated current-run metadata and identical relative output paths may
differ. Changed sizes or hashes require verification against actual referenced
files that independently passed the comparison. Missing files, removed fields,
changed scientific counts and unexplained serialization changes fail closed.
This audit supplements the production engine's strict validation and offline
replay; it does not replace either.

## Acceptance and evidence

Keep reports under `local_md/mania_performance_v1_<UTC>_<uuid>/`. Record the
source SHA, environment, exact commands, baseline repeats, coarse/function
profiles, peak memory, output sizes, parity classifications, replay/validation
and regression outputs. Archive the compact evidence separately from input
trajectories and full output trees.

Only a measured significant hotspot can authorize an implementation change.
At most two allowlisted source files may change. One dominating hotspot calls
for one optimization. Reject changes with scientific mismatches, weakened
integrity, uncontrolled memory growth or disproportionate complexity. Report
mean/median times and variability from two fresh optimized repeats. A useful
target is approximately 20% walltime reduction; scientific parity is mandatory
at any speedup.

The accepted full-production reference is 91335.52 s launcher walltime,
1935.77 s preparation, 39.16 s confirmation and 10.81 s validation. Embedded
`preprocessing_graph_export` time is 50888.453344 s for 476 samples and 2704881
contact observations. The difference between launcher and embedded timings
is unassigned until measured evidence supports an explanation. Technical
speedups must not be presented as measured full-production speedups.

## Measured Phase A result

The real 5–8 ns plain command wall times were 1652.408751 and 1660.499429 s
(mean/median 1656.454090 s). Peak RSS was 885552 and 893424 KiB. Both runs
completed fresh science with `reused=false`. The coarse run took 1684.056258 s
inside CLI dispatch; measured exclusive boundaries account for 99.964% of it.

| Coarse boundary | Exclusive seconds | Percent | Calls |
|---|---:|---:|---:|
| Lipid geometry, `compute_protein_lipid_contacts` | 628.998725 | 37.35 | 16 |
| Protein geometry, `_compute_contact_frame` | 527.727666 | 31.34 | 16 |
| Annotated protein table construction | 196.546266 | 11.67 | 2 |
| Production input/output digest function | 60.636081 | 3.60 | 56 |
| Strict validation, excluding separately timed children | 56.133883 | 3.33 | 1 |
| JSON parsing | 34.848450 | 2.07 | 1648613 |
| Artifact inventory digest function | 29.322281 | 1.74 | 60 |
| DCD coordinate-read wrapper | 6.463196 | 0.38 | 1169 |

The separate cProfile run took 3341.604277 s whole-process wall, including
1364.926659 cumulative seconds in lipid geometry and 1059.073038 in protein
geometry. The lipid distance generator recorded 3130696320 call/resume events.
Those diagnostic times include profiling overhead and are not before/after
benchmark times. Baseline repeat, coarse and cProfile outputs each pass the
complete 26-file comparison: 20 files are byte-identical, with zero unexplained
field differences in the remaining six.

There is one DCD reader construction and four physical reopen operations.
Temporal resolution reads the full 1000-frame axis. Protein traverses 80 frames
to yield the 16 selected samples; lipid and glycan share a second such traversal.
The coarse wrapper records 1168 successful next-timestep reads and one failed
end-of-axis attempt, plus the constructor's separate initial read outside that
counter. Coordinate reading is not a leading optimization candidate.

Repeated input SHA256 scans account for 30308164032 logical bytes and 91.473678 s.
Derived-output scans account for 112177059 logical bytes and only 0.345033 s.
These figures do not measure physical disk traffic or explain the unmeasured
full-production timing residual. Repeated canonical-reference reconstruction
beneath annotation is material, but its modules are outside this task's source
allowlist and remain unchanged.

## Exact lipid rejection

The only implementation change is conservative heavy-coordinate bounding in
`preprocessing/protein_lipid_contacts.py`. After all original heavy-atom
validation, six axis extrema are retained per protein residue and whole lipid
molecule. A pair is rejected only if an axis proves that every atom-pair distance
exceeds the inclusive 6.0 Å cutoff. Every remaining pair uses the original
exhaustive `math.hypot` minimum, atom order and observation construction.
Evaluated-pair counts, molecule membership and all downstream schemas remain
unchanged. There is no internal MIC or precision reduction.

Bounds are used only for exact native floats with finite four-times-coordinate
values. This excludes mixed integer/float subtraction, whose rounding may differ
from integer bounds, and extreme coordinates that could produce a nonfinite
minimum. Those inputs retain the original calculation and error behavior. In
the bounded domain, each coordinate magnitude is at most max-float/4, each
component difference is at most max-float/2, and the three-dimensional norm is
at most sqrt(3)/2 of max-float, hence finite. Monotone float subtraction makes
the axis separation a conservative lower bound.

Auxiliary storage is six bounds per residue/partner for the current frame.
Worker count, batching, trajectory passes and retained-frame policy do not
change. Regression cases cover seeded exhaustive oracles, exact distance bits,
all cutoff-axis directions, mixed large integers/floats and extreme finite
coordinates with both finite and nonfinite original minima.

## Accepted technical performance and parity

Two fresh optimized plain runs completed through the unchanged native strict
validation and offline replay path. Neither run used completed-result reuse.

| Run | Whole-process wall s | CPU s | Peak RSS KiB | Output bytes |
|---|---:|---:|---:|---:|
| baseline_1 | 1652.408751 | 1651.041370 | 885552 | 37418754 |
| baseline_2 | 1660.499429 | 1658.719263 | 893424 | 37418752 |
| optimized_1 | 1074.479418 | 1071.841968 | 893180 | 37418760 |
| optimized_2 | 1090.428846 | 1084.654692 | 887780 | 37418760 |

Mean/median wall time changes from 1656.454090 to
1082.454132 s: 573.999959 s saved,
a 34.6523% reduction and 1.5303× speedup.
The optimized repeat spread is about 1.5%, versus about 0.5% for baseline;
the improvement is substantially larger than either spread. Both optimized
RSS peaks fall within the measured baseline range. There are no workers,
retained coordinate batches or added dependencies.

Both optimized outputs pass all 26 artifact comparisons, including 20
byte-identical files and all 19 deterministic scientific artifacts. Each run
has exactly 21 accepted field differences: seven output-root paths, two
timestamps, two runtime timings and ten independently verified dependent
hashes/sizes. No scientific CSV differs. Output size changes by only 6 or
8 bytes from the respective baseline totals, fully accounted for by these
current-run fields. Completion, temporal identities, protein/lipid/glycan
observations, source/canonical/annotated tables, graph data, occupancy,
episodes, lifetimes, distances and coverage are unchanged.

Independent offline replay of baseline and both optimized outputs exactly
reconstructs all three source window tables. Trajectory/topology file access
and MDAnalysis imports are blocked during that replay, with three explicit
guard canaries. The native strict validator also reconstructs canonical and
annotated results. Detailed validation reports and test outputs accompany
the evidence bundle.

Only one implementation optimization is retained. Benchmarks ran before
the final local commit; separate frozen and optimized source SHA256 inventories
and the implementation diff bind the measured working trees to the change.
The full 5–100 ns trajectory was not rerun, and this technical speedup is not
a measured full-production speedup. The full-production timing residual and
approximately 12.7 GB full-run RSS remain reference observations, not new
measurements. No production tag or remote branch is changed.

## Verification result

Focused checks: 241 passed. Broader contact/temporal/persistence/replay/canonical/
annotation/production regressions: 4137 passed across 78 files. Full pytest:
10519 passed, 22 skipped, 1380 warnings in 1210.26 s. Full-suite warnings and
skips are retained in the evidence log. Ruff reports `All checks passed!`; mypy
reports `Success: no issues found in 189 source files`. The existing version,
example configuration and plan-only CLI commands also pass.

Independent native validation of the baseline and optimized output each passes
26 specialized validations, with zero errors and zero unsupported artifacts.
Both memory measurement mechanisms agree on all four plain-run RSS peaks.
Profile line numbers refer to the frozen baseline commit; source hash inventories
identify both measured implementations. There are no remaining task TODOs.
