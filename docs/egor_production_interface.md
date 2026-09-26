# Egor production interface

The supported `mania production` commands select a single catalog trajectory or
replica group. They reuse existing MANIA preprocessing, inclusive temporal
planning, D.4d persistence/replay, Stage 32 QC and Stage 31 aggregation. They do
not prepare coordinates or publish a Dataset. Dataset v1 remains unreleased;
each execution still requires the reviewed input authority and separate final QC.

The recipient entry point is now `./run_egor_all.sh EGOR_DATA_DIR OUTPUT_DIR`;
see the [Russian quick-start](egor_handoff_quickstart_ru.md). A normal FAIR
checkout contains the reviewed runtime authority in `production/egor_runtime/`.
No delivery archive, manual JSON, entered hashes or trajectory selection is
required. The launcher records the actual Git HEAD and installed versions.
It orchestrates existing source binding, preparation, confirmation, production
validation and execution without adding scientific implementations.

## Batch preparation, review and retry

Normal operation selects exactly 0SS/1SS/2SS × r1/r2/r3. The source inventory
maps its logical `egor/` mount to the first argument; paths below that mount
are literal. All nine source sets must exist and pass exact system/run/control
checks before any preparation. PSF/CONF/OUT/XSC and toppar hashes are checked;
DCD/header/full-axis correspondence is verified by the existing preparation tool.
A missing DCD error names its trajectory, expected path and run declaration.

The launcher creates a private hard-link view beneath
`EGOR_DATA_DIR/.mania_egor/<output-key>/production/`, copies only the small tracked
runtime authority, and prepares each trajectory there. It never copies raw DCD
payloads. Input storage must be writable and support hard links for every selected
source file. Cross-filesystem links fail explicitly. Neither input nor output
may contain the other, and source symlinks may not escape the input directory.
The existing preparation and production containment rules remain unchanged.
Original source identities are checked again before confirmation and execution,
including sources replaced after their hard links were created.

Preparation is serial. Any failed check stops the batch before new production.
After all preparations pass, the launcher shows each result, source/run/PSF paths
and summary/report locations. It asks once for a nonblank reviewer name, review
note and explicit `y` approval. No default reviewer or automatic approval exists.
Each separate existing `confirm` receives its own actual report hash. All
confirmations and public production preflights must pass before new contacts run.
DCD has no atom labels; the human still reviews source/run/PSF correspondence.

Each trajectory has its own `OUTPUT_DIR/production/trajectories/<id>/attempt_NNNN/`
with a separate production root. Each invocation has a unique directory under
`OUTPUT_DIR/production/launcher/`, retaining Git SHA, Python/MANIA/MDAnalysis
versions, source binding, authority inventory, commands, stdout/stderr, exit codes,
review and final completed count. Preparation logs and full source/prepared
identity evidence stay under `.mania_egor/`; retain both trees and raw sources.

Repeating the same two-argument command verifies/reuses completed results via
`production run --resume`, including strict validation/replay. Corruption or
changed sources fails; it is never silently accepted. A partial contact run is
preserved and a fresh numbered attempt is selected. No mid-frame resume exists.
An unchanged completed preparation declined with `N` can be reviewed again.
If a later trajectory fails, earlier completed results remain intact and the
launcher reports N/9 completed. All-completed reruns need no new human approval.

Disk preflight budgets the pending prepared DCD estimates plus 12 GB on input
storage, and checks a 12 GB floor on output storage. This is a threshold, not a
reservation or contact-output size estimate. Preparation/production are heavy:
on a cluster, run inside a compute allocation/node, never a login/management node.
No scheduler submission or cluster resource values are supplied.

## Commands and roots

Set `MANIA_DATA_ROOT` to an existing input directory. Scientific files, controls,
QC evidence and their explicitly bound dependencies must resolve below that
root. Choose a separate output root; neither root may contain the other.
Catalog and CSV metadata may live in the checkout. No working-directory search,
source relocation, automatic path expansion or pilot fallback occurs.

```bash
mania production validate --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id "$TRAJECTORY_ID" --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET"

mania production run --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id "$TRAJECTORY_ID" --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET"

mania production run --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id "$TRAJECTORY_ID" --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET" --resume

mania production assemble-group --catalog production/dataset_v1/dataset.yaml \
  --replica-group-id "$REPLICA_GROUP_ID" --output-root "$OUTPUT_ROOT" \
  --qc-manifest "$QC_MANIFEST"
```

`run` requires a positive byte budget. `validate` and `assemble-group` accept a
nonnegative budget, defaulting to zero (report/check available space without
reserving a minimum). This threshold is a user-supplied storage budget, not an
estimate or reservation: sparse contact output size is data-dependent. Check
storage for external preparation separately. Preflight streams bound files for
SHA256 integrity; it does not import MDAnalysis or calculate contacts.

Results are JSON. Blocking errors, unresolved group QC and pending review have
exit status 1. Successful preflight has `trajectory_pbc_qc_certified=false`.
No validation outcome certifies physical atom order or PBC quality automatically.

## Strict catalog and binding

The reader accepts the exact Dataset v1 catalog v1.1 descriptor and CSV columns,
33 distinct trajectory IDs, 19 systems, expected population and replica counts,
and the approved temporal requests. It rejects duplicate YAML/CSV identities,
unknown fields, conflicting groups and legacy/pilot temporal substitution.
Source existence is checked only for selected work, so unrelated incomplete
Alina/GROMACS inputs do not block Egor. Execution is initially Egor NAMD only.

`--input-binding` is an explicit externally reviewed JSON document below the
data root. Its exact fields are:

| Field | Value |
| --- | --- |
| `schema_version` | `mania.production_input_binding.v0.1` |
| `dataset_id` | Exact catalog Dataset identity |
| `catalog_row` | Complete selected CSV row, preserving every cell as a string |
| `temporal_policy` | Exact catalog inclusive-policy object |
| `files` | Exact role-to-file-record mapping below |
| `prepared_lineage` | Exact attestation below |

Every file record has exactly `path` (relative POSIX path below the data root),
`size_bytes` (positive integer), and `sha256` (64 lowercase hex characters).
The exact required roles are:

```text
topology_path trajectory_path config_path log_path box_path
element_control time_control canonical_mapping biological_annotations partner_metadata
prepared_trajectory prepared_time_control pbc_evidence
```

`trajectory_path` and `time_control` identify raw authority;
`prepared_trajectory` and `prepared_time_control` identify the derivative actually
consumed by MANIA. `files` explicitly rebinds catalog roles, including newly
supplied controls, without editing the catalog or guessing delivery names.
The retained complete `catalog_row` ties this reviewed binding to one selection.
Catalog readiness is historical metadata; successful execution requires current
verified inputs and authority, regardless of that historical status.

`prepared_lineage` has exactly these fields:

```text
protocol: unwrap_bonded_fragments_center_protein_wrap_complete_fragments
internal_mic: false
atom_order_preserved: true
frame_order_preserved: true
topology_sha256: <bound topology digest>
raw_trajectory_sha256: <bound raw DCD digest>
prepared_trajectory_sha256: <bound prepared DCD digest>
frame_count: <full source and prepared frame count>
atom_count: <common atom count>
reviewer: <external authority>
note: <scope and basis of the external attestation>
```

`pbc_evidence` identifies the corresponding external preparation/audit report.
The binding and report are supplied authority; this command does not issue that
authority. All their bytes are bound before execution. The initial interface
requires a distinct prepared file, unchanged atom/frame order and the full raw
time axis. Both DCD controls must pass the existing NAMD `validate_time` contract;
the runtime additionally checks the prepared DCD's actual header/times. Derivatives
with cropped/reindexed frames or incompatible headers are unsupported. Nothing
silently rewrites embedded control paths or transfers raw authority to a new path.

Element definitions must match the exact PSF/type population and reviewed toppar
sources. Both time controls must bind the selected CONF/OUT files. Mapping and
partner metadata use their existing strict readers, with topology applicability
attested by the source-bound input binding; annotations must match the Dataset
system. Runtime molecular-partner checks remain unchanged. No classifications,
residue lists or cross-replica correspondence are inferred.

The generated preprocessing manifest supplies optional paired
`namd_element_control_path` and `namd_time_control_path`, existing mapping,
annotation and partner paths, and `production_input_binding_path`. These controls
are inventoried and technically validated. Legacy manifests omit the new fields
and retain their previous behavior. General preprocessing remains usable with
NAMD controls independently of this production wrapper.

## Science and completed-stage resume

Egor uses the explicit `mania.window_boundaries.inclusive.v1` profile: 5–100 ns,
200 ps, 2 ns windows and 1 ns steps. This requests 476 samples and 94 complete
windows with 11 targets each. Raw write cadence does not replace the analysis
stride. No five-frame selection is applied. Missing resolved samples retain
existing coverage/episode semantics; Stage 32 retains its 95% policy.

The wrapper runs existing protein contacts, specialized layers from explicit
metadata, canonical/annotated exports and D.4d per-frame persistence. Rg is not
requested by this narrow contact-science interface. Existing graph diagnostics
and technical metadata remain in the preprocessing workflow. Internal MIC stays
disabled; the existing observation-only PBC audit does not become external PBC
approval. The binding provides separate external preparation lineage.

```text
OUTPUT_ROOT/trajectories/TRAJECTORY_ID/
  request.json
  inputs/preprocessing.json
  preprocessing/             existing science, per-frame and technical artifacts
  science_complete.json      protected completion record

OUTPUT_ROOT/groups/REPLICA_GROUP_ID/attempts/INPUT_DIGEST/
  request.json
  qc/                        Stage 32 evidence and decisions
  qc_complete.json
  aggregation/               Stage 31 outputs, only after resolved QC
  aggregation_complete.json
```

Fresh runs exclusively claim their trajectory directory. Existing output is
rejected without `--resume`; no overwrite option is exposed. Resume verifies
catalog/binding identity, every bound input hash, the generated manifest, complete
artifact validation, D.4d completion and replay, and hashes of accepted outputs.
It does not load trajectories or compute geometry. A completed preprocessing run
whose final wrapper marker was interrupted can be validated and marked complete.
An incomplete/failed preprocessing run cannot be resumed midway or overwritten;
retain it and use a new output root for a fresh attempt. Changed inputs require
a new root. No stage completion is inferred from sparse CSV rows.

## Explicit technical subsets

`production validate` and `production run` accept `--technical-manifest FILE`.
This optional strict JSON control narrows only the selected catalog trajectory's
execution interval. It does not replace the catalog or its input binding.
Without the option, production behavior and output layout are unchanged.

The complete v0.1 manifest for the Egor 0SS/r1 5–8 ns technical validation is:

```json
{
  "schema_version": "mania.production_technical_run.v0.1",
  "purpose": "technical_validation",
  "trajectory_id": "namd_egor_wt_0ss_r1",
  "start_ns": 5,
  "end_ns": 8
}
```

All five fields are required. Unknown fields, duplicate JSON keys, other schema
versions/purposes, multiple or mismatched trajectory IDs, booleans, numeric
strings and nonfinite times are rejected. Start/end must form a positive proper
subset of the catalog interval: either endpoint may equal its catalog endpoint,
but the full unchanged interval is forbidden. At least one inherited full window
must fit. Only `start_ns` and `end_ns` are execution overrides; even redundant
stride, window, overlap or boundary-policy fields are rejected.

The catalog and binding retain 5–100 ns. Execution inherits 200 ps stride,
2 ns window length, 1 ns step, 50% duration overlap, and
`mania.window_boundaries.inclusive.v1`. With all requested source times available,
5–8 ns selects **16 samples**, with **two inclusive windows [5,7] and [6,8]**,
**11 expected samples per window**, and **six shared samples**. Missing samples
retain the existing temporal semantics; the subset option does not synthesize them.

```bash
mania production validate --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id namd_egor_wt_0ss_r1 --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --technical-manifest "$TECHNICAL_MANIFEST"

mania production run --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id namd_egor_wt_0ss_r1 --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --technical-manifest "$TECHNICAL_MANIFEST" \
  --min-free-bytes "$FREE_SPACE_BUDGET"

mania production run --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id namd_egor_wt_0ss_r1 --output-root "$OUTPUT_ROOT" \
  --technical-manifest "$TECHNICAL_MANIFEST" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET" --resume
```

The technical manifest is metadata and may live outside `MANIA_DATA_ROOT`, like
the catalog. Every original input-binding, full-axis time, element, mapping,
annotation, partner and prepared-input authority check remains mandatory. The
prepared trajectory must still retain its complete frame/atom order and time axis.

Technical outputs reside at
`OUTPUT_ROOT/technical_validation/trajectories/TRAJECTORY_ID/`. Their request uses
`mania.production_technical_request.v0.1` and retains both the catalog spec and
effective execution spec, the manifest payload, and its original-byte SHA256.
The request, result, completion marker and preprocessing provenance identify
`purpose=technical_validation` and `production_eligible=false`. Completion is
`technical_complete.json`, with result status `technical_complete`; no production
`science_complete.json` is issued. The preprocessing provenance's `technical_run`
record preserves the same context when that directory is relocated.

Resume requires the explicit manifest again with identical bytes, including
whitespace. An identical copy at a different path is acceptable. Changed intervals,
changed bytes, changed saved controls or changed technical provenance fail without
rerunning geometry or overwriting evidence. A different technical request requires
a new output root. A normal production run can coexist in its separate original
`trajectories/` tree.

`assemble-group` accepts only completed catalog production science and rejects
technical results, including a technical tree supplied as the output root or
copied into the production layout. `mania dataset publish` rejects input paths
inside technical requests or preprocessing trees bearing technical provenance,
including relocated preprocessing directories. Preserve the complete technical
provenance with artifacts; isolated CSV rows are not production authority.
Technical completion supplies no Stage 32 QC decision or publication eligibility.

## Replica group and QC boundary

Assembly requires all expected catalog replicas to have validated completed
science and compatible inclusive windows. Supply an existing strict Stage 32 QC
manifest whose template references those exact canonical files and windows.
Its evidence must cover the exact member identities and their retained sampling
plans. Technical preflight does not fabricate manual review or RMSD evidence.

Protein aggregation is required. Specialized aggregation is selected by the
template's specialized canonical input paths; each requested family requires
explicit partner correspondence. The wrapper uses `run_dataset_qc`, verifies the
exact result of `build_qc_derived_replica_aggregation_manifest`, and calls
`run_replica_aggregation`. Every stage requires `status=passed`, `complete=true`
and no unsupported validation roles, with all external inputs mapped explicitly.

Missing QC returns a blocker while preserving trajectory science. Unresolved
REVIEW retains a completed QC attempt without aggregation. A changed manual
resolution creates a different digest-named group attempt; earlier evidence is
preserved. An identical completed group attempt is validated and reused. Partial
stage outputs are never overwritten. `mania dataset publish` remains separate.

## Delivery and installation

Use the HTTPS clone and ordinary editable installation in the Russian quick-start:

```bash
git clone https://github.com/2Myaka2/MANIA_WANIA.git
cd MANIA_WANIA && git checkout FAIR
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[md]"
./run_egor_all.sh /path/to/Egor /path/to/results
```

No detached commit, delivery ZIP, wheelhouse, overlay or PYTHONPATH hook is part
of this workflow. Dependency installation needs access to the configured package
index. An installation/network failure is a blocker, not permission to silently
substitute a different installation procedure. Stable UTC/NTP is required by
existing provenance checks; those checks are not weakened by the launcher.

The [tracked runtime subset](../production/egor_runtime/README.md) preserves
reviewed authority records byte-for-byte, including historical provenance fields.
Those historical paths never become runtime dependencies. Its regenerated
`HANDOFF_FILES.sha256` describes only the tracked subset; packaging fields inside
the retained historical manifest are provenance. The launcher verifies/copies
this subset automatically. Historical evidence and helper scripts are excluded.

## Nine-trajectory authority and remaining work

Each system's replicas share its byte-identical PSF, 690-residue mapping,
element definitions, annotations and partner metadata. Partner indices remain
specific to each system; element and time templates remain replica-specific.
Their recorded intake readiness does not replace preparation at the execution
site. The checkout includes no DCD, PSF, CONF/OUT/XSC or toppar payload: Egor
supplies his own raw files. Seven DCDs were absent at local intake; no full
nine-trajectory scientific execution is claimed by the software handoff.

For acceptance testing only, the advanced launcher option
`--TEST-0ss-r1-5-8ns` selects raw 0SS/r1 with the existing technical manifest in
`production/egor_runtime/technical_0ss_r1.json`. It still performs fresh full-axis
preparation and requires explicit human review. Its output/preparation namespaces
are separate (`test_0ss_r1`), and the existing production interface labels its
16-sample, two-window output ineligible for production aggregation/publication.
This option is absent from the normal recipient quick-start.

Full 5–100 ns calculations, final QC, authoritative exclusions/availability,
specialized partner correspondence, aggregation and publication remain distinct
work. This launcher neither aggregates nor publishes.
