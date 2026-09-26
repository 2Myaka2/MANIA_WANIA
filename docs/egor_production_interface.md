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
The catalog records seven locally missing Egor DCDs, one 1SS/r1 row awaiting
DCD runtime verification and external preparation/lineage, and one 0SS/r1 row
with accepted local prepared-input readiness. All nine now have topology-bound
system authority and portable templates. Missing local DCDs do not imply missing
scientific system authority. Real QC and specialized correspondence remain
separate gates; historical pilot acceptance cannot supply them by analogy.

## Nine-trajectory handoff

The final delivery is bound to committed repository HEAD
`e3f69331f95a42d1da5d0cf7d6a60646421b8079`:
`local_md/egor_FINAL_e3f69331f95a.zip`, with persistent verification evidence in
`local_md/egor_FINAL_e3f69331f95a/`. Send that commit, the final ZIP, and the
[Russian quick-start](egor_handoff_quickstart_ru.md). Extract the ZIP's
`egor_handoff/` directly under `MANIA_DATA_ROOT`; no tracked-file overlay is
required. The original 79 package files are retained, with deterministic
packaging/provenance updates and one added quick-start (80 files total).

The packaged catalog and reference interface document are read directly from
the recorded commit. This working-tree documentation update is not substituted
for that committed reference. The new quick-start is an explicitly identified
delivery supplement, also present in the ZIP; it is not claimed to exist at
the recorded commit. The package README and manifest record this distinction.
Historical catalog `source_head`/`catalog_basis_head` fields retain their original
meaning; `repository_head` in the handoff manifest identifies the required
checkout. `HANDOFF_FILES.sha256` covers every other package file, and the sibling
ZIP checksum covers the complete archive. Helpers, controls, templates and
scientific authority remain unchanged. Final checks read controls and templates,
verify checksums and HEAD identity, and exercise synthetic helper guards only.
No MD, QC or aggregation is run during packaging.

The earlier authority-build evidence remains at
`local_md/egor_9_trajectory_handoff_20260926/handoff/`; the evidence ZIP is
`local_md/egor_9_trajectory_handoff_20260926.zip`.
That historical ZIP includes `handoff/handoff_manifest.json`, `handoff/README.md`,
`handoff/catalog/`, `handoff/controls/`, `handoff/authority/`, `handoff/templates/`
and the strict verification/materialization helpers. The archive inventory lists
every exact file and checksum. Raw inputs, toppar and prepared DCDs are referenced
by identity and are not included. No DCD was downloaded or copied for this task.

All three replica PSFs within each system have the same complete SHA256:

| System | PSF SHA256 | Actual topology bonds |
| --- | --- | --- |
| 0SS | `89d521cf033bf1a0e01ec80d5ee5f74037ad46a68167297e1e4950a56e794417` | none |
| 1SS | `c81688aaff64bd7342a19896581f14b90a22e4b8b1dbe4f2157392685a4846f9` | C303–C350 |
| 2SS | `04b7bee588edf61bde25dfded24216ed4e0727d75d1e144356b500ecc89004bb` | C303–C350 and C322–C328 |

Each system shares its own 690-residue canonical mapping, element definitions,
complete annotations and molecular partner metadata across its replicas.
Partner membership was independently enumerated from each system's PSF and
checked against exact shared toppar definitions; 2SS indices were not copied
into 0SS/1SS. Nine element templates bind the individual replica PSF paths,
because the runtime reader requires exact path identity even for identical bytes.
Time and preparation attestations remain replica-specific.

0SS/1SS annotations have source/verifier `Egor`, glycosylation sites `[295,308]`
with FA2G2S2 at both, design sites `[303,322,328,350]`, and empty cysteine variant
sites. These design annotations do not encode S–S bond pairs. Accepted complete
2SS annotations are rebound to the production identity with provenance retained.

Install `handoff/` as `MANIA_DATA_ROOT/egor_handoff/`. Supply each row's own
PSF/CONF/OUT/XSC under `MANIA_DATA_ROOT/egor/`, and the reviewed shared `toppar/`
there. Preserve declared filenames and verify source hashes using the manifest.
The seven absent DCD paths retain the exact non-NPT CONF/OUT declarations;
the two observed DCDs retain their NPT delivery names. If the execution-site
delivery name differs, record the explicit path and verify its linkage to the
selected CONF/OUT. Never substitute a historical pilot trajectory.

Before `mania production validate`, Egor must complete each row's checklist:

1. Verify the supplied small-source identities and shared toppar hashes. Supply
   the exact raw DCD; check its bytes/hash, header, full frame/cell integrity,
   physical atom order and CONF/OUT linkage. Missing DCD templates contain no
   invented bytes, header observations or validated runtime time control.
2. Complete raw and prepared time controls from actual local observations. Each
   CONF/OUT independently supplies 1000 writes, 2 fs steps, 50000-step cadence,
   and the 100–100000 ps axis. XSC supplies the final 50000000-step cell only.
3. Supply a distinct full-axis derivative prepared with the approved external
   fragment protocol, reviewed PBC audit and named atom/frame-order attestation.
   The accepted 0SS/r1 derivative may be reused only when its exact bytes and
   evidence are available and verified. The other eight have no intake-bound
   prepared-input acceptance in this package.
4. Materialize embedded absolute paths and final file hashes, retain the exact
   catalog row, then strict-read the final existing-schema input binding. Follow
   the package README/helpers; `.template.json` files intentionally fail the
   production binding reader until completed. No template grants a PBC PASS.
5. Check **stable UTC/NTP before unattended runs**, storage budget and disjoint
   input/output roots. Run the supported `production validate` command with the
   completed binding. No host UTC fix is included in code.

The catalog's `READY` remains local prepared-input readiness for 0SS/r1;
`NEEDS_AUTHORITY` for 1SS/r1 now means execution verification/preparation is
pending, and seven `MISSING_FILES` rows mean local DCD absence. All three groups
remain incomplete. This handoff runs no MD, contact science, QC or aggregation
and does not authorize Stage 35.

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

Its historical result is `preflight_passed`, with `trajectory_pbc_qc_certified=false`.
The binding selects the complete derivative; diagnostic partial files are never
production inputs. No contacts, Stage 32, aggregation or publication were run.

The nine-row handoff updates the catalog, so the historical command above needs
the refreshed binding
`$MANIA_DATA_ROOT/egor_handoff/local_0ss_r1/production_input_binding.json`.
The original binding remains valid only with its frozen historical catalog row.
The refreshed local binding reuses accepted input identities; it is not a new
DCD audit. Portable execution sites must complete their own handoff template.

At this checkpoint, a **5–8 ns-only** real contact test was blocked by software
selection. The explicit technical-subset interface documented above now supplies
that selection while catalog v1.1 still requires Egor 5–100 ns. Cropping the
prepared file or changing the catalog end to 8 ns remains invalid. The interface
was verified with synthetic runtimes only; no real MD, QC, aggregation or
publication run is authorized or performed by this software change.
