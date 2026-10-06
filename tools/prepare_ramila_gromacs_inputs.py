"""Approved full-axis bonded-fragment preparation into native precision-4 XTC."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

if __package__:
    from . import ramila_gromacs_runtime as rt
else:
    import ramila_gromacs_runtime as rt


def storage_budget(
    source_bytes: int,
    source_frames: int,
    atoms: int,
    prepared_frames: int,
    selected_samples: int,
    measured_bytes_per_frame: float,
) -> dict[str, int]:
    """Actual source/representation-derived estimate, including verification scratch."""
    estimated = int(prepared_frames * measured_bytes_per_frame * 1.15)
    scratch = atoms * 3 * 4 * prepared_frames
    # Contact output is sparse/data-dependent. Acceptance records observed output
    # sizes separately; this estimate is not a capacity guarantee.
    science = int(source_bytes / source_frames * selected_samples * 4)
    margin = int((estimated + scratch + science) * 0.15)
    return dict(
        raw_source_bytes=source_bytes,
        estimated_prepared_bytes=estimated,
        verification_scratch_bytes=scratch,
        expected_output_headroom_bytes=science,
        safety_headroom_bytes=margin,
        required_free_bytes=estimated + scratch + science + margin,
    )


def prepare(
    source: Path,
    output: Path,
    row: dict[str, Any],
    *,
    runtime: Path = rt.RUNTIME,
    technical_subset: bool = False,
) -> dict[str, Any]:
    import MDAnalysis as mda
    import numpy as np
    from MDAnalysis.lib.distances import calc_bonds
    from MDAnalysis.lib.formats.libmdaxdr import XTCFile
    from MDAnalysis.lib.mdamath import triclinic_box, triclinic_vectors

    # Reuse the accepted generic implementation verbatim; no new PBC fast path.
    if __package__:
        from .production_input_preparation import FragmentPreparation
    else:
        from production_input_preparation import FragmentPreparation

    source, output = source.resolve(), output.resolve()
    rt.require(
        not output.is_relative_to(source) and not source.is_relative_to(output),
        "Separate source/output roots required",
    )
    rt.require(not output.exists(), f"Preserve existing preparation attempt: {output}")
    rt.discover(source, [row])
    topology_path = rt.checked_file(source, row["tpr"]["path"])
    xtc_path = rt.checked_file(source, row["xtc_path"])
    source_identity = rt.file_identity(xtc_path)
    universe = mda.Universe(str(topology_path))
    rt.validate_topology(universe, row, runtime)
    axis = rt.scan_xtc(
        xtc_path, atom_count=len(universe.atoms), spec=row["dataset_spec"]
    )
    indexes = list(range(axis["frame_count"]))
    if technical_subset:
        rt.require(
            row["trajectory_id"] in rt.REPRESENTATIVES,
            "Technical subset restricted to two representatives",
        )
        spec = {
            **row["dataset_spec"],
            "temporal": {**row["dataset_spec"]["temporal"], "production_end_ns": 8.0},
        }
        plan = rt.sampling_plan(tuple(axis["times_ps"]), spec)
        rt.require(
            plan.requested_sample_count == len(plan.selected_samples) == 16,
            "Technical interval must resolve all 16 samples",
        )
        indexes = [s.source_frame_index for s in plan.selected_samples]
    authority = rt.load_authority(runtime)
    budget = storage_budget(
        source_identity["size_bytes"],
        axis["frame_count"],
        len(universe.atoms),
        len(indexes),
        axis["sampling_plan"]["sampled_frame_count"],
        authority["representation_bytes_per_frame"],
    )
    existing = output.parent
    while not existing.exists():
        existing = existing.parent
    free = shutil.disk_usage(existing).free
    rt.require(
        free >= budget["required_free_bytes"],
        f"Insufficient storage BEFORE preparation: free={free}, budget={budget}",
    )
    output.mkdir(parents=True)
    rt.dump(
        output / "storage_budget.json",
        dict(**budget, free_bytes_before=free, filesystem=str(existing)),
    )
    rt.dump(output / "source_axis.json", axis)
    rt.dump(
        output / "source_binding.json",
        dict(
            trajectory_id=row["trajectory_id"],
            source_root=str(source),
            output_root=str(output),
            source_xtc=source_identity,
            lightweight=rt.lightweight(row),
            purpose="technical_subset" if technical_subset else "full_axis_preparation",
            biological_annotation_authority="PENDING",
        ),
    )
    universe.load_new(
        np.zeros((1, len(universe.atoms), 3), dtype=np.float32),
        format=mda.coordinates.memory.MemoryReader,
    )
    protein = universe.select_atoms("protein")
    fragments = FragmentPreparation(universe)
    prepared_path = output / "prepared.xtc"
    scratch_path = output / "verification_coordinates.float32"
    # This scratch is on OUTPUT_ROOT, never implicitly on C:/WSL ext4.
    started = time.perf_counter()
    frame_evidence = []
    with (
        XTCFile(str(xtc_path), "r") as reader,
        scratch_path.open("xb") as scratch,
        mda.Writer(
            str(prepared_path), n_atoms=len(universe.atoms), precision=4
        ) as writer,
    ):
        reader.set_offsets(np.array(axis["offsets"], dtype=np.int64))
        for n, i in enumerate(indexes):
            reader.seek(i)
            frame = reader.read()
            ts = universe.trajectory.ts
            ts.positions = frame.x * 10
            ts.dimensions = triclinic_box(*(frame.box * 10))
            ts.time = float(frame.time)
            ts.data["step"] = int(frame.step)
            rt.require(
                np.isfinite(ts.positions).all(),
                f"Nonfinite source coordinates at frame {i}",
            )
            rt.require(ts.time == axis["times_ps"][i], "Changed source time/order")
            original_bond_lengths = calc_bonds(
                ts.positions[fragments.bonds[:, 0]],
                ts.positions[fragments.bonds[:, 1]],
                box=ts.dimensions,
            )
            fragments.unwrap()
            vectors = triclinic_vectors(ts.dimensions)
            ts.positions += vectors.sum(axis=0) / 2 - protein.center_of_geometry()
            fragments.wrap()
            xyz = np.ascontiguousarray(ts.positions, dtype=np.float32)
            scratch.write(xyz.tobytes())
            # Check complete-fragment representation and protein center, retaining
            # observed cells; these facts do not imply biological annotation.
            centers = universe.atoms.center_of_geometry(compound="fragments")
            frac = centers @ np.linalg.inv(vectors)
            center_error = float(
                np.max(np.abs(protein.center_of_geometry() - vectors.sum(axis=0) / 2))
            )
            rt.require(
                center_error <= 0.001
                and frac.min() >= -1e-5
                and frac.max() <= 1 + 1e-5,
                f"PBC representation failed at source frame {i}",
            )
            direct_bond_lengths = calc_bonds(
                ts.positions[fragments.bonds[:, 0]],
                ts.positions[fragments.bonds[:, 1]],
            )
            bond_error = float(
                np.max(np.abs(original_bond_lengths - direct_bond_lengths))
            )
            writer.write(universe.atoms)
            frame_evidence.append(
                dict(
                    prepared_frame_index=n,
                    source_frame_index=i,
                    time_ps=ts.time,
                    cell=ts.dimensions.tolist(),
                    protein_center_error_A=center_error,
                    bond_representation_max_error_A=bond_error,
                    complete_fragment_fractional_min=float(frac.min()),
                    complete_fragment_fractional_max=float(frac.max()),
                )
            )
            if n % 100 == 0:
                print(
                    f"PREPARATION {row['trajectory_id']}: "
                    f"{n + 1}/{len(indexes)} frames",
                    flush=True,
                )
    max_error, cell_error = 0.0, 0.0
    with XTCFile(str(prepared_path), "r") as reader, scratch_path.open("rb") as scratch:
        rt.require(reader.n_atoms == len(universe.atoms), "Reopened atom count changed")
        reopened = 0
        for n, frame in enumerate(reader):
            rt.require(n < len(frame_evidence), "Extra prepared frame")
            expected = np.frombuffer(
                scratch.read(len(universe.atoms) * 12), dtype=np.float32
            ).reshape((-1, 3))
            error = float(np.max(np.abs(frame.x * 10 - expected)))
            max_error = max(max_error, error)
            evidence = frame_evidence[n]
            rt.require(
                float(frame.time) == evidence["time_ps"],
                "Reopened exact time/order changed",
            )
            cell_error = max(
                cell_error,
                float(
                    np.max(np.abs(triclinic_box(*(frame.box * 10)) - evidence["cell"]))
                ),
            )
            rt.require(
                error <= 0.001 and cell_error <= 0.001,
                "XTC:4 representation tolerance exceeded",
            )
            reopened += 1
        rt.require(
            reopened == len(indexes) and not scratch.read(1),
            "Reopened frame/order count mismatch",
        )
    rt.require(
        rt.file_identity(xtc_path) == source_identity,
        "Raw source changed during preparation",
    )
    rt.discover(source, [row])
    rt.dump(output / "frame_evidence.json", frame_evidence)
    result = dict(
        status="passed",
        trajectory_id=row["trajectory_id"],
        protocol=rt.PROTOCOL,
        internal_MIC=False,
        format="XTC:4",
        source_xtc=source_identity,
        prepared_xtc=rt.file_identity(prepared_path),
        source_frames=axis["frame_count"],
        prepared_frames=len(indexes),
        source_frame_indexes=indexes,
        full_axis_preserved=not technical_subset,
        preparation_purpose="technical_subset"
        if technical_subset
        else "full_axis_preparation",
        atom_order_preserved=True,
        frame_order_preserved=True,
        exact_time_identity=True,
        cells_preserved=True,
        max_coordinate_component_error_A=max_error,
        max_cell_component_error=cell_error,
        wall_seconds=time.perf_counter() - started,
        storage=budget,
        biological_annotation_authority="PENDING",
        implementation=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            mdanalysis=mda.__version__,
            preparation_script=rt.file_identity(Path(__file__)),
            fragment_script=rt.file_identity(
                Path(inspect.getfile(FragmentPreparation))
            ),
        ),
        protein_integrity_observations=dict(
            protein_atom_identity_sha256=hashlib.sha256(
                np.asarray(protein.indices, dtype="<i8").tobytes()
            ).hexdigest(),
            protein_fragment_ids=[
                int(i) for i in np.unique(fragments.fragment_ids[protein.indices])
            ],
            protein_remains_broken=None,
            assessment_source=None,
        ),
    )
    rt.dump(output / "preparation_complete.json", result)
    publish_preparation_integrity(source, output, row)
    scratch_path.unlink()  # Only this attempt's successful verification scratch.
    return result


def publish_preparation_integrity(
    source: Path,
    preparation: Path,
    row: dict[str, Any],
) -> Path:
    from mania.dataset_identity import DatasetTrajectoryIdentity
    from mania.preprocessing.protein_integrity_observations import (
        normalize_preparation_observations,
        write_protein_integrity,
    )
    from mania.preprocessing.trajectory_rmsd_io import bind_file

    identity = DatasetTrajectoryIdentity.model_validate(row["dataset_spec"]["identity"])
    bindings = {
        "topology": bind_file(source / row["tpr"]["path"], "source:topology"),
        "raw_trajectory": bind_file(source / row["xtc_path"], "source:raw_trajectory"),
        "prepared_trajectory": bind_file(
            preparation / "prepared.xtc", "source:prepared_trajectory"
        ),
    }
    evidence = normalize_preparation_observations(
        identity,
        preparation / "preparation_complete.json",
        preparation / "frame_evidence.json",
        source_bindings=bindings,
        report_portable_path="evidence/producer/preparation_report/preparation_complete.json",
    )
    path = preparation / "protein_integrity_observations.json"
    write_protein_integrity(path, evidence)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("trajectory_id", choices=rt.SELECTIONS)
    parser.add_argument("--developer-technical-subset", action="store_true")
    args = parser.parse_args(argv)
    try:
        row = rt.select(rt.load_authority(), (args.trajectory_id,))[0]
        result = prepare(
            args.source_root,
            args.output_root,
            row,
            technical_subset=args.developer_technical_subset,
        )
        print(json_summary(result))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def json_summary(value: Any) -> str:
    import json

    return json.dumps(value, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
