# Egor raw input preparation and confirmation

`tools/prepare_production_inputs.py` prepares **one explicitly selected** Egor
trajectory and, in a separate operation, materializes its reviewed production
binding. Use the installed MANIA environment with its existing optional
MDAnalysis dependency and the two adjacent tool files from this checkout.
No new dependency, catalog edit or manual JSON editing is needed.

The supported selections are `namd_egor_wt_{0,1,2}ss_r{1,2,3}` (choose one literal
ID). This implementation is verified with synthetic fixtures only. Real 0SS/r1
clean-environment preparation and real 1SS applicability remain the next task.

## Inputs and roots

Extract the reviewed nine-trajectory handoff as `DATA_ROOT/egor_handoff/` and
supply the selected replica's raw bundle and shared reviewed toppar at their
explicit package paths. Supply PSF, CONF, OUT, XSC and DCD; do not substitute a
different replica's files. The package's `HANDOFF_FILES.sha256` is verified,
including catalog, source inventory, templates and each system's own controls.
The package must be complete and immutable. Its Python helpers are never executed.
Checksums establish consistency with the supplied package; obtain that authority
package through the reviewed handoff, since checksums are not signatures.

`--authority-package` explicitly selects the extracted package. The established
`egor_handoff/` mount in its bindings is rebased to that directory, which must be
below `--data-root`. Other file bindings remain relative to the data root.
The supplied package already distinguishes a delivered filename from the literal
CONF/OUT DCD declaration; both are checked. No suffix search or filename inference
occurs. A new delivery path not present in the reviewed package requires a revised
explicit authority binding; this tool does not infer one.

`--result-root` is a new, exclusively claimed directory **below the data root**,
outside the package and all selected source directories. This location is required
because the existing production binding permits scientific inputs only below
`MANIA_DATA_ROOT`. Raw files are read only. The tool rejects existing result
directories and symlink output paths. `--production-output-root`, supplied at
confirmation, is disjoint from the data root and is used in the printed commands.

## Prepare

For example, with shell variables set to explicit site paths:

```bash
python tools/prepare_production_inputs.py prepare \
  --data-root "$DATA_ROOT" \
  --result-root "$DATA_ROOT/prepared/0ss_r1_attempt_001" \
  --authority-package "$DATA_ROOT/egor_handoff" \
  --trajectory-id namd_egor_wt_0ss_r1 \
  --min-free-bytes 12000000000 --workers 1 --threads 1
```

The byte budget is a site choice, not a reservation. The guard requires the larger
of that budget and a full all-atom DCD estimate (`frames * (12 * atoms + 8192) +
1 MiB`, including audit allowance). Available disk can change during writing;
write failures stop the attempt. This version exposes the accepted serial profile
only: one worker, one transformation/library thread, one frame in flight, one
ordered writer. The CLI sets library thread limits before importing numerical
modules. Coordinate memory does not grow with frame count; time-control arrays
retain the complete axis required by the existing contract. No parallel speedup
or real-system performance claim is made.

The implementation migrates accepted 0SS/r1 D.4e.3 `FragmentPreparation` and the
per-frame audit from `prepare_input.py`. It retains the accepted batched
orthorhombic `make_whole` early-return predicate, standard `make_whole` for other
fragments, protein geometry centering, and complete-fragment COG wrapping. It
compares the batched operations with standard MDAnalysis operations at the first
and last frames and exact catalog start/end times when present. No algorithm,
contact cutoff or internal MIC policy is changed. Historical files document the
migration; they are not runtime dependencies.

Every source frame receives finite coordinate/time, valid positive cell,
bond representation, atom lattice lineage, protein centering and complete-fragment
center checks. Accepted tolerances remain 0.001 Å for representation checks,
`[-1e-6, 1+1e-6]` for fractional fragment centers, `1e-5` for reopened cells
and `1e-6 ps` for reopened raw time. All persisted float32 coordinate hashes
must match exactly by frame and atom index. Topology bonds may not be guessed.
Each system uses its own PSF, element definitions, annotations, mapping and partner
metadata; no 2SS atom or partner indexes are copied to 0SS/1SS.

Actual raw and reopened observations use `observe_dcd`. Both strict controls use
`derive_time`, `TimeControl`, `validate_time` and the existing CONF/OUT authority.
The derivative retains the full atom/frame/header/raw-time axis, and the prepared
runtime is checked with `apply_namd_authority`. XSC is bound endpoint evidence;
it is not used to invent per-frame cells. Every cell is read from the DCD.

Successful preparation prints JSON with `status=pending_review`, a report path,
its SHA256, and a readable summary path. Inspect `summary.txt`, `report.json` and
the referenced per-frame evidence. No production binding exists yet.

## Confirm and materialize the binding

A reviewer must check the raw DCD's correspondence to the PSF and selected run,
the report, and the limitations. DCD has no atom labels: indexed raw-to-prepared
lineage cannot independently prove the original raw atom order matches the PSF.
Automatic technical checks never claim that a human performed this review.

Use the SHA256 printed by **that** preparation after inspecting its report:

```bash
python tools/prepare_production_inputs.py confirm \
  --data-root "$DATA_ROOT" \
  --result-root "$DATA_ROOT/prepared/0ss_r1_attempt_001" \
  --authority-package "$DATA_ROOT/egor_handoff" \
  --trajectory-id namd_egor_wt_0ss_r1 \
  --report-sha256 "$REPORT_SHA256" \
  --reviewer "$REVIEWER" --review-note "$REVIEW_NOTE" --approve \
  --production-output-root "$PRODUCTION_OUTPUT_ROOT" \
  --min-free-bytes 12000000000
```

`--reviewer` and `--review-note` must be explicit, nonblank values. The tool records
the supplied name as an external attestation; it does not authenticate the person.
The confirmation binds the exact report digest and every input/output digest.
Before accepting it, the tool rechecks the package, raw files, generated files,
completed operation, strict controls, selected row and UTC ordering. A failed or
incomplete technical attempt cannot be approved. Changed bytes, even whitespace
in the report, invalidate the original confirmation digest.

The existing handoff `SiteReview` model is migrated without changing its fields.
`PreparedLineage` and `ProductionInputBinding` come from `mania.production_run`.
Reviewer identity and the exact report hash enter the lineage; the report remains
an immutable automatic report with no fabricated human-review field. Confirmation
records no final QC decision and prints `trajectory_pbc_qc_certified=false`.

The returned JSON includes the concrete binding path and two shell-quoted existing
commands: `env MANIA_DATA_ROOT=... mania production validate ...` and
`env MANIA_DATA_ROOT=... mania production run ...`. Both use the package catalog,
selected trajectory, new binding and separate production output root. This tool
prints those commands; it does not launch production, contacts, final QC,
aggregation or publication.

## Artifacts, errors and integrity

```text
RESULT_ROOT/
  request.json              selection, roots, input/package hashes, resources
  elements.json             existing element control with explicit absolute paths
  raw_time.json             actual raw observation plus strict time authority
  prepared.dcd              complete externally prepared trajectory
  prepared_time.json        actual reopened observation plus strict time authority
  frame_audit.jsonl          raw/prepared indexes, times, cells, hashes, errors
  reopened_audit.jsonl       actual persisted coordinate/cell/time observations
  report.json               automatic checks, limitations, all artifact identities
  summary.txt               short readable checks/failures/limitations
  operation.log             preparation output, warnings and failure traceback
  phases.jsonl              phase and frame progress with UTC timestamps
  operation.json            exact command, timestamps, elapsed duration, exit code
  complete.json             hashes of the completed report and operation evidence
  confirmation/
    confirmation.json       named explicit approval bound to all hashes
    site_review.json        existing strict site-review contract
    production_input_binding.json
    commands.json           concrete existing production validate/run commands
    operation.log
    phases.jsonl
    operation.json
```

An operation error exits 1; argument errors exit 2. Failures preserve partial
files and logs, never a preparation completion marker or successful binding.
Result directories and confirmation directories are exclusively claimed; no
overwrite or mid-calculation resume exists. Preserve a failed attempt and select
a new result root for a fresh preparation. No timestamps, observations, hashes or
success flags should be edited to repair an attempt. A backwards UTC clock fails
clearly; stabilize UTC/NTP before a new attempt. Existing MANIA clock guards are
unchanged. Embedded generated control paths are absolute: moving inputs after
preparation requires a fresh preparation/binding at the final site paths.

## Verification

The new tests use tiny synthetic DCDs with four complete frames, distinct system
atom counts and partner indexes, and all nine selections. They exercise actual
fragment preparation and reopened reading, explicit confirmation, strict binding,
public `production validate`, and a standalone copy of only the two tool files.
They do not use real trajectories, historical directories or runtime developer
hooks. Failure tests cover changed identity, missing approval, partial writes,
output protection, disk/path guards and clock order. Existing NAMD and production
binding tests remain the contract reference. No full pytest run is required for
this scoped task.
