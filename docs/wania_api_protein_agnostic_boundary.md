# WANIA API protein-agnostic boundary

## Purpose

MANIA/WANIA must be protein-agnostic. The accepted Stage 15 backend graph
workflow is a run/output-root workflow, not a NaPi2b-only workflow and not a
final WANIA API contract.

This document records a documentation and testing boundary for future Stage
16 API/storage/frontend design. It does not implement FastAPI, API schemas,
database models, frontend payloads, or any runtime behavior.

## Protein run metadata

Future Stage 16 API/job metadata should include:

- `protein_id`: stable machine-readable identifier, for example `"napi2b"` or
  `"egfr"`;
- `protein_name`: human-readable display name, for example `"NaPi2b"` or
  `"EGFR"`;
- `run_name`: user-facing run label, for example `"napi2b_10ns_protein"`;
- `condition_names`: states/groups inside this run, for example
  `["normal", "tumor"]`.

Example future metadata:

```json
{
  "protein_id": "napi2b",
  "protein_name": "NaPi2b",
  "run_name": "napi2b_10ns_protein",
  "condition_names": ["normal", "tumor"]
}
```

```json
{
  "protein_id": "egfr",
  "protein_name": "EGFR",
  "run_name": "egfr_mutant_test",
  "condition_names": ["wild_type", "mutant"]
}
```

Do not implement this metadata in code as part of this docs boundary. Do not
add API schemas or database models in this task.

## Conditions vs protein identity

Conditions are states/groups within a protein run. Conditions are not protein
identity.

Correct:

```text
protein_id = "egfr"
condition_names = ["wild_type", "mutant"]
```

Incorrect:

```text
condition_names = ["egfr", "napi2b"]
```

Example condition names include:

```text
normal
tumor
wild_type
mutant
apo
ligand_bound
```

A condition may represent a state, group, variant, experimental condition, or
biological/structural category inside one protein run.

## NaPi2b sample boundary

NaPi2b is current sample/test data only. NaPi2b examples may remain useful for
local documentation and tests, but future Stage 16 API and storage design must
not hardcode NaPi2b as the product target.

The current backend graph workflow must remain generic for other proteins
such as EGFR when callers provide an accepted preprocessing manifest and local
inputs through the existing Stage 15 boundaries.

## One uploaded package/job = one protein run

One uploaded package should represent one protein run. One job should
represent one protein run.

Within that run, `condition_names` describe states/groups such as `normal` and
`tumor`, or `wild_type` and `mutant`. They do not select between different
proteins.

## Artifact storage boundary

Output artifacts should be associated with a run/job. Graph/scientific
artifact paths must not hardcode a specific protein.

Acceptable conceptual examples for future Stage 16 job/output storage include:

```text
outputs/<run_id>/graph/nodes.csv
outputs/<run_id>/graph/edges.csv
outputs/<run_id>/graph/graph.json
outputs/<run_id>/rg/rg_timeseries.csv
outputs/<run_id>/contacts/contact_edges.csv
```

or:

```text
jobs/<job_id>/artifacts/...
```

These examples do not prescribe a final API storage implementation and do not
change the current Stage 15 output layout.

## What Stage 16 should design

Future Stage 16 API work should design a protein-agnostic future API boundary
around generic protein runs, not NaPi2b-specific assumptions.

Stage 16 should decide how uploads/jobs carry `protein_id`, `protein_name`,
`run_name`, and `condition_names`; how run/job artifacts are stored and
retrieved; and how WANIA frontend/API payloads are shaped. Temporal RIN, if
added later, should also be generic per protein run.

## Future multi-protein product scope

Full multi-protein dashboard or catalog behavior is future product scope.
Cross-protein comparison is future scope.

Cross-protein comparison may require residue/sequence/structure mapping or
alignment before results can be compared responsibly. The current backend
graph workflow must not imply cross-protein comparability by default.

## Out of scope for current backend workflow

The current Stage 15 backend workflow does not implement:

- FastAPI endpoints;
- API schema objects;
- upload/job storage;
- protein database/catalog models;
- WANIA frontend payloads;
- cross-protein comparison;
- residue, sequence, or structure mapping;
- temporal RIN artifacts.

No FastAPI/API schema is implemented in this task.

## Guardrails for Stage 16

- Keep API/storage/frontend design protein-agnostic.
- Do not hardcode NaPi2b in API routes, job metadata, storage paths, or
  frontend payload assumptions.
- Treat one uploaded package/job as one protein run.
- Keep conditions as states/groups inside one protein run.
- Keep output artifacts associated with run/job identity.
- Keep multi-protein dashboard/catalog/comparison out of the current backend
  graph workflow.
- Do not infer protein identity from `condition_names` or path names.
