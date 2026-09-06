# Artifact inventory contract v0.1

## Status and purpose

Stage 25.C.1 is implemented: immutable models, an explicit file-specification
builder, streaming opt-in SHA256, and an atomic JSON writer are available through
the Python API. Stage 25.C.2 preprocessing integration is implemented.
Stage 25.C.3 analysis integration and final acceptance remain planned.
Stage 25.C as a whole remains incomplete.

Artifact inventory is an additive per-run registry connecting declared inputs,
one MANIA run, and known outputs. It records file identity and integrity metadata
without changing scientific artifacts.

## Layout and root contract

Inventory locations are:

- preprocessing: `<output>/artifact_inventory.json`;
- analysis (planned): `<output>/analysis/artifact_inventory.json`.

Preprocessing creates inventory automatically after scientific execution as
described below. Calling the Python builder alone never writes a file; callers
must explicitly invoke the writer.

The independently versioned root uses this exact field order:

1. `schema_version`: `mania.artifact_inventory.v0.1`;
2. `kind`: `mania_artifact_inventory`;
3. `run_id`: non-empty stripped run identifier;
4. `workflow`: non-empty stripped workflow name;
5. `inventory_path`: normalized relative POSIX path ending in the exact filename
   `artifact_inventory.json`;
6. `checksum_mode`: `none` or `sha256`;
7. `artifact_count`: derived total;
8. `input_artifact_count`: derived input count;
9. `output_artifact_count`: derived output count;
10. `artifacts`: ordered array of entries, possibly empty.

`ArtifactInventory` and `ArtifactInventoryEntry` are frozen dataclasses in
`mania.artifact_inventory`. The inventory accepts a tuple of entries and preserves
caller order. `to_dict()` returns fresh JSON-safe dictionaries and lists. Models
perform no file, environment, Git, hash, or clock access.

## Entry contract

Entries serialize in this exact order:

| Field | Meaning and validation |
| --- | --- |
| `artifact_id` | Unique portable identifier: ASCII letters, digits, dots, underscores, hyphens, colons; starts with an ASCII letter or digit. |
| `direction` | Exactly `input` or `output`. |
| `role` | Explicit, non-empty stripped string. The self role `artifact_inventory` is reserved and forbidden in entries. |
| `path` | Unique normalized portable relative POSIX path, supplied by the caller. |
| `format` | Explicit, non-empty lowercase ASCII format using letters, digits, dots, plus signs, underscores, or hyphens. |
| `byte_size` | Exact non-negative integer size in bytes; booleans are invalid. |
| `sha256` | `null` or exactly 64 lowercase hexadecimal characters. |
| `condition` | Optional non-empty stripped condition string, otherwise `null`. |

Portable paths reject absolute paths, Windows drive paths, backslashes, URI-like
values containing `://`, NUL characters, `.` and `..` components, and any spelling
that differs from its normalized POSIX form. Filenames and nested paths are valid.
The caller defines the portable mapping for external inputs; the builder does not
derive that mapping from local paths or require inputs to live under the output.

`ArtifactInventoryFileSpec` in `mania.artifact_inventory_io` contains the same
identity metadata and a concrete native `pathlib.Path` named `local_path`.
Absolute and relative execution paths are allowed. Construction does not inspect
or resolve them. Local execution paths are never serialized; this execution-only
type intentionally has no `to_dict()` API. Symlinks to regular files may be
inspected without resolving or serializing their targets. Directories and other
non-regular files are rejected.

## Checksum modes

- `"none"` is the default: sizes only, using file metadata with no file-content
  opening or reading. All entry checksums are `null`.
- `"sha256"` requires explicit Python API or preprocessing CLI opt-in. Every
  declared artifact is streamed in bounded positive chunks, defaulting to one MiB.
  No whole-file memory
  loading occurs. Every entry must have a checksum; incomplete mixed checksum sets
  are rejected.

`stream_file_sha256(path, chunk_size=...)` accepts a concrete native `Path` and a
positive integer chunk size, excluding booleans. Where file descriptors support
it, hashing checks initial and final size and modification timestamp and verifies
the streamed byte count against the descriptor size. The builder also checks size
and timestamp around hashing. These detect observed mutations, without promising
a locked filesystem snapshot or detecting changes that restore the same metadata.
Modification timestamps are never part of the portable payload.

Normal preprocessing automatically writes `<output>/artifact_inventory.json`:

```bash
mania preprocessing run-graph-export --manifest manifest.yaml --output out
```

The default `--artifact-checksum-mode none` records exact byte sizes without
reading file contents for inventory. All SHA256 fields are `null`. There is no
second integrity or publication flag and no automatic checksum-mode switching.

Explicit opt-in is available with:

```bash
mania preprocessing run-graph-export --manifest manifest.yaml --output out \
  --artifact-checksum-mode sha256
```

SHA256 streams every inventoried file, including topology and trajectory inputs.
It can require reading multi-gigabyte XTC files in full again and may be expensive
for large MD datasets. Use it only intentionally. Checksums remain outside all
scientific tables and manifests.

## Authoritative-source boundary

Integrations build specifications only from validated input manifests,
authoritative workflow results, and known output paths. Blind output-directory
scanning is forbidden because it could mix old or unrelated files into the current
run. The builder inspects only the exact supplied paths, preserving specification
order; it infers neither roles nor formats. All metadata, duplicates, and
self-reference are validated before any file is opened or stat-ed.

## Self-reference policy and existing metadata

`inventory_path` is recorded at the root. The inventory is excluded from its own
artifact entries by both its portable path and the reserved role
`artifact_inventory`. It has no self-SHA256. No separate `checksums.sha256` file
is created.

Stage 25.C.2 excludes `run_provenance.json` from inventory as well. A successfully
written preprocessing inventory adds exactly one portable reference to completed
or failed preprocessing provenance: role `artifact_inventory`, path
`artifact_inventory.json`. Unavailable or failed inventory generation adds no
reference, even if an older inventory file is present. Authoritative files feed
inventory, then provenance references inventory: neither metadata file is hashed
by inventory, and no checksum cycle exists. The provenance schema is unchanged.

These remain separate: `run_provenance.json`, `mania_manifest.json`,
`extended_metrics.json`, legacy `RunMeta`, and artifact inventory.
None replaces another.

## Writing and failure policy

`build_artifact_inventory(...)` is all-or-nothing for the declared specification
set. Inspection or hashing failure raises `ArtifactInventoryBuildError`, with a
deterministic message that may identify a portable artifact ID but never a local
path or underlying exception representation. No partial inventory model or file
is produced. Invalid metadata raises `ValueError` before file access.

`write_artifact_inventory(inventory, output_root, overwrite=False)` creates missing
parents and writes UTF-8 JSON with two-space indentation, preserved key order,
literal non-ASCII text, finite JSON primitives, and exactly one trailing newline.
It publishes a complete temporary file in the target directory atomically. By
default an existing target, including one created concurrently, is preserved;
`overwrite=True` atomically replaces it. Expected serialization and filesystem
failures return a failed `ArtifactInventoryWriteResult` with deterministic text.
Temporary files are removed after success or failure; if the filesystem refuses
cleanup, that failure is reported explicitly. No partial final file is left.

The frozen internal write result exposes `output_path`, `written`, `error`, and
derived `passed` in that order. It may serialize its local output path as a string
and must never be embedded in the portable inventory payload. An unsuccessful
result requires a non-empty error; a successful result requires no error.

### Preprocessing authoritative sources and portable identities

`mania.preprocessing.artifact_inventory` adapts accepted retained state without
reopening the manifest, reloading trajectories, scanning directories, writing
files, or reading Git or the clock. Inputs precede outputs.

- The manifest itself is `input:manifest`, role `input_manifest`, portable path
  `inputs/manifest/<filename>`.
- Each condition uses its retained `PreprocessingConditionLoadResult.runtime_input`
  for topology, ordered trajectory paths, and optional reference structure.
  Manifest/runtime condition order determines 1-based ordinals `0001`, `0002`,
  etc. For example, `input:condition:0001:topology` maps to
  `inputs/conditions/0001/topology/<filename>`;
  `input:condition:0001:trajectory:0001` maps to
  `inputs/conditions/0001/trajectories/0001/<filename>`; and
  `input:condition:0001:reference_structure` maps to
  `inputs/conditions/0001/reference_structure/<filename>`.
- Raw condition names occur only in the input entry's `condition` field, never
  its ID or virtual path. Manifest and CLI reference entries have null condition.
- When comparison is enabled, supplied CLI reference nodes, edges, and graph
  inputs use `input:reference:nodes`, `input:reference:edges`, and
  `input:reference:graph`, under `inputs/reference/nodes/`,
  `inputs/reference/edges/`, and `inputs/reference/graph/`, with filename-only
  final components. Their roles are `reference_nodes`, `reference_edges`, and
  `reference_graph`. Disabled comparison contributes no reference inputs.
- The current graph-export workflow checks external residue-library path metadata
  but does not open and consume those files. Such schema fields are excluded.
  The generated `mania_residue_library.json` is an output when analysis-input
  export succeeds.

Input formats derive from the lowercase final filename suffix (for example
`yaml`, `tpr`, `xtc`, `csv`); a missing or unusable suffix is rejected. This does
not infer a scientific engine or MIME type.

Outputs come only from successful accepted stage results, in execution order:
graph nodes, edges, and JSON; requested analysis-input exports; requested
scientific CSVs; written diagnostics report; enabled and written reference
comparison report. Analysis-input exports enumerate every reported per-condition
residue table, protein contact edge table and contact-per-frame table, plus
`edge_semantics.json`, `mania_residue_library.json`, and `mania_manifest.json`.
Condition-specific output IDs use ordinals with the actual condition stored
separately. The accepted output layout and filenames remain unchanged. Optional
scientific CSVs include only requested `rg_timeseries`, `contact_edges`, and
`contacts_perframe` outputs. Reports require passed stages and enabled writing.
Output paths are lexical POSIX paths relative to the output root; outside-root
paths are rejected without resolving symlinks. No directory scan occurs, so
unrelated files, old outputs, temporary files, and analysis/WANIA artifacts are
never discovered or automatically included.

### Preprocessing workflow failure semantics

Inventory is technical post-processing after the existing scientific stages.
The existing end timestamp is captured before inventory construction, and
software identity is captured only once. Hashing duration is not added to
provenance. Inventory adds no scientific stage, verbose message, or stdout field.
On scientific success, inventory is built and atomically written using the
resolved `options.overwrite`, then completed provenance is written, then the
existing successful stdout summary is printed unchanged.

A scientific success followed by inventory failure returns exit 1 and suppresses
the successful summary. Completed provenance is still attempted without an
inventory reference. One deterministic stderr line begins `Artifact inventory
build failed:` or `Artifact inventory write failed:`. If fallback provenance also
fails, its existing `Run provenance build failed:` or `Run provenance write
failed:` line follows the inventory error. Scientific outputs are retained;
no partial inventory is published. An existing target is preserved when
`overwrite=False`.

Covered scientific failures retain their original stdout and exit code.
Inventory is attempted before failed provenance only when readiness passed and
one accepted runtime-input record exists for every intended condition. A failed
condition load is sufficient if its validated input record is retained; missing
records skip inventory silently rather than publish a partial input set.

| Failed stage | Inventoried outputs, in addition to complete inputs |
| --- | --- |
| Plan | No inventory |
| Runtime loading | None; incomplete inputs mean no inventory |
| Computation or graph export | None |
| Analysis-input export | Successful graph outputs |
| Scientific CSV export | Graph and earlier successful analysis-input outputs |
| Diagnostics | Graph, analysis-input and scientific CSV outputs from successful stages |
| Reference comparison | All earlier successful outputs, including a written diagnostics report |

Skipped stages and partial outputs from the failed stage are excluded. Failed-run
inventory success adds the inventory reference to failed provenance with no
extra stderr. Inventory failure prints the same deterministic inventory prefix,
still attempts failed provenance without the reference, and preserves the
original scientific failure. No scientific rollback occurs.

Parser errors, missing required arguments, invalid sampling or option
combinations, help, and version never create inventory. Analysis inventory and
its workflow failure semantics remain deferred to Stage 25.C.3.

## Scientific boundary and deferred work

There is no scientific row, schema, value, sampling behavior, contact definition,
RIN calculation, PCA, or clustering behavior change. Integrity metadata belongs
only in this additive contract.

Deferred work:

- Stage 25.C.3 analysis integration;
- analysis workflow failure semantics;
- Stage 25.C final acceptance;
- unified publication validation in Stage 25.D;
- PBC audit in Stage 25.E;
- FAIR² software/dataset bridge in Stage 25.F.
