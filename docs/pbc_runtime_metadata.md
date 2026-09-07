# PBC audit and runtime metadata

## Status and boundary

Stage 25.E.1 is implemented: immutable observation models, environment collection,
runtime summaries, and PBC aggregation are available as Python APIs. Automatic
workflow integration is deferred to E.2. Stage 25.E remains incomplete.

**E.1 observes metadata only. It does not alter trajectories or distance
calculations.** It creates no automatic artifacts, CLI options, provenance
references, inventory entries, or validator coverage.

## Runtime/environment contract

`mania.runtime_metadata` provides `RuntimeEnvironment`, `RuntimePerformance`,
`RuntimeMetadata`, `collect_runtime_environment()`, `build_runtime_performance()`,
and `build_runtime_metadata()`.

The root schema is `mania.runtime_metadata.v0.1`, kind `mania_runtime_metadata`.
Its deterministic key order is `schema_version`, `kind`, `run_id`, `workflow`,
`scope`, `metadata_path`, `environment`, `performance`. Scope is `preprocessing`
or `analysis`. Paths are normalized portable relative POSIX paths ending with
the exact filename `runtime_metadata.json`; absolute paths, backslashes, URI
schemes, control characters, and `.`/`..` components are rejected. E.2 will enforce
the exact scope-specific location.

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

## Future E.2 integration

Intended future artifacts:

```text
<output>/runtime_metadata.json
<output>/pbc_audit.json
<output>/analysis/runtime_metadata.json
```

E.2 will capture PBC observations during existing sampled-frame processing,
without a second trajectory pass or rereading XTC/DCD files. It will reuse
Stage 25.B timestamps, derive counters already retained by accepted results
without recomputation, add generated technical artifacts to the existing
provenance/inventory chain, and update unified validation role coverage.
E.1 adds contracts only and preserves the current chain:

```text
SoftwareIdentity -> run_provenance.json -> artifact_inventory.json
                 -> unified technical validation
```

## Deferred scientific decisions

No PBC correction is implemented or promised. PBC preprocessing protocol,
internal minimum-image correction, lifetime, physical-time window semantics,
replica aggregation, cross-engine mapping, and Dataset v1.0 scientific
acceptance remain deferred. E.1 does not wrap, unwrap, center, make molecules
whole, modify coordinates, change sampling, or change distances, contacts,
edge counts, RIN results, or Stage 20–24 scientific schemas.

## Publication validation note

The existing technical validation CLI intentionally returns exit 0 for both
`passed` and `partial` reports, and exit 1 for `failed`. Stage 25.G publication
acceptance must require a complete technical report: `report.status == "passed"`
and `report.complete is True`. This gate and any `--require-complete` option
are not implemented in E.1. Technical completeness does not resolve scientific
acceptance. Stages 25.F/G remain planned; Stage 25 overall remains incomplete.
