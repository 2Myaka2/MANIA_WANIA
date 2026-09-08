# Reproducible MANIA execution

## Scope

This guide covers computational/technical reproducibility of the current MANIA
preprocessing and analysis workflows. It does not freeze unresolved scientific
Dataset v1.0 choices or establish publication readiness. Software-to-dataset
handoff is described in the [software release reference](software_release_reference.md).

## Identify the exact software

Use the same environment for version checks and execution:

```bash
mania --version
python -m mania --version
```

Both currently print `mania-wania 0.1.0`. These commands report the package
version only; they do not inspect Git. Each run's `run_provenance.json` stores
the actual `software_identity` snapshot captured before workflow execution:

| SoftwareIdentity field | Interpretation |
| --- | --- |
| `software_name` | `MANIA` |
| `distribution_name` | `mania-wania` |
| `version` | Exact package version, currently `0.1.0` |
| `commit_sha` | Full lowercase 40-character commit SHA when available; otherwise JSON `null` |
| `commit_source` | `git_checkout` or `unavailable` |
| `working_tree_status` | `clean`, `dirty`, or `unavailable` |

The identity describes the installed module's source checkout, independently of
the shell's current directory. Wheel installations without checkout metadata
honestly report Git fields unavailable. A missing status lookup may leave a
known commit with `working_tree_status = "unavailable"`.

An exact full commit is reproducible source evidence. A dirty checkout also has
uncommitted changes that the SHA alone cannot reconstruct; an unavailable status
does not establish a clean checkout. Retain the actual identity and account for
that limitation before generation. Recheck the exact software identity at dataset
generation time. A real formal release tag may later provide a human-friendly
reference, but cannot replace the exact commit. SoftwareIdentity has no release
tag, release DOI, or repository URL fields; consumer references own those facts.

## Reproduce preprocessing

Prepare the same manifest and accessible source inputs using the
[input contract](preprocessing_input_contract.md) and
[current workflow](../README.md). Preprocessing requires the existing optional
MDAnalysis stack; preserve the environment used for the original run. Keep the
original manifest and a private mapping to relocated inputs. Use a fresh output
directory for each reproduction so earlier artifacts remain attributable.

```bash
mania preprocessing run-graph-export \
  --manifest manifest.yaml \
  --output out \
  --contact-selection protein \
  --export-analysis-inputs
```

This example uses the default expected conditions `normal` and `tumor`; for
different manifest conditions, repeat `--expected-condition NAME` for the exact
names. Preserve the original `--run-name`, selection, exports, and sampling
settings when reconstructing the command. `--export-analysis-inputs` writes the
accepted root-level analysis inputs and requires protein contacts; it cannot be
combined with `--skip-contacts`.

Sampling options are `--frame-start` (default 0), `--frame-stop` (exclusive),
`--frame-stride` (default 1), and `--max-frames` (cap after filtering). Restore
the original settings from provenance; these options affect scientific outputs.
Do not treat observed time spacing as an approved physical-time window protocol.

The default `--artifact-checksum-mode none` is normal size-only integrity mode.
Explicit `--artifact-checksum-mode sha256` intentionally streams every
inventoried input and output, including potentially large trajectories in full.
Hashing is bounded in memory but adds file reads; it is not automatically enabled.

Completed runs with successful technical writing produce these technical
artifacts under `out/`:

- `runtime_metadata.json`;
- `pbc_audit.json`;
- `artifact_inventory.json`;
- `run_provenance.json`.

These are not scientific output tables. Keep the scientific outputs and manifest
they describe as well. A technical write failure returns exit 1 while retaining
scientific outputs and attempting the remaining technical writes. Covered failed
scientific runs can retain provenance/inventory, but do not automatically write
runtime metadata or PBC audit; their failure coverage is documented in the
[provenance contract](run_provenance_contract.md).

## Reproduce analysis

Use the preprocessing output containing the accepted Stage 20 inputs:

```bash
mania analyze \
  --input out \
  --output run_output \
  --condition normal \
  --condition tumor
```

Repeat `--condition` for the original conditions in their original order. Add
`--enable-pca` only if it was enabled originally; preserve recorded clustering
settings too. Analysis also accepts `--artifact-checksum-mode none` (default)
or explicit `--artifact-checksum-mode sha256` for its own inventoried files.

Completed analysis writes these technical artifacts relative to `run_output/`:

- `analysis/runtime_metadata.json`;
- `analysis/artifact_inventory.json`;
- `analysis/run_provenance.json`.

`analysis/extended_metrics.json` remains separate scientific/analysis metadata.
Analysis does not write a PBC audit or infer upstream sampling. Keep preprocessing
provenance alongside analysis provenance. The `analysis/` layout preserves root
preprocessing metadata even when input and output roots are equal; reuse of an
analysis output directory replaces its latest-run metadata rather than archiving
history.

## Interpret run provenance

| Field | Meaning for reproduction |
| --- | --- |
| `run_id` | Preprocessing uses the workflow run name; callers ensure uniqueness. Analysis derives its ID from the UTC start timestamp. Neither is a dataset version. |
| `workflow` | `preprocessing_graph_export` or `analysis` |
| `status` | `completed` or `failed` scientific workflow execution; not scientific acceptance or proof that every technical write succeeded |
| `started_at_utc`, `ended_at_utc` | UTC timing; the scientific workflow ends before technical artifact writing |
| `software_identity` | The run's exact software-source identity |
| `command` | Portable argument tokens; known path arguments are normalized, not a directly replayable shell command |
| `resolved_configuration` | Resolved options/defaults, including sampling, selection, exports or analysis options and checksum mode; local path options use portable labels |
| `conditions` | Conditions in execution order |
| `sampling_by_condition` | Preprocessing requested/effective sampling; empty for analysis |
| `artifact_references` | Successful artifact writes referenced by `role` and portable `path` |
| `issues` | Recorded warnings/errors; inspect with status and CLI outcome |

Portable preprocessing input arguments use filenames and output becomes `.`;
analysis input is a filename or `.` when roots coincide, and output is `.`.
Resolve those labels to actual inputs/output locations before rerunning. Preserve
the manifest separately: the resolved configuration is not a copy of raw inputs.
Caller-supplied free text is not automatically scrubbed of private information.

Requested sampling records `frame_start`, `frame_stop`, `frame_stride`, and
`max_frames`. Effective records distinguish `source_frame_count` from
`sampled_frame_count`, first/last source indexes, first/last observed times in ps,
`time_spacing_status`, and `observed_time_spacing_ps`. Unavailable observations
remain null; they are not reconstructed from requested sampling. Consult the
[full contract](run_provenance_contract.md) for exact field constraints.

Provenance points to inventory through a portable reference:
`artifact_inventory.json` or `analysis/artifact_inventory.json`. It does not
hash inventory and requires no reciprocal checksum loop.

## Interpret artifact inventory

The inventory identifies its `run_id`, `workflow`, `inventory_path`,
`checksum_mode`, and total/input/output artifact counts. Each entry has:

- `artifact_id`, `direction` (`input` or `output`), and an explicit `role`;
- a portable `path`, `format`, and optional `condition`;
- exact `byte_size` and optional `sha256` (`null` in `none` mode).

Output paths are relative to the run output root. Input paths are portable lineage
labels and may not exist below that root; validation requires explicit input
mapping. Matching size alone does not establish identical contents. In `sha256`
mode every entry has a hash; checksums still do not certify scientific correctness.

Inventory does not include or hash itself and does not include the corresponding
run provenance. Scientific files and runtime/PBC metadata are written first,
then inventoried, then referenced by provenance. There is no provenance/inventory
cycle. Raw trajectory inputs in inventory record lineage, NOT dataset publication
membership or permission to distribute them. See the
[inventory contract](artifact_inventory_contract.md).

## Interpret runtime metadata

`runtime_metadata.json` identifies the run, workflow, scope and portable
`metadata_path`, then separates `environment` from `performance`.

Environment fields are `python_version`, `python_implementation`,
`platform_system`, `platform_release`, `platform_machine`, `numpy_version`,
`mdanalysis_version`, `pydantic_version`, and `pyyaml_version`. Installed package
versions use `importlib.metadata.version()` distribution metadata. Package modules
are not imported merely to query versions. Analysis-only metadata collection must
not require importing MDAnalysis or other optional scientific packages for version
reporting. Absent distributions are `None` in Python and `null` in JSON.

Runtime collection excludes username, hostname, home-directory path, absolute
local paths (source or output), current working directory, environment variables,
and machine serial identifiers. It records OS/platform and architecture, not
machine identity. Publication-facing technical metadata must exclude these
personal/local values too: consumers must review caller-supplied names, free
text and manifests before sharing; portable paths are not general anonymization.

Performance fields describe the observed run:

| Field | Interpretation |
| --- | --- |
| `wall_clock_seconds` | Existing UTC end minus start, excluding subsequent technical writing |
| `condition_count` | Conditions represented by this workflow |
| `sampled_frame_count` | Effective observed sampled frames where applicable |
| `seconds_per_sampled_frame` | Duration divided by positive sampled-frame count; otherwise null |
| `contact_frame_count` | Retained contact frame-result count, or null |
| `contact_observation_count` | Retained residue-contact observations, or null |

Preprocessing reuses retained counters; analysis records duration and condition
count with sampling/contact counters null. These are operational measurements,
not scientific statistics or guarantees of identical performance on another
machine. Recorded versions help reconstruct an environment but do not constitute
a full environment lockfile. Details: [runtime contract](pbc_runtime_metadata.md).

## Interpret PBC audit

**PBC observations cover sampled frames only: the frames actually observed by
the selected existing pass. They do not validate the whole trajectory or describe
unsampled frames.** If 1001 source frames yield 101 observed sampled frames, the
audit describes those 101 frames only.

The canonical pass is the Rg pass when enabled, otherwise the contacts pass.
When both run, only the existing Rg pass supplies observations, avoiding double counting. With
neither computation enabled there are no observations. No additional trajectory
pass or coordinate modification is performed.

| Field(s) | Units and scope |
| --- | --- |
| `box_lengths_A` | Per-observation lx, ly, lz in ångström (Å) |
| `box_angles_deg` | Per-observation alpha, beta, gamma in degrees |
| `box_lengths_min_A`, `box_lengths_max_A` | Component-wise observed valid length bounds in Å |
| `box_angles_min_deg`, `box_angles_max_deg` | Component-wise observed valid angle bounds in degrees |

Per-frame helpers expose the first two fields; the persisted audit contains
condition aggregates, not a per-frame observation list. `sampled_frame_count`
equals present + missing dimensions counts; present equals valid + invalid.
The exact count fields are `dimensions_present_frame_count`,
`dimensions_missing_frame_count`, `dimensions_valid_frame_count`, and
`dimensions_invalid_frame_count`.

`metadata_status` describes observed unit-cell availability/validity:

- `unavailable`: no observations or no dimensions present;
- `invalid`: dimensions present but none valid;
- `complete`: every observed sampled frame has valid dimensions;
- `partial`: some valid observations and some missing/invalid dimensions.

Here valid means six finite positive dimension values. Ranges use only valid
observations and are null without any. `box_varies` describes only observed valid
box metadata: null with fewer than two valid observations; otherwise true if any
component min/max differs, false if none differs. No tolerance or scientific
judgment is implied by constant or consistently varying boxes.

Current fixed facts are:

- `mania_internal_minimum_image_correction_applied = false`;
- `distance_semantics = "euclidean_selected_atom_coordinates_without_mania_minimum_image_correction"`;
- automatic `external_pbc_preprocessing_status = "undeclared"`;
- `scientific_pbc_status = "unresolved"`.

Contact distances use Euclidean selected-atom coordinates without MANIA internal
minimum-image correction. Explicit Python callers may declare external processing;
declarations are not scientific verification and automatic runs do not infer them.

**Box metadata presence is not evidence that the protein was made whole, centered,
unwrapped, minimum-image corrected, or that contacts are scientifically
PBC-correct.** Finite positive dimensions do not establish scientific PBC
correctness. Scientific PBC status remains unresolved even with complete box
metadata and a technically passed validator. See the
[PBC contract](pbc_runtime_metadata.md).

## Validate a run

Use the root belonging to the selected workflow. If both workflows share `out`,
the accepted commands are:

```bash
mania artifacts validate out --scope preprocessing
mania artifacts validate out --scope analysis
```

For the separate analysis output in this guide, use
`mania artifacts validate run_output --scope analysis`.
Read input `artifact_id` values from the appropriate inventory and supply each
external input explicitly, for example:

```bash
mania artifacts validate out --scope preprocessing \
  --input-artifact-path input:condition:0001:trajectory:0001=source/trajectory.xtc
```

Repeat `--input-artifact-path ARTIFACT_ID=PATH` for all required inputs, including
manifest, topology, other trajectories, and reference inputs where inventoried.
Analysis inputs also need explicit mapping, even if they are in the same root.
The example maps one input only; it does not promise complete validation. Local
mapping values are not serialized into the report. Validation never guesses paths.

| `report.status` | Meaning | Exit code |
| --- | --- | --- |
| `passed` | Integrity and every applicable specialized check passed; validation complete | 0 |
| `partial` | No technical error established, but unresolved inputs or unsupported roles leave checks incomplete | 0 |
| `failed` | An integrity, specialized validator, or coordinator contract error occurred | 1 |

Ordinary validation prints one JSON report line to stdout. `report.passed` may
be true while `report.complete` is false: `partial` currently exits 0 because no
technical error was established. The future Stage 25.G publication gate must
require **both `report.status == "passed"` and `report.complete is True`**.
Stage 25.F documents this requirement only; it adds no `--require-complete`
option or changed exit codes. Retain the serialized report when needed, for
example by redirecting stdout to a consumer-chosen file outside the run inventory.

Technical validation can establish matching declared SHA256 and byte sizes,
parseable metadata, agreeing artifact/condition references, and passing existing
CSV/JSON contract validators. Technical validity is not scientific acceptance:
it does not establish scientific PBC correctness, approved contact lifetime
semantics, approved physical-time windows, approved replica aggregation, approved
cross-engine mapping, Dataset v1.0 scientific approval, or publication readiness.
Those protocol decisions remain separate. Validation does not compare recorded
runtime versions against the current environment or prove two executions produce
identical scientific results. See [unified validation](unified_artifact_validation.md).

## Reproducibility checklist

For one completed run:

- Capture exact SoftwareIdentity and account for dirty/unavailable source state.
- Retain the original manifest, inputs or accessible references, and resolved options.
- Preserve run provenance, inventory and runtime metadata for each workflow.
- Preserve preprocessing PBC audit where applicable, with sampled-frame scope.
- Map required external inputs when performing complete validation.
- Record unified validation status and completeness, not just the exit code.
- Document scientific protocol decisions and unresolved questions separately.

This is a technical run checklist, not a Dataset v1.0 release checklist.
