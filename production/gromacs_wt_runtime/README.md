# WT GROMACS source authority — pre-XTC checkpoint

This is a small, portable inventory for NORM/TUMOR × replicas 1–3 only.
`authority.json` records exact small-file paths, byte sizes, SHA256, TPR input
parameters, MDP text parameters, and all 31 supplied LOG command lines. Source
payloads are external. No GROMACS executable is required by the new launcher.

The six TPRs and six MDPs were re-read on 2026-09-29, along with 31 LOGs.
TPR parameters were extracted with `gmx dump -s <literal TPR> -sys -param`.
The parameter records imply 100 ns nominal production and 10 ps compressed
output cadence. They do not prove actual XTC frame coverage or completeness.
The requested analysis remains 5–100 ns inclusive, 200 ps stride, 2 ns windows,
1 ns step: 476 samples, 94 full windows, 11 samples/window if complete.

Five MDP/TPR discrepancies remain unresolved, one affected source set each:
NORM r2/r3 and TUMOR r1/r2/r3. In each, MDP specifies Parrinello–Rahman,
`tau-p=4`, `continuation=yes`; TPR specifies Berendsen, `tau-p=2`,
`continuation=false`. These observations do not establish why the files differ.
They block final run-parameter reconciliation/publication, not source-only
inventory or a correspondence-only approval. They do not authorize preparation.
NORM r1 LOGs additionally use `md_rep1_replacement` as the run basename; that
fact is retained separately and is not a sixth MDP/TPR discrepancy.

The previous lightweight-intake report was not located during this checkpoint.
Its reported five affected sets were independently re-observed. Only the
user-supplied TUMOR/r2 delivery name `TUMOR/replica 2/md_rep2_full.xtc` is
established. Five other delivered XTC names remain null/UNRESOLVED: a LOG run
basename is not evidence for a final concatenated delivery filename. Six-source
approval therefore fails closed until authoritative delivery evidence is added
in a reviewed future change. No user JSON editing is part of the workflow.

`mania.gromacs_source_attestation.v0.1` is separate from Egor's schema. It binds
XTC, TPR, MDP and every reviewed LOG to exact relative paths, sizes and hashes,
source root, reviewer/note, approval UTC, repository HEAD, runtime inventory and
payload checksum. Scope is exactly `source_run_correspondence_only`. It is a
local integrity record, not a cryptographic reviewer signature. No review of
PBC, prepared coordinates, contacts, time completeness or QC is implied.

The launcher hashes complete XTC bytes only after explicit six-source approval,
or when verifying an existing approval. It never decodes coordinates. Changed
inputs, paths, authority or HEAD require a fresh explicitly approved output;
an existing approval is never silently replaced. Interrupted approval writes
fail closed. Hashing checks file stability during each read; stop all source
writers/downloads before approval. Runtime checks use the repository's reviewed
authority as their trust anchor, not a user-entered expected hash.

The coordinate continuation boundary is the validated list of `SourceSet`
records returned by `discover`, with attestation identity when applicable.
Developer representative discovery is restricted to `gromacs_wt_tumor_r2`; it
checks metadata/existence only and creates no source approval. The next task
must audit real TPR/XTC headers and times, establish an approved PBC protocol,
measure a candidate writer, run the 5–8 ns technical contact test, and replay and
validate. None of those operations is implemented here.

Prepared storage format remains **OPEN**. Acceptance requires atom/frame order,
time and unit-cell preservation, correct PBC representation, re-opened coordinate
error, and measured Colab storage practicality. Do not convert to DCD for NAMD
compatibility, assume a 57.5 GB derivative is necessary, or silently accept a
second lossy XTC encoding. No raw/prepared/temporary capacity promise is made.
