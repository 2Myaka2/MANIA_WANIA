# Stage 34.B NAMD input authority

This continuation supplies two explicit, bundle-specific controls and a bounded
readiness helper. It does not execute the real pilot. The 2026-09-22 inspection
accepted 58 direct and 39 independently reviewed assignments, covering all 97
used PSF types. That input-authority checkpoint was **BLOCKED** because no reviewed,
PSF-bound NAMD canonical mapping was supplied. Stage 34.B.2 below closes that
mapping gate with exact WT sequence evidence. Stage 34 remains in progress and
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
unexecuted in the mapping-only Stage 34.B.2 continuation.

The subsequent runner must revalidate inputs, perform independent NAMD Variant C
diagnostics, persist the five-frame prepared trajectory, run protein-only MANIA,
independently reconstruct Stage 28 results, and package evidence. Provisional
Variant C is bonded-fragment unwrap, protein geometry centering with
`wrap=False`, then complete-fragment wrapping with `center="cog"`. Diagnostics
must cover all topology bonds, both disulfides, both glycan branches, direct
versus periodic near-protein geometry, and actual per-frame DCD boxes.
The GROMACS diagnostic does not establish NAMD PBC acceptance. Complete element
authority does not establish specialized molecular partner correspondence.
The existing runners do not yet implement the complete NAMD five-frame workflow.
Input readiness does not establish an executable pilot command or PBC acceptance.

## Stage 34.B.2 canonical mapping authority

`tools/stage34b_namd_mapping_authority.py` is a standalone topology-only helper.
Run it with the accepted input evidence directory, using the existing environment:

```bash
.venv/bin/python tools/stage34b_namd_mapping_authority.py \
  --authority-evidence local_md/stage34b_authority_20260922T144226Z_e0bab9b6a6f64a998eb2e179785d60b8
```

It creates a unique ignored `local_md/stage34b_mapping_*` directory and sibling
ZIP. It rechecks the accepted PSF/control/source fingerprints and DCD header/size,
without coordinates, an element/toppar re-audit, or network access. Prior box and
runtime evidence is referenced by path/hash; no full DCD checksum is claimed.

The accepted PSF SHA256 is
`04b7bee588edf61bde25dfded24216ed4e0727d75d1e144356b500ecc89004bb`.
The actual `protein` selection contains 690 residues and 10,814 atoms, all in
segment `PROA`. Counts are extracted before testing full-length correspondence.
The source sequence exactly matches packaged Stage 30 O95436-1 sequence version
3, SHA256 `33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
There are no mismatches, indels, unresolved identities, or ambiguous placements.
Equal complete lengths and ordered identity at every position establish the
unique order-preserving bijection. Source residue numbers provide no authority.

Sequence comparison reuses the earlier real GROMACS preflight policy in
`local_md/stage34_start_ae1cafd/run_pilot.py`: standard amino acids plus
HSD/HSE/HSP as histidine. This explicit handling also covers HSP, which the
installed MDAnalysis conversion function does not recognize directly. Source
names remain unchanged. The real HSD residues are 220, 239, 253, 352, 358 and 491.

`namd_canonical_mapping.json` uses the unchanged strict Stage 30 model and I/O,
including its lexical source-key ordering and `source_chain_id = PSF segid`.
`source_protein_residues.csv` retains topology order, zero-based residue indexes,
one-based source/canonical sequence positions, exact source identity, status and
per-record authority. `psf_binding.json` binds the mapping digest, PSF path/hash,
protein counts, ordered identity signature and source/reference sequence digests.
The mapping JSON must travel with this binding; Stage 30 alone does not bind PSFs.
No earlier GROMACS mapping is overwritten or promoted over.

A second verification path parses the PSF NATOM records directly, independently
loads the packaged reference and checks every saved mapping row. Wrong PSFs,
changed residue order, missing/duplicate rows, duplicate canonical assignments,
wrong reference identities, unresolved names and nonexact WT sequences fail.
There is no permissive alignment fallback. The standalone WT checks do not
change Stage 30's accepted sparse/variant/many-source mapping semantics.

Previously recorded source atoms independently cross-check C303–C350,
C322–C328, Asn295 and Asn308 after mapping. The 2SS label remains user-authoritative
simulation metadata. CARA/CARB glycan partners remain separate and unmapped.

The evidence includes the mapping, binding, residue CSV, explicit sequence,
comparison/reference identities, strict and independent validation, topology
feature checks, accepted controls, readiness matrix, commands, Git state and
verification logs. Repository regression results must be recorded separately;
the standalone helper initially reports implementation verification pending.
Stage 34.B input readiness is **PASS** after repository verification. Stage 34.B
scientific execution is **NOT RUN** and Stage 34 remains incomplete. Source and
mapping authority close the canonical input-readiness blocker, while
the complete NAMD diagnostic/preparation/protein-only pilot runner remains
unimplemented. No future execution command is fabricated from the GROMACS tools.
No real scientific run occurred; `scientific_pbc_status = unresolved`.
