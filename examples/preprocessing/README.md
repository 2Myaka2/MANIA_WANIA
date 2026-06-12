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

There is currently no preprocessing-manifest CLI command.
