# Preprocessing local reference package

## Purpose

This document describes a local-only directory convention and preflight check
for preprocessing reference inputs.

## Current status

Stage 8.5 adds local sanity checks only. It does not add a scientific runtime,
parse scientific files, validate scientific file contents, commit or require
real data, or add CLI or workflow integration.

Only local directories are supported. Zip files, tar files, archive extraction,
downloads, and package distribution are outside this stage.

## Suggested local package shape

```text
local_reference_package/
  preprocessing_manifest.yaml
  data/normal/topology.tpr
  data/normal/trajectory.xtc
  data/normal/reference.pdb
  residue_library/mania_residue_library.json
  residue_library/custom_residues.json
```

This shape is a local/manual convention. A real package and its scientific data
must not be committed to the repository.

## Sanity checker

`check_preprocessing_reference_package(...)` accepts a package root directory.
The optional `manifest_name` selects the manifest filename and defaults to
`preprocessing_manifest.yaml`. The optional `check_output_root` flag is passed
to the existing declared-path validator and defaults to `False`.

The returned `PreprocessingReferencePackageReport` contains package-level
issues and, after a successful manifest load, a nested
`PreprocessingPathValidationReport`. The package report passes only when there
are no package-level issues and the nested path validation passes.

## What is checked

- The package root exists.
- The package root is a directory.
- The configured manifest exists.
- The configured manifest is a file.
- The manifest loads through `load_preprocessing_input_manifest(...)`.
- Manifest-declared paths are checked through
  `validate_preprocessing_manifest_paths(...)` relative to the package root.

## What is not checked

Stage 8.5 does not:

- open or parse topology files;
- open or parse trajectory files;
- validate residue-library JSON content;
- run residue QC;
- calculate Rg;
- calculate contacts;
- generate graph outputs;
- run through the CLI;
- run through the workflow;
- require MDAnalysis or GROMACS;
- support zip or tar archives.

## Local data policy

Real reference packages are local-only. Do not commit real topology,
trajectory, reference-structure, or residue-library data. Do not commit
notebooks, parquet files, figures, full reference exports, or local package
directories.

Tests may create intentionally tiny temporary files under pytest-managed
temporary directories. `data/reference/...` remains untouched by Stage 8.5.

## Example usage

```python
from pathlib import Path

from mania.preprocessing import check_preprocessing_reference_package

report = check_preprocessing_reference_package(
    Path("/path/to/local_reference_package")
)

print(report.passed)
print(report.to_dict())
```

## Future stages

Stage 9 may decide optional scientific dependencies and a local-only integration
test strategy. Stage 10 may connect residue-library options to the existing
loader and QC layer. Stage 11 and later may begin topology or trajectory loading
after explicit dependency decisions.
