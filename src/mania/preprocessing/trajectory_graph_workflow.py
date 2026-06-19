"""Dependency-free preprocessing graph workflow planning contracts."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

from mania.preprocessing.input_manifest import PreprocessingInputManifest
from mania.preprocessing.path_validation import (
    PreprocessingPathValidationReport,
)

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
_MANIFEST_LOAD_EXCEPTION_NAMES = (
    "FileNotFoundError",
    "IsADirectoryError",
    "ValueError",
)
_MANIFEST_CONTRACT_EXCEPTION_NAME = "ValidationError"


class _ManifestLoader(Protocol):
    def __call__(self, path: str | Path) -> PreprocessingInputManifest: ...


class _ManifestPathValidator(Protocol):
    def __call__(
        self,
        manifest: PreprocessingInputManifest,
        *,
        base_dir: str | Path | None = None,
        check_output_root: bool = False,
    ) -> PreprocessingPathValidationReport: ...


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
class PreprocessingGraphWorkflowManifestReadinessIssue:
    """One deterministic local manifest readiness issue."""

    kind: str
    message: str
    field: str | None = None
    condition_name: str | None = None
    path: Path | None = None
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
            "condition_name",
            _optional_non_empty_string(
                self.condition_name,
                "condition_name",
            ),
        )
        _require_optional_path(self.path, "path")
        object.__setattr__(
            self,
            "value",
            _optional_non_empty_string(self.value, "value"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe readiness issue dictionary."""
        return {
            "kind": self.kind,
            "message": self.message,
            "field": self.field,
            "condition_name": self.condition_name,
            "path": _optional_path_string(self.path),
            "value": self.value,
        }


@dataclass(frozen=True)
class PreprocessingGraphWorkflowManifestReadinessResult:
    """Local manifest readiness metadata before workflow runtime loading."""

    manifest_path: Path
    manifest_loaded: bool
    manifest_paths_valid: bool
    condition_names: tuple[str, ...]
    expected_condition_count: int | None = None
    input_paths: tuple[Path, ...] = ()
    issues: tuple[PreprocessingGraphWorkflowManifestReadinessIssue, ...] = ()

    def __post_init__(self) -> None:
        _require_path(self.manifest_path, "manifest_path")
        _require_bool(self.manifest_loaded, "manifest_loaded")
        _require_bool(self.manifest_paths_valid, "manifest_paths_valid")
        if not isinstance(self.condition_names, tuple):
            raise ValueError("condition_names must be a tuple of strings")
        object.__setattr__(
            self,
            "condition_names",
            tuple(
                _non_empty_string(condition_name, "condition_names")
                for condition_name in self.condition_names
            ),
        )
        if self.expected_condition_count is not None:
            _require_non_negative_int(
                self.expected_condition_count,
                "expected_condition_count",
            )
        if not isinstance(self.input_paths, tuple):
            raise ValueError("input_paths must be a tuple of Path")
        for input_path in self.input_paths:
            _require_path(input_path, "input_paths")
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "issues must be a tuple of "
                "PreprocessingGraphWorkflowManifestReadinessIssue"
            )
        for issue in self.issues:
            if not isinstance(
                issue,
                PreprocessingGraphWorkflowManifestReadinessIssue,
            ):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingGraphWorkflowManifestReadinessIssue"
                )

    @property
    def passed(self) -> bool:
        """Return whether the manifest is ready for later runtime loading."""
        return (
            self.manifest_loaded
            and self.manifest_paths_valid
            and self.issues == ()
        )

    @property
    def issue_count(self) -> int:
        """Return the number of readiness issues."""
        return len(self.issues)

    @property
    def condition_count(self) -> int:
        """Return the number of manifest conditions reported."""
        return len(self.condition_names)

    @property
    def input_path_count(self) -> int:
        """Return the number of manifest-declared local input paths checked."""
        return len(self.input_paths)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe readiness result dictionary."""
        return {
            "manifest_path": str(self.manifest_path),
            "manifest_loaded": self.manifest_loaded,
            "manifest_paths_valid": self.manifest_paths_valid,
            "condition_names": list(self.condition_names),
            "condition_count": self.condition_count,
            "expected_condition_count": self.expected_condition_count,
            "input_paths": [str(input_path) for input_path in self.input_paths],
            "input_path_count": self.input_path_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_count": self.issue_count,
            "passed": self.passed,
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


def check_preprocessing_graph_workflow_manifest_readiness(
    manifest_path: str | Path,
    *,
    expected_condition_names: Iterable[str] | None = ("normal", "tumor"),
) -> PreprocessingGraphWorkflowManifestReadinessResult:
    """Check local manifest readiness without loading runtime objects."""
    normalized_manifest_path = Path(manifest_path)
    expected_names = _normalize_expected_condition_names(
        expected_condition_names
    )
    expected_count = (
        None if expected_names is None else len(expected_names)
    )

    if not normalized_manifest_path.exists():
        return PreprocessingGraphWorkflowManifestReadinessResult(
            manifest_path=normalized_manifest_path,
            manifest_loaded=False,
            manifest_paths_valid=False,
            condition_names=(),
            expected_condition_count=expected_count,
            issues=(
                PreprocessingGraphWorkflowManifestReadinessIssue(
                    kind="manifest_path_missing",
                    message=(
                        "Manifest path does not exist: "
                        f"{normalized_manifest_path}"
                    ),
                    field="manifest_path",
                    path=normalized_manifest_path,
                ),
            ),
        )

    if normalized_manifest_path.is_dir():
        return PreprocessingGraphWorkflowManifestReadinessResult(
            manifest_path=normalized_manifest_path,
            manifest_loaded=False,
            manifest_paths_valid=False,
            condition_names=(),
            expected_condition_count=expected_count,
            issues=(
                PreprocessingGraphWorkflowManifestReadinessIssue(
                    kind="manifest_path_is_directory",
                    message=(
                        "Manifest path is a directory: "
                        f"{normalized_manifest_path}"
                    ),
                    field="manifest_path",
                    path=normalized_manifest_path,
                ),
            ),
        )

    try:
        manifest = _manifest_loader()(normalized_manifest_path)
    except Exception as exc:
        return PreprocessingGraphWorkflowManifestReadinessResult(
            manifest_path=normalized_manifest_path,
            manifest_loaded=False,
            manifest_paths_valid=False,
            condition_names=(),
            expected_condition_count=expected_count,
            issues=(
                _manifest_load_issue(normalized_manifest_path, exc),
            ),
        )

    condition_names = manifest.condition_names()

    try:
        validation_report = _manifest_path_validator()(
            manifest,
            base_dir=normalized_manifest_path.parent,
        )
    except Exception as exc:
        return PreprocessingGraphWorkflowManifestReadinessResult(
            manifest_path=normalized_manifest_path,
            manifest_loaded=True,
            manifest_paths_valid=False,
            condition_names=condition_names,
            expected_condition_count=expected_count,
            issues=(
                PreprocessingGraphWorkflowManifestReadinessIssue(
                    kind="unexpected_error",
                    message=(
                        "Manifest path validation failed unexpectedly: "
                        f"{exc.__class__.__name__}"
                    ),
                    field="manifest_paths",
                ),
            ),
        )

    issues = list(_path_validation_issues(validation_report))
    input_paths = tuple(
        checked_path.path for checked_path in validation_report.checked_paths
    )
    if expected_names is not None:
        issues.extend(
            _condition_readiness_issues(
                condition_names=condition_names,
                expected_condition_names=expected_names,
            )
        )

    return PreprocessingGraphWorkflowManifestReadinessResult(
        manifest_path=normalized_manifest_path,
        manifest_loaded=True,
        manifest_paths_valid=validation_report.passed,
        condition_names=condition_names,
        expected_condition_count=expected_count,
        input_paths=input_paths,
        issues=tuple(issues),
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


def _require_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")


def _normalize_expected_condition_names(
    expected_condition_names: Iterable[str] | None,
) -> tuple[str, ...] | None:
    if expected_condition_names is None:
        return None
    normalized_names: list[str] = []
    for condition_name in expected_condition_names:
        normalized_names.append(
            _non_empty_string(
                condition_name,
                "expected_condition_names",
            )
        )
    return tuple(normalized_names)


def _manifest_loader() -> _ManifestLoader:
    module = _import_preprocessing_module("input_" + "manifest")
    return cast(
        _ManifestLoader,
        getattr(module, "load_" + "preprocessing_input_manifest"),
    )


def _manifest_path_validator() -> _ManifestPathValidator:
    module = _import_preprocessing_module("path_" + "validation")
    return cast(
        _ManifestPathValidator,
        getattr(module, "validate_" + "preprocessing_manifest_paths"),
    )


def _import_preprocessing_module(module_name: str) -> ModuleType:
    return importlib.import_module(f"mania.preprocessing.{module_name}")


def _manifest_load_issue(
    manifest_path: Path,
    exc: Exception,
) -> PreprocessingGraphWorkflowManifestReadinessIssue:
    exception_name = exc.__class__.__name__
    if exception_name == _MANIFEST_CONTRACT_EXCEPTION_NAME:
        kind = "manifest_contract_invalid"
        message = "Manifest does not conform to the preprocessing contract."
    elif exception_name in _MANIFEST_LOAD_EXCEPTION_NAMES:
        kind = "manifest_load_failed"
        message = f"Manifest could not be loaded: {exception_name}."
    else:
        kind = "unexpected_error"
        message = f"Manifest readiness failed unexpectedly: {exception_name}."
    return PreprocessingGraphWorkflowManifestReadinessIssue(
        kind=kind,
        message=message,
        field="manifest_path",
        path=manifest_path,
    )


def _path_validation_issues(
    validation_report: PreprocessingPathValidationReport,
) -> tuple[PreprocessingGraphWorkflowManifestReadinessIssue, ...]:
    issues: list[PreprocessingGraphWorkflowManifestReadinessIssue] = []
    for path_issue in validation_report.issues:
        if path_issue.kind == "missing":
            kind = "local_path_missing"
            message = f"Declared local file path does not exist: {path_issue.path}"
        elif path_issue.kind in {"not_file", "not_directory"}:
            kind = "local_path_is_directory"
            message = f"Declared local path has the wrong type: {path_issue.path}"
        else:
            kind = "manifest_path_validation_failed"
            message = f"Declared local path failed validation: {path_issue.path}"
        issues.append(
            PreprocessingGraphWorkflowManifestReadinessIssue(
                kind=kind,
                message=message,
                field=path_issue.field,
                condition_name=path_issue.condition,
                path=path_issue.path,
            )
        )
    return tuple(issues)


def _condition_readiness_issues(
    *,
    condition_names: tuple[str, ...],
    expected_condition_names: tuple[str, ...],
) -> tuple[PreprocessingGraphWorkflowManifestReadinessIssue, ...]:
    issues: list[PreprocessingGraphWorkflowManifestReadinessIssue] = []
    if len(condition_names) != len(expected_condition_names):
        issues.append(
            PreprocessingGraphWorkflowManifestReadinessIssue(
                kind="condition_count_mismatch",
                message=(
                    "Manifest condition count does not match the expected "
                    "condition count."
                ),
                field="conditions",
                value=(
                    f"expected={len(expected_condition_names)},"
                    f"actual={len(condition_names)}"
                ),
            )
        )
    existing_names = set(condition_names)
    for expected_condition_name in expected_condition_names:
        if expected_condition_name not in existing_names:
            issues.append(
                PreprocessingGraphWorkflowManifestReadinessIssue(
                    kind="condition_missing",
                    message=(
                        "Expected condition is missing from manifest: "
                        f"{expected_condition_name}"
                    ),
                    field="conditions",
                    condition_name=expected_condition_name,
                )
            )
    return tuple(issues)


__all__ = [
    "PreprocessingGraphWorkflowManifestReadinessIssue",
    "PreprocessingGraphWorkflowManifestReadinessResult",
    "PreprocessingGraphWorkflowIssue",
    "PreprocessingGraphWorkflowOptions",
    "PreprocessingGraphWorkflowOutputLayout",
    "PreprocessingGraphWorkflowPlan",
    "build_preprocessing_graph_workflow_plan",
    "check_preprocessing_graph_workflow_manifest_readiness",
]
