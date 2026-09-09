"""Additive Dataset specs preserve condition-centric preprocessing inputs."""

import builtins
import datetime
import importlib.metadata
import io
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import mania.preprocessing as preprocessing
from mania.dataset_identity import DatasetTrajectorySpec
from mania.preprocessing.input_manifest import (
    PreprocessingInputManifest,
    load_preprocessing_input_manifest,
)
from mania.preprocessing.trajectory_runtime import PreprocessingConditionRuntimeInput

IDENTITY = {
    "dataset_id": "development-subset",
    "system_id": "WT-NORM-gromacs",
    "trajectory_id": "trajectory-A",
    "variant_id": "WT",
    "engine": "gromacs",
    "condition": "NORM",
    "replica_id": "A",
    "disulfide_state": None,
}
REQUESTED = {
    "production_start_ns": 0.125,
    "production_end_ns": 100.0,
    "frame_stride_ps": 17.3,
    "window_length_ns": 7.1,
    "window_step_ns": 3.7,
    "overlap_percent": 42.0,
}
LEGACY_ENTRY = {
    "condition": "NORM",
    "topology_path": "data/example/topology.tpr",
    "trajectory_paths": ["data/example/part-2.xtc", "data/example/part-1.xtc"],
}


def spec_payload(**identity_changes: object) -> dict[str, object]:
    return {"identity": IDENTITY | identity_changes, "temporal": dict(REQUESTED)}


def make_manifest(*entries: dict[str, object]) -> PreprocessingInputManifest:
    return PreprocessingInputManifest.model_validate(
        {
            "output_root": "output",
            "conditions": list(entries),
            "frame_time_ps": 100.0,
        }
    )


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".yml"])
@pytest.mark.parametrize("explicit_none", [False, True])
def test_legacy_manifest_loading_and_exact_serialization(
    tmp_path: Path,
    suffix: str,
    explicit_none: bool,
) -> None:
    entry = dict(LEGACY_ENTRY)
    if explicit_none:
        entry["dataset_spec"] = None
    payload = {"output_root": "output", "conditions": [entry], "frame_time_ps": 100.0}
    path = tmp_path / f"manifest{suffix}"
    path.write_text(
        json.dumps(payload) if suffix == ".json" else yaml.safe_dump(payload),
        encoding="utf-8",
    )
    manifest = load_preprocessing_input_manifest(path)

    assert manifest.condition_names() == ("NORM",)
    assert manifest.get_condition(" NORM ") is manifest.conditions[0]
    assert manifest.conditions[0].topology_path == Path(LEGACY_ENTRY["topology_path"])
    assert manifest.conditions[0].trajectory_paths == (
        Path("data/example/part-2.xtc"),
        Path("data/example/part-1.xtc"),
    )
    assert manifest.frame_time_ps == 100.0
    assert manifest.dataset_specs() == ()
    assert manifest.dataset_spec_for_condition(" NORM ") is None
    assert manifest.to_dict() == {
        "output_root": "output",
        "conditions": [
            LEGACY_ENTRY | {"reference_structure_path": None, "metadata": {}}
        ],
        "residue_library": {
            "library_path": None,
            "custom_residues_path": None,
            "skip_resnames": [],
            "allow_user_overrides": False,
        },
        "frame_time_ps": 100.0,
    }


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_dataset_aware_manifest_loads_and_uses_spec_serialization(
    tmp_path: Path,
    suffix: str,
) -> None:
    payload = {
        "output_root": "output",
        "conditions": [
            LEGACY_ENTRY
            | {
                "condition": " NORM ",
                "dataset_spec": spec_payload(condition=" NORM "),
            }
        ],
    }
    path = tmp_path / f"dataset{suffix}"
    path.write_text(
        json.dumps(payload) if suffix == ".json" else yaml.safe_dump(payload),
        encoding="utf-8",
    )
    manifest = load_preprocessing_input_manifest(path)
    spec = manifest.dataset_spec_for_condition("NORM")
    assert isinstance(spec, DatasetTrajectorySpec)
    assert spec.identity.to_dict() == IDENTITY
    assert spec.temporal.to_dict() == REQUESTED
    assert manifest.dataset_specs() == (spec,)
    serialized = manifest.to_dict()["conditions"][0]
    assert serialized == LEGACY_ENTRY | {
        "reference_structure_path": None,
        "metadata": {},
        "dataset_spec": spec.to_dict(),
    }
    assert list(serialized["dataset_spec"]) == [
        "schema_version",
        "kind",
        "identity",
        "temporal",
    ]
    assert "identity" not in serialized
    assert "temporal" not in serialized
    json.dumps(manifest.to_dict(), allow_nan=False)


def test_unresolved_namd_condition_is_never_copied_from_execution_label() -> None:
    # Synthetic execution label and requested times do not assert NAMD dataset facts.
    manifest = make_manifest(
        LEGACY_ENTRY
        | {
            "condition": "synthetic-execution-A",
            "dataset_spec": spec_payload(engine="namd", condition=None),
        }
    )
    spec = manifest.dataset_spec_for_condition("synthetic-execution-A")
    assert spec is not None
    assert spec.identity.condition is None
    assert (
        manifest.to_dict()["conditions"][0]["dataset_spec"]["identity"]["condition"]
        is None
    )
    assert manifest.condition_names() == ("synthetic-execution-A",)


@pytest.mark.parametrize("scientific_condition", ["TUMOR", "norm", "Norm"])
def test_non_null_scientific_condition_must_match_case_sensitively(
    scientific_condition: str,
) -> None:
    with pytest.raises(ValidationError, match="Dataset identity condition must equal"):
        make_manifest(
            LEGACY_ENTRY
            | {
                "dataset_spec": spec_payload(condition=scientific_condition),
            }
        )


@pytest.mark.parametrize("execution_condition", ["", " \t"])
def test_optional_scientific_condition_does_not_relax_execution_condition(
    execution_condition: str,
) -> None:
    with pytest.raises(ValidationError, match="Condition name must not be empty"):
        make_manifest(
            LEGACY_ENTRY
            | {
                "condition": execution_condition,
                "dataset_spec": spec_payload(engine="namd", condition=None),
            }
        )


def test_mixed_migration_and_accessor_order_and_lookup() -> None:
    first = DatasetTrajectorySpec.model_validate(spec_payload())
    last = DatasetTrajectorySpec.model_validate(
        spec_payload(condition="TUMOR", replica_id="B")
    )
    manifest = make_manifest(
        LEGACY_ENTRY | {"dataset_spec": first},
        LEGACY_ENTRY | {"condition": "legacy-only"},
        LEGACY_ENTRY | {"condition": "TUMOR", "dataset_spec": last},
    )
    assert manifest.condition_names() == ("NORM", "legacy-only", "TUMOR")
    assert manifest.dataset_specs() == (first, last)
    assert manifest.dataset_spec_for_condition(" legacy-only ") is None
    assert manifest.dataset_spec_for_condition(" NORM ") is first
    assert manifest.dataset_spec_for_condition("TUMOR") is last
    assert "dataset_spec" not in manifest.to_dict()["conditions"][1]
    for missing in ("norm", "unknown", "", " \t"):
        with pytest.raises(KeyError):
            manifest.dataset_spec_for_condition(missing)


def test_duplicate_replica_keys_fail_across_different_execution_labels() -> None:
    with pytest.raises(ValidationError, match="Duplicate Dataset replica_key"):
        make_manifest(
            LEGACY_ENTRY | {"dataset_spec": spec_payload()},
            LEGACY_ENTRY
            | {
                "condition": "synthetic-execution",
                "dataset_spec": spec_payload(condition=None, engine="namd"),
            },
        )


def test_different_replicas_can_share_system_variant_and_unresolved_condition() -> None:
    manifest = make_manifest(
        *(
            LEGACY_ENTRY
            | {
                "condition": f"synthetic-execution-{replica}",
                "dataset_spec": spec_payload(
                    engine="namd", condition=None, replica_id=replica
                ),
            }
            for replica in ("B", "A", "C")
        )
    )
    assert [spec.identity.replica_id for spec in manifest.dataset_specs()] == [
        "B",
        "A",
        "C",
    ]


def test_distinct_replica_keys_do_not_relax_unique_execution_conditions() -> None:
    with pytest.raises(ValidationError, match="Duplicate condition name"):
        make_manifest(
            LEGACY_ENTRY | {"dataset_spec": spec_payload(replica_id="A")},
            LEGACY_ENTRY | {"dataset_spec": spec_payload(replica_id="B")},
        )


def test_dataset_spec_does_not_change_runtime_input_or_paths(tmp_path: Path) -> None:
    legacy = make_manifest(LEGACY_ENTRY).conditions[0]
    aware = make_manifest(LEGACY_ENTRY | {"dataset_spec": spec_payload()}).conditions[0]
    before = PreprocessingConditionRuntimeInput.from_manifest_condition(
        legacy.condition, legacy, base_dir=tmp_path
    )
    after = PreprocessingConditionRuntimeInput.from_manifest_condition(
        aware.condition, aware, base_dir=tmp_path
    )
    assert after.to_dict() == before.to_dict()
    assert after.topology_path == tmp_path / "data/example/topology.tpr"
    assert after.trajectory_paths == (
        tmp_path / "data/example/part-2.xtc",
        tmp_path / "data/example/part-1.xtc",
    )


@pytest.mark.parametrize("suffix", [None, ".json", ".yaml"])
def test_manifest_operations_are_pure_except_explicit_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str | None,
) -> None:
    payload = {
        "output_root": "missing-output",
        "conditions": [
            LEGACY_ENTRY,
            LEGACY_ENTRY
            | {
                "condition": "synthetic-execution",
                "dataset_spec": spec_payload(engine="namd", condition=None),
            },
        ],
        "frame_time_ps": 100.0,
    }
    path = tmp_path / f"manifest{suffix}"
    path.write_text(
        yaml.safe_dump(payload) if suffix == ".yaml" else json.dumps(payload),
        encoding="utf-8",
    )
    real_open, real_stat = io.open, Path.stat
    opened: list[Path] = []

    def explicit_open(file: object, *args: object, **kwargs: object) -> object:
        assert suffix is not None and Path(file) == path
        opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    def explicit_stat(file: Path, *args: object, **kwargs: object) -> object:
        assert suffix is not None and file == path
        return real_stat(file, *args, **kwargs)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Manifest must not discover state or invoke science")

    class ForbiddenDateTime(datetime.datetime):
        now = forbidden
        utcnow = forbidden
        today = forbidden

    with monkeypatch.context() as guard:
        guard.setattr(io, "open", explicit_open)
        guard.setattr(Path, "stat", explicit_stat)
        guard.setattr(datetime, "datetime", ForbiddenDateTime)
        for target, names in (
            (builtins, ("open",)),
            (Path, ("glob", "rglob", "iterdir", "cwd", "resolve")),
            (os, ("listdir", "scandir", "getenv", "system")),
            (type(os.environ), ("__getitem__", "__iter__")),
            (subprocess, ("run", "Popen", "check_output")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (importlib.metadata, ("version", "distribution", "distributions")),
            (
                preprocessing,
                ("load_manifest_condition_runtimes", "load_single_condition_runtime"),
            ),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        manifest = (
            PreprocessingInputManifest.model_validate(payload)
            if suffix is None
            else load_preprocessing_input_manifest(path)
        )
        assert manifest.condition_names() == ("NORM", "synthetic-execution")
        assert manifest.get_condition("NORM").dataset_spec is None
        assert manifest.dataset_spec_for_condition("synthetic-execution") is not None
        specs = manifest.dataset_specs()
        serialized = manifest.to_dict()

    assert opened == ([] if suffix is None else [path])
    assert len(specs) == 1
    assert vars(specs[0].temporal) == REQUESTED
    assert serialized["frame_time_ps"] == 100.0
