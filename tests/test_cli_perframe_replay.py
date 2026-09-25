"""Opt-in persistence in the established CLI and strict unified reconstruction."""

import json

import pytest
from test_cli_preprocessing_canonical_annotation_export import install_stage30
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_physical_time_execution import physical_command
from test_cli_preprocessing_specialized_contact_export import (
    assert_valid,
    install_specialized,
)

from mania import canonical_window_tables_io as canonical_io
from mania.preprocessing import perframe_observations as persistence
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.temporal_policy import (
    INCLUSIVE_BOUNDARY_PROFILE,
    LEGACY_BOUNDARY_PROFILE,
)
from mania.preprocessing.window_replay import replay_window_tables
from mania.validation import validate_run_artifacts


@pytest.mark.parametrize(
    "profile", [LEGACY_BOUNDARY_PROFILE, INCLUSIVE_BOUNDARY_PROFILE]
)
@pytest.mark.parametrize("checksum", ["none", "sha256"])
def test_cli_persistence_replays_source_and_canonical_without_extra_passes(
    tmp_path,
    monkeypatch,
    capsys,
    profile,
    checksum,
):
    source, runtimes, _, mappings = install_stage30(monkeypatch, tmp_path)
    data = json.loads(source.manifest_path.read_text())
    data["temporal_policy"] = {
        "schema_version": "mania.preprocessing_temporal_policy.v0.1",
        "boundary_profile": profile,
    }
    source.manifest_path.write_text(json.dumps(data))
    invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(
            tmp_path,
            "--persist-perframe-observations",
            "--artifact-checksum-mode",
            checksum,
        ),
    )
    root = tmp_path / "out"
    assert [r.trajectory.passes for r in runtimes] == [4, 4]
    assert_valid(root, mappings)
    temporal = read_preprocessing_temporal_execution(root / "temporal_execution.json")
    # The strict source replay and existing Stage 30 validator together enforce
    # exact all-layer source -> canonical parity through supplied mapping controls.
    replayed = replay_window_tables(root, temporal)
    assert replayed.protein.rows and replayed.lipid.rows and replayed.glycan.rows
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    for role in (
        "perframe_completion",
        "contacts_perframe",
        "protein_lipid_perframe",
        "protein_glycan_perframe",
    ):
        assert sum(e["role"] == role for e in inventory["artifacts"]) == 1
    for kind in ("edge", "lipid", "glycan"):
        table = getattr(canonical_io, f"read_canonical_protein_{kind}_window_csv")(
            root
            / (
                {
                    "edge": "protein_edges",
                    "lipid": "protein_lipid_contacts",
                    "glycan": "protein_glycan_contacts",
                }[kind]
                + "_by_window_canonical.csv"
            )
        )
        assert table.rows and all(r.boundary_profile == profile for r in table.rows)


@pytest.mark.parametrize(
    "damage", ["source_metric", "positive_distance", "missing_file", "lineage"]
)
def test_unified_replay_rejects_valid_but_inconsistent_artifacts(
    tmp_path, monkeypatch, capsys, damage
):
    _, _, _, mappings = install_specialized(monkeypatch, tmp_path)
    invoke_cli(
        monkeypatch,
        capsys,
        *physical_command(tmp_path, "--persist-perframe-observations"),
    )
    root = tmp_path / "out"
    inventory_path = root / "artifact_inventory.json"
    inventory = json.loads(inventory_path.read_text())
    if damage == "source_metric":
        path = root / "protein_lipid_contacts_by_window_source.csv"
        from dataclasses import replace

        from mania.preprocessing.specialized_contact_window_tables_io import (
            read_protein_lipid_window_csv,
            write_protein_lipid_window_csv,
        )

        table = read_protein_lipid_window_csv(path)
        assert write_protein_lipid_window_csv(
            replace(
                table,
                rows=(replace(table.rows[0], distance_mean_A=2.5), *table.rows[1:]),
            ),
            root,
            overwrite=True,
        ).passed
    elif damage == "positive_distance":
        path = root / "protein_lipid_perframe.json"
        value = json.loads(path.read_text())
        value["bindings"][0]["frames"][0]["contacts"][0]["minimum_distance_A"] = 2.5
        path.write_text(json.dumps(value))
    elif damage == "missing_file":
        (root / "protein_lipid_perframe.json").unlink()
    else:
        inventory["artifacts"] = [
            e for e in inventory["artifacts"] if e["role"] != "perframe_completion"
        ]
    for entry in inventory["artifacts"]:
        if entry["direction"] == "output" and (root / entry["path"]).is_file():
            entry["byte_size"] = (root / entry["path"]).stat().st_size
    inventory_path.write_text(json.dumps(inventory))
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=mappings
    )
    assert report.status == "failed"
    if damage != "lineage":
        assert any(i.code == "perframe_replay_mismatch" for i in report.issues)


def test_failed_persistence_claims_no_completion_or_output_roles(
    tmp_path, monkeypatch, capsys
):
    install_specialized(monkeypatch, tmp_path)
    original = persistence._write_json

    def interrupted(value, path, overwrite):
        if path.name == "protein_glycan_perframe.json":
            raise OSError("simulated disk failure")
        return original(value, path, overwrite)

    monkeypatch.setattr(persistence, "_write_json", interrupted)
    with pytest.raises(SystemExit):
        invoke_cli(
            monkeypatch,
            capsys,
            *physical_command(tmp_path, "--persist-perframe-observations"),
        )
    root = tmp_path / "out"
    assert not (root / "perframe_completion.json").exists()
    inventory = json.loads((root / "artifact_inventory.json").read_text())
    assert not any(
        e["role"]
        in ("perframe_completion", "protein_lipid_perframe", "protein_glycan_perframe")
        for e in inventory["artifacts"]
    )
