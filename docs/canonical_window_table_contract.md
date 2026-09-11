# Canonical window table contract

## Status

Stage 29 is complete. Stage 30.A is accepted. Stage 30.B is accepted.
Stage 30.C canonicalized intermediate tables are implemented.
Stage 30 remains incomplete. Stage 30.D biological annotations and
workflow/provenance/validation integration is next. Dataset v1.0 remains
unreleased; its frozen scientific contract is unchanged.

## Inputs and explicit Dataset binding

`mania.canonical_window_tables` consumes only the accepted exact source types:

- Stage 28 `DatasetProteinEdgeWindowTable`;
- Stage 29 `ProteinLipidWindowTable`;
- Stage 29 `ProteinGlycanWindowTable`.

The frozen `DatasetCanonicalResidueMappingBinding` declares, in order,
`dataset_id`, `system_id`, `trajectory_id`, `replica_id`, and `mapping_table`.
Identifiers must be non-empty stripped strings; the mapping must have the exact
accepted `CanonicalResidueMappingTable` type. Its derived `replica_key` is
`(dataset_id, system_id, trajectory_id, replica_id)`.

`DatasetCanonicalResidueMappingBindings` contains only a tuple named `bindings`.
Replica keys must be unique and already in deterministic lexical order.
`lookup(replica_key)` returns the explicitly assigned mapping table or raises
`CanonicalWindowTableError`. There is no condition or engine lookup. Two replicas
with the same condition can have different mappings. `condition=None` remains
None, including NAMD rows. No condition labels are invented.

Each collection validates every mapping through the accepted
`validate_canonical_residue_mapping_table(..., reference=...)`, using only
`load_default_napi2b_canonical_reference()`. Mapping structure, records and fixed
reference metadata are also checked for bypassed frozen-model invariants. Extra
bindings are allowed, including replicas absent from sparse source tables.
An empty source table accepts an empty binding collection and yields an empty
canonical table. No mapping coverage is inferred from an empty result.

This binding is an in-memory application contract. It contains no paths,
manifest fields, automatic mapping-file reads, or preprocessing integration.
Stage 30.D will bind authoritative external mapping files to real trajectories.
Synthetic explicit mappings suffice for this stage; they make no claim to be
real GROMACS/NAMD Dataset mappings.

## Mapping authority

After selecting the table by the exact replica key, every emitted protein
residue requires this exact four-field source key:

```text
(source_engine, source_chain_id, source_resid, source_resname)
```

Engine comes from `row.engine`. Edges use each side's source evidence;
specialized rows use `protein_chain_id`, `protein_resid`, and `protein_resname`.
Chain None matches only None. Protein resid must be a non-empty string; an
internal residue index never supplies a missing resid. Lookup is case-sensitive
and the retrieved record's complete key must equal the requested key.

Missing records and explicit `mapping_status="unmapped"` records fail the entire
build. No row is dropped, merged, silently deduplicated, or emitted with blank
canonical cells. There is no numeric equality rule, offset, sequence alignment,
source-name inference, or live UniProt dependency. Source `"311"` can explicitly
map to canonical 312; removing that mapping fails even if canonical 311 and its
amino acid happen to match the source.

Canonical numbers/names are validated through the accepted Stage 30.B resolution
helper against local O95436-1 sequence v3, reference ID
`uniprotkb:O95436-1:sequence-v3`, sequence SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
Every canonical row construction, root construction, and write validates the
canonical targets. The sequence and residue-name logic are not duplicated.
Builders access only passed models and the packaged local reference, with no
source/output file access, network, trajectory access, or process execution.

## Variants and source evidence

Source and canonical residue names are independent evidence. For T330M:

```text
source:    gromacs / A / "330" / MET
canonical: 330 / THR
```

Both MET and THR persist in the canonical row and CSV round trip. Source MET
must not be rewritten to THR, and the difference is not a validation error.
Canonical MET at pinned position 330 does fail reference validation.

## Protein edges

`build_canonical_protein_edge_window_table(source_table, *, mapping_bindings)`
returns a frozen `CanonicalProteinEdgeWindowTable` of exact frozen
`CanonicalProteinEdgeWindowRow` records.

Canonical orientation requires `source_canonical_residue_number <
target_canonical_residue_number`. If necessary, all six evidence fields of each
side swap together: source topology residue index, chain, resid, resname,
canonical number, and canonical name. Dataset/window evidence, edge type, and
all scientific metrics retain their values. Source indexes can therefore be in
descending order in a valid canonical edge. Validation delegates to the accepted
Stage 28 source row using a private copy restored to source-index orientation;
it never changes the canonical row or input table.

A canonical self-loop fails. Unique row identity is exactly:

```text
(dataset_id, system_id, trajectory_id, replica_id, window_id,
 source_canonical_residue_number, target_canonical_residue_number, edge_type)
```

Distinct source edges that collapse to this identity fail. Repeated canonical
targets permitted by Stage 30.B do not permit ambiguous application identities.
There is no merge, averaging, or deduplication. Condition is not an identity field.

## Specialized layers

The lipid and glycan builders have the same keyword-only binding API:
`build_canonical_protein_lipid_window_table` and
`build_canonical_protein_glycan_window_table`. They return their corresponding
frozen `CanonicalProteinLipidWindowRow/Table` and
`CanonicalProteinGlycanWindowRow/Table` models.

Only the contacting protein residue receives `canonical_residue_number` and
`canonical_resname`. Lipid/glycan partner IDs, names and component membership
remain source-topology-local and unchanged. Glycan carrier residue index,
first-sugar residue index, linkage evidence and both link atom indexes are
retained unchanged. Neither sugar residues nor carrier source indexes are
interpreted as canonical positions.

Each specialized identity is exactly:

```text
(dataset_id, system_id, trajectory_id, replica_id, window_id,
 canonical_residue_number, lipid_partner_id OR glycan_partner_id)
```

Two different source protein residues mapping to the same canonical position
for the same partner/window/replica fail. Distinct partner IDs stay distinct.
There is no specialized `edge_weight` or canonical partner identity.

## Root models and evidence preservation

All three roots accept only a tuple of exact corresponding rows, including an
empty tuple. Non-init public fields are `schema_version`, `kind`,
`canonical_reference_id`, and `canonical_reference_sequence_sha256`.
`row_count` is derived. Deterministic `to_dict()` writes these four metadata
fields, then row count, then rows in order. Component tuples serialize to
independent lists. Row dictionaries follow declaration order.

| Layer | Schema version | Kind |
| --- | --- | --- |
| Protein edge | `mania.canonical_protein_edges_by_window.v0.1` | `mania_canonical_protein_edges_by_window` |
| Lipid | `mania.canonical_protein_lipid_contacts_by_window.v0.1` | `mania_canonical_protein_lipid_contacts_by_window` |
| Glycan | `mania.canonical_protein_glycan_contacts_by_window.v0.1` | `mania_canonical_protein_glycan_contacts_by_window` |

All Dataset fields and Stage 27 temporal evidence copy unchanged: requested and
effective bounds, window ID/index, endpoint inclusion, counts and coverage.
Stage 28 metrics copy unchanged: contact frames, occupancy, episode count,
mean/max episode length and edge weight. Stage 29 copies the same first five
metrics plus mean/minimum distance. Validation reuses accepted source model
checks and does not recalculate metrics, episodes, geometry, or time matching.

## Exact CSV contracts

`mania.canonical_window_tables_io` provides three column tuples and matching
`read_canonical_protein_{edge,lipid,glycan}_window_csv`,
`write_canonical_protein_{edge,lipid,glycan}_window_csv`, and
`validate_canonical_protein_{edge,lipid,glycan}_window_csv` APIs.
Writers receive a table and output directory, with keyword `overwrite=False`.

| Filename | Columns | Accepted source columns |
| --- | ---: | ---: |
| `protein_edges_by_window_canonical.csv` | 38 | 34 |
| `protein_lipid_contacts_by_window_canonical.csv` | 35 | 33 |
| `protein_glycan_contacts_by_window_canonical.csv` | 40 | 38 |

Every header follows model declaration order. All begin with:

```text
dataset_id,system_id,trajectory_id,variant_id,engine,condition,replica_id,disulfide_state,
window_id,window_index,requested_window_start_ns,requested_window_end_ns,right_endpoint_inclusive,
effective_window_start_ns,effective_window_end_ns,requested_sample_count,resolved_frame_count,
missing_sample_count,coverage_fraction
```

Protein-edge fields then follow in this exact order:

```text
source_residue_index,source_chain_id,source_resid,source_resname,
source_canonical_residue_number,source_canonical_resname,
target_residue_index,target_chain_id,target_resid,target_resname,
target_canonical_residue_number,target_canonical_resname,edge_type,
n_contact_frames,occupancy,n_contact_episodes,mean_episode_length_ns,max_episode_length_ns,edge_weight
```

Both specialized layers next use:

```text
protein_residue_index,protein_chain_id,protein_resid,protein_resname,
canonical_residue_number,canonical_resname
```

Lipid partner fields:

```text
lipid_partner_id,lipid_partner_name,lipid_component_residue_indexes
```

Glycan partner/linkage fields:

```text
glycan_partner_id,glycan_partner_name,glycan_component_residue_indexes,
carrier_residue_index,first_sugar_residue_index,linkage_evidence,
carrier_link_atom_index,first_sugar_link_atom_index
```

Both specialized layers end with:

```text
n_contact_frames,occupancy,n_contact_episodes,mean_episode_length_ns,
max_episode_length_ns,distance_mean_A,distance_min_A
```

Displayed wraps are for readability; each actual CSV header is one line.
There is no `mapping_status` column and no biological annotation columns.

## Strictness, ordering, and atomic persistence

Builders sort the resulting rows; root constructors and readers require the
existing deterministic canonical order and never silently sort external files.
Edges sort by Dataset replica key, window index, edge type, source canonical
number, then target canonical number. Specialized rows sort by Dataset replica
key, window index, canonical protein number, then partner ID.

Readers require exact headers/order/cell counts, lowercase `true`/`false`,
strict non-negative integer syntax without signs or leading zeros, finite
floats, valid rows, canonical targets, unique identities and sorted rows.
Required cells cannot be blank. Optional condition, disulfide state, chains,
and linkage atom indexes use blank cells for None; placeholder strings such as
`None`, `null`, and `NA` are rejected there. Protein resids cannot be None on
canonical rows. Component membership uses semicolon-separated strictly
increasing unique non-negative integers, for example `40;41`.

Writers use the accepted atomic text publication helper, UTF-8, the standard
`csv` module, LF records, and an always-present header. Header-only files are
valid. Floats retain their ordinary round-trip representation without scientific
rounding. Identical input produces identical bytes across output directories.
No timestamps, random identifiers, content checksums, or discovery scans enter
these CSVs. Overwrite uses atomic replacement; default publication uses an
atomic no-clobber link, including concurrent creation protection. Cleanup touches
only the writer's temporary file.

Frozen write results and validation issue/report types reuse the accepted Stage
28 technical outcome contract under canonical I/O names. Reports retain path,
row count or None, issues, and `passed`. Each validator delegates to its strict
reader once; no mapping or scientific calculations are added to the validator.
CSV validation proves the canonical table contract, not a join back to an
external mapping artifact; workflow lineage verification belongs to 30.D.

## Intermediate status and no source mutation

The `_source.csv` artifacts remain authoritative source-evidence artifacts;
their names, schemas, bytes, source objects, and mapping inputs are unchanged.
These three canonical outputs are additive intermediate tables, not final
biologically annotated Stage 30 release outputs.

No ECD/MX35, glycosylation, variant-site, disulfide-site, or other biological
annotations are attached. There are no CLI/manifest changes, automatic exports,
provenance/inventory changes, or unified validation integration. Stage 27–29
science, PBC, analysis, dependencies and WANIA are unchanged. Stage 30.D remains
required for biological annotations/integration and final Stage 30 acceptance.
