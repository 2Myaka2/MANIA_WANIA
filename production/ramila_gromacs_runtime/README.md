# Ramila GROMACS runtime authority

The 12 existing Dataset-v1 identities bind the owner-declared
`eqmd_rep100ns_09_2026` WT series and `T330M_30ns_09_2026` T330M series.
`authority.json` records literal source-root-relative paths, sizes and SHA256
for all audited TPR/MDP/LOG files, including the additional 101-ns extension
TPR for WT-TUMOR-r2. Final XTC hashes are computed at the execution site. The shared Dataset CSV/YAML
remain the byte-frozen Egor catalog snapshot; only their existing scientific
identities and temporal parameters are consumed here. This runtime JSON supplies
current Ramila source bindings and supersedes historical phase1 intake notes.
The delivered directories are named `replica 1`, `replica 2`, `replica 3`.

Each system has an explicit 690-residue mapping to the pinned O95436-1 reference,
TPR-derived partner membership and topology observations. Ordered chemistry,
elements and connectivity were independently compared across all three TPRs
within each system before sharing its controls. Controls are never shared across
systems. Sugar fragments attached to protein have the deliberately opaque label
`topology_attached_sugar_fragment`; this is not a biological glycan name.
Multi-residue membrane fragments remain complete lipid partners. Water/ions are
excluded through audited explicit classifications, not runtime name guessing.

`RAMILA_BIOLOGICAL_ANNOTATION_AUTHORITY = PENDING`. No complete biological
annotation object, glycan name, design-site declaration, source or verifier is
supplied. Topology observations do not establish publication annotations.
Protein/lipid/glycan contact execution and canonical exports remain available;
annotated exports and publication annotation readiness remain pending.

Use the [production interface](../../docs/ramila_gromacs_production_interface.md)
and [quickstart](../../docs/ramila_gromacs_quickstart_ru.md). These controls are
specific to the audited source bytes. A changed lightweight input requires a new
source audit and reviewed controls, not automatic replacement of hashes.
