# Stage 34.A: short real NORMAL specialised pilot

This formal Stage 34.A calculation uses only NORMAL source frames
`500,505,510,515,520`, at exactly `5000,5050,5100,5150,5200 ps`.
The prior PBC diagnostics are supporting evidence, not this calculation.
Stage 34 remains incomplete even when this pilot passes.

## Standalone execution and guards

The helper is `tools/stage34a_specialized_normal_pilot.py`; it is outside the
public MANIA CLI. Run from the checkout with the existing optional scientific
environment:

```bash
.venv/bin/python tools/stage34a_specialized_normal_pilot.py --repo .
```

It requires branch `FAIR`, ancestry of `develop` and accepted diagnostic SHA
`7ea24a51821f6dcfea1b152815a1183e097741b7`, and MDAnalysis 2.10.0. It preserves
existing files and creates a unique `local_md/stage34a_specialized_normal_*`
workspace and sibling ZIP. No dependency installation or Git mutation occurs.
Only these three helper/test/guide files belong to the repository change.

The only real inputs are `local_md/normal/topology.tpr` and
`local_md/normal/trajectory.xtc`. The required topology SHA256 is
`91a9fbbc6c1615095294acd349be3e7df0e0f37eb6329f877ada825efef4654f`.
The source XTC is recorded by path and byte size, never automatically hashed.
The low-level reader opens only the five exact frames, with in-memory offsets.
Actual times, finite coordinates, valid boxes, authoritative bonds and
unguessed elements must pass before preparation. No atom-name/mass hydrogen
heuristics are permitted. Ambiguity stops execution and retains evidence.

## Provisional external preparation

The unchanged accepted diagnostic function supplies Variant C:

1. Unwrap all topology-bonded fragments.
2. Center the whole `protein` selection with `center="geometry", wrap=False`.
3. Wrap complete fragments with `compound="fragments", center="cog"`.

MDAnalysis `XTCFile.write` writes all atoms in their original topology order.
It copies original native box vectors and actual times, using coordinate
precision `1,000,000 nm^-1` to keep quantization below the accepted representation
tolerance. The new XTC pairs with the unchanged source TPR. Its local indexes
`0,1,2,3,4` map explicitly to source indexes `500,505,510,515,520`.

The reopened trajectory must preserve identity, exact times and box dimensions.
Every persisted frame compares **all topology bonds** in direct prepared
coordinates against the corresponding raw periodic reference, using the accepted
`0.001 A` representation tolerance. Protein-connected, attached branches,
Asn295/Asn308 attachments and branches, and environment bonds are reported
separately. No universal chemical bond-length cutoff is applied.

The exact supporting archive, when present, is bound by path and SHA256:
`stage34_pbc_normal_20260915T120709Z_65b51f8f405441a790316e72ad9c9ff9.zip`.
No arbitrary latest-archive selection occurs. MANIA's PBC audit is preserved;
external preparation is described in separate provenance. Internal MIC remains
false and `scientific_pbc_status` remains **unresolved**.

## Explicit partner and mapping authority

The user declares both Asn295- and Asn308-linked glycans to be **FA2G2S2**.
Non-protein topology traversal from each unique carrier attachment defines the
whole glycan, with exact atoms, original residue names and first-sugar linkage.
Structural anchors are retained; carrier-to-own-glycan raw positives are excluded
from every ordinary proximity metric under accepted Stage 29 semantics. Other
protein residues can contact the same whole glycan.

The NORMAL pilot instruction explicitly supplies the membrane classes POPC,
POPE, POPI, POPS, PSM, CHL1 and CER160-containing connected components. These
names occur only in this standalone pilot policy. Every included molecular
component receives an explicit ID and complete atom/residue membership.
Disconnected equal-name molecules stay separate; connected multi-residue
CER160 components stay whole and retain their full original composition.
No unsupported GM1/GM3 biological label is assigned. TPR TIP3 H2O components and
single-atom sodium/chloride ions supply explicit non-partner evidence. Any
remaining component is ambiguous and stops the pilot.

The helper writes and strict-reads the accepted Stage 29 metadata model and
verifies the identified catalog against the inventory. It uses the earlier
NORMAL pilot's `local_md/stage34_start_ae1cafd/mapping/normal.json`, verifies its
earlier command/manifest binding and topology authority, strict-reads it and
requires complete unique coverage of all 690 protein residues. It never infers
canonical mapping from residue numbers. Existing protein-only artifacts are
hashed before and after the run.

## Accepted execution and independent checking

The accepted `mania preprocessing run-graph-export` workflow receives the source
TPR, prepared XTC, explicit partner metadata and reviewed canonical mapping.
Dataset physical-time controls are start/end `5.0/5.2 ns`, stride `50 ps`, and
one full `0.2 ns` window. It must resolve exactly five requested and five
selected samples, zero missing samples and coverage 1.0. Legacy frame sampling
is not used.

A child wrapper observes the actual accepted lipid/glycan function return values
during the CLI run and writes a JSONL trace. It returns the same objects without
changing arguments, functions, cutoffs, coordinates or results. This allows
comparison against actual production per-frame positives without another
production geometry pass.

The independent checker uses float64 NumPy coordinate subtraction, squared
distances and square roots for every protein residue and every whole partner.
It has no MIC and does not call production geometry or aggregation APIs. Lipid
and glycan cutoffs remain inclusive `6.0 A` and `4.5 A`; classification uses no
tolerance. Identity populations and counts must agree exactly. Float comparisons
use absolute tolerance `1e-12`, relative tolerance zero.

The checker reconstructs occupancy, requested-sample episodes, actual-time
mean/max lifetimes and positive-frame-only mean/minimum distances. Intentional
source stride preserves requested adjacency, a resolved negative breaks an
episode, and a single positive frame has lifetime zero. `gap_tolerance=0` and
accepted missing-sample semantics remain unchanged. Canonicalization must
preserve every common serialized source field exactly and match the explicit
protein mapping. No specialised `edge_weight` exists.

Unified preprocessing validation binds every input explicitly and must report
`passed`, `complete=true`. Neither technical validation nor independent agreement
grants scientific PBC approval. No Stage 31 aggregation, Stage 32 release QC,
Stage 33 publication, NAMD, TUMOR or full 33-replica run is performed.

## Evidence and verification

The ZIP contains source guards, frame mapping, preparation/identity/bond evidence,
strict partner metadata/catalog, full partner inventory, compact partner/anchor
review tables, independent positives and comparisons, accepted source/canonical
CSVs, MANIA raw-positive trace, technical validation with input bindings, PBC
audit, timings, warnings, Git state and exact commands recorded before execution.
Raw TPR/XTC and the prepared trajectory are excluded; prepared path/size/SHA256
are retained. The helper prints `SEND THIS ARCHIVE: <absolute path>`.

Run focused synthetic tests and the existing Stage 27/29/30/PBC regressions
before real execution, followed by full `pytest`, `ruff check .`, `mypy src`,
both MANIA version commands, MDAnalysis version, example config validation and
`git diff --check`. The optional `--session-commands` accepts the contemporaneous
session command ledger. `--verification-evidence` accepts successful command
records with their actual outputs. Without that evidence the helper leaves
acceptance pending repository verification, even if the calculation succeeds.

PASS proves consistency for this five-frame NORMAL representation and explicit
pilot metadata only. Remaining Stage 34 gates include a real three-replica group
(preferably T330M), real QC-derived availability/exclusion and aggregation,
authoritative specialised correspondence, and remaining multi-engine evidence.

## Current real execution result

The 2026-09-15 run at unchanged HEAD
`7ea24a51821f6dcfea1b152815a1183e097741b7` completed its technical and independent
checks successfully. Evidence workspace and sibling ZIP basename:

```text
stage34a_specialized_normal_20260915T131821Z_02b6678fd1cf41498b41a0085d2f4d7a
```

| Layer | Partners | Ordinary positive observations | Source rows | Canonical rows |
| --- | ---: | ---: | ---: | ---: |
| Lipid | 800 | 3873 | 968 | 968 |
| Glycan | 2 | 38 | 9 | 9 |

There were 48 raw glycan positives; all 10 carrier-anchor observations were
excluded. Asn295 contributed 12 ordinary positives/3 rows; Asn308 contributed
26/6. Exactly 117 membrane partners contacted the protein. Observed membrane
counts were POPC 260, POPE 180, POPI 64, POPS 60, PSM 32, CHL1 192, and 12
complete `ANE5AC:1+BGAL:2+BGALNA:1+BGLC:1+CER160:1` components.

All five persisted frames retained 551462 atoms, 150626 residues and 11 segments,
with exact time/box identity. All 402644 bonds per frame passed the representation
check; the maximum difference was `5.737440293451801e-5 A`. Geometry, metrics,
anchors and canonical comparisons had zero mismatches. Unified validation was
`passed`, `complete=true`, with zero errors, warnings or unsupported validators.
All 22 files in the earlier exact NORMAL pilot directory remained unchanged.

Measured wall times were preparation 417.0552042060008 s, MANIA
406.6121387350013 s, independent checker 97.72347700999853 s, and total pilot
933.2831265860004 s. Total excludes ZIP packaging and repository verification;
preparation includes source and metadata guards. Full verification returned
9632 passed/22 skipped; focused tests returned 23 passed and the requested
regression set returned 1295 passed. Ruff and mypy passed.

No production code, formula, schema or dependency changed. Variant C remains
provisional, scientific PBC status remains unresolved, and Stage 34 remains
incomplete. The final task evidence combines the real calculation with the
completed repository checks before assigning formal Stage 34.A acceptance.
