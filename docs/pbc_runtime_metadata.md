# PBC audit and runtime metadata

## Status and boundary

Stage 25.E.1 contracts and Stage 25.E.2 workflow integration are implemented.
Stage 25.E is complete. Stage 25.F reproducibility documentation and FAIR² bridge
is complete. Stage 25.G final technical-hardening acceptance is complete;
Stage 25 is complete. Stage 26 is complete. Stage 27.C observes physically
selected scientific frames; Stage 27 is complete.
FastAPI remains postponed.

**Observation only:** MANIA reads sampled timestep dimensions without changing
coordinates, frame selection, Rg, distances, contacts, graphs, or scientific
schemas. The scientific PBC protocol remains unresolved and no internal
minimum-image correction is applied.

For publication-facing interpretation, observations cover **sampled frames only**:
the frames actually observed by the selected pass, not the entire unsampled
trajectory. For 1001 source frames and 101 observed sampled frames, the audit
describes only those 101 frames. **Box metadata presence does not establish that
the protein was made whole, centered, unwrapped, minimum-image corrected, or that
contacts are scientifically PBC-correct.** This remains true for finite positive
dimensions and constant or consistently varying observed boxes. Scientific PBC
status remains unresolved.

See the [reproducibility guide](reproducibility.md) and
[software release reference](software_release_reference.md) for run verification
and the consumer dataset boundary.

## Runtime/environment contract

`mania.runtime_metadata` provides `RuntimeEnvironment`, `RuntimePerformance`,
`RuntimeMetadata`, `collect_runtime_environment()`, `build_runtime_performance()`,
and `build_runtime_metadata()`.

The root schema is `mania.runtime_metadata.v0.1`, kind `mania_runtime_metadata`.
Its deterministic key order is `schema_version`, `kind`, `run_id`, `workflow`,
`scope`, `metadata_path`, `environment`, `performance`. Scope is `preprocessing`
or `analysis`. Paths are normalized portable relative POSIX paths ending with
the exact filename `runtime_metadata.json`; absolute paths, backslashes, URI
schemes, control characters, and `.`/`..` components are rejected. E.2 integration
and unified validation enforce the exact scope-specific location.

Environment fields, in order:

| Fields | Observation source |
| --- | --- |
| `python_version`, `python_implementation` | `platform.python_version()`, `platform.python_implementation()` |
| `platform_system`, `platform_release`, `platform_machine` | `platform.system()`, `platform.release()`, `platform.machine()` |
| `numpy_version`, `mdanalysis_version`, `pydantic_version`, `pyyaml_version` | `importlib.metadata.version()` for `numpy`, `MDAnalysis`, `pydantic`, `PyYAML` |

Missing distributions are recorded as `None` (JSON `null`). Required text and
present optional versions must be non-empty stripped strings. Package modules
are not imported to discover versions. Collection uses only the listed platform
and package-metadata APIs; no separate file reads, clock calls, Git commands,
or network access are performed. Environment metadata contains no hostnames,
usernames, local paths, environment variables, cwd, or processor/host identifiers.
The root's portable artifact path is a reference, not a machine location.

Analysis-only metadata collection must not import MDAnalysis merely to report
its installed distribution version. Publication-facing metadata must exclude
username, hostname, home-directory path, absolute local paths (source or output),
environment variables and machine serial identifiers. Consumers must also review
caller-supplied free text and input manifests; portable references are not a
general privacy filter for arbitrary user content.

Performance fields, in order:

| Field | Meaning |
| --- | --- |
| `wall_clock_seconds` | Supplied end minus start, normalized to UTC, using exact `timedelta.total_seconds()` |
| `condition_count` | Number of conditions represented by the workflow |
| `sampled_frame_count` | Total effective sampled frames represented by the accepted workflow, when applicable |
| `seconds_per_sampled_frame` | Wall-clock seconds divided by positive sampled-frame count; otherwise `None` |
| `contact_frame_count` | Total retained contact frame-result count, when contacts were computed |
| `contact_observation_count` | Total retained residue-contact observations across contact frame results |

Timestamps must be timezone-aware and end must not precede start. No current
clock is read. Duration and seconds/frame must be finite and non-negative;
counts must be non-negative integers, excluding bool. Optional counters may be
`None`. Positive sampled-frame counts require seconds/frame; zero or unavailable
counts require `None`. These are operational counters, not new scientific
statistics. The builder computes the quotient; direct model construction
validates its presence and numeric bounds.

`build_runtime_metadata()` only composes supplied objects, requiring exact
`RuntimeEnvironment` and `RuntimePerformance` instances. All models are frozen;
`to_dict()` returns fresh dictionaries in declared field order, compatible with
`json.dumps(payload, allow_nan=False)`. SoftwareIdentity and MANIA commit SHA
remain owned by run provenance and are not duplicated here.

```python
from datetime import UTC, datetime
from mania.runtime_metadata import (
    build_runtime_metadata, build_runtime_performance, collect_runtime_environment,
)

performance = build_runtime_performance(
    started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    ended_at_utc=datetime(2026, 1, 1, 0, 0, 12, tzinfo=UTC),
    condition_count=1,
    sampled_frame_count=3,
)
metadata = build_runtime_metadata(
    run_id="example-run", workflow="preprocessing_graph_export",
    scope="preprocessing", metadata_path="runtime_metadata.json",
    environment=collect_runtime_environment(), performance=performance,
)
payload = metadata.to_dict()  # In memory only; 12 seconds, 4 seconds/frame.
```

## PBC observation contract

`mania.preprocessing.pbc_audit` provides `PbcFrameObservation`,
`PbcConditionAudit`, `PbcAudit`, `observe_pbc_frame_dimensions()`,
`summarize_pbc_condition_observations()`, and `build_pbc_audit()`.

The schema is `mania.pbc_audit.v0.1`, kind `mania_pbc_audit`. Root key order is
`schema_version`, `kind`, `run_id`, `workflow`, `audit_path`, `distance_semantics`,
`mania_internal_minimum_image_correction_applied`,
`external_pbc_preprocessing_status`, `scientific_pbc_status`, `conditions`.
The portable path rules match runtime metadata, with exact filename
`pbc_audit.json`. Models are frozen and serialization is deterministic and
JSON-safe. Dimension tuples serialize as lists.

The helper consumes only caller-supplied dimensions for an already selected
frame, never a trajectory. `None` means missing. Present dimensions must contain
exactly six finite positive real scalars: three lengths in angstroms followed
by three angles in degrees. Ordinary malformed values are recorded as present
but invalid, with no lengths/angles retained. Bool is not numeric. Generic
iterables are supported without NumPy APIs; consumption is bounded to seven
items to detect excess values. Non-90-degree angles are accepted. Validity here
does not assess scientific box adequacy or triclinic suitability.

Units are explicit and unchanged from E.1:

| Fields | Units and component order |
| --- | --- |
| `box_lengths_A` | Observation lx, ly, lz in ångström (Å) |
| `box_angles_deg` | Observation alpha, beta, gamma in degrees |
| `box_lengths_min_A`, `box_lengths_max_A` | Component-wise valid observed length bounds in Å |
| `box_angles_min_deg`, `box_angles_max_deg` | Component-wise valid observed angle bounds in degrees |

The per-frame fields belong to `PbcFrameObservation`; persisted condition
aggregates contain the min/max fields, without a per-frame list. Units do not
change the scientific meaning of metadata validity.

Each observation has a stripped condition name, a non-negative integer frame
index (excluding bool), and finite non-negative `time_ps` or `None`. Dimensions
flags are real bools; valid dimensions must be present with both length/angle
triples. Missing/invalid dimensions require both triples to be `None`.

Condition summaries validate these relationships:

```text
sampled = present + missing
present = valid + invalid
```

| Metadata status | Supplied observations |
| --- | --- |
| `unavailable` | No observations, or no dimensions present |
| `invalid` | Some dimensions present, but none valid |
| `complete` | Every supplied sampled frame has valid dimensions |
| `partial` | At least one valid frame and at least one missing/invalid frame |

Component-wise min/max lengths and angles use only valid observations; without
valid observations, ranges are `None`. `box_varies` is `None` with fewer than two
valid observations; otherwise it is true exactly when any minimum differs from
its maximum, with no tolerance or scientific interpretation. Count/status/range
and variation consistency are validated even for direct model construction.

The builders require tuples. Declared condition names are non-empty, unique,
and retain supplied order. Observation conditions must be declared; frame indexes
must be unique within each condition. Conditions with no observations remain
visible as unavailable. The final audit contains aggregates only, without a
per-frame list, coordinates, or raw trajectory data.

Current fixed facts:

- `distance_semantics` is
  `euclidean_selected_atom_coordinates_without_mania_minimum_image_correction`.
- MANIA internal minimum-image correction is **false**.
- External PBC preprocessing defaults to `undeclared`; `declared_applied` and
  `declared_not_applied` are caller declarations, not verified scientific facts.
- Scientific PBC status remains **unresolved**. There is no `approved` state.

Metadata can therefore be complete while internal correction is false, external
preprocessing is undeclared, and scientific status is unresolved. This is a
useful audit result, not a scientific failure or a validation failure by itself.

```python
from mania.preprocessing.pbc_audit import (
    build_pbc_audit, observe_pbc_frame_dimensions,
)

observation = observe_pbc_frame_dimensions(
    condition="normal", frame_index=0, time_ps=0.0,
    dimensions=(10, 20, 30, 90, 90, 90),
)
audit = build_pbc_audit(
    run_id="example-run", workflow="preprocessing_graph_export",
    condition_names=("normal",), observations=(observation,),
)
payload = audit.to_dict()  # Complete metadata; scientific status unresolved.
```

## E.2 completed-run integration

The existing commands automatically emit these technical artifacts:

```text
mania preprocessing run-graph-export:
  <output>/runtime_metadata.json
  <output>/pbc_audit.json
mania analyze:
  <output>/analysis/runtime_metadata.json
```

There is no automatic analysis PBC audit and no new PBC CLI option. Automatic
preprocessing always records `external_pbc_preprocessing_status = "undeclared"`;
filenames, engine, directory names, manifest free text, coordinates and box values
never imply an external declaration. Explicit E.1 Python callers may still
supply a declaration when building their own audit.

The canonical collection rule is deterministic:

1. Observe selected frames from the existing Rg pass when Rg runs.
2. Otherwise observe selected frames from the existing contacts pass.
3. With neither computation enabled, collect no observations.

When both computations run, only Rg supplies observations, so frames are never
double-counted. The dimensions helper reads only the already yielded timestep's
`dimensions` attribute. Missing or raising attributes are unavailable; invalid
values remain invalid observations. Every selected frame contributes one
observation in workflow condition order, even when dimensions are unavailable.
There is never an extra metadata trajectory pass. No coordinate/trajectory is
reopened for this audit, and progress stages and scientific stdout remain unchanged.

Runtime wall-clock duration uses the exact existing Stage 25.B start/end
timestamps; there is no additional clock read. The end remains the end of the
scientific workflow before technical writing. Environment is collected once after
successful science. Preprocessing condition count and sampled-frame count come
from the retained computation and its PBC observation tuple. Contact frame and
observation counts reuse the retained aggregate `frame_count` and `contact_count`;
without contacts they are `None`. Seconds/frame divides duration by positive
sampled-frame count. No CSV reads, filesystem inspection, contact recomputation,
or trajectory access supplies these counters. Analysis records condition count
and duration only: sampled-frame count, seconds/frame and contact counters remain
`None`, without invented upstream observations.

Completed-run writing follows this acyclic order:

```text
scientific/input artifacts + runtime metadata + preprocessing PBC audit
  -> artifact_inventory.json
  -> run_provenance.json references successful artifacts and inventory
```

Analysis follows the same chain under `analysis/`, without PBC. Technical files
participate in the existing `--artifact-checksum-mode {none,sha256}`: `none`
records exact sizes without checksum content reads; `sha256` streams the
already-written files. Inventory excludes itself and provenance; provenance has
no reciprocal hashes. Raw MD inputs remain source lineage, without publication
membership metadata.

`mania.runtime_metadata_io` and `mania.preprocessing.pbc_audit_io` provide strict
readers and atomic writers. Writers create target parents, use a temporary file
in the target directory, and publish UTF-8 JSON with indent 2, declared key order,
literal Unicode, finite values, and exactly one trailing newline. Existing targets
are preserved by default; overwrite atomically replaces them. Preprocessing uses
its existing overwrite setting and analysis uses `overwrite=True`. Readers reject
malformed JSON, duplicate keys, unknown/missing fields and invalid nested values,
and reconstruct the accepted frozen models without environment recollection,
clock, Git, hashing, trajectory access, or scans.

Runtime/PBC artifacts are required technical post-processing for completed runs.
A build/write failure retains scientific outputs, suppresses the successful
summary and returns exit 1. Inventory and completed provenance are still attempted,
including only successfully written technical artifacts in runtime, PBC, inventory
order after scientific references. Error prefixes are `Runtime metadata build
failed:`, `Runtime metadata write failed:`, `PBC audit build failed:` and `PBC audit
write failed:`; analysis uses `Analysis runtime metadata build failed:` or
`Analysis runtime metadata write failed:`. Later inventory/provenance errors
retain their existing prefixes and order.

Failed scientific runs retain the existing Stage 25.B/C failure metadata boundary:
they do not automatically persist E.2 runtime/PBC artifacts, even if observations
were retained in memory before failure. No failed-run inventory matrix is changed.

Unified validation delegates `runtime_metadata` to its strict reader in both
scopes, enforcing scope and canonical path, and preprocessing `pbc_audit` to its
strict reader. Unavailable, invalid or partial box observations and scientific
status `unresolved` can still be technically valid. Unresolved PBC science is
**not a technical validation failure** and does not imply scientific approval.

## Deferred scientific decisions

No PBC correction is implemented or promised. PBC preprocessing protocol,
internal minimum-image correction, lifetime, physical-time window semantics,
replica aggregation, cross-engine mapping, and Dataset v1.0 scientific
acceptance remain deferred. Stage 25.E does not wrap, unwrap, center, make molecules
whole, modify coordinates, change sampling, or change distances, contacts,
edge counts, RIN results, or Stage 20–24 scientific schemas.

## Publication validation note

The existing technical validation CLI intentionally returns exit 0 for both
`passed` and `partial` reports, and exit 1 for `failed`. Stage 25.G publication
acceptance must require a complete technical report: `report.status == "passed"`
and `report.complete is True`. This gate and any `--require-complete` option
are not implemented in Stage 25.F. Technical completeness does not resolve
scientific acceptance. Stage 25.F is complete; Stage 25.G is next and remains
planned. Stage 25 overall remains incomplete.

## Stage 27.C — physical selection observations

Dataset-aware preprocessing now plans physical sampling once before scientific
passes. Only exact resolved source frames enter Rg and contacts. PBC observations
remain on Rg when enabled, otherwise contacts, with no double collection. The
time-axis planning pass reads no dimensions and creates no PBC observations;
window planning creates no trajectory pass.

Each Dataset condition's PBC `sampled_frame_count` equals its temporal sampling
plan count, including accepted partial coverage. Existing runtime performance
counters derive from these observations and require no adapter/schema change.
Unified validation cross-checks those counts. No minimum-image correction is
applied and scientific PBC status remains `unresolved`. See the
[execution contract](physical_time_execution_contract.md).
