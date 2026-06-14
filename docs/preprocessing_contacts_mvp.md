# Preprocessing contacts MVP

## Stage 13 goal

Stage 13 introduces residue contacts in small, contacts-specific steps. Stage
13.1a is contract-only: it defines the MVP contact meaning and validated
detection options before any contact computation or output shape is added.

## MVP contact definition

A residue-residue contact is detected per frame when the minimum distance
between selected atoms of two distinct residues is less than or equal to the
configured cutoff distance.

The MVP contact level is residue-level, detection occurs per trajectory frame,
and each pair represents two distinct residues. The distance is the minimum
atom-atom distance between the selected atoms of those residues. The default
atom filter is `heavy`, the default cutoff is `4.5`, and the default distance
unit label is `angstrom`.

Stage 13.1a performs no unit conversion. Stage 13 performs no biological interpretation.

## Contact detection options

`PreprocessingContactDefinition` records the fixed MVP definition.
`PreprocessingContactDetectionOptions` records the future extraction options:

- `cutoff_distance` and `distance_unit`;
- `atom_filter`, currently `heavy` or `all`;
- residue-level `contact_level`;
- same-residue and duplicate-pair exclusion;
- `skip_resnames`, which controls solvent and ion exclusion;
- optional frame-index and time fields for future results.

Same-residue exclusion and duplicate-pair exclusion are enabled by default.
The options validate their values, normalize `skip_resnames` deterministically,
and serialize without runtime objects. They do not select atoms or calculate
distances.

## What contact_edges.csv means

contact_edges.csv is an aggregate contacts table of observed residue pairs.
It is not backend graph edges.csv and does not establish the backend graph
data contract.

## What is not implemented yet

Stage 13.1a adds no contact computation and no contact result dataclasses. It
adds no `contacts_perframe.csv` writer, no `contact_edges.csv` writer, no CSV
validation or comparison, no report bundle, and no local scientific contacts
test.

## Boundary before graph

Stage 13.1a adds no graph export: no backend graph `nodes.csv`, no backend graph `edges.csv`,
and no `graph.json`. Graph export belongs to a later stage after contacts are
stable.

## Next Stage 13 steps

Stage 13.1b will define contact result dataclasses and report shape. Stage
13.2a will add single-condition residue contacts extraction. Later explicit
steps will cover manifest aggregation, local scientific smoke coverage, CSV
writing and validation, reference comparison, and performance boundaries.
