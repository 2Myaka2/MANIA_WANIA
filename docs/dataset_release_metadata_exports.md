# Dataset v1.0 metadata publication exports — Stage 33.B

## Status

Stage 32 is complete (Stage 32 COMPLETE). Stage 33.A is accepted at
`60940ef803d6bdbdc98956aa559c7e2f72548313` and remains the frozen schema authority.
Stage 33.B metadata/QC/canonical publication exporters are implemented.
Stage 33 remains incomplete. Stage 33.C scientific publication exporters are next.
Dataset v1.0 remains unreleased. Package version remains `mania-wania 0.1.0`.

Exactly these ten tables are supported:

| Table | Exact relative path |
| --- | --- |
| Systems | `metadata/systems.csv` |
| Simulations | `metadata/simulations.csv` |
| Time windows | `metadata/time_windows.csv` |
| Contact definitions | `metadata/contact_definitions.csv` |
| Software versions | `metadata/software_versions.csv` |
| QC decisions | `metadata/quality_control.csv` |
| QC findings | `metadata/quality_control_findings.csv` |
| QC evidence | `metadata/quality_control_evidence.csv` |
| Canonical nodes | `canonical/nodes.csv` |
| Biological annotations | `canonical/residue_annotations.csv` |

## Inputs are authoritative accepted models

`build_dataset_release_metadata_tables` in `mania.dataset_release_metadata`
returns a frozen `DatasetReleaseMetadataTables` containing all ten logical tables.
It consumes accepted Stage 32 `DatasetQCDecisionSet` and `DatasetQCSummary`, a
QC-derived Stage 31 `ReplicaAggregationManifest` with explicit derivation evidence,
Stage 27 `PreprocessingConditionTemporalExecution` records, complete Stage 30
system annotation models, supplied contact definitions and supplied software
version records. It does not rerun QC, sampling, canonical mapping or science.

The production order remains:

```text
27–30 per-replica science
  -> 32 QC and authoritative decisions
  -> accepted QC-derived Stage 31 manifest
  -> 31 aggregation
  -> 33 publication
```

33.B does not execute that DAG. `QCDerivedAggregationEvidence` binds the supplied
manifest to its decision set and a portable source reference with role
`qc_derived_replica_aggregation_manifest`. This is an explicit caller attestation
from accepted Stage 32 output, not a mechanism to promote a pre-QC template.
The manifest alone is rejected. Full artifact lineage verification belongs to
33.D. Any `pending_review` decision prevents release metadata construction.

There is no caller-file reading, directory scan, current-environment inference or
directory creation in builders. Accepted Stage 30 public APIs load only their
packaged pinned reference resource. Stage 31 manifest construction is not repeated,
because its constructor resolves and inspects source paths. Group/member metadata
is checked without inspecting those paths. Input models remain unchanged.

## Systems / simulations

Systems use `(dataset_id, system_id)`. Replicas assigned to a system must agree
exactly on `engine, variant_id, condition, disulfide_state`. Disagreement fails.
`condition` remains nullable, with no invented NAMD labels. Equal conditions never
merge distinct systems.

Simulations use the full key
`(dataset_id, system_id, trajectory_id, replica_id)`. Their population is exactly
the unique candidate population shared by Stage 32 decisions and the QC-derived
Stage 31 manifest. Missing or extra candidates fail. Repeated group/window
occurrences must agree on identity labels, availability state and reason.
QC fields and accepted aggregation availability/reasons are copied losslessly.

## Excluded trajectories remain visible

A hard-failed replica retains its simulations row with
`fail / excluded / automatic`, its accepted reason, QC decision, findings and
evidence. A manual REVIEW exclusion retains `review / excluded / manual` and
manual provenance. Both have scientific inclusion false. A QC-derived excluded
member has aggregation inclusion false. No historical metadata is deleted.

## Scientific-release inclusion

The caller must explicitly supply `scientific_release_replica_keys`, representing
replicas whose required publication science has been proven present. Keys must
be unique full candidate keys, each with `release_decision=available`.
`included_in_scientific_release` is true exactly for that set. QC availability
does not prove science-file existence. The builder never examines source files
or sparse science rows. 33.C/33.D will derive this selection from publication
science models.

## Technical unavailable

Stage 31 availability is copied as `available`, `unavailable` or `excluded`.
`included_in_replica_aggregation` is true exactly for `available`. Available
reasons stay null; unavailable/excluded reasons retain accepted nonempty text.
Stage 32's technical-unavailable precedence is preserved even if QC also excludes
the replica. Technical absence never becomes a new QC decision.

A QC-available, aggregation-unavailable replica remains visible. It can have
scientific inclusion true or false according only to the explicit science set.
The science set need not equal the aggregation-available set.

## Time windows

All supplied valid requested windows for candidate replicas are published,
including historical rows for subsequently excluded replicas. Missing temporal
evidence creates no rows; the candidate remains in simulations/QC.

Requested production/window bounds, endpoint inclusion, length, step, overlap and
stride remain separate from nullable effective observed endpoints. Accepted
expected/resolved/missing counts and coverage are copied. The existing Stage 27
models validate partitions and coverage; no sampling is rerun. Effective ps
bounds are converted to ns by an exact decimal exponent shift. Empty windows
preserve null effective bounds. Incompatible physical definitions sharing a label
or index within a replica fail, as do duplicate primary keys.

## Contact definitions

`build_dataset_release_contact_definition` projects a supplied complete accepted
parameter tree into the frozen long-form schema, one row per tree node. The
caller supplies the full replica key, stable definition ID, layer, interaction
type, portable source role/path, all required parameter roots and optional units
keyed by parameter path. No defaults or scientific definitions are inferred.

The evidence must carry actual run configuration: for generic protein contacts,
use `PreprocessingContactDetectionOptions.to_dict(include_contact_selection=True)`
so selection, atom filtering, cutoffs, skip lists and exclusions remain visible.
Accepted typed edge semantics, atom maps, angles, interval/exclusive rules and
other type-specific options remain in the supplied tree, without collapse to one
protein cutoff. Stage 29 lipid/glycan cutoffs, units and distance-definition
constants supply 6 Å / 4.5 Å inclusive whole-partner heavy-atom minimum geometry.
Accepted evidence also retains resolved-frame occupancy, requested-index episode
continuity, gap tolerance zero, actual-time lifetime, positive-frame-only distance
statistics and glycan carrier-first-sugar summary exclusion.

PBC evidence preserves internal minimum-image correction false, external
preparation declarations and observation-only audit semantics. Scientific PBC
status remains unresolved. The exporter neither applies nor claims internal PBC
correction. It projects caller authority and does not certify scientific content.

Objects, arrays, null and all scalar types survive separately, including empty
containers and strings. Paths use `$` at the root and the accepted `~0` / `~1`
escaping. Units and every supplied parameter are preserved. Container member
order is normalized; array order remains encoded by indexes.

## Software versions

`build_dataset_release_software_versions` takes explicit schema-shaped records
with `dataset_id, component_role, component_name, version, run_id,
source_artifact_role, source_artifact_path`. Unknown versions/run IDs remain null.
A recorded `mania-wania 0.1.0` remains that value regardless of the export machine.
No `pip freeze`, version lookup or environment inference occurs. Duplicate or
conflicting component records under the frozen source-scoped primary key fail.
Different authoritative runs may legitimately record different versions.

## Normalized QC

`build_dataset_release_qc_tables` copies the accepted summary's hard/review
statuses and counts. It cross-checks that summary against the accepted Stage 32
decision-to-summary projection, without invoking a QC evaluator.
Every decision produces one decision row. Every finding, including PASS,
produces a finding row. Every accepted evidence record produces an evidence row.
`used_for_decision` is true exactly for membership in `decision_evidence_ids`,
which must each trace to exactly one evidence row. Manual reviewer/note remain
in the QC decision table; automatic values remain null. Evidence paths must
already be portable; unsafe paths fail without rewriting.

## Nodes

`build_dataset_release_nodes` uses the pinned Stage 30 resource/API exclusively:
690 rows, positions 1..690, identical reference ID/hash, exact canonical names.
Unobserved topology residues remain nodes. T330M position 330 remains THR;
source MET cannot modify the reference.

## Residue annotations

The caller explicitly supplies `annotation_publication_system_keys`, a subset
of systems. Every selected system requires `complete_for_system` Stage 30
metadata and gets exactly 690 canonical rows. Missing metadata fails; an empty
selection produces no annotations, not all-false biology. 33.D may require full
system coverage for final release.

The accepted Stage 30 per-residue builder supplies ECD (234–361 inclusive), MX35
(311–341 inclusive), glycosylation and variant flags. Glycan name, topology
presence and source/verifier are preserved. Variant source/verifier are copied
from the complete system site records, which retain evidence omitted by the
per-residue model. T330M 330 THR has ECD/MX35 true; variant flags require supplied
site metadata and are never inferred from a source MET/canonical THR mismatch.

## CSV rules

`DatasetReleaseTable` binds immutable tuple rows to the exact accepted
`PublicationTableSpec`. It exposes table ID, relative path, row count and schema
identity. No duplicate publication schemas or row dataclasses are introduced.
Rows sort by primary key, except time windows sort by full replica key then
`window_index, window_id`. Duplicate primary keys fail. The bundle validates all
in-scope foreign keys, including the simulations/QC cycle, findings/evidence,
annotation systems/nodes and contact-definition replicas.

`write_publication_csv(table, path, overwrite=False)` writes one requested file,
whose path must end in the exact frozen relative path. It uses the repository's
atomic temporary-file/link-or-replace convention, creates only the requested
parent chain and protects existing files. It never assembles the release tree.
`read_publication_csv(table_id, path)` requires explicit table identity, exact
headers and column counts, valid logical types and unique keys; it normalizes
row order. Low-level header-only tables are supported. Normal bundle builders
require nonempty systems/simulations, matching QC and all 690 nodes.

CSV is UTF-8, comma-delimited, one exact header and one final newline. Logical
null is a blank cell; booleans are lowercase `true` / `false`. `None`, `null`,
`NA` and `N/A` strings are never null sentinels. Nullable strings must be nonempty,
except `string_value` under contact `parameter_kind=string`, where blank means
the actual empty string. Noncanonical integer and boolean encodings fail.

Logical numbers normalize to exact `Decimal` values. Floats use their exact
binary-value decimal expansion, so CSV may contain more digits than a display
formatter. Integers and supplied Decimals retain their exact values. No rounding,
quantization or scientific modification occurs; converting a restored number
back to its original float preserves that float. Nonfinite values fail. Encoding
and normalization do not depend on the ambient Decimal precision. `to_dict()`
provides independent audit dictionaries and retains Decimal scalars.

## Stage 33.C

Per-replica science, replica/system aggregates and metrics remain 33.C work.
33.D owns release assembly, JSON manifest/inventory/provenance, full cross-table
validation and final acceptance. No publication CLI, Parquet adapter, runtime
roles, dependencies, WANIA changes or QC/science recomputation are added here.
