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
emission. Stage 25.B is complete. Stage 25.C.1 implements the additive
artifact-inventory contract, streaming opt-in SHA256 primitives, and atomic
inventory writing. Stage 25.C.2 preprocessing integration and Stage 25.C.3
analysis integration are implemented. Stage 25.C is complete. Stage 25.D.1
integrity/reference validation is implemented as a Python API. Stage 25.D.2
specialized-validator coordination and CLI are implemented; Stage 25.D is complete.
Stage 25.E.1 observation contracts are implemented. Stage 25.E.2 workflow
integration is next and remains planned; Stage 25.E remains incomplete.
Stages 25.F/G remain planned and unimplemented;
Stage 25 as a whole remains incomplete. FastAPI remains postponed.
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
- Stage 25.C — Input/output artifact inventory and opt-in checksums (25.C.1–25.C.3 implemented; complete)
- Stage 25.D — Unified technical artifact validation (D.1 and D.2 implemented; complete)
- Stage 25.E — PBC audit and runtime metadata (E.1 implemented; E.2 next; incomplete)
- Stage 25.F — Reproducibility documentation and FAIR² bridge
- Stage 25.G — Validation and technical-hardening acceptance

Stage 25.A, Stage 25.B.1–25.B.3c, Stage 25.C.1–25.C.3, Stage 25.D.1–D.2, and
Stage 25.E.1 are implemented. Stages 25.E.2–25.G require separate, focused
implementation and acceptance steps.

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
scientific schemas, and calculations. Stage 25.B is complete. Stage 25.C is
complete as described below; Stage 25 as a whole remains incomplete.

## Stage 25.C status — complete

Stage 25.C.1 implements the independently versioned additive artifact-inventory
contract, immutable models, explicit file-specification builder, streaming
opt-in SHA256 primitives, and atomic inventory writing. See
[`docs/artifact_inventory_contract.md`](artifact_inventory_contract.md).

Default inventory construction records exact byte sizes using file metadata only,
without opening or reading file contents. SHA256 requires explicit Python API
or preprocessing/analysis CLI opt-in. Specifications are caller-supplied; no
output-directory scanning occurs. The inventory excludes itself and its own
checksum and remains separate from provenance, manifests, and scientific artifacts.

Stage 25.C.2 preprocessing inventory integration is implemented. Normal
`mania preprocessing run-graph-export` execution automatically writes
`<output>/artifact_inventory.json` using `--artifact-checksum-mode none` by
default: exact sizes only, with no inventory content reads. Explicit
`--artifact-checksum-mode sha256` streams all inventoried files, including
potentially multi-gigabyte trajectory inputs, and may be expensive. Authoritative
retained inputs and successful output results supply the file list; no directory
scanning or scientific schema changes occur.

Inventory excludes itself and run provenance. Successfully written inventory is
referenced by completed or failed preprocessing provenance without a schema
change. Covered scientific failures attempt inventory only with complete retained
inputs and claim only earlier successful outputs. Inventory failure after
scientific success returns exit 1 with completed provenance still attempted;
inventory failure during a failed workflow preserves the original failure.

Stage 25.C.3 analysis inventory integration is implemented. `mania analyze`
automatically writes `<output>/analysis/artifact_inventory.json`, with size-only
`none` as default and streaming SHA256 as explicit opt-in through the same flag.
The public resolver supplies authoritative inputs once for execution and
inventory; completed result paths supply outputs. Failed runs with resolved
inputs get input-only inventory. Earlier failures get no inventory. Analysis
provenance links inventory only after successful writing. Neither root
preprocessing technical file is modified, including with equal input/output roots.

Stage 25.C acceptance covers generic C.1 compatibility, preprocessing and analysis
in both checksum modes, conservative failure handling, separate technical metadata
locations, no directory scanning, and unchanged manifests, scientific results,
CLI summaries, and dependencies. Stage 25.C is complete.

## Stage 25.D status — complete

Stage 25.D.1 provides strict readers for the existing inventory and provenance
contracts and a reusable Python artifact-set integrity/reference API. It checks
technical metadata, run IDs, workflows, conditions, portable references, regular
file existence, exact byte sizes, and SHA256 only when declared. External input
paths require explicit artifact-ID mappings; unavailable inputs produce a partial
technical report, not a missing-file error. Inventory excludes itself and its
corresponding provenance; source-input lineage does not imply publication
membership. See [unified artifact validation](unified_artifact_validation.md).

Stage 25.D.2 implements `validate_run_artifacts` and `mania artifacts validate`.
The coordinator calls D.1 once, then delegates existing CSV, condition, graph,
Rg, contact, and graph-pair validators for explicitly inventoried roles. Known
artifacts without matching public validators remain integrity-only. Unknown
future roles yield warnings and partial reports. Integrity failures gate content
checks. No scientific validator, schema, or calculation is changed.

Stage 25.D is complete. Stage 25.E.1 is implemented; Stage 25.E.2 is next;
Stages 25.F/G remain planned. Stage 25 as a whole remains incomplete. FastAPI
remains postponed. A technically passed report does not certify scientific
correctness or publication readiness.

## Stage 25.E status — E.1 implemented; E.2 planned; incomplete

Stage 25.E.1 provides immutable runtime/environment metadata and observation-only
PBC audit contracts, safe distribution-version collection, duration/counter
builders using supplied timestamps, and aggregation of caller-supplied sampled
frame dimensions. See [PBC and runtime metadata](pbc_runtime_metadata.md).

E.1 observes metadata only. Current MANIA distances use Euclidean selected-atom
coordinates without MANIA internal minimum-image correction. No PBC correction
has been implemented; scientific PBC status remains unresolved. Complete box
metadata with undeclared external preprocessing and no internal correction is a
valid observation audit, not a scientific verdict or validation failure by itself.

E.2 workflow integration remains planned. It will observe dimensions during
existing sampled-frame processing, reuse Stage 25.B timestamps and retained
counters, and integrate technical artifacts into provenance, inventory, and
unified validation. E.1 does not write automatic artifacts or references, add CLI
options, iterate trajectories, or change existing scientific calculations.
Stage 25.E and Stage 25 overall remain incomplete; Stages 25.F/G remain planned.

## Stage 25.G publication acceptance — planned

The ordinary unified technical validator retains `passed -> exit 0`,
`partial -> exit 0`, and `failed -> exit 1`. Stage 25.G publication acceptance
must require a **complete** technical report, equivalent to
`report.status == "passed"` and `report.complete is True`. E.1 does not implement
this publication gate or add `--require-complete`. A complete technical report
does not itself certify scientific correctness or Dataset v1.0 readiness.

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

The following remain outside the implemented Stage 25.A–25.E.1 hardening scope and
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
