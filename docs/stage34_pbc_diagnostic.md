# Stage 34 PBC protocol diagnostic checkpoint

This standalone tool compares three coordinate representations on five NORMAL
or TUMOR frames. It does not implement or approve a production PBC protocol. MANIA
scientific code, manifests, scientific status fields, and accepted pilot results
are outside its scope. Analyzer/project-owner review is required before adoption.

## Coordinate variants

All atoms remain present. Each variant resets an isolated in-memory Universe
from the same original coordinates, time and box. No variant starts from another
variant's output. Reconstruction uses topology bonds, including protein-attached
non-protein branches; names and proximity never define molecular components.

| Variant | Exact sequence |
| --- | --- |
| `A_raw` | Original coordinates, no transformations. |
| `B_literal_proposed` | `trans.unwrap(u.atoms)`; `trans.center_in_box(protein, center="geometry", point=None, wrap=True)`; `trans.wrap(u.atoms, compound="atoms")`. |
| `C_fragment_preserving_candidate` | `trans.unwrap(u.atoms)`; `trans.center_in_box(protein, center="geometry", point=None, wrap=False)`; `u.atoms.wrap(compound="fragments", center="cog", box=box, inplace=True)`. |

Here `protein = u.select_atoms("protein")` includes the whole selected protein,
including hydrogens. Each transformation class explicitly receives
`max_threads=1, parallelizable=True`; execution is sequential. `trans.unwrap`
calls `make_whole` on each complete topology-bonded fragment. The last operation
in C uses `AtomGroup.wrap` because it exposes the explicit geometry-center option
(`cog`) without requiring masses. Its translation applies to every atom of each
fragment. A fragment's center can be inside the primary cell while some atoms
remain outside. B retains the literal atom-wrap semantics; its internal default
center argument is irrelevant when wrapping individual atoms.

These APIs were inspected in installed MDAnalysis 2.10.0; see the official
[wrap/unwrap documentation](https://docs.mdanalysis.org/2.10.0/documentation_pages/transformations/wrap.html)
and [AtomGroup API](https://docs.mdanalysis.org/2.10.0/documentation_pages/core/groups.html#MDAnalysis.core.groups.AtomGroup.wrap).
The runner requires that version and does not install or change dependencies.

The synthetic boundary counterexample deliberately remains a failure for B:
two bonded atoms at 99 and 1 Å in a 100 Å cell have a periodic separation of
approximately 2 Å, but B returns a direct distance of 98 Å. C returns 2 Å in this
case. A separate synthetic case preserves C's bonded geometry while losing
intermolecular periodic-close contacts. Neither case is tuned to make every
variant succeed.

**NoJump is not used.** Per-frame reconstruction addresses molecular integrity;
temporal continuity would require separate sequential evidence. No sequential
coordinate pass or continuity claim is made here.

## Reviewed input profiles

Exactly two reviewed input profiles are fixed in this diagnostic-only runner:

| Condition | Expected topology path convention | Reviewed TPR SHA256 |
| --- | --- | --- |
| `normal` | `local_md/normal/topology.tpr` | `91a9fbbc6c1615095294acd349be3e7df0e0f37eb6329f877ada825efef4654f` |
| `tumor` | `local_md/tumor/topology.tpr` | `6bbb9864b261fba40d945a7401125cfe9da3f1106a4deb65ba2a41bae78d1dcf` |

Select the profile explicitly with `--condition {normal,tumor}`. Omitting it
defaults to `normal` for backward compatibility. The profile is never inferred
from topology/trajectory paths, filenames, system contents, residue names, or
the observed hash. Paths above are conventions; the selected reviewed TPR hash
is the identity guard. Arbitrary expected-hash overrides are not supported.
A cross-profile hash mismatch fails before TPR parsing or opening the XTC;
guard and error messages identify the selected condition. The full XTC is never
hashed.

TUMOR uses exactly the same diagnostic algorithms, transformations, thresholds,
tolerances and validation as NORMAL. No tuning occurred after seeing NORMAL.
The accepted NORMAL and TUMOR results retain their scientific meaning and are
not regenerated or overwritten by this expanded-coverage implementation. Their
five-frame observations found bonded representation failures for B and no
bonded-component disagreements for C across all topology bonds. The remaining
follow-up here expands detailed contact coverage and separates numerical flips.

## Manual NORMAL expanded-coverage invocation

From the repository root:

```bash
.venv/bin/python tools/pbc_protocol_diagnostic.py \
  --condition normal \
  --topology local_md/normal/topology.tpr \
  --trajectory local_md/normal/trajectory.xtc \
  --frames 500 505 510 515 520 \
  --expected-times-ps 5000 5050 5100 5150 5200 \
  --output local_md/pbc_diagnostics
```

## Manual TUMOR expanded-coverage invocation

Run separately from the repository root:

```bash
.venv/bin/python tools/pbc_protocol_diagnostic.py \
  --condition tumor \
  --topology local_md/tumor/topology.tpr \
  --trajectory local_md/tumor/trajectory.xtc \
  --frames 500 505 510 515 520 \
  --expected-times-ps 5000 5050 5100 5150 5200 \
  --output local_md/pbc_diagnostics
```

Only this five-frame checkpoint is supported for either condition. Indexes and
expected times remain explicit CLI arguments. Altered indexes/times are
rejected. Actual times must equal the requested times exactly, with no snapping,
relative tolerance or neighboring-frame substitution. Unavailable frames fail.

The low-level MDAnalysis `XTCFile` reader opens the trajectory read-only and
decodes only the five selected frames. Random access builds frame offsets in
memory by scanning the file structure; this can take time on first access. It
does not reconstruct other frames, write offset/lock sidecars beside the input,
or establish temporal continuity. Native XTC coordinates/box vectors are
converted from nm to Å by multiplication by 10; native time is ps. No processed
trajectory is written. TPR residue numbering is explicitly one-based as in the
accepted pilot, while atom indexes and residue indexes are zero-based.

## Measurements and coverage

- Each frame/variant verifies atom count, order/indexes, IDs, names, residue
  mapping/identity, segment mapping/identity, time, lengths, angles, and finite
  coordinates. Invalid boxes or missing/guessed bond metadata fail explicitly.
- All topology bonds are measured, including protein, attached non-protein
  branches and environment bonds. Asn295 and Asn308 get explicit cross-boundary
  attachment-bond and downstream branch groups. Branches are traced through
  non-protein topology bonds from the attachment, without guessed sugar names.
  Missing attachments are reported. Observed names are topology labels only,
  not publication partner identities.
- Direct bond lengths before/after transformation are compared to raw-frame
  box-aware `calc_bonds` distances. The 0.001 Å absolute comparison tolerance is
  numerical representation tolerance, **not a universal chemical bond cutoff**.
  Prepared periodic distances are also compared to the raw periodic reference
  to expose unexpected geometric drift.
- Heavy-atom probes require complete, unguessed topology elements. Unknown,
  missing or guessed elements skip heavy-atom probes with an explicit warning;
  bond diagnostics still run. Element symbols H/D/T are hydrogen. Names and
  masses are never used to infer heavy/hydrogen identity.
- Contact probes cover protein–protein, protein–attached non-protein,
  protein–environment, attached non-protein–environment, and
  environment–environment heavy atoms. Self pairs and duplicate unordered pairs
  are excluded for same-set probes. Bonded pairs remain included: these are
  geometry measurements, not production typed contacts.
- The old detailed probe selected at most the nearest **16** environment
  components with at least two heavy atoms; if none were within 6 Å, it sampled
  up to 16 evenly spaced eligible component IDs. This remains the inexpensive
  A/B control coverage. It is no longer the Variant C near-protein coverage.
- **Variant C qualifies every topology component outside the protein-connected
  components if and only if at least one protein-heavy ↔ component-heavy pair
  has raw-frame periodic distance <= 6.0 Å.** Every environment heavy atom is
  searched, including components with only one heavy atom and singleton
  topology components. No residue-name classification or biological identity is
  inferred. Components without heavy atoms cannot qualify.
- Every qualifying component contributes **all** its heavy atoms, including
  atoms farther than 6 Å from protein. Component IDs are sorted only for stable
  output; no ranking or 16-component truncation applies to C. Its protein–
  environment, attachment–environment and environment–environment probes use
  this full population. Environment–environment covers all unique unordered
  pairs through bounded searches, without a component cap. Protein–protein and
  protein–attachment probes remain present. Only C receives expanded coverage.
- Zero qualifying components is valid full coverage with zero detailed
  environment atoms/components; no fallback is added to that set. In this case,
  the old sampled environment–environment probe remains separately labeled
  `supplemental_environment_environment`, with exact atom ranges and component
  IDs. It preserves the separate-molecule counterexample, including its
  substantive failures, outside the empty near-protein set.
- `capped_distance(method="pkdtree")` searches blocks of at most 128 × 2048
  atoms. Each block compares the union of raw periodic-close candidates and
  prepared direct-close candidates. Final distances use `calc_bonds`; no dense
  full-system distance matrix or unbounded pair table is constructed. Candidate
  selection stores only component minima; detailed pair arrays are discarded
  after each block. Memory scales with atom/component populations and fixed
  pair blocks, not the full pair population. There are no new dependencies or
  multiprocessing. Changing block partitioning preserves counts and examples;
  ties between example distances use atom indexes for deterministic ordering.
- **4.5 and 6.0 Å are geometry probe thresholds only.** Strict `distance <=
  threshold` classifications remain unpadded. Candidate search uses 0.001 Å
  padding, but qualification at 6 Å and final classifications do not. These
  measurements do not validate angles, typed interactions or other
  contact-specific criteria.

Coverage records include atom counts and lossless inclusive atom-index ranges,
candidate-search coverage and selected component IDs for each frame/variant.
The historical subset key `representative_environment_heavy` contains the full
qualifying heavy-atom population for C; `full_near_protein_mode` identifies it.
Each record explicitly reports:

- eligible environment component and candidate-search heavy-atom counts;
- `periodic_6A_qualifying_component_count`, the complete qualifying component ID
  list, and `periodic_6A_qualifying_heavy_atom_count`;
- `detailed_environment_component_count` and
  `detailed_environment_heavy_atom_count`;
- `detailed_coverage_equals_full_qualifying_set`.

C requires equality of qualifying/detailed component counts and IDs and exact
membership of all corresponding heavy atoms. A failed assertion raises a clear
incomplete-coverage error and produces a failed diagnostic archive. Missing
authoritative elements still skip contact probes with warnings; skipped probes
never claim completed near-protein coverage.

Every contact category reports its exact atom ranges and full
`pair_population_count`. At **each** threshold, `pairs_examined` counts the
padded 6 Å periodic/direct candidate union whose distances were evaluated;
`close_union_pair_count` counts pairs actually close under either geometry at
that threshold. Thus `pairs_examined` can be equal at 4.5 and 6 Å without implying
equal contact counts. Same-set populations exclude self and duplicate pairs.
The periodic reference always uses the original frame and its box. It is a
diagnostic reference only; no MIC is added to MANIA.

### Strict flips, numerical boundaries and substantive mismatches

The accepted absolute distance-agreement tolerance stays **0.001 Å**.

| Field | Meaning at the reported geometry threshold |
| --- | --- |
| `strict_lost_periodic_close` | Periodic <= threshold, direct > threshold. |
| `strict_direct_only_close` | Direct <= threshold, periodic > threshold. |
| `numerical_threshold_boundary_flip` | Either strict flip AND absolute direct–periodic distance difference <= 0.001 Å. |
| `substantive_lost_periodic_close` | Strict lost contact with difference > 0.001 Å. |
| `substantive_direct_only_close` | Strict direct-only contact with difference > 0.001 Å. |
| `distance_disagreement` | Difference > 0.001 Å among pairs close under at least one geometry, including pairs whose contact classifications agree. |

The original `lost_periodic_close`, `direct_only_close` and
`close_pair_distance_disagreement_count` remain aliases of their corresponding
strict/distance counts. The legacy `near_threshold_discrepancy_count` remains
an observation that either distance is near the cutoff; that alone does **not**
make a large representation error numerical.

For example, periodic 5.999999834 Å versus direct 6.000004883 Å remains one
strict lost 6 Å contact, additionally classified as one numerical boundary flip
and zero substantive mismatches. Numerical flips retain bounded examples in a
separate `numerical_threshold_boundary_examples` list, so larger failures cannot
displace all their raw observations. Examples include both distances, atom
identities, strict direction, classification, frame and variant.

## Results and review

Each execution creates a fresh directory and sibling ZIP under `--output`,
using the selected condition for both successful and failed runs:

`stage34_pbc_normal_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>/`

`stage34_pbc_normal_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>.zip`

For TUMOR:

`stage34_pbc_tumor_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>/`

`stage34_pbc_tumor_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>.zip`

The five archived files are:

- `pbc_diagnostic.json`: explicit selected `condition`, observations, preservation
  checks, coverage, bond/contact summaries and up to three largest examples per
  summary plus a separate bounded numerical-boundary example list;
- `input_observations.json`: explicit selected `condition`, paths, expected
  topology path convention, sizes, observed/expected TPR hashes, selected
  indexes/times, MDAnalysis/MANIA versions, Git commit and diagnostic source SHA256;
- `transformations.json`: explicit variant configuration;
- `summary.txt`: separate answers for B integrity, C integrity, C contact
  agreement, and unresolved questions;
- `diagnostic.log`: progress, warnings and errors.

Send the exact ZIP printed after `SEND THIS ARCHIVE:` to the Analyzer. The ZIP
uses an explicit five-file allowlist, excludes raw TPR/XTC, and never overwrites
an earlier archive. Failed runs also retain a diagnostic archive and return a
nonzero exit code. Partial runs do not produce a complete five-frame conclusion.

The earlier TUMOR attempt used the NORMAL-only guard and correctly failed with
`NORMAL TPR SHA256 differs from the reviewed hash.` This was expected input
identity rejection, not a scientific failure or evidence that the TUMOR TPR is
bad. Preserve its guardrail evidence archive unchanged:
`stage34_pbc_normal_20260915T104447Z_bcf1f68ab75f430b8ab7dbf621229fd2.zip`.
A future `--condition tumor` run creates a new unique TUMOR result; it does not
rename or overwrite that archive or the accepted NORMAL output.

Machine-readable conclusions explicitly include:

- `variant_c_bonded_integrity_preserved`;
- `variant_c_full_near_protein_coverage_completed`;
- `variant_c_substantive_contact_mismatch_count`;
- `variant_c_numerical_threshold_boundary_flip_count`.

The human summary distinguishes bonded integrity **PASS** (zero disagreements
across all topology bonds) from full near-protein direct-distance representation
**PASS/FAIL** (full coverage completed and zero substantive mismatches). Missing
elements give **NOT ASSESSED** for contact representation. Substantive counts
sum `distance_disagreement` over C's five primary contact categories, thresholds
and frames; a substantive lost/direct-only pair is already included and is not
added twice for its classification. Numerical counts sum the corresponding
boundary-flip counts and stay visible in strict totals. Supplemental observations
have a separate substantive count and PASS/FAIL line; they are excluded from the
near-protein conclusion. Failed/interrupted runs have no assessed overall
integrity/mismatch conclusion and cannot claim complete five-frame coverage.

Exit code zero means observations were collected, even when a coordinate
variant fails geometric checks. Read each integrity/contact result and the
warnings; there is no blanket PBC pass. Counts summed in the summary can count
one pair under both geometry thresholds and across multiple frames. Results can
establish consistency or demonstrate failures only for the recorded frame,
bond and atom-set coverage. They do not approve a universal PBC protocol,
temporal continuity, full typed interactions, biological interpretation or
Dataset publication. Scientific PBC status fields are never updated.

Synthetic verification: `.venv/bin/pytest -q tests/test_pbc_protocol_diagnostic.py`.
Tests use `pytest.importorskip("MDAnalysis")` to preserve the optional scientific
dependency boundary. Regressions cover more than 16 qualifying fragments,
complete-fragment heavy-atom inclusion, single-heavy-atom components, strict
numerical flips in both directions, substantive failures, empty coverage,
triclinic candidate search, coverage assertion failures and block-independent
counts/examples. The existing separate-molecule failure remains, and an
additional full near-protein case shows that C can preserve every bond while
still losing substantive contacts. This implementation runs only synthetic
diagnostics; both real NORMAL and TUMOR follow-ups are left to the user.

Even full near-protein coverage on these five frames is **not a universal PBC
proof**. Production protocol acceptance remains pending Analyzer review;
scientific PBC status, production MANIA, and the accepted transformations remain
unchanged.
