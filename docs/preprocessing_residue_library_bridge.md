# Preprocessing residue library bridge

## Purpose

This document plans a future bridge between preprocessing manifest
residue-library options and the existing MANIA residue-library loader,
extension, classification, and QC components.

## Current status

Stage 8.4 is documentation and planning only. The preprocessing manifest already
defines residue-library options, and the existing residue-library layer already
loads a source library and supports in-memory custom residues and QC. These two
parts are not connected yet.

No manifest-to-residue-loader bridge is implemented in Stage 8.4.

## Existing residue-library layer

The current residue-library implementation is in
`src/mania/residue_library.py`:

- `load_residue_library(path)` reads and validates a MANIA residue library JSON
  file and returns a `ResidueLibrary`.
- `ResidueLibrary` contains normalized residue and patch mappings plus lookup
  helpers. `classify_residue(resname)` returns the stored category or `None`.
- `extend_residue_library(...)` creates a new effective library from a loaded
  library and an in-memory mapping of custom residue names to `ResidueEntry`
  objects.
- Custom residue names are normalized. Replacing a source entry is rejected
  unless `allow_override_existing=True`.
- `run_residue_library_qc(...)` accepts residue names grouped by condition, a
  loaded library, skip residue names, and a `fail_on_error` policy.
- QC rows use `ok`, `skip`, and `not_found` statuses. `ResidueQCReport` exposes
  error, unknown-name, and status-count helpers.
- `write_residue_qc_report(...)` can write an existing QC report as CSV.

The current layer does not load custom residue definitions from a separate
manifest-declared file. Its custom-residue extension API accepts already parsed
`ResidueEntry` objects.

The archive inventory identifies `mania_residue_library.json` as the source of
truth for residue classification and QC, while also stating that the full
library should not be committed to the backend repository.

## Manifest residue-library options

The preprocessing manifest currently supports:

```yaml
residue_library:
  library_path: residue_library/mania_residue_library.json
  custom_residues_path: residue_library/custom_residues.json
  skip_resnames:
    - CLA
    - SOD
    - TIP3
  allow_user_overrides: false
```

- `library_path` is the path to the full/source residue library JSON. It is an
  external or reference input. A real full library must not be committed unless
  a later task explicitly permits a tiny deterministic fixture.
- `custom_residues_path` is the canonical preprocessing manifest field for an
  optional file containing custom residue definitions. A future bridge should
  map it to the existing custom-residue mechanism.
- `skip_resnames` lists residue names to ignore during later classification or
  QC. The manifest model already strips, uppercases, and deduplicates them.
- `allow_user_overrides` records whether custom definitions may replace source
  definitions. Enforcement should remain with the existing residue-library
  layer or the future bridge that calls it.

## Planned bridge responsibilities

A future bridge, likely in Stage 10.1, should:

- accept `ResidueLibraryInputConfig`;
- optionally accept an explicit `base_dir`;
- resolve relative residue-library paths without changing manifest parsing;
- call `load_residue_library()` for the configured source library;
- parse custom definitions into the existing `ResidueEntry` representation;
- pass those entries to `extend_residue_library()`;
- map `allow_user_overrides` to the existing `allow_override_existing` policy;
- preserve normalized `skip_resnames` for a later QC call;
- reuse `ResidueLibrary`, `ResidueQCReport`, and existing exception types where
  appropriate;
- produce deterministic errors or reports.

Path existence checks may use the explicit Stage 8.3 path validator, but
manifest loading itself must remain shape-and-type validation only.

## Non-goals for Stage 8.4

Stage 8.4 does not:

- implement a manifest-to-residue-loader bridge;
- load residue-library files from preprocessing manifests;
- validate residue-library JSON content;
- run residue QC;
- classify residues from topology or trajectory data;
- parse topology files;
- parse trajectory files;
- require MDAnalysis;
- require GROMACS;
- add scientific dependencies;
- compute Rg;
- compute contacts;
- add CLI behavior;
- add workflow behavior.

## Future stage ownership

```text
Stage 8.4:
  bridge planning only

Stage 10.1:
  connect manifest residue_library options to the existing loader

Stage 10.2:
  validate full library format locally

Stage 10.3:
  run residue QC against explicit/local residue-name inputs when available

Stage 11:
  obtain residue names from topology/trajectory loading if feasible
```

These are planning notes, not implemented capabilities.

## Proposed future API shape

The following is **proposed future pseudocode**. The function is **not
implemented in Stage 8.4**.

```python
def load_residue_library_from_manifest_options(
    options: ResidueLibraryInputConfig,
    *,
    base_dir: str | Path | None = None,
) -> object:
    ...
```

The future implementation should return the existing `ResidueLibrary` type
where possible. A richer result should be introduced only if the bridge needs
to carry deterministic loading or validation details that the existing type
cannot represent.

## Local/reference data policy

Full real residue libraries are external/reference inputs. Real local reference
data must not be committed. Tiny fixtures or examples are allowed only when
they are deterministic, intentionally small, and introduced by an explicit
task.

`data/reference/...` must remain local and uncommitted unless an explicit later
task changes that policy.

## Open questions

- Should the future bridge return a loaded `ResidueLibrary` directly or a
  report alongside the loaded object?
- Should relative paths always require an explicit `base_dir`, matching the
  Stage 8.3 path validator?
- Which existing residue-loader exceptions should be preserved, and which, if
  any, should be wrapped with manifest field context?
- What file format should `custom_residues_path` use, and how should it be
  converted into `ResidueEntry` objects?
- Where should local-only full-library validation reports be written, if
  anywhere?
- Should Stage 10.3 reuse `ResidueQCReport` directly or add a bridge-level
  result containing both the effective library and QC report?
