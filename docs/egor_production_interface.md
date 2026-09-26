# Egor production interface — Stage 34.D.4e.2 / D.4e.3

The supported `mania production` commands select a single catalog trajectory or
replica group. They reuse existing MANIA preprocessing, inclusive temporal
planning, D.4d persistence/replay, Stage 32 QC and Stage 31 aggregation. They do
not prepare coordinates or publish a Dataset. Dataset v1 remains unreleased;
this implementation does not authorize Stage 35 or supply real scientific authority.

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
  --min-free-bytes "$FREE_SPACE_BUDGET" --resume

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
  --min-free-bytes "$FREE_SPACE_BUDGET" --resume
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

## Current data boundary

Software tests use synthetic controls/runtimes, all nine real catalog selections,
and existing QC/aggregation APIs. They are not Egor scientific acceptance.
The catalog records seven missing Egor DCD deliveries, one authority-blocked
1SS/r1 row, and one 0SS/r1 row with verified prepared-input readiness. Egor has
now supplied separate complete 0SS and 1SS annotation decisions. Other input
controls, real QC and specialized correspondence remain separate gates;
historical pilot acceptance cannot supply them by analogy.

## Real 0SS/r1 prepared-input checkpoint

Stage 34.D.4e.3 evidence is retained under the ignored directory
`local_md/stage34d4e3_egor_0ss_r1_20260926T061309Z_49d690e736a84bb7a5b58f4825e787c1/`
with a sibling ZIP. Operational inputs are under
`local_md/production_intake/prepared_inputs/` followed by the same checkpoint name.
The ZIP contains controls, scripts, inventories, lineage, audit and verification
records; large raw/prepared DCDs remain local and are referenced by path/hash.

Both new system annotation controls bind `napi2b-dataset-v1`, respectively
`namd_egor_wt_0ss` and `namd_egor_wt_1ss`, with source/verifier `Egor` and
`annotation_scope=complete_for_system`. Each lists Asn295/Asn308 with FA2G2S2
present, design sites C303/C322/C328/C350, and no cysteine variant sites.
Design-site annotation does not encode actual bond pairs. Separate PSF evidence
records no SG–SG bonds for 0SS and C303–C350 for 1SS.

0SS/r1 has an exact 96-type element control, 690-residue canonical relation with
its own PSF binding, and topology-specific metadata for 828 membrane partners
and two glycans. No 2SS atom/partner indices were copied. All shared CHARMM
definitions were revalidated against the actual source bytes and membership.

The prepared DCD preserves all 1000 frames and 409865 atoms. External preparation
uses the approved fragment protocol, with protein geometry centering and
complete-fragment COG wrapping. A batched implementation of the installed
MDAnalysis operations was checked bitwise against the standard protocol at
source frames 0, 49, 79 and 999. Four workers feed one ordered writer. Every
frame passes bond/image/cell/centering checks; every persisted coordinate array
matches its indexed writer hash. Both time controls bind the original CONF/OUT
and retain exact scientific times of 100–100000 ps. Internal MIC stays false.

The following public preflight passed with exit 0 and created no science output:

```bash
CHECKPOINT=stage34d4e3_egor_0ss_r1_20260926T061309Z_49d690e736a84bb7a5b58f4825e787c1
export MANIA_DATA_ROOT="$(pwd)/local_md/production_intake"
.venv/bin/mania production validate \
  --catalog production/dataset_v1/dataset.yaml \
  --trajectory-id namd_egor_wt_0ss_r1 \
  --output-root "local_md/$CHECKPOINT/preflight_output" \
  --input-binding "$MANIA_DATA_ROOT/prepared_inputs/$CHECKPOINT/production_input_binding.json"
```

Its result is `preflight_passed`, with `trajectory_pbc_qc_certified=false`.
The binding selects the complete derivative; diagnostic partial files are never
production inputs. No contacts, Stage 32, aggregation or publication were run.

At this checkpoint, a **5–8 ns-only** real contact test was blocked by software
selection. The explicit technical-subset interface documented above now supplies
that selection while catalog v1.1 still requires Egor 5–100 ns. Cropping the
prepared file or changing the catalog end to 8 ns remains invalid. The interface
was verified with synthetic runtimes only; no real MD, QC, aggregation or
publication run is authorized or performed by this software change.
