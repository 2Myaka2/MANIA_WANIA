# Dataset QC workflow — Stage 32.D

Stage 32.A/B/C are accepted and their source and scientific semantics are
unchanged. Stage 32.D implements the separate Dataset-level authority and
orchestration layer. **Stage 32.D: PASS. Stage 32: COMPLETE.**
Stages 25, 26, 27, 28, 29, 30 and 31 are complete. Stage 33 publication export
is next and has not started. Stage 34 multi-engine pilot and Stage 35 full
production remain later.
The accepted Stage 32.C checkpoint is
`4b046ac4c8c61053f4d7fa1a9a6a3f284b2ce177` on branch `FAIR`.

## Execution and authority

```text
strict QC manifest + Stage 31 template + existing hard/review evidence
→ accepted 32.B hard evaluator
→ accepted 32.C Dataset review evaluator (hard-PASS cohorts only)
→ accepted 32.A ReplicaQCDecisionRecord / DatasetQCDecisionSet
→ summary and production_ready
→ optional QC-derived accepted Stage 31 aggregation manifest
```

```bash
mania dataset qc --manifest dataset_qc_manifest.json --output qc_run \
  --artifact-checksum-mode none
```

The checksum choices are `none` and `sha256`. `--overwrite` follows the existing
atomic writer convention. Use a dedicated QC output root. There are no threshold,
MAD-scale, RMSD-threshold, force-exclusion, or condition-filter options. The
command reports full-replica counts, pass/review/fail and release counts,
`production_ready`, output paths, and zero trajectory passes.

`dataset_qc_workflow.py` calls the accepted public evaluators and decision models;
it implements no independent MAD formula, RMSD calculation, frame sampling,
mapping, contacts, distances, contact episodes, or aggregation statistics.
`dataset_qc_run.py` adds only execution, inventory and provenance. No trajectories
are opened and MDAnalysis is not required. Canonical input tables named by the
Stage 31 template are preserved as locations; QC does not reread their science
or run `mania dataset aggregate-replicas`. Aggregation is a subsequent command.

## Strict QC control manifest

The frozen `DatasetQCManifest` contains `aggregation_manifest_template_path`
and a non-empty tuple `replicas`, sorted by unique full replica key. Fixed,
non-init metadata pins the accepted Stage 30 reference:

```json
{
  "aggregation_manifest_template_path": "aggregation/replica_aggregation_manifest.json",
  "replicas": [
    {
      "dataset_id": "synthetic",
      "system_id": "synthetic-system",
      "trajectory_id": "trajectory-1",
      "replica_id": "1",
      "hard_qc_evidence_path": "hard/replica-1.json",
      "review_qc_evidence_path": "review/replica-1.json",
      "manual_resolution": null
    }
  ],
  "schema_version": "mania.dataset_qc_manifest.v0.1",
  "kind": "mania_dataset_qc_manifest",
  "canonical_reference_id": "uniprotkb:O95436-1:sequence-v3",
  "canonical_reference_sequence_sha256": "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
}
```

This is a synthetic shape example, not authoritative evidence for a real run.
Every root and nested key is required, including explicit nulls for nullable
fields. Extra/duplicate keys, invalid literals, non-finite numbers, incorrect
scalar types, and mismatched fixed reference metadata fail. UTF-8 writers are
atomic, protected against overwrite by default, deterministic, and append one
newline. `read_dataset_qc_manifest`, `write_dataset_qc_manifest`, and
`validate_dataset_qc_manifest` provide the public manifest I/O.

All three control paths are portable relative forward-slash paths without
absolute paths, parent traversal, home/environment expansion, or empty path
components. Resolve them relative to the QC manifest location, never CWD.
The Stage 31 reader resolves its own canonical paths against its own location;
the accepted writer rebases their representation for the derived manifest while
preserving the canonical input locations.

QC controls must cover exactly the unique set of
`(dataset_id, system_id, trajectory_id, replica_id)` appearing anywhere in the
Stage 31 template. A replica repeated across windows has one decision and one
summary row. Condition is never QC authority. Identical conditions across systems
remain isolated, and `condition=None` is preserved in the Stage 31 manifest.

## Evidence adapters

`dataset_qc_evidence_io.py` provides strict read/write adapters for the exact
accepted evidence types. Its serialization-only `ReplicaHardQCEvidence` wrapper
has precisely the eight keyword inputs of `evaluate_replica_hard_qc`:
`identity`, `raw_integrity`, `mapping_binding`, `required_source_keys`,
`protein_pbc`, `sampling_plan`, `required_metadata`, and `required_artifacts`.
Nested accepted Stage 26/27/30 models are reconstructed through their constructors.
The canonical table family selects its exact accepted row/table model.

The review file reconstructs `ReplicaReviewQCEvidence`, including explicit
`RMSDDriftAssessment`, `ProteinEdgeEmptyWindowEvidence`, and any declared
`ReplicaMADMetricObservation` records. No observation is inferred from absent
evidence. Replica keys must match the controls; review engine must match hard
identity. Missing fields and wrong scalar types fail before evaluation.

Hard PASS requires a review evidence path. Hard FAIL skips review authority and
review cohorts entirely. An optional review file for a hard-failed replica is
still strictly read, identity-checked and inventoried. Its metrics do not enter
the reference distributions. Raw readability, atom order, PBC integrity and RMSD
drift remain supplied authoritative observations. Readers do not rediscover them.

## Final decisions and manual review

| Hard | Review | Manual control | Accepted final decision |
| --- | --- | --- | --- |
| FAIL | skipped | absent | `fail / excluded / automatic` |
| PASS | PASS | absent | `pass / available / automatic` |
| PASS | REVIEW | absent | `review / pending_review / automatic` |
| PASS | REVIEW | explicit clearance | `review / available / manual` |
| PASS | REVIEW | explicit exclusion | `review / excluded / manual` |

The first FAIL in accepted 32.B check order supplies the automatic exclusion
reason, prose and evidence IDs. The first REVIEW in accepted 32.C check order
supplies unresolved review authority. All findings remain in the decision JSON.
Combined check IDs and evidence IDs must be unique; the workflow never renames
them. Clean PASS and hard FAIL both forbid manual resolution.

`QCManualReviewResolution` contains exactly `release_decision` (`available` or
`excluded`), `decision_reason_code`, `human_readable_reason`,
`decision_evidence_ids`, `reviewer`, and `decision_note`. It has no `decision_mode`.
Reason must be review-class; prose, reviewer and note must be non-empty; evidence
IDs must be non-empty and unique. After evaluation the reason must occur in an
actual REVIEW finding, and every selected evidence ID must belong to REVIEW
findings carrying that same reason. An explicit manual resolution may select
any qualifying REVIEW reason. The unchanged 32.A model is the final validator.
Anonymous manual exclusion and inferred reviewer clearance are forbidden.

## Production bridge and the accepted architectural correction

A production template containing any pre-QC `excluded` member fails, even if QC
would also exclude it. Production exclusion must originate in an authoritative
32.A decision. Template `available` plus QC `available` stays available with no
reason. Template `available` plus QC `excluded` becomes excluded with:

```text
QC exclusion [<reason_code>]: <human_readable_reason>
```

Template `unavailable` remains a technical/statistical state with its exact
original reason, regardless of the separate QC release decision. It is never
converted into QC exclusion or added to correspondence membership.

The original request to preserve correspondence membership literally conflicted
with accepted Stage 31.C: every correspondence must cover exactly all available
replica keys. The accepted correction uses the shared pure bridge builder
`build_qc_derived_replica_aggregation_manifest(template, decisions)` to restrict
each lipid and glycan correspondence to the derived available replica set.

Partner correspondence evidence is immutable at the identity/binding level,
but its membership in the QC-derived production aggregation manifest is
restricted to replicas that remain statistically available after authoritative
QC. This is required by the accepted Stage 31.C exact-available-coverage
contract.

Correspondence ID, kind and name stay unchanged. All retained local bindings
stay unchanged: every replica key, local partner ID and partner name remains
exactly equal. Only bindings for
originally available replicas newly excluded by QC are removed. Projection acts
on every correspondence in every affected group/window independently; it never
matches by partner name or equal local ID and never adds, infers, renames, copies
or reassigns a binding. Missing retained evidence fails. If no available replicas
remain, both specialized correspondence collections are empty; no correspondence
with an empty member tuple is produced. Accepted Stage 31 constructors validate
the complete derived manifest. Stage 31 scientific source is unchanged.

The original template is immutable. Removed bindings remain in that template
and in original per-replica scientific artifacts; no scientific evidence is
deleted. Group specs, windows, expected replicas, canonical input locations,
engine, condition, variant and disulfide metadata are unchanged.

## Readiness, outputs and failure behavior

`production_ready` is true exactly when no authoritative decision remains
`pending_review`, including decisions for technically unavailable members.
Pending review is a valid completed QC outcome: CLI exit 0, decision and summary
outputs present, and no derived aggregation manifest. Technical unavailable
alone does not make QC unresolved.

| Output | Schema/authority | Presence |
| --- | --- | --- |
| `dataset_qc_decision_set.json` | Accepted `mania.dataset_qc_decision_set.v0.1` / `mania_dataset_qc_decision_set` | Always on success |
| `dataset_qc_summary.csv` | Exact 16-column audit summary | Always on success |
| `replica_aggregation_manifest_qc_derived.json` | Accepted `mania.replica_aggregation_manifest.v0.1` | Only production-ready |
| `artifact_inventory.json` | Unchanged Stage 25 inventory | Always on success |
| `run_provenance.json` | Unchanged Stage 25 provenance | Always on success |

Summary columns, in order:

```text
dataset_id,system_id,trajectory_id,replica_id,hard_qc_status,review_qc_status,qc_status,release_decision,decision_mode,decision_reason_code,human_readable_reason,reviewer,decision_note,hard_fail_count,review_finding_count,total_check_count
```

Counts derive from final authoritative records, not repeated aggregation members.
Nullable values use blank CSV cells, including `review_qc_status` after hard FAIL.
The low-level summary schema permits header-only output. Evidence payload remains
in the authoritative JSON. Neither scientific JSON nor CSV contains timestamps
or environment metadata.

All inputs, evaluations, decisions, summaries and optional derived models are
built before any scientific output write. Scientific/control failure writes no
new decision, summary or derived manifest. Writer failure can leave earlier
atomically successful files; failed provenance/inventory claim only successful
writes. Preflight prevents overwriting inputs, symlink targets and another
workflow's provenance. A pending rerun cannot reuse a root containing a previous
derived manifest, even with `--overwrite`; use a new output root.

## Inventory, provenance and offline reconstruction

Input roles are `dataset_qc_manifest`, `replica_aggregation_manifest_template`,
`dataset_hard_qc_evidence`, and `dataset_review_qc_evidence`. Every distinct listed
evidence file receives its own entry, including unused hard-FAIL review evidence;
identical contents are never deduplicated. The control manifest ID is
`input:dataset_qc_manifest`, portable path `inputs/dataset_qc_manifest.json`.
Other input IDs are `input:<role>:0001`, incrementing per role in deterministic
control order, with portable paths `inputs/qc/<manifest-relative-path>`.

Output roles are `dataset_qc_decision_set`, `dataset_qc_summary`, and conditional
`qc_derived_replica_aggregation_manifest`; IDs are `output:<role>`. Inventory
excludes itself and run provenance, preserving the Stage 25 DAG. `none` records
exact byte sizes with null SHA256 and never invokes the content-hashing helper.
`sha256` streams every inventoried input and successful output through the
accepted bounded helper.

Provenance workflow is `dataset_qc`. Configuration records the portable QC
manifest path, canonical reference, unique replica count, hard pass/fail counts,
review pass/review counts, final pass/fail and available/pending/excluded counts,
production readiness and checksum mode. Full evidence is not embedded. Conditions
and sampling are empty. References name only successfully written outputs and
inventory. Prior preprocessing, analysis and aggregation provenance is untouched.

```bash
mania artifacts validate qc_run --scope dataset_qc \
  --input-artifact-path input:dataset_qc_manifest=dataset_qc_manifest.json \
  --input-artifact-path input:replica_aggregation_manifest_template:0001=aggregation/replica_aggregation_manifest.json \
  --input-artifact-path input:dataset_hard_qc_evidence:0001=hard/replica-1.json \
  --input-artifact-path input:dataset_review_qc_evidence:0001=review/replica-1.json
```

Repeat mappings for every declared input. No CWD-based guessing occurs. Unmapped
inputs produce partial validation; mapped missing or malformed files fail.
Preserve the relative layout of the template's canonical locations and the
derived manifest when relocating a complete run bundle.

After generic integrity checks, `validation/dataset_qc.py` strictly reads all
roles, checks input/output lineage in both directions, and calls the same
workflow and bridge builder. It reruns accepted 32.B and 32.C, rebuilds 32.A
decisions, summary, readiness and correspondence projection, then compares every
output model and deterministic byte serialization exactly. It does not trust
stored decisions, counts or projected bindings. Missing required outputs,
unexpected derived output during pending review, changed manual provenance,
changed authority, changed retained binding or inconsistent counts fail even
under checksum `none`. Both production-ready and pending runs can validate
`status=passed`, `complete=true`, with zero unsupported current roles.
Failed-run declared files still receive strict/integrity checks, without requiring
a completed output set or scientific reconstruction. Failed provenance cannot
receive complete Stage 32 acceptance. No validation trajectory pass is performed.

## Real-data and publication boundary

Real Stage 32 QC smoke not run because authoritative hard-QC and/or review-QC
evidence is not yet available.

All framework acceptance evidence is explicitly synthetic. Real atom-order/PBC
observations, RMSD assessment, review metrics, manual resolution and QC decisions
must never be fabricated. Scientific PBC status and concrete final NAMD condition
labels remain unresolved. Dataset v1.0 remains unreleased, FastAPI is postponed,
and WANIA is unchanged. Publication export belongs to Stage 33 and is not started
by the QC command.

## Final acceptance matrix

All 132 criteria pass with the accepted revised criterion 55. These groups cover
every original criterion without changing its meaning:

| Criteria | Result | Evidence |
| --- | --- | --- |
| 1–7 | PASS | Accepted 32.A/B/C source unchanged; workflow and validation reuse evaluators; zero trajectory passes and no independent contact, RMSD or MAD calculations. |
| 8–20 | PASS | Strict manifest and exact evidence adapters; full-key coverage; pre-QC exclusion rejection; technical unavailable preserved; hard FAIL skipped; required review evidence and combined ID uniqueness enforced. |
| 21–36 | PASS | Automatic PASS/FAIL/pending rules, deterministic first-fail/first-review authority, explicit manual clearance/exclusion, and same-reason evidence traceability; clean PASS and hard FAIL overrides rejected. |
| 37–44 | PASS | Accepted decision set, strict deterministic JSON and summary CSV, exact unique-replica counts, resolved readiness and valid pending completion without derived output. |
| 45–57 | PASS | Availability bridge, deterministic exclusion prose, technical unavailable preservation, window/system isolation, null condition, accepted Stage 31 schema and canonical locations, revised correspondence projection without inference, no aggregation execution. |
| 58–68 | PASS | Every control/evidence/successful output inventoried; conditional derived role; no self/provenance cycle; exact sizes, no helper hashing under none, correct bounded SHA256 and mutation rejection. |
| 69–78 | PASS | Separate dataset_qc provenance with canonical reference, unique replica and status/release counts, readiness and portable paths; previous provenance and generic schemas unchanged. |
| 79–89 | PASS | Explicit unified scope/roles; strict mapped controls and evidence; accepted B/C/A reconstruction, shared bridge projection, exact output models and deterministic bytes. |
| 90–102 | PASS | Missing/unexpected outputs, changed decisions/summaries/availability/bindings/manual traceability and lineage fail; pending/resolved validation complete with zero unknown roles; conservative failed runs; all models built before writes. |
| 103–114 | PASS | Synthetic hard FAIL, clean PASS, pending REVIEW, manual clearance/exclusion, unavailable, pre-exclusion rejection, multiple windows, same-condition distinct systems, null condition, direct pure/workflow equality and deterministic reruns. |
| 115–126 | PASS | No fabricated real evidence; real QC smoke safely skipped; frozen scientific contract, Stage 27–31 science, PBC, analysis, dependencies, WANIA and version unchanged; config validation passes. |
| 127–132 | PASS | Full pytest, Ruff, mypy and installed offline wheel pass; Stage 32 complete only after acceptance; Stage 33 remains next and unstarted. |

The 12 additional bridge regressions cover protein-only exclusion, lipid,
glycan and combined projection, retained binding equality, missing binding
rejection, zero available replicas, technical unavailable, repeated windows,
multiple correspondences, identity metadata preservation and original-template
immutability. Complete reconstruction also rejects changed projected bindings.

The installed wheel was built and installed without index access or dependency
resolution, using task-owned directories outside the checkout:

```bash
.venv/bin/python -m pip wheel --no-index --no-deps --no-build-isolation \
  --wheel-dir "$stage32_wheel_root/wheels" "$stage32_wheel_root/source"
.venv/bin/python -m pip install --no-index --no-deps \
  --target "$stage32_wheel_root/installed_final" \
  "$stage32_wheel_root/wheels/mania_wania-0.1.0-py3-none-any.whl"
.venv/bin/python "$stage32_wheel_root/smoke_verified.py"
```

The smoke loads every MANIA module from the installed wheel. It blocks network,
Git/subprocess execution, MDAnalysis imports and trajectory/topology access.
Eight scenarios in both checksum modes (16 completed runs) pass complete unified
validation with zero unknown roles; pre-QC exclusion is rejected in both modes.
Scenarios include clean PASS, hard FAIL, pending REVIEW, manual available,
manual excluded, complete multi-system/multi-window projection, all excluded,
and technical unavailable. Roundtrips, immutable source templates, exact projected
bindings, expected decision equality and deterministic bytes are checked.
External-operation attempts and trajectory passes are both zero.

The frozen scientific contract SHA256 matches the accepted Stage 32.C checkpoint:
`c9efd004740f8aff039bede205dc2ef4d2212fd4067a7cf7628e403b8e065868`.
No commit or push is made by this task. The former blocked attempt changed no
files and is not a failed implementation checkpoint.


## Verification record

Final full-suite command and observed output after current-status updates:

```text
.venv/bin/pytest
8930 passed, 22 skipped in 143.81s (0:02:23)
```

The final wheel is 538919 bytes, SHA256
`2ab6927cef0f61ec75aae13c19f800dc28dc7b05ba9beacdc837501803947e22`.
Its installed final-source smoke passes all 18 cases, with 16 complete successful
validations and two expected pre-QC exclusion rejections. Both completed-run
variants use new task-owned output roots and verify overwrite-protected roundtrips.

Focused scientific/integration regression command:

```bash
.venv/bin/pytest -q tests/test_dataset_qc_*.py tests/test_dataset_hard_qc.py tests/test_dataset_review_qc.py tests/test_cli_dataset_qc.py tests/test_replica_*.py tests/test_canonical_*.py tests/test_annotated_*.py tests/test_biological_*.py tests/test_preprocessing_physical_time*.py tests/test_preprocessing_protein_edge*.py tests/test_preprocessing_protein_lipid*.py tests/test_preprocessing_protein_glycan*.py tests/test_preprocessing_contact_episodes.py tests/test_preprocessing_specialized*.py tests/test_preprocessing_molecular*.py tests/test_artifact_inventory*.py tests/test*run_provenance*.py tests/test_unified*.py tests/test_run_artifact_validation.py tests/test_dataset_v1_scientific_contract_docs.py tests/test_readme_current_workflow_docs.py
```

```text
4716 passed, 2 skipped in 83.10s (0:01:23)
```

The new Stage 32.D implementation has 188 passing test cases. After updating
current status docs and their tests, the focused documentation/frozen-contract
checks report:

```text
.venv/bin/pytest -q tests/test_readme_current_workflow_docs.py tests/test_dataset_v1_scientific_contract_docs.py
62 passed in 1.08s

.venv/bin/ruff check .
All checks passed!

.venv/bin/mypy src
Success: no issues found in 165 source files

.venv/bin/mania --version
mania-wania 0.1.0

.venv/bin/python -m mania --version
mania-wania 0.1.0

.venv/bin/mania validate-config configs/mania.example.yaml
Config is valid: configs/mania.example.yaml

.venv/bin/mania run --config configs/mania.example.yaml
MANIA pipeline execution is not implemented yet.
Project: NaPi2b_NORM_TUMOR
Run ID: run_001
Run mode: full
Conditions: normal, tumor
Output directory: mania_output
```

The complete installed synthetic run contains seven authoritative replicas:
three PASS, two REVIEW, two FAIL; four available, three QC excluded, zero pending.
One technically unavailable template member retains that state and its original
reason even though its separate QC decision is excluded. Multiple windows do not
increase those counts. The separate pending smoke contains three replicas, with
one pending review and no derived manifest. Both pass complete unified validation.

Scope inspection confirms 35 authorized changed/new files and zero unexpected
files. All 156 protected tracked source/dependency/frozen-contract files are
byte-identical to the accepted Stage 32.C checkpoint. The installed wheel's Python
files match the final source byte-for-byte. `git diff --check` is empty; nothing
is staged. Branch remains `FAIR` and HEAD remains the accepted Stage 32.C commit,
with `develop` an ancestor. The user will commit reviewed changes manually.
