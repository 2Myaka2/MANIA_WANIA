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

## Stage 34.C.2 — three-replica downstream gates

`tools/stage34c_three_replica_downstream.py` binds the committed Stage 34.C.1
archive and the accepted replica-1 publication history. It reads and hashes
evidence without loading coordinates, calculating RMSD, or rerunning Stage
27–30. New tracked work is limited to this helper, its focused tests, and this
document. Production scientific code, dependencies, and schemas are unchanged.

The supplied manual assessments belong separately to replicas 2 and 3. Both
record reviewer Andrey (the supplied spelling is preserved exactly in JSON),
`drift_detected=false`, and the accepted five-frame equal-weight Kabsch RMSD of
690 protein C-alpha atoms against each replica's own prepared frame 0 at 0.1 ns.
The recorded maxima are 2.0765174977816443 and 1.9755625384645457 angstrom,
respectively. These are evidence bindings, never decision thresholds. The review
scope is only the technical five-frame pilot, with no full-trajectory stability
assessment. Replica 1 retains its original reviewer and accepted assessment.

The runner checks exact RMSD CSV values, times, atom identities, reference,
prepared-trajectory hashes, and method evidence. A metadata-only `condition`
projection binds the explicitly supplied PMm label for replicas 2 and 3; every
other canonical model field must remain equal to its accepted source. Original
artifacts remain unchanged. WT, 2SS, NAMD, and all three full replica keys remain
separate identity fields.

Accepted Stage 32 evaluators first complete the real review cohort. The original
replica-1 decision remains archived; its hard evidence and manual RMSD assessment
are reused while the accepted raw-MAD comparison now sees all three real edge
counts. Any pending, excluded, unknown, or unresolved replica stops this pilot
before aggregation. Only after three available decisions does the runner verify
the shared PSF/mapping authority, record the canonical freeze, and construct the
technical template required by Stage 32.D. It executes the unchanged Stage 32
workflow, requires the exact same decisions, and feeds only its QC-derived
manifest into Stage 31.

The independent checker does not call the production aggregator. It reconstructs
every emitted Stage 31 field from the frozen canonical tables, including complete
identity, window, mean, median, sample SD (`n-1`), availability, positive-occupancy
support, support fraction, and null semantics. Available sparse absence contributes
zero; unavailable/excluded members contribute neither a zero nor a denominator
entry. Every edge's vector and contributor keys are archived, together with real
examples of one, two, and three sparse presences when present. Exact mismatches
block Stage 33.

The helper preserves the accepted biological annotation authority and the
requested-time exact Decimal serialization. Producer provenance remains NAMD
2.14 / seed 2026040842 for r1 and NAMD 3.0.3 / seeds 2026051942 and 2026083042
for r2/r3. This version difference is explicit; different seeds do not establish
complete statistical independence. Per-trajectory Variant C diagnostics remain
archived, internal MIC remains false, and the legacy `scientific_pbc_status`
remains unresolved.

Run from the repository root:

```bash
.venv/bin/pytest -q tests/test_stage34c_three_replica_downstream.py
.venv/bin/python tools/stage34c_three_replica_downstream.py --root local_md
```

The runner creates one unique ignored downstream workspace. Repository checks,
offline-wheel verification, the final Git inspection, and evidence packaging
follow separately. A stopped gate must have explicit NOT RUN downstream records;
it cannot imply F1, F2, cross-table, or complete release validation success.

### Frozen Stage 33 coverage constraint

The accepted Stage 33 workflow and validator require canonical artifact coverage
in all three families (protein, lipid, glycan) for **every** replica selected for
scientific publication. Header-only output tables for missing specialized
aggregates do not waive this per-replica canonical-input requirement. Replicas 2
and 3 have only protein evidence under the authorized Stage 34.C scope.

Binding their identities to replica-1 specialized artifacts or synthesizing empty
canonical files would claim unsupported scientific coverage. Selecting only r1
would omit the required r2/r3 per-replica protein science. Neither is a valid
three-replica publication solution. The runner therefore supplies truthful
bindings to the unchanged Stage 33 gate and stops if it rejects missing coverage.
Supporting protein-only scientific publication requires a separately approved
contract decision; this task does not change that contract or run r2/r3 Stage 29.

Publication F2 validates emitted metrics only. An empty optional metrics table
does not establish article-metric readiness. Article metrics, clean-install
reproducibility / Stage 34.D, cluster handoff / Stage 34.E, and specialized
multi-replica correspondence remain separate work. Stage 34 is still IN PROGRESS.

### Real Stage 34.C.2 result

At unchanged HEAD `b52bad0c43cba8929a6920bfc1281992c3bfd2d8`, the three
Stage 32 decisions are `pass / available`, with `production_ready=true` and no
unresolved findings. Replica 1 has 38 hard and 3 review findings; replicas 2 and
3 each have 26 hard and 3 review findings. Complete Stage 32 and Stage 31 offline
validation passed with zero issues.

The frozen protein sources contain 6,514 / 6,533 / 6,575 rows. Real Stage 31
aggregation produced 7,168 rows. Independent reconstruction found zero missing,
extra, identity, numeric, denominator/availability, or null-semantics mismatches.
All vectors have three available replicas. There are 5,945 identities present
in three sparse tables, 564 present in two, and 659 present in only one.

| Real edge | r1/r2/r3 vector | Mean | Median | Sample SD | Supporting / available |
| --- | --- | --- | --- | --- | --- |
| 1–2 hydrophobic | 1.0, 0.8, 1.0 | 0.9333333333333333 | 1.0 | 0.11547005383792515 | 3 / 3 |
| 3–520 vdw | 0, 0.2, 0.4 | 0.2 | 0.2 | 0.2 | 2 / 3 |
| 2–521 hydrophobic | 0, 0.2, 0 | 0.06666666666666667 | 0 | 0.11547005383792515 | 1 / 3 |

The unchanged Stage 33 implementation rejected the real candidate before writing
publication artifacts: `Dataset release input failed: invalid or inconsistent
authority.` The explicit binding audit identifies missing lipid and glycan
canonical coverage for r2 and r3. No empty sources, partner correspondences, or
metrics were invented. The publication surface is therefore **0 CSV / 0 JSON**;
F1, F2, cross-table validation, release validation, and independent publication
inspection are **NOT RUN**, not PASS. Accepted annotation inputs remain bound;
there is no new annotation output to verify.

Stage 34.C.1 remains PASS. Stage 34.C.2 is STOP at the frozen Stage 33 input
contract, and the Stage 34.C three-replica chain is incomplete. Resolving the
protein-only publication contract is an additional Stage 34 blocker. Evidence
uses the ignored workspace basename
`stage34c_three_replica_downstream_20260923T162715Z_97cb0bc52b9347cfa0da2a09d7082f6c`.

Verification: 4,209 relevant regressions and the full suite with 9,922 passed,
22 skipped. The final focused run passed 59 tests, including four final
Git-status guard cases added after full-suite collection. Ruff, mypy (183 source
files), CLI/module version, MDAnalysis version, config validation, and the
offline installed-wheel reference/mapping probe passed. No network, staging,
commit, push, full-100-ns analysis, or r2/r3 specialized science was performed.
