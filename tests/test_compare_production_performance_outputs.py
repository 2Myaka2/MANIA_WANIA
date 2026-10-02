"""Parity audit fails closed on science, missing fields and unproven digests."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "compare_production_performance_outputs",
    Path(__file__).parents[1] / "tools/compare_production_performance_outputs.py",
)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def roots(tmp_path):
    pair = [tmp_path / "before", tmp_path / "after"]
    for root in pair:
        for name in audit.REQUIRED:
            write(root, name, {})
    return pair


def test_identical_and_missing_science(roots):
    assert audit.compare(*roots)["passed"]
    (roots[1] / "preprocessing/protein_lipid_perframe.json").unlink()
    assert not audit.compare(*roots)["passed"]


def test_empty_roots_cannot_pass(tmp_path):
    assert not audit.compare(tmp_path / "absent1", tmp_path / "absent2")["passed"]


@pytest.mark.parametrize("field", ["contact_observation_count", "sampled_frame_count"])
def test_scientific_runtime_counts_are_never_ignored(roots, field):
    for n, root in enumerate(roots):
        write(root, "preprocessing/runtime_metadata.json", {"performance": {field: n}})
    result = audit.compare(*roots)
    assert not result["passed"]
    assert result["unaccepted_field_count"] == 1


def test_provenance_change_requires_verified_hash_chain(roots):
    for n, root in enumerate(roots):
        p = write(
            root,
            "preprocessing/runtime_metadata.json",
            {"performance": {"wall_clock_seconds": float(n)}},
        )
        inventory = write(
            root,
            "preprocessing/artifact_inventory.json",
            {
                "artifacts": [
                    {
                        "direction": "output",
                        "path": p.name,
                        "sha256": audit.digest(p),
                        "byte_size": p.stat().st_size,
                    }
                ]
            },
        )
        write(
            root,
            "technical_complete.json",
            {
                "artifacts": {
                    p.name: audit.digest(p),
                    inventory.name: audit.digest(inventory),
                }
            },
        )
    result = audit.compare(*roots)
    assert result["passed"]
    fields = result["files"]["technical_complete.json"]["differences"]
    assert all("independently accepted" in field["classification"] for field in fields)
    write(
        roots[1],
        "technical_complete.json",
        {"artifacts": {"runtime_metadata.json": "fake"}},
    )
    assert not audit.compare(*roots)["passed"]


def test_deleted_provenance_field_is_rejected(roots):
    write(
        roots[0], "preprocessing/run_provenance.json", {"started_at_utc": "timestamp"}
    )
    assert not audit.compare(*roots)["passed"]


def test_csv_records_every_changed_cell(roots):
    name = "preprocessing/graph/edges.csv"
    for n, root in enumerate(roots):
        (root / name).write_text(f"source,target,distance\na,b,{n}\n")
    result = audit.compare(*roots)
    assert not result["passed"]
    assert result["files"][name]["differences"][0]["pointer"] == [1, 2]


def test_path_relocation_requires_same_relative_artifact(roots):
    for root in roots:
        write(
            root,
            "inputs/preprocessing.json",
            {"output_root": str(root / "preprocessing")},
        )
    assert audit.compare(*roots)["passed"]
    write(
        roots[1], "inputs/preprocessing.json", {"output_root": str(roots[1] / "wrong")}
    )
    assert not audit.compare(*roots)["passed"]


def test_nested_diagnostics_paths_are_exactly_scoped(roots):
    name = "preprocessing/reports/graph_diagnostics_report.json"
    for root in roots:
        write(
            root,
            name,
            {
                "sections": [
                    {},
                    {
                        "summary": {
                            "edges_csv_path": str(
                                root / "preprocessing/graph/edges.csv"
                            )
                        }
                    },
                ]
            },
        )
    assert audit.compare(*roots)["passed"]
    write(
        roots[1],
        name,
        {
            "sections": [
                {},
                {
                    "summary": {
                        "edges_csv_path": str(
                            roots[1] / "preprocessing/graph/other.csv"
                        )
                    }
                },
            ]
        },
    )
    assert not audit.compare(*roots)["passed"]
