"""Stage 30 synthetic acceptance through actual retained Stage 28/29 science."""

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_biological_annotations import glyco, metadata, variant
from test_cli_preprocessing_graph_workflow import FIXED_IDENTITY, invoke_cli
from test_cli_preprocessing_physical_time_execution import physical_command
from test_cli_preprocessing_specialized_contact_export import (
    assert_valid,
    install_specialized,
    records,
)

import mania.cli as cli
from mania import annotated_window_tables_io as annotated_io
from mania import canonical_window_tables_io as canonical_io
from mania.biological_annotations_io import write_dataset_system_biological_annotations
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.canonical_residue_mapping_io import write_canonical_residue_mapping
from mania.preprocessing.artifact_inventory import STAGE30_OUTPUT_ROLES
from mania.preprocessing.dataset_binding import resolve_preprocessing_dataset_context
from mania.preprocessing.input_manifest import load_preprocessing_input_manifest

FAMILIES = {
    "protein_edges": "edge",
    "protein_lipid_contacts": "lipid",
    "protein_glycan_contacts": "glycan",
}


def install_stage30(
    monkeypatch, root, *, mapping=True, annotation=True, specialized=True, empty=False
):
    source, runtimes, spies, paths = install_specialized(
        monkeypatch, root, supplied=specialized, empty=empty
    )
    payload = json.loads(source.manifest_path.read_text())
    for runtime in runtimes:
        runtime.residues[1].resid = 330
        runtime.residues[1].resname = "MET"
    for entry in payload["conditions"]:
        if not mapping:
            continue
        path = source.manifest_path.parent / "mapping.json"
        if not path.exists():
            table = CanonicalResidueMappingTable(
                (
                    CanonicalResidueMappingRecord(
                        "namd", "PROA", "1", "ALA", 311, "GLN", "mapped"
                    ),
                    CanonicalResidueMappingRecord(
                        "namd", "PROA", "330", "MET", 330, "THR", "mapped"
                    ),
                )
            )
            assert write_canonical_residue_mapping(table, path).passed
        entry["canonical_residue_mapping_path"] = path.name
        if annotation:
            path = source.manifest_path.parent / "biology.json"
            if not path.exists():
                identity = entry["dataset_spec"]["identity"]
                data = metadata(
                    dataset_id=identity["dataset_id"],
                    system_id=identity["system_id"],
                    glycosylation_sites=(glyco(present_in_topology=False),),
                    cysteine_variant_sites=(variant(),),
                )
                assert write_dataset_system_biological_annotations(data, path).passed
            entry["biological_annotation_metadata_path"] = path.name
    source.manifest_path.write_text(json.dumps(payload))
    if mapping:
        manifest = load_preprocessing_input_manifest(source.manifest_path)
        *_, specs = cli._preflight_stage30_controls(
            manifest,
            resolve_preprocessing_dataset_context(
                manifest, base_dir=source.manifest_path.parent
            ),
            source.manifest_path.parent,
        )
        paths.update({s.artifact_id: s.local_path for s in specs})
    # Software-identity reload tests intentionally replace the module class.
    # Use the stable existing provenance fixture for order-independent CLI evidence.
    monkeypatch.setattr(cli, "get_software_identity", Mock(return_value=FIXED_IDENTITY))
    return source, runtimes, spies, paths


@pytest.mark.parametrize("annotation", [False, True])
@pytest.mark.parametrize("checksum", ["none", "sha256"])
def test_full_synthetic_acceptance_t330m_lineage_checksums_and_pass_counts(
    monkeypatch, capsys, tmp_path, annotation, checksum
):
    _, runtimes, _, paths = install_stage30(
        monkeypatch, tmp_path, annotation=annotation
    )
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(tmp_path, "--artifact-checksum-mode", checksum),
    )
    assert stderr == "" and json.loads(stdout)["passed"]
    root = tmp_path / "out"
    assert [rt.trajectory.passes for rt in runtimes] == [4, 4]
    assert all(
        rt.trajectory.observed == [(2, i) for i in (0, 2, 4, 6, 8, 10)]
        for rt in runtimes
    )
    inventory, provenance = records(root)
    assert provenance["status"] == "completed"
    config = provenance["resolved_configuration"]
    assert config["canonical_reference"] == {
        "reference_id": "uniprotkb:O95436-1:sequence-v3",
        "sequence_sha256": (
            "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
        ),
    }
    assert len(config["canonical_residue_mapping_bindings"]) == 2
    assert all(
        set(binding)
        == {"dataset_id", "system_id", "trajectory_id", "replica_id", "mapping_path"}
        for binding in config["canonical_residue_mapping_bindings"]
    )
    if annotation:
        assert len(config["biological_annotation_bindings"]) == 1
        assert set(config["biological_annotation_bindings"][0]) == {
            "dataset_id",
            "system_id",
            "annotation_metadata_path",
        }
    else:
        assert "biological_annotation_bindings" not in config
    for family, kind in FAMILIES.items():
        role = f"{family}_by_window_canonical"
        canonical = getattr(canonical_io, f"read_canonical_protein_{kind}_window_csv")(
            root / f"{role}.csv"
        )
        assert canonical.rows and all(row.condition is None for row in canonical.rows)
        annotated_path = root / f"{role}_annotated.csv"
        assert annotated_path.exists() is annotation
        if annotation:
            table = getattr(
                annotated_io, f"read_annotated_canonical_protein_{kind}_window_csv"
            )(annotated_path)
            assert all(row.condition is None for row in table.rows)
            assert {row.replica_id for row in table.rows} == {"1", "2"}
            for row in table.rows:
                if kind != "edge" and row.protein_resid != "330":
                    continue
                prefix = "target_" if kind == "edge" else ""
                assert (
                    getattr(
                        row, "target_resname" if kind == "edge" else "protein_resname"
                    )
                    == "MET"
                )
                assert getattr(row, prefix + "canonical_resname") == "THR"
                assert getattr(row, prefix + "is_ecd") and getattr(
                    row, prefix + "is_mx35_region"
                )
                assert getattr(row, prefix + "is_glycosylation_site")
                assert (
                    getattr(row, prefix + "glycosylation_present_in_topology") is False
                )
                assert getattr(row, prefix + "is_cysteine_variant_site")
                assert not getattr(row, prefix + "is_disulfide_variant_site")
    stage30 = [
        e
        for e in inventory["artifacts"]
        if e["role"]
        in (
            *STAGE30_OUTPUT_ROLES,
            "canonical_residue_mapping",
            "biological_annotation_metadata",
        )
    ]
    assert len(stage30) == (9 if annotation else 5)
    for entry in stage30:
        local = (
            paths[entry["artifact_id"]]
            if entry["direction"] == "input"
            else root / entry["path"]
        )
        assert entry["condition"] is None
        assert not Path(entry["path"]).is_absolute()
        assert entry["sha256"] == (
            hashlib.sha256(local.read_bytes()).hexdigest()
            if checksum == "sha256"
            else None
        )
        if entry["direction"] == "output":
            assert {"role": entry["role"], "path": entry["path"]} in provenance[
                "artifact_references"
            ]
    assert_valid(root, paths)


@pytest.mark.parametrize("case", ["mapping", "annotation", "system", "conflict"])
def test_invalid_controls_fail_before_trajectory_access(
    monkeypatch, capsys, tmp_path, case
):
    source, runtimes, spies, _ = install_stage30(monkeypatch, tmp_path)
    parent = source.manifest_path.parent
    if case in ("mapping", "annotation"):
        (parent / ("mapping.json" if case == "mapping" else "biology.json")).write_text(
            "{"
        )
    else:
        path = parent / "biology.json"
        data = json.loads(path.read_text())
        if case == "system":
            data["system_id"] = "wrong-system"
        else:
            data["glycosylation_sites"] = []
            path = parent / "conflict.json"
            payload = json.loads(source.manifest_path.read_text())
            payload["conditions"][1]["biological_annotation_metadata_path"] = path.name
            source.manifest_path.write_text(json.dumps(payload))
        path.write_text(json.dumps(data))
    _, _, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    assert stderr.startswith(
        "Canonical residue mapping failed:"
        if case == "mapping"
        else "Biological annotation failed:"
    )
    assert "Traceback" not in stderr
    assert [rt.trajectory.passes for rt in runtimes] == [0, 0]
    spies["compute_preprocessing_graph_workflow_rg_contacts"].assert_not_called()
    cli.load_preprocessing_graph_workflow_condition_runtimes.assert_not_called()


@pytest.mark.parametrize(
    "case,prefix",
    [
        ("coverage", "Canonical table generation failed:"),
        ("partial_mapping", "Canonical table generation failed:"),
        ("partial_annotation", "Biological annotation failed:"),
        ("canonical_write", "Canonical table export write failed:"),
        ("annotated_write", "Annotated table export write failed:"),
    ],
)
def test_late_failure_preserves_science_and_has_no_false_output_claims(
    monkeypatch, capsys, tmp_path, case, prefix
):
    source, runtimes, _, paths = install_stage30(monkeypatch, tmp_path)
    if case == "coverage":
        path = source.manifest_path.parent / "mapping.json"
        data = json.loads(path.read_text())
        data["mappings"] = data["mappings"][:1]
        data["mapping_count"] = 1
        path.write_text(json.dumps(data))
    elif case.startswith("partial_"):
        payload = json.loads(source.manifest_path.read_text())
        second = payload["conditions"][1]
        if case == "partial_mapping":
            second.pop("canonical_residue_mapping_path")
            second.pop("biological_annotation_metadata_path")
        else:
            second["dataset_spec"]["identity"]["system_id"] = "without-annotation"
            second.pop("biological_annotation_metadata_path")
        source.manifest_path.write_text(json.dumps(payload))
        # Recollect current control IDs; the external inputs are explicit.
        manifest = load_preprocessing_input_manifest(source.manifest_path)
        *_, specs = cli._preflight_stage30_controls(
            manifest,
            resolve_preprocessing_dataset_context(
                manifest, base_dir=source.manifest_path.parent
            ),
            source.manifest_path.parent,
        )
        paths = {k: v for k, v in paths.items() if "canonical_residue_mapping" not in k}
        paths.update({s.artifact_id: s.local_path for s in specs})
    else:
        module = canonical_io if case == "canonical_write" else annotated_io
        name = (
            "write_canonical_protein_edge_window_csv"
            if case == "canonical_write"
            else "write_annotated_canonical_protein_edge_window_csv"
        )
        monkeypatch.setattr(module, name, Mock(side_effect=OSError("private path")))
    _, _, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    assert (
        prefix in stderr and "Traceback" not in stderr and "private path" not in stderr
    )
    assert [rt.trajectory.passes for rt in runtimes] == [4, 4]
    root = tmp_path / "out"
    inventory, provenance = records(root)
    assert provenance["status"] == "failed"
    for family in FAMILIES:
        assert (root / f"{family}_by_window_source.csv").is_file()
    for reference in provenance["artifact_references"]:
        if reference["role"] in STAGE30_OUTPUT_ROLES:
            assert (root / reference["path"]).is_file()
    for entry in inventory["artifacts"]:
        if entry["role"] in STAGE30_OUTPUT_ROLES:
            assert (root / entry["path"]).is_file()
    assert_valid(root, paths)


def test_determinism_source_science_preservation_and_no_mapping_no_work(
    monkeypatch, capsys, tmp_path
):
    roots = []
    for label, mapped in (("baseline", False), ("first", True), ("second", True)):
        base = tmp_path / label
        with monkeypatch.context() as patch:
            _, runtimes, _, paths = install_stage30(patch, base, mapping=mapped)
            if not mapped:
                patch.setattr(
                    cli,
                    "_preflight_stage30_controls",
                    Mock(side_effect=AssertionError("No Stage 30 without controls")),
                )
                patch.setattr(
                    cli,
                    "_export_stage30_tables",
                    Mock(side_effect=AssertionError("No Stage 30 without controls")),
                )
            invoke_cli(patch, capsys, *physical_command(base))
            assert [rt.trajectory.passes for rt in runtimes] == [4, 4]
            assert_valid(base / "out", paths)
        roots.append(base / "out")
    baseline, first, second = roots
    for role in STAGE30_OUTPUT_ROLES:
        assert not (baseline / f"{role}.csv").exists()
        assert (first / f"{role}.csv").read_bytes() == (
            second / f"{role}.csv"
        ).read_bytes()
    # Every existing scientific artifact is compared, including the source tables.
    inventory, _ = records(baseline)
    for entry in inventory["artifacts"]:
        if entry["direction"] != "output" or entry["role"] in (
            "runtime_metadata",
            "graph_diagnostics_report",
        ):
            continue
        for root in (first, second):
            assert (root / entry["path"]).read_bytes() == (
                baseline / entry["path"]
            ).read_bytes(), entry["role"]


@pytest.mark.parametrize("empty", [False, True])
def test_existing_sources_only_and_header_only_tables(
    monkeypatch, capsys, tmp_path, empty
):
    _, runtimes, _, paths = install_stage30(
        monkeypatch, tmp_path, specialized=empty, empty=empty
    )
    if empty:
        from mania.preprocessing.protein_edge_window_table import (
            DatasetProteinEdgeWindowTable,
        )
        from mania.preprocessing.specialized_contact_window_tables import (
            ProteinGlycanWindowTable,
            ProteinLipidWindowTable,
        )

        monkeypatch.setattr(
            cli,
            "build_preprocessing_protein_edge_window_source_table",
            Mock(return_value=DatasetProteinEdgeWindowTable(())),
        )
        monkeypatch.setattr(
            cli,
            "build_specialized_contact_source_tables",
            Mock(
                return_value=(ProteinLipidWindowTable(()), ProteinGlycanWindowTable(()))
            ),
        )
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    if empty:
        for role in STAGE30_OUTPUT_ROLES:
            assert len((root / f"{role}.csv").read_text().splitlines()) == 1
    else:
        assert [rt.trajectory.passes for rt in runtimes] == [3, 3]
        for family in ("protein_lipid_contacts", "protein_glycan_contacts"):
            for suffix in ("source", "canonical", "canonical_annotated"):
                assert not (root / f"{family}_by_window_{suffix}.csv").exists()
    assert_valid(root, paths)


def test_workflow_and_validation_offline_no_md_reads_or_directory_scan(
    monkeypatch, capsys, tmp_path
):
    import socket
    import urllib.request

    import mania.artifact_inventory_io as inventory_io
    import mania.validation.run_artifacts as integrity

    _, _, _, paths = install_stage30(monkeypatch, tmp_path)
    forbidden = Mock(
        side_effect=AssertionError(
            "Unexpected network, content hash, or directory scan"
        )
    )
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(inventory_io, "stream_file_sha256", forbidden)
    monkeypatch.setattr(integrity, "stream_file_sha256", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        if path.suffix in (".xtc", ".tpr", ".gro", ".psf", ".dcd"):
            pytest.fail("Offline Stage 30 validation accessed MD contents")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert_valid(tmp_path / "out", paths)


def test_mapping_and_annotations_bind_resolved_parameter_table_replicas(
    monkeypatch, capsys, tmp_path
):
    from test_preprocessing_dataset_binding import reference, write_table

    from mania.dataset_identity import DatasetTrajectorySpec

    source, runtimes, _, paths = install_stage30(monkeypatch, tmp_path)
    payload = json.loads(source.manifest_path.read_text())
    specs = []
    for entry in payload["conditions"]:
        spec = DatasetTrajectorySpec.model_validate(entry.pop("dataset_spec"))
        entry["dataset_ref"] = reference(spec)
        specs.append(spec)
    path = write_table(source.manifest_path.parent / "parameters.csv", *specs)
    payload["dataset_parameter_table_path"] = path.name
    source.manifest_path.write_text(json.dumps(payload))
    paths["input:dataset_parameter_table"] = path
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    assert [rt.trajectory.passes for rt in runtimes] == [4, 4]
    assert_valid(tmp_path / "out", paths)
