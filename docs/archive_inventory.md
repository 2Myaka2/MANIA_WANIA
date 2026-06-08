# Archive Inventory and Source-of-Truth Decisions

## 1. Purpose

This document records how the MANIA/WANIA backend should treat the v1.1
archive/reference materials under `data/reference/notebooks_libraries_v1_1/`.

The backend contract is the stable WANIA-facing layer. Notebook outputs are
reference/intermediate artifacts: they can guide later engineering work, but
their filenames, directory layout, and duplicated exports must not become the
backend contract. A future export adapter may translate notebook-like outputs
into backend contract outputs while preserving the stable WANIA-facing output
defined by `docs/data_contract.md` and `src/mania/constants.py`.

## 2. Current backend status

The backend is still an engineering skeleton. The package structure exists, the
CLI skeleton exists, config validation exists, and the current pipeline builds a
placeholder plan instead of running scientific trajectory analysis.
`docs/data_contract.md` defines the planned WANIA-facing output contract,
`src/mania/constants.py` mirrors contract names and columns, and the residue
registry is still a placeholder. Tests and CI exist for the skeleton. Real
scientific trajectory analysis is not implemented yet.

## 3. Archive inventory

| Group | Examples | Role | Source of truth? | Commit to backend? |
| --- | --- | --- | --- | --- |
| This document | `docs/archive_inventory.md` | Concise inventory and source-of-truth decision record | Yes, for archive handling decisions | Yes |
| notebooks | `MANIA_preprocessing_v1_1.ipynb`, `MANIA_analysis_v1_1.ipynb` | Reference workflow and migration guide | No | No |
| residue library main JSON | `residue_library/mania_residue_library.json` | Source of truth for residue classification/QC | Yes, for residue classification/QC | No; do not commit the full library |
| residue library summary TSV | `residue_library/mania_residue_library_summary.tsv` | Human-readable summary of the residue library | No | No |
| residue library builder script | `residue_library/build_mania_residue_library.py` | Reference builder logic for the archive library | No | No |
| CHARMM/toppar files | `residue_library/toppar_c36_jul22/*.rtf`, `residue_library/toppar_c36_jul22/*.str` | Upstream reference inputs for residue-library construction | No | No |
| old v0.1 residue library files | `residue_library/v0.1/common_residue_library/*.json`, `*.tsv` | Legacy comparison/reference materials | No | No |
| old preprocessing outputs | `results/preprocess_export/residue_table_normal.csv`, `protein_contact_edges_undirected_tumor.csv` | Earlier reference/intermediate artifacts | No | No |
| v1.1 preprocessing outputs | `results/preprocess_export_v1.1/residue_table_normal.csv`, `protein_contact_edges_undirected_normal.csv`, `mania_manifest.json` | Reference/intermediate artifacts from preprocessing | No | No |
| v1.1 analysis outputs | `results/analysis_exports/centrality_normal.csv`, `communities_tumor.csv`, `graph.json`, `stats.csv` | Reference/intermediate analysis exports | No | No |
| Rg outputs | `results/preprocess_export_v1.1/rg_timeseries_normal.csv`, `rg_timeseries_tumor.csv` | Reference/intermediate global protein Rg time series | No | No |
| residue QC report | `results/preprocess_export_v1.1/residue_qc_report.csv` | Reference QC output for residue classification | No | No |
| manifests/configs | `mania_manifest.json`, `manifest.json`, `mania_config.json`, `edge_semantics.json` | Reference metadata/config artifacts | No, except stable backend contract docs/constants | No |
| figures | `results/analysis_exports/figures/*.png`, `results/preprocess_export_v1.1/figures/*.png` | Reference visual outputs only | No | No |
| parquet contact files | `contacts_perframe_normal.parquet`, `contacts_perframe_tumor.parquet` | Reference/intermediate per-frame contact tables | No | No |
| future tiny artificial fixtures | Task-specific fake files | Minimal tests for validators or export adapter behavior | No | Yes only when explicitly requested by a task |

## 4. Source-of-truth decisions

1. `mania_residue_library.json` is the source of truth for residue
   classification/QC.
2. The full residue library must not be copied into `src/mania/residues.py`.
3. Residue classification should later go through a loader/validator layer.
4. Notebook outputs are reference/intermediate artifacts.
5. `docs/data_contract.md` and `src/mania/constants.py` define the stable
   WANIA-facing backend contract.
6. `rg_timeseries_{condition}.csv` from the notebook should later map to
   `{condition}/rg_timeseries.csv` in the backend contract.
7. `contacts_perframe.parquet` must include `condition`, even if stored inside
   a condition-specific folder.
8. Combined graph node IDs must be condition-scoped, for example `normal:1` and
   `tumor:1`.
9. `comparison.csv` and `stats.csv` have different meanings and must not be
   blindly copied from duplicated notebook outputs.
10. Full reference outputs, figures, parquet files, CHARMM/toppar files, and the
    full residue library should not be committed to backend.
11. Small artificial test fixtures are allowed only when a specific task asks
    for them.

## 5. How archive artifacts should be used

| Artifact | Use as | Future backend layer |
| --- | --- | --- |
| `MANIA_preprocessing_v1_1.ipynb` | Reference workflow for preprocessing concepts | Controlled notebook block migration later |
| `MANIA_analysis_v1_1.ipynb` | Reference workflow for analysis concepts | Controlled notebook block migration later |
| `mania_residue_library.json` | Source of truth for residue classification/QC | Residue library loader/validator |
| `residue_qc_report.csv` | Reference QC output | Reference artifact validators |
| `rg_timeseries_normal.csv` | Reference/intermediate Rg output for normal | Export adapter to `normal/rg_timeseries.csv` |
| `rg_timeseries_tumor.csv` | Reference/intermediate Rg output for tumor | Export adapter to `tumor/rg_timeseries.csv` |
| `residue_table_{condition}.csv` | Reference/intermediate residue table | Export adapter to `{condition}/nodes.csv` |
| `centrality_{condition}.csv` | Reference/intermediate centrality table | Export adapter to `{condition}/centrality.csv` |
| `communities_{condition}.csv` | Reference/intermediate community table | Export adapter to `{condition}/communities.csv` |
| `protein_contact_edges_undirected_{condition}.csv` | Reference/intermediate protein contact edges | Export adapter to `{condition}/edges.csv` |
| `contacts_perframe_{condition}.parquet` | Reference/intermediate per-frame contacts | Export adapter to `{condition}/contacts_perframe.parquet` |
| `graph.json` | Reference graph export; condition scoping must be validated | Export adapter to per-condition `graph.json` |
| `mania_manifest.json` | Reference preprocessing manifest | Manifest validator and export adapter input |
| `manifest.json` | Reference analysis manifest | Manifest validator and export adapter input |
| `comparison.csv` | Reference comparison export | Export adapter to backend `comparison.csv` |
| `stats.csv` | Reference statistics export | Export adapter to backend `stats.csv` |

## 6. Non-goals for the first milestone

Milestone 1 must not include full MDAnalysis pipeline migration, GROMACS
integration, FastAPI, biological interpretation in reports, heavy dependencies
as required runtime dependencies, copying thousands of residue names into Python
constants, committing full reference outputs, changing the backend contract to
match notebook filenames, committing the full `mania_residue_library.json`, or
committing parquet files, figures, CHARMM/toppar files, or notebook output
directories.

## 7. First safe engineering layer

The safe order of work is:

```text
archive inventory
-> data contract update
-> residue library loader/QC model
-> reference artifact validators
-> export adapter
-> reference-output comparison harness
-> controlled notebook block migration
-> real scientific pipeline later
```

This order keeps the backend skeleton, archive reference materials,
source-of-truth files, reference/intermediate artifacts, and files that must not
be committed clearly separated. The backend contract must not be changed to
match notebook filenames; notebook-like outputs should be translated through a
future export adapter into stable WANIA-facing output.
