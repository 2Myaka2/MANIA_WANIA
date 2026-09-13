# Dataset v1.0 release assembly — Stage 33.D

## Status

Stage 25–32 are complete; Stage 32 COMPLETE. Stage 33.A/B/C are accepted.
Accepted Stage 33.C checkpoint: `4239b3cc74f6979eaeb9224db0a905f857b29b64`.
Stage 33.D final release assembly is implemented and final technical acceptance
has passed. Stage 33 is complete (Stage 33 COMPLETE) after all final gates passed.
Stage 34 is next and has not started.
Dataset v1.0 remains unreleased. Package version remains `mania-wania 0.1.0`.

## Production DAG

```text
27–30 per-replica science
  -> 32 QC and authoritative decisions
  -> QC-derived Stage 31 manifest
  -> 31 replica aggregation using that exact manifest
  -> 33 publication
```

The manifest and provenance copy the exact five-node
`PRODUCTION_EXECUTION_DAG` from the accepted Stage 33.A contract. Development
stage numbering never changes this production order. Stage 35 full production
will execute this same DAG.

## Control and publication manifests

`dataset_release_export_manifest.json` is an execution control. Its strict
schema is `mania.dataset_release_export_manifest.v0.1`, kind
`mania_dataset_release_export_manifest`. It is separate from the published
`release/dataset_manifest.json`, whose schema is
`mania.dataset_release_manifest.v0.1`, kind `mania_dataset_release_manifest`.

The control has exactly these fields, including the schema and kind above:

| Field | Authority |
| --- | --- |
| `dataset_id` | One Dataset shared by the complete candidate population. |
| `stage32_run`, `stage31_run` | Explicit `provenance_path`, `inventory_path`, and `input_bindings`. Each binding has exactly `artifact_id` and `path`; every inventoried upstream input is bound. |
| `decision_set_path`, `qc_summary_path` | Accepted Stage 32 decision-set JSON and summary CSV. |
| `qc_derived_manifest_path` | Declared conditional Stage 32 output. |
| `aggregation_manifest_used_path` | Exact control used by the completed Stage 31 run. |
| `protein_aggregate_path`, `lipid_aggregate_path`, `glycan_aggregate_path` | Successful Stage 31 outputs; null only when that family was not produced. |
| `canonical_bindings` | Each binding has `family` (`protein`, `lipid`, `glycan`), `path`, and full `replica_keys`. |
| `temporal_evidence_paths` | Explicit accepted Stage 27 `temporal_execution.json` files. |
| `annotation_bindings` | Exactly `dataset_id`, `system_id`, `path` per accepted complete-system annotation input. |
| `publication_inputs_path` | One narrow input for supplied contact definitions, software records and metrics. |
| `scientific_release_replica_keys` | Explicit full `(dataset_id, system_id, trajectory_id, replica_id)` selections. |
| `annotation_publication_system_keys` | Explicit `(dataset_id, system_id)` selections, equal to all published systems for final release. |

All paths are portable forward-slash paths relative to the control's parent.
Absolute paths, parent traversal, home shorthand and environment substitutions
are rejected. No upstream authority is discovered from directory contents.
Upstream runs retain their accepted layout: explicitly bound sibling
`artifact_inventory.json` and `run_provenance.json`. Input artifact IDs map
portable upstream aliases to the actual files under the control root.

The output manifest records release version `1.0`, Dataset and pinned canonical
reference ID/hash, the exact production DAG, all 20 registry descriptors, three
explicit Stage 32/31 authority references and counts `17`/`3`. It also declares
`upstream_reference_base=export_control_manifest_parent` and the external control
alias `inputs/dataset_release_export_manifest.json`. It can list its own registry
entry, but contains no own checksum and embeds no upstream scientific artifacts.

Both manifest readers reject unknown/missing fields, duplicate JSON keys, wrong
scalar types and modified fixed contracts. Writers emit deterministic UTF-8 JSON
with a final newline and atomic overwrite protection. They use no clock, network
or Git.

## Supplied publication input

One additional control uses schema
`mania.dataset_release_publication_input.v0.1` and kind
`mania_dataset_release_publication_input`. Its only other root keys are
`contact_definitions`, `software_versions`, and `metrics`.

Each contact definition contains the accepted builder arguments: `replica_key`,
`contact_definition_id`, `contact_layer`, `interaction_type`, `parameters`,
`source_artifact_role`, `source_artifact_path`, and `units`. The complete parameter
tree is projected by Stage 33.B; no defaults, cutoffs or atom lists are invented.
The frozen required roots preserve selections, cutoffs/comparators, typed rules,
PBC status, occupancy denominator, episode continuity, gap tolerance, lifetime,
and specialized distance semantics. Arbitrary nested parameter keys remain data.

Software records have the exact frozen `software_versions` fields. Metric
records have exactly the fields of accepted `AuthoritativePublicationMetric`.
The adapters validate and copy supplied values; they never query installed
software or promote QC evidence into primary metrics. Unknown software versions
remain null. Metrics can be replica-global or have an exact window key.

## File-level upstream authority

Assembly strict-reads the accepted decision, summary, aggregation manifest,
canonical CSV, temporal and annotation models. Accepted generic integrity APIs
check upstream file sizes and any recorded SHA256 values. Every upstream input
binding is checked against the corresponding accepted input-spec collector.

Stage 32 must be completed and production-ready, with no pending review. Its
configuration, candidate population, counts, command, output references and
inventory must agree. Decisions, summary and the QC-derived manifest must be
declared successful outputs at their exact bound paths.

The Stage 31 manifest used must equal the QC-derived model exactly, including
source paths, groups, windows, member availability and correspondence. Its
provenance command/configuration and inventoried input bind that manifest.
Every produced aggregate family must be explicitly bound to the corresponding
successful output role and path. A copied unrelated aggregate, different manifest
binding or pre-QC manifest fails even if its standalone schema is valid.

Stage 33 does not execute upstream unified science reconstruction, QC evaluators
or aggregation. It uses structural integrity and accepted strict readers, then
calls the accepted Stage 33.B/C publication builders. There are zero trajectory
passes, no topology access, and no contact, sampling, mapping, annotation, QC,
RMSD/MAD or aggregate-statistics recalculation.

## Historical population and selection

Every Stage 32 candidate retains a simulation and QC row. All accepted findings
and evidence, including excluded trajectories, remain exact. A hard-failed
simulation can have no valid temporal rows. No time windows are fabricated.

Scientific inclusion requires an explicitly selected QC-available replica with
listed canonical artifact coverage in all three families. Coverage comes from
bindings, so a selected replica can legitimately have zero rows in every sparse
science table. Missing evidence does not become a fake zero row.

Technical unavailability is independent of the QC decision and remains visible.
Stage 31 unavailable/excluded members have aggregation inclusion false and do not
enter aggregate denominators. QC-available unavailable replicas can still enter
per-replica publication when explicitly selected with complete artifact evidence.

## Cross-table validation

All frozen primary keys are rechecked. Stage 33.B checks metadata foreign keys;
Stage 33.C checks science, aggregates and metrics against metadata. This covers
every declared Stage 33.A FK. The only conditional FK is the time-window link
for replica-global metrics, whose two window identity fields must both be null.

The full validator also compares exact authoritative simulation and QC populations,
all findings/evidence, duplicated identity labels, exact 690-position nodes,
complete 690-row annotations for every system, and artifact-based science coverage.
It checks exact aggregate group/window definitions, available-member counts and
specialized correspondence IDs in the authoritative group/family. Statistical
values remain copied. T330M retains canonical `330 THR` despite source `MET`.
Nullable conditions remain null; systems sharing `NORM` remain distinct.

## Exact publication tree

```text
metadata/systems.csv
metadata/simulations.csv
metadata/time_windows.csv
metadata/contact_definitions.csv
metadata/software_versions.csv
metadata/quality_control.csv
metadata/quality_control_findings.csv
metadata/quality_control_evidence.csv
canonical/nodes.csv
canonical/residue_annotations.csv
science/protein_edges_by_window.csv
science/protein_lipid_contacts_by_window.csv
science/protein_glycan_contacts_by_window.csv
aggregates/protein_edges_by_window_replica_aggregation.csv
aggregates/protein_lipid_contacts_by_window_replica_aggregation.csv
aggregates/protein_glycan_contacts_by_window_replica_aggregation.csv
metrics/metrics.csv
release/dataset_manifest.json
release/artifact_inventory.json
release/provenance.json
```

Exactly 17 CSV + 3 JSON files are produced. Header-only tables are valid when the
expected population is empty. Output-tree inspection rejects extra artifacts;
this inspection never discovers input authority. CSV and JSON are normative.
Parquet remains an optional future adapter; no Parquet implementation, dependency
or CLI option is added.

## Inventory, provenance and failure boundary

The unchanged generic `ArtifactInventory` has exactly 18 output entries: the
17 CSVs and dataset manifest. Roles are the frozen registry artifact IDs; entry
IDs are `output:<artifact_id>`. Inventory excludes itself and provenance, so
the graph has no checksum cycle. Inputs remain external explicit audit bindings.

`none` records exact sizes and null SHA256 without invoking the content-hash
helper. `sha256` uses the accepted bounded streaming helper. Inventory uses stable
logical release identity `dataset-release:<dataset_id>:1.0`, ensuring identical
inputs and checksum mode produce byte-identical inventory, manifest and CSVs.
Provenance records timestamps separately; its run ID is the same logical identity.

The unchanged `RunProvenance` schema uses workflow `dataset_release`. It records
the control alias, production DAG, canonical identity, upstream run bindings,
manifest used, exact population counts, checksum mode, successful output references
and verified aggregate lineage. Its software identity records the running MANIA
package version with Git fields explicitly unavailable. Publication software
metadata always comes from the supplied input. No current checkout is inspected.

All inputs, lineage, 17 tables, relationships, manifest and deterministic
serialization are validated before the first output write. Pre-write failure
creates no release files. Files are then written atomically in registry CSV order,
followed by manifest, inventory and provenance. Later failure reports incomplete
release; partial CSVs may remain. Completion JSON is removed on failure where the
filesystem permits cleanup, preventing a false completed release declaration.
Explicit overwrite invalidates previous completion JSON before writing. Inputs
and unknown output files are protected.

## CLI and offline reconstruction

```bash
mania dataset publish --manifest dataset_release_export_manifest.json \
  --output dataset_release --artifact-checksum-mode none
mania artifacts validate dataset_release --scope dataset_release \
  --input-artifact-path input:dataset_release_export_manifest=dataset_release_export_manifest.json
```

Use `--artifact-checksum-mode sha256` for checksums and `--overwrite` for explicit
replacement. There are no scientific threshold or inclusion override options.
Expected failures use `Dataset release <phase> failed:` without a traceback.

The unified scope requires that explicit external control mapping; it never
guesses a control location or copies the control into the 20-file release surface.
Validation reruns the same assembly builders, reconstructs all 17 expected models,
checks their relationships, and compares strict CSV models and deterministic bytes.
It reconstructs the dataset manifest and validates exact inventory metadata,
sizes/hashes, provenance configuration, command, counts and successful references.
Validation is read-only and needs no trajectory runtime.

## Real-data boundary and Stage 34

Synthetic framework acceptance does not release Dataset v1.0 or satisfy Stage 34.
Real Stage 33 Dataset release smoke not run because authoritative complete
real production inputs are not yet available.

Stage 34 remains next and unstarted: a real multi-engine pilot requires at least
one real three-replica group, real canonical mapping and physical-window contract,
authoritative real Stage 32 QC-derived availability/exclusion, and real Stage 31
aggregation, preferably T330M. Specialized layers require authoritative real
partner correspondence. Stage 35 full production remains later.
Concrete NAMD conditions remain pending, scientific PBC remains unresolved,
FastAPI remains postponed, and WANIA is unchanged.

## Final Stage 33 acceptance

The final 159-criterion matrix is grouped below. PASS records framework
acceptance; it does not assert a real Dataset release or a completed Stage 34.

| Criteria | Gate | Result |
| --- | --- | --- |
| 1–10 | Committed checkpoint; unchanged accepted schema/builders/science; correct production DAG; zero trajectory and scientific recomputation | PASS |
| 11–17 | Exact 17 CSV + 3 JSON surface; separate strict control; portable paths; explicit inputs | PASS |
| 18–35 | Stage 32 authority and production readiness; exact QC-derived manifest and Stage 31 run binding; substitution rejection; explicit publication inputs | PASS |
| 36–41 | Explicit science/annotation selections; artifact-based sparse coverage; accepted 33.B/C builder reuse | PASS |
| 42–75 | All 28 declared foreign keys; historical QC/exclusions; exact windows/nodes/annotations; denominators/correspondences/metrics; nullable conditions and T330M | PASS |
| 76–98 | Strict output manifest; exact registry; 18-entry cycle-free inventory; checksums; deterministic bytes; portable complete provenance; unchanged upstream runs | PASS |
| 99–118 | Build before writing; conservative failures; complete and header-only releases; synthetic population variants; supplied metadata and metrics; exact aggregate values | PASS |
| 119–139 | Unified read-only reconstruction; exact model/byte comparison; lineage/FK/history/denominator/correspondence mutations rejected; no extra outputs | PASS |
| 140–152 | No fabricated real authority; real release deferred; Stage 34/35 boundaries; no Parquet/dependencies/version/scientific-contract/WANIA changes | PASS |
| 153–159 | Full pytest, Ruff, mypy, CLI/config and offline installed-wheel checks; Stage 33 completion; Stage 34 next and unstarted | PASS |

Synthetic tests execute accepted QC followed by accepted aggregation before
release guards are installed. Publication and reconstruction then run with
upstream science, network, subprocess and trajectory access blocked. The offline
wheel repeats complete release, exclusion/unavailability, canonical T330M,
projected correspondence, exact three-replica statistics, null single-replica SD,
metrics, manifest, both checksum modes, determinism and unified validation.
No real production evidence is synthesized by the application.
