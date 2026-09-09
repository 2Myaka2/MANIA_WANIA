"""Input manifest models for future trajectory preprocessing."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from json import JSONDecodeError
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mania.dataset_identity import DatasetTrajectorySpec


class TrajectoryInputConfig(BaseModel):
    """Raw simulation inputs declared for one analysis condition."""

    model_config = ConfigDict(frozen=True)

    condition: str
    topology_path: Path
    trajectory_paths: tuple[Path, ...]
    reference_structure_path: Path | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    dataset_spec: DatasetTrajectorySpec | None = None

    @model_validator(mode="after")
    def validate_dataset_condition(self) -> Self:
        """Match supplied scientific labels without inferring unresolved labels."""
        if self.dataset_spec is not None:
            scientific_condition = self.dataset_spec.identity.condition
            if (
                scientific_condition is not None
                and scientific_condition != self.condition
            ):
                raise ValueError(
                    "Dataset identity condition must equal the manifest condition"
                )
        return self

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        """Strip and validate a condition name while preserving case."""
        normalized = value.strip()
        if normalized == "":
            raise ValueError("Condition name must not be empty")
        return normalized

    @field_validator(
        "topology_path",
        "reference_structure_path",
        mode="before",
    )
    @classmethod
    def validate_path(cls, value: object) -> object:
        """Reject empty string paths before Path conversion."""
        return _reject_empty_path(value)

    @field_validator("trajectory_paths", mode="before")
    @classmethod
    def validate_trajectory_paths(cls, value: object) -> tuple[object, ...]:
        """Require a non-empty list or tuple of non-empty paths."""
        if isinstance(value, str):
            raise ValueError("trajectory_paths must not be a plain string")
        if not isinstance(value, (list, tuple)):
            raise ValueError("trajectory_paths must be a list or tuple")
        if not value:
            raise ValueError("trajectory_paths must contain at least one path")
        return tuple(_reject_empty_path(path) for path in value)


class ResidueLibraryInputConfig(BaseModel):
    """Residue library inputs reserved for later loading and QC."""

    model_config = ConfigDict(frozen=True)

    library_path: Path | None = None
    custom_residues_path: Path | None = None
    skip_resnames: tuple[str, ...] = ()
    allow_user_overrides: bool = False

    @field_validator("library_path", "custom_residues_path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> object:
        """Reject empty string paths before Path conversion."""
        return _reject_empty_path(value)

    @field_validator("skip_resnames", mode="before")
    @classmethod
    def validate_skip_resnames(cls, value: object) -> tuple[str, ...]:
        """Normalize residue names and remove duplicates in input order."""
        if isinstance(value, str):
            raise ValueError("skip_resnames must not be a plain string")
        if not isinstance(value, (list, tuple)):
            raise ValueError("skip_resnames must be a list or tuple")

        normalized_resnames: list[str] = []
        seen_resnames: set[str] = set()
        for resname in value:
            if not isinstance(resname, str):
                raise ValueError("skip_resnames entries must be strings")
            normalized = resname.strip().upper()
            if normalized == "":
                raise ValueError("skip_resnames entries must not be empty")
            if normalized not in seen_resnames:
                normalized_resnames.append(normalized)
                seen_resnames.add(normalized)
        return tuple(normalized_resnames)


class PreprocessingInputManifest(BaseModel):
    """Validated raw-input declaration for future preprocessing."""

    model_config = ConfigDict(frozen=True)

    output_root: Path
    conditions: tuple[TrajectoryInputConfig, ...]
    residue_library: ResidueLibraryInputConfig = Field(
        default_factory=ResidueLibraryInputConfig
    )
    frame_time_ps: float | None = None

    @field_validator("output_root", mode="before")
    @classmethod
    def validate_output_root(cls, value: object) -> object:
        """Reject an empty output root before Path conversion."""
        return _reject_empty_path(value)

    @field_validator("conditions", mode="before")
    @classmethod
    def validate_conditions_input(cls, value: object) -> object:
        """Reject string and empty condition collections."""
        if isinstance(value, str):
            raise ValueError("conditions must not be a plain string")
        if not isinstance(value, (list, tuple)):
            raise ValueError("conditions must be a list or tuple")
        if not value:
            raise ValueError("conditions must contain at least one condition")
        return value

    @field_validator("conditions")
    @classmethod
    def validate_unique_conditions(
        cls,
        value: tuple[TrajectoryInputConfig, ...],
    ) -> tuple[TrajectoryInputConfig, ...]:
        """Reject duplicate normalized condition names."""
        seen_conditions: set[str] = set()
        for condition_config in value:
            condition = condition_config.condition
            if condition in seen_conditions:
                raise ValueError(f"Duplicate condition name: {condition!r}")
            seen_conditions.add(condition)
        return value

    @field_validator("frame_time_ps")
    @classmethod
    def validate_frame_time_ps(cls, value: float | None) -> float | None:
        """Require positive finite frame time when it is provided."""
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("frame_time_ps must be finite and positive")
        return value

    @field_validator("conditions")
    @classmethod
    def validate_unique_replica_keys(
        cls,
        value: tuple[TrajectoryInputConfig, ...],
    ) -> tuple[TrajectoryInputConfig, ...]:
        """Reject duplicate Dataset identity keys among supplied specs only."""
        seen_keys: set[tuple[str, str, str, str]] = set()
        for condition_config in value:
            if condition_config.dataset_spec is None:
                continue
            key = condition_config.dataset_spec.identity.replica_key
            if key in seen_keys:
                raise ValueError(f"Duplicate Dataset replica_key: {key!r}")
            seen_keys.add(key)
        return value

    def condition_names(self) -> tuple[str, ...]:
        """Return condition names in manifest order."""
        return tuple(config.condition for config in self.conditions)

    def get_condition(self, condition: str) -> TrajectoryInputConfig:
        """Return one condition config using stripped, case-sensitive matching."""
        normalized = condition.strip()
        if normalized == "":
            raise KeyError(condition)
        for condition_config in self.conditions:
            if condition_config.condition == normalized:
                return condition_config
        raise KeyError(condition)

    def dataset_spec_for_condition(
        self, condition: str
    ) -> DatasetTrajectorySpec | None:
        """Return an optional spec using the existing condition lookup semantics."""
        return self.get_condition(condition).dataset_spec

    def dataset_specs(self) -> tuple[DatasetTrajectorySpec, ...]:
        """Return only supplied Dataset specs in manifest condition order."""
        return tuple(
            config.dataset_spec
            for config in self.conditions
            if config.dataset_spec is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Preserve legacy fields and serialize supplied specs with their contract."""
        payload = self.model_dump(
            mode="json", exclude={"conditions": {"__all__": {"dataset_spec"}}}
        )
        for config, serialized in zip(
            self.conditions, payload["conditions"], strict=True
        ):
            if config.dataset_spec is not None:
                serialized["dataset_spec"] = config.dataset_spec.to_dict()
        return payload


def load_preprocessing_input_manifest(
    path: str | Path,
) -> PreprocessingInputManifest:
    """Load and validate a JSON or YAML preprocessing input manifest."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if manifest_path.is_dir():
        raise IsADirectoryError(manifest_path)
    if not manifest_path.is_file():
        raise ValueError(f"Manifest path is not a file: {manifest_path}")

    try:
        payload = _load_manifest_payload(manifest_path)
    except (JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(
            f"Invalid preprocessing input manifest: {manifest_path}"
        ) from exc

    if not isinstance(payload, Mapping):
        raise ValueError("Preprocessing input manifest must contain an object")

    return PreprocessingInputManifest.model_validate(dict(payload))


def _load_manifest_payload(path: Path) -> object:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as manifest_file:
            return yaml.safe_load(manifest_file)
    raise ValueError(f"Unsupported preprocessing manifest suffix: {path.suffix}")


def _reject_empty_path(value: object) -> object:
    if isinstance(value, str) and value.strip() == "":
        raise ValueError("Path must not be empty")
    return value


__all__ = [
    "PreprocessingInputManifest",
    "ResidueLibraryInputConfig",
    "TrajectoryInputConfig",
    "load_preprocessing_input_manifest",
]
