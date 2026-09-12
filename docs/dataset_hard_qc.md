# Dataset hard QC — Stage 32.B

## Status

Stage 31 is complete. Stage 32.A is accepted at committed checkpoint
`c5e3e29afce3a20c509eb4ddeae385aff7b92c89` on `FAIR`.
Stage 32.B hard-QC evaluator is implemented in `mania.dataset_hard_qc`.
Stage 32.B is accepted at committed checkpoint
`85fc62f17b47b94120b3e1e21c2c8af579396f60` on `FAIR`.
Stage 32.C manual-review QC is implemented; see [Dataset review QC](dataset_review_qc.md).
Stage 32.C is accepted. Stage 32.D integration is complete;
see the [Dataset QC workflow](dataset_qc_workflow.md). Stage 32 is complete.
Dataset v1.0 remains unreleased; version remains `mania-wania 0.1.0`.

## Hard-QC vs final release decision

The pure `evaluate_replica_hard_qc` function returns frozen
`ReplicaHardQCEvaluation` with fields, in order: `dataset_id`, `system_id`,
`trajectory_id`, `replica_id`, `checks`, and non-init `hard_qc_status`.
`replica_key` derives the four identity strings. `condition` has no authority.
The checks are exact accepted Stage 32.A `ReplicaQCCheckResult` objects.
`HardQCStatus` is exactly `Literal["pass", "fail"]`: any FAIL makes the hard
summary fail; otherwise it passes. There is no REVIEW status, release decision,
decision mode, or production availability in this result.

A hard-QC pass means only that the emitted hard checks passed. Stage 32.C may
still produce REVIEW findings. Stage 32.D combines hard and review findings and
then applies the unchanged 32.A decision semantics to construct authoritative
release decisions and bridge Stage 31 availability. 32.B does not call any
release-decision helper or create `ReplicaQCDecisionRecord`.

Only hard-pass replicas feed Stage 32.C reference cohorts. Hard-failed replicas
do not participate in manual-review distributions and receive no 32.C review
evaluation. Stage 32.C does not override hard failures.

## Existing evidence and API

All arguments are explicit and keyword-only:

| Argument | Evidence consumed |
| --- | --- |
| `identity` | Accepted `DatasetTrajectoryIdentity`; full replica key |
| `raw_integrity` | Frozen `ReplicaRawIntegrityEvidence` |
| `mapping_binding` | Accepted `DatasetCanonicalResidueMappingBinding`, or None |
| `required_source_keys` | Tuple of exact Stage 30 source keys, or None |
| `protein_pbc` | Frozen `ReplicaProteinPBCEvidence`, or None |
| `sampling_plan` | Accepted `ResolvedPhysicalTimeSamplingPlan`, or None |
| `required_metadata` | Tuple of frozen `RequiredMetadataEvidence` |
| `required_artifacts` | Tuple of frozen `RequiredArtifactEvidence` |

The caller supplies the complete authoritative requirements for the replica,
including requested window definitions/artifacts. Requirements are never inferred
from sparse scientific rows. Empty requirement tuples explicitly declare no
additional requirements in that category; they are not Dataset discovery.
Stage 32.D owns strict readers and binds explicitly supplied requirements
and evidence to execution; it does not infer requirements from sparse rows.
The sampling plan has no embedded replica identity; supplying the correct plan
for the explicit replica key is the caller's responsibility, as with raw/PBC
observations. Mapping bindings are checked against all four replica fields.

The evaluator performs no filesystem access, CSV parsing, network access, Git,
clock access, trajectory reading, or scientific reconstruction. It does not rerun
protein/lipid/glycan contacts, distances, episodes, sampling, canonical mapping,
or replica aggregation. There are no RMSD, median, MAD, or other REVIEW calculations.

Normal hard-QC failures produce valid findings. `DatasetHardQCError(ValueError)`
means malformed API/evidence structure, such as wrong types, inconsistent sample
partitions, duplicate requirement IDs or incorrect replica binding. Numeric
structural defects in stored canonical models produce findings, not this error.
Inputs are not mutated. Deterministic `to_dict()` returns independent JSON data;
evidence observations are text, including non-finite occupancy observations.
No timestamps, UUIDs, machine paths, or environment observations are generated.

## Raw readability and atom ordering

`ReplicaRawIntegrityEvidence` declares exact bool `topology_readable` and
`trajectory_readable`; non-negative exact int or None `topology_atom_count` and
`trajectory_atom_count`; bool or None `atom_order_consistent`; `atom_universe_id`;
and structured `topology_evidence`, `trajectory_evidence`, `atom_order_evidence`.
Readable sources require count evidence. Bool counts are rejected. Counts must
refer to the same explicitly declared **all-atom universe**, never a protein-only
count compared with all atoms. The adapter is responsible for this declaration.

False readability emits `TOPOLOGY_UNREADABLE` or `TRAJECTORY_UNREADABLE`.
Equal counts pass the count check; unequal counts emit
`TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH`.

Equal atom counts do not prove semantic atom order. Explicit authoritative order
evidence is mandatory: true passes; false emits
`TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH`; None emits `REQUIRED_METADATA_MISSING`.
An explicit bool order state requires its `QCEvidenceRecord`. None represents
unavailable authority, even if evidence explains that limitation. Many trajectory
formats cannot independently prove atom identity/order. Counts, residue numbering,
coordinates, and filenames never supply that authority.

## Deterministic omitted-check policy

Omission means not evaluated, never PASS and never a new QC status:

- Always emit both readability checks. If either source is unreadable, omit
  atom count and atom order, regardless of incidental count/order fields.
- Evaluate retained mapping evidence even after raw failure. Without a mapping
  artifact, emit missing-artifact failure only when topology is readable;
  otherwise omit mapping completeness.
- Evaluate explicit PBC evidence when supplied. With neither evidence nor both
  readable sources, omit PBC; with both readable sources, missing PBC evidence fails.
- Evaluate a retained sampling plan even after raw failure. If the plan is absent,
  emit missing evidence for time and coverage only when trajectory is readable.
- Continue explicit metadata/artifact checks independently. An absent artifact
  has no schema check. Missing strict-validation evidence on a present artifact
  emits `REQUIRED_METADATA_MISSING`.
- Structural checks inspect supplied canonical models. Without a model, no
  self-loop/duplicate/occupancy PASS is invented. A required canonical artifact
  marked schema-valid must provide its model or receive missing-evidence FAIL.
  A schema-invalid artifact without a model already fails and has no structural
  findings. Retained model observations remain inspectable even with schema FAIL.
- Canonical reference is independently checked across available mapping/table
  metadata; no reference evidence emits missing-metadata FAIL.

## Mapping

Completeness uses accepted Stage 30 `source_key` exactly:
`(source_engine, source_chain_id, source_resid, source_resname)`.
The explicit required-key inventory must cover every source protein residue
requiring canonical identity, including residues without positive contacts.
Every required key needs a record with `mapping_status="mapped"`. An absent
required record or explicit unmapped record in a present mapping table emits
`CANONICAL_MAPPING_INCOMPLETE`. Extra non-required records do not affect completeness.

A missing binding/artifact emits `REQUIRED_ARTIFACT_MISSING`; an absent required
source-key inventory emits `REQUIRED_METADATA_MISSING`. Absence of the mapping
artifact itself is not evidence of incomplete mapping.

There is no requirement for all 690 reference positions to exist in a topology.
No source-resid numeric equality rule exists. Explicit T330M mapping
`gromacs / A / "330" / MET -> canonical 330 / THR` passes. Source and canonical
names need not match. The accepted Stage 30 schema/reference validation remains
responsible for canonical target names; 32.B does not remap or load a reference.

## PBC

`ReplicaProteinPBCEvidence` contains exact bool `protein_remains_broken` and a
structured `pbc` evidence record. True emits `PROTEIN_PBC_BROKEN`; false passes.
Missing required PBC authority emits `REQUIRED_METADATA_MISSING`.

The accepted Stage 25 `PbcAudit` observes dimensions and explicitly retains
unresolved scientific PBC status. It cannot establish protein integrity and is
not silently converted to this observation. Successful contacts provide no PBC
integrity evidence. QC is observational: no unwrapping, centering, repair,
coordinate modification or internal MIC. Scientific PBC status remains unresolved.

## Time

Read actual times from the accepted plan's selected samples in their existing
requested-sample/source order. Compare adjacent represented observations with
`Decimal(str(actual_time_ps))` and strict `>`; no epsilon, sorting or fake times.
Equal/backward observations emit `FRAME_TIME_NOT_STRICTLY_INCREASING`.

Stage 27 rejects non-increasing source axes before resolving samples. Its retained
`non_monotonic_source_time` diagnostic is also authoritative negative evidence
and emits the same hard failure. This preserves actual source-order evidence
without rereading the trajectory or running the resolver again.

Missing samples have no actual timestamp. Zero or one actual resolved time has
no pairwise violation and passes monotonicity unless an explicit Stage 27 source
violation exists. Coverage separately handles insufficient resolved samples.

## Coverage

Expected = Stage 27 requested expected production samples.
Resolved = the selected samples partitioning those expected requests.
Coverage = resolved / expected. The evaluator verifies count/partition structure
without rebuilding the production grid or resolving frames again.

Coverage **>= 0.95 passes**, including exactly 95%. Below it emits
`PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT`. Decimal cross multiplication gives
an exact decision; a fresh 50-digit-or-greater Decimal context serializes the
quotient independently of ambient precision/traps. Repeating quotients are
reported to that precision; the decision does not use a rounded percentage.

| Resolved / expected | Hard coverage result |
| --- | --- |
| 95 / 100 | PASS |
| 94 / 100 | FAIL |
| 19 / 20 | PASS |
| 18 / 20 | FAIL |
| 101 / 101 | PASS |
| 96 / 101 (~0.950495) | PASS |
| 95 / 101 (~0.940594) | FAIL |

The primary 101-sample schedule is the accepted closed 50–100 ns production
interval with 500 ps stride. Extra unrequested source frames do not increase
coverage. Raw frame count, contacts, rows, windows and aggregates are never the
denominator. Missing expected samples lower coverage and remain missing science.

## Required metadata, artifacts and schemas

`RequiredMetadataEvidence` contains `item_id`, exact bool `present`, and structured
`evidence`. Missing required metadata emits `REQUIRED_METADATA_MISSING`.
Valid nullable scientific metadata is not absence: `condition=None` remains valid,
and pending final NAMD condition labels are not required in 32.B.

`RequiredArtifactEvidence` contains `item_id`, exact bool `present`, bool or None
`schema_valid`, `evidence`, optional `canonical_family`, and optional
`canonical_table`. Absent artifacts cannot carry validation outcomes or tables.
Missing artifacts emit `REQUIRED_ARTIFACT_MISSING`; present artifacts get presence
PASS independently of scientific row count. A present strict-validation failure
emits `SCHEMA_INVALID`. Validation is supplied evidence from accepted readers;
32.B neither parses files nor redefines any Stage 27–31 schema.

Families are exactly `protein_edge`, `protein_lipid`, `protein_glycan`; their tables
must have the corresponding accepted Stage 30 type. Supply one complete table
per family, including all relevant windows, rather than splitting one family
into independently checked fragments. Generic technical artifacts omit the
family/table. IDs (including the raw atom-universe ID) use letters, digits, dots,
dashes or underscores, start with a letter/digit, and cannot carry local paths.
QCEvidenceRecord enforces its existing portable artifact-path contract; callers
must also keep explanatory text portable and free of local environment dumps.

## Empty-edge-table boundary

A present, strict-schema-valid header-only/zero-row protein-edge table is a
present artifact. Its empty rows do not emit `REQUIRED_ARTIFACT_MISSING`.
A requested window existing with no contacts differs from a missing requested
window definition/artifact. Only the latter is a hard missing-requirement failure.
The >1% empty-window REVIEW rule belongs to 32.C and is not calculated here.

## Structural integrity

Mapping and supplied table reference metadata must exactly match accepted Stage
30 constants: `uniprotkb:O95436-1:sequence-v3`, sequence SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.
Mismatch emits `CANONICAL_REFERENCE_MISMATCH`.

Protein edges with equal source/target canonical numbers emit
`FORBIDDEN_SELF_LOOP`. Specialized partner IDs/carrier positions are not canonical
protein endpoints and receive no protein self-loop test.

Duplicates use each accepted row's `row_identity` directly: full replica key,
window, canonical endpoints and edge type for protein edges; full replica key,
window, canonical protein residue and partner ID for specialized rows. Each family
is independent; only rows matching the requested replica key are inspected.
Distinct windows, replicas, systems, partners, edge types and families do not
collide. Repeated accepted identities emit `DUPLICATE_RECORD`; no deduplication.

Stored per-replica occupancy must be finite and within inclusive `[0,1]` in all
three families. Exact zero and one pass; below zero, above one, NaN and either
infinity emit `OCCUPANCY_OUT_OF_RANGE`. No tolerance, rounding or contact-count
recalculation occurs. This range check does not replace the stricter accepted
source schema's other relationships or sparse-positive row rules.

Accepted strict constructors already reject self-loops, duplicates and invalid
occupancies, and canonical constructors can load the packaged reference. The
pure evaluator reads existing model fields and accepted identity properties
without reconstructing them. Tests inject synthetic damage into private copies
of these models to verify defensive inspection and no repair. Future reader
rejection is supplied as schema FAIL; 32.B introduces no second scientific row
schema to represent rejected CSV rows.

## Check IDs, ordering and evidence

Fixed IDs and their ordering are frozen:

```text
topology_readable
trajectory_readable
topology_trajectory_atom_count
topology_trajectory_atom_order
canonical_mapping_complete
protein_pbc_integrity
frame_time_strictly_increasing
production_frame_coverage
required_metadata:<item_id>          # sorted item IDs
required_artifact:<item_id>          # sorted item IDs
schema:<item_id>                     # sorted item IDs
canonical_reference
forbidden_self_loops
duplicate_records
occupancy_range
```

A schema-valid required canonical artifact without its model adds
`schema:<item_id>:canonical_model` immediately after that artifact's schema check.
Only evaluated checks appear; their relative order is preserved. Every PASS and
FAIL has nonempty structured evidence. FAIL has an exact accepted 32.A hard
reason code and deterministic human-readable explanation. No reason codes are
added. Supporting evidence IDs are deterministically scoped as
`<check_id>:evidence:<zero-based-index>`, preserving source payloads while ensuring
uniqueness across findings even when one observation supports multiple checks.

## Real-data limitation and protected boundaries

Implementation acceptance uses synthetic evidence. No real per-replica semantic
atom-order authority or protein PBC integrity conclusion is established by this
task. Real smoke is skipped until both are supplied; the accepted box audit is
insufficient. Explicit complete real mapping authority must also be supplied for
any chosen replica. No atom-order, PBC, mapping or availability evidence is fabricated.

The 32.B pure module adds no CLI or workflow I/O. Stage 32.D now consumes its
findings for release decisions, reports, inventory/provenance and validation.
The first FAIL in accepted deterministic check order supplies the automatic
exclusion reason, prose and evidence IDs; all findings remain preserved.
Frozen scientific contract, Stage 27–31 source, preprocessing, aggregation,
annotations, PBC code, analysis, dependencies and WANIA remain unchanged.
Stage 32.D integration is complete. Stage 32 is complete.
