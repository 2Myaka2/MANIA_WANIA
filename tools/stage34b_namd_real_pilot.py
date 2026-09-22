#!/usr/bin/env python3
"""One authority-bound five-frame NAMD pilot; fail closed before protein science."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import shlex
import subprocess
import sys
import time
import traceback
import zipfile
from collections import Counter, defaultdict
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import MDAnalysis as mda
import numpy as np
from MDAnalysis.coordinates.DCD import DCDReader
from MDAnalysis.coordinates.memory import MemoryReader
from MDAnalysis.lib.distances import calc_bonds, minimize_vectors, self_capped_distance
from MDAnalysis.lib.formats.libmdaxdr import XTCFile
from MDAnalysis.lib.mdamath import triclinic_vectors

from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import require_mapped_source_residue
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.dataset_identity import (
    DatasetTemporalParameters,
    DatasetTrajectoryIdentity,
    DatasetTrajectorySpec,
)
from mania.preprocessing import trajectory_contact_chemistry as chemistry
from mania.preprocessing import trajectory_interaction_geometry as geometry
from mania.preprocessing.namd_authority import (
    ElementControl,
    TimeControl,
    read_control,
    validate_elements,
    validate_time,
)
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)
from mania.preprocessing.physical_time_windows import plan_physical_time_windows
from mania.preprocessing.trajectory_contacts import (
    BACKBONE_MAX_CA_DIST_A,
    PreprocessingContactDetectionOptions,
)


def helper(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pbc = helper("pbc_protocol_diagnostic")
mapping_authority = helper("stage34b_namd_mapping_authority")
input_authority = helper("stage34b_namd_authority")
FRAMES = (0, 1, 2, 3, 4)
TIMES_PS = (100.0, 200.0, 300.0, 400.0, 500.0)
PSF_SHA256 = "04b7bee588edf61bde25dfded24216ed4e0727d75d1e144356b500ecc89004bb"
ELEMENT_SHA256 = "f226151e1ba155714a5bf66ef3dac65517e1ca058fbf336a33ff0255dd1de11c"
TIME_SHA256 = "f5434ef78438123bdbcdc8c901ffc94698672671f75d6918494e30bf75a15a17"
MAPPING_SHA256 = "95d5cdb6eed7d847ededf58f968eeb52139815f95fe751f7eca44ccbda681fed"
AUTHORITY_DIRECTORY = (
    "stage34b_authority_20260922T144226Z_e0bab9b6a6f64a998eb2e179785d60b8"
)
MAPPING_DIRECTORY = "stage34b_mapping_20260922T154353Z_29ad662b9bb8"
TOLERANCE_A = pbc.DISTANCE_TOLERANCE_A
METRICS = (
    "n_contact_frames",
    "occupancy",
    "n_contact_episodes",
    "mean_episode_length_ns",
    "max_episode_length_ns",
    "edge_weight",
)
REQUIRED_EVIDENCE = (
    "accepted_authority_bindings",
    "source_input_observations",
    "selected_frames",
    "variant_c_pbc_diagnostic",
    "prepared_trajectory_identity",
    "persisted_pbc_validation",
    "stage27_sampling_result",
    "protein_per_frame_independent_check",
    "protein_window_independent_check",
    "canonicalization_check",
    "technical_validation",
)
LIMITATIONS = (
    "NAMD WT NaPi2b, 2SS, replica 1, PMm; Dataset condition remains unresolved.\n"
    "Variant C is provisional; scientific_pbc_status=unresolved; internal MIC=false.\n"
    "Only source DCD frames 0..4 are read for coordinates. No full DCD hash.\n"
    "DCD/XTC have no atom identity labels; order is checked by the unchanged PSF\n"
    "and pointwise comparison against the exact arrays passed to the writer.\n"
    "No Stage 29 specialized science, Stage 31/32/33 workflows, or Stage 35.\n"
    "No other source trajectory; no long-trajectory contact analysis.\n"
    "Raw inputs and the prepared trajectory are excluded from the evidence ZIP.\n"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def file_record(path):
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": pbc.sha256(path),
    }


def require_hash(path, expected, label):
    record = file_record(path)
    require(record["sha256"] == expected, f"Wrong {label} SHA256")
    return record


def frame_map():
    return [
        dict(
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            requested_sample_index=i,
            authoritative_time_ps=t,
        )
        for i, t in zip(FRAMES, TIMES_PS, strict=True)
    ]


def sampling_contract(times=TIMES_PS):
    require(
        tuple(times) == TIMES_PS, "Exact five-frame scientific time freeze violated"
    )
    temporal = DatasetTemporalParameters(
        production_start_ns=0.1,
        production_end_ns=0.5,
        frame_stride_ps=100,
        window_length_ns=0.4,
        window_step_ns=0.4,
        overlap_percent=0,
    )
    samples = resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, t) for i, t in enumerate(times)),
        temporal=temporal,
    )
    windows = plan_physical_time_windows(samples, temporal=temporal)
    require(
        samples.requested_sample_count == samples.sampled_frame_count == 5
        and samples.missing_sample_count == 0
        and samples.coverage_fraction == 1.0,
        "Stage 27 five-sample resolution failed",
    )
    require(
        tuple(s.source_frame_index for s in samples.selected_samples) == FRAMES,
        "Stage 27 selected different frames",
    )
    require(
        len(windows.windows) == 1
        and windows.windows[0].right_endpoint_inclusive
        and windows.windows[0].source_frame_indexes == FRAMES,
        "Stage 27 requires one inclusive five-sample window",
    )
    return temporal, samples, windows


def threshold_definitions():
    """Frozen enabled distance predicates, including the strict cation-pi bound."""
    return {
        "residue_contact": (
            PreprocessingContactDetectionOptions().cutoff_distance,
            "le",
        ),
        "backbone_CA": (BACKBONE_MAX_CA_DIST_A, "le"),
        "hbond_DA": (chemistry.HBOND_MAX_DONOR_ACCEPTOR_DISTANCE_A, "le"),
        "disulfide_SG": (chemistry.DISULFIDE_MAX_SG_DISTANCE_A, "le"),
        "vdw_lower": (chemistry.VDW_MIN_HEAVY_ATOM_DISTANCE_A, "ge"),
        "vdw_upper": (chemistry.VDW_MAX_HEAVY_ATOM_DISTANCE_A, "le"),
        "hydrophobic_CB": (chemistry.HYDROPHOBIC_MAX_CB_DISTANCE_A, "le"),
        "ionic": (chemistry.IONIC_MAX_CHARGED_ATOM_DISTANCE_A, "le"),
        "salt_bridge": (chemistry.SALT_BRIDGE_MAX_CHARGED_ATOM_DISTANCE_A, "le"),
        "aromatic_centroid": (geometry.AROMATIC_PI_MAX_CENTROID_DISTANCE_A, "le"),
        "cation_centroid": (geometry.CATION_PI_MAX_DISTANCE_A, "lt"),
    }


def classifications(periodic, direct, cutoff, predicate="le"):
    operations = {"le": np.less_equal, "lt": np.less, "ge": np.greater_equal}
    left, right = (
        operations[predicate](periodic, cutoff),
        operations[predicate](direct, cutoff),
    )
    lost, added = left & ~right, right & ~left
    disagreement = np.abs(periodic - direct) > TOLERANCE_A
    boundary = (lost | added) & ~disagreement
    return {
        "strict_periodic": int(left.sum()),
        "strict_direct": int(right.sum()),
        "strict_lost": int(lost.sum()),
        "strict_direct_only": int(added.sum()),
        "numerical_boundary_flips": int(boundary.sum()),
        "substantive_lost": int((lost & disagreement).sum()),
        "substantive_direct_only": int((added & disagreement).sum()),
        "distance_disagreements": int(disagreement.sum()),
    }


def protein_representation(raw, prepared, box, indexes, components):
    """Sparse union of periodic and direct neighbors: direct-only pairs are retained."""
    cutoff = max(t[0] for t in threshold_definitions().values())
    periodic_pairs = self_capped_distance(
        raw[indexes], cutoff, box=box, method="pkdtree", return_distances=False
    )
    direct_pairs = self_capped_distance(
        prepared[indexes], cutoff, method="pkdtree", return_distances=False
    )
    pairs = np.unique(
        np.sort(np.concatenate((periodic_pairs, direct_pairs)), axis=1), axis=0
    )
    a, b = indexes[pairs].T
    periodic = calc_bonds(raw[a], raw[b], box=box)
    direct = np.linalg.norm(
        prepared[a].astype(float) - prepared[b].astype(float), axis=1
    )
    difference = np.abs(periodic - direct)
    inter = components[a] != components[b]
    bad = np.flatnonzero(difference > TOLERANCE_A)
    return {
        "method": "union of sparse periodic/direct self_capped_distance pkdtree pairs",
        "maximum_enabled_range_A": cutoff,
        "heavy_atom_count": len(indexes),
        "periodic_neighbor_pairs": len(periodic_pairs),
        "direct_neighbor_pairs": len(direct_pairs),
        "pair_observations": len(pairs),
        "substantive_mismatches": len(bad),
        "max_distance_disagreement_A": float(difference.max(initial=0)),
        "interfragment_pair_observations": int(inter.sum()),
        "interfragment_substantive_mismatches": int(
            (inter & (difference > TOLERANCE_A)).sum()
        ),
        "thresholds": {
            name: {
                "cutoff_A": cut,
                "predicate": op,
                **classifications(periodic, direct, cut, op),
            }
            for name, (cut, op) in threshold_definitions().items()
        },
        "examples": [
            {
                "atom_indexes": [int(a[i]), int(b[i])],
                "periodic_A": float(periodic[i]),
                "prepared_direct_A": float(direct[i]),
            }
            for i in bad[:10]
        ],
    }


def require_representation(records):
    require(len(records) == 5, "Five diagnostic frames required")
    require(
        all(
            r["bonds"]["all_topology_bonds"]["prepared_direct_disagreement_count"] == 0
            and r["protein"]["substantive_mismatches"] == 0
            and r.get("centroids", {}).get("substantive_mismatches", 0) == 0
            and r.get("hbond_geometry", {}).get("substantive_mismatches", 0) == 0
            for r in records
        ),
        "Substantive NAMD PBC representation mismatch; STOP before MANIA",
    )


def validate_persisted(u, identity, expected_coordinates, box, expected_time):
    actual_box = pbc.validate_box(u.dimensions)
    coordinate_delta = float(
        np.max(np.abs(u.atoms.positions.astype(float) - expected_coordinates))
    )
    checks = {
        name: bool(np.array_equal(values, getattr(u.atoms, name)))
        for name, values in identity.items()
    }
    checks.update(
        finite_coordinates=bool(np.isfinite(u.atoms.positions).all()),
        scientific_time=float(u.trajectory.ts.time) == expected_time,
        box=bool(np.allclose(actual_box, box, rtol=0, atol=2e-5)),
        pointwise_atom_order=coordinate_delta <= 0.0001,
    )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "coordinate_writer_max_error_A": coordinate_delta,
        "box_difference": (actual_box.astype(float) - box).tolist(),
        "actual_time_ps": float(u.trajectory.ts.time),
    }


def attach_elements(u, lookup):
    assigned = [lookup[str(t)] for t in u.atoms.types]
    existing = getattr(u.atoms, "elements", None)
    require(
        existing is None or list(existing) == assigned, "Conflicting prepared elements"
    )
    if existing is None:
        u.add_TopologyAttr("elements", assigned)
    # Audit the frozen name fallback's equivalence; never assign elements by name.
    protein = u.select_atoms("protein")
    require(
        all(
            (a.element.upper() == "H")
            == (a.element.upper() == "H" or a.name.upper().startswith("H"))
            for a in protein
        ),
        "Frozen hydrogen filter conflicts with explicit authority",
    )


def validate_authorities(root, work):
    bundle = root / "namd/egor_2ss_r1/raw"
    psf = bundle / "MD_2_bonds_NPT_W_I_PMm_100_ns.psf"
    dcd = bundle / "MD_2_bonds_NPT_W_I_PMm_100_ns.dcd"
    elements_path = root / AUTHORITY_DIRECTORY / "namd_atom_type_elements.json"
    time_path = root / AUTHORITY_DIRECTORY / "namd_time_authority.json"
    mapping_path = root / MAPPING_DIRECTORY / "namd_canonical_mapping.json"
    hashes = {
        name: require_hash(path, sha, name)
        for name, path, sha in (
            ("psf", psf, PSF_SHA256),
            ("elements", elements_path, ELEMENT_SHA256),
            ("time", time_path, TIME_SHA256),
            ("mapping", mapping_path, MAPPING_SHA256),
        )
    }
    dump(work / "accepted_authority_bindings.json", {"status": "VALIDATING", **hashes})
    _, elements, _, _, header = mapping_authority.accepted_inputs(elements_path.parent)
    require(
        elements == read_control(elements_path, ElementControl),
        "Element strict-read mismatch",
    )
    lookup = validate_elements(elements, psf)
    time_control = read_control(time_path, TimeControl)
    times = validate_time(time_control, dcd)
    require(times[:5] == TIMES_PS, "Wrong accepted time axis")
    require(
        len(lookup) == 97 and sum(elements.used_type_counts.values()) == 439436,
        "Element population guard failed",
    )
    u = mda.Universe(str(psf), to_guess=())
    attach_elements(u, lookup)
    require(
        (
            len(u.atoms),
            len(u.select_atoms("protein").residues),
            len(u.bonds),
            len(u.segments),
        )
        == (439436, 690, 439176, 22),
        "Actual PSF topology observation guard failed",
    )
    mapping = read_canonical_residue_mapping(mapping_path)
    rows = mapping_authority.extract_protein(u)
    binding = json.loads((mapping_path.parent / "psf_binding.json").read_text())
    require(
        binding["mapping_artifact"] == hashes["mapping"],
        "Wrong mapping artifact binding",
    )
    mapping_authority.check_binding(psf, rows, binding)
    mapping_check = mapping_authority.verify_records(
        mapping, rows, load_default_napi2b_canonical_reference()
    )
    features = input_authority.topology_features(u)
    dump(
        work / "source_input_observations.json",
        {
            "psf": hashes["psf"],
            "dcd": time_control.dcd.model_dump(),
            "config": time_control.config.model_dump(),
            "log": time_control.log.model_dump(),
            "atoms": len(u.atoms),
            "protein_residues": len(rows),
            "topology_bonds": len(u.bonds),
            "segments": len(u.segments),
            "topology_features": features,
        },
    )
    dump(
        work / "accepted_authority_bindings.json",
        {
            "status": "PASS",
            **hashes,
            "header_revalidation": header,
            "used_types_covered": len(lookup),
            "atoms_covered": len(u.atoms),
            "unresolved_elements": 0,
            "conflicting_elements": 0,
            "mapping_validation": mapping_check,
            "mapping_psf_binding": binding,
            "authority_science_reimplemented": False,
        },
    )
    return u, psf, dcd, lookup, time_control, mapping_path, mapping, features


def read_five(dcd, time_control, atom_count, work):
    """DCDReader initialization reads frame 0; indexed access is guarded and logged."""
    frames, records = [], []
    reads = [0]
    with DCDReader(str(dcd)) as reader:
        require(reader.n_atoms == atom_count, "DCD/PSF atom count mismatch")
        require(reader.dt == time_control.dcd.dt_ps, "Raw DCD dt differs")
        raw_times = {r.frame: r.time_ps for r in time_control.dcd.observed_times}
        for index, expected in zip(FRAMES, TIMES_PS, strict=True):
            require(index in FRAMES, "Forbidden source coordinate read")
            ts = reader[index]
            reads.append(index)
            box = pbc.validate_box(ts.dimensions)
            coordinates = ts.positions.copy()
            require(
                coordinates.shape == (atom_count, 3) and np.isfinite(coordinates).all(),
                f"Invalid source frame {index}",
            )
            require(float(ts.time) == raw_times[index], "Raw DCD time evidence differs")
            require(
                float(time_control.scientific_times_ps[index]) == expected,
                "Time authority mismatch",
            )
            frames.append((coordinates, box, expected))
            records.append(
                {
                    **frame_map()[index],
                    "raw_dcd_time_ps": float(ts.time),
                    "box": box.tolist(),
                    "finite_coordinates": True,
                    "atom_count": atom_count,
                }
            )
    dump(
        work / "selected_frames.json",
        {
            "frames": records,
            "source_coordinate_read_indexes_including_initialization": reads,
            "unique_source_coordinate_indexes_read": sorted(set(reads)),
            "neighboring_source_frames_read": False,
        },
    )
    return frames


def bond_context(u, features):
    context = pbc.topology_context(u)
    for key in ("C303-C350", "C322-C328"):
        pair = sorted(r["index"] for r in features["features"][key])
        mask = (np.sort(context["bonds"], axis=1) == pair).all(axis=1)
        require(int(mask.sum()) == 1, "Disulfide missing from all-bond diagnostic")
        context["bond_groups"][key] = mask
    return context


def diagnose(u, context, frames, *, persisted=None):
    records, prepared_frames = [], []
    heavy = np.flatnonzero(context["protein"] & context["heavy"])
    for i, (raw, box, actual) in enumerate(frames):
        if persisted is None:
            pbc.prepare_variant(u, raw, box, actual, pbc.VARIANTS[2])
        else:
            u.trajectory[i]
        prepared = u.atoms.positions.copy()
        bonds = pbc.bond_integrity(u, context, raw, prepared, box, {})
        protein = protein_representation(
            raw, prepared, box, heavy, context["components"]
        )
        centroids = centroid_representation(u, raw, prepared, box)
        hbond_geometry = hbond_representation(u, raw, prepared, box)
        records.append(
            {
                **frame_map()[i],
                "bonds": bonds,
                "protein": protein,
                "centroids": centroids,
                "hbond_geometry": hbond_geometry,
            }
        )
        prepared_frames.append(prepared)
        print(
            f"{'Persisted' if persisted else 'Variant C'} frame {i}: "
            "bond disagreements="
            f"{bonds['all_topology_bonds']['prepared_direct_disagreement_count']}; "
            f"protein mismatches={protein['substantive_mismatches']}",
            flush=True,
        )
    return {
        "frames": records,
        "representation_tolerance_A": TOLERANCE_A,
        "bond_boundary_cases": "not applicable: distance agreement, no contact cutoff",
        "protein_fragment_count": len(
            np.unique(context["components"][context["protein"]])
        ),
        "variant_c_sequence": pbc.transformation_parameters(pbc.VARIANTS[2]),
    }, prepared_frames


def persist(psf, lookup, u, context, raw_frames, prepared_frames, work):
    path = work / "prepared_variant_c.xtc"
    require(not path.exists(), "Refusing to overwrite prepared trajectory")
    with XTCFile(str(path), "w") as writer:
        for i, (positions, (_, box, actual)) in enumerate(
            zip(prepared_frames, raw_frames, strict=True)
        ):
            writer.write(
                np.asarray(positions / 10, dtype=np.float32),
                triclinic_vectors(box) / 10,
                i,
                actual,
                precision=1_000_000.0,
            )
    identity_records = []
    reopened = mda.Universe(str(psf), str(path), to_guess=())
    attach_elements(reopened, lookup)
    try:
        require(
            len(reopened.trajectory) == 5,
            "Persisted trajectory must contain five frames",
        )
        for i, (_raw, box, actual) in enumerate(raw_frames):
            reopened.trajectory[i]
            identity_records.append(
                {
                    **frame_map()[i],
                    **validate_persisted(
                        reopened, context["identity"], prepared_frames[i], box, actual
                    ),
                }
            )
        dump(
            work / "prepared_trajectory_identity.json",
            {
                **file_record(path),
                "frames": identity_records,
                "identity_limitation": (
                    "XTC lacks identity labels; PSF and pointwise order checked"
                ),
            },
        )
        require(
            all(r["passed"] for r in identity_records),
            "Persisted identity/time/box mismatch",
        )
        diagnostic, _ = diagnose(reopened, context, raw_frames, persisted=path)
        dump(work / "persisted_pbc_validation.json", diagnostic)
        require_representation(diagnostic["frames"])
    finally:
        reopened.trajectory.close()
    return path


def norm(vector):
    return float(np.sqrt(np.sum(np.asarray(vector, dtype=float) ** 2)))


def angle(first, vertex, third):
    a, b = first - vertex, third - vertex
    na, nb = norm(a), norm(b)
    if min(na, nb) <= geometry._GEOMETRY_TOLERANCE:
        return None
    return math.degrees(math.acos(float(np.clip(np.dot(a / na, b / nb), -1, 1))))


def ring_geometry(coordinates):
    """Independent NumPy symmetric eigensolver, not MANIA's Jacobi implementation."""
    center = coordinates.mean(axis=0)
    centered = coordinates - center
    values, vectors = np.linalg.eigh(centered.T @ centered)
    tolerance = geometry._GEOMETRY_TOLERANCE
    if values[-1] <= tolerance or values[1] <= tolerance * max(1.0, values[-1]):
        return None
    return center, vectors[:, 0]


def protein_layout(u):
    """Explicit elements; names select only the frozen chemical sites."""
    result = []
    elements = np.char.upper(np.asarray(u.atoms.elements, dtype=str))
    require(
        set(elements) & {"D", "T"} == set(),
        "Frozen protein chemistry isotope scope unsupported",
    )
    for i, residue in enumerate(u.select_atoms("protein").residues):
        named = {}
        for atom in residue.atoms:
            named.setdefault(str(atom.name).strip().upper(), int(atom.index))
        heavy = np.asarray(
            [a.index for a in residue.atoms if elements[a.index] != "H"], dtype=int
        )
        donors = {}
        for name, index in named.items():
            if name.lstrip("0123456789").startswith(("N", "O")):
                donors[index] = np.asarray(
                    [
                        a.index
                        for a in u.atoms[index].bonded_atoms
                        if elements[a.index] == "H"
                    ],
                    dtype=int,
                )
        ring_names = chemistry._AROMATIC_RING_ATOMS.get(residue.resname.upper(), ())
        ring = [named[n] for n in ring_names if n in named]
        result.append(
            {
                "index": i,
                "resid": str(residue.resid),
                "resname": str(residue.resname),
                "segid": str(residue.segid),
                "named": named,
                "heavy": heavy,
                "donors": donors,
                "ring": ring if len(ring) == len(ring_names) else [],
                "acceptors": list(donors),
            }
        )
    return result


def centroid_representation(u, raw, prepared, box):
    """Centroid ranges are explicit: an atom-neighbor search alone cannot cover them."""
    rings, cations = [], []
    for r in protein_layout(u):
        indexes = r["ring"]
        if indexes:
            raw_ring = raw[indexes].astype(float)
            whole = raw_ring[0] + minimize_vectors(raw_ring - raw_ring[0], box)
            rg, pg = (
                ring_geometry(whole),
                ring_geometry(prepared[indexes].astype(float)),
            )
            require(
                (rg is None) == (pg is None),
                "Ring degeneracy changed during preparation",
            )
            if rg is not None:
                rings.append((r["index"], rg, pg))
        name = chemistry._CATION_CENTER_ATOMS.get(r["resname"].upper())
        if name in r["named"]:
            index = r["named"][name]
            cations.append(
                (r["index"], raw[index].astype(float), prepared[index].astype(float))
            )
    periodic, direct, kinds, angle_flips = [], [], [], []
    for offset, (i, rg, pg) in enumerate(rings):
        for j, r2, p2 in rings[offset + 1 :]:
            a = norm(minimize_vectors((rg[0] - r2[0])[None, :], box)[0])
            b = norm(pg[0] - p2[0])
            if min(a, b) <= geometry.AROMATIC_PI_MAX_CENTROID_DISTANCE_A:
                periodic.append(a)
                direct.append(b)
                kinds.append("aromatic_centroid")
                ra = math.degrees(
                    math.acos(float(np.clip(abs(np.dot(rg[1], r2[1])), 0, 1)))
                )
                pa = math.degrees(
                    math.acos(float(np.clip(abs(np.dot(pg[1], p2[1])), 0, 1)))
                )
                for cutoff, op in (
                    (geometry.AROMATIC_PI_PARALLEL_MAX_ANGLE_DEG, "lt"),
                    (geometry.AROMATIC_PI_TSHAPED_MIN_ANGLE_DEG, "ge"),
                    (geometry.AROMATIC_PI_TSHAPED_MAX_ANGLE_DEG, "le"),
                ):
                    pred = {"lt": np.less, "ge": np.greater_equal, "le": np.less_equal}[
                        op
                    ]
                    if pred(ra, cutoff) != pred(pa, cutoff):
                        angle_flips.append(
                            dict(
                                residues=[i, j],
                                periodic_deg=ra,
                                direct_deg=pa,
                                cutoff_deg=cutoff,
                                predicate=op,
                            )
                        )
        for j, rc, pc in cations:
            if i == j:
                continue
            a = norm(minimize_vectors((rg[0] - rc)[None, :], box)[0])
            b = norm(pg[0] - pc)
            if min(a, b) <= geometry.CATION_PI_MAX_DISTANCE_A:
                periodic.append(a)
                direct.append(b)
                kinds.append("cation_centroid")
    a, b, kinds = np.asarray(periodic), np.asarray(direct), np.asarray(kinds)
    return {
        "pair_observations": len(a),
        "substantive_mismatches": int((np.abs(a - b) > TOLERANCE_A).sum()),
        "strict_aromatic_angle_boundary_flips": angle_flips,
        "thresholds": {
            kind: classifications(
                a[kinds == kind], b[kinds == kind], *threshold_definitions()[kind]
            )
            for kind in ("aromatic_centroid", "cation_centroid")
        },
    }


def hbond_representation(u, raw, prepared, box):
    """Check explicit D-H-A triples with strict frozen angle membership."""
    layout = protein_layout(u)
    donors = {a: hs for r in layout for a, hs in r["donors"].items() if len(hs)}
    indexes = np.asarray([a for r in layout for a in r["acceptors"]], dtype=int)
    cutoff = chemistry.HBOND_MAX_DONOR_ACCEPTOR_DISTANCE_A
    a = self_capped_distance(
        raw[indexes], cutoff, box=box, method="pkdtree", return_distances=False
    )
    b = self_capped_distance(
        prepared[indexes], cutoff, method="pkdtree", return_distances=False
    )
    pairs = indexes[np.unique(np.sort(np.concatenate((a, b)), axis=1), axis=0)]
    periodic, direct, substantive, flips = [], [], 0, []
    for first, second in pairs:
        if u.atoms[first].resindex == u.atoms[second].resindex:
            continue
        for donor, acceptor in ((first, second), (second, first)):
            for hydrogen in donors.get(donor, ()):
                rp = raw[[donor, hydrogen, acceptor]].astype(float)
                rp = rp[0] + minimize_vectors(rp - rp[0], box)
                pp = prepared[[donor, hydrogen, acceptor]].astype(float)
                ra, pa = angle(*rp), angle(*pp)
                require((ra is None) == (pa is None), "Hbond angle degeneracy changed")
                if ra is None:
                    continue
                disagreement = (
                    max(
                        abs(norm(rp[i] - rp[j]) - norm(pp[i] - pp[j]))
                        for i, j in ((0, 1), (0, 2), (1, 2))
                    )
                    > TOLERANCE_A
                )
                substantive += int(disagreement)
                cutoff_angle = chemistry.HBOND_MIN_DONOR_HYDROGEN_ACCEPTOR_ANGLE_DEG
                periodic.append(ra >= cutoff_angle)
                direct.append(pa >= cutoff_angle)
                if periodic[-1] != direct[-1]:
                    flips.append(
                        {
                            "atom_indexes": [int(donor), int(hydrogen), int(acceptor)],
                            "periodic_angle_deg": ra,
                            "direct_angle_deg": pa,
                            "substantive": disagreement,
                        }
                    )
    left, right = np.asarray(periodic, dtype=bool), np.asarray(direct, dtype=bool)
    return {
        "triple_observations": len(left),
        "substantive_mismatches": substantive,
        "strict_periodic_angle_members": int(left.sum()),
        "strict_direct_angle_members": int(right.sum()),
        "strict_lost": int((left & ~right).sum()),
        "strict_direct_only": int((right & ~left).sum()),
        "numerical_boundary_flips": sum(not f["substantive"] for f in flips),
        "angle_flips": flips,
        "classification": (
            "strict angle >=120 degrees; numerical only when all D-H-A distances "
            "agree within 0.001 A"
        ),
    }


def minimum(coords, left, right):
    if not len(left) or not len(right):
        return math.inf
    delta = coords[left, None, :] - coords[np.asarray(right)[None, :], :]
    return float(np.sqrt(np.sum(delta * delta, axis=2)).min())


def independent_frame(u, layout=None):
    """Direct float64 geometry, frozen constants; no production results."""
    layout = protein_layout(u) if layout is None else layout
    coords = u.atoms.positions.astype(float)
    hbond_angle = chemistry.HBOND_MIN_DONOR_HYDROGEN_ACCEPTOR_ANGLE_DEG
    rings = {r["index"]: ring_geometry(coords[r["ring"]]) for r in layout if r["ring"]}
    contacts, backbones = {}, {}

    def remember(i, j, kind, distance):
        key = (min(i, j), max(i, j), kind)
        contacts[key] = min(distance, contacts.get(key, math.inf))

    for left_offset, left in enumerate(layout):
        i, ln, lr = left["index"], left["named"], left["resname"].upper()
        for right in layout[left_offset + 1 :]:
            j, rn, rr = right["index"], right["named"], right["resname"].upper()
            d = minimum(coords, left["heavy"], right["heavy"])
            if d <= PreprocessingContactDetectionOptions().cutoff_distance:
                remember(i, j, "residue_contact", d)
            if (
                chemistry.VDW_MIN_HEAVY_ATOM_DISTANCE_A
                <= d
                <= chemistry.VDW_MAX_HEAVY_ATOM_DISTANCE_A
            ):
                remember(i, j, "vdw", d)
            if lr == rr == "CYS" and "SG" in ln and "SG" in rn:
                sg = norm(coords[ln["SG"]] - coords[rn["SG"]])
                if sg <= chemistry.DISULFIDE_MAX_SG_DISTANCE_A:
                    remember(i, j, "disulfide", sg)
            if (
                lr in chemistry._HYDROPHOBIC_RESNAMES
                and rr in chemistry._HYDROPHOBIC_RESNAMES
            ):
                if "CB" in ln and "CB" in rn:
                    cb = norm(coords[ln["CB"]] - coords[rn["CB"]])
                    if cb <= chemistry.HYDROPHOBIC_MAX_CB_DISTANCE_A:
                        remember(i, j, "hydrophobic", cb)
            for kind, positive, negative, cutoff in (
                (
                    "ionic",
                    chemistry._POSITIVE_CHARGED_ATOMS,
                    chemistry._NEGATIVE_CHARGED_ATOMS,
                    chemistry.IONIC_MAX_CHARGED_ATOM_DISTANCE_A,
                ),
                (
                    "salt_bridge",
                    chemistry._SALT_BRIDGE_POSITIVE_ATOMS,
                    chemistry._SALT_BRIDGE_NEGATIVE_ATOMS,
                    chemistry.SALT_BRIDGE_MAX_CHARGED_ATOM_DISTANCE_A,
                ),
            ):
                for a, b in ((left, right), (right, left)):
                    ai = [
                        a["named"][n]
                        for n in positive.get(a["resname"].upper(), ())
                        if n in a["named"]
                    ]
                    bi = [
                        b["named"][n]
                        for n in negative.get(b["resname"].upper(), ())
                        if n in b["named"]
                    ]
                    charged = minimum(coords, ai, bi)
                    if charged <= cutoff:
                        remember(i, j, kind, charged)
            if d <= chemistry.HBOND_MAX_DONOR_ACCEPTOR_DISTANCE_A:
                for donor, acceptor in ((left, right), (right, left)):
                    for da, hydrogens in donor["donors"].items():
                        if not len(hydrogens):
                            continue
                        for aa in acceptor["acceptors"]:
                            distance = norm(coords[da] - coords[aa])
                            if (
                                distance
                                <= chemistry.HBOND_MAX_DONOR_ACCEPTOR_DISTANCE_A
                            ):
                                angles = [
                                    angle(coords[da], coords[h], coords[aa])
                                    for h in hydrogens
                                ]
                                if any(
                                    a is not None and a >= hbond_angle for a in angles
                                ):
                                    remember(i, j, "hbond", distance)
            if rings.get(i) is not None and rings.get(j) is not None:
                lc, lv = rings[i]
                rc, rv = rings[j]
                distance = norm(lc - rc)
                normal_angle = math.degrees(
                    math.acos(float(np.clip(abs(np.dot(lv, rv)), 0, 1)))
                )
                if distance <= geometry.AROMATIC_PI_MAX_CENTROID_DISTANCE_A and (
                    normal_angle < geometry.AROMATIC_PI_PARALLEL_MAX_ANGLE_DEG
                    or geometry.AROMATIC_PI_TSHAPED_MIN_ANGLE_DEG
                    <= normal_angle
                    <= geometry.AROMATIC_PI_TSHAPED_MAX_ANGLE_DEG
                ):
                    remember(i, j, "aromatic_pi", distance)
            for a, b in ((left, right), (right, left)):
                name = chemistry._CATION_CENTER_ATOMS.get(a["resname"].upper())
                if name in a["named"] and rings.get(b["index"]) is not None:
                    distance = norm(coords[a["named"][name]] - rings[b["index"]][0])
                    if distance < geometry.CATION_PI_MAX_DISTANCE_A:
                        remember(i, j, "cation_pi", distance)
            if (
                j == i + 1
                and left["segid"] == right["segid"]
                and "CA" in ln
                and "CA" in rn
            ):
                distance = norm(coords[ln["CA"]] - coords[rn["CA"]])
                if distance <= threshold_definitions()["backbone_CA"][0]:
                    backbones[(i, j)] = distance
    return contacts, backbones


def reconstruct_windows(observations, times=TIMES_PS):
    require(
        len(observations) == len(times) == 5,
        "Independent reconstruction needs five resolved samples",
    )
    positives = defaultdict(list)
    for i, frame in enumerate(observations):
        for key in frame:
            positives[key].append(i)
    rows = {}
    for key, positions in positives.items():
        episodes = []
        for position in positions:
            if not episodes or position != episodes[-1][-1] + 1:
                episodes.append([])
            episodes[-1].append(position)
        lengths = [
            (Decimal(str(times[e[-1]])) - Decimal(str(times[e[0]]))) / 1000
            for e in episodes
        ]
        occupancy = len(positions) / 5
        rows[key] = dict(
            n_contact_frames=len(positions),
            occupancy=occupancy,
            n_contact_episodes=len(episodes),
            mean_episode_length_ns=float(sum(lengths) / len(lengths)),
            max_episode_length_ns=float(max(lengths)),
            edge_weight=occupancy,
            requested_positions=positions,
            episodes=episodes,
        )
    return rows


def compare_canonical(source, canonical, mapping):
    def key(row):
        return tuple(
            row[k]
            for k in (
                "dataset_id",
                "system_id",
                "trajectory_id",
                "replica_id",
                "window_id",
                "source_residue_index",
                "target_residue_index",
                "edge_type",
            )
        )

    a, b = {key(r): r for r in source}, {key(r): r for r in canonical}
    require(
        len(a) == len(source) and len(b) == len(canonical),
        "Duplicate canonical/source row",
    )
    differences, features = [], Counter()
    for identity in a.keys() | b.keys():
        if identity not in a or identity not in b:
            differences.append({"identity": identity, "problem": "missing/extra"})
            continue
        left, right = a[identity], b[identity]
        for field, value in left.items():
            if right.get(field) != value:
                differences.append({"identity": identity, "field": field})
        for side in ("source", "target"):
            record = require_mapped_source_residue(
                mapping,
                source_engine=left["engine"],
                source_chain_id=left[f"{side}_chain_id"] or None,
                source_resid=left[f"{side}_resid"],
                source_resname=left[f"{side}_resname"],
            )
            for suffix, value in (
                ("canonical_residue_number", str(record.canonical_residue_number)),
                ("canonical_resname", record.canonical_resname),
            ):
                if right.get(f"{side}_{suffix}") != value:
                    differences.append(
                        {"identity": identity, "field": f"{side}_{suffix}"}
                    )
            if record.canonical_residue_number in (303, 350, 322, 328, 295, 308):
                features[str(record.canonical_residue_number)] += 1
    return {
        "source_rows": len(source),
        "canonical_rows": len(canonical),
        "missing_rows": len(a.keys() - b.keys()),
        "extra_rows": len(b.keys() - a.keys()),
        "scientific_value_mismatches": len(differences),
        "differences": differences,
        "mapped_feature_row_occurrences": dict(features),
        "comparison": (
            "exact equality for every shared field; explicit mapped identities"
        ),
    }


def csv_rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def check_independent(psf, prepared, lookup, mapping, work):
    u = mda.Universe(str(psf), str(prepared), to_guess=())
    attach_elements(u, lookup)
    actual = json.loads((work / "mania_contact_result.json").read_text())
    expected, missing, extra, distances, backbone_errors = [], [], [], [], []
    counts, maximum_distance_delta = [], 0.0
    try:
        layout = protein_layout(u)
        require(
            len(actual["frame_results"]) == 5, "Production per-frame population differs"
        )
        for i in FRAMES:
            u.trajectory[i]
            require(
                float(u.trajectory.ts.time) == TIMES_PS[i],
                "Independent read time mismatch",
            )
            frame, backbones = independent_frame(u, layout)
            expected.append(frame)
            raw = actual["frame_results"][i]
            require(
                raw["frame_index"] == i and raw["time_ps"] == TIMES_PS[i],
                "Production frame identity mismatch",
            )
            observed = {
                (
                    c["source_residue_index"],
                    c["target_residue_index"],
                    c.get("edge_type", "residue_contact"),
                ): c["minimum_distance"]
                for c in raw["contacts"]
            }
            require(
                len(observed) == len(raw["contacts"]), "Duplicate production contact"
            )
            missing.extend((i, k) for k in frame.keys() - observed.keys())
            extra.extend((i, k) for k in observed.keys() - frame.keys())
            for key in frame.keys() & observed.keys():
                delta = abs(frame[key] - observed[key])
                maximum_distance_delta = max(maximum_distance_delta, delta)
                if not math.isclose(
                    frame[key], observed[key], rel_tol=0, abs_tol=1e-12
                ):
                    distances.append((i, key, delta))
            observed_backbones = {
                (r["source_residue_index"], r["target_residue_index"]): r["ca_distance"]
                for r in raw["backbone_observations"]
            }
            if backbones.keys() != observed_backbones.keys() or any(
                not math.isclose(
                    d, observed_backbones.get(k, math.inf), rel_tol=0, abs_tol=1e-12
                )
                for k, d in backbones.items()
            ):
                backbone_errors.append(i)
            counts.append(
                {
                    "frame": i,
                    "contacts": len(frame),
                    "backbones": len(backbones),
                    "by_type": dict(Counter(k[2] for k in frame)),
                }
            )
            print(
                f"Independent frame {i}: {len(frame)} contact observations", flush=True
            )
    finally:
        u.trajectory.close()
    report = {
        "missing_rows": len(missing),
        "extra_rows": len(extra),
        "distance_mismatches": len(distances),
        "backbone_mismatch_frames": backbone_errors,
        "max_distance_delta_A": maximum_distance_delta,
        "counts": counts,
        "details": {"missing": missing, "extra": extra, "distances": distances},
        "method": (
            "float64 direct geometry, explicit elements/bonded H, frozen constants, "
            "NumPy ring eigensolver; no MIC"
        ),
        "floating_comparison": "rel_tol=0, abs_tol=1e-12; strict contact predicates",
    }
    dump(work / "protein_per_frame_independent_check.json", report)
    require(
        not (missing or extra or distances or backbone_errors),
        "Independent per-frame mismatch",
    )
    reconstructed = reconstruct_windows(expected)
    source = csv_rows(work / "output/protein_edges_by_window_source.csv")
    observed_rows = {
        (
            int(r["source_residue_index"]),
            int(r["target_residue_index"]),
            r["edge_type"],
        ): r
        for r in source
    }
    require(len(observed_rows) == len(source), "Duplicate source window row")
    missing_rows = sorted(reconstructed.keys() - observed_rows.keys())
    extra_rows = sorted(observed_rows.keys() - reconstructed.keys())
    mismatches = []
    for key in reconstructed.keys() & observed_rows.keys():
        for field in METRICS:
            a, b = reconstructed[key][field], observed_rows[key][field]
            equal = (
                (a == int(b))
                if field.startswith("n_")
                else math.isclose(a, float(b), rel_tol=0, abs_tol=1e-12)
            )
            if not equal:
                mismatches.append(
                    {"identity": key, "metric": field, "expected": a, "actual": b}
                )
    chronology = None
    if reconstructed:
        key = max(
            sorted(reconstructed),
            key=lambda k: (
                reconstructed[k]["n_contact_episodes"],
                reconstructed[k]["n_contact_frames"] < 5,
            ),
        )
        row = reconstructed[key]
        chronology = {
            "edge_identity": key,
            "source_identity": observed_rows.get(key),
            **row,
            "source_dcd_indexes": list(FRAMES),
            "authoritative_times_ps": list(TIMES_PS),
            "positive_pattern": [i in row["requested_positions"] for i in FRAMES],
            "lifetime_arithmetic_ns": [
                f"{TIMES_PS[e[-1]] / 1000} - {TIMES_PS[e[0]] / 1000}"
                for e in row["episodes"]
            ],
            "occupancy_arithmetic": f"{row['n_contact_frames']} / 5",
        }
    window_report = {
        "source_rows": len(source),
        "independent_rows": len(reconstructed),
        "missing_rows": len(missing_rows),
        "extra_rows": len(extra_rows),
        "metric_mismatches": len(mismatches),
        "mismatches": mismatches,
        "mismatches_by_metric": {
            m: sum(e["metric"] == m for e in mismatches) for m in METRICS
        },
        "floating_comparison": (
            "integer equality; rel_tol=0, abs_tol=1e-12; Decimal episode subtraction"
        ),
        "genuine_chronology": chronology,
    }
    dump(work / "protein_window_independent_check.json", window_report)
    require(
        not (missing_rows or extra_rows or mismatches),
        "Independent Stage 28 window mismatch",
    )
    canonical = compare_canonical(
        source, csv_rows(work / "output/protein_edges_by_window_canonical.csv"), mapping
    )
    dump(work / "canonicalization_check.json", canonical)
    require(
        canonical["scientific_value_mismatches"] == 0,
        "Canonical scientific-value mismatch",
    )
    return report, window_report, canonical


@contextmanager
def timed(timings, name):
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = time.perf_counter() - started


@contextmanager
def replace_attribute(owner, name, replacement):
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    try:
        yield original
    finally:
        setattr(owner, name, original)


def record_command(work, argv, **details):
    path = work / "commands.json"
    records = json.loads(path.read_text()) if path.exists() else []
    records.append({"argv": argv, "command": shlex.join(argv), **details})
    dump(path, records)


def manifest_payload(psf, prepared, mapping_path, work):
    temporal, _, _ = sampling_contract()
    spec = DatasetTrajectorySpec(
        identity=DatasetTrajectoryIdentity(
            dataset_id="napi2b-stage34b-pilot",
            system_id="namd-wt-2ss-pmm",
            trajectory_id="egor-2ss-r1-five-frames",
            variant_id="WT",
            engine="namd",
            condition=None,
            replica_id="1",
            disulfide_state="2SS",
        ),
        temporal=temporal,
    )
    return {
        "output_root": "output",
        "conditions": [
            {
                "condition": "namd-pilot",
                "topology_path": str(psf),
                "trajectory_paths": [str(prepared)],
                "canonical_residue_mapping_path": str(mapping_path),
                "dataset_spec": spec.model_dump(mode="json"),
                "metadata": {
                    "source_membrane_label": "PMm",
                    "protein": "WT NaPi2b",
                    "replica": "1",
                    "external_preparation_evidence": str(work / "pbc_audit.json"),
                    "purpose": (
                        "Stage 34.B.3 protein-only five-frame pilot; "
                        "routing alias is not a Dataset condition"
                    ),
                },
            }
        ],
    }


def run_mania(psf, prepared, lookup, time_control, mapping_path, work, timings):
    """Scoped prepared-input loader; scientific and export functions unchanged."""
    import mania.cli as cli
    from mania.preprocessing import trajectory_contacts as contacts
    from mania.preprocessing import trajectory_manifest_loader as loader
    from mania.preprocessing.namd_runtime import _AuthoritativeTime
    from mania.preprocessing.trajectory_runtime import (
        PreprocessingConditionLoadResult,
        PreprocessingConditionRuntime,
    )

    manifest = work / "pilot_manifest.json"
    dump(manifest, manifest_payload(psf, prepared, mapping_path, work))
    prepared_record = file_record(prepared)
    opened, captured, loaded_state = [], [], []

    def explicit_loader(runtime_input):
        require(
            runtime_input.condition_name == "namd-pilot"
            and runtime_input.topology_path == psf
            and runtime_input.trajectory_paths == (prepared,)
            and runtime_input.frame_time_ps is None,
            "Unexpected scientific runtime input",
        )
        require_hash(psf, PSF_SHA256, "PSF")
        require(
            file_record(prepared) == prepared_record,
            "Prepared trajectory changed before science",
        )
        require(
            validate_time(time_control, Path(time_control.dcd.path))[:5] == TIMES_PS,
            "Scientific time control changed",
        )
        u = mda.Universe(str(psf), str(prepared), to_guess=())
        opened.append(u)
        attach_elements(u, lookup)
        require(len(u.trajectory) == 5, "Unexpected scientific frame count")
        for i in FRAMES:
            require(
                float(u.trajectory[i].time) == TIMES_PS[i],
                "Persisted scientific time changed",
            )
        # Reuse the accepted absolute-index adapter on the verified derivative axis.
        u.trajectory.add_transformations(_AuthoritativeTime(TIMES_PS))
        return PreprocessingConditionLoadResult(
            runtime_input.condition_name,
            runtime_input,
            PreprocessingConditionRuntime(
                runtime_input.condition_name, u, "MDAnalysis.Universe", psf, (prepared,)
            ),
            status="loaded",
        )

    original_compute = contacts.compute_condition_contacts
    original_loading = cli.load_preprocessing_graph_workflow_condition_runtimes
    original_canonical = cli.canonical_tables.build_canonical_protein_edge_window_table

    def capture_contacts(*args, **kwargs):
        require(not captured, "A second protein science run is forbidden")
        require(
            kwargs.get("source_frame_indexes") == FRAMES,
            "Science requires Stage 27 resolved indexes",
        )
        require(
            kwargs["options"].contact_selection == "protein",
            "Protein-only selection required",
        )
        result = original_compute(*args, **kwargs)
        captured.append(result)
        dump(work / "mania_contact_result.json", result.to_dict())
        return result

    def capture_loading(*args, **kwargs):
        result = original_loading(*args, **kwargs)
        loaded_state.append(result)
        return result

    def capture_canonical(*args, **kwargs):
        with timed(timings, "production_canonicalization_seconds"):
            return original_canonical(*args, **kwargs)

    argv = [
        "mania",
        "preprocessing",
        "run-graph-export",
        "--manifest",
        str(manifest),
        "--output",
        str(work / "output"),
        "--run-name",
        work.name,
        "--expected-condition",
        "namd-pilot",
        "--contact-selection",
        "protein",
        "--skip-rg",
        "--export-analysis-inputs",
        "--export-contact-edges",
        "--export-contacts-perframe",
        "--artifact-checksum-mode",
        "none",
        "--verbose",
    ]
    record_command(
        work,
        argv,
        execution="in-process CLI with this runner's explicit prepared loader",
        production_science="unchanged; return-value observation only",
    )
    old_argv = sys.argv
    try:
        with (
            replace_attribute(loader, "load_single_condition_runtime", explicit_loader),
            replace_attribute(contacts, "compute_condition_contacts", capture_contacts),
            replace_attribute(
                cli,
                "load_preprocessing_graph_workflow_condition_runtimes",
                capture_loading,
            ),
            replace_attribute(
                cli.canonical_tables,
                "build_canonical_protein_edge_window_table",
                capture_canonical,
            ),
            (work / "mania_stdout.json").open("w") as stdout,
            (work / "mania_stderr.log").open("w") as stderr,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            sys.argv = argv
            try:
                cli.main()
            except SystemExit as exc:
                require(exc.code in (0, None), f"MANIA CLI failed with code {exc.code}")
    finally:
        sys.argv = old_argv
        for u in opened:
            u.trajectory.close()
    require(
        len(captured) == len(loaded_state) == 1 and captured[0].passed,
        "MANIA protein run incomplete",
    )
    return loaded_state[0]


def technical_validation(loaded_state, mapping_path, work):
    from mania.preprocessing.artifact_inventory import (
        collect_preprocessing_input_file_specs,
        collect_stage30_input_file_specs,
    )
    from mania.preprocessing.physical_time_execution_io import (
        read_preprocessing_temporal_execution,
    )
    from mania.validation import validate_run_artifacts

    temporal = read_preprocessing_temporal_execution(
        work / "output/temporal_execution.json"
    )
    require(len(temporal.bindings) == 1, "Unexpected production temporal population")
    binding = temporal.bindings[0]
    _, expected, windows = sampling_contract()
    require(
        binding.sampling_plan == expected and binding.window_plan == windows,
        "Production Stage 27 differs from frozen five-frame plan",
    )
    dump(
        work / "stage27_sampling_result.json",
        {"status": "PASS", "production_execution": temporal.to_dict()},
    )
    identity = binding.dataset_spec.identity
    key = tuple(
        getattr(identity, n)
        for n in ("dataset_id", "system_id", "trajectory_id", "replica_id")
    )
    specs = (
        *collect_preprocessing_input_file_specs(loaded_state),
        *collect_stage30_input_file_specs(((key, mapping_path),)),
    )
    paths = {s.artifact_id: s.local_path for s in specs}
    dump(work / "technical_input_bindings.json", {k: str(v) for k, v in paths.items()})
    report = validate_run_artifacts(
        work / "output", scope="preprocessing", input_artifact_paths=paths
    )
    dump(work / "technical_validation.json", report.to_dict())
    require(
        report.status == "passed" and report.complete and report.unsupported_count == 0,
        "Required unified technical validation incomplete/failed",
    )
    return report


def package(work):
    archive = work.with_suffix(".zip")
    # Regeneration after verification is confined to this run's sibling archive.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(work.rglob("*")):
            if path.is_file() and not any(
                p in {"wheels", "wheel_install", "__pycache__"}
                for p in path.relative_to(work).parts
            ):
                if path.suffix.lower() in {
                    ".json",
                    ".jsonl",
                    ".csv",
                    ".log",
                    ".txt",
                    ".md",
                    ".py",
                }:
                    stream.write(path, path.relative_to(work))
    return archive


def git_checkpoint(repo, work):
    records = []
    commands = (
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
        ["git", "rev-parse", "develop"],
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        ["git", "log", "--oneline", "--decorate", "-32"],
    )
    for argv in commands:
        result = subprocess.run(
            argv, cwd=repo, text=True, capture_output=True, check=False
        )
        record_command(
            work,
            argv,
            exit_code=result.returncode,
            output=result.stdout + result.stderr,
        )
        require(result.returncode == 0, "Repository checkpoint command failed")
        records.append(result.stdout)
    require(records[0].strip() == "FAIR", "Required branch FAIR")
    for commit in ("2c48aea", "4577530", "360b9be"):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=repo,
            check=False,
        )
        require(
            result.returncode == 0, f"Accepted committed checkpoint missing: {commit}"
        )
    require(
        not subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], cwd=repo, text=True
        ),
        "Nothing may be staged",
    )
    (work / "git_state.txt").write_text(
        "\n".join(
            shlex.join(c) + "\n" + r for c, r in zip(commands, records, strict=True)
        )
    )
    return records[1].strip()


def run(root, work, repo):
    started, timings = time.perf_counter(), {}
    summary = {
        "stage34b3_status": "BLOCKED",
        "stage34b_status": "BLOCKED",
        "scientific_pbc_status": "unresolved",
        "internal_mic": False,
        "mania_executed": False,
        "stage29_specialized_executed": False,
        "stage31_32_33_executed": False,
        "other_namd_source_executed": False,
        "full_trajectory_contacts_executed": False,
        "stage35_executed": False,
    }
    dump(
        work / "pbc_audit.json",
        {
            "source_engine": "NAMD",
            "source_topology": "PSF",
            "source_trajectory": "DCD",
            "scientific_coordinate_representation": (
                "separate persisted five-frame Variant C trajectory"
            ),
            "external_preparation": "Variant C provisional",
            "MANIA_internal_MIC": False,
            "scientific_pbc_status": "unresolved",
        },
    )
    (work / "warnings_limitations.txt").write_text(LIMITATIONS)
    try:
        summary["starting_head"] = git_checkpoint(repo, work)
        with timed(timings, "authority_source_readiness_seconds"):
            u, psf, dcd, lookup, control, mapping_path, mapping, features = (
                validate_authorities(root, work)
            )
            frames = read_five(dcd, control, len(u.atoms), work)
            _, samples, windows = sampling_contract()
            dump(
                work / "stage27_sampling_result.json",
                {
                    "status": "PASS",
                    "phase": "pre-science readiness",
                    "sampling_plan": samples.to_dict(),
                    "window_plan": windows.to_dict(),
                },
            )
            u.load_new(frames[0][0][None, :, :].copy(), format=MemoryReader)
            context = bond_context(u, features)
        with timed(timings, "pbc_diagnostic_seconds"):
            diagnostic, prepared_frames = diagnose(u, context, frames)
            dump(work / "variant_c_pbc_diagnostic.json", diagnostic)
            require_representation(diagnostic["frames"])
        with timed(timings, "persisted_creation_validation_seconds"):
            prepared = persist(psf, lookup, u, context, frames, prepared_frames, work)
        del u, context, frames, prepared_frames
        summary["mania_executed"] = True
        with timed(timings, "mania_stage27_28_and_exports_seconds"):
            loaded = run_mania(
                psf, prepared, lookup, control, mapping_path, work, timings
            )
        with timed(timings, "independent_checker_seconds"):
            check_independent(psf, prepared, lookup, mapping, work)
        with timed(timings, "canonicalization_validation_seconds"):
            technical_validation(loaded, mapping_path, work)
        summary.update(
            stage34b3_status="PASS",
            stage34b_status="PASS",
            repository_verification="pending; requires external regression results",
        )
    except Exception as exc:
        summary["blocker"] = str(exc)
        if summary["mania_executed"]:
            summary["stage34b3_status"] = "FAIL"
        (work / "failure.log").write_text(traceback.format_exc())
        print(f"{summary['stage34b3_status']}: {exc}", flush=True)
    finally:
        timings["total_pilot_seconds"] = time.perf_counter() - started
        for phase in (
            "authority_source_readiness_seconds",
            "pbc_diagnostic_seconds",
            "persisted_creation_validation_seconds",
            "mania_stage27_28_and_exports_seconds",
            "independent_checker_seconds",
            "canonicalization_validation_seconds",
        ):
            timings.setdefault(phase, None)
        for name in REQUIRED_EVIDENCE:
            path = work / (name + ".json")
            if not path.exists():
                dump(
                    path,
                    {
                        "status": "NOT_RUN",
                        "reason": summary.get("blocker", "Earlier gate failed"),
                    },
                )
        summary["current_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        dump(work / "timings.json", timings)
        dump(work / "stage34b_real_pilot_summary.json", summary)
        if not (work / "verification.log").exists():
            (work / "verification.log").write_text("Repository verification pending.\n")
        archive = package(work)
        print(f"SEND THIS ARCHIVE: {archive.resolve()}", flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", type=Path, default=Path("local_md"))
    parser.add_argument("--evidence-directory", type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    root = args.local_root.resolve()
    work = args.evidence_directory or root / (
        "stage34b_namd_real_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid4().hex
    )
    work = work.resolve()
    require(
        work.is_relative_to(root) and work.name.startswith("stage34b_namd_real_"),
        "Unique ignored evidence directory required",
    )
    require(
        not (work / "stage34b_real_pilot_summary.json").exists(),
        "Refusing a second real pilot in this workspace",
    )
    require(
        subprocess.run(
            ["git", "check-ignore", "-q", str(work)], cwd=repo, check=False
        ).returncode
        == 0,
        "Evidence workspace must be ignored",
    )
    work.mkdir(parents=True, exist_ok=True)
    record_command(
        work,
        [
            sys.executable,
            str(Path(__file__).resolve()),
            *(argv if argv is not None else sys.argv[1:]),
        ],
    )
    summary = run(root, work, repo)
    return 0 if summary["stage34b3_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
