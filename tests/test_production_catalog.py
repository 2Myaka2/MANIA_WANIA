"""Operational catalog validation never opens trajectory inputs."""

import csv
import json
from pathlib import Path

import pytest
import yaml

from mania.production_catalog import (
    CATALOG_COLUMNS,
    ProductionError,
    contained_path,
    load_production_catalog,
    read_technical_run_manifest,
)

CATALOG = Path(__file__).parents[1] / "production/dataset_v1/dataset.yaml"
EGOR_IDS = tuple(f"namd_egor_wt_{ss}ss_r{r}" for ss in range(3) for r in range(1, 4))


def catalog_copy(root):
    root.mkdir(parents=True, exist_ok=True)
    for name in ("dataset.yaml", "trajectories.csv"):
        (root / name).write_bytes((CATALOG.parent / name).read_bytes())
    return root / "dataset.yaml"


def change_rows(path, edit):
    csv_path = path.parent / "trajectories.csv"
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    edit(rows)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("trajectory_id", EGOR_IDS)
def test_all_nine_egor_selections_without_source_access(trajectory_id):
    catalog = load_production_catalog(CATALOG)
    row = catalog.trajectory(trajectory_id)
    assert row.spec.identity.engine == "namd"
    assert row.spec.identity.condition == "PMm"
    assert row.spec.temporal.model_dump() == {
        "production_start_ns": 5,
        "production_end_ns": 100,
        "frame_stride_ps": 200,
        "window_length_ns": 2,
        "window_step_ns": 1,
        "overlap_percent": 50,
    }
    assert len(catalog.group(row.group_id)) == 3
    assert (
        catalog.temporal_policy.boundary_profile
        == "mania.window_boundaries.inclusive.v1"
    )


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "group",
        "replica",
        "engine",
        "escape",
        "five_frames",
        "unknown_group",
    ],
)
def test_invalid_catalog_fails(tmp_path, damage):
    path = catalog_copy(tmp_path)

    def edit(rows):
        row = rows[12]
        if damage == "duplicate":
            rows[13]["trajectory_id"] = row["trajectory_id"]
        else:
            key, value = {
                "group": ("replica_group_id", "another"),
                "replica": ("replica_id", "2"),
                "engine": ("engine", "gromacs"),
                "escape": ("topology_path", "../topology.psf"),
                "five_frames": ("production_end_ns", "0.5"),
                "unknown_group": ("source_group", "guessed"),
            }[damage]
            row[key] = value

    change_rows(path, edit)
    with pytest.raises(ProductionError):
        load_production_catalog(path)


@pytest.mark.parametrize("damage", ["duplicate_yaml", "legacy", "extra", "count"])
def test_strict_descriptor(tmp_path, damage):
    path = catalog_copy(tmp_path)
    if damage == "duplicate_yaml":
        path.write_text(path.read_text() + "catalog_version: '1.1'\n")
    else:
        payload = yaml.safe_load(path.read_text())
        if damage == "legacy":
            payload["temporal_policy"]["boundary_profile"] = (
                "mania.window_boundaries.legacy.v1"
            )
        elif damage == "extra":
            payload["guess"] = True
        else:
            payload["expected_trajectories"] = 9
        path.write_text(yaml.safe_dump(payload))
    with pytest.raises(ProductionError):
        load_production_catalog(path)


def test_unknown_selection_and_symlink_escape(tmp_path):
    catalog = load_production_catalog(CATALOG)
    for selector in (catalog.trajectory, catalog.group):
        with pytest.raises(ProductionError):
            selector("unknown")
    root = tmp_path / "data"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ProductionError, match="escapes"):
        contained_path(root, "escape/file")


def technical_payload(**changes):
    return {
        "schema_version": "mania.production_technical_run.v0.1",
        "purpose": "technical_validation",
        "trajectory_id": EGOR_IDS[0],
        "start_ns": 5,
        "end_ns": 8,
        **changes,
    }


def technical_file(root, **changes):
    path = root / "technical.json"
    path.write_text(json.dumps(technical_payload(**changes)))
    return path


@pytest.mark.parametrize("start,end", [(5, 8), (6, 100), (6, 9)])
def test_technical_interval_inherits_without_mutating_catalog(tmp_path, start, end):
    selected = load_production_catalog(CATALOG).trajectory(EGOR_IDS[0])
    before = selected.spec.model_dump()
    manifest = read_technical_run_manifest(
        technical_file(tmp_path, start_ns=start, end_ns=end)
    )
    effective = manifest.execution_spec(selected)
    assert effective.identity == selected.spec.identity
    assert effective.temporal.model_dump() == {
        **before["temporal"],
        "production_start_ns": start,
        "production_end_ns": end,
    }
    assert selected.spec.model_dump() == before
    assert selected.row["production_end_ns"] == "100"


@pytest.mark.parametrize(
    "changes",
    [
        {"start_ns": 4},
        {"end_ns": 101},
        {"end_ns": 100},
        {"end_ns": 5},
        {"start_ns": 9},
        {"end_ns": 6},
        {"start_ns": True},
        {"end_ns": "8"},
        {"end_ns": float("nan")},
        {"end_ns": float("inf")},
        {"start_ns": None},
        {"purpose": "production"},
        {"schema_version": "mania.production_technical_run.v9"},
        {"trajectory_id": EGOR_IDS[1]},
        {"trajectory_id": "unknown"},
        {"trajectory_id": list(EGOR_IDS[:2])},
        {"trajectory_id": EGOR_IDS[0] + " "},
        {"frame_stride_ps": 100},
        {"window_length_ns": 1},
        {"window_step_ns": 0.5},
        {"overlap_percent": 0},
        {"boundary_profile": "mania.window_boundaries.legacy.v1"},
        {
            "temporal_policy": {
                "boundary_profile": "mania.window_boundaries.inclusive.v1"
            }
        },
        {"frame_stride_ps": 200},
        {"trajectory_ids": list(EGOR_IDS[:2])},
    ],
)
def test_technical_manifest_rejects_invalid_or_extra_controls(tmp_path, changes):
    selected = load_production_catalog(CATALOG).trajectory(EGOR_IDS[0])
    with pytest.raises(ValueError):
        read_technical_run_manifest(technical_file(tmp_path, **changes)).execution_spec(
            selected
        )


@pytest.mark.parametrize("damage", ["duplicate", "missing", "array"])
def test_technical_manifest_strict_json(tmp_path, damage):
    path = technical_file(tmp_path)
    if damage == "duplicate":
        path.write_text(path.read_text()[:-1] + ', "end_ns": 9}')
    elif damage == "missing":
        payload = technical_payload()
        del payload["purpose"]
        path.write_text(json.dumps(payload))
    else:
        path.write_text(json.dumps([technical_payload()]))
    with pytest.raises(ValueError):
        read_technical_run_manifest(path)


def test_technical_interval_cannot_replace_catalog_production(tmp_path):
    path = catalog_copy(tmp_path)

    def edit(rows):
        for row in rows:
            if row["source_group"] == "egor_namd":
                row["production_end_ns"] = "8"
                row["nominal_duration_ns"] = "8"

    change_rows(path, edit)
    with pytest.raises(ProductionError, match="production timing mismatch"):
        load_production_catalog(path)
