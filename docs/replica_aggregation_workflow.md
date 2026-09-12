# Dataset canonical replica aggregation — Stage 31.D

**Stage 31.D: PASS. Stage 31: COMPLETE.**
Stage 25, Stage 26, Stage 27, Stage 28, Stage 29 and Stage 30 are complete.
Stage 32 Dataset QC / exclusion is next and has not started. Stage 33 publication
export, Stage 34 multi-engine pilot and Stage 35 full production remain later.
Dataset v1.0 remains unreleased; final NAMD condition labels and scientific PBC
status remain unresolved. FastAPI is postponed and WANIA is unchanged.

Stage 31.A/B/C are accepted. Stage 31.D integrates their existing models and
statistics as a separate Dataset-level postprocessing run after Stage 30.
The accepted Stage 31.C checkpoint is
`dfe614cada83b91cf8015df89c1ea551960b1113`.

**Availability and partner correspondence are explicit control metadata.
They are never inferred from sparse scientific rows.**

## Final technical acceptance

All 98 supplied Stage 31 acceptance criteria pass. The matrix groups the original
criterion numbers without changing their meaning:

| Criteria | Result | Evidence |
| --- | --- | --- |
| 1–21 | PASS | Accepted A/B/C source unchanged; full existing and new tests enforce canonical identity, engine/window isolation, explicit states, available-only universes and complete partner correspondence. |
| 22–33 | PASS | Exact protein/lipid/glycan statistics, singleton null SD, occupancy-only exports, no QC or distance/lifetime/contact-frame aggregation. |
| 34–45 | PASS | Strict manifest and accepted canonical readers; pure API reuse; deterministic header-only capable CSVs; separate Dataset run with zero trajectory passes and no MDAnalysis requirement. |
| 46–64 | PASS | Manifest/canonical/output inventory, portable provenance, both checksum modes, complete exact model/byte reconstruction, reverse lineage checks and conservative failed-run requirements. |
| 65–78 | PASS | Protein-only, all families, specialized-only, singleton, three replicas, unavailable/excluded, null condition, same-condition separate systems, invalid engines/windows/correspondences, same-name protection and direct pure/workflow equality. |
| 79–90 | PASS | Inputs and accepted Stage 27–30 science/annotations, PBC, analysis and frozen contract unchanged; deterministic outputs; no invented real controls; no dependencies added. |
| 91–98 | PASS | WANIA and version unchanged; config, full pytest, Ruff, mypy and installed offline wheel smoke pass; Stage 32 remains next and unstarted. |

The new Stage 31.D tests contain 90 passing cases. With current workflow docs:

```text
122 passed in 4.80s
```

Final required checks and observed output:

```text
git diff --check
(no output; exit 0)

.venv/bin/pytest
8164 passed, 22 skipped in 103.98s (0:01:43)

.venv/bin/ruff check .
All checks passed!

.venv/bin/mypy src
Success: no issues found in 153 source files

.venv/bin/mania --version
mania-wania 0.1.0

.venv/bin/python -m mania --version
mania-wania 0.1.0

.venv/bin/mania validate-config configs/mania.example.yaml
Config is valid: configs/mania.example.yaml

.venv/bin/mania run --config configs/mania.example.yaml
MANIA pipeline execution is not implemented yet.
Project: NaPi2b_NORM_TUMOR
Run ID: run_001
Run mode: full
Conditions: normal, tumor
Output directory: mania_output
```

The 22 existing skips include optional/local scientific cases; no hour-long real
trajectory acceptance was rerun. The full suite covers accepted Stage 31.A/B/C,
Stage 27–30 science and canonical/annotation contracts, prior inventory/provenance/
unified validation, CLI behavior, current docs and frozen-contract checks.
An existing software-identity reload test required isolating the new validation
test's identity fixture; no generic provenance or software-identity code changed.
Historical Stage 30 wording remains visibly marked as superseded so the frozen
historical checkpoint tests remain intact alongside current Stage 31 completion.

The complete synthetic CLI run produced five protein aggregate rows, one lipid
row and one glycan row. All six external input mappings were supplied (manifest,
three protein files, one lipid file, one glycan file). Observed unified result:

```json
{"complete": true, "error_count": 0, "status": "passed", "unsupported_count": 0, "warning_count": 0, "workflow": "replica_aggregation"}
```

Wheel verification used task-owned directories outside the checkout:

```bash
.venv/bin/python -m pip wheel --no-index --no-deps --no-build-isolation \
  --wheel-dir "$stage31_wheel_root/wheels" "$stage31_wheel_root/source"
.venv/bin/python -m pip install --no-index --no-deps \
  --target "$stage31_wheel_root/installed" \
  "$stage31_wheel_root/wheels/mania_wania-0.1.0-py3-none-any.whl"
.venv/bin/python /tmp/mania-stage31-wheel-smoke.py
```

Build/install succeeded. Wheel size was 504003 bytes; SHA256 was
`5f03470272b9ababdab0ceeaed1760e8c1003513133b9da89f71b2264795bf7a`.
Its installed Python files match the final source exactly. With network,
Git/subprocess execution and MDAnalysis imports blocked, both `none` and
`sha256` installed CLI runs and complete unified reconstruction passed, with
zero unsupported roles. They exercised strict manifest reading, three-replica
protein aggregation, singleton null SD, lipid/glycan correspondence, null
condition, and exact CSV write/read and byte equality.

The frozen scientific contract SHA256 is identical at the accepted checkpoint
and after Stage 31.D:
`c9efd004740f8aff039bede205dc2ef4d2212fd4067a7cf7628e403b8e065868`.
Checkpoint comparisons also show no changes to accepted A/B/C source, Stage
27–30 scientific/canonical/annotation modules, preprocessing, PBC, analysis,
generic inventory/provenance models, dependencies or WANIA.

Final scope inspection found 31 authorized files, zero unexpected files and
zero staged files. Branch remains `FAIR`; HEAD remains the Stage 31.C checkpoint
above, with `develop` an ancestor. No commit or push was made. Stage 32 was not
started; the only deferred execution is real aggregation pending authoritative
control metadata.

## Execution and boundaries

```text
per-replica source science → explicit Stage 30 mapping → canonical tables
→ explicit aggregation manifest → accepted Stage 31.A/B/C → aggregate CSVs
```

```bash
mania dataset aggregate-replicas \
  --manifest replica_aggregation_manifest.json \
  --output aggregate_run \
  --artifact-checksum-mode none
```

The checksum choices are `none` (default) and `sha256`; `--overwrite` follows
the existing atomic writer convention. Use a dedicated output root. Existing
preprocessing provenance is never overwritten or extended. There are no frame,
cutoff, condition-filter or estimator options. The manifest is authoritative.

The workflow performs **zero trajectory passes**. It never reopens trajectories,
reruns temporal selection, computes contacts, remaps residues, or requires
MDAnalysis. New workflow modules import the accepted canonical data APIs; the
existing package and CLI retain their historical transitive module imports.
No trajectory runtime function is invoked by aggregation or reconstruction.
Stage 27–30 scientific implementations and preprocessing artifacts are unchanged.

Stage 32 remains responsible for Dataset QC/exclusion. Availability states are
consumed verbatim: no 95% policy, RMSD, MAD, edge-count outliers or PBC decisions.
Stage 33 owns final publication bundles and later biological annotation joins.
ECD, MX35, glycosylation and variant-site annotations are not grouping inputs.

## Manifest contract

`replica_aggregation_manifest.json` is a control input, not a publication table.
Its schema is `mania.replica_aggregation_manifest.v0.1`; kind is
`mania_replica_aggregation_manifest`. Root and nested keys are exact: missing,
unknown and duplicate keys fail. UTF-8 JSON uses strict scalar types, including
actual booleans and integers; numeric strings and nonfinite numbers fail.
The writer emits deterministic indented JSON with one trailing newline and
atomic no-clobber publication unless overwrite is explicit. JSON object key
order is immaterial to reading; the writer has a fixed key order.

Root fields are `schema_version`, `kind`, `canonical_reference_id`,
`canonical_reference_sequence_sha256`, `protein_canonical_table_paths`,
`lipid_canonical_table_paths`, `glycan_canonical_table_paths`, and `groups`.
The reference is pinned to `uniprotkb:O95436-1:sequence-v3` and SHA256
`33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9`.

Each path array is explicit and may be empty; at least one path overall and
one group are required. Relative paths resolve against the manifest location.
Paths must be physically unique within a family, including symlinks and hard
links. Distinct files with identical contents remain distinct inventory inputs.
Path order is retained as explicit inventory ordinal order. No directory scan
or filename inference occurs. Multiple tables are strictly read through the
accepted Stage 30.C readers, combined in memory, sorted by canonical row order,
and validated by the accepted canonical root, which rejects duplicate rows
across files. Source CSV schemas and annotated CSV schemas are not accepted.

Every group contains exactly `spec`, `members`, `lipid_correspondences`, and
`glycan_correspondences`. These reconstruct the exact accepted Stage 31.A/C
models. Expected replica IDs are explicit and every expected member must occur
once. Group members are ordered by the specification's expected replica tuple.
Groups are ordered by dataset, system, engine, window index, physical key, then
window ID. Duplicate group identities fail. Identity is dataset/system/engine,
the requested physical window key, window ID and index; condition is metadata.

All members must agree on engine, variant, condition, disulfide state, canonical
reference, requested production and window bounds, endpoint convention, length,
step, overlap, window ID and index. `window_id` alone never proves compatibility.
Effective coverage is not requested-window identity. Different systems sharing
`NORM` remain separate. NAMD-style `condition=null` is retained without a label.

`available` requires a null reason. `unavailable` and `excluded` require portable
nonempty reason text. Reasons stay in the inventoried manifest and are never
interpreted by Stage 31. Unavailable/excluded members never enter denominators
or contribute zeros. Protein sparse absence in an available replica contributes
zero privately in the accepted statistical vector.

Each correspondence collection contains exactly `correspondences`, an array of
`SpecializedPartnerCorrespondence` objects. Each object has exactly
`partner_correspondence_id`, `partner_kind`, `partner_name`, and `members`.
Each binding has `dataset_id`, `system_id`, `trajectory_id`, `replica_id`,
`local_partner_id`, and `partner_name`. Correspondences sort by ID and their
members by replica key. Kind must match the family's collection. Each declared
correspondence must cover exactly every available replica, even when canonical
tables are empty. Equal local IDs or names never authorize correspondence.
Only explicitly bound local partners participate. Complete correspondence plus
absent sparse row contributes zero; incomplete correspondence fails before
statistics. No available replicas requires empty correspondence collections.

An empty correspondence collection produces no rows for that group/family.
A declared specialized correspondence without its family's canonical input
fails. Header-only canonical tables are valid and say nothing about availability.
**Input family present → corresponding aggregate CSV exists**, including a
header-only CSV when no correspondence or observed aggregate rows exist.

## Exports

Exact filenames:

- `protein_edges_by_window_canonical_replica_aggregation.csv`
- `protein_lipid_contacts_by_window_canonical_replica_aggregation.csv`
- `protein_glycan_contacts_by_window_canonical_replica_aggregation.csv`

Every row starts with these exact common columns, in order:

```text
dataset_id,system_id,engine,variant_id,condition,disulfide_state,
window_id,window_index,requested_production_start_ns,requested_production_end_ns,
requested_window_start_ns,requested_window_end_ns,right_endpoint_inclusive,
window_length_ns,window_step_ns,overlap_percent
```

Protein rows then contain:

```text
source_canonical_residue_number,source_canonical_resname,
target_canonical_residue_number,target_canonical_resname,edge_type
```

Lipid and glycan rows instead contain:

```text
canonical_residue_number,canonical_resname,partner_correspondence_id,partner_name
```

All rows end with the same six statistics:

```text
mean_occupancy,std_occupancy,median_occupancy,n_replicates_available,
n_replicates_supporting,support_fraction
```

There is no trajectory/replica ID, source residue ID, local partner ID, occupancy
vector, linkage/component index, distance, lifetime, contact-frame count or
specialized `edge_weight`. Accepted B/C result values are copied exactly by pure
builders; export does not calculate statistics again. Supporting means strictly
`occupancy > 0`. SD is sample SD, **ddof=1**. For one available replica SD is
`None`, serialized as an **empty CSV cell**, never zero, `None`, `null` or `NA`.

| Available values | Mean | Sample SD | Median | Available | Supporting | Support fraction |
| --- | --- | --- | --- | --- | --- | --- |
| Protein/lipid `[0.7, 0, 0.2]` | 0.3 | 0.36055512754639896 | 0.2 | 3 | 2 | 0.6666666666666666 |
| Glycan `[0.5, 0.5, 0]` | 0.3333333333333333 | 0.28867513459481287 | 0.5 | 3 | 2 | 0.6666666666666666 |
| `[0.7, 0]`, third unavailable/excluded | 0.35 | 0.4949747468305833 | 0.35 | 2 | 1 | 0.5 |
| `[0.6]` | 0.6 | blank | 0.6 | 1 | 1 | 1.0 |

Rows sort by dataset/system/engine/window index, then protein edge type/source/
target canonical numbers or specialized correspondence ID/canonical number.
Physical key and window ID break otherwise equal sort keys. No condition sort
or condition-based identity is used. The frozen table roots derive row counts,
pin the canonical reference, enforce unique scientific identities and consistent
group metadata. Empty roots are valid. Strict UTF-8 CSV I/O requires exact
headers/order, finite numbers, lowercase booleans and blank null cells. Writers
use LF and a single final newline, preserve scientific precision, and publish
atomically. Deterministic bytes support exact offline reconstruction.

## Technical artifacts and validation

Every separate aggregation output root has `artifact_inventory.json` and
`run_provenance.json`. Generic schemas are unchanged. Inventory includes the
manifest, each listed canonical file individually, and successfully written
aggregate CSVs. It excludes itself and provenance, preventing reciprocal hashes.
Input roles are `replica_aggregation_manifest`,
`canonical_protein_edge_window_table`, `canonical_protein_lipid_window_table`,
and `canonical_protein_glycan_window_table`. Output roles are
`canonical_protein_edge_replica_aggregation`,
`canonical_protein_lipid_replica_aggregation`, and
`canonical_protein_glycan_replica_aggregation`.

The manifest ID is `input:replica_aggregation_manifest`, portable path
`inputs/replica_aggregation_manifest.json`. Canonical IDs are
`input:protein:0001`, `input:lipid:0001`, `input:glycan:0001`, etc., ordered by
family then manifest path ordinal. Virtual paths are
`inputs/<family>/<ordinal>/canonical.csv`. Outputs use `output:<family>` and
the exact filenames above. All inventory conditions are null because artifacts
may contain multiple groups. Under `none`, exact byte sizes are recorded and
SHA256 is null without invoking content hashing. Under `sha256`, the existing
bounded streaming helper hashes every declared input and aggregate output.

Provenance records workflow `replica_aggregation`, a portable manifest path,
pinned reference, group count, family participation booleans, scientific
condition labels (including JSON null), checksum mode, and portable output and
inventory references. It embeds neither the full manifest nor aggregation rows.
There is no PBC audit, runtime metadata, temporal execution, trajectory sampling
or analysis propagation. Non-null labels alone appear in the generic conditions
tuple; null labels remain in resolved configuration and in scientific tables.

```bash
mania artifacts validate aggregate_run --scope replica_aggregation \
  --input-artifact-path input:replica_aggregation_manifest=replica_aggregation_manifest.json \
  --input-artifact-path input:protein:0001=replicas/1/protein_edges_by_window_canonical.csv
```

Supply every external input mapping, including lipid/glycan files when present.
No local path is guessed. Unmapped inputs produce a partial report; mapped
missing or malformed files fail. Complete validation strictly reads controls
and canonical files, reconstructs compatible A groups, reruns B/C, builds
expected tables, and compares **both exact models and deterministic CSV bytes**.
It supports relocation without the checkout or original input paths. Required
outputs follow family participation. Missing/extra family outputs, wrong
reference, mismatched group/window/correspondence, altered statistics and
inventory/provenance inconsistencies fail. All seven current roles are recognized.

All input reads and model builds finish before any aggregate CSV write starts.
Scientific failure therefore writes no new aggregate CSV. Writer failure may
leave previously atomically published outputs; best-effort failed provenance
and inventory reference only successfully written artifacts. Failed runs may
omit incomplete outputs and do not claim successful scientific reconstruction.
Normal CLI errors have portable phase prefixes: `Replica aggregation manifest
failed:`, `Replica aggregation input failed:`, `Replica aggregation failed:`, or
`Replica aggregation export write failed:`. No normal failure prints a traceback.

## Real-data policy

The acceptance suite uses synthetic controls only. Do not invent authoritative
replica states, specialized partner correspondence, mapping or annotations for
real NaPi2b. No authoritative existing Stage 31 control metadata was found in
the checked local control locations. Real Stage 31 replica-aggregation smoke
not run because authoritative replica availability and/or specialized partner
correspondence metadata are not yet available. This is not a Stage 31 technical
blocker. Prior accepted Stage 27–30 trajectory/PBC/analysis evidence is reused;
no trajectories are rerun for Stage 31 acceptance.

## Exact synthetic manifest example

The following is a structural example only. Its synthetic replica state and
partner bindings are not real NaPi2b authority. Corresponding strict canonical
CSV inputs must be supplied before execution.

```json
{
  "schema_version": "mania.replica_aggregation_manifest.v0.1",
  "kind": "mania_replica_aggregation_manifest",
  "canonical_reference_id": "uniprotkb:O95436-1:sequence-v3",
  "canonical_reference_sequence_sha256": "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9",
  "protein_canonical_table_paths": [
    "replicas/1/protein_edges_by_window_canonical.csv"
  ],
  "lipid_canonical_table_paths": [
    "replicas/1/protein_lipid_contacts_by_window_canonical.csv"
  ],
  "glycan_canonical_table_paths": [
    "replicas/1/protein_glycan_contacts_by_window_canonical.csv"
  ],
  "groups": [
    {
      "spec": {
        "dataset_id": "napi2b-v1-test",
        "system_id": "wt-norm",
        "engine": "namd",
        "variant_id": "WT",
        "condition": null,
        "disulfide_state": null,
        "expected_replica_ids": [
          "1"
        ],
        "window": {
          "window_id": "window_0001",
          "window_index": 0,
          "requested_production_start_ns": 20.0,
          "requested_production_end_ns": 30.0,
          "requested_window_start_ns": 20.0,
          "requested_window_end_ns": 25.0,
          "right_endpoint_inclusive": false,
          "window_length_ns": 5.0,
          "window_step_ns": 2.5,
          "overlap_percent": 50.0
        },
        "canonical_reference_id": "uniprotkb:O95436-1:sequence-v3",
        "canonical_reference_sequence_sha256": "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
      },
      "members": [
        {
          "dataset_id": "napi2b-v1-test",
          "system_id": "wt-norm",
          "trajectory_id": "trajectory-1",
          "replica_id": "1",
          "variant_id": "WT",
          "engine": "namd",
          "condition": null,
          "disulfide_state": null,
          "canonical_reference_id": "uniprotkb:O95436-1:sequence-v3",
          "canonical_reference_sequence_sha256": "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9",
          "window": {
            "window_id": "window_0001",
            "window_index": 0,
            "requested_production_start_ns": 20.0,
            "requested_production_end_ns": 30.0,
            "requested_window_start_ns": 20.0,
            "requested_window_end_ns": 25.0,
            "right_endpoint_inclusive": false,
            "window_length_ns": 5.0,
            "window_step_ns": 2.5,
            "overlap_percent": 50.0
          },
          "availability_status": "available",
          "availability_reason": null
        }
      ],
      "lipid_correspondences": {
        "correspondences": [
          {
            "partner_correspondence_id": "lipid-correspondence-01",
            "partner_kind": "lipid",
            "partner_name": "LIPID-X",
            "members": [
              {
                "dataset_id": "napi2b-v1-test",
                "system_id": "wt-norm",
                "trajectory_id": "trajectory-1",
                "replica_id": "1",
                "local_partner_id": "lipid_0003",
                "partner_name": "LIPID-X"
              }
            ]
          }
        ]
      },
      "glycan_correspondences": {
        "correspondences": [
          {
            "partner_correspondence_id": "glycan-correspondence-01",
            "partner_kind": "glycan",
            "partner_name": "GLYCAN-X",
            "members": [
              {
                "dataset_id": "napi2b-v1-test",
                "system_id": "wt-norm",
                "trajectory_id": "trajectory-1",
                "replica_id": "1",
                "local_partner_id": "glycan_0003",
                "partner_name": "GLYCAN-X"
              }
            ]
          }
        ]
      }
    }
  ]
}
```
