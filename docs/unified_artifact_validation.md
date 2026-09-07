# Unified artifact validation — Stage 25.D.1

## Status

Stage 25.D.1 is implemented as a Python integrity/reference API with strict disk
readers for the existing provenance and inventory contracts. Specialized-validator
coordination and the final unified CLI/API remain Stage 25.D.2. There is no
`mania artifacts validate` command yet. Stage 25.D and Stage 25 overall remain
incomplete; Stage 25.E–G remain planned.

## Purpose and boundary

D.1 checks technical integrity and cross-artifact consistency:

- technical metadata parses as the supported contract;
- provenance references correspond to inventory outputs;
- files exist and are regular files;
- exact byte sizes match;
- SHA256 matches when declared;
- run IDs, workflows, inventory locations, and conditions are consistent.

A passing technical result does not certify scientific acceptance. D.1 makes no
decisions about PBC correctness, contact definitions, contact lifetime semantics,
replica aggregation, or Dataset v1.0 scientific approval. A failed scientific run
can have technically consistent metadata and retained artifacts that pass D.1.

D.1 neither calls nor duplicates existing CSV, graph, manifest, Stage 20, Rg,
contacts, diagnostics, PCA, clustering, or temporal RIN validators. Scientific
content can pass these integrity checks even when it would fail a specialized
validator. D.2 will coordinate the existing validators.

## Strict disk readers

```python
from mania.artifact_inventory_io import (
    ArtifactInventoryReadError,
    read_artifact_inventory,
)
from mania.run_provenance_io import RunProvenanceReadError, read_run_provenance

inventory = read_artifact_inventory("out/artifact_inventory.json")
provenance = read_run_provenance("out/run_provenance.json")
```

Readers accept a non-empty string or `Path` identifying an existing regular file.
They read UTF-8 JSON objects with the exact supported schema version and kind.
Missing or extra contract fields, duplicate JSON keys, non-finite JSON constants,
invalid arrays/nested values, and inconsistent inventory counts are rejected.
Nullable fields and empty arrays must be present as emitted by `to_dict()`.
Resolved configuration retains its caller-defined JSON keys and values.

Existing constructors enforce portable paths, unique IDs/paths, checksum-mode
consistency, sampling constraints, and provenance ordering. Software identity
field validation occurs in the reader because that existing dataclass has no
constructor validation. The stored identity is preserved without calling Git or
`get_software_identity()`. Timestamp strings must be timezone-aware ISO 8601;
the existing provenance constructor normalizes them to UTC and serialization
uses the accepted UTC microsecond representation. No current clock is read.

Completed and failed provenance round-trip through the same reader. Readers
preserve inventory, condition, sampling, reference, issue, and command-token
order. Neither reader modifies the file or discovers other files. Expected read
failures raise the corresponding `ValueError` subclass with fixed messages and
no local paths or underlying exception representations. Schemas and writers are
unchanged; no schema migration framework is introduced.

## Integrity API and exact layouts

```python
from pathlib import Path
from mania.validation import validate_run_artifact_integrity

report = validate_run_artifact_integrity(Path("out"), scope="preprocessing")
payload = report.to_dict()

analysis_report = validate_run_artifact_integrity(Path("out"), scope="analysis")
```

`run_root` must be an exact native `Path`, and scope must be supplied explicitly.
There is no auto-detection or alternate-file search.

| Scope | Provenance | Inventory |
| --- | --- | --- |
| `preprocessing` | `run_provenance.json` | `artifact_inventory.json` |
| `analysis` | `analysis/run_provenance.json` | `analysis/artifact_inventory.json` |

All paths in this table and in reports are portable paths relative to `run_root`.
An output resolves only as `run_root / entry.path`. No `Path.resolve()`, directory
enumeration, basename matching, environment lookup, or fallback convention is
used. Unrelated files are ignored. As in the accepted inventory builder, a symlink
to a regular file can be inspected without resolving or serializing its target.

The validator reads both technical metadata files independently. Missing,
unreadable, or malformed metadata yields `provenance_read_error` or
`inventory_read_error` and a failed report rather than an ordinary validation
exception. If inventory loaded, its ordinary artifacts can still be checked;
cross-record checks require both models. Available provenance supplies the report
run ID/workflow, with inventory as fallback. Unavailable fields are null. Invalid
API argument types or scope raise `ValueError`.

Provenance must contain exactly one `artifact_inventory` reference at the scope's
expected path. Every other provenance reference must match an inventory output
path; D.1 does not require every inventory output to appear in provenance.
Non-null artifact conditions must occur verbatim in provenance conditions.

## External input portability

Stage 25.C deliberately omits execution-local input paths. An inventory path such
as `inputs/conditions/0001/trajectories/0001/trajectory.xtc` is a virtual lineage
identifier, not necessarily a file below the run directory. D.1 never guesses its
local location, even if a file happens to exist at that portable path.

External revalidation requires an explicit `artifact_id -> local Path` mapping:

```python
report = validate_run_artifact_integrity(
    Path("out"),
    scope="preprocessing",
    input_artifact_paths={
        "input:condition:0001:trajectory:0001": Path("source/trajectory.xtc"),
    },
)
```

Keys must be strings identifying input entries in that inventory. Unknown IDs,
including output IDs, yield `unknown_input_artifact_mapping`. Values must be exact
native `Path` objects and never enter report serialization. A mapped input gets
the same regular-file, size, and declared-checksum checks as an output.

An unmapped input has `resolution_status="not_resolved"`, null existence/size/
match observations, `sha256_checked=False`, and `sha256_matches=None`. It is not
reported as missing or invalid. One aggregate `external_inputs_not_resolved`
warning contains the unresolved count; there is no warning per trajectory.

## Deterministic reports

Frozen `ArtifactSetValidationIssue`, `ArtifactSetValidationRecord`, and
`ArtifactSetValidationReport` models expose independent JSON-safe `to_dict()`
results in fixed key order. Artifact records follow inventory order; issues follow
metadata reads, mapping checks, reference checks, artifact checks in inventory
order, and finally the aggregate unresolved warning. No local mapping values,
tracebacks, or underlying exception text are serialized.

| Status | Meaning |
| --- | --- |
| `failed` | At least one error issue exists. |
| `partial` | No errors, but at least one external input is unresolved. |
| `passed` | No errors and all inventory artifacts are resolved. |

The boolean `passed` means **no technical error issues**, so it is also true for a
partial report. `complete` means inventory was readable and no ordinary inventory
artifact remains unresolved; it does not mean all checks passed. Missing mapped
files are resolved locations with failed existence checks. Counts expose total
records, resolved records, unresolved inputs, errors, and warnings. Metadata
files are validated separately and never receive synthetic artifact records.
Forbidden self/provenance entries in a corrupt inventory produce errors and are
excluded from ordinary records and checksum reads.

Artifact errors distinguish `artifact_missing`, `artifact_not_file`,
`artifact_size_mismatch`, `artifact_checksum_error`, and
`artifact_checksum_mismatch`. An OS failure obtaining metadata yields
`artifact_stat_error`: existence cannot be confirmed (`exists=False`), and size
observations remain null. `sha256_checked` records a checksum attempt;
`sha256_matches=None` means verification was not applicable or did not finish.

Entries with `sha256=None` never have their content opened for checksum checks.
Declared hashes use the accepted bounded `stream_file_sha256` helper, including
its observed-file-mutation checks. Validation does not lock the filesystem or
claim an atomic snapshot of the whole run. It never changes checksum mode or
adds a checksum CLI switch.

## Acyclic metadata

```text
run provenance -> portable inventory reference -> artifact records
```

Inventory excludes itself and its corresponding provenance. The inventory model
continues to reject its own path and reserved role, and D.1 also protects the
actual expected inventory location if a corrupt root declares a different path.
The latter yields `inventory_self_reference`; a reverse provenance entry yields
`provenance_inventory_cycle`. No reciprocal checksum loop is required or created.
A portable provenance-to-inventory reference is sufficient.

## FAIR² publication boundary

An inventoried XTC, TPR, DCD, PSF, PDB, GRO, or other source MD file records source
lineage. It is not automatically part of the published Dataset v1.0. Inventory
and validation reports introduce no publication-membership field or inference.

The current FAIR² plan still assumes publication of derived dynRIN resources
rather than raw trajectories unless the dataset contract is changed later by the
authors. Publication membership belongs to the future FAIR² dataset package.

## Next step

Stage 25.D.2 will coordinate the existing specialized validators and expose the
final unified CLI/API. D.1 provides the reusable integrity/reference foundation
only; Stage 25.D acceptance remains outstanding.
