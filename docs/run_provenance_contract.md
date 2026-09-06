# MANIA Run-Provenance Contract

## Status and purpose

Stage 25.B.1 is implemented: the contract and validated in-memory model are
available through `mania.run_provenance`. Stage 25.B.2 implements the in-memory
preprocessing sampling adapter described below. Stage 25.B.3a implements automatic
completed preprocessing file emission. Stage 25.B.3b failed-run emission, analysis
linkage, and final acceptance remain planned; Stage 25.B as a whole is incomplete.

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

Run provenance is additive and does not replace these records. Later integration
may link them through portable artifact references. Existing Stage 20–24 schemas,
scientific rows, calculation semantics, and CLI behavior remain unchanged.

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
preprocessing emission below. Failed-run emission and analysis linkage remain
Stage 25.B.3b. Checksums and the full artifact inventory remain Stage 25.C.

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
and write failures as described below. Failed scientific workflow capture and
failed-run emission remain deferred to Stage 25.B.3b. Status is not inferred
from the issue list.

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
runtime command. Stage 25.C and Stage 25.F will provide the stronger input
inventory and publication bridge.

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
are retained and no partial passport is published. Earlier scientific failures,
argument parsing failures, and invalid options retain their existing behavior
and emit no passport. Failed-run emission and analysis provenance remain deferred
to Stage 25.B.3b; existing manifests and scientific behavior remain unchanged.

`run_provenance.json` records the execution passport; existing `RunMeta` records
export run metadata, `mania_manifest.json` describes preprocessing artifacts,
and `extended_metrics.json` describes analysis artifacts. None replaces another.
No backlinks or changes to the existing manifests are introduced.

## Explicit non-goals

No failed-run or analysis provenance, checksum, environment inventory, runtime
performance metrics, PBC audit, PBC-aware calculation, sampling change, contact
or RIN change, lifetime, aggregation, FAIR² package generation, FastAPI, or WANIA
change is implemented by Stage 25.B.3a.
