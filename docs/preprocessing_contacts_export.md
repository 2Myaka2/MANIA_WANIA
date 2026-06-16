# Contacts export

## Purpose

Contacts export turns existing contacts result objects into two dependency-free
CSV outputs:

```text
contacts_perframe.csv
contact_edges.csv
```

It does not compute contacts.
It does not load trajectories.
It does not acquire MDAnalysis.
It does not run graph export.

The accepted conceptual flow is:

```text
contacts result object
-> write contacts_perframe.csv
-> write contact_edges.csv
-> validate both CSV outputs
```

## Inputs

The accepted writer inputs are:

```python
PreprocessingConditionContactsResult
PreprocessingManifestContactsResult
```

Those result objects are normally produced by:

```python
compute_condition_contacts(...)
compute_manifest_contacts(...)
```

Stage 13.3d examples use synthetic constructed result objects instead of real
MD data. They do not require MDAnalysis, load trajectories, or compute contacts
from runtime objects.

## Per-frame contacts CSV

The canonical filename is `contacts_perframe.csv`.

The writer is:

```python
write_contacts_perframe_csv(...)
```

The validator is:

```python
validate_contacts_perframe_csv(...)
```

The file contains one row per contact pair per frame. Zero-contact results and
empty manifest results write a header-only file and pass when the input object
and output path are valid.

Failed frames are skipped by default and counted in the writer result. With
`include_failed_frames=True`, contacts already present on failed frames are
written with `frame_passed` set to `false`.

The exact header is:

```text
condition_name,frame_index,time_ps,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,minimum_distance,distance_unit,atom_filter,frame_passed
```

## Aggregate contact edges CSV

The canonical filename is `contact_edges.csv`.

The writer is:

```python
write_contact_edges_csv(...)
```

The validator is:

```python
validate_contact_edges_csv(...)
```

The file contains one row per aggregate residue pair per condition.
Zero-contact results and empty manifest results write a header-only file and
pass when the input object and output path are valid.

Failed frames are skipped by default and do not contribute to
`total_frame_count`. Failed frames do not contribute to `total_frame_count`.
With `include_failed_frames=True`, failed frames contribute to totals and any
contacts already present on those frames are aggregated.

The aggregate fields are:

- `contact_frame_count`
- `total_frame_count`
- `contact_frequency`
- `minimum_distance`
- `mean_minimum_distance`

The exact header is:

```text
condition_name,source_residue_index,target_residue_index,source_residue_id,target_residue_id,source_resname,target_resname,source_segid,target_segid,contact_frame_count,total_frame_count,contact_frequency,minimum_distance,mean_minimum_distance,distance_unit,atom_filter
```

contact_edges.csv is an aggregate contacts table.
It is not backend graph edges.csv.

contact_edges.csv is not nodes.csv.
contact_edges.csv is not backend graph edges.csv.
contact_edges.csv is not graph.json.
Graph export belongs to a later stage.

## Validation

Use the read-only validators after writing:

```python
validate_contacts_perframe_csv(...)
validate_contact_edges_csv(...)
```

The validators are:

- read-only
- dependency-free
- exact-header validators
- type/range validators
- not reference comparison
- not graph validation

They read existing CSV files only. They do not compute contacts, load runtime
objects, write CSV, compare references, or produce graph outputs.

## Synthetic example

See `examples/preprocessing/contacts_export_usage.py` for a dependency-free
example that constructs synthetic contacts results, writes both accepted CSVs
inside a `TemporaryDirectory`, and validates both files.

Small static examples are also committed:

- `examples/preprocessing/contacts_perframe.example.csv`
- `examples/preprocessing/contact_edges.example.csv`

These examples are deterministic synthetic rows, not real scientific data.

## Boundaries

Stage 13.3d does not add:

- new computation
- source behavior changes
- local scientific export smoke
- reference comparison
- report bundle
- graph export
- CLI/workflow integration
- real-data CI
- biological interpretation

The examples do not create backend graph `nodes.csv`, backend graph
`edges.csv`, or `graph.json`.

## Local scientific smoke

Stage 13.3e adds an opt-in local scientific contacts export smoke test. It
verifies the accepted local compute/write/validate chain:

```text
load manifest -> load runtimes -> compute manifest contacts
-> write contacts_perframe.csv -> write contact_edges.csv
-> validate both CSV outputs
```

The test uses the existing local scientific harness, requires
`MANIA_RUN_LOCAL_SCIENTIFIC=1`, and uses
`MANIA_LOCAL_REFERENCE_PACKAGE=<path>` for local real data. Generated CSV
files are written only to pytest's temporary directory.

The smoke test does not add new export APIs, compare references, build a
report bundle, or produce graph outputs. contact_edges.csv remains aggregate
contacts output, not backend graph edges.csv.

## Future stages

Stage 13.4 will add contacts reference comparison.
Graph export remains future after contacts MVP.
