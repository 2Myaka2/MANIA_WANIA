"""Synthetic full production requests, protected evidence, and existing science APIs."""

import csv
import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_biological_annotations import metadata as biology
from test_cli_preprocessing_graph_workflow import FIXED_IDENTITY
from test_dataset_hard_qc import artifact, inputs, raw
from test_dataset_review_qc import review
from test_namd_authority import config_log, helper, time_control
from test_preprocessing_molecular_partner_metadata_io import metadata as partners
from test_preprocessing_pbc_observation_integration import Runtime
from test_preprocessing_trajectory_contacts_compute_condition import (
    FakeAtom,
    FakeResidue,
)
from test_production_catalog import CATALOG, EGOR_IDS, technical_file

import mania.cli as cli
import mania.production_run as production
from mania.biological_annotations_io import write_dataset_system_biological_annotations
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.canonical_residue_mapping_io import write_canonical_residue_mapping
from mania.canonical_window_tables import DatasetCanonicalResidueMappingBinding
from mania.canonical_window_tables_io import read_canonical_protein_edge_window_csv
from mania.dataset_hard_qc import evaluate_replica_hard_qc
from mania.dataset_qc_evidence_io import (
    ReplicaHardQCEvidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import (
    DatasetQCManifest,
    DatasetQCWorkflowReplica,
    QCManualReviewResolution,
)
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_review_qc import evaluate_dataset_review_qc
from mania.preprocessing import trajectory_manifest_loader as loader
from mania.preprocessing.molecular_partner_metadata_io import (
    write_molecular_partner_metadata,
)
from mania.preprocessing.namd_authority import DCDIdentity, RawFrameTime, write_control
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
)
from mania.production_catalog import ProductionError, load_production_catalog
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_aggregation_manifest_io import write_replica_aggregation_manifest
from mania.replica_specialized_aggregation import (
    ReplicaSpecializedPartnerCorrespondenceMember,
    SpecializedPartnerCorrespondence,
    SpecializedPartnerCorrespondences,
)


def bound_file(path, data_root):
    return {
        "path": path.relative_to(data_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": production.file_digest(path),
    }


def make_case(root, monkeypatch, trajectory_id=EGOR_IDS[0]):
    data_root, output = root / "data", root / "out"
    source = data_root / trajectory_id
    source.mkdir(parents=True)
    monkeypatch.setenv("MANIA_DATA_ROOT", str(data_root))
    for module in (
        "mania.cli",
        "mania.dataset_qc_run",
        "mania.replica_aggregation_run",
    ):
        monkeypatch.setattr(module + ".get_software_identity", lambda: FIXED_IDENTITY)
    catalog = load_production_catalog(CATALOG)
    selected = catalog.trajectory(trajectory_id)
    psf = source / "input.psf"
    text = "PSF EXT\n\n         1 !NTITLE\n REMARKS synthetic\n\n         4 !NATOM\n"
    for i, name in enumerate(("ALA", "GLY", "XXX", "YYY"), 1):
        text += (
            f"{i:10d} {'PROA':<8} {i:<8} {name:<8} {'CA':<8} "
            f"{'C':<8} {0.0:14.6f} {12.0:14.4f} {0:8d}\n"
        )
    psf.write_text(text + "\n         1 !NBOND: bonds\n         1         4\n")
    toppar = source / "toppar"
    toppar.mkdir()
    (toppar / "types.rtf").write_text("MASS -1 C 12 C\n")
    elements = helper.build_elements(psf, toppar, ())
    element_path = source / "elements.json"
    write_control(element_path, elements)
    config, log = config_log(source, 1000)
    raw_dcd, prepared_dcd = source / "raw.dcd", source / "prepared.dcd"
    raw_dcd.write_bytes(b"Synthetic source only; no real coordinates")
    prepared_dcd.write_bytes(b"Synthetic prepared source; fake runtime below")
    times = []
    for path in (raw_dcd, prepared_dcd):
        raw_identity = DCDIdentity(
            path=str(path),
            size_bytes=path.stat().st_size,
            atom_count=4,
            frame_count=1000,
            istart=50000,
            nsavc=50000,
            delta=0.04090965911746025,
            dt_ps=100.00000029814058,
            unit_cell=True,
            remarks="FILENAME=original.dcd CREATED BY NAMD",
            observed_times=(
                RawFrameTime(frame=0, time_ps=100.00000029814058),
                RawFrameTime(frame=999, time_ps=100000.00029814057),
            ),
        )
        control_path = source / (path.stem + "_time.json")
        write_control(control_path, time_control(config, log, raw_identity))
        times.append(control_path)
    mapping = CanonicalResidueMappingTable(
        (
            CanonicalResidueMappingRecord(
                "namd", "PROA", "1", "ALA", 311, "GLN", "mapped"
            ),
            CanonicalResidueMappingRecord(
                "namd", "PROA", "2", "GLY", 330, "THR", "mapped"
            ),
        )
    )
    mapping_path = source / "mapping.json"
    assert write_canonical_residue_mapping(mapping, mapping_path).passed
    annotations = source / "annotations.json"
    assert write_dataset_system_biological_annotations(
        biology(
            dataset_id=selected.spec.identity.dataset_id,
            system_id=selected.group_id,
        ),
        annotations,
    ).passed
    partner_path = source / "partners.json"
    assert write_molecular_partner_metadata(partners(), partner_path).passed
    box = source / "input.xsc"
    box.write_text("Synthetic cell evidence\n")
    pbc = source / "pbc.txt"
    pbc.write_text(
        "Synthetic reviewer: full atom/frame order preserved; external preparation.\n"
    )
    paths = dict(
        zip(
            (
                "topology_path",
                "trajectory_path",
                "config_path",
                "log_path",
                "box_path",
                "element_control",
                "time_control",
                "canonical_mapping",
                "biological_annotations",
                "partner_metadata",
                "prepared_trajectory",
                "prepared_time_control",
                "pbc_evidence",
            ),
            (
                psf,
                raw_dcd,
                config,
                log,
                box,
                element_path,
                times[0],
                mapping_path,
                annotations,
                partner_path,
                prepared_dcd,
                times[1],
                pbc,
            ),
            strict=True,
        )
    )
    payload = {
        "schema_version": "mania.production_input_binding.v0.1",
        "dataset_id": selected.spec.identity.dataset_id,
        "catalog_row": selected.row,
        "temporal_policy": catalog.temporal_policy.model_dump(),
        "files": {k: bound_file(v, data_root) for k, v in paths.items()},
        "prepared_lineage": {
            "protocol": (
                "unwrap_bonded_fragments_center_protein_wrap_complete_fragments"
            ),
            "internal_mic": False,
            "atom_order_preserved": True,
            "frame_order_preserved": True,
            "topology_sha256": production.file_digest(psf),
            "raw_trajectory_sha256": production.file_digest(raw_dcd),
            "prepared_trajectory_sha256": production.file_digest(prepared_dcd),
            "frame_count": 1000,
            "atom_count": 4,
            "reviewer": "Synthetic reviewer",
            "note": "Synthetic authority only",
        },
    }
    binding = source / "binding.json"
    binding.write_text(json.dumps(payload))
    return SimpleNamespace(
        catalog=CATALOG,
        selected=selected,
        data_root=data_root,
        output=output,
        binding=binding,
        paths=paths,
        payload=payload,
        mapping=mapping,
    )


def install_runtime(monkeypatch):
    runtimes = []

    def load(runtime_input, *, namd_authority):
        assert namd_authority.elements.is_file() and namd_authority.time.is_file()
        runtime = Runtime([None] * 1000)
        runtime.trajectory.n_frames = 1000
        for i, frame in enumerate(runtime.trajectory.frames):
            frame.time = float((i + 1) * 100)
        runtime.residues.extend(
            [
                FakeResidue("XXX", 3, [FakeAtom(position=(2, 0, 0))]),
                FakeResidue("YYY", 4, [FakeAtom(position=(1, 0, 0))]),
            ]
        )
        for i, residue in enumerate(runtime.residues):
            residue.ix = i
            for atom in residue.atoms:
                atom.index = i
        runtime.bonds = [SimpleNamespace(indices=(0, 3))]
        runtime.select_atoms = lambda selection: SimpleNamespace(
            residues=runtime.residues[:2]
        )
        runtimes.append(runtime)
        return PreprocessingConditionLoadResult(
            runtime_input.condition_name,
            runtime_input,
            PreprocessingConditionRuntime(
                runtime_input.condition_name,
                runtime,
                "synthetic",
                runtime_input.topology_path,
                runtime_input.trajectory_paths,
            ),
            status="loaded",
        )

    monkeypatch.setattr(loader, "load_single_condition_runtime", load)
    return runtimes


def run_case(case, **kwargs):
    return production.run_production_trajectory(
        case.catalog,
        case.selected.trajectory_id,
        case.output,
        input_binding=case.binding,
        min_free_bytes=1,
        **kwargs,
    )


@pytest.mark.parametrize("trajectory_id", EGOR_IDS)
def test_all_nine_preflight_explicit_rebinding(tmp_path, monkeypatch, trajectory_id):
    case = make_case(tmp_path, monkeypatch, trajectory_id)
    result = production.preflight_trajectory(
        case.catalog,
        trajectory_id,
        case.output,
        input_binding=case.binding,
    )
    assert result.to_dict()["status"] == "preflight_passed"
    assert result.to_dict()["trajectory_pbc_qc_certified"] is False
    assert not case.output.exists()


@pytest.mark.parametrize(
    "damage",
    [
        "cross_group",
        "escape",
        "symlink",
        "collision",
        "disk",
        "stale",
        "wrong_control",
        "lineage",
        "time",
        "legacy",
        "five_frames",
        "missing",
        "existing",
    ],
)
@pytest.mark.parametrize("technical", [False, True])
def test_preflight_rejects_before_any_runtime(tmp_path, monkeypatch, damage, technical):
    case = make_case(tmp_path, monkeypatch)
    payload = case.payload
    output = case.output
    if damage == "cross_group":
        payload["catalog_row"]["system_id"] = "different"
    elif damage == "escape":
        payload["files"]["topology_path"]["path"] = "../outside.psf"
    elif damage == "symlink":
        target = case.paths["topology_path"]
        external = tmp_path / "outside.psf"
        external.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(external)
    elif damage == "collision":
        output = case.data_root / "outputs"
    elif damage == "disk":
        monkeypatch.setattr(
            production.shutil, "disk_usage", lambda p: SimpleNamespace(free=0)
        )
    elif damage == "stale":
        case.paths["element_control"].write_text("changed")
    elif damage == "wrong_control":
        path = case.paths["element_control"]
        data = json.loads(path.read_text())
        data["used_type_counts"]["C"] = 3
        path.write_text(json.dumps(data))
        payload["files"]["element_control"] = bound_file(path, case.data_root)
    elif damage == "lineage":
        payload["prepared_lineage"]["raw_trajectory_sha256"] = "0" * 64
    elif damage == "time":
        path = case.paths["prepared_time_control"]
        data = json.loads(path.read_text())
        data["scientific_times_ps"][0] = "0"
        path.write_text(json.dumps(data))
        payload["files"]["prepared_time_control"] = bound_file(path, case.data_root)
    elif damage == "legacy":
        payload["temporal_policy"]["boundary_profile"] = (
            "mania.window_boundaries.legacy.v1"
        )
    elif damage == "five_frames":
        payload["catalog_row"]["production_end_ns"] = "0.5"
    elif damage == "missing":
        case.paths["pbc_evidence"].unlink()
    elif damage == "existing":
        base = output / "technical_validation" if technical else output
        (base / "trajectories" / case.selected.trajectory_id).mkdir(parents=True)
    case.binding.write_text(json.dumps(payload))
    monkeypatch.setattr(
        cli, "run_production_preprocessing", Mock(side_effect=AssertionError)
    )
    with pytest.raises((ValueError, OSError)):
        production.run_production_trajectory(
            case.catalog,
            case.selected.trajectory_id,
            output,
            input_binding=case.binding,
            technical_manifest=technical_file(tmp_path) if technical else None,
            min_free_bytes=1,
        )
    cli.run_production_preprocessing.assert_not_called()


def test_egor_technical_subset_and_identical_resume(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    manifest = technical_file(tmp_path)
    original_binding = case.binding.read_bytes()
    runtimes = install_runtime(monkeypatch)
    result = run_case(case, technical_manifest=manifest)
    assert result["status"] == "technical_complete"
    assert result["purpose"] == "technical_validation"
    assert result["production_eligible"] is False
    root = Path(result["output"])
    assert root == case.output / "technical_validation/trajectories" / EGOR_IDS[0]
    assert (root / "technical_complete.json").is_file()
    assert not (root / "science_complete.json").exists()
    assert not (case.output / "trajectories").exists()
    temporal = read_preprocessing_temporal_execution(
        root / "preprocessing/temporal_execution.json"
    )
    binding = temporal.bindings[0]
    assert binding.sampling_plan.sampled_frame_count == 16
    windows = binding.window_plan.windows
    assert [(w.requested_start_ns, w.requested_end_ns) for w in windows] == [
        (5, 7),
        (6, 8),
    ]
    assert [w.requested_sample_count for w in windows] == [11, 11]
    assert [w.sampled_frame_count for w in windows] == [11, 11]
    assert all(w.right_endpoint_inclusive for w in windows)
    assert (
        len(set(windows[0].source_frame_indexes) & set(windows[1].source_frame_indexes))
        == 6
    )
    assert (
        binding.window_plan.boundary_profile == "mania.window_boundaries.inclusive.v1"
    )
    assert binding.dataset_spec.temporal.frame_stride_ps == 200
    request = json.loads((root / "request.json").read_text())
    assert request["binding"]["catalog_row"]["production_end_ns"] == "100"
    assert request["catalog_spec"]["temporal"]["production_end_ns"] == 100
    assert request["execution_spec"]["temporal"]["production_end_ns"] == 8
    assert request["technical_manifest_sha256"] == production.file_digest(manifest)
    assert case.binding.read_bytes() == original_binding
    before = production._tree_digests(root)
    assert run_case(case, technical_manifest=manifest, resume=True)["reused"]
    assert production._tree_digests(root) == before
    assert len(runtimes) == 1
    # A normal run still requests all 476 samples in its independent tree.
    normal = run_case(case)
    assert normal["status"] == "science_complete"
    full = read_preprocessing_temporal_execution(
        Path(normal["output"]) / "preprocessing/temporal_execution.json"
    )
    assert full.bindings[0].sampling_plan.sampled_frame_count == 476
    assert len(full.bindings[0].window_plan.windows) == 94
    assert production._tree_digests(root) == before


@pytest.mark.parametrize(
    "damage", ["interval", "bytes", "omitted", "saved_request", "provenance"]
)
def test_changed_technical_manifest_or_label_forbids_resume(
    tmp_path, monkeypatch, damage
):
    case = make_case(tmp_path, monkeypatch)
    manifest = technical_file(tmp_path)
    install_runtime(monkeypatch)
    root = Path(run_case(case, technical_manifest=manifest)["output"])
    if damage == "interval":
        technical_file(tmp_path, end_ns=9)
    elif damage == "bytes":
        manifest.write_text(manifest.read_text() + "\n")
    elif damage == "saved_request":
        path = root / "request.json"
        payload = json.loads(path.read_text())
        payload["technical_manifest"]["end_ns"] = 9
        path.write_text(json.dumps(payload))
    elif damage == "provenance":
        path = root / "preprocessing/run_provenance.json"
        payload = json.loads(path.read_text())
        del payload["resolved_configuration"]["technical_run"]
        path.write_text(json.dumps(payload))
    before = production._tree_digests(root)
    monkeypatch.setattr(
        cli, "run_production_preprocessing", Mock(side_effect=AssertionError)
    )
    with pytest.raises(ProductionError, match="[Tt]echnical"):
        run_case(
            case,
            technical_manifest=None if damage == "omitted" else manifest,
            resume=True,
        )
    cli.run_production_preprocessing.assert_not_called()
    assert production._tree_digests(root) == before


@pytest.mark.parametrize(
    "placement", ["isolated", "output_root", "copied", "preprocessing_only"]
)
def test_technical_outputs_cannot_assemble_as_production(
    tmp_path, monkeypatch, placement
):
    case = make_case(tmp_path, monkeypatch)
    install_runtime(monkeypatch)
    root = Path(run_case(case, technical_manifest=technical_file(tmp_path))["output"])
    output = case.output
    if placement == "output_root":
        output /= "technical_validation"
    elif placement in ("copied", "preprocessing_only"):
        target = output / "trajectories" / case.selected.trajectory_id
        shutil.copytree(root, target)
        if placement == "preprocessing_only":
            (target / "request.json").unlink()
            # A copied preprocessing tree must also be rejected at publication.
            with pytest.raises(ProductionError, match="Technical validation"):
                production.require_production_science(
                    target / "preprocessing/temporal_execution.json"
                )
    with pytest.raises((ProductionError, OSError)):
        production.assemble_production_group(
            case.catalog, case.selected.group_id, output
        )
    assert not (output / "groups").exists()


def test_completed_science_resume_and_manual_qc_independence(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    runtimes = install_runtime(monkeypatch)
    result = run_case(case)
    assert result["status"] == "science_complete" and not result["reused"]
    root = Path(result["output"])
    temporal = read_preprocessing_temporal_execution(
        root / "preprocessing/temporal_execution.json"
    )
    binding = temporal.bindings[0]
    assert binding.sampling_plan.sampled_frame_count == 476
    assert len(binding.window_plan.windows) == 94
    assert {w.requested_sample_count for w in binding.window_plan.windows} == {11}
    assert len(runtimes) == 1 and runtimes[0].trajectory.passes == 3
    before = production._tree_digests(root)
    monkeypatch.setattr(
        cli, "run_production_preprocessing", Mock(side_effect=AssertionError)
    )
    assert run_case(case, resume=True)["reused"] is True
    assert production._tree_digests(root) == before
    cli.run_production_preprocessing.assert_not_called()
    with pytest.raises(ProductionError, match="protected"):
        run_case(case)
    case.paths["pbc_evidence"].write_text("New authority, not an identical run")
    with pytest.raises(ProductionError, match="Stale"):
        run_case(case, resume=True)
    case.payload["files"]["pbc_evidence"] = bound_file(
        case.paths["pbc_evidence"], case.data_root
    )
    case.binding.write_text(json.dumps(case.payload))
    with pytest.raises(ProductionError, match="Changed"):
        run_case(case, resume=True)


@pytest.mark.parametrize("damage", ["missing_pair", "frame_time", "wrong_engine"])
def test_manifest_control_conflicts(tmp_path, monkeypatch, damage):
    case = make_case(tmp_path, monkeypatch)
    checked = production.preflight_trajectory(
        case.catalog,
        case.selected.trajectory_id,
        case.output,
        input_binding=case.binding,
    )
    payload = production._manifest(checked).model_dump(mode="json")
    if damage == "missing_pair":
        del payload["conditions"][0]["namd_time_control_path"]
    elif damage == "frame_time":
        payload["frame_time_ps"] = 100
    else:
        payload["conditions"][0]["dataset_spec"]["identity"]["engine"] = "gromacs"
    with pytest.raises(ValueError):
        production.PreprocessingInputManifest.model_validate(payload)


def test_missing_data_root_and_output_symlink(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    monkeypatch.delenv("MANIA_DATA_ROOT")
    with pytest.raises(ProductionError, match="MANIA_DATA_ROOT"):
        run_case(case)
    monkeypatch.setenv("MANIA_DATA_ROOT", str(case.data_root))
    case.output.symlink_to(case.data_root, target_is_directory=True)
    with pytest.raises(ProductionError, match="symlinks"):
        run_case(case)


def test_failed_stage_cannot_resume_or_overwrite(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "run_production_preprocessing",
        Mock(side_effect=ProductionError("interrupted")),
    )
    with pytest.raises(ProductionError, match="interrupted"):
        run_case(case)
    before = production._tree_digests(case.output)
    with pytest.raises((ValueError, OSError)):
        run_case(case, resume=True)
    assert cli.run_production_preprocessing.call_count == 1
    assert production._tree_digests(case.output) == before


def test_incomplete_validation_cannot_accept_science(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    install_runtime(monkeypatch)
    monkeypatch.setattr(
        production,
        "validate_run_artifacts",
        lambda *a, **k: SimpleNamespace(
            status="partial",
            complete=False,
            unsupported_count=0,
        ),
    )
    with pytest.raises(ProductionError, match="complete artifact"):
        run_case(case)
    assert not (
        case.output
        / "trajectories"
        / case.selected.trajectory_id
        / "science_complete.json"
    ).exists()


def group_case(root, monkeypatch, *, pending=False, specialized=True):
    cases = [make_case(root, monkeypatch, tid) for tid in EGOR_IDS[:3]]
    install_runtime(monkeypatch)
    for case in cases:
        run_case(case)
    science = [
        case.output / "trajectories" / case.selected.trajectory_id / "preprocessing"
        for case in cases
    ]
    temporals = [
        read_preprocessing_temporal_execution(p / "temporal_execution.json")
        for p in science
    ]
    p = cases[0].selected.spec.temporal
    groups = []
    for w in temporals[0].bindings[0].window_plan.windows:
        window = ReplicaAggregationWindowDefinition(
            w.window_id,
            w.window_index,
            p.production_start_ns,
            p.production_end_ns,
            w.requested_start_ns,
            w.requested_end_ns,
            True,
            2,
            1,
            50,
            "mania.window_boundaries.inclusive.v1",
        )
        identity = cases[0].selected.spec.identity
        spec = ReplicaAggregationGroupSpec(
            identity.dataset_id,
            identity.system_id,
            identity.engine,
            identity.variant_id,
            identity.condition,
            identity.disulfide_state,
            ("1", "2", "3"),
            window,
        )
        members = tuple(
            ReplicaAggregationMember(
                **case.selected.spec.identity.model_dump(),
                canonical_reference_id=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
                canonical_reference_sequence_sha256=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
                window=window,
                availability_status="available",
                availability_reason=None,
            )
            for case in cases
        )
        correspondences = []
        for kind in ("lipid", "glycan"):
            correspondences.append(
                SpecializedPartnerCorrespondences(
                    (
                        SpecializedPartnerCorrespondence(
                            f"{kind}-shared",
                            kind,
                            f"{kind.upper()}-X",
                            tuple(
                                ReplicaSpecializedPartnerCorrespondenceMember(
                                    *case.selected.spec.identity.replica_key,
                                    f"{kind}-one",
                                    f"{kind.upper()}-X",
                                )
                                for case in cases
                            ),
                        ),
                    )
                    if specialized
                    else ()
                )
            )
        groups.append(ReplicaAggregationWorkflowGroup(spec, members, *correspondences))
    control_root = cases[0].data_root / "qc"
    control_root.mkdir()
    template = ReplicaAggregationManifest(
        tuple(p / production._FAMILY_FILES["protein"] for p in science),
        tuple(p / production._FAMILY_FILES["lipid"] for p in science)
        if specialized
        else (),
        tuple(p / production._FAMILY_FILES["glycan"] for p in science)
        if specialized
        else (),
        tuple(groups),
    )
    template_path = control_root / "template.json"
    assert write_replica_aggregation_manifest(template, template_path).passed
    replicas = []
    for case, temporal, path in zip(cases, temporals, science, strict=True):
        identity = case.selected.spec.identity
        mapping = DatasetCanonicalResidueMappingBinding(
            *identity.replica_key, case.mapping
        )
        values = inputs(
            identity=identity,
            mapping_binding=mapping,
            required_source_keys=tuple(r.source_key for r in case.mapping.mappings),
            sampling_plan=temporal.bindings[0].sampling_plan,
            raw_integrity=raw(topology_atom_count=4, trajectory_atom_count=4),
            required_artifacts=(
                replace(
                    artifact(),
                    canonical_table=read_canonical_protein_edge_window_csv(
                        path / production._FAMILY_FILES["protein"]
                    ),
                ),
            ),
        )
        hard = ReplicaHardQCEvidence(**values)
        review_evidence = review(
            identity.replica_key, drift=pending, expected=94, engine="namd"
        )
        hard_path = Path(f"hard-{identity.replica_id}.json")
        review_path = Path(f"review-{identity.replica_id}.json")
        assert write_replica_hard_qc_evidence(hard, control_root / hard_path).passed
        assert write_replica_review_qc_evidence(
            review_evidence, control_root / review_path
        ).passed
        replicas.append(
            DatasetQCWorkflowReplica(
                *identity.replica_key, hard_path, review_path, None
            )
        )
    manifest = DatasetQCManifest(Path("template.json"), tuple(replicas))
    qc_path = control_root / "qc.json"
    assert write_dataset_qc_manifest(manifest, qc_path).passed
    return cases, qc_path, template


def test_three_replica_group_and_qc_pending_preserve_science(tmp_path, monkeypatch):
    cases, qc, _ = group_case(tmp_path, monkeypatch, pending=True)
    first = cases[0]
    science_before = production._tree_digests(first.output / "trajectories")
    missing = production.assemble_production_group(
        CATALOG, first.selected.group_id, first.output
    )
    assert missing["status"] == "blocked_qc"
    pending = production.assemble_production_group(
        CATALOG, first.selected.group_id, first.output, qc_manifest=qc
    )
    assert pending["status"] == "pending_review"
    assert not (Path(pending["output"]) / "aggregation").exists()
    control = production.read_dataset_qc_manifest(qc)
    resolved = []
    for replica in control.replicas:
        from mania.dataset_qc_evidence_io import read_replica_review_qc_evidence

        hard = production.read_replica_hard_qc_evidence(
            qc.parent / replica.hard_qc_evidence_path
        )
        review_input = read_replica_review_qc_evidence(
            qc.parent / replica.review_qc_evidence_path
        )
        from dataclasses import fields

        hard_result = evaluate_replica_hard_qc(
            **{f.name: getattr(hard, f.name) for f in fields(hard)}
        )
        finding = next(
            c
            for c in evaluate_dataset_review_qc((hard_result,), (review_input,))
            .evaluations[0]
            .checks
            if c.status == "review"
        )
        resolution = QCManualReviewResolution(
            "excluded" if replica.replica_id == "1" else "available",
            finding.reason_code,
            "Synthetic decision",
            tuple(e.evidence_id for e in finding.evidence),
            "Synthetic reviewer",
            "No real QC authority",
        )
        resolved.append(replace(replica, manual_resolution=resolution))
    assert write_dataset_qc_manifest(
        replace(control, replicas=tuple(resolved)), qc, overwrite=True
    ).passed
    result = production.assemble_production_group(
        CATALOG, first.selected.group_id, first.output, qc_manifest=qc
    )
    assert (
        result["status"] == "aggregation_complete"
        and result["output"] != pending["output"]
    )
    from mania.replica_aggregation_workflow import FAMILIES

    for family in FAMILIES:
        with (
            Path(result["output"]) / "aggregation" / family.filename
        ).open() as stream:
            rows = list(csv.DictReader(stream))
        assert rows
        assert {int(r["n_replicates_available"]) for r in rows} == {2}
        assert {float(r["mean_occupancy"]) for r in rows} == {1.0}
    assert production._tree_digests(first.output / "trajectories") == science_before
    accepted = production._tree_digests(Path(result["output"]))
    assert (
        production.assemble_production_group(
            CATALOG, first.selected.group_id, first.output, qc_manifest=qc
        )
        == result
    )
    assert production._tree_digests(Path(result["output"])) == accepted


@pytest.mark.parametrize(
    "damage", ["correspondence", "legacy", "cross_group", "missing_review"]
)
def test_group_authority_failures_preserve_science(tmp_path, monkeypatch, damage):
    cases, qc, template = group_case(tmp_path, monkeypatch)
    first = cases[0]
    before = production._tree_digests(first.output / "trajectories")
    if damage == "missing_review":
        (qc.parent / "review-1.json").unlink()
    else:
        data = json.loads((qc.parent / "template.json").read_text())
        if damage == "correspondence":
            data["groups"][0]["lipid_correspondences"]["correspondences"] = []
        elif damage == "legacy":
            data["groups"][0]["spec"]["window"]["boundary_profile"] = (
                "mania.window_boundaries.legacy.v1"
            )
        else:
            data["groups"][0]["spec"]["system_id"] = "wrong"
        (qc.parent / "template.json").write_text(json.dumps(data))
    with pytest.raises((ValueError, OSError)):
        production.assemble_production_group(
            CATALOG, first.selected.group_id, first.output, qc_manifest=qc
        )
    assert production._tree_digests(first.output / "trajectories") == before
