# MANIA/WANIA Data Sources

## Purpose

This document records where MANIA/WANIA input data will be stored and how local
data should be organized during development.

This is documentation only. It does not implement downloading, syncing, parsing,
validation, preprocessing, or any other data-handling logic.

## Data Storage Policy

Large molecular dynamics data must stay outside Git.

The repository should store:

- source code;
- documentation;
- configuration examples;
- tests;
- small future fixtures only if explicitly approved.

The repository must not store:

- raw trajectories;
- topology files;
- generated outputs;
- cache files;
- logs;
- local secrets or credentials.

Scientific data should be treated as external input, not as normal repository
content.

## External Source

External team storage is not configured in code at this stage.

Current placeholder:

- Source: TBD
- Owner/contact: TBD
- Access notes: TBD

A future project decision may define Yandex Disk or another shared team storage
location for raw and processed MANIA input data.

Yandex Disk integration is not implemented in MANIA code at this stage. There is
no downloader, API client, sync command, or cloud integration in the current
engineering skeleton.

## Recommended Local Layout

A possible local layout for development is:

    data/
    ├── raw/
    │   ├── normal/
    │   └── tumor/
    ├── processed/
    └── README.md

The `data/` directory is ignored by Git and should remain local.

This layout is only a recommendation for organizing local files. It is not
created automatically by MANIA, and current config validation does not require
these directories to exist.

## Relationship To Config

The example config at `configs/mania.example.yaml` uses placeholder paths such
as:

- `data/normal/system.tpr`
- `data/normal/traj.xtc`
- `data/tumor/system.tpr`
- `data/tumor/traj.xtc`

These paths document the expected shape of future local inputs.

Current config validation checks YAML structure and Pydantic model constraints.
It does not check whether topology or trajectory files physically exist.

Future QC/input checks will validate file existence and input consistency.

## Files That Must Not Be Committed

The following local directories and generated outputs must not be committed:

- `data/`
- `outputs/`
- `mania_output/`
- `cache/`
- `temp/`
- `logs/`

The following molecular dynamics and scientific data files must not be committed:

- `.xtc`
- `.trr`
- `.tpr`
- `.dcd`
- `.psf`
- `.edr`
- `.gro`
- `.pdb`
- `.xvg`
- `.cpt`

Parquet files must also stay out of Git by default:

- `.parquet`

A `.parquet` file may be committed only if it is explicitly approved as a small
test fixture.

## Future Fixtures

Small test fixtures may be added later under:

    tests/fixtures/

Fixtures require:

- an explicit task;
- review before commit;
- small file size;
- no sensitive or private data;
- clear purpose in tests.

Large scientific data must never be added as fixtures.

If a fixture exception is needed later, `.gitignore` can be updated explicitly,
for example:

    # !tests/fixtures/**/*.parquet

The exception should remain disabled until a specific fixture task requires it.

## Current Non-Goals

The current engineering skeleton does not include:

- Yandex Disk API integration;
- downloader implementation;
- cloud sync;
- real trajectory loading;
- MDAnalysis integration;
- preprocessing implementation;
- topology or trajectory validation;
- automatic local data layout creation.
