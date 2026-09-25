"""Synthetic C.3 guards; real evidence is never an implicit test prerequisite."""

import ast
import copy
import importlib.util
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from test_replica_protein_edge_aggregation import row as protein_row
from test_replica_specialized_aggregation import row as specialized_row
from test_stage34b4_namd_specialized_pilot import synthetic

from mania import canonical_window_tables_io as canonical_io
from mania.preprocessing.molecular_partner_catalog_io import (
    MolecularPartnerCatalogBinding,
    PreprocessingMolecularPartnerCatalog,
)

spec = importlib.util.spec_from_file_location(
    "stage34c3", Path(__file__).parents[1] / "tools/stage34c_r2r3_specialized.py"
)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


@pytest.fixture
def small(tmp_path):
    u, partners, temporal = synthetic(tmp_path)
    identity = temporal.bindings[0].dataset_spec.identity.model_copy(
        update=dict(trajectory_id="egor-2ss-r1-five-frames")
    )
    binding = replace(
        temporal.bindings[0],
        dataset_spec=temporal.bindings[0].dataset_spec.model_copy(
            update=dict(identity=identity)
        ),
    )
    temporal = replace(temporal, bindings=(binding,))
    catalog = pilot.shared.build_metadata(
        u, partners, tmp_path / "catalog_metadata.json"
    )
    accepted = PreprocessingMolecularPartnerCatalog(
        (
            MolecularPartnerCatalogBinding(
                binding.execution_condition, binding.dataset_spec, "available", catalog
            ),
        )
    )
    return u, partners, temporal, accepted


def new_temporal(temporal, replica):
    binding = temporal.bindings[0]
    identity = binding.dataset_spec.identity.model_copy(
        update=dict(
            replica_id=replica, trajectory_id=f"egor-2ss-r{replica}-five-frames"
        )
    )
    return replace(
        temporal,
        bindings=(
            replace(
                binding,
                dataset_spec=binding.dataset_spec.model_copy(
                    update=dict(identity=identity)
                ),
            ),
        ),
    )


@pytest.mark.parametrize("replica", ["2", "3"])
def test_exact_identity_rebinding_and_no_r1_reuse(small, replica):
    _, _, temporal, accepted = small
    rebound = pilot.rebind_catalog(accepted, new_temporal(temporal, replica), replica)
    pilot.compare_catalogs(accepted, rebound, replica)
    assert rebound.bindings[0].dataset_spec.identity.replica_id == replica
    assert pilot.structural_catalog(rebound) == pilot.structural_catalog(accepted)
    with pytest.raises(ValueError, match="not rebound"):
        pilot.compare_catalogs(accepted, accepted, replica)
    with pytest.raises(ValueError, match="Only explicit"):
        pilot.rebind_catalog(accepted, temporal, replica)


@pytest.mark.parametrize(
    "field,value",
    [
        ("condition", "PMm"),
        ("system_id", "changed"),
        ("engine", "gromacs"),
        ("variant_id", "T330M"),
        ("disulfide_state", "4SS"),
    ],
)
def test_only_two_identity_fields_are_ignored(small, field, value):
    _, _, temporal, accepted = small
    temporal = new_temporal(temporal, "2")
    binding = temporal.bindings[0]
    identity = binding.dataset_spec.identity.model_copy(update={field: value})
    changed = replace(
        temporal,
        bindings=(
            replace(
                binding,
                execution_condition=value
                if field == "condition"
                else binding.execution_condition,
                dataset_spec=binding.dataset_spec.model_copy(
                    update=dict(identity=identity)
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="Only explicit"):
        pilot.rebind_catalog(accepted, changed, "2")


@pytest.mark.parametrize("change", ["membership", "classification", "anchor"])
def test_component_classification_or_anchor_difference_stops(small, change):
    _, _, temporal, accepted = small
    rebound = pilot.rebind_catalog(accepted, new_temporal(temporal, "2"), "2")
    data = rebound.to_dict()
    part = data["bindings"][0]["partner_catalog"]["partners"][0]
    if change == "membership":
        part["component_atom_indexes"].append(99)
    elif change == "classification":
        part["partner_name"] = "invented"
    else:
        part = next(
            p
            for p in data["bindings"][0]["partner_catalog"]["partners"]
            if p["partner_kind"] == "glycan"
        )
        part["carrier_link_bond"] = None
    candidate = SimpleNamespace(bindings=rebound.bindings, to_dict=lambda: data)
    with pytest.raises(ValueError, match="structure or classification"):
        pilot.compare_catalogs(accepted, candidate, "2")


@pytest.mark.parametrize("replica", ["2", "3"])
def test_shared_psf_and_prepared_hash_guards(tmp_path, replica):
    psf = tmp_path / "shared.psf"
    psf.write_bytes(b"wrong PSF")
    with pytest.raises(ValueError, match="SHA256"):
        pilot.prepared_binding(None, psf, tmp_path, tmp_path, replica, tmp_path)
    prepared = tmp_path / "prepared.xtc"
    prepared.write_bytes(b"wrong prepared bytes")
    with pytest.raises(ValueError, match="SHA256"):
        pilot.b3.require_hash(prepared, pilot.PREPARED[replica], "prepared")


def test_accepted_archive_classification_cannot_be_substituted(tmp_path):
    base = tmp_path / "accepted"
    base.mkdir()
    name = "classification.json"
    (base / name).write_text('{"authority": "accepted"}')
    with zipfile.ZipFile(base.with_suffix(".zip"), "w") as archive:
        archive.write(base / name, name)
    sha = pilot.file_record(base.with_suffix(".zip"))["sha256"]
    pilot.bind_archive(base, sha, [name], tmp_path / "bound")
    (base / name).write_text('{"authority": "substituted"}')
    with pytest.raises(ValueError, match="Accepted evidence changed"):
        pilot.bind_archive(base, sha, [name], tmp_path / "bad")


@pytest.mark.parametrize("change", ["psf", "unresolved", "count", "status"])
def test_r1_classification_authority_gate(small, change):
    _, _, _, catalog = small
    partner_catalog = SimpleNamespace(lipid_partner_count=828, glycan_partner_count=2)
    catalog = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                dataset_spec=catalog.bindings[0].dataset_spec,
                partner_catalog=partner_catalog,
            ),
        )
    )
    summary = dict(stage34b4_status="PASS")
    inventory = dict(status="PASS", unresolved=[], counts=dict(membrane=828, glycan=2))
    classification = dict(psf=dict(sha256=pilot.b3.PSF_SHA256))
    pilot.validate_r1_authority(summary, catalog, inventory, classification)
    if change == "psf":
        classification["psf"]["sha256"] = "other"
    elif change == "unresolved":
        inventory["unresolved"] = ["unknown"]
    elif change == "count":
        inventory["counts"]["membrane"] = 827
    else:
        summary["stage34b4_status"] = "FAIL"
    with pytest.raises(ValueError):
        pilot.validate_r1_authority(summary, catalog, inventory, classification)


def test_exact_anchor_atoms_membership_and_replica_metadata(small):
    u, _, _, _ = small
    u.atoms.names = ["ND2", "ND2", "C1", "C1", "C", "C"]
    context = pilot.b3.pbc.topology_context(u)
    anchors = pilot.shared.glycan_components(u, context, context["heavy"])
    assert pilot.validate_anchors(u, anchors, anchors) == anchors
    assert [p["carrier_residue"]["resid"] for p in anchors] == [295, 308]
    changed = copy.deepcopy(anchors)
    changed[0]["atom_indexes"].append(99)
    with pytest.raises(ValueError, match="membership/anchor"):
        pilot.validate_anchors(u, anchors, changed)
    u.atoms.names = ["C", "ND2", "C1", "C1", "C", "C"]
    context = pilot.b3.pbc.topology_context(u)
    wrong = pilot.shared.glycan_components(u, context, context["heavy"])
    with pytest.raises(ValueError, match="Accepted anchor"):
        pilot.validate_anchors(u, wrong, wrong)


@pytest.mark.parametrize("kind,cutoff", [("lipid", 6.0), ("glycan", 4.5)])
def test_direct_no_mic_inclusive_cutoffs(kind, cutoff):
    distance = pilot.shared.minimum_distance([[0, 0, 0]], [[cutoff, 0, 0]])
    partner = dict(carrier_residue=dict(residue_index=99))
    assert pilot.shared.ordinary_positive(kind, distance, 0, partner)
    assert not pilot.shared.ordinary_positive(
        kind, np.nextafter(cutoff, np.inf), 0, partner
    )
    # A 10-A periodic cell could wrap this separation, but direct geometry does not.
    assert pilot.shared.minimum_distance([[0, 0, 0]], [[9, 0, 0]]) == 9
    assert not pilot.shared.ordinary_positive(kind, 9, 0, partner)


def test_independent_geometry_windows_and_anchor_exclusion(
    small, tmp_path, monkeypatch
):
    u, partners, temporal, _ = small
    execution, tables = pilot.b4.execute_science(u, temporal, tmp_path)
    import mania.preprocessing.specialized_contact_execution as production

    forbidden = Mock(
        side_effect=AssertionError("Independent checker called production")
    )
    monkeypatch.setattr(production, "execute_specialized_contact_condition", forbidden)
    monkeypatch.setattr(
        production, "build_specialized_contact_source_tables", forbidden
    )
    observations = pilot.b4.independent_observations(u, partners)
    check = pilot.b4.compare_independent(
        observations, execution.condition_results[0], tables
    )
    assert check["status"] == "PASS"
    assert sum(r["standard_summary_excluded"] for r in observations) == 10
    assert not tables[1].rows
    row = tables[0].rows[0]
    assert (row.n_contact_frames, row.occupancy, row.n_contact_episodes) == (3, 0.6, 3)
    assert row.mean_episode_length_ns == row.max_episode_length_ns == 0
    damaged = [dict(r) for r in observations]
    damaged[0]["minimum_distance_A"] += 0.01
    assert (
        pilot.b4.compare_independent(damaged, execution.condition_results[0], tables)[
            "geometry_mismatches"
        ]
        == 1
    )
    damaged = [dict(r) for r in observations]
    anchor = next(r for r in damaged if r["standard_summary_excluded"])
    anchor["standard_summary_excluded"] = False
    assert (
        pilot.b4.compare_independent(damaged, execution.condition_results[0], tables)[
            "anchor_exclusion_mismatches"
        ]
        == 1
    )
    forbidden.assert_not_called()


def test_intentional_stride_and_positive_only_distance_summaries():
    rows = [
        dict(
            partner_kind="lipid",
            protein_residue_index=0,
            partner_id="L",
            prepared_frame_index=i,
            minimum_distance_A=d,
            standard_summary_excluded=False,
        )
        for i, d in [(0, 2), (1, 4), (4, 6)]
    ]
    result = pilot.shared.aggregate_observations(rows, times=pilot.b3.TIMES_PS)
    metrics = result[("lipid", 0, "L")]
    assert metrics == dict(
        n_contact_frames=3,
        occupancy=0.6,
        n_contact_episodes=2,
        mean_episode_length_ns=0.05,
        max_episode_length_ns=0.1,
        distance_mean_A=4,
        distance_min_A=2,
    )


def test_canonical_scientific_value_preservation(small, tmp_path):
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping import (
        CanonicalResidueMappingRecord,
        CanonicalResidueMappingTable,
    )

    u, _, temporal, _ = small
    execution, tables = pilot.b4.execute_science(u, temporal, tmp_path)
    ref = load_default_napi2b_canonical_reference()
    mapping = CanonicalResidueMappingTable(
        tuple(
            CanonicalResidueMappingRecord(
                "namd",
                "PROA",
                str(n),
                "ASN",
                n,
                ref.residue_at(n).canonical_resname,
                "mapped",
            )
            for n in (295, 308)
        )
    )
    canonical, technical = pilot.b4.export_validate(
        execution, tables, mapping, temporal, tmp_path
    )
    assert (
        canonical["lipid"]["source_rows"] == canonical["lipid"]["canonical_rows"] == 1
    )
    assert canonical["lipid"]["scientific_value_mismatches"] == 0
    assert technical["complete"] and technical["status"] == "passed"


@pytest.fixture
def coverage_case(tmp_path):
    bindings, freezes = [], {}
    for family in pilot.FAMILIES:
        for replica in ("1", "2", "3"):
            row = (
                protein_row(replica_id=replica)
                if family.name == "protein"
                else specialized_row(family.name, replica_id=replica)
            )
            model = family.canonical_table((row,))
            directory = tmp_path / family.name / replica
            directory.mkdir(parents=True)
            writer = getattr(
                canonical_io,
                "write_canonical_protein_"
                + ("edge" if family.name == "protein" else family.name)
                + "_window_csv",
            )
            assert writer(model, directory).passed
            path = next(directory.glob("*.csv"))
            relative = str(path.relative_to(tmp_path))
            bindings.append(
                pilot.ReleaseCanonicalBinding(family.name, relative, (row.replica_key,))
            )
            freezes[relative] = dict(**pilot.file_record(path), rows=1)
    keys = tuple(b.replica_keys[0] for b in bindings[:3])
    control = SimpleNamespace(
        canonical_bindings=tuple(bindings), scientific_release_replica_keys=keys
    )
    return control, tmp_path, set(keys), freezes


def test_complete_strict_canonical_coverage_without_downstream_execution(
    coverage_case, monkeypatch
):
    import mania.dataset_release_run as release
    import mania.dataset_release_workflow as workflow
    import mania.replica_aggregation_run as aggregation

    forbidden = Mock(side_effect=AssertionError("Forbidden downstream execution"))
    monkeypatch.setattr(release, "run_dataset_release", forbidden)
    monkeypatch.setattr(workflow, "build_dataset_release", forbidden)
    monkeypatch.setattr(aggregation, "run_replica_aggregation", forbidden)
    report = pilot.coverage_readiness(*coverage_case)
    assert report["status"] == "PASS" and report["complete"]
    assert len(report["sources"]) == 9 and not report["missing_canonical_coverage"]
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "family,replica", [("lipid", "2"), ("glycan", "3"), ("protein", "1")]
)
def test_readiness_reports_exact_missing_family_replica(coverage_case, family, replica):
    control, base, candidates, freezes = coverage_case
    removed = next(
        b
        for b in control.canonical_bindings
        if b.family == family and b.replica_keys[0][-1] == replica
    )
    control.canonical_bindings = tuple(
        b for b in control.canonical_bindings if b != removed
    )
    report = pilot.coverage_readiness(control, base, candidates, freezes)
    assert report["status"] == "STOP"
    assert report["missing_canonical_coverage"] == [
        dict(family=family, replica_key=removed.replica_keys[0])
    ]
    assert "lacks required canonical" in report["frozen_validator_error"]


@pytest.mark.parametrize("change", ["missing", "empty", "modified", "unbound"])
def test_readiness_rejects_fake_or_missing_frozen_sources(coverage_case, change):
    control, base, candidates, freezes = coverage_case
    binding = control.canonical_bindings[-1]
    path = base / binding.path
    if change == "missing":
        path.unlink()
    elif change == "empty":
        path.write_text(path.read_text().splitlines()[0] + "\n")
        freezes[binding.path] = dict(**pilot.file_record(path), rows=0)
    elif change == "modified":
        path.write_text(path.read_text() + "\n")
    else:
        del freezes[binding.path]
    report = pilot.coverage_readiness(control, base, candidates, freezes)
    assert report["status"] == "STOP" and report["invalid_sources"]


def test_runner_contains_no_downstream_or_scientific_recomputation_calls():
    tree = ast.parse(Path(pilot.__file__).read_text())
    called = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    forbidden = (
        "run_replica_aggregation",
        "run_dataset_release",
        "build_dataset_release",
        "run_dataset_qc",
        "run_protein",
        "rmsd_evidence",
        "diagnose",
        "persist",
        "SpecializedPartnerCorrespondence",
        "ReplicaAggregationManifest",
    )
    assert not any(name.split(".")[-1] in forbidden for name in called)
    assert pilot.IDENTITY_FIELDS == ("trajectory_id", "replica_id")


@pytest.mark.parametrize("replica", ["2", "3"])
def test_replica_orchestration_exports_real_science_and_freezes(
    small, tmp_path, monkeypatch, replica
):
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping import (
        CanonicalResidueMappingRecord,
        CanonicalResidueMappingTable,
    )
    from mania.preprocessing.molecular_partner_metadata_io import (
        read_molecular_partner_metadata,
        write_molecular_partner_metadata,
    )

    u, partners, temporal, accepted = small
    u.atoms.names = ["ND2", "ND2", "C1", "C1", "C", "C"]
    for ts in u.trajectory:
        ts.positions[1, 0] = 5
        ts.positions[2, 0] = 0.5
        ts.positions[3, 0] = 6
    context = pilot.b3.pbc.topology_context(u)
    anchors = pilot.shared.glycan_components(u, context, context["heavy"])
    partners = copy.deepcopy(anchors) + [
        p for p in partners if p["partner_kind"] == "lipid"
    ]
    for p in partners:
        p["heavy_atom_indexes"] = p["atom_indexes"]
    history = tmp_path / "history/r1"
    history.mkdir(parents=True)
    pilot.dump(history / "glycan_anchor_metadata.json", anchors)
    metadata = read_molecular_partner_metadata(
        tmp_path / "molecular_partner_metadata.json"
    )
    assert write_molecular_partner_metadata(
        metadata, history / "molecular_partner_metadata.json"
    ).passed
    temporal = new_temporal(temporal, replica)
    monkeypatch.setattr(
        pilot,
        "prepared_binding",
        lambda *args: (temporal, dict(prepared=dict(sha256="synthetic-prepared"))),
    )
    reference = load_default_napi2b_canonical_reference()
    mapping = CanonicalResidueMappingTable(
        tuple(
            CanonicalResidueMappingRecord(
                "namd",
                "PROA",
                str(n),
                "ASN",
                n,
                reference.residue_at(n).canonical_resname,
                "mapped",
            )
            for n in (295, 308)
        )
    )
    result = pilot.run_replica(
        u,
        None,
        mapping,
        accepted,
        partners,
        tmp_path,
        tmp_path / f"replica{replica}",
        replica,
    )
    assert result["status"] == "PASS"
    assert result["counts"]["anchor_observations_excluded"] == 10
    assert result["counts"]["ordinary_glycan_positives"] == 5
    for family, freeze in result["freeze"].items():
        assert freeze["sha256"] == pilot.file_record(Path(freeze["path"]))["sha256"]
        assert freeze["rows"] == result["canonical"][family]["source_rows"] > 0
    rebound = pilot.read_molecular_partner_catalog(
        tmp_path / f"r{replica}_partner_catalog.json"
    )
    pilot.compare_catalogs(accepted, rebound, replica)


def test_frozen_coverage_rejects_unrecognized_source_digest(monkeypatch, tmp_path):
    monkeypatch.setattr(pilot, "file_record", lambda path: {"sha256": "0" * 64})
    with pytest.raises(ValueError, match="coverage validator SHA256"):
        pilot.frozen_coverage_gate(None, tmp_path, set())
