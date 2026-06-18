"""Read-only diagnostics bridge for generated preprocessing graph artifacts."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mania.analysis.contract_graph import (
    ContractGraph,
    ContractGraphError,
    load_contract_graph,
)
from mania.analysis.graph_qc import GraphQCError, compute_graph_qc
from mania.preprocessing.trajectory_graph_export import (
    PreprocessingGraphExportBundleIssue,
    PreprocessingGraphExportBundleResult,
    build_preprocessing_graph_export_bundle,
)
from mania.validation.graph import GraphValidationError, validate_graph_json

_SUMMARY_VALUE_TYPES = (str, int, float, bool, type(None))
_GRAPH_EXPORT_BUNDLE_CHECK = "graph_export_bundle"
_GRAPH_JSON_VALIDATION_CHECK = "graph_json_validation"
_CONTRACT_GRAPH_LOAD_CHECK = "contract_graph_load"
_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK = "graph_structure_diagnostics"

_SummaryValue = str | int | float | bool | None


@dataclass(frozen=True)
class PreprocessingGraphDiagnosticsRunIssue:
    """One deterministic preprocessing graph diagnostics run issue."""

    kind: str
    message: str
    check_name: str | None = None
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
            "check_name",
            _optional_non_empty_string(self.check_name, "check_name"),
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
            "check_name": self.check_name,
            "field": self.field,
            "value": self.value,
        }


@dataclass(frozen=True)
class PreprocessingGraphDiagnosticsCheckResult:
    """One deterministic preprocessing graph diagnostics check result."""

    name: str
    passed: bool
    summary: Mapping[str, _SummaryValue]
    issues: tuple[PreprocessingGraphDiagnosticsRunIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _non_empty_string(self.name, "name"))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be bool")
        object.__setattr__(self, "summary", _summary_dict(self.summary))
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "issues must be a tuple of "
                "PreprocessingGraphDiagnosticsRunIssue"
            )
        for issue in self.issues:
            if not isinstance(issue, PreprocessingGraphDiagnosticsRunIssue):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingGraphDiagnosticsRunIssue"
                )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe check result dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "summary": dict(self.summary),
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class PreprocessingGraphDiagnosticsRunResult:
    """Lightweight run result for generated preprocessing graph diagnostics."""

    nodes_csv_path: Path
    edges_csv_path: Path
    graph_json_path: Path
    node_count: int
    edge_count: int
    checks: tuple[PreprocessingGraphDiagnosticsCheckResult, ...]
    issues: tuple[PreprocessingGraphDiagnosticsRunIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes_csv_path", Path(self.nodes_csv_path))
        object.__setattr__(self, "edges_csv_path", Path(self.edges_csv_path))
        object.__setattr__(self, "graph_json_path", Path(self.graph_json_path))
        _require_non_negative_int(self.node_count, "node_count")
        _require_non_negative_int(self.edge_count, "edge_count")
        if not isinstance(self.checks, tuple):
            raise ValueError(
                "checks must be a tuple of "
                "PreprocessingGraphDiagnosticsCheckResult"
            )
        for check in self.checks:
            if not isinstance(check, PreprocessingGraphDiagnosticsCheckResult):
                raise ValueError(
                    "checks must contain "
                    "PreprocessingGraphDiagnosticsCheckResult"
                )
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "issues must be a tuple of "
                "PreprocessingGraphDiagnosticsRunIssue"
            )
        for issue in self.issues:
            if not isinstance(issue, PreprocessingGraphDiagnosticsRunIssue):
                raise ValueError(
                    "issues must contain "
                    "PreprocessingGraphDiagnosticsRunIssue"
                )

    @property
    def passed(self) -> bool:
        """Return whether the run passed all checks without top-level issues."""
        return not self.issues and all(check.passed for check in self.checks)

    @property
    def issue_count(self) -> int:
        """Return the number of top-level run issues."""
        return len(self.issues)

    @property
    def check_count(self) -> int:
        """Return the number of executed or recorded checks."""
        return len(self.checks)

    @property
    def failed_check_count(self) -> int:
        """Return the number of failed checks."""
        return sum(1 for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe diagnostics run dictionary."""
        return {
            "nodes_csv_path": str(self.nodes_csv_path),
            "edges_csv_path": str(self.edges_csv_path),
            "graph_json_path": str(self.graph_json_path),
            "passed": self.passed,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "check_count": self.check_count,
            "failed_check_count": self.failed_check_count,
            "issue_count": self.issue_count,
            "checks": [check.to_dict() for check in self.checks],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def run_preprocessing_graph_diagnostics(
    nodes_csv_path: str | Path,
    edges_csv_path: str | Path,
    graph_json_path: str | Path,
) -> PreprocessingGraphDiagnosticsRunResult:
    """Run existing graph checks on generated Stage 14 graph artifacts."""
    bundle = build_preprocessing_graph_export_bundle(
        nodes_csv_path,
        edges_csv_path,
        graph_json_path,
    )
    checks: list[PreprocessingGraphDiagnosticsCheckResult] = [
        _graph_export_bundle_check(bundle)
    ]

    if not bundle.passed:
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="bundle_failed",
            message=(
                "Graph export bundle failed; downstream diagnostics were not run."
            ),
            check_name=_GRAPH_EXPORT_BUNDLE_CHECK,
            field="bundle.issues",
            value=str(bundle.issue_count),
        )
        return PreprocessingGraphDiagnosticsRunResult(
            nodes_csv_path=bundle.nodes_csv_path,
            edges_csv_path=bundle.edges_csv_path,
            graph_json_path=bundle.graph_json_path,
            node_count=bundle.node_count,
            edge_count=bundle.edge_count,
            checks=tuple(checks),
            issues=(issue,),
        )

    graph_condition, graph_json_check = _run_graph_json_validation(bundle)
    checks.append(graph_json_check)

    condition = graph_condition or bundle.condition
    graph, load_check = _run_contract_graph_load(bundle, condition)
    checks.append(load_check)

    structure_check = _run_graph_structure_diagnostics(graph)
    checks.append(structure_check)

    return PreprocessingGraphDiagnosticsRunResult(
        nodes_csv_path=bundle.nodes_csv_path,
        edges_csv_path=bundle.edges_csv_path,
        graph_json_path=bundle.graph_json_path,
        node_count=bundle.node_count,
        edge_count=bundle.edge_count,
        checks=tuple(checks),
        issues=(),
    )


def _graph_export_bundle_check(
    bundle: PreprocessingGraphExportBundleResult,
) -> PreprocessingGraphDiagnosticsCheckResult:
    return PreprocessingGraphDiagnosticsCheckResult(
        name=_GRAPH_EXPORT_BUNDLE_CHECK,
        passed=bundle.passed,
        summary={
            "bundle_passed": bundle.passed,
            "node_count": bundle.node_count,
            "edge_count": bundle.edge_count,
            "artifact_count": bundle.artifact_count,
            "issue_count": bundle.issue_count,
            "csv_validation_passed": bundle.csv_validation_passed,
            "csv_validation_issue_count": bundle.csv_validation_issue_count,
            "condition": bundle.condition,
            "schema_version": bundle.schema_version,
        },
        issues=tuple(_bundle_issue_to_run_issue(issue) for issue in bundle.issues),
    )


def _bundle_issue_to_run_issue(
    issue: PreprocessingGraphExportBundleIssue,
) -> PreprocessingGraphDiagnosticsRunIssue:
    return PreprocessingGraphDiagnosticsRunIssue(
        kind=issue.kind,
        message=issue.message,
        check_name=_GRAPH_EXPORT_BUNDLE_CHECK,
        field=issue.field,
        value=issue.value,
    )


def _run_graph_json_validation(
    bundle: PreprocessingGraphExportBundleResult,
) -> tuple[str | None, PreprocessingGraphDiagnosticsCheckResult]:
    try:
        result = validate_graph_json(
            bundle.graph_json_path,
            expected_condition=bundle.condition,
        )
    except GraphValidationError as exc:
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="graph_validation_failed",
            message=str(exc),
            check_name=_GRAPH_JSON_VALIDATION_CHECK,
            field="graph_json_path",
        )
        return None, PreprocessingGraphDiagnosticsCheckResult(
            name=_GRAPH_JSON_VALIDATION_CHECK,
            passed=False,
            summary={"validated": False, "issue_count": 1},
            issues=(issue,),
        )
    return result.condition, PreprocessingGraphDiagnosticsCheckResult(
        name=_GRAPH_JSON_VALIDATION_CHECK,
        passed=True,
        summary={
            "validated": True,
            "condition": result.condition,
            "n_nodes_declared": result.n_nodes_declared,
            "n_edges_declared": result.n_edges_declared,
            "node_count": len(result.node_ids),
            "edge_count": result.edge_count,
            "missing_key_count": len(result.missing_keys),
            "duplicate_node_id_count": len(result.duplicate_node_ids),
        },
    )


def _run_contract_graph_load(
    bundle: PreprocessingGraphExportBundleResult,
    condition: str | None,
) -> tuple[ContractGraph | None, PreprocessingGraphDiagnosticsCheckResult]:
    if condition is None or condition.strip() == "":
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="diagnostic_unavailable",
            message="Contract graph loading requires a non-empty condition.",
            check_name=_CONTRACT_GRAPH_LOAD_CHECK,
            field="condition",
            value=condition,
        )
        return None, PreprocessingGraphDiagnosticsCheckResult(
            name=_CONTRACT_GRAPH_LOAD_CHECK,
            passed=False,
            summary={
                "loaded": False,
                "diagnostic_available": False,
                "issue_count": 1,
            },
            issues=(issue,),
        )

    try:
        graph = load_contract_graph(
            bundle.nodes_csv_path,
            bundle.edges_csv_path,
            condition=condition,
        )
    except ContractGraphError as exc:
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="graph_load_failed",
            message=str(exc),
            check_name=_CONTRACT_GRAPH_LOAD_CHECK,
            field="graph_csv_paths",
        )
        return None, PreprocessingGraphDiagnosticsCheckResult(
            name=_CONTRACT_GRAPH_LOAD_CHECK,
            passed=False,
            summary={
                "loaded": False,
                "diagnostic_available": True,
                "condition": condition,
                "issue_count": 1,
            },
            issues=(issue,),
        )

    return graph, PreprocessingGraphDiagnosticsCheckResult(
        name=_CONTRACT_GRAPH_LOAD_CHECK,
        passed=True,
        summary={
            "loaded": True,
            "condition": graph.condition,
            "node_count": graph.n_nodes,
            "edge_count": graph.n_edges,
            "isolated_node_count": len(graph.isolated_node_ids()),
        },
    )


def _run_graph_structure_diagnostics(
    graph: ContractGraph | None,
) -> PreprocessingGraphDiagnosticsCheckResult:
    if graph is None:
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="diagnostic_unavailable",
            message="Graph structure diagnostics require a loaded contract graph.",
            check_name=_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK,
            field="contract_graph",
        )
        return PreprocessingGraphDiagnosticsCheckResult(
            name=_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK,
            passed=False,
            summary={"diagnostic_available": False, "issue_count": 1},
            issues=(issue,),
        )

    try:
        qc_report = compute_graph_qc(graph)
    except GraphQCError as exc:
        issue = PreprocessingGraphDiagnosticsRunIssue(
            kind="diagnostic_failed",
            message=str(exc),
            check_name=_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK,
            field="graph",
        )
        return PreprocessingGraphDiagnosticsCheckResult(
            name=_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK,
            passed=False,
            summary={
                "diagnostic_available": True,
                "condition": graph.condition,
                "node_count": graph.n_nodes,
                "edge_count": graph.n_edges,
                "issue_count": 1,
            },
            issues=(issue,),
        )

    return PreprocessingGraphDiagnosticsCheckResult(
        name=_GRAPH_STRUCTURE_DIAGNOSTICS_CHECK,
        passed=qc_report.passed_basic_qc,
        summary={
            "diagnostic_available": True,
            "condition": graph.condition,
            "node_count": graph.n_nodes,
            "edge_count": graph.n_edges,
            "n_components": qc_report.n_components,
            "largest_component_size": qc_report.largest_component_size,
            "n_isolated_nodes": qc_report.n_isolated_nodes,
            "n_self_loops": len(qc_report.self_loop_edges),
            "n_duplicate_undirected_edge_keys": (
                len(qc_report.duplicate_undirected_edge_keys)
            ),
            "passed_basic_qc": qc_report.passed_basic_qc,
        },
    )


def _summary_dict(summary: Mapping[str, object]) -> dict[str, _SummaryValue]:
    if not isinstance(summary, Mapping):
        raise ValueError("summary must be a JSON-safe mapping")
    normalized: dict[str, _SummaryValue] = {}
    for key, value in summary.items():
        if not isinstance(key, str) or key.strip() == "":
            raise ValueError("summary keys must be non-empty strings")
        if not isinstance(value, _SUMMARY_VALUE_TYPES):
            raise ValueError("summary values must be JSON-safe scalars")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("summary float values must be finite")
        normalized[key] = value
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


def _optional_non_empty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field_name)


def _require_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")


__all__ = [
    "PreprocessingGraphDiagnosticsCheckResult",
    "PreprocessingGraphDiagnosticsRunIssue",
    "PreprocessingGraphDiagnosticsRunResult",
    "run_preprocessing_graph_diagnostics",
]
