# Biological annotation and Stage 30 preprocessing contract

Stage 30.D adds complete system annotations and integrates accepted Stage
30.A/B/C reference, mapping, and canonical tables into preprocessing. All
artifacts described here are reproducible Dataset intermediate artifacts.
Stage 33 owns publication bundles and final export. Dataset v1.0 remains
unreleased; authoritative real mapping and annotation inputs are still required.

## Two annotation categories

Reference-derived flags are deterministic functions of the packaged O95436-1
canonical position, validated through the accepted local reference:

| Region | Inclusive canonical positions |
| --- | --- |
| ECD | 234..361 |
| MX35 region | 311..341 |

`NAPI2B_ECD_START=234`, `NAPI2B_ECD_END=361`, `NAPI2B_MX35_START=311`, and
`NAPI2B_MX35_END=341` are frozen constants. `is_napi2b_ecd_residue(number)` and
`is_napi2b_mx35_residue(number)` reject bools, non-integers and positions outside
1..690. Every position 311..341 is both ECD and MX35. These helpers need no
system annotation file and accept no source residue identifiers.

System-supplied glycosylation and variant site annotations require explicit
metadata. MANIA never infers them from sequence motifs, residue names,
connectivity, topology glycans, the Stage 29 partner catalog, `variant_id`,
`disulfide_state`, or a source/canonical mismatch. No final glycan names, residue
lists, evidence strings, or team-member identities are hardcoded as science.

## Complete system metadata

`mania.biological_annotations` exposes frozen dataclasses:

| Model | Fields in declaration order |
| --- | --- |
| `GlycosylationSiteAnnotation` | `canonical_residue_number`, `canonical_resname`, `present_in_topology`, `glycan_name`, `source`, `verifier` |
| `CanonicalVariantSiteAnnotation` | `canonical_residue_number`, `canonical_resname`, `source`, `verifier` |
| `DatasetSystemBiologicalAnnotations` | `dataset_id`, `system_id`, `annotation_scope`, `glycosylation_sites`, `disulfide_variant_sites`, `cysteine_variant_sites` |

Canonical number/name pairs must match the packaged reference exactly. Booleans
must be exact bools. Identifiers, glycan names, source and verifier strings must
be non-empty, already stripped strings; MANIA validates and preserves them.
`present_in_topology` is supplied evidence, including an explicit false value;
it is never derived by reading topology. The two variant lists contain **site
annotations only**, with no inferred disulfide bonds or bond-pair semantics.
Sites may be listed in both distinct variant lists when explicitly supplied.

`annotation_scope` must equal `"complete_for_system"`. A valid file represents
one complete Dataset system, with exhaustive lists. Each list is an immutable
tuple of exact site records, in ascending canonical position order, with no
repeated positions within that list. Incomplete scopes, unknown scopes,
duplicate sites, and unsorted lists fail. No system is inferred from condition.

For a complete system, `annotation_for_residue(number)` creates a frozen
`CanonicalResidueBiologicalAnnotation` with canonical number/name, `is_ecd`,
`is_mx35_region`, and these system-supplied fields:

1. `is_glycosylation_site`
2. `glycosylation_present_in_topology`
3. `glycan_name`
4. `glycosylation_source`
5. `glycosylation_verifier`
6. `is_disulfide_variant_site`
7. `is_cysteine_variant_site`

Absence from an exhaustive site list means false. For a non-glycosylation site,
all four glycosylation detail fields are None. For a listed site, topology
presence is an exact bool and all three detail strings are required. Region
flags must equal the frozen canonical ranges. This record has no source
topology fields.

**Without complete metadata there are no system-supplied annotated outputs.**
Unknown biological information is never converted to false. Reference-derived
flags alone do not authorize a partially annotated artifact.

## Strict JSON controls

`mania.biological_annotations_io` provides
`read_dataset_system_biological_annotations(path)`,
`write_dataset_system_biological_annotations(annotations, path, overwrite=False)`,
and `validate_dataset_system_biological_annotations(path)`.
The preferred filename is `biological_annotations.json`; callers choose paths.

The exact root keys, in deterministic writer order, are:

1. `schema_version`: `mania.dataset_system_biological_annotations.v0.1`
2. `kind`: `mania_dataset_system_biological_annotations`
3. `dataset_id`
4. `system_id`
5. `annotation_scope`: `complete_for_system`
6. `glycosylation_sites`
7. `disulfide_variant_sites`
8. `cysteine_variant_sites`

Each array row has exactly its model's fields above. Readers reject unknown or
missing fields, duplicate JSON keys, malformed UTF-8/JSON, non-finite constants,
incorrect scalars, and invalid canonical pairs. JSON object key order need not
match writer order; site arrays must already follow canonical order. Writers
use UTF-8, two-space indentation, `allow_nan=False`, and one trailing newline.
Atomic temporary-file publication protects existing and concurrently created
files unless overwrite is explicit. Errors are deterministic and portable.
No API uses the network, Git, or clock.

## Dataset execution binding and manifest controls

Each existing trajectory manifest entry may supply:

```yaml
canonical_residue_mapping_path: controls/canonical_residue_mapping.json
biological_annotation_metadata_path: controls/biological_annotations.json
```

These are optional `Path | None` fields. Absent controls add no null keys to
legacy serialization. Declared path spelling remains unchanged in the manifest;
relative control paths resolve against the manifest directory, following
accepted manifest control semantics. An annotation path requires a mapping path.
Either requires an explicit inline Dataset specification or Dataset table
reference. A legacy execution condition cannot bind canonical controls.

After Dataset specification resolution and before trajectory loading/science,
preflight strictly reads mapping JSON using Stage 30.B and biological JSON using
30.D. Mapping files carry no Dataset identity: the manifest explicitly binds
them to the resolved `(dataset_id, system_id, trajectory_id, replica_id)` key
through accepted `DatasetCanonicalResidueMappingBindings`. Full 690-position
coverage is unnecessary; Stage 30.C requires only source keys represented by
rows being canonicalized. Missing, unmapped and colliding mappings fail.

`DatasetBiologicalAnnotationBinding(dataset_id, system_id, annotations)` and
`DatasetBiologicalAnnotationBindings(bindings)` use exactly
`(dataset_id, system_id)`. The file's root identity must match that resolved
system. Equivalent files shared by replicas yield one system binding; all
supplied contents for that system must be exactly equal, otherwise preflight
fails. Distinct system/path inputs remain explicit provenance entries.
Condition, trajectory and replica never choose biological flags. Replicas of a
system receive identical annotations for each canonical residue; systems with
the same condition remain distinct. NAMD `condition=None` remains None through
source, canonical and annotated CSVs and strict offline validation.

## Additive table enrichment

With any mapping configured, preprocessing uses accepted Stage 30.C builders on
each successfully exported existing Stage 28/29 source table. It never scans
for source artifacts or fabricates missing source tables. Every represented
Dataset replica must have a mapping; combined tables are never partially mapped.

| Source | Canonical output | Annotated output |
| --- | --- | --- |
| `protein_edges_by_window_source.csv` | `protein_edges_by_window_canonical.csv` | `protein_edges_by_window_canonical_annotated.csv` |
| `protein_lipid_contacts_by_window_source.csv` | `protein_lipid_contacts_by_window_canonical.csv` | `protein_lipid_contacts_by_window_canonical_annotated.csv` |
| `protein_glycan_contacts_by_window_source.csv` | `protein_glycan_contacts_by_window_canonical.csv` | `protein_glycan_contacts_by_window_canonical_annotated.csv` |

If no system supplies annotations, only canonical outputs are generated. If
annotations are requested, every system represented by the corresponding
non-empty canonical table must have complete metadata. A missing binding fails;
rows are neither omitted nor filled with false/unknown values. Empty canonical
tables can produce header-only annotated CSVs without a binding for any row.

`mania.annotated_window_tables` consumes exact Stage 30.C table models through
`build_annotated_canonical_protein_edge_window_table`,
`build_annotated_canonical_protein_lipid_window_table`, and
`build_annotated_canonical_protein_glycan_window_table`, each with keyword
`annotation_bindings`. Canonical tables and their schemas remain unchanged.

Annotated rows copy every canonical field in its accepted order and append
`is_ecd`, `is_mx35_region`, and the seven system fields listed above. Protein
edges append the nine `source_` fields first and the nine `target_` fields next.
Specialized rows append nine unprefixed protein fields. Lipid/glycan partners
retain their Stage 29 identity and linkage evidence and are never annotated as
protein residues. Annotation fields do not participate in row identity.

No occupancy, lifetime, distance, edge-weight, temporal field, mapping,
orientation or source evidence is recalculated. T330M source `"330" / MET`
remains distinct from canonical `330 / THR`. Canonical 330 sets ECD/MX35 true;
it does not set any supplied variant flag without an explicit site-list entry.
An explicit source `"311"` mapping to canonical 312 uses position 312 for flags.

`mania.annotated_window_tables_io` exposes exact column tuples and strict
`read_annotated_canonical_protein_{edge,lipid,glycan}_window_csv`,
`write_annotated_canonical_protein_{edge,lipid,glycan}_window_csv`, and matching
`validate_...` functions. Stage 30.C CSV conventions are retained: exact headers,
strict scalar spellings, empty cells for None, lowercase true/false, semicolon
partner-index tuples, deterministic row order, header-only empty tables,
duplicate identity rejection, atomic publication and overwrite protection.

## Portable lineage and offline validation

Preprocessing configuration records `canonical_reference` whenever mapping is
used, with reference ID `uniprotkb:O95436-1:sequence-v3` and sequence SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
`canonical_residue_mapping_bindings` records four-field replica keys plus
`mapping_path`. `biological_annotation_bindings` records two-field system keys
plus `annotation_metadata_path`. Paths refer to portable input inventory paths;
complete controls are never embedded in provenance. Generic RunProvenance is
unchanged, with no new runtime timestamp or live reference fetch.

Input roles are `canonical_residue_mapping` and
`biological_annotation_metadata`. Inputs are ordered by replica/system key and
path; IDs are `input:<role>:0001`, etc., with portable paths
`inputs/<role>/0001/<filename>`. Shared annotations use one entry per unique
system/path. Mapping inputs remain explicit per replica. No condition labels
enter these IDs or scientific bindings. Output roles are the six CSV stems in
the table above, with IDs `output:<role>`. Only successful writes enter inventory
and provenance. All paths are portable, and generic provenance references carry
no checksums. Checksum `none` records null hashes; opt-in `sha256` hashes declared
inputs and outputs using the accepted inventory policy, with no directory scan.

Unified preprocessing validation strictly reads each explicitly mapped external
control and each declared CSV. It cross-checks Dataset keys, reference identity,
portable binding paths, inventory entries and provenance references. It rebuilds
canonical tables with accepted 30.C builders from source tables and mapping
inputs, then rebuilds annotated tables with the same 30.D builders and complete
system controls. Exact model equality is required. Biological/mapping formulas
are not independently implemented in the validator.

Completed runs require canonical output whenever mapping is used and its source
exists; annotations additionally require annotated output. Outputs without their
input/canonical/source lineage fail, as do unclaimed known output files. Old
runs without mapping require no Stage 30 artifacts. Unresolved external input
paths remain partial validation, never a complete pass. Failed runs may lack
outputs from the failed stage; successfully claimed outputs still validate.
Current roles have no unsupported-role warnings. Analysis/PCA and analysis
inventory/provenance do not consume or propagate Stage 30 artifacts.

Preflight errors begin `Canonical residue mapping failed:` or
`Biological annotation failed:`. Late failures use
`Canonical table generation failed:`, `Canonical table export write failed:`,
`Biological annotation failed:`, or `Annotated table export write failed:`.
Late failures retain already generated Stage 28/29 science and record failed
preprocessing provenance without claiming missing outputs. No traceback is
printed for expected control/export failures.

Stage 30 operates exclusively on controls, the packaged reference and existing
source tables: **zero additional trajectory passes**. Scientific loading,
physical-time execution, contacts, PBC and analysis remain unchanged. PBC science
is unresolved; no internal minimum-image correction is introduced. Dependencies,
version 0.1.0, WANIA, and the frozen Dataset scientific contract remain unchanged.
Synthetic controls provide reproducible technical evidence without claiming real
NaPi2b annotations. Real smoke requires existing authoritative controls; absent
controls are never fabricated.
