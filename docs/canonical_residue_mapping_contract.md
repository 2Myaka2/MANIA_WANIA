# Explicit canonical residue mapping contract

## Status

Stage 29 is complete. Stage 30.A is accepted. Stage 30.B explicit source mapping
is implemented as a standalone contract with strict offline validation.
Stage 30.B is accepted. Stage 30.C canonicalized intermediate tables are
implemented through exact source keys and explicit replica-key bindings.
Stage 30 is complete. Stage 30.C is accepted. Stage 30.D biological annotations/integration is complete.
Stage 31 replica/system aggregation is next and has not started.
Dataset v1.0 remains unreleased; its frozen scientific contract is unchanged.

## Target authority

Every mapped target is validated against the accepted local Stage 30.A reference:

| Field | Value |
| --- | --- |
| Reference ID | `uniprotkb:O95436-1:sequence-v3` |
| Canonical isoform | `O95436-1` |
| Sequence version / length | 3 / 690 aa |
| Sequence SHA256 | `33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9` |

`load_default_napi2b_canonical_reference()` supplies the packaged authority.
There is no duplicated sequence or independent canonical residue-name table.
`validate_canonical_residue_mapping_table(table, reference=reference)` requires
the exact accepted `CanonicalProteinReference` type, reference ID, and sequence
checksum. Each mapped number/name must match `reference.residue_at(number)`.
Validation returns the same table without changing records.

## Exact source namespace

**`source_resid != canonical_residue_number` unless an explicit mapping row
asserts the relationship. Numeric equality gives no authority.** These are
different namespaces; equal-looking values do not establish an association.

The complete source key, in order, is:

```text
(source_engine, source_chain_id, source_resid, source_resname)
```

All four fields participate in exact lookup. `source_engine` accepts only
lowercase `gromacs` or `namd`; uppercase names and typos fail. Chain may be
`None`; when present, it is a non-empty, already stripped string. Case is
preserved. No chain or segment identity is inferred.

`source_resid` is always a non-empty, already stripped **string**, including
`"311"`, `"330"`, `"330A"`, and `"15:CA"`. It is never parsed as an integer or
used in arithmetic. `source_resname` is also a non-empty, already stripped,
case-sensitive string. It preserves source topology evidence without canonical
three-letter-code conversion. No field is silently normalized.

Keys do not include source residue index, condition, Dataset ID, system ID,
trajectory ID, or replica ID. There is no fallback to engine/resid, chain/resid,
resid alone, residue index, or condition. If a future trajectory application
finds the four-field namespace ambiguous, it must fail rather than infer a rule.

## Record and state

`mania.canonical_residue_mapping.CanonicalResidueMappingRecord` is a frozen
dataclass with these exact fields in declaration and serialization order:

| Field | Type |
| --- | --- |
| `source_engine` | `str` |
| `source_chain_id` | `str \| None` |
| `source_resid` | `str` |
| `source_resname` | `str` |
| `canonical_residue_number` | `int \| None` |
| `canonical_resname` | `str \| None` |
| `mapping_status` | `Literal["mapped", "unmapped"]` |

For `mapped`, canonical number and name are required. The number must be an
actual integer in **1..690**; booleans, floats, and strings fail. Construction
checks the name's syntax: three uppercase ASCII letters. Reference validation
additionally requires the exact standard three-letter name at that pinned
position; readers, writers, and canonical resolution always perform this check.
A syntactically valid name alone does not establish a valid canonical target.

For `unmapped`, both canonical fields must be `None` (JSON `null`). Sentinel
values such as `0`, `-1`, `UNK`, or `NA` are forbidden. An explicit unmapped row
is distinct from an absent source key. Neither supplies a canonical coordinate.

### Variants

**`source_resname` may differ from `canonical_resname`.** For a T330M source
variant, source `MET` maps explicitly to canonical O95436-1 position 330 `THR`.
This is expected, not an error. Both names remain unchanged. Canonical `MET`
at position 330 fails because the pinned WT reference has `THR` there. Lookup
with source `THR` cannot match an explicit source `MET` key.

### No inference

Missing explicit mapping means **no mapping**, even when canonical position
311 exists as GLN and the queried source is `gromacs / A / "311" / GLN`.
Tests also explicitly map source `"311"` to canonical position 312 with its
reference-valid name. This is a synthetic namespace proof, not a biological
NaPi2b mapping claim. Removing the row leaves the source lookup missing.

There are no residue-number or chain offsets, sequence-start assumptions,
sequence alignment, BLAST, pairwise alignment, residue-name matching heuristics,
PDB/UniProt live mapping, or web/API lookup. No automatic mapping fallback exists.

## Table and ordering

`CanonicalResidueMappingTable` is frozen and accepts only a tuple of exact
`CanonicalResidueMappingRecord` objects. Source keys must be unique and already
sorted by engine, then chain (`None` uses an empty sort key), then lexical
source resid, then source resname. Neither construction nor reading silently
sorts records. For example, string `"100"` sorts before `"20"`.

Repeated canonical target numbers are allowed for distinct explicit source
keys, including different engines or chains. This does not infer equivalence
between rows. Empty and sparse tables are structurally valid: there is no
requirement for 690 rows or contiguous source/canonical positions. A passing
empty table has zero counts and establishes no trajectory coverage. Application
and per-trajectory coverage requirements belong to Stage 30.C/30.D.

## Strict JSON control artifact

Stage 30.B uses a strict self-describing JSON mapping table so the target
canonical reference identity/checksum travel with the explicit mapping records.
Later publication tables remain CSV. There is no duplicate CSV representation
in 30.B, and this control artifact is not a Dataset publication table.

The default/control filename is `canonical_residue_mapping.json`.
`mania.canonical_residue_mapping_io` reads and writes exact root keys in order:

1. `schema_version`: `mania.canonical_residue_mapping.v0.1`
2. `kind`: `mania_canonical_residue_mapping`
3. `canonical_reference_id`: the pinned ID above
4. `canonical_reference_sequence_sha256`: the pinned SHA256 above
5. `mapping_count`: actual integer equal to the array length
6. `mappings`: array of the seven-field records in exact source-key order

Root and row object key order is strict on input as well as output. The reader
rejects missing/unknown fields, duplicate JSON keys, malformed UTF-8/JSON,
non-finite constants, incorrect scalar types, changed target provenance,
count mismatches, duplicate source keys, unsorted rows, invalid null states,
and wrong canonical positions/names. It then validates with the packaged local
reference. Errors are deterministic and contain no local paths or input values.

`write_canonical_residue_mapping(table, path, overwrite=False)` validates the
table against the local reference before filesystem mutation. Invalid arguments
or reference semantics raise; filesystem/serialization failures return a frozen
`CanonicalResidueMappingWriteResult(output_path, written, error)` with `passed`.
Serialization is UTF-8 with `indent=2`, `sort_keys=False`, `ensure_ascii=False`,
`allow_nan=False`, and one trailing newline. Identical tables produce identical
bytes at different destinations; compact `json.dumps(table.to_dict(),
allow_nan=False, separators=(",", ":"))` is deterministic too.

Publication uses a temporary file in the destination directory. Overwrite uses
atomic replacement; default publication uses an atomic no-clobber link, which
also protects a concurrently created destination. Cleanup touches only that
writer's temporary file. No timestamps, UUIDs, environment metadata, local paths,
or extra metadata enter the JSON payload.

`validate_canonical_residue_mapping(path)` delegates interpretation to the strict
reader once. Its frozen report contains the path, mapping/mapped/unmapped counts,
and `(field, message)` issues. Failure leaves all counts `None`; passing reports
contain exact counts and no issues. `passed` means this control file validates,
not that any trajectory is covered or ready for publication.

## Lookup and resolution

| API | Result |
| --- | --- |
| `find_source_residue_mapping` | Exact record or `None` when absent |
| `require_source_residue_mapping` | Any explicit record, including unmapped; absence raises |
| `require_mapped_source_residue` | Explicit mapped record; absence or unmapped raises |
| `canonical_residue_for_mapping(record, reference)` | Validated pinned residue for an explicit mapped record |

Lookup arguments obey the same strict source-field contract. Lookup establishes
only the presence/state of explicit evidence; canonical semantic validation is
provided separately by the table validator, reader/writer, and resolution helper.
Resolution accepts a record, never source fields from which to infer a mapping.

## Offline verification and scope

Tests block socket/urllib, subprocess/Git, and clock access. The reader,
validator, and writer use no network or runtime identity discovery. A corrupt
current-directory reference decoy cannot replace the packaged Stage 30.A data.
The scientific smoke round-trips an explicit synthetic `"311"` to 312 row,
T330M `MET` to canonical `THR`, and an explicit unmapped row. Wheel verification
exercises these APIs outside the checkout using only installed package resources.

30.B does not bind mapping to a Dataset trajectory and does not modify source
tables. It adds no canonical output tables, publication CSVs, manifest bindings,
workflow/CLI changes, provenance/inventory changes, unified validation integration,
or biological annotations. Stage 27–29 science, PBC, analysis, dependencies, the
frozen Dataset scientific contract, and WANIA remain unchanged.

Stage 30.C applies explicit mapping to protein/lipid/glycan window outputs
through exact source keys and explicit `(dataset_id, system_id, trajectory_id,
replica_id)` binding, never condition. Its
[canonicalized intermediate tables](canonical_window_table_contract.md)
preserve source evidence and reject missing,
unmapped, and colliding application identities without changing 30.B semantics.
Stage 30.D integrates mapping and biological annotations with workflow,
provenance, validation, and final Stage 30 acceptance. The accepted mapping
semantics remain unchanged; see the [integrated annotation contract](biological_annotation_contract.md).
