# Dataset v1 production catalog

This Stage 34.D.4a inventory represents **19 systems / 33 trajectories** from
the [frozen scientific contract](../../docs/dataset_v1_scientific_contract.md).
It records source availability and unresolved production inputs. `dataset.yaml`
is an operational descriptor, not a new scientific Dataset schema or an
executable manifest. Dataset v1 remains unreleased. **This catalog does not
itself authorize Stage 35.** No launcher, scheduler, PBC preparation, MD
calculation, or Stage 27–33 execution belongs to D.4a.

| `source_group` | Engine | Systems | Trajectories | Replicas per system |
| --- | --- | ---: | ---: | ---: |
| `gromacs` | `gromacs` | 4 | 12 | 3 |
| `egor_namd` | `namd` | 3 | 9 | 3 |
| `alina_namd` | `namd` | 12 | 12 | 1 |

`trajectory_id` is unique. `replica_group_id` equals the system's catalog ID;
groups never mix engines, variants, conditions or disulfide-design states.
Every expected replica remains a row regardless of availability. A system is
READY only when all its expected trajectories are READY.

## Identity and evidence

GROMACS has WT/NORM, WT/TUMOR, T330M/NORM and T330M/TUMOR. Egor has WT/0SS,
WT/1SS and WT/2SS. Replica numbers 1–3 reserve the frozen population; they do
not establish a source-file assignment. Only the three Egor WT/2SS source
assignments are locally established. The historical raw directory name includes
replica 1 but contains all three independently identified runs.

Alina has one WT slot (`namd_alina_wt`) and eleven unnamed Cys-variant slots
(`namd_alina_inventory_01` through `namd_alina_inventory_11`). No authoritative
Alina source-bundle register or exact Cys labels were found. These opaque IDs
reserve the eleven frozen inventory positions, not discovered bundles, residue
positions, mutation names or scientific identities. Their `variant_id` remains
blank. Preserve these bookkeeping IDs when authoritative labels arrive, and
record the source-to-slot assignment. Alina's `replica_id=1` expresses only the
frozen one-trajectory cardinality; no original run number has been established.

The task's series-level authority assigns **PMm only to Egor NAMD** (all nine
rows). It does not resolve Alina's condition. Variant, condition, disulfide
state and replica remain separate fields. Directory names never establish
scientific authority. The CSV uses the existing model spellings `gromacs` and
`namd`. The task's Egor condition clarification supplements the older frozen
contract's unresolved NAMD condition statement without changing that contract.

## Portable paths

All nonblank scientific source/control paths are relative POSIX paths below
the future environment-defined `MANIA_DATA_ROOT`. They contain neither that
variable's expansion nor a machine mount, drive, workspace ID or parent escape.
`trajectories_csv` in the descriptor is relative to this catalog directory;
it is not a scientific input path.

The inspected Egor bundle has a shared PSF and toppar set alongside three
DCD/config/log/final-XSC sets. Preserve its source basenames and `toppar/`
structure under `namd/egor_wt_2ss/raw/`. This group directory avoids misleadingly
assigning the shared bundle to just replica 1. Accepted controls have future
locations under `controls/namd/egor_wt_2ss/`; each time control is in `r1/`,
`r2/` or `r3/`. These are intended locations, not a claim that a production
bundle has already been assembled. No source files were copied, moved, renamed
or linked. Paths for unbound or absent production sources remain blank.

The ignored audit maps current discoveries to these future paths, with existence,
size, accepted hash/binding evidence and reuse scope. Candidate 10-ns GROMACS
pilot inputs are inventoried separately; neither their names nor their pilot
mapping assigns them to a frozen full-production replica. No Alina or Egor
0SS/1SS bundle was found in the inspected sources. The audit records its search
locations and one unreadable external directory; absence is scoped to that
inspection, not a claim about all team storage.

## Timing and controls

`nominal_duration_ns` preserves frozen GROMACS facts (WT: 100; T330M: 30) and
the independently established 100-ns Egor WT/2SS runs. It does not establish a
requested analysis start/end. Egor's full source controls independently record
steps 0–50,000,000 at 2 fs, and 1,000 writes from 0.1 to 100 ns at 100 ps.
Those facts are retained in the audit; no requested production interval is
selected from the raw first/last frame or engine run boundaries.

The five requested timing fields remain blank until a full-production MANIA
contract explicitly supplies start, end, analysis stride, window length and
window step. `overlap_percent` is also retained because the frozen contract
requires it explicitly. Raw write cadence is not automatically analysis stride.
Stage 34's five-frame 0.1–0.5 ns windows and 50/100 ps pilot strides are not
full-production authority and are not copied into these fields.

| Path column | Meaning and blank-field rule |
| --- | --- |
| `topology_path`, `trajectory_path` | Authoritatively assigned raw production inputs; required for every row. |
| `config_path`, `log_path` | Engine production configuration and log evidence; absent or unbound sources remain unresolved. |
| `box_path` | Egor WT/2SS: final production XSC as endpoint evidence, with per-frame cells in DCD. An XSC is not a replacement for per-frame cells; XST is not required by that accepted source contract. GROMACS TPR/XTC needs no invented separate box file. Other NAMD systems need their own box/cell authority or an explicit not-applicable decision. |
| `element_control` | Reviewed atom-type authority for the exact NAMD PSF/toppar universe. A separate NAMD-style element control is not applicable to the accepted GROMACS TPR input route; actual topology validity still needs checking. |
| `time_control` | Additional source-axis authority for each NAMD DCD/config/log; does not supply requested analysis parameters. A separate NAMD JSON control is not applicable to GROMACS. |
| `canonical_mapping` | Explicit source-to-O95436 mapping with its exact topology binding; residue-number equality is never sufficient. |
| `biological_annotations` | Accepted complete-for-system biological annotations; missing authority is not an empty negative annotation list. |
| `partner_metadata` | Explicit topology-specific molecular classification/atom-index inputs for applicable specialised layers; never inferred from residue names. |

GROMACS `disulfide_state` is blank because the frozen GROMACS population has
no disulfide-design dimension; this does not assert that disulfide bonds are
absent. Alina's disulfide metadata/applicability remains unresolved. No other
blank scientific field is treated as not applicable without explicit evidence.

Only Egor WT/2SS reuses the accepted 97-type element control, exact 690/690 WT
mapping, complete-for-system annotations and explicit 830-partner metadata.
Reuse rests on the accepted shared PSF/toppar fingerprints and replica-specific
source bindings, not merely WT or 2SS labels. The mapping's `psf_binding.json`,
element definition/review sources, annotation provenance and partner
classification evidence must accompany the controls in a future bundle.
The audit lists those dependencies and hashes. None applies to other systems.

`partner_metadata` references the accepted input metadata, which has no pilot
time binding, not a five-frame output catalog. It does not establish inter-replica
partner correspondence. Specialised aggregation would still need separate
authoritative correspondence. Existing element/time/binding documents contain
historical source references, and the accepted annotations carry pilot Dataset
identity. Controlled portable path rebinding and production annotation identity
binding remain explicit unresolved inputs; this task edits none of those files.

## Readiness and resolution

Allowed statuses are exactly `READY`, `MISSING_FILES`, `MISSING_METADATA`, and
`NEEDS_AUTHORITY`. Classification precedence for multiple blockers is missing
files, missing identity metadata, then missing authority. `readiness_notes`
lists all known blockers, separated by semicolons. Blank means unresolved unless
the preceding engine/system rules explicitly establish non-applicability.

READY requires all applicable raw/source files, scientific and replica identity,
the approved full-production timing/window contract, and exact accepted controls
with valid production bindings. File existence, nominal duration, historical
pilot PASS, or an inventory ID cannot establish READY. Currently **READY = 0**,
**MISSING_FILES = 30**, **MISSING_METADATA = 0**, **NEEDS_AUTHORITY = 3**:
all 33 trajectories and all 19 systems are blocked. Zero primary metadata
statuses does not mean that metadata is complete; file blockers take precedence.

To resolve rows, source owners must supply/bind each missing full-production
bundle and its identity. Egor owns his NAMD source/control questions; Alina owns
her source/run/variant questions; use the GROMACS source-data owner for that
series. The scientific supervisor must approve unresolved requested timing,
window and applicability choices. The Dataset curator must preserve/rebind
accepted controls with their provenance. Recheck all blockers before changing
status; do not reduce expected replica counts. Technical and scientific QC/PBC
execution gates remain separate later requirements, not results of this catalog.

The ignored task evidence includes the complete field-level unresolved-input
inventory, one primary actionable blocker per non-READY trajectory, source/path
maps, checks and the readiness report. Catalog validation checks population,
IDs/groups, status vocabulary, Egor-only PMm, portability, timing provenance,
descriptor/README consistency and source immutability. It executes no science.
