# Ramila GROMACS production interface

`ramila-production-v1` remains the frozen historical handoff. This implementation
branch adopts the common RMSD/handoff contract for future fresh attempts.
`ramila-production-v2` has not been created; real representative acceptance,
benchmarking and the v2 freeze are a separate checkpoint.

The supported unit is one existing Dataset trajectory. The five shell entry
points share `tools/run_ramila_gromacs.py`; no core scientific engine or optional
dependency boundary changes. `SOURCE_ROOT` contains the preserved WT/T330M
source trees. `OUTPUT_ROOT` is a separate writable filesystem with sufficient
capacity. These roots and the actual Git HEAD enter provenance.

The shared Dataset CSV/YAML remain byte-identical to the frozen Egor runtime
catalog, required by its existing acceptance test. Ramila source/readiness
observations live in its own tracked runtime authority and audit inventory. Only
the unchanged scientific Dataset specifications are consumed from the shared
snapshot; historical phase1 notes never supply current execution bindings.

```bash
./init_ramila_gromacs.sh "$SOURCE_ROOT" "$OUTPUT_ROOT"
./run_ramila_gromacs_one.sh "$SOURCE_ROOT" "$OUTPUT_ROOT" gromacs_wt_norm_r1
./run_ramila_wt_all.sh "$SOURCE_ROOT" "$OUTPUT_ROOT"
./run_ramila_t330m_all.sh "$SOURCE_ROOT" "$OUTPUT_ROOT"
./run_ramila_gromacs_all.sh "$SOURCE_ROOT" "$OUTPUT_ROOT"
```

Init requires all 12 final XTCs and the exact audited TPR/MDP/LOG sets. It shows
all mappings, requests reviewer, note and `Approve? y/N`, then computes hashes.
Approval covers `source_run_correspondence_only`. It is immutable. Reuse checks
all source bytes, exact mappings, runtime JSON controls and Git HEAD. A changed
source or version blocks continuation; use a fresh output root after a new audit
and review. Users never supply hashes. Ten XTCs are intentionally absent from the
local acceptance; their absence cannot be bypassed during normal init.

The authoritative final names are `md_repN_full.xtc` (WT, 100 ns) and
`t330m_repN.xtc` (T330M, 30 ns), in `VARIANT/CONDITION/replica N/`.
WT-TUMOR-r2 has preserved exception names: `mdrep2replacement.tpr`,
`production_fresh_100ns.mdp` and four `mdrep2replacement.part000N.log` files.
Its fourth LOG binds `mdrep2replacement_repair_to_101ns.tpr`, which is also
hashed. No absent checkpoints, energy files or alternate trajectories are required.
TPR and mdrun LOG establish runtime settings; discrepancies with MDP remain
provenance, without rewriting inputs or substituting historical phase1 sources.

Before heavy preparation, the runtime scans every native XTC header in source
order, checks atom count and every cell, resolves exact requested times and
applies accepted Stage 32 time QC. Duplicate or backward timestamps block.
An absent target remains missing: no interpolation, nearest frame, shift,
zero-contact frame or occupancy-denominator contribution. Missing targets break
contact episodes. Coverage below 95% fails; adequate honest gaps remain one run.
Owner-reported gaps (not verified local axes) are WT-TUMOR-r2 at
37.61–38.06 ns; T330M-NORM-r2 with 2,988 reported frames; T330M-NORM-r3 with
2,982 reported frames. Each delivered XTC is inspected independently.

Preparation decodes the complete source axis, unwraps bonded fragments, centers
on protein and wraps complete fragments, using the accepted generic preparation
implementation. It writes native XTC at precision 4, retaining atom/frame order,
physical times and framewise cells. Every written frame is reopened and compared
to ordered prepared coordinates, with maximum component error <=0.001 Å.
Contact execution uses internal MIC=false. Raw source trees are read-only; native
XTC reading avoids writing offset caches there. Verification scratch, prepared
coordinates and outputs live below the requested output directory.

Storage preflight derives its estimate from measured precision-4 frame size,
actual source bytes, atom/frame/sample counts, a float32 verification scratch,
estimated contact-output capacity and a 15% margin. Sparse science-output sizes
remain data-dependent. There is no fixed 100-GiB rule. Successful preparation
removes only its own verification scratch. Budget and observed free space are
saved. An interrupted preparation and its numbered attempt remain inspectable.

A per-trajectory `.active` directory prevents simultaneous ownership. Normal
exceptions release ownership; a killed process leaves the marker for inspection.
After confirming no process owns it, an operator may remove that empty marker;
the next run preserves earlier attempts and creates the next number. Never
remove or overwrite source approvals, completed results or incomplete attempts.
Fresh attempts attach the common C-alpha RMSD observer to the existing contact
pass and retain the two authoritative RMSD artifacts. Completed new-contract
reuse loads and validates the compact handoff seal; its retained preparation
evidence supports review even when the external prepared directory is unavailable.
Initial production still verifies exact source authority. Historical v1 science
markers are identified as legacy and preserved; the next new-contract run uses
a fresh numbered attempt. A new-contract science marker without a valid handoff
seal cannot be reused as completed.

Strict unified validation and exact offline reconstruction cover six source and
canonical protein/lipid/glycan CSVs. Per-frame observations and the completion
ledger are retained. Both specialized layers run with accepted cutoffs and
carrier/own-glycan exclusion. The main dynRIN graph remains protein-only.

The fixed production grid is 5–100 ns for WT (476 expected samples) and
5–30 ns for T330M (126), every 200 ps. Windows are inclusive, length 2 ns,
step 1 ns. No replica aggregation or Stage 33 publication runs here. Subsequent
production QC and any manual review must precede QC-derived aggregation; each
condition and variant retains its own three-replica group.

Developer acceptance is restricted to WT-NORM-r1 and T330M-NORM-r1:

```bash
python tools/run_ramila_gromacs.py run "$SOURCE_ROOT" "$OUTPUT_ROOT" \
  gromacs_wt_norm_r1 --technical --developer-representative \
  --developer-technical-subset
python tools/run_ramila_gromacs.py run "$SOURCE_ROOT" "$OUTPUT_ROOT" \
  gromacs_t330m_norm_r1 --technical --developer-representative \
  --prepared-directory "$FULL_T330M_PREPARATION"
```

The WT subset is explicitly not full production preparation. Both technical
runs remain `production_eligible=false`: 16 samples over 5–8 ns, windows [5,7]
and [6,8], 11 samples per window and six shared samples. They cannot establish
production QC, aggregation or publication eligibility.

## Biological annotation authority

`RAMILA_BIOLOGICAL_ANNOTATION_AUTHORITY = PENDING` for all four systems.
Actual sugar residues/attachments, actual SG–SG bonds and exact sequence identity
are topology observations. They are never promoted to a complete annotation.
No Egor annotation is transferred. Contact science and strict validation of
available canonical outputs remain separate from annotated-output readiness.

Required owner question:

> For the current Dataset/manuscript, please confirm the complete biological
> annotation for each of the four GROMACS systems
> (WT-NORM, WT-TUMOR, T330M-NORM, T330M-TUMOR).
>
> For each system, please specify:
>
> 1. all intended glycosylation sites;
> 2. the glycan identity/name at each site;
> 3. whether there are any other glycosylation sites intended for this system;
> 4. disulfide_variant_sites (studied/design positions, NOT the actual S–S bond pairs);
> 5. cysteine_variant_sites;
> 6. whether this list is complete_for_system for the current publication.
>
> Please also state whether the same annotation applies to NORM and TUMOR for each variant.
>
> After explicit confirmation, record the confirming owner as source/verifier
> (e.g. Ramila only if Ramila provides that confirmation).
>
> Actual S–S bonds observed in the TPR remain separate topology authority.

## Colab handoff and local freeze

The production tag is local only; this task never pushes. Transfer the supplied
`ramila-production-v1.bundle` with the handoff. Clone the public repository via
HTTPS, fetch that bundle, then check out the exact annotated tag before install.
This supplies the accepted local version without claiming it is on GitHub.
The quickstart includes those commands. Google's
[runtime-version FAQ](https://research.google.com/colaboratory/runtime-version-faq.html)
currently lists Python 3.12.13 and NumPy 2.0.2 for runtime 2026.07. The installation
proof uses a clean Linux Python 3.12 environment with NumPy 2.0.2 and the existing
`.[science]` extra; it does not claim an interactive Colab session was executed.


## Future common handoff contract

See [production RMSD and handoff](production_rmsd_handoff_contract.md) for the
frozen method, two artifacts, portable evidence registry, completion gate and
coordinate-free review/group interfaces. RMSD uses the exact already-loaded
prepared production frames, explicit canonical C-alpha mapping and the first
resolved requested production sample as its fixed reference. Missing requests
remain missing. Stabilization is excluded. There is no automatic drift classifier
or universal threshold; explicit scientific review supplies Stage 32 assessment.

Fresh preparation additionally records all-frame bonded representation error,
protein atom/fragment identity, centering and complete-fragment observations and
writes normalized `protein_integrity_observations.json`. Original
`preparation_complete.json` remains immutable. Scientific PBC protocol status
remains unresolved; technical observations do not imply trajectory-level QC PASS.
The source/time/contact/PBC algorithms and cutoffs are unchanged.

Fresh production retains exact original reports, normalized observations, source
binding/axis, source attestation, consumed MDP/logs, mapping, partner controls,
software/runtime identity, per-frame/source/canonical outputs, validation/replay
and inventories beneath the attempt root. Missing annotation/correspondence
scientific authority remains explicit. `handoff_complete.json` is separate from
`science_complete.json` and is written only after all mandatory compact bytes are
hash-bound and strictly valid. Technical runs retain `production_eligible=false`.

`--prepared-directory` remains the literal external preparation authority. It
must supply the new normalized evidence and complete frame observations; the
producer copies compact evidence into OUTPUT_ROOT without duplicating XTC/TPR
files or changing that directory. An old preparation lacking required observations
cannot masquerade as a completed new-contract handoff. Source/prepared coordinates
are not deleted. The default sole prepared XTC may remain in the attempt's
preparation directory, outside the compact handoff registry.

Normal subsequent validation, review, QC and canonical aggregation can use
OUTPUT_ROOT alone. Review writes a new `postproduction/attempt_*` record and does
not change the producer seal. Real representative acceptance and benchmarking
remain necessary before a Ramila v2 release; no v2 tag exists at this checkpoint.
