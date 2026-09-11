# Specialized molecular-partner windows and source artifacts

**Stage 29.D: PASS. Stage 29: COMPLETE.** Stage 30 canonical mapping / biological
annotations is next and has not started. Generic acceptance uses synthetic
authoritative metadata; real partner metadata remains a separate team input.

Stage 29.A molecular partner identification, 29.B protein-lipid geometry, and
29.C protein-glycan geometry are accepted and unchanged. Stage 29.D connects
these contracts to retained Stage 27 physical-time execution and Stage 28.A
episodes. All specialized outputs belong to preprocessing. They do not change
protein contact results, main graph nodes/edges/JSON, the Stage 28 protein-edge
source table, WANIA, or analysis/PCA inputs.

## Authoritative external metadata

**Classification is explicit metadata. MANIA never auto-classifies lipids or
glycans from resname. Connectivity groups already classified components only.**
No final biological residue lists, glycan types, glycosylation sites, NAMD
condition labels, carrier mappings, or partner IDs are inferred from names.

A Dataset-aware condition can declare `molecular_partner_metadata_path` in its
preprocessing manifest. The filename is user-controlled; relative paths follow
the existing manifest-directory base semantics. The path is execution metadata,
not part of `DatasetTrajectorySpec` or Dataset scientific identity. Mixed
manifests are supported. An absent path is omitted from serialization, and
conditions without it have no partner identification, catalog record, or extra
trajectory pass. A legacy-only condition does not activate Stage 29 even if it
supplies the field.

`molecular_partner_metadata_io.py` defines the frozen `MolecularPartnerMetadata`:

- `schema_version`: exactly `mania.molecular_partner_metadata.v0.1`, non-init;
- `kind`: exactly `mania_molecular_partner_metadata`, non-init;
- `classifications`: tuple of exact accepted
  `MolecularPartnerComponentClassification` records;
- `explicit_partners`: tuple of exact accepted
  `ExplicitMolecularPartnerDefinition` records.

The JSON root requires all four fields. Each classification requires exactly
`residue_index`, `partner_kind`, and `partner_name`. Each explicit partner
requires exactly `partner_id`, `partner_kind`, `partner_name`,
`component_residue_indexes`, `carrier_residue_index`,
`first_sugar_residue_index`, and `linkage_evidence`. Nullable linkage values are
JSON null; the accepted 29.A model checks their combinations. Arrays become
immutable tuples through exact model reconstruction. Classification residue
indexes and explicit IDs must be unique, explicit memberships cannot overlap,
and ordering is normalized by source residue index and then lipid/glycan + ID.
Identification subsequently checks classification/grouping/topology consistency.

A synthetic empty control file is valid:

```json
{
  "schema_version": "mania.molecular_partner_metadata.v0.1",
  "kind": "mania_molecular_partner_metadata",
  "classifications": [],
  "explicit_partners": []
}
```

`read_molecular_partner_metadata`, `write_molecular_partner_metadata`, and
`validate_molecular_partner_metadata` use strict UTF-8 JSON. Unknown/missing
fields, duplicate object keys, invalid types, and non-finite numbers fail.
Writers use deterministic JSON with `allow_nan=False`, one trailing newline,
and atomic publication with explicit overwrite control. Readers never scan
folders or infer classification. Empty supplied metadata is still identified
and retained as an empty catalog, with no specialized geometry pass.

## Runtime authority and trajectory passes

`specialized_contact_execution.py` adapts source topology residue ordering and
source atom indexes into accepted `MolecularPartnerTopology`. Protein membership
comes from the repository's accepted `select_atoms("protein")` mechanism and is
translated to source topology indexes, checking atom membership. A missing,
empty, or inconsistent accepted selection fails specialized identification.

Successfully exposed authoritative bonds produce `connectivity_status=available`
and `SourceTopologyBond` evidence. Unavailable bond access or guessed bonds
produce `unavailable`, never an assertion of zero bonds. No spatial connectivity
inference is performed. An accessible authoritative empty bond collection is
available connectivity. Unavailable connectivity requires the accepted 29.A
explicit grouping fallback; glycan linkage then uses external metadata.

Required protein and partner atoms need authoritative topology element or atomic
number evidence. Atomic number 1 or element H denotes hydrogen. Missing,
invalid, conflicting, or solely guessed element/atomic-number evidence fails
specialized computation. Atom names, H prefixes, masses, force-field type
strings, and residue names are never fallbacks. No coordinates enter serialized
execution or catalog evidence.

For every non-empty metadata-bearing catalog, exactly **one** additional pass
visits the accepted Stage 27 explicit selected source frame indexes. Both lipid
and glycan geometry run from the same coordinates during this pass. There is no
new time matching, per-kind pass, per-partner pass, per-window pass, or PBC pass.
With temporal planning, Rg, protein contacts and specialized partners enabled,
the conceptual passes are: time-axis planning, Rg, protein contacts, and the
shared specialized pass. PBC observation remains on its accepted scientific
pass. MANIA applies no internal minimum-image correction; the scientific PBC
protocol remains unresolved.

The frozen `PreprocessingSpecializedContactConditionResult` retains execution
condition, Dataset spec, connectivity status, accepted partner catalog, and
29.B/29.C frame results. `PreprocessingSpecializedContactExecution` retains
participating conditions in Dataset/manifest order. Every present partner kind
requires exactly one scientific result for every selected Stage 27 source frame.
Missing, extra, duplicate, or inconsistent scientific evidence raises an error;
missing computation is never interpreted as contact absence.

## Window formulas and sparse semantics

The pure `specialized_contact_windows.py` consumes accepted sampling/window
plans. Protein-lipid minimum Cartesian heavy-atom distance uses the unchanged
inclusive **6.0 Å** cutoff; protein-glycan uses unchanged inclusive **4.5 Å**.
Each molecular partner is the complete identified 29.A entity.

Each ordinary protein-residue/partner/window row contains:

| Metric | Definition |
| --- | --- |
| `n_contact_frames` | Number of ordinary positive resolved frames |
| `occupancy` | `n_contact_frames / window.sampled_frame_count`, Decimal ratio before float conversion |
| `n_contact_episodes` | Accepted Stage 28.A episode count |
| `mean_episode_length_ns` | Arithmetic mean of accepted episode durations |
| `max_episode_length_ns` | Maximum accepted episode duration |
| `distance_mean_A` | Deterministic Decimal mean of frame minimum distances over ordinary positive frames only |
| `distance_min_A` | Minimum of those same ordinary positive distances |

**There is no specialized `edge_weight` field in Dataset v1.0.**

Missing requested samples break continuity and do not enter the occupancy
denominator. Resolved contact-negative frames break continuity and do enter it.
All episode calculation delegates to `compute_window_contact_episodes`; no
second episode engine exists. `gap_tolerance=0` and
`episode_length_ns = last_contact_actual_time_ns - first_contact_actual_time_ns`.
Single-frame episodes last 0.0 ns. Window calls are independent, so overlapping
windows can reuse the same observation without sharing episode state.

For requested indexes 0,1,2,3,4 with positives 0,1,3,4: missing index 2 gives four
resolved frames, occupancy 1.0 and two episodes. A resolved negative index 2 gives
five resolved frames, occupancy 0.8 and two episodes. Two positive distances 3.0
and 4.0 among five resolved frames give mean 3.5 Å and minimum 3.0 Å. Distances
from the other three negative frames never enter these statistics.

Glycan raw observations marked `standard_summary_excluded=True` are excluded
before ordinary positives are formed. They contribute to none of the seven
ordinary metrics and are not converted to negative observations. Raw 29.C
geometric evidence remains valid. An excluded-only carrier/glycan pair emits no
ordinary row. Another protein residue contacting the same glycan uses all
resolved window frames as its denominator and only its own positive distances.
`excluded_raw_observation_count` is technical audit evidence, not a publication
metric; root totals sum per-window exclusions, counting overlaps independently.

Rows are sparse: only pair/window combinations with at least one ordinary
positive observation appear. No zero-occupancy rows are emitted. Same-name
partners remain separate by partner ID. Empty windows and header-only source
CSVs are valid. Aggregation `complete`/`partial` describes physical-plan coverage
only; contact computation failure raises and cannot become `partial`. The 95%
QC/exclusion policy remains Stage 32.

## Combined catalog artifact

`molecular_partner_catalog_io.py` strictly writes, reads and validates one
`molecular_partner_catalog.json`. Its schema version is
`mania.preprocessing_molecular_partner_catalog.v0.1` and kind is
`mania_preprocessing_molecular_partner_catalog`. The exact root fields are
`schema_version`, `kind`, and `bindings`. Every binding contains exactly:

- `execution_condition` for routing;
- `dataset_spec`, including unchanged requested Dataset identity and temporal parameters;
- `topology_connectivity_status`;
- the complete accepted 29.A `partner_catalog`, including components, atom
  membership, identification mode, carrier/first-sugar linkage and partner counts.

Bindings require unique execution conditions and Dataset replica keys. At least
one metadata-bearing binding is required, but its catalog may be empty.
Strict reconstruction preserves source evidence and verifies serialized counts,
fixed fields and model invariants. The artifact contains no coordinates.
Generated IDs remain source-topology-local; cross-system canonical partner
identity is not claimed.

## Exact pre-canonical CSV contracts

`specialized_contact_window_tables.py` and
`specialized_contact_window_tables_io.py` build and persist exactly:

- `protein_lipid_contacts_by_window_source.csv`;
- `protein_glycan_contacts_by_window_source.csv`.

Both begin with the following columns, in this order:

```text
dataset_id,system_id,trajectory_id,variant_id,engine,condition,replica_id,disulfide_state,
window_id,window_index,requested_window_start_ns,requested_window_end_ns,right_endpoint_inclusive,
effective_window_start_ns,effective_window_end_ns,requested_sample_count,resolved_frame_count,
missing_sample_count,coverage_fraction
```

Lipid identity columns follow:

```text
protein_residue_index,protein_chain_id,protein_resid,protein_resname,
lipid_partner_id,lipid_partner_name,lipid_component_residue_indexes
```

Glycan identity and linkage columns follow instead:

```text
protein_residue_index,protein_chain_id,protein_resid,protein_resname,
glycan_partner_id,glycan_partner_name,glycan_component_residue_indexes,
carrier_residue_index,first_sugar_residue_index,linkage_evidence,
carrier_link_atom_index,first_sugar_link_atom_index
```

Both end with these seven metrics:

```text
n_contact_frames,occupancy,n_contact_episodes,mean_episode_length_ns,
max_episode_length_ns,distance_mean_A,distance_min_A
```

The displayed wraps are for readability; the CSV header occupies one line.
Requested/effective window bounds, right-endpoint semantics and coverage follow
accepted Stage 28 source-table semantics. Effective bounds convert retained
actual picoseconds to nanoseconds using Decimal. Protein source `segid` becomes
`protein_chain_id`, and source residue IDs become text in `protein_resid`,
matching the accepted Stage 28 source-evidence convention.

Component membership is encoded as semicolon-separated, strictly increasing,
unique non-negative integers, for example `20;21;22`. Empty membership,
whitespace ambiguity, leading-zero ambiguity and Python tuple representations
are rejected. Nullable Dataset condition, disulfide state, source chain/resid
and external-linkage atom indexes use blank CSV cells. Literal `None`, `null`
or `NA` placeholders are rejected for nullable fields. Booleans are `true` or
`false`; numbers must be finite and contract-valid.

Each table rejects duplicate identities:
`(dataset_id, system_id, trajectory_id, replica_id, window_id,
protein_residue_index, partner_id)`. Condition is never an identity key.
Rows sort by Dataset replica key, numeric window index, protein source index,
and partner ID. Readers require exact headers, column order, cell counts,
scalars, row contracts, uniqueness and existing deterministic row order.
Writers atomically publish UTF-8 CSV with deterministic scalar formatting,
LF records, and explicit overwrite control. Both layers provide reader, writer
and strict-reader validation wrapper APIs.

**Both CSVs are source-indexed and PRE-CANONICAL. Stage 30 must map protein
residues to UniProt O95436 before final Dataset publication.** Neither table
contains `canonical_residue_number`, `canonical_resname` or `mapping_status`.
Partner IDs remain topology-local. Dataset v1.0 remains unreleased; unresolved
NAMD condition labels remain nullable, without invented labels.

## Workflow, lineage, and offline validation

The existing `mania preprocessing run-graph-export` command needs no new flags.
After normal protein science and retained Stage 27 planning, it validates all
participating metadata before specialized geometry, identifies partners,
computes both layers in one pass, aggregates windows, and writes one combined
catalog and one CSV per layer. A supplied valid empty metadata file still
produces all three artifacts, with header-only source tables. No metadata means
none of these artifacts or roles is emitted.

Actually used metadata enters preprocessing inventory as input role
`molecular_partner_metadata`, using
`input:condition:NNNN:molecular_partner_metadata` and portable path
`inputs/conditions/NNNN/molecular_partner_metadata/<filename>`. The inventory
condition is the execution routing condition, not Dataset identity. This is a
control input, not a Dataset publication table.

Successful output roles are `molecular_partner_catalog`,
`protein_lipid_contacts_by_window_source`, and
`protein_glycan_contacts_by_window_source`, with one combined output each.
All three are referenced by preprocessing provenance. Requested scientific
parameters remain in `resolved_configuration.dataset_context`; resolved temporal
evidence remains in `temporal_execution.json`. The generic RunProvenance schema,
analysis inventories/provenance and PCA consumption are unchanged. Default
checksum mode `none` performs no content hashing; existing `sha256` hashes
these small inputs/outputs through the accepted inventory implementation.

Unified preprocessing validation recognizes all four roles and reuses the strict
readers. Successful completed runs with a metadata input require exactly one
catalog, lipid CSV and glycan CSV, with matching provenance references. Their
Dataset replica identities (including nullable condition), temporal window IDs,
requested/effective bounds, counts/coverage, partner IDs, component membership,
and glycan linkage evidence are cross-checked. Empty sparse tables remain valid;
validation does not require every window, partner, or protein residue to have a
row. Offline validation never opens topology/trajectory contents or recomputes
geometry/time matching. As for other inputs, complete input validation requires
an explicit artifact-ID-to-local-path mapping; no directory scan occurs.

Normal CLI failures exit 1 without tracebacks, with these prefixes:

- `Molecular partner metadata failed:`
- `Molecular partner identification failed:`
- `Specialized contact computation failed:`
- `Specialized contact aggregation failed:`
- `Specialized contact export write failed:`

Existing valid protein science is preserved. Failed specialized stages claim no
successful specialized output roles/references, including partial file writes.
Previously written files are not deleted. Failures are recorded through the
preprocessing adapter's `specialized_contact_export` stage; this adds no generic
provenance schema fields.

## Data-specific acceptance boundary

Synthetic authoritative metadata is sufficient for generic Stage 29 acceptance.
Real NaPi2b partner classifications/grouping/linkage remain a team data input.
A real scientific smoke may use only already authoritative local metadata and a
bounded physical-time slice. Missing real metadata is not a generic completion
blocker and must never be manufactured from residue names. Accepted Stage 28
real protein, temporal, PBC and analysis evidence remains applicable when its
scientific code is unchanged; no hours-long trajectory rerun is required.
