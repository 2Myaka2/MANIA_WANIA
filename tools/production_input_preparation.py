"""External Egor preparation and explicit review; no contact or QC execution.

The fragment helper and representation checks are migrated from accepted D.4e.3.
Only the supplied portable handoff is read at runtime, never historical runners.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shlex
import shutil
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from mania.biological_annotations_io import read_dataset_system_biological_annotations
from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
from mania.preprocessing.molecular_partner_metadata_io import (
    read_molecular_partner_metadata,
    read_strict_json,
    write_atomic_text,
)
from mania.preprocessing.namd_authority import (
    ElementControl,
    TimeControl,
    derive_time,
    literal_config,
    read_control,
    source_identity,
    validate_elements,
    validate_time,
    write_control,
)
from mania.preprocessing.namd_runtime import (
    NAMDControlPaths,
    apply_namd_authority,
    observe_dcd,
)
from mania.production_catalog import load_production_catalog, portable_path
from mania.production_run import BoundFile, PreparedLineage, ProductionInputBinding

PROTOCOL = "unwrap_bonded_fragments_center_protein_wrap_complete_fragments"
TOLERANCE = 0.001
SELECTIONS = {f"namd_egor_wt_{ss}ss_r{r}" for ss in range(3) for r in range(1, 4)}
SOURCE_ROLES = ("topology_path", "config_path", "log_path", "box_path")
SYSTEM_ROLES = ("canonical_mapping", "biological_annotations", "partner_metadata")
AUTOMATIC_CHECKS = {
    "package_and_source_identity",
    "full_frame_atom_time_axis",
    "finite_positive_preserved_cells",
    "bond_representation",
    "atom_lattice_lineage",
    "protein_centering",
    "complete_fragment_centers",
    "standard_protocol_equivalence",
    "reopened_indexed_coordinate_hashes",
    "strict_time_controls",
    "prepared_runtime_authority",
    "raw_sources_unchanged",
}
LIMITATIONS = [
    "Automatic technical checks are not human review or scientific/QC approval.",
    "DCD has no atom labels: indexed lineage preserves raw order, but cannot prove "
    "the original raw DCD physically corresponds to the PSF; the reviewer must check.",
    "No contacts, final QC, aggregation or publication were run.",
    "Serial preparation, one coordinate frame at a time; no mid-calculation resume.",
]


class SiteReview(BaseModel):
    """Existing egor.handoff.site_review.v1 model, migrated from the handoff helper."""

    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["egor.handoff.site_review.v1"]
    trajectory_id: str
    raw_trajectory: str
    prepared_trajectory: str
    raw_time_control: str
    prepared_time_control: str
    pbc_evidence: str
    prepared_lineage: PreparedLineage


def require(ok: Any, message: str) -> None:
    if not ok:
        raise ValueError(message)


def dump(path: Path, value: Any) -> None:
    result = write_atomic_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", path, overwrite=False
    )
    if not result.passed:
        raise OSError(f"Protected atomic write failed: {path}: {result.error}")


def contained(root: Path, value: str) -> Path:
    path = (root / portable_path(value)).resolve()
    require(path != root and path.is_relative_to(root), f"Path escapes root: {value}")
    return path


def no_symlinks(path: Path) -> None:
    require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        f"Symlink output/package path forbidden: {path}",
    )


def record(path: Path, root: Path) -> dict[str, Any]:
    actual = source_identity(path)
    return BoundFile(
        path=path.resolve().relative_to(root).as_posix(),
        size_bytes=actual.size_bytes,
        sha256=actual.sha256,
    ).model_dump()


def check_records(records: dict[str, Any], root: Path) -> None:
    for role, expected in records.items():
        require(
            record(contained(root, expected["path"]), root) == expected,
            f"Changed input/output identity: {role}",
        )


def package_inventory(package: Path) -> dict[str, str]:
    """Verify the delivered checksum list as data; never execute package Python."""
    no_symlinks(package)
    manifest = package / "HANDOFF_FILES.sha256"
    result = {manifest.name: source_identity(manifest).sha256}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "Malformed package checksum line")
        digest, name = match.groups()  # type: ignore[union-attr]
        require(name not in result, "Duplicate package checksum path")
        path = contained(package, name)
        no_symlinks(package / name)
        require(source_identity(path).sha256 == digest, f"Stale package file: {name}")
        result[name] = digest
    require(
        {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
        == set(result),
        "Uninventoried or missing package files",
    )
    return result


def _package_path(root: Path, package: Path, value: str) -> Path:
    """Rebase the package's explicit egor_handoff mount; do not guess basenames."""
    parts = portable_path(value).parts
    if parts[0] == "egor_handoff":
        return contained(package, Path(*parts[1:]).as_posix())
    return contained(root, value)


def _rebind(value: Any, root: Path, package: Path) -> Any:
    if isinstance(value, dict):
        return {
            k: str(_package_path(root, package, v))
            if k in {"path", "source_directory"}
            else _rebind(v, root, package)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_rebind(v, root, package) for v in value]
    return value


def select_authority(root: Path, package: Path, trajectory_id: str) -> dict[str, Any]:
    require(trajectory_id in SELECTIONS, "Select exactly one of the nine Egor rows")
    inventory = package_inventory(package)
    manifest = read_strict_json(package / "handoff_manifest.json")
    require(manifest["schema_version"] == "egor.handoff.manifest.v1", "Wrong package")
    rows = manifest["rows"]
    require(
        len(rows) == 9 and {r["trajectory_id"] for r in rows} == SELECTIONS,
        "Package must explicitly contain all nine selections",
    )
    row = next(r for r in rows if r["trajectory_id"] == trajectory_id)
    catalog_path = package / "catalog/dataset.yaml"
    catalog = load_production_catalog(catalog_path)
    selected = catalog.trajectory(trajectory_id)
    template = read_strict_json(contained(package, row["input_binding_template"]))
    require(
        template["schema_version"] == "egor.handoff.input_binding_template.v1"
        and template["trajectory_id"] == trajectory_id
        and template["status"] == "requires_execution_site_verification"
        and template["executable"] is False,
        "Wrong binding template/replica",
    )
    draft = template["payload"]
    require(
        draft["catalog_row"] == selected.row
        and draft["dataset_id"]
        == manifest["dataset_id"]
        == selected.spec.identity.dataset_id
        and draft["temporal_policy"] == catalog.temporal_policy.model_dump(mode="json"),
        "Catalog/template identity mismatch",
    )
    sources = read_strict_json(package / "authority/source_inventory.json")
    require(
        len(sources) == 9 and {s["trajectory_id"] for s in sources} == SELECTIONS,
        "Wrong source inventory",
    )
    source = next(s for s in sources if s["trajectory_id"] == trajectory_id)
    system_id = selected.row["system_id"]
    require(
        source["system_id"] == row["system_id"] == system_id
        and source["replica_id"] == selected.row["replica_id"],
        "Wrong source system/replica",
    )
    systems = [s for s in manifest["systems"] if s["system_id"] == system_id]
    require(len(systems) == 1, "Missing/duplicate system authority")
    system = systems[0]
    controls = contained(package, system["controls"])
    require(
        read_strict_json(controls / "topology_authority.json") == system,
        "System topology authority mismatch",
    )
    files, paths = {}, {}
    for role in (*SOURCE_ROLES, *SYSTEM_ROLES):
        expected = BoundFile.model_validate(draft["files"][role]).model_dump()
        path = _package_path(root, package, expected["path"])
        actual = record(path, root)
        require(
            (actual["size_bytes"], actual["sha256"])
            == (expected["size_bytes"], expected["sha256"]),
            f"Wrong source/control: {role}",
        )
        if role in SOURCE_ROLES:
            require(expected == source["files"][role], f"Wrong replica {role}")
            require(
                expected["path"] == selected.row[role], f"Wrong source path: {role}"
            )
        else:
            require(path.parent == controls, f"Foreign system control: {role}")
        files[role], paths[role] = actual, path
    require(draft["files"]["topology_path"] in system["psfs"], "Foreign PSF")
    raw_path = source["expected_dcd_path"]
    require(
        raw_path
        == template["expected_dcd_path"]
        == row["expected_dcd_path"]
        == draft["files"]["trajectory_path"]["path"]
        == selected.row["trajectory_path"],
        "Wrong explicit raw DCD binding",
    )
    paths["trajectory_path"] = contained(root, raw_path)
    files["trajectory_path"] = record(paths["trajectory_path"], root)
    values = literal_config(paths["config_path"])
    require(
        values["structure"] == source["declared_structure"], "Wrong PSF declaration"
    )
    require(
        values["dcdfile"]
        == source["declared_dcd_filename"]
        == template["declared_dcd_filename"]
        == row["declared_dcd_filename"],
        "Wrong declared DCD source/replica",
    )
    element_path = _package_path(root, package, selected.row["element_control"])
    portable_elements = read_strict_json(element_path)
    require(
        portable_elements["psf"] == source["files"]["topology_path"],
        "Wrong element PSF/replica",
    )
    elements = ElementControl.model_validate_json(
        json.dumps(_rebind(portable_elements, root, package))
    )
    validate_elements(elements, paths["topology_path"])
    require(
        sum(elements.used_type_counts.values()) == system["atom_count"],
        "Wrong system atom population",
    )
    shared = read_strict_json(package / "authority/shared_toppar.json")
    require(portable_elements["sources"] == shared["sources"], "Wrong shared toppar")
    for i, item in enumerate(elements.sources):
        files[f"toppar:{i}"] = record(Path(item.path), root)
    read_canonical_residue_mapping(paths["canonical_mapping"])
    read_molecular_partner_metadata(paths["partner_metadata"])
    annotations = read_dataset_system_biological_annotations(
        paths["biological_annotations"]
    )
    require(
        (annotations.dataset_id, annotations.system_id)
        == (draft["dataset_id"], system_id),
        "Wrong annotation system",
    )
    time_templates = {}
    for role in ("raw", "prepared"):
        t = read_strict_json(contained(package, row[f"{role}_time_template"]))
        require(
            t["schema_version"] == "egor.handoff.time_template.v1"
            and t["trajectory_id"] == trajectory_id
            and t["role"] == role
            and t["runtime_schema"] == "mania.namd_time_authority.v1"
            and t["status"] == "requires_execution_site_DCD_verification"
            and t["dcd_observation"] is None
            and t["config"] == source["files"]["config_path"]
            and t["log"] == source["files"]["log_path"]
            and t["declared_dcd_filename"] == values["dcdfile"]
            and t["expected_atom_count"] == system["atom_count"],
            f"Wrong {role} time template/source/replica",
        )
        expected_path = (
            raw_path if role == "raw" else draft["files"]["prepared_trajectory"]["path"]
        )
        require(t["expected_path"] == expected_path, "Wrong time template path")
        derived = derive_time(
            paths["config_path"], paths["log_path"], t["expected_frame_count"]
        )
        require(
            json.loads(json.dumps(derived)) == t["source_derivation"],
            "Time template differs from selected CONF/OUT",
        )
        time_templates[role] = t
    require(
        time_templates["raw"]["source_derivation"]
        == time_templates["prepared"]["source_derivation"],
        "Unequal time axes",
    )
    protocol = read_strict_json(package / "authority/pbc_protocol.json")
    times = [float(t) for t in derived["scientific_times_ps"]]
    require(
        protocol["schema_version"] == "egor.handoff.pbc_protocol.v1"
        and protocol["protocol"] == PROTOCOL
        and protocol["internal_mic"] is False
        and protocol["required_atom_order_preserved"] is True
        and protocol["required_frame_order_preserved"] is True
        and protocol["required_frame_count"] == len(times)
        and protocol["required_full_axis_ps"] == [times[0], times[-1]]
        and times[-1] == float(selected.row["nominal_duration_ns"]) * 1000,
        "Unsupported protocol/full-axis authority",
    )
    return dict(
        inventory=inventory,
        draft=draft,
        paths=paths,
        inputs=files,
        elements=elements,
        times=times,
        template=time_templates["raw"],
        catalog=catalog_path,
        selected=selected,
        protocol=protocol,
    )


class FragmentPreparation:
    """Accepted D.4e.3 batched make_whole early return and complete-fragment wrap."""

    def __init__(self, universe: Any):
        self.u = universe
        self.bonds = universe.bonds.indices.copy()
        self.fragment_ids = universe.atoms.fragindices.copy()
        self.fragments = universe.atoms.fragments
        _, self.first_atoms, self.counts = np.unique(
            self.fragment_ids, return_index=True, return_counts=True
        )
        require(
            np.array_equal(
                np.unique(self.fragment_ids), np.arange(len(self.fragments))
            ),
            "Noncontiguous fragment identities",
        )
        require(
            np.all(
                self.fragment_ids[self.bonds[:, 0]]
                == self.fragment_ids[self.bonds[:, 1]]
            ),
            "Cross-fragment bond",
        )

    def unwrap(self) -> int:
        from MDAnalysis.lib.mdamath import make_whole

        xyz = self.u.atoms.positions
        if np.all(self.u.dimensions[3:] == 90):
            offsets = np.abs(xyz - xyz[self.first_atoms[self.fragment_ids]])
            needs_work = np.any(
                offsets >= self.u.dimensions[:3] * np.float32(0.5), axis=1
            )
            changed = np.unique(self.fragment_ids[needs_work])
        else:
            changed = np.flatnonzero(self.counts > 1)
        for index in changed:
            make_whole(self.fragments[int(index)])
        return len(changed)

    def wrap(self) -> None:
        from MDAnalysis.lib.distances import apply_PBC

        centers = self.u.atoms.center_of_geometry(
            wrap=False, compound="fragments"
        ).astype(np.float32)
        shifts = apply_PBC(centers, self.u.dimensions) - centers
        self.u.trajectory.ts.positions += shifts[self.fragment_ids]


def coordinate_digest(array: Any) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array, dtype=np.float32).tobytes()
    ).hexdigest()


def _time_control(authority: dict[str, Any], observed: Any) -> TimeControl:
    p = authority["paths"]
    return TimeControl(
        schema_version="mania.namd_time_authority.v1",
        engine="NAMD",
        config=source_identity(p["config_path"]),
        log=source_identity(p["log_path"]),
        dcd=observed,
        **derive_time(p["config_path"], p["log_path"], observed.frame_count),
        derivation="config_log_step_times_timestep_fs_divided_by_1000",
        status="validated",
    )


def prepare_coordinates(
    authority: dict[str, Any], out: Path, phase: Any
) -> dict[str, Any]:
    """Stream full-axis coordinates and reopen every frame; no sampling or contacts."""
    import MDAnalysis as mda
    from MDAnalysis import transformations as trans
    from MDAnalysis.lib.distances import calc_bonds, minimize_vectors
    from MDAnalysis.lib.mdamath import triclinic_vectors

    p, elements = authority["paths"], authority["elements"]
    target = out / "prepared.dcd"
    # The attempt directory is exclusively claimed before this writer is opened.
    require(not target.exists(), "Existing prepared trajectory is protected")
    with contextlib.ExitStack() as stack:
        u = mda.Universe(
            str(p["topology_path"]), str(p["trajectory_path"]), to_guess=()
        )
        stack.callback(u.trajectory.close)
        observed = observe_dcd(u.trajectory, p["trajectory_path"])
        raw_time = _time_control(authority, observed)
        times = validate_time(raw_time, p["trajectory_path"])
        require(list(times) == authority["times"], "Unexpected full raw time axis")
        require(
            observed.unit_cell
            and len(u.atoms)
            == observed.atom_count
            == sum(elements.used_type_counts.values()),
            "PSF/DCD atom/cell mismatch",
        )
        require(
            dict(Counter(u.atoms.types)) == elements.used_type_counts,
            "Runtime atom/type population mismatch",
        )
        lookup = validate_elements(elements, p["topology_path"])
        u.add_TopologyAttr("elements", [lookup[str(t)] for t in u.atoms.types])
        write_control(out / "raw_time.json", raw_time)
        protein = u.select_atoms("protein")
        bonds = u.bonds.indices.copy()
        fragments = u.atoms.fragindices.copy()
        require(len(protein) > 0 and len(bonds) > 0, "Protein/bond authority required")
        require(
            len(np.unique(fragments[protein.indices])) == 1,
            "Protein must be one fragment",
        )
        require(not np.any(u._topology.bonds.is_guessed), "Guessed bonds forbidden")
        batched = FragmentPreparation(u)
        unwrap = trans.unwrap(u.atoms, max_threads=1, parallelizable=True)
        center = trans.center_in_box(
            protein, center="geometry", wrap=False, max_threads=1, parallelizable=True
        )
        standard_indexes = {0, len(times) - 1}
        for key in ("production_start_ns", "production_end_ns"):
            standard_indexes.update(
                i
                for i, t in enumerate(times)
                if t == float(authority["selected"].row[key]) * 1000
            )
        maxima = dict(
            bond_distance_max_error_A=0.0,
            atom_lattice_max_error_A=0.0,
            protein_center_error_A=0.0,
        )
        remarks = (
            "EXTERNAL PBC PREPARED; raw FILENAME="
            + literal_config(p["config_path"])["dcdfile"]
        )
        phase("raw_observed", frame_count=len(times), atom_count=len(u.atoms))
        with (
            (out / "frame_audit.jsonl").open("x") as audit,
            mda.coordinates.DCD.DCDWriter(
                str(target),
                n_atoms=len(u.atoms),
                dt=observed.dt_ps,
                nsavc=observed.nsavc,
                istart=observed.istart,
                remarks=remarks,
            ) as writer,
        ):
            for i, ts in enumerate(u.trajectory):
                require(
                    ts.frame == i and i < len(times), "Raw frame order/count changed"
                )
                original, box, raw_t = (
                    ts.positions.copy(),
                    ts.dimensions,
                    float(ts.time),
                )
                require(box is not None, f"Missing cell at frame {i}")
                box = box.copy()
                require(
                    np.isfinite(original).all()
                    and np.isfinite(box).all()
                    and np.isfinite(raw_t),
                    f"Nonfinite coordinates/cell/time at frame {i}",
                )
                require(
                    np.all(box[:3] > 0) and np.all((box[3:] > 0) & (box[3:] < 180)),
                    f"Invalid cell at frame {i}",
                )
                vectors = triclinic_vectors(box).astype(float)
                require(
                    np.linalg.det(vectors) > 0, f"Invalid cell determinant at frame {i}"
                )
                periodic_bonds = calc_bonds(
                    original[bonds[:, 0]], original[bonds[:, 1]], box=box
                )
                changed = batched.unwrap()
                standard = i in standard_indexes
                if standard:
                    unwrapped = ts.positions.copy()
                    ts.positions = original.copy()
                    unwrap(ts)
                    require(
                        np.array_equal(ts.positions, unwrapped),
                        "Standard unwrap mismatch",
                    )
                    ts.positions = unwrapped
                translation = vectors.sum(axis=0) / 2 - protein.center_of_geometry()
                center(ts)
                centered = ts.positions.copy() if standard else None
                batched.wrap()
                if standard:
                    prepared = ts.positions.copy()
                    ts.positions = centered
                    u.atoms.wrap(
                        compound="fragments", center="cog", box=box, inplace=True
                    )
                    require(
                        np.array_equal(ts.positions, prepared), "Standard wrap mismatch"
                    )
                    ts.positions = prepared
                prepared = ts.positions
                require(np.isfinite(prepared).all(), "Nonfinite prepared coordinates")
                direct = calc_bonds(prepared[bonds[:, 0]], prepared[bonds[:, 1]])
                residual = minimize_vectors(
                    prepared.astype(float) - original.astype(float) - translation, box
                )
                errors = dict(
                    bond_distance_max_error_A=float(
                        np.max(np.abs(periodic_bonds - direct))
                    ),
                    atom_lattice_max_error_A=float(
                        np.max(np.linalg.norm(residual, axis=1))
                    ),
                    protein_center_error_A=float(
                        np.linalg.norm(
                            protein.center_of_geometry() - vectors.sum(axis=0) / 2
                        )
                    ),
                )
                for key, value in errors.items():
                    require(value <= TOLERANCE, f"{key} failed at frame {i}: {value}")
                    maxima[key] = max(maxima[key], value)
                centers = u.atoms.center_of_geometry(
                    compound="fragments"
                ) @ np.linalg.inv(vectors)
                require(
                    centers.min() >= -1e-6 and centers.max() <= 1 + 1e-6,
                    f"Fragment center outside cell at frame {i}",
                )
                require(
                    np.array_equal(ts.dimensions, box),
                    "Cell changed during preparation",
                )
                row = dict(
                    source_frame=i,
                    prepared_frame=i,
                    scientific_time_ps=times[i],
                    raw_time_ps=raw_t,
                    box=box.tolist(),
                    raw_coordinate_sha256_float32=coordinate_digest(original),
                    coordinate_sha256_float32=coordinate_digest(prepared),
                    fragments_requiring_unwrap=changed,
                    standard_protocol_bitwise_comparison=standard,
                    fragment_center_fractional_range=[
                        float(centers.min()),
                        float(centers.max()),
                    ],
                    **errors,
                )
                writer.write(u.atoms)
                audit.write(json.dumps(row, allow_nan=False) + "\n")
                if i == 0 or (i + 1) % 10 == 0:
                    audit.flush()
                    phase("preparing", frames_written=i + 1, expected=len(times))
        phase("written_reopening")
        reader = mda.coordinates.DCD.DCDReader(str(target))
        stack.callback(reader.close)
        reopened = observe_dcd(reader, target)
        for field in (
            "atom_count",
            "frame_count",
            "istart",
            "nsavc",
            "delta",
            "unit_cell",
        ):
            require(
                getattr(observed, field) == getattr(reopened, field),
                f"Reopened {field} changed",
            )
        count = 0
        with (
            (out / "frame_audit.jsonl").open() as audit,
            (out / "reopened_audit.jsonl").open("x") as persisted,
        ):
            for ts, line in zip(reader, audit, strict=True):
                row = json.loads(line)
                require(
                    ts.frame == row["prepared_frame"] == count,
                    "Reopened frame order changed",
                )
                require(
                    coordinate_digest(ts.positions) == row["coordinate_sha256_float32"],
                    f"Reopened indexed atom coordinates differ at frame {count}",
                )
                require(
                    np.allclose(ts.dimensions, row["box"], rtol=0, atol=1e-5),
                    "Reopened cell differs",
                )
                require(
                    abs(ts.time - row["raw_time_ps"]) <= 1e-6,
                    "Reopened raw time differs",
                )
                persisted.write(
                    json.dumps(
                        dict(
                            frame=count,
                            raw_time_ps=float(ts.time),
                            box=ts.dimensions.tolist(),
                            coordinate_sha256_float32=coordinate_digest(ts.positions),
                        )
                    )
                    + "\n"
                )
                count += 1
        require(count == len(times), "Incomplete reopened frame axis")
        prepared_time = _time_control(authority, reopened)
        require(
            validate_time(prepared_time, target) == times, "Prepared time axis differs"
        )
        write_control(out / "prepared_time.json", prepared_time)
        loaded = mda.Universe(str(p["topology_path"]), str(target), to_guess=())
        stack.callback(loaded.trajectory.close)
        apply_namd_authority(
            loaded,
            p["topology_path"],
            target,
            NAMDControlPaths(out / "elements.json", out / "prepared_time.json"),
        )
        for i in sorted(standard_indexes):
            require(
                loaded.trajectory[i].time == times[i], "Prepared runtime time mismatch"
            )
        phase("reopened_verified", frames_checked=count)
    return dict(
        frame_count=count,
        atom_count=observed.atom_count,
        raw_observation=observed.model_dump(mode="json"),
        prepared_observation=reopened.model_dump(mode="json"),
        scientific_time_bounds_ps=[times[0], times[-1]],
        standard_protocol_comparison_frames=sorted(standard_indexes),
        representation_tolerance_A=TOLERANCE,
        bond_count_per_frame=len(bonds),
        fragment_count=len(np.unique(fragments)),
        mdanalysis_version=mda.__version__,
        **maxima,
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Attempt:
    """Exclusive operation log; even a failed operation leaves inspectable evidence."""

    def __init__(self, directory: Path, command: list[str]):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory, self.command = directory, command
        self.start, self.last = utc_now(), ""
        self.timer = time.monotonic()

    def phase(self, name: str, **details: Any) -> None:
        now = utc_now()
        require(
            now >= (self.last or self.start),
            "UTC clock moved backwards; stabilize UTC/NTP and use a new attempt",
        )
        self.last = now
        with (self.directory / "phases.jsonl").open("a") as stream:
            stream.write(json.dumps(dict(phase=name, utc=now, **details)) + "\n")
        print(name + (": " + json.dumps(details) if details else ""), flush=True)

    def publish(self, path: Path, value: Any) -> None:
        """Publish the final marker/binding; retain a failed invocation if it fails."""
        try:
            dump(path, value)
        except BaseException as exc:
            operation_path = self.directory / "operation.json"
            operation = read_strict_json(operation_path)
            operation.update(
                status="failed",
                exit_code=1,
                error=str(exc),
                failed_phase="final_publication",
            )
            # Only this exclusively owned, still unsuccessful attempt is updated.
            write_atomic_text(
                json.dumps(operation, indent=2) + "\n", operation_path, overwrite=True
            )
            with (self.directory / "operation.log").open("a") as log:
                log.write(f"Final publication failed: {exc}\n")
            raise

    @contextlib.contextmanager
    def logged(self):
        with (self.directory / "operation.log").open("x") as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                try:
                    self.phase("started", command=self.command, cwd=str(Path.cwd()))
                    yield self
                    self.phase("completed")
                except BaseException as exc:
                    traceback.print_exc()
                    if not (self.directory / "summary.txt").exists():
                        (self.directory / "summary.txt").write_text(
                            "FAILED / INCOMPLETE: " + str(exc) + "\n"
                            "Inspect operation.log and phases.jsonl. "
                            "No successful binding or QC decision.\n"
                            + "\n".join(LIMITATIONS)
                            + "\n"
                        )
                    dump(
                        self.directory / "operation.json",
                        dict(
                            status="failed",
                            exit_code=1,
                            command=self.command,
                            started_utc=self.start,
                            ended_utc=utc_now(),
                            error=str(exc),
                            elapsed_seconds=time.monotonic() - self.timer,
                        ),
                    )
                    raise
                else:
                    dump(
                        self.directory / "operation.json",
                        dict(
                            status="completed",
                            exit_code=0,
                            command=self.command,
                            started_utc=self.start,
                            ended_utc=self.last,
                            elapsed_seconds=time.monotonic() - self.timer,
                        ),
                    )


def roots(
    data_root: Path, result_root: Path, authority_package: Path
) -> tuple[Path, Path, Path]:
    root, out, package = (
        data_root.resolve(),
        result_root.absolute(),
        authority_package.absolute(),
    )
    require(root.is_dir(), "Data root must exist")
    no_symlinks(out)
    no_symlinks(package)
    out, package = out.resolve(), package.resolve()
    require(
        out != root and out.is_relative_to(root),
        "Preparation result root must be below data root",
    )
    require(
        package != root and package.is_relative_to(root),
        "Authority package must be below data root",
    )
    require(
        not out.is_relative_to(package) and not package.is_relative_to(out),
        "Authority package/result root collision",
    )
    return root, out, package


def _space(out: Path, min_free_bytes: int, estimated_bytes: int) -> dict[str, int]:
    require(
        type(min_free_bytes) is int and min_free_bytes > 0,
        "Positive min-free-bytes required",
    )
    ancestor = out
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    required = max(min_free_bytes, estimated_bytes)
    require(free >= required, f"Insufficient disk space: {free} < {required} bytes")
    return dict(
        free_bytes=free, required_bytes=required, estimated_bytes=estimated_bytes
    )


def prepare(
    *,
    data_root: Path,
    result_root: Path,
    authority_package: Path,
    trajectory_id: str,
    min_free_bytes: int,
    workers: int = 1,
    threads: int = 1,
    command: list[str] | None = None,
) -> dict[str, Any]:
    root, out, package = roots(data_root, result_root, authority_package)
    require(trajectory_id in SELECTIONS, "Unknown trajectory_id")
    require(
        workers == threads == 1,
        "Accepted serial resource profile requires workers=threads=1",
    )
    require(
        not out.exists(), "Existing preparation output protected; use a new result root"
    )
    attempt = Attempt(
        out, command or ["python", "tools/prepare_production_inputs.py", "prepare"]
    )
    with attempt.logged():
        authority = select_authority(root, package, trajectory_id)
        for item in authority["inputs"].values():
            path = contained(root, item["path"])
            require(
                not path.is_relative_to(out) and not out.is_relative_to(path.parent),
                f"Raw/control source and output directories must be separate: {path}",
            )
        # Full all-atom float32 DCD plus cells/headers and per-frame audit overhead.
        n = authority["template"]["expected_frame_count"]
        atoms = authority["template"]["expected_atom_count"]
        space = _space(out, min_free_bytes, n * (12 * atoms + 8192) + 1024 * 1024)
        request = dict(
            trajectory_id=trajectory_id,
            data_root=str(root),
            result_root=str(out),
            authority_package=str(package),
            package_inventory=authority["inventory"],
            inputs=authority["inputs"],
            resources=dict(workers=1, threads=1, coordinate_frames_in_flight=1),
            disk=space,
            command=attempt.command,
            tool_sources=[
                source_identity(Path(__file__)).model_dump(),
                source_identity(
                    Path(__file__).with_name("prepare_production_inputs.py")
                ).model_dump(),
            ],
        )
        dump(out / "request.json", request)
        write_control(out / "elements.json", authority["elements"])
        attempt.phase("authority_verified")
        evidence = prepare_coordinates(authority, out, attempt.phase)
        check_records(authority["inputs"], root)
        require(
            package_inventory(package) == authority["inventory"],
            "Package changed during preparation",
        )
        attempt.phase("input_integrity_rechecked")
        outputs = {
            name: record(out / name, root)
            for name in (
                "request.json",
                "elements.json",
                "raw_time.json",
                "prepared_time.json",
                "prepared.dcd",
                "frame_audit.jsonl",
                "reopened_audit.jsonl",
            )
        }
        checks = dict.fromkeys(sorted(AUTOMATIC_CHECKS), True)
        report = dict(
            schema_version="egor.preparation.report.v1",
            status="pending_review",
            checks_kind="automatic_technical",
            checks=checks,
            trajectory_id=trajectory_id,
            protocol=PROTOCOL,
            protocol_authority=authority["protocol"]["authority"],
            internal_mic=False,
            human_review=None,
            scientific_contact_or_qc_certification=False,
            inputs=authority["inputs"],
            outputs=outputs,
            evidence=evidence,
            failures=[],
            limitations=LIMITATIONS,
            completed_utc=utc_now(),
        )
        dump(out / "report.json", report)
        summary = [
            f"{trajectory_id}: automatic checks passed; PENDING HUMAN REVIEW.",
            f"Frames: {evidence['frame_count']}; atoms: {evidence['atom_count']}.",
            f"Representation tolerance: {TOLERANCE} A.",
            f"Scientific time bounds (ps): {evidence['scientific_time_bounds_ps']}.",
            f"Maximum bond error (A): {evidence['bond_distance_max_error_A']}.",
            f"Maximum atom lattice error (A): {evidence['atom_lattice_max_error_A']}.",
            f"Maximum protein center error (A): {evidence['protein_center_error_A']}.",
            *[f"Automatic PASS: {name}" for name in checks],
            "Failures: none.",
            *LIMITATIONS,
        ]
        (out / "summary.txt").write_text("\n".join(summary) + "\n")
    # Completion is last: a partial write or clock failure never creates it.
    complete = {
        name: record(out / name, root)
        for name in (
            "report.json",
            "summary.txt",
            "operation.json",
            "operation.log",
            "phases.jsonl",
        )
    }
    attempt.publish(out / "complete.json", complete)
    return dict(
        status="pending_review",
        report=str(out / "report.json"),
        report_sha256=complete["report.json"]["sha256"],
        summary=str(out / "summary.txt"),
    )


def production_commands(
    catalog: Path,
    root: Path,
    output: Path,
    binding: Path,
    trajectory_id: str,
    min_free_bytes: int,
) -> list[str]:
    return [
        shlex.join(
            [
                "env",
                f"MANIA_DATA_ROOT={root}",
                "mania",
                "production",
                op,
                "--catalog",
                str(catalog),
                "--trajectory-id",
                trajectory_id,
                "--output-root",
                str(output),
                "--input-binding",
                str(binding),
                "--min-free-bytes",
                str(min_free_bytes),
            ]
        )
        for op in ("validate", "run")
    ]


def confirm(
    *,
    data_root: Path,
    result_root: Path,
    authority_package: Path,
    trajectory_id: str,
    report_sha256: str,
    reviewer: str,
    review_note: str,
    approve: bool,
    production_output_root: Path,
    min_free_bytes: int,
    command: list[str] | None = None,
) -> dict[str, Any]:
    require(approve is True, "Explicit --approve confirmation required")
    require(reviewer.strip() == reviewer and bool(reviewer), "Named reviewer required")
    require(
        review_note.strip() == review_note and bool(review_note), "Review note required"
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", report_sha256), "Exact report SHA256 required"
    )
    root, out, package = roots(data_root, result_root, authority_package)
    production_out = production_output_root.absolute()
    no_symlinks(production_out)
    production_out = production_out.resolve()
    require(
        not production_out.is_relative_to(root)
        and not root.is_relative_to(production_out),
        "Production output and data roots must be disjoint",
    )
    require(
        not any(p.is_symlink() for p in out.rglob("*")), "Result tree symlink forbidden"
    )
    attempt = Attempt(
        out / "confirmation",
        command or ["python", "tools/prepare_production_inputs.py", "confirm"],
    )
    with attempt.logged():
        _space(production_out, min_free_bytes, 0)
        complete = read_strict_json(out / "complete.json")
        check_records(complete, root)
        require(
            source_identity(out / "report.json").sha256 == report_sha256,
            "Report changed or confirmation SHA256 differs",
        )
        report = read_strict_json(out / "report.json")
        require(
            report["status"] == "pending_review"
            and report["schema_version"] == "egor.preparation.report.v1"
            and report["protocol"] == PROTOCOL
            and report["internal_mic"] is False
            and report["scientific_contact_or_qc_certification"] is False
            and report["human_review"] is None
            and report["checks_kind"] == "automatic_technical"
            and report["failures"] == []
            and set(report["checks"]) == AUTOMATIC_CHECKS
            and all(v is True for v in report["checks"].values()),
            "Failed/incomplete technical report cannot be approved",
        )
        require(
            report["trajectory_id"] == trajectory_id, "Wrong report trajectory/replica"
        )
        require(
            utc_now() >= report["completed_utc"],
            "UTC clock precedes preparation; stabilize UTC/NTP before confirmation",
        )
        check_records(report["inputs"], root)
        check_records(report["outputs"], root)
        request = read_strict_json(out / "request.json")
        require(
            (
                request["data_root"],
                request["result_root"],
                request["authority_package"],
                request["trajectory_id"],
            )
            == (str(root), str(out), str(package), trajectory_id),
            "Request roots/selection changed",
        )
        authority = select_authority(root, package, trajectory_id)
        require(
            authority["inventory"] == request["package_inventory"]
            and authority["inputs"] == report["inputs"],
            "Package/input authority changed",
        )
        operation = read_strict_json(out / "operation.json")
        require(
            operation["status"] == "completed" and operation["exit_code"] == 0,
            "Incomplete preparation operation",
        )
        require(
            utc_now() >= operation["ended_utc"],
            "UTC clock precedes completed operation",
        )
        raw_time = read_control(out / "raw_time.json", TimeControl)
        prepared_time = read_control(out / "prepared_time.json", TimeControl)
        raw_times = validate_time(raw_time, authority["paths"]["trajectory_path"])
        require(
            validate_time(prepared_time, out / "prepared.dcd") == raw_times,
            "Raw/prepared time mismatch",
        )
        require(
            raw_time.dcd.atom_count
            == prepared_time.dcd.atom_count
            == report["evidence"]["atom_count"]
            and raw_time.dcd.frame_count
            == prepared_time.dcd.frame_count
            == report["evidence"]["frame_count"],
            "Frame/atom evidence mismatch",
        )
        elements = read_control(out / "elements.json", ElementControl)
        require(
            elements == authority["elements"], "Generated element authority changed"
        )
        draft = authority["draft"]
        files = {
            role: authority["inputs"][role]
            for role in (*SOURCE_ROLES, *SYSTEM_ROLES, "trajectory_path")
        }
        for role, name in (
            ("element_control", "elements.json"),
            ("time_control", "raw_time.json"),
            ("prepared_time_control", "prepared_time.json"),
            ("prepared_trajectory", "prepared.dcd"),
            ("pbc_evidence", "report.json"),
        ):
            files[role] = record(out / name, root)
        lineage = PreparedLineage(
            protocol=PROTOCOL,
            internal_mic=False,
            atom_order_preserved=True,
            frame_order_preserved=True,
            topology_sha256=files["topology_path"]["sha256"],
            raw_trajectory_sha256=files["trajectory_path"]["sha256"],
            prepared_trajectory_sha256=files["prepared_trajectory"]["sha256"],
            frame_count=raw_time.dcd.frame_count,
            atom_count=raw_time.dcd.atom_count,
            reviewer=reviewer,
            note=f"{review_note} Report SHA256: {report_sha256}. "
            "Explicit external preparation/atom-order review; no final QC decision.",
        )
        site = SiteReview(
            schema_version="egor.handoff.site_review.v1",
            trajectory_id=trajectory_id,
            raw_trajectory=files["trajectory_path"]["path"],
            prepared_trajectory=files["prepared_trajectory"]["path"],
            raw_time_control=files["time_control"]["path"],
            prepared_time_control=files["prepared_time_control"]["path"],
            pbc_evidence=files["pbc_evidence"]["path"],
            prepared_lineage=lineage,
        )
        binding = ProductionInputBinding.model_validate(
            dict(
                schema_version=draft["schema_version"],
                dataset_id=draft["dataset_id"],
                catalog_row=draft["catalog_row"],
                temporal_policy=draft["temporal_policy"],
                files=files,
                prepared_lineage=lineage,
            )
        )
        attempt.phase("integrity_verified")
        confirmation = dict(
            approved=True,
            reviewer=reviewer,
            review_note=review_note,
            report_sha256=report_sha256,
            inputs=report["inputs"],
            outputs=report["outputs"],
            confirmed_utc=utc_now(),
            final_qc_decision=None,
        )
        dump(attempt.directory / "confirmation.json", confirmation)
        dump(attempt.directory / "site_review.json", site.model_dump(mode="json"))
        binding_path = attempt.directory / "production_input_binding.json"
        commands = production_commands(
            authority["catalog"],
            root,
            production_out,
            binding_path,
            trajectory_id,
            min_free_bytes,
        )
        dump(attempt.directory / "commands.json", commands)
        check_records(report["inputs"], root)
        check_records(report["outputs"], root)
        require(
            source_identity(out / "report.json").sha256 == report_sha256,
            "Report changed during confirmation",
        )
    # Materialize the successful binding only after all guards, including clock order.
    attempt.publish(binding_path, binding.model_dump(mode="json"))
    return dict(
        status="binding_materialized",
        binding=str(binding_path),
        commands=commands,
        trajectory_pbc_qc_certified=False,
    )
