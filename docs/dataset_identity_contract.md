# Dataset v1.0 trajectory identity — Stage 26

## Status and scope

Stage 25 is complete. Stage 26.A is implemented and accepted as an additive, independent
in-memory contract in [`dataset_identity.py`](../src/mania/dataset_identity.py).
Stage 26.B optional manifest integration and standalone parameter-table input
are accepted. Stage 26.C authoritative execution binding, technical propagation,
validation, and acceptance are implemented. Stage 26 is complete.
At the accepted Stage 26 checkpoint, the recorded boundary was:
Stage 27 physical-time sampling/window engine is next; no such engine is
implemented yet.

The [Dataset v1.0 scientific contract](dataset_v1_scientific_contract.md) records
the frozen scientific decisions for Stages 27–35. Scientific decisions being
frozen does not mean their future functionality is implemented or that Dataset
v1.0 is released. Historical Stage 25 records retain their acceptance context.

## Stage 27.A–B status

Stage 26 is complete. The accepted standalone Stage 27.A resolver consumes requested
`production_start_ns`, `production_end_ns`, and `frame_stride_ps` for production
interval and stride resolution only. See the
[physical-time sampling contract](physical_time_sampling_contract.md).
Stage 27.B is implemented: the [pure window planner](physical_time_window_contract.md)
now interprets `window_length_ns`, `window_step_ns`, and `overlap_percent` over
the accepted sampling plan. Dataset models remain unchanged.
There is no workflow integration. Stage 27 remains incomplete; Stage 27.C
workflow integration is next. Stage 26 history below is unchanged.

## Identity boundary

The existing preprocessing workflow is condition-centric. Its legacy
`condition` remains the execution condition name. Dataset identity carries a
separate scientific `condition`, which may be unresolved. A condition label
alone MUST NOT stand in for the new dataset/system/trajectory/replica identity.

`DatasetTrajectoryIdentity` declares these fields in serialization order:

| Field | Type | Meaning |
| --- | --- | --- |
| `dataset_id` | `str` | Caller-supplied dataset identifier |
| `system_id` | `str` | Caller-supplied system identifier |
| `trajectory_id` | `str` | Caller-supplied trajectory identifier |
| `variant_id` | `str` | Supplied protein/design variant identifier |
| `engine` | `DatasetEngine` | Exactly `gromacs` or `namd` after normalization |
| `condition` | `str \| None` | Required field; scientific label or explicit absence |
| `replica_id` | `str` | Caller-supplied replica identifier |
| `disulfide_state` | `str \| None` | Optional supplied design label, default `None` |

The five identifier fields MUST be actual strings. They are stripped and MUST
remain non-empty. IDs retain case; no numeric-only rule, naming convention,
cross-field derivation, or relationship is imposed. Engine input accepts case
differences and surrounding whitespace, storing exactly lowercase `gromacs` or
`namd`. Other engines MUST be rejected; there is no `other` engine.

`condition` is represented now. Final concrete NAMD condition values remain
pending scientific-team input. `None` is allowed in this new identity contract
and is serialized as JSON `null`; the field MUST be supplied even when absent
scientifically. MANIA MUST NOT invent missing labels or automatically substitute
`unknown`, `pending`, `N/A`, or guessed NORM/TUMOR labels. Supplied strings are
stripped, retain case, and MUST NOT be empty.

`disulfide_state` follows the same optional-string validation. MANIA MUST NOT
infer it from `variant_id`, require it for every NAMD system, or limit it to an
enum of `0SS`/`1SS`/`2SS`. ECD/Cys designs need not share those semantics.

`DatasetTrajectoryIdentity.replica_key` returns exactly
`(dataset_id, system_id, trajectory_id, replica_id)`, a deterministic
`tuple[str, str, str, str]`. It excludes `condition` because concrete NAMD
labels remain pending. This is an identity/reference key only. It MUST NOT be
used as a cross-engine statistical grouping key.

## Requested physical parameters

`DatasetTemporalParameters` preserves six explicit REQUESTED scientific
parameters in this order:

| Field | Unit | Validation |
| --- | --- | --- |
| `production_start_ns` | ns | At least zero |
| `production_end_ns` | ns | Greater than `production_start_ns` |
| `frame_stride_ps` | ps | Greater than zero |
| `window_length_ns` | ns | Greater than zero, at most the production duration |
| `window_step_ns` | ns | Greater than zero |
| `overlap_percent` | percent | At least zero and strictly less than 100 |

Stored values are finite floats. Booleans, NaN, and infinities MUST be rejected.
The declared interval MUST satisfy
`window_length_ns <= production_end_ns - production_start_ns`.

`window_length_ns`, `window_step_ns`, and `overlap_percent` remain three
independent, explicit requests. Stage 26.A enforces no mathematical consistency
relation between step and overlap. It does not choose or reconcile a sampling
or window policy.

Stage 26.A does not translate physical parameters into frames or windows.
There is no ps/ns conversion, source/sampled frame-index calculation, window
count, effective boundary, effective stride, expected coverage, or overlap
mechanics. Stage 27 owns operational physical-time sampling and window semantics.

## Combined specification and serialization

All three public Pydantic models use
`ConfigDict(frozen=True, extra="forbid")`. Undeclared fields are rejected.
`DatasetTrajectorySpec` accepts only `identity: DatasetTrajectoryIdentity` and
`temporal: DatasetTemporalParameters`; Pydantic also validates nested input
dictionaries into these models.

`schema_version` and `kind` are read-only properties, not constructor fields.
`DatasetTrajectorySpec.to_dict()` produces root keys in this exact order:

1. `schema_version`: `mania.dataset_trajectory_spec.v0.1`;
2. `kind`: `mania_dataset_trajectory_spec`;
3. `identity`: the identity dictionary in declaration order;
4. `temporal`: the temporal dictionary in declaration order.

Leaf `to_dict()` methods also retain declaration order and optional `None`
values. Each call returns independent JSON-safe dictionaries. `to_dict()` is
the versioned serialization boundary; ordinary Pydantic `model_dump()` on the
root contains only its two input fields. No filesystem path, environment,
clock, Git, package metadata, or runtime data is inspected or added. This
module MUST NOT import preprocessing or analysis runtime modules.

The public API is limited to:

- `DATASET_TRAJECTORY_SPEC_KIND`;
- `DATASET_TRAJECTORY_SPEC_SCHEMA_VERSION`;
- `DATASET_V1_EXPECTED_SYSTEM_COUNT = 19`;
- `DATASET_V1_EXPECTED_TRAJECTORY_COUNT = 33`;
- `DatasetEngine = Literal["gromacs", "namd"]`;
- `DatasetTemporalParameters`;
- `DatasetTrajectoryIdentity`;
- `DatasetTrajectorySpec`.

The counts describe the frozen full Dataset v1.0 composition. They do not
require partial/development collections to contain exactly 33 trajectories or
19 systems; full dataset-completeness validation belongs later. There are no
re-exports from `mania.__init__` or preprocessing in Stage 26.A.

## Backwards compatibility

Stage 26.A made no legacy manifest change and had no manifest integration.
Stage 26.B adds only the optional
`dataset_spec: DatasetTrajectorySpec | None = None` field to
`TrajectoryInputConfig`. Old manifests need no change: missing or explicit
`None` means legacy mode. Mixed legacy-only and Dataset-aware entries are valid.
Paths, `frame_time_ps`, and stripped, case-sensitive execution condition lookup
retain their existing behavior.

Nested input dictionaries contain the accepted spec constructor fields,
`identity` and `temporal`. A non-`None` Dataset scientific condition MUST exactly
equal the normalized legacy execution condition. Scientific condition `None`
is allowed, including NAMD entries with synthetic execution labels; no label
is inferred or copied from the legacy condition.

Legacy execution conditions remain unique within a manifest. Among supplied
Dataset specs, exact `replica_key` values must also be unique. Neither system,
variant, nor scientific condition alone becomes a Dataset uniqueness key.
Replicas sharing a known scientific condition may still need separate legacy
execution manifests; the standalone table permits repeated conditions.

`PreprocessingInputManifest.to_dict()` omits `dataset_spec` when absent while
preserving existing null-valued legacy fields. When present, it includes the
nested `DatasetTrajectorySpec.to_dict()` contract, including its version and
kind. These tags remain output-only properties, not spec constructor fields.
`dataset_spec_for_condition(condition)` uses `get_condition()` lookup semantics
(including `KeyError` for unknown names); `dataset_specs()` returns only supplied
specs in manifest order. Both helpers are pure and infer nothing.

The [external parameter-table contract](dataset_parameter_table_contract.md)
defines the separate CSV input path. Stage 26.B did not automatically bind or
merge that table with a manifest. Stage 26.C adds the explicit execution binding
below. There is no new CLI option or trajectory runtime-input change,
analysis-request change, runtime change, sampling change, or scientific artifact change.
Stage 26.A had no CLI change; Stage 26.C changes only input orchestration and
technical metadata. Stage 20–24 scientific schemas, rows, and calculation
semantics MUST remain intact.

Stage 25 software identity, generic provenance/inventory schemas, checksum modes,
unified validation status semantics, runtime metadata, and observation-only PBC
audit remain compatible. Stage 26.C adds optional preprocessing metadata and validation.
No dependency, optional scientific dependency boundary, WANIA component, FAIR²
dataset repository, service, database, or worker is changed. Stages 26.A–B add no
scientific calculation, biological annotation, QC engine, or publication export.

## Stage 26.C authoritative execution binding

`DatasetTrajectoryReference` is a frozen model with `extra="forbid"`. Its four
actual-string fields are stripped, non-empty, and case-preserving:
`dataset_id`, `system_id`, `trajectory_id`, `replica_id`. Its `replica_key` is an
identity/reference key only, never a statistical grouping key.

A manifest condition can declare inline `dataset_spec`, explicit `dataset_ref`,
both, or neither. Every reference requires top-level `dataset_parameter_table_path`,
even alongside an inline spec. Both declarations must have identical replica keys.
A declared table requires at least one Dataset-aware condition; mixed migration is
valid. Effective replica keys must be unique across Dataset-aware conditions.
Legacy condition uniqueness remains unchanged. Absent `dataset_spec`, `dataset_ref`,
and `dataset_parameter_table_path` keys are omitted by `to_dict()`; existing legacy
null fields retain their serialization.

`resolve_preprocessing_dataset_context(manifest, base_dir=...)` reads only the
explicit table through the accepted CSV reader. Relative table paths require an
explicit base directory; the CLI supplies the manifest parent. Absolute explicit
paths are valid execution inputs. There is no implicit cwd or directory discovery.

| Declaration | Binding source | Rule |
| --- | --- | --- |
| Inline only, no table | `inline_manifest` | Retain the exact inline spec |
| Reference plus table | `parameter_table` | Lookup exact four-part replica key |
| Inline plus table, with or without reference | `inline_and_parameter_table` | Exact key lookup and full spec serialization equality |
| Neither | No binding | Preserve the legacy execution path |

There is no lookup by condition, topology basename, filename, variant, row order,
or directory. Unused table rows are valid. Full equality covers all identity and
requested temporal fields; conflicts and missing rows fail before trajectory
loading or science with exit 1 and `Dataset specification binding failed:` stderr.
A resolved non-null scientific condition must equal the normalized execution
condition. Scientific condition `None` is never filled from an execution label.

`PreprocessingDatasetBinding` contains only `execution_condition`, `source`, and
`dataset_spec`, in that serialization order. `PreprocessingDatasetContext` has
read-only schema `mania.preprocessing_dataset_context.v0.1` and kind
`mania_preprocessing_dataset_context`. Its portable `to_dict()` order is
`schema_version`, `kind`, `bindings`. Bindings are non-empty, retain manifest order,
and have unique execution conditions and replica keys. `from_dict()` strictly
reconstructs this versioned serialization, including nested spec tags.

The frozen `PreprocessingDatasetResolution` separates portable `context` from
execution-only `parameter_table_local_path`. Context is absent for legacy runs.
A local path is present exactly when context uses a table; the resolution has no
portable serializer. No path or runtime object enters Dataset context.

Completed and covered failed preprocessing provenance records optional Dataset
context. Used tables become input inventory lineage, with strict table/context
cross-checking during unified validation. Generic schemas and scientific
`mania_manifest.json`, graph, and CSV artifacts are unchanged. Requested physical
values remain exactly as supplied model values; no frames, windows, conversions,
overlap, coverage, or time QC are calculated. Analysis propagation is not part of
Stage 26; future export layers may consume this preprocessing identity boundary
without inferring condition or altering current analysis semantics.
