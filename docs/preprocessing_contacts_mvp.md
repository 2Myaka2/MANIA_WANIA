# Preprocessing contacts MVP

## Stage 13 goal

Stage 13 introduces residue contacts in small, contacts-specific steps. Stage
13.1a was contract-only: it defined the MVP contact meaning and validated
detection options before any contact computation. Stage 13.1b added only the
dependency-free result dataclasses and report shape. Stage 13.2a adds
single-condition residue contact extraction from an already loaded runtime.
Stage 13.2b composes those condition results across an existing manifest load
result. Stage 13.2c adds opt-in local scientific smoke coverage for the
manifest contacts computation path.

## MVP contact definition

A residue-residue contact is detected per frame when the minimum distance
between selected atoms of two distinct residues is less than or equal to the
configured cutoff distance.

The MVP contact level is residue-level, detection occurs per trajectory frame,
and each pair represents two distinct residues. The distance is the minimum
atom-atom distance between the selected atoms of those residues. The default
atom filter is `heavy`, the default cutoff is `4.5`, and the default distance
unit label is `angstrom`.

Stage 13 performs no unit conversion and no biological interpretation.

## Contact detection options

`PreprocessingContactDefinition` records the fixed MVP definition.
`PreprocessingContactDetectionOptions` records the extraction options:

- `cutoff_distance` and `distance_unit`;
- `atom_filter`, currently `heavy` or `all`;
- residue-level `contact_level`;
- same-residue and duplicate-pair exclusion;
- `skip_resnames`, which controls solvent and ion exclusion;
- frame-index and time inclusion flags reserved by the result contract.

Same-residue exclusion and duplicate-pair exclusion are enabled by default.
The options validate their values, normalize `skip_resnames` deterministically,
and serialize without runtime objects.

## Result contracts

Stage 13.1b added these shape contracts:

```python
PreprocessingContactComputationIssue
PreprocessingContactPairResult
PreprocessingContactFrameResult
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
```

The pair contract represents one observed residue-residue contact in one
frame. It validates distinct source and target residue indexes but does not
create graph direction or graph semantics. Stage 13.2a emits each pair once in
canonical lower-index-first order.

Frame, condition, and manifest contracts provide deterministic contact, frame,
and condition counts plus nested JSON-safe `to_dict()` output. Stage 13.2a
consumes the frame and condition contracts without changing their behavior,
and Stage 13.2b consumes the manifest contract without changing its summary
semantics.

Stage 13.1a added no contact computation and no contact result dataclasses.
Stage 13.1b added those dataclasses before Stage 13.2a implemented
single-condition computation.

## Stage 13.2a single-condition extraction

`compute_condition_contacts(...)` accepts one existing
`PreprocessingConditionLoadResult`, uses its already loaded runtime object, and
returns `PreprocessingConditionContactsResult`. It does not load files or
acquire MDAnalysis.

For every trajectory frame, the function:

- preserves zero-based trajectory iteration order;
- reads a usable frame time, then falls back to
  `frame_index * frame_time_ps`, or uses `None`;
- preserves original residue iteration indexes;
- respects `skip_resnames`;
- selects heavy atoms by default or all atoms when requested;
- computes the minimum selected atom distance for each canonical distinct
  residue pair;
- records a contact when that distance is less than or equal to the cutoff;
- returns deterministic pair ordering and JSON-safe result objects.

Coordinates are assumed compatible with the configured option unit label. No
unit conversion is performed. Pure-Python nested distance loops are the
accepted MVP; performance optimization is future Stage 13.5 work. Biological
interpretation is out of scope.

Missing load/runtime inputs are returned as failed condition results. Atom
position problems are frame issues, so available frame results are preserved
and the condition can return `partial`. Residues with no selected atoms,
including hydrogen-only residues under the heavy filter, produce no contacts
without failing.

## Stage 13.2b manifest aggregation

`compute_manifest_contacts(...)` accepts one existing
`PreprocessingManifestLoadResult`, calls `compute_condition_contacts(...)` for
each contained condition load result in deterministic manifest order, and
returns `PreprocessingManifestContactsResult`.

The manifest function defaults options to
`PreprocessingContactDetectionOptions()` and passes the selected options to
each condition computation. Failed and partial condition contact results are
preserved. Manifest-level load issues are mapped into contact computation
issues on the manifest result. Unexpected per-condition computation exceptions
are captured as deterministic failed condition contact results so later
conditions can still be processed.

Stage 13.2b is orchestration only. It does not inspect runtime objects, load
files, acquire MDAnalysis, add distance logic, export CSV, compare references,
run local scientific smoke tests, or add graph semantics.

## Stage 13.2c local scientific smoke

The local scientific contacts computation smoke test validates the accepted
runtime computation path when explicitly enabled with the existing local
scientific harness. It uses the public load-manifest, load-runtimes, and
compute-manifest-contacts APIs, then checks result shape and JSON
serialization.

The smoke test is opt-in and local only. It does not add export, validation,
reference comparison, report bundles, graph output, benchmark thresholds, or
biological interpretation. Contacts CSV export remains future Stage 13.3
work, and graph export remains future work.

## What contact_edges.csv means

contact_edges.csv is a future aggregate contacts table of observed residue
pairs. It is not backend graph edges.csv and does not establish the backend
graph data contract.

## What is not implemented yet

No CSV export exists yet.
No `contacts_perframe.csv` writer exists yet.
No `contact_edges.csv` writer exists yet.
No contact aggregation writer exists yet. CSV validation, comparison, report
bundles, and contacts export smoke coverage also remain future work.

## Boundary before graph

No graph export exists yet.
No backend graph `nodes.csv` is produced.
No backend graph `edges.csv` is produced.
No `graph.json` is produced.
Graph export belongs to a later stage after contacts are stable.

## Next Stage 13 steps

CSV export begins only in Stage 13.3. Later explicit steps cover validation,
reference comparison, and performance boundaries.
