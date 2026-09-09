# Dataset v1.0 trajectory identity — Stage 26.A

## Status and scope

Stage 25 is complete. Stage 26.A is implemented as an additive, independent
in-memory contract in [`dataset_identity.py`](../src/mania/dataset_identity.py).
Stage 26 remains incomplete. Stage 26.B manifest/parameter-table integration
is next; workflow/provenance propagation and final acceptance belong to later
Stage 26 checkpoints.

The [Dataset v1.0 scientific contract](dataset_v1_scientific_contract.md) records
the frozen scientific decisions for Stages 27–35. Scientific decisions being
frozen does not mean their future functionality is implemented or that Dataset
v1.0 is released. Historical Stage 25 records retain their acceptance context.

## Identity boundary

The existing preprocessing workflow is condition-centric. Its legacy
`condition` remains a scientific condition label. A condition label alone MUST
NOT stand in for the new dataset/system/trajectory/replica identity.

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

Stage 26.A makes no legacy manifest change: `TrajectoryInputConfig` and
`PreprocessingInputManifest` remain unchanged. There is no manifest integration,
CLI change, trajectory runtime-input change, analysis-request change, runtime
change, sampling change, or scientific artifact change. Stage 20–24 scientific
schemas, rows, and calculation semantics MUST remain intact.

Stage 25 software identity, run provenance, inventory/checksum modes, unified
validation, runtime metadata, and observation-only PBC audit remain unchanged.
No dependency, optional scientific dependency boundary, WANIA component, FAIR²
dataset repository, service, database, or worker is changed. Stage 26.A adds no
scientific calculation, biological annotation, QC engine, or publication export.
