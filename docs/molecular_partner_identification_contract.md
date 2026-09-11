# Molecular partner identification contract — Stage 29.A

## Status

Stage 28 is complete. Stage 29.A topology/entity identification is implemented
as two standalone pure modules. Stage 29 remains incomplete. Stage 29.B
protein-lipid contacts is next; Stage 29.C owns protein-glycan contacts and
Stage 29.D owns window aggregation/export, workflow integration, and acceptance.
Lipid/glycan contact calculations and workflow integration do not exist in 29.A.

The accepted Stage 28.D checkpoint is
`b26263666803d6a18a5919ee839f0ed953cdd208`. The
[frozen Dataset scientific contract](dataset_v1_scientific_contract.md) is
unchanged. Stage 29.A implements its identity prerequisite without amending it.

## Why this layer exists

Distance calculation is meaningless until molecular partner identity is defined.
One partner may contain several source residues. Future Stage 29.B/C calculations
need exact molecular membership, and glycans also need carrier/first-sugar
evidence for the covalent-linkage exclusion.

**Classification is supplied metadata; grouping establishes one molecular entity.**
A `MolecularPartnerComponentClassification` states that one source residue
participates as `lipid` or `glycan`, with an explicit `partner_name`. It does not
say which other residues belong to the same molecule. Grouping comes from
authoritative topology connectivity or an `ExplicitMolecularPartnerDefinition`.

MANIA never classifies a lipid/glycan merely from resname patterns. There are no
residue lists, substring/regex rules, atom-name rules, chain-name rules, or
element/composition heuristics for partner kind. Unclassified residues produce
no partners, whatever their names. `partner_name` is caller-supplied source/Dataset
metadata, with no imposed biological vocabulary. `condition` is neither an API
input nor a classification, grouping, or partner identity key.

## Public API and source models

Import contracts directly from `mania.preprocessing.molecular_partner_entities`
and identification from `mania.preprocessing.molecular_partner_identification`.
There are no new re-exports in `preprocessing/__init__.py`.

```python
identify_molecular_partners(
    topology: MolecularPartnerTopology,
    *,
    protein_residue_indexes: tuple[int, ...],
    classifications: tuple[MolecularPartnerComponentClassification, ...],
    explicit_partners: tuple[ExplicitMolecularPartnerDefinition, ...] = (),
) -> MolecularPartnerCatalog
```

All records are frozen dataclasses. Model validation raises `ValueError`;
cross-input identification failures raise the public
`MolecularPartnerIdentificationError(ValueError)`. Errors are deterministic,
portable, and do not echo user-supplied paths or metadata values.

- `SourceTopologyResidue` retains `residue_index`, `residue_id`, `resname`,
  `segid`, and `atom_indexes`. The internal/source index identifies membership;
  source `residue_id` (integer/string/None) need not be unique, and `segid` may be
  None. Source residue IDs are preserved verbatim, including string values.
- `SourceTopologyBond` retains two distinct non-negative integer atom indexes,
  canonicalizing only orientation so the smaller atom index comes first.
- `MolecularPartnerTopology` requires `residues`, `bonds`, and an explicit
  `connectivity_status`. Every atom has exactly one source residue owner, and
  every bond endpoint must exist. Duplicate residues or bonds are rejected.
- `MolecularPartnerComponentClassification` requires a source `residue_index`,
  exact supported `partner_kind`, and `partner_name`.
- `ExplicitMolecularPartnerDefinition` requires `partner_id`, `partner_kind`,
  `partner_name`, and `component_residue_indexes`. Optional glycan fields are
  `carrier_residue_index`, `first_sugar_residue_index`, and `linkage_evidence`.

Following the accepted local models, normalized text means a non-empty string
already stripped of leading/trailing whitespace. Invalid text is rejected,
not silently rewritten. This applies to names, partner IDs, and non-None segids;
source `residue_id` remains verbatim. Boolean indexes and boolean residue IDs are
rejected. Membership tuples are non-empty, strictly increasing, and unique.
Topology residues must already be ordered by `residue_index`; canonical bonds
must already be ordered by their atom-index pair. Lists and non-record elements
are rejected. Caller membership/order is not silently sorted. Classification
and explicit-definition tuple order carries no scientific meaning and does not
change successful results.

`protein_residue_indexes` is a required, strictly increasing, unique tuple of
non-negative integer source residue indexes, all present in the topology.
No protein residue may also be classified lipid/glycan. The set provides only
authoritative protein-carrier evidence; MANIA does not infer protein from names
or assume every non-glycan neighbor is protein.

## Connectivity and grouping

`TopologyConnectivityStatus` has exactly two values:

| Status | Meaning |
| --- | --- |
| `available` | Supplied bonds are authoritative connectivity evidence, including an explicitly empty bond tuple. |
| `unavailable` | No trusted connectivity was supplied; bonds must be empty. Automatic multi-residue grouping and glycan carrier inference are forbidden. |

An empty bond tuple alone never silently means that absence of covalent bonds
has been established. The caller must declare the status. This is needed for
portable snapshots, including future NAMD inputs; it adds no topology reader.

Only classified components participate in connectivity grouping, with lipid
and glycan graphs separate. Bonds through unclassified residues or another
partner kind cannot bridge a group. Within one kind, a connected component
must have one matching explicit `partner_name`; conflicting names fail and
require explicit grouping rather than an invented entity label.

Explicit definitions are authoritative only for their listed components. Each
component must exist and have exactly matching kind/name classification. A
residue may have only one classification, including rejection of identical
duplicate classification records. Explicit definitions cannot overlap and their
IDs must be unique. Their exact membership is retained even if topology bonds
connect to other components. The covered components are removed from automatic
grouping; remaining classified components may use the connectivity rules.
Explicit grouping does not require internal component bonds, but glycan linkage
must still satisfy the evidence rules below. No partial successful catalog is
returned if any partner fails identification.

### Lipid entities

One explicitly classified source lipid residue may define one partner, even
without connectivity. It uses `identification_mode="topology_connectivity"`:
the source residue supplies the entity boundary; this mode does not claim that
cross-residue bonds exist. Lipids have no glycan linkage fields or evidence.

Connected same-name classified lipid residues form one multi-residue partner
when connectivity is available. Matching names, adjacent residues, sequential
source IDs, or shared segids cannot merge disconnected residues. Three
disconnected same-name lipid residues produce three partners. Without trusted
bonds, a caller needing a multi-residue lipid must supply explicit grouping.

### Glycan entities and carrier linkage

Remaining glycan components group only through authoritative covalent bonds
among classified glycan residues. Disconnected same-name glycans remain separate,
including when they share a carrier. No grouping uses spatial proximity.

Automatic identification requires exactly one crossing topology bond from the
glycan component to the authoritative protein set. Its protein residue is
`carrier_residue_index`; its glycan residue is `first_sugar_residue_index`; its
exact atom pair is `carrier_link_bond`. The first sugar need not have the lowest
source residue index. Zero protein links, multiple carrier residues, multiple
first sugars, or multiple exact carrier bonds all fail automatic identification.
Even multiple bonds between the same residue pair need explicit mapping so that
automatic identification never silently selects a bond. No unresolved glycan
is emitted as a successful partner.

At raw explicit-model level, carrier and first sugar may both be absent or both
present. The carrier must be outside component membership and the first sugar
inside. Successful explicit glycan identification requires both, with the carrier
in the authoritative protein set.

## Explicit linkage fallback

`MolecularPartnerLinkageEvidence` is exactly `topology_connectivity` or
`external_metadata`. It is retained on the identified record as well as being
available on an explicit definition. No external evidence is invented.

| Connectivity | Successful explicit glycan rule | Identified evidence |
| --- | --- | --- |
| `available` | At least one supplied topology bond must connect the specified carrier and first sugar. | `topology_connectivity`, with an exact bond. |
| `unavailable` | Explicit grouping, carrier, first sugar, and `linkage_evidence="external_metadata"` are required. | `external_metadata`, with `carrier_link_bond=None`. |

With authoritative connectivity, an external attestation cannot bypass a missing
bond, even when the authoritative bond tuple is empty. When a valid bond exists,
the result records topology evidence regardless of an external attestation on
the input. An explicit residue pair resolves carrier/first-sugar ambiguity;
if several bonds support that pair, the lowest canonical atom pair is retained
as a deterministic representative. The field does not claim to list all bonds.

With unavailable connectivity, `None` or `topology_connectivity` evidence on the
explicit definition fails. The external-only result is an explicitly attested
identity, not a claim that topology validation succeeded. It retains both source
residue indexes and the evidence status while never fabricating an atom bond.
Three same-name glycan residues without trusted bonds cannot be merged or
identified automatically. A validated explicit definition can group them into
one externally attested partner. This is the Stage 29.A NAMD-style fallback.

## Identified membership, catalogs, and partner IDs

`IdentifiedMolecularPartner` preserves the supplied/generated ID, kind, name,
identification mode, exact component residue indexes, sorted union of component
atom indexes, and complete source residue records. Model validation rejects
overlap, inconsistent unions/order, and inconsistent linkage. An identified
topology bond must cross from the first sugar to outside component membership;
the identification API additionally verifies the actual carrier atom ownership.
External linkage is permitted only in explicit-mapping mode with no bond.

`MolecularPartnerCatalog` contains successful disjoint partners only, ordered
lipid then glycan, then lexicographically by `partner_id`. IDs, component residue
memberships, and component atom memberships must not overlap. Derived counts
are `partner_count`, `lipid_partner_count`, and `glycan_partner_count`. An empty
catalog is valid.

Explicit mapping preserves the validated supplied ID unchanged. Connectivity
identification generates `lipid_0001`, `lipid_0002`, ... and `glycan_0001`,
`glycan_0002`, ... independently per kind. Assignment orders automatic entities
by minimum component atom index, then minimum component residue index. Explicit
entities do not consume this numbering. A collision with an explicit ID fails;
the caller must supply non-conflicting explicit IDs. Numbering has minimum width
four; final catalog order always follows the stated lexicographic rule.

**Generated IDs are stable within the same source topology ordering and
classification. They are NOT cross-system canonical molecular identifiers.**
They never contain a condition, trajectory filename, or local path. Source
numbering is not canonical protein mapping.

All `to_dict()` methods produce deterministic JSON-compatible dictionaries and
lists, preserving optional evidence as `None`/JSON `null`. Identical inputs give
byte-identical output from:

```python
json.dumps(catalog.to_dict(), allow_nan=False, separators=(",", ":"))
```

The mixed synthetic smoke has protein residues 0/1; independent lipid residues
10/11 classified `LIPID-X`; and glycan residues 20/21 classified `GLYCAN-X`, with
bonds protein 1–glycan 20–glycan 21. It yields `lipid_0001` containing 10,
`lipid_0002` containing 11, and `glycan_0001` containing 20/21, carrier 1, first
sugar 20, with exact deterministic atom memberships.

## Stage 29.C handoff and scientific boundary

Carrier/first-sugar source evidence lets Stage 29.C/29.D enforce the frozen
rule: the covalent carrier-residue <-> directly attached first-sugar linkage
must not artificially enter ordinary occupancy/lifetime summaries. Stage 29.A
records evidence only and performs no exclusion or contact calculations.

All source component atoms are retained. Stage 29.A does not label atoms heavy
or light; authoritative runtime atom data and heavy-atom filtering belong to
29.B/C. The future calculations should not rediscover molecular membership.

There is no distance calculation, contact cutoff implementation, contact
presence, occupancy, episodes, lifetime, or distance statistic. There are no
coordinates, trajectory access, MDAnalysis imports, PBC changes, or main protein
graph changes. The main dynRIN remains protein-only. The modules perform no
filesystem, Git/subprocess, clock, environment, or random-ID access.

This evidence does not invent canonical glycosylation sites, biological glycan
types, occupancy annotations, or annotation sources/verifiers. Those remain
supplied by the Dataset team and later annotation stages. No CLI/workflow,
provenance, inventory, unified validation, analysis, dependencies, WANIA,
replica aggregation, QC, 95% exclusion policy, or publication integration changes
are part of 29.A.
