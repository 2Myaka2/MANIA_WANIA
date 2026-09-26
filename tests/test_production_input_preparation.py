"""Synthetic raw-to-binding exercises; no historical files or real MD inputs."""

import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_biological_annotations import metadata as biology
from test_namd_authority import helper

from mania.biological_annotations_io import write_dataset_system_biological_annotations
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.canonical_residue_mapping_io import write_canonical_residue_mapping
from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition,
    MolecularPartnerComponentClassification,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    MolecularPartnerMetadata,
    write_molecular_partner_metadata,
)
from mania.preprocessing.namd_authority import TimeControl, derive_time, read_control
from mania.production_catalog import CATALOG_COLUMNS, load_production_catalog
from mania.production_run import read_production_input_binding

REPO = Path(__file__).resolve().parents[1]
ATTESTATION_SPEC = importlib.util.spec_from_file_location(
    "production_source_attestation", REPO / "tools/production_source_attestation.py"
)
attestation = importlib.util.module_from_spec(ATTESTATION_SPEC)
sys.modules[ATTESTATION_SPEC.name] = attestation
ATTESTATION_SPEC.loader.exec_module(attestation)
SPEC = importlib.util.spec_from_file_location(
    "production_input_preparation", REPO / "tools/production_input_preparation.py"
)
prep = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prep
SPEC.loader.exec_module(prep)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def seal(package):
    (package / "HANDOFF_FILES.sha256").write_text(
        "".join(
            f"{prep.source_identity(p).sha256}  {p.relative_to(package).as_posix()}\n"
            for p in sorted(package.rglob("*"))
            if p.is_file() and p.name != "HANDOFF_FILES.sha256"
        )
    )


def portable(value, root):
    if isinstance(value, dict):
        return {
            k: Path(v).relative_to(root).as_posix()
            if k in {"path", "source_directory"}
            else portable(v, root)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [portable(v, root) for v in value]
    return value


def build_bundle(base, source_prefix="raw"):
    """Nine identities with distinct system authority and four full frames."""
    mda = pytest.importorskip("MDAnalysis")
    root = base / "data"
    package = root / "egor_handoff"
    (package / "catalog").mkdir(parents=True)
    shutil.copyfile(
        REPO / "production/dataset_v1/dataset.yaml", package / "catalog/dataset.yaml"
    )
    with (REPO / "production/dataset_v1/trajectories.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    toppar = root / "egor/toppar"
    toppar.mkdir(parents=True)
    (toppar / "types.rtf").write_text("MASS -1 C 12 C\n")
    systems, sources, handoff_rows = {}, [], []
    for row in rows:
        if row["trajectory_id"] not in prep.SELECTIONS:
            continue
        tid, sid = row["trajectory_id"], row["system_id"]
        ss = int(row["disulfide_state"][0])
        n = 4 + ss
        rawdir = root / source_prefix / sid / row["replica_id"]
        rawdir.mkdir(parents=True)
        psf = rawdir / "own.psf"
        text = "PSF EXT\n\n         1 !NTITLE\n REMARKS synthetic\n\n"
        text += f"{n:10d} !NATOM\n"
        for i in range(n):
            name = "ALA" if i < 2 else "XXX"
            text += (
                f"{i + 1:10d} {'PROA':<8} {i + 1:<8} {name:<8} {'CA':<8} "
                f"{'C':<8} {0.0:14.6f} {12.0:14.4f} {0:8d}\n"
            )
        psf.write_text(text + "\n         1 !NBOND: bonds\n         1         2\n")
        raw = rawdir / "explicit_delivery.dcd"
        declaration = f"declared_{tid}.dcd"
        config, log = rawdir / "control.conf", rawdir / "run.out"
        frequency = 12500000
        config.write_text(
            f"structure declared.psf\ndcdfile {declaration}\ntimestep 2.0\n"
            f"dcdfreq {frequency}\nfirsttimestep 0\nnumsteps 50000000\n"
        )
        log.write_text(
            "Info: TIMESTEP 2\n" + f"Info: DCD FREQUENCY {frequency}\n"
            "Info: NUMBER OF STEPS 50000000\n" + f"Info: DCD FIRST STEP {frequency}\n"
            "Info: STRUCTURE FILE declared.psf\n"
            + f"Info: DCD FILENAME {declaration}\n"
            + "".join(
                f"WRITING COORDINATES TO DCD FILE {declaration} "
                f"AT STEP {i * frequency}\n"
                for i in range(1, 5)
            )
        )
        box = rawdir / "end.xsc"
        box.write_text(
            "# Synthetic endpoint cell only\n50000000 20 0 0 0 20 0 0 0 20 0 0 0\n"
        )
        u = mda.Universe(str(psf), to_guess=())
        u.load_new(np.zeros((4, n, 3), dtype=np.float32), order="fac")
        with mda.coordinates.DCD.DCDWriter(
            str(raw),
            n_atoms=n,
            dt=25000,
            nsavc=frequency,
            istart=frequency,
            remarks=f"FILENAME={declaration}",
        ) as writer:
            for i, ts in enumerate(u.trajectory):
                ts.dimensions = [20 + i, 21 + i, 22 + i, 90, 90, 90]
                ts.positions[:] = np.arange(n * 3).reshape(n, 3) % 15
                # A bonded protein crossing the x boundary exercises real unwrapping.
                ts.positions[0] = [0.25, 2, 2]
                ts.positions[1] = [19.75 + i, 2, 2]
                writer.write(u.atoms)
        u.trajectory.close()
        element = helper.build_elements(psf, toppar, ())
        control_rel = f"controls/{sid}"
        controls = package / control_rel
        template_rel = f"templates/{tid}"
        template_dir = package / template_rel
        write(
            template_dir / "elements.portable.json",
            portable(element.model_dump(mode="json"), root),
        )
        paths = dict(
            topology_path=psf,
            trajectory_path=raw,
            config_path=config,
            log_path=log,
            box_path=box,
        )
        for role, path in paths.items():
            row[role] = path.relative_to(root).as_posix()
        for role, name in (
            ("element_control", f"{template_rel}/elements.portable.json"),
            ("time_control", f"{template_rel}/raw_time.template.json"),
            ("canonical_mapping", f"{control_rel}/canonical_mapping.json"),
            ("biological_annotations", f"{control_rel}/annotations.json"),
            ("partner_metadata", f"{control_rel}/partner_metadata.json"),
        ):
            row[role] = "egor_handoff/" + name
        if sid not in systems:
            controls.mkdir(parents=True)
            mapping = CanonicalResidueMappingTable(
                (
                    CanonicalResidueMappingRecord(
                        "namd", "PROA", "1", "ALA", 311, "GLN", "mapped"
                    ),
                )
            )
            assert write_canonical_residue_mapping(
                mapping, controls / "canonical_mapping.json"
            ).passed
            assert write_dataset_system_biological_annotations(
                biology(dataset_id="napi2b-dataset-v1", system_id=sid),
                controls / "annotations.json",
            ).passed
            partners = MolecularPartnerMetadata(
                (
                    MolecularPartnerComponentClassification(
                        n - 1, "lipid", f"SYNTHETIC-{ss}"
                    ),
                ),
                (
                    ExplicitMolecularPartnerDefinition(
                        f"own-{ss}", "lipid", f"SYNTHETIC-{ss}", (n - 1,)
                    ),
                ),
            )
            assert write_molecular_partner_metadata(
                partners, controls / "partner_metadata.json"
            ).passed
            systems[sid] = dict(
                system_id=sid, controls=control_rel, atom_count=n, psfs=[]
            )
        systems[sid]["psfs"].append(prep.record(psf, root))
        source_files = {k: prep.record(paths[k], root) for k in prep.SOURCE_ROLES}
        sources.append(
            dict(
                trajectory_id=tid,
                system_id=sid,
                replica_id=row["replica_id"],
                files=source_files,
                declared_structure="declared.psf",
                declared_dcd_filename=declaration,
                expected_dcd_path=row["trajectory_path"],
            )
        )
        files = dict(source_files)
        for role in prep.SYSTEM_ROLES:
            files[role] = prep.record(root / row[role], root)
        for role, path in (
            ("trajectory_path", row["trajectory_path"]),
            ("prepared_trajectory", f"prepared/{tid}/full_axis.dcd"),
            ("time_control", f"egor_handoff/site/{tid}/raw_time.json"),
            ("prepared_time_control", f"egor_handoff/site/{tid}/prepared_time.json"),
            ("element_control", f"egor_handoff/site/{tid}/elements.json"),
            ("pbc_evidence", f"egor_handoff/site/{tid}/pbc.json"),
        ):
            files[role] = dict(path=path, size_bytes=None, sha256=None)
        payload = dict(
            schema_version="mania.production_input_binding.v0.1",
            dataset_id="napi2b-dataset-v1",
            catalog_row=row,
            temporal_policy=dict(
                schema_version="mania.preprocessing_temporal_policy.v0.1",
                boundary_profile="mania.window_boundaries.inclusive.v1",
            ),
            files=files,
        )
        write(
            template_dir / "input_binding.template.json",
            dict(
                schema_version="egor.handoff.input_binding_template.v1",
                trajectory_id=tid,
                status="requires_execution_site_verification",
                executable=False,
                payload=payload,
                expected_dcd_path=row["trajectory_path"],
                declared_dcd_filename=declaration,
            ),
        )
        handoff_rows.append(
            dict(
                trajectory_id=tid,
                system_id=sid,
                expected_dcd_path=row["trajectory_path"],
                declared_dcd_filename=declaration,
                input_binding_template=f"{template_rel}/input_binding.template.json",
                raw_time_template=f"{template_rel}/raw_time.template.json",
                prepared_time_template=f"{template_rel}/prepared_time.template.json",
            )
        )
        for role in ("raw", "prepared"):
            write(
                template_dir / f"{role}_time.template.json",
                dict(
                    schema_version="egor.handoff.time_template.v1",
                    trajectory_id=tid,
                    role=role,
                    runtime_schema="mania.namd_time_authority.v1",
                    config=source_files["config_path"],
                    log=source_files["log_path"],
                    declared_dcd_filename=declaration,
                    expected_path=files[
                        "trajectory_path" if role == "raw" else "prepared_trajectory"
                    ]["path"],
                    source_derivation=derive_time(config, log, 4),
                    dcd_observation=None,
                    status="requires_execution_site_DCD_verification",
                    expected_atom_count=n,
                    expected_frame_count=4,
                ),
            )
    with (package / "catalog/trajectories.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    for system in systems.values():
        write(package / system["controls"] / "topology_authority.json", system)
    write(
        package / "authority/shared_toppar.json",
        dict(sources=[prep.record(toppar / "types.rtf", root)]),
    )
    write(package / "authority/source_inventory.json", sources)
    write(
        package / "authority/pbc_protocol.json",
        dict(
            schema_version="egor.handoff.pbc_protocol.v1",
            protocol=prep.PROTOCOL,
            authority="Synthetic protocol fixture; not Egor certification",
            internal_mic=False,
            required_atom_order_preserved=True,
            required_frame_order_preserved=True,
            required_frame_count=4,
            required_full_axis_ps=[25000, 100000],
        ),
    )
    write(
        package / "handoff_manifest.json",
        dict(
            schema_version="egor.handoff.manifest.v1",
            dataset_id="napi2b-dataset-v1",
            rows=handoff_rows,
            systems=list(systems.values()),
        ),
    )
    seal(package)
    return SimpleNamespace(
        root=root,
        package=package,
        result=root / "prepared/attempt",
        output=base / "production_results",
        rows=rows,
    )


@pytest.fixture
def bundle(tmp_path):
    return build_bundle(tmp_path)


def prepare_args(bundle, tid="namd_egor_wt_0ss_r1"):
    return dict(
        data_root=bundle.root,
        result_root=bundle.result,
        authority_package=bundle.package,
        trajectory_id=tid,
        min_free_bytes=1,
        workers=1,
        threads=1,
    )


def confirm_args(bundle, result, tid="namd_egor_wt_0ss_r1"):
    return dict(
        data_root=bundle.root,
        result_root=bundle.result,
        authority_package=bundle.package,
        trajectory_id=tid,
        min_free_bytes=1,
        report_sha256=result["report_sha256"],
        reviewer="Synthetic reviewer",
        review_note="Synthetic test only; reviewed raw correspondence and report",
        approve=True,
        production_output_root=bundle.output,
    )


@pytest.mark.parametrize("tid", sorted(prep.SELECTIONS))
def test_raw_to_review_and_strict_binding_all_nine(bundle, tid, monkeypatch, capsys):
    authority = prep.select_authority(bundle.root, bundle.package, tid)
    before = {k: prep.source_identity(v) for k, v in authority["paths"].items()}
    result = prep.prepare(**prepare_args(bundle, tid))
    report = prep.read_strict_json(Path(result["report"]))
    assert report["status"] == "pending_review" and report["human_review"] is None
    assert report["checks_kind"] == "automatic_technical"
    assert not report["scientific_contact_or_qc_certification"]
    assert not list(bundle.result.rglob("production_input_binding.json"))
    assert before == {k: prep.source_identity(v) for k, v in authority["paths"].items()}
    assert report["evidence"]["atom_count"] == 4 + int(tid.split("_")[-2][0])
    raw = read_control(bundle.result / "raw_time.json", TimeControl)
    prepared = read_control(bundle.result / "prepared_time.json", TimeControl)
    assert raw.scientific_times_ps == prepared.scientific_times_ps
    assert raw.dcd.observed_times == prepared.dcd.observed_times
    rows = [
        json.loads(s)
        for s in (bundle.result / "frame_audit.jsonl").read_text().splitlines()
    ]
    reopened = [
        json.loads(s)
        for s in (bundle.result / "reopened_audit.jsonl").read_text().splitlines()
    ]
    assert [r["source_frame"] for r in rows] == [0, 1, 2, 3]
    assert [r["coordinate_sha256_float32"] for r in rows] == [
        r["coordinate_sha256_float32"] for r in reopened
    ]
    assert [r["box"] for r in rows] == [r["box"] for r in reopened]
    assert rows[0]["fragments_requiring_unwrap"] == 1
    confirmed = prep.confirm(**confirm_args(bundle, result, tid))
    binding = read_production_input_binding(Path(confirmed["binding"]))
    assert binding.prepared_lineage.reviewer == "Synthetic reviewer"
    assert result["report_sha256"] in binding.prepared_lineage.note
    for role in prep.SYSTEM_ROLES:
        assert binding.files[role].path == authority["inputs"][role]["path"]
    site = prep.SiteReview.model_validate(
        prep.read_strict_json(bundle.result / "confirmation/site_review.json")
    )
    assert site.prepared_lineage == binding.prepared_lineage
    # Public CLI, actual controls and hashes; no fake runtime/authority hooks.
    import mania.cli as cli

    monkeypatch.setenv("MANIA_DATA_ROOT", str(bundle.root))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "production",
            "validate",
            "--catalog",
            str(authority["catalog"]),
            "--trajectory-id",
            tid,
            "--output-root",
            str(bundle.output),
            "--input-binding",
            confirmed["binding"],
        ],
    )
    cli.main()
    public = json.loads(capsys.readouterr().out)
    assert (
        public["status"] == "preflight_passed"
        and public["trajectory_pbc_qc_certified"] is False
    )


@pytest.mark.parametrize(
    "damage",
    [
        "report",
        "input",
        "output",
        "package",
        "failed",
        "missing_check",
        "incomplete",
        "clock",
    ],
)
def test_confirmation_rejects_changed_or_failed_evidence(bundle, damage, monkeypatch):
    result = prep.prepare(**prepare_args(bundle))
    report = bundle.result / "report.json"
    if damage == "report":
        report.write_text(report.read_text() + " ")
    elif damage == "input":
        selected = load_production_catalog(
            bundle.package / "catalog/dataset.yaml"
        ).trajectory("namd_egor_wt_0ss_r1")
        with (bundle.root / selected.row["trajectory_path"]).open("ab") as stream:
            stream.write(b"changed")
    elif damage == "output":
        (bundle.result / "prepared.dcd").write_bytes(b"incomplete")
    elif damage == "package":
        path = bundle.package / "authority/pbc_protocol.json"
        path.write_text(path.read_text() + " ")
    elif damage == "incomplete":
        (bundle.result / "complete.json").unlink()
    elif damage == "clock":
        monkeypatch.setattr(prep, "utc_now", lambda: "2000-01-01T00:00:00+00:00")
    elif damage in {"failed", "missing_check"}:
        obj = prep.read_strict_json(report)
        obj["checks"]["bond_representation"] = False
        if damage == "missing_check":
            del obj["checks"]["bond_representation"]
        write(report, obj)
        complete = prep.read_strict_json(bundle.result / "complete.json")
        complete["report.json"] = prep.record(report, bundle.root)
        write(bundle.result / "complete.json", complete)
        result["report_sha256"] = prep.source_identity(report).sha256
    with pytest.raises((ValueError, OSError)):
        prep.confirm(**confirm_args(bundle, result))
    assert not list(bundle.result.rglob("production_input_binding.json"))
    assert (
        prep.read_strict_json(bundle.result / "confirmation/operation.json")[
            "exit_code"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "damage", ["source", "control", "replica", "foreign_system", "time"]
)
def test_wrong_source_or_control_rejected(bundle, damage):
    tid = "namd_egor_wt_0ss_r1"
    template = bundle.package / f"templates/{tid}/input_binding.template.json"
    obj = prep.read_strict_json(template)
    if damage == "source":
        (bundle.root / obj["payload"]["files"]["topology_path"]["path"]).write_text(
            "wrong"
        )
    elif damage == "control":
        (
            bundle.root / obj["payload"]["files"]["biological_annotations"]["path"]
        ).write_text("{}")
    elif damage == "replica":
        obj["trajectory_id"] = "namd_egor_wt_0ss_r2"
        write(template, obj)
        seal(bundle.package)
    elif damage == "foreign_system":
        other = prep.read_strict_json(
            bundle.package / "templates/namd_egor_wt_2ss_r1/input_binding.template.json"
        )
        obj["payload"]["files"]["partner_metadata"] = other["payload"]["files"][
            "partner_metadata"
        ]
        write(template, obj)
        seal(bundle.package)
    else:
        path = bundle.package / f"templates/{tid}/raw_time.template.json"
        t = prep.read_strict_json(path)
        t["trajectory_id"] = "namd_egor_wt_0ss_r2"
        write(path, t)
        seal(bundle.package)
    with pytest.raises(ValueError):
        prep.prepare(**prepare_args(bundle))
    assert not (bundle.result / "complete.json").exists()
    assert not (bundle.result / "prepared.dcd").exists()


def test_incomplete_write_protected_and_raw_unchanged(bundle, monkeypatch):
    authority = prep.select_authority(
        bundle.root, bundle.package, "namd_egor_wt_0ss_r1"
    )

    def interrupted(authority, out, phase):
        (out / "prepared.dcd").write_bytes(b"partial")
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(prep, "prepare_coordinates", interrupted)
    with pytest.raises(OSError, match="disk failure"):
        prep.prepare(**prepare_args(bundle))
    prep.check_records(authority["inputs"], bundle.root)
    assert not (bundle.result / "complete.json").exists()
    assert "disk failure" in (bundle.result / "operation.log").read_text()
    with pytest.raises(ValueError, match="protected"):
        prep.prepare(**prepare_args(bundle))
    assert (bundle.result / "prepared.dcd").read_bytes() == b"partial"


def test_existing_success_and_missing_approval_protected(bundle):
    result = prep.prepare(**prepare_args(bundle))
    original = prep.source_identity(bundle.result / "prepared.dcd")
    with pytest.raises(ValueError, match="protected"):
        prep.prepare(**prepare_args(bundle))
    assert prep.source_identity(bundle.result / "prepared.dcd") == original
    kwargs = confirm_args(bundle, result)
    kwargs["approve"] = False
    with pytest.raises(ValueError, match="Explicit"):
        prep.confirm(**kwargs)
    assert not (bundle.result / "confirmation").exists()
    kwargs["approve"] = True
    prep.confirm(**kwargs)
    with pytest.raises(FileExistsError):
        prep.confirm(**kwargs)


@pytest.mark.parametrize("damage", ["escape", "symlink", "collision", "space"])
def test_path_and_disk_guards(bundle, damage, monkeypatch):
    kwargs = prepare_args(bundle)
    if damage == "escape":
        kwargs["result_root"] = bundle.root.parent / "outside"
    elif damage == "collision":
        kwargs["result_root"] = bundle.package / "out"
    elif damage == "symlink":
        link = bundle.root / "link"
        link.symlink_to(bundle.root.parent, target_is_directory=True)
        kwargs["result_root"] = link / "result"
    else:
        monkeypatch.setattr(
            prep.shutil, "disk_usage", lambda _: SimpleNamespace(free=0)
        )
    with pytest.raises(ValueError):
        prep.prepare(**kwargs)
    assert not (bundle.result / "prepared.dcd").exists()


def test_wrong_raw_replica_header_rejected(bundle):
    catalog = load_production_catalog(bundle.package / "catalog/dataset.yaml")
    left = (
        bundle.root / catalog.trajectory("namd_egor_wt_0ss_r1").row["trajectory_path"]
    )
    right = (
        bundle.root / catalog.trajectory("namd_egor_wt_0ss_r2").row["trajectory_path"]
    )
    shutil.copyfile(right, left)
    with pytest.raises(ValueError, match="header/config/log linkage"):
        prep.prepare(**prepare_args(bundle))
    assert not (bundle.result / "complete.json").exists()


@pytest.mark.parametrize("damage", ["atom_order", "cell", "short_write", "time"])
def test_reopened_corruption_cannot_complete(bundle, monkeypatch, damage):
    import MDAnalysis as mda

    original_write = mda.coordinates.DCD.DCDWriter.write
    original_init = mda.coordinates.DCD.DCDWriter.__init__
    writes = 0

    def bad_write(self, obj):
        nonlocal writes
        writes += 1
        if damage == "atom_order":
            obj.positions = obj.positions[::-1]
        elif damage == "cell":
            obj.universe.dimensions = [40, 40, 40, 90, 90, 90]
        elif damage == "short_write" and writes == 4:
            return
        original_write(self, obj)

    def bad_init(self, *args, **kwargs):
        kwargs["dt"] *= 2
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(mda.coordinates.DCD.DCDWriter, "write", bad_write)
    if damage == "time":
        monkeypatch.setattr(mda.coordinates.DCD.DCDWriter, "__init__", bad_init)
    with pytest.raises(ValueError, match="Reopened"):
        prep.prepare(**prepare_args(bundle))
    assert not (bundle.result / "complete.json").exists()
    assert not list(bundle.result.rglob("production_input_binding.json"))


def test_representation_failure_is_not_reviewable(bundle, monkeypatch):
    original = prep.FragmentPreparation.wrap

    def damage(self):
        original(self)
        self.u.atoms.positions += np.float32(2)

    monkeypatch.setattr(prep.FragmentPreparation, "wrap", damage)
    with pytest.raises(ValueError, match="Standard wrap mismatch"):
        prep.prepare(**prepare_args(bundle))
    assert not (bundle.result / "complete.json").exists()
    assert "FAILED / INCOMPLETE" in (bundle.result / "summary.txt").read_text()


def test_atomic_binding_write_failure_has_no_binding(bundle, monkeypatch):
    result = prep.prepare(**prepare_args(bundle))
    original = prep.write_atomic_text

    def fail_binding(payload, target, *, overwrite):
        if target.name == "production_input_binding.json":
            return SimpleNamespace(passed=False, error="synthetic final write failure")
        return original(payload, target, overwrite=overwrite)

    monkeypatch.setattr(prep, "write_atomic_text", fail_binding)
    with pytest.raises(OSError, match="final write failure"):
        prep.confirm(**confirm_args(bundle, result))
    assert not list(bundle.result.rglob("production_input_binding.json"))
    operation = prep.read_strict_json(bundle.result / "confirmation/operation.json")
    assert operation["status"] == "failed" and operation["exit_code"] == 1
