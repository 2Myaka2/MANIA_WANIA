"""MANIA backend contract-subset comparison helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from mania.comparison.reference import (
    COMPARISON_MODE_CSV_EXACT,
    COMPARISON_MODE_JSON_EXACT,
    ArtifactComparisonSpec,
    ReferenceComparisonReport,
    compare_artifact_sets,
)

CONTRACT_SUBSET_ROOT_ARTIFACTS = ("run_meta.json",)

CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS = (
    "rg_timeseries.csv",
    "centrality.csv",
    "communities.csv",
    "nodes.csv",
    "edges.csv",
)

CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS = ("graph.json",)


class ContractSubsetComparisonError(Exception):
    """Raised when contract-subset comparison helpers receive invalid input."""


def build_contract_subset_comparison_specs(
    conditions: Iterable[str],
) -> tuple[ArtifactComparisonSpec, ...]:
    """Build ordered comparison specs for the supported backend contract subset."""
    normalized_conditions = _normalize_conditions(conditions)
    specs = [
        ArtifactComparisonSpec(
            artifact,
            COMPARISON_MODE_JSON_EXACT,
        )
        for artifact in CONTRACT_SUBSET_ROOT_ARTIFACTS
    ]

    for condition in normalized_conditions:
        specs.extend(
            ArtifactComparisonSpec(
                (Path(condition) / artifact).as_posix(),
                COMPARISON_MODE_CSV_EXACT,
            )
            for artifact in CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS
        )
        specs.extend(
            ArtifactComparisonSpec(
                (Path(condition) / artifact).as_posix(),
                COMPARISON_MODE_JSON_EXACT,
            )
            for artifact in CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS
        )

    return tuple(specs)


def compare_contract_subset(
    expected_root: str | Path,
    actual_root: str | Path,
    conditions: Iterable[str],
) -> ReferenceComparisonReport:
    """Compare expected and actual directories for the supported contract subset."""
    specs = build_contract_subset_comparison_specs(conditions)
    return compare_artifact_sets(expected_root, actual_root, specs)


def _normalize_conditions(conditions: Iterable[str]) -> tuple[str, ...]:
    if isinstance(conditions, str):
        raise ContractSubsetComparisonError(
            "Conditions must be an iterable of condition names, not a string"
        )

    normalized_conditions: list[str] = []
    seen_conditions: set[str] = set()

    for condition in conditions:
        if not isinstance(condition, str):
            raise ContractSubsetComparisonError(
                f"Condition names must be strings: {condition!r}"
            )
        normalized_condition = condition.strip()
        if normalized_condition == "":
            raise ContractSubsetComparisonError("Condition names must not be empty")
        if normalized_condition in seen_conditions:
            raise ContractSubsetComparisonError(
                f"Duplicate condition name: {normalized_condition!r}"
            )
        normalized_conditions.append(normalized_condition)
        seen_conditions.add(normalized_condition)

    return tuple(normalized_conditions)


__all__ = [
    "CONTRACT_SUBSET_PER_CONDITION_CSV_ARTIFACTS",
    "CONTRACT_SUBSET_PER_CONDITION_JSON_ARTIFACTS",
    "CONTRACT_SUBSET_ROOT_ARTIFACTS",
    "ContractSubsetComparisonError",
    "build_contract_subset_comparison_specs",
    "compare_contract_subset",
]
