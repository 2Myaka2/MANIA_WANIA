# Preprocessing contacts MVP

## Stage 13 goal

Stage 13 introduces residue contacts in small, contacts-specific steps. Stage
13.1a is contract-only: it defines the MVP contact meaning and validated
detection options before any contact computation. Stage 13.1b adds only the
dependency-free result dataclasses and report shape.

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

## Result contracts

Stage 13.1b adds these shape contracts:

```python
PreprocessingContactComputationIssue
PreprocessingContactPairResult
PreprocessingContactFrameResult
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
```

The issue contract records future result or computation failures without
closing the allowed issue-kind vocabulary. Expected later examples include
`runtime_not_loaded`, `missing_runtime_object`,
`missing_residue_information`, `missing_atom_positions`,
`contact_computation_error`, `frame_iteration_error`,
`manifest_load_issue`, and `condition_contacts_failed`.

The pair contract represents one observed residue-residue contact in one
frame. It validates distinct source and target residue indexes but does not
create graph direction or graph semantics. Future computation is responsible
for deterministic source-target ordering when duplicate pairs are excluded.

Frame, condition, and manifest contracts provide deterministic contact, frame,
and condition counts plus nested JSON-safe `to_dict()` output. They are shape
contracts only. No contact computation exists yet, and no distance calculation
exists yet.

## What contact_edges.csv means

contact_edges.csv is a future aggregate contacts table of observed residue
pairs. It is not backend graph edges.csv and does not establish the backend
graph data contract.

## What is not implemented yet

Stage 13.1a added no contact result dataclasses; Stage 13.1b now adds their
dependency-free report shape. No contact computation exists yet. No distance
calculation exists yet. No CSV export exists yet.
No `contacts_perframe.csv` writer exists yet.
No `contact_edges.csv` writer exists yet.
No contact aggregation writer exists yet. CSV validation, comparison, report
bundles, and local scientific contacts tests also remain future work.

## Boundary before graph

No graph export exists yet.
No backend graph `nodes.csv` is produced.
No backend graph `edges.csv` is produced.
No `graph.json` is produced.
Graph export belongs to a later stage after contacts are stable.

## Next Stage 13 steps

Stage 13.2a will add single-condition residue contacts extraction. Stage 13.2b
will compose manifest results, and Stage 13.2c will add opt-in local scientific
smoke coverage. CSV export begins only in Stage 13.3. Later explicit steps
cover validation, reference comparison, and performance boundaries.
