"""End-to-end synthetic specialized execution, lineage and offline acceptance."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_physical_time_execution import (
    install_physical,
    physical_command,
)
from test_preprocessing_molecular_partner_metadata_io import metadata
from test_preprocessing_trajectory_contacts_compute_condition import (
    FakeAtom,
    FakeResidue,
)

import mania.cli as cli
from mania.preprocessing.molecular_partner_metadata_io import (
    write_molecular_partner_metadata,
)
from mania.preprocessing.specialized_contact_window_tables_io import (
    read_protein_glycan_window_csv,
    read_protein_lipid_window_csv,
)
from mania.validation import validate_run_artifacts

ROLES = (
    "molecular_partner_catalog",
    "protein_lipid_contacts_by_window_source",
    "protein_glycan_contacts_by_window_source",
)
FILES = (
    "molecular_partner_catalog.json",
    "protein_lipid_contacts_by_window_source.csv",
    "protein_glycan_contacts_by_window_source.csv",
)


def install_specialized(
    monkeypatch,
    root,
    *,
    kinds=(True, True),
    external=False,
    empty=False,
    supplied=True,
    mode="inline",
    nullable=True,
    one_condition=False,
    times=None,
    temporal=None,
):
    source, runtimes, spies, mappings = install_physical(
        monkeypatch, root, mode=mode, times=times, temporal=temporal
    )
    payload = json.loads(source.manifest_path.read_text())
    for ordinal, (entry, rt) in enumerate(
        zip(payload["conditions"], runtimes, strict=True), 1
    ):
        rt.residues.extend(
            [
                FakeResidue("UNCLASSIFIED-X", 100, [FakeAtom(position=(2, 0, 0))]),
                FakeResidue("UNCLASSIFIED-Y", 101, [FakeAtom(position=(1, 0, 0))]),
            ]
        )
        for i, residue in enumerate(rt.residues):
            residue.ix = i
            for atom in residue.atoms:
                atom.index = i
        rt.select_atoms = Mock(return_value=SimpleNamespace(residues=rt.residues[:2]))
        if not external:
            rt.bonds = [SimpleNamespace(indices=(0, 3))]
        if nullable and "dataset_spec" in entry:
            identity = entry["dataset_spec"]["identity"]
            identity.update(
                condition=None,
                engine="namd",
                system_id="same-system",
                trajectory_id="same-trajectory",
                replica_id=str(ordinal),
            )
        if supplied and not (one_condition and ordinal == 2):
            path = source.manifest_path.parent / f"partners-{ordinal}.json"
            assert write_molecular_partner_metadata(
                metadata(
                    lipid=kinds[0] and not empty,
                    glycan=kinds[1] and not empty,
                    external=external,
                ),
                path,
            ).passed
            entry["molecular_partner_metadata_path"] = path.name
            if "dataset_spec" in entry or "dataset_ref" in entry:
                mappings[
                    f"input:condition:{ordinal:04d}:molecular_partner_metadata"
                ] = path
    source.manifest_path.write_text(json.dumps(payload))
    for name in (
        "read_specialized_metadata_inputs",
        "execute_preprocessing_specialized_contacts",
        "build_specialized_contact_source_tables",
        "write_molecular_partner_catalog",
        "write_protein_lipid_window_csv",
        "write_protein_glycan_window_csv",
    ):
        spies[name] = Mock(wraps=getattr(cli, name))
        monkeypatch.setattr(cli, name, spies[name])
    return source, runtimes, spies, mappings


def records(root):
    return (
        json.loads((root / "artifact_inventory.json").read_text()),
        json.loads((root / "run_provenance.json").read_text()),
    )


def assert_valid(root, mappings):
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete, report.to_dict()
    assert report.unsupported_count == 0
    return report


@pytest.mark.parametrize("kinds", [(True, False), (False, True), (True, True)])
@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("checksum", ["none", "sha256"])
def test_specialized_run_catalog_tables_pass_counts_and_lineage(
    monkeypatch, capsys, tmp_path, kinds, external, checksum
):
    source, runtimes, spies, mappings = install_specialized(
        monkeypatch, tmp_path, kinds=kinds, external=external
    )
    if checksum == "none":
        import mania.artifact_inventory_io as inventory_io
        import mania.validation.run_artifacts as integrity

        forbidden = Mock(side_effect=AssertionError("No content hashes in none mode"))
        monkeypatch.setattr(inventory_io, "stream_file_sha256", forbidden)
        monkeypatch.setattr(integrity, "stream_file_sha256", forbidden)
    _, stdout, stderr = invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(tmp_path, "--artifact-checksum-mode", checksum),
    )
    assert stderr == "" and json.loads(stdout)["passed"]
    root = tmp_path / "out"
    assert [rt.trajectory.passes for rt in runtimes] == [4, 4]
    # PBC stayed attached to the accepted Rg pass only.
    assert all(
        rt.trajectory.observed == [(2, i) for i in (0, 2, 4, 6, 8, 10)]
        for rt in runtimes
    )
    lipid = read_protein_lipid_window_csv(root / FILES[1])
    glycan = read_protein_glycan_window_csv(root / FILES[2])
    assert bool(lipid.rows) is kinds[0] and bool(glycan.rows) is kinds[1]
    for table in (lipid, glycan):
        assert all(row.condition is None for row in table.rows)
        if table.rows:
            assert {row.replica_id for row in table.rows} == {"1", "2"}
    assert all(row.protein_residue_index == 1 for row in glycan.rows)
    assert all(
        row.occupancy == 1.0 and row.distance_mean_A == row.distance_min_A == 2.0
        for row in glycan.rows
    )
    inventory, provenance = records(root)
    assert provenance["status"] == "completed"
    assert all(
        sum(r["role"] == role for r in provenance["artifact_references"]) == 1
        for role in ROLES
    )
    context = provenance["resolved_configuration"]["dataset_context"]
    assert all(
        b["dataset_spec"]["identity"]["condition"] is None for b in context["bindings"]
    )
    for entry in inventory["artifacts"]:
        if entry["role"] in (*ROLES, "molecular_partner_metadata"):
            path = (
                mappings[entry["artifact_id"]]
                if entry["direction"] == "input"
                else root / entry["path"]
            )
            assert entry["sha256"] == (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if checksum == "sha256"
                else None
            )
            assert not entry["path"].startswith("/")
    assert_valid(root, mappings)
    if checksum == "sha256":
        target = root / FILES[0]
        target.write_bytes(
            target.read_bytes()
            .replace(b"LIPID-X", b"LIPID-Y")
            .replace(b"GLYCAN-X", b"GLYCAN-Y")
        )
        assert (
            validate_run_artifacts(
                root, scope="preprocessing", input_artifact_paths=mappings
            ).status
            == "failed"
        )
    for name in (
        "execute_preprocessing_specialized_contacts",
        "build_specialized_contact_source_tables",
    ):
        spies[name].assert_called_once()


@pytest.mark.parametrize(
    "case", ["empty", "no_metadata", "legacy", "mixed", "one_condition"]
)
def test_empty_and_opt_in_boundaries(monkeypatch, capsys, tmp_path, case):
    _, runtimes, spies, mappings = install_specialized(
        monkeypatch,
        tmp_path,
        empty=case == "empty",
        supplied=case != "no_metadata",
        mode="legacy" if case == "legacy" else "mixed" if case == "mixed" else "inline",
        one_condition=case == "one_condition",
    )
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    inventory, provenance = records(root)
    if case in ("no_metadata", "legacy"):
        assert all(not (root / filename).exists() for filename in FILES)
        assert all(
            e["role"] not in (*ROLES, "molecular_partner_metadata")
            for e in inventory["artifacts"]
        )
        assert all(e["role"] not in ROLES for e in provenance["artifact_references"])
        spies["execute_preprocessing_specialized_contacts"].assert_not_called()
    if case == "empty":
        assert all((root / f).exists() for f in FILES)
        assert read_protein_lipid_window_csv(root / FILES[1]).rows == ()
        assert read_protein_glycan_window_csv(root / FILES[2]).rows == ()
    assert [rt.trajectory.passes for rt in runtimes] == {
        "empty": [3, 3],
        "no_metadata": [3, 3],
        "legacy": [2, 2],
        "mixed": [4, 2],
        "one_condition": [4, 3],
    }[case]
    assert_valid(root, mappings)


@pytest.mark.parametrize(
    "failure,prefix",
    [
        ("metadata", "Molecular partner metadata failed:"),
        ("identification", "Molecular partner identification failed:"),
        ("geometry", "Specialized contact computation failed:"),
        ("aggregation", "Specialized contact aggregation failed:"),
        ("write", "Specialized contact export write failed:"),
        ("existing", "Specialized contact export write failed:"),
    ],
)
def test_failure_prefixes_protein_preservation_and_no_false_claims(
    monkeypatch, capsys, tmp_path, failure, prefix
):
    source, runtimes, spies, mappings = install_specialized(monkeypatch, tmp_path)
    root = tmp_path / "out"
    if failure == "metadata":
        (source.manifest_path.parent / "partners-2.json").write_text("{}")
    elif failure == "identification":
        runtimes[0].bonds = [SimpleNamespace(indices=(0, 999))]
    elif failure == "geometry":
        del runtimes[0].residues[2].atoms._atoms[0].element
    elif failure == "aggregation":
        spies["build_specialized_contact_source_tables"].side_effect = ValueError(
            "private/path"
        )
    elif failure == "write":
        spies["write_protein_glycan_window_csv"].side_effect = OSError("private/path")
    else:
        root.mkdir()
        (root / FILES[0]).write_bytes(b"user existing catalog")
    _, stdout, stderr = invoke_cli(
        monkeypatch, capsys, *physical_command(tmp_path), expected_exit_code=1
    )
    assert stdout == "" and stderr.startswith(prefix)
    assert "Traceback" not in stderr and "private/path" not in stderr
    inventory, provenance = records(root)
    assert provenance["status"] == "failed"
    assert all(e["role"] not in ROLES for e in inventory["artifacts"])
    assert all(e["role"] not in ROLES for e in provenance["artifact_references"])
    assert (root / "protein_edges_by_window_source.csv").is_file()
    assert any(e["role"] == "graph_json" for e in inventory["artifacts"])
    if failure == "metadata":
        assert all(rt.trajectory.passes == 3 for rt in runtimes)
    if failure == "existing":
        assert (root / FILES[0]).read_bytes() == b"user existing catalog"
    # Invalid supplied metadata is not claimed as a successful used input.
    assert_valid(
        root,
        {
            k: v
            for k, v in mappings.items()
            if failure != "metadata" or "molecular_partner_metadata" not in k
        },
    )


def test_specialized_determinism_and_main_protein_byte_regression(
    monkeypatch, capsys, tmp_path
):
    originals, artifacts = [], []
    for i, supplied in enumerate((False, True, True)):
        with monkeypatch.context() as patch:
            work = tmp_path / str(i)
            install_specialized(patch, work, supplied=supplied)
            invoke_cli(patch, capsys, *physical_command(work))
            root = work / "out"
            inventory, _ = records(root)
            originals.append(
                {
                    e["path"]: (root / e["path"]).read_bytes()
                    for e in inventory["artifacts"]
                    if e["direction"] == "output"
                    and e["role"]
                    not in (*ROLES, "runtime_metadata", "graph_diagnostics_report")
                }
            )
            if supplied:
                artifacts.append(
                    tuple((root / filename).read_bytes() for filename in FILES)
                )
    assert originals[0] == originals[1] == originals[2]
    assert artifacts[0] == artifacts[1]


def refresh_sizes(root):
    path = root / "artifact_inventory.json"
    inventory = json.loads(path.read_text())
    for entry in inventory["artifacts"]:
        if entry["direction"] == "output":
            entry["byte_size"] = (root / entry["path"]).stat().st_size
    path.write_text(json.dumps(inventory))


@pytest.mark.parametrize(
    "damage",
    [
        "catalog_replica",
        "catalog_partner",
        "catalog_membership",
        "catalog_linkage",
        "row_condition",
        "row_window",
        "row_bounds",
        "missing_catalog",
        "missing_lipid",
        "missing_glycan",
    ],
)
def test_unified_crosschecks_offline_context_and_required_roles(
    monkeypatch, capsys, tmp_path, damage
):
    _, _, _, mappings = install_specialized(monkeypatch, tmp_path)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    if damage.startswith("catalog"):
        path = root / FILES[0]
        catalog = json.loads(path.read_text())
        binding = catalog["bindings"][0]
        if damage == "catalog_replica":
            binding["dataset_spec"]["identity"]["replica_id"] = "9"
        elif damage == "catalog_partner":
            binding["partner_catalog"]["partners"][0]["partner_id"] = "wrong-id"
        elif damage == "catalog_membership":
            partner = binding["partner_catalog"]["partners"][0]
            partner["component_residue_indexes"] = [12]
            partner["components"][0]["residue_index"] = 12
        else:
            binding["partner_catalog"]["partners"][1]["carrier_residue_index"] = 9
        path.write_text(json.dumps(catalog))
        refresh_sizes(root)
    elif damage.startswith("row"):
        import csv

        path = root / FILES[1]
        with path.open(newline="") as stream:
            rows = list(csv.reader(stream))
        name, value = {
            "row_condition": ("condition", "invented"),
            "row_window": ("window_id", "window_9999"),
            "row_bounds": ("requested_window_start_ns", "0.01"),
        }[damage]
        rows[1][rows[0].index(name)] = value
        with path.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)
        refresh_sizes(root)
    else:
        missing = ROLES[
            ("missing_catalog", "missing_lipid", "missing_glycan").index(damage)
        ]
        inventory, provenance = records(root)
        inventory["artifacts"] = [
            e for e in inventory["artifacts"] if e["role"] != missing
        ]
        provenance["artifact_references"] = [
            e for e in provenance["artifact_references"] if e["role"] != missing
        ]
        (root / "artifact_inventory.json").write_text(json.dumps(inventory))
        (root / "run_provenance.json").write_text(json.dumps(provenance))
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "failed", report.to_dict()
    assert report.unsupported_count == 0


def test_glycan_exclusion_and_positive_distances_from_runtime_through_csv(
    monkeypatch, capsys, tmp_path
):
    _, runtimes, _, mappings = install_specialized(
        monkeypatch,
        tmp_path,
        kinds=(False, True),
        times=tuple(range(0, 801, 100)),
        temporal={
            "production_end_ns": 0.8,
            "window_length_ns": 0.8,
            "window_step_ns": 0.4,
        },
    )
    for rt in runtimes:
        original = rt.trajectory
        glycan_atom = rt.residues[3].atoms._atoms[0]

        class ControlledTrajectory:
            def __init__(self, source, atom):
                self.source, self.atom = source, atom
                self.n_frames = source.n_frames

            def __iter__(self):
                for frame in self.source:
                    self.atom.position = (
                        0 if frame._index == 0 else -1 if frame._index == 6 else -4,
                        0,
                        0,
                    )
                    yield frame

        rt.trajectory = ControlledTrajectory(original, glycan_atom)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    table = read_protein_glycan_window_csv(root / FILES[2])
    assert table.row_count == 2  # One ordinary non-carrier row per replica.
    for row in table.rows:
        assert row.protein_residue_index == 1
        assert row.n_contact_frames == 2 and row.resolved_frame_count == 5
        assert row.occupancy == 0.4 and row.n_contact_episodes == 2
        assert row.distance_mean_A == 3.5 and row.distance_min_A == 3.0
    assert_valid(root, mappings)


@pytest.mark.parametrize("artifact", ("metadata", *FILES))
def test_each_specialized_artifact_checksum_mutation_is_detected(
    monkeypatch, capsys, tmp_path, artifact
):
    _, _, _, mappings = install_specialized(monkeypatch, tmp_path)
    invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(tmp_path, "--artifact-checksum-mode", "sha256"),
    )
    root = tmp_path / "out"
    assert_valid(root, mappings)
    path = (
        mappings["input:condition:0001:molecular_partner_metadata"]
        if artifact == "metadata"
        else root / artifact
    )
    path.write_bytes(
        path.read_bytes()
        .replace(b"LIPID-X", b"LIPID-Y")
        .replace(b"GLYCAN-X", b"GLYCAN-Y")
    )
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "failed"
    role = (
        "molecular_partner_metadata"
        if artifact == "metadata"
        else artifact.rsplit(".", 1)[0]
    )
    assert any(
        r.role == role and r.status == "skipped_integrity_failure"
        for r in report.specialized_records
    )


def test_offline_validation_never_opens_md_contents(monkeypatch, capsys, tmp_path):
    from pathlib import Path

    _, _, _, mappings = install_specialized(monkeypatch, tmp_path)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    original = Path.open

    def controlled_open(path, *args, **kwargs):
        if path.suffix in (".tpr", ".xtc", ".gro", ".psf", ".dcd"):
            raise AssertionError("Offline validation must not open MD contents")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", controlled_open)
    assert_valid(tmp_path / "out", mappings)
