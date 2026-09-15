#!/usr/bin/env python3
"""Bounded Stage 34.A NORMAL pilot; no production protocol or science changes."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import shlex
import shutil
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import MDAnalysis as mda
import numpy as np
from MDAnalysis.coordinates.memory import MemoryReader
from MDAnalysis.lib.formats.libmdaxdr import XTCFile
from MDAnalysis.topology.TPRParser import TPRParser

from mania import __version__
from mania.canonical_residue_mapping import require_mapped_source_residue
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition,
    MolecularPartnerComponentClassification,
)
from mania.preprocessing.molecular_partner_identification import (
    identify_molecular_partners,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    MolecularPartnerMetadata,
    read_molecular_partner_metadata,
    write_molecular_partner_metadata,
)
from mania.preprocessing.specialized_contact_execution import (
    adapt_molecular_partner_topology,
)

_spec = importlib.util.spec_from_file_location(
    "stage34a_accepted_pbc_diagnostic",
    Path(__file__).with_name("pbc_protocol_diagnostic.py"),
)
pbc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pbc)

FRAMES = pbc.FRAMES
TIMES_PS = pbc.TIMES_PS
CHECKPOINT = "7ea24a51821f6dcfea1b152815a1183e097741b7"
DIAGNOSTIC_BASENAME = (
    "stage34_pbc_normal_20260915T120709Z_65b51f8f405441a790316e72ad9c9ff9.zip"
)
OLD_PILOT = "stage34_normal_5frames_20260914T054036Z_d5e2a9"
# Only this user-authorized NORMAL pilot: never imported by production MANIA.
PILOT_SINGLE_RESIDUE_MEMBRANE = frozenset(
    ("POPC", "POPE", "POPI", "POPS", "PSM", "CHL1")
)
METRICS = (
    "n_contact_frames",
    "occupancy",
    "n_contact_episodes",
    "mean_episode_length_ns",
    "max_episode_length_ns",
    "distance_mean_A",
    "distance_min_A",
)
FLOAT_ATOL = 1e-12
LIMITATIONS = (
    "Variant C is provisional external preparation for exactly five NORMAL frames.\n"
    "scientific_pbc_status=unresolved; MANIA internal MIC=false.\n"
    "No universal PBC or temporal coordinate continuity approval.\n"
    "No biological interpretation, T330M proof, or cross-system partner identity.\n"
    "Stage 34 remains incomplete; this is pre-production evidence only.\n"
    "No Stage 31 aggregation, Stage 32 release QC, Stage 33 publication, NAMD,\n"
    "TUMOR, or full 33-replica execution. Raw XTC is not hashed.\n"
    "Prepared trajectory excluded from ZIP; path, size and SHA256 are retained.\n"
)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_record(path):
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": pbc.sha256(path),
    }


def frame_map():
    return [
        {
            "prepared_frame_index": i,
            "source_frame_index": source,
            "actual_time_ps": actual,
        }
        for i, (source, actual) in enumerate(zip(FRAMES, TIMES_PS, strict=True))
    ]


def require_elements(u):
    attr = getattr(u._topology, "elements", None)
    require(
        attr is not None and not np.any(attr.is_guessed),
        "Missing or guessed authoritative topology elements",
    )
    from MDAnalysis.guesser.tables import SYMB2Z

    elements = np.char.upper(np.asarray(u.atoms.elements, dtype=str))
    valid = {s.upper() for s in SYMB2Z} | {"D", "T"}
    missing = np.flatnonzero(~np.isin(elements, list(valid)))
    require(
        not len(missing), f"Missing element identity at atom indexes {missing.tolist()}"
    )
    return ~np.isin(elements, ["H", "D", "T"])


def residue_record(residue):
    return {
        "residue_index": int(residue.ix),
        "resid": int(residue.resid),
        "resname": str(residue.resname),
        "segid": str(residue.segid),
    }


def component_record(u, indexes, component_id, heavy):
    group = u.atoms[np.asarray(indexes, dtype=int)]
    composition = dict(sorted(Counter(group.residues.resnames).items()))
    return {
        "component_id": component_id,
        "atom_indexes": group.indices.tolist(),
        "residues": [residue_record(r) for r in group.residues],
        "composition": composition,
        "composition_label": "+".join(f"{k}:{v}" for k, v in composition.items()),
        "element_counts": dict(sorted(Counter(group.elements).items())),
        "atom_count": len(group),
        "heavy_atom_count": int(heavy[group.indices].sum()),
    }


def membrane_classification(record):
    """Fail closed using this pilot's explicit authority and actual topology."""
    comp = record["composition"]
    elements = record["element_counts"]
    if len(comp) == 1 and sum(comp.values()) == 1:
        name = next(iter(comp))
        if name in PILOT_SINGLE_RESIDUE_MEMBRANE:
            return (
                "lipid",
                name,
                "User-declared NORMAL membrane class; original TPR name",
            )
        if name == "TIP3" and elements == {"H": 2, "O": 1}:
            return "non_partner", name, "TPR TIP3 connected H2O solvent component"
        if (name, tuple(elements.items())) in (
            ("SOD", (("Na", 1),)),
            ("CLA", (("Cl", 1),)),
        ):
            return "non_partner", name, "TPR single-atom sodium/chloride ion"
    if comp.get("CER160") == 1:
        return (
            "lipid",
            record["composition_label"],
            "User-declared CER160 membrane component; complete TPR composition",
        )
    raise ValueError(
        f"Ambiguous component {record['component_id']}: {comp}; {elements}"
    )


def glycan_components(u, context, heavy):
    """Traverse non-protein topology bonds from each exact attachment."""
    bonds = context["bonds"]
    attached = context["attached"]
    adjacency = defaultdict(list)
    for a, b in bonds[attached[bonds].all(axis=1)]:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    result, seen = [], set()
    for carrier_id in (295, 308):
        carriers = u.select_atoms(
            f"protein and resname ASN and resid {carrier_id}"
        ).residues
        require(len(carriers) == 1, f"Asn{carrier_id}: require one carrier residue")
        carrier = carriers[0]
        carrier_atoms = np.zeros(len(u.atoms), dtype=bool)
        carrier_atoms[carrier.atoms.indices] = True
        cross = bonds[
            (carrier_atoms[bonds[:, 0]] & attached[bonds[:, 1]])
            | (carrier_atoms[bonds[:, 1]] & attached[bonds[:, 0]])
        ]
        require(
            len(cross) == 1, f"Asn{carrier_id}: require exactly one attachment bond"
        )
        a, b = (int(i) for i in cross[0])
        carrier_atom, sugar_atom = (a, b) if carrier_atoms[a] else (b, a)
        branch, pending = {sugar_atom}, [sugar_atom]
        while pending:
            for neighbor in adjacency[pending.pop()]:
                if neighbor not in branch:
                    branch.add(neighbor)
                    pending.append(neighbor)
        require(not (branch & seen), "Declared glycan branches overlap")
        seen.update(branch)
        branch_mask = np.zeros(len(u.atoms), dtype=bool)
        branch_mask[list(branch)] = True
        all_cross = bonds[
            branch_mask[bonds].any(axis=1) & ~branch_mask[bonds].all(axis=1)
        ]
        require(
            len(all_cross) == 1 and set(all_cross[0]) == set(cross[0]),
            f"Asn{carrier_id}: branch has additional external attachment",
        )
        record = component_record(u, sorted(branch), f"glycan_Asn{carrier_id}", heavy)
        require(
            set(record["atom_indexes"])
            == set(u.atoms[sorted(branch)].residues.atoms.indices.tolist()),
            "Glycan branch contains only part of a topology residue",
        )
        record.update(
            partner_id=f"glycan_Asn{carrier_id}",
            partner_kind="glycan",
            partner_name="FA2G2S2",
            carrier_residue=residue_record(carrier),
            carrier_atom_index=carrier_atom,
            carrier_atom_name=str(u.atoms[carrier_atom].name),
            first_sugar_residue=residue_record(u.atoms[sugar_atom].residue),
            first_sugar_atom_index=sugar_atom,
            first_sugar_atom_name=str(u.atoms[sugar_atom].name),
            classification_evidence="User-declared Asn295/Asn308 FA2G2S2 authority",
            linkage_evidence="topology_connectivity",
            ordinary_carrier_pair_excluded=True,
        )
        result.append(record)
    require(
        seen == set(np.flatnonzero(attached).tolist()),
        "Unclassified non-protein branch attached to the protein component",
    )
    return result


def inventory_components(u, context, heavy, work):
    glycans = glycan_components(u, context, heavy)
    dump(work / "glycan_anchor_metadata.json", glycans)
    partners, ambiguous = list(glycans), []
    excluded = Counter()
    for fragment in u.atoms.fragments:
        indexes = fragment.indices
        if context["protein_connected"][indexes].any():
            continue
        record = component_record(u, indexes, int(fragment.fragindices[0]), heavy)
        try:
            kind, name, evidence = membrane_classification(record)
        except ValueError as exc:
            record["error"] = str(exc)
            ambiguous.append(record)
            continue
        if kind == "non_partner":
            excluded[(name, record["composition_label"], evidence)] += 1
            continue
        record.update(
            partner_id=f"membrane_fragment_{record['component_id']:06d}",
            partner_kind=kind,
            partner_name=name,
            classification_evidence=evidence,
        )
        require(
            set(indexes) == set(fragment.residues.atoms.indices),
            "Membrane component contains only part of a topology residue",
        )
        partners.append(record)
    dump(work / "ambiguous_components.json", ambiguous)
    dump(work / "pilot_partner_inventory.json", partners)
    dump(
        work / "non_partner_inventory.json",
        [
            {"name": key[0], "composition": key[1], "evidence": key[2], "count": value}
            for key, value in sorted(excluded.items())
        ],
    )
    require(not ambiguous, f"Ambiguous components: {len(ambiguous)}; contacts stopped")
    return partners


def build_metadata(u, partners, path):
    classifications, definitions = [], []
    for p in partners:
        indexes = tuple(r["residue_index"] for r in p["residues"])
        classifications.extend(
            MolecularPartnerComponentClassification(
                i, p["partner_kind"], p["partner_name"]
            )
            for i in indexes
        )
        linkage = {}
        if p["partner_kind"] == "glycan":
            linkage = {
                "carrier_residue_index": p["carrier_residue"]["residue_index"],
                "first_sugar_residue_index": p["first_sugar_residue"]["residue_index"],
                "linkage_evidence": "topology_connectivity",
            }
        definitions.append(
            ExplicitMolecularPartnerDefinition(
                p["partner_id"],
                p["partner_kind"],
                p["partner_name"],
                indexes,
                **linkage,
            )
        )
    metadata = MolecularPartnerMetadata(tuple(classifications), tuple(definitions))
    require(
        write_molecular_partner_metadata(metadata, path).passed, "Metadata write failed"
    )
    restored = read_molecular_partner_metadata(path)
    require(restored == metadata, "Metadata strict roundtrip failed")
    topology, protein = adapt_molecular_partner_topology(u)
    catalog = identify_molecular_partners(
        topology,
        protein_residue_indexes=protein,
        classifications=restored.classifications,
        explicit_partners=restored.explicit_partners,
    )
    by_id = {p["partner_id"]: p for p in partners}
    for p in catalog.partners:
        require(
            list(p.component_atom_indexes) == by_id[p.partner_id]["atom_indexes"],
            "Accepted catalog changed explicit component atom membership",
        )
    require(catalog.partner_count == len(partners), "Catalog lost explicit partners")
    return catalog


def check_persisted_identity(u, before, raw_box, expected_time):
    ts = u.trajectory.ts
    box = pbc.validate_box(ts.dimensions)
    checks = {
        field: bool(np.array_equal(values, getattr(u.atoms, field)))
        for field, values in before.items()
    }
    checks.update(
        time=float(ts.time) == expected_time,
        box_lengths=bool(np.array_equal(box[:3], raw_box[:3])),
        box_angles=bool(np.array_equal(box[3:], raw_box[3:])),
        finite_coordinates=bool(np.isfinite(u.atoms.positions).all()),
    )
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "actual_time_ps": float(ts.time),
        "time_difference_ps": float(ts.time) - expected_time,
        "box_difference": (box.astype(float) - raw_box.astype(float)).tolist(),
        "atom_count": len(u.atoms),
        "residue_count": len(u.residues),
        "segment_count": len(u.segments),
    }


def write_prepared_frames(u, raw_frames, prepared_path):
    require(not prepared_path.exists(), "Prepared trajectory already exists")
    with XTCFile(str(prepared_path), "w") as writer:
        for raw, box, actual, native_box, step in raw_frames:
            pbc.prepare_variant(u, raw, box, actual, pbc.VARIANTS[2])
            require(
                np.isfinite(u.atoms.positions).all(), "Non-finite prepared coordinates"
            )
            writer.write(
                np.asarray(u.atoms.positions / 10.0, dtype=np.float32),
                native_box,
                step,
                actual,
                precision=1_000_000.0,
            )


def prepare(u, context, source, prepared_path, work):
    """Use accepted Variant C unchanged; preserve native XTC box vectors exactly."""
    raw_frames, source_records = [], []
    with XTCFile(str(source), "r") as reader:
        for source_index, expected in zip(FRAMES, TIMES_PS, strict=True):
            raw, box, actual = pbc.read_selected(reader, source_index, expected)
            require(
                raw.shape == (len(u.atoms), 3) and np.isfinite(raw).all(),
                f"Frame {source_index}: invalid atom count or coordinates",
            )
            reader.seek(source_index)
            native = reader.read()
            raw_frames.append((raw, box, actual, native.box.copy(), int(native.step)))
            source_records.append(
                {
                    "source_frame_index": source_index,
                    "actual_time_ps": actual,
                    "box": box.tolist(),
                    "finite_coordinates": True,
                }
            )
    dump(work / "source_frame_observations.json", source_records)
    write_prepared_frames(u, raw_frames, prepared_path)
    reopened = mda.Universe(
        str(work.parent / "normal/topology.tpr"),
        str(prepared_path),
        to_guess=(),
        tpr_resid_from_one=True,
    )
    identities, bonds = [], []
    try:
        require(
            len(reopened.trajectory) == 5, "Prepared trajectory must have five frames"
        )
        require(
            np.array_equal(reopened.bonds.indices, context["bonds"]),
            "Reopened topology bond identity differs",
        )
        require(
            np.array_equal(reopened.atoms.elements, u.atoms.elements),
            "Reopened topology element identity differs",
        )
        for i, (raw, box, actual, _, _) in enumerate(raw_frames):
            reopened.trajectory[i]
            identity = check_persisted_identity(
                reopened, context["identity"], box, actual
            )
            identity.update(frame_map()[i])
            identities.append(identity)
            integrity = pbc.bond_integrity(
                reopened, context, raw, reopened.atoms.positions, box, {}
            )
            bonds.append({**frame_map()[i], "groups": integrity})
            print(
                f"Persisted frame {i} -> {FRAMES[i]}: "
                f"identity={identity['passed']}; bonded disagreements="
                f"{integrity['all_topology_bonds']['prepared_direct_disagreement_count']}",
                flush=True,
            )
        dump(work / "prepared_trajectory_identity.json", identities)
        dump(
            work / "persisted_bonded_integrity.json",
            {
                "comparison": "prepared direct vs corresponding raw periodic reference",
                "representation_tolerance_A": pbc.DISTANCE_TOLERANCE_A,
                "frames": bonds,
            },
        )
        require(
            all(r["passed"] for r in identities), "Persisted identity/time/box mismatch"
        )
        require(
            all(
                g["prepared_direct_disagreement_count"] == 0
                for r in bonds
                for g in r["groups"].values()
            ),
            "Persisted bonded representation disagreements",
        )
    finally:
        reopened.trajectory.close()
    return identities, bonds


def minimum_distance(left, right):
    """Independent float64 direct Cartesian geometry, without MIC or MANIA API."""
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    require(
        left.ndim == right.ndim == 2 and len(left) > 0 and len(right) > 0,
        "Empty heavy-atom geometry",
    )
    delta = left[:, None, :] - right[None, :, :]
    return float(np.sqrt(np.sum(delta * delta, axis=2)).min())


def ordinary_positive(kind, distance, protein_index, partner):
    cutoff = 6.0 if kind == "lipid" else 4.5
    return distance <= cutoff and not (
        kind == "glycan"
        and protein_index == partner["carrier_residue"]["residue_index"]
    )


def aggregate_observations(observations, times=TIMES_PS):
    """Pilot arithmetic only; requested positions, not source index differences."""
    grouped = defaultdict(list)
    for row in observations:
        if not row["standard_summary_excluded"]:
            grouped[
                (row["partner_kind"], row["protein_residue_index"], row["partner_id"])
            ].append(row)
    summaries = {}
    for key, rows in grouped.items():
        rows = sorted(rows, key=lambda r: r["prepared_frame_index"])
        indexes = [r["prepared_frame_index"] for r in rows]
        require(
            len(indexes) == len(set(indexes)), "Duplicate independent frame identity"
        )
        episodes, start, previous = [], indexes[0], indexes[0]
        for index in indexes[1:]:
            if index != previous + 1:
                episodes.append((times[previous] - times[start]) / 1000.0)
                start = index
            previous = index
        episodes.append((times[previous] - times[start]) / 1000.0)
        distances = [r["minimum_distance_A"] for r in rows]
        summaries[key] = dict(
            zip(
                METRICS,
                (
                    len(rows),
                    len(rows) / len(times),
                    len(episodes),
                    sum(episodes) / len(episodes),
                    max(episodes),
                    sum(distances) / len(distances),
                    min(distances),
                ),
                strict=True,
            )
        )
    return summaries


def write_csv(path, rows, fieldnames=None):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compare_metrics(expected, actual):
    differences = []
    for metric in METRICS:
        a, b = expected[metric], actual[metric]
        equal = (
            (a == int(b))
            if metric.startswith("n_")
            else math.isclose(a, float(b), rel_tol=0.0, abs_tol=FLOAT_ATOL)
        )
        if not equal:
            differences.append({"metric": metric, "expected": a, "actual": b})
    return differences


def compare_canonical(source, canonical, kind, mapping):
    """Compare serialized common fields exactly; resolve explicit mapping only."""

    def key(row):
        return (
            row["dataset_id"],
            row["system_id"],
            row["trajectory_id"],
            row["replica_id"],
            row["window_id"],
            row["protein_residue_index"],
            row[f"{kind}_partner_id"],
        )

    expected = {key(r): r for r in source}
    actual = {key(r): r for r in canonical}
    require(
        len(expected) == len(source) and len(actual) == len(canonical),
        "Duplicate source/canonical identities",
    )
    differences = []
    for identity in sorted(expected.keys() | actual.keys()):
        if identity not in expected or identity not in actual:
            differences.append({"identity": identity, "problem": "missing/extra row"})
            continue
        a, b = expected[identity], actual[identity]
        for field in a:
            if a[field] != b.get(field):
                differences.append(
                    {
                        "identity": identity,
                        "field": field,
                        "source": a[field],
                        "canonical": b.get(field),
                    }
                )
        record = require_mapped_source_residue(
            mapping,
            source_engine=a["engine"],
            source_chain_id=a["protein_chain_id"] or None,
            source_resid=a["protein_resid"],
            source_resname=a["protein_resname"],
        )
        target = {
            "canonical_residue_number": str(record.canonical_residue_number),
            "canonical_resname": record.canonical_resname,
        }
        for field, value in target.items():
            if b.get(field) != value:
                differences.append(
                    {
                        "identity": identity,
                        "field": field,
                        "expected": value,
                        "actual": b.get(field),
                    }
                )
    return differences


def inspect_mapping(u, kit, work):
    path = kit / "mapping/normal.json"
    require(path.is_file(), "Reviewed explicit NORMAL canonical mapping is unavailable")
    old_command = kit / "runs" / OLD_PILOT / "command.json"
    require(old_command.is_file(), "Exact earlier NORMAL pilot command unavailable")
    argv = json.loads(old_command.read_text())
    old_manifest = Path(argv[argv.index("--manifest") + 1])
    require(
        old_manifest.resolve() == (kit / "manifests/normal_5frames.json").resolve(),
        "Earlier NORMAL pilot manifest binding differs",
    )
    entry = json.loads(old_manifest.read_text())["conditions"][0]
    require(
        (old_manifest.parent / entry["canonical_residue_mapping_path"]).resolve()
        == path.resolve(),
        "Mapping is not the earlier NORMAL pilot mapping",
    )
    authority = json.loads((kit / "topology_identity_evidence.json").read_text())[
        "normal"
    ]
    require(
        authority["topology_sha256"] == pbc.NORMAL_TPR_SHA256,
        "Mapping topology authority differs",
    )
    mapping = read_canonical_residue_mapping(path)
    protein = u.select_atoms("protein").residues
    resolved = []
    for residue in protein:
        record = require_mapped_source_residue(
            mapping,
            source_engine="gromacs",
            source_chain_id=str(residue.segid) or None,
            source_resid=str(residue.resid),
            source_resname=str(residue.resname),
        )
        resolved.append(record.canonical_residue_number)
    require(
        len(resolved) == len(mapping.mappings) == 690 and len(set(resolved)) == 690,
        "Reviewed mapping does not completely and uniquely cover the protein",
    )
    dump(
        work / "canonical_mapping_authority.json",
        {
            **file_record(path),
            "earlier_command": file_record(old_command),
            "earlier_manifest": file_record(old_manifest),
            "topology_authority": authority,
            "mapped_protein_residues": len(resolved),
            "mapping_gaps": 0,
            "numeric_resid_inference": False,
        },
    )
    shutil.copyfile(path, work / "canonical_residue_mapping.json")
    return path, mapping


def snapshot(directory):
    if not directory.is_dir():
        return None
    return {
        str(p.relative_to(directory)): file_record(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def recorded_command(work, argv, repo, *, log_name=None):
    path = work / "commands.json"
    commands = json.loads(path.read_text()) if path.exists() else []
    entry = {
        "argv": argv,
        "command": shlex.join(argv),
        "cwd": str(repo),
        "started_at": datetime.now(UTC).isoformat(),
    }
    entry_index = len(commands)
    commands.append(entry)
    dump(path, commands)  # Persist the exact invocation BEFORE execution.
    start = time.perf_counter()
    if log_name:
        with (work / log_name).open("w") as stream:
            process = subprocess.run(
                argv, cwd=repo, stdout=stream, stderr=subprocess.STDOUT, check=False
            )
        output = None
    else:
        process = subprocess.run(
            argv, cwd=repo, capture_output=True, text=True, check=False
        )
        output = process.stdout + process.stderr
    # The child may have appended its in-process CLI invocation.
    commands = json.loads(path.read_text())
    entry.update(
        returncode=process.returncode,
        wall_seconds=time.perf_counter() - start,
        output=output,
        output_log=log_name,
    )
    commands[entry_index] = entry
    dump(path, commands)
    return process.returncode, output


def mania_worker(work, argv):
    """Observe the accepted CLI's actual per-frame returns, without changing them."""
    import mania.cli as cli
    import mania.preprocessing.specialized_contact_execution as execution

    commands = json.loads((work / "commands.json").read_text())
    command = ["mania", *argv]
    commands.append(
        {
            "argv": command,
            "command": shlex.join(command),
            "kind": "in_process_CLI",
            "started_at": datetime.now(UTC).isoformat(),
            "capture": "Return-value observation only; same functions and arguments",
        }
    )
    dump(work / "commands.json", commands)
    originals = {}
    with (work / "mania_specialized_per_frame.jsonl").open("w") as stream:

        def capture(original, kind):
            def wrapper(frame):
                result = original(frame)
                stream.write(
                    json.dumps(
                        {"partner_kind": kind, **result.to_dict()}, allow_nan=False
                    )
                    + "\n"
                )
                stream.flush()
                print(
                    f"MANIA {kind} frame {frame.frame_index}: "
                    f"{result.contact_count} raw positives",
                    file=sys.stderr,
                    flush=True,
                )
                return result

            return wrapper

        try:
            for kind in ("lipid", "glycan"):
                name = f"compute_protein_{kind}_contacts"
                originals[name] = getattr(execution, name)
                setattr(execution, name, capture(originals[name], kind))
            sys.argv = command
            cli.main()
        finally:
            for name, original in originals.items():
                setattr(execution, name, original)


def check_temporal(output):
    from mania.preprocessing.physical_time_execution_io import (
        read_preprocessing_temporal_execution,
    )

    temporal = read_preprocessing_temporal_execution(output / "temporal_execution.json")
    require(len(temporal.bindings) == 1, "Expected one temporal binding")
    binding = temporal.bindings[0]
    plan = binding.sampling_plan
    require(
        binding.selected_source_frame_indexes == tuple(range(5)),
        "Stage 27 must resolve prepared indexes 0..4",
    )
    require(
        plan.requested_sample_count == plan.sampled_frame_count == 5
        and plan.missing_sample_count == 0
        and plan.coverage_fraction == 1.0,
        "Unexpected physical-time coverage",
    )
    require(
        tuple(s.actual_time_ps for s in plan.selected_samples) == TIMES_PS,
        "Physical-time samples differ",
    )
    windows = binding.window_plan.windows
    require(
        len(windows) == 1
        and windows[0].requested_start_ns == 5.0
        and windows[0].requested_end_ns == 5.2
        and windows[0].right_endpoint_inclusive,
        "Expected one inclusive full 5.0-5.2 ns physical window",
    )
    return binding


def independent_check(topology, prepared, partners, mapping, work):
    output = work / "output"
    binding = check_temporal(output)
    identity = binding.dataset_spec.identity.to_dict()
    u = mda.Universe(str(topology), str(prepared), to_guess=(), tpr_resid_from_one=True)
    observations = []
    try:
        heavy = require_elements(u)
        protein = [
            (r, r.atoms.indices[heavy[r.atoms.indices]])
            for r in u.select_atoms("protein").residues
        ]
        partner_heavy = {
            p["partner_id"]: np.asarray(p["atom_indexes"], dtype=int)[
                heavy[p["atom_indexes"]]
            ]
            for p in partners
        }
        require(
            all(len(indexes) for indexes in partner_heavy.values()),
            "Partner lacks heavy atoms",
        )
        for i, ts in enumerate(u.trajectory):
            require(
                i < 5 and ts.time == TIMES_PS[i], "Independent trajectory time mismatch"
            )
            coords = u.atoms.positions.astype(np.float64)
            for residue, indexes in protein:
                for p in partners:
                    distance = minimum_distance(
                        coords[indexes], coords[partner_heavy[p["partner_id"]]]
                    )
                    cutoff = 6.0 if p["partner_kind"] == "lipid" else 4.5
                    if distance > cutoff:
                        continue
                    excluded = not ordinary_positive(
                        p["partner_kind"], distance, int(residue.ix), p
                    )
                    observations.append(
                        {
                            **identity,
                            **frame_map()[i],
                            "partner_kind": p["partner_kind"],
                            "partner_id": p["partner_id"],
                            "partner_name": p["partner_name"],
                            "protein_residue_index": int(residue.ix),
                            "protein_chain_id": str(residue.segid),
                            "protein_resid": int(residue.resid),
                            "protein_resname": str(residue.resname),
                            "minimum_distance_A": distance,
                            "cutoff_A": cutoff,
                            "contact_positive": True,
                            "standard_summary_excluded": excluded,
                        }
                    )
            print(
                f"Independent prepared frame {i}: complete residue x partner geometry",
                flush=True,
            )
    finally:
        u.trajectory.close()
    require(len(observations) > 0, "Pilot has no positive observations")
    write_csv(work / "independent_specialized_per_frame.csv", observations)
    expected_frames = {
        (
            r["partner_kind"],
            r["prepared_frame_index"],
            r["protein_residue_index"],
            r["partner_id"],
        ): r
        for r in observations
    }
    observed_frames = {}
    frame_populations = []
    for line in (work / "mania_specialized_per_frame.jsonl").read_text().splitlines():
        frame = json.loads(line)
        kind = frame["partner_kind"]
        frame_populations.append((kind, frame["frame_index"]))
        require(
            frame["time_ps"] == TIMES_PS[frame["frame_index"]],
            "MANIA observation time mismatch",
        )
        require(
            frame["evaluated_pair_count"]
            == len(protein) * sum(p["partner_kind"] == kind for p in partners),
            "MANIA did not evaluate every explicit partner",
        )
        for contact in frame["contacts"]:
            key = (
                kind,
                frame["frame_index"],
                contact["protein_residue_index"],
                contact[f"{kind}_partner_id"],
            )
            require(key not in observed_frames, "Duplicate MANIA per-frame identity")
            observed_frames[key] = contact
    require(
        sorted(frame_populations)
        == sorted((k, i) for k in ("lipid", "glycan") for i in range(5)),
        "MANIA raw geometry did not cover both layers and all five frames",
    )
    missing, extra = (
        sorted(expected_frames.keys() - observed_frames.keys()),
        sorted(observed_frames.keys() - expected_frames.keys()),
    )
    distance_errors, anchor_errors = [], []
    max_delta = 0.0
    for key in expected_frames.keys() & observed_frames.keys():
        a, b = expected_frames[key], observed_frames[key]
        delta = abs(a["minimum_distance_A"] - b["minimum_distance_A"])
        max_delta = max(max_delta, delta)
        if delta > FLOAT_ATOL:
            distance_errors.append({"identity": key, "delta_A": delta})
        if a["standard_summary_excluded"] != b.get("standard_summary_excluded", False):
            anchor_errors.append(
                {"identity": key, "problem": "exclusion flag mismatch"}
            )
    summaries = aggregate_observations(observations)
    metric_errors, canonical_errors, populations = [], [], {}
    from mania import canonical_window_tables_io as canonical_io
    from mania.preprocessing import specialized_contact_window_tables_io as source_io

    for kind in ("lipid", "glycan"):
        source_path = output / f"protein_{kind}_contacts_by_window_source.csv"
        canonical_path = output / f"protein_{kind}_contacts_by_window_canonical.csv"
        getattr(source_io, f"read_protein_{kind}_window_csv")(source_path)
        getattr(canonical_io, f"read_canonical_protein_{kind}_window_csv")(
            canonical_path
        )
        with source_path.open() as stream:
            reader = csv.DictReader(stream)
            require(
                "edge_weight" not in reader.fieldnames,
                "Specialized edge_weight is forbidden",
            )
            source_rows = list(reader)
        with canonical_path.open() as stream:
            reader = csv.DictReader(stream)
            require(
                "edge_weight" not in reader.fieldnames,
                "Specialized edge_weight is forbidden",
            )
            canonical_rows = list(reader)
        actual = {
            (kind, int(r["protein_residue_index"]), r[f"{kind}_partner_id"]): r
            for r in source_rows
        }
        expected = {key: value for key, value in summaries.items() if key[0] == kind}
        for key in sorted(expected.keys() | actual.keys()):
            if key not in expected or key not in actual:
                metric_errors.append(
                    {"identity": key, "problem": "missing/extra window row"}
                )
                continue
            metric_errors.extend(
                {"identity": key, **error}
                for error in compare_metrics(expected[key], actual[key])
            )
        canonical_errors.extend(
            compare_canonical(source_rows, canonical_rows, kind, mapping)
        )
        positives = [r for r in observations if r["partner_kind"] == kind]
        populations[kind] = {
            "partner_count": sum(p["partner_kind"] == kind for p in partners),
            "raw_positive_observations": len(positives),
            "ordinary_positive_observations": sum(
                not r["standard_summary_excluded"] for r in positives
            ),
            "excluded_anchor_observations": sum(
                r["standard_summary_excluded"] for r in positives
            ),
            "contacted_partner_count": len(
                {
                    r["partner_id"]
                    for r in positives
                    if not r["standard_summary_excluded"]
                }
            ),
            "window_rows": len(source_rows),
            "canonical_rows": len(canonical_rows),
        }
        if kind == "glycan":
            for p in (p for p in partners if p["partner_kind"] == kind):
                own_key = (kind, p["carrier_residue"]["residue_index"], p["partner_id"])
                if own_key in expected or own_key in actual:
                    anchor_errors.append(
                        {
                            "identity": own_key,
                            "problem": "carrier entered ordinary summary",
                        }
                    )
    review = []
    for p in partners:
        positives = [
            r
            for r in observations
            if r["partner_id"] == p["partner_id"] and not r["standard_summary_excluded"]
        ]
        review.append(
            {
                "partner_id": p["partner_id"],
                "kind": p["partner_kind"],
                "partner_name": p["partner_name"],
                "composition": p["composition_label"],
                "residues": ";".join(
                    f"{r['residue_index']}:{r['resid']}:{r['resname']}"
                    for r in p["residues"]
                ),
                "atom_count": p["atom_count"],
                "heavy_atom_count": p["heavy_atom_count"],
                "classification_evidence": p["classification_evidence"],
                "contacted": bool(positives),
                "ordinary_positive_observations": len(positives),
                "ordinary_window_rows": sum(
                    key[2] == p["partner_id"] for key in summaries
                ),
            }
        )
    write_csv(work / "pilot_partner_review.csv", review)
    dump(
        work / "glycan_review.json",
        [
            {**p, **next(r for r in review if r["partner_id"] == p["partner_id"])}
            for p in partners
            if p["partner_kind"] == "glycan"
        ],
    )
    report = {
        "comparison_semantics": "Exact identities/counts; float64 direct geometry; "
        "abs_tol=1e-12, rel_tol=0 for geometry and metrics; cutoffs have NO tolerance; "
        "all common serialized source/canonical fields exactly equal",
        "missing_MANIA_positives": missing,
        "unexpected_MANIA_positives": extra,
        "distance_mismatches": distance_errors,
        "max_distance_delta_A": max_delta,
        "metric_mismatches": metric_errors,
        "anchor_exclusion_mismatches": anchor_errors,
        "canonical_mismatches": canonical_errors,
        "counts": populations,
        "membrane_compositions": dict(
            sorted(
                Counter(
                    p["composition_label"]
                    for p in partners
                    if p["partner_kind"] == "lipid"
                ).items()
            )
        ),
    }
    report["passed"] = not any(
        (
            missing,
            extra,
            distance_errors,
            metric_errors,
            anchor_errors,
            canonical_errors,
        )
    )
    dump(work / "independent_specialized_window_check.json", report)
    require(
        report["passed"],
        "Independent specialized comparison failed; inspect detailed evidence",
    )
    return report


def validate_technical(work, inputs):
    from mania.preprocessing.molecular_partner_catalog_io import (
        read_molecular_partner_catalog,
    )
    from mania.validation import validate_run_artifacts

    output = work / "output"
    inventory = json.loads((output / "artifact_inventory.json").read_text())
    bindings = {}
    for entry in inventory["artifacts"]:
        if entry["direction"] == "input":
            require(
                entry["role"] in inputs,
                f"Unbound technical input role: {entry['role']}",
            )
            bindings[entry["artifact_id"]] = inputs[entry["role"]]
    dump(
        work / "technical_input_bindings.json", {k: str(v) for k, v in bindings.items()}
    )
    report = validate_run_artifacts(
        output, scope="preprocessing", input_artifact_paths=bindings
    )
    dump(work / "technical_validation.json", report.to_dict())
    require(
        report.status == "passed" and report.complete,
        "Technical validation incomplete/failed",
    )
    audit = json.loads((output / "pbc_audit.json").read_text())

    def check_status(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "scientific_pbc_status":
                    require(item == "unresolved", "PBC status changed")
                if key == "mania_internal_minimum_image_correction_applied":
                    require(item is False, "Internal MANIA MIC changed")
                check_status(item)
        elif isinstance(value, list):
            for item in value:
                check_status(item)

    check_status(audit)
    catalog = read_molecular_partner_catalog(output / "molecular_partner_catalog.json")
    shutil.copyfile(
        output / "molecular_partner_catalog.json",
        work / "molecular_partner_catalog.json",
    )
    return report, catalog


def run(repo, session_commands=None, verification=None):
    start = time.perf_counter()
    name = (
        "stage34a_specialized_normal_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid4().hex
    )
    work = repo / "local_md" / name
    work.mkdir(parents=True, exist_ok=False)
    commands = json.loads(session_commands.read_text()) if session_commands else []
    commands.append(
        {
            "argv": [sys.executable, *sys.argv],
            "command": shlex.join([sys.executable, *sys.argv]),
            "kind": "runner_entry",
            "started_at": datetime.now(UTC).isoformat(),
        }
    )
    dump(work / "commands.json", commands)
    if verification:
        shutil.copyfile(verification, work / "repository_verification.json")
    summary = {
        "stage": "34.A",
        "scope": "Real five-frame NORMAL specialized GROMACS pilot",
        "stage34a_acceptance": "FAIL",
        "technical_execution_status": "not_run",
        "independent_scientific_consistency": "not_run",
        "production_code_changes": [],
        "scientific_pbc_status": "unresolved",
        "MANIA_internal_MIC": False,
        "stage34_complete": False,
        "frame_map": frame_map(),
        "remaining_stage34_blockers": [
            "Universal scientific PBC protocol unresolved",
            "Real three-replica group (preferably T330M), mapping and physical windows",
            "Authoritative real QC-derived availability/exclusion and real aggregation",
            "Authoritative cross-replica/system specialized partner correspondence",
            "Remaining multi-engine pilot evidence, including NAMD condition authority",
        ],
    }
    timings = {
        "preparation_wall_seconds": None,
        "MANIA_wall_seconds": None,
        "independent_checker_wall_seconds": None,
    }
    kit = repo / "local_md/stage34_start_ae1cafd"
    old_directory = kit / "runs" / OLD_PILOT
    old_before = snapshot(old_directory)
    dump(work / "previous_protein_only_artifacts_before.json", old_before)
    diagnostic = repo / "local_md/pbc_diagnostics" / DIAGNOSTIC_BASENAME
    supporting = file_record(diagnostic) if diagnostic.is_file() else None
    dump(
        work / "supporting_PBC_diagnostic.json",
        {"exact_basename": DIAGNOSTIC_BASENAME, "archive": supporting},
    )
    topology = repo / "local_md/normal/topology.tpr"
    trajectory = repo / "local_md/normal/trajectory.xtc"
    prepared = work / "prepared_normal_5frames.xtc"
    provenance = {
        "Variant_C": pbc.transformation_parameters(pbc.VARIANTS[2]),
        "protein_selection": "protein",
        "frame_map": frame_map(),
        "MANIA_version": __version__,
        "MDAnalysis_version": mda.__version__,
        "pilot_helper": file_record(Path(__file__).resolve()),
        "accepted_diagnostic_helper": file_record(
            Path(__file__).with_name("pbc_protocol_diagnostic.py").resolve()
        ),
        "scientific_pbc_status": "unresolved",
        "supporting_diagnostic": supporting,
        "writer": "MDAnalysis XTCFile; original atom order and native box vectors",
        "writer_precision_nm_inverse": 1_000_000.0,
        "prepared_trajectory": None,
    }
    shutil.copyfile(Path(__file__), work / "pilot_runner_source.py")
    exit_code = 1
    caught_warnings = []
    try:
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            git_lines = []
            for argv in (
                ["git", "branch", "--show-current"],
                ["git", "rev-parse", "HEAD"],
                ["git", "status", "--short"],
                ["git", "rev-parse", "develop"],
                ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
                ["git", "merge-base", "--is-ancestor", CHECKPOINT, "HEAD"],
            ):
                code, output = recorded_command(work, argv, repo)
                git_lines.append(f"$ {shlex.join(argv)}\n{output}exit={code}\n")
                require(code == 0, f"Repository checkpoint failed: {shlex.join(argv)}")
                if argv == ["git", "branch", "--show-current"]:
                    require(output.strip() == "FAIR", "Expected branch FAIR")
                if argv == ["git", "rev-parse", "HEAD"]:
                    summary["current_HEAD"] = provenance["current_git_SHA"] = (
                        output.strip()
                    )
            (work / "git_state.txt").write_text("\n".join(git_lines))
            prep_start = time.perf_counter()
            source = {
                "topology": file_record(topology),
                "trajectory": {
                    "path": str(trajectory),
                    "size_bytes": trajectory.stat().st_size,
                    "sha256_computed": False,
                },
                "expected_topology_sha256": pbc.NORMAL_TPR_SHA256,
                "requested_source_frame_indexes": list(FRAMES),
                "requested_times_ps": list(TIMES_PS),
            }
            dump(work / "source_input_observations.json", source)
            require(
                source["topology"]["sha256"] == pbc.NORMAL_TPR_SHA256,
                "NORMAL TPR hash mismatch",
            )
            require(
                mda.__version__ == "2.10.0",
                "Variant C checkpoint requires MDAnalysis 2.10.0",
            )
            topology_data = TPRParser(str(topology)).parse(tpr_resid_from_one=True)
            u = mda.Universe(
                topology_data,
                np.zeros((1, topology_data.n_atoms, 3), np.float32),
                format=MemoryReader,
                to_guess=(),
            )
            context = pbc.topology_context(u)
            heavy = require_elements(u)
            require(
                not context["warnings"],
                f"Topology guard warnings: {context['warnings']}",
            )
            source.update(
                atom_count=len(u.atoms),
                residue_count=len(u.residues),
                segment_count=len(u.segments),
                topology_bond_count=len(u.bonds),
                element_counts=dict(sorted(Counter(u.atoms.elements).items())),
                elements_authoritative=True,
                bonds_authoritative=True,
            )
            dump(work / "source_input_observations.json", source)
            provenance.update(
                source_topology=source["topology"],
                source_trajectory=source["trajectory"],
            )
            print(
                "Building exact glycan anchors and complete component inventory",
                flush=True,
            )
            partners = inventory_components(u, context, heavy, work)
            metadata_path = work / "molecular_partner_metadata.json"
            catalog = build_metadata(u, partners, metadata_path)
            mapping_path, mapping = inspect_mapping(u, kit, work)
            print(
                f"Metadata guards passed: {catalog.lipid_partner_count} lipids, "
                f"{catalog.glycan_partner_count} glycans; 690 mapped protein residues",
                flush=True,
            )
            identities, bonds = prepare(u, context, trajectory, prepared, work)
            provenance.update(
                prepared_trajectory=file_record(prepared),
                identity_checks=identities,
                bonded_integrity=bonds,
                prepared_frame_indexes=list(range(5)),
            )
            timings["preparation_wall_seconds"] = time.perf_counter() - prep_start
            dump(work / "pbc_preparation_provenance.json", provenance)
            manifest = {
                "output_root": "output",
                "conditions": [
                    {
                        "condition": "normal",
                        "topology_path": str(topology),
                        "trajectory_paths": [str(prepared)],
                        "canonical_residue_mapping_path": str(mapping_path),
                        "molecular_partner_metadata_path": str(metadata_path),
                        "metadata": {
                            "purpose": "Stage 34.A short NORMAL pre-production pilot",
                            "external_preparation_evidence": str(
                                work / "pbc_preparation_provenance.json"
                            ),
                        },
                        "dataset_spec": {
                            "identity": {
                                "dataset_id": "napi2b-stage34a-specialized-pilot",
                                "system_id": "normal-local-input",
                                "trajectory_id": "normal-prepared-5frames",
                                "variant_id": "WT",
                                "engine": "gromacs",
                                "condition": "normal",
                                "replica_id": "local-pilot-not-production-id",
                                "disulfide_state": None,
                            },
                            "temporal": {
                                "production_start_ns": 5.0,
                                "production_end_ns": 5.2,
                                "frame_stride_ps": 50.0,
                                "window_length_ns": 0.2,
                                "window_step_ns": 0.2,
                                "overlap_percent": 0.0,
                            },
                        },
                    }
                ],
            }
            manifest_path = work / "pilot_manifest.json"
            dump(manifest_path, manifest)
            del context, u, topology_data
            cli_args = [
                "preprocessing",
                "run-graph-export",
                "--manifest",
                str(manifest_path),
                "--output",
                str(work / "output"),
                "--run-name",
                name,
                "--expected-condition",
                "normal",
                "--contact-selection",
                "protein",
                "--export-analysis-inputs",
                "--artifact-checksum-mode",
                "none",
                "--verbose",
            ]
            mania_start = time.perf_counter()
            print(
                "Preparation and metadata guards passed; invoking accepted MANIA CLI",
                flush=True,
            )
            code, _ = recorded_command(
                work,
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--capture-mania",
                    str(work),
                    *cli_args,
                ],
                repo,
                log_name="preprocessing.log",
            )
            timings["MANIA_wall_seconds"] = time.perf_counter() - mania_start
            summary["technical_execution_status"] = (
                "completed" if code == 0 else "failed"
            )
            require(code == 0, "MANIA preprocessing failed; see preprocessing.log")
            technical, actual_catalog = validate_technical(
                work,
                {
                    "input_manifest": manifest_path,
                    "condition_topology": topology,
                    "condition_trajectory": prepared,
                    "canonical_residue_mapping": mapping_path,
                    "molecular_partner_metadata": metadata_path,
                },
            )
            require(
                len(actual_catalog.bindings) == 1
                and actual_catalog.bindings[0].partner_catalog == catalog,
                "MANIA catalog differs from the accepted preflight catalog",
            )
            summary["technical_validation"] = {
                "status": technical.status,
                "complete": technical.complete,
                "errors": technical.error_count,
                "warnings": technical.warning_count,
            }
            check_start = time.perf_counter()
            independent = independent_check(topology, prepared, partners, mapping, work)
            timings["independent_checker_wall_seconds"] = (
                time.perf_counter() - check_start
            )
            summary.update(
                independent_scientific_consistency="passed",
                counts=independent["counts"],
                membrane_compositions=independent["membrane_compositions"],
                geometry_mismatches=0,
                metric_mismatches=0,
                anchor_exclusion_mismatches=0,
                canonical_mismatches=0,
                total_prepared_frames=5,
            )
            if verification:
                checks = json.loads(verification.read_text())
                require(
                    checks and all(c["result"]["exit_code"] == 0 for c in checks),
                    "Repository verification contains a failed or incomplete command",
                )
                summary["stage34a_acceptance"] = "PASS"
            else:
                summary["stage34a_acceptance"] = "PENDING_REPOSITORY_VERIFICATION"
            exit_code = 0
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        (work / "error.txt").write_text(traceback.format_exc())
        print(f"STOP: {summary['error']}", file=sys.stderr, flush=True)
    finally:
        if prepared.is_file():
            provenance["prepared_trajectory"] = file_record(prepared)
        dump(work / "pbc_preparation_provenance.json", provenance)
        old_after = snapshot(old_directory)
        unchanged = old_before == old_after
        summary["old_protein_only_outputs_unchanged"] = unchanged
        dump(work / "previous_protein_only_artifacts_after.json", old_after)
        if not unchanged or (supporting and file_record(diagnostic) != supporting):
            summary["stage34a_acceptance"] = "FAIL"
            summary["protection_error"] = (
                "Previous pilot or supporting diagnostic changed"
            )
            exit_code = 1
        timings["total_pilot_wall_seconds"] = time.perf_counter() - start
        dump(work / "runtime_timing.json", timings)
        summary["timings"] = timings
        summary["warnings"] = sorted({str(w.message) for w in caught_warnings})
        (work / "warnings_limitations.txt").write_text(
            LIMITATIONS + "\n" + "\n".join(summary["warnings"]) + "\n"
        )
        dump(work / "pilot_summary.json", summary)
        archive = work.with_suffix(".zip")
        with zipfile.ZipFile(
            archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as z:
            for path in sorted(work.rglob("*")):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.suffix.lower()
                    not in (
                        ".tpr",
                        ".xtc",
                        ".trr",
                        ".dcd",
                    )
                ):
                    z.write(
                        path,
                        arcname=(Path(work.name) / path.relative_to(work)).as_posix(),
                    )
        print(f"Stage 34.A acceptance: {summary['stage34a_acceptance']}", flush=True)
        print(f"SEND THIS ARCHIVE: {archive}", flush=True)
    return exit_code


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--capture-mania":
        mania_worker(Path(argv[1]), argv[2:])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--session-commands", type=Path)
    parser.add_argument("--verification-evidence", type=Path)
    args = parser.parse_args(argv)
    return run(args.repo.resolve(), args.session_commands, args.verification_evidence)


if __name__ == "__main__":
    raise SystemExit(main())
