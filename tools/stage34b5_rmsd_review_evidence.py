#!/usr/bin/env python3
"""Read-only, five-frame RMSD evidence; no QC evaluation or downstream workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np

B3 = "stage34b_namd_real_20260922T163031Z_d5711581c4494dc58936d4b91a334ebd"
B4 = "stage34b4_namd_specialized_20260922T182122Z_f919e15778874c6ca1a794b28609b798"
PREPARED_SHA256 = "3f9ac9353ad0a6c551845d166651a0ade0436ee5b815c297ff45f9dfa3d0b28c"
PSF_SHA256 = "04b7bee588edf61bde25dfded24216ed4e0727d75d1e144356b500ecc89004bb"
FRAMES = (0, 1, 2, 3, 4)
TIMES_NS = (0.1, 0.2, 0.3, 0.4, 0.5)
TIMES_PS = (100.0, 200.0, 300.0, 400.0, 500.0)
SELECTION = "protein and name CA"
IDENTITY = {
    "dataset_id": "napi2b-stage34b-pilot",
    "system_id": "namd-wt-2ss-pmm",
    "trajectory_id": "egor-2ss-r1-five-frames",
    "variant_id": "WT",
    "engine": "namd",
    "condition": None,
    "replica_id": "1",
    "disulfide_state": "2SS",
}
CONTRACT_SOURCES = {
    "docs/dataset_review_qc.md": "RMSD; Real-data evidence policy",
    "docs/dataset_qc_contract.md": "Stage 32.C boundary",
    "src/mania/dataset_review_qc.py": "RMSDDriftAssessment; explicit authority only",
    "tests/test_dataset_review_qc.py": "exact model fields and explicit authority",
}
LIMITATIONS = """Only the NAMD WT NaPi2b / 2SS / PMm replica 1 five-frame pilot,
scientific times 0.1–0.5 ns, is covered. This is not an assessment of the full
100-ns production trajectory. No automatic RMSD threshold applied.
No drift decision made. Human assessment remains pending_review;
production_ready remains false. No authoritative reviewer has been supplied.
scientific_pbc_status remains unresolved; MANIA internal MIC remains false.
No PBC transformation or coordinate/box rewrite is performed.
XTC has no atom identity labels: identity relies on the exact accepted PSF/XTC
hashes and the accepted B.3 pointwise atom-order evidence. Protein residue
identity is also checked against the accepted ordered identity digest.
No DCD coordinates are read; its current size/mtime are protection observations,
not a new full-trajectory content verification. Technical timestamps are separate
from authoritative scientific times. Equal-weight Cα RMSD uses all 690 residues.
Repeat agreement and self-reference checks verify software behavior only;
they are not independent scientific validation or QC criteria.
Stage 31, Stage 33, release validation, C-prep and Stage 35 are NOT RUN.
Raw inputs and prepared trajectory bytes are excluded from the ZIP.
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def file_record(path):
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def require_hash(path, expected):
    record = file_record(path)
    require(record["sha256"] == expected, f"SHA256 binding differs: {path.name}")
    return record


def archived_json(directory, name):
    """Bind consumed evidence to the accepted sibling archive, without extraction."""
    path = directory / name
    content = path.read_bytes()
    with zipfile.ZipFile(directory.with_suffix(".zip")) as archive:
        require(content == archive.read(name), f"Accepted archive differs: {name}")
    return json.loads(content)


def validate_frames(records):
    require(len(records) == 5, "Exactly five accepted frames required")
    for i, record in enumerate(records):
        require(
            record["prepared_frame_index"] == i
            and record["source_dcd_frame_index"] == i
            and record["requested_sample_index"] == i
            and record["authoritative_time_ps"] == TIMES_PS[i],
            "Accepted frame mapping/scientific times differ",
        )


def validate_pending(pending, summary):
    require(
        pending["status"] == "pending_review"
        and pending["production_ready"] is False
        and pending["reviewer"] is None
        and pending["authoritative_release_decision"] is None,
        "Accepted pending-review authority state differs",
    )
    require(
        pending["replica_key"]
        == [
            IDENTITY[k]
            for k in ("dataset_id", "system_id", "trajectory_id", "replica_id")
        ]
        and summary["hard_qc_status"] == "pass"
        and summary["qc_decision_status"] == "pending_review"
        and summary["production_ready"] is False,
        "Accepted B.5 QC binding differs",
    )
    for name in (
        "qc_derived_stage31_manifest",
        "stage31_aggregation",
        "stage33_publication",
    ):
        require(summary[name] == "NOT RUN", "Accepted downstream state differs")


def validate_temporal_binding(temporal, manifest_spec):
    # The serialized execution spec adds schema_version/kind to manifest input.
    require(len(temporal) == 1, "Expected one temporal binding")
    spec = temporal[0]["dataset_spec"]
    require(
        spec["identity"] == manifest_spec["identity"]
        and spec["temporal"] == manifest_spec["temporal"]
        and spec["temporal"]["production_start_ns"] == 0.1
        and spec["temporal"]["production_end_ns"] == 0.5,
        "Time contract differs",
    )


def bind_inputs(b3, b4):
    authority = archived_json(b3, "accepted_authority_bindings.json")
    prepared = archived_json(b3, "prepared_trajectory_identity.json")
    selected = archived_json(b3, "selected_frames.json")["frames"]
    summary = archived_json(b3, "stage34b_real_pilot_summary.json")
    source = archived_json(b3, "source_input_observations.json")
    require(
        summary["stage34b3_status"] == summary["repository_verification"] == "PASS"
        and summary["scientific_pbc_status"] == "unresolved"
        and summary["internal_mic"] is False,
        "Accepted B.3 status differs",
    )
    validate_frames(prepared["frames"])
    validate_frames(selected)
    require(
        all(r["passed"] and all(r["checks"].values()) for r in prepared["frames"]),
        "Accepted atom-order/coordinate evidence incomplete",
    )
    xtc = b3 / "prepared_variant_c.xtc"
    actual = require_hash(xtc, PREPARED_SHA256)
    require(
        all(prepared[k] == v for k, v in actual.items()), "Prepared binding differs"
    )
    for role in ("psf", "elements", "time", "mapping"):
        expected = authority[role]
        require(
            file_record(Path(expected["path"])) == expected, f"{role} binding differs"
        )
    require(authority["psf"]["sha256"] == PSF_SHA256, "Accepted PSF differs")
    require(source["psf"] == authority["psf"], "Source PSF differs")
    time_control = json.loads(Path(authority["time"]["path"]).read_text())
    require(
        tuple(map(float, time_control["scientific_times_ps"][:5])) == TIMES_PS,
        "Authoritative scientific times differ",
    )
    for role in ("config", "log"):
        require(
            file_record(Path(time_control[role]["path"])) == time_control[role],
            f"Time authority {role} differs",
        )
    manifest = archived_json(b3, "pilot_manifest.json")["conditions"][0]
    require(manifest["dataset_spec"]["identity"] == IDENTITY, "System identity differs")
    require(
        manifest["metadata"]["protein"] == "WT NaPi2b"
        and manifest["metadata"]["source_membrane_label"] == "PMm"
        and manifest["topology_path"] == authority["psf"]["path"]
        and manifest["trajectory_paths"] == [str(xtc.resolve())],
        "Pilot source binding differs",
    )
    temporal = archived_json(b3, "output/temporal_execution.json")["bindings"]
    validate_temporal_binding(temporal, manifest["dataset_spec"])
    samples = temporal[0]["sampling_plan"]["selected_samples"]
    require(
        len(samples) == 5
        and all(
            s["source_frame_index"] == i
            and s["requested_sample_index"] == i
            and s["requested_time_ps"] == s["actual_time_ps"] == TIMES_PS[i]
            for i, s in enumerate(samples)
        ),
        "Accepted sampling mapping differs",
    )
    accepted_b4 = archived_json(b4, "accepted_b3_bindings.json")
    require(
        accepted_b4["authorities"] == authority and accepted_b4["prepared"] == actual,
        "B.4 source bindings differ",
    )
    b4_summary = archived_json(b4, "stage34b4_summary.json")
    require(b4_summary["stage34b4_status"] == "PASS", "B.4 is not accepted")
    pending = archived_json(b4, "b5/stage32_qc_pending_decision.json")
    validate_pending(pending, archived_json(b4, "b5/stage34b5_summary.json"))
    dcd = Path(source["dcd"]["path"])
    require(dcd.stat().st_size == source["dcd"]["size_bytes"], "DCD size differs")
    return {
        "authority": authority,
        "prepared": actual,
        "selected_frames": selected,
        "source": source,
        "pending_record": file_record(b4 / "b5/stage32_qc_pending_decision.json"),
        "pilot_interval_ns": [0.1, 0.5],
        "dcd_stat": {
            "size_bytes": dcd.stat().st_size,
            "mtime_ns": dcd.stat().st_mtime_ns,
        },
    }


def protected_snapshot(b3, b4, binding):
    paths = {p for base in (b3, b4) for p in base.rglob("*") if p.is_file()}
    paths.update((b3.with_suffix(".zip"), b4.with_suffix(".zip")))
    for role in ("psf", "elements", "time", "mapping"):
        paths.add(Path(binding["authority"][role]["path"]))
    for role in ("config", "log"):
        paths.add(Path(binding["source"][role]["path"]))
    return {str(p.resolve()): digest(p) for p in sorted(paths)}


def load_coordinates(binding):
    import MDAnalysis as mda
    from MDAnalysis.lib.formats.libmdaxdr import XTCFile
    from MDAnalysis.lib.mdamath import triclinic_box

    u = mda.Universe(binding["authority"]["psf"]["path"], to_guess=())
    protein = u.select_atoms("protein")
    ca = u.select_atoms(SELECTION)
    require(
        len(u.atoms) == 439436
        and len(protein) == 10814
        and len(protein.residues) == len(ca) == 690
        and np.array_equal(ca.resindices, protein.residues.resindices),
        "Accepted atom/residue/C-alpha identity differs",
    )
    residue_rows = [
        [str(r.segid), str(r.resid), str(r.resname), int(r.resindex), position]
        for position, r in enumerate(protein.residues, 1)
    ]
    signature = hashlib.sha256(
        json.dumps(residue_rows, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    require(
        signature
        == binding["authority"]["mapping_psf_binding"][
            "ordered_residue_identity_sha256"
        ],
        "Accepted ordered residue identity differs",
    )
    atoms = [
        dict(
            index=int(a.index),
            id=int(a.id),
            name=str(a.name),
            resindex=int(a.resindex),
            resid=int(a.resid),
            resname=str(a.resname),
            segid=str(a.segid),
        )
        for a in ca
    ]
    coordinates, technical = [], []
    # Low-level read-only XTC access avoids creating/modifying offset sidecars.
    with XTCFile(binding["prepared"]["path"], "r") as reader:
        require(
            len(reader) == 5, "Prepared trajectory must contain exactly five frames"
        )
        for i in FRAMES:
            frame = reader.read()
            require(frame.x.shape == (len(u.atoms), 3), "Prepared atom count differs")
            require(np.isfinite(frame.x).all(), "Nonfinite prepared coordinates")
            require(frame.time == TIMES_PS[i], "Prepared technical time differs")
            box = triclinic_box(*frame.box)
            box[:3] *= 10.0
            require(
                np.allclose(
                    box, binding["selected_frames"][i]["box"], rtol=0, atol=2e-5
                ),
                "Accepted prepared box differs",
            )
            # XTC native length is nm; match MDAnalysis float32 conversion to A
            # before promoting to float64 for fitting. Never mutate frame.x.
            coordinates.append(
                (frame.x[ca.indices].copy() * np.float32(10)).astype(float)
            )
            technical.append(
                {
                    "prepared_frame_index": i,
                    "prepared_time_ps": float(frame.time),
                    "historical_raw_dcd_time_ps": binding["selected_frames"][i][
                        "raw_dcd_time_ps"
                    ],
                    "box_A_degrees": box.tolist(),
                    "all_coordinates_finite": True,
                }
            )
    return np.stack(coordinates), atoms, technical


def aligned_rmsd(mobile, reference):
    """Equal-weight Kabsch proper rotation and RMSD on the same float64 atoms."""
    x, y = (
        np.array(mobile, dtype=np.float64, copy=True),
        np.array(reference, dtype=np.float64, copy=True),
    )
    require(
        x.shape == y.shape and x.ndim == 2 and x.shape[1] == 3, "Invalid coordinates"
    )
    require(
        len(x) >= 3 and np.isfinite(x).all() and np.isfinite(y).all(), "Invalid atoms"
    )
    x -= x.mean(axis=0)
    y -= y.mean(axis=0)
    left, _, right = np.linalg.svd(x.T @ y)
    correction = np.eye(3)
    correction[2, 2] = -1.0 if np.linalg.det(left @ right) < 0 else 1.0
    rotation = left @ correction @ right
    residual = x @ rotation - y
    return float(np.sqrt(np.sum(residual * residual) / len(x)))


def calculate_twice(coordinates):
    require(
        coordinates.ndim == 3 and len(coordinates) == 5, "Exactly five frames required"
    )
    before = coordinates.copy()
    reference = coordinates[0].copy()
    runs = [[aligned_rmsd(frame, reference) for frame in coordinates] for _ in range(2)]
    require(np.array_equal(coordinates, before), "Coordinates were modified")
    difference = float(np.max(np.abs(np.array(runs[0]) - runs[1])))
    require(difference <= 1e-12, "Software repeat reproducibility failed")
    require(runs[0][0] <= 1e-10, "Software self-reference precision check failed")
    return runs, difference


def write_review(work, coordinates, binding, atoms, technical, head):
    runs, difference = calculate_twice(coordinates)
    rows = [
        dict(
            prepared_frame_index=i,
            source_dcd_frame_index=i,
            scientific_time_ns=TIMES_NS[i],
            rmsd_A=value,
            reference_prepared_frame_index=0,
            reference_scientific_time_ns=0.1,
            atom_selection=SELECTION,
            n_atoms_used=len(atoms),
        )
        for i, value in enumerate(runs[0])
    ]
    with (work / "rmsd_evidence.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Use the existing optional plotting installation; no dependency changes.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(9, 5), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.plot(TIMES_NS, runs[0], marker="o", markersize=7, linewidth=1.4)
    ax.set(xlabel="Scientific time, ns", ylabel="Aligned RMSD, Å", xticks=TIMES_NS)
    ax.set_title("Stage 34.B NAMD five-frame pilot RMSD review evidence", fontsize=12)
    fig.supxlabel(
        "WT NaPi2b · 2SS · PMm · replica 1 | Cα reference: frame 0, 0.1 ns", fontsize=10
    )
    fig.savefig(work / "rmsd_evidence.png", dpi=180)
    method = {
        "system_identity": {
            **IDENTITY,
            "protein": "WT NaPi2b",
            "source_membrane_label": "PMm",
        },
        "pilot_interval_ns": [0.1, 0.5],
        "prepared_frames": FRAMES,
        "source_frames": FRAMES,
        "scientific_times_ns": TIMES_NS,
        "psf": binding["authority"]["psf"],
        "prepared_trajectory": binding["prepared"],
        "git_sha": head,
        "versions": {
            n: importlib.metadata.version(n)
            for n in ("mania-wania", "MDAnalysis", "numpy", "matplotlib")
        },
        "atom_selection": SELECTION,
        "alignment_selection": SELECTION,
        "rmsd_selection": SELECTION,
        "n_atoms_used": len(atoms),
        "reference_prepared_frame_index": 0,
        "reference_scientific_time_ns": 0.1,
        "alignment_method": "Equal-weight least-squares rigid-body Kabsch fit; "
        "float64 centering, NumPy SVD, proper rotation (det=+1)",
        "rmsd_definition": "sqrt(sum_i ||centered_mobile_i @ rotation - "
        "centered_reference_i||^2 / N), same atoms as fit",
        "rmsd_unit": "angstrom",
        "method_status": "documented_review_fallback",
        "method_authority": "User-specified fallback; Stage 32 does not freeze "
        "a coordinate RMSD procedure",
        "stage32_contract_sources": CONTRACT_SOURCES,
        "implementation": {
            **file_record(Path(__file__)),
            "function": "aligned_rmsd",
            "archived_copy": Path(__file__).name,
        },
        "coordinate_reader": "MDAnalysis.lib.formats.libmdaxdr.XTCFile, read-only; "
        "native nm multiplied by 10 in float32, then float64 fit",
        "statements": ["no automatic RMSD threshold applied", "no drift decision made"],
        "scientific_pbc_status": "unresolved",
        "internal_mic": False,
        "reproducibility": {
            "runs_A": runs,
            "maximum_repeat_difference_A": difference,
            "software_repeat_atol_A": 1e-12,
            "actual_self_reference_rmsd_A": runs[0][0],
            "software_self_reference_atol_A": 1e-10,
            "interpretation": "Software checks only; not independent "
            "scientific validation or QC criteria",
        },
        "technical_timestamps_and_boxes": technical,
    }
    dump(work / "rmsd_method.json", method)
    dump(work / "selected_atom_identity.json", atoms)
    (work / "warnings_limitations.txt").write_text(LIMITATIONS)
    (work / "README.md").write_text(
        "# Five-frame RMSD review evidence\n\n" + LIMITATIONS + "\n"
        "The same protein Cα atoms are aligned and measured with equal weights. "
        "Prepared frame 0 (0.1 ns) is the reference fixed before calculation. "
        "RMSD is the root mean square residual positional difference after the "
        "least-squares rigid-body fit, in angstrom. All five observations are shown. "
        "Lines connect observations only. "
        "The first value is computed, not forced to zero.\n\n"
        "A human reviewer must decide whether drift is present for this pilot QC gate. "
        "These files contain review evidence only "
        "and do not constitute that decision.\n"
    )
    return method


def package(work):
    archive_path = work.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(work)))
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None, "Evidence ZIP CRC failure")
    return archive_path


def run(repo):
    commands = []
    for argv in (
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
        ["git", "rev-parse", "develop"],
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        ["git", "log", "--oneline", "--decorate", "-24"],
        ["git", "diff", "--cached", "--name-only"],
    ):
        result = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
        require(result.returncode == 0, "Repository checkpoint failed")
        commands.append(
            {
                "argv": argv,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr,
            }
        )
    require(commands[0]["output"].strip() == "FAIR", "Required branch FAIR")
    require(not commands[-1]["output"].strip(), "Index must be empty")
    head = commands[1]["output"].strip()
    b3, b4 = repo / "local_md" / B3, repo / "local_md" / B4
    binding = bind_inputs(b3, b4)
    protected = protected_snapshot(b3, b4, binding)
    coordinates, atoms, technical = load_coordinates(binding)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    work = repo / "local_md" / f"stage34b5_rmsd_review_{stamp}_{uuid4().hex}"
    work.mkdir()
    require(
        subprocess.run(["git", "check-ignore", "-q", str(work)], cwd=repo).returncode
        == 0,
        "Evidence workspace must be ignored",
    )
    method = write_review(work, coordinates, binding, atoms, technical, head)
    require(
        protected_snapshot(b3, b4, binding) == protected,
        "Protected source bytes changed",
    )
    dcd = Path(binding["source"]["dcd"]["path"])
    require(
        binding["dcd_stat"]
        == {"size_bytes": dcd.stat().st_size, "mtime_ns": dcd.stat().st_mtime_ns},
        "Source DCD changed",
    )
    dump(
        work / "source_identity.json",
        {
            **binding,
            "protected_file_sha256_before_and_after": protected,
            "protected_files_unchanged": True,
            "source_dcd_coordinate_reads": 0,
            "prepared_coordinate_frame_reads": list(FRAMES),
            "stage32_decision_mutated": False,
            "stage31_executed": False,
            "stage33_executed": False,
            "contract_source_bindings": {
                p: file_record(repo / p) for p in CONTRACT_SOURCES
            },
        },
    )
    commands.append(
        {
            "argv": [sys.executable, *sys.argv],
            "purpose": "Evidence generation; no scientific QC decision",
        }
    )
    dump(work / "commands.json", commands)
    (work / "git_state.txt").write_text(
        "\n".join(
            "$ " + shlex.join(c["argv"]) + "\n" + c.get("output", "") for c in commands
        )
    )
    (work / "verification.log").write_text(
        "Accepted archive/PSF/XTC/control/frame/time/identity/finite-coordinate "
        "bindings verified.\n"
        f"Protected files unchanged: {len(protected)}\n"
        f"Software reproducibility: {json.dumps(method['reproducibility'])}\n"
        "Existing pending-review QC evidence unchanged. Stage 31/33 NOT RUN.\n"
    )
    shutil.copyfile(__file__, work / Path(__file__).name)
    archive = package(work)
    print(
        json.dumps(
            {
                "workspace": str(work),
                "zip": str(archive),
                "rmsd_A": method["reproducibility"]["runs_A"][0],
                "maximum_repeat_difference_A": method["reproducibility"][
                    "maximum_repeat_difference_A"
                ],
            },
            indent=2,
        )
    )
    return work


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    run(Path(__file__).resolve().parents[1])
