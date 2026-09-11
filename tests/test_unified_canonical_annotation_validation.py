"""Mutations test reconstruction, not merely CSV syntax or current byte sizes."""

import csv
import json

import pytest
from test_cli_preprocessing_canonical_annotation_export import install_stage30
from test_cli_preprocessing_graph_workflow import invoke_cli
from test_cli_preprocessing_physical_time_execution import physical_command
from test_cli_preprocessing_specialized_contact_export import assert_valid, records

from mania.validation import validate_run_artifacts


def refresh_inventory(root, paths, inventory=None):
    if inventory is None:
        inventory = json.loads((root / "artifact_inventory.json").read_text())
    for entry in inventory["artifacts"]:
        path = (
            root / entry["path"]
            if entry["direction"] == "output"
            else paths[entry["artifact_id"]]
        )
        entry["byte_size"] = path.stat().st_size
    inventory["artifact_count"] = len(inventory["artifacts"])
    for direction in ("input", "output"):
        inventory[f"{direction}_artifact_count"] = sum(
            e["direction"] == direction for e in inventory["artifacts"]
        )
    (root / "artifact_inventory.json").write_text(json.dumps(inventory))


def edit_csv(path, field, value):
    with path.open(newline="") as stream:
        rows = list(csv.reader(stream))
    rows[1][rows[0].index(field)] = value
    with path.open("w", newline="") as stream:
        csv.writer(stream).writerows(rows)


@pytest.mark.parametrize(
    "case",
    [
        "missing_canonical",
        "missing_annotated",
        "no_mapping",
        "no_annotations",
        "no_canonical_for_annotated",
        "wrong_replica",
        "duplicate_replica",
        "wrong_reference",
        "wrong_binding_path",
        "extra_binding_key",
        "condition_binding",
        "annotation_system",
        "mapping_corrupt",
        "annotation_corrupt",
        "canonical_model",
        "annotated_model",
        "canonical_resname",
        "annotated_region",
        "input_direction",
        "unclaimed_output",
        "reference_mismatch",
        "wrong_external_mapping",
    ],
)
def test_unified_stage30_mutations_fail_even_with_current_sizes(
    monkeypatch, capsys, tmp_path, case
):
    _, _, _, paths = install_stage30(monkeypatch, tmp_path)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    root = tmp_path / "out"
    assert_valid(root, paths)
    inventory, provenance = records(root)
    config = provenance["resolved_configuration"]
    canonical_role = "protein_edges_by_window_canonical"
    annotated_role = canonical_role + "_annotated"
    remove_role = None
    if case in ("missing_canonical", "no_canonical_for_annotated"):
        remove_role = canonical_role
    elif case in ("missing_annotated", "unclaimed_output"):
        remove_role = annotated_role
    elif case == "no_mapping":
        remove_role = "canonical_residue_mapping"
        config.pop("canonical_residue_mapping_bindings")
        config.pop("canonical_reference")
    elif case == "no_annotations":
        remove_role = "biological_annotation_metadata"
        config.pop("biological_annotation_bindings")
    elif case == "wrong_replica":
        config["canonical_residue_mapping_bindings"][0]["replica_id"] = "absent"
    elif case == "duplicate_replica":
        config["canonical_residue_mapping_bindings"][1]["replica_id"] = "1"
    elif case == "wrong_reference":
        config["canonical_reference"]["sequence_sha256"] = "0" * 64
    elif case == "wrong_binding_path":
        config["canonical_residue_mapping_bindings"][0]["mapping_path"] = (
            "inputs/wrong.json"
        )
    elif case == "extra_binding_key":
        config["canonical_residue_mapping_bindings"][0]["unexpected"] = True
    elif case == "condition_binding":
        config["biological_annotation_bindings"][0]["condition"] = "NORM"
    elif case in ("annotation_system", "annotation_corrupt"):
        path = paths["input:biological_annotation_metadata:0001"]
        data = json.loads(path.read_text())
        data["system_id" if case == "annotation_system" else "annotation_scope"] = (
            "wrong"
        )
        path.write_text(json.dumps(data))
    elif case in ("mapping_corrupt", "wrong_external_mapping"):
        path = paths["input:canonical_residue_mapping:0001"]
        data = json.loads(path.read_text())
        if case == "mapping_corrupt":
            data["kind"] = "wrong"
        else:
            # Valid control with different explicit target; reconstruction must fail.
            data["mappings"][0].update(
                canonical_residue_number=312, canonical_resname="ILE"
            )
        path.write_text(json.dumps(data))
        if case == "wrong_external_mapping":
            from mania.canonical_residue_mapping_io import (
                read_canonical_residue_mapping,
            )

            assert (
                read_canonical_residue_mapping(path)
                .mappings[0]
                .canonical_residue_number
                == 312
            )
    elif case in ("canonical_model", "canonical_resname"):
        edit_csv(
            root / f"{canonical_role}.csv",
            "source_resid" if case == "canonical_model" else "source_canonical_resname",
            "changed" if case == "canonical_model" else "MET",
        )
    elif case in ("annotated_model", "annotated_region"):
        edit_csv(
            root / f"{annotated_role}.csv",
            "source_is_cysteine_variant_site"
            if case == "annotated_model"
            else "source_is_ecd",
            "true" if case == "annotated_model" else "false",
        )
    elif case == "input_direction":
        entry = next(
            e
            for e in inventory["artifacts"]
            if e["role"] == "canonical_residue_mapping"
        )
        entry["condition"] = "normal"
    elif case == "reference_mismatch":
        next(
            r for r in provenance["artifact_references"] if r["role"] == canonical_role
        )["path"] = "other.csv"
    if remove_role:
        inventory["artifacts"] = [
            e for e in inventory["artifacts"] if e["role"] != remove_role
        ]
        provenance["artifact_references"] = [
            r for r in provenance["artifact_references"] if r["role"] != remove_role
        ]
        if case != "unclaimed_output" and remove_role in (
            canonical_role,
            annotated_role,
        ):
            (root / f"{remove_role}.csv").unlink()
    (root / "run_provenance.json").write_text(json.dumps(provenance))
    refresh_inventory(root, paths, inventory)
    report = validate_run_artifacts(
        root, scope="preprocessing", input_artifact_paths=paths
    )
    assert report.status == "failed", report.to_dict()
    assert report.unsupported_count == 0
    assert any(
        issue.code
        in (
            "stage30_lineage_or_reconstruction_mismatch",
            "specialized_validation_failed",
        )
        for issue in report.issues
    ), report.to_dict()


def test_explicit_external_inputs_unresolved_is_incomplete(
    monkeypatch, capsys, tmp_path
):
    _, _, _, paths = install_stage30(monkeypatch, tmp_path)
    invoke_cli(monkeypatch, capsys, *physical_command(tmp_path))
    paths.pop("input:biological_annotation_metadata:0001")
    report = validate_run_artifacts(
        tmp_path / "out", scope="preprocessing", input_artifact_paths=paths
    )
    assert report.status == "partial" and not report.complete
    assert report.unsupported_count == 0
