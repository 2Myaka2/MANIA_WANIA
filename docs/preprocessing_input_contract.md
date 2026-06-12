# Preprocessing input contract

## Purpose

The preprocessing input manifest describes raw simulation inputs for future real
MANIA preprocessing. It records analysis conditions, topology and trajectory
paths, an output root, residue library options, and minimal timing metadata
without interpreting or loading scientific data.

## Current status

This is only a contract and typed model layer. It does not parse trajectories,
parse topology, run MDAnalysis, run GROMACS, compute contacts, compute Rg,
export backend artifacts, or modify the current workflow CLI.

Stage 8.2 is documentation and example hardening only. It does not check whether
declared scientific files exist, validate full residue-library content, connect
manifest residue-library options to residue QC, parse topology or trajectory
files, compute Rg or contacts, export backend scientific outputs, or run through
the CLI.

## Example files

Two tiny committed placeholder manifests demonstrate the contract:

- `examples/preprocessing/minimal_manifest.yaml`
- `examples/preprocessing/full_manifest.yaml`

Both examples are tested against the public
`load_preprocessing_input_manifest(...)` loader. Their declared scientific
paths are illustrative and are not expected to exist.

## Manifest shape

```yaml
output_root: tmp/mania_output
frame_time_ps: 100.0

residue_library:
  library_path: residue_library/mania_residue_library.json
  custom_residues_path: residue_library/custom_residues.json
  skip_resnames:
    - CLA
    - SOD
    - TIP3
  allow_user_overrides: false

conditions:
  - condition: normal
    topology_path: data/normal/topology.tpr
    trajectory_paths:
      - data/normal/traj.xtc
    reference_structure_path: data/normal/reference.pdb
    metadata:
      replicate: rep1

  - condition: tumor
    topology_path: data/tumor/topology.tpr
    trajectory_paths:
      - data/tumor/traj.xtc
```

These paths are illustrative. They do not imply that real trajectory, topology,
or residue-library data should be committed to this repository.

## Field descriptions

- `output_root`: planned root directory for future preprocessing outputs.
- `frame_time_ps`: optional positive, finite time interval between frames.
- `residue_library.library_path`: optional base residue library path.
- `residue_library.custom_residues_path`: optional path describing custom
  residues. The name follows the existing residue-library API's "custom
  residues" terminology.
- `residue_library.skip_resnames`: residue names reserved for later QC skipping.
- `residue_library.allow_user_overrides`: records whether future processing may
  let custom residues replace entries from the base library.
- `conditions[].condition`: case-preserving analysis condition name.
- `conditions[].topology_path`: declared topology path for the condition.
- `conditions[].trajectory_paths`: one or more declared trajectory paths.
- `conditions[].reference_structure_path`: optional reference structure path.
- `conditions[].metadata`: optional string-to-string condition metadata.

## Validation rules

- Condition names are stripped, and empty names are rejected.
- Duplicate condition names are rejected after stripping.
- Condition matching is case-sensitive.
- Path strings cannot be empty or whitespace-only.
- Declared scientific input paths are not required to exist during manifest
  validation.
- Trajectory paths must be a non-empty list or tuple, not a plain string.
- `frame_time_ps`, when provided, must be finite and positive.
- Skip residue names are stripped, uppercased, and deduplicated in input order.

## Canonical terminology

`custom_residues_path` is the canonical field for the optional custom residue
definition path. Competing names are not supported aliases.

## Future use

Later stages may use this manifest to drive local file existence validation,
residue library QC, trajectory loading, Rg computation, contacts extraction,
and backend contract export. None of those capabilities is implemented by this
contract task.

Stage 8.3 may add local declared-file existence validation for preprocessing
manifests. Stage 8.4 may add a residue-library validation bridge. Optional
scientific runtime dependencies may be introduced only in later stages after an
explicit architectural decision.

## Non-goals

- No MDAnalysis.
- No GROMACS.
- No trajectory parsing.
- No topology parsing.
- No contacts computation.
- No Rg computation.
- No residue library content validation.
- No CLI integration.
- No workflow runner integration.
- No real data committed.
