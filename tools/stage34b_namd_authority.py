#!/usr/bin/env python3
"""Bounded Stage 34.B input-authority inspection. Never executes science."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np

from mania.dataset_identity import DatasetTemporalParameters
from mania.preprocessing.namd_authority import (
    ElementControl,
    ElementEntry,
    TimeControl,
    collect_definitions,
    definition_elements,
    derive_time,
    literal_config,
    psf_population,
    read_reviewed_assignments,
    source_identity,
    toppar_sources,
    validate_elements,
    validate_time,
    write_control,
)
from mania.preprocessing.namd_runtime import (
    NAMDControlPaths,
    apply_namd_authority,
    observe_dcd,
)
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)
from mania.preprocessing.scientific_runtime import require_mdanalysis


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def one_file(bundle, pattern):
    paths = sorted(bundle.glob(pattern))
    require(len(paths) == 1, f"Require exactly one {pattern}: {paths}")
    return paths[0]


def build_elements(psf, directory, reviews):
    counts, _ = psf_population(psf)
    sources = toppar_sources(directory)
    definitions = collect_definitions(sources, set(counts))
    reviewed = {row.atom_type: row for row in reviews}
    require(len(reviewed) == len(reviews), "Duplicate reviewed exact atom type")
    entries, consumed = [], set()
    for key in counts:
        direct = definition_elements(definitions[key])
        review = None
        if direct:
            element = next(iter(direct))
            kind = "direct_definition"
        else:
            require(key in reviewed, f"Unresolved used type: {key}")
            review = reviewed[key]
            require(review.status == "accepted", f"Unaccepted used type: {key}")
            consumed.add(key)
            element = review.element
            kind = "reviewed_explicit_assignment"
        entries.append(
            ElementEntry(
                atom_type=key,
                element=element,
                authority_kind=kind,
                status="accepted",
                definitions=definitions[key],
                review=review,
            )
        )
    require(consumed == set(reviewed), "Review contains unused/direct type assignments")
    control = ElementControl(
        schema_version="mania.namd_atom_type_elements.v1",
        engine="NAMD",
        psf=source_identity(psf),
        source_directory=str(directory.resolve()),
        sources=sources,
        used_type_counts=counts,
        entries=tuple(entries),
    )
    validate_elements(control, psf)
    return control


def sampling_proof(time):
    # All 1000 axis records come from log/header authority; no full DCD traversal.
    source = tuple(
        PhysicalTimeSourceFrame(i, float(Decimal(t)))
        for i, t in enumerate(time.scientific_times_ps)
    )
    results = {}
    for name, end, count in (("full_grid", 100.0, 1000), ("future_pilot", 0.5, 5)):
        temporal = DatasetTemporalParameters(
            production_start_ns=0.1,
            production_end_ns=end,
            frame_stride_ps=100,
            window_length_ns=0.4,
            window_step_ns=0.4,
            overlap_percent=0,
        )
        plan = resolve_physical_time_sampling(source, temporal=temporal)
        require(
            plan.requested_sample_count == plan.sampled_frame_count == count
            and plan.missing_sample_count == 0,
            f"Stage 27 {name} failed",
        )
        require(
            all(s.time_delta_ps == 0 for s in plan.selected_samples),
            "Stage 27 must resolve without snapping",
        )
        results[name] = plan.to_dict()
    return {
        "status": "PASS",
        "coordinate_pass": False,
        "axis_source": "validated config/log output steps and DCD frame count",
        "global_tolerance_changed": False,
        **results,
    }


def atom_record(atom):
    return dict(
        index=int(atom.index),
        psf_atom_number=int(atom.index) + 1,
        segid=str(atom.segid),
        resid=int(atom.resid),
        resname=str(atom.resname),
        name=str(atom.name),
        atom_type=str(atom.type),
    )


def topology_features(u):
    results = {}
    for first, last in ((303, 350), (322, 328)):
        a = u.select_atoms(f"protein and resid {first} and name SG")
        b = u.select_atoms(f"protein and resid {last} and name SG")
        require(
            len(a) == len(b) == 1 and b[0] in a[0].bonded_atoms,
            f"Missing expected C{first}-C{last} topology bond",
        )
        results[f"C{first}-C{last}"] = [atom_record(a[0]), atom_record(b[0])]
    for resid in (295, 308):
        a = u.select_atoms(f"protein and resname ASN and resid {resid} and name ND2")
        require(len(a) == 1, f"Missing Asn{resid} carrier")
        partners = [
            atom for atom in a[0].bonded_atoms if atom.resindex != a[0].resindex
        ]
        require(
            len(partners) == 1
            and partners[0].resname == "BGLCNA"
            and partners[0].name == "C1",
            f"Unexpected Asn{resid} anchor",
        )
        results[f"Asn{resid}"] = [atom_record(a[0]), atom_record(partners[0])]
    return {"status": "PASS", "evidence_kind": "PSF topology only", "features": results}


def mapping_readiness(u, psf, mapping_path, psf_sha256):
    """Require an explicitly supplied reviewed mapping and its PSF binding."""
    if mapping_path is None or psf_sha256 is None:
        return {
            "status": "BLOCKED",
            "selected_mapping": None,
            "reason": "No reviewed explicit NAMD canonical mapping with PSF binding",
            "numeric_resid_inference": False,
        }
    from mania.canonical_residue_mapping import require_mapped_source_residue
    from mania.canonical_residue_mapping_io import read_canonical_residue_mapping

    require(source_identity(psf).sha256 == psf_sha256, "Wrong mapping PSF binding")
    mapping = read_canonical_residue_mapping(mapping_path)
    resolved = []
    for residue in u.select_atoms("protein").residues:
        record = require_mapped_source_residue(
            mapping,
            source_engine="namd",
            source_chain_id=str(residue.segid) or None,
            source_resid=str(residue.resid),
            source_resname=str(residue.resname),
        )
        resolved.append(record.canonical_residue_number)
    require(
        len(resolved) == len(set(resolved)) == 690,
        "NAMD mapping is not complete and unambiguous",
    )
    return {
        "status": "PASS",
        "selected_mapping": source_identity(mapping_path).model_dump(),
        "psf_sha256": psf_sha256,
        "mapped_residues": len(resolved),
        "numeric_resid_inference": False,
        "authority": "Explicit caller-supplied reviewed mapping and PSF SHA256 binding",
    }


def inspect(args, work):
    bundle = args.bundle.resolve()
    psf, dcd = one_file(bundle, "*.psf"), one_file(bundle, "*.dcd")
    config, log = one_file(bundle, "*.conf"), one_file(bundle, "*.out")
    review_zip = one_file(bundle, "MANIA_NAMD_toppar_review_bundle.zip")
    pdb = bundle / "2_bonds_W_I_PMm.pdb"
    sources = [psf, config, log, pdb, review_zip, args.reviewed_assignments]
    if args.canonical_mapping is not None:
        sources.append(args.canonical_mapping)
    inventory = [source_identity(path).model_dump() for path in sources]
    inventory.extend(
        source.model_dump() for source in toppar_sources(bundle / "toppar")
    )
    inventory.extend(source_identity(p).model_dump() for p in bundle.glob("*.xsc"))
    dump(
        work / "source_inventory.json",
        {
            "hashed_sources": inventory,
            "dcd": {
                "path": str(dcd),
                "size_bytes": dcd.stat().st_size,
                "sha256_computed": False,
            },
        },
    )
    dump(work / "source_hashes.json", {row["path"]: row["sha256"] for row in inventory})
    with zipfile.ZipFile(review_zip) as archive:
        prior = json.loads(archive.read("audit_summary.json"))
        hashes = json.loads(archive.read("source_file_hashes.json"))
        require(
            prior["psf_sha256"] == source_identity(psf).sha256,
            "Review bundle PSF binding differs",
        )
        actual = {
            str(Path(row["path"]).relative_to(bundle)): row["sha256"]
            for row in inventory
            if Path(row["path"]).is_relative_to(bundle / "toppar")
        }
        require(
            actual == hashes, "Original toppar source set differs from supplied bundle"
        )
    config_values = literal_config(config)
    for line in config.read_text().splitlines():
        fields = line.split()
        if fields and fields[0].lower() == "parameters":
            require(
                len(fields) == 2 and (bundle / fields[1]).is_file(),
                "Missing original config parameter source",
            )
    u = require_mdanalysis().Universe(str(psf), str(dcd), to_guess=())
    try:
        counts, masses = psf_population(psf)
        observations = dict(
            atom_count=len(u.atoms),
            residue_count=len(u.residues),
            protein_residue_count=len(u.select_atoms("protein").residues),
            bond_count=len(u.bonds),
            segment_count=len(u.segments),
            used_type_count=len(counts),
            used_type_counts=counts,
            psf_masses=masses,
        )
        dump(work / "psf_observations.json", observations)
        require(
            (
                len(u.atoms),
                observations["protein_residue_count"],
                len(counts),
                len(u.trajectory),
            )
            == (439436, 690, 97, 1000),
            "Real topology/frame observations differ from expected checkpoint; STOP",
        )
        dump(work / "topology_feature_readiness.json", topology_features(u))
        pdb_fields = Counter()
        with pdb.open() as stream:
            for line in stream:
                if line.startswith(("ATOM  ", "HETATM")):
                    pdb_fields[line[76:78].strip()] += 1
        observations["initial_pdb"] = {
            "element_fields": dict(pdb_fields),
            "atom_count": sum(pdb_fields.values()),
            "element_authority": False,
            "limitation": (
                "Initial PDB is NOT element authority or production coordinates"
            ),
        }
        require(sum(pdb_fields.values()) == len(u.atoms), "Initial PDB count differs")
        dump(work / "psf_observations.json", observations)
        raw = observe_dcd(u.trajectory, dcd)
        dump(work / "dcd_raw_timing_observations.json", raw.model_dump())
        derived = derive_time(config, log, raw.frame_count)
        time = TimeControl(
            schema_version="mania.namd_time_authority.v1",
            engine="NAMD",
            config=source_identity(config),
            log=source_identity(log),
            dcd=raw,
            derivation="config_log_step_times_timestep_fs_divided_by_1000",
            status="validated",
            **derived,
        )
        validate_time(time, dcd)
        write_control(work / "namd_time_authority.json", time)
        reviews = read_reviewed_assignments(args.reviewed_assignments)
        elements = build_elements(psf, bundle / "toppar", reviews)
        write_control(work / "namd_atom_type_elements.json", elements)
        review_report = {
            "status": "PASS",
            "used_type_coverage": len(elements.entries),
            "direct_count": sum(
                e.authority_kind == "direct_definition" for e in elements.entries
            ),
            "reviewed_accepted": len(reviews),
            "reviewed_rejected": 0,
            "reviewed_unresolved": 0,
            "unresolved_types": [],
            "entries": [e.model_dump() for e in elements.entries],
            "mass_evidence": {
                e.atom_type: {
                    "psf": masses[e.atom_type],
                    "source": sorted({d.mass for d in e.definitions}),
                }
                for e in elements.entries
            },
            "mass_policy": "Evidence only; differences never assign elements or reject",
        }
        require(
            review_report["direct_count"] == 58 and len(reviews) == 39,
            "Observed direct/reviewed population differs",
        )
        dump(work / "toppar_type_review.json", review_report)
        frames = {}
        for i in (0, 1, 2, 3, 4, 999):
            ts = u.trajectory[i]
            require(np.isfinite(ts.positions).all(), f"Nonfinite coordinates at {i}")
            box = ts.dimensions
            require(
                box is not None
                and np.isfinite(box).all()
                and (box[:3] > 0).all()
                and (box[3:] > 0).all()
                and (box[3:] < 180).all()
                and ts.volume > 0,
                f"Unusable DCD box at frame {i}",
            )
            frames[i] = (ts.positions.copy(), box.copy())
        box_report = {
            "status": "PASS",
            "frames": [
                {
                    "frame": i,
                    "box_A_degrees": frames[i][1].tolist(),
                    "finite_coordinates": True,
                }
                for i in (0, 1, 2, 3, 4)
            ],
            "xst_available": bool(list(bundle.glob("*.xst"))),
        }
        final_xsc = dcd.with_suffix(".xsc")
        if final_xsc.is_file():
            rows = [
                line.split()
                for line in final_xsc.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]
            require(
                len(rows) == 1 and int(rows[0][0]) == time.production_end_step,
                "Final XSC production-step binding differs",
            )
            vectors = np.array(rows[0][1:10], dtype=float).reshape(3, 3)
            from MDAnalysis.lib.mdamath import triclinic_box

            xsc_box = triclinic_box(*vectors)
            require(
                np.allclose(xsc_box, frames[999][1], atol=1e-4, rtol=0),
                "Final XSC/DCD box mismatch",
            )
            box_report["final_xsc_crosscheck"] = {
                "status": "PASS",
                "step": int(rows[0][0]),
                "frame": 999,
                "source": source_identity(final_xsc).model_dump(),
                "box_A_degrees": xsc_box.tolist(),
                "tolerance_A": 1e-4,
                "limitation": "Final XSC does not supply boxes for frames 0..4",
            }
        dump(work / "box_readiness.json", box_report)
        log_text = log.read_text()
        log_atom_counts = re.findall(r"^Info: (\d+) ATOMS$", log_text, re.M)
        require(log_atom_counts == [str(len(u.atoms))], "PSF/log atom counts differ")
        active_bonds = int(re.findall(r"^Info: (\d+) BONDS$", log_text, re.M)[-1])
        ignored_bonds = int(
            re.findall(
                r"^Warning: Ignored (\d+) bonds with zero force constants\.$",
                log_text,
                re.M,
            )[0]
        )
        require(
            len(u.bonds) == active_bonds + ignored_bonds,
            "PSF/log bond accounting differs",
        )
        require(
            raw.atom_count == len(u.atoms) and config_values["dcdfile"] in raw.remarks,
            "PSF/DCD/config correspondence differs",
        )
        dump(
            work / "psf_dcd_correspondence.json",
            {
                "status": "PASS",
                "psf": source_identity(psf).model_dump(),
                "dcd": raw.model_dump(),
                "config_structure": config_values["structure"],
                "config_dcdfile": config_values["dcdfile"],
                "source_bundle": str(bundle),
                "coordinate_frames_read": list(frames),
                "finite_coordinates": True,
                "log_atom_count": int(log_atom_counts[0]),
                "linkage": "User-supplied bundle; review ZIP binds PSF/toppar hashes; "
                "config/log agree on original PSF and DCD names; DCD remarks "
                "retain that original DCD name; header/output sequence agree",
                "renamed_local_files": (
                    psf.name != Path(config_values["structure"]).name
                    or dcd.name != Path(config_values["dcdfile"]).name
                ),
                "log_bond_reconciliation": {
                    "psf_bonds": len(u.bonds),
                    "log_active_bonds": active_bonds,
                    "log_ignored_zero_force_bonds": ignored_bonds,
                    "verified": True,
                },
                "limitation": "DCD has no per-atom identity records; no full DCD hash",
            },
        )
        identity_before = topology_snapshot(u)
        apply_namd_authority(
            u,
            psf,
            dcd,
            NAMDControlPaths(
                work / "namd_atom_type_elements.json",
                work / "namd_time_authority.json",
            ),
        )
        require(topology_snapshot(u) == identity_before, "Adapter changed topology")
        for i in (4, 0, 2, 1, 3, 4, 0, 999):
            ts = u.trajectory[i]
            require(
                ts.time == float(time.scientific_times_ps[i])
                and np.array_equal(ts.positions, frames[i][0])
                and np.array_equal(ts.dimensions, frames[i][1]),
                "Adapter changed coordinates/box or supplied wrong time",
            )
        dump(
            work / "element_authority_validation.json",
            {
                "status": "PASS",
                "coverage": len(elements.entries),
                "atom_element_totals": dict(Counter(u.atoms.elements)),
                "topology_preserved": True,
                "coordinate_box_preserved": True,
                "name_guessing": False,
                "mass_guessing": False,
            },
        )
        dump(work / "stage27_time_resolution_check.json", sampling_proof(time))
        # Canonical mappings cannot be generated from residue-number equality.
        candidates = sorted(bundle.parent.rglob("*mapping*.json"))
        mapping = mapping_readiness(
            u,
            psf,
            args.canonical_mapping,
            args.mapping_psf_sha256,
        )
        mapping["candidates"] = [str(p) for p in candidates]
        dump(work / "canonical_mapping_readiness.json", mapping)
        return {
            "input_authority": "PASS",
            "real_input_readiness": "BLOCKED"
            if mapping["status"] != "PASS"
            else "verification_pending",
            "blockers": [mapping["reason"]] if mapping["status"] != "PASS" else [],
            "psf": str(psf),
            "dcd": str(dcd),
            "config": str(config),
            "log": str(log),
            "toppar": str(bundle / "toppar"),
            "review_bundle": str(review_zip),
            "element_coverage": "97/97",
            "direct": 58,
            "reviewed_accepted": 39,
            "future_pilot": {
                "frames": [0, 1, 2, 3, 4],
                "times_ps": [100, 200, 300, 400, 500],
            },
            "controls": [
                source_identity(work / name).model_dump()
                for name in ("namd_atom_type_elements.json", "namd_time_authority.json")
            ],
        }
    finally:
        u.trajectory.close()


def topology_snapshot(u):
    import hashlib

    digest = hashlib.sha256()
    for name in (
        "indices",
        "names",
        "types",
        "charges",
        "masses",
        "resids",
        "resnames",
        "resindices",
        "segids",
        "segindices",
    ):
        digest.update(json.dumps(getattr(u.atoms, name).tolist()).encode())
    digest.update(u.bonds.indices.tobytes())
    return digest.hexdigest()


def archive_evidence(work):
    archive = work.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(work.iterdir()):
            if path.is_file() and path.suffix in {
                ".json",
                ".txt",
                ".log",
                ".py",
                ".md",
            }:
                z.write(path, arcname=f"{work.name}/{path.name}")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--reviewed-assignments", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("local_md"))
    parser.add_argument("--evidence-directory", type=Path)
    parser.add_argument("--canonical-mapping", type=Path)
    parser.add_argument("--mapping-psf-sha256")
    args = parser.parse_args()
    work = args.evidence_directory or args.output_root / (
        "stage34b_authority_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid.uuid4().hex
    )
    work.mkdir(parents=True, exist_ok=args.evidence_directory is not None)
    require(
        not (work / "stage34b_authority_summary.json").exists(),
        "Evidence directory already contains a run",
    )
    ignored = subprocess.run(["git", "check-ignore", str(work)], capture_output=True)
    require(ignored.returncode == 0, "Evidence directory must be ignored by Git")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    summary = {
        "starting_HEAD": head,
        "current_HEAD": head,
        "scientific_pilot_execution": "NOT RUN",
        "scientific_pbc_status": "unresolved",
        "implementation": "verification_pending",
        "gromacs_regression": "pending",
        "user_declared_identity": {
            "engine": "NAMD",
            "protein": "WT NaPi2b",
            "disulfide_state": "2SS",
            "disulfide_bonds": ["C303-C350", "C322-C328"],
            "replica": 1,
            "membrane_label": "PMm",
            "protein_linked_glycans": {"Asn295": "FA2G2S2", "Asn308": "FA2G2S2"},
            "declared_production_duration_ns": 100,
            "broader_dataset_condition": None,
        },
    }
    dump(
        work / "commands.json",
        [
            {
                "argv": [sys.executable, *sys.argv],
                "command": shlex.join([sys.executable, *sys.argv]),
            }
        ],
    )
    try:
        summary.update(inspect(args, work))
    except Exception as exc:
        summary.update(
            input_authority="BLOCKED",
            real_input_readiness="BLOCKED",
            blockers=[f"{type(exc).__name__}: {exc}"],
        )
    finally:
        dump(work / "stage34b_authority_summary.json", summary)
        (work / "warnings_limitations.txt").write_text(
            "No contacts, Variant C preparation, scientific pilot, full trajectory "
            "workflow, Stage 31/32/33/35 execution, or network access.\n"
            "scientific_pbc_status = unresolved.\n"
            "Initial PDB is NOT element authority or production coordinates.\n"
            "Complete element authority does not establish partner correspondence.\n"
            "Canonical readiness is recorded separately; never inferred.\n"
            "Only DCD frames 0..4 and 999 are read; the 1000-point proof uses "
            "the config/log axis, without a full coordinate pass.\n"
        )
        archive = archive_evidence(work)
    print(
        json.dumps(
            {
                **summary,
                "evidence_directory": str(work.resolve()),
                "evidence_zip": str(archive.resolve()),
            },
            indent=2,
        )
    )
    return 0 if summary.get("real_input_readiness") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
