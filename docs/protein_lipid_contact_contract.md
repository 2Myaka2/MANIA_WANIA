# Protein-lipid per-frame contact contract — Stage 29.B

## Status

Stage 28 is complete. Stage 29.A is accepted. Stage 29.B protein-lipid per-frame
geometry is implemented as the standalone pure
`mania.preprocessing.protein_lipid_contacts` module. Stage 29 remains incomplete.
Stage 29.C protein-glycan contacts is next. Stage 29.D owns window aggregation,
export, workflow integration, and final Stage 29 acceptance.

The accepted Stage 29.A checkpoint is
`fdab41ba82f6bc2e2d510cbec90cd40372f57490`. The
[frozen Dataset scientific contract](dataset_v1_scientific_contract.md) is unchanged.

**Coordinates are supplied in Ångström. There is no box input and no internal
minimum-image correction.** The caller must supply coordinates satisfying the
accepted external PBC preprocessing assumptions. MANIA does not unwrap, center,
compact, inspect box dimensions, or modify coordinates in this layer. The broader
scientific PBC protocol remains unresolved.

## Input and public API

Import directly from `mania.preprocessing.protein_lipid_contacts`; there are no
new re-exports through `preprocessing/__init__.py`.

```python
compute_protein_lipid_contacts(
    frame: ProteinLipidContactFrameInput,
) -> ProteinLipidContactFrameResult
```

The API has no cutoff, periodic box, atom-filter, or other scientific options.
It accepts no trajectory object or filesystem input and requires no MDAnalysis.
All four public models are frozen dataclasses. Invalid model values, inconsistent
catalog/topology evidence, missing coordinates, invalid heavy-atom sets, and
unrepresentable minimum distances raise
`ProteinLipidContactComputationError(ValueError)`. Messages are deterministic and
portable, without echoing supplied metadata or local filesystem paths. No input
is repaired, reordered, or silently completed.

`ProteinLipidContactFrameInput` contains, in order:

- `frame_index`: a non-negative integer source frame index, excluding bool;
- `time_ps`: None or a finite non-negative numeric time;
- `topology`: an exact accepted `MolecularPartnerTopology`;
- `partner_catalog`: an exact accepted `MolecularPartnerCatalog`;
- `protein_residue_indexes`: a non-empty, strictly increasing, unique tuple of
  non-negative integer source residue indexes, excluding bool;
- `atom_coordinates`: a tuple of exact `SourceAtomFrameCoordinate` records,
  strictly increasing and unique by atom index.

The protein set is authoritative caller input. Every selected protein residue
must exist in the topology and must not belong to any catalog partner component.
Protein identity is never inferred from residue names.

`SourceAtomFrameCoordinate` contains exactly `atom_index`, `x_A`, `y_A`, `z_A`,
and `is_hydrogen`, in that order. The atom index is non-negative integer source
topology identity, excluding bool. Coordinate values are finite Python numbers
(int or float, excluding bool), and may be negative. `is_hydrogen` must be exact
bool. There are no atom-name, inferred-element, or residue-name fields.

Every supplied coordinate atom must exist in the topology. Coordinates are
required for every atom of every selected protein residue and every identified
lipid partner, including hydrogen atoms. Unrelated topology atoms may be supplied
and are ignored. Solvent or glycan coordinates are not required for this lipid
calculation. Missing atoms fail instead of being silently skipped.

## Catalog authority and partner semantics

The [accepted Stage 29.A catalog](molecular_partner_identification_contract.md)
defines partner kind, name, ID, and exact membership. Stage 29.B never decides
what is a lipid: it selects only `partner_kind == "lipid"`. It does not reclassify,
regroup, infer connectivity, merge components, or generate partner IDs.

Before geometry, every catalog partner's component residues must exist in the
supplied topology. Complete component source evidence must equal the topology
records, and `component_atom_indexes` must equal the union of the topology atom
membership of those component residues. No component may overlap the supplied
protein set. Individually valid models from different topologies can fail these
cross-input checks. Catalog mismatch fails; membership is never reconstructed.

One identified molecular partner is one lipid entity even if it contains multiple
topology residues. Geometry uses all its accepted component atom indexes. A contact
with any component can therefore produce one observation for the whole partner.
Same-name disconnected partners retain their distinct accepted IDs and produce
separate observations. Partner IDs and names are copied unchanged.

Mixed lipid/glycan catalogs are valid. Glycan component evidence undergoes the
same topology consistency checks, but glycan partners have no geometry evaluation
or coordinate requirement here. An empty or glycan-only catalog is valid:
`lipid_partner_count = evaluated_pair_count = contact_count = 0` and `contacts = ()`.
The supplied protein representation must still be valid.

## Explicit heavy atoms

Only coordinates with `is_hydrogen is False` participate. The caller explicitly
supplies hydrogen/heavy status; Stage 29.A deliberately retains all source atoms
without assigning it. There are no atom-name, residue-name, mass, geometry,
force-field, or string-prefix heuristics.

Every selected protein residue and identified lipid partner must have at least
one heavy atom. An empty heavy-atom set is invalid scientific input and fails;
it cannot establish contact absence, even when no lipid partners exist.

Stage 29.D may adapt authoritative runtime topology metadata into this pure
contract. If authoritative runtime atom typing is unavailable, that integration
must fail instead of inferring heavy atoms. This keeps the contract portable
across GROMACS, NAMD, and different force fields/topologies.

## Distance, units, and fixed boundary

For every protein residue × lipid partner, compute the minimum over **all**
protein heavy atom × lipid-partner heavy atom pairs:

```text
minimum_distance_A = min(sqrt((x2-x1)^2 + (y2-y1)^2 + (z2-z1)^2))
contact-positive iff minimum_distance_A <= 6.0
```

This is ordinary Cartesian Euclidean distance on the supplied Å coordinates,
using deterministic standard Python arithmetic. The implementation uses
`math.hypot(dx, dy, dz)` for the Euclidean norm, avoiding intermediate squaring
overflow/underflow. The resulting minimum must be finite and non-negative.
There is no early exit at the first positive atom pair, average, center of mass,
center of geometry, representative atom, or C-alpha distance.

The cutoff is **6.0 Å inclusive**, with no configurable cutoff and no scientific
tolerance. There is no unit auto-detection, nm conversion, engine inspection, or
magnitude-based inference. Any future runtime conversion belongs to a validated
Stage 29.D adapter.

| Public constant | Fixed value |
| --- | --- |
| `PROTEIN_LIPID_CONTACT_SCHEMA_VERSION` | `mania.protein_lipid_contacts.v0.1` |
| `PROTEIN_LIPID_CONTACT_KIND` | `mania_protein_lipid_contacts` |
| `PROTEIN_LIPID_CONTACT_CUTOFF_A` | `6.0` |
| `PROTEIN_LIPID_DISTANCE_UNIT` | `angstrom` |
| `PROTEIN_LIPID_DISTANCE_DEFINITION` | `minimum_heavy_atom_distance` |

## Sparse observations, source identity, and result

Each `ProteinLipidContactObservation` represents one positive protein residue ×
accepted lipid molecular partner × sampled frame. Only positive observations
exist; there are no atom-level rows or `contact=false` rows. A pair with a minimum
greater than 6.0 Å produces no observation. On a successfully evaluated frame,
absence of a positive row is observed contact absence for future occupancy.
Invalid frames fail and cannot be treated as negative observations.

Observation fields and deterministic dictionary key order are:

```text
frame_index, time_ps,
protein_residue_index, protein_residue_id, protein_resname, protein_segid,
lipid_partner_id, lipid_partner_name, lipid_component_residue_indexes,
minimum_distance_A
```

Protein source fields are copied directly from the accepted topology residue.
Source `residue_id` remains an integer, string, or None, including negative
integers and unchanged strings; bool is invalid. Names, partner IDs, and non-None
segids follow accepted non-empty stripped-string semantics. Component residue
indexes form a non-empty, sorted, unique tuple. Observation distance must be
finite and in `[0, 6.0]`.

Partner ID is source-topology-local Stage 29.A identity. Protein residue identity
is source topology identity. Neither implies canonical mapping; Stage 30 remains
responsible. No condition, dataset, trajectory, replica, or canonical fields are
added to these models.

`ProteinLipidContactFrameResult` has fixed non-init metadata and this root key order:

```text
schema_version, kind, cutoff_A, distance_unit, distance_definition,
frame_index, time_ps, protein_residue_count, lipid_partner_count,
evaluated_pair_count, contact_count, contacts
```

`protein_residue_count` is the supplied protein set size; `lipid_partner_count` is
the number of catalog lipid partners. `evaluated_pair_count` is their product and
`contact_count = len(contacts)`. Contacts are unique and ordered by
`(protein_residue_index, lipid_partner_id)`, never by distance. All observations
must share the result frame/time, and observed identity counts cannot exceed
the declared counts.

Coordinate, observation, and result `to_dict()` methods return deterministic
JSON-compatible dictionaries, using lists for serialized membership and contacts.
Repeated computation on identical input produces byte-identical output from:

```python
json.dumps(result.to_dict(), allow_nan=False, separators=(",", ":"))
```

There are no generated timestamps, random IDs, or environment metadata.

## Time and Stage boundary

`time_ps` is informational source traceability only. It does not determine
contacts, group partners, or calculate lifetimes. The accepted Stage 27 physical
sampling/window plan remains temporal authority for future Stage 29.D
episode/lifetime aggregation, as in Stage 28.

Stage 29.B adds no protein-glycan contact calculation, window aggregation,
occupancy, episodes/lifetime, distance mean/min aggregation, CSV export, workflow
or CLI integration, provenance/inventory, unified validation, or main protein
graph changes. The main dynRIN remains protein-only. Existing Stage 27/28 and
protein-contact science, PBC behavior, analysis, dependencies, and WANIA are unchanged.

## Synthetic scientific checks

| Supplied geometry | Expected result |
| --- | --- |
| Protein heavy x = 0, 10; one two-residue lipid with heavy x = 20, 16 | Minimum 6.0 Å, one partner contact. |
| Move the nearest lipid atom to x = 16.000001 | Minimum above 6.0 Å, no contact. |
| Protein heavy x = 0, H x = 100; lipid heavy x = 10, H x = 100.1 | Heavy-heavy minimum 10 Å, no contact despite nearby hydrogens. |
| Protein heavy x = 0.1; lipid heavy x = 9.9 | Cartesian distance 9.8 Å, no contact; never wrapped to 0.2 Å. |

All other axes are zero. Synthetic tests also cover identity preservation,
multi-residue minima, distinct same-name partners, mixed catalogs, deterministic
serialization, and integrity failures without trajectory files or MDAnalysis.
