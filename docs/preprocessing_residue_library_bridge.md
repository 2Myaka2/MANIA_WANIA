# Preprocessing residue library bridge

## Purpose

Stage 10.1 connects preprocessing manifest residue-library options to the
existing MANIA residue-library loader and extension layer.

The bridge is implemented in
`src/mania/preprocessing/residue_library_bridge.py` and is publicly exported
from `mania.preprocessing`.

## Public API

`resolve_residue_library_manifest_paths(options, base_dir=None)` returns
`ResolvedResidueLibraryManifestOptions`. It:

- requires `residue_library.library_path`;
- resolves relative `library_path` and `custom_residues_path` values against an
  explicitly supplied `base_dir`;
- keeps absolute paths unchanged;
- leaves paths as provided when `base_dir` is `None`;
- does not check file existence or open files;
- preserves the manifest model's normalized `skip_resnames` tuple;
- preserves `allow_user_overrides`.

Missing `library_path` raises
`PreprocessingResidueLibraryBridgeError`, a bridge-level `ValueError`.
`ResolvedResidueLibraryManifestOptions.to_dict()` converts paths to strings and
returns JSON-serializable data.

`load_residue_library_from_manifest_options(options, base_dir=None)`:

1. resolves the manifest options with the helper above;
2. loads `library_path` with the existing `load_residue_library(...)`;
3. when configured, loads `custom_residues_path` through the same existing
   residue-library format and loader;
4. passes the custom library's parsed residue mapping to the existing
   `extend_residue_library(...)`;
5. maps `allow_user_overrides` to
   `extend_residue_library(..., allow_override_existing=...)`;
6. returns the existing `ResidueLibrary` type.

The custom file therefore uses the existing `MANIA_residue_library` JSON
format. Stage 10.1 does not introduce another custom-residue format or parser.
Only its residue entries are applied because the existing extension API accepts
a mapping of residue names to `ResidueEntry` objects.

## Override policy

The bridge preserves existing extension behavior:

- with `allow_user_overrides: false`, a custom residue that would replace a
  source residue raises the existing `ResidueLibraryValidationError`;
- with `allow_user_overrides: true`, the custom residue replaces that entry in
  the returned effective library;
- custom residue names continue to use the existing normalization and
  validation rules.

Loader and extension errors are not hidden or converted into generic bridge
errors.

## Skipped residue names

`skip_resnames` is already stripped, uppercased, and deduplicated by
`ResidueLibraryInputConfig`. The resolved-options object retains that tuple for
future Stage 10.3 and later QC or classification work.

Stage 10.1 does not pass skipped names to the loader, run
`run_residue_library_qc(...)`, or classify any topology or trajectory
residues.

## Explicit path base

Relative paths are joined to `base_dir` only when callers provide it. The
bridge does not infer a base directory from a manifest path and does not use
strict path resolution. File existence and content errors remain the
responsibility of the existing loader or explicit preprocessing path checks.

## Stage 10.2 local format validation

`validate_residue_library_from_manifest_options(options, base_dir=None)`
provides explicit local validation of the residue-library files declared in
`ResidueLibraryInputConfig`. It is publicly exported from
`mania.preprocessing`.

The validator:

- resolves paths through
  `resolve_residue_library_manifest_paths(...)`, including the same explicit
  `base_dir` behavior;
- returns a `PreprocessingResidueLibraryValidationReport` rather than raising
  for expected missing-path, file-type, load, or extension problems;
- requires `residue_library.library_path`;
- checks that the source and optional custom paths exist and are files;
- loads both files through the existing `load_residue_library(...)`;
- applies custom residue entries through the existing
  `extend_residue_library(...)`;
- maps `allow_user_overrides` to the existing `allow_override_existing`
  extension policy;
- reports whether the source loaded, whether custom residues were applied, and
  the effective residue count when available.

Validation issues distinguish a missing `library_path`, missing files,
non-file paths, source load errors, custom load errors, and extension errors.
The report and issue `to_dict()` methods return JSON-serializable dictionaries,
including string path values. They do not contain a `ResidueLibrary` object.

Normalized `skip_resnames` remain available through the report's resolved
options, but Stage 10.2 does not use them to run residue QC or classification.
The validator checks only the declared residue-library JSON files. It does not
inspect topology, trajectory, or reference-structure paths.

## Stage 10.3 residue QC for explicit residue names

`run_residue_qc_from_manifest_options(options, residue_names, base_dir=None)`
runs the existing residue-library QC against residue names supplied directly by
the caller. It is publicly exported from `mania.preprocessing`.

The wrapper:

1. validates residue-library options through
   `validate_residue_library_from_manifest_options(...)`;
2. strips each explicit residue name and rejects non-string or empty entries;
3. filters names matching the manifest's normalized `skip_resnames`, using the
   existing residue-name normalization convention;
4. loads the effective library through
   `load_residue_library_from_manifest_options(...)` only after validation and
   input checks pass;
5. calls the existing `run_residue_library_qc(...)` for the remaining explicit
   names.

The preprocessing report preserves the stripped input names, the names checked
by QC, and the names removed by skip filtering. If all names are skipped, QC is
not run. The wrapper passes an empty skip set to the existing QC function
because preprocessing has already applied the manifest's explicit skip policy.

The existing QC function normalizes residue-name case for lookup. Stage 10.3
uses `fail_on_error=False` so unknown residues remain available as the existing
`not_found` rows and make the preprocessing report fail without discarding QC
details. Expected `ResidueLibraryQCError` failures are represented as a
preprocessing `qc_error` issue.

`PreprocessingResidueQCReport.to_dict()` is JSON-serializable. It includes the
Stage 10.2 validation report and lightweight existing QC fields: rows, status
counts, unknown residue names, and error status. It does not contain a runtime
`ResidueLibrary` object.

Residue names are explicit caller inputs only. Stage 10.3 does not extract or
infer names from topology, trajectory, reference-structure, or reference
package files.

## Stage 10.1 boundaries

Stage 10.1 itself does not:

- add a separate full-library validation task;
- run residue QC;
- classify residues from topology or trajectory data;
- parse topology files;
- parse trajectory files;
- require MDAnalysis;
- require GROMACS;
- compute Rg;
- compute contacts;
- integrate residue-library loading with the CLI or workflow.

## Stage 10.2 boundaries

Stage 10.2 does not:

- run residue QC;
- classify residues from topology or trajectory data;
- parse topology files;
- parse trajectory files;
- require MDAnalysis;
- require GROMACS;
- compute Rg;
- compute contacts;
- integrate residue-library validation with the CLI or workflow;
- commit real residue libraries.

## Stage 10.3 boundaries

Stage 10.3 does not:

- parse topology files;
- parse trajectory files;
- use MDAnalysis;
- use GROMACS;
- compute Rg;
- compute contacts;
- generate graphs;
- integrate residue QC with the CLI or workflow;
- add real data.

## Stage 10.4 boundary summary

Stage 10 residue-library work is complete for local residue-library files and
explicit residue-name inputs. Topology/trajectory-derived residue names remain
future Stage 11 and later work.

Stage 10.4 adds no runtime behavior. See
`docs/preprocessing_before_trajectory_parsing.md` for the complete boundary
before scientific file loading begins.

Full real residue libraries remain external or local reference inputs.
`data/reference/...` is not populated by this bridge.
Optional scientific dependencies remain governed by
`docs/adr/0001-optional-scientific-dependencies.md`.
