# Canonical NaPi2b reference contract

## Status

Stage 29 is complete. Stage 30.A canonical reference is implemented.
Stage 30.A is accepted. Stage 30.B explicit source mapping is implemented and
uses the local pinned reference as validation authority; no live UniProt
dependency was introduced. Stage 30 is complete.
Stage 30.B is accepted. Stage 30.C canonicalized intermediate tables are
implemented and use the pinned reference to validate canonicalized outputs.
Stage 30.C is accepted. Stage 30.D biological annotations/integration is complete.
Stage 31 replica/system aggregation is next and has not started.
Dataset v1.0 remains unreleased; the accepted scientific contract is unchanged.

## Canonical reference

| Field | Pinned value |
| --- | --- |
| Schema | `mania.canonical_reference.v0.1` |
| Kind | `mania_canonical_protein_reference` |
| UniProtKB accession | `O95436` |
| Canonical isoform | `O95436-1` |
| UniProt entry | `NPT2B_HUMAN` |
| Gene | `SLC34A2` |
| Protein | Sodium-dependent phosphate transport protein 2B |
| Organism | Homo sapiens |
| Sequence length | 690 aa |
| UniProt sequence version | 3 |
| Sequence last updated | `2010-11-30` |
| UniProt sequence MD5 | `16C21D07D36DC8B416EA72769F0B0280` |
| Local sequence SHA256 | `33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9` |
| Derived reference ID | `uniprotkb:O95436-1:sequence-v3` |

The frozen dataclasses live in `mania.canonical_reference`. This task chooses
the permitted **NaPi2b-only contract**, consistent with the fixed 1..690 residue
range and the repository's narrow stage-specific dataclasses. Both explicit
file reads and default loads require the pinned identity and sequence. Alternate
proteins, isoforms, sequence versions, or sequences are rejected, even when a
replacement sequence carries internally consistent checksums.

`CanonicalProteinReference` declares identity fields first, sequence provenance
second, sequence length and sequence third, and non-init `schema_version` and
`kind` last. Its `to_dict()` preserves that order. `reference_id` is derived from
isoform and sequence version and is not an extra JSON payload field. Both models
are frozen and expose no mutation APIs. Their dictionaries contain independent
scalar values. Compact `json.dumps(reference.to_dict(), allow_nan=False,
separators=(",", ":"))` is deterministic, with no clock or environment fields.

## Offline pinning

The single authoritative production sequence payload is
`src/mania/data/canonical/slc34a2_o95436_reference.json`. It ships inside the
installed wheel at `mania/data/canonical/slc34a2_o95436_reference.json`.
There is no independently maintained Python sequence copy.

`mania.canonical_reference_io.load_default_napi2b_canonical_reference()` reads
only that packaged local JSON through `importlib.resources`, independent of the
current working directory. Production runs never fetch UniProt, REST APIs, HTTP
endpoints, or external sequence databases. They never refresh or write the
reference. Missing or corrupt packaged data raises the deterministic
`CanonicalReferenceReadError`; no fallback or network retry exists.

`read_canonical_reference(path)` accepts a local UTF-8 JSON file under the same
NaPi2b-only contract. It rejects malformed JSON, duplicate keys, non-finite
constants, incorrect scalar types, missing or unknown fields, wrong schema/kind,
invalid metadata, invalid sequence alphabet/length, and checksum failures.
Integers must be actual positive integers, excluding booleans and floats.
Strings must already be non-empty and stripped; no biological normalization is
performed. Dates use strict `YYYY-MM-DD` calendar dates. MD5 must be 32 hex
characters and match the uppercase pin; SHA256 must be 64 lowercase hex
characters and match its pin.

## Provenance

The source system is `UniProtKB/Swiss-Prot`. The source URL
`https://www.uniprot.org/uniprotkb/O95436-1/entry` records where the pinned
reference originated. **It is not a live dependency.** It is provenance text
only and is never dereferenced during loading or execution.

The scientifically meaningful identity is pinned by accession, canonical
isoform, sequence version, sequence length, UniProt MD5, local SHA256, and the
exact sequence bytes. Both checksums are computed over ASCII sequence bytes
with no newline, not over formatted JSON. No production result depends on
current website contents, URL availability, hostname, local path, or network
state. There is no runtime retrieval timestamp.

An explicit local file may change only `source_record_url` to another non-empty
stripped string while retaining the valid biological identity and sequence.
This does not change `reference_id` or redirect the default loader. The shipped
JSON retains the approved source URL.

## Numbering

Canonical residue numbering is **1..690**, the 1-based positions of the O95436-1
canonical sequence. Position 1 is the first residue; position 690 is the last.
Position 0 does not exist. `reference.residue_at(canonical_residue_number)`
rejects booleans, non-integers, and positions outside that range. It accepts no
source identifiers. `reference.residues()` returns an immutable tuple of exactly
690 residue records in ascending position order; joining their one-letter
codes reconstructs the pinned sequence.

The coordinate smoke checks only these sequence-defined residues:

| Position | One-letter code | Canonical resname |
| --- | --- | --- |
| 1 | M | MET |
| 234 | V | VAL |
| 311 | Q | GLN |
| 330 | T | THR |
| 341 | V | VAL |
| 361 | D | ASP |
| 690 | L | LEU |

These checks attach no biological annotations.

## Canonical resname

`canonical_resname` is an uppercase standard three-letter amino-acid code,
derived deterministically from the sequence's one-letter code. Source topology
residue spelling has no authority here. `CanonicalResidueReference` validates
the position range, one supported letter, and exact translation. An independently
constructed residue record validates those local fields; `residue_at()` supplies
the additional evidence that the letter occurs at that pinned sequence position.

| One-letter | Three-letter | One-letter | Three-letter |
| --- | --- | --- | --- |
| A | ALA | L | LEU |
| R | ARG | K | LYS |
| N | ASN | M | MET |
| D | ASP | F | PHE |
| C | CYS | P | PRO |
| Q | GLN | S | SER |
| E | GLU | T | THR |
| G | GLY | W | TRP |
| H | HIS | Y | TYR |
| I | ILE | V | VAL |

## Namespace boundary

**`source_resid` and `canonical_residue_number` are different namespaces. Numeric
equality carries zero mapping authority.** Treat
`source_resid != canonical_residue_number` as the namespace boundary unless an
explicit, validated Stage 30.B mapping record proves the association.

For example, `source_resid = 311` does **not** imply
`canonical_residue_number = 311`. GROMACS residue 311 and NAMD residue 330 do not
acquire UniProt positions from their numeric values. Only an explicit validated
mapping record can establish a source-to-canonical identity.

## No mapping

Stage 30.A defines only the canonical target coordinate system. It performs no
source mapping, residue-number equality inference, default offsets,
`canonical = source + offset`, or first-residue alignment assumptions. There are
no sequence alignment, BLAST, pairwise alignment, PDB mapping, or automatic
sequence reconciliation algorithms or convenience APIs.

There are no biological annotations, ECD/MX35 flags, glycosylation sites,
mutation/disulfide annotations, or preprocessing workflow integration. Stage
27/28/29 science and source tables, contact/PBC behavior, provenance, inventory,
unified validation, analysis, dependencies, and WANIA remain unchanged.

## Verification

Model and I/O tests independently verify the approved sequence/checksums,
immutable field contracts, strict reads, coordinate ordering, and corruption
rejection. They block socket connections, urllib access, subprocesses, and Git
execution during default loading and inspect production imports for network
clients. A corrupt current-directory decoy cannot override the packaged data.
Wheel acceptance builds and installs into a temporary target, then loads and
reconstructs the reference outside the checkout with network/process access
blocked. Existing scientific regressions remain required.

## Mapping and next steps

Stage 30.B provides [explicit source-to-canonical mapping and strict offline
validation](canonical_residue_mapping_contract.md) against this local reference.
Stage 30.C applies validated mapping to protein/lipid/glycan Dataset window
tables. Stage 30.D adds biological annotations, workflow/provenance/validation
integration, and final Stage 30 acceptance. This integration is complete and
preserves the accepted reference semantics; see the
[biological annotation contract](biological_annotation_contract.md).
The [Stage 30.C table contract](canonical_window_table_contract.md) retains source
names alongside pinned canonical names without adding a live UniProt dependency.
