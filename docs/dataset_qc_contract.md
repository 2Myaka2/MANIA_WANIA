# Dataset QC contract — Stage 32.A

## Status

Stage 31 is complete. Stage 32.A QC contract is implemented in the standalone
pure `mania.dataset_qc_contract` module. Stage 32 remains incomplete.
Stage 32.B hard QC is next. Stage 32.C manual-review evaluation and Stage 32.D
aggregation availability/report/provenance/validation integration remain later.
Dataset v1.0 remains unreleased.

The accepted, committed Stage 31.D / Stage 31 COMPLETE checkpoint is
`01c6929046144ac9b4d94bbbebdaf27e243d4bcf` on branch `FAIR`.
The frozen [Dataset v1 scientific contract](dataset_v1_scientific_contract.md)
is unchanged. This document adds QC contracts, not scientific evaluation.

## Authority boundary

Stage 31 accepts explicit `available`, `unavailable` and `excluded` aggregation
control states. It does not decide why a replica is excluded. Stage 32 is the
first layer that owns authoritative QC exclusion reasoning. In future production
Dataset execution, every `excluded` state must trace to an authoritative Stage 32
decision with a reason and supporting evidence. Arbitrary anonymous/manual
exclusion is forbidden in that production path.

32.A defines this authority contract only. Stage 31 source, accepted calculations,
control manifests and workflow behavior remain unchanged. Existing Stage 31
controls do not yet acquire QC authority through this module.

Every decision uses exactly `(dataset_id, system_id, trajectory_id, replica_id)`.
The derived `replica_key` contains those four strings. `condition` is absent from
the authority model. A bare replica ID has no authority across systems: system A,
replica `1` and system B, replica `1` are distinct. No biological identity,
condition or reviewer identity is inferred.

## QC status vs release decision

The public aliases are exact:

- `QCStatus`: `pass`, `review`, `fail`.
- `QCReleaseDecision`: `available`, `pending_review`, `excluded`.
- `QCDecisionMode`: `automatic`, `manual`.

QC status and release decision are separate semantics. A `review` is unresolved
until an explicit manual resolution supplies the required provenance.

| QC status | Decision mode | Release decision | Required outcome |
| --- | --- | --- | --- |
| `pass` | `automatic` | `available` | Only PASS path |
| `review` | `automatic` | `pending_review` | Unresolved review |
| `review` | `manual` | `available` | Explicit human clearance |
| `review` | `manual` | `excluded` | Explicit justified manual exclusion |
| `fail` | `automatic` | `excluded` | Only FAIL path; no override |

Every other combination is rejected. Review findings never automatically
exclude a replica or make it production-available. PASS cannot be manually
excluded; a hard FAIL cannot be overridden to available. Manual pending review
is not a resolution.

## Unavailable

Stage 31 `unavailable` is a technical/statistical availability state, separate
from QC failure or exclusion. It is deliberately not a `QCReleaseDecision`.
`pending_review` is not production-available. Stage 32.D will define the exact
bridge without treating unavailable data as a QC failure or statistical zero.

## Reason codes and severity ownership

`QCReasonCode` is the frozen Literal taxonomy below. The deterministic public
`expected_qc_status(reason_code)` helper returns its exact severity class and
rejects unknown codes. No reason code represents PASS. A reason cannot be paired
with another status: for example, `RMSD_DRIFT_REVIEW` with `fail` and
`OCCUPANCY_OUT_OF_RANGE` with `review` both fail validation.

Hard-fail codes, always `fail`:

```text
TOPOLOGY_UNREADABLE
TRAJECTORY_UNREADABLE
TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH
TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH
CANONICAL_MAPPING_INCOMPLETE
PROTEIN_PBC_BROKEN
FRAME_TIME_NOT_STRICTLY_INCREASING
PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT
REQUIRED_METADATA_MISSING
REQUIRED_ARTIFACT_MISSING
SCHEMA_INVALID
CANONICAL_REFERENCE_MISMATCH
FORBIDDEN_SELF_LOOP
DUPLICATE_RECORD
OCCUPANCY_OUT_OF_RANGE
```

Manual-review codes, always `review`:

```text
RMSD_DRIFT_REVIEW
PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT
EDGE_COUNT_MAD_OUTLIER_REVIEW
CONTACT_FRACTION_MAD_OUTLIER_REVIEW
BASIC_METRIC_MAD_OUTLIER_REVIEW
MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW
```

Machine behavior is determined by status, reason code, release decision and
decision mode. Human-readable prose provides auditable explanation only; it is
never a machine identity or an instruction to change severity.

## Evidence

Frozen `QCEvidenceRecord` fields, in declaration/serialization order:

```text
evidence_id: str
evidence_type: QCEvidenceType
artifact_role: str | None
artifact_path: str | None
window_id: str | None
metric_name: str | None
observed_value: str | None
expected_or_threshold: str | None
details: str | None
```

`QCEvidenceType` contains exactly `artifact`, `metric`, `window`, `mapping`,
`pbc`, `manual_review`. There is no generic `other` type. An ID/type pair alone
is insufficient; the following minimum structure is mandatory:

| Type | Required payload |
| --- | --- |
| `artifact` | `artifact_role` and `artifact_path` |
| `metric` | `metric_name` and `observed_value` |
| `window` | `window_id` plus at least one of `metric_name`, `observed_value`, `details` |
| `mapping` | An artifact role/path pair, or `details` |
| `pbc` | An artifact role/path pair, or `observed_value`, or `details` |
| `manual_review` | `details` |

Strings are stripped of outer whitespace only. Case, internal whitespace and
prose are preserved. Optional strings remain `None` when explicitly absent;
supplied blank strings and non-string values are rejected, never silently
converted into invented content or absence. Status/type/reason literals must
already be exact. IDs and evidence references use the same strip-only rule.

Artifact paths are portable relative forward-slash paths. Absolute POSIX paths,
Windows drive/UNC paths, backslashes, empty/`.`/`..` path components, URI/drive
colons, control characters and home/environment expansion markers (`~`, `$`, `%`)
are rejected. Paths are never resolved, expanded, checked for existence or read.
Callers supply portable references and explanatory text, not filesystem dumps
or local environment/user-home information. The contract collects no environment
information. Metric observations and thresholds are text, not evaluated numbers.

## Checks and overall status

Frozen `ReplicaQCCheckResult` has fields `check_id`, `status`, `reason_code`,
`human_readable_reason`, `evidence`, in that order. The ID is non-empty and
`evidence` is an exact non-empty tuple of `QCEvidenceRecord` objects. Evidence IDs
must be unique within the check.

PASS requires `reason_code=None` and `human_readable_reason=None`, but still
requires evidence showing what was checked. REVIEW requires a review code and
non-empty human-readable reason; FAIL requires a hard-fail code and non-empty
human-readable reason. All three require evidence.

Frozen `ReplicaQCDecisionRecord` fields, in declaration/serialization order:

```text
dataset_id: str
system_id: str
trajectory_id: str
replica_id: str
qc_status: QCStatus
findings: tuple[ReplicaQCCheckResult, ...]
release_decision: QCReleaseDecision
decision_mode: QCDecisionMode
decision_reason_code: QCReasonCode | None
human_readable_reason: str | None
decision_evidence_ids: tuple[str, ...]
reviewer: str | None
decision_note: str | None
```

The four identity strings are required. Findings must be an exact non-empty
tuple: an empty record cannot claim an auditable PASS. Within a replica, check
IDs are unique and evidence IDs are globally unique across all findings.

Overall status is `fail` if any finding fails, otherwise `review` if any finding
requires review, otherwise `pass`. The explicitly supplied `qc_status` must equal
this derived status; inconsistent summaries are rejected.

## Decision traceability and manual decisions

PASS requires automatic available with `decision_reason_code=None`,
`human_readable_reason=None`, `decision_evidence_ids=()`, `reviewer=None` and
`decision_note=None`. Its findings retain their evidence.

Every non-PASS decision requires a reason code of the overall QC status class,
non-empty human-readable rationale and a non-empty exact tuple of unique evidence
references. The selected reason must occur in at least one finding of that
status class. Every referenced evidence ID must belong to a finding carrying
that selected reason. Unknown IDs and references to unrelated findings are
rejected, including a mixture of supporting and unrelated IDs. Multiple findings
with the same reason may supply evidence.

This establishes `decision -> reason code -> finding -> evidence` traceability.
FAIL decisions therefore cite evidence from FAIL findings; unresolved and
manually resolved REVIEW decisions cite evidence from REVIEW findings.

Automatic decisions forbid reviewer and decision note. Manual decisions are
allowed only for REVIEW and require both a non-empty opaque `reviewer` string
and a non-empty `decision_note`, in addition to reason, human-readable rationale
and evidence. An email address, prescribed name or biological ownership is not
required or inferred. Notes are supplied explicitly and never manufactured.

There is no anonymous manual exclusion. Omitting reviewer, decision note,
human-readable rationale or evidence from a manual exclusion rejects the record.
The same protection applies to manual clearance. A valid `manual_review`
evidence record may be included in the finding supporting the review reason.

## Decision set, canonical reference and serialization

Frozen `DatasetQCDecisionSet` accepts only
`records: tuple[ReplicaQCDecisionRecord, ...]`. It may be empty. Both direct
construction and `build_dataset_qc_decision_set(records)` reject duplicate full
replica keys and return records ordered lexicographically by dataset, system,
trajectory and replica ID. Inputs and their nested tuples remain unchanged.
Finding/evidence/reference order within a decision preserves the supplied order.

Non-init public fields are pinned:

- `schema_version`: `mania.dataset_qc_decision_set.v0.1`.
- `kind`: `mania_dataset_qc_decision_set`.
- `canonical_reference_id`: `uniprotkb:O95436-1:sequence-v3`.
- `canonical_reference_sequence_sha256`:
  `33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.

The canonical identity reuses accepted Stage 30 constants; sequence data is not
duplicated or read. Model fields cannot be reassigned. Each `to_dict()` returns
independent JSON-compatible values in declaration order, converting nested
models to dictionaries and tuples to lists. The derived `replica_key` is a
property, not an additional serialized field. Identical models produce identical
`json.dumps(obj.to_dict(), allow_nan=False, separators=(",", ":"))` output.
There are no timestamps, UUIDs, machine paths or environment-derived fields.
Validation raises `DatasetQCContractError`, a `ValueError` subclass.
No JSON readers/writers or QC files are added in 32.A.

## Hard-QC boundary

32.B later evaluates hard criteria from existing evidence. 32.A only freezes
reason/status semantics. It reads no topology, trajectory, temporal execution,
PBC audit, mapping table or aggregate table, and performs no occupancy or
duplicate-row scanning.

The future Stage 32.B production-frame coverage rule is: coverage below 95%
produces hard FAIL `PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT`. Coverage uses
accepted Stage 27 requested/resolved physical-sampling semantics. A missing
expected sample remains missing, not negative. No coverage calculation occurs
in 32.A. The mandatory synthetic smoke supplies the text observation `0.94`
and threshold `>=0.95` for `production_frame_coverage`; the supplied FAIL finding
produces automatic excluded with reason/evidence traceability.

`PROTEIN_PBC_BROKEN` is hard FAIL. Later Stage 32 evaluates already-existing
evidence only; it does not repair PBC, unwrap or center coordinates, or apply
internal minimum-image correction (MIC). The broader scientific PBC status
remains unresolved.

`CANONICAL_MAPPING_INCOMPLETE` is hard FAIL. Accepted Stage 30 explicit mapping
remains authoritative. Source-to-canonical mapping is never inferred from
source resid equality or any other heuristic.

## Review-QC boundary

32.C later calculates RMSD drift, empty protein-edge window fractions, medians,
MAD, outlier bands and contact/basic-metric review evidence. None of these
calculations is implemented in 32.A. Review codes never cause automatic
exclusion; only explicit manual resolution can clear or exclude a REVIEW.

### MAD zero

`MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW` does not mean automatic outlier or
automatic exclusion. It signals that MAD-based automatic classification is not
valid for that reference distribution. Its automatic decision remains
`pending_review`. Stage 32.C implements the evaluation later; 32.A does not
calculate MAD or median ± 3 MAD bands.

### Empty protein-edge windows vs missing artifacts

`PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT` is REVIEW-class, not hard
FAIL. An individual empty protein-edge window is not by itself a
missing-required-artifact hard failure. A valid sparse window with no positive
protein edge remains distinct from missing input.

`REQUIRED_ARTIFACT_MISSING` means a technically required artifact, table or
schema input is missing. It must not mean that a valid sparse window contains
no positive protein edge. Stage 32.C later evaluates the >1% empty-window rule.

## Aggregation bridge and preserved science

32.D will derive production Stage 31 aggregation availability from authoritative
QC decisions and add reports, provenance and validation. There is no availability
bridge, manifest input, CLI change, inventory/provenance role or unified
validation extension in 32.A.

Stage 32 QC evaluates existing evidence. It does not rerun contact detection,
episode detection, specialized distance calculation, canonicalization or replica
aggregation. 32.A implements none of those operations and performs no filesystem,
network, Git, clock or MDAnalysis access. Stages 27–31 calculations, preprocessing,
canonical mapping, biological annotations, PBC, analysis, dependencies, WANIA and
version `mania-wania 0.1.0` remain unchanged.
