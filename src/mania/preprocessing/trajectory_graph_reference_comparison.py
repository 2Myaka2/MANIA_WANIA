"""Input contract for future preprocessing graph reference comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mania.preprocessing.trajectory_graph_export import (
    PreprocessingGraphExportBundleIssue,
    PreprocessingGraphExportBundleResult,
    build_preprocessing_graph_export_bundle,
)

_CURRENT_REFERENCE_SEMANTICS = "MANIA_analysis_v1_2"
_BOOLEAN_FIELDS = (
    "require_matching_condition",
    "require_matching_schema_version",
    "compare_nodes",
    "compare_edges",
    "compare_graph_json",
)
_PATH_FIELDS = (
    "generated_nodes_csv_path",
    "generated_edges_csv_path",
    "generated_graph_json_path",
    "reference_nodes_csv_path",
    "reference_edges_csv_path",
    "reference_graph_json_path",
)
_GENERATED_ARTIFACT_FIELDS = {
    "nodes_csv": "generated_nodes_csv_path",
    "edges_csv": "generated_edges_csv_path",
    "graph_json": "generated_graph_json_path",
}
_REFERENCE_ARTIFACT_FIELDS = {
    "nodes_csv": "reference_nodes_csv_path",
    "edges_csv": "reference_edges_csv_path",
    "graph_json": "reference_graph_json_path",
}
_PASSTHROUGH_BUNDLE_ISSUES = frozenset(
    {
        "invalid_path",
        "path_missing",
        "path_is_directory",
    }
)


@dataclass(frozen=True)
class PreprocessingGraphReferenceComparisonOptions:
    """Options for future generated-vs-reference graph comparison."""

    reference_semantics: str = _CURRENT_REFERENCE_SEMANTICS
    condition: str | None = None
    require_matching_condition: bool = True
    require_matching_schema_version: bool = True
    compare_nodes: bool = True
    compare_edges: bool = True
    compare_graph_json: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reference_semantics",
            _non_empty_string(self.reference_semantics, "reference_semantics"),
        )
        object.__setattr__(
            self,
            "condition",
            _optional_non_empty_string(self.condition, "condition"),
        )
        for field_name in _BOOLEAN_FIELDS:
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe options dictionary."""
        return {
            "reference_semantics": self.reference_semantics,
            "condition": self.condition,
            "require_matching_condition": self.require_matching_condition,
            "require_matching_schema_version": (
                self.require_matching_schema_version
            ),
            "compare_nodes": self.compare_nodes,
            "compare_edges": self.compare_edges,
            "compare_graph_json": self.compare_graph_json,
        }


@dataclass(frozen=True)
class PreprocessingGraphReferenceComparisonInput:
    """Explicit generated/reference graph artifact paths."""

    generated_nodes_csv_path: Path
    generated_edges_csv_path: Path
    generated_graph_json_path: Path
    reference_nodes_csv_path: Path
    reference_edges_csv_path: Path
    reference_graph_json_path: Path
    options: PreprocessingGraphReferenceComparisonOptions = field(
        default_factory=PreprocessingGraphReferenceComparisonOptions
    )

    def __post_init__(self) -> None:
        for field_name in _PATH_FIELDS:
            if not isinstance(getattr(self, field_name), Path):
                raise ValueError(f"{field_name} must be Path")
        if not isinstance(
            self.options,
            PreprocessingGraphReferenceComparisonOptions,
        ):
            raise ValueError(
                "options must be "
                "PreprocessingGraphReferenceComparisonOptions"
            )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe input dictionary."""
        return {
            "generated_nodes_csv_path": str(self.generated_nodes_csv_path),
            "generated_edges_csv_path": str(self.generated_edges_csv_path),
            "generated_graph_json_path": str(self.generated_graph_json_path),
            "reference_nodes_csv_path": str(self.reference_nodes_csv_path),
            "reference_edges_csv_path": str(self.reference_edges_csv_path),
            "reference_graph_json_path": str(self.reference_graph_json_path),
            "options": self.options.to_dict(),
        }


@dataclass(frozen=True)
class PreprocessingGraphReferenceComparisonIssue:
    """One deterministic graph reference comparison input issue."""

    kind: str
    message: str
    artifact_group: str | None = None
    artifact_kind: str | None = None
    field: str | None = None
    value: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _non_empty_string(self.kind, "kind"))
        object.__setattr__(
            self,
            "message",
            _non_empty_string(self.message, "message"),
        )
        object.__setattr__(
            self,
            "artifact_group",
            _optional_non_empty_string(self.artifact_group, "artifact_group"),
        )
        object.__setattr__(
            self,
            "artifact_kind",
            _optional_non_empty_string(self.artifact_kind, "artifact_kind"),
        )
        object.__setattr__(
            self,
            "field",
            _optional_non_empty_string(self.field, "field"),
        )
        if self.value is not None and not isinstance(self.value, str):
            raise ValueError("value must be a string or None")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe issue dictionary."""
        return {
            "kind": self.kind,
            "message": self.message,
            "artifact_group": self.artifact_group,
            "artifact_kind": self.artifact_kind,
            "field": self.field,
            "value": self.value,
        }


@dataclass(frozen=True)
class PreprocessingGraphReferenceComparisonInputValidationResult:
    """Readiness report for future graph reference comparison."""

    comparison_input: PreprocessingGraphReferenceComparisonInput
    generated_node_count: int
    generated_edge_count: int
    reference_node_count: int
    reference_edge_count: int
    generated_condition: str | None = None
    reference_condition: str | None = None
    generated_schema_version: str | None = None
    reference_schema_version: str | None = None
    issues: tuple[PreprocessingGraphReferenceComparisonIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(
            self.comparison_input,
            PreprocessingGraphReferenceComparisonInput,
        ):
            raise ValueError(
                "comparison_input must be "
                "PreprocessingGraphReferenceComparisonInput"
            )
        for field_name in (
            "generated_node_count",
            "generated_edge_count",
            "reference_node_count",
            "reference_edge_count",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)
        for field_name in (
            "generated_condition",
            "reference_condition",
            "generated_schema_version",
            "reference_schema_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_non_empty_string(getattr(self, field_name), field_name),
            )
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "issues must be a tuple of "
                "PreprocessingGraphReferenceComparisonIssue"
            )
        for issue in self.issues:
            if not isinstance(
                issue,
                PreprocessingGraphReferenceComparisonIssue,
            ):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingGraphReferenceComparisonIssue"
                )

    @property
    def passed(self) -> bool:
        """Return whether validation found no issues."""
        return self.issues == ()

    @property
    def issue_count(self) -> int:
        """Return the number of validation issues."""
        return len(self.issues)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe validation report."""
        return {
            "comparison_input": self.comparison_input.to_dict(),
            "passed": self.passed,
            "issue_count": self.issue_count,
            "generated_node_count": self.generated_node_count,
            "generated_edge_count": self.generated_edge_count,
            "reference_node_count": self.reference_node_count,
            "reference_edge_count": self.reference_edge_count,
            "generated_condition": self.generated_condition,
            "reference_condition": self.reference_condition,
            "generated_schema_version": self.generated_schema_version,
            "reference_schema_version": self.reference_schema_version,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_preprocessing_graph_reference_comparison_input(
    comparison_input: PreprocessingGraphReferenceComparisonInput,
) -> PreprocessingGraphReferenceComparisonInputValidationResult:
    """Validate graph artifact readiness without comparing graph contents."""
    if not isinstance(
        comparison_input,
        PreprocessingGraphReferenceComparisonInput,
    ):
        raise ValueError(
            "comparison_input must be "
            "PreprocessingGraphReferenceComparisonInput"
        )

    issues: list[PreprocessingGraphReferenceComparisonIssue] = []
    options = comparison_input.options
    try:
        _validate_options(options)
    except ValueError:
        issues.append(
            PreprocessingGraphReferenceComparisonIssue(
                kind="invalid_options",
                message="Graph reference comparison options are invalid.",
                field="options",
            )
        )

    generated_bundle = build_preprocessing_graph_export_bundle(
        comparison_input.generated_nodes_csv_path,
        comparison_input.generated_edges_csv_path,
        comparison_input.generated_graph_json_path,
    )
    issues.extend(_bundle_issues(generated_bundle, artifact_group="generated"))

    reference_bundle = build_preprocessing_graph_export_bundle(
        comparison_input.reference_nodes_csv_path,
        comparison_input.reference_edges_csv_path,
        comparison_input.reference_graph_json_path,
    )
    issues.extend(_bundle_issues(reference_bundle, artifact_group="reference"))

    if options.reference_semantics != _CURRENT_REFERENCE_SEMANTICS:
        issues.append(
            PreprocessingGraphReferenceComparisonIssue(
                kind="reference_semantics_invalid",
                message="Graph reference semantics must be MANIA_analysis_v1_2.",
                field="options.reference_semantics",
                value=options.reference_semantics,
            )
        )

    if (
        not options.compare_nodes
        and not options.compare_edges
        and not options.compare_graph_json
    ):
        issues.append(
            PreprocessingGraphReferenceComparisonIssue(
                kind="comparison_target_disabled",
                message="At least one graph comparison target must be enabled.",
                field="options",
            )
        )

    _add_condition_issues(
        generated_condition=generated_bundle.condition,
        reference_condition=reference_bundle.condition,
        options=options,
        issues=issues,
    )
    _add_schema_version_issues(
        generated_schema_version=generated_bundle.schema_version,
        reference_schema_version=reference_bundle.schema_version,
        options=options,
        issues=issues,
    )

    return PreprocessingGraphReferenceComparisonInputValidationResult(
        comparison_input=comparison_input,
        generated_node_count=generated_bundle.node_count,
        generated_edge_count=generated_bundle.edge_count,
        reference_node_count=reference_bundle.node_count,
        reference_edge_count=reference_bundle.edge_count,
        generated_condition=generated_bundle.condition,
        reference_condition=reference_bundle.condition,
        generated_schema_version=generated_bundle.schema_version,
        reference_schema_version=reference_bundle.schema_version,
        issues=tuple(issues),
    )


def _validate_options(
    options: object,
) -> None:
    if not isinstance(options, PreprocessingGraphReferenceComparisonOptions):
        raise ValueError(
            "options must be PreprocessingGraphReferenceComparisonOptions"
        )
    PreprocessingGraphReferenceComparisonOptions(
        reference_semantics=options.reference_semantics,
        condition=options.condition,
        require_matching_condition=options.require_matching_condition,
        require_matching_schema_version=options.require_matching_schema_version,
        compare_nodes=options.compare_nodes,
        compare_edges=options.compare_edges,
        compare_graph_json=options.compare_graph_json,
    )


def _bundle_issues(
    bundle: PreprocessingGraphExportBundleResult,
    *,
    artifact_group: str,
) -> tuple[PreprocessingGraphReferenceComparisonIssue, ...]:
    artifact_fields = (
        _GENERATED_ARTIFACT_FIELDS
        if artifact_group == "generated"
        else _REFERENCE_ARTIFACT_FIELDS
    )
    return tuple(
        _bundle_issue_to_comparison_issue(
            issue,
            artifact_group=artifact_group,
            field=artifact_fields.get(issue.artifact_kind or ""),
        )
        for issue in bundle.issues
    )


def _bundle_issue_to_comparison_issue(
    issue: PreprocessingGraphExportBundleIssue,
    *,
    artifact_group: str,
    field: str | None,
) -> PreprocessingGraphReferenceComparisonIssue:
    if issue.kind in _PASSTHROUGH_BUNDLE_ISSUES:
        kind = issue.kind
    else:
        kind = f"{artifact_group}_bundle_invalid"
    return PreprocessingGraphReferenceComparisonIssue(
        kind=kind,
        message=(
            f"{artifact_group} graph export bundle issue: {issue.message}"
        ),
        artifact_group=artifact_group,
        artifact_kind=issue.artifact_kind,
        field=field or issue.field,
        value=issue.value,
    )


def _add_condition_issues(
    *,
    generated_condition: str | None,
    reference_condition: str | None,
    options: PreprocessingGraphReferenceComparisonOptions,
    issues: list[PreprocessingGraphReferenceComparisonIssue],
) -> None:
    if options.require_matching_condition:
        if generated_condition is None or reference_condition is None:
            issues.append(
                PreprocessingGraphReferenceComparisonIssue(
                    kind="condition_missing",
                    message=(
                        "Generated and reference graph conditions are required."
                    ),
                    field="condition",
                )
            )
        elif generated_condition != reference_condition:
            issues.append(
                PreprocessingGraphReferenceComparisonIssue(
                    kind="condition_mismatch",
                    message="Generated and reference graph conditions differ.",
                    field="condition",
                    value=f"{generated_condition}|{reference_condition}",
                )
            )

    expected_condition = options.condition
    if expected_condition is not None:
        if (
            generated_condition != expected_condition
            or reference_condition != expected_condition
        ):
            issues.append(
                PreprocessingGraphReferenceComparisonIssue(
                    kind="condition_mismatch",
                    message="Graph artifacts do not match the requested condition.",
                    field="options.condition",
                    value=expected_condition,
                )
            )


def _add_schema_version_issues(
    *,
    generated_schema_version: str | None,
    reference_schema_version: str | None,
    options: PreprocessingGraphReferenceComparisonOptions,
    issues: list[PreprocessingGraphReferenceComparisonIssue],
) -> None:
    if not options.require_matching_schema_version:
        return
    if (
        generated_schema_version is None
        or reference_schema_version is None
        or generated_schema_version != reference_schema_version
    ):
        issues.append(
            PreprocessingGraphReferenceComparisonIssue(
                kind="schema_version_mismatch",
                message="Generated and reference graph schema versions differ.",
                field="schema_version",
                value=(
                    f"{generated_schema_version}|{reference_schema_version}"
                ),
            )
        )


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_non_empty_string(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} must be None or a non-empty string")
    return value


def _require_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")


__all__ = [
    "PreprocessingGraphReferenceComparisonInput",
    "PreprocessingGraphReferenceComparisonInputValidationResult",
    "PreprocessingGraphReferenceComparisonIssue",
    "PreprocessingGraphReferenceComparisonOptions",
    "validate_preprocessing_graph_reference_comparison_input",
]
