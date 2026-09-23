# Stage 34.C.1 — replicas 2 and 3 protein evidence

The standalone `tools/stage34c_namd_r2r3_pilots.py` executes one five-frame
protein pilot for each new NAMD WT NaPi2b / 2SS / PMm replica. Replica 1 is
historical evidence only. This task stops before any QC-derived group manifest,
Stage 31 aggregation or Stage 33 publication. No production modules, scientific
formulas, numeric serialization contracts or dependencies are changed.

The runner binds the accepted intake archive and revalidates each config, log,
final XSC, DCD header/stat identity and the shared exact PSF, element authority
and explicit canonical mapping. The raw files all reside beneath the historical
`local_md/namd/egor_2ss_r1/raw/` directory; that directory name does not assign
replica identity. The intake fixed-record parser reads only source frames 0–4,
without coordinate-reader initialization or indexing scans. Full source DCD
hashes are not available from intake; correspondence retains that limitation.

As in accepted r1 preprocessing, execution uses the `namd-pilot` routing alias
and the source/canonical Dataset condition is null. The explicit source label
is PMm. The existing manifest requires a non-null Dataset condition to equal
the execution alias; this runner preserves the accepted helper and records the
known source label in metadata. A later group workflow must bind that label
consistently across the three replicas before aggregation.

Each config/log independently supplies 2 fs, 50,000 steps per coordinate and
1,000 ordered saved steps. Scientific frames 0–4 are exactly 100–500 ps, with a
0.1–0.5 ns inclusive window and 100 ps stride. Raw reader-formula times remain
separate and unrounded. The Stage 27 tolerance is unchanged.

The accepted Stage 34.B helper supplies Variant C, all-bond and protein geometry
checks, prepared XTC persistence/reopening, production Stage 27/28/30 execution,
independent per-frame/episode/window reconstruction and canonical-value checks.
Every representation gate precedes MANIA. The exact transformation order is
bonded-fragment unwrap, whole-protein geometry centering with `wrap=False`, then
whole-fragment wrapping with `center="cog"`. The 0.001 Å comparison tolerance
never pads scientific membership. Scientific PBC status remains unresolved;
MANIA applies no internal MIC.

Successful scientific outputs and their evidence are frozen by path, size and
SHA256 before the accepted Stage 32 hard evaluator reads them. Expected pilot
samples are five. Empty-window and singleton raw-MAD observations use the
existing Stage 32 helper unchanged. They do not supply missing RMSD authority.

Each replica gets a separate CSV, PNG and provenance JSON for 690 protein Cα
atoms aligned by equal-weight Kabsch to its own prepared frame 0 at 0.1 ns.
The same atoms are measured in angstrom, using the accepted r1 fallback
implementation. There is no numerical QC threshold, reviewer or drift decision.
Hard PASS therefore retains `pending_review`, with `production_ready=false`.
No human review input is accepted by this runner.

Run from the repository root, after focused synthetic verification:

```bash
.venv/bin/pytest -q tests/test_stage34c_namd_r2r3_pilots.py \
  tests/test_stage34b_namd_real_pilot.py \
  tests/test_stage34b5_single_replica_release_smoke.py \
  tests/test_stage34b5_rmsd_review_evidence.py
.venv/bin/python tools/stage34c_namd_r2r3_pilots.py --root local_md
```

A fresh ignored `local_md/stage34c_r2r3_pilots_<UTC>_<uuid>/` contains separate
replica subdirectories and top-level review files. A `science_started.json`
marker prevents rerunning science within a replica workspace. A failed gate
stops that replica; evidence never promotes an incomplete result to PASS.
Repository verification and final evidence packaging follow execution; the
runner's `package(work)` archives only small evidence types and validates every
archived size/hash. Prepared trajectories stay outside the ZIP with exact
bindings. Raw PSF/DCD/toppar bytes are excluded.

NAMD producer provenance remains 2.14 / seed 2026040842 for r1 and 3.0.3 /
seeds 2026051942 and 2026083042 for r2/r3. Different seeds do not establish
statistical independence. The producer-version difference and shared starting
state remain evidence for later scientific review. No full 100-ns contacts,
Stage 29 specialized science, other NAMD system or Stage 35 is run here.

## Real execution result

Stage 34.C.1 passed at unchanged HEAD
`1ea66836d1e5c1c9355f6405ab4d40dd2404a6bd`. Replica 2 produced 27,809
protein observations and 6,533 source/canonical rows; replica 3 produced 27,977
observations and 6,575 source/canonical rows. Both had zero independent
per-frame, window-metric and canonical-value mismatches, zero substantive PBC
mismatches before and after persistence, and 26/26 hard-QC checks passed.
Separate RMSD evidence is complete; both reviews remain pending and neither
replica is production-ready. Replica 1 was not scientifically rerun.

Verification: 85 focused tests, 2,768 relevant regressions, and the full suite
with 9,867 passed and 22 skipped. Ruff, mypy (183 source files), version/config
checks and the offline installed-wheel reference/mapping probe passed.
Evidence and its sibling ZIP use the ignored workspace basename
`stage34c_r2r3_pilots_20260923T152511Z_f535800b12ae449bb565fe823fbbc0c9`.
No group manifest, aggregation or publication was generated.
