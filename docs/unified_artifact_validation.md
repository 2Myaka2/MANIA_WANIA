# Unified technical artifact validation — Stage 25.D

## Stage 31.D — canonical replica aggregation scope

The [separate Dataset aggregation workflow](replica_aggregation_workflow.md)
uses explicit scope `replica_aggregation`, with root `artifact_inventory.json`
and `run_provenance.json`. Generic schemas and preprocessing/analysis validation
behavior are unchanged. All seven aggregation roles have strict readers:
the manifest, three canonical input families and three aggregate output families.

Complete technical validation requires explicit `ARTIFACT_ID=PATH` mappings for
the manifest and every listed canonical file. It reads exact Stage 31.A/C control
models and the accepted Stage 30.C canonical CSV models, reconstructs A groups,
reruns accepted B/C aggregation, builds aggregate tables, and compares exact
models **and deterministic CSV bytes**. Inputs may be relocated without the
checkout or original source paths; no directory scan or trajectory access occurs.

Completed runs require exactly one aggregate output for each participating input
family, including header-only outputs, and no output for an absent family.
Provenance configuration must equal the reconstructed manifest summary; output
references and inventory agree in both directions. Wrong reference, group/window
binding, explicit correspondence, statistics, required output or family lineage
fails. Unmapped external inputs remain partial; mapped missing/invalid files
fail. Failed-run outputs receive strict/integrity checks, but incomplete outputs
and scientific reconstruction are not required for a failed execution.

```bash
mania artifacts validate aggregate_run --scope replica_aggregation \
  --input-artifact-path input:replica_aggregation_manifest=replica_aggregation_manifest.json \
  --input-artifact-path input:protein:0001=replica1/protein_edges_by_window_canonical.csv
```

Repeat canonical mappings for every manifest file and participating family.
The complete synthetic acceptance run passes with `complete=true` and zero
unknown current roles. Technical validation does not decide Stage 32 exclusions.

## Current status

Stage 25 and Stage 26 are complete. Stage 27.C integrates physical-time
preprocessing and temporal artifact validation; Stage 27 is complete.
Stage 28 is complete; Stage 29 protein-lipid / protein-glycan dynamic layers are next. FastAPI remains postponed.

## Historical Stage 25.F milestone status

The following preserves the acceptance context before Stage 25.G. Current
Dataset validation additions are described in the Stage 26.C section below.

Stage 25.D.1 integrity/reference readers and API are implemented. Stage 25.D.2
existing-validator coordination, unified Python API, and CLI are implemented.
Stage 25.D is complete. Stage 25.E observation-only PBC audit and runtime metadata
is complete. Stage 25.F reproducibility documentation and FAIR² bridge is complete.
Stage 25.G final technical-hardening acceptance is next. Stage 25 as a whole
remains incomplete. FastAPI remains postponed.

## Purpose and boundary

D.1 checks technical integrity and cross-artifact consistency:

- technical metadata parses as the supported contract;
- provenance references correspond to inventory outputs;
- files exist and are regular files;
- exact byte sizes match;
- SHA256 matches when declared;
- run IDs, workflows, inventory locations, and conditions are consistent.

A passing technical result does not certify scientific acceptance. D.1 makes no
decisions about PBC correctness, contact definitions, contact lifetime semantics,
replica aggregation, or Dataset v1.0 scientific approval. A failed scientific run
can have technically consistent metadata and retained artifacts that pass D.1.

D.1 neither calls nor duplicates existing CSV, graph, manifest, Stage 20, Rg,
contacts, diagnostics, PCA, clustering, or temporal RIN validators. Scientific
content can pass these integrity checks even when it would fail a specialized
validator. D.2 coordinates the existing validators after D.1 succeeds for each
applicable artifact, as described below.

## Unified Python API

```python
from pathlib import Path
from mania.validation import validate_run_artifacts

report = validate_run_artifacts(
    Path("out"),
    scope="preprocessing",
)
payload = report.to_dict()
```

The scope is required and selects the same exact metadata layouts as D.1 below.
`run_root` must be an exact native `Path`. Optional `input_artifact_paths` is an
explicit artifact-ID to local `Path` mapping passed unchanged to D.1. No local
input path is guessed, even when a file exists under the portable inventory path.
Outputs resolve only as `run_root / entry.path`. Validation is read-only and
uses no directory discovery, clock, Git, network, or scientific runtime.

| Unified status | Meaning | CLI exit |
| --- | --- | --- |
| `passed` | Integrity passed and every applicable specialized check passed. | 0 |
| `partial` | No technical errors, but unresolved inputs or unknown roles leave validation incomplete. | 0 |
| `failed` | Integrity, an existing specialized check, or a coordinator contract check failed. | 1 |

`report.passed` means no technical validation errors and is true for partial
reports too. `report.complete` is true **only** for unified status `passed`.
Use `report.status` to distinguish all three outcomes. The embedded D.1 report
retains its original `complete` semantics described under integrity reports below.

**Future publication gate:** normal validation retains `passed -> exit 0`,
`partial -> exit 0`, and `failed -> exit 1`. Exit 0 alone is insufficient for
publication-style technical acceptance. Stage 25.G must require both
`report.status == "passed"` and `report.complete is True` (JSON `complete == true`).
Stage 25.F documents this requirement without changing CLI behavior or adding
`--require-complete`. Complete technical validation still does not establish
scientific acceptance or publication readiness. See the
[reproducibility guide](reproducibility.md) for explicit input mapping and interpretation.

## CLI

```bash
mania artifacts validate out --scope preprocessing
mania artifacts validate out --scope preprocessing \
  --input-artifact-path \
  input:condition:0001:trajectory:0001=source/trajectory.xtc
mania artifacts validate out --scope analysis
```

Repeat `--input-artifact-path ARTIFACT_ID=PATH` for multiple distinct input IDs.
The parser splits at the first `=`; both sides must be non-empty. Duplicate IDs
and syntax errors return argparse exit 2. Unknown input IDs are validation errors.
Ordinary validation prints exactly one JSON line, with sorted keys, to stdout
and nothing to stderr. Partial returns exit 0; failed returns exit 1. Unexpected
internal failures return exit 1 with `Artifact validation failed:` on stderr,
without exception details or traceback. There is no auto-scope, checksum, strict,
require-complete, scientific, publication, or skip-validator option.

## Existing-validator coordination and role audit

D.2 calls `validate_run_artifact_integrity` exactly once, then rereads the inventory
with `read_artifact_inventory`. Inventory and generic provenance use D.1 and never
receive synthetic inventory entries. Stage 26.C additionally reconstructs optional
preprocessing Dataset context from provenance and verifies its parameter-table
lineage. E.2 runtime/PBC artifacts have explicit inventory
entries and strict reader dispatch. An unreadable inventory or changed artifact
identities prevents dispatch. Missing/nonregular files, size mismatch, declared checksum
mismatch, and checksum read failures produce `skipped_integrity_failure` records
without duplicate specialized errors. Matching size permits validation in `none`
mode. In `sha256` mode the declared checksum must also match first.

Dispatch uses the following explicit roles and accepted contracts, with static
imports and no metadata-selected callables, plugins, or file-extension discovery.
The regression test derives the emitted roles from both current inventory adapters
using synthetic retained objects and requires exact policy coverage.

| Scope and roles | Existing delegated validators |
| --- | --- |
| Preprocessing `graph_nodes` + `graph_edges`; `reference_nodes` + `reference_edges` | `validate_preprocessing_graph_csvs`, once per pair |
| Preprocessing `graph_json`, `reference_graph`; analysis `analysis_graph` | `validate_graph_json`, with `expected_condition` when supplied |
| Preprocessing `rg_timeseries` | `validate_rg_timeseries_csv` |
| Preprocessing `contact_edges` | `validate_contact_edges_csv` |
| Preprocessing `contacts_perframe` | `validate_contacts_perframe_csv` (older optional export contract) |
| Both scopes `residue_table`, `protein_contact_edges`; preprocessing `protein_contacts_perframe`; analysis `contacts_perframe` | `validate_csv_artifact_schema` with Stage 20 `RESIDUE_TABLE_COLUMNS`, `PROTEIN_CONTACT_EDGE_COLUMNS`, `PROTEIN_CONTACT_PERFRAME_COLUMNS` respectively; `validate_condition_column` when condition-scoped |
| Analysis `analysis_centrality`, `analysis_communities`, `analysis_region_enrichment`, `analysis_temporal_rin`, `analysis_conformation_pca`, `analysis_conformation_labels` | `validate_csv_artifact_schema` with the corresponding exported `STATIC_RIN_METRICS_COLUMNS`, `STATIC_RIN_COMMUNITIES_COLUMNS`, `STATIC_RIN_REGION_ENRICHMENT_COLUMNS`, `TEMPORAL_RIN_METRICS_COLUMNS`, `CONFORMATION_PCA_COLUMNS`, `CONFORMATION_LABELS_COLUMNS`; `validate_condition_column` when condition-scoped |
| Both scopes `runtime_metadata` | `read_runtime_metadata`, with scope and canonical metadata path checks |
| Preprocessing `dataset_parameter_table` | `read_dataset_parameter_table_csv`, then exact context/spec cross-check |
| Preprocessing `pbc_audit` | `read_pbc_audit`, requiring `pbc_audit.json` |
| Analysis `analysis_comparison`, `analysis_stats` | `validate_csv_artifact_schema` with `STATIC_RIN_COMPARISON_COLUMNS`, `STATIC_RIN_STATS_COLUMNS`; no forced per-condition check |

Stage 20 has no matching standalone public row validator; its existing exported
column constants are used by the generic validator. The older optional contact
validator does **not** match Stage 20 per-frame tables. Analysis producers have
writer/in-memory checks, not additional reusable on-disk scientific validators.
D.2 does not copy their assertions, parse CSV/graph content itself, or add
centrality/community/PCA/clustering/temporal calculations or row semantics.

The following roles are explicitly integrity-only (`not_applicable`):

- Preprocessing: `input_manifest`, `condition_topology`, `condition_trajectory`,
  `condition_reference_structure`, `edge_semantics`, `residue_library`,
  `preprocessing_manifest`, `graph_diagnostics_report`, `reference_comparison_report`.
- Analysis: `edge_semantics`, `residue_library`, `preprocessing_manifest`,
  `analysis_manifest` (`analysis/extended_metrics.json`).

These source, manifest, and report types have no matching public specialized
validator in this scope. `validate_global_features` is a legacy manifest contract
that does not match `mania_manifest.json` or `extended_metrics.json`; it is not
called. Source MD files remain integrity-only even when mapped. Unmapped known
raw inputs are `not_applicable` here and partial in D.1. Unmapped recognized
analysis tables are `not_resolved` here. Unknown future roles are `unsupported`,
with a warning and partial status if no other error exists. Current coverage is
16 specialized + 9 integrity-only preprocessing roles, and 13 specialized + 4
integrity-only analysis roles; zero unsupported current roles.

Runtime metadata reconstructs the recorded environment and performance through
its strict reader. Preprocessing requires scope `preprocessing` and path
`runtime_metadata.json`; analysis requires scope `analysis` and path
`analysis/runtime_metadata.json`. Validation does not compare recorded versions
to the current machine or recollect the original environment.

PBC audits use a strict reader that rejects claims of internal minimum-image
correction or any scientific status other than `unresolved`. PBC audit scientific
status `unresolved` can still be technically valid: unavailable, partial and invalid
box metadata are observations, not scientific failures or warnings. Technical
validation does not approve the unresolved scientific PBC protocol. The PBC role
is supported only for preprocessing. No coordinates or trajectory frames are read.

Graph CSV pairs are selected only from inventory roles, with matching direction
and condition. Exactly one nodes and one edges entry must be declared in each
participating group; missing or ambiguous membership is a coordinator contract
error. Both files must pass integrity before the single pair invocation. If a
member fails integrity, resolved members are skipped; unmapped members retain
`not_resolved`. If only input resolution blocks the pair, both records are
`not_resolved`. Invalid membership also preserves each member's integrity gate.
The validator owns pair consistency, with no duplicated parsing.

## Unified report records

Frozen `SpecializedArtifactValidationRecord`, `UnifiedArtifactValidationIssue`,
and `UnifiedArtifactValidationReport` expose JSON-safe `to_dict()` results.
Schema is `mania.unified_artifact_validation.v0.1`; kind is
`mania_unified_artifact_validation`. The report contains the unchanged integrity
report, portable artifact/check records, and additional coordinator issues.
Root error/warning counts include D.1 plus coordinator issues; root `issues`
contains only the additional issues, avoiding copies of the embedded diagnostics.

Records follow inventory order. Generic schema and condition checks have separate
records naming their public functions, in that order; the condition check runs
only after schema success. Each grouped check supplies one record per member.
Thus specialized validation/passed/failed counts count artifact/check records,
including both pair members, rather than function invocations. Counts exclude
not-applicable, unresolved, skipped, and unsupported records. Unsupported count
counts unknown-role records.

Exactly one normalized error issue is added per failed invocation, including a
failed pair invocation. Its message is `Existing specialized artifact validation
failed.` The issue identifies the artifact, portable path, condition, and validator;
the record also names the role. `issue_count` is the existing issue collection's
length when safely available, otherwise 1. Raw result objects, local paths, and
validator exception messages are never serialized. Expected public validation and
file-read failures become reports; unexpected programming errors propagate to the
Python caller. Validation neither locks files nor claims an atomic snapshot.

A technically passed report does not certify PBC correctness, contact definitions,
lifetime definitions, aggregation semantics, Dataset v1.0 scientific approval,
publication readiness, or scientific conclusions.

## Strict disk readers

```python
from mania.artifact_inventory_io import (
    ArtifactInventoryReadError,
    read_artifact_inventory,
)
from mania.run_provenance_io import RunProvenanceReadError, read_run_provenance

inventory = read_artifact_inventory("out/artifact_inventory.json")
provenance = read_run_provenance("out/run_provenance.json")
```

Readers accept a non-empty string or `Path` identifying an existing regular file.
They read UTF-8 JSON objects with the exact supported schema version and kind.
Missing or extra contract fields, duplicate JSON keys, non-finite JSON constants,
invalid arrays/nested values, and inconsistent inventory counts are rejected.
Nullable fields and empty arrays must be present as emitted by `to_dict()`.
Resolved configuration retains its caller-defined JSON keys and values.

Existing constructors enforce portable paths, unique IDs/paths, checksum-mode
consistency, sampling constraints, and provenance ordering. Software identity
field validation occurs in the reader because that existing dataclass has no
constructor validation. The stored identity is preserved without calling Git or
`get_software_identity()`. Timestamp strings must be timezone-aware ISO 8601;
the existing provenance constructor normalizes them to UTC and serialization
uses the accepted UTC microsecond representation. No current clock is read.

Completed and failed provenance round-trip through the same reader. Readers
preserve inventory, condition, sampling, reference, issue, and command-token
order. Neither reader modifies the file or discovers other files. Expected read
failures raise the corresponding `ValueError` subclass with fixed messages and
no local paths or underlying exception representations. Schemas and writers are
unchanged; no schema migration framework is introduced.

## Integrity API and exact layouts

```python
from pathlib import Path
from mania.validation import validate_run_artifact_integrity

report = validate_run_artifact_integrity(Path("out"), scope="preprocessing")
payload = report.to_dict()

analysis_report = validate_run_artifact_integrity(Path("out"), scope="analysis")
```

`run_root` must be an exact native `Path`, and scope must be supplied explicitly.
There is no auto-detection or alternate-file search.

| Scope | Provenance | Inventory |
| --- | --- | --- |
| `preprocessing` | `run_provenance.json` | `artifact_inventory.json` |
| `analysis` | `analysis/run_provenance.json` | `analysis/artifact_inventory.json` |

All paths in this table and in reports are portable paths relative to `run_root`.
An output resolves only as `run_root / entry.path`. No `Path.resolve()`, directory
enumeration, basename matching, environment lookup, or fallback convention is
used. Unrelated files are ignored. As in the accepted inventory builder, a symlink
to a regular file can be inspected without resolving or serializing its target.

The validator reads both technical metadata files independently. Missing,
unreadable, or malformed metadata yields `provenance_read_error` or
`inventory_read_error` and a failed report rather than an ordinary validation
exception. If inventory loaded, its ordinary artifacts can still be checked;
cross-record checks require both models. Available provenance supplies the report
run ID/workflow, with inventory as fallback. Unavailable fields are null. Invalid
API argument types or scope raise `ValueError`.

Provenance must contain exactly one `artifact_inventory` reference at the scope's
expected path. Every other provenance reference must match an inventory output
path; D.1 does not require every inventory output to appear in provenance.
Non-null artifact conditions must occur verbatim in provenance conditions.

## External input portability

Stage 25.C deliberately omits execution-local input paths. An inventory path such
as `inputs/conditions/0001/trajectories/0001/trajectory.xtc` is a virtual lineage
identifier, not necessarily a file below the run directory. D.1 never guesses its
local location, even if a file happens to exist at that portable path.

External revalidation requires an explicit `artifact_id -> local Path` mapping:

```python
report = validate_run_artifact_integrity(
    Path("out"),
    scope="preprocessing",
    input_artifact_paths={
        "input:condition:0001:trajectory:0001": Path("source/trajectory.xtc"),
    },
)
```

Keys must be strings identifying input entries in that inventory. Unknown IDs,
including output IDs, yield `unknown_input_artifact_mapping`. Values must be exact
native `Path` objects and never enter report serialization. A mapped input gets
the same regular-file, size, and declared-checksum checks as an output.

An unmapped input has `resolution_status="not_resolved"`, null existence/size/
match observations, `sha256_checked=False`, and `sha256_matches=None`. It is not
reported as missing or invalid. One aggregate `external_inputs_not_resolved`
warning contains the unresolved count; there is no warning per trajectory.

## Deterministic integrity reports (D.1)

Frozen `ArtifactSetValidationIssue`, `ArtifactSetValidationRecord`, and
`ArtifactSetValidationReport` models expose independent JSON-safe `to_dict()`
results in fixed key order. Artifact records follow inventory order; issues follow
metadata reads, mapping checks, reference checks, artifact checks in inventory
order, and finally the aggregate unresolved warning. No local mapping values,
tracebacks, or underlying exception text are serialized.

| Status | Meaning |
| --- | --- |
| `failed` | At least one error issue exists. |
| `partial` | No errors, but at least one external input is unresolved. |
| `passed` | No errors and all inventory artifacts are resolved. |

The boolean `passed` means **no technical error issues**, so it is also true for a
partial report. `complete` means inventory was readable and no ordinary inventory
artifact remains unresolved; it does not mean all checks passed. Missing mapped
files are resolved locations with failed existence checks. Counts expose total
records, resolved records, unresolved inputs, errors, and warnings. Metadata
files are validated separately and never receive synthetic artifact records.
Forbidden self/provenance entries in a corrupt inventory produce errors and are
excluded from ordinary records and checksum reads.

Artifact errors distinguish `artifact_missing`, `artifact_not_file`,
`artifact_size_mismatch`, `artifact_checksum_error`, and
`artifact_checksum_mismatch`. An OS failure obtaining metadata yields
`artifact_stat_error`: existence cannot be confirmed (`exists=False`), and size
observations remain null. `sha256_checked` records a checksum attempt;
`sha256_matches=None` means verification was not applicable or did not finish.

Entries with `sha256=None` never have their content opened for checksum checks.
Declared hashes use the accepted bounded `stream_file_sha256` helper, including
its observed-file-mutation checks. Validation does not lock the filesystem or
claim an atomic snapshot of the whole run. It never changes checksum mode or
adds a checksum CLI switch.

## Acyclic metadata

```text
run provenance -> portable inventory reference -> artifact records
```

Inventory excludes itself and its corresponding provenance. The inventory model
continues to reject its own path and reserved role, and D.1 also protects the
actual expected inventory location if a corrupt root declares a different path.
The latter yields `inventory_self_reference`; a reverse provenance entry yields
`provenance_inventory_cycle`. No reciprocal checksum loop is required or created.
A portable provenance-to-inventory reference is sufficient.

## FAIR² publication boundary

An inventoried XTC, TPR, DCD, PSF, PDB, GRO, or other source MD file records source
lineage. It is not automatically part of the published Dataset v1.0. Inventory
and validation reports introduce no publication-membership field or inference.

The current FAIR² plan still assumes publication of derived dynRIN resources
rather than raw trajectories unless the dataset contract is changed later by the
authors. Publication membership belongs to the future FAIR² dataset package.

## Invariants and next step

No self-hash, no provenance/inventory checksum cycle, no blind scans, and the
single checksum contract `{none,sha256}` remain unchanged. Validation verifies
SHA256 exactly when declared and introduces no checksum flags. Raw input inventory
is lineage only, not publication membership. Existing readers, schemas, scientific
validators, calculations, and scientific artifacts remain unchanged.

Stage 25.D and Stage 25.E are complete. Stage 25.F reproducibility documentation
and FAIR² bridge is complete. Stage 25.G final technical-hardening acceptance is
complete; Stage 25 is complete. Stage 26 is complete; Stage 27.C physical-time
integration is accepted and Stage 27 is complete. The scientific
PBC protocol remains unresolved, no internal minimum-image correction is applied,
and FastAPI remains postponed.

## Stage 26.C — Dataset context and table consistency

For preprocessing, optional `resolved_configuration.dataset_context` is strictly
reconstructed as `PreprocessingDatasetContext`. Schema/kind, nested specs, binding
sources, non-empty ordered bindings, unique execution conditions and replica keys,
and scientific-condition consistency must validate. Binding conditions must be
an ordered subset of provenance execution conditions. Malformed context yields
`dataset_context_invalid`; absent context remains valid for legacy runs.

Context with `parameter_table` or `inline_and_parameter_table` sources requires
exactly one `dataset_parameter_table` input, CSV format and null condition.
Conversely, declaring that role without table-backed context fails. This gives a
portable `dataset_parameter_table_lineage_mismatch` technical error.

The table role is specialized only for preprocessing. When mapped and permitted
by the existing integrity gate, validation calls the strict accepted
`read_dataset_parameter_table_csv` reader. It locates every table-backed binding
by exact `(dataset_id, system_id, trajectory_id, replica_id)` and requires full
Dataset spec equality. Repeated conditions and unused rows are valid; condition
is never a lookup key. Missing rows, malformed tables, and changed requested or
identity fields fail technical validation, even for same-size changes in checksum
mode `none`. Semantic checking is independent of optional SHA256. Diagnostics
contain no local mapped path.

An unresolved table receives specialized `not_resolved` and keeps overall status
`partial` under existing semantics. Complete validation must explicitly map every
input, including:

```bash
mania artifacts validate out --scope preprocessing \
  --input-artifact-path input:dataset_parameter_table=source/parameters.csv
```

Add mappings for the manifest, topology, trajectories, and every other inventoried
input. Require both `report.status == "passed"` and `report.complete is True` for
complete technical acceptance. Ordinary CLI exit behavior is unchanged. This
performs no trajectory access, frame/window calculation, condition inference,
scientific validation extension, or analysis Dataset-context propagation.

## Stage 27.C — temporal execution consistency

Preprocessing role `temporal_execution` delegates to
`read_preprocessing_temporal_execution`. Its strict nested reconstruction rejects
failed plans, malformed sampling/windows, or Dataset request mismatches. No
trajectory is opened and neither accepted planner is rerun. The existing integrity
gate precedes this specialized validation. There are 16 specialized and nine
integrity-only preprocessing roles, with no unsupported current role. Analysis
has no temporal role in Stage 27.

A completed Dataset-aware provenance requires exactly one output/reference for
`temporal_execution.json`; a legacy run requires neither. The output ID is
`output:temporal_execution`, format `json`, and condition `null`. Missing/reverse
lineage fails with `temporal_execution_lineage_mismatch`. Strictly read bindings
must match context in order by execution condition and full Dataset specification.
This uses the Stage 26 requested context unchanged. Scientific condition alone
is never a Dataset identity lookup.

When valid temporal and PBC artifacts coexist, shared execution conditions must
have equal PBC sampled counts and temporal selected sample counts. A mismatch
yields `temporal_execution_pbc_count_mismatch`. Scientific PBC status `unresolved`
remains technically valid. Covered failed scientific runs need no successful
temporal output; missing temporal evidence after completed science fails the gate.
Complete validation still requires explicit mappings for every external input,
including a used Dataset table, and both status `passed` and `complete: true`.
See the [execution contract](physical_time_execution_contract.md).

## Stage 28.D — protein-edge source validation

Preprocessing role `protein_edges_by_window_source` delegates once to
`read_dataset_protein_edge_window_csv` after the existing size/SHA256 integrity
gate. The fixed ID/path are `output:protein_edges_by_window_source` and
`protein_edges_by_window_source.csv`, with CSV format and null condition. There
are now 17 specialized and nine integrity-only preprocessing roles; unsupported
current roles remain zero. No analysis role is added.

A completed run requires exactly one source output and one matching provenance
reference only when recorded `resolved_configuration.dataset_context` exists,
`include_contacts` is true, and `contact_detection_options.contact_selection` is
`protein`. Disabled and non-protein configurations permit absence. Failed runs
permit absence even after successful temporal writing. Declared source output
requires Dataset context, temporal output/reference, and one matching source
reference. Reverse reference/inventory mismatches, duplicates, wrong role metadata,
and a known source table in legacy execution fail technical validation with
`protein_edge_window_lineage_mismatch`. No required-artifact rule is inferred
from filenames alone.

The strict source reader owns all CSV structure, sparse positive-row, occupancy,
edge-weight, lifetime, uniqueness, and ordering checks. Cross-checks use retained
models after all specialized reads, independent of inventory order. Every row maps
by `(dataset_id, system_id, trajectory_id, replica_id)` to exactly one temporal
binding already checked against requested Dataset context. `variant_id`, `engine`,
`condition` including null, and `disulfide_state` must agree exactly. Condition is
never an identity lookup key.

The matched `(window_id, window_index)` must have identical requested start/end,
right-endpoint inclusion, requested/resolved/missing counts, and coverage. Effective
start/end use the accepted `float(Decimal(str(actual_ps)) / Decimal("1000"))` in an
independent Decimal context. Mismatches yield `protein_edge_window_context_mismatch`.
No trajectory or contact/episode recalculation occurs. A zero-edge window needs no
row, and a fully header-only source CSV passes when otherwise valid.

Requested configuration, resolved temporal execution, and derived science remain
separate. Complete acceptance requires all external input mappings, including a
used Dataset parameter table, `status == "passed"`, and `complete is True`.
Technical validation makes no canonical mapping or release claim; the source
artifact remains pre-canonical until Stage 30 mapping is applied and validated.
