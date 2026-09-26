# Egor production interface

The supported `mania production` commands select a single catalog trajectory or
replica group. They reuse existing MANIA preprocessing, inclusive temporal
planning, D.4d persistence/replay, Stage 32 QC and Stage 31 aggregation. They do
not prepare coordinates or publish a Dataset. Dataset v1 remains unreleased;
each execution still requires the reviewed input authority and separate final QC.

The external [production input preparation tool](production_input_preparation.md)
now provides the raw-to-binding handoff step. Its `prepare` operation takes one
explicit trajectory, the reviewed authority package and site roots; it generates
the full-axis derivative, actual observations, strict time controls and an
automatic report pending review. Its separate `confirm` operation requires a
named reviewer and the exact report SHA256, rechecks integrity, and materializes
the existing binding models. It prints the concrete production validate/run
commands without running them. The recipient entry point is the supplied
[Russian quick-start](egor_handoff_quickstart_ru.md); this document is a reference.
The clean recipient validation at commit
`aa24f04900767b04f1303be18fe867e879feea93` completed real 0SS/r1 preparation,
explicit human confirmation, production preflight and the 5–8 ns technical run.
Strict artifact validation was complete and passed; direct/replay scientific
mismatches were zero, offline replay needed no trajectory/geometry access, and
identical resume reused the completed result with no geometry recomputation.
Full 5–100 ns execution is the recipient's next calculation, not a completed test.
For 1SS/r1, the same preparation path selected its own topology/controls and
passed the first-frame applicability check. Full preparation, reopening,
confirmation and contact calculation for 1SS were not validated.

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

Check out exactly `aa24f04900767b04f1303be18fe867e879feea93` and use the final
`egor_delivery_aa24f0490076/` package. Its root `COMMIT.txt` identifies the runtime
code; the supplied quick-start and reference documents are delivery supplements,
not a claim that these uncommitted documentation revisions exist at that SHA.
The nested reviewed handoff's older repository/catalog identities describe the
preserved authority snapshot, not the runtime checkout to install.

The primary installation is editable source plus the supplied local dependency
and build wheels. From the exact checkout, in a new CPython 3.12 venv:

```bash
export PIP_NO_INDEX=1 PIP_FIND_LINKS="$DELIVERY/wheelhouse"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[md]'
python -m pip check
```

These are the installation commands verified in the recipient test and rechecked
against the final wheelhouse. Online pip installation failed in that test.
The wheelhouse targets CPython 3.12, Linux x86_64 with glibc >= 2.28; it is not a
cross-platform dependency bundle. Python/venv and Git must already be available.
It includes no MANIA project wheel: MANIA imports from the exact checked-out
source, MDAnalysis and the other dependencies from the new venv. Do not use a
PYTHONPATH hook or an old project wheel to supply missing source files.

`DELIVERY_FILES.sha256` covers every other delivery file, including wheels and
the nested `HANDOFF_FILES.sha256`. The latter covers every other handoff file.
Check both before preparation, then run the unchanged `check_package.py` with
`python -B`. It strict-reads all nine selections and their controls/templates;
it does not certify local coordinates. Keep the package immutable after prepare.
The retained `materialize_binding.py` is a legacy compatibility asset, not a
recipient step: the checkout's `confirm` now creates the site review and binding.
Do not fill templates or edit generated observations, hashes, lineage or flags.

## Nine-trajectory authority and remaining work

The existing authority, three sets of system controls and all nine trajectory
templates are preserved. Each system's replicas share its byte-identical PSF,
690-residue mapping, element definitions, annotations and partner metadata.
Partner indices remain specific to each system. Element and time templates remain
replica-specific. Templates are intentionally incomplete and non-executable.
Their recorded intake readiness does not replace preparation at the execution site.

The delivery includes no DCD, PSF, CONF/OUT/XSC or toppar payload. The recipient
supplies their own files at the explicit paths listed in `SOURCE_PATHS.tsv`,
with source identities in `authority/source_inventory.json` and shared definitions
in `authority/shared_toppar.json`. Seven DCDs were absent at intake; their bytes
and observations are not claimed verified. No trajectory is substituted by filename
search. A source mismatch or an unlisted delivery path requires clarification of
the authority, not a JSON edit to force acceptance.

For each selected trajectory: prepare a fresh full-axis derivative, read the
summary, perform and record human review, confirm, then execute the generated
validate and full production run. Do not reuse a historical prepared trajectory,
runtime time control, binding, output or approval. DCD does not contain atom labels;
the reviewer must attest source/run correspondence on the available provenance,
not claim an independent DCD atom-label proof. A technical PASS is not human approval.

The quick-start records stdout/stderr and numeric exit status for prepare, confirm,
validate and run in a separate log directory. The first two also retain
`operation.log`, `phases.jsonl` and `operation.json` below their respective attempt
directories. Early failures may precede those internal logs, so preserve the shell
logs too. Every nonzero exit stops the documented flow. Check stable UTC/NTP and
free space before long work; the byte budget is not a disk reservation.

Return complete production, preparation/confirmation and log directories to
Andrey. Preserve failed attempts and use new paths for fresh attempts. Existing
`--resume` verifies/reuses completed stages; it does not resume a partial contact
pass. Full 5–100 ns runs, the remaining trajectory preparations, final QC,
replica availability/exclusions, specialized correspondence, aggregation and
publication remain separate work. Do not aggregate replicas in this handoff.
