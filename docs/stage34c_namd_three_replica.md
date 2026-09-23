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

## Stage 34.C.3 — real specialised coverage for replicas 2 and 3

`tools/stage34c_r2r3_specialized.py` fills the four missing per-replica lipid and
glycan canonical sources using only the accepted C.1 prepared trajectories. It
reuses the accepted B.4 Stage 29 execution, independent arithmetic, Stage 30
mapping and applicable artifact validators. Production code, formulas,
dependencies and the public CLI remain unchanged. Protein science, RMSD, QC,
Stage 31 and Stage 33 are not executed.

The runner pins the B.4, C.1 and C.2 evidence archives. Before reusing any partner
classification it revalidates the exact shared PSF, accepted external elements
(97 types, 439,436 atoms, no unresolved or conflicting assignments), and accepted
canonical mapping. The strict-read B.4 catalog is reconstructed from its explicit
classification records and actual PSF connectivity. Each replica receives its
own catalog; the only permitted differences are `trajectory_id` and `replica_id`.
Every other field, component atom/residue membership, partner name, and glycan
linkage must match exactly. This does not establish global partner identities or
Stage 31 correspondence.

Each prepared XTC is checked against its pinned hash and accepted pointwise-order
and PBC evidence, then reopened for five finite, identity-preserving frames with
matching boxes at 100, 200, 300, 400 and 500 ps. The accepted physical-time plan
remains one inclusive 0.1–0.5 ns window, five resolved samples, and 100 ps stride.
No coordinates are regenerated or transformed. Scientific PBC status remains
unresolved and internal MIC remains false.

Protein-lipid geometry uses complete explicit membrane partner heavy atoms and
an inclusive 6.0 angstrom cutoff. Protein-glycan geometry uses whole-glycan heavy
atoms and an inclusive 4.5 angstrom cutoff. The two PSF-connected FA2G2S2 branches
retain Asn295 ND2 and Asn308 ND2 to first-sugar C1 anchors. Their carrier-to-own-
glycan observations are archived separately and excluded from all ordinary
window statistics. There is no specialised `edge_weight`.

For each replica the independent B.4 checker uses float64 prepared coordinates
and direct Cartesian minima for every protein residue/explicit partner pair.
It never calls production contact detection or window aggregation. Requested
sample adjacency defines episodes with gap tolerance zero; a single-frame
lifetime is zero. Distance summaries use positive-frame distances only. Integer
and identity comparisons are exact; floating comparisons use zero relative and
1e-12 absolute tolerance, without padding contact cutoffs. Strict source and
canonical readers, catalog/temporal/source checks and exact shared-field
comparison precede freezing the canonical paths, row counts and SHA256 hashes.

The readiness check runs only the exact canonical-input coverage block extracted
from the SHA256-pinned Stage 33 workflow. That implementation has no standalone
coverage API, so its unchanged AST block is isolated without invoking the release
builder or writer. Additional C.3 checks require nonempty strict canonical rows
with the declared replica identities and frozen hashes. This is a coverage check,
not F1, F2, cross-table validation or publication acceptance. The accepted
QC-derived protein manifest and 7,168-row aggregate remain historical evidence.
The source/canonical condition remains null under the accepted `namd-pilot`
execution alias; a later publication task must bind the authoritative PMm label
consistently, as C.2 already does for protein inputs.

```bash
.venv/bin/pytest -q tests/test_stage34c_r2r3_specialized.py
.venv/bin/python tools/stage34c_r2r3_specialized.py --root local_md
```

The runner creates one unique ignored
`local_md/stage34c_r2r3_specialized_<UTC>_<uuid>/` directory. Verification and final
packaging follow execution. The accepted C.1 `package(work)` helper creates the
sibling ZIP with size/hash inventory verification; raw PSF, DCD, toppar and
prepared trajectory bytes are excluded. No staging, commit or push is performed.

### Real Stage 34.C.3 result

Stage 34.C.3 passed at unchanged HEAD
`0d2a17218c2c501baa19ed97d57e058746c88841`. Both replicas have 828 membrane
partners and two protein-linked FA2G2S2 glycans, zero unresolved components, and
exact catalog equality after ignoring only trajectory/replica identity.

| Observation | Replica 2 | Replica 3 |
| --- | ---: | ---: |
| Membrane partners contacting protein | 105 | 109 |
| Lipid positive observations | 3,529 | 3,528 |
| Lipid source / canonical rows | 916 / 916 | 913 / 913 |
| Raw glycan positives | 35 | 32 |
| Anchor observations excluded | 10 | 10 |
| Ordinary glycan positives | 25 | 22 |
| Glycan source / canonical rows | 7 / 7 | 6 / 6 |

Both replicas have zero missing/extra positives, geometry mismatches,
missing/extra window rows, mismatches in every window metric, anchor-exclusion
mismatches and canonical-value differences. The maximum independent geometry
delta is 0.0 angstrom. Nine applicable artifact checks per replica pass with
`complete=true`, zero errors, zero warnings and zero unsupported checks. Runtime
emitted the expected topology-only PSF initialization warning before the prepared
XTC was explicitly loaded and validated.

Frozen coverage readiness now passes for protein, lipid and glycan sources for
all three scientifically selected replicas. The C.2 missing-coverage blocker is
resolved by the real new canonical sources. Stage 33, F1, F2 and cross-table
validation remain NOT RUN. The accepted QC decisions, QC-derived protein
manifest and 7,168-row aggregate remain unchanged. Stage 34.C still awaits its
separately reviewed publication continuation; specialised replica aggregation
continues to require authoritative correspondence.

Real execution took 1,074.58 seconds. Stage 29 production / independent checking
took 441.84 / 131.08 seconds for r2 and 250.41 / 114.74 seconds for r3. Evidence
and its sibling ZIP use basename
`stage34c_r2r3_specialized_20260923T172052Z_707e6e5f6d6b4426922145487a665bcd`.
The per-replica freeze JSON files record exact canonical paths, counts and hashes.

Verification: 34 focused tests, 1,273 relevant regressions, and 9,958 passed /
22 skipped in the full suite. Two final synthetic orchestration tests were added
after full-suite collection and are included in the 34-test focused result.
Ruff, mypy (183 source files), CLI/module version, MDAnalysis version, example
config validation, and offline installed-wheel reference/mapping checks passed.
Only the standalone runner, its tests and this document changed. No production
code, network access, staging, commit, push or full-trajectory analysis occurred.

## Stage 34.C.4 — publication-only continuation

`tools/stage34c_publication_resume.py` resumes Stage 33 from the exact accepted
C.2 QC decisions, QC-derived manifest, three protein sources and 7,168-row
aggregate, plus the C.3-frozen specialised sources for all three replicas.
It verifies pinned archive and live-file bytes, then copies compact authority
into a fresh ignored workspace. It never calls upstream science, RMSD, QC or
aggregation. Production modules, schemas, dependencies and scientific formulas
remain unchanged.

The QC-derived manifest is bound to SHA256
`a61d84021593a94973539bb1f318ee09bff0595fef0f4052b7fe73063176e452`;
the protein aggregate is bound to
`823f43543e0a8459c1353d5ff0f4244ec2ebef9c1ce707a1dbe8a92bf1b57bff`.
Replica 1 specialised inputs are exactly the history paths frozen by C.3:
lipid SHA256
`ea7887ed8dc9de6a029fa791c4c713acb7a0bd83acc7889038b4ce6236c4507c`
and glycan SHA256
`7cde63b71bcce0b13df716de4488d4075e7575b5d7eba421cdab6f89a9dfe497`.
The runner also pins every r2/r3 source hash and requires the accepted independent
and technical C.3 gates. No historical files are rewritten.

New specialised publication copies bind `condition=PMm`. Strict model equality
permits only that field to differ: row population, topology-local partner IDs,
window identity, source identity and every scientific value remain equal.
Replica 1 already carries PMm and therefore its copy has no changed model fields.
The unchanged C.3 coverage gate requires real nonempty protein/lipid/glycan rows
for each of the three replicas before publication.

Stage 33 uses its existing absent-family semantics to emit header-only lipid
and glycan aggregate tables. The runner rejects specialised aggregation inputs
or correspondence. It never creates global partner identities. Optional metrics
remain empty; F2 validates emitted metrics and does not establish article-metric
or centrality readiness.

The accepted corrective F1 verifies complete protein models against the exact
three Stage 31 inputs. Since the accepted Stage 31 run contains only protein,
C.4 additionally compares every specialised canonical model against its frozen
C.3 authority after the explicit condition binding. Independent inspection reads
the actual persisted publication CSVs and compares every emitted scientific and
aggregate field, without invoking aggregate arithmetic. It also checks the exact
three simulations, exact requested-time Decimal values, five samples, complete
positive/negative annotations and replica-specific manual QC evidence.

The complete unchanged Stage 33 cross-table and unified release validators are
required. `status=passed`, `complete=true` and zero unsupported validators are
mandatory; partial validation cannot promote C.4 to PASS. External PBC approval
and each trajectory's diagnostics remain explicit, internal MIC stays false,
and historical `scientific_pbc_status=unresolved` is preserved. The frozen
`release_version=1.0` identifies the schema; this is only a 0.1–0.5 ns publication
smoke for NAMD WT NaPi2b / PMm / 2SS replicas 1, 2 and 3.

```bash
.venv/bin/pytest -q tests/test_stage34c_publication_resume.py
.venv/bin/python tools/stage34c_publication_resume.py --root local_md
```

The ignored workspace uses
`local_md/stage34c_publication_resume_<UTC timestamp>_<uuid>/`. Repository checks,
offline installed-wheel verification and final evidence packaging follow the
runner. Its sibling ZIP includes the actual compact release, exact input
bindings, gate reports, commands and verification logs. No raw topology,
trajectory, wheel or environment is included.

### Real Stage 34.C.4 result

Publication passed at unchanged HEAD
`6a72a90975eb8c79914f191e4991eeb59f0ad456`. The actual release contains 17 CSV
and 3 JSON artifacts, matching the frozen 20-artifact surface. Exactly three
simulations retain `namd / WT / PMm / 2SS`, with five requested/resolved samples
per replica in the 0.1–0.5 ns pilot window.

| Published family | Replica 1 | Replica 2 | Replica 3 | Total |
| --- | ---: | ---: | ---: | ---: |
| Protein | 6,514 | 6,533 | 6,575 | 19,622 |
| Lipid | 897 | 916 | 913 | 2,726 |
| Glycan | 6 | 7 | 6 | 19 |

The protein aggregate has 7,168 rows. Independent comparisons found zero missing,
extra, identity, numeric, denominator/availability or null mismatches in either
the aggregate or any per-replica family. Lipid and glycan aggregates are truthful
header-only tables; metrics are header-only with zero emitted metrics.

All nine canonical source bindings, complete model checks, coverage, F1, F2,
cross-table validation and independent inspection passed. Unified release
validation reports `status=passed`, `complete=true`, zero errors, zero warnings
and zero unsupported validators. F2 PASS applies only to emitted metrics and
does not establish article-metric readiness.

All 690 residue annotations were checked: ASN295/ASN308 glycosylation,
CYS303/CYS322/CYS328/CYS350 disulfide variants, no cysteine variants, ECD exactly
234–361 and MX35 exactly 311–341. All three QC outcomes remain `pass / available`
and production-ready. The 246 published QC evidence records exactly preserve
replica-specific human assessments: Ramilya Akhmetovna for r1 and Andrey for
r2/r3, with the original supplied spellings retained in evidence.

The first standalone final inspection incorrectly expected a review-input
evidence ID to survive Stage 32 unchanged. Accepted Stage 32 assigns
finding-local IDs; the reviewer payload was already identical in the release.
Only that checker assumption was corrected and regression-tested. Reinspection
passed on identical release bytes, with both exact accepted decision IDs and all
manual evidence fields checked. No production validator failed or was bypassed,
and publication, QC, aggregation and upstream science were not rerun.

Initial execution took 329.11 seconds, including 116.80 seconds for binding,
68.35 for publication and 79.08 for full release validation. Final reinspection
took 84.41 seconds; combined execution/checking time was 413.52 seconds.
Evidence and its sibling ZIP use basename
`stage34c_publication_resume_20260923T180448Z_43c729e565164ac3addfc1e8451b155f`.

Stage 34.C.1, C.2 protein QC/aggregation, C.3 specialised coverage and C.4
publication are PASS; the real three-replica Stage 34.C chain is PASS. These
results supersede the historical C.2 publication STOP above. Stage 34 remains
IN PROGRESS. Separate remaining work is the article-metric readiness audit,
Stage 34.D clean-install reproducibility, the Russian production run guide,
Stage 34.E real cluster handoff and any future authoritative specialised
cross-replica correspondence decision. Dataset v1.0 remains unreleased.

Verification: 81 focused tests passed, 3,514 relevant regressions passed, and
the final full suite passed 10,041 tests with 22 skipped and 22 warnings in
591.05 seconds. Ruff reported `All checks passed!`; mypy reported
`Success: no issues found in 183 source files`. Both CLI version commands returned
`mania-wania 0.1.0`; MDAnalysis was 2.10.0 and example config validation passed.
The offline wheel build/install and isolated 690-row reference/mapping round-trip
passed. Only the allowed standalone runner, its tests and this document changed;
no production-code change, network access, staging, commit or push occurred.
