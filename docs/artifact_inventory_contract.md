# Artifact inventory contract v0.1

## Status and purpose

Stage 25.C.1 is implemented: immutable models, an explicit file-specification
builder, streaming opt-in SHA256, and an atomic JSON writer are available through
the Python API. Automatic preprocessing and analysis integration is not yet
implemented. Stage 25.C as a whole remains incomplete.

Artifact inventory is an additive per-run registry connecting declared inputs,
one MANIA run, and known outputs. It records file identity and integrity metadata
without changing scientific artifacts.

## Layout and root contract

Intended locations are:

- preprocessing: `<output>/artifact_inventory.json`;
- analysis: `<output>/analysis/artifact_inventory.json`.

Automatic creation begins only in later integration steps. Calling the builder
alone never writes a file; callers must explicitly invoke the writer.

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
- `"sha256"` requires explicit Python API opt-in. Every declared artifact is
  streamed in bounded positive chunks, defaulting to one MiB. No whole-file memory
  loading occurs. Every entry must have a checksum; incomplete mixed checksum sets
  are rejected.

`stream_file_sha256(path, chunk_size=...)` accepts a concrete native `Path` and a
positive integer chunk size, excluding booleans. Where file descriptors support
it, hashing checks initial and final size and modification timestamp and verifies
the streamed byte count against the descriptor size. The builder also checks size
and timestamp around hashing. These detect observed mutations, without promising
a locked filesystem snapshot or detecting changes that restore the same metadata.
Modification timestamps are never part of the portable payload.

Normal MANIA execution must not silently hash large XTC files. Normal preprocessing
still does not automatically hash trajectories. No CLI checksum flag or command
exists yet; the exact opt-in CLI surface is deferred.

## Authoritative-source boundary

Later integrations must build specifications only from validated input manifests,
authoritative workflow results, and known output paths. Blind output-directory
scanning is forbidden because it could mix old or unrelated files into the current
run. The builder inspects only the exact supplied paths, preserving specification
order; it infers neither roles nor formats. All metadata, duplicates, and
self-reference are validated before any file is opened or stat-ed.

## Self-reference policy and existing metadata

`inventory_path` is recorded at the root. The inventory is excluded from its own
artifact entries by both its portable path and the reserved role
`artifact_inventory`. It has no self-SHA256. No separate `checksums.sha256` file
exists in Stage 25.C.1.

Future run provenance may reference inventory, and inventory may describe and
checksum run provenance without creating a checksum cycle. This task does not
add those references or modify run provenance.

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

Exact workflow-level failure semantics remain deferred to Stage 25.C.2 and
Stage 25.C.3.

## Scientific boundary and deferred work

There is no scientific row, schema, value, sampling behavior, contact definition,
RIN calculation, PCA, or clustering behavior change. Integrity metadata belongs
only in this additive contract.

Deferred work:

- Stage 25.C.2 preprocessing integration;
- Stage 25.C.3 analysis integration;
- the exact opt-in CLI surface;
- provenance-to-inventory references;
- workflow failure semantics;
- Stage 25.C final acceptance;
- unified publication validation in Stage 25.D;
- PBC audit in Stage 25.E;
- FAIR² software/dataset bridge in Stage 25.F.
