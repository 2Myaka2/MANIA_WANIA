# All-layer per-frame persistence and offline replay — Stage 34.D.4d

This additive contract preserves the Stage 34.D.4c temporal profiles and existing
protein, specialized, source-window, canonical, Stage 31 and Stage 33 contracts.
Dataset v1 remains unreleased. No full production run or launcher is added.

## Persisted evidence

| File | Version / representation | Purpose |
| --- | --- | --- |
| `contacts/contacts_perframe.csv` | Existing typed protein CSV, unchanged header and writer | Positive protein contacts and structural backbone observations |
| `perframe_completion.json` | `mania.perframe_completion.v0.1` | Complete requested-sample ledger, Dataset/sampling binding and per-layer completion counts |
| `protein_lipid_perframe.json` | `mania.protein_lipid_perframe.v0.1` | Exact accepted `mania.protein_lipid_contacts.v0.1` frame results |
| `protein_glycan_perframe.json` | `mania.protein_glycan_perframe.v0.1` | Exact accepted `mania.protein_glycan_contacts.v0.1` frame results, including excluded anchor observations |
| `molecular_partner_catalog.json` | Existing `mania.preprocessing_molecular_partner_catalog.v0.1` | Authoritative topology-local partner membership and linkage |
| `temporal_execution.json` | Existing v0.1 legacy / v0.2 inclusive | Authoritative sampling and window/profile execution |

Protein geometry is stored only in the existing CSV. The completion sidecar
adds typed residue identity, detection options and frame counts because sparse
CSV rows alone cannot establish zero-contact frames or distinguish integer and
string source residue IDs. Structural backbone rows round-trip but remain outside
the existing protein contact-window aggregation, exactly as before.

The completion root has exact fields `schema_version`, `kind`, `completion`,
`specialized_conditions`, `bindings` and `protein_csv_row_count`. Every binding
contains `execution_condition`, `dataset_identity`, `sampling_plan`,
`protein_options`, `protein_residues` and `samples`. It stores the accepted full
sampling plan unchanged; it does not store or infer a competing window profile.
Each requested sample contains:

- `requested_sample_index`, `requested_time_ps` and `state`;
- `source_frame_index` and `actual_time_ps` from temporal execution;
- nullable `prepared_frame_index`, supplied explicitly through the Python API
  when separate prepared-frame identity exists;
- `completion`, containing the per-layer status/counts for a resolved sample.

Source indexes retain the accepted enumeration of the trajectory supplied to
preprocessing. Separate prepared indexes are never guessed. An optional prepared
index sequence must cover every selected sample of its named condition, contain
unique increasing nonnegative integers, and remain null for missing samples.

Each specialized root has exact fields `schema_version`, `kind`, `bindings` and
`completion`. Every binding contains `execution_condition`, `frames`,
`frame_count` and `observation_count`. Frame objects preserve their existing fixed
schema, cutoff, distance unit and definition; time, protein/partner/evaluated-pair
counts; contact count; and every positive observation. Glycans additionally retain
excluded-contact count, carrier/first-sugar indexes, atom linkage, exclusion flag
and reason. Distances use JSON's lossless Python float round-trip without rounding.

## Completion and strict reading

A resolved sample requires a passed protein frame with `status: complete`, exact
contact and backbone counts, and its original informational frame time. For a
present specialized partner kind, it requires a complete frame result even when
`contact_count` is zero. The frame's evaluated-pair count remains available.

A missing expected sample has `state: missing` with null source frame, actual
time, prepared index and completion. It has no observation frame. Missing data
cannot become negative contacts. A resolved sample lacking an expected result is
an error, not a partial success or an inferred zero.

When authoritative metadata declares no partners of a kind, the resolved sample
has `status: not_applicable` for that kind and no geometry frames. When no partner
metadata was supplied, it has `status: unavailable`. An empty sparse source table
from an unavailable layer is not evidence that the layer was evaluated.

Writers validate coverage first, write observation files, then atomically publish
`perframe_completion.json` last. Authorized overwrite removes the old completion
marker before replacing observations. An interrupted write has no valid completion
claim. Readers require exact schemas/fields, finite values, full sample/frame and
observation counts, unique ordered identities, and agreement with the authoritative
Dataset identity and sampling plan. Duplicate JSON keys, duplicate samples or
observations, truncated files, missing frame results, extra rows, inconsistent
partner membership/linkage and false anchor-exclusion flags fail.

These checks establish structural completeness and consistency, not authenticity
against an actor rewriting every artifact. The existing optional inventory SHA256
mode remains the content-integrity mechanism; checksum mode `none` remains unhashed.
No schema or Decimal arithmetic outside these new artifacts changes.

## Existing command and Python API

The existing preprocessing command accepts the opt-in flag
`--persist-perframe-observations`. It requires enabled protein contacts and Dataset
binding for every execution condition. Specialized layers use the existing explicit
partner metadata. Without the flag, existing CLI outputs and behavior are unchanged.
There is no new launcher or production orchestration command.

The implementation APIs are:

```python
from mania.preprocessing.perframe_observations import (
    write_perframe_observations,
    read_perframe_observations,
)
from mania.preprocessing.window_replay import replay_window_tables

write_perframe_observations(output_dir, temporal, protein_results, specialized_results)
saved = read_perframe_observations(output_dir, temporal)
replayed = replay_window_tables(
    output_dir,
    temporal_json_path,
    mapping_bindings=authoritative_mapping_bindings,
)
```

Replay reads a single observation set once, delegates all windows to the accepted
aggregators, and optionally delegates canonical mapping to Stage 30. The result
contains protein/lipid/glycan source tables and, when mappings are supplied, their
normal canonical tables. Existing table writers persist these outputs for Stage
31/33 without a replay-specific schema or special treatment. No cross-replica
correspondence is inferred; Stage 31 still requires explicit authority.

A caller may supply a different validated window execution with the same exact
Dataset identity and sampling plan. This permits several overlapping windows,
alternate window schedules and either accepted profile to reuse the same saved
observations. Geometry is never recomputed per window. Saved temporal execution
provides the profile; local right-endpoint flags are not used to infer it.

Unified preprocessing validation recognizes the new inventory/provenance roles,
checks complete artifact lineage, and reconstructs all source tables exactly.
Existing Stage 30 validation then reconstructs canonical/annotated tables from
those sources. Historical runs without the new roles retain their old validation
path. Validation never discovers or opens trajectory/topology contents.

## Scientific and production boundaries

Occupancy uses resolved frames. Missing requested samples break episodes;
`gap_tolerance = 0`; singleton lifetime is zero. Inclusive shared endpoints
participate independently in each window. Positive-frame distances, lipid 6.0 Å,
glycan 4.5 Å, heavy-atom geometry, glycan anchor exclusion and the absence of
specialized `edge_weight` remain unchanged. No PBC or Decimal changes occur.

Tests block geometry functions, trajectory iteration and MDAnalysis imports during
replay, and restrict data reads to persisted observations, temporal evidence and
the bundled canonical reference. Tests also feed replayed positive canonical CSVs
through existing Stage 31 and Stage 33 workflows for both profiles. Synthetic
fixtures prove software compatibility; they do not satisfy real pilot/QC gates.

A supported Egor production interface still requires its separately scoped
launcher/operational interface, complete raw bundles, authoritative per-topology
controls and canonical mappings, real full-trajectory QC/PBC preparation and source
lineage, and real partner correspondence for specialized replica aggregation.
This stage does not certify readiness or run production MD.
