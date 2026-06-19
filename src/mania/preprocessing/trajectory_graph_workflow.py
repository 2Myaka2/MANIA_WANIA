"""Dependency-free preprocessing graph workflow planning contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_CURRENT_REFERENCE_SEMANTICS = "MANIA_analysis_v1_2"
_DEFAULT_RUN_NAME = "preprocessing_graph_export"

_OPTION_BOOL_FIELDS = (
    "overwrite",
    "include_rg",
    "include_contacts",
    "include_graph_export",
    "include_diagnostics",
    "enable_reference_comparison",
)
_OPTION_REFERENCE_PATH_FIELDS = (
    "reference_nodes_csv_path",
    "reference_edges_csv_path",
    "reference_graph_json_path",
)
_OUTPUT_LAYOUT_PATH_FIELDS = (
    "output_dir",
    "rg_timeseries_csv_path",
    "contacts_perframe_csv_path",
    "contact_edges_csv_path",
    "graph_nodes_csv_path",
    "graph_edges_csv_path",
    "graph_json_path",
    "diagnostics_report_json_path",
    "reference_comparison_json_path",
)
_FOUNDATIONAL_STEPS = (
    "load_manifest",
    "validate_manifest_paths",
    "load_condition_runtimes",
)
_GRAPH_EXPORT_STEPS = (
    "build_graph_mapping",
    "write_graph_nodes_csv",
    "write_graph_edges_csv",
    "validate_graph_csvs",
    "write_graph_json",
    "build_graph_export_bundle",
)
_DIAGNOSTICS_STEPS = (
    "run_graph_diagnostics",
    "build_graph_diagnostics_report",
)
_REFERENCE_COMPARISON_STEPS = (
    "validate_reference_comparison_input",
    "compare_reference_graph_artifacts",
)


@dataclass(frozen=True)
class PreprocessingGraphWorkflowOptions:
    """Run options for future preprocessing graph export orchestration."""

    manifest_path: Path
    output_dir: Path
    run_name: str = _DEFAULT_RUN_NAME
    overwrite: bool = False
    include_rg: bool = True
    include_contacts: bool = True
    include_graph_export: bool = True
    include_diagnostics: bool = True
    enable_reference_comparison: bool = False
    reference_nodes_csv_path: Path | None = None
    reference_edges_csv_path: Path | None = None
    reference_graph_json_path: Path | None = None
    reference_semantics: str = _CURRENT_REFERENCE_SEMANTICS

    def __post_init__(self) -> None:
        _require_path(self.manifest_path, "manifest_path")
        _require_path(self.output_dir, "output_dir")
        object.__setattr__(
            self,
            "run_name",
            _non_empty_string(self.run_name, "run_name"),
        )
        for field_name in _OPTION_BOOL_FIELDS:
            _require_bool(getattr(self, field_name), field_name)
        for field_name in _OPTION_REFERENCE_PATH_FIELDS:
            _require_optional_path(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "reference_semantics",
            _non_empty_string(self.reference_semantics, "reference_semantics"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe workflow options."""
        return {
            "manifest_path": str(self.manifest_path),
            "output_dir": str(self.output_dir),
            "run_name": self.run_name,
            "overwrite": self.overwrite,
            "include_rg": self.include_rg,
            "include_contacts": self.include_contacts,
            "include_graph_export": self.include_graph_export,
            "include_diagnostics": self.include_diagnostics,
            "enable_reference_comparison": self.enable_reference_comparison,
            "reference_nodes_csv_path": _optional_path_string(
                self.reference_nodes_csv_path
            ),
            "reference_edges_csv_path": _optional_path_string(
                self.reference_edges_csv_path
            ),
            "reference_graph_json_path": _optional_path_string(
                self.reference_graph_json_path
            ),
            "reference_semantics": self.reference_semantics,
        }


@dataclass(frozen=True)
class PreprocessingGraphWorkflowOutputLayout:
    """Deterministic planned output paths for future workflow execution."""

    output_dir: Path
    run_name: str
    rg_timeseries_csv_path: Path
    contacts_perframe_csv_path: Path
    contact_edges_csv_path: Path
    graph_nodes_csv_path: Path
    graph_edges_csv_path: Path
    graph_json_path: Path
    diagnostics_report_json_path: Path
    reference_comparison_json_path: Path

    def __post_init__(self) -> None:
        for field_name in _OUTPUT_LAYOUT_PATH_FIELDS:
            _require_path(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "run_name",
            _non_empty_string(self.run_name, "run_name"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe output layout metadata."""
        return {
            "output_dir": str(self.output_dir),
            "run_name": self.run_name,
            "rg_timeseries_csv_path": str(self.rg_timeseries_csv_path),
            "contacts_perframe_csv_path": str(
                self.contacts_perframe_csv_path
            ),
            "contact_edges_csv_path": str(self.contact_edges_csv_path),
            "graph_nodes_csv_path": str(self.graph_nodes_csv_path),
            "graph_edges_csv_path": str(self.graph_edges_csv_path),
            "graph_json_path": str(self.graph_json_path),
            "diagnostics_report_json_path": str(
                self.diagnostics_report_json_path
            ),
            "reference_comparison_json_path": str(
                self.reference_comparison_json_path
            ),
        }


@dataclass(frozen=True)
class PreprocessingGraphWorkflowIssue:
    """One deterministic workflow planning issue."""

    kind: str
    message: str
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
            "field",
            _optional_non_empty_string(self.field, "field"),
        )
        object.__setattr__(
            self,
            "value",
            _optional_non_empty_string(self.value, "value"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe issue dictionary."""
        return {
            "kind": self.kind,
            "message": self.message,
            "field": self.field,
            "value": self.value,
        }


@dataclass(frozen=True)
class PreprocessingGraphWorkflowPlan:
    """In-memory plan for future preprocessing graph export orchestration."""

    options: PreprocessingGraphWorkflowOptions
    output_layout: PreprocessingGraphWorkflowOutputLayout
    planned_steps: tuple[str, ...]
    issues: tuple[PreprocessingGraphWorkflowIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.options, PreprocessingGraphWorkflowOptions):
            raise ValueError(
                "options must be PreprocessingGraphWorkflowOptions"
            )
        if not isinstance(
            self.output_layout,
            PreprocessingGraphWorkflowOutputLayout,
        ):
            raise ValueError(
                "output_layout must be "
                "PreprocessingGraphWorkflowOutputLayout"
            )
        if not isinstance(self.planned_steps, tuple):
            raise ValueError("planned_steps must be a tuple of strings")
        object.__setattr__(
            self,
            "planned_steps",
            tuple(
                _non_empty_string(step, "planned_steps")
                for step in self.planned_steps
            ),
        )
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "issues must be a tuple of PreprocessingGraphWorkflowIssue"
            )
        for issue in self.issues:
            if not isinstance(issue, PreprocessingGraphWorkflowIssue):
                raise ValueError(
                    "issues must contain PreprocessingGraphWorkflowIssue"
                )

    @property
    def passed(self) -> bool:
        """Return whether the workflow plan has no planning issues."""
        return self.issues == ()

    @property
    def issue_count(self) -> int:
        """Return the number of planning issues."""
        return len(self.issues)

    @property
    def planned_step_count(self) -> int:
        """Return the number of planned step names."""
        return len(self.planned_steps)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe workflow plan dictionary."""
        return {
            "options": self.options.to_dict(),
            "output_layout": self.output_layout.to_dict(),
            "planned_steps": list(self.planned_steps),
            "planned_step_count": self.planned_step_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_count": self.issue_count,
            "passed": self.passed,
        }


def build_preprocessing_graph_workflow_plan(
    options: PreprocessingGraphWorkflowOptions,
) -> PreprocessingGraphWorkflowPlan:
    """Build an in-memory workflow plan without executing any step."""
    if not isinstance(options, PreprocessingGraphWorkflowOptions):
        raise ValueError("options must be PreprocessingGraphWorkflowOptions")

    output_layout = _build_output_layout(options)
    planned_steps = _build_planned_steps(options)
    issues = _build_planning_issues(options)

    return PreprocessingGraphWorkflowPlan(
        options=options,
        output_layout=output_layout,
        planned_steps=planned_steps,
        issues=issues,
    )


def _build_output_layout(
    options: PreprocessingGraphWorkflowOptions,
) -> PreprocessingGraphWorkflowOutputLayout:
    output_dir = options.output_dir
    return PreprocessingGraphWorkflowOutputLayout(
        output_dir=output_dir,
        run_name=options.run_name,
        rg_timeseries_csv_path=output_dir / "rg" / "rg_timeseries.csv",
        contacts_perframe_csv_path=(
            output_dir / "contacts" / "contacts_perframe.csv"
        ),
        contact_edges_csv_path=output_dir / "contacts" / "contact_edges.csv",
        graph_nodes_csv_path=output_dir / "graph" / "nodes.csv",
        graph_edges_csv_path=output_dir / "graph" / "edges.csv",
        graph_json_path=output_dir / "graph" / "graph.json",
        diagnostics_report_json_path=(
            output_dir / "reports" / "graph_diagnostics_report.json"
        ),
        reference_comparison_json_path=(
            output_dir / "reports" / "graph_reference_comparison.json"
        ),
    )


def _build_planned_steps(
    options: PreprocessingGraphWorkflowOptions,
) -> tuple[str, ...]:
    planned_steps: list[str] = list(_FOUNDATIONAL_STEPS)

    if options.include_rg:
        planned_steps.append("compute_rg")
    if options.include_contacts:
        planned_steps.append("compute_contacts")
    if options.include_graph_export:
        planned_steps.extend(_GRAPH_EXPORT_STEPS)
    if options.include_diagnostics and options.include_graph_export:
        planned_steps.extend(_DIAGNOSTICS_STEPS)
    if (
        options.enable_reference_comparison
        and options.include_graph_export
    ):
        planned_steps.extend(_REFERENCE_COMPARISON_STEPS)

    return tuple(planned_steps)


def _build_planning_issues(
    options: PreprocessingGraphWorkflowOptions,
) -> tuple[PreprocessingGraphWorkflowIssue, ...]:
    issues: list[PreprocessingGraphWorkflowIssue] = []

    if options.include_graph_export and not options.include_contacts:
        issues.append(
            PreprocessingGraphWorkflowIssue(
                kind="stage_disabled",
                field="include_contacts",
                value=str(options.include_contacts),
                message=(
                    "graph export depends on contacts; enable contacts or "
                    "disable graph export."
                ),
            )
        )

    if options.include_diagnostics and not options.include_graph_export:
        issues.append(
            PreprocessingGraphWorkflowIssue(
                kind="stage_disabled",
                field="include_graph_export",
                value=str(options.include_graph_export),
                message=(
                    "diagnostics depend on graph export; enable graph export "
                    "or disable diagnostics."
                ),
            )
        )

    if (
        options.enable_reference_comparison
        and not options.include_graph_export
    ):
        issues.append(
            PreprocessingGraphWorkflowIssue(
                kind="stage_disabled",
                field="include_graph_export",
                value=str(options.include_graph_export),
                message=(
                    "reference comparison depends on graph export; enable "
                    "graph export or disable reference comparison."
                ),
            )
        )

    if options.enable_reference_comparison:
        missing_fields = _missing_reference_path_fields(options)
        if missing_fields:
            issues.append(
                PreprocessingGraphWorkflowIssue(
                    kind="reference_paths_required",
                    field="reference_paths",
                    value=",".join(missing_fields),
                    message=(
                        "reference comparison requires explicit reference "
                        "artifact paths: "
                        + ", ".join(missing_fields)
                        + "."
                    ),
                )
            )

    if _all_workflow_targets_disabled(options):
        issues.append(
            PreprocessingGraphWorkflowIssue(
                kind="no_workflow_targets_enabled",
                field="workflow_targets",
                message="At least one workflow target must be enabled.",
            )
        )

    return tuple(issues)


def _missing_reference_path_fields(
    options: PreprocessingGraphWorkflowOptions,
) -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in _OPTION_REFERENCE_PATH_FIELDS
        if getattr(options, field_name) is None
    )


def _all_workflow_targets_disabled(
    options: PreprocessingGraphWorkflowOptions,
) -> bool:
    return (
        not options.include_rg
        and not options.include_contacts
        and not options.include_graph_export
        and not options.include_diagnostics
        and not options.enable_reference_comparison
    )


def _require_path(value: object, field_name: str) -> None:
    if not isinstance(value, Path):
        raise ValueError(f"{field_name} must be Path")


def _require_optional_path(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, Path):
        raise ValueError(f"{field_name} must be None or Path")


def _require_bool(value: object, field_name: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    stripped = value.strip()
    if stripped == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


def _optional_non_empty_string(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field_name)


def _optional_path_string(value: Path | None) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "PreprocessingGraphWorkflowIssue",
    "PreprocessingGraphWorkflowOptions",
    "PreprocessingGraphWorkflowOutputLayout",
    "PreprocessingGraphWorkflowPlan",
    "build_preprocessing_graph_workflow_plan",
]
