#!/usr/bin/env python3
"""Standalone five-frame PBC geometry diagnostic; never a production protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import MDAnalysis as mda
import MDAnalysis.transformations as trans
import numpy as np
from MDAnalysis.coordinates.memory import MemoryReader
from MDAnalysis.lib.distances import calc_bonds, capped_distance
from MDAnalysis.lib.formats.libmdaxdr import XTCFile
from MDAnalysis.lib.mdamath import triclinic_box
from MDAnalysis.topology.TPRParser import TPRParser

FRAMES = (500, 505, 510, 515, 520)
TIMES_PS = (5000, 5050, 5100, 5150, 5200)
NORMAL_TPR_SHA256 = "91a9fbbc6c1615095294acd349be3e7df0e0f37eb6329f877ada825efef4654f"
VARIANTS = ("A_raw", "B_literal_proposed", "C_fragment_preserving_candidate")
THRESHOLDS_A = (4.5, 6.0)
DISTANCE_TOLERANCE_A = 0.001  # Representation comparison, not a bond-length limit.
REFERENCE_BLOCK = 128
CONFIGURATION_BLOCK = 2048
ENVIRONMENT_LIMIT = 16
EXAMPLE_LIMIT = 3
IDENTITY_FIELDS = (
    "indices",
    "ids",
    "names",
    "resindices",
    "resids",
    "resnames",
    "segindices",
    "segids",
)
ARTIFACTS = (
    "pbc_diagnostic.json",
    "input_observations.json",
    "transformations.json",
    "summary.txt",
    "diagnostic.log",
)


def transformation_parameters(variant):
    if variant == VARIANTS[0]:
        return []
    common = {"max_threads": 1, "parallelizable": True}
    steps = [
        {
            "operation": "trans.unwrap",
            "selection": "all",
            **common,
            "component_semantics": "make_whole on each topology-bonded fragment",
        },
        {
            "operation": "trans.center_in_box",
            "selection": "protein",
            "center": "geometry",
            "point": None,
            "wrap": variant == VARIANTS[1],
            **common,
        },
    ]
    if variant == VARIANTS[1]:
        steps.append(
            {
                "operation": "trans.wrap",
                "selection": "all",
                "compound": "atoms",
                "center": "com (unused for atoms)",
                "box": "current frame",
                "inplace": True,
                **common,
            }
        )
    else:
        steps.append(
            {
                "operation": "AtomGroup.wrap",
                "selection": "all",
                "compound": "fragments",
                "center": "cog",
                "box": "current frame",
                "inplace": True,
            }
        )
    return steps


def validate_box(box):
    if box is None:
        raise ValueError("Missing box metadata; periodic diagnostics require a box.")
    box = np.asarray(box, dtype=np.float32)
    if (
        box.shape != (6,)
        or not np.isfinite(box).all()
        or np.any(box[:3] <= 0)
        or np.any(box[3:] <= 0)
        or np.any(box[3:] >= 180)
    ):
        raise ValueError(
            "Invalid box metadata: require a finite, positive-volume cell."
        )
    ca, cb, cg = np.cos(np.deg2rad(box[3:].astype(np.float64)))
    if 1 + 2 * ca * cb * cg - ca**2 - cb**2 - cg**2 <= 0:
        raise ValueError(
            "Invalid box metadata: angles do not define a positive volume."
        )
    return box.copy()


def identity(u):
    return {field: getattr(u.atoms, field).copy() for field in IDENTITY_FIELDS}


def topology_context(u):
    bond_attr = getattr(u._topology, "bonds", None)
    if bond_attr is None or np.any(bond_attr.is_guessed) or not len(u.bonds):
        raise ValueError(
            "Missing or guessed topology bonds; fragments need real bonds."
        )
    bonds = u.bonds.indices.copy()
    components = u.atoms.fragindices.copy()
    protein = np.zeros(len(u.atoms), dtype=bool)
    protein[u.select_atoms("protein").indices] = True
    if not protein.any():
        raise ValueError("The explicit MDAnalysis selection 'protein' is empty.")
    protein_connected = np.isin(components, np.unique(components[protein]))
    attached = protein_connected & ~protein
    notes = []
    elements_attr = getattr(u._topology, "elements", None)
    heavy = None
    if elements_attr is None or np.any(elements_attr.is_guessed):
        notes.append("Missing authoritative elements: all heavy-atom probes skipped.")
    else:
        elements = np.asarray(u.atoms.elements, dtype=str)
        # Validate against the library's element table, never names or masses.
        from MDAnalysis.guesser.tables import SYMB2Z

        valid_symbols = [symbol.upper() for symbol in SYMB2Z] + ["D", "T"]
        if not np.isin(np.char.upper(elements), valid_symbols).all():
            notes.append("Incomplete/unknown elements: all heavy-atom probes skipped.")
        else:
            heavy = ~np.isin(np.char.upper(elements), ["H", "D", "T"])
    groups = {
        "all_topology_bonds": np.ones(len(bonds), dtype=bool),
        "protein_bonds": protein[bonds].all(axis=1),
        "protein_connected_component_bonds": protein_connected[bonds].all(axis=1),
        "attached_nonprotein_internal_bonds": attached[bonds].all(axis=1),
    }
    adjacency = {}
    for a, b in bonds[attached[bonds].all(axis=1)]:
        adjacency.setdefault(int(a), []).append(int(b))
        adjacency.setdefault(int(b), []).append(int(a))
    attachments = {}
    for resid in (295, 308):
        anchor = protein & (u.atoms.resids == resid) & (u.atoms.resnames == "ASN")
        crossing = (anchor[bonds[:, 0]] & attached[bonds[:, 1]]) | (
            anchor[bonds[:, 1]] & attached[bonds[:, 0]]
        )
        key = f"Asn{resid}"
        groups[f"{key}_attachment_bonds"] = crossing
        seeds = set(int(i) for i in bonds[crossing].ravel() if attached[i])
        branch, pending = set(seeds), list(seeds)
        while pending:
            for neighbor in adjacency.get(pending.pop(), []):
                if neighbor not in branch:
                    branch.add(neighbor)
                    pending.append(neighbor)
        branch_mask = np.zeros(len(u.atoms), dtype=bool)
        branch_mask[list(branch)] = True
        groups[f"{key}_attached_branch_bonds"] = branch_mask[bonds].any(axis=1)
        attachments[key] = {
            "topology_attachment_atom_pairs": bonds[crossing].tolist(),
            "nonprotein_branch_atom_index_ranges": index_ranges(sorted(branch)),
            "nonprotein_branch_atom_count": len(branch),
        }
        if not crossing.any():
            notes.append(f"{key}: no topology bond to non-protein atoms identified.")
    return {
        "bonds": bonds,
        "components": components,
        "protein": protein,
        "attached": attached,
        "protein_connected": protein_connected,
        "heavy": heavy,
        "bond_groups": groups,
        "attachments": attachments,
        "warnings": notes,
        "identity": identity(u),
    }


def prepare_variant(work, raw, box, time_ps, variant):
    """Reset the isolated Universe from the same raw array before EACH variant."""
    if variant not in VARIANTS:
        raise ValueError(f"Unknown coordinate variant: {variant}")
    work.atoms.positions = raw.copy()
    work.dimensions = validate_box(box)
    work.trajectory.ts.time = time_ps
    if variant == VARIANTS[0]:
        return
    protein = work.select_atoms("protein")
    trans.unwrap(work.atoms, max_threads=1, parallelizable=True)(work.trajectory.ts)
    trans.center_in_box(
        protein,
        center="geometry",
        point=None,
        wrap=variant == VARIANTS[1],
        max_threads=1,
        parallelizable=True,
    )(work.trajectory.ts)
    if variant == VARIANTS[1]:
        trans.wrap(work.atoms, compound="atoms", max_threads=1, parallelizable=True)(
            work.trajectory.ts
        )
    else:
        # The transformation wrapper hides the center argument. Use AtomGroup.wrap
        # explicitly to choose geometry, avoiding a mass requirement/inference.
        work.atoms.wrap(compound="fragments", center="cog", box=box, inplace=True)


def index_ranges(indices):
    """Lossless inclusive index ranges, including singleton ranges."""
    result = []
    for index in indices:
        index = int(index)
        if result and index == result[-1][1] + 1:
            result[-1][1] = index
        else:
            result.append([index, index])
    return result


def blocks(left, right, same=False):
    for start in range(0, len(left), REFERENCE_BLOCK):
        a = left[start : start + REFERENCE_BLOCK]
        for offset in range(0, len(right), CONFIGURATION_BLOCK):
            b = right[offset : offset + CONFIGURATION_BLOCK]
            if same and a[0] > b[-1]:
                continue
            yield a, b


def neighbors(x, y, box):
    # Force a neighbor search; no automatic dense all-pairs fallback.
    return capped_distance(
        x,
        y,
        max_cutoff=max(THRESHOLDS_A) + DISTANCE_TOLERANCE_A,
        box=box,
        method="pkdtree",
        return_distances=False,
    )


def diagnostic_subsets(context, raw, box):
    heavy = context["heavy"]
    if heavy is None:
        return {}, {"heavy_atom_probes": "skipped: no authoritative elements"}
    components = context["components"]
    protein = np.flatnonzero(context["protein"] & heavy)
    attached = np.flatnonzero(context["attached"] & heavy)
    counts = np.bincount(components, weights=heavy.astype(int))
    eligible = ~context["protein_connected"] & (counts[components] >= 2)
    environment = np.flatnonzero(eligible & heavy)
    closest = {}
    # Coverage includes every eligible environment heavy atom, but only as a
    # candidate search against protein. Select whole fragments for later probes.
    for a, b in blocks(protein, environment):
        pairs = neighbors(raw[a], raw[b], box)
        if len(pairs):
            atom_a, atom_b = a[pairs[:, 0]], b[pairs[:, 1]]
            distances = calc_bonds(raw[atom_a], raw[atom_b], box=box)
            within = distances <= max(THRESHOLDS_A)
            for component, distance in zip(
                components[atom_b[within]], distances[within], strict=True
            ):
                component = int(component)
                closest[component] = min(
                    closest.get(component, float("inf")), float(distance)
                )
    chosen = sorted(closest, key=lambda c: (closest[c], c))[:ENVIRONMENT_LIMIT]
    eligible_ids = np.unique(components[environment])
    selection_rule = "nearest raw periodic protein distance <= 6 A; tie: component ID"
    if not chosen and len(eligible_ids):
        chosen = eligible_ids[
            np.linspace(
                0,
                len(eligible_ids) - 1,
                min(ENVIRONMENT_LIMIT, len(eligible_ids)),
                dtype=int,
            )
        ].tolist()
        selection_rule = "no nearby candidates; evenly spaced topology component IDs"
    selected = np.isin(components, chosen)
    subsets = {
        "protein_heavy": protein,
        "protein_attached_nonprotein_heavy": attached,
        "representative_environment_heavy": np.flatnonzero(selected & heavy),
    }
    coverage = {
        "selection_rule": selection_rule,
        "environment_component_limit": ENVIRONMENT_LIMIT,
        "selected_environment_component_ids": [int(c) for c in chosen],
        "eligible_environment_component_count": len(eligible_ids),
        "candidate_search_environment_heavy_atom_count": len(environment),
        "candidate_search_environment_atom_index_ranges": index_ranges(environment),
        "candidate_components_within_6_A": len(closest),
        "environment_eligibility": "not protein-connected; >= 2 heavy atoms",
        "subsets": {
            name: {"atom_count": len(ids), "atom_index_ranges": index_ranges(ids)}
            for name, ids in subsets.items()
        },
        "contact_scope": "selected subsets only; no typed-interaction exclusions",
    }
    return subsets, coverage


def atom_record(u, context, index):
    atom = u.atoms[int(index)]
    return {
        "index": int(atom.index),
        "id": int(atom.id),
        "name": str(atom.name),
        "residue_index": int(atom.resindex),
        "residue_id": int(atom.resid),
        "residue_name": str(atom.resname),
        "segment_id": str(atom.segid),
        "component_id": int(context["components"][index]),
    }


def discrepancy(u, context, pair, direct, periodic, category, threshold=None):
    return {
        "atoms": [atom_record(u, context, i) for i in pair],
        "direct_distance_A": float(direct),
        "periodic_reference_distance_A": float(periodic),
        "absolute_disagreement_A": float(abs(direct - periodic)),
        "geometry_probe_threshold_A": threshold,
        "discrepancy_type": category,
    }


def retain_largest(existing, candidates):
    return sorted(
        existing + candidates,
        key=lambda row: row["absolute_disagreement_A"],
        reverse=True,
    )[:EXAMPLE_LIMIT]


def bond_integrity(u, context, raw, prepared, box, coverage):
    pairs = context["bonds"]
    a, b = pairs.T
    reference = calc_bonds(raw[a], raw[b], box=box)
    before = calc_bonds(raw[a], raw[b])
    after = calc_bonds(prepared[a], prepared[b])
    after_periodic = calc_bonds(prepared[a], prepared[b], box=box)
    error = np.abs(after - reference)
    groups = dict(context["bond_groups"])
    selected = coverage.get("selected_environment_component_ids", [])
    groups["selected_environment_bonds"] = np.isin(context["components"][a], selected)
    summaries = {}
    for name, mask in groups.items():
        ids = np.flatnonzero(mask)
        failed = ids[error[ids] > DISTANCE_TOLERANCE_A]
        worst = failed[np.argsort(error[failed])[-EXAMPLE_LIMIT:][::-1]]
        summaries[name] = {
            "bond_count": len(ids),
            "raw_direct_disagreement_count": int(
                np.count_nonzero(
                    np.abs(before[ids] - reference[ids]) > DISTANCE_TOLERANCE_A
                )
            ),
            "prepared_direct_disagreement_count": len(failed),
            "affected_component_count": len(
                np.unique(context["components"][a[failed]])
            ),
            "max_absolute_disagreement_A": float(error[ids].max(initial=0)),
            "max_raw_direct_distance_A": float(before[ids].max(initial=0)),
            "max_prepared_direct_distance_A": float(after[ids].max(initial=0)),
            "max_periodic_reference_distance_A": float(reference[ids].max(initial=0)),
            "prepared_periodic_reference_drift_count": int(
                np.count_nonzero(
                    np.abs(after_periodic[ids] - reference[ids]) > DISTANCE_TOLERANCE_A
                )
            ),
            "examples": [
                {
                    **discrepancy(
                        u,
                        context,
                        pairs[i],
                        after[i],
                        reference[i],
                        "bonded_component_split",
                    ),
                    "raw_direct_distance_A": float(before[i]),
                }
                for i in worst
            ],
        }
    return summaries


def compare_contacts(u, context, raw, prepared, box, left, right, same=False):
    reports = [
        {
            "geometry_probe_threshold_A": threshold,
            "periodic_close_count": 0,
            "direct_close_count": 0,
            "lost_periodic_close": 0,
            "direct_only_close": 0,
            "near_threshold_discrepancy_count": 0,
            "close_pair_distance_disagreement_count": 0,
            "max_absolute_disagreement_A": 0.0,
            "examples": [],
        }
        for threshold in THRESHOLDS_A
    ]
    drift_count = 0
    for a, b in blocks(left, right, same):
        periodic_pairs = neighbors(raw[a], raw[b], box)
        direct_pairs = neighbors(prepared[a], prepared[b], None)
        pairs = np.unique(np.concatenate((periodic_pairs, direct_pairs)), axis=0)
        if not len(pairs):
            continue
        pairs = np.column_stack((a[pairs[:, 0]], b[pairs[:, 1]]))
        if same:
            pairs = pairs[pairs[:, 0] < pairs[:, 1]]
        if not len(pairs):
            continue
        x, y = pairs.T
        periodic = calc_bonds(raw[x], raw[y], box=box)
        direct = calc_bonds(prepared[x], prepared[y])
        after_periodic = calc_bonds(prepared[x], prepared[y], box=box)
        drift_count += int(
            np.count_nonzero(np.abs(after_periodic - periodic) > DISTANCE_TOLERANCE_A)
        )
        for report in reports:
            threshold = report["geometry_probe_threshold_A"]
            pc, dc = periodic <= threshold, direct <= threshold
            report["periodic_close_count"] += int(pc.sum())
            report["direct_close_count"] += int(dc.sum())
            close_error = np.abs(direct[pc | dc] - periodic[pc | dc])
            report["close_pair_distance_disagreement_count"] += int(
                np.count_nonzero(close_error > DISTANCE_TOLERANCE_A)
            )
            report["max_absolute_disagreement_A"] = max(
                report["max_absolute_disagreement_A"],
                float(close_error.max(initial=0)),
            )
            for category, mask in (
                ("lost_periodic_close", pc & ~dc),
                ("direct_only_close", dc & ~pc),
            ):
                report[category] += int(mask.sum())
                ids = np.flatnonzero(mask)
                report["near_threshold_discrepancy_count"] += int(
                    np.count_nonzero(
                        (np.abs(periodic[ids] - threshold) <= DISTANCE_TOLERANCE_A)
                        | (np.abs(direct[ids] - threshold) <= DISTANCE_TOLERANCE_A)
                    )
                )
                error = np.abs(direct[ids] - periodic[ids])
                report["max_absolute_disagreement_A"] = max(
                    report["max_absolute_disagreement_A"], float(error.max(initial=0))
                )
                worst = ids[np.argsort(error)[-EXAMPLE_LIMIT:][::-1]]
                report["examples"] = retain_largest(
                    report["examples"],
                    [
                        discrepancy(
                            u,
                            context,
                            pairs[i],
                            direct[i],
                            periodic[i],
                            category,
                            threshold,
                        )
                        for i in worst
                    ],
                )
    return {
        "left_atom_count": len(left),
        "right_atom_count": len(right),
        "pair_semantics": "unique unordered, exclude self" if same else "cross set",
        "periodic_reference_drift_count_on_candidate_union": drift_count,
        "thresholds": reports,
    }


def evaluate_frame(work, context, raw, box, frame_index, time_ps):
    box = validate_box(box)
    raw = np.array(raw, dtype=np.float32, copy=True)
    if raw.shape != (len(work.atoms), 3) or not np.isfinite(raw).all():
        raise ValueError(
            f"Frame {frame_index}: atom count mismatch or nonfinite coordinates."
        )
    raw.setflags(write=False)
    subsets, coverage = diagnostic_subsets(context, raw, box)
    results = []
    for variant in VARIANTS:
        prepare_variant(work, raw, box, time_ps, variant)
        prepared = work.atoms.positions.copy()
        checks = {
            f"{key}_unchanged": bool(np.array_equal(getattr(work.atoms, key), value))
            for key, value in context["identity"].items()
        }
        checks.update(
            {
                "atom_count_unchanged": len(prepared) == len(raw),
                "time_unchanged": work.trajectory.ts.time == time_ps,
                "box_lengths_unchanged": bool(
                    np.array_equal(work.dimensions[:3], box[:3])
                ),
                "box_angles_unchanged": bool(
                    np.array_equal(work.dimensions[3:], box[3:])
                ),
                "finite_coordinates": bool(np.isfinite(prepared).all()),
            }
        )
        if not all(checks.values()):
            raise ValueError(
                f"Frame {frame_index}, {variant}: preservation failed: {checks}"
            )
        bonds = bond_integrity(work, context, raw, prepared, box, coverage)
        contacts = {}
        if subsets:
            p, g, e = subsets.values()
            for name, left, right, same in (
                ("protein_protein", p, p, True),
                ("protein_attached_nonprotein", p, g, False),
                ("protein_environment", p, e, False),
                ("attached_nonprotein_environment", g, e, False),
                ("environment_environment", e, e, True),
            ):
                contacts[name] = compare_contacts(
                    work, context, raw, prepared, box, left, right, same
                )
        for group in list(bonds.values()) + [
            t for c in contacts.values() for t in c["thresholds"]
        ]:
            for example in group["examples"]:
                example.update({"source_frame_index": frame_index, "variant": variant})
        results.append(
            {
                "source_frame_index": frame_index,
                "actual_time_ps": time_ps,
                "variant": variant,
                "atom_count": len(raw),
                "box_lengths_A": box[:3].tolist(),
                "box_angles_deg": box[3:].tolist(),
                "preservation_checks": checks,
                "transformation_parameters": transformation_parameters(variant),
                "bond_integrity": bonds,
                "contact_diagnostics": contacts,
                "checked_atom_set_coverage": coverage,
            }
        )
    return results


def conclude(records, notes):
    lines = ["Stage 34 PBC diagnostic: observations only; Analyzer review required."]
    for label, variant in (
        ("A. Variant B bonded integrity", VARIANTS[1]),
        ("B. Variant C bonded integrity", VARIANTS[2]),
    ):
        selected = [r for r in records if r["variant"] == variant]
        failures = sum(
            r["bond_integrity"]["all_topology_bonds"][
                "prepared_direct_disagreement_count"
            ]
            for r in selected
        )
        lines.append(
            f"{label}: {failures} bond/frame disagreements over "
            f"{len(selected)} frames (tolerance {DISTANCE_TOLERANCE_A} A)."
        )
    candidate = [r for r in records if r["variant"] == VARIANTS[2]]
    probes = [
        t
        for r in candidate
        for c in r["contact_diagnostics"].values()
        for t in c["thresholds"]
    ]
    lost = sum(t["lost_periodic_close"] for t in probes)
    appearing = sum(t["direct_only_close"] for t in probes)
    distance_disagreements = sum(
        t["close_pair_distance_disagreement_count"] for t in probes
    )
    lines.append(
        "C. Variant C checked close-contact agreement: "
        + (
            f"{lost} lost_periodic_close; {appearing} direct_only_close; "
            f"{distance_disagreements} close-pair distance disagreements "
            "(counts summed over frames, probes and both thresholds)."
            if probes
            else "NOT ASSESSED: heavy-atom metadata unavailable."
        )
    )
    if lost:
        notes.append(
            "Candidate still loses periodic-close contacts in checked subsets."
        )
    if appearing:
        notes.append(
            "Candidate has direct-only contacts; inspect numerical boundary/drift."
        )
    drift = sum(
        r["bond_integrity"]["all_topology_bonds"][
            "prepared_periodic_reference_drift_count"
        ]
        + sum(
            c["periodic_reference_drift_count_on_candidate_union"]
            for c in r["contact_diagnostics"].values()
        )
        for r in records
    )
    if drift:
        notes.append(f"{drift} periodic-reference drift observations exceed tolerance.")
    lines.append(
        "D. Unresolved: general intermolecular periodic-image choice; unchecked "
        "contacts/frames/conditions; typed interactions and angles; temporal "
        "continuity; scientific production PBC protocol acceptance."
    )
    lines.extend(f"WARNING: {note}" for note in dict.fromkeys(notes))
    return "\n".join(lines) + "\n"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_observations(topology, trajectory):
    from mania import __version__

    return {
        "topology_path": str(topology),
        "trajectory_path": str(trajectory),
        "topology_size_bytes": topology.stat().st_size,
        "trajectory_size_bytes": trajectory.stat().st_size,
        "topology_sha256": sha256(topology),
        "expected_topology_sha256": NORMAL_TPR_SHA256,
        "trajectory_hash_computed": False,
        "selected_source_frame_indexes": list(FRAMES),
        "expected_times_ps": list(TIMES_PS),
        "MDAnalysis_version": mda.__version__,
        "MANIA_version": __version__,
        "current_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        ).strip(),
        "diagnostic_runner_sha256": sha256(Path(__file__)),
        "reader": "XTCFile read-only; native nm -> A by x10; native time in ps",
        "offsets": "in-memory frame-offset scan; no sidecar cache or continuity pass",
    }


def read_selected(reader, frame_index, expected_time):
    if frame_index >= len(reader):
        raise ValueError(
            f"Selected frame {frame_index} unavailable; {len(reader)} frames."
        )
    reader.seek(frame_index)
    frame = reader.read()
    actual = float(frame.time)
    if actual != expected_time:
        raise ValueError(
            f"Selected time mismatch at frame {frame_index}: "
            f"actual {actual} ps; expected exactly {expected_time} ps."
        )
    raw = np.asarray(frame.x, dtype=np.float32) * 10.0
    vectors = np.asarray(frame.box, dtype=np.float64) * 10.0
    if not np.isfinite(vectors).all() or np.linalg.det(vectors) <= 0:
        raise ValueError(f"Frame {frame_index}: invalid box vectors.")
    box = validate_box(triclinic_box(*vectors))
    return raw, box, actual


def write_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def package_results(work):
    archive = work.with_suffix(".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in ARTIFACTS:
            bundle.write(work / name, arcname=f"{work.name}/{name}")
    return archive


def run(topology, trajectory, output_root):
    name = "stage34_pbc_normal_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    work = output_root.resolve() / f"{name}_{uuid4().hex}"
    work.mkdir(parents=True, exist_ok=False)
    result = {
        "execution_status": "incomplete",
        "purpose": "diagnostic only",
        "production_protocol_approved": False,
        "records": [],
        "warnings": [],
        "geometry_probe_thresholds_A": THRESHOLDS_A,
        "representation_comparison_tolerance_A": DISTANCE_TOLERANCE_A,
        "pair_block_limits": [REFERENCE_BLOCK, CONFIGURATION_BLOCK],
        "examples_per_summary_limit": EXAMPLE_LIMIT,
    }
    observations = {}
    config = {v: transformation_parameters(v) for v in VARIANTS}
    exit_code = 1
    with (work / "diagnostic.log").open("x", encoding="utf-8") as log:

        def emit(message):
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            try:
                emit("Checking NORMAL input identity before opening the XTC.")
                observations = input_observations(topology, trajectory)
                if observations["topology_sha256"] != NORMAL_TPR_SHA256:
                    raise ValueError(
                        "NORMAL TPR SHA256 differs from the reviewed hash."
                    )
                if mda.__version__ != "2.10.0":
                    raise ValueError(
                        "This checkpoint requires inspected MDAnalysis 2.10.0."
                    )
                topology_data = TPRParser(str(topology)).parse(tpr_resid_from_one=True)
                work_u = mda.Universe(
                    topology_data,
                    np.zeros((1, topology_data.n_atoms, 3), np.float32),
                    format=MemoryReader,
                    to_guess=(),
                )
                context = topology_context(work_u)
                result["warnings"].extend(context["warnings"])
                result["topology_attachments"] = context["attachments"]
                result["topology_component_count"] = (
                    int(context["components"].max()) + 1
                )
                result["element_evidence"] = (
                    "unguessed topology elements; no name/mass inference"
                    if context["heavy"] is not None
                    else "unavailable; heavy probes skipped"
                )
                with XTCFile(str(trajectory), "r") as reader:
                    for frame_index, expected in zip(FRAMES, TIMES_PS, strict=True):
                        emit(
                            f"Reading selected frame {frame_index}; "
                            f"expected {expected} ps."
                        )
                        raw, box, actual = read_selected(reader, frame_index, expected)
                        result["records"].extend(
                            evaluate_frame(
                                work_u, context, raw, box, frame_index, actual
                            )
                        )
                        emit(
                            f"Frame {frame_index}: "
                            "all three coordinate variants measured."
                        )
                result["execution_status"] = "completed_observations"
                exit_code = 0
            except Exception as exc:
                result["execution_status"] = "failed"
                result["error"] = f"{type(exc).__name__}: {exc}"
                emit("FAILED: " + result["error"])
            except KeyboardInterrupt:
                result["execution_status"] = "interrupted"
                result["error"] = "Interrupted by user; partial observations only."
                exit_code = 130
            result["warnings"].extend(str(w.message) for w in captured)
        if exit_code == 0:
            summary = conclude(result["records"], result["warnings"])
        else:
            summary = (
                "Diagnostic incomplete: "
                + result["error"]
                + "\nNo complete five-frame conclusion is available.\n"
            )
        emit(summary.rstrip())
        result["warnings"] = list(dict.fromkeys(result["warnings"]))
        write_json(work / "pbc_diagnostic.json", result)
        write_json(work / "input_observations.json", observations)
        write_json(work / "transformations.json", config)
        (work / "summary.txt").write_text(summary, encoding="utf-8")
    archive = package_results(work)
    print(f"SEND THIS ARCHIVE: {archive}", flush=True)
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--frames", nargs="+", type=int, required=True)
    parser.add_argument("--expected-times-ps", nargs="+", type=float, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Parent directory; always creates a unique child and ZIP.",
    )
    args = parser.parse_args(argv)
    if tuple(args.frames) != FRAMES or tuple(args.expected_times_ps) != TIMES_PS:
        parser.error(
            "This NORMAL checkpoint requires frames 500 505 510 515 520 "
            "and expected times 5000 5050 5100 5150 5200 ps, exactly."
        )
    return run(args.topology, args.trajectory, args.output)


if __name__ == "__main__":
    sys.exit(main())
