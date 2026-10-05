"""Literal Ramila source bindings and GROMACS-native technical gates.

Scientific sampling, QC, partner identification, mapping and contacts remain in
the accepted MANIA engine. No biological annotation is inferred here.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

if __package__:
    from .gromacs_wt_runtime import checked_file, identity, read_json, require
else:
    from gromacs_wt_runtime import checked_file, identity, read_json, require

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "production/ramila_gromacs_runtime"
SELECTIONS = tuple(
    f"gromacs_{variant}_{condition}_r{replica}"
    for variant in ("wt", "t330m")
    for condition in ("norm", "tumor")
    for replica in (1, 2, 3)
)
REPRESENTATIVES = ("gromacs_wt_norm_r1", "gromacs_t330m_norm_r1")
PROTOCOL = "unwrap_bonded_fragments_center_protein_wrap_complete_fragments"


def dump(path: Path, value: Any) -> None:
    """Exclusive publication preserves incomplete attempts and existing approvals."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    path = path.resolve()
    result = identity(path.parent, path.name).model_dump()
    result["path"] = str(path)
    return result


def load_authority(runtime: Path = RUNTIME) -> dict[str, Any]:
    data = read_json(runtime / "authority.json")
    require(
        data["schema_version"] == "mania.ramila_gromacs_runtime.v1", "Wrong runtime"
    )
    require(
        data["protocol"] == PROTOCOL and data["format"] == "XTC:4", "Wrong PBC contract"
    )
    require(data["internal_MIC"] is False, "Internal MIC must remain false")
    require(
        data["biological_annotation_authority"] == "PENDING", "Unconfirmed annotation"
    )
    rows = data["trajectories"]
    require(
        tuple(r["trajectory_id"] for r in rows) == SELECTIONS,
        "Require exact 12 selections",
    )
    from mania.production_catalog import load_production_catalog

    catalog = load_production_catalog(REPO / "production/dataset_v1/dataset.yaml")
    for row in rows:
        selected = catalog.trajectory(row["trajectory_id"])
        require(
            row["dataset_spec"] == selected.spec.to_dict(),
            "Catalog scientific identity changed",
        )
        variant = selected.spec.identity.variant_id
        replica = selected.spec.identity.replica_id
        expected = (
            f"md_rep{replica}_full.xtc"
            if variant == "WT"
            else f"t330m_rep{replica}.xtc"
        )
        require(Path(row["xtc_path"]).name == expected, "Wrong authoritative final XTC")
        names = [r["path"] for r in lightweight(row)]
        require(
            len(names) == len(set(names)) and row["logs"],
            "Duplicate/empty source bindings",
        )
    return data


def lightweight(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [row["tpr"], row["mdp"], *row["logs"], *row["additional_tprs"]]


def select(
    authority: dict[str, Any], selections: tuple[str, ...]
) -> list[dict[str, Any]]:
    require(
        bool(selections) and len(set(selections)) == len(selections),
        "Empty/duplicate selection",
    )
    require(set(selections) <= set(SELECTIONS), "Unknown Ramila trajectory")
    return [r for r in authority["trajectories"] if r["trajectory_id"] in selections]


def discover(
    source: Path,
    rows: list[dict[str, Any]],
    *,
    require_xtc: bool = True,
) -> None:
    errors = []
    for row in rows:
        primary = source / row["tpr"]["path"]
        observed_logs = {
            p.relative_to(source).as_posix()
            for p in primary.parent.glob(primary.stem + "*.log")
        }
        if observed_logs != {f["path"] for f in row["logs"]}:
            errors.append(f"{row['trajectory_id']}: authoritative LOG set changed")
        for expected in lightweight(row):
            try:
                require(
                    identity(source, expected["path"]).model_dump() == expected,
                    f"Changed authoritative source: {expected['path']}",
                )
            except (OSError, ValueError) as exc:
                errors.append(f"{row['trajectory_id']}: {exc}")
        if require_xtc:
            try:
                checked_file(source, row["xtc_path"])
            except (OSError, ValueError) as exc:
                errors.append(f"{row['trajectory_id']}: {exc}")
    require(not errors, "\n".join(errors))


def runtime_inventory(runtime: Path = RUNTIME) -> list[dict[str, Any]]:
    return [
        identity(runtime, p.relative_to(runtime).as_posix()).model_dump()
        for p in sorted(runtime.rglob("*"))
        if p.is_file() and p.suffix == ".json"
    ]


def sampling_plan(times: tuple[float, ...], spec: dict[str, Any]):
    from mania.dataset_identity import DatasetTrajectorySpec
    from mania.preprocessing.physical_time_sampling import (
        PhysicalTimeSourceFrame,
        resolve_physical_time_sampling,
    )

    parsed = DatasetTrajectorySpec.model_validate(
        {key: spec[key] for key in ("identity", "temporal")}
    )
    plan = resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, t) for i, t in enumerate(times)),
        temporal=parsed.temporal,
    )
    require(plan.status != "failed", f"Source time axis BLOCKED: {plan.to_dict()}")
    return plan


def time_qc(plan) -> list[dict[str, Any]]:
    # Reuse the accepted Stage 32.B exact Decimal coverage comparison unchanged.
    from mania.dataset_hard_qc import _time_checks

    return [check.to_dict() for check in _time_checks(plan)]


def require_time_qc(plan) -> None:
    checks = time_qc(plan)
    require(
        all(c["status"] == "pass" for c in checks), f"Production time QC FAIL: {checks}"
    )


def scan_xtc(path: Path, *, atom_count: int, spec: dict[str, Any]) -> dict[str, Any]:
    """Inspect every native XTC header without creating raw-source offset caches.

    Full coordinate decoding and representation checks occur during preparation.
    Source order is retained verbatim; no sorting or duplicate branch selection.
    """
    times, steps, offsets, boxes = [], [], [], []
    size = path.stat().st_size
    with path.open("rb") as stream:
        while stream.tell() < size:
            offsets.append(stream.tell())
            header = stream.read(52)
            require(len(header) == 52, "Truncated XTC header")
            magic, atoms, step, time, *box = struct.unpack(">iiif9f", header)
            require(
                magic == 1995 and atoms == atom_count, "TPR/XTC atom-count mismatch"
            )
            require(math.isfinite(time) and time >= 0, "Invalid XTC time")
            require(all(math.isfinite(v) for v in box), "Nonfinite XTC unit cell")
            a, b, c = box[:3], box[3:6], box[6:]
            determinant = (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            )
            require(determinant > 0, "Invalid XTC unit-cell volume")
            chunk = stream.read(4)
            require(
                len(chunk) == 4 and struct.unpack(">i", chunk)[0] == atoms,
                "Invalid XTC coordinate count",
            )
            if atoms > 9:
                chunk = stream.read(36)
                require(len(chunk) == 36, "Truncated XTC compression header")
                precision, *integers = struct.unpack(">f8i", chunk)
                length = integers[-1]
                require(
                    math.isfinite(precision) and precision > 0 and length > 0,
                    "Invalid XTC compression",
                )
                stream.seek((length + 3) // 4 * 4, 1)
            else:
                stream.seek(atoms * 12, 1)
            require(stream.tell() <= size, "Truncated XTC coordinates")
            times.append(float(time))
            steps.append(step)
            boxes.append(box)
    require(bool(times), "Empty XTC")
    plan = sampling_plan(tuple(times), spec)
    require_time_qc(plan)
    return dict(
        atom_count=atom_count,
        frame_count=len(times),
        times_ps=times,
        steps=steps,
        offsets=offsets,
        boxes_nm=boxes,
        sampling_plan=plan.to_dict(),
        time_qc=time_qc(plan),
    )


def topology_fingerprint(universe) -> str:
    """TPR atom/residue order, chemistry, elements and bonds; no coordinates/seeds."""
    import numpy as np

    sha = hashlib.sha256()
    for values in (
        universe.atoms.names,
        universe.atoms.types,
        universe.atoms.elements,
        universe.residues.resnames,
        universe.residues.segids,
    ):
        sha.update(json.dumps(values.tolist(), separators=(",", ":")).encode())
    for values in (
        universe.atoms.resindices,
        universe.residues.resids,
        universe.atoms.masses,
        universe.atoms.charges,
        universe.bonds.indices,
    ):
        sha.update(np.ascontiguousarray(values).tobytes())
    return sha.hexdigest()


def validate_topology(universe, row: dict[str, Any], runtime: Path = RUNTIME) -> None:
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
    from mania.preprocessing.molecular_partner_identification import (
        identify_molecular_partners,
    )
    from mania.preprocessing.molecular_partner_metadata_io import (
        read_molecular_partner_metadata,
    )
    from mania.preprocessing.specialized_contact_execution import (
        adapt_molecular_partner_topology,
    )

    require(
        topology_fingerprint(universe) == row["topology_fingerprint"],
        "Wrong topology atom order/chemistry",
    )
    mapping = read_canonical_residue_mapping(runtime / row["canonical_mapping_path"])
    protein = universe.select_atoms("protein").residues
    require(len(protein) == len(mapping.mappings) == 690, "Incomplete protein mapping")
    lookup = {
        (m.source_chain_id, m.source_resid, m.source_resname): m
        for m in mapping.mappings
    }
    reference = load_default_napi2b_canonical_reference()
    substitutions = []
    for residue in protein:
        key = (residue.segid, str(residue.resid), residue.resname)
        require(key in lookup, "Protein source key absent from explicit mapping")
        m = lookup[key]
        expected = reference.residue_at(m.canonical_residue_number)
        source_name = (
            "HIS" if residue.resname in ("HSD", "HSE", "HSP") else residue.resname
        )
        if source_name != expected.canonical_resname:
            substitutions.append(
                (m.canonical_residue_number, source_name, expected.canonical_resname)
            )
    variant = row["dataset_spec"]["identity"]["variant_id"]
    require(
        substitutions == ([] if variant == "WT" else [(330, "MET", "THR")]),
        "Unexpected protein substitution",
    )
    metadata = read_molecular_partner_metadata(runtime / row["partner_metadata_path"])
    topology, indexes = adapt_molecular_partner_topology(universe)
    require(
        topology.connectivity_status == "available", "Missing authoritative TPR bonds"
    )
    catalog = identify_molecular_partners(
        topology,
        protein_residue_indexes=indexes,
        classifications=metadata.classifications,
        explicit_partners=metadata.explicit_partners,
    )
    require(
        (catalog.lipid_partner_count, catalog.glycan_partner_count)
        == (row["lipid_partners"], row["glycan_partners"]),
        "Partner roster changed",
    )
