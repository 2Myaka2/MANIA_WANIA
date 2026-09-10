# Dataset v1.0 frozen scientific contract

## Status and implementation boundary

This is the normative scientific decision record for Dataset v1.0 and the
source contract for Stages 27–35. Its scientific decisions are frozen. The only
unresolved input-data detail is the final concrete NAMD `condition` labels,
pending scientific-team input. MANIA MUST NOT invent these labels.

Stage 25 is complete. Stage 26.A is implemented only as independent identity
and requested physical-parameter models, described in the
[identity contract](dataset_identity_contract.md). Stage 26.B manifest/parameter-
table integration is next. Stage 26 remains incomplete. Dataset v1.0 remains
unreleased. This record supersedes the pre-freeze scientific-planning status
for Dataset v1.0 without rewriting historical Stage 25 acceptance records.

Frozen decisions MUST NOT be mistaken for implemented functionality. The
following Dataset v1.0 extensions are future work, not implemented in Stage
26.A:

| Future implementation owner | Scope | Status |
| --- | --- | --- |
| Stage 27 | Physical-time frame selection, effective windows and overlap mechanics | Future; not implemented in 26.A |
| Stage 28 | Protein occupancy/edge weight, contact episodes and lifetime | Future; not implemented in 26.A |
| Stage 29 | Separate protein-lipid and protein-glycan dynamic layers | Future; not implemented in 26.A |
| Stage 30 | Canonical residue mapping and supplied biological annotations | Future; not implemented in 26.A |
| Stage 31 | Replica aggregation | Future; not implemented in 26.A |
| Stage 32 | Dataset scientific QC engine | Future; not implemented in 26.A |
| Stage 33 | Publication exports | Future; not implemented in 26.A |

Stages 34–35 MUST preserve this source contract; this document assigns no new
implementation scope to them. It does not freeze a final Dataset v1.0 CSV/schema
layout. Named future fields below are scientific requirements, not current
artifact columns. Existing Stage 20–24 artifact schemas, scientific rows, and
calculation semantics MUST remain unchanged in 26.A.

## Dataset composition

Dataset v1.0 contains 33 trajectories/replicas across 19 systems. Every replica
MUST remain independently retained.

### GROMACS

| Variant | Condition | Replicas | Duration per replica |
| --- | --- | --- | --- |
| WT | NORM | 3 | 100 ns |
| WT | TUMOR | 3 | 100 ns |
| T330M | NORM | 3 | 30 ns |
| T330M | TUMOR | 3 | 30 ns |

GROMACS total: 12 replicas and 4 systems. Variant and condition are separate
scientific dimensions; NORM/TUMOR MUST NOT be inferred from WT/T330M.

### NAMD disulfide-design

| Variant | `disulfide_state` | Replicas |
| --- | --- | --- |
| WT | `0SS` | 3 |
| WT | `1SS` | 3 |
| WT | `2SS` | 3 |

NAMD disulfide total: 9 replicas and 3 systems.

### NAMD ECD/Cys

There is 1 WT system and 11 Cys-variant systems, with one replica per system.
NAMD ECD/Cys total: 12 replicas and 12 systems.

The totals are `12 + 9 + 12 = 33` trajectories and `4 + 3 + 12 = 19` systems.
Final concrete NAMD condition labels remain unresolved. The new identity
contract MUST represent `condition` and allow explicit `None` until supplied;
MANIA MUST NOT substitute guessed NORM/TUMOR or placeholder labels. No NAMD
duration or final Cys-variant names are invented here. The composition counts
are descriptive constants, not a completeness gate on partial/dev collections.

## Protein graph and separate dynamic layers

The main dynRIN MUST remain protein-only. Nodes MUST be NaPi2b amino-acid
residues. Edges MUST use only existing scientifically accepted MANIA
protein-protein interaction types. Lipids and glycans MUST NOT become nodes
in a heterogeneous main graph.

Stage 29 MUST provide separate dynamic layers:

- `protein_lipid_contacts_by_window`: a separate protein-lipid layer;
- `protein_glycan_contacts_by_window`: a separate protein-glycan layer when
  glycans are present.

These future layers MUST NOT change the identity of the protein-only main graph.

## External PBC preprocessing

PBC correction MUST occur before MANIA, through external preprocessing. The
expected conceptual pipeline is:

```text
whole molecule
-> remove jumps / unwrap when required
-> center on protein
-> compact trajectory when required
```

External preprocessing provenance MUST eventually retain commands/scripts,
software version, inputs, outputs, and provenance linking them. This is an
external scientific preparation requirement, not a MANIA GROMACS/NAMD wrapper.

MANIA Dataset v1.0 MUST NOT apply internal minimum-image correction, modify
coordinates, unwrap, center, or otherwise change scientific geometry. There is
no internal minimum-image correction in MANIA. The Stage 25 PBC audit MUST remain
observation/QC only; box metadata or a passed technical validation MUST NOT be
treated as proof that external PBC preparation is scientifically correct.

## Requested physical-time publication parameters — Stage 27

Each trajectory MUST receive `variant_id`, `engine`, `condition`, `replica_id`,
and these explicit requested scientific parameters:

| Parameter | Unit |
| --- | --- |
| `production_start_ns` | ns |
| `production_end_ns` | ns |
| `frame_stride_ps` | ps |
| `window_length_ns` | ns |
| `window_step_ns` | ns |
| `overlap_percent` | percent |

The new contract also carries dataset, system, and trajectory identifiers.
Publication semantics MUST NOT remain frame-count-only. Stage 27 will translate
physical requests into actual source/sampled frames and effective windows.
Stage 26.A only validates the requested values; it MUST NOT convert ps/ns,
select frames, count/create windows, calculate effective boundaries/stride or
coverage, or interpret overlap mechanically. Window length MUST fit inside the
declared production interval. Window length, step, and overlap remain three
explicit parameters; no step/overlap consistency relation is imposed in 26.A.

## Protein-protein occupancy and lifetime — Stage 28

The future per-window contract MUST use:

```text
occupancy = n_contact_frames / n_frames_in_window
edge_weight = occupancy
gap_tolerance = 0
```

The accepted denominator clarification for future Stage 28.B is that
`n_frames_in_window` means `n_resolved_frames_in_window`:

```text
occupancy = n_contact_frames / n_resolved_frames_in_window
```

Missing requested samples are not contact-negative resolved observations and
MUST NOT enter this denominator. Stage 32 separately evaluates sampling coverage;
missingness breaks continuity without inventing an observed negative frame.

A contact episode MUST be strictly continuous within one window and one
replica. Continuity MUST use adjacent SELECTED MANIA frames. Intentional frame
stride does not itself break an episode. An episode MUST break when:

- contact is absent on the next sampled frame;
- an expected sampled frame is actually missing;
- a window boundary is crossed;
- a replica boundary is crossed.

The accepted reviewer clarification defines adjacency as consecutive requested
sample indexes in the authoritative resolved window, not source-frame indexes.
`gap_tolerance = 0` is fixed, with no configurable tolerance. Episodes cannot
continue across windows or trajectories/replicas; overlapping windows calculate
their episodes independently.

Lifetime MUST use the actual first/last resolved contact-positive sample times:

```text
episode_length_ns = last_contact_sample_time - first_contact_sample_time
                 = (end_actual_time_ps - start_actual_time_ps) / 1000
```

The first line expresses sample times in ns. The second uses
`Decimal(str(actual_time_ps))` for subtraction and conversion. Requested indexes
define continuity; actual resolved times define duration, without snapping back
to requested targets. A single contact-positive sample has length `0.0 ns`.
This is conservative: MANIA does not assign unobserved time before the first or
after the last positive observation. No frame-count/stride or half-frame
correction is applied. No contact-positive samples means zero episodes and
`null` mean/max lifetime; a real one-frame episode instead has mean/max `0.0`.

Future protein-edge/window fields MUST include at minimum `n_contact_frames`,
`occupancy`, `n_contact_episodes`, `mean_episode_length_ns`,
`max_episode_length_ns`, and `edge_weight`. Stage 28 owns episode/lifetime
implementation; 26.A performs none of these calculations.

## Protein-lipid contacts — Stage 29

The separate layer MUST use the heavy atoms of one amino-acid residue on the
protein side and the heavy atoms of one lipid molecule on the lipid side.
Distance MUST be the minimum interatomic distance, with a cutoff of 6.0 Å.

Future residue-lipid/window fields MUST include `n_contact_frames`, `occupancy`,
`n_contact_episodes`, `mean_episode_length_ns`, `max_episode_length_ns`,
`distance_mean_A`, and `distance_min_A`. This remains a separate layer, not new
lipid nodes in the main dynRIN. No final lipid residue registry is invented.

## Protein-glycan contacts — Stage 29

When glycans are present, the separate layer MUST use the heavy atoms of one
amino-acid residue on the protein side and heavy atoms of the glycan on the
glycan side. Distance MUST be the minimum interatomic distance, with a cutoff
of 4.5 Å.

Future residue-glycan/window fields MUST include `n_contact_frames`, `occupancy`,
`n_contact_episodes`, `mean_episode_length_ns`, `max_episode_length_ns`,
`distance_mean_A`, and `distance_min_A`.

The covalent carrier-residue <-> first-sugar linkage MUST NOT artificially
enter ordinary occupancy/lifetime summaries. This exclusion boundary is frozen;
its implementation belongs to Stage 29. No final glycan or glycolipid residue
registry is invented.

### Accepted distance and edge-weight clarification for both specialized layers

For future Stage 29 protein-lipid and protein-glycan layers, `distance_mean_A`
MUST be the mean minimum interatomic distance over contact-positive frames only.
`distance_min_A` MUST be the minimum over contact-positive frames only.

These specialized layers do not require a duplicate `edge_weight` field in
Dataset v1.0 at present because `occupancy` is explicit. If future schema
unification exposes `edge_weight` there, it is derivative of occupancy, not a
new scientific formula. These clarifications introduce no Stage 29 implementation.

## Canonical residue reference — Stage 30

The canonical mapping reference MUST be:

- UniProtKB accession: `O95436`;
- entry: `NPT2B_HUMAN`;
- gene: `SLC34A2`;
- length: 690 aa.

Future mapping fields MUST include `source_engine`, `source_chain_id`,
`source_resid`, `source_resname`, `canonical_residue_number`,
`canonical_resname`, and `mapping_status`.

All publication tables MUST eventually use canonical numbering. GROMACS and
NAMD residues MUST NOT be compared merely because source `resid` values
coincidentally match. Stage 30 owns mapping; Stage 26.A performs none.

## Supplied biological annotations — Stage 30

The frozen canonical regions are ECD 234–361 and MX35 311–341 (residues).
Future fields MUST include `is_ecd` and `is_mx35_region`. A separate
`epitope_annotations.csv` is not mandatory for Dataset v1.0.

Future supplied glycosylation information MUST include the canonical site,
whether the glycan is present in topology, glycan type/name, source, and verifier.
Biological information ownership is currently recorded as:

| Systems | Owner |
| --- | --- |
| WT/T330M GROMACS | Ramila |
| NAMD disulfide systems | Egor |
| NAMD ECD Cys variants | Alina |

Supplied annotations also include `disulfide_variant_sites` and
`cysteine_variant_sites`. MANIA may validate and attach supplied annotations;
it MUST NOT infer or invent biological annotations or final biological
interpretation. Annotation attachment is future Stage 30 work.

## Replica aggregation — Stage 31

Every replica MUST remain independently retained. For three-replica statistical
groups, future aggregation MUST include `mean_occupancy`, `std_occupancy`,
`median_occupancy`, `n_replicates_available`, `n_replicates_supporting`, and
`support_fraction`.

```text
n_replicates_supporting = number of replicas where occupancy > 0
support_fraction = n_replicates_supporting / n_replicates_available
```

For single-replica Cys systems, `n_replicates_available = 1` and
`std_occupancy = null`. MANIA MUST NOT fabricate inter-replica statistics.
GROMACS and NAMD MUST NOT be mixed into one statistical group: no cross-engine
aggregation is permitted. `engine` MUST be present in publication tables.
The identity/reference `replica_key` MUST NOT serve as a cross-engine
statistical grouping key. Aggregation is future work owned by Stage 31.

## Dataset QC — Stage 32

The future QC engine may automatically exclude data for accepted technical
failures including:

- unreadable topology/trajectory;
- atom count/order or residue-mapping mismatch;
- protein remains broken after external PBC preprocessing;
- frame times duplicate or move backwards;
- less than 95% of expected production frames available (sampling coverage);
- required metadata/windows/nodes/edges missing;
- schema/reference failures;
- missing source/target nodes;
- prohibited self-loops;
- prohibited duplicates;
- occupancy outside [0, 1].

The following MUST trigger manual review only, not automatic exclusion:

- marked RMSD drift;
- more than 1% of windows without protein-protein edges;
- edge count, contact-type fraction, or basic metrics outside median ± 3 MAD
  within the appropriate replicate group.

RMSD alone MUST NOT be an exclusion criterion. When `MAD == 0`, that criterion
MUST NOT automatically declare an outlier.

Single-replica Cys systems MUST use technical QC, PBC QC, mapping QC, and graph
QC. Lack of replicate statistics is a Dataset v1.0 limitation; MANIA MUST NOT
invent replicate-based evidence for these systems. These rules are frozen
requirements for future Stage 32 implementation, not a QC engine added in 26.A.

## Stage 25 infrastructure and publication boundary

Stage 25 technical metadata MUST remain required infrastructure:
`SoftwareIdentity`, run provenance, artifact inventories, checksum modes,
unified technical validation, runtime/environment metadata, and the
observation-only PBC audit. Its reproducibility documentation, FAIR² software/run
bridge, and final real NaPi2b PoC acceptance remain the technical baseline.
See [Stage 25 reproducibility hardening](stage25_reproducibility_hardening.md)
and the [reproducibility guide](reproducibility.md).

Later publication work SHOULD use that existing infrastructure. Stage 26.A
MUST NOT redesign it, integrate the new identity into legacy manifests or run
provenance, alter CLI arguments or runtime inputs, or change scientific
calculations. Stage 33 owns future publication exports; final CSV/schema layout
and dataset-package generation are not implemented or frozen by this document.
No WANIA redesign, FAIR² dataset-repository change, FastAPI, dependency change,
database, service, or background worker is introduced.
