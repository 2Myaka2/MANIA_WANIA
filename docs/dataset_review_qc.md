# Dataset manual-review QC — Stage 32.C

## Status

Stage 31 is complete. Stage 32.A is accepted. Stage 32.B is accepted at committed
checkpoint `85fc62f17b47b94120b3e1e21c2c8af579396f60` on branch `FAIR`.
Stage 32.C manual-review QC is implemented in `mania.dataset_review_qc`.
Stage 32 remains incomplete. Stage 32.D integration is next.
Dataset v1.0 remains unreleased; version remains `mania-wania 0.1.0`.

## Review is not exclusion

The evaluator produces accepted Stage 32.A `ReplicaQCCheckResult` findings with
statuses **pass** or **review** only. `review_qc_status == "review"` does not imply
exclusion. No FAIL finding, release decision, decision mode, availability state,
reviewer, decision note, manual clearance or manual exclusion is produced.
Stage 32.D will combine the independent hard and review findings and apply the
unchanged [32.A decision contract](dataset_qc_contract.md), including unresolved
`pending_review` or an explicit manual resolution. A normal scientific REVIEW
is a valid result, not an exception.

## Pure API and models

```python
evaluate_dataset_review_qc(
    hard_evaluations: tuple[ReplicaHardQCEvaluation, ...],
    review_evidence: tuple[ReplicaReviewQCEvidence, ...],
) -> DatasetReviewQCEvaluation
```

Every new public model is a frozen dataclass with deterministic, independent,
JSON-compatible `to_dict()`. No timestamps, UUIDs or environment observations
are generated. Input tuples and their nested evidence are not mutated.

| Model | Fields, in declaration order |
| --- | --- |
| `RMSDDriftAssessment` | `drift_detected`, `assessment_method`, `evidence` |
| `ProteinEdgeEmptyWindowEvidence` | `expected_window_count`, `empty_window_count`, `evidence` |
| `ReplicaMADMetricObservation` | `dataset_id`, `system_id`, `trajectory_id`, `replica_id`, `engine`, `metric_family`, `metric_name`, `value`, `unit`, `evidence` |
| `ReplicaReviewQCEvidence` | `dataset_id`, `system_id`, `trajectory_id`, `replica_id`, `engine`, `rmsd_drift`, `protein_edge_empty_windows`, `mad_metrics` |
| `ReplicaReviewQCEvaluation` | `dataset_id`, `system_id`, `trajectory_id`, `replica_id`, `checks`, derived non-init `review_qc_status` |
| `DatasetReviewQCEvaluation` | `evaluations`, `skipped_hard_failed_replica_keys` |

The per-replica containers and metric observation expose `replica_key` as exactly
`(dataset_id, system_id, trajectory_id, replica_id)`. Identity fields must be
nonempty strings; engine is exactly `gromacs` or `namd`. Evidence identity must
match an accepted hard result in all four fields, and each metric must match
its review container's full key and engine. The accepted hard result has no
engine field: authoritative engine metadata is supplied by the review container.
No condition is required, inferred or looked up; `condition=None` is irrelevant.

Only `hard_qc_status == "pass"` replicas receive review evaluation. Hard-failed
replicas receive neither artificial PASS nor REVIEW; their keys appear only in
the sorted skipped tuple. Optional evidence supplied for a hard-failed replica
must still be well-formed, but never enters calculations or metric completeness.
Duplicate hard results, duplicate evidence containers, unknown full replica keys,
or missing review evidence for a hard-PASS replica raise
`DatasetReviewQCError(ValueError)`. Every hard-PASS replica requires an explicit
RMSD assessment and empty-window evidence, plus zero or more metric observations.
Absent evidence never implies no drift, zero empty windows or a scientific PASS.

## RMSD

`RMSDDriftAssessment.drift_detected` is an exact bool; integer substitutes are
rejected. `assessment_method` must be nonempty portable text and `evidence` a
nonempty tuple of accepted structured `QCEvidenceRecord` values.

- `False` produces PASS, with no reason code or reason prose.
- `True` produces REVIEW with `RMSD_DRIFT_REVIEW`.

32.C uses the supplied explicit authoritative assessment. No numeric drift
threshold, coordinate calculation, slope cutoff, regression algorithm, unit
cutoff or time-window heuristic is implemented. The method and bool remain
structured finding evidence. An independently supplied RMSD-derived scalar may
be a `basic_metric`, but its MAD finding never uses `RMSD_DRIFT_REVIEW`.

## Empty protein-edge windows

`expected_window_count` is the count of **valid requested windows**: each window
exists and has its required table/schema evidence. `empty_window_count` counts
only those valid windows with zero protein-protein edge rows. The caller attests
to this scope through explicit evidence; 32.C does not inspect artifacts or
recalculate windows. Missing windows/artifacts remain hard-QC territory and
must never be counted as empty scientific windows.

Counts are exact ints, bool rejected, with `expected_window_count > 0` and
`0 <= empty_window_count <= expected_window_count`. Evidence must be nonempty.

```text
empty_window_fraction = Decimal(empty_window_count) / Decimal(expected_window_count)
```

Only fractions strictly greater than `Decimal("0.01")` produce REVIEW with
`PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT`. Exactly 1% passes.
No binary-float threshold comparison or rounded percentage is used.

| Empty / valid requested | Outcome |
| --- | --- |
| 0 / 100 | PASS |
| 1 / 100 = 0.01 | PASS |
| 2 / 100 = 0.02 | REVIEW |
| 1 / 101 | PASS |
| 2 / 101 | REVIEW |

Evidence preserves both exact integer counts and the computed Decimal fraction
as portable strings. Repeating fractions use a fresh Decimal context with
precision `max(50, digits(expected_window_count) + 4)`; the counts preserve the
exact rational value. No global Decimal context is changed.

## MAD metrics and completeness

`ReviewMADMetricFamily` is exactly `Literal["edge_count", "contact_fraction",
"basic_metric"]`. `value` accepts exact Python int or float, rejects bool,
strings and non-finite values, and uses `Decimal(str(value))` internally.

- `edge_count`: non-negative integer-valued number; no rounding.
- `contact_fraction`: exactly within `[0, 1]`; no tolerance.
- `basic_metric`: any finite scalar.

`metric_name` is explicit, stable, nonempty caller-supplied text. `unit` is
explicit portable text or None; units are never inferred or converted. There
is no frozen production basic-metric list or contact-type taxonomy. Synthetic
tests use names such as `hbond_fraction` and `radius_of_gyration_mean_A` solely
as examples. Every observation requires nonempty structured evidence.

Within each hard-PASS dataset/system/engine cohort, the set of metric
`(metric_family, metric_name)` identities must match for every replica. Missing
one metric is invalid incomplete input: it is not zero and does not silently
reduce the cohort. All members may explicitly supply empty metric tuples.
Duplicate metric identities are rejected. Units must match within a metric
cohort, including explicit None, or evaluation raises `DatasetReviewQCError`.

## Reference cohort

The full reference cohort identity is:

```text
(dataset_id, system_id, engine, metric_family, metric_name)
```

Only hard-QC-passing replicas participate. Hard-failed replicas cannot influence
the median, MAD or bands. Systems remain separate even with identical condition
labels; GROMACS and NAMD never mix. A target remains in its own reference cohort:
statistics are calculated once for all hard-passing members, with no leave-one-out
calculation. Stage 32.C consumes accepted hard status without recalculating hard QC.

## Raw MAD and outlier band

All calculations use Decimal arithmetic in a fresh isolated local context with
sufficient precision for the supplied finite values, including even medians and
widely separated exponents. The global precision, rounding, traps and flags are
unchanged. Values and statistics are serialized as strings without float conversion.

```text
median = median(x_i)
absolute_deviations = abs(x_i - median)
MAD = median(absolute_deviations)
```

Odd medians use the middle sorted Decimal. Even medians use the arithmetic mean
of the two middle values. MAD is raw and unscaled: there is no 1.4826 factor or
other scaling. When MAD > 0:

```text
lower = median - 3 * MAD
upper = median + 3 * MAD
REVIEW only if value < lower or value > upper
```

Boundary values pass. There is no epsilon or tolerance.

| Family | Normal outside-band reason |
| --- | --- |
| `edge_count` | `EDGE_COUNT_MAD_OUTLIER_REVIEW` |
| `contact_fraction` | `CONTACT_FRACTION_MAD_OUTLIER_REVIEW` |
| `basic_metric` | `BASIC_METRIC_MAD_OUTLIER_REVIEW` |

For `[10, 20, 100]`, median is 20, MAD is 10 and the band is `[-10, 50]`;
100 reviews. For `[10, 20, 50]`, 50 passes exactly at the upper boundary.

## MAD zero

For reference count >= 2 and MAD == 0, no zero-width automatic outlier band is
applied. A target equal to the median passes. A differing target reviews with
`MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW`, never a normal metric-outlier code.
This records a degenerate reference distribution requiring manual review;
it does not automatically exclude anything.

`[10, 10, 100]` has median 10 and MAD 0: the first two pass and 100 reviews
with the zero-MAD reason. `[10, 10, 10]` passes throughout: zero MAD alone does
not justify REVIEW. Both bands are structured `not_applicable` evidence.

## Single replica

With exactly one hard-passing replica, cross-replica MAD comparison is not
applicable. Its check passes, with `reference_count = 1` and structured
`comparison = not_applicable_single_replica`. No MAD-zero review is generated.
Both bands are `not_applicable`; retained median/value and MAD describe only
the supplied singleton. This supports single-replica Cys systems.

For hard-PASS values 10 and 20 plus hard-FAIL value 1000, the reference values
are exactly `[10, 20]`, median 15, raw MAD 5 and band `[0, 30]`. The failed
replica receives no Stage 32.C evaluation. If every replica hard-failed, the
result has an empty evaluation tuple and only skipped keys.

## Finding evidence and determinism

Fixed check IDs are `rmsd_drift` and `protein_edge_empty_window_fraction`, followed
by metrics sorted by family/name as `mad:<metric_family>:<metric_name>`. Result
replicas and skipped keys are sorted by full replica key and must be unique
and disjoint. Identical input, including reordered replica tuples, yields
identical JSON-compatible output. Caller evidence order remains explicit.

Every PASS has structured evidence, `reason_code=None` and
`human_readable_reason=None`. Every REVIEW uses only an accepted reason code,
deterministic portable prose, and structured supporting evidence. Any REVIEW
check derives `review_qc_status="review"`; otherwise it is `"pass"`.

MAD evidence includes target value, reference count, median, raw MAD, both bands,
comparison applicability, engine, family, name, supplied unit and source evidence.
RMSD and window findings similarly retain their source evidence and structured
assessment/count/threshold values. Evidence IDs follow the accepted 32.B style
`<check_id>:evidence:<index>`, preserving payloads while ensuring uniqueness
across findings. Accepted evidence validation is reused; lexical checks also
reject absolute/home/environment paths and control characters in supplied text.
No filesystem resolution occurs. Caller prose must be portable and must not
include usernames; `manual_review` evidence belongs to subsequent decisions.

## Real-data evidence policy

Acceptance uses synthetic explicit authority. No authoritative real RMSD drift
assessment with method/evidence, valid requested/empty protein-edge window counts,
or complete named per-cohort edge-count/contact-fraction/basic-metric observations
with units and source evidence was supplied for this task. Real Stage 32.C smoke
is therefore skipped. Production review metric sets and RMSD methodology remain
external authority; real assessments and measurements are never fabricated.
This does not block implementation or synthetic acceptance.

## Stage 32.D and scientific boundary

Stage 32.D integration is next: it will combine hard and review findings, create
authoritative release decisions, bridge Stage 31 aggregation availability, and
add reports, inventory/provenance and validation. None of that integration exists
in 32.C; Stage 32 remains incomplete.

The evaluator uses no filesystem, network, Git, subprocess, clock, trajectory or
topology access. It does not calculate RMSD, protein/lipid/glycan contacts,
occupancy or windows, canonicalize residues, rerun hard QC or aggregate replicas.
It does not mutate Stage 31 manifests or source and adds no CLI integration.
Accepted Stage 27–31 science, 32.A/B source, frozen scientific contract,
preprocessing, mapping/annotations, PBC, analysis, dependencies and WANIA remain
unchanged. There is no new runtime dependency or version change.
