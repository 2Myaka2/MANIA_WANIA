# Stage 34 PBC protocol diagnostic checkpoint

This standalone tool compares three coordinate representations on five NORMAL
frames. It does not implement or approve a production PBC protocol. MANIA
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

## Run NORMAL once

From `~/MANIA_WANIA`, after `source .venv/bin/activate`:

```bash
python tools/pbc_protocol_diagnostic.py \
  --topology local_md/normal/topology.tpr \
  --trajectory local_md/normal/trajectory.xtc \
  --frames 500 505 510 515 520 \
  --expected-times-ps 5000 5050 5100 5150 5200 \
  --output local_md/pbc_diagnostics
```

Only this five-frame NORMAL checkpoint is supported. Altered indexes/times are
rejected. Actual times must equal the requested times exactly, with no snapping,
relative tolerance or neighboring-frame substitution. Unavailable frames fail.
The TPR must have SHA256
`91a9fbbc6c1615095294acd349be3e7df0e0f37eb6329f877ada825efef4654f`;
a mismatch fails before opening the XTC. The full XTC is never hashed.

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
- Eligible environment components are topology fragments outside the
  protein-connected components with at least two heavy atoms. A periodic
  neighbor search against all protein heavy atoms scans every eligible
  environment heavy atom. Up to 16 components nearest to protein within 6 Å are
  selected (ties use component ID). If none qualify by distance, up to 16
  evenly spaced eligible component IDs are selected. All their heavy atoms are
  retained; whole components remain intact for transformations. This sampling
  does not validate every environment component's contacts. Waters and ions
  remain in the system and in available bond checks.
- `capped_distance(method="pkdtree")` searches blocks of at most 128 × 2048
  atoms. Each block compares the union of raw periodic-close candidates and
  prepared direct-close candidates. Final distances use `calc_bonds`; no dense
  full-system distance matrix or unbounded pair table is constructed.
- **4.5 and 6.0 Å are geometry probe thresholds only.** Strict `distance <=
  threshold` classifications report `lost_periodic_close` and
  `direct_only_close`, numerical cases near the threshold, distance disagreement
  counts, maximum differences and bounded examples. Candidate search uses
  0.001 Å padding, but final classifications do not. These measurements do not
  validate angles, typed interactions or other contact-specific criteria.

Coverage records include atom counts and lossless inclusive atom-index ranges,
candidate-search coverage and selected component IDs for each frame/variant.
The periodic reference always uses the original frame and its box. It is a
diagnostic reference only; no MIC is added to MANIA.

## Results and review

Each execution creates a fresh directory and sibling ZIP under `--output`:

`stage34_pbc_normal_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>/`

`stage34_pbc_normal_<UTC YYYYMMDDTHHMMSSZ>_<32-character UUID>.zip`

The five archived files are:

- `pbc_diagnostic.json`: observations, preservation checks, coverage, bond/contact
  summaries and up to three largest examples per summary;
- `input_observations.json`: paths, sizes, TPR hash, selected indexes/times,
  MDAnalysis/MANIA versions, Git commit and diagnostic source SHA256;
- `transformations.json`: explicit variant configuration;
- `summary.txt`: separate answers for B integrity, C integrity, C contact
  agreement, and unresolved questions;
- `diagnostic.log`: progress, warnings and errors.

Send the exact ZIP printed after `SEND THIS ARCHIVE:` to the Analyzer. The ZIP
uses an explicit five-file allowlist, excludes raw TPR/XTC, and never overwrites
an earlier archive. Failed runs also retain a diagnostic archive and return a
nonzero exit code. Partial runs do not produce a complete five-frame conclusion.

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
dependency boundary. Real NORMAL execution is deliberately left to the user.
