"""Offline reconstruction and conservative Stage 31 artifact mismatch handling."""

import csv
import io
import json
import shutil

import pytest
from test_replica_aggregation_run import completed_run

from mania.replica_aggregation_workflow import FAMILIES
from mania.software_identity import SoftwareIdentity
from mania.validation.unified import validate_run_artifacts


@pytest.fixture(autouse=True)
def stable_software_identity(monkeypatch):
    # The existing software-identity reload test replaces its class after test
    # collection. Keep this metadata-only fixture bound to the same accepted
    # class as the already imported generic provenance reader/model.
    identity = SoftwareIdentity(
        "MANIA",
        "mania-wania",
        "0.1.0",
        None,
        "unavailable",
        "unavailable",
    )
    monkeypatch.setattr(
        "mania.replica_aggregation_run.get_software_identity",
        lambda: identity,
    )


def rewrite_json(path, mutate):
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data) + "\n")


def refresh_sizes(output, mappings):
    def update(data):
        for entry in data["artifacts"]:
            path = (
                mappings.get(entry["artifact_id"])
                if entry["direction"] == "input"
                else (output / entry["path"])
            )
            if path is not None and path.exists():
                entry["byte_size"] = path.stat().st_size

    rewrite_json(output / "artifact_inventory.json", update)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_manifest",
        "invalid_manifest",
        "missing_input",
        "malformed_input",
        "reference",
        "group_window",
        "missing_output",
        "undeclared_output",
        "mean_occupancy",
        "std_occupancy",
        "support_fraction",
        "correspondence",
        "provenance_reference",
        "inventory_reference",
        "input_role",
        "output_bytes",
    ],
)
def test_reconstruction_rejects_mutations(tmp_path, mutation):
    _, manifest_path, output, _, mappings = completed_run(tmp_path)
    protein = output / FAMILIES[0].filename
    if mutation == "missing_manifest":
        manifest_path.unlink()
    elif mutation == "invalid_manifest":
        manifest_path.write_text("{}")
    elif mutation == "missing_input":
        mappings["input:protein:0001"].unlink()
    elif mutation == "malformed_input":
        mappings["input:protein:0001"].write_text("source_id,occupancy\n1,0.7\n")
    elif mutation == "reference":
        rewrite_json(
            manifest_path,
            lambda d: d.update(
                canonical_reference_id="wrong-reference",
            ),
        )
    elif mutation == "group_window":

        def mutate(d):
            for window in [
                d["groups"][0]["spec"]["window"],
                *(m["window"] for m in d["groups"][0]["members"]),
            ]:
                window.update(
                    requested_window_start_ns=22.5, requested_window_end_ns=27.5
                )

        rewrite_json(manifest_path, mutate)
    elif mutation == "missing_output":
        protein.unlink()
    elif mutation == "undeclared_output":
        rewrite_json(
            output / "artifact_inventory.json",
            lambda d: d.update(
                artifacts=[
                    e for e in d["artifacts"] if e["artifact_id"] != "output:protein"
                ],
            ),
        )
        rewrite_json(
            output / "run_provenance.json",
            lambda d: d.update(
                artifact_references=[
                    r
                    for r in d["artifact_references"]
                    if r["role"] != FAMILIES[0].output_role
                ],
            ),
        )
    elif mutation in ("mean_occupancy", "std_occupancy", "support_fraction"):
        rows = list(csv.reader(io.StringIO(protein.read_text())))
        rows[1][rows[0].index(mutation)] = {
            "mean_occupancy": "0.4",
            "std_occupancy": "0.46055512754639896",
            "support_fraction": "0.5",
        }[mutation]
        stream = io.StringIO(newline="")
        csv.writer(stream, lineterminator="\n").writerows(rows)
        protein.write_text(stream.getvalue())
    elif mutation == "correspondence":

        def mutate(d):
            d["groups"][0]["lipid_correspondences"]["correspondences"][0]["members"][0][
                "local_partner_id"
            ] = "lipid_not_bound"

        rewrite_json(manifest_path, mutate)
    elif mutation == "provenance_reference":
        rewrite_json(
            output / "run_provenance.json",
            lambda d: d.update(
                artifact_references=d["artifact_references"][1:],
            ),
        )
    elif mutation == "inventory_reference":
        rewrite_json(
            output / "artifact_inventory.json",
            lambda d: d.update(
                artifacts=[
                    e for e in d["artifacts"] if e["artifact_id"] != "output:lipid"
                ],
            ),
        )
    elif mutation == "input_role":
        rewrite_json(
            output / "artifact_inventory.json",
            lambda d: d["artifacts"][1].update(role=FAMILIES[1].input_role),
        )
    else:
        protein.write_bytes(protein.read_bytes().replace(b"\n", b"\r\n"))
    refresh_sizes(output, mappings)
    report = validate_run_artifacts(
        output, scope="replica_aggregation", input_artifact_paths=mappings
    )
    assert report.status == "failed", report.to_dict()


def test_unexpected_absent_family_and_sha256_mutation(tmp_path):
    _, _, output, _, mappings = completed_run(tmp_path / "protein", specialized=False)
    (output / FAMILIES[1].filename).write_text("unexpected")
    assert (
        validate_run_artifacts(
            output, scope="replica_aggregation", input_artifact_paths=mappings
        ).status
        == "failed"
    )
    _, _, output, _, mappings = completed_run(tmp_path / "sha", mode="sha256")
    protein = output / FAMILIES[0].filename
    protein.write_bytes(protein.read_bytes().replace(b"0.3,", b"0.4,", 1))
    assert (
        validate_run_artifacts(
            output, scope="replica_aggregation", input_artifact_paths=mappings
        ).status
        == "failed"
    )


def test_partial_unmapped_and_relocated_complete_validation(tmp_path):
    _, _, output, _, mappings = completed_run(tmp_path / "original", complete=True)
    report = validate_run_artifacts(output, scope="replica_aggregation")
    assert report.status == "partial" and report.complete is False
    relocated = tmp_path / "relocated"
    shutil.copytree(output, relocated)
    new_mappings = {}
    for index, (key, path) in enumerate(mappings.items()):
        target = tmp_path / "mapped" / f"{index}{path.suffix}"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(path.read_bytes())
        new_mappings[key] = target
    shutil.rmtree(tmp_path / "original")
    report = validate_run_artifacts(
        relocated, scope="replica_aggregation", input_artifact_paths=new_mappings
    )
    assert report.status == "passed" and report.complete is True, report.to_dict()


def test_header_only_complete_validation(tmp_path):
    _, _, output, _, mappings = completed_run(tmp_path, empty=True)
    report = validate_run_artifacts(
        output, scope="replica_aggregation", input_artifact_paths=mappings
    )
    assert report.status == "passed" and report.complete is True, report.to_dict()
