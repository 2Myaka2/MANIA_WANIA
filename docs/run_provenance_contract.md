# MANIA Run-Provenance Contract

## Status and purpose

Stage 25.B.1 is implemented: the contract and validated in-memory model are
available through `mania.run_provenance`. Stage 25.B.2 implements the in-memory
preprocessing sampling adapter described below. Stage 25.B.3a implements automatic
completed preprocessing file emission; Stage 25.B.3b implements failed preprocessing
emission. Stage 25.B.3c implements completed and failed analysis provenance.
Stage 25.B and Stage 25.C input/output artifact inventory and opt-in checksums
are complete. Stage 25.D unified artifact validation and Stage 25.E observation-only
PBC/runtime metadata are complete. Stage 25.F reproducibility documentation and
FAIR² bridge is complete. Stage 25.G final technical-hardening acceptance is next.
Stage 25 as a whole remains incomplete.

`RunProvenance` is the in-memory final-run passport for one MANIA execution.
The caller supplies identity, timing, command tokens, resolved configuration,
conditions, observations, references, and issues. Construction validates these
values; it does not collect runtime metadata or perform scientific computation.
All six public dataclasses are frozen and expose `to_dict()`. Invalid input
raises `ValueError`.

## Relationship to existing metadata

- `RunMeta` remains unchanged in `src/mania/export/run_meta.py`.
- `mania_manifest.json` remains the preprocessing artifact manifest.
- `extended_metrics.json` remains the analysis manifest.

Run provenance is additive and does not replace these records. Lightweight
references can point to existing manifests; the manifests have no backlinks.
Existing Stage 20–24 schemas, scientific rows, calculation semantics, and CLI
behavior remain unchanged.

The [Stage 25.D.1 integrity/reference API](unified_artifact_validation.md) checks
the existing portable provenance-to-inventory reference. The appropriate path
is `artifact_inventory.json` for preprocessing and
`analysis/artifact_inventory.json` for analysis. A portable reference is
sufficient: provenance does not hash inventory, and inventory excludes its
corresponding provenance. No reciprocal checksum loop is required.

Software identity remains the run's software-source identity. Dataset release
metadata, dataset version/DOI, consumer repository URL and reference status are
outside this contract; they do not extend SoftwareIdentity. The
[software release reference](software_release_reference.md) describes how a
consumer refreshes its own record from actual generation provenance.

## Stage 25.E.2 — completed-run technical references

Completed preprocessing appends these portable references, in order, after the
existing scientific references:

1. `runtime_metadata` → `runtime_metadata.json`;
2. `pbc_audit` → `pbc_audit.json`;
3. `artifact_inventory` → `artifact_inventory.json`.

Completed analysis appends `runtime_metadata` → `analysis/runtime_metadata.json`,
then `artifact_inventory` → `analysis/artifact_inventory.json`. Analysis emits
no PBC audit. Each reference requires a successful write in the current run;
stale files and unsuccessful writes are never claimed.

Scientific execution ends at the existing Stage 25.B timestamp. Runtime duration
reuses that timestamp and the existing start, without another clock read. Runtime
and preprocessing PBC artifacts are written first, then inventoried, then referenced
by provenance. There is no schema change, provenance hash, inventory self-hash,
or reciprocal checksum loop. Scientific manifests remain unchanged.

Runtime/PBC technical failure after successful science retains scientific outputs
and still attempts inventory and completed provenance with successful technical
references only; it suppresses the successful summary and returns exit 1.
Failed scientific runs preserve the existing Stage 25.B/C failure boundary and
do not automatically persist E.2 runtime/PBC artifacts.

## Public API and root contract

```python
from mania.run_provenance import (
    ConditionSamplingProvenance,
    EffectiveFrameSampling,
    PortableArtifactReference,
    RequestedFrameSampling,
    RunProvenance,
    RunProvenanceIssue,
)
```

The module also exports the three constants and three literal aliases below
through `__all__`; these names are not re-exported from `mania.__init__`.

- `RUN_PROVENANCE_SCHEMA_VERSION = "mania.run_provenance.v0.1"`
- `RUN_PROVENANCE_KIND = "mania_run_provenance"`
- `RUN_PROVENANCE_FILENAME = "run_provenance.json"`
- `RunProvenanceStatus = Literal["completed", "failed"]`
- `RunProvenanceIssueSeverity = Literal["warning", "error"]`
- `TimeSpacingStatus = Literal["uniform", "non_uniform", "unavailable"]`

The provenance schema version is independent of the general `SCHEMA_VERSION`
and the package version. `to_dict()` returns exactly these root keys in order:

| Field | Meaning and constraints |
| --- | --- |
| `schema_version` | Fixed provenance schema constant; not a constructor argument. |
| `kind` | Fixed provenance kind constant; not a constructor argument. |
| `run_id` | Caller-supplied non-empty stripped run identifier; never generated. |
| `workflow` | Caller-supplied non-empty stripped workflow identifier. |
| `status` | Final `completed` or `failed` status. |
| `started_at_utc` | Caller-supplied timezone-aware start datetime. |
| `ended_at_utc` | Caller-supplied timezone-aware end datetime, not earlier than start. |
| `software_identity` | Supplied immutable Stage 25.A `SoftwareIdentity` snapshot, serialized with its existing `to_dict()`. |
| `command` | Non-empty tuple of non-empty string argument tokens, preserved verbatim. |
| `resolved_configuration` | Defensive, recursively ordered, immutable snapshot of JSON-compatible configuration. |
| `conditions` | Tuple of unique non-empty stripped condition names; may be empty. |
| `sampling_by_condition` | Tuple of `ConditionSamplingProvenance`, default empty; condition names must be unique and present in `conditions`. |
| `artifact_references` | Tuple of `PortableArtifactReference`, default empty; `(role, path)` pairs must be unique. |
| `issues` | Tuple of `RunProvenanceIssue`, default empty; any supplied issue condition must be present in `conditions`. |

Sampling records need not cover every condition; artifact references are optional.
The model does not call `get_software_identity()` or execute Git. Software identity
retains its existing fields: `software_name`, `distribution_name`, `version`,
`commit_sha`, `commit_source`, and `working_tree_status`. Unavailable Git metadata
retains its existing `None`/`unavailable` representation.

Serialization preserves tuple order as JSON arrays and unavailable values as
JSON null. Nested provenance records use their own `to_dict()` methods. Every
call returns fresh dictionaries and lists; no datetime, path object, mapping
proxy, tuple, set, bytes, NaN, or infinity remains in the output.
`json.dumps(payload, allow_nan=False)` succeeds. Command tokens are never joined
into a shell command string.

## Sampling contract

Requested sampling describes what the user requested. Effective sampling
describes what was actually observed. Stage 25.B.1 only stores supplied
observations; collection and the observation algorithm belong to Stage 25.B.2.
There is no scientific sampling behavior change or inference of missing frames.

`RequestedFrameSampling.to_dict()` contains these fields in declaration order:

| Field | Constraint |
| --- | --- |
| `frame_start` | Non-negative integer, default `0`. |
| `frame_stop` | Non-negative integer greater than start, or `None` (default). |
| `frame_stride` | Positive integer, default `1`. |
| `max_frames` | Positive integer or `None` (default). |

`EffectiveFrameSampling.to_dict()` contains these fields in declaration order:

| Field | Meaning and constraint |
| --- | --- |
| `source_frame_count` | Available source count, a non-negative integer or `None`. |
| `sampled_frame_count` | Required non-negative integer, at most the available source count. |
| `first_source_frame_index` | First observed source index, non-negative integer or `None`. |
| `last_source_frame_index` | Last observed source index, non-negative integer or `None`. |
| `first_time_ps` | First observed time in ps, finite and non-negative or `None`. |
| `last_time_ps` | Last observed time in ps, finite and non-negative or `None`. |
| `time_spacing_status` | `uniform`, `non_uniform`, or `unavailable`. |
| `observed_time_spacing_ps` | Supplied uniform spacing in ps, finite and positive or `None`. |

Booleans are rejected as integers and as time values. For zero sampled frames,
both indexes, both endpoint times, and observed spacing must be `None`, with
spacing status `unavailable`. For a positive count, both indexes must be present
and first must not exceed last. Endpoint times may be independently unavailable;
when both are available, first must not exceed last.

- `uniform`: the caller observed uniform spacing; requires at least two frames
  and a positive `observed_time_spacing_ps`.
- `non_uniform`: the caller observed non-uniform spacing; requires at least two
  frames and `observed_time_spacing_ps = None`.
- `unavailable`: spacing was unavailable; requires `observed_time_spacing_ps = None`.
  Zero-frame and one-frame observations must use this status.

The root model defines no numerical tolerance for uniformity; the Stage 25.B.2
adapter defines the observation algorithm below. No endpoint, count, or spacing
is calculated from other fields in the root model.

`ConditionSamplingProvenance.to_dict()` contains `condition` (a non-empty
stripped string), `requested` (a `RequestedFrameSampling` dictionary), and
`effective` (an `EffectiveFrameSampling` dictionary or null). `effective = None`
means observations were unavailable, for example when execution did not reach
sampling; the model does not infer a reason.

## Stage 25.B.2 — preprocessing sampling adapter implemented

```python
from mania.preprocessing.run_provenance import (
    PreprocessingSamplingProvenanceResult,
    collect_preprocessing_sampling_provenance,
)

# computation is an existing PreprocessingGraphWorkflowComputationResult.
sampling = collect_preprocessing_sampling_provenance(computation)
payload = sampling.to_dict()
```

This Python API copies requested sampling directly from the accepted
`PreprocessingFrameSamplingOptions` into one immutable `RequestedFrameSampling`
snapshot shared by all conditions. Effective sampling uses only frame records
already retained in preprocessing contact and Rg results, counting every
selected/attempted frame, including scientifically unsuccessful rows. An empty
condition frame tuple records zero observations; absent sources produce
`effective=None` and a warning. No missing requested frames are inferred.

When both sources exist, their source-frame indexes must agree in recorded
order. Available times are retained; two available times must agree within the
declared tolerances, with their minimum used as the symmetric deterministic
value. Index or time disagreement, invalid sources, and invalid sequences
produce error issues and `effective=None`. Index validation checks non-negative
integers, strict increase, and the existing start/stop/stride/max-frame bounds.

The existing runtime metadata helper supplies the total source trajectory frame
count when available, without reopening files or iterating over the trajectory.
Unrelated atom, residue, or segment metadata issues do not discard an available
count. Observed indexes and sampled count must fit that source count. An
unavailable count remains `None` with a warning; other effective metadata is
still collected.

Time spacing describes consecutive **selected frames**, not the source
integration timestep. Classification uses only these provenance tolerances:

- `PREPROCESSING_SAMPLING_TIME_REL_TOL = 1e-9`
- `PREPROCESSING_SAMPLING_TIME_ABS_TOL_PS = 1e-9`

Zero or one frame, or any missing sampled time, gives `"unavailable"` spacing.
With all times available, finite positive differences matching the first
difference using the declared `math.isclose` tolerances give `"uniform"`;
spacing is their deterministic arithmetic mean (`math.fsum` divided by the
number of differences). Fully available unequal spacing, including zero or
negative differences, gives `"non_uniform"` with no spacing value. Every
available time must be finite and non-negative. Values incompatible with the
root `EffectiveFrameSampling` contract, including reversed endpoint times,
produce `invalid_effective_sampling` and `effective=None`.

The frozen `PreprocessingSamplingProvenanceResult` serializes keys in order:
`sampling_by_condition`, `issues`, `passed`. Conditions follow computation order;
each receives one record. All issues use stage `"preprocessing_sampling"`
(`PREPROCESSING_SAMPLING_STAGE`). Within a condition, a source-count warning
precedes observation or validation issues. Warnings do not fail `passed`;
errors do. The result can later supply sampling records and issues to
`RunProvenance`.

The adapter produces an in-memory result only. It changes no frame selection or
scientific calculation and adds no fields to existing scientific serialization.
The adapter itself writes no file. Stage 25.B.3a uses its result for completed
preprocessing emission below. Stage 25.B.3b retains the same sampling observations
for failed runs; analysis provenance is described under Stage 25.B.3c. Checksums
and the full artifact inventory remain Stage 25.C.

## Configuration contract

Resolved configuration must be a mapping with string keys. Supported values
are null, booleans, integers, finite floats, strings, nested mappings with string
keys, and lists or tuples of supported values. Non-string keys, non-finite
floats, Path objects, datetime objects, bytes, sets, arbitrary objects, and
cyclic containers are rejected.

The private freeze/thaw implementation copies mappings into read-only mapping
proxies, sorts keys recursively, and stores input sequences as tuples. Mutating
the input or any returned payload does not affect the stored snapshot. Each
`to_dict()` call returns independent ordinary dictionaries and lists.

No config hash is calculated yet. Stage 25.B.3a integration normalizes known
path fields before constructing publication-facing provenance. Stage 25.B.1
does not infer filesystem path semantics from arbitrary strings.

## Time contract

Integration code supplies timezone-aware datetime values. The model normalizes
both to UTC and serializes them as RFC 3339 with fixed microsecond precision:
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Output uses trailing `Z`, never `+00:00`.
The model does not read the clock. Equal start and end timestamps are permitted.

## Artifact-reference boundary

`PortableArtifactReference.to_dict()` contains only `role` and `path`.
Both are non-empty stripped strings. Paths must be normalized relative portable
POSIX paths, such as `mania_manifest.json` or `analysis/extended_metrics.json`.
Absolute paths, Windows drive paths, backslashes, NUL characters, `.` or `..`
components, URI-like `://` values, and paths changed by POSIX normalization
(such as repeated separators or trailing slashes) are rejected.

No file existence check or filesystem probing occurs. Checksums, byte sizes,
row counts, media types, modification times, and the full artifact registry
belong to Stage 25.C.

## Failure boundary

Final status can be `completed` or `failed`. `RunProvenanceIssue.to_dict()`
contains `severity`, `code`, `message`, `stage`, and `condition` in that order.
Severity is `warning` or `error`; code and message are non-empty stripped
strings. Optional stage and condition default to `None` and must be non-empty
stripped strings when supplied. Tracebacks are not part of the portable model;
callers supply portable issue messages, and exception objects are not inspected.

Stage 25.B.1 represents issues only. Stage 25.B.3a handles completed-run build
and write failures as described below. Stage 25.B.3b adds emission for the eight
covered workflow-stage failures. Status is not inferred from the issue list.

## Stage 25.B.3a — completed preprocessing emission implemented

A successful `mania preprocessing run-graph-export` now automatically writes
`<output>/run_provenance.json`. There is no new CLI command or flag. The existing
`run_name` supplies the run ID; callers remain responsible for its uniqueness.
Software identity is captured exactly once after options validation and before
the first workflow stage. Start and end timestamps are recorded in UTC. The
completed builder uses Stage 25.B.2 requested/effective sampling, preserves its
warnings as root issues, and rejects sampling errors. The builder itself is
in-memory only and uses caller-supplied identity and timestamps.

The portable command is a tuple of argument tokens with token zero `mania`.
Only known path options (`--manifest`, `--output`, `--reference-nodes`,
`--reference-edges`, `--reference-graph-json`) are normalized, in both separated
and `--option=value` forms. Input values become filename-only references and
output becomes `.`; empty portable filenames are rejected. Other argument
values and order are preserved without path guessing. Runtime paths and
`sys.argv` are unchanged. This representation is not a replacement for the
runtime command. Stage 25.C provides input inventory; Stage 25.F documents the
[reproduction procedure](reproducibility.md) and consumer publication bridge.

Resolved configuration contains `manifest_name`, `output_root`, `run_name`,
`expected_condition_names`, `include_rg`, `include_contacts`,
`include_graph_export`, `include_diagnostics`, `enable_reference_comparison`,
`reference_semantics`, `reference_input_names`, `frame_sampling`,
`contact_detection_options`, `contact_computation_limits`,
`export_analysis_inputs`, `scientific_csv_exports`, `write_diagnostics_report`,
and `write_reference_comparison_report`. Input references are filename-only
(or null), output root is `.`, and scientific CSV flags are explicit after
shortcut expansion. The snapshot contains JSON values, including contact
selection and resolved expected conditions, without runtime objects, working
directory, environment, scientific results, or a config hash.

Lightweight artifact references contain only `role` and relative POSIX `path`.
They follow this order when applicable: `graph_nodes`, `graph_edges`,
`graph_json`, `preprocessing_manifest`, `rg_timeseries`, `contact_edges`,
`contacts_perframe`, `graph_diagnostics_report`, `reference_comparison_report`.
The three graph links are always present after successful export. The manifest
link is `mania_manifest.json` only when analysis-input export was requested and
passed. Scientific CSV links follow resolved export flags and successful export;
report links require their stage and report writing to be enabled and successful.
Paths come lexically from the accepted output layout, with no symlink resolution,
file existence checks, checksums, sizes, row counts, or media types. The manifest
is the lightweight anchor for Stage 20 artifacts until the Stage 25.C inventory.

`mania.run_provenance_io.write_run_provenance` writes ordered UTF-8 JSON with
two-space indentation, preserved non-ASCII text, strict finite JSON values, and
exactly one trailing newline. It creates missing output parents, writes a
same-directory temporary file, then publishes the complete file atomically.
Without overwrite, atomic publication preserves an existing target, including
one created concurrently; with overwrite, atomic replacement is used. Temporary
files are removed after writing or publication failures. Its frozen
`RunProvenanceWriteResult` reports `output_path`, `written`, `error`, and `passed`.
These local writer-result paths are never embedded in the portable payload.

Successful stdout JSON, stderr, verbose stage messages/counts, and exit code zero
remain unchanged; provenance emission is silent and adds no verbose stage. After
scientific success, provenance construction or writing failure prints one line
beginning `Run provenance build failed:` or `Run provenance write failed:` and
returns exit code 1 without the successful final summary. Scientific artifacts
are retained and no partial passport is published. Stage 25.B.3b covers earlier
workflow-stage failures below. Argument parsing failures and invalid options
emit no passport. Analysis provenance is described under Stage 25.B.3c; existing
manifests and scientific behavior remain unchanged.

`run_provenance.json` records the execution passport; existing `RunMeta` records
export run metadata, `mania_manifest.json` describes preprocessing artifacts,
and `extended_metrics.json` describes analysis artifacts. None replaces another.
No backlinks or changes to the existing manifests are introduced.

## Stage 25.B.3b — failed preprocessing emission implemented

After validated preprocessing options and the execution context exist, the
existing command attempts to write `<output>/run_provenance.json` when a covered
workflow stage fails. The public `PreprocessingRunFailureStage` literal and
`PREPROCESSING_RUN_FAILURE_STAGES` tuple define these stages in order: `plan`,
`runtime_loading`, `computation`, `graph_export`, `analysis_input_export`,
`scientific_csv_export`, `diagnostics`, and `reference_comparison`.

`build_failed_preprocessing_run_provenance` produces `status="failed"` and
workflow `preprocessing_graph_export`, preserving caller-supplied run identity,
UTC timestamps, software identity, command tokens, resolved configuration,
conditions, and artifact references. The first issue has severity `error`, code
`preprocessing_stage_failed`, the failed stage, no condition, and message
`Preprocessing workflow failed during <failure_stage>.` Sampling issues follow it;
no exception text, traceback, or raw scientific results are copied into issues.

Without a computation, each known condition receives the requested sampling,
`effective=None`, and an `effective_sampling_unavailable` warning. No zero-frame
observation is invented. Empty conditions produce no sampling entries or
condition-specific warnings. With a retained accepted computation, including a
failed computation, Stage 25.B.2 supplies observations and all sampling warnings
and errors. Sampling inconsistencies can coexist with the main workflow failure.
The builder neither recomputes frames nor inspects trajectories or files.

The CLI reuses its start-time software snapshot and captures one end timestamp:
normal success or failure calls the clock exactly twice. Known conditions come
from the accepted computation, otherwise runtime loading when available,
otherwise resolved expected conditions. Order is preserved; invalid metadata
is not silently sorted, deduplicated, or discarded. Portable commands, resolved
configuration, output root, run ID, and overwrite behavior use the same helpers
and options as completed runs.

References use the existing lightweight portable layout rules, limited to earlier
successful stages. Plan, loading, computation, and graph-export failures claim
no artifacts. An analysis-input failure retains only graph links; a scientific
CSV failure can also retain a previously exported preprocessing manifest.
Diagnostics failure additionally retains successful requested scientific CSVs.
Reference-comparison failure can retain a successfully written diagnostics
report. Disabled exports and reports are omitted. Partial outputs from the
failed stage and the provenance file itself are never claimed. No existence
checks or directory enumeration occur; checksums and full inventory remain
Stage 25.C.

Successful failed-run emission is silent: original failure stdout, stderr,
verbose messages, and exit code remain unchanged. If building fails, one safe
line begins `Failed-run provenance build failed:`; if writing fails, one begins
`Failed-run provenance write failed:`. A failed writer result uses its safe error
text; expected boundary exceptions receive fixed messages without tracebacks.
Neither replaces the original workflow failure, removes its stdout summary,
nor rolls back scientific artifacts. Existing provenance is preserved when
overwrite is false.

Parser errors, missing required arguments, invalid option combinations and
frame sampling, help, version, and other commands remain outside this boundary.
They have no validated preprocessing execution context. Completed-run provenance
build/write failures retain Stage 25.B.3a behavior. Stage 25.B.3c adds the separate
analysis boundary below and completes Stage 25.B.
`RunMeta`, `mania_manifest.json`, and `extended_metrics.json` remain unchanged
and are not replaced; no backlinks or schema changes are introduced.

## Stage 25.C.2 — preprocessing inventory linkage

When preprocessing inventory is successfully written, completed or failed root
preprocessing provenance includes one portable artifact reference with role
`artifact_inventory` and path `artifact_inventory.json`. Inventory generation
failure or unavailable complete inputs adds no such reference, even if an older
inventory file is present. Inventory excludes itself and `run_provenance.json`;
there is no checksum cycle. The provenance schema itself is unchanged. See
[artifact inventory contract](artifact_inventory_contract.md) for emission and
failure ordering.

## Stage 25.B.3c — completed and failed analysis emission implemented

The existing `mania analyze` command automatically writes
`<output>/analysis/run_provenance.json` with workflow `analysis` and final status
`completed` or `failed`. There is no new command or flag. This file is separate
from both `<output>/run_provenance.json` (preprocessing provenance) and
`<output>/analysis/extended_metrics.json` (the scientific analysis manifest).
Analysis never modifies root preprocessing provenance, including when its input
and output roots are equal. Existing manifests and `RunMeta` retain their roles.

`mania.analysis.run_provenance` provides pure completed/failed builders, lexical
artifact collection, and `analysis_run_id_from_started_at`. The run ID has format
`analysis-YYYYMMDDTHHMMSSffffffZ`, for example `analysis-20260906T120304123456Z`.
It derives only from a caller-supplied aware start timestamp normalized to UTC.
The builders consume accepted `AnalyzeRunResult` or `AnalyzeRequest` instances
and supplied execution context; they do not read clocks, inspect Git, or read
or write files. Invalid metadata raises `AnalysisRunProvenanceBuildError` with
a deterministic message without local paths or exception details.

The CLI captures one software-identity snapshot and one start timestamp after
parsing, immediately before request execution. One end timestamp covers success
or failure. Command tokens remain a tuple, with token zero normalized to `mania`.
Only `--input` and `--output` are normalized, supporting separated and equals
forms: output becomes `.`, and input becomes `.` when the actual request roots
are equal, otherwise its filename. Empty portable filenames are rejected.
Other tokens and order, `sys.argv`, and actual runtime paths are preserved.
Resolved configuration has `input_root`, `output_root`, `analysis_root`,
`conditions`, `enable_pca`, `clustering_basis`, `pca_components_for_clustering`,
and, since Stage 25.C.3, `artifact_checksum_mode`. The checksum mode is technical
execution metadata; no hashes or inventory contents are added. Explicit checksum
flag/value tokens remain in the portable command; default omission remains
omission. Roots use the same portable labels, with
`analysis_root="analysis"`; other values and condition order come from the
request. No working directory, environment, hashes, or runtime objects are added.

Analysis consumes prepared artifacts, so `sampling_by_condition` remains empty.
Upstream requested/effective sampling belongs to preprocessing provenance; no
sampling is copied or inferred from analysis tables. Completed references contain
only role and a portable POSIX path relative to the output root. In condition
result order, their roles are `analysis_graph`, `analysis_centrality`,
`analysis_communities`, `analysis_region_enrichment`, `analysis_temporal_rin`,
`analysis_conformation_pca`, and `analysis_conformation_labels`, followed by
`analysis_comparison`, `analysis_stats`, and `analysis_manifest` when available.
Repeated roles across conditions are allowed. Paths come from the existing
result without resolving symlinks, checking existence, or scanning directories;
paths outside the output root are rejected. Neither provenance file, upstream
inputs, nor richer artifact inventory fields are included.

Successful execution builds completed provenance and uses the existing atomic
writer with `result.analysis_root` and `overwrite=True`. This intentionally
replaces the latest-run passport in the current mutable analysis output directory;
it is not a history archive. Existing stdout JSON, keys, artifact list/count,
stderr, and exit code zero remain unchanged. Provenance is not added to
`AnalyzeRunResult.artifacts`, `to_summary()`, or `extended_metrics.json`.

When `run_analysis()` raises `AnalyzeError` or another existing caught exception,
failed provenance is attempted at `request.output_root / "analysis"`, also with
`overwrite=True`. Without additional Stage 25.C.3 references, it conservatively
contains no artifact references or sampling and exactly one root issue: severity
`error`, code `analysis_execution_failed`,
message `Analysis workflow failed.`, stage `analysis_execution`, condition null.
Original exception text is never stored in the passport. Partial outputs are
neither inspected nor claimed. The original `Analyze failed: <message>` stderr
line and exit code 1 are preserved, with no additional stdout.

After scientific success, metadata build/write failure reports one deterministic
line beginning `Analysis run provenance build failed:` or
`Analysis run provenance write failed:`, returns 1, and omits the success summary.
After scientific failure, the original error remains first; metadata failure adds
exactly one second line beginning `Failed analysis provenance build failed:` or
`Failed analysis provenance write failed:`, retaining exit code 1. No scientific
artifacts are rolled back, no partial passport is published, and temporary writer
files are cleaned up. Normal failures do not emit tracebacks; `BaseException`
is not caught. Request-construction failure preserves the original behavior
without inventing a request or passport. Parser errors, missing required arguments,
invalid parser-level integers, help, version, and other commands do not enter
this analysis provenance boundary.

Stage 25.C adds inventory linkage below. Stronger lineage and the publication
bridge remain planned for Stage 25.F.

## Stage 25.C.3 — analysis inventory linkage

Completed and failed builders accept optional
`additional_artifact_references: tuple[PortableArtifactReference, ...] = ()`.
Completed builders preserve scientific references first and append additional
references. Failed builders use the supplied references; omission preserves the
existing empty list. Existing model validation rejects invalid references.
No filesystem, clock, Git access, or generic provenance schema change is added.

After successful inventory writing, completed or failed analysis provenance
includes role `artifact_inventory`, path `analysis/artifact_inventory.json`.
Unavailable or failed inventory adds no reference, even if an older file exists.
After authoritative input resolution, failed runs can link an input-only inventory;
partial outputs are never claimed. Resolution failures still attempt failed
provenance without inventory. Scientific success followed by inventory failure
still attempts completed provenance without inventory, returns 1, and suppresses
the success summary. Inventory errors precede provenance meta-errors; after a
scientific failure, the original `Analyze failed:` line stays first.

The CLI retains one software identity, one start timestamp, and one end timestamp,
with the end captured before inventory work. Inventory is atomically written to
`<output>/analysis/artifact_inventory.json` before provenance; neither root
preprocessing technical file changes when input and output roots coincide.
Inventory excludes itself and both provenance files, so there is no checksum
cycle. See the [artifact inventory contract](artifact_inventory_contract.md).

## Explicit non-goals

No checksum, complete artifact inventory, environment inventory, runtime
performance metrics, PBC audit, PBC-aware calculation, sampling change, contact
or RIN change, lifetime, aggregation, FAIR² package generation, FastAPI, or WANIA
change is implemented by Stage 25.B.

## Stage 26.C — preprocessing Dataset context

Completed and failed preprocessing builders accept optional
`dataset_context: PreprocessingDatasetContext | None = None`. They add the
portable `PreprocessingDatasetContext.to_dict()` under configuration key
`dataset_context`; the on-disk location is
`resolved_configuration.dataset_context`. The key is absent for legacy runs,
never emitted as null. The generic `RunProvenance` schema is unchanged.

Bindings preserve manifest order, execution condition, binding source, exact
Dataset identity, and all requested temporal model values. Scientific condition
`None` stays `None`. Context contains no local parameter-table path, topology or
trajectory path, runtime object, or derived frame/window value.

The CLI resolves context before scientific execution. Completed runs and covered
later workflow failures retain it; binding failures produce no normal provenance
or inventory. Failed-run inventory still follows the Stage 25 authoritative-input
boundary. A used table is portable input lineage in the inventory, not a path in
Dataset context. No Dataset fields enter scientific `mania_manifest.json`, graph,
or CSV artifacts. `mania analyze` does not propagate Dataset context in Stage 26.

## Stage 27.C — requested context and temporal execution

Dataset-aware preprocessing now records a portable `temporal_execution` reference
at `temporal_execution.json` after scientific references and before runtime
metadata, PBC audit, and artifact inventory. The reference is added only after
successful atomic publication. No local path or checksum enters the reference.
`resolved_configuration.dataset_context` remains the requested Dataset contract;
the dedicated temporal artifact carries resolved sampling and window evidence.
Legacy runs add neither a temporal reference nor a planning pass.

Planning/configuration failures retain requested context in failed provenance
at the existing `computation` failure boundary, with unavailable effective
sampling and no successful temporal output. Planning still precedes science. A technical write failure after science follows
the existing best-effort completed-science metadata boundary and exits 1 without
a successful summary. The generic schema is unchanged. Analysis does not propagate
temporal execution. See the [execution contract](physical_time_execution_contract.md).
