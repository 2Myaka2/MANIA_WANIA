# Publication contact-definition construction authority v1

Stage 34.D.R1 repairs the missing construction recipe discovered during the
Stage 34.D clean reproduction. It does not accept D.2 or D.2c. The package stays
`mania-wania 0.1.0`; contact calculations, Stage 27–32 formulas, Stage 31 statistics,
F1/F2, release schemas and validators are unchanged.

Previously B.5 copied caller-supplied `publication_inputs.json`; C.2 and C.4
transformed its nested definitions. Stage 33 validated that supplied metadata
but did not construct it. Thus a clean checkout lacked an authoritative recipe.
The new constructor needs current explicit source bindings and a packaged
versioned contract, with no historical publication-input seed.

## Migration authority

The user explicitly authorized the accepted C.4 nested input and its upstream
C.2/B.5 inputs as one-time migration authority. The C.4 nested input SHA256 is
`46eb2767d6c3822447cf8181a78b17a6779a1224f472f1314f9e1d0fd9009bb7`.
Its accepted evidence archive SHA256 is
`653047a14750c1495896f06bd903f4bed109af1ace91303b4aa946b4b41244d1`.
The external repair evidence records absolute historical paths, archive identities,
acceptance records and every source hash. These are migration provenance only.
No historical paths, UUIDs, timestamps or evidence-directory identities occur in
the committed scientific contract.

C.4 records F1, F2, cross-table validation, complete release validation and
independent publication inspection as passed. Nested C.4/C.2/B.5 source bytes
were verified against their accepted ZIPs and inventories; the upstream copies
match exactly. Migration starts from these nested models, never from inferred
meaning in the flattened CSV.

## Package authority and API

`src/mania/data/publication/contact_definition_authority_v1.json` has schema
`mania.publication_contact_definition_authority.v1`, contract version `1`, and
SHA256 `6beafe903e8ca10fc8b9d749108043c3d2c366aed0d516cc4a8041054a89c597`.
It contains shared accepted publication prose, PBC required values/path fields,
protein publication role/layer/units, and the two specialized definition templates.
It contains no protein detection-criteria copy and no complete pilot input.
`pyproject.toml` includes this resource in the wheel. The loader verifies its hash.

`mania.dataset_release_contact_definition_authority` provides:

- `materialize_contact_definition_authority(workspace, path)`: write exact package
  bytes to an explicit portable workspace path; reject an existing differing file.
- `build_dataset_release_contact_definitions(...)`: return a deterministic tuple
  of `PublicationContactDefinition` nested models, each validated by the unchanged
  Stage 33 `build_dataset_release_contact_definition` projection.
- `PublicationContactDefinition.to_dict()` and `.to_table()`: expose the existing
  nested input shape and strict flattened table, without schema additions.

Example bindings, with caller-supplied PBC evidence:

```python
from pathlib import Path
from mania.dataset_release_contact_definition_authority import (
    build_dataset_release_contact_definitions,
    materialize_contact_definition_authority,
)

workspace = Path("publication-work")
authority_path = "authority/contact_definition_authority_v1.json"
materialize_contact_definition_authority(workspace, authority_path)
definitions = build_dataset_release_contact_definitions(
    workspace=workspace,
    replica_key=("dataset", "system", "trajectory", "replica"),
    edge_semantics_path="run/edge_semantics.json",
    run_provenance_path="run/run_provenance.json",
    pbc_correction_status={
        "internal_mic": False,
        "external_protocol_approved": True,
        "historical_scientific_pbc_status": "unresolved",
        "protocol_authority": "evidence/protocol_approval.json",
        "trajectory_preparation_and_diagnostics": "evidence/trajectory_pbc.json",
    },
    specialized_authority_path=authority_path,
    partner_catalog_path="run/molecular_partner_catalog.json",
)
```

Every supplied path must be portable and point to an existing artifact. The
constructor binds explicit PBC and catalog evidence; it does not evaluate PBC,
re-identify partners, or infer protocol approval from coordinates. Stage 34
adapters additionally check their supplied protocol approval document. Existing
Stage 33 inventory/provenance and release validation retain source artifacts.
Omitting both specialized bindings constructs the protein definitions alone.

## Stable fields and dynamic bindings

Protein definitions come from each supplied `edge_semantics.json`. The complete
artifact must match the existing production `build_edge_semantics_manifest()`
authority, including implemented identities, backend spelling, definitions,
criteria, priority, overlap, limitations and protein flags. Missing, duplicate,
renamed or collapsed types fail. The exact artifact's edge models are copied
into `type_specific_parameters`; typed cutoffs and descriptions are derived
from those same models, not a second hardcoded criteria table.

`residue_contact` retains the edge model's `runtime contact definition` threshold
source. Its cutoff and all atom-selection options come from the completed current
run provenance. Complete options are validated without normalization; the unit
must retain the accepted `angstrom` spelling. Typed edges remain separate.
The replica key must match exactly one Dataset binding in the run provenance.
A nonempty current `run_id` is required but is not inserted into the frozen
contact parameter schema; software records retain the appropriate run identity.

The shared occupancy template takes the effective resolved sample count from
that run's matching condition. Count five retains the exact accepted phrase
`five resolved samples`; another count is rendered explicitly. The denominator
remains `n_contact_frames / resolved_frame_count`, with missing samples excluded.
Episode continuity, zero gap tolerance and lifetime prose are stable authority.
No episode or contact measurement is recomputed.

The specialized templates preserve `protein_lipid` / `protein_glycan`, layers
`protein-lipid` / `protein-glycan`, and source role
`accepted_specialized_window_contract`. They retain minimum Cartesian heavy-atom
distance, inclusive 6.0/4.5 angstrom cutoffs, positive-contact-frame distance
summaries, and the carrier/first-sugar exclusion. No specialized `edge_weight`
is introduced. Partner catalog, PBC protocol and trajectory diagnostics are
bound explicitly for each replica. `internal_mic=false`, explicit external
approval and legacy `historical_scientific_pbc_status=unresolved` are preserved.

Protein units remain the accepted empty mapping. Specialized units remain
exactly `{"$/cutoff/value": "angstrom"}`. Embedded unit strings in parameter trees
are unchanged; no aesthetic unit normalization is allowed. Hash binding rejects
changes to the materialized specialized identity, source role, units, cutoff,
anchor exclusion or any other stable field.

## Stage 34 adapters and migration proof

B.5 now constructs publication inputs by default; its optional
`--publication-inputs` argument preserves explicitly requested external-input
support. C.2 constructs protein definitions for all replicas and the accepted
r1 specialized pair. C.4 constructs all three replicas' definitions directly.
C.2/C.4 no longer read historical publication inputs for contact or software
construction. Software metadata comes from explicit current provenance bindings.
The historical resume tools still retain their frozen upstream execution gates;
the production constructor itself has no implicit evidence discovery or
`local_md` dependency. A new clean workflow can call it with arbitrary explicit
current workspace paths and identities.

The migration evidence compares complete strict nested models and production
flattened tables. The only normalization is each specialized definition's
`source_artifact_path`: the old explanatory Markdown path becomes the exact
materialized versioned JSON authority path. No role, parameter, unit, null,
array, scalar type or scientific field is ignored. All six replacements are
listed individually in the evidence report.

The accepted three-replica case produces 36 identities and 1,278 flattened rows
naturally, with zero missing/extra definitions, identity/layer/type/role/tree/unit
mismatches and zero complete nested or flattened mismatches. The accepted nested
projection also equals its persisted release CSV exactly. These counts are
migration test expectations only, never constructor loop bounds.

`stable_dynamic_field_classification.json` classifies every node of every accepted
contact definition and separates migration-only provenance. No field is left as
an unexplained external input. Synthetic temporary-directory tests exercise the
constructor and all three adapters without historical inputs; negative tests
reject identity/role/science/unit substitutions and missing bindings. Installed
wheel verification checks the same resource bytes and construction outside the
checkout, together with the established offline canonical reference/mapping probe.

After user review and commit, a separate clean-clone D.2c replay must reconstruct
these inputs from the committed wheel/resources and current explicit run
bindings, then pass the unchanged Stage 33 F1/F2, cross-table and complete release
validation and independent science comparisons. The R1 migration evidence is
not a D.2c acceptance result.
