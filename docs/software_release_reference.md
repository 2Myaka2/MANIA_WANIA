# MANIA software release reference and consumer dataset bridge

## Purpose

This is a generic documentation contract for using accepted MANIA software/run
metadata in a consumer dataset repository. It is not a new machine schema,
serializer, CLI command, or scientific/publication schema.

```text
MANIA software release/commit
  -> MANIA runs and technical metadata
  -> consumer dataset assembly
  -> dataset release
```

MANIA owns software/run technical metadata. The dataset repository owns dataset
release metadata, manuscript, annotations, final dataset schemas, FAIR² package,
dataset DOI and dataset version. MANIA must not own those dataset-specific
publication decisions. A MANIA software release/commit is not a dataset release:
the MANIA version is not the NaPi2b Dataset v1.0 version. Every dataset release
must point back to the exact MANIA software identity that generated its data.

## Software reference identity

A consumer reference should record the following conceptual information using
its own record format and paths:

| Concept | Source and responsibility |
| --- | --- |
| Software name | `SoftwareIdentity.software_name` (`MANIA`); `distribution_name` identifies `mania-wania` |
| Canonical software repository URL | Supplied and verified by the consumer/reference record; absent from SoftwareIdentity |
| Reported package version | Exact `SoftwareIdentity.version` |
| Exact full commit SHA | `SoftwareIdentity.commit_sha` when available; retain `commit_source` and `working_tree_status` as evidence of availability and checkout state |
| Release tag | Include only when a real MANIA release tag actually exists and its target commit is verified |
| Reference status, such as draft/released | Owned by the consumer dataset repository; cannot be inferred from a MANIA version |

Identity precedence is:

1. The exact commit SHA identifies the source snapshot.
2. The package version identifies the software version.
3. A real release tag provides an additional human-facing reference.

A tag must not replace exact commit identity in reproducibility records. Do not
add repository URL, release tag, DOI, or consumer status fields to SoftwareIdentity.
There is no MANIA software-release serializer to invoke. Populate/refresh the
consumer record from the actual provenance `software_identity` object, plus
consumer-verified repository/release facts, under the consumer's existing rules.

`commit_sha = null`, `commit_source = "unavailable"`, and unavailable tree status
are honest supported states, common for wheel installations without Git metadata.
Do not substitute the shell's current repository HEAD for missing run identity.
If exact source traceability is required, retain independently verified build/source
evidence in the consumer record, or generate from an identifiable source checkout;
do not invent a SHA in the MANIA artifact. A dirty working tree can contain changes
outside the recorded commit, so its SHA alone does not reconstruct the executed
source. Account for those changes before treating generation as source-pinned.

## Refresh-before-dataset-generation rule

Before production dataset generation, do not blindly reuse an old
architecture-audit commit or a stale software-reference record:

1. Rerun `mania --version` and `python -m mania --version` in the environment
   that will execute the work.
2. Check the current identity with the existing Python API if needed:

   ```bash
   python -c 'import json; from mania.software_identity import get_software_identity; print(json.dumps(get_software_identity().to_dict()))'
   ```

3. Capture the actual generation run provenance and confirm its full commit SHA,
   package version, commit source and working-tree status. Reconcile unavailable
   or dirty state; a version command alone cannot confirm the source snapshot.
4. Refresh the consumer software-reference record from that generation identity,
   keeping only real, verified release references and consumer-owned status.
5. Retain links to the actual preprocessing and analysis run provenance used to
   generate the data. If runs used different identities, retain every identity
   and its run association rather than presenting one commit as covering all runs.

These steps use existing metadata; they do not freeze a Dataset v1.0 schema or
require a particular historical commit or future release tag.

## Bridge from software to run

The evidence can be followed as:

```text
SoftwareIdentity (embedded in run_provenance.json)
  -> run_provenance.json
  -> artifact_inventory.json
  -> runtime_metadata.json / pbc_audit.json (preprocessing only)
  -> unified technical validation evidence
```

These arrows describe reading/traceability, not physical creation order or a
series of hash links. The actual reference DAG has provenance embedding software
identity and pointing directly to successful artifacts plus inventory. Inventory
records the scientific/input artifacts and successfully written runtime/PBC files.
Validation consumes provenance, inventory and explicitly resolved files, producing
a separate report; runtime/PBC files do not point to that report.

Physical writing proceeds from scientific outputs and runtime/PBC metadata to
inventory, then provenance. Provenance's inventory link is a portable `role`/`path`
reference. Inventory excludes itself and corresponding provenance, so there is
no self-hash or reciprocal hash loop. Analysis uses the same relationships under
`analysis/` and emits no PBC audit. The
[reproducibility guide](reproducibility.md) explains execution and each record.

## Recommended provenance material for a consumer dataset

A consumer FAIR² repository MAY preserve copies or release-bound references to:

| Source | Existing technical material |
| --- | --- |
| Preprocessing run | `run_provenance.json`, `artifact_inventory.json`, `runtime_metadata.json`, `pbc_audit.json` |
| Analysis run | `analysis/run_provenance.json`, `analysis/artifact_inventory.json`, `analysis/runtime_metadata.json` |
| Validation evidence | Serialized output from `mania artifacts validate` when needed, including scope, status and completeness |

The consumer chooses its own provenance-package paths. Preserve original records
and their run associations; if packaging relocates files, keep a consumer mapping
back to original run roots and artifact IDs rather than rewriting accepted MANIA
metadata into a new schema. Full revalidation still requires the referenced
files and explicit input mappings; preserving metadata alone does not provide
every input. A validation report generated after the run is not automatically a
member of that run's inventory.

Do not copy MANIA backend source into the dataset repository; use a software
reference to the maintained software repository/source snapshot. This bridge
does not require copying raw trajectories. Before publishing provenance material,
review consumer-supplied free text and input manifests for personal/local data;
runtime collection itself excludes username, hostname, absolute local paths,
environment variables and machine serial identifiers.

## Raw MD boundary

An XTC, TPR, DCD, PSF, PDB, GRO, or other MD input may appear in MANIA artifact
inventory for lineage/integrity. Raw MD inventory does not imply dataset
membership: that does NOT make the raw file a member of the published dataset or
establish permission to distribute it. The current NaPi2b FAIR² plan expects
derived dynRIN resources rather than raw MD trajectories unless the authors later
change that dataset contract. Keep lineage and publication membership separate.

## NaPi2b example (non-normative)

The separate dataset/article consumer repository `napi2b-dynrin-fair2` may keep a
software-reference record at a consumer-controlled location such as
`provenance/software/MANIA_RELEASE.json`. Its maintainers should refresh that
record from the MANIA software identity actually used for production generation
and retain references to the associated run provenance and validation evidence.
The filename does not prove a formal MANIA release or a released dataset record.

This example neither changes that repository nor declares Dataset v1.0 released.
The dataset release remains separate from the MANIA release. It defines no final
release tag, Dataset v1.0 schema, Croissant record, or author/CRediT metadata.
Those decisions remain owned by the consumer.

## Release vs commit

Valid reference states include a development/production run pinned by exact
commit, a formal MANIA release pinned by tag + exact commit, and a dataset
release citing whichever exact MANIA source generated it. These are separate
software and dataset lifecycles. A missing formal MANIA release tag is not a
reason to fabricate one, and an exact source reference alone is not publication
approval.

## FAIR² interpretation

These records support reproducibility, provenance, traceability, and integrity
verification. They do not by themselves satisfy every FAIR² publication requirement.
Final dataset licensing, DOI, Croissant, authorship/CRediT, annotations, scientific
protocol approval and release completeness remain consumer/dataset concerns;
the final Dataset v1.0 schema and final Croissant remain deferred here.

Technical validity is not scientific acceptance. PBC correction is not
implemented by MANIA; scientific PBC status remains unresolved. Contact lifetime,
physical-time windows, replica aggregation and cross-engine mapping remain
outside this task's implementation/approval scope. Observed box metadata does not
prove scientifically PBC-correct contacts. A technically valid metadata set does
not establish Dataset v1.0 scientific approval or publication readiness.

The current validator retains `passed -> exit 0`, `partial -> exit 0`, and
`failed -> exit 1`. Future Stage 25.G publication-style technical acceptance must
require `report.status == "passed"` and `report.complete is True`; Stage 25.F
does not implement that gate or add `--require-complete`. Even that future
complete/pass gate will not replace separate scientific acceptance.
