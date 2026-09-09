# Dataset trajectory parameter-table input — Stage 26.B

## Purpose and status

The external parameter table supplies per-trajectory Dataset identity and
REQUESTED physical-time parameters. It is an input/control table, not a
scientific-output table, aggregation table, final Dataset v1.0 publication
table, or FAIR² publication schema.

Stage 26.A identity models are accepted; Stage 26.B manifest and table input
integration is implemented. Stage 26 remains incomplete. Stage 26.C execution
binding/propagation and acceptance are next. The
[identity contract](dataset_identity_contract.md) and unchanged
[frozen scientific contract](dataset_v1_scientific_contract.md) remain authoritative.

## Exact CSV columns and units

The UTF-8 CSV header MUST contain exactly these 14 columns in this order:

| Column | Unit / meaning |
| --- | --- |
| `dataset_id` | Required dataset identifier |
| `system_id` | Required system identifier |
| `trajectory_id` | Required trajectory identifier |
| `variant_id` | Required supplied variant identifier |
| `engine` | `gromacs` or `namd`, normalized by the identity model |
| `condition` | Optional scientific condition label |
| `replica_id` | Required replica identifier |
| `disulfide_state` | Optional supplied design label |
| `production_start_ns` | ns |
| `production_end_ns` | ns |
| `frame_stride_ps` | ps |
| `window_length_ns` | ns |
| `window_step_ns` | ns |
| `overlap_percent` | percent |

No paths, results, canonical mapping fields, or QC fields are included.
Standard CSV quoting is supported. Missing, extra, duplicated, or reordered
header columns, incorrect row widths (including blank records), malformed CSV,
invalid UTF-8, empty files, and header-only files are rejected. The reader
requires an existing regular file and preserves source row order without
directory discovery or sorting.

## Validation and identity semantics

Each row is validated through the accepted `DatasetTrajectoryIdentity`,
`DatasetTemporalParameters`, and `DatasetTrajectorySpec` models. Required text
identifiers must remain non-empty after stripping; case is preserved. Only
engine spelling is normalized to lowercase.

Empty or whitespace-only `condition` and `disulfide_state` cells become `None`.
All other supplied label strings, including `unknown`, `pending`, `N/A`, `none`,
and `null`, remain ordinary strings. Final concrete NAMD scientific condition
labels remain unresolved; MANIA does not invent them or derive them from IDs
or execution labels.

The exact identity/reference `replica_key` is
`(dataset_id, system_id, trajectory_id, replica_id)`. Duplicate keys are rejected.
This is not a statistical aggregation key. Repeated scientific conditions
across distinct replicas are valid, including three replicas with `NORM`.
Neither `condition`, `variant_id`, nor `system_id` alone is a replica identity key.

Numeric cells are parsed into Python floats and passed to the accepted temporal
model. Empty/malformed values, NaN, infinities, and invalid temporal requests
are rejected: start must be non-negative, end must exceed start, stride and
window step must be positive, window length must be positive and fit within
the production interval, and overlap must be in `[0, 100)`. Units and requested
values are retained. Length, step, and overlap remain independent requests;
no overlap or effective stride is derived.

One valid row is sufficient. Development subsets and future full tables are
supported without enforcing 33 trajectories, 19 systems, three replicas per
group, known NAMD labels, or any particular `dataset_id`. Dataset-completeness
validation belongs to later work.

## Python API and serialization

Import from `mania.dataset_parameter_table`:

```python
from mania.dataset_parameter_table import read_dataset_parameter_table_csv

table = read_dataset_parameter_table_csv("parameters.csv")
specs = table.specs
row_count = table.row_count
```

`read_dataset_parameter_table_csv(path: str | Path) -> DatasetParameterTable`
raises `DatasetParameterTableReadError(ValueError)` for file, CSV, or row/table
validation failures. Row validation errors include the source line number.

`DatasetParameterTable` is a frozen Pydantic model with `extra="forbid"` and one
input field, `specs: tuple[DatasetTrajectorySpec, ...]`. It requires at least one
validated spec and unique exact replica keys. `schema_version`, `kind`, and
`row_count` are read-only properties, not user-supplied fields.

`to_dict()` returns independent JSON-safe data with this exact root order:

1. `schema_version`: `mania.dataset_parameter_table.v0.1`;
2. `kind`: `mania_dataset_parameter_table`;
3. `row_count`: number of supplied specs;
4. `specs`: ordered nested `DatasetTrajectorySpec.to_dict()` dictionaries.

The public constants are `DATASET_PARAMETER_TABLE_SCHEMA_VERSION`,
`DATASET_PARAMETER_TABLE_KIND`, and `DATASET_PARAMETER_TABLE_COLUMNS`.

## Execution and scientific stage boundary

Stage 26.B reads and validates requested parameters. An embedded manifest
`dataset_spec` and a standalone external parameter table are separate input
paths. There is no automatic binding, merging, filename/topology matching, or
matching by condition. No `parameter_table_path` manifest field or CLI argument
is added, including to `mania preprocessing run-graph-export`.

Stage 26.C owns authoritative execution binding and identity propagation into
runtime/provenance/inventory. Stage 27 owns physical-time frame selection,
effective windows, and overlap mechanics. Stage 26.B does not convert ps/ns,
select or calculate frames, construct or count windows, calculate lifetime or
occupancy, aggregate replicas, or invoke topology/trajectory loading or
MDAnalysis. Existing runtime, CLI, and scientific calculations remain unchanged.
