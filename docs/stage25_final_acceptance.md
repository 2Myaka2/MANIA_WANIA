# Stage 25.G final acceptance

**Stage 25.G acceptance: PASS. Stage 25 — COMPLETE.** All 18 acceptance
criteria passed before documentation closeout. Stage 25.A–G are complete.

Stage 25 proves technical reproducibility/integrity hardening, not final
scientific Dataset v1.0 semantics.

## Acceptance snapshot and regression

- Branch: `FAIR`; initially clean, with `develop` an ancestor of HEAD.
- Acceptance code snapshot: `d7b85280daaa121c50e2a083a0c0917bdb3be447`.
- Stage 25 base / accepted pre-Stage-25 `develop`:
  `2f1cd267a79318e22d233f4c60931a7a7d6d7d93`.
- `.venv/bin/pytest`: **4512 passed, 22 skipped**. The skips comprise 20
  opt-in local scientific tests and two inapplicable no-checksum cases.
- `.venv/bin/ruff check .`: `All checks passed!`
- `.venv/bin/mypy src`: `Success: no issues found in 111 source files`.
- `.venv/bin/mania --version` and `.venv/bin/python -m mania --version`:
  `mania-wania 0.1.0`.
- Wheel: built with `pip wheel . --no-deps --no-build-isolation`, installed
  into a temporary target with `--no-deps`, and exercised outside the checkout.
  Version commands, runtime/PBC/validation imports, and preprocessing/analysis
  help passed. Installed-package software identity correctly reported Git
  information unavailable. Temporary wheel/install directories were removed.

## Controlled acceptance

The existing synthetic fixtures drove real preprocessing computation/export,
analysis with PCA, inventory, provenance, runtime metadata, PBC observation,
strict readers, and unified validation. Both scopes reported `passed` with
`complete: true`; analysis retained root preprocessing technical files and
reported its existing 17 scientific artifacts.

Targeted C–E regression coverage: **608 passed, 2 skipped**. It demonstrated
that checksum mode `none` records sizes without invoking `stream_file_sha256`
or opening file contents for inventory construction. The controlled E2E hash
spy recorded zero calls. Raw real trajectories were not hashed.

Controlled SHA256 smoke passed: expected digest, production streaming helper,
bounded-read regression, unchanged-file validation, detection of a same-size
content mutation, and `skipped_integrity_failure` for the specialized validator.
Inventories excluded themselves and their corresponding provenance; no checksum
cycles were introduced.

Preprocessing and analysis failure smokes preserved exit 1 and byte-identical
stdout/stderr against the Stage 25 base on the same controlled inputs. Failed
provenance read strictly, inventories claimed zero successful outputs, and
successful-run-only runtime/PBC artifacts were absent. Analysis preserved root
technical files. Existing metadata-postprocessing failure regressions confirmed
that successful scientific outputs survive technical metadata failures.

Version collection passed with optional scientific imports prohibited, including
MDAnalysis package metadata both present and unavailable.

## Real NaPi2b PoC

- Accepted baseline: `mania_output/napi2b_poc_last5ns_stride5`.
- Baseline evidence: `logs/napi2b_poc_commit.txt`,
  `logs/napi2b_poc_preprocessing.log`, `logs/napi2b_poc_analysis_fingerprint.log`,
  `local_md/manifests/napi2b_poc.yaml`, and the baseline artifacts themselves.
  The recorded commit equals the Stage 25 base. Logs, contact-frame CSVs,
  manifest declarations, and PCA configuration establish the accepted scope.
- New output: `local_md/stage25g_acceptance/d7b8528`.
- Local evidence: `local_md/stage25g_acceptance/d7b8528_evidence`.
- NORM + TUMOR (`normal`, `tumor`); final 5 ns, 5000–10000 ps;
  `frame_start=500`, exclusive `frame_stop=1001`, `frame_stride=5`, no cap;
  101 sampled frames per condition; protein contacts; analysis inputs exported;
  PCA enabled with the accepted default fingerprint clustering basis.

```bash
.venv/bin/mania preprocessing run-graph-export \
  --manifest local_md/manifests/napi2b_poc.yaml \
  --output local_md/stage25g_acceptance/d7b8528 \
  --expected-condition normal --expected-condition tumor \
  --contact-selection protein --export-analysis-inputs \
  --frame-start 500 --frame-stop 1001 --frame-stride 5 \
  --artifact-checksum-mode none --verbose

.venv/bin/mania analyze \
  --input local_md/stage25g_acceptance/d7b8528 \
  --output local_md/stage25g_acceptance/d7b8528 \
  --condition normal --condition tumor --enable-pca \
  --artifact-checksum-mode none
```

Both commands exited 0. Analysis stdout matched the accepted baseline summary,
including its 17 scientific artifacts. The completed output contains exactly
37 expected files: the 30 baseline counterparts and seven Stage 25 technical
artifacts, separated between preprocessing root and `analysis/`.

All **29 deterministic scientific artifacts are byte-identical** by `cmp`:
12 preprocessing artifacts (nine root analysis inputs and three `graph/`
artifacts) and all 17 analysis artifacts, including `extended_metrics.json`.
No expected scientific artifact was omitted. The thirtieth baseline file,
`reports/graph_diagnostics_report.json`, is a legacy technical report with six
run-directory references. Its only differences are those output-root references;
all other diagnostic fields agree. Baseline file sizes and scientific-output
SHA256 fingerprints remained unchanged. No baseline file was rewritten.

## Complete technical gate and observation semantics

| Scope | Status | Complete | Explicit mapped inputs | Inventory outputs |
| --- | --- | --- | --- | --- |
| Preprocessing | `passed` | `true` | 5 | 15 |
| Analysis | `passed` | `true` | 9 | 18 |

Both real CLI validations used `mania artifacts validate` with explicit scope
and every required `--input-artifact-path ARTIFACT_ID=LOCAL_PATH`. Preprocessing
mappings came from the manifest and accepted condition-input contract; analysis
mappings came from the actual analysis resolver and inventory specification API.
Exact portable command arguments and JSON reports are retained in local evidence.
The run satisfies the complete technical publication-style validation gate:
`report.status == "passed"` and `report.complete is True` for both scopes.

Strict readers verified inventory sizes/references, scope-specific provenance
and runtime metadata, and the PBC audit. Inventories exclude themselves and
corresponding provenance. Analysis did not overwrite root technical artifacts.
The runtime environment recorded CPython 3.12.3, Linux/x86_64, NumPy 2.4.6,
MDAnalysis 2.10.0, Pydantic 2.13.4, and PyYAML 6.0.3. Preprocessing counters
record 202 sampled/contact frames; analysis retains only its applicable counters.

PBC observations cover **only the 101 actually sampled frames per condition**,
cross-checked against effective provenance (source frames 500–1000; 50 ps spacing).
Both conditions have internally consistent counts and finite box ranges, with
length fields in Å and angle fields in degrees. These observations do not
establish whole-protein, centering, unwrapping, or scientific contact correctness.

- `mania_internal_minimum_image_correction_applied`: `false`.
- `scientific_pbc_status`: `unresolved`.
- `external_pbc_preprocessing_status`: `undeclared`.

Recursive privacy inspection covered all seven portable technical JSON artifacts
and 460 string values. No private absolute local paths, usernames, hostnames,
environment-value dumps, machine identifiers, or secrets were found. Dynamic
path/identity checks supplemented the explicitly supplied private-fragment checks.

## Scope and architecture pause

Path and semantic inspection from the resolved Stage 25 base found no WANIA
production changes, runtime/optional/build dependency changes, scientific Dataset
or output-schema changes, or unintended config/data changes. Packaging changes
only centralized the existing version and refreshed the project description.
Scientific computation additions were observation callbacks and retained technical
state; the real scientific byte comparison verifies their compatibility.

MANIA technical publication hardening is complete. Review scientific decisions
with Ramila Akhmetovna, then freeze the Dataset v1.0 scientific contract,
and only then design scientific extensions. Dataset v1.0 remains unreleased
and not scientifically frozen. Scientific PBC remains unresolved until the
scientific decision. FastAPI remains postponed.
