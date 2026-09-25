"""Strict operational catalog selection; no trajectory access or science."""

from __future__ import annotations

import csv
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from mania.dataset_identity import (
    DatasetTemporalParameters,
    DatasetTrajectoryIdentity,
    DatasetTrajectorySpec,
)
from mania.preprocessing.temporal_policy import (
    INCLUSIVE_BOUNDARY_PROFILE,
    PreprocessingTemporalPolicy,
)

CATALOG_COLUMNS = tuple(
    "trajectory_id system_id replica_id engine variant_id condition disulfide_state "
    "replica_group_id expected_replicas topology_path trajectory_path config_path "
    "log_path box_path production_start_ns production_end_ns frame_stride_ps "
    "window_length_ns window_step_ns element_control canonical_mapping "
    "biological_annotations partner_metadata readiness_status readiness_notes "
    "source_group nominal_duration_ns time_control overlap_percent".split()
)
PATH_COLUMNS = tuple(
    "topology_path trajectory_path config_path log_path box_path element_control "
    "canonical_mapping biological_annotations partner_metadata time_control".split()
)
RAW_COLUMNS = PATH_COLUMNS[:5]
CONTROL_COLUMNS = PATH_COLUMNS[5:]
TEMPORAL_COLUMNS = tuple(DatasetTemporalParameters.model_fields)
_DESCRIPTOR_FIELDS = set(
    "catalog_schema catalog_version dataset_id dataset_version "
    "data_root_environment_variable trajectories_csv expected_systems "
    "expected_trajectories temporal_policy population_groups "
    "allowed_readiness_statuses readiness_precedence source_head "
    "catalog_basis_head generation_note stage35_authorized".split()
)
_POPULATIONS = {
    "gromacs": ("gromacs", 4, 12, 3),
    "egor_namd": ("namd", 3, 9, 3),
    "alina_namd": ("namd", 12, 12, 1),
}


class ProductionError(ValueError):
    """A production binding, preflight, or completed-stage gate failed."""


def portable_path(value: str) -> Path:
    """Require a literal relative POSIX path, without expansion or traversal."""
    if (
        not value
        or value != value.strip()
        or "\\" in value
        or "$" in value
        or "~" in value
        or "\x00" in value
        or PurePosixPath(value).is_absolute()
        or any(p in ("", ".", "..") for p in value.split("/"))
        or ":" in value
    ):
        raise ProductionError(f"Invalid portable path: {value!r}")
    return Path(value)


def contained_path(root: Path, value: str) -> Path:
    path = root / portable_path(value)
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
        raise ProductionError(f"Path escapes MANIA_DATA_ROOT: {value}")
    return resolved


def data_root_from_environment() -> Path:
    value = os.environ.get("MANIA_DATA_ROOT")
    if not value or not Path(value).is_dir():
        raise ProductionError("MANIA_DATA_ROOT must name an existing directory")
    return Path(value).resolve()


class _UniqueYamlLoader(yaml.SafeLoader):
    pass


def _yaml_object(loader: _UniqueYamlLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    pairs = loader.construct_pairs(node)
    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProductionError(f"Duplicate catalog YAML key: {key}")
        result[key] = value
    return result


_UniqueYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_object
)


@dataclass(frozen=True)
class CatalogTrajectory:
    row: dict[str, str]
    spec: DatasetTrajectorySpec

    @property
    def trajectory_id(self) -> str:
        return self.spec.identity.trajectory_id

    @property
    def group_id(self) -> str:
        return self.row["replica_group_id"]


@dataclass(frozen=True)
class ProductionCatalog:
    path: Path
    descriptor: dict[str, Any]
    trajectories: tuple[CatalogTrajectory, ...]
    temporal_policy: PreprocessingTemporalPolicy

    def trajectory(self, trajectory_id: str) -> CatalogTrajectory:
        selected = [t for t in self.trajectories if t.trajectory_id == trajectory_id]
        if len(selected) != 1:
            raise ProductionError("Select exactly one known trajectory_id")
        return selected[0]

    def group(self, group_id: str) -> tuple[CatalogTrajectory, ...]:
        selected = tuple(t for t in self.trajectories if t.group_id == group_id)
        if not selected:
            raise ProductionError("Select exactly one known replica_group_id")
        return selected


def load_production_catalog(path: str | Path) -> ProductionCatalog:
    """Validate v1.1 metadata globally, checking source existence only on selection."""
    try:
        target = Path(path).resolve()
        descriptor = yaml.load(target.read_text(), Loader=_UniqueYamlLoader)
        if not isinstance(descriptor, dict) or set(descriptor) != _DESCRIPTOR_FIELDS:
            raise ProductionError("Invalid exact catalog descriptor fields")
        fixed = {
            "catalog_schema": "mania.production_catalog",
            "catalog_version": "1.1",
            "dataset_id": "napi2b-dataset-v1",
            "dataset_version": "1.0",
            "data_root_environment_variable": "MANIA_DATA_ROOT",
            "expected_systems": 19,
            "expected_trajectories": 33,
            "stage35_authorized": False,
        }
        if any(
            type(descriptor[k]) is not type(v) or descriptor[k] != v
            for k, v in fixed.items()
        ):
            raise ProductionError("Unsupported Dataset v1 catalog descriptor")
        statuses = ["READY", "MISSING_FILES", "MISSING_METADATA", "NEEDS_AUTHORITY"]
        if (
            descriptor["allowed_readiness_statuses"] != statuses
            or descriptor["readiness_precedence"] != statuses[1:]
        ):
            raise ProductionError("Invalid catalog readiness contract")
        expected_populations = {
            k: dict(
                zip(
                    (
                        "engine",
                        "expected_systems",
                        "expected_trajectories",
                        "expected_replicas_per_system",
                    ),
                    v,
                    strict=True,
                )
            )
            for k, v in _POPULATIONS.items()
        }
        if descriptor["population_groups"] != expected_populations:
            raise ProductionError("Invalid catalog population contract")
        if any(
            type(descriptor["population_groups"][group][key]) is not type(value)
            for group, population in expected_populations.items()
            for key, value in population.items()
        ):
            raise ProductionError("Catalog population values require exact types")
        for key in ("source_head", "catalog_basis_head"):
            if not isinstance(descriptor[key], str) or not re.fullmatch(
                r"[0-9a-f]{40}", descriptor[key]
            ):
                raise ProductionError(
                    "Catalog source revisions require exact Git hashes"
                )
        if not isinstance(descriptor["generation_note"], str) or not (
            descriptor["generation_note"].strip()
        ):
            raise ProductionError("Catalog generation note is required")
        policy = PreprocessingTemporalPolicy.model_validate(
            descriptor["temporal_policy"]
        )
        if policy.boundary_profile != INCLUSIVE_BOUNDARY_PROFILE:
            raise ProductionError("Production requires the explicit inclusive profile")
        csv_path = contained_path(target.parent, descriptor["trajectories_csv"])
        with csv_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != CATALOG_COLUMNS:
                raise ProductionError("Invalid exact production catalog CSV header")
            rows = []
            for cells in reader:
                if len(cells) != len(CATALOG_COLUMNS):
                    raise ProductionError("Invalid catalog CSV row width")
                row = dict(zip(CATALOG_COLUMNS, cells, strict=True))
                if any(
                    v != v.strip() for k, v in row.items() if k != "readiness_notes"
                ):
                    raise ProductionError(
                        "Catalog values must not have surrounding whitespace"
                    )
                for key in (
                    "trajectory_id",
                    "system_id",
                    "replica_group_id",
                    "replica_id",
                ):
                    if len(portable_path(row[key]).parts) != 1:
                        raise ProductionError(
                            "Catalog IDs must be single path components"
                        )
                for key in PATH_COLUMNS:
                    if row[key]:
                        portable_path(row[key])
                if row["source_group"] not in _POPULATIONS:
                    raise ProductionError("Unknown catalog source group")
                if row["readiness_status"] not in statuses:
                    raise ProductionError("Unknown catalog readiness status")
                identity = DatasetTrajectoryIdentity.model_validate(
                    {
                        "dataset_id": descriptor["dataset_id"],
                        **{
                            k: row[k] or None
                            for k in (
                                "system_id",
                                "trajectory_id",
                                "replica_id",
                                "engine",
                                "variant_id",
                                "condition",
                                "disulfide_state",
                            )
                        },
                    }
                )
                temporal = DatasetTemporalParameters.model_validate(
                    {k: float(row[k]) for k in TEMPORAL_COLUMNS}
                )
                # This version pins the approved production request, not pilot timing.
                end = (
                    100
                    if row["source_group"] == "egor_namd"
                    or (row["source_group"] == "gromacs" and row["variant_id"] == "WT")
                    else 30
                )
                if (
                    tuple(getattr(temporal, k) for k in TEMPORAL_COLUMNS)
                    != (5, end, 200, 2, 1, 50)
                    or float(row["nominal_duration_ns"]) != end
                ):
                    raise ProductionError("Catalog v1.1 production timing mismatch")
                if row["replica_group_id"] != identity.system_id:
                    raise ProductionError("Conflicting catalog system/group identity")
                population = _POPULATIONS[row["source_group"]]
                if identity.engine != population[0] or row["expected_replicas"] != str(
                    population[3]
                ):
                    raise ProductionError("Conflicting population/replica identity")
                rows.append(
                    CatalogTrajectory(
                        row, DatasetTrajectorySpec(identity=identity, temporal=temporal)
                    )
                )
        if len(rows) != 33 or len({t.trajectory_id for t in rows}) != len(rows):
            raise ProductionError("Duplicate trajectory or invalid catalog cardinality")
        groups = {t.group_id for t in rows}
        if len(groups) != 19:
            raise ProductionError("Invalid catalog system cardinality")
        for name, (_, systems, trajectories, replicas) in _POPULATIONS.items():
            members = [t for t in rows if t.row["source_group"] == name]
            if (
                len(members) != trajectories
                or len({t.group_id for t in members}) != systems
            ):
                raise ProductionError("Invalid catalog source population")
            for group in {t.group_id for t in members}:
                entries = [t for t in members if t.group_id == group]
                if (
                    Counter(t.spec.identity.replica_id for t in entries)
                    != Counter(str(i) for i in range(1, replicas + 1))
                    or len(
                        {
                            (
                                t.spec.identity.engine,
                                t.spec.identity.variant_id,
                                t.spec.identity.condition,
                                t.spec.identity.disulfide_state,
                                t.spec.temporal,
                            )
                            for t in entries
                        }
                    )
                    != 1
                ):
                    raise ProductionError("Conflicting or duplicate group membership")
        return ProductionCatalog(target, descriptor, tuple(rows), policy)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        if isinstance(exc, ProductionError):
            raise
        raise ProductionError(f"Invalid production catalog: {exc}") from exc
