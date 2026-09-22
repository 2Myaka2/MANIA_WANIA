# Stage 34.B NAMD input authority

This continuation supplies two explicit, bundle-specific controls and a bounded
readiness helper. It does not execute the real pilot. The 2026-09-22 inspection
accepted 58 direct and 39 independently reviewed assignments, covering all 97
used PSF types. Overall real readiness remains **BLOCKED** because no reviewed,
PSF-bound NAMD canonical mapping was supplied. Stage 34 remains in progress and
`scientific_pbc_status = unresolved`.

The source identity supplied by the user is NAMD, WT NaPi2b, 2SS
(C303–C350 and C322–C328), replica 1, PMm, with FA2G2S2 at Asn295 and Asn308,
and a declared 100 ns production duration. No broader Dataset condition label
is assigned. All real source files remain under the ignored local data root.

## Controls and source review

`mania.preprocessing.namd_authority` strict-reads versioned JSON, rejects extra
fields and duplicate keys, verifies source hashes, and checks exact type counts
against the bound PSF. The entire supplied `.rtf`, `.prm`, `.str`, and `.crd` set
is inventoried. Every used type retains all original MASS records, including
compatible repetitions. Direct element tokens are distinguished from atom-type
keys: original `CL` is carbon, `CLA` is chlorine, and `SOD` is sodium. Only
element tokens are normalized for CHARMM capitalization; type lookup is exact.

The 39 assignments lacking element tokens require a separately authored,
accepted review with exact original source lines and chemical rationale.
The helper never accepts the proposal table as review authority. In this
inspection, protein RTF chemical definitions and residue/patch usages support
all 39. The shorter hydrogen descriptions were checked against complete residue
diagrams and bonds, including ALA, ASP, ILE and HSD; CT2A was checked against its
explicit CT2 derivation and ASP topology; SM was checked against DISU. All
compatible parameter-file definitions are retained. Mass discrepancies for
O/OC/OH1 and SOD are evidence only. Neither names nor masses assign elements.
The initial PDB has 439,436 blank element fields and is **not element authority**.

The time control binds config/log SHA256 identities and the DCD path, size,
header and bounded raw timing observations. It supports one literal production
configuration and rejects unsupported dynamic/multiple-run timing. It verifies
the actual ordered coordinate-write sequence, not merely its count. The real
2 fs timestep and 50,000-step output frequency give exact Decimal step-derived
times of 100 ps at frame 0 and 100,000 ps at frame 999. Raw reader timing is
retained separately, including observed `dt = 100.00000029814058 ps`.
No full DCD hash or full coordinate traversal is performed.

## Execution boundary

`load_single_condition_runtime(runtime_input, namd_authority=NAMDControlPaths(
elements_path, time_path))` is the only production integration. Callers must
explicitly pass both controls on every new load. It disables guessing on that
path, validates both controls before attachment, and rejects a conflicting
existing element attribute or legacy `frame_time_ps` override. A single DCD
reader exposes absolute indexed scientific times through an ordinary
MDAnalysis trajectory transformation. Repeated, random, sequential and reopened
reads see the same times, including later Stage 27/28 consumers. The reader's
raw `dt` remains evidence; consumers use `ts.time`.

The adapter must precede any geometry transformations. Reapplying it is rejected;
rewinding or reopening the existing reader retains it. Replacing a trajectory
with `Universe.load_new` is outside this adapter API: reopen through the explicit
loader with the controls. There is no global patch, fallback, filename trigger,
public CLI option, or GROMACS integration. The no-control loader path retains
its existing behavior. No accepted scientific formula or artifact schema changes.

## Bounded readiness helper

`tools/stage34b_namd_authority.py` accepts `--bundle`, `--reviewed-assignments`
and an ignored `--output-root` (default `local_md`). Each run creates a unique
authority evidence directory and sibling ZIP. `--evidence-directory` can name a
new, reserved directory that has no previous run summary. The review assignment
file is a JSON array of `ReviewedAssignment` records; it is specific to the
hashed source set and is not a universal type table.

The actual review ZIP was found inside `local_md/namd/egor_2ss_r1/raw`, rather
than the suggested `local_md/namd_authority` path. The helper verifies its PSF and
original toppar hashes without executing bundled scripts. Local PSF/DCD names
include `NPT`; original config/log names and the DCD title retain their original
spelling. That linkage, the supplied bundle, matching atom counts, finite bounded
coordinate reads, and log/header timing support correspondence. DCD itself has
no atom identity records. The log explicitly reconciles its active bond count
with the PSF through 111,066 ignored zero-force bonds.

Only real frames 0–4 and 999 are read. The last frame supports endpoint timing
and the matching final XSC box check. Initial equilibration XSC is not treated
as a production box. Stage 27 resolves the validated 1,000-record authority axis
and the future five-frame subset with zero missing points and zero time deltas;
this proof does not traverse the full coordinates. Tests also pass a synthetic
1,000-frame DCD through the actual loader and Stage 27 source-axis collector.

If a reviewed canonical mapping becomes available, supply it explicitly with
`--canonical-mapping` and `--mapping-psf-sha256`. The existing Stage 30 reader
and exact NAMD source identities must resolve all 690 residues unambiguously.
No mapping is inferred from equal residue numbers. Repository verification is
recorded separately after focused and full checks; standalone readiness does
not manufacture a regression PASS.

## Frozen subsequent pilot

The future pilot is this one NAMD replica, source frames 0–4, scientific times
100, 200, 300, 400, 500 ps, 0.1–0.5 ns inclusive at 100 ps stride. It remains
unexecuted while canonical mapping readiness is blocked.

The subsequent runner must revalidate inputs, perform independent NAMD Variant C
diagnostics, persist the five-frame prepared trajectory, run protein-only MANIA,
independently reconstruct Stage 28 results, and package evidence. Provisional
Variant C is bonded-fragment unwrap, protein geometry centering with
`wrap=False`, then complete-fragment wrapping with `center="cog"`. Diagnostics
must cover all topology bonds, both disulfides, both glycan branches, direct
versus periodic near-protein geometry, and actual per-frame DCD boxes.
The GROMACS diagnostic does not establish NAMD PBC acceptance. Complete element
authority does not establish specialized molecular partner correspondence.
No scientific execution command is supplied while this readiness gate is blocked.
