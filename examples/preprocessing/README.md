# Preprocessing manifest examples

These files are committed placeholder manifests for the Stage 8 preprocessing
input contract. They are documentation examples, not real scientific datasets.

The declared topology, trajectory, reference-structure, and residue-library
paths are placeholders and are not expected to exist. Stage 8.2 does not check
whether declared scientific input paths exist, parse trajectory or topology
files, or validate full residue-library content.

Real or local reference data must not be committed to this repository. The
canonical field for a custom residue definition file is
`custom_residues_path`.

Load an example through the public Python API:

```python
from mania.preprocessing import load_preprocessing_input_manifest

manifest = load_preprocessing_input_manifest(
    "examples/preprocessing/minimal_manifest.yaml"
)
print(manifest.condition_names())
```

Loading an example and validating its declared file paths are separate
operations. The examples intentionally use placeholder paths, so explicit local
path validation is expected to fail unless matching local files are created.

Residue-library paths in these examples are placeholder contract fields.
Stage 8.4 documents future bridge behavior only: the examples do not load,
parse, or validate residue-library content, and the placeholder
residue-library files are not expected to exist.

These examples are standalone placeholder manifests, not local reference
packages. Reference package sanity checks are intended for user-local
directories containing matching files; no local reference package is committed
to this repository.

There is currently no preprocessing-manifest CLI command.

## Stage 12 Rg export

Stage 12 Rg export is available through Python APIs:
`write_rg_timeseries_csv(...)` writes `rg_timeseries.csv`, and
`validate_rg_timeseries_csv(...)` validates the exported file.

The committed Rg examples are synthetic and dependency-free:

- `examples/preprocessing/rg_export_usage.py` constructs synthetic Stage 12
  result objects, writes into a `TemporaryDirectory`, and validates the
  output;
- `examples/preprocessing/rg_timeseries.example.csv` shows the exact accepted
  CSV schema and synthetic rows;
- `docs/preprocessing_rg_export.md` documents the full manifest loading,
  computation, writing, and validation chain.

Run the synthetic example from the repository root:

```bash
python examples/preprocessing/rg_export_usage.py
```

It does not require MDAnalysis, real trajectories, or a local reference
package. Real local MD data belongs outside the repository. The local
scientific export smoke test remains planned for Stage 12.2d and is not part
of Stage 12.2c.

## Stage 13 contacts export

Stage 13 contacts export is available through Python APIs:
`write_contacts_perframe_csv(...)` writes `contacts_perframe.csv`,
`write_contact_edges_csv(...)` writes `contact_edges.csv`, and
`validate_contacts_perframe_csv(...)` plus `validate_contact_edges_csv(...)`
validate the exported files.

The committed contacts examples are synthetic and dependency-free:

- `examples/preprocessing/contacts_export_usage.py` constructs synthetic
  Stage 13 result objects, writes both CSV outputs into a `TemporaryDirectory`,
  and validates both outputs;
- `examples/preprocessing/contacts_perframe.example.csv` shows the exact
  accepted per-frame contacts schema and synthetic rows;
- `examples/preprocessing/contact_edges.example.csv` shows the exact accepted
  aggregate contacts schema and synthetic rows;
- `docs/preprocessing_contacts_export.md` documents the contacts result,
  writing, and validation chain.

Run the synthetic example from the repository root:

```bash
python examples/preprocessing/contacts_export_usage.py
```

It does not require MDAnalysis, real trajectories, or a local reference
package. It does not compute contacts from runtime objects and does not create
graph outputs. Real local MD data belongs outside the repository.
