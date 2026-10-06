# Production RMSD evidence and compact handoff v1

The common new-contract producer measures RMSD automatically during the existing
selected contact-frame traversal, retains compact prerequisites under its attempt
root, validates them and seals a separate `handoff_complete.json`. Science
completion retains its established meaning. This implementation is ready for a
separate real representative acceptance and benchmarking checkpoint; it does not
freeze a Ramila v2 release or supply scientific QC decisions.

## Scientific contract

Coordinates are the exact PBC-prepared trajectory loaded for production contact
science, in angstrom. The temporal scope is exactly the Stage 27 requested
production sample roster, with measurements for resolved requests. Stabilization
is excluded from RMSD v1 and retained separately in preparation/time/PBC evidence.
No nearest substitution, interpolation, coordinate transformation or additional
trajectory traversal solely for RMSD occurs.

The reference identity is fixed before traversal to the first resolved requested
production sample. Its coordinates are captured once when that frame is already
loaded. Early missing requests remain missing. The reference records requested
index/time, actual time, runtime/source/prepared indexes and the SHA256 of its
contiguous little-endian float64 selected coordinate bytes. Its RMSD is calculated
with the same fit as subsequent samples. Zero resolved samples fail explicitly.

Every present protein residue requires complete explicit mapping in the accepted
engine/chain/resid/resname namespace and exactly one atom named `CA`, element `C`.
The selected atoms follow canonical position order. Numeric resid equality supplies
no mapping authority. Duplicate canonical targets, missing or multiple C-alpha
atoms, incomplete mapping and fewer than three atoms fail. Alignment requires at
least two independent centered coordinate axes; NumPy's float64 rank tolerance is
`eps * max(shape) * largest singular value`. The pinned O95436 reference remains
unchanged. The selected residue count is not fixed: WT, T330M, substitutions and
explicitly mapped 684-residue deletion systems share this method.

Alignment and measurement use the same atoms, equal weights, float64 arithmetic,
centroid subtraction and SVD Kabsch. With row vectors, the proper rotation has
determinant +1; reflection equivalence is forbidden. RMSD is
`sqrt(sum_i ||X_centered_i @ R - reference_centered_i||^2 / N)` in angstrom.
Malformed/nonfinite coordinates, changed atom identity and sample reordering fail.
There is no universal RMSD threshold or automatic drift classifier.

## Two RMSD authorities

Paths are relative to the individual attempt root:

| Artifact | Inventory role | Contract |
| --- | --- | --- |
| `preprocessing/protein_rmsd_timeseries.csv` | `protein_rmsd_timeseries` | Exact ordered 20-column sample table |
| `preprocessing/protein_rmsd_measurement.json` | `protein_rmsd_measurement` | `mania.protein_rmsd_measurement.v0.1` |

CSV columns are `dataset_id,system_id,trajectory_id,replica_id,engine,variant_id,condition,scope_id,requested_sample_index,requested_time_ps,state,runtime_frame_index,source_frame_index,prepared_frame_index,actual_time_ps,time_delta_ps,rmsd_A,reference_requested_sample_index,selection_id,measurement_contract_id`.

Every requested index appears once, in order. Missing rows keep their requested
identity and shared reference/selection/contract fields, with blank actual time,
frame indexes, delta and RMSD. A blank condition represents the Dataset's explicit
nullable condition. Resolved rows contain finite nonnegative RMSD and all indexes
and times. Floats use `.17g`, UTF-8 CSV escaping, LF and a final newline.

Runtime indexes identify the trajectory actually loaded. Prepared indexes identify
that same prepared artifact; raw source indexes come from the complete retained
preparation frame map. Equality of these indexes is checked for full-axis
preparation and is never presumed for technical subsets.

JSON retains the full replica identity, exact execution binding, temporal artifact
hash, fixed reference, ordered atom roster and canonical identity, topology/mapping/
raw/prepared/report hashes and sizes, method contract
`mania.production_ca_rmsd.v1`, implementation/source build hashes and software
versions, CSV hash, completeness and explicit limitations. The CSV hashes no JSON;
JSON binds the finalized CSV; inventory and seal bind JSON. All writes are atomic
and existing evidence is immutable. Readers reject extra/missing schema fields,
duplicate JSON keys, nonfinite values, table or temporal hash changes, missing or
reordered samples, changed method/reference/selection and expected input/software
identity mismatches. Unified validation checks the two roles together and binds
mapping, topology and prepared identity to the preprocessing inventory.

## Preparation observations and portable retention

`evidence/producer/<role>/<original_basename>` retains exact immutable original
reports and consumed controls. `evidence/preparation_evidence.json` supplies the
common resolver and coordinate identities. The normalized
`protein_integrity_observations` member uses
`mania.protein_integrity_observations.v0.1`, with the full prepared-to-source frame
map, physical times, protein atom/fragment identity, bonded representation error,
centering and complete-fragment observations, their tolerance and original-report
binding. It never rewrites the original report.

Ramila observes periodic source bond lengths versus direct prepared bond lengths
inside the existing preparation pass. This diagnostic does not change the accepted
unwrap/center/wrap algorithm or classify an arbitrary PBC state. Each frame's
observations are retained. `scientific_pbc_status=unresolved` remains distinct from
an explicitly supplied protein-broken observation/assessment. Contacts succeeding
never supplies PBC PASS. Protocol approval, technical validation and trajectory QC
remain separate. Handoff completion requires all-frame bonded evidence or a
supported explicit integrity assessment.

Mandatory compact categories include preparation report, integrity/frame evidence,
source bindings/time authority, source attestation, Dataset request, canonical
mapping, partner metadata/catalog, temporal execution, contact and specialized
per-frame evidence/completion, all emitted source/canonical/annotated outputs,
runtime identity, PBC audit, producer validation/replay, preprocessing inventory/
provenance, and science completion. Consumed source MDP/logs and producer script
identities accompany Ramila retention. Every actual member has size and SHA256.
Biological annotations and partner correspondence are copied when authoritative
controls exist; genuine absence is recorded explicitly. Review and group QC/
aggregation remain pending until separate postproduction attempts supply them.
Absence records never create scientific authority.

`handoff/manifest.json` uses `mania.production_handoff.v0.1` and declares exact
requirements, authority states, resolver, coordinate identities and RMSD bindings.
`handoff/artifact_inventory.json` and `handoff/run_provenance.json` reuse unchanged
Stage 25 schemas with workflow `production_handoff`. The inventory excludes
itself, its provenance and final seal. Original preprocessing inventories are
immutable retained snapshots. `handoff/validation.json` records compact validation
and byte-identical replay without coordinate access. Provenance alone has producer
timestamps; scientific RMSD artifacts contain none.

## Completion, review and aggregation

`handoff_complete.json` uses `mania.production_handoff_complete.v0.1`, binds the
full replica identity and production eligibility, required member count, science
completion, manifest, inventory, provenance and validation. It is written only
following strict validation. The same compact closure check runs before the
existing science marker is published. Technical common attempts bind their
existing `technical_complete.json` marker and remain production ineligible.
Missing compact evidence or a hash/schema/lineage
mismatch prevents completion. A science marker alone is legacy completion and is
never silently upgraded. Frozen historical bytes and tags are unchanged.

Future common producers supply a `mania.production_handoff_inputs.v0.1` control
with `identity`, `compact_files`, documentary `large_artifact_identities`,
`production_eligible` and explicit `authority_absences`. The common new-contract
entry point requires that control and automatically runs measurement, retention,
validation and sealing:

```bash
mania production run-handoff --catalog CATALOG --trajectory-id ID \
  --output-root OUTPUT_ROOT --input-binding INPUT_BINDING \
  --handoff-inputs HANDOFF_INPUTS --min-free-bytes N
mania production validate-handoff --output-root ATTEMPT_ROOT
mania production review-rmsd --output-root ATTEMPT_ROOT
mania production build-rmsd-qc --output-root ATTEMPT_ROOT \
  --assessment EXPLICIT_ASSESSMENT --output ATTEMPT_ROOT/postproduction/attempt_0001/review.json
mania production assemble-handoff-group --output-root OUTPUT_ROOT \
  --handoff-root REPLICA_1_ATTEMPT REPLICA_2_ATTEMPT REPLICA_3_ATTEMPT \
  --qc-manifest OUTPUT_ROOT/controls/qc.json
```

Existing legacy catalog commands and frozen producers keep their interface. An
explicit `--handoff-inputs` on `production run` also selects the new contract.
A new-contract run cannot stamp an existing legacy attempt; choose a fresh output
namespace. Standalone validation/review commands need only the sealed attempt.
Output-only group assembly requires three distinct production-eligible sealed
replicas, matching windows/identities, exact canonical tables and explicit Stage 32
controls under OUTPUT_ROOT. It runs the existing QC evaluator, waits for explicit
review resolutions when required, then uses only QC-derived availability for the
unchanged Stage 31 aggregation. Specialized layers require explicit correspondence.

Review presentation is deterministic and has `assessment_state=explicit_assessment_required`.
The assessment input requires schema `mania.production_review_assessment.v0.1`, an
exact JSON `drift_detected` bool, `assessment_method`, `reviewer` and `decision_note`.
Saved review records bind the sealed measurements and replica. Measurements alone
cannot become `drift_detected=False`. The bridge builds the exact existing
`RMSDDriftAssessment`; false preserves Stage 32 PASS behavior and true preserves
REVIEW behavior, subject to its other checks. No Stage 32 evaluator or policy changes.

## Large-artifact lifecycle and compatibility

Raw and prepared coordinates are not copied into the compact handoff. Preparation
may already store its sole prepared XTC under OUTPUT_ROOT; it remains outside the
compact member registry and can be omitted from a compact transfer. This task
deletes no source/prepared coordinates. Ramila's existing successful scratch
cleanup is unchanged. Coordinate recomputation or later coordinate-dependent
science still needs retained source/prepared data and its recorded identities.
Ordinary QC review, validation, per-frame replay and aggregation use compact
members alone; coordinate-free validation does not claim to recompute RMSD.

Frozen Egor producer files and `egor-production-v2` are untouched. A separate future
recovery helper can use the same math/selection/persistence with genuine explicit
mapping, prepared trajectory and temporal lineage; it must perform its necessary
recovery coordinate read honestly and must not silently upgrade historical seals.
Future Alina systems use explicit present-residue mapping, including deletions;
no owner identity or universal 690-atom requirement enters common preprocessing.
The next checkpoint must assess representative real preparation, RMSD/handoff
acceptance and measured production impact before any Ramila v2 freeze.
