# Stage 25 — Reproducibility and Publication Hardening

## Current status

The MANIA scientific/backend CLI is operational through accepted Stage 24.G.
It includes Stage 20 protein-only preprocessing artifacts, Stage 21 static RIN
construction and related analyses, Stage 22 temporal RIN, contact fingerprints
and conformation artifacts, and Stage 24 computed PCA, PCA-based clustering,
analysis orchestration and CLI integration. See [README.md](../README.md) for
the current implementation-status overview.

Stage 25 is approved as reproducibility and publication hardening. Stage 25.A
is implemented; Stage 25.B.1 provides the run-provenance contract and in-memory
model, Stage 25.B.2 provides the preprocessing sampling adapter, Stage 25.B.3a
provides completed preprocessing emission, Stage 25.B.3b provides failed
preprocessing emission, and Stage 25.B.3c provides completed and failed analysis
emission. Stage 25.B is complete. Stage 25.C input/output artifact inventory and
opt-in checksums is the next focused step. Stages 25.C–25.G remain planned and
unimplemented; Stage 25 as a whole remains incomplete. FastAPI remains postponed.
Existing scientific semantics remain frozen unless changed by
a separate, explicitly approved task. Older v0.1 planning statements remain
historical records.

## Stage 25 objective

Stage 25 aims to make each MANIA run:

- unambiguously identifiable;
- reproducible;
- verifiable;
- suitable for later assembly into a FAIR² dataset package.

This roadmap does not claim FAIR² certification or Dataset v1.0 readiness.

## Stage decomposition

- Stage 25.A — Software identity and release metadata (implemented)
- Stage 25.B — Run provenance and effective sampling (25.B.1–25.B.3c implemented; complete)
- Stage 25.C — Input/output artifact inventory and opt-in checksums (next)
- Stage 25.D — Unified artifact validation
- Stage 25.E — PBC audit and runtime metadata
- Stage 25.F — Reproducibility documentation and FAIR² bridge
- Stage 25.G — Validation and technical-hardening acceptance

Stage 25.A and Stage 25.B.1–25.B.3c are implemented. Stages 25.C–25.G require
separate, focused implementation and acceptance steps.

## Stage 25.A status — implemented

Stage 25.A provides `src/mania/_version.py` as the single package-version
source; dynamic Setuptools package/build metadata reads the same version.
`mania.__version__` remains publicly available. The immutable
`SoftwareIdentity` returned by `get_software_identity()` exposes the version,
exact checkout commit as a full lowercase 40-character SHA, commit source,
and working-tree status (`clean`, `dirty`, or `unavailable`), with a JSON-safe
`to_dict()` representation containing no local paths. Git metadata is collected
lazily only when the function is called, validating the module's source-checkout
location independently of the process working directory. Missing Git or checkout
metadata, failed commands, and timeouts safely report unavailable Git fields;
a valid commit is preserved if only the status lookup fails. Wheel installations
without checkout metadata report Git fields as unavailable (`commit_sha` is
`None`). Imports and version commands do not inspect Git. Existing version CLI
output remains `mania-wania 0.1.0`.

Stage 25.A alone does not provide run provenance, effective sampling, checksums,
artifact inventory, PBC audit, runtime metrics, or FAIR² package generation.
Provenance emission belongs to Stage 25.B below; no existing manifest is changed.
Stage 25 as a whole remains incomplete.

## Stage 25.B status — complete

Stage 25.B.1 implements the additive run-provenance contract, root in-memory model,
validation, and deterministic JSON-safe conversion. See
[`docs/run_provenance_contract.md`](run_provenance_contract.md).

Stage 25.B.2 implements the preprocessing sampling adapter: requested sampling
is copied from existing options, and effective metadata is collected from
retained frame observations and available source frame counts. Its result is
in-memory only.

Stage 25.B.3a implements the atomic writer, completed preprocessing provenance
builder, and automatic successful preprocessing CLI emission of
`<output>/run_provenance.json`. Successful stdout, verbose stage messages,
existing manifests, and scientific behavior remain unchanged.

Stage 25.B.3b implements failed preprocessing provenance construction and
best-effort emission after covered workflow-stage failures. Requested sampling,
retained effective observations, and references to earlier successful outputs
are preserved without replacing the original workflow failure.

Stage 25.B.3c implements completed and failed analysis provenance at
`<output>/analysis/run_provenance.json`, separate from root preprocessing
provenance and `analysis/extended_metrics.json`. Analysis run IDs derive from
the UTC start timestamp. Portable command and configuration snapshots describe
the request; completed runs reference existing outputs and failed runs claim no
partial artifacts. Analysis sampling stays empty because upstream observations
belong to preprocessing provenance. The analysis passport is a latest-run record
in the existing mutable output directory.

Stage 25.B acceptance covers both workflows, output-location separation,
unchanged CLI summaries and original failure behavior, and preserved manifests,
scientific schemas, and calculations. Stage 25.B is complete; Stage 25.C
input/output artifact inventory and opt-in checksums is next. Stage 25 as a whole
remains incomplete.

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

The following remain outside the implemented Stage 25.A–25.B hardening scope and
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
