"""Real common orchestration with compact transfer, strict seals and offline replay."""

import json
import shutil
from types import SimpleNamespace

import pytest
from test_preprocessing_trajectory_rmsd import XYZ, mapped_universe, temporal_binding

from mania.canonical_residue_mapping_io import write_canonical_residue_mapping
from mania.cli import run_production_preprocessing
from mania.preprocessing.input_manifest import (
    PreprocessingInputManifest,
    TrajectoryInputConfig,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    MolecularPartnerMetadata,
    write_molecular_partner_metadata,
)
from mania.preprocessing.protein_integrity_observations import (
    normalize_preparation_observations,
    write_protein_integrity,
)
from mania.preprocessing.temporal_policy import PreprocessingTemporalPolicy
from mania.preprocessing.trajectory_rmsd_io import (
    atomic_json,
    bind_file,
    read_rmsd_evidence,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
)
from mania.production_handoff import (
    CONDITIONAL_AUTHORITIES,
    HandoffInputs,
    load_completed_handoff,
    publish_handoff,
    retain_handoff_inputs,
    validate_handoff_prerequisites,
)
from mania.validation import validate_run_artifacts


def handoff_case(
    tmp_path,
    monkeypatch,
    *,
    produce=True,
    seal=True,
    complete=True,
    technical_marker=False,
    spec=None,
    source_paths=None,
):
    mda = pytest.importorskip("MDAnalysis")
    from mania.run_provenance import SoftwareIdentity

    # Keep this fixture isolated from the software-identity module reload tests.
    fixed_identity = SoftwareIdentity(
        "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
    )
    for module in (
        "mania.cli",
        "mania.production_handoff",
        "mania.dataset_qc_run",
        "mania.replica_aggregation_run",
    ):
        monkeypatch.setattr(module + ".get_software_identity", lambda: fixed_identity)
    preparation = tmp_path / "external preparation"
    preparation.mkdir()
    root = tmp_path / "output" / "attempt_0001"
    root.mkdir(parents=True)
    binding = temporal_binding(spec=spec)
    identity = binding.dataset_spec.identity
    _, mapping = mapped_universe()
    mapping_path = preparation / "mapping.json"
    assert write_canonical_residue_mapping(mapping, mapping_path).passed
    partners = preparation / "partners.json"
    assert write_molecular_partner_metadata(
        MolecularPartnerMetadata((), ()), partners
    ).passed
    raw, prepared, topology = [
        preparation / name for name in ("raw.xtc", "prepared.xtc", "input.tpr")
    ]
    for path in (raw, prepared, topology):
        path.write_bytes(
            path.name.encode()
        )  # Fake bytes, never passed to a coordinate reader.
    if source_paths is not None:
        raw = source_paths["raw_trajectory"]
        topology = source_paths["topology"]
    large = {
        role: bind_file(path, "source:" + role)
        for role, path in (
            ("topology", topology),
            ("raw_trajectory", raw),
            ("prepared_trajectory", prepared),
        )
    }
    frames = [
        dict(
            prepared_frame_index=i,
            source_frame_index=i,
            time_ps=float(i * 200),
            protein_center_error_A=0.0,
            bond_representation_max_error_A=0.0,
            complete_fragment_fractional_min=0.0,
            complete_fragment_fractional_max=0.9,
        )
        for i in range(binding.sampling_plan.source_frame_count)
    ]
    report = dict(
        status="passed",
        trajectory_id=identity.trajectory_id,
        protocol="unwrap_bonded_fragments_center_protein_wrap_complete_fragments",
        source_xtc=dict(
            sha256=large["raw_trajectory"].sha256, size_bytes=raw.stat().st_size
        ),
        prepared_xtc=dict(
            sha256=large["prepared_trajectory"].sha256,
            size_bytes=prepared.stat().st_size,
        ),
        prepared_frames=len(frames),
        source_frame_indexes=list(range(len(frames))),
        atom_order_preserved=True,
        frame_order_preserved=True,
        exact_time_identity=True,
        cells_preserved=True,
        full_axis_preserved=True,
        protein_integrity_observations=dict(
            protein_atom_identity_sha256="a" * 64,
            protein_fragment_ids=[0],
            protein_remains_broken=None,
            assessment_source=None,
        ),
    )
    report_path = preparation / "preparation_complete.json"
    frames_path = preparation / "frame_evidence.json"
    atomic_json(report_path, report)
    atomic_json(frames_path, frames)
    integrity = normalize_preparation_observations(
        identity,
        report_path,
        frames_path,
        source_bindings=large,
        report_portable_path="evidence/producer/preparation_report/preparation_complete.json",
    )
    integrity_path = preparation / "protein_integrity_observations.json"
    write_protein_integrity(integrity_path, integrity)
    files = dict(
        preparation_report=report_path,
        frame_evidence=frames_path,
        protein_integrity_observations=integrity_path,
        canonical_residue_mapping=mapping_path,
        molecular_partner_metadata=partners,
    )
    for role in (
        "source_binding",
        "source_time_authority",
        "source_attestation",
        "dataset_request",
    ):
        path = preparation / f"{role}.json"
        atomic_json(path, {"role": role, "replica_identity": identity.to_dict()})
        files[role] = path
    inputs = HandoffInputs(
        identity,
        files,
        large,
        not technical_marker,
        {
            role: "Authority not supplied for this synthetic technical example"
            for role in CONDITIONAL_AUTHORITIES
        },
    )
    retained = retain_handoff_inputs(root, inputs)
    manifest = PreprocessingInputManifest(
        output_root=root / "preprocessing",
        temporal_policy=PreprocessingTemporalPolicy(
            schema_version="mania.preprocessing_temporal_policy.v0.1",
            boundary_profile="mania.window_boundaries.inclusive.v1",
        ),
        conditions=(
            TrajectoryInputConfig(
                condition=binding.execution_condition,
                topology_path=topology,
                trajectory_paths=(prepared,),
                dataset_spec=binding.dataset_spec,
                canonical_residue_mapping_path=mapping_path,
                molecular_partner_metadata_path=partners,
            ),
        ),
    )
    manifest_path = root / "inputs/preprocessing.json"
    atomic_json(manifest_path, manifest.model_dump(mode="json"))
    universe = mda.Universe.empty(
        4, n_residues=4, atom_resindex=list(range(4)), trajectory=True
    )
    universe.add_TopologyAttr("names", ["CA"] * 4)
    universe.add_TopologyAttr("elements", ["C"] * 4)
    universe.add_TopologyAttr("masses", [12.0] * 4)
    universe.add_TopologyAttr("resids", [900, 901, 902, 903])
    universe.add_TopologyAttr("resnames", [r.source_resname for r in mapping.mappings])
    universe.add_TopologyAttr("segids", ["PROA"])
    universe.add_TopologyAttr("bonds", [(0, 1), (1, 2), (2, 3)])

    class Axis:
        n_frames = len(frames)
        passes = 0
        yields = 0
        ts = universe.trajectory.ts

        def __iter__(self):
            self.passes += 1
            for frame in frames:
                self.yields += 1
                self.ts.positions = XYZ * 0.3
                self.ts.dimensions = [20, 20, 20, 90, 90, 90]
                self.ts.time = frame["time_ps"]
                yield self.ts

    axis = Axis()
    universe._trajectory = axis
    from mania.preprocessing import trajectory_manifest_loader as loader

    def load(runtime_input):
        return PreprocessingConditionLoadResult(
            runtime_input.condition_name,
            runtime_input,
            PreprocessingConditionRuntime(
                runtime_input.condition_name,
                universe,
                "synthetic",
                runtime_input.topology_path,
                runtime_input.trajectory_paths,
            ),
            status="loaded",
        )

    monkeypatch.setattr(loader, "load_single_condition_runtime", load)
    if produce:
        run_production_preprocessing(
            manifest_path, root / "preprocessing", "normal", handoff_inputs=retained
        )
        mappings = {
            "input:manifest": manifest_path,
            "input:condition:0001:topology": topology,
            "input:condition:0001:trajectory:0001": prepared,
            "input:canonical_residue_mapping:0001": mapping_path,
            "input:condition:0001:molecular_partner_metadata": partners,
        }
        validation = validate_run_artifacts(
            root / "preprocessing", scope="preprocessing", input_artifact_paths=mappings
        )
        assert validation.complete, validation.to_dict()
        acceptance = root / "acceptance.json"
        atomic_json(acceptance, {"validation": validation.to_dict(), "replay": "PASS"})
        from mania.production_run import _tree_digests

        completion_document = {
            "artifacts": _tree_digests(root / "preprocessing"),
            "production_eligible": not technical_marker,
        }
        marker_name = (
            "technical_complete.json" if technical_marker else "science_complete.json"
        )
        validate_handoff_prerequisites(
            root,
            retained,
            technical_validation=acceptance,
            completion_document=completion_document,
            completion_path=marker_name,
        )
        if complete:
            atomic_json(root / marker_name, completion_document)
        if seal:
            publish_handoff(root, retained, technical_validation=acceptance)
    return SimpleNamespace(
        root=root,
        preparation=preparation,
        retained=retained,
        axis=axis,
        manifest=manifest_path,
        report=report_path,
    )


@pytest.mark.parametrize(
    "role",
    ["preparation_report", "protein_integrity_observations", "source_attestation"],
)
def test_prerequisite_gate_fails_before_science_marker(tmp_path, monkeypatch, role):
    case = handoff_case(tmp_path, monkeypatch, seal=False, complete=False)
    (case.root / case.retained.bindings[role].path).unlink()
    with pytest.raises((ValueError, OSError)):
        validate_handoff_prerequisites(
            case.root,
            case.retained,
            technical_validation=case.root / "acceptance.json",
            completion_document={"artifacts": {}},
        )
    assert not (case.root / "science_complete.json").exists()
    assert not (case.root / "handoff_complete.json").exists()


def test_common_technical_marker_remains_ineligible(tmp_path, monkeypatch):
    case = handoff_case(tmp_path, monkeypatch, technical_marker=True)
    load_completed_handoff(case.root)
    assert not (case.root / "science_complete.json").exists()
    data = json.loads((case.root / "handoff_complete.json").read_text())
    assert data["production_eligible"] is False
    assert data["bindings"]["science_completion"]["path"] == "technical_complete.json"


def test_output_root_only_transfer_and_no_coordinate_review(tmp_path, monkeypatch):
    case = handoff_case(tmp_path, monkeypatch)
    report_bytes = case.report.read_bytes()
    manifest = load_completed_handoff(case.root)
    assert case.axis.passes == 2  # Existing time planning + selected contact pass.
    assert case.axis.yields == 82
    copied = tmp_path / "transferred"
    shutil.copytree(case.root, copied)
    shutil.rmtree(case.preparation)
    assert load_completed_handoff(copied) == manifest
    assert (
        copied / "evidence/producer/preparation_report/preparation_complete.json"
    ).read_bytes() == report_bytes
    assert not list(copied.rglob("*.xtc"))
    assert not list(copied.rglob("*.tpr"))
    metadata, rows = read_rmsd_evidence(copied / "preprocessing")
    assert len(rows) == 16 and metadata.atom_selection.atom_count == 4


@pytest.mark.parametrize(
    "role",
    [
        "preparation_report",
        "protein_integrity_observations",
        "protein_rmsd_timeseries",
        "canonical_residue_mapping",
    ],
)
def test_missing_mandatory_compact_file_and_hash_mismatch_reject_load(
    tmp_path, monkeypatch, role
):
    case = handoff_case(tmp_path, monkeypatch)
    manifest = load_completed_handoff(case.root)
    binding = next(e.binding for e in manifest.required_evidence if e.role == role)
    target = case.root / binding.path
    before = target.read_bytes()
    target.write_bytes(before + b"changed")
    with pytest.raises(ValueError, match="changed"):
        load_completed_handoff(case.root)
    target.unlink()
    with pytest.raises(ValueError):
        load_completed_handoff(case.root)


def test_legacy_science_marker_never_means_handoff_complete(tmp_path):
    atomic_json(tmp_path / "science_complete.json", {"artifacts": {}})
    with pytest.raises(ValueError, match="Legacy"):
        load_completed_handoff(tmp_path)
    assert not (tmp_path / "handoff_complete.json").exists()


def test_missing_bonded_observation_prevents_seal(tmp_path, monkeypatch):
    case = handoff_case(tmp_path, monkeypatch, produce=False)
    case.retained.source.compact_files["preparation_report"].unlink()
    with pytest.raises(ValueError):
        from mania.production_run import complete_production_handoff

        complete_production_handoff(
            case.root, case.retained, case.root / "acceptance.json"
        )
    assert not (case.root / "handoff_complete.json").exists()


@pytest.mark.parametrize(
    "role",
    [
        "preparation_report",
        "protein_integrity_observations",
        "frame_evidence",
        "source_attestation",
    ],
)
def test_science_complete_with_one_missing_compact_member_cannot_be_sealed(
    tmp_path, monkeypatch, role
):
    case = handoff_case(tmp_path, monkeypatch, seal=False)
    assert (case.root / "science_complete.json").exists()
    (case.root / case.retained.bindings[role].path).unlink()
    with pytest.raises((ValueError, OSError)):
        publish_handoff(
            case.root, case.retained, technical_validation=case.root / "acceptance.json"
        )
    assert not (case.root / "handoff_complete.json").exists()


def test_seal_production_eligibility_cannot_be_changed(tmp_path, monkeypatch):
    case = handoff_case(tmp_path, monkeypatch)
    path = case.root / "handoff_complete.json"
    data = json.loads(path.read_text())
    data["production_eligible"] = False
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_completed_handoff(case.root)
