#!/usr/bin/env python3
"""Stage 34.B.2: exact WT PSF mapping authority, without scientific execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from mania.canonical_reference_io import (
    load_default_napi2b_canonical_reference,
    read_canonical_reference,
)
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
    validate_canonical_residue_mapping_table,
)
from mania.canonical_residue_mapping_io import (
    read_canonical_residue_mapping,
    write_canonical_residue_mapping,
)
from mania.preprocessing.namd_authority import (
    ElementControl,
    TimeControl,
    read_control,
    source_identity,
)

IDENTITY_FIELDS = (
    "source_segment",
    "source_resid",
    "source_resname",
    "source_topology_residue_index",
    "source_sequence_position",
)
AUTHORITY = "unique exact full-length ordered WT sequence correspondence"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def file_record(path):
    return source_identity(path).model_dump()


def reference_path():
    return Path(
        str(
            files("mania").joinpath(
                "data", "canonical", "slc34a2_o95436_reference.json"
            )
        )
    )


def ordered_signature(rows):
    return digest(
        json.dumps(
            [[row[key] for key in IDENTITY_FIELDS] for row in rows],
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )


def extract_protein(universe):
    """Use the same protein selection and segment namespace as accepted readiness."""
    return [
        dict(
            zip(
                IDENTITY_FIELDS,
                (
                    str(r.segid),
                    str(r.resid),
                    str(r.resname),
                    int(r.resindex),
                    position,
                ),
                strict=True,
            )
        )
        for position, r in enumerate(universe.select_atoms("protein").residues, 1)
    ]


def sequence_identity(rows, reference):
    # Reuse the earlier real GROMACS mapping policy: only standard names plus
    # HSD/HSE/HSP -> histidine, using the installed MDAnalysis code conversion.
    from MDAnalysis.lib.util import convert_aa_code

    allowed = {r.canonical_resname for r in reference.residues()} | {
        "HSD",
        "HSE",
        "HSP",
    }
    unresolved = [r for r in rows if r["source_resname"] not in allowed]
    sequence = "".join(
        (
            "H"
            if r["source_resname"] in ("HSD", "HSE", "HSP")
            else convert_aa_code(r["source_resname"])
        )
        if r["source_resname"] in allowed
        else "?"
        for r in rows
    )
    mismatches = [
        {"position": i, "source": a, "canonical": b}
        for i, (a, b) in enumerate(zip(sequence, reference.sequence, strict=False), 1)
        if a != b
    ]
    exact = not unresolved and sequence == reference.sequence
    return sequence, {
        "status": "PASS" if exact else "BLOCKED",
        "source_length": len(sequence),
        "canonical_length": reference.sequence_length,
        "source_sequence_sha256": digest(sequence),
        "canonical_sequence_sha256": reference.sequence_sha256,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "ambiguous_count": len(unresolved),
        "unresolved_residues": unresolved,
        "length_difference": len(sequence) - reference.sequence_length,
        "insertion_count": 0 if exact else None,
        "deletion_count": 0 if exact else None,
        "indel_note": "No indels in exact identity; no alignment attempted on failure",
        "unique_one_to_one_placement": exact,
        "placement_proof": "Equal full lengths and every ordered identity equal: "
        "the sole order-preserving bijection is source position i to target i",
        "numeric_resid_authority": False,
        "normalization_policy": "Earlier real GROMACS preflight: standard amino "
        "acids and HSD/HSE/HSP as HIS, sequence comparison only",
    }


def build_mapping(rows, reference):
    require(
        reference == load_default_napi2b_canonical_reference(),
        "Wrong canonical reference identity",
    )
    keys = [(r["source_segment"], r["source_resid"], r["source_resname"]) for r in rows]
    require(len(set(keys)) == len(keys), "Duplicated source residue identity")
    indexes = [r["source_topology_residue_index"] for r in rows]
    require(
        all(type(i) is int and i >= 0 for i in indexes)
        and indexes == sorted(set(indexes)),
        "Invalid ordered topology indexes",
    )
    require(
        [r["source_sequence_position"] for r in rows] == list(range(1, len(rows) + 1)),
        "Missing/reordered source position",
    )
    _, comparison = sequence_identity(rows, reference)
    require(not comparison["ambiguous_count"], "Unresolved source amino-acid identity")
    require(
        len(rows) == reference.sequence_length,
        "Missing source residue or insertion/deletion: full-length WT required",
    )
    require(comparison["status"] == "PASS", "WT sequence mismatch; mapping blocked")
    records = []
    # Residue IDs are never parsed, compared with target positions or offset.
    for position, row in enumerate(rows, 1):
        target = reference.residue_at(position)
        records.append(
            CanonicalResidueMappingRecord(
                "namd",
                row["source_segment"] or None,
                row["source_resid"],
                row["source_resname"],
                position,
                target.canonical_resname,
                "mapped",
            )
        )
    table = CanonicalResidueMappingTable(
        tuple(
            sorted(
                records,
                key=lambda r: (
                    r.source_engine,
                    r.source_chain_id or "",
                    r.source_resid,
                    r.source_resname,
                ),
            )
        )
    )
    return validate_canonical_residue_mapping_table(table, reference=reference)


def verify_records(table, rows, reference):
    validate_canonical_residue_mapping_table(table, reference=reference)
    require(
        len(table.mappings) == len(rows) == reference.sequence_length,
        "Missing or extra mapping record",
    )
    targets = [r.canonical_residue_number for r in table.mappings]
    require(len(set(targets)) == len(targets), "Duplicate canonical mapping record")
    lookup = {r.source_key: r for r in table.mappings}
    for position, row in enumerate(rows, 1):
        key = (
            "namd",
            row["source_segment"] or None,
            row["source_resid"],
            row["source_resname"],
        )
        require(key in lookup, "Missing exact source mapping record")
        record = lookup[key]
        target = reference.residue_at(position)
        require(
            record.mapping_status == "mapped"
            and record.canonical_residue_number == position
            and record.canonical_resname == target.canonical_resname,
            "Mapping differs from ordered sequence correspondence",
        )
    require(
        sequence_identity(rows, reference)[1]["status"] == "PASS",
        "WT sequence mismatch during validation",
    )
    return {
        "status": "PASS",
        "mapping_count": len(targets),
        "canonical_coverage": len(set(targets)),
        "missing": 0,
        "duplicates": 0,
        "source_resnames_preserved": True,
        "strict_read": True,
    }


def check_binding(psf, rows, binding):
    require(file_record(psf) == binding["psf"], "Wrong PSF binding")
    require(
        len(rows) == binding["protein_residue_count"]
        and ordered_signature(rows) == binding["ordered_residue_identity_sha256"],
        "Different ordered residue identity",
    )
    ref = load_default_napi2b_canonical_reference()
    require(
        binding["canonical_reference_id"] == ref.reference_id
        and binding["canonical_sequence_sha256"] == ref.sequence_sha256,
        "Wrong canonical reference identity",
    )
    require(
        sequence_identity(rows, ref)[1]["source_sequence_sha256"]
        == binding["source_sequence_sha256"],
        "Different source sequence binding",
    )


def independent_psf_residues(psf):
    """Second extraction: read PSF NATOM text, without Universe or builder rows."""
    from MDAnalysis.core.selection import ProteinSelection

    rows, previous, topology_index, atom_count = [], None, -1, 0
    with psf.open() as stream:
        for line in stream:
            if "!NATOM" in line:
                count = int(line.split()[0])
                break
        else:
            raise ValueError("PSF has no NATOM section")
        for index in range(count):
            parts = next(stream).split()
            require(
                len(parts) >= 8 and int(parts[0]) == index + 1,
                "Unsupported or malformed PSF atom record",
            )
            segment, resid, name = parts[1:4]
            identity = (segment, resid, name)
            if identity != previous:
                topology_index += 1
                if name in ProteinSelection.prot_res:
                    rows.append(
                        dict(
                            zip(
                                IDENTITY_FIELDS,
                                (
                                    segment,
                                    resid,
                                    name,
                                    topology_index,
                                    len(rows) + 1,
                                ),
                                strict=True,
                            )
                        )
                    )
            if name in ProteinSelection.prot_res:
                atom_count += 1
            previous = identity
    return rows, atom_count


def independent_check(psf, mapping_path, binding):
    from MDAnalysis.lib.util import convert_aa_code

    rows, atom_count = independent_psf_residues(psf)
    check_binding(psf, rows, binding)
    if "mapping_artifact" in binding:
        require(
            file_record(mapping_path) == binding["mapping_artifact"],
            "Different persisted mapping binding",
        )
    require(atom_count == binding["protein_atom_count"], "Protein atom count differs")
    reference = read_canonical_reference(reference_path())
    # Load the packaged bytes anew and compare every identity without using the
    # generator's table, sequence, expected-record dictionary or canonical output.
    require(len(rows) == len(reference.sequence), "Independent length mismatch")
    for row, letter in zip(rows, reference.sequence, strict=True):
        name = row["source_resname"]
        normalized = "HIS" if name in ("HSD", "HSE", "HSP") else name
        require(
            convert_aa_code(normalized) == letter, "Independent amino-acid mismatch"
        )
    table = read_canonical_residue_mapping(mapping_path)
    require(len(table.mappings) == len(rows), "Missing independent mapping record")
    remaining = list(table.mappings)
    for position, row in enumerate(rows, 1):
        matches = [
            r
            for r in remaining
            if r.source_key
            == (
                "namd",
                row["source_segment"] or None,
                row["source_resid"],
                row["source_resname"],
            )
        ]
        require(len(matches) == 1, "Independent source identity is not unique")
        record = matches[0]
        require(
            record.canonical_residue_number == position
            and record.canonical_resname
            == reference.residue_at(position).canonical_resname,
            "Independent persisted mapping correspondence differs",
        )
        remaining.remove(record)
    require(not remaining, "Unexpected independent mapping records")
    return {
        "status": "PASS",
        "checked_records": len(rows),
        "method": "Independent raw PSF NATOM parser and fresh packaged reference",
        "protein_atom_count": atom_count,
        "ordered_residue_identity_sha256": ordered_signature(rows),
    }


def accepted_inputs(directory):
    """Rebind accepted evidence by hashes; do not repeat the element/toppar audit."""
    summary = json.loads((directory / "stage34b_authority_summary.json").read_text())
    require(
        summary["input_authority"] == summary["implementation"] == "PASS",
        "Previous input authority is not accepted",
    )
    controls = []
    for expected in summary["controls"]:
        require(
            file_record(Path(expected["path"])) == expected,
            "Accepted element/time control has changed",
        )
        controls.append(expected)
    elements = read_control(directory / "namd_atom_type_elements.json", ElementControl)
    time = read_control(directory / "namd_time_authority.json", TimeControl)
    require(elements.psf.path == summary["psf"], "Wrong accepted PSF path")
    require(
        file_record(Path(summary["psf"])) == elements.psf.model_dump(),
        "Wrong accepted PSF fingerprint",
    )
    hashes = json.loads((directory / "source_hashes.json").read_text())
    for path, expected in hashes.items():
        require(
            source_identity(Path(path)).sha256 == expected,
            f"Previously accepted source changed: {path}",
        )
    # Header-only access; zero coordinate frames, diagnostics or transformations.
    from MDAnalysis.lib.formats.libdcd import DCDFile

    dcd = Path(time.dcd.path)
    require(dcd.stat().st_size == time.dcd.size_bytes, "DCD size changed")
    with DCDFile(str(dcd)) as reader:
        header = reader.header
        require(len(reader) == time.dcd.frame_count, "DCD frame count changed")
        for key, expected in (
            ("natoms", time.dcd.atom_count),
            ("istart", time.dcd.istart),
            ("nsavc", time.dcd.nsavc),
            ("delta", time.dcd.delta),
            ("is_periodic", time.dcd.unit_cell),
            ("remarks", time.dcd.remarks),
        ):
            require(header[key] == expected, f"DCD header changed: {key}")
    matrix = json.loads((directory / "readiness_acceptance_matrix.json").read_text())
    require(
        all(
            r["status"] == "PASS"
            for r in matrix
            if r["gate"] != "explicit_canonical_mapping"
        ),
        "Previous readiness has another blocker",
    )
    return (
        summary,
        elements,
        controls,
        matrix,
        {
            "status": "PASS",
            "source_hashes_checked": len(hashes),
            "dcd_header_size_revalidated": True,
            "coordinate_frames_read": 0,
            "full_dcd_hash": False,
            "element_toppar_audit_repeated": False,
            "prior_evidence": [
                file_record(directory / name)
                for name in (
                    "stage34b_authority_summary.json",
                    "source_hashes.json",
                    "readiness_acceptance_matrix.json",
                    "box_readiness.json",
                    "topology_feature_readiness.json",
                    "stage27_time_resolution_check.json",
                )
            ],
        },
    )


def feature_check(universe, table, accepted_directory):
    # Use exact previously observed source atoms, never canonical numbers to
    # select source residues. 2SS remains user-declared simulation metadata.
    features = json.loads(
        (accepted_directory / "topology_feature_readiness.json").read_text()
    )
    lookup = {r.source_key: r for r in table.mappings}
    result = {}
    for label, targets in (
        ("C303-C350", (303, 350)),
        ("C322-C328", (322, 328)),
        ("Asn295", (295,)),
        ("Asn308", (308,)),
    ):
        atoms = features["features"][label]
        first, second = (universe.atoms[a["index"]] for a in atoms)
        require(second in first.bonded_atoms, "Accepted topology feature bond missing")
        resolved = []
        for original, target in zip(atoms, targets, strict=False):
            atom = universe.atoms[original["index"]]
            require(
                (str(atom.segid), int(atom.resid), str(atom.resname), str(atom.name))
                == (
                    original["segid"],
                    original["resid"],
                    original["resname"],
                    original["name"],
                ),
                "Accepted feature source identity changed",
            )
            record = lookup[
                ("namd", str(atom.segid) or None, str(atom.resid), str(atom.resname))
            ]
            require(
                record.canonical_residue_number == target
                and record.canonical_resname == ("CYS" if label[0] == "C" else "ASN"),
                "Topology feature maps to unexpected canonical identity",
            )
            resolved.append({"source_atom": original, "mapping": record.to_dict()})
        result[label] = {
            "protein": resolved,
            "bond_verified": True,
            "separate_partner": atoms[1] if label.startswith("Asn") else None,
        }
    return {
        "status": "PASS",
        "mapping_authority": False,
        "features": result,
        "disulfide_state_authority": "user simulation metadata, not mapping",
        "glycan_partners_in_mapping": False,
    }


def package(work):
    archive = work.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(work.iterdir()):
            if path.is_file() and path.suffix in {
                ".json",
                ".csv",
                ".txt",
                ".log",
                ".py",
                ".md",
            }:
                output.write(path, f"{work.name}/{path.name}")
    return archive


def run(authority_directory, work):
    import MDAnalysis as mda

    accepted, elements, controls, matrix, revalidation = accepted_inputs(
        authority_directory
    )
    dump(work / "accepted_input_revalidation.json", revalidation)
    psf = Path(elements.psf.path)
    universe = mda.Universe(str(psf), to_guess=())
    rows = extract_protein(universe)
    reference = load_default_napi2b_canonical_reference()
    sequence, comparison = sequence_identity(rows, reference)
    (work / "source_sequence.txt").write_text(sequence + "\n")
    dump(work / "source_sequence_identity.json", comparison)
    dump(
        work / "canonical_reference_identity.json",
        {
            **{k: v for k, v in reference.to_dict().items() if k != "sequence"},
            "reference_id": reference.reference_id,
            "artifact": file_record(reference_path()),
        },
    )
    # Persist raw identities even when correspondence fails, before building.
    with (work / "source_protein_residues.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=IDENTITY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    binding = {
        "psf": elements.psf.model_dump(),
        "protein_selection": "protein",
        "source_chain_id_semantics": "exact PSF segid",
        "protein_atom_count": len(universe.select_atoms("protein")),
        "protein_residue_count": len(rows),
        "ordered_residue_identity_sha256": ordered_signature(rows),
        "ordered_signature_encoding": "ASCII JSON array of ordered IDENTITY_FIELDS "
        "values; compact separators; no newline; SHA256",
        "ordered_identity_fields": list(IDENTITY_FIELDS),
        "source_sequence_sha256": digest(sequence),
        "sequence_digest_encoding": "ASCII one-letter sequence without newline",
        "canonical_reference_id": reference.reference_id,
        "canonical_sequence_sha256": reference.sequence_sha256,
    }
    dump(work / "psf_binding.json", binding)
    check_binding(psf, rows, binding)
    table = build_mapping(rows, reference)
    path = work / "namd_canonical_mapping.json"
    require(write_canonical_residue_mapping(table, path).passed, "Mapping write failed")
    persisted = read_canonical_residue_mapping(path)
    dump(work / "mapping_validation.json", verify_records(persisted, rows, reference))
    dump(work / "independent_mapping_check.json", independent_check(psf, path, binding))
    dump(
        work / "topology_feature_mapping_check.json",
        feature_check(universe, persisted, authority_directory),
    )
    # Stage 30 JSON stays unchanged. Additional per-record evidence lives in CSV.
    extended = []
    for position, row in enumerate(rows, 1):
        extended.append(
            {
                **row,
                "canonical_residue_number": position,
                "canonical_resname": reference.residue_at(position).canonical_resname,
                "canonical_sequence_position": position,
                "mapping_status": "mapped",
                "mapping_authority": AUTHORITY,
                "mapping_evidence": "source_sequence_identity.json;psf_binding.json",
            }
        )
    with (work / "source_protein_residues.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(extended[0]))
        writer.writeheader()
        writer.writerows(extended)
    binding["mapping_artifact"] = file_record(path)
    dump(work / "psf_binding.json", binding)
    for row in matrix:
        if row["gate"] == "explicit_canonical_mapping":
            row["status"] = "PASS"
        row["evidence_origin"] = (
            "this_mapping_run"
            if row["gate"] == "explicit_canonical_mapping"
            else "accepted_input_evidence"
        )
    dump(work / "readiness_acceptance_matrix.json", matrix)
    return {
        "real_mapping_authority": "PASS",
        "real_input_readiness": "PASS",
        "mapping_implementation": "verification_pending",
        "blockers": [],
        "mapping": file_record(path),
        "psf": binding["psf"],
        "protein_residue_count": len(rows),
        "protein_atom_count": binding["protein_atom_count"],
        "sequence_comparison": comparison,
        "canonical_coverage": len(table.mappings),
        "accepted_controls": controls,
        "input_evidence": str(authority_directory),
        "user_declared_identity": accepted["user_declared_identity"],
        "histidine_source_names": [
            r
            for r in extended
            if r["source_resname"]
            in {
                "HSD",
                "HSE",
                "HSP",
            }
        ],
        "future_pilot_frames": [0, 1, 2, 3, 4],
        "future_pilot_times_ps": [100, 200, 300, 400, 500],
        "future_pilot_command": None,
        "future_pilot_runner_status": (
            "Not implemented by the existing tools; mapping-only scope"
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-evidence", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("local_md"))
    args = parser.parse_args(argv)
    work = args.output_root.resolve() / (
        "stage34b_mapping_"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid.uuid4().hex[:12]
    )
    require(
        subprocess.run(
            ["git", "check-ignore", str(work)], capture_output=True
        ).returncode
        == 0,
        "Evidence must be in an ignored directory",
    )
    work.mkdir(parents=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    summary = {
        "starting_HEAD": head,
        "current_HEAD": head,
        "scientific_pilot_execution": "NOT RUN",
        "scientific_pbc_status": "unresolved",
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
        summary.update(run(args.authority_evidence.resolve(), work))
    except Exception as exc:
        summary.update(
            real_mapping_authority="BLOCKED",
            real_input_readiness="BLOCKED",
            blockers=[f"{type(exc).__name__}: {exc}"],
        )
    dump(work / "stage34b_mapping_summary.json", summary)
    (work / "warnings_limitations.txt").write_text(
        "Mapping authority only; scientific_pbc_status = unresolved.\n"
        "No coordinates read, PBC preparation/diagnostic, contacts, canonical "
        "scientific tables, Stage 31/32/33/35 or network access.\n"
        "Prior box/runtime evidence reused after source/control hash and DCD "
        "header/size checks; no full DCD hash or trajectory traversal.\n"
        "2SS is user-declared; glycan partners remain separate molecular entities.\n"
        "Stage 30 consumer must receive mapping plus PSF binding; "
        "JSON alone has no PSF field.\n"
        "No complete NAMD five-frame runner is currently implemented.\n"
    )
    (work / "git_state.txt").write_text(
        subprocess.check_output(["git", "status", "--short"], text=True)
    )
    (work / "verification.log").write_text(
        "Real mapping validation: "
        + summary["real_mapping_authority"]
        + "\nRepository regression verification pending.\n"
    )
    archive = package(work)
    print(
        json.dumps(
            {**summary, "evidence_directory": str(work), "evidence_zip": str(archive)},
            indent=2,
        )
    )
    return 0 if summary["real_mapping_authority"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
