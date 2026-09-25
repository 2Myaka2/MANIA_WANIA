#!/usr/bin/env python3
"""Stage 34.C.3: exact prepared r2/r3 specialised science, without downstream runs."""

from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import shutil
import subprocess
import time
import traceback
import zipfile
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np

from mania.dataset_qc_decision_io import read_dataset_qc_decision_set
from mania.dataset_release_manifest import ReleaseCanonicalBinding
from mania.dataset_release_manifest_io import read_dataset_release_export_manifest
from mania.preprocessing.molecular_partner_catalog_io import (
    PreprocessingMolecularPartnerCatalog,
    read_molecular_partner_catalog,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    read_molecular_partner_metadata,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.replica_aggregation_workflow import FAMILIES

_spec = importlib.util.spec_from_file_location(
    "stage34c3_b4", Path(__file__).with_name("stage34b4_namd_specialized_pilot.py")
)
b4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b4)
b3, shared = b4.b3, b4.shared
c1 = b3.helper("stage34c_namd_r2r3_pilots")
require, dump, file_record, read = b3.require, b3.dump, b3.file_record, c1.read
B4 = "stage34b4_namd_specialized_20260922T182122Z_f919e15778874c6ca1a794b28609b798"
B4_SHA = "7ec2365b4a5093359d56f68443f933960f9dcf218c6cd4f65a23f3de43feebe9"
C1 = "stage34c_r2r3_pilots_20260923T152511Z_f535800b12ae449bb565fe823fbbc0c9"
C1_SHA = "be9f7f18d78fe4f9d0d148b97236daaab76ef4202fce28d6222aaa69cfc5e21e"
C2 = (
    "stage34c_three_replica_downstream_20260923T162715Z_"
    "97cb0bc52b9347cfa0da2a09d7082f6c"
)
C2_SHA = "a59a8bf8c78695cbc01d674de46c40b127bcb10ff178eb332fc563b35da2c276"
PREPARED = {
    "2": "fd34052005a629f28e22b805463afb130617bd68dea0ccb366a2ca0d6d24d3bc",
    "3": "9fe19cfb9a8de59afd613b6d4c3eaef166a17e925611671c984974edfab4cf55",
}
COVERAGE_SHA = "63dced08b8547970f5404b02833619e790205a3a24520cbeda63cdbdacc1f7be"
# D.4c adds release-profile propagation after the unchanged coverage block.
PROFILE_COVERAGE_SHA = (
    "82b07a3486e2ae19268109fb5b344b4f5ccce63d24fa627b80a4703cfb582096"
)
ALLOWED_FILES = (
    "tools/stage34c_r2r3_specialized.py",
    "tests/test_stage34c_r2r3_specialized.py",
    "docs/stage34c_namd_three_replica.md",
)
IDENTITY_FIELDS = ("trajectory_id", "replica_id")
LIMITATIONS = (
    "Only real r2/r3 Stage 29/30 specialised science, five prepared frames each.\n"
    "No protein science, RMSD, QC, Stage 31, Stage 33, F1/F2 or release validation.\n"
    "No cross-replica correspondence; partner IDs remain topology-local.\n"
    "Direct heavy-heavy distances: lipid <=6.0 A, glycan <=4.5 A; no MIC.\n"
    "Accepted Variant C only; scientific PBC status remains unresolved.\n"
    "XTC has no atom labels: exact bytes bind accepted pointwise-order evidence.\n"
    "Source/canonical condition remains null under the accepted namd-pilot alias.\n"
    "Later publication must bind PMm consistently, as in accepted C.2 protein inputs.\n"
    "Coverage readiness is only the frozen input gate, not publication acceptance.\n"
    "Specialised aggregation still requires authoritative partner correspondence.\n"
    "No full 100-ns analysis; raw topology/trajectory/toppar bytes excluded.\n"
)


def checkpoint(repo, work):
    outputs = []
    commands = [
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
        ["git", "rev-parse", "develop"],
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        ["git", "log", "--oneline", "--decorate", "-32"],
        ["git", "diff", "--cached", "--name-only"],
    ]
    for argv in commands:
        cp = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
        b3.record_command(
            work, argv, exit_code=cp.returncode, output=cp.stdout + cp.stderr
        )
        require(cp.returncode == 0, "Repository checkpoint failed")
        outputs.append(cp.stdout)
    require(outputs[0].strip() == "FAIR", "Required branch FAIR")
    require(not outputs[-1].strip(), "Nothing may be staged")
    require(
        all(line[3:] in ALLOWED_FILES for line in outputs[2].splitlines()),
        "Unexpected working-tree changes",
    )
    for stem in ("stage34c_namd_r2r3_pilots", "stage34c_three_replica_downstream"):
        for name in (f"tools/{stem}.py", f"tests/test_{stem}.py"):
            blob = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=repo)
            require(blob == (repo / name).read_bytes(), "Accepted tooling changed")
    (work / "git_state.txt").write_text("\n".join(outputs))
    return outputs[1].strip()


def bind_archive(base, sha, names, target):
    """Bind each small authority to a pinned archive and its unchanged live file."""
    b3.require_hash(base.with_suffix(".zip"), sha, "accepted evidence archive")
    records = []
    with zipfile.ZipFile(base.with_suffix(".zip")) as archive:
        for name in names:
            require(
                not Path(name).is_absolute() and ".." not in Path(name).parts,
                "Unsafe archive entry",
            )
            data = archive.read(name)
            require(
                data == (base / name).read_bytes(), f"Accepted evidence changed: {name}"
            )
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            records.append(file_record(base / name))
    return records


def validate_r1_authority(summary, catalog, inventory, classification):
    require(summary["stage34b4_status"] == "PASS", "r1 specialised authority not PASS")
    require(
        classification["psf"]["sha256"] == b3.PSF_SHA256,
        "Classification shared PSF differs",
    )
    require(
        inventory["status"] == "PASS" and not inventory["unresolved"],
        "Unresolved accepted classification",
    )
    require(
        inventory["counts"]["membrane"] == 828 and inventory["counts"]["glycan"] == 2,
        "Accepted partner counts differ",
    )
    require(len(catalog.bindings) == 1, "One r1 catalog binding required")
    binding = catalog.bindings[0]
    require(
        binding.dataset_spec.identity.replica_id == "1"
        and binding.dataset_spec.identity.trajectory_id == "egor-2ss-r1-five-frames",
        "Accepted catalog is not replica 1",
    )
    require(
        binding.partner_catalog.lipid_partner_count == 828
        and binding.partner_catalog.glycan_partner_count == 2,
        "Accepted catalog population differs",
    )


def structural_catalog(catalog):
    data = copy.deepcopy(catalog.to_dict())
    require(len(data["bindings"]) == 1, "One catalog binding required")
    identity = data["bindings"][0]["dataset_spec"]["identity"]
    for name in IDENTITY_FIELDS:
        del identity[name]
    return data


def compare_catalogs(accepted, candidate, replica):
    require(replica in PREPARED, "Only r2/r3 catalog rebinding is authorized")
    identity = candidate.bindings[0].dataset_spec.identity
    require(
        identity.replica_id == replica
        and identity.trajectory_id == f"egor-2ss-r{replica}-five-frames",
        "Replica/trajectory identity was not rebound",
    )
    require(
        structural_catalog(accepted) == structural_catalog(candidate),
        "Topology-local catalog structure or classification changed",
    )


def rebind_catalog(accepted, temporal, replica):
    require(len(temporal.bindings) == 1, "One temporal binding required")
    original = accepted.bindings[0]
    binding = temporal.bindings[0]
    expected_identity = original.dataset_spec.identity.model_copy(
        update=dict(
            replica_id=replica, trajectory_id=f"egor-2ss-r{replica}-five-frames"
        )
    )
    require(
        binding.dataset_spec
        == original.dataset_spec.model_copy(update=dict(identity=expected_identity))
        and binding.execution_condition == original.execution_condition,
        "Only explicit replica/trajectory identity may change",
    )
    result = PreprocessingMolecularPartnerCatalog(
        (replace(original, dataset_spec=binding.dataset_spec),)
    )
    compare_catalogs(accepted, result, replica)
    return result


def validate_anchors(u, partners, accepted_anchors):
    context = b3.pbc.topology_context(u)
    actual = shared.glycan_components(u, context, context["heavy"])
    require(actual == accepted_anchors, "Glycan topology membership/anchor changed")
    by_id = {p["partner_id"]: p for p in partners if p["partner_kind"] == "glycan"}
    require(len(by_id) == 2, "Exactly two glycans required")
    for p in actual:
        require(
            p["carrier_atom_name"] == "ND2"
            and p["first_sugar_atom_name"] == "C1"
            and p["partner_name"] == "FA2G2S2"
            and p["ordinary_carrier_pair_excluded"],
            "Accepted anchor differs",
        )
        require(
            all(by_id[p["partner_id"]][k] == v for k, v in p.items()),
            "Inventory anchor differs from connectivity",
        )
    return actual


def prepared_binding(u, psf, accepted, historical, replica, work):
    b3.require_hash(psf, b3.PSF_SHA256, "shared classification PSF")
    prepared = accepted / "prepared_variant_c.xtc"
    record = b3.require_hash(
        prepared, PREPARED[replica], "accepted prepared trajectory"
    )
    identity = read(historical / "prepared_trajectory_identity.json")
    require(
        all(identity[k] == v for k, v in record.items()), "Prepared identity differs"
    )
    b4.validate_frame_records(identity["frames"])
    authority = read(historical / "shared_authority.json")
    require(authority["psf"] == file_record(psf), "Prepared shared PSF binding differs")
    for name in ("variant_c_pbc_diagnostic", "persisted_pbc_validation"):
        b3.require_representation(read(historical / f"{name}.json")["frames"])
    audit = read(historical / "pbc_audit.json")
    require(
        audit
        == dict(
            replica_id=replica,
            external_preparation="specified Variant C",
            scientific_pbc_status="unresolved",
            MANIA_internal_MIC=False,
        ),
        "Accepted PBC provenance changed",
    )
    before = {
        k: getattr(u.atoms, k).copy()
        for k in (
            "indices",
            "ids",
            "names",
            "resindices",
            "resids",
            "resnames",
            "segindices",
            "segids",
        )
    }
    u.load_new(str(prepared))
    require(len(u.trajectory) == 5, "Exactly five prepared frames required")
    frames = []
    selected = read(historical / "selected_frames.json")["frames"]
    for i in b3.FRAMES:
        ts = u.trajectory[i]
        require(float(ts.time) == b3.TIMES_PS[i], "Prepared scientific time changed")
        require(np.isfinite(ts.positions).all(), "Nonfinite prepared coordinates")
        require(
            np.allclose(ts.dimensions, selected[i]["box"], rtol=0, atol=2e-5),
            "Prepared box changed",
        )
        require(
            all(np.array_equal(v, getattr(u.atoms, k)) for k, v in before.items()),
            "Prepared topology identity/order differs",
        )
        frames.append(
            {
                **b3.frame_map()[i],
                "box": ts.dimensions.tolist(),
                "identity_order_finite_passed": True,
            }
        )
    temporal_path = historical / "output/temporal_execution.json"
    temporal = read_preprocessing_temporal_execution(temporal_path)
    _, samples, windows = b3.sampling_contract()
    require(len(temporal.bindings) == 1, "Exactly one physical-time binding required")
    binding = temporal.bindings[0]
    require(
        binding.sampling_plan == samples and binding.window_plan == windows,
        "Accepted five-frame physical-time contract changed",
    )
    shutil.copyfile(temporal_path, work / "temporal_execution.json")
    evidence = dict(
        status="PASS",
        prepared=record,
        psf=file_record(psf),
        frames=frames,
        topology_identity_fields=list(before),
        accepted_pbc=audit,
        new_pbc_transform=False,
        source_dcd_frames_read=0,
        identity_limitation=identity["identity_limitation"],
    )
    dump(work / "prepared_binding.json", evidence)
    return temporal, evidence


def frozen_coverage_gate(control, base, candidates):
    """Execute ONLY the unchanged input-coverage block from the pinned Stage 33 code.

    There is no standalone production coverage API. Extracting its exact AST keeps
    the validator unchanged without calling the release builder, metadata assembly,
    source-authority F1, cross-table validation, or any output-writing function.
    """
    source = (
        Path(__file__).resolve().parents[1] / "src/mania/dataset_release_workflow.py"
    )
    require(
        file_record(source)["sha256"] in (COVERAGE_SHA, PROFILE_COVERAGE_SHA),
        "Wrong frozen Stage 33 coverage validator SHA256",
    )
    tree = ast.parse(source.read_text())
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "build_dataset_release"
    )
    body = function.body[2].body  # Pinned function's try block.
    start = next(
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "canonical" for t in n.targets)
    )
    nodes = body[start : start + 2]
    require(
        isinstance(nodes[1], ast.For) and ast.unparse(nodes[1].iter) == "FAMILIES",
        "Coverage block changed",
    )
    namespace = dict(
        control=control, base=base, candidates=candidates, FAMILIES=FAMILIES
    )
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace
    )
    return namespace["canonical"]


def coverage_readiness(control, base, candidates, freezes):
    missing, records, invalid = [], [], []
    for family in FAMILIES:
        present = set()
        for binding in control.canonical_bindings:
            if binding.family != family.name:
                continue
            try:
                path = base / binding.path
                expected = freezes[binding.path]
                record = file_record(path)
                require(record["sha256"] == expected["sha256"], "Frozen source changed")
                table = family.canonical_reader(path)
                keys = {r.replica_key for r in table.rows}
                require(
                    keys == set(binding.replica_keys) and len(table.rows) > 0,
                    "Missing real canonical rows for explicit replica coverage",
                )
                require(len(table.rows) == expected["rows"], "Frozen row count changed")
                present.update(keys)
                records.append(
                    dict(
                        family=family.name,
                        replica_keys=list(keys),
                        rows=len(table.rows),
                        **record,
                    )
                )
            except (OSError, ValueError, KeyError) as exc:
                invalid.append(
                    dict(family=family.name, path=binding.path, reason=str(exc))
                )
        missing.extend(
            dict(family=family.name, replica_key=key)
            for key in control.scientific_release_replica_keys
            if key not in present
        )
    gate_error = None
    try:
        frozen_coverage_gate(control, base, candidates)
    except (ValueError, OSError) as exc:
        gate_error = str(exc)
    return dict(
        status="PASS" if not (missing or invalid or gate_error) else "STOP",
        complete=not (missing or invalid or gate_error),
        missing_canonical_coverage=missing,
        invalid_sources=invalid,
        frozen_validator_error=gate_error,
        sources=records,
        policy_source="src/mania/dataset_release_workflow.py:312",
        policy_sha256=file_record(
            Path(__file__).resolve().parents[1]
            / "src/mania/dataset_release_workflow.py"
        )["sha256"],
        publication_executed=False,
        scope="Exact frozen input coverage block only; no publication/F1/F2",
    )


def run_replica(u, psf, mapping, accepted_catalog, partners, root, work, replica):
    work.mkdir()
    timings = {}
    with b3.timed(timings, "prepared_binding_seconds"):
        temporal, prepared = prepared_binding(
            u,
            psf,
            root / C1 / f"replica{replica}",
            work.parent / "history/c1" / f"replica{replica}",
            replica,
            work,
        )
        expected = rebind_catalog(accepted_catalog, temporal, replica)
        catalog_path = work.parent / f"r{replica}_partner_catalog.json"
        dump(catalog_path, expected.to_dict())
        compare_catalogs(
            accepted_catalog, read_molecular_partner_catalog(catalog_path), replica
        )
        anchors = validate_anchors(
            u, partners, read(work.parent / "history/r1/glycan_anchor_metadata.json")
        )
        dump(
            work / "glycan_anchor_metadata.json",
            dict(
                replica_key=temporal.bindings[0].dataset_spec.identity.replica_key,
                prepared_sha256=prepared["prepared"]["sha256"],
                anchors=anchors,
            ),
        )
        metadata = work / "molecular_partner_metadata.json"
        shutil.copyfile(
            work.parent / "history/r1/molecular_partner_metadata.json", metadata
        )
        read_molecular_partner_metadata(metadata)
    print(f"r{replica} prepared binding/catalog PASS; Stage 29 starting", flush=True)
    with b3.timed(timings, "production_specialized_seconds"):
        execution, tables = b4.execute_science(u, temporal, work)
        require(
            execution.catalog() == expected, "Production catalog differs from authority"
        )
    print(
        f"r{replica} Stage 29 complete; independent all-pairs check starting",
        flush=True,
    )
    with b3.timed(timings, "independent_seconds"):
        observations = b4.independent_observations(u, partners)
        shared.write_csv(work / "specialised_per_frame_independent.csv", observations)
        check = b4.compare_independent(
            observations, execution.condition_results[0], tables
        )
        dump(work.parent / f"r{replica}_specialized_check.json", check)
        require(check["status"] == "PASS", "Independent specialised science differs")
    with b3.timed(timings, "canonical_validation_seconds"):
        canonical, technical = b4.export_validate(
            execution, tables, mapping, temporal, work
        )
        compare_catalogs(
            accepted_catalog,
            read_molecular_partner_catalog(work / "molecular_partner_catalog.json"),
            replica,
        )
    freeze = {}
    for kind in ("lipid", "glycan"):
        require(
            canonical[kind]["source_rows"] == canonical[kind]["canonical_rows"] > 0,
            "Canonical population lost or fake empty source",
        )
        path = work / f"output/protein_{kind}_contacts_by_window_canonical.csv"
        freeze[kind] = dict(
            **file_record(path),
            rows=canonical[kind]["canonical_rows"],
            replica_id=replica,
            independent_status="PASS",
            technical_status=technical["status"],
        )
    dump(work.parent / f"r{replica}_canonical_source_freeze.json", freeze)
    counts = dict(
        membrane_partners=expected.bindings[0].partner_catalog.lipid_partner_count,
        membrane_compositions=dict(
            sorted(
                Counter(
                    p["composition_label"]
                    for p in partners
                    if p["partner_kind"] == "lipid"
                ).items()
            )
        ),
        membrane_classes=dict(
            sorted(
                Counter(
                    p["partner_name"] for p in partners if p["partner_kind"] == "lipid"
                ).items()
            )
        ),
        membrane_partners_with_contacts=len(
            {r["partner_id"] for r in observations if r["partner_kind"] == "lipid"}
        ),
        lipid_raw_positives=sum(r["partner_kind"] == "lipid" for r in observations),
        glycan_partners=2,
        glycan_raw_positives=sum(r["partner_kind"] == "glycan" for r in observations),
        anchor_observations_excluded=sum(
            r["standard_summary_excluded"] for r in observations
        ),
    )
    counts["ordinary_glycan_positives"] = (
        counts["glycan_raw_positives"] - counts["anchor_observations_excluded"]
    )
    result = dict(
        replica_id=replica,
        status="PASS",
        prepared=prepared,
        counts=counts,
        independent=check,
        canonical=canonical,
        freeze=freeze,
        technical=technical,
        timings=timings,
    )
    dump(work / "summary.json", result)
    print(f"r{replica} PASS: {counts}", flush=True)
    return result


def run(root, work):
    started = time.perf_counter()
    summary = dict(
        status="BLOCKED",
        production_code_changes=[],
        stage31_executed=False,
        stage33_executed=False,
        stage32_executed=False,
        correspondence_created=False,
        protein_science_recomputed=False,
        rmsd_recomputed=False,
        full_100ns_analysis=False,
        repository_verification="pending",
        replicas=[],
    )
    u = None
    try:
        summary["starting_head"] = checkpoint(Path(__file__).resolve().parents[1], work)
        r1_names = [
            "stage34b4_summary.json",
            "molecular_partner_catalog.json",
            "molecular_partner_metadata.json",
            "partner_classification_evidence.json",
            "glycan_anchor_metadata.json",
            "accepted_b3_bindings.json",
        ]
        bind_archive(root / B4, B4_SHA, r1_names, work / "history/r1")
        # Verify the large inventory, retaining only its partner records.
        inventory_path = root / B4 / "namd_partner_inventory.json"
        with zipfile.ZipFile((root / B4).with_suffix(".zip")) as archive:
            require(
                archive.read(inventory_path.name) == inventory_path.read_bytes(),
                "Accepted classification inventory changed",
            )
        inventory = read(inventory_path)
        catalog = read_molecular_partner_catalog(
            work / "history/r1/molecular_partner_catalog.json"
        )
        r1_summary = read(work / "history/r1/stage34b4_summary.json")
        classification = read(work / "history/r1/partner_classification_evidence.json")
        validate_r1_authority(r1_summary, catalog, inventory, classification)
        partners = inventory["partners"]
        dump(
            work / "accepted_r1_specialized_authority.json",
            dict(
                status="PASS",
                archive=file_record((root / B4).with_suffix(".zip")),
                classification=file_record(
                    root / B4 / "partner_classification_evidence.json"
                ),
                inventory=file_record(inventory_path),
                partners=partners,
                historical_counts=r1_summary["counts"],
                historical_canonical=r1_summary["canonical"],
            ),
        )
        names = ["stage34c_r2r3_summary.json"] + [
            f"replica{r}/{n}"
            for r in PREPARED
            for n in (
                "prepared_trajectory_identity.json",
                "selected_frames.json",
                "shared_authority.json",
                "variant_c_pbc_diagnostic.json",
                "persisted_pbc_validation.json",
                "pbc_audit.json",
                "output/temporal_execution.json",
            )
        ]
        bind_archive(root / C1, C1_SHA, names, work / "history/c1")
        require(
            read(work / "history/c1/stage34c_r2r3_summary.json")["status"] == "PASS",
            "Accepted C.1 is not PASS",
        )
        bind_archive(
            root / c1.INTAKE,
            c1.INTAKE_SHA,
            ["input_compatibility.json"],
            work / "history/intake",
        )
        u, psf, _, _, mapping, authority = c1.shared_authority(
            root, work / "history/intake", work
        )
        require(
            authority["psf"]["sha256"] == classification["psf"]["sha256"],
            "Shared classification PSF differs",
        )
        elements = np.asarray(u.atoms.elements)
        for p in partners:
            indexes = np.asarray(p["atom_indexes"])
            require(
                indexes[elements[indexes] != "H"].tolist() == p["heavy_atom_indexes"],
                "Accepted heavy membership differs",
            )
        # Reconstruct from accepted explicit classes, without reclassification.
        rebuilt = shared.build_metadata(
            u, partners, work / "reconstructed_partner_metadata.json"
        )
        require(
            rebuilt == catalog.bindings[0].partner_catalog,
            "Accepted explicit classification does not reconstruct exact catalog",
        )
        require(
            read_molecular_partner_metadata(
                work / "reconstructed_partner_metadata.json"
            )
            == read_molecular_partner_metadata(
                work / "history/r1/molecular_partner_metadata.json"
            ),
            "Accepted explicit classifications differ",
        )
        control_path = root / C2 / "dataset_release_export_manifest.json"
        control = read_dataset_release_export_manifest(control_path)
        history_names = [
            "dataset_release_export_manifest.json",
            "stage34c2_summary.json",
            "stage31_aggregate_check.json",
            control.decision_set_path,
            control.qc_derived_manifest_path,
            control.protein_aggregate_path,
            *[b.path for b in control.canonical_bindings],
        ]
        frozen_history = bind_archive(
            root / C2, C2_SHA, history_names, work / "history/c2"
        )
        old = read(work / "history/c2/stage34c2_summary.json")
        require(
            old["aggregate_rows"] == 7168
            and old["independent_aggregate_mismatches"] == 0,
            "Accepted protein aggregation evidence differs",
        )
        manifest = read(work / "history/c2" / control.qc_derived_manifest_path)
        require(
            all(
                not group[kind + "_correspondences"]["correspondences"]
                for group in manifest["groups"]
                for kind in ("lipid", "glycan")
            ),
            "Unexpected correspondence",
        )
        dump(work / "frozen_protein_chain.json", frozen_history)
        for replica in PREPARED:
            summary["replicas"].append(
                run_replica(
                    u,
                    psf,
                    mapping,
                    catalog,
                    partners,
                    root,
                    work / f"replica{replica}",
                    replica,
                )
            )
        dump(
            work / "shared_partner_classification_check.json",
            dict(
                status="PASS",
                psf=authority["psf"],
                ignored_identity_fields=list(IDENTITY_FIELDS),
                structural_differences=0,
                classification_ambiguities=0,
                replica_ids=["1", "2", "3"],
                correspondence_created=False,
            ),
        )
        bindings, freezes = [], {}
        for binding in control.canonical_bindings:
            relative = "history/c2/" + binding.path
            path = work / relative
            family = next(f for f in FAMILIES if f.name == binding.family)
            bindings.append(replace(binding, path=relative))
            freezes[relative] = dict(
                **file_record(path), rows=len(family.canonical_reader(path).rows)
            )
        for result in summary["replicas"]:
            replica = result["replica_id"]
            key = (
                "napi2b-stage34b-pilot",
                "namd-wt-2ss-pmm",
                f"egor-2ss-r{replica}-five-frames",
                replica,
            )
            for family, record in result["freeze"].items():
                relative = str(Path(record["path"]).relative_to(work))
                bindings.append(ReleaseCanonicalBinding(family, relative, (key,)))
                freezes[relative] = record
        candidate = replace(control, canonical_bindings=tuple(bindings))
        decisions = read_dataset_qc_decision_set(
            work / "history/c2" / control.decision_set_path
        )
        require(
            all(d.release_decision == "available" for d in decisions.records),
            "Accepted QC availability changed",
        )
        readiness = coverage_readiness(
            candidate, work, {d.replica_key for d in decisions.records}, freezes
        )
        dump(work / "stage33_canonical_coverage_readiness.json", readiness)
        require(readiness["status"] == "PASS", "Canonical coverage is still missing")
        for record in frozen_history:
            require(
                file_record(Path(record["path"])) == record,
                "Historical protein chain changed",
            )
        technical = dict(
            status="passed",
            complete=True,
            error_count=0,
            warning_count=0,
            unsupported_count=0,
            replicas={r["replica_id"]: r["technical"] for r in summary["replicas"]},
        )
        dump(work / "technical_validation.json", technical)
        summary.update(
            status="PASS",
            coverage_readiness=readiness,
            technical=technical,
            shared_authority=authority,
            frozen_protein_chain_unchanged=True,
        )
    except Exception as exc:
        summary["blocker"] = str(exc)
        (work / "failure_traceback.txt").write_text(traceback.format_exc())
        print(f"STOP: {exc}", flush=True)
    finally:
        if u is not None and hasattr(u, "trajectory"):
            u.trajectory.close()
        timings = dict(
            total_seconds=time.perf_counter() - started,
            replicas={r["replica_id"]: r["timings"] for r in summary["replicas"]},
        )
        dump(work / "timings.json", timings)
        summary["timings"] = timings
        dump(work / "stage34c3_summary.json", summary)
        (work / "warnings_limitations.txt").write_text(LIMITATIONS)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("local_md"))
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    work = (
        args.workspace
        or root
        / (
            "stage34c_r2r3_specialized_"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_")
            + uuid4().hex
        )
    ).resolve()
    require(work.is_relative_to(root), "Workspace must be under ignored evidence root")
    require(
        subprocess.run(["git", "check-ignore", "-q", str(work)]).returncode == 0,
        "Workspace must be ignored",
    )
    work.mkdir(exist_ok=False)
    print(f"Evidence workspace: {work}", flush=True)
    summary = run(root, work)
    print(f"Stage 34.C.3: {summary['status']}", flush=True)
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
