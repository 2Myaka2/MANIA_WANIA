# Dataset v1 production catalog

This Stage 34.D.4b reconciliation retains **19 systems / 33 trajectories** from
the [frozen scientific contract](../../docs/dataset_v1_scientific_contract.md).
The supervisor's D.4b decisions supply production timing, Egor PMm, Alina POPC
and variant names, current GROMACS collections, and the inclusive-window
rule implemented by Stage 34.D.4c. These supplement historical unresolved-input
statements; they do not change the Dataset scientific schema. Dataset v1 remains
unreleased.

`dataset.yaml` is an operational descriptor, not an executable manifest.
Stage 34.D.4e.2 adds the [supported Egor production interface](../../docs/egor_production_interface.md),
which projects an explicitly selected row into existing MANIA workflows. It
requires independently supplied prepared-input bindings and production controls.
The D.4e.2 interface alone does not change readiness or Stage 35 authority.
D.4e.3 supplies complete Egor 0SS/1SS annotations and verified prepared-input
readiness for `namd_egor_wt_0ss_r1`, as recorded below.
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

All nonblank CSV data/control paths are relative POSIX paths below the configured
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

D.4e.3 binds 0SS/r1 directly to `egor/<preserved filename>` with
`MANIA_DATA_ROOT=local_md/production_intake` (resolved to an absolute path).
Its new controls and prepared DCD are under that root's `prepared_inputs/`
checkpoint directory. Other raw rows retain their future layout; the explicit
input binding supports source relocation. Raw intake files remain unchanged.

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
At D.4b these were reusable *relations/definitions*, not ready-to-use controls:
new exact PSF/type-count and mapping bindings were required. No 2SS topology,
system annotations, partner atom indices or per-DCD time control is transferred
to 0SS/1SS by analogy. D.4e.3 supplies separately bound complete annotations
from Egor for both systems: glycosylation sites 295 and 308, each with FA2G2S2
present; disulfide design sites 303, 322, 328 and 350; and no cysteine variant
sites. Both `source` and `verifier` are `Egor`. The design-site list is independent
of actual SG–SG bonds: none for 0SS, C303–C350 for 1SS, and C303–C350 plus
C322–C328 for 2SS. No bond pairs are encoded through that annotation list.

The 0SS/r1 continuation revalidates all 96 used element types against exact
reviewed source definitions and binds all 690 canonical residues to its own PSF.
Its independently enumerated partner metadata contains 828 membrane partners
and two protein-linked FA2G2S2 glycans. Every 0SS atom is accounted for, including
101225 waters, 339 sodium ions and 277 chloride ions excluded from the partner
layers. No 2SS atom or partner indices are reused. Outside 0SS/r1, element/time,
mapping and partner controls remain unbound. Production specialized aggregation still requires authoritative
partner correspondence.

The approved external PBC protocol remains **unwrap bonded fragments → center
on protein → wrap complete bonded fragments**. D.4e.3 executes and technically
audits it for 0SS/r1 only. The new DCD preserves all 1000 frames, 409865 atoms,
source order, per-frame cells and the 100–100000 ps scientific time axis.
All persisted coordinate arrays match their indexed writer hashes. All
409655000 bond observations pass the established 0.001 angstrom representation
tolerance. MANIA still applies no internal minimum-image correction.

The public preflight returns `preflight_passed` with
`trajectory_pbc_qc_certified=false`; this is prepared-input readiness, not
contact/QC acceptance. No contacts, Stage 32, aggregation or publication were
run. The [interface guide](../../docs/egor_production_interface.md#real-0ssr1-prepared-input-checkpoint)
identifies the persistent checkpoint and replay command.

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

## Approved requested timing and explicit inclusive profile

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

The explicit production profile includes **both start and end boundaries**:
`[5,7]` and `[6,8]` each contain 11 requested samples at 200 ps.
They share six samples (6.0–7.0 ns); 50% duration overlap is not 50% of the
discrete sample count.

Implemented planner results under `mania.window_boundaries.inclusive.v1`:

| Inclusive interval | Selected samples | Full windows | Last full window | Samples/window |
| --- | ---: | ---: | --- | ---: |
| 5–100 ns | 476 | 94 | [98,100] ns | 11 |
| 5–30 ns | 126 | 24 | [28,30] ns | 11 |

Catalog v1.1 requests one policy for all 33 rows in `dataset.yaml`:

```yaml
temporal_policy:
  schema_version: mania.preprocessing_temporal_policy.v0.1
  boundary_profile: mania.window_boundaries.inclusive.v1
```

Copy this carrier unchanged to the top level of a Dataset preprocessing manifest.
The descriptor remains operational metadata; no launcher consumes it here.
The [versioned contract](../../docs/inclusive_window_contract.md) documents strict
persistence, offline reconstruction and mixed-profile rejection. Existing inputs
without a policy retain `mania.window_boundaries.legacy.v1`: ordinary windows
have ten targets, and a production-ending window has eleven. Historical pilots
retain that profile. Both profiles use the same requested sampling and generate
only full windows.

`trajectories.csv` remains byte-for-byte unchanged from D.4b. Its historical
notes saying "inclusive-window contract implementation pending" are superseded
by this descriptor policy and D.4c implementation; all other blockers and all
readiness statuses remain in force.

## Strict readiness and independent group preparation

Allowed statuses remain `READY`, `MISSING_FILES`, `MISSING_METADATA` and
`NEEDS_AUTHORITY`, with missing files taking precedence over missing identity
metadata, then missing authority. Notes retain all known blockers.

READY requires all applicable raw/source files, scientific and replica identity,
the approved requested timing/window contract, and exact accepted controls with
valid production bindings. Timing approval, inclusive windows, the launcher and
per-frame persistence/replay are implemented. D.4e.3 closes external preparation
for 0SS/r1; real contact execution and QC remain separate gates.

| Scope | READY | MISSING_FILES | MISSING_METADATA | NEEDS_AUTHORITY |
| --- | ---: | ---: | ---: | ---: |
| ALL DATASET | 1 | 31 | 0 | 1 |
| EGOR ONLY | 1 | 7 | 0 | 1 |
| GROMACS | 0 | 12 | 0 | 0 |
| ALINA | 0 | 12 | 0 | 0 |

All 19 systems remain non-READY because no expected replica group is complete.
Egor 0SS/r1 is now READY for the technical preflight with its exact controls and
prepared binding. Egor 1SS/r1 remains `NEEDS_AUTHORITY` for its other controls
and preparation; the seven missing-DCD rows remain `MISSING_FILES`. Complete
0SS/1SS system annotations are bound across their respective three rows.
Incomplete Alina/GROMACS groups do not block preparing Egor independently.

The ignored D.4b evidence contains all nine Egor bindings/ambiguities, separate
availability levels, source metadata preservation checks, machine-readable
source guards, readiness, the read-only inclusive-window impact audit, future
acceptance cases, per-frame export readiness, exact commands and verification.
The D.4b evidence contains no raw MD bytes. D.4c implements the explicit window
contract only; it performs no launcher work, Stage 35 or production run.

Historical statements above that persistence/replay and the launcher are later
software gates describe D.4b/D.4c. D.4d provides all-layer per-frame persistence
and offline replay; D.4e.2 provides the narrow catalog interface linked above.
Full source/control authority, external preparation and real QC remain separate
data gates. D.4e.3 promotes only 0SS/r1 prepared-input readiness. A future
**5–8 ns-only** contact run remains blocked by the public interface's fixed
**5–100 ns** Egor selection: no interval override exists, and cropped/reindexed
prepared inputs are unsupported. A separate approved interface change is needed;
the current full-range command must not be treated as a short technical test.
