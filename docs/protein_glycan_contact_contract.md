# Protein-glycan per-frame contact contract — Stage 29.C

## Status

Stage 28 is complete. Stage 29.A is accepted. Stage 29.B is accepted.
Stage 29.C protein-glycan per-frame geometry is implemented as the standalone pure
`mania.preprocessing.protein_glycan_contacts` module. Stage 29 remains incomplete.
Stage 29.D is next: window aggregation/export, workflow integration, and final
Stage 29 acceptance.

The accepted Stage 29.B checkpoint is
`a0f2ddcbefb5392cf33071e91c1a2508410cd81f`. The
[frozen Dataset scientific contract](dataset_v1_scientific_contract.md) is unchanged.

## Input and public API

Import directly from `mania.preprocessing.protein_glycan_contacts`; there are no
re-exports through `preprocessing/__init__.py`.

```python
compute_protein_glycan_contacts(
    frame: ProteinGlycanContactFrameInput,
) -> ProteinGlycanContactFrameResult
```

There are no options, configurable cutoff, box, trajectory, or filesystem inputs.
The three new models are frozen dataclasses. Invalid frame, observation, or result
values raise `ProteinGlycanContactComputationError(ValueError)` with deterministic,
portable messages that do not echo supplied paths or metadata.

`ProteinGlycanContactFrameInput` contains these fields in order:

| Field | Contract |
| --- | --- |
| `frame_index` | Non-negative integer source index; bool is rejected. |
| `time_ps` | None or a finite non-negative number; bool is rejected. |
| `topology` | Exact accepted `MolecularPartnerTopology`. |
| `partner_catalog` | Exact accepted `MolecularPartnerCatalog`. |
| `protein_residue_indexes` | Non-empty, strictly increasing, unique tuple of non-negative integer source indexes; bool is rejected. |
| `atom_coordinates` | Tuple of exact accepted `SourceAtomFrameCoordinate` records, strictly increasing and unique by atom index. |

The shared coordinate model is imported unchanged from the accepted
[Stage 29.B API](protein_lipid_contact_contract.md), without a duplicate model or
new coordinate re-export in `__all__`. Its fields are `atom_index`, `x_A`, `y_A`,
`z_A`, and explicit exact-bool `is_hydrogen`. Its existing validation, including
`ProteinLipidContactComputationError` for invalid coordinate construction, is
unchanged. Coordinates are finite Python numbers in Å; bool is rejected.

Every protein residue and supplied atom index must exist in topology. No supplied
protein residue may belong to any partner component. Coordinates are required
for **all** atoms of supplied protein residues and identified glycan partners,
including hydrogens. Lipid coordinates are not required in mixed catalogs.
Unrelated topology coordinates may be supplied and are ignored. Missing required
atoms fail; input is never silently sorted, completed, or repaired.

`time_ps` is informational source traceability only. It affects neither geometry,
partner identity, nor exclusion. Accepted Stage 27 physical sampling/window plans
remain the temporal authority for Stage 29.D windows and lifetime semantics.

## Authoritative partner identity and linkage integrity

[Stage 29.A](molecular_partner_identification_contract.md) supplies partner kind,
name, ID, exact component membership, carrier, first sugar, and linkage evidence.
Stage 29.C performs no glycan identification, sugar classification, membership
inference, regrouping, carrier inference, first-sugar inference, or ID generation.

Every catalog partner's component residues must exist in topology, its complete
source residue evidence must match topology exactly, and its component atom
indexes must equal the topology atom union. Components cannot overlap protein
residues. As in 29.B, these component integrity checks also cover the ignored
partner kind without requiring its coordinates.

Every glycan's carrier must exist and belong to the authoritative protein set.
Its first sugar must exist and belong to its accepted glycan component tuple.
The accepted models forbid a carrier inside the glycan component. Mismatch fails
before geometry; no evidence is reinterpreted.

For `linkage_evidence="topology_connectivity"`, connectivity must be available,
the exact accepted `carrier_link_bond` must remain in topology, and its endpoints
must belong to the declared carrier and first sugar. Directional observation
atom indexes are derived from topology membership, never the canonical bond
tuple orientation. The smaller source atom index can belong to either side.
Accepted explicit grouping is retained even without internal sugar bonds;
Stage 29.C never reruns connectivity grouping or selects a replacement bond.

For `linkage_evidence="external_metadata"`, accepted explicit mapping with
unavailable connectivity and `carrier_link_bond=None` remains valid. Carrier and
first sugar are preserved, while both observation link-atom indexes are None.
No bond or atom index is fabricated. Changing the supplied topology to available
connectivity is inconsistent with that external-only accepted evidence and fails.

Only `partner_kind == "glycan"` participates in geometry. An empty or lipid-only
catalog gives zero glycan partners, evaluated pairs, contacts, and excluded
contacts. The supplied protein representation must still be valid.

## Heavy atoms, whole-partner geometry, and fixed cutoff

Heavy atoms are exactly those with `is_hydrogen is False`. Atom names, types,
resnames, sugar names, elements, and coordinate geometry never infer this status.
Every supplied protein residue and evaluated glycan partner must have at least
one heavy atom. Empty heavy sets fail, including an invalid protein set when no
glycans exist; invalid input cannot establish contact absence.

For each protein residue × whole glycan partner, geometry uses every protein
heavy atom and the heavy atoms across all `partner.component_atom_indexes`:

```text
minimum_distance_A = min(sqrt(dx*dx + dy*dy + dz*dz))
contact-positive iff minimum_distance_A <= 4.5
```

The minimum is finite and non-negative. `math.hypot` evaluates the Cartesian norm
without intermediate squaring overflow/underflow. There is no early exit at the
first positive pair, center of mass, centroid, representative atom, or C-alpha
distance. Multiple sugar residues form one partner observation, including contact
only with a distal component. Same-name partners with different accepted IDs
remain independent.

The cutoff is **4.5 Å inclusive**, with no epsilon. Exactly 4.5 Å is positive;
4.500001 Å is negative. Coordinates are already Å: no engine-based conversion,
nm detection, or magnitude-based unit inference occurs.

| Public constant | Fixed value |
| --- | --- |
| `PROTEIN_GLYCAN_CONTACT_SCHEMA_VERSION` | `mania.protein_glycan_contacts.v0.1` |
| `PROTEIN_GLYCAN_CONTACT_KIND` | `mania_protein_glycan_contacts` |
| `PROTEIN_GLYCAN_CONTACT_CUTOFF_A` | `4.5` |
| `PROTEIN_GLYCAN_DISTANCE_UNIT` | `angstrom` |
| `PROTEIN_GLYCAN_DISTANCE_DEFINITION` | `minimum_heavy_atom_distance` |
| `PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON` | `covalent_carrier_first_sugar_linkage` |

## Covalent exclusion preserves raw geometry

The raw carrier ↔ attached whole-glycan positive observation is retained. The
minimum still includes **all glycan heavy atoms**, including the first sugar and
carrier-link pair. No atom is removed, no substitute minimum is calculated, and
no positive observation or distance is erased.

The exact observation rule is:

| Source protein residue | `standard_summary_excluded` | `standard_summary_exclusion_reason` |
| --- | --- | --- |
| Equals `carrier_residue_index` | True | `covalent_carrier_first_sugar_linkage` |
| Any other supplied protein residue | False | None |

This is explicit scientific evidence for future ordinary-summary exclusion.
**Stage 29.D must exclude marked observations from ordinary occupancy/lifetime
summaries** so the covalent carrier/first-sugar linkage does not artificially
contribute. Stage 29.C performs no such summaries and does not filter its raw
observations. The rule applies equally to topology and external linkage evidence.
Observation validation rejects any other flag/reason combination, including
integer substitutes for bool.

## Sparse observations and deterministic results

Only positive pairs produce `ProteinGlycanContactObservation` records. No negative
rows exist. A valid resolved frame without a positive pair is distinct from
missing/invalid geometry, which fails. Exact field and dictionary key order is:

```text
frame_index, time_ps,
protein_residue_index, protein_residue_id, protein_resname, protein_segid,
glycan_partner_id, glycan_partner_name, glycan_component_residue_indexes,
carrier_residue_index, first_sugar_residue_index, linkage_evidence,
carrier_link_atom_index, first_sugar_link_atom_index,
standard_summary_excluded, standard_summary_exclusion_reason,
minimum_distance_A
```

Protein source identity and atom membership come directly from topology. Source
residue IDs retain integer/string/None values verbatim. Text identity fields use
accepted non-empty stripped strings; component indexes are non-empty, sorted,
unique tuples. Topology link atom indexes are distinct non-negative integers;
external evidence has both None. Observation distance must be in `[0, 4.5]`.

`ProteinGlycanContactFrameResult` has fixed non-init metadata followed by data:

```text
schema_version, kind, cutoff_A, distance_unit, distance_definition,
frame_index, time_ps, protein_residue_count, glycan_partner_count,
evaluated_pair_count, contact_count, excluded_contact_count, contacts
```

The protein count is the supplied protein set size; glycan count is the catalog
glycan count; evaluated pairs are their product. `contact_count = len(contacts)`
includes excluded positives. `excluded_contact_count` counts True exclusion flags.
Counts must be non-negative integers, protein count positive, contact counts
consistent, and observed identity counts no greater than declared totals.
Contacts share frame/time, are unique by `(protein_residue_index, glycan_partner_id)`,
and are sorted by that key, never distance.

`to_dict()` serializes memberships and contacts as lists and absent evidence as
None/JSON null. Identical input serializes byte-identically with
`json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))`.
There are no random IDs, timestamps, or environment metadata.

## PBC and scientific boundary

There is **no internal minimum-image correction**, box argument, dimension
inspection, unwrapping, centering, compaction, or coordinate modification.
Coordinates must satisfy the unchanged external preprocessing/PBC policy; the
scientific PBC protocol remains unresolved. Supplied x = 0.1 and x = 9.9 yield
9.8 Å and no contact, never a wrapped 0.2 Å.

Stage 29.C adds no occupancy, episodes, lifetime, distance aggregation,
`distance_mean_A`, `distance_min_A`, windows, export, workflow/CLI integration,
provenance/inventory, validation integration, or main protein graph modifications.
It reads no trajectories, requires no MDAnalysis, and uses no filesystem, Git,
subprocess, or clock. Existing protein science, Stage 27/28, Stage 29.A/B,
dependencies, analysis, and WANIA are unchanged.

All identities are source topology only. There are no condition or Dataset routing
fields, canonical glycosylation sites, or biological annotations. Canonical
mapping remains Stage 30 and is required before Dataset release publication.
