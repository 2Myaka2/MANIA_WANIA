"""One-trajectory Ramila execution with immutable sources and exact offline reuse."""

from __future__ import annotations

import argparse
import json
import os
import sys
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
    from . import prepare_ramila_gromacs_inputs as prep
    from . import ramila_gromacs_runtime as rt
    from . import ramila_gromacs_source_attestation as attestation
else:
    import prepare_ramila_gromacs_inputs as prep
    import ramila_gromacs_runtime as rt
    import ramila_gromacs_source_attestation as attestation


def init(
    source: Path, output: Path, *, runtime: Path = rt.RUNTIME, input_fn=input
) -> dict[str, Any]:
    source, output = source.resolve(), output.resolve()
    rt.require(
        not output.is_relative_to(source) and not source.is_relative_to(output),
        "Separate source/output roots required",
    )
    authority = rt.load_authority(runtime)
    rows = rt.select(authority, rt.SELECTIONS)
    rt.discover(source, rows)  # All 12 final XTCs required before approval.
    path = output / "source_attestation.json"
    if path.exists():
        attestation.verify(path, source, rows, runtime=runtime)
        return dict(status="source_approval_reused", output_root=str(output))
    for row in rows:
        print(
            f"{row['trajectory_id']} -> XTC {row['xtc_path']} "
            f"-> TPR {row['tpr']['path']} "
            f"-> MDP {row['mdp']['path']} -> LOGs {[f['path'] for f in row['logs']]} "
            f"-> additional TPRs {[f['path'] for f in row['additional_tprs']]}"
        )
    print(attestation.STATEMENT)
    print(
        "Scope: source_run_correspondence_only. PBC, prepared coordinates, "
        "contacts and final QC are automatic/separate checks."
    )
    reviewer = input_fn("Reviewer: ").strip()
    note = input_fn("Review note: ").strip()
    approve = input_fn("Approve? y/N: ").strip()
    attestation.save(
        path,
        source,
        rows,
        reviewer=reviewer,
        review_note=note,
        approve=approve,
        runtime=runtime,
    )
    return dict(status="source_approved", output_root=str(output))


def select_ids(selector: str) -> tuple[str, ...]:
    if selector in rt.SELECTIONS:
        return (selector,)
    if selector in ("wt", "t330m", "all"):
        return tuple(
            t
            for t in rt.SELECTIONS
            if selector == "all" or t.startswith(f"gromacs_{selector}_")
        )
    raise ValueError("Unknown trajectory/variant selection")


def tree_digests(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): rt.file_identity(p)["sha256"]
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def next_attempt(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    n = 1
    while (parent / f"attempt_{n:04d}").exists():
        n += 1
    return parent / f"attempt_{n:04d}"


def verify_preparation(
    path: Path, source: Path, row: dict[str, Any], *, technical: bool
) -> dict[str, Any]:
    report = rt.read_json(path / "preparation_complete.json")
    rt.require(
        report["status"] == "passed"
        and report["trajectory_id"] == row["trajectory_id"],
        "Incomplete/wrong preparation",
    )
    rt.require(
        report["protocol"] == rt.PROTOCOL
        and report["format"] == "XTC:4"
        and report["internal_MIC"] is False,
        "Wrong preparation protocol",
    )
    rt.require(
        technical or report["full_axis_preserved"] is True,
        "Technical subset is not production preparation",
    )
    rt.require(
        report["source_xtc"] == rt.file_identity(source / row["xtc_path"]),
        "Preparation raw source changed",
    )
    rt.require(
        report["prepared_xtc"] == rt.file_identity(path / "prepared.xtc"),
        "Prepared trajectory changed",
    )
    for field in (
        "atom_order_preserved",
        "frame_order_preserved",
        "exact_time_identity",
        "cells_preserved",
    ):
        rt.require(report[field] is True, f"Preparation gate failed: {field}")
    rt.require(
        report["max_coordinate_component_error_A"] <= 0.001
        and report["max_cell_component_error"] <= 0.001,
        "Representation error",
    )
    binding = rt.read_json(path / "source_binding.json")
    rt.require(
        binding["source_root"] == str(source)
        and binding["lightweight"] == rt.lightweight(row),
        "Preparation source binding changed",
    )
    return report


def manifest_for(
    source: Path,
    preparation: Path,
    root: Path,
    row: dict[str, Any],
    *,
    technical: bool,
    runtime: Path,
):
    from mania.dataset_identity import DatasetTrajectorySpec
    from mania.preprocessing.input_manifest import (
        PreprocessingInputManifest,
        TrajectoryInputConfig,
    )
    from mania.preprocessing.temporal_policy import PreprocessingTemporalPolicy

    spec = row["dataset_spec"]
    if technical:
        spec = {
            **spec,
            "temporal": {
                **spec["temporal"],
                "production_start_ns": 5.0,
                "production_end_ns": 8.0,
            },
        }
    return PreprocessingInputManifest(
        output_root=root / "preprocessing",
        temporal_policy=PreprocessingTemporalPolicy(
            schema_version="mania.preprocessing_temporal_policy.v0.1",
            boundary_profile="mania.window_boundaries.inclusive.v1",
        ),
        conditions=(
            TrajectoryInputConfig(
                condition=spec["identity"]["condition"],
                topology_path=source / row["tpr"]["path"],
                trajectory_paths=(preparation / "prepared.xtc",),
                dataset_spec=DatasetTrajectorySpec.model_validate(
                    {key: spec[key] for key in ("identity", "temporal")}
                ),
                canonical_residue_mapping_path=runtime / row["canonical_mapping_path"],
                molecular_partner_metadata_path=runtime / row["partner_metadata_path"],
                metadata={"ramila_biological_annotation_authority": "PENDING"},
            ),
        ),
    )


def validate_and_replay(
    root: Path, manifest, row: dict[str, Any], runtime: Path
) -> dict[str, Any]:
    from mania.artifact_inventory_io import read_artifact_inventory
    from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
    from mania.canonical_window_tables import (
        DatasetCanonicalResidueMappingBinding,
        DatasetCanonicalResidueMappingBindings,
    )
    from mania.canonical_window_tables_io import (
        write_canonical_protein_edge_window_csv,
        write_canonical_protein_glycan_window_csv,
        write_canonical_protein_lipid_window_csv,
    )
    from mania.preprocessing.physical_time_execution_io import (
        read_preprocessing_temporal_execution,
    )
    from mania.preprocessing.protein_edge_window_table_io import (
        write_dataset_protein_edge_window_csv,
    )
    from mania.preprocessing.specialized_contact_window_tables_io import (
        write_protein_glycan_window_csv,
        write_protein_lipid_window_csv,
    )
    from mania.preprocessing.window_replay import replay_window_tables
    from mania.run_provenance_io import read_run_provenance
    from mania.validation import validate_run_artifacts

    science = root / "preprocessing"
    condition = manifest.conditions[0]
    prefix = "input:condition:0001:"
    mappings = {
        "input:manifest": root / "inputs/preprocessing.json",
        prefix + "topology": condition.topology_path,
        prefix + "trajectory:0001": condition.trajectory_paths[0],
        prefix
        + "molecular_partner_metadata": condition.molecular_partner_metadata_path,
        "input:canonical_residue_mapping:0001": (
            condition.canonical_residue_mapping_path
        ),
    }
    inventory = read_artifact_inventory(science / "artifact_inventory.json")
    rt.require(
        {e.artifact_id for e in inventory.artifacts if e.direction == "input"}
        == set(mappings),
        "Unexpected stage input bindings",
    )
    report = validate_run_artifacts(
        science, scope="preprocessing", input_artifact_paths=mappings
    )
    rt.require(
        report.status == "passed" and report.complete and not report.unsupported_count,
        "Strict artifact validation failed",
    )
    rt.require(
        read_run_provenance(science / "run_provenance.json").status == "completed",
        "Science incomplete",
    )
    temporal = read_preprocessing_temporal_execution(
        science / "temporal_execution.json"
    )
    key = manifest.conditions[0].dataset_spec.identity.replica_key
    bindings = DatasetCanonicalResidueMappingBindings(
        (
            DatasetCanonicalResidueMappingBinding(
                *key,
                read_canonical_residue_mapping(runtime / row["canonical_mapping_path"]),
            ),
        )
    )
    replayed = replay_window_tables(science, temporal, mapping_bindings=bindings)
    target = next_attempt(root / "offline_replay")
    writers = (
        (write_dataset_protein_edge_window_csv, replayed.protein),
        (write_protein_lipid_window_csv, replayed.lipid),
        (write_protein_glycan_window_csv, replayed.glycan),
        (write_canonical_protein_edge_window_csv, replayed.canonical_protein),
        (write_canonical_protein_lipid_window_csv, replayed.canonical_lipid),
        (write_canonical_protein_glycan_window_csv, replayed.canonical_glycan),
    )
    files = []
    for writer, table in writers:
        result = writer(table, target)
        rt.require(result.passed, "Offline replay CSV writing failed")
        filename = result.output_path.name
        rt.require(
            (target / filename).read_bytes() == (science / filename).read_bytes(),
            f"Offline replay mismatch: {filename}",
        )
        files.append(filename)
    plan = temporal.bindings[0].sampling_plan
    rt.require_time_qc(plan)
    windows = temporal.bindings[0].window_plan.windows
    return dict(
        validation=report.to_dict(),
        replay="PASS",
        byte_identical_replay_files=files,
        expected_samples=plan.requested_sample_count,
        resolved_samples=plan.sampled_frame_count,
        missing_samples=plan.missing_sample_count,
        windows=[
            dict(
                start_ns=w.requested_start_ns,
                end_ns=w.requested_end_ns,
                expected=w.requested_sample_count,
                resolved=w.sampled_frame_count,
                source_frame_indexes=list(w.source_frame_indexes),
            )
            for w in windows
        ],
        biological_annotation_authority="PENDING",
        annotated_output_readiness="PENDING",
    )


def run_one(
    source: Path,
    output: Path,
    trajectory_id: str,
    *,
    technical: bool = False,
    developer: bool = False,
    technical_subset: bool = False,
    prepared_directory: Path | None = None,
    runtime: Path = rt.RUNTIME,
) -> dict[str, Any]:
    source, output = source.resolve(), output.resolve()
    rt.require(
        not output.is_relative_to(source) and not source.is_relative_to(output),
        "Separate source/output roots required",
    )
    rt.require(
        not technical_subset or (technical and developer),
        "Subset preparation requires developer technical mode",
    )
    rt.require(
        not developer or (technical and trajectory_id in rt.REPRESENTATIVES),
        "Developer mode restricted to representative technical tests",
    )
    authority = rt.load_authority(runtime)
    row = rt.select(authority, (trajectory_id,))[0]
    rt.discover(source, [row])
    if developer:
        snapshot = attestation.capture(source, [row])
        source_record = dict(
            mode="developer_technical_only",
            human_source_approval=False,
            sources=snapshot,
        )
    else:
        approval = attestation.verify(
            output / "source_attestation.json",
            source,
            rt.select(authority, rt.SELECTIONS),
            runtime=runtime,
        )
        source_record = dict(
            mode="approved_production", attestation_sha256=approval["payload_sha256"]
        )
    # Exclusive per-trajectory directory ownership; no flock, hard links or SLURM.
    parent = (
        output
        / ("technical_validation" if technical else "trajectories")
        / trajectory_id
    )
    parent.mkdir(parents=True, exist_ok=True)
    lock = parent / ".active"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError(
            f"Active/incomplete ownership preserved: {lock}; "
            "inspect its attempt before retry"
        ) from exc
    try:
        request = dict(
            trajectory_id=trajectory_id,
            source_root=str(source),
            output_root=str(output),
            source_record=source_record,
            dataset_spec=row["dataset_spec"],
            runtime_inventory=rt.runtime_inventory(runtime),
            repository_head=attestation.repository_head(),
            purpose="technical_validation"
            if technical
            else "individual_trajectory_science",
            production_eligible=not technical,
            biological_annotation_authority="PENDING",
        )
        for candidate in sorted(parent.glob("attempt_*")):
            if (candidate / "science_complete.json").is_file():
                rt.require(
                    rt.read_json(candidate / "request.json") == request,
                    "Changed source/runtime request forbids completed reuse",
                )
                completion = rt.read_json(candidate / "science_complete.json")
                rt.require(
                    prepared_directory is None
                    or Path(completion["preparation_root"])
                    == prepared_directory.resolve(),
                    "Explicit preparation differs from completed result; "
                    "use a fresh OUTPUT_ROOT",
                )
                rt.require(
                    completion["artifacts"]
                    == tree_digests(candidate / "preprocessing"),
                    "Completed artifacts changed",
                )
                preparation = Path(completion["preparation_root"])
                verify_preparation(preparation, source, row, technical=technical)
                manifest = manifest_for(
                    source,
                    preparation,
                    candidate,
                    row,
                    technical=technical,
                    runtime=runtime,
                )
                checks = validate_and_replay(candidate, manifest, row, runtime)
                return dict(
                    status="technical_complete" if technical else "science_complete",
                    reused=True,
                    output=str(candidate),
                    production_eligible=not technical,
                    **checks,
                )
        root = next_attempt(parent)
        root.mkdir()
        rt.dump(root / "request.json", request)
        if prepared_directory is not None:
            preparation = prepared_directory.resolve()
            verify_preparation(preparation, source, row, technical=technical)
        else:
            preparation = root / "preparation"
            prep.prepare(
                source,
                preparation,
                row,
                runtime=runtime,
                technical_subset=technical_subset,
            )
        manifest = manifest_for(
            source, preparation, root, row, technical=technical, runtime=runtime
        )
        rt.dump(root / "inputs/preprocessing.json", manifest.model_dump(mode="json"))
        from mania.cli import run_production_preprocessing

        context = (
            dict(
                purpose="technical_validation",
                production_eligible=False,
                start_ns=5.0,
                end_ns=8.0,
            )
            if technical
            else None
        )
        run_production_preprocessing(
            root / "inputs/preprocessing.json",
            root / "preprocessing",
            row["dataset_spec"]["identity"]["condition"],
            technical_context=context,
        )
        checks = validate_and_replay(root, manifest, row, runtime)
        rt.require(
            attestation.capture(source, [row])
            == (
                snapshot
                if developer
                else [
                    r
                    for r in approval["trajectories"]
                    if r["trajectory_id"] == trajectory_id
                ]
            ),
            "Source changed during contacts",
        )
        verify_preparation(preparation, source, row, technical=technical)
        rt.dump(root / "acceptance.json", checks)
        rt.dump(
            root / "science_complete.json",
            dict(
                artifacts=tree_digests(root / "preprocessing"),
                preparation_root=str(preparation),
                purpose=request["purpose"],
                production_eligible=not technical,
            ),
        )
        return dict(
            status="technical_complete" if technical else "science_complete",
            reused=False,
            output=str(root),
            production_eligible=not technical,
            **checks,
        )
    finally:
        lock.rmdir()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("init", "run"))
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("selector", nargs="?", default="all")
    parser.add_argument("--technical", action="store_true")
    parser.add_argument("--developer-representative", action="store_true")
    parser.add_argument("--developer-technical-subset", action="store_true")
    parser.add_argument("--prepared-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "init":
            rt.require(
                not args.technical
                and not args.developer_representative
                and not args.developer_technical_subset
                and args.prepared_directory is None,
                "Init requires normal all-12 source review",
            )
            result = init(args.source_root, args.output_root)
        else:
            ids = select_ids(args.selector)
            rt.require(
                not args.developer_representative
                or (args.technical and set(ids) <= set(rt.REPRESENTATIVES)),
                "Developer selection restricted to representative technical tests",
            )
            rt.require(
                args.prepared_directory is None or len(ids) == 1,
                "Explicit preparation selects one trajectory",
            )
            results = []
            for tid in ids:
                results.append(
                    run_one(
                        args.source_root,
                        args.output_root,
                        tid,
                        technical=args.technical,
                        developer=args.developer_representative,
                        technical_subset=args.developer_technical_subset,
                        prepared_directory=args.prepared_directory,
                    )
                )
            result = dict(
                status="completed", trajectories=results, replica_aggregation="NOT_RUN"
            )
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
