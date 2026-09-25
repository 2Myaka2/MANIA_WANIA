# Dataset v1 production catalog

This Stage 34.D.4b reconciliation retains **19 systems / 33 trajectories** from
the [frozen scientific contract](../../docs/dataset_v1_scientific_contract.md).
The supervisor's D.4b decisions supply production timing, Egor PMm, Alina POPC
and variant names, current GROMACS collections, and a future inclusive-window
rule. These supplement historical unresolved-input statements; they do not
change the Dataset scientific schema. Dataset v1 remains unreleased.

`dataset.yaml` is an operational descriptor, not an executable manifest.
**This catalog does not authorize Stage 35.** No launcher, PBC preparation,
MD calculation, or Stage 27–33 implementation change belongs to D.4b.

| Source group | Engine | Systems | Trajectories | Replicas/system |
| --- | --- | ---: | ---: | ---: |
| GROMACS | gromacs | 4 | 12 | 3 |
| Egor | namd | 3 | 9 | 3 |
| Alina | namd | 12 | 12 | 1 |

`trajectory_id` is unique; `replica_group_id` equals `system_id`. Groups never
mix engines, variants, conditions or disulfide-design states. Every expected
replica remains a row. A system is READY only if all its expected rows are READY.

## Current source authority and portable paths

The authoritative local intake is `local_md/production_intake/`, with flat
`egor/`, `alina/`, and `ramila/` source directories. System/replica subdirectories
are not required. Files retain their original preserved names and locations.
No source file is copied, moved, renamed or linked by this reconciliation.

All nonblank CSV data/control paths are relative POSIX paths below future
`MANIA_DATA_ROOT`, without expansion, absolute paths or parent escapes.
`trajectories_csv` in the descriptor is relative to this catalog directory.
The ignored source-to-portable audit map records actual locations, declarations,
size, inspection level, binding evidence and control dependencies.

Egor's future portable layout is `namd/egor/raw/<preserved filename>`, with
shared `namd/egor/raw/toppar/`. This follows the authoritative storage identity
without requiring physical rearrangement. Alina uses `namd/alina/raw/`.
Missing DCD delivery basenames are not invented: their CSV paths remain blank;
Egor's exact CONF/OUT-declared DCD names remain in the audit.
**No Dataset v1 Egor raw binding is sourced from `Other_files/` or a historical
pilot raw directory.** Historical controls remain evidence, not replacement
production coordinates.

## Egor: nine explicit source records

The three WT systems are 0SS, 1SS and 2SS, each with three replicas, **PMm** and
a supervisor-declared 100 ns duration. PMm occurs only on these nine rows.
The audit supplies nine PSF, nine CONF, nine OUT and nine XSC bindings, plus nine
DCD source references: two observed delivery files and seven declared-only
references with unresolved preserved delivery names/bytes.

The preserved PSF/CONF/OUT/XSC stems are
`MD_no_bonds_NPT_W_I_PMm_100_ns`, `MD_303_350_NPT_W_I_PMm_100_ns`, and
`MD_2_bonds_NPT_W_I_PMm_100_ns`, respectively. Replicas 2/3 add `_2`/`_3`.
This assignment is corroborated by CONF/OUT structure names, distinct seeds,
DCD/output names, PSF atom counts and explicit SG–SG bonds, not suffixes alone.

| System | PSF atoms | Used types | Protein SG–SG bonds (source residue IDs) | Local DCDs |
| --- | ---: | ---: | --- | ---: |
| 0SS | 409865 | 96 | none | 1/3 |
| 1SS | 438622 | 97 | 303–350 | 1/3 |
| 2SS | 439436 | 97 | 303–350, 322–328 | 0/3 |

The two present DCDs retain their matching NPT stems. Each 276-byte header
corroborates its CONF/OUT-declared non-NPT filename, system atom count,
1,000 frames, 50,000-step write frequency and cell flag; file sizes match
the header-implied layout. No coordinate payload is read. Seven DCDs are
absent **from this authoritative local intake**; this does not mean Egor lacks
them elsewhere. Older locally stored 2SS trajectories do not establish intake
availability and are not substituted.

Availability is recorded separately as **A: file/location identified**,
**B: lightweight authoritative evidence inspected**, and **C: actual local
trajectory sufficiently inspected**. All nine runs have B-level source
evidence. DCD delivery A is established for two; all nine DCD declarations
are identified. No row has C-level full trajectory verification in D.4b.
Header agreement does not prove atom order, frame integrity or PBC quality.

All nine CONF/OUT records independently support 2 fs steps, 50,000-step writes,
and a 0–100 ns run with declared saved coordinates at 0.1–100 ns, every 100 ps.
All XSCs record the final 50,000,000 step. XSC is endpoint cell evidence;
the DCD cell flag is not a full per-frame cell audit. Shared parameter
references exist; all 57 previously reviewed toppar source hashes match.

## Control applicability

| Input/control | Requirement |
| --- | --- |
| `topology_path`, `trajectory_path` | Explicit observed source binding; missing delivery files remain blank. A bound partial file is not a complete production trajectory. |
| `config_path`, `log_path` | Exact run evidence; declarations and preserved delivery names are distinguished. |
| `box_path` | Egor final XSC endpoint evidence; per-frame cells still require verification. No separate GROMACS box file is invented. Alina cell/time authority remains unresolved. |
| `element_control` | Exact NAMD PSF/type-count binding to reviewed definitions. NAMD-style control is not applicable to the GROMACS TPR route. |
| `time_control` | Exact NAMD DCD/CONF/OUT source-axis authority, independent of requested analysis stride. |
| `canonical_mapping` | Explicit O95436 residue relation with exact topology binding. |
| `biological_annotations` | Authoritative complete-for-system annotations and production Dataset/system identity. |
| `partner_metadata` | Explicit topology-specific classification and atom membership; no residue-name guessing or inferred inter-replica correspondence. |

All three intake 2SS PSFs match accepted SHA256
`04b7bee588edf61bde25dfded24216ed4e0727d75d1e144356b500ecc89004bb`.
Their CONF/OUT/XSC files also match the accepted per-replica hashes despite
preserved filename differences. The 97-type element definitions, 690/690
canonical mapping relation and 830-partner input metadata therefore have
exact topology compatibility. Existing controls under future
`controls/namd/egor_wt_2ss/` still need portable path rebinding; annotations
need production identity binding; time controls need actual intake DCD
verification. Binding/review/annotation/classification provenance must accompany
the controls. A historical pilot PASS is not production readiness.

0SS/1SS have different PSF hashes and atom counts. Their exact ordered
690-residue identities match the accepted mapping relation, and their used
types/masses match reviewed definitions (0SS omits SM; 1SS uses all 97).
These are proven reusable *relations/definitions*, not ready-to-use controls:
new exact PSF/type-count and mapping bindings are required. No 2SS topology,
system annotations, partner atom indices or per-DCD time control is transferred
to 0SS/1SS. Their complete annotations and partner authority remain unresolved.
Production specialized aggregation requires authoritative partner correspondence.

The approved external PBC protocol remains **unwrap bonded fragments → center
on protein → wrap complete bonded fragments**. Its authority is distinct from
future per-trajectory execution/audit. MANIA still applies no internal
minimum-image correction. No trajectory-level PBC audit is claimed here.

## GROMACS production collections

WT/NORM and WT/TUMOR each have three 100 ns replicas from
`phase1eqmd3rep100ns`. The inspected Ramila directory is empty; current source
storage may still change, so none of these six rows has an observed assignment.

T330M/NORM and T330M/TUMOR each retain three 30 ns replicas awaiting
`T330M_30ns_09-2026`. **`30ns_03-2026` is excluded from current FAIR² Dataset v1**
and cannot supply T330M bindings. Historical pilot results remain untouched.
All twelve rows remain blocked for missing/unbound production sources.
GROMACS has no frozen disulfide-design dimension; its blank field does not
assert absence of physical disulfide bonds.

## Alina identity and condition

POPC is authoritative as Alina's membrane environment. The existing catalog
and `DatasetTrajectoryIdentity.condition` carry the supplied scientific
condition/environment label and have no separate membrane-composition field.
Therefore **`condition=POPC`** fits this contract without schema changes.
It is not replaced by PMm. Alina disulfide metadata/applicability remains
unresolved; a mutation label does not establish a disulfide annotation.

The stable bookkeeping IDs are preserved. `namd_alina_wt` binds WT.
`namd_alina_inventory_01` through `_11` bind the following exact confirmed
filename labels in order:

| Slot | Filename label | Scientific variant |
| --- | --- | --- |
| 01 | 303 | C303A |
| 02 | 322 | C322A |
| 03 | 328 | C328A |
| 04 | 350 | C350A |
| 05 | 303-322 | C303A_C322A |
| 06 | 303-328 | C303A_C328A |
| 07 | 303-350 | C303A_C350A |
| 08 | 322-328 | C322A_C328A |
| 09 | 322-350 | C322A_C350A |
| 10 | 328-350 | C328A_C350A |
| 11 | 328tyr | C328Y |

All twelve have corresponding preserved PSFs and reference PDBs. The single
observed `328tyr_2.dcd` is associated with `step5_assembly328-tyr.psf` by the
confirmed label and matching 282647-atom header. Atom order/run provenance
is unverified; its 400-frame header suggests approximately 10 ns, not the
approved 30 ns production duration. It is explicitly a partial observed
source, not a completed production assignment. Eleven DCDs and all Alina
CONF/OUT/toppar/time controls are absent from this intake.
`replica_id=1` retains frozen one-trajectory cardinality only; **`_2` is never
interpreted as an independent replica without separate authority**.

## Approved requested timing and pending inclusive windows

| Group | Start (ns) | End (ns) | Stride (ps) | Length (ns) | Step (ns) | Overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GROMACS WT | 5 | 100 | 200 | 2 | 1 | 50% |
| GROMACS T330M | 5 | 30 | 200 | 2 | 1 | 50% |
| Egor NAMD | 5 | 100 | 200 | 2 | 1 | 50% |
| Alina NAMD | 5 | 30 | 200 | 2 | 1 | 50% |

All rows now carry these explicit supervisor-approved requested values.
**Overlap duration = length − step = 1 ns; overlap percent =
(1 − step / length) × 100 = 50%.** The existing `overlap_percent` column is used.
The first 5 ns remain stabilization/QC source data and are not deleted.
Raw write cadence does not redefine the approved 200 ps requested stride.
No five-frame 0.1–0.5 ns pilot interval or 50/100 ps pilot stride is reused.

The new future rule includes **both start and end boundaries**:
`[5,7]` and `[6,8]` each contain 11 requested samples at 200 ps.
They share six samples (6.0–7.0 ns); 50% duration overlap is not 50% of the
discrete sample count.

Audit expectations, not current executable-contract claims:

| Inclusive interval | Selected samples | Full windows | Last full window | Samples/window |
| --- | ---: | ---: | --- | ---: |
| 5–100 ns | 476 | 94 | [98,100] ns | 11 |
| 5–30 ns | 126 | 24 | [28,30] ns | 11 |

**inclusive-window contract implementation pending**. No final contract/profile
identifier is invented. Current Stage 27 code uses `[start,end)` except a window
ending exactly at production end, which uses `[start,end]`. It already selects
production endpoints when they lie on the requested grid; ordinary windows
currently contain ten targets in these schedules, and the last contains eleven.
No shortened trailing window is generated. Historical outputs must retain
their recorded semantics and remain readable/verifiable in the future change.

## Strict readiness and independent group preparation

Allowed statuses remain `READY`, `MISSING_FILES`, `MISSING_METADATA` and
`NEEDS_AUTHORITY`, with missing files taking precedence over missing identity
metadata, then missing authority. Notes retain all known blockers.

READY requires all applicable raw/source files, scientific and replica identity,
the approved requested timing/window contract, and exact accepted controls with
valid production bindings. Timing-approval blockers are removed. The pending
inclusive implementation and launcher interface are separate execution gates,
not raw-data blockers. Full trajectory QC/PBC execution remains a later gate.

| Scope | READY | MISSING_FILES | MISSING_METADATA | NEEDS_AUTHORITY |
| --- | ---: | ---: | ---: | ---: |
| ALL DATASET | 0 | 31 | 0 | 2 |
| EGOR ONLY | 0 | 7 | 0 | 2 |
| GROMACS | 0 | 12 | 0 | 0 |
| ALINA | 0 | 12 | 0 | 0 |

All 19 systems remain non-READY. Egor has two locally complete raw bundles at
header-inspection level, seven missing local DCDs, zero rows with complete
production scientific controls, and zero launcher-ready rows. The two present
bundles are `NEEDS_AUTHORITY`; the seven others are `MISSING_FILES`.
Incomplete Alina/GROMACS groups do not block preparing Egor independently.

The ignored D.4b evidence contains all nine Egor bindings/ambiguities, separate
availability levels, source metadata preservation checks, machine-readable
source guards, readiness, the read-only inclusive-window impact audit, future
acceptance cases, per-frame export readiness, exact commands and verification.
It contains no raw MD bytes. No launcher, inclusive-window implementation,
Stage 35 or production run is performed by this checkpoint.
