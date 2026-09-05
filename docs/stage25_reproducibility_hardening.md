# Stage 25 — Reproducibility and Publication Hardening

## Current status

The MANIA scientific/backend CLI is operational through accepted Stage 24.G.
It includes Stage 20 protein-only preprocessing artifacts, Stage 21 static RIN
construction and related analyses, Stage 22 temporal RIN, contact fingerprints
and conformation artifacts, and Stage 24 computed PCA, PCA-based clustering,
analysis orchestration and CLI integration. See [README.md](../README.md) for
the current implementation-status overview.

Stage 25 is approved as reproducibility and publication hardening. Stage 25.A
is underway; Stage 25 functionality is not yet fully implemented. Existing
scientific semantics remain frozen unless changed by a separate, explicitly
approved task. Older v0.1 planning statements remain historical records.

## Stage 25 objective

Stage 25 aims to make each MANIA run:

- unambiguously identifiable;
- reproducible;
- verifiable;
- suitable for later assembly into a FAIR² dataset package.

This roadmap does not claim FAIR² certification or Dataset v1.0 readiness.

## Stage decomposition

- Stage 25.A — Software identity and release metadata
- Stage 25.B — Run provenance and effective sampling
- Stage 25.C — Input/output artifact inventory and checksums
- Stage 25.D — Unified artifact validation
- Stage 25.E — PBC audit and runtime metadata
- Stage 25.F — Reproducibility documentation and FAIR² bridge
- Stage 25.G — Validation and technical-hardening acceptance

These are approved work areas, not a claim of complete implementation. Each
requires separate, focused implementation and acceptance steps.

## Stage 25.A implementation note

Stage 25.A.2 provides `src/mania/_version.py` as the single package-version
source; package/build metadata reads the same version. The immutable
`SoftwareIdentity` returned by `get_software_identity()` exposes the version,
exact checkout commit, commit source, and working-tree status, with a JSON-safe
`to_dict()` representation. Git metadata is collected lazily when the function
is called, using the module's source-checkout location. Wheel installations
without checkout metadata report Git fields as unavailable (`commit_sha` is
`None`). Existing version CLI output remains `mania-wania 0.1.0`.

No `run_provenance.json` is produced yet, and no existing manifest is changed.
This step does not complete Stage 25.A or Stage 25 as a whole.

## Compatibility rules

- Prefer additive changes.
- Preserve existing CLI behavior unless a separately approved task explicitly
  changes it.
- Preserve `mania_manifest.json`.
- Preserve `extended_metrics.json`.
- Preserve existing Stage 20–24 scientific artifact schemas.
- Preserve existing Stage 20–24 scientific rows and calculation semantics.
- Do not add a new dependency without explicit approval.
- Software releases and dataset releases are separate concepts.
- Stage 25 must not silently replace existing manifests or schemas.

## Frozen scientific scope

The following remain outside the current Stage 25.A software-identity task and
require separate scientific or architectural approval:

- contact lifetime;
- contact episode statistics;
- a new interaction-strength formula;
- PBC-aware scientific distance correction;
- physical-time window semantics;
- replica-level aggregation;
- condition-level aggregation;
- cross-engine canonical residue mapping;
- protein-lipid interactions;
- protein-glycan interactions;
- final Dataset v1.0 schemas;
- final Dataset v1.0 package generation;
- final Croissant metadata;
- FastAPI;
- database or worker infrastructure;
- WANIA redesign.
