#!/usr/bin/env python3
"""Two bounded, source-bound protein pilots; stop at pending human RMSD review.

Scientific formulas and gates come from accepted Stage 34.B helpers. Only the
input bindings, replica identities and evidence orchestration are new here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import shutil
import struct
import subprocess
import time
import traceback
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import MDAnalysis as mda
import numpy as np
from MDAnalysis import units
from MDAnalysis.coordinates.memory import MemoryReader

from mania.preprocessing.namd_authority import (
    DCDIdentity,
    RawFrameTime,
    TimeControl,
    derive_time,
    source_identity,
    write_control,
)

# The helper loader resolves sibling files without changing import search paths.
_spec_path = Path(__file__).with_name("stage34b_namd_real_pilot.py")

_spec = importlib.util.spec_from_file_location("stage34c_b3", _spec_path)
b3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b3)
qc = b3.helper("stage34b5_single_replica_release_smoke")
rmsd = b3.helper("stage34b5_rmsd_review_evidence")
require, dump, file_record = b3.require, b3.dump, b3.file_record
FRAMES, TIMES_PS = b3.FRAMES, b3.TIMES_PS
INTAKE = "stage34c_intake_20260923T142525Z_fffa835e6823"
INTAKE_SHA = "93547ed34912ec59f06509983aa694cfa17242cc3a16713e0b313567cfc0b2ff"
PUBLICATION = (
    "stage34b5_publication_resume_20260923T131137Z_0e3f6851c19f4cc28f4fa451e425ce4f"
)
PUBLICATION_SHA = "d30d6ff6d6e532548dbd64f446cdaaf8a9115abaa91b1a3dd5663ee5c081122c"
SEEDS = {"2": 2026051942, "3": 2026083042}
ALLOWED_FILES = (
    "tools/stage34c_namd_r2r3_pilots.py",
    "tests/test_stage34c_namd_r2r3_pilots.py",
    "docs/stage34c_namd_three_replica.md",
)
LIMITATIONS = (
    "Only WT NaPi2b / 2SS / PMm replicas 2 and 3, source frames 0..4.\n"
    "Replica 1 is accepted historical evidence; no new replica-1 science.\n"
    "Variant C is the specified external protocol; scientific PBC remains unresolved.\n"
    "No internal MIC, NoJump, Stage 29, Stage 31, Stage 33 or Stage 35 execution.\n"
    "No full 100-ns analysis. No group availability manifest or release decision.\n"
    "RMSD evidence needs separate human review for each new replica.\n"
    "NAMD 2.14 (r1) versus 3.0.3 (r2/r3) requires later scientific review.\n"
    "Different seeds do not prove statistical independence; starting state is shared.\n"
    "DCD has no atom labels: correspondence uses reviewed source linkage and PSF.\n"
    "Raw DCD binding uses intake stat/header/config/log evidence, not a full hash.\n"
    "Prepared trajectories remain outside the ZIP with exact SHA256 and size.\n"
)


def read(path):
    return json.loads(path.read_text())


def new_replica(replica):
    require(replica in SEEDS, "Only new replicas 2 and 3 are authorized")
    return replica


def source_paths(root, replica):
    new_replica(replica)
    base = root / "namd/egor_2ss_r1/raw"
    label = f"MD_2_bonds_W_I_PMm_100_ns_{replica}"
    return {
        suffix: base / f"{label}.{suffix}" for suffix in ("dcd", "conf", "out", "xsc")
    }


def fortran_record(stream, endian, expected=None):
    prefix = stream.read(4)
    require(len(prefix) == 4, "Truncated record marker")
    size = struct.unpack(endian + "i", prefix)[0]
    require(0 <= size <= 10_000_000, "Unsupported record size")
    require(expected is None or size == expected, "Unexpected record length")
    data = stream.read(size)
    require(len(data) == size and stream.read(4) == prefix, "Invalid Fortran record")
    return data


def dcd_header(path):
    """Intake fixed-record parser: metadata only, no hidden initialization read."""
    with path.open("rb") as stream:
        prefix = stream.read(4)
        require(len(prefix) == 4, "Truncated DCD")
        endian = "<" if struct.unpack("<i", prefix)[0] == 84 else ">"
        stream.seek(0)
        control = fortran_record(stream, endian, 84)
        require(control[:4] == b"CORD", "Not a coordinate DCD")
        ints = struct.unpack(endian + "20i", control[4:])
        require(
            ints[8] == 0 and ints[19] != 0 and ints[11] == 0 and ints[10] == 1,
            "Only reviewed fixed-size NAMD 3-D DCD with boxes is supported",
        )
        title = fortran_record(stream, endian)
        count = struct.unpack(endian + "i", title[:4])[0]
        require(len(title) == 4 + count * 80, "Malformed DCD title")
        atoms = struct.unpack(endian + "i", fortran_record(stream, endian, 4))[0]
        offset = stream.tell()
    require(atoms > 0 and ints[2] > 0, "Invalid DCD atom/frequency metadata")
    frame_bytes = 3 * (4 * atoms + 8) + 56
    payload = path.stat().st_size - offset
    require(payload == ints[0] * frame_bytes, "DCD header/size frame count differs")
    delta = struct.unpack(endian + "f", control[40:44])[0]
    return dict(
        path=str(path.resolve()),
        size_bytes=path.stat().st_size,
        endian=endian,
        frame_count=ints[0],
        atom_count=atoms,
        istart=ints[1],
        nsavc=ints[2],
        delta=delta,
        unit_cell=True,
        remarks=title[4:].decode("ascii").replace("\0", ""),
        header_bytes=offset,
        frame_bytes=frame_bytes,
        raw_reader_dt_ps=units.convert(delta, "AKMA", "ps") * ints[2],
    )


def bind_sources(root, replica, intake):
    paths = source_paths(root, replica)
    accepted = read(intake / "per_replica_time_authority_check.json")[replica]
    rows = b3.csv_rows(intake / "replica_input_bindings.csv")
    row = next(r for r in rows if r["replica_id"] == replica)
    for role, key in (
        ("conf", "configuration"),
        ("out", "production_log"),
        ("xsc", "final_xsc"),
    ):
        require(
            paths[role].resolve() == (root.parent / row[f"{key}_path"]).resolve(),
            f"Wrong replica {replica} {role} path",
        )
        b3.require_hash(paths[role], row[f"{key}_sha256"], role)
    header = dcd_header(paths["dcd"])
    require(
        all(accepted["dcd"][k] == v for k, v in header.items()),
        "DCD binding differs from accepted intake",
    )
    stat = paths["dcd"].stat()
    old = next(
        r
        for r in read(intake / "input_inventory_before.json")
        if r["path"] == str(paths["dcd"].relative_to(root.parent))
    )
    require(
        all(
            old[k] == v
            for k, v in dict(
                size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, inode=stat.st_ino
            ).items()
        ),
        "Source DCD stat binding differs from intake",
    )
    derived = derive_time(paths["conf"], paths["out"], header["frame_count"])
    require(
        all(
            list(v) == accepted[k] if isinstance(v, tuple) else v == accepted[k]
            for k, v in derived.items()
        ),
        "Independent time differs from intake",
    )
    require(
        header["frame_count"] == 1000 and header["atom_count"] == 439436,
        "Unexpected source population",
    )
    text, config = paths["out"].read_text(), paths["conf"].read_text()
    require(
        re.search(r"^Info:\s+NAMD 3\.0\.3\b", text, re.M) is not None,
        "Wrong producer version",
    )
    require(
        re.findall(r"^\s*seed\s+(\d+)\s*$", config, re.M) == [str(SEEDS[replica])],
        "Wrong replica seed",
    )
    require(
        re.findall(r"^Info:\s+RANDOM NUMBER SEED\s+(\d+)\s*$", text, re.M)
        == [str(SEEDS[replica])],
        "Config/log seed differs",
    )
    raw_times = tuple(
        RawFrameTime(
            frame=i,
            time_ps=(i + header["istart"] / header["nsavc"])
            * header["raw_reader_dt_ps"],
        )
        for i in FRAMES
    )
    dcd = DCDIdentity(
        **{
            k: header[k]
            for k in (
                "path",
                "size_bytes",
                "atom_count",
                "frame_count",
                "istart",
                "nsavc",
                "delta",
                "unit_cell",
                "remarks",
            )
        },
        dt_ps=header["raw_reader_dt_ps"],
        observed_times=raw_times,
    )
    control = TimeControl(
        schema_version="mania.namd_time_authority.v1",
        engine="NAMD",
        config=source_identity(paths["conf"]),
        log=source_identity(paths["out"]),
        dcd=dcd,
        **derived,
        derivation="config_log_step_times_timestep_fs_divided_by_1000",
        status="validated",
    )
    validate_replica_time(control, paths["dcd"], replica)
    return paths, header, control


def validate_replica_time(control, dcd, replica):
    new_replica(replica)
    label = f"MD_2_bonds_W_I_PMm_100_ns_{replica}"
    require(
        Path(control.config.path).name == label + ".conf"
        and Path(control.log.path).name == label + ".out"
        and Path(control.dcd.path).name == label + ".dcd"
        and dcd.name == label + ".dcd",
        "Wrong-replica time control",
    )
    times = b3.validate_time(control, dcd)
    require(times[:5] == TIMES_PS and len(times) == 1000, "Wrong scientific time axis")
    b3.sampling_contract(times[:5])


def read_selected(header, control, intake, replica, work):
    frames, records = [], []
    expected = read(intake / "selected_frame_box_readiness.json")["replicas"][replica]
    with Path(header["path"]).open("rb") as stream:
        for index in FRAMES:
            offset = header["header_bytes"] + index * header["frame_bytes"]
            stream.seek(offset)
            cell_bytes = fortran_record(stream, header["endian"], 48)
            cell = np.frombuffer(cell_bytes, dtype=header["endian"] + "f8")
            columns = [
                fortran_record(stream, header["endian"], 4 * header["atom_count"])
                for _ in range(3)
            ]
            require(
                stream.tell() == offset + header["frame_bytes"], "Frame size differs"
            )
            coordinates = np.column_stack(
                [np.frombuffer(c, dtype=header["endian"] + "f4") for c in columns]
            )
            box = cell[[0, 2, 5, 4, 3, 1]].copy()
            require(np.all(box[3:] == 0), "Unreviewed nonorthogonal cell")
            box[3:] = 90
            require(
                box.tolist() == expected["frames"][index]["box_A_degrees"],
                "Selected-frame box differs from intake",
            )
            box = b3.pbc.validate_box(box.astype(np.float32))
            require(np.isfinite(coordinates).all(), "Nonfinite source coordinates")
            require(
                float(control.scientific_times_ps[index]) == TIMES_PS[index],
                "Wrong selected scientific time",
            )
            frames.append((coordinates, box, TIMES_PS[index]))
            records.append(
                {
                    **b3.frame_map()[index],
                    "atom_count": len(coordinates),
                    "raw_dcd_time_ps": control.dcd.observed_times[index].time_ps,
                    "box": box.tolist(),
                    "finite_coordinates": True,
                    "selected_payload_sha256": hashlib.sha256(
                        cell_bytes + b"".join(columns)
                    ).hexdigest(),
                }
            )
    dump(
        work / "selected_frames.json",
        dict(
            frames=records,
            source_coordinate_read_indexes=list(FRAMES),
            initialization_reads=[],
            indexing_scans=[],
            neighboring_source_frames_read=False,
            raw_time_method="Installed DCDReader formula; no rounding or DCD reader",
        ),
    )
    return frames


def shared_authority(root, intake, work):
    accepted = read(intake / "input_compatibility.json")
    psf = root / "namd/egor_2ss_r1/raw/MD_2_bonds_NPT_W_I_PMm_100_ns.psf"
    elements_path = root / b3.AUTHORITY_DIRECTORY / "namd_atom_type_elements.json"
    mapping_path = root / b3.MAPPING_DIRECTORY / "namd_canonical_mapping.json"
    binding_path = mapping_path.with_name("psf_binding.json")
    for path, sha in (
        (psf, b3.PSF_SHA256),
        (elements_path, b3.ELEMENT_SHA256),
        (mapping_path, b3.MAPPING_SHA256),
        (binding_path, accepted["canonical_mapping"]["binding"]["sha256"]),
    ):
        b3.require_hash(path, sha, path.name)
    elements = b3.read_control(elements_path, b3.ElementControl)
    lookup = b3.validate_elements(elements, psf)
    require(
        len(lookup) == 97 and sum(elements.used_type_counts.values()) == 439436,
        "Incomplete element authority",
    )
    u = mda.Universe(str(psf), to_guess=())
    b3.attach_elements(u, lookup)
    require(
        (len(u.atoms), len(u.bonds), len(u.residues), len(u.segments))
        == (439436, 439176, 113292, 22),
        "Shared topology population differs",
    )
    rows = b3.mapping_authority.extract_protein(u)
    require(rows == accepted["ordered_protein_residues"], "Protein identity differs")
    mapping, binding = (
        b3.read_canonical_residue_mapping(mapping_path),
        read(binding_path),
    )
    b3.mapping_authority.check_binding(psf, rows, binding)
    check = b3.mapping_authority.verify_records(
        mapping, rows, b3.load_default_napi2b_canonical_reference()
    )
    independent = b3.mapping_authority.independent_check(psf, mapping_path, binding)
    require(len(rows) == len(mapping.mappings) == 690, "Incomplete mapping")
    authority = dict(
        status="PASS",
        psf=file_record(psf),
        elements=file_record(elements_path),
        mapping=file_record(mapping_path),
        used_types_covered=len(lookup),
        atoms_covered=len(u.atoms),
        unresolved_elements=0,
        conflicting_elements=0,
        mapping_validation=check,
        independent_mapping_validation=independent,
        required_source_keys=[r.source_key for r in mapping.mappings],
    )
    dump(work / "shared_authority.json", authority)
    return u, psf, lookup, mapping_path, mapping, authority


def pilot_manifest(replica, psf, prepared, mapping_path, work):
    new_replica(replica)
    payload = b3.manifest_payload_original(psf, prepared, mapping_path, work)
    condition = payload["conditions"][0]
    identity = condition["dataset_spec"]["identity"]
    identity.update(
        dataset_id="napi2b-stage34b-pilot",
        replica_id=replica,
        trajectory_id=f"egor-2ss-r{replica}-five-frames",
        condition=None,
    )
    condition["metadata"].update(
        replica=replica,
        purpose="Stage 34.C.1 protein-only five-frame pilot; pending human review",
    )
    return payload


# Preserve the accepted factory while a scoped replacement supplies new identities.
b3.manifest_payload_original = b3.manifest_payload


def run_protein(replica, psf, prepared, lookup, control, mapping_path, work, timings):
    validate_replica_time(control, Path(control.dcd.path), replica)
    b3.require_representation(read(work / "variant_c_pbc_diagnostic.json")["frames"])
    b3.require_representation(read(work / "persisted_pbc_validation.json")["frames"])
    identity = read(work / "prepared_trajectory_identity.json")
    require(all(r["passed"] for r in identity["frames"]), "Persisted integrity failed")
    require(
        file_record(prepared)
        == {k: identity[k] for k in ("path", "size_bytes", "sha256")},
        "Prepared binding changed",
    )
    require(not (work / "science_started.json").exists(), "Scientific rerun forbidden")
    dump(work / "science_started.json", {"replica_id": replica, "prepared": identity})

    def manifest(*args):
        return pilot_manifest(replica, *args)

    with b3.replace_attribute(b3, "manifest_payload", manifest):
        return b3.run_mania(psf, prepared, lookup, control, mapping_path, work, timings)


def freeze_science(work, mapping_path, elements_path):
    roles = {
        "protein_edge": work / "output/protein_edges_by_window_canonical.csv",
        "protein_source": work / "output/protein_edges_by_window_source.csv",
        "temporal": work / "output/temporal_execution.json",
        "validation": work / "technical_validation.json",
        "authority": work / "authority.json",
        "identity": work / "prepared_trajectory_identity.json",
        "pbc": work / "persisted_pbc_validation.json",
        "mapping": mapping_path,
        "elements": elements_path,
        "time": work / "namd_time_authority.json",
        "per_frame": work / "mania_contact_result.json",
        "independent": work / "science_check.json",
        "selected": work / "selected_frames.json",
    }
    frozen = work / "frozen"
    frozen.mkdir()
    records = {
        role: qc.freeze_file(path, frozen / path.name) for role, path in roles.items()
    }
    dump(work / "frozen_science.json", records)
    return records


def validate_freeze(work, records):
    require(records == read(work / "frozen_science.json"), "Frozen ledger changed")
    for role, item in records.items():
        b3.require_hash(Path(item["path"]), item["sha256"], role)
        frozen = work / item["frozen_path"]
        require(frozen.stat().st_size == item["size_bytes"], "Frozen size differs")
        b3.require_hash(frozen, item["sha256"], role)


def hard_qc(work, records, replica):
    validate_freeze(work, records)

    def path(role):
        return work / records[role]["frozen_path"]

    def ev(role, **kwargs):
        return qc.evidence(role, records, **kwargs)

    authority, identity = read(path("authority")), read(path("identity"))
    require(authority["replica_id"] == new_replica(replica), "Wrong QC replica")
    b3.require_hash(Path(identity["path"]), identity["sha256"], "prepared QC")
    require(
        all(
            r["passed"] and r["checks"]["pointwise_atom_order"]
            for r in identity["frames"]
        ),
        "QC lacks persisted identity evidence",
    )
    b3.require_representation(read(path("pbc"))["frames"])
    validation = read(path("validation"))
    require(
        validation["complete"] and validation["status"] == "passed",
        "QC requires complete real technical validation",
    )
    temporal = qc.read_preprocessing_temporal_execution(path("temporal"))
    require(len(temporal.bindings) == 1, "QC temporal population differs")
    binding = temporal.bindings[0]
    require(binding.dataset_spec.identity.replica_id == replica, "QC identity differs")
    require(
        binding.sampling_plan == b3.sampling_contract()[1],
        "QC pilot sample count differs",
    )
    protein = qc.canonical_io.read_canonical_protein_edge_window_csv(
        path("protein_edge")
    )
    mapping = b3.read_canonical_residue_mapping(path("mapping"))
    keys = tuple(tuple(r) for r in authority["shared"]["required_source_keys"])
    require(set(keys) == {r.source_key for r in mapping.mappings}, "QC mapping differs")
    value = qc.ReplicaHardQCEvidence(
        binding.dataset_spec.identity,
        qc.ReplicaRawIntegrityEvidence(
            True,
            True,
            authority["shared"]["atoms_covered"],
            read(path("selected"))["frames"][0]["atom_count"],
            True,
            f"accepted_psf_replica{replica}_five_frames",
            ev("authority"),
            ev("identity"),
            ev(
                "identity",
                detail="Pointwise prepared writer/reader order; unchanged PSF. "
                "Trajectory has no independent atom labels.",
            ),
        ),
        qc.DatasetCanonicalResidueMappingBinding(
            *binding.dataset_spec.identity.replica_key, mapping
        ),
        keys,
        qc.ReplicaProteinPBCEvidence(
            False,
            ev(
                "pbc",
                kind="pbc",
                detail="Five frames: zero substantive bond/protein disagreements; "
                "scientific PBC status remains unresolved.",
            ),
        ),
        binding.sampling_plan,
        tuple(
            qc.RequiredMetadataEvidence(role, True, ev(role))
            for role in ("authority", "elements", "mapping", "time")
        ),
        (
            qc.RequiredArtifactEvidence(
                "protein_edge", True, True, ev("protein_edge"), "protein_edge", protein
            ),
            *(
                qc.RequiredArtifactEvidence(role, True, True, ev(role))
                for role in ("protein_source", "temporal", "validation", "independent")
            ),
        ),
    )
    hard = qc.hard_findings(value, work / "stage32_hard_evidence.json")
    dump(work / "stage32_hard_qc.json", hard.to_dict())
    require(hard.hard_qc_status == "pass", "Hard QC failed; no pending-pass claim")
    partial = qc.partial_review_observations(
        binding.dataset_spec.identity, protein, temporal, records
    )
    dump(work / "stage32_partial_review.json", partial)
    pending = qc.pending_decision(hard)
    dump(work / "stage32_pending_review.json", pending)
    validate_freeze(work, records)
    return hard, partial, pending


def rmsd_evidence(replica, psf, prepared, work, head):
    new_replica(replica)
    identity = read(work / "authority.json")
    require(identity["replica_id"] == replica, "RMSD authority replica differs")
    prepared_identity = read(work / "prepared_trajectory_identity.json")
    b3.require_hash(prepared, prepared_identity["sha256"], "RMSD prepared")
    u = mda.Universe(str(psf), str(prepared), to_guess=())
    try:
        atoms = u.select_atoms(rmsd.SELECTION)
        require(
            len(atoms) == len(atoms.residues) == 690, "RMSD requires 690 protein CA"
        )
        require(len(u.trajectory) == 5, "RMSD requires exactly five prepared frames")
        coordinates, technical = [], []
        for i in FRAMES:
            ts = u.trajectory[i]
            require(ts.time == TIMES_PS[i], "RMSD time differs")
            coordinates.append(atoms.positions.astype(np.float64))
            technical.append(
                dict(frame=i, time_ps=float(ts.time), box=ts.dimensions.tolist())
            )
        selected = [b3.input_authority.atom_record(a) for a in atoms]
    finally:
        u.trajectory.close()
    runs, repeat_delta = rmsd.calculate_twice(np.asarray(coordinates))
    rows = [
        dict(
            replica_id=replica,
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            scientific_time_ns=rmsd.TIMES_NS[i],
            rmsd_A=value,
        )
        for i, value in enumerate(runs[0])
    ]
    with (work / "rmsd_evidence.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(9, 5), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.plot(rmsd.TIMES_NS, runs[0], marker="o")
    ax.set(
        xlabel="Scientific time, ns",
        ylabel="Aligned C-alpha RMSD, angstrom",
        xticks=rmsd.TIMES_NS,
        title=f"WT NaPi2b / 2SS / PMm / replica {replica}",
    )
    fig.supxlabel(
        "Reference: this replica's prepared frame 0 (0.1 ns); human review pending"
    )
    fig.savefig(work / "rmsd_evidence.png", dpi=180)
    method = dict(
        replica_id=replica,
        reference_replica_id=replica,
        selection=rmsd.SELECTION,
        n_atoms_used=len(selected),
        n_residues=690,
        reference_prepared_frame_index=0,
        reference_scientific_time_ns=0.1,
        alignment="equal-weight Kabsch proper rotation; same CA fit and measurement",
        rmsd_unit="angstrom",
        method_status="documented_review_fallback",
        implementation={**file_record(Path(rmsd.__file__)), "function": "aligned_rmsd"},
        psf=file_record(psf),
        prepared_trajectory=file_record(prepared),
        selected_atoms=selected,
        frames=technical,
        source_frame_map=b3.frame_map(),
        rmsd_values_A=runs[0],
        maximum_repeat_difference_A=repeat_delta,
        git_sha=head,
        versions={
            n: importlib.metadata.version(n)
            for n in ("mania-wania", "MDAnalysis", "numpy", "matplotlib")
        },
        manual_review_status="pending_review",
        threshold=None,
        statements=["No drift decision made", "No reviewer supplied"],
        scientific_pbc_status="unresolved",
        internal_mic=False,
    )
    dump(work / "rmsd_method.json", method)
    return method


def historical_binding(root, work):
    publication = root / PUBLICATION
    b3.require_hash(
        publication.with_suffix(".zip"), PUBLICATION_SHA, "accepted publication"
    )
    with zipfile.ZipFile(publication.with_suffix(".zip")) as archive:
        require(archive.testzip() is None, "Historical archive CRC differs")
        for name in (
            "accepted_evidence_links.json",
            "stage34b5_publication_resume_summary.json",
        ):
            require(
                archive.read(name) == (publication / name).read_bytes(),
                "Historical publication evidence differs",
            )
    links = read(publication / "accepted_evidence_links.json")
    prior = Path(links["b3"]["directory"])
    b3.require_hash(
        Path(links["b3"]["archive"]["path"]),
        links["b3"]["archive"]["sha256"],
        "accepted r1 B3",
    )
    names = (
        "source_input_observations.json",
        "accepted_authority_bindings.json",
        "prepared_trajectory_identity.json",
        "protein_per_frame_independent_check.json",
        "protein_window_independent_check.json",
        "canonicalization_check.json",
    )
    with zipfile.ZipFile(Path(links["b3"]["archive"]["path"])) as archive:
        require(archive.testzip() is None, "Historical B3 CRC differs")
        for name in names:
            require(
                archive.read(name) == (prior / name).read_bytes(),
                "Historical B3 evidence differs",
            )
    source = read(prior / names[0])
    controls = read(prior / "accepted_authority_bindings.json")
    for role in ("psf", "elements", "time", "mapping"):
        require(
            file_record(Path(controls[role]["path"])) == controls[role],
            "Accepted r1 control binding differs",
        )
    for role in ("psf", "config", "log"):
        require(
            file_record(Path(source[role]["path"])) == source[role],
            "Accepted r1 source binding differs",
        )
    h = dcd_header(Path(source["dcd"]["path"]))
    require(
        all(
            h[k] == source["dcd"][k]
            for k in (
                "path",
                "size_bytes",
                "atom_count",
                "frame_count",
                "istart",
                "nsavc",
                "delta",
                "unit_cell",
                "remarks",
            )
        ),
        "Accepted r1 DCD binding differs",
    )
    prepared = read(prior / "prepared_trajectory_identity.json")
    b3.require_hash(Path(prepared["path"]), prepared["sha256"], "accepted r1 prepared")
    result = dict(
        status="accepted_historical",
        publication_archive=file_record(publication.with_suffix(".zip")),
        b3_archive=links["b3"]["archive"],
        publication_summary=read(
            publication / "stage34b5_publication_resume_summary.json"
        ),
        source=source,
        observations=read(prior / names[3]),
        window=read(prior / names[4]),
        canonical=read(prior / names[5]),
        newly_read_coordinates=0,
        newly_run_science=False,
        producer="NAMD 2.14",
        seed=2026040842,
    )
    dump(work / "accepted_r1_binding.json", result)
    return result


def checkpoint(repo, work):
    commands = [
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
        ["git", "rev-parse", "develop"],
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        ["git", "log", "--oneline", "--decorate", "-32"],
    ]
    results = []
    for argv in commands:
        cp = subprocess.run(argv, cwd=repo, text=True, capture_output=True, check=True)
        results.append(
            dict(
                argv=argv, returncode=cp.returncode, stdout=cp.stdout, stderr=cp.stderr
            )
        )
    require(results[0]["stdout"].strip() == "FAIR", "Branch FAIR required")
    require(
        all(line[3:] in ALLOWED_FILES for line in results[2]["stdout"].splitlines()),
        "Unexpected working-tree changes",
    )
    for name in ("tools/stage34b5_publication_resume.py",):
        blob = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=repo)
        require(blob == (repo / name).read_bytes(), "Accepted checkpoint not committed")
    dump(work / "repository_checkpoint.json", results)
    dump(work / "commands.json", results)
    return results[1]["stdout"].strip()


def run_replica(root, work, replica, head):
    work.mkdir()
    started, timings = time.perf_counter(), {}
    result = dict(replica_id=replica, status="BLOCKED", mania_executed=False)
    try:
        with b3.timed(timings, "authority_readiness_seconds"):
            intake = root / INTAKE
            paths, header, control = bind_sources(root, replica, intake)
            u, psf, lookup, mapping_path, mapping, shared = shared_authority(
                root, intake, work
            )
            write_control(work / "namd_time_authority.json", control)
            authority = dict(
                replica_id=replica,
                status="PASS",
                producer="NAMD 3.0.3",
                seed=SEEDS[replica],
                shared=shared,
                source_header=header,
                time_control=file_record(work / "namd_time_authority.json"),
                config=file_record(paths["conf"]),
                log=file_record(paths["out"]),
                final_xsc=file_record(paths["xsc"]),
                intake=file_record(intake / "per_replica_time_authority_check.json"),
            )
            dump(work / "authority.json", authority)
            frames = read_selected(header, control, intake, replica, work)
            _, samples, windows = b3.sampling_contract()
            dump(
                work / "stage27_sampling_result.json",
                dict(
                    status="PASS",
                    sampling_plan=samples.to_dict(),
                    window_plan=windows.to_dict(),
                ),
            )
            u.load_new(frames[0][0][None, :, :].copy(), format=MemoryReader)
            context = b3.bond_context(u, b3.input_authority.topology_features(u))
        with b3.timed(timings, "pbc_diagnostic_seconds"):
            diagnostic, prepared_frames = b3.diagnose(u, context, frames)
            dump(work / "variant_c_pbc_diagnostic.json", diagnostic)
            b3.require_representation(diagnostic["frames"])
        with b3.timed(timings, "prepared_persistence_validation_seconds"):
            prepared = b3.persist(
                psf, lookup, u, context, frames, prepared_frames, work
            )
        del u, context, frames, prepared_frames
        dump(
            work / "pbc_audit.json",
            dict(
                replica_id=replica,
                external_preparation="specified Variant C",
                scientific_pbc_status="unresolved",
                MANIA_internal_MIC=False,
            ),
        )
        with b3.timed(timings, "mania_stage27_28_seconds"):
            loaded = run_protein(
                replica, psf, prepared, lookup, control, mapping_path, work, timings
            )
        result["mania_executed"] = True
        with b3.timed(timings, "independent_checker_seconds"):
            per_frame, window, canonical = b3.check_independent(
                psf, prepared, lookup, mapping, work
            )
            dump(
                work / "science_check.json",
                dict(
                    status="PASS",
                    per_frame=per_frame,
                    window=window,
                    canonical=canonical,
                ),
            )
        with b3.timed(timings, "canonicalization_validation_seconds"):
            b3.technical_validation(loaded, mapping_path, work)
        records = freeze_science(
            work,
            mapping_path,
            root / b3.AUTHORITY_DIRECTORY / "namd_atom_type_elements.json",
        )
        with b3.timed(timings, "hard_qc_seconds"):
            hard, partial, pending = hard_qc(work, records, replica)
        with b3.timed(timings, "rmsd_evidence_seconds"):
            method = rmsd_evidence(replica, psf, prepared, work, head)
        validate_freeze(work, records)
        result.update(
            status="PASS",
            producer=authority["producer"],
            seed=SEEDS[replica],
            stage27=dict(requested=5, resolved=5, missing=0, coverage=1.0),
            source_frames=list(FRAMES),
            scientific_times_ps=list(TIMES_PS),
            prepared=read(work / "prepared_trajectory_identity.json"),
            per_frame_counts=[r["contacts"] for r in per_frame["counts"]],
            total_observations=sum(r["contacts"] for r in per_frame["counts"]),
            source_rows=window["source_rows"],
            canonical_rows=canonical["canonical_rows"],
            independent=read(work / "science_check.json"),
            hard_qc_status=hard.hard_qc_status,
            hard_qc_check_totals=dict(Counter(c.status for c in hard.checks)),
            partial_review=partial,
            rmsd_values_A=method["rmsd_values_A"],
            manual_review=pending,
            production_ready=False,
        )
    except Exception as exc:
        result.update(status="BLOCKED", blocker=str(exc))
        (work / "failure.log").write_text(traceback.format_exc())
        print(f"Replica {replica} STOP: {exc}", flush=True)
    finally:
        timings["total_replica_seconds"] = time.perf_counter() - started
        dump(work / "timings.json", timings)
        dump(work / "summary.json", result)
    return result


def package(work):
    archive = work.with_suffix(".zip")
    require(not archive.exists(), "Refusing to overwrite archive")
    files = [
        p
        for p in sorted(work.rglob("*"))
        if p.is_file()
        and p.suffix in {".json", ".csv", ".txt", ".md", ".log", ".py", ".png"}
        and p.name not in {"evidence_inventory.json", "archive_integrity.json"}
    ]
    inventory = [{**file_record(p), "path": str(p.relative_to(work))} for p in files]
    dump(
        work / "evidence_inventory.json",
        dict(
            files=inventory,
            excluded="Raw inputs, prepared XTC, caches, wheels; no self-inventory",
        ),
    )
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
        for path in [*files, work / "evidence_inventory.json"]:
            stream.write(path, path.relative_to(work))
    with zipfile.ZipFile(archive) as stream:
        require(stream.testzip() is None, "Archive CRC failed")
        for row in inventory:
            data = stream.read(row["path"])
            require(
                hashlib.sha256(data).hexdigest() == row["sha256"]
                and len(data) == row["size_bytes"],
                "Archive inventory differs",
            )
    dump(
        work / "archive_integrity.json",
        dict(status="PASS", archive=file_record(archive), file_count=len(files) + 1),
    )
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("local_md"))
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    work = args.workspace or root / (
        "stage34c_r2r3_pilots_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_")
        + uuid4().hex
    )
    work = work.resolve()
    work.mkdir(exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    started = time.perf_counter()
    summary = dict(
        status="BLOCKED",
        stage31_executed=False,
        stage33_executed=False,
        stage29_executed=False,
        full_100ns_analysis=False,
        replica1_rerun=False,
    )
    try:
        head = checkpoint(repo, work)
        summary["starting_head"] = head
        require(
            subprocess.run(
                ["git", "check-ignore", "-q", str(work)], cwd=repo
            ).returncode
            == 0,
            "Evidence workspace must be ignored",
        )
        intake = root / INTAKE
        b3.require_hash(intake.with_suffix(".zip"), INTAKE_SHA, "accepted intake")
        with zipfile.ZipFile(intake.with_suffix(".zip")) as archive:
            require(archive.testzip() is None, "Intake archive CRC differs")
            for name in (
                "per_replica_time_authority_check.json",
                "replica_input_bindings.csv",
                "input_inventory_before.json",
                "input_compatibility.json",
                "selected_frame_box_readiness.json",
            ):
                require(
                    archive.read(name) == (intake / name).read_bytes(),
                    "Intake evidence differs from accepted archive",
                )
        historical = historical_binding(root, work)
        results = [run_replica(root, work / f"replica{r}", r, head) for r in ("2", "3")]
        summary.update(
            replicas=results,
            status="PASS" if all(r["status"] == "PASS" for r in results) else "BLOCKED",
        )
        dump(
            work / "three_replica_readiness.json",
            {"1": historical, **{r["replica_id"]: r for r in results}},
        )
        for replica in ("2", "3"):
            for source, target in (
                ("authority.json", "authority.json"),
                ("variant_c_pbc_diagnostic.json", "pbc_diagnostic.json"),
                ("prepared_trajectory_identity.json", "prepared_identity.json"),
                ("science_check.json", "science_check.json"),
                ("stage32_hard_qc.json", "stage32_hard_qc.json"),
                ("rmsd_evidence.csv", "rmsd_evidence.csv"),
                ("rmsd_evidence.png", "rmsd_evidence.png"),
                ("rmsd_method.json", "rmsd_method.json"),
            ):
                path = work / f"replica{replica}" / source
                if path.exists():
                    shutil.copyfile(path, work / f"replica{replica}_{target}")
    except Exception as exc:
        summary["blocker"] = str(exc)
        (work / "failure.log").write_text(traceback.format_exc())
    finally:
        summary["current_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        dump(work / "stage34c_r2r3_summary.json", summary)
        dump(
            work / "timings.json",
            dict(
                total_new_execution_seconds=time.perf_counter() - started,
                replicas={
                    r: read(work / f"replica{r}/timings.json")
                    for r in ("2", "3")
                    if (work / f"replica{r}/timings.json").exists()
                },
            ),
        )
        (work / "warnings_limitations.txt").write_text(LIMITATIONS)
        print(f"EVIDENCE DIRECTORY: {work}", flush=True)
        print(
            f"Stage 34.C.1 {summary['status']}; verification/package pending",
            flush=True,
        )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
